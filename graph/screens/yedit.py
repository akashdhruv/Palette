from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.keys import Key, BACK_KEYS, ENTER_KEYS, BS_KEYS

_SOFTKEYS = ['BACK', '', '', '', '']


class YEditScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self.cursor    = 0
        self.edit_mode = False
        self._orig: str = ''

    def on_enter(self):
        curses.curs_set(0)

    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)
        safe_addstr(self.stdscr, 1, 0, 'Y= Functions', curses.color_pair(Color.STATUS_BAR))

        for i in range(9):
            row  = 2 + i
            en   = self.state.y_enabled[i]
            expr = self.state.y_exprs[i]
            flag = '*' if en else ' '

            if i == self.cursor and self.edit_mode:
                line = f'[{flag}]Y{i + 1}={expr}_'
                attr = curses.color_pair(Color.HIGHLIGHT)
            elif i == self.cursor:
                line = f'[{flag}]Y{i + 1}={expr}'
                attr = curses.color_pair(Color.HIGHLIGHT)
            else:
                line = f' {flag} Y{i + 1}={expr}'
                attr = 0

            safe_addstr(self.stdscr, row, 0, line[:self.cols].ljust(self.cols - 1), attr)

        if self.edit_mode:
            curses.curs_set(1)
            # position cursor after '='
            col = len(f'[*]Y{self.cursor + 1}=') + len(self.state.y_exprs[self.cursor])
            try:
                self.stdscr.move(2 + self.cursor, min(col, self.cols - 1))
            except curses.error:
                pass
        else:
            curses.curs_set(0)

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if self.edit_mode:
            self._edit_key(key)
        else:
            self._nav_key(key)

    def _nav_key(self, key):
        if key in BACK_KEYS + Key.F1:
            self.manager.pop()
        elif key in Key.UP:
            self.cursor = max(0, self.cursor - 1)
        elif key in Key.DOWN:
            self.cursor = min(8, self.cursor + 1)
        elif key in ENTER_KEYS:
            self._orig = self.state.y_exprs[self.cursor]
            self.edit_mode = True
            curses.curs_set(1)
        elif key in (ord(' '),) + Key.TAB:
            self.state.y_enabled[self.cursor] = not self.state.y_enabled[self.cursor]
            self.state.invalidate_graph()
        elif key in BS_KEYS:
            self.state.y_exprs[self.cursor] = ''
            self.state.invalidate_graph()

    def _edit_key(self, key):
        if key in ENTER_KEYS or key in Key.UP or key in Key.DOWN:
            self._commit()
            if key in Key.UP:
                self.cursor = max(0, self.cursor - 1)
            elif key in Key.DOWN:
                self.cursor = min(8, self.cursor + 1)
        elif key in BACK_KEYS:
            # cancel edit
            self.state.y_exprs[self.cursor] = self._orig
            self.edit_mode = False
        elif key in BS_KEYS:
            self.state.y_exprs[self.cursor] = self.state.y_exprs[self.cursor][:-1]
        elif 32 <= key < 127:
            self.state.y_exprs[self.cursor] += chr(key)

    def _commit(self):
        self.edit_mode = False
        self.state.invalidate_graph()
        curses.curs_set(0)
