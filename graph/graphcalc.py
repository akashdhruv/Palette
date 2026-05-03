"""Graphical calculator — type y=<expr> to plot, clear to reset."""

import copy
import math
import re
import tkinter as tk
from itertools import combinations

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
import sympy as sp


COLORS = [
    '#e74c3c', '#3498db', '#27ae60', '#f39c12',
    '#8e44ad', '#16a085', '#e67e22', '#2980b9',
]

_X = sp.Symbol('x')
_Y = sp.Symbol('y')


# ── Equation ─────────────────────────────────────────────────────────────────

class Equation:
    def __init__(self, name: str, raw: str, sym_expr, color: str,
                 implicit: bool = False, lhs_sym=None, rhs_sym=None):
        self.name = name
        self.raw = raw
        self.sym_expr = sym_expr  # explicit: f(x); implicit: lhs-rhs (=0)
        self.color = color
        self.implicit = implicit
        self._lhs_sym = lhs_sym
        self._rhs_sym = rhs_sym
        if implicit:
            self._fn = None
            self._fn2d = sp.lambdify((_X, _Y), sym_expr, modules='numpy')
            self._zero_fn2d = self._fn2d
        else:
            self._fn = sp.lambdify(_X, sym_expr, modules='numpy')
            self._fn2d = None
            self._zero_fn2d = sp.lambdify((_X, _Y), _Y - sym_expr,
                                           modules='numpy')

    @property
    def label(self) -> str:
        if self.implicit:
            return f'${sp.latex(self._lhs_sym)} = {sp.latex(self._rhs_sym)}$'
        return f'$y={sp.latex(self.sym_expr)}$'

    def evaluate(self, x_arr: np.ndarray) -> np.ndarray:
        if self.implicit:
            return None
        try:
            result = self._fn(x_arr)
            if np.isscalar(result):
                return np.full_like(x_arr, float(result), dtype=float)
            return np.asarray(result, dtype=float)
        except Exception:
            return np.full_like(x_arr, np.nan, dtype=float)

    def evaluate_2d(self, x_mesh: np.ndarray, y_mesh: np.ndarray) -> np.ndarray:
        try:
            result = self._fn2d(x_mesh, y_mesh)
            if np.isscalar(result):
                return np.full_like(x_mesh, float(result), dtype=float)
            return np.asarray(result, dtype=float)
        except Exception:
            return np.full_like(x_mesh, np.nan, dtype=float)


# ── Main app ─────────────────────────────────────────────────────────────────

