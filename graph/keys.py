import curses

class Key:
    ENTER = (10, 13, curses.KEY_ENTER)
    BS    = (127, curses.KEY_BACKSPACE, 8)
    ESC   = (27,)
    F1 = (curses.KEY_F1,)
    F2 = (curses.KEY_F2,)
    F3 = (curses.KEY_F3,)
    F4 = (curses.KEY_F4,)
    F5 = (curses.KEY_F5,)
    UP   = (curses.KEY_UP,)
    DOWN = (curses.KEY_DOWN,)
    LEFT = (curses.KEY_LEFT,)
    RIGHT = (curses.KEY_RIGHT,)
    TAB  = (9,)
    SPACE = (32,)

BACK_KEYS  = Key.ESC + (ord('q'),)
ENTER_KEYS = Key.ENTER
BS_KEYS    = Key.BS

SOFTKEY_MAP = {
    curses.KEY_F1: 'F1',
    curses.KEY_F2: 'F2',
    curses.KEY_F3: 'F3',
    curses.KEY_F4: 'F4',
    curses.KEY_F5: 'F5',
}

def is_key(k, group):
    return k in group
