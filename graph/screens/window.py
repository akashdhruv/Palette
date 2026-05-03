from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.keys import Key, BACK_KEYS, ENTER_KEYS, BS_KEYS

_FIELDS = ['Xmin', 'Xmax', 'Xscl', 'Ymin', 'Ymax', 'Yscl', 'Xres']
_ATTRS  = ['xmin', 'xmax', 'xscl', 'ymin', 'ymax', 'yscl', 'xres']
_SOFTKEYS = ['BACK', '', '', '', '']


class WindowScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self.cursor  = 0
        self._bufs   = [str(getattr(self.state.window, a)) for a in _ATTRS]

    def on_enter(self):
        self._bufs = [str(getattr(self.state.window, a)) for a in _ATTRS]
        curses.curs_set(1)

    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)
        safe_addstr(self.stdscr, 1, 0, 'WINDOW', curses.color_pair(Color.STATUS_BAR))

        for i, (label, buf) in enumerate(zip(_FIELDS, self._bufs)):
            row  = 2 + i
            attr = curses.color_pair(Color.HIGHLIGHT) if i == self.cursor else 0
            text = f'{label}={buf}'
            safe_addstr(self.stdscr, row, 0, text[:self.cols].ljust(self.cols - 1), attr)

        # cursor at end of current field value
        col = len(_FIELDS[self.cursor]) + 1 + len(self._bufs[self.cursor])
        try:
            self.stdscr.move(2 + self.cursor, min(col, self.cols - 1))
        except curses.error:
            pass

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if key in BACK_KEYS + Key.F2:
            self._commit_all()
            self.manager.pop()
        elif key in ENTER_KEYS + Key.DOWN + Key.TAB:
            self._commit_field(self.cursor)
            self.cursor = (self.cursor + 1) % len(_FIELDS)
        elif key in Key.UP:
            self._commit_field(self.cursor)
            self.cursor = (self.cursor - 1) % len(_FIELDS)
        elif key in BS_KEYS:
            self._bufs[self.cursor] = self._bufs[self.cursor][:-1]
        elif key == ord('-') or (ord('0') <= key <= ord('9')) or key == ord('.'):
            self._bufs[self.cursor] += chr(key)

    def _commit_field(self, idx: int):
        try:
            val = float(self._bufs[idx])
            setattr(self.state.window, _ATTRS[idx], val)
            self.state.invalidate_graph()
        except ValueError:
            self._bufs[idx] = str(getattr(self.state.window, _ATTRS[idx]))

    def _commit_all(self):
        for i in range(len(_FIELDS)):
            self._commit_field(i)