class GraphCalcApp:
    def __init__(self, initial_equations=None):
        self.root = tk.Tk()
        self.root.title('Graph Calculator')
        self.root.configure(bg='#1a1a2e')
        self.root.geometry('960x700')

        self.equations = []
        self.x_min, self.x_max = -10.0, 10.0
        self.y_min, self.y_max = -10.0, 10.0

        self._history = []
        self._hpos = -1

        self._snapshots = []  # stack of (equations, x_min, x_max, y_min, y_max)

        self._build_ui()

        if initial_equations:
            for eq_str in initial_equations:
                self._dispatch(eq_str)

        self._redraw()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Status bar (pack first so it's never clipped) — matplotlib for LaTeX
        self.status_fig = Figure(figsize=(9, 0.45), dpi=100)
        self.status_fig.set_facecolor('#1a1a2e')
        self._status_default = (
            r"$y = x^{2}$  or  $x = y^{3}$  to plot  •  "
            r"clear  to reset  •  undo  to restore  •  scroll to zoom"
        )
        self.status_text = self.status_fig.text(
            0.02, 0.5, self._status_default,
            fontsize=13, color='#8888bb',
            verticalalignment='center',
        )
        self.status_canvas = FigureCanvasTkAgg(self.status_fig, self.root)
        self.status_canvas.get_tk_widget().pack(
            side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6),
        )
        self.status_canvas.get_tk_widget().configure(height=35)

        # Input bar (pack second-from-bottom)
        bar = tk.Frame(self.root, bg='#1a1a2e')
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 4))

        self.prompt_label = tk.Label(
            bar, text='>', fg='#9999cc', bg='#1a1a2e',
            font=('Monospace', 14, 'bold'),
        )
        self.prompt_label.pack(side=tk.LEFT, padx=(2, 6))

        self.entry = tk.Entry(
            bar, font=('Monospace', 14),
            bg='#16213e', fg='#e8e8ff',
            insertbackground='#aaaaff',
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor='#5555bb',
            highlightbackground='#333366',
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.entry.bind('<Return>', self._on_enter)
        self.entry.bind('<Up>', self._hist_up)
        self.entry.bind('<Down>', self._hist_down)
        self.entry.bind('<KeyRelease>', self._on_key_preview)
        self.entry.focus()

        # LaTeX preview strip (between input bar and graph)
        self.preview_fig = Figure(figsize=(9, 0.5), dpi=100)
        self.preview_fig.set_facecolor('#1a1a2e')
        self.preview_text = self.preview_fig.text(
            0.02, 0.5, '', fontsize=16, color='#e8e8ff',
            verticalalignment='center',
        )
        self.preview_canvas = FigureCanvasTkAgg(self.preview_fig, self.root)
        self.preview_canvas.get_tk_widget().pack(
            side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 2),
        )
        self.preview_canvas.get_tk_widget().configure(height=45)

        # Graph canvas (pack last — fills remaining space)
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True,
                                         padx=6, pady=6)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)

        # Re-scale fonts when the window is resized
        self.root.bind('<Configure>', self._on_resize)

    def _set_status(self, text: str):
        """Update the status bar (supports LaTeX via matplotlib)."""
        self.status_text.set_text(text)
        self.status_canvas.draw_idle()

    def _on_resize(self, _event=None):
        """Scale UI fonts based on window width."""
        w = self.root.winfo_width()
        scale = max(w / 960, 1.0)  # 960 is the default width
        entry_size = int(14 * scale)
        status_size = int(13 * scale)
        self.entry.configure(font=('Monospace', entry_size))
        self.prompt_label.configure(font=('Monospace', entry_size, 'bold'))
        self.status_text.set_fontsize(status_size)
        self.status_canvas.draw_idle()
        preview_size = int(16 * scale)
        self.preview_text.set_fontsize(preview_size)
        self.preview_canvas.draw_idle()

    def _on_key_preview(self, _event=None):
        """Update the LaTeX preview strip as the user types."""
        text = self.entry.get().strip()
        locals_dict = {'x': _X, 'y': _Y, 'e': sp.E, 'pi': sp.pi}
        m = re.match(r'^(.+?)\s*=\s*(.+)$', text)
        if m:
            lhs_str, rhs_str = m.group(1).strip(), m.group(2).strip()
            try:
                lhs = sp.sympify(lhs_str.replace('^', '**'), locals=locals_dict)
                rhs = sp.sympify(rhs_str.replace('^', '**'), locals=locals_dict)
                latex_str = f'${sp.latex(lhs)} = {sp.latex(rhs)}$'
            except Exception:
                latex_str = text
        elif text:
            latex_str = text
        else:
            latex_str = ''
        self.preview_text.set_text(latex_str)
        self.preview_canvas.draw_idle()

    # ── Drawing ──────────────────────────────────────────────────────────────

    def _redraw(self):
        ax = self.ax
        ax.clear()

        # Graph-paper background: classic green-tinted
        ax.set_facecolor('#f4fff4')
        self.fig.set_facecolor('#e0e0e0')

        ax.set_xlim(self.x_min, self.x_max)
        ax.set_ylim(self.y_min, self.y_max)

        # Auto tick spacing
        major_x = _nice_step((self.x_max - self.x_min) / 10)
        major_y = _nice_step((self.y_max - self.y_min) / 10)
        ax.xaxis.set_major_locator(MultipleLocator(major_x))
        ax.yaxis.set_major_locator(MultipleLocator(major_y))
        ax.xaxis.set_minor_locator(MultipleLocator(major_x / 5))
        ax.yaxis.set_minor_locator(MultipleLocator(major_y / 5))

        # Suppress the "0" label (it sits right at the axis crossing)
        def _fmt(val, _pos):
            if abs(val) < 1e-9:
                return ''
            return f'{val:g}'

        ax.xaxis.set_major_formatter(FuncFormatter(_fmt))
        ax.yaxis.set_major_formatter(FuncFormatter(_fmt))

        # Grid lines — minor then major (minor drawn first so major is on top)
        ax.grid(True, which='minor', color='#a8d8a8',
                linewidth=0.45, linestyle='-', zorder=0)
        ax.grid(True, which='major', color='#52a852',
                linewidth=0.9, linestyle='-', zorder=1)

        # Bold axes at origin
        ax.axhline(0, color='#1a1a1a', linewidth=1.8, zorder=2)
        ax.axvline(0, color='#1a1a1a', linewidth=1.8, zorder=2)

        # Move spines to origin (classic math-book look)
        for spine in ('left', 'bottom'):
            ax.spines[spine].set_position('zero')
            ax.spines[spine].set_linewidth(1.0)
            ax.spines[spine].set_color('#555555')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)

        # Scale tick labels with canvas size
        w = self.canvas.get_tk_widget().winfo_width()
        tick_size = max(8, int(8 * w / 900))
        ax.tick_params(axis='both', which='major',
                       labelsize=tick_size, length=4, width=0.8, color='#444444')
        ax.tick_params(axis='both', which='minor', length=2, width=0.5)

        # Plot equations
        x_arr = np.linspace(self.x_min, self.x_max, 4000)
        legend_handles = []
        for eq in self.equations:
            if eq.implicit:
                xi = np.linspace(self.x_min, self.x_max, 800)
                yi = np.linspace(self.y_min, self.y_max, 800)
                Xm, Ym = np.meshgrid(xi, yi)
                Zm = eq.evaluate_2d(Xm, Ym)
                ax.contour(Xm, Ym, Zm, levels=[0],
                           colors=[eq.color], linewidths=2.4, zorder=5)
                legend_handles.append(
                    Line2D([0], [0], color=eq.color, linewidth=2.4,
                           label=eq.label))
            else:
                y_arr = eq.evaluate(x_arr)
                y_plot = _sanitize(y_arr, self.y_min, self.y_max)
                line, = ax.plot(x_arr, y_plot,
                                color=eq.color, linewidth=2.4,
                                label=eq.label, zorder=5,
                                solid_capstyle='round')
                legend_handles.append(line)

        # Intersection points (all equation pairs)
        for ix, iy in self._intersections(x_arr, self.equations):
            ax.plot(ix, iy, 'o', color='#111111', markersize=7, zorder=8)
            ax.annotate(
                f'({_fc(ix)}, {_fc(iy)})',
                xy=(ix, iy), xytext=(9, 9),
                textcoords='offset points',
                fontsize=tick_size, color='#111111',
                bbox=dict(boxstyle='round,pad=0.3',
                          fc='white', alpha=0.9,
                          ec='#aaaaaa', lw=0.7),
            )

        if legend_handles:
            ax.legend(handles=legend_handles,
                      loc='upper right', fontsize=max(9, tick_size),
                      framealpha=0.92, facecolor='white',
                      edgecolor='#bbbbbb', borderpad=0.6)

        self.fig.tight_layout(pad=0.6)
        self.canvas.draw()

    # ── Intersections ─────────────────────────────────────────────────────────

    def _intersections(self, x_arr, eqs=None):
        eqs = eqs or self.equations
        pts = []
        for eq1, eq2 in combinations(eqs, 2):
            if not self._sym_intersect(eq1, eq2, pts):
                if not eq1.implicit and not eq2.implicit:
                    self._num_intersect(eq1, eq2, x_arr, pts)
                elif eq1.implicit and eq2.implicit:
                    self._num_intersect_implicit(eq1, eq2, pts)
                else:
                    exp, imp = (eq1, eq2) if not eq1.implicit else (eq2, eq1)
                    self._num_intersect_mixed(exp, imp, x_arr, pts)
        return pts

    def _sym_intersect(self, eq1, eq2, pts):
        """Analytical solution via sympy (handles all equation types)."""
        try:
            e1 = _Y - eq1.sym_expr if not eq1.implicit else eq1.sym_expr
            e2 = _Y - eq2.sym_expr if not eq2.implicit else eq2.sym_expr
            sols = sp.solve([e1, e2], [_X, _Y])
            if isinstance(sols, dict):
                sols = [(sols.get(_X), sols.get(_Y))]
            found = False
            for sol in sols:
                try:
                    sx_c, sy_c = complex(sol[0]), complex(sol[1])
                    if abs(sx_c.imag) > 1e-8 or abs(sy_c.imag) > 1e-8:
                        continue
                    sx, sy = float(sx_c.real), float(sy_c.real)
                except Exception:
                    continue
                if not (self.x_min <= sx <= self.x_max):
                    continue
                if not (self.y_min <= sy <= self.y_max):
                    continue
                if not _dup(sx, sy, pts):
                    pts.append((sx, sy))
                    found = True
            return found
        except Exception:
            return False

    def _num_intersect(self, eq1, eq2, x_arr, pts):
        """Numerical intersection for two explicit equations."""
        try:
            y1 = eq1.evaluate(x_arr)
            y2 = eq2.evaluate(x_arr)
            diff = y1 - y2
            valid = ~(np.isnan(diff) | np.isinf(diff))
            sign = np.sign(diff)
            changes = np.where(
                (np.diff(sign) != 0) & valid[:-1] & valid[1:]
            )[0]
            for idx in changes:
                a, b = float(x_arr[idx]), float(x_arr[idx + 1])
                da, db = float(diff[idx]), float(diff[idx + 1])
                sx = _bisect(lambda xv: float(eq1._fn(xv)) - float(eq2._fn(xv)),
                             a, b, da, db)
                sy = float(eq1._fn(sx))
                if self.y_min <= sy <= self.y_max and not _dup(sx, sy, pts):
                    pts.append((sx, sy))
        except Exception:
            pass

    def _num_intersect_mixed(self, explicit_eq, implicit_eq, x_arr, pts):
        """Numerical intersection: substitute y=f(x) into implicit equation."""
        try:
            y_arr = explicit_eq.evaluate(x_arr)
            vals = implicit_eq.evaluate_2d(x_arr, y_arr)
            valid = ~(np.isnan(vals) | np.isinf(vals))
            sign = np.sign(vals)
            changes = np.where(
                (np.diff(sign) != 0) & valid[:-1] & valid[1:]
            )[0]
            for idx in changes:
                a, b = float(x_arr[idx]), float(x_arr[idx + 1])
                fa, fb = float(vals[idx]), float(vals[idx + 1])

                def _f(xv):
                    yv = float(explicit_eq._fn(xv))
                    return float(implicit_eq._fn2d(xv, yv))

                sx = _bisect(_f, a, b, fa, fb)
                sy = float(explicit_eq._fn(sx))
                if self.y_min <= sy <= self.y_max and not _dup(sx, sy, pts):
                    pts.append((sx, sy))
        except Exception:
            pass

    def _num_intersect_implicit(self, eq1, eq2, pts):
        """Numerical intersection for two implicit curves on a 2-D grid."""
        try:
            nx = ny = 400
            xi = np.linspace(self.x_min, self.x_max, nx)
            yi = np.linspace(self.y_min, self.y_max, ny)
            Xm, Ym = np.meshgrid(xi, yi)
            Z1 = eq1.evaluate_2d(Xm, Ym)
            Z2 = eq2.evaluate_2d(Xm, Ym)

            # Vectorised: find cells where both functions have a sign change
            z1_min = np.minimum(np.minimum(Z1[:-1, :-1], Z1[:-1, 1:]),
                                np.minimum(Z1[1:, :-1], Z1[1:, 1:]))
            z1_max = np.maximum(np.maximum(Z1[:-1, :-1], Z1[:-1, 1:]),
                                np.maximum(Z1[1:, :-1], Z1[1:, 1:]))
            z2_min = np.minimum(np.minimum(Z2[:-1, :-1], Z2[:-1, 1:]),
                                np.minimum(Z2[1:, :-1], Z2[1:, 1:]))
            z2_max = np.maximum(np.maximum(Z2[:-1, :-1], Z2[:-1, 1:]),
                                np.maximum(Z2[1:, :-1], Z2[1:, 1:]))

            both = ((z1_min <= 0) & (z1_max >= 0) &
                    (z2_min <= 0) & (z2_max >= 0))
            cells = np.argwhere(both)

            for i, j in cells:
                sx = (xi[j] + xi[j + 1]) / 2
                sy = (yi[i] + yi[i + 1]) / 2
                sx, sy = _refine_2d(eq1._zero_fn2d, eq2._zero_fn2d, sx, sy)
                if (self.x_min <= sx <= self.x_max and
                        self.y_min <= sy <= self.y_max and
                        not _dup(sx, sy, pts)):
                    pts.append((sx, sy))
        except Exception:
            pass

    # ── Auto-fit ──────────────────────────────────────────────────────────────

    def _find_all_intersections(self, x_arr: np.ndarray, eqs=None):
        """Find intersections without view-bound filtering (used for auto-fit)."""
        pts = []
        for eq1, eq2 in combinations(eqs or self.equations, 2):
            found_sym = False
            try:
                e1 = _Y - eq1.sym_expr if not eq1.implicit else eq1.sym_expr
                e2 = _Y - eq2.sym_expr if not eq2.implicit else eq2.sym_expr
                sols = sp.solve([e1, e2], [_X, _Y])
                if isinstance(sols, dict):
                    sols = [(sols.get(_X), sols.get(_Y))]
                for sol in sols:
                    try:
                        sx_c, sy_c = complex(sol[0]), complex(sol[1])
                        if abs(sx_c.imag) > 1e-8 or abs(sy_c.imag) > 1e-8:
                            continue
                        sx, sy = float(sx_c.real), float(sy_c.real)
                    except Exception:
                        continue
                    if np.isfinite(sx) and np.isfinite(sy) and not _dup(sx, sy, pts):
                        pts.append((sx, sy))
                        found_sym = True
            except Exception:
                pass

            if not found_sym:
                if not eq1.implicit and not eq2.implicit:
                    try:
                        y1 = eq1.evaluate(x_arr)
                        y2 = eq2.evaluate(x_arr)
                        diff = y1 - y2
                        valid = ~(np.isnan(diff) | np.isinf(diff))
                        sign = np.sign(diff)
                        changes = np.where(
                            (np.diff(sign) != 0) & valid[:-1] & valid[1:]
                        )[0]
                        for idx in changes:
                            a, b = float(x_arr[idx]), float(x_arr[idx + 1])
                            da, db = float(diff[idx]), float(diff[idx + 1])
                            sx = _bisect(
                                lambda xv: float(eq1._fn(xv)) - float(eq2._fn(xv)),
                                a, b, da, db,
                            )
                            sy = float(eq1._fn(sx))
                            if np.isfinite(sy) and not _dup(sx, sy, pts):
                                pts.append((sx, sy))
                    except Exception:
                        pass
                elif not eq1.implicit or not eq2.implicit:
                    # mixed: explicit + implicit
                    exp, imp = (eq1, eq2) if not eq1.implicit else (eq2, eq1)
                    try:
                        y_arr = exp.evaluate(x_arr)
                        vals = imp.evaluate_2d(x_arr, y_arr)
                        valid = ~(np.isnan(vals) | np.isinf(vals))
                        sign = np.sign(vals)
                        changes = np.where(
                            (np.diff(sign) != 0) & valid[:-1] & valid[1:]
                        )[0]
                        for idx in changes:
                            a, b = float(x_arr[idx]), float(x_arr[idx + 1])
                            fa, fb = float(vals[idx]), float(vals[idx + 1])

                            def _f(xv):
                                yv = float(exp._fn(xv))
                                return float(imp._fn2d(xv, yv))

                            sx = _bisect(_f, a, b, fa, fb)
                            sy = float(exp._fn(sx))
                            if np.isfinite(sy) and not _dup(sx, sy, pts):
                                pts.append((sx, sy))
                    except Exception:
                        pass
                # implicit-implicit: skip numerical for auto-fit (no view window)
        return pts

    def _auto_fit(self):
        """Set view window to best display the equations and their intersections."""
        explicit = [e for e in self.equations if not e.implicit]
        if not explicit:
            self.x_min, self.x_max = -10.0, 10.0
            self.y_min, self.y_max = -10.0, 10.0
            return

        wide_x = np.linspace(-100.0, 100.0, 40001)
        intersect_pts = self._find_all_intersections(wide_x, explicit)

        if intersect_pts:
            ix_vals = [p[0] for p in intersect_pts]
            x_center = (min(ix_vals) + max(ix_vals)) / 2
            x_half = max((max(ix_vals) - min(ix_vals)) / 2, 2.0) * 1.5
        else:
            x_center = 0.0
            x_half = 10.0

        cand_x_min = x_center - x_half
        cand_x_max = x_center + x_half

        eval_x = np.linspace(cand_x_min, cand_x_max, 4000)
        all_y = []
        for eq in explicit:
            y = eq.evaluate(eval_x)
            finite = y[np.isfinite(y)]
            if len(finite):
                all_y.append(finite)
        for _, iy in intersect_pts:
            all_y.append(np.array([iy]))

        if all_y:
            combined = np.concatenate(all_y)
            y_lo = float(np.percentile(combined, 2))
            y_hi = float(np.percentile(combined, 98))
            y_center = (y_lo + y_hi) / 2
            y_half = max((y_hi - y_lo) / 2, 2.0) * 1.4
        else:
            y_center = 0.0
            y_half = 10.0

        self.x_min, self.x_max = _nice_bounds(cand_x_min, cand_x_max)
        self.y_min, self.y_max = _nice_bounds(y_center - y_half, y_center + y_half)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _on_enter(self, _event=None):
        text = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        if not text:
            return
        if not self._history or self._history[-1] != text:
            self._history.append(text)
        self._hpos = len(self._history)
        self._dispatch(text)

    def _save_snapshot(self):
        self._snapshots.append((
            copy.deepcopy(self.equations),
            self.x_min, self.x_max, self.y_min, self.y_max,
        ))

    def _undo(self):
        if not self._snapshots:
            self._set_status('Nothing to undo.')
            return
        eqs, xn, xx, yn, yx = self._snapshots.pop()
        self.equations = eqs
        self.x_min, self.x_max = xn, xx
        self.y_min, self.y_max = yn, yx
        n = len(self.equations)
        self._set_status(
            f"Undo — {'no equations' if n == 0 else f'{n} equation(s)'} remaining."
        )
        self._redraw()

    def _dispatch(self, text: str):
        lower = text.lower().strip()

        if lower == 'undo':
            self._undo()
            return

        # clear  or  clear/del/remove y1
        if lower == 'clear':
            self._save_snapshot()
            self.equations.clear()
            self._set_status('Cleared.')
            self._redraw()
            return

        m = re.match(r'^(?:clear|del|remove)\s+(y\d*)$', lower)
        if m:
            name = m.group(1)
            self._save_snapshot()
            before = len(self.equations)
            self.equations = [e for e in self.equations if e.name != name]
            msg = f'Removed {name}.' if len(self.equations) < before \
                else f'{name} not found.'
            self._set_status(msg)
            self._auto_fit()
            self._redraw()
            return

        # xmin / xmax / ymin / ymax
        m = re.match(r'^(xmin|xmax|ymin|ymax)\s*=\s*(.+)$', lower)
        if m:
            attr, val_str = m.group(1), m.group(2)
            try:
                val = float(sp.sympify(val_str))
                self._save_snapshot()
                if attr == 'xmin':
                    self.x_min = val
                elif attr == 'xmax':
                    self.x_max = val
                elif attr == 'ymin':
                    self.y_min = val
                else:
                    self.y_max = val
                self._set_status(f'{attr} = {val}')
                self._redraw()
            except Exception:
                self._set_status(f'Bad value for {attr}.')
            return

        # y = expr  (explicit, y isolated on the left)
        m = re.match(r'^y\s*=\s*(.+)$', text, re.IGNORECASE)
        if m:
            rhs = m.group(1).strip()
            # Only treat as explicit if rhs has no 'y'
            if not re.search(r'\by\b', rhs, re.IGNORECASE):
                name = self._next_name()
                self._add_eq(name, rhs)
                return

        # General equation: <lhs> = <rhs>  (implicit)
        m = re.match(r'^(.+?)\s*=\s*(.+)$', text)
        if m:
            self._add_implicit_eq(m.group(1).strip(), m.group(2).strip())
            return

        self._set_status(
            r"Unknown input.  Try:  $y=x^{2}$  |  $x=y^{3}$  |  clear  |  xmin=-20"
        )

    def _next_name(self) -> str:
        """Return the next available internal name (y1, y2, ...)."""
        used = {e.name for e in self.equations}
        i = 1
        while f'y{i}' in used:
            i += 1
        return f'y{i}'

    def _add_implicit_eq(self, lhs_str: str, rhs_str: str):
        try:
            locals_dict = {'x': _X, 'y': _Y, 'e': sp.E, 'pi': sp.pi}
            lhs_expr = sp.sympify(lhs_str.replace('^', '**'), locals=locals_dict)
            rhs_expr = sp.sympify(rhs_str.replace('^', '**'), locals=locals_dict)
            implicit_expr = lhs_expr - rhs_expr
            self._save_snapshot()
            name = self._next_name()
            color = COLORS[len(self.equations) % len(COLORS)]
            self.equations.append(Equation(
                name, f'{lhs_str}={rhs_str}', implicit_expr, color,
                implicit=True, lhs_sym=lhs_expr, rhs_sym=rhs_expr,
            ))
            n = len(self.equations)
            self._set_status(
                f"Plotted  ${sp.latex(lhs_expr)} = {sp.latex(rhs_expr)}$  "
                f"({'1 equation' if n == 1 else f'{n} equations'})"
            )
            self._auto_fit()
            self._redraw()
        except Exception as exc:
            self._set_status(f'Error: {exc}')

    def _add_eq(self, name: str, raw: str):
        try:
            expr_str = raw.replace('^', '**')
            self._save_snapshot()
            sym_expr = sp.sympify(
                expr_str,
                locals={'x': _X, 'e': sp.E, 'pi': sp.pi},
            )
            # Replace existing equation of the same name
            self.equations = [e for e in self.equations if e.name != name]
            color = COLORS[len(self.equations) % len(COLORS)]
            self.equations.append(Equation(name, raw, sym_expr, color))
            n = len(self.equations)
            latex = sp.latex(sym_expr)
            self._set_status(
                f"Plotted  $y = {latex}$  "
                f"({'1 equation' if n == 1 else f'{n} equations'})"
            )
            self._auto_fit()
            self._redraw()
        except Exception as exc:
            self._set_status(f'Error: {exc}')

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_scroll(self, event):
        factor = 1.15 if event.button == 'up' else 1 / 1.15
        cx = (self.x_min + self.x_max) / 2
        cy = (self.y_min + self.y_max) / 2
        dx = (self.x_max - self.x_min) / 2 * factor
        dy = (self.y_max - self.y_min) / 2 * factor
        self.x_min, self.x_max = cx - dx, cx + dx
        self.y_min, self.y_max = cy - dy, cy + dy
        self._redraw()

    def _hist_up(self, _event):
        if self._history and self._hpos > 0:
            self._hpos -= 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self._history[self._hpos])

    def _hist_down(self, _event):
        if self._hpos < len(self._history) - 1:
            self._hpos += 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self._history[self._hpos])
        else:
            self._hpos = len(self._history)
            self.entry.delete(0, tk.END)

    def run(self):
        self.root.mainloop()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nice_step(raw: float) -> float:
    if raw <= 0:
        return 1.0
    exp = math.floor(math.log10(raw))
    frac = raw / 10 ** exp
    nice = 1 if frac < 1.5 else 2 if frac < 3.5 else 5 if frac < 7.5 else 10
    return float(nice * 10 ** exp)


