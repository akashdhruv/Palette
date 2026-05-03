from __future__ import annotations
import curses
import math
import statistics
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.keys import Key, BACK_KEYS

_SOFTKEYS = ['1-Var', 'LinReg', '', '', 'BACK']


def _one_var(data: list[float]) -> dict[str, str]:
    if not data:
        return {'Error': 'L1 is empty'}
    n    = len(data)
    mean = sum(data) / n
    sx   = sum(x * x for x in data)
    sx2  = sx
    try:
        s  = statistics.stdev(data)
        sg = statistics.pstdev(data)
    except Exception:
        s  = sg = 0.0
    sdata = sorted(data)
    med   = statistics.median(sdata)
    q1    = sdata[n // 4] if n >= 4 else sdata[0]
    q3    = sdata[3 * n // 4] if n >= 4 else sdata[-1]
    return {
        'x̄':   f'{mean:.6g}',
        'Σx':  f'{sum(data):.6g}',
        'Σx²': f'{sx2:.6g}',
        'Sx':  f'{s:.6g}',
        'σx':  f'{sg:.6g}',
        'n':   str(n),
        'minX':f'{sdata[0]:.6g}',
        'Q1':  f'{q1:.6g}',
        'Med': f'{med:.6g}',
        'Q3':  f'{q3:.6g}',
        'maxX':f'{sdata[-1]:.6g}',
    }


def _lin_reg(xs: list[float], ys: list[float]) -> dict[str, str]:
    n = min(len(xs), len(ys))
    if n < 2:
        return {'Error': 'Need ≥2 pts'}
    xs = xs[:n]; ys = ys[:n]
    mx = sum(xs) / n; my = sum(ys) / n
    ssxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    ssxx = sum((x - mx) ** 2 for x in xs)
    if ssxx == 0:
        return {'Error': 'All X same'}
    a = ssxy / ssxx
    b = my - a * mx
    # r
    ssyy = sum((y - my) ** 2 for y in ys)
    r    = ssxy / math.sqrt(ssxx * ssyy) if ssxx * ssyy > 0 else 0.0
    return {
        'a':  f'{a:.6g}',
        'b':  f'{b:.6g}',
        'r':  f'{r:.6g}',
        'r²': f'{r*r:.6g}',
    }


class StatCalcScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self._results: dict[str, str] = {}
        self._title = ''

    def on_enter(self):
        curses.curs_set(0)
        self._run_1var()

    # ------------------------------------------------------------------

    def _run_1var(self):
        data = self.state.lists.get('L1', [])
        self._results = _one_var(data)
        self._title   = '1-Var Stats (L1)'
        self.state.stat1var = {k: v for k, v in self._results.items()}

    def _run_linreg(self):
        xs = self.state.lists.get('L1', [])
        ys = self.state.lists.get('L2', [])
        self._results = _lin_reg(xs, ys)
        self._title   = 'LinReg(ax+b) L1,L2'
        self.state.reg_coeffs = {k: v for k, v in self._results.items()}
        self.state.last_reg_type = 'LinReg'

    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)
        safe_addstr(self.stdscr, 1, 0, self._title, curses.color_pair(Color.STATUS_BAR))

        for i, (k, v) in enumerate(self._results.items()):
            row = 2 + i
            if row >= self.rows - 1:
                break
            safe_addstr(self.stdscr, row, 2, f'{k}={v}')

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if key in BACK_KEYS + Key.F5:
            self.manager.pop()
        elif key in Key.F1:
            self._run_1var()
        elif key in Key.F2:
            self._run_linreg()
