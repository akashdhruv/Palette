from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.engine import make_numpy_func
from graph.keys import Key, BACK_KEYS, ENTER_KEYS, BS_KEYS
import numpy as np

_SOFTKEYS = ['TBLSET', 'BACK', '', '', '']


class TableScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self.tbl_start = 0.0
        self.delta_tbl = 1.0
        self.scroll    = 0        # first visible row
        self._set_mode = False    # editing TblSet dialog
        self._set_field = 0      # 0=TblStart, 1=ΔTbl
        self._set_bufs  = ['0', '1']

    def on_enter(self):
        curses.curs_set(0)

    # ------------------------------------------------------------------

    def _enabled_slots(self):
        return [(i, self.state.y_exprs[i]) for i in range(9)
                if self.state.y_exprs[i] and self.state.y_enabled[i]]

    def _compute_rows(self, n: int):
        slots = self._enabled_slots()
        rows  = []
        for r in range(n):
            x = self.tbl_start + r * self.delta_tbl
            vals = [x]
            for _, expr in slots:
                fn = make_numpy_func(expr, self.state)
                if fn is None:
                    vals.append(float('nan'))
                else:
                    try:
                        with np.errstate(all='ignore'):
                            v = float(fn(np.array([x]))[0])
                    except Exception:
                        v = float('nan')
                    vals.append(v)
            rows.append(vals)
        return slots, rows

    # ------------------------------------------------------------------

    def draw(self):
        if self._set_mode:
            self._draw_tblset()
            return

        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)

        slots   = self._enabled_slots()
        n_rows  = self.rows - 4      # rows available for data
        slots_d, rows_d = self._compute_rows(n_rows + self.scroll)

        header = 'X'.center(10) + ''.join(f'Y{i+1}'.center(10) for i, _ in slots)
        safe_addstr(self.stdscr, 1, 0, header[:self.cols], curses.color_pair(Color.STATUS_BAR))

        for r_idx, row_vals in enumerate(rows_d[self.scroll:self.scroll + n_rows]):
            row = 2 + r_idx
            line = ''
            for v in row_vals:
                import math
                s = f'{v:.6g}' if math.isfinite(v) else 'ERR'
                line += s.center(10)
            safe_addstr(self.stdscr, row, 0, line[:self.cols])

    def _draw_tblset(self):
        draw_status_bar(self.stdscr, self.state)
        safe_addstr(self.stdscr, 2, 2, 'TABLE SETUP', curses.color_pair(Color.STATUS_BAR))
        labels = ['TblStart=', 'ΔTbl=   ']
        for i, (lbl, buf) in enumerate(zip(labels, self._set_bufs)):
            attr = curses.color_pair(Color.HIGHLIGHT) if i == self._set_field else 0
            safe_addstr(self.stdscr, 4 + i, 2, f'{lbl}{buf}', attr)
        safe_addstr(self.stdscr, 7, 2, 'ENTER=OK  ESC=cancel')

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if self._set_mode:
            self._tblset_key(key)
        else:
            self._main_key(key)

    def _main_key(self, key):
        if key in BACK_KEYS + Key.F2:
            self.manager.pop()
        elif key in Key.F1:
            self._set_mode   = True
            self._set_field  = 0
            self._set_bufs   = [str(self.tbl_start), str(self.delta_tbl)]
            curses.curs_set(1)
        elif key in Key.DOWN:
            self.scroll += 1
        elif key in Key.UP:
            self.scroll = max(0, self.scroll - 1)

    def _tblset_key(self, key):
        if key in BACK_KEYS:
            self._set_mode = False
            curses.curs_set(0)
        elif key in ENTER_KEYS:
            try:
                self.tbl_start = float(self._set_bufs[0])
                self.delta_tbl = float(self._set_bufs[1]) or 1.0
            except ValueError:
                pass
            self._set_mode = False
            curses.curs_set(0)
        elif key in Key.DOWN or key in Key.UP:
            self._set_field ^= 1
        elif key in BS_KEYS:
            self._set_bufs[self._set_field] = self._set_bufs[self._set_field][:-1]
        elif key == ord('-') or (ord('0') <= key <= ord('9')) or key == ord('.'):
            self._set_bufs[self._set_field] += chr(key)
