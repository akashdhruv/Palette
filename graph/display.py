from __future__ import annotations
import curses


class Color:
    NORMAL      = 0
    HIGHLIGHT   = 1
    STATUS_BAR  = 2
    SOFTKEY_BAR = 3
    GRAPH_Y1    = 4
    GRAPH_Y2    = 5
    GRAPH_Y3    = 6
    ERROR       = 7
    DIM         = 8


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(Color.HIGHLIGHT,   curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(Color.STATUS_BAR,  curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(Color.SOFTKEY_BAR, curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(Color.GRAPH_Y1,    curses.COLOR_GREEN,  -1)
    curses.init_pair(Color.GRAPH_Y2,    curses.COLOR_YELLOW, -1)
    curses.init_pair(Color.GRAPH_Y3,    curses.COLOR_CYAN,   -1)
    curses.init_pair(Color.ERROR,       curses.COLOR_RED,    -1)
    curses.init_pair(Color.DIM,         curses.COLOR_WHITE,  -1)


def draw_status_bar(win: 'curses.window', state) -> None:
    rows, cols = win.getmaxyx()
    angle  = state.angle_mode
    mode   = state.display_mode
    ftype  = state.func_type
    left   = f' {angle}  {ftype}  {mode} '
    right  = ' TI-82 '
    middle = ' ' * max(0, cols - len(left) - len(right))
    text   = (left + middle + right)[:cols]
    try:
        win.addstr(0, 0, text, curses.color_pair(Color.STATUS_BAR))
    except curses.error:
        pass


def draw_softkey_bar(win: 'curses.window', labels: list[str]) -> None:
    rows, cols = win.getmaxyx()
    cell_w = cols // 5
    row    = rows - 1
    for i, label in enumerate(labels[:5]):
        x    = i * cell_w
        text = label[:cell_w].center(cell_w)
        try:
            win.addstr(row, x, text, curses.color_pair(Color.SOFTKEY_BAR))
        except curses.error:
            pass


def safe_addstr(
    win: 'curses.window',
    row: int,
    col: int,
    text: str,
    attr: int = 0,
) -> None:
    rows, cols = win.getmaxyx()
    if row < 0 or row >= rows or col >= cols or col < 0:
        return
    available = cols - col
    if available <= 0:
        return
    try:
        win.addstr(row, col, text[:available], attr)
    except curses.error:
        pass


def draw_box(
    win: 'curses.window',
    top: int,
    left: int,
    height: int,
    width: int,
    title: str = '',
) -> None:
    rows, cols = win.getmaxyx()
    bottom = min(top + height - 1, rows - 1)
    right  = min(left + width - 1, cols - 1)

    safe_addstr(win, top,    left,  '┌' + '─' * (width - 2) + '┐')
    safe_addstr(win, bottom, left,  '└' + '─' * (width - 2) + '┘')
    for r in range(top + 1, bottom):
        safe_addstr(win, r, left,  '│')
        safe_addstr(win, r, right, '│')
    if title:
        safe_addstr(win, top, left + 2, f' {title} ')
