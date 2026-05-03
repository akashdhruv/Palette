from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_softkey_bar, safe_addstr
from graph.renderer import GraphRenderer
from graph.keys import Key, BACK_KEYS

_SOFTKEYS = ['Y=', 'WINDOW', 'ZOOM', 'TRACE', '']


class TraceScreen(BaseScreen):
    """Overlay that draws graph + crosshair cursor with coordinate readout."""

    def __init__(self, manager):
        super().__init__(manager)
        self._gr = GraphRenderer(self.state)

    def on_enter(self):
        curses.curs_set(0)
        # start trace_x at center of window
        w = self.state.window
        self.state.trace_x = (w.xmin + w.xmax) / 2.0
        self._rerender()

    def on_resume(self):
        curses.curs_set(0)

    # ------------------------------------------------------------------

    def _rerender(self):
        self._gr.render_graph(force=self.state.graph_dirty)
        w   = self.state.window
        idx = self.state.trace_fn_idx
        self._gr.draw_trace_cursor(self.state.trace_x, idx, w)

    def _step(self) -> float:
        w = self.state.window
        return (w.xmax - w.xmin) * 0.05

    # ------------------------------------------------------------------

    def draw(self):
        draw_softkey_bar(self.stdscr, _SOFTKEYS)
        self._gr.blit_to_window(self.stdscr, start_row=1, start_col=1)

        # coordinate readout
        idx  = self.state.trace_fn_idx
        x    = self.state.trace_x
        y_arr = self._gr.sample_function(idx, self.state.window)
        w    = self.state.window
        if y_arr is not None:
            px_f, _ = self._gr.world_to_pixel(x, 0, w)
            px = int(round(px_f))
            y = y_arr[px] if 0 <= px < len(y_arr) else float('nan')
        else:
            y = float('nan')

        import math
        y_str = f'{y:.5f}' if math.isfinite(y) else '------'
        info  = f'Y{idx + 1}  X={x:.5f}  Y={y_str}'
        safe_addstr(self.stdscr, self.rows - 2, 0, info[:self.cols])

    # ------------------------------------------------------------------

    def handle_key(self, key):
        w = self.state.window
        if key in BACK_KEYS:
            self.manager.pop()
        elif key in Key.LEFT:
            self.state.trace_x = max(w.xmin, self.state.trace_x - self._step())
            self._rerender()
        elif key in Key.RIGHT:
            self.state.trace_x = min(w.xmax, self.state.trace_x + self._step())
            self._rerender()
        elif key in Key.UP:
            self._cycle_fn(1)
            self._rerender()
        elif key in Key.DOWN:
            self._cycle_fn(-1)
            self._rerender()
        elif key in Key.F1:
            self.manager.pop()
            self.manager.replace('yedit')
        elif key in Key.F2:
            self.manager.pop()
            self.manager.replace('window')
        elif key in Key.F3:
            self.manager.pop()
            self.manager.push('zoom')

    def _cycle_fn(self, direction: int):
        enabled = [i for i in range(9) if self.state.y_exprs[i] and self.state.y_enabled[i]]
        if not enabled:
            return
        idx = self.state.trace_fn_idx
        if idx not in enabled:
            self.state.trace_fn_idx = enabled[0]
            return
        pos = enabled.index(idx)
        self.state.trace_fn_idx = enabled[(pos + direction) % len(enabled)]
