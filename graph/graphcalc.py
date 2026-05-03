"""Graphical calculator — type y=<expr> to plot, clear to reset."""

import copy
import math
import re
import tkinter as tk
from itertools import combinations

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
import sympy as sp


COLORS = [
    '#e74c3c', '#3498db', '#27ae60', '#f39c12',
    '#8e44ad', '#16a085', '#e67e22', '#2980b9',
]

_X = sp.Symbol('x')


# ── Equation ─────────────────────────────────────────────────────────────────

class Equation:
    def __init__(self, name: str, raw: str, sym_expr, color: str):
        self.name = name          # e.g. "y" or "y1"
        self.raw = raw            # original string the user typed
        self.sym_expr = sym_expr  # sympy expression in x
        self.color = color
        self._fn = sp.lambdify(_X, sym_expr, modules='numpy')

    @property
    def label(self) -> str:
        return f'{self.name}={self.raw}'

    def evaluate(self, x_arr: np.ndarray) -> np.ndarray:
        try:
            result = self._fn(x_arr)
            if np.isscalar(result):
                return np.full_like(x_arr, float(result), dtype=float)
            return np.asarray(result, dtype=float)
        except Exception:
            return np.full_like(x_arr, np.nan, dtype=float)


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
        # Graph canvas
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True,
                                         padx=6, pady=6)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)

        # Input bar
        bar = tk.Frame(self.root, bg='#1a1a2e')
        bar.pack(fill=tk.X, padx=6, pady=(0, 4))

        tk.Label(bar, text='>', fg='#9999cc', bg='#1a1a2e',
                 font=('Monospace', 13, 'bold')).pack(side=tk.LEFT,
                                                       padx=(2, 6))

        self.entry = tk.Entry(
            bar, font=('Monospace', 13),
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
        self.entry.focus()

        self.status = tk.StringVar(
            value="y=x**2  to plot  •  y=x  to add another  •  "
                  "clear  to reset  •  undo  to restore  •  scroll to zoom"
        )
        tk.Label(self.root, textvariable=self.status,
                 fg='#555588', bg='#1a1a2e',
                 font=('Monospace', 9), anchor='w'
                 ).pack(fill=tk.X, padx=8, pady=(0, 4))

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

        ax.tick_params(axis='both', which='major',
                       labelsize=8, length=4, width=0.8, color='#444444')
        ax.tick_params(axis='both', which='minor', length=2, width=0.5)

        # Plot equations
        x_arr = np.linspace(self.x_min, self.x_max, 4000)
        for eq in self.equations:
            y_arr = eq.evaluate(x_arr)
            y_plot = _sanitize(y_arr, self.y_min, self.y_max)
            ax.plot(x_arr, y_plot,
                    color=eq.color, linewidth=2.4,
                    label=eq.label, zorder=5,
                    solid_capstyle='round')

        # Intersection points
        for ix, iy in self._intersections(x_arr):
            ax.plot(ix, iy, 'o', color='#111111', markersize=7, zorder=8)
            ax.annotate(
                f'({_fc(ix)}, {_fc(iy)})',
                xy=(ix, iy), xytext=(9, 9),
                textcoords='offset points',
                fontsize=8, color='#111111',
                bbox=dict(boxstyle='round,pad=0.3',
                          fc='white', alpha=0.9,
                          ec='#aaaaaa', lw=0.7),
            )

        if self.equations:
            ax.legend(loc='upper right', fontsize=9,
                      framealpha=0.92, facecolor='white',
                      edgecolor='#bbbbbb', borderpad=0.6)

        self.fig.tight_layout(pad=0.6)
        self.canvas.draw()

    # ── Intersections ─────────────────────────────────────────────────────────

    def _intersections(self, x_arr):
        pts = []
        for eq1, eq2 in combinations(self.equations, 2):
            if not self._sym_intersect(eq1, eq2, pts):
                self._num_intersect(eq1, eq2, x_arr, pts)
        return pts

    def _sym_intersect(self, eq1, eq2, pts):
        """Analytical solution via sympy. Returns True if solutions found."""
        try:
            sols = sp.solve(eq1.sym_expr - eq2.sym_expr, _X)
            found = False
            for sol in sols:
                try:
                    cv = complex(sol)
                    if abs(cv.imag) > 1e-8:
                        continue
                    sx = float(cv.real)
                except Exception:
                    continue
                if not (self.x_min <= sx <= self.x_max):
                    continue
                sy = float(eq1._fn(sx))
                if not (self.y_min <= sy <= self.y_max):
                    continue
                if not _dup(sx, pts):
                    pts.append((sx, sy))
                    found = True
            return found
        except Exception:
            return False

    def _num_intersect(self, eq1, eq2, x_arr, pts):
        """Numerical intersection by sign-change detection + bisection."""
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
                if self.y_min <= sy <= self.y_max and not _dup(sx, pts):
                    pts.append((sx, sy))
        except Exception:
            pass

    # ── Auto-fit ──────────────────────────────────────────────────────────────

    def _find_all_intersections(self, x_arr: np.ndarray):
        """Find intersections without view-bound filtering (used for auto-fit)."""
        pts = []
        for eq1, eq2 in combinations(self.equations, 2):
            found_sym = False
            try:
                sols = sp.solve(eq1.sym_expr - eq2.sym_expr, _X)
                for sol in sols:
                    try:
                        cv = complex(sol)
                        if abs(cv.imag) > 1e-8:
                            continue
                        sx = float(cv.real)
                    except Exception:
                        continue
                    if not np.isfinite(sx):
                        continue
                    sy = float(eq1._fn(sx))
                    if np.isfinite(sy) and not _dup(sx, pts):
                        pts.append((sx, sy))
                        found_sym = True
            except Exception:
                pass

            if not found_sym:
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
                        if np.isfinite(sy) and not _dup(sx, pts):
                            pts.append((sx, sy))
                except Exception:
                    pass
        return pts

    def _auto_fit(self):
        """Set view window to best display the equations and their intersections."""
        if not self.equations:
            self.x_min, self.x_max = -10.0, 10.0
            self.y_min, self.y_max = -10.0, 10.0
            return

        wide_x = np.linspace(-100.0, 100.0, 40001)
        intersect_pts = self._find_all_intersections(wide_x)

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
        for eq in self.equations:
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
            self.status.set('Nothing to undo.')
            return
        eqs, xn, xx, yn, yx = self._snapshots.pop()
        self.equations = eqs
        self.x_min, self.x_max = xn, xx
        self.y_min, self.y_max = yn, yx
        n = len(self.equations)
        self.status.set(
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
            self.status.set('Cleared.')
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
            self.status.set(msg)
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
                self.status.set(f'{attr} = {val}')
                self._redraw()
            except Exception:
                self.status.set(f'Bad value for {attr}.')
            return

        # y[n] = expr
        m = re.match(r'^(y\d*)\s*=\s*(.+)$', text, re.IGNORECASE)
        if m:
            self._add_eq(m.group(1).lower(), m.group(2).strip())
            return

        self.status.set(
            "Unknown input.  Try:  y=x**2  |  y=sin(x)  |  clear  |  xmin=-20"
        )

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
            self.status.set(
                f"Plotted  {name}={raw}  "
                f"({'1 equation' if n == 1 else f'{n} equations'})"
            )
            self._auto_fit()
            self._redraw()
        except Exception as exc:
            self.status.set(f'Error: {exc}')

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


def _dup(sx: float, pts, tol: float = 1e-4) -> bool:
    return any(abs(sx - p[0]) < tol for p in pts)


def _fc(v: float) -> str:
    """Format a coordinate value cleanly."""
    if v == int(v):
        return str(int(v))
    return f'{v:.3g}'
