from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_box, safe_addstr
from graph.keys import Key, BACK_KEYS, ENTER_KEYS

_HELP_LINES = [
    ('COMMANDS', None),
    ('help', 'Show this help screen'),
    ('exit / quit', 'Exit the calculator'),
    ('', None),
    ('NAVIGATION', None),
    ('F1 / Y=', 'Open Y= function editor'),
    ('F2 / WINDOW', 'Edit graph window settings'),
    ('F3 / ZOOM', 'Zoom menu'),
    ('F4 / TRACE', 'Trace graph'),
    ('F5 / GRAPH', 'Draw graph'),
    ('m', 'MATH menu (abs, round, nCr…)'),
    ('s', 'Statistics screen'),
    ('t', 'Table screen'),
    ('Up / Down', 'Scroll history recall'),
    ('ESC / q', 'Go back / close menu'),
    ('', None),
    ('ARITHMETIC', None),
    ('+  -  *  /', 'Basic operations'),
    ('^  or  **', 'Exponentiation  (2^8)'),
    ('%', 'Modulo  (17%5 → 2)'),
    ('()', 'Grouping  (2*(3+4))'),
    ('', None),
    ('FUNCTIONS', None),
    ('sin / cos / tan', 'Trig (obeys DEG/RAD mode)'),
    ('asin / acos / atan', 'Inverse trig'),
    ('sqrt(x)', 'Square root'),
    ('log(x)', 'Base-10 logarithm'),
    ('ln(x)', 'Natural logarithm'),
    ('abs(x)', 'Absolute value'),
    ('round(x)', 'Round to nearest integer'),
    ('iPart(x)', 'Integer part'),
    ('fPart(x)', 'Fractional part'),
    ('nCr(n,r)', 'Combinations'),
    ('nPr(n,r)', 'Permutations'),
    ('rand', 'Random number [0, 1)'),
    ('', None),
    ('VARIABLES', None),
    ('A … Z', 'Single-letter variables'),
    ('2X', 'Implicit multiply  (= 2*X)'),
    ('ANS', 'Last result'),
    ('', None),
    ('MODES  (status bar)', None),
    ('DEG / RAD', 'Angle mode (toggle in WINDOW)'),
    ('NORM / SCI / ENG', 'Display mode'),
    ('', None),
    ('SCROLLING THIS SCREEN', None),
    ('Up / Down  or  PgUp / PgDn', 'Scroll'),
    ('ESC / q / Enter', 'Close help'),
]


class HelpScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self._scroll = 0

    def on_enter(self):
        curses.curs_set(0)
        self._scroll = 0

    def draw(self):
        w = min(56, self.cols - 4)
        inner_h = self.rows - 6        # rows available for content
        h = inner_h + 4                # box height = content + top/bottom borders + title row
        top  = max(1, (self.rows - h) // 2)
        left = max(0, (self.cols - w) // 2)

        draw_box(self.stdscr, top, left, h, w, 'HELP')

        content_top  = top + 2
        content_left = left + 2
        max_lines    = inner_h

        visible = _HELP_LINES[self._scroll: self._scroll + max_lines]
        for i, (key, desc) in enumerate(visible):
            row = content_top + i
            if desc is None:
                # section header
                safe_addstr(self.stdscr, row, content_left,
                            key[:w - 4],
                            curses.color_pair(Color.STATUS_BAR))
            elif key == '':
                pass  # blank separator
            else:
                key_col  = content_left
                desc_col = content_left + 26
                safe_addstr(self.stdscr, row, key_col,  key[:24])
                if desc_col < left + w - 2:
                    safe_addstr(self.stdscr, row, desc_col, desc[:w - 28])

        # scroll hint at bottom of box
        total = len(_HELP_LINES)
        if total > max_lines:
            pct = int(100 * (self._scroll + max_lines) / total)
            hint = f' {min(pct, 100)}% -- Up/Down to scroll, ESC to close '
            safe_addstr(self.stdscr, top + h - 1, left + 2,
                        hint[:w - 4], curses.color_pair(Color.SOFTKEY_BAR))

    def handle_key(self, key):
        max_scroll = max(0, len(_HELP_LINES) - (self.rows - 6))
        if key in BACK_KEYS or key in ENTER_KEYS:
            self.manager.pop()
        elif key in Key.UP:
            self._scroll = max(0, self._scroll - 1)
        elif key in Key.DOWN:
            self._scroll = min(max_scroll, self._scroll + 1)
        elif key in (curses.KEY_PPAGE,):
            self._scroll = max(0, self._scroll - (self.rows - 8))
        elif key in (curses.KEY_NPAGE,):
            self._scroll = min(max_scroll, self._scroll + (self.rows - 8))
