from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.keys import Key, BACK_KEYS, ENTER_KEYS, BS_KEYS

_SOFTKEYS = ['', 'CALC', '', '', 'BACK']
_LIST_NAMES = [f'L{i}' for i in range(1, 7)]


class StatScreen(BaseScreen):
    """3-column list editor for L1–L6."""

    def __init__(self, manager):
        super().__init__(manager)
        self.col_start = 0    # first visible list (0–3)
        self.row       = 0    # cursor row within list
        self.col       = 0    # cursor col within visible 3
        self._edit_buf = ''
        self._editing  = False

    def on_enter(self):
        curses.curs_set(0)

    def _list_name(self, vis_col: int) -> str:
        return _LIST_NAMES[self.col_start + vis_col]

    def _list_data(self, vis_col: int) -> list:
        return self.state.lists[self._list_name(vis_col)]

    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)

        col_w = (self.cols) // 3

        # header
        for vc in range(3):
            name = self._list_name(vc)
            attr = curses.color_pair(Color.STATUS_BAR) if vc == self.col else curses.color_pair(Color.DIM)
            safe_addstr(self.stdscr, 1, vc * col_w, name.center(col_w)[:col_w], attr)

        data_rows = self.rows - 4
        for vc in range(3):
            lst = self._list_data(vc)
            for r in range(data_rows):
                row_idx = r
                if row_idx < len(lst):
                    if self._editing and vc == self.col and row_idx == self.row:
                        val = self._edit_buf + '_'
                    else:
                        val = f'{lst[row_idx]:.6g}'
                elif self._editing and vc == self.col and row_idx == self.row:
                    val = self._edit_buf + '_'
                else:
                    val = ''

                attr = curses.color_pair(Color.HIGHLIGHT) if (vc == self.col and row_idx == self.row) else 0
                safe_addstr(self.stdscr, 2 + r, vc * col_w, val[:col_w].rjust(col_w), attr)

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if self._editing:
            self._edit_key(key)
        else:
            self._nav_key(key)

    def _nav_key(self, key):
        if key in BACK_KEYS + Key.F5:
            self.manager.pop()
        elif key in Key.F2:
            self.manager.push('stat_calc')
        elif key in Key.LEFT and self.col_start > 0:
            self.col_start -= 1
        elif key in Key.RIGHT and self.col_start < 3:
            self.col_start += 1
        elif key in Key.UP:
            self.row = max(0, self.row - 1)
        elif key in Key.DOWN:
            self.row += 1
        elif key in ENTER_KEYS or (32 <= key < 127):
            self._editing  = True
            self._edit_buf = '' if key in ENTER_KEYS else chr(key)
            curses.curs_set(1)

    def _edit_key(self, key):
        if key in BACK_KEYS:
            self._editing  = False
            self._edit_buf = ''
            curses.curs_set(0)
        elif key in ENTER_KEYS:
            self._commit()
        elif key in BS_KEYS:
            self._edit_buf = self._edit_buf[:-1]
        elif key == ord('-') or (ord('0') <= key <= ord('9')) or key == ord('.'):
            self._edit_buf += chr(key)

    def _commit(self):
        try:
            val = float(self._edit_buf)
            lst = self._list_data(self.col)
            # extend if needed
            while len(lst) <= self.row:
                lst.append(0.0)
            lst[self.row] = val
            self.row += 1
        except ValueError:
            pass
        self._editing  = False
        self._edit_buf = ''
        curses.curs_set(0)
