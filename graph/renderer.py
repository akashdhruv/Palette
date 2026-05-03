from __future__ import annotations
import math
import curses
import numpy as np
from typing import Optional
from itertools import combinations

from graph.state import CalcState, WindowVars
from graph.braille import BrailleBuffer
from graph.engine import make_numpy_func

GRAPH_CHAR_COLS = 78
GRAPH_CHAR_ROWS = 20


def _ceil_to_multiple(val: float, step: float) -> float:
    if step <= 0:
        return val
    return math.ceil(val / step) * step


class GraphRenderer:
    """Owns a BrailleBuffer and renders axes + Y= functions into it."""

    def __init__(self, state: CalcState) -> None:
        self.state = state
        self.buf   = BrailleBuffer(GRAPH_CHAR_COLS, GRAPH_CHAR_ROWS)
        self._cache: dict[int, Optional[np.ndarray]] = {}

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------

    def world_to_pixel(
        self,
        x_world: float,
        y_world: float,
        w: WindowVars,
    ) -> tuple[float, float]:
        px = (x_world - w.xmin) / (w.xmax - w.xmin) * (self.buf.px_cols - 1)
        py = (w.ymax - y_world) / (w.ymax - w.ymin) * (self.buf.px_rows - 1)
        return px, py

    def pixel_to_world(
        self,
        px_col: int,
        px_row: int,
        w: WindowVars,
    ) -> tuple[float, float]:
        x = w.xmin + px_col / max(1, self.buf.px_cols - 1) * (w.xmax - w.xmin)
        y = w.ymax - px_row / max(1, self.buf.px_rows - 1) * (w.ymax - w.ymin)
        return x, y

    # ------------------------------------------------------------------
    # Axes and tick marks
    # ------------------------------------------------------------------

    def draw_axes(self, w: WindowVars) -> None:
        # X-axis (y=0)
        if w.ymin <= 0 <= w.ymax:
            _, y0_f = self.world_to_pixel(0, 0, w)
            y0 = int(round(y0_f))
            for px in range(self.buf.px_cols):
                self.buf.set_pixel(px, y0)
            # tick marks at multiples of xscl
            x_tick = _ceil_to_multiple(w.xmin, w.xscl)
            while x_tick <= w.xmax + 1e-9:
                tx_f, _ = self.world_to_pixel(x_tick, 0, w)
                tx = int(round(tx_f))
                for dy in (-2, -1, 0, 1, 2):
                    self.buf.set_pixel(tx, y0 + dy)
                x_tick += w.xscl

        # Y-axis (x=0)
        if w.xmin <= 0 <= w.xmax:
            x0_f, _ = self.world_to_pixel(0, 0, w)
            x0 = int(round(x0_f))
            for py in range(self.buf.px_rows):
                self.buf.set_pixel(x0, py)
            # tick marks at multiples of yscl
            y_tick = _ceil_to_multiple(w.ymin, w.yscl)
            while y_tick <= w.ymax + 1e-9:
                _, ty_f = self.world_to_pixel(0, y_tick, w)
                ty = int(round(ty_f))
                for dx in (-2, -1, 0, 1, 2):
                    self.buf.set_pixel(x0 + dx, ty)
                y_tick += w.yscl

    # ------------------------------------------------------------------
    # Function sampling (cached)
    # ------------------------------------------------------------------

    def sample_function(
        self,
        fn_idx: int,
        w: WindowVars,
        force: bool = False,
    ) -> Optional[np.ndarray]:
        if fn_idx in self._cache and not force:
            return self._cache[fn_idx]

        expr = self.state.y_exprs[fn_idx]
        if not expr or not self.state.y_enabled[fn_idx]:
            self._cache[fn_idx] = None
            return None

        fn = make_numpy_func(expr, self.state)
        if fn is None:
            self._cache[fn_idx] = None
            return None

        x_arr = np.linspace(w.xmin, w.xmax, self.buf.px_cols)
        try:
            with np.errstate(all='ignore'):
                y_arr = fn(x_arr)
                y_arr = np.where(np.isfinite(y_arr), y_arr, np.nan)
        except Exception:
            y_arr = np.full(self.buf.px_cols, np.nan)

        self._cache[fn_idx] = y_arr
        return y_arr

    def invalidate_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # Intersection detection
    # ------------------------------------------------------------------

    def find_intersections(self, w: WindowVars) -> list[tuple[float, float]]:
        """Find intersection points between all pairs of enabled functions."""
        # Collect sampled y arrays for enabled functions
        active: list[tuple[int, np.ndarray]] = []
        for i in range(9):
            y_arr = self.sample_function(i, w)
            if y_arr is not None:
                active.append((i, y_arr))

        if len(active) < 2:
            return []

        x_arr = np.linspace(w.xmin, w.xmax, self.buf.px_cols)
        intersections: list[tuple[float, float]] = []

        for (i, y1), (j, y2) in combinations(active, 2):
            diff = y1 - y2
            # Find sign changes (zero crossings)
            valid = np.isfinite(diff)
            for k in range(len(diff) - 1):
                if not (valid[k] and valid[k + 1]):
                    continue
                if diff[k] == 0:
                    intersections.append((x_arr[k], y1[k]))
                elif diff[k] * diff[k + 1] < 0:
                    # Linear interpolation to find crossing
                    t = diff[k] / (diff[k] - diff[k + 1])
                    ix = x_arr[k] + t * (x_arr[k + 1] - x_arr[k])
                    iy = y1[k] + t * (y1[k + 1] - y1[k])
                    if math.isfinite(ix) and math.isfinite(iy):
                        intersections.append((ix, iy))

        return intersections

    def draw_intersection_markers(self, w: WindowVars) -> None:
        """Draw circle markers at intersection points."""
        intersections = self.find_intersections(w)
        self._intersections = intersections  # store for external access

        for ix, iy in intersections:
            px_f, py_f = self.world_to_pixel(ix, iy, w)
            px = int(round(px_f))
            py = int(round(py_f))
            # Draw a small circle/diamond marker (radius ~3 pixels)
            for r in range(3, 5):
                for angle_step in range(16):
                    a = angle_step * (2 * math.pi / 16)
                    dx = int(round(r * math.cos(a)))
                    dy = int(round(r * math.sin(a)))
                    self.buf.set_pixel(px + dx, py + dy)
            # Draw crosshair center
            for d in range(-2, 3):
                self.buf.set_pixel(px + d, py)
                self.buf.set_pixel(px, py + d)

    # ------------------------------------------------------------------
    # Full render
    # ------------------------------------------------------------------

    def render_graph(self, force: bool = False) -> None:
        self.buf.clear()
        w = self.state.window

        if force or self.state.graph_dirty:
            self.invalidate_cache()
            self.state.graph_dirty = False

        self.draw_axes(w)

        for i in range(9):
            y_arr = self.sample_function(i, w, force=force)
            if y_arr is None:
                continue
            px_c = np.arange(self.buf.px_cols, dtype=np.float64)
            px_r = (w.ymax - y_arr) / (w.ymax - w.ymin) * (self.buf.px_rows - 1)
            valid   = np.isfinite(px_r)
            c_valid = px_c[valid].astype(np.int64)
            r_valid = np.clip(
                np.round(px_r[valid]), 0, self.buf.px_rows - 1
            ).astype(np.int64)
            self.buf.set_pixel_batch(c_valid, r_valid)

        # Draw intersection markers after all curves are plotted
        self.draw_intersection_markers(w)

    # ------------------------------------------------------------------
    # Write to curses window
    # ------------------------------------------------------------------

    def blit_to_window(
        self,
        win: 'curses.window',
        start_row: int = 1,
        start_col: int = 1,
    ) -> None:
        rows_str = self.buf.render()
        for r_idx, row_str in enumerate(rows_str):
            try:
                win.addstr(start_row + r_idx, start_col, row_str)
            except curses.error:
                pass

    # ------------------------------------------------------------------
    # Trace cursor
    # ------------------------------------------------------------------

    def draw_trace_cursor(
        self,
        x_world: float,
        fn_idx: int,
        w: WindowVars,
    ) -> None:
        y_arr = self.sample_function(fn_idx, w)
        if y_arr is None:
            return
        px_col_f, _ = self.world_to_pixel(x_world, 0, w)
        px_col = int(round(px_col_f))
        if not (0 <= px_col < len(y_arr)):
            return
        y_world = y_arr[px_col]
        if not math.isfinite(y_world):
            return
        _, px_row_f = self.world_to_pixel(0, y_world, w)
        px_row = int(round(px_row_f))
        for dc in range(-3, 4):
            self.buf.set_pixel(px_col + dc, px_row)
        for dr in range(-3, 4):
            self.buf.set_pixel(px_col, px_row + dr)
