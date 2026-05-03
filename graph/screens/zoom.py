from __future__ import annotations
import math
import curses
from graph.screens import BaseScreen
from graph.display import draw_status_bar, draw_softkey_bar, safe_addstr, Color, draw_box
from graph.state import WindowVars
from graph.keys import Key, BACK_KEYS, ENTER_KEYS

_SOFTKEYS = ['', '', '', '', '']

_ZOOM_ITEMS = [
    'ZBox', 'Zoom In', 'Zoom Out', 'ZDecimal', 'ZSquare',
    'ZStandard', 'ZTrig', 'ZInteger', 'ZoomStat', 'ZoomFit', 'ZoomPrev',
]


class ZoomScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self.cursor = 0

    def on_enter(self):
        curses.curs_set(0)

    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        w    = min(22, self.cols - 4)
        h    = len(_ZOOM_ITEMS) + 4
        top  = max(1, (self.rows - h) // 2)
        left = max(0, (self.cols - w) // 2)
        draw_box(self.stdscr, top, left, h, w, 'ZOOM')

        for i, name in enumerate(_ZOOM_ITEMS):
            attr  = curses.color_pair(Color.HIGHLIGHT) if i == self.cursor else 0
            label = f'{i + 1:2}. {name}'
            safe_addstr(self.stdscr, top + 2 + i, left + 2, label.ljust(w - 4)[:w - 4], attr)

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if key in BACK_KEYS:
            self.manager.pop()
        elif key in Key.UP and self.cursor > 0:
            self.cursor -= 1
        elif key in Key.DOWN and self.cursor < len(_ZOOM_ITEMS) - 1:
            self.cursor += 1
        elif key in ENTER_KEYS:
            self._apply(self.cursor)
        else:
            digit = key - ord('1')
            if 0 <= digit < len(_ZOOM_ITEMS):
                self._apply(digit)

    # ------------------------------------------------------------------

    def _apply(self, idx: int):
        self.state.save_zoom()
        name = _ZOOM_ITEMS[idx]
        w    = self.state.window
        if name == 'ZStandard':
            self._set(w, -10, 10, 1, -10, 10, 1)
        elif name == 'ZDecimal':
            self._set(w, -4.7, 4.7, 0.5, -3.1, 3.1, 0.5)
        elif name == 'ZTrig':
            self._set(w, -2 * math.pi, 2 * math.pi, math.pi / 2, -4, 4, 1)
        elif name == 'Zoom In':
            cx = (w.xmin + w.xmax) / 2
            cy = (w.ymin + w.ymax) / 2
            self._set(w,
                cx - (cx - w.xmin) / 2, cx + (w.xmax - cx) / 2, w.xscl,
                cy - (cy - w.ymin) / 2, cy + (w.ymax - cy) / 2, w.yscl)
        elif name == 'Zoom Out':
            cx = (w.xmin + w.xmax) / 2
            cy = (w.ymin + w.ymax) / 2
            self._set(w,
                cx - (cx - w.xmin) * 2, cx + (w.xmax - cx) * 2, w.xscl,
                cy - (cy - w.ymin) * 2, cy + (w.ymax - cy) * 2, w.yscl)
        elif name == 'ZoomPrev':
            self.state.restore_zoom()  # already saved above, balance by popping extra
            self.state.restore_zoom()  # the one we just saved
        else:
            pass  # ZBox, ZSquare, ZInteger, ZoomStat, ZoomFit — simplified: just pop
        self.state.invalidate_graph()
        self.manager.pop()

    @staticmethod
    def _set(w, xmin, xmax, xscl, ymin, ymax, yscl):
        w.xmin = xmin; w.xmax = xmax; w.xscl = xscl
        w.ymin = ymin; w.ymax = ymax; w.yscl = yscl