def _nice_bounds(lo: float, hi: float):
    """Round lo/hi outward to the nearest nice grid line."""
    span = hi - lo if hi > lo else 1.0
    step = _nice_step(span / 8)
    return math.floor(lo / step) * step, math.ceil(hi / step) * step


def _sanitize(y: np.ndarray, y_min: float, y_max: float) -> np.ndarray:
    """Insert NaN at discontinuities and values far outside the view."""
    margin = (y_max - y_min) * 8
    out = y.copy().astype(float)
    out[np.abs(out) > abs(y_max) + abs(margin)] = np.nan
    # Break large jumps (discontinuities like 1/x, tan(x))
    jump = (y_max - y_min) * 3
    big = np.abs(np.diff(out, prepend=np.nan)) > jump
    out[big] = np.nan
    return out


def _bisect(f, a: float, b: float, fa: float, fb: float,
            tol: float = 1e-7, maxiter: int = 52) -> float:
    for _ in range(maxiter):
        mid = (a + b) / 2
        fm = f(mid)
        if abs(fm) < tol or (b - a) < tol:
            return mid
        if math.copysign(1, fm) == math.copysign(1, fa):
            a, fa = mid, fm
        else:
            b, fb = mid, fm
    return (a + b) / 2


def _refine_2d(fn1, fn2, x0: float, y0: float,
               iters: int = 20, tol: float = 1e-10) -> tuple:
    """Newton-refine a 2-D intersection of fn1(x,y)==0 and fn2(x,y)==0."""
    h = 1e-7
    x, y = x0, y0
    for _ in range(iters):
        try:
            f1 = float(fn1(x, y))
            f2 = float(fn2(x, y))
        except Exception:
            break
        if abs(f1) < tol and abs(f2) < tol:
            break
        try:
            f1x = (float(fn1(x + h, y)) - f1) / h
            f1y = (float(fn1(x, y + h)) - f1) / h
            f2x = (float(fn2(x + h, y)) - f2) / h
            f2y = (float(fn2(x, y + h)) - f2) / h
        except Exception:
            break
        det = f1x * f2y - f1y * f2x
        if abs(det) < 1e-15:
            break
        x -= (f1 * f2y - f2 * f1y) / det
        y -= (f2 * f1x - f1 * f2x) / det
    return x, y


def _dup(sx: float, sy: float, pts, tol: float = 1e-4) -> bool:
    return any(abs(sx - p[0]) < tol and abs(sy - p[1]) < tol for p in pts)


def _fc(v: float) -> str:
    """Format a coordinate value cleanly."""
    if v == int(v):
        return str(int(v))
    return f'{v:.3g}'
