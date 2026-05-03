from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.engine import evaluate
from graph.keys import Key, BACK_KEYS, ENTER_KEYS, BS_KEYS

_SOFTKEYS = ['Y=', 'WINDOW', 'ZOOM', 'TRACE', 'GRAPH']

_MATH_ITEMS = ['abs(', 'round(', 'iPart(', 'fPart(', 'nCr(', 'nPr(', 'rand']


class HomeScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self._history_recall = -1   # index into history for ↑ recall

    def on_enter(self):
        curses.curs_set(1)

    def on_resume(self):
        curses.curs_set(1)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)

        input_row  = self.rows - 2
        hist_start = 1
        hist_end   = input_row - 1

        # draw history (newest at bottom)
        visible_rows = hist_end - hist_start + 1
        hist = self.state.history[-visible_rows:]
        for i, (expr, result) in enumerate(hist):
            row = hist_start + (visible_rows - len(hist)) + i
            safe_addstr(self.stdscr, row, 0, expr[:self.cols])
            r_str = result[:self.cols]
            safe_addstr(self.stdscr, row, self.cols - len(r_str), r_str)

        # input line
        buf = self.state.input_buffer
        prompt = '> '
        safe_addstr(self.stdscr, input_row, 0, prompt + buf[:self.cols - 2])
        # position cursor
        cx = len(prompt) + min(self.state.cursor_pos, self.cols - 3)
        try:
            self.stdscr.move(input_row, cx)
        except curses.error:
            pass

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def handle_key(self, key):
        if key in Key.F1:
            self.manager.replace('yedit')
        elif key in Key.F2:
            self.manager.replace('window')
        elif key in Key.F3:
            self.manager.push('zoom')
        elif key in Key.F4:
            self.manager.push('trace')
        elif key in Key.F5:
            self.manager.replace('graph')
        elif key == ord('m') and not self.state.input_buffer:
            self._open_math_menu()
        elif key == ord('s') and not self.state.input_buffer:
            self.manager.replace('stat')
        elif key == ord('t') and not self.state.input_buffer:
            self.manager.replace('table')
        elif key in ENTER_KEYS:
            self._evaluate()
        elif key in BS_KEYS:
            self._backspace()
        elif key in Key.LEFT:
            self.state.cursor_pos = max(0, self.state.cursor_pos - 1)
        elif key in Key.RIGHT:
            self.state.cursor_pos = min(len(self.state.input_buffer), self.state.cursor_pos + 1)
        elif key in Key.UP:
            self._history_up()
        elif key in Key.DOWN:
            self._history_down()
        elif key in BACK_KEYS:
            pass   # can't exit home screen
        elif 32 <= key < 127:
            self._insert(chr(key))
            self._history_recall = -1

    # ------------------------------------------------------------------

    def _insert(self, ch: str):
        buf = self.state.input_buffer
        pos = self.state.cursor_pos
        self.state.input_buffer = buf[:pos] + ch + buf[pos:]
        self.state.cursor_pos   = pos + 1

    def _backspace(self):
        pos = self.state.cursor_pos
        if pos > 0:
            buf = self.state.input_buffer
            self.state.input_buffer = buf[:pos - 1] + buf[pos:]
            self.state.cursor_pos   = pos - 1
        self._history_recall = -1

    def _evaluate(self):
        expr = self.state.input_buffer.strip()
        if not expr:
            return
        cmd = expr.lower()
        if cmd == 'help':
            self.state.input_buffer = ''
            self.state.cursor_pos   = 0
            self._history_recall    = -1
            self.manager.push('help')
            return
        if cmd in ('exit', 'quit'):
            self.manager.quit()
            return
        result = evaluate(expr, self.state)
        self.state.push_history(expr, result.display)
        self.state.input_buffer = ''
        self.state.cursor_pos   = 0
        self._history_recall    = -1

    def _history_up(self):
        hist = self.state.history
        if not hist:
            return
        if self._history_recall == -1:
            self._history_recall = len(hist) - 1
        elif self._history_recall > 0:
            self._history_recall -= 1
        self.state.input_buffer = hist[self._history_recall][0]
        self.state.cursor_pos   = len(self.state.input_buffer)

    def _history_down(self):
        hist = self.state.history
        if self._history_recall == -1:
            return
        if self._history_recall < len(hist) - 1:
            self._history_recall += 1
            self.state.input_buffer = hist[self._history_recall][0]
        else:
            self._history_recall    = -1
            self.state.input_buffer = ''
        self.state.cursor_pos = len(self.state.input_buffer)

    def _open_math_menu(self):
        def insert_fn(fn):
            return lambda: self._insert_and_enter(fn)

        cbs = [insert_fn(f) for f in _MATH_ITEMS]

        from graph.screens.menu import MenuScreen
        screen = MenuScreen(self.manager, 'MATH', _MATH_ITEMS, cbs)
        self.manager._stack.append(screen)
        screen.on_enter()

    def _insert_and_enter(self, text: str):
        self.state.input_buffer = text
        self.state.cursor_pos   = len(text)
