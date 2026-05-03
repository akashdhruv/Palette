from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, safe_addstr, draw_box
from graph.keys import Key, BACK_KEYS, ENTER_KEYS


class MenuScreen(BaseScreen):
    """Generic numbered pop-up menu overlay."""

    def __init__(self, manager, title: str, items: list[str], callbacks: list):
        super().__init__(manager)
        self.title     = title
        self.items     = items
        self.callbacks = callbacks
        self.cursor    = 0

    def on_enter(self):
        curses.curs_set(0)

    def draw(self):
        w = min(30, self.cols - 4)
        h = len(self.items) + 4
        top  = max(1, (self.rows - h) // 2)
        left = max(0, (self.cols - w) // 2)

        draw_box(self.stdscr, top, left, h, w, self.title)

        for i, item in enumerate(self.items):
            attr = curses.color_pair(Color.HIGHLIGHT) if i == self.cursor else 0
            label = f'{i + 1}. {item}'
            safe_addstr(self.stdscr, top + 2 + i, left + 2, label.ljust(w - 4)[:w - 4], attr)

    def handle_key(self, key):
        if key in BACK_KEYS:
            self.manager.pop()
        elif key in Key.UP and self.cursor > 0:
            self.cursor -= 1
        elif key in Key.DOWN and self.cursor < len(self.items) - 1:
            self.cursor += 1
        elif key in ENTER_KEYS:
            self._execute(self.cursor)
        else:
            # digit shortcut
            digit = key - ord('1')
            if 0 <= digit < len(self.items):
                self._execute(digit)

    def _execute(self, idx: int):
        self.manager.pop()
        if callable(self.callbacks[idx]):
            self.callbacks[idx]()
