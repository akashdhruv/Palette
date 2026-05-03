"""graph — plot equations in the terminal using Braille characters.

Usage:
    graph [OPTIONS] eq1 [eq2 ...]

Options:
    --xmin FLOAT    left x bound   (default -10)
    --xmax FLOAT    right x bound  (default  10)
    --ymin FLOAT    bottom y bound (default auto)
    --ymax FLOAT    top y bound    (default auto)
    --width  INT    output width in chars  (default: terminal width)
    --height INT    output height in chars (default: terminal height / 3)
    --deg           use degree mode for trig functions
    --no-axes       omit axis lines
"""

from __future__ import annotations
import sys
import argparse
import shutil
import math
import numpy as np

from graph.state import CalcState, WindowVars
from graph.braille import BrailleBuffer
from graph.engine import make_numpy_func


def _fmt(val: float) -> str:
    if val == 0:
        return '0'
    if val == int(val) and abs(val) < 1e7:
        return str(int(val))
    return f'{val:.4g}'


def _sample(eq: str, state: CalcState, x_arr: np.ndarray) -> np.ndarray | None:
    fn = make_numpy_func(eq, state)
    if fn is None:
        return None
    try:
        with np.errstate(all='ignore'):
            y = fn(x_arr)
            return np.where(np.isfinite(y), y, np.nan)
    except Exception:
        return None


def _autofit_y(equations: list[str], state: CalcState, x_arr: np.ndarray) -> tuple[float, float]:
    extremes: list[float] = []
    for eq in equations:
        y = _sample(eq, state, x_arr)
        if y is None:
            continue
        valid = y[np.isfinite(y)]
        if valid.size:
            extremes.extend([float(valid.min()), float(valid.max())])
    if not extremes:
        return -10.0, 10.0
    ymin, ymax = min(extremes), max(extremes)
    margin = (ymax - ymin) * 0.1 or 1.0
    return ymin - margin, ymax + margin


def plot(
    equations: list[str],
    *,
    xmin: float = -10.0,
    xmax: float = 10.0,
    ymin: float = -10.0,
    ymax: float = 10.0,
    char_cols: int = 80,
    char_rows: int = 24,
    angle_mode: str = 'RAD',
    show_axes: bool = True,
) -> None:
    state = CalcState()
    state.angle_mode = angle_mode
    state.window = WindowVars(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
    buf = BrailleBuffer(char_cols, char_rows)
    w = state.window

    px_w = buf.px_cols
    px_h = buf.px_rows
    x_range = w.xmax - w.xmin
    y_range = w.ymax - w.ymin

    def wx_to_px(xw: float) -> float:
        return (xw - w.xmin) / x_range * (px_w - 1)

    def wy_to_py(yw: float) -> float:
        return (w.ymax - yw) / y_range * (px_h - 1)

    # Axes
    if show_axes:
        if w.ymin <= 0 <= w.ymax:
            y0 = int(round(wy_to_py(0)))
            for px in range(px_w):
                buf.set_pixel(px, y0)
        if w.xmin <= 0 <= w.xmax:
            x0 = int(round(wx_to_px(0)))
            for py in range(px_h):
                buf.set_pixel(x0, py)

    # Functions
    x_arr = np.linspace(xmin, xmax, px_w)
    for i, eq in enumerate(equations[:9]):
        if not eq.strip():
            continue
        y_arr = _sample(eq, state, x_arr)
        if y_arr is None:
            print(f'  error: could not parse "{eq}"', file=sys.stderr)
            continue
        px_c = np.arange(px_w, dtype=np.float64)
        px_r = (w.ymax - y_arr) / y_range * (px_h - 1)
        valid = np.isfinite(px_r)
        c_v = px_c[valid].astype(np.int64)
        r_v = np.clip(np.round(px_r[valid]), 0, px_h - 1).astype(np.int64)
        buf.set_pixel_batch(c_v, r_v)

    rows = buf.render()

    # Y-axis label width
    y_labels = {
        0:              _fmt(ymax),
        char_rows // 2: _fmt((ymax + ymin) / 2),
        char_rows - 1:  _fmt(ymin),
    }
    lw = max(len(v) for v in y_labels.values())

    for r_idx, row in enumerate(rows):
        lbl = y_labels.get(r_idx, '')
        print(f'{lbl.rjust(lw)} │{row}')

    # X-axis labels
    pad = ' ' * (lw + 2)
    xmin_s = _fmt(xmin)
    xmid_s = _fmt((xmin + xmax) / 2)
    xmax_s = _fmt(xmax)

    mid_col = char_cols // 2 - len(xmid_s) // 2
    gap_before = mid_col - len(xmin_s)
    gap_after = char_cols - mid_col - len(xmid_s) - len(xmax_s)
    x_line = pad + xmin_s
    if gap_before > 0:
        x_line += ' ' * gap_before + xmid_s
    if gap_after > 0:
        x_line += ' ' * gap_after
    x_line += xmax_s
    print(x_line)


def main() -> None:
    p = argparse.ArgumentParser(
        prog='graph',
        description='Plot equations in the terminal (Braille rendering).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('equations', nargs='+', metavar='EQ',
                   help='Equation(s) in terms of x (quote each one)')
    p.add_argument('--xmin',   type=float, default=-10.0)
    p.add_argument('--xmax',   type=float, default=10.0)
    p.add_argument('--ymin',   type=float, default=None)
    p.add_argument('--ymax',   type=float, default=None)
    p.add_argument('--width',  type=int,   default=None)
    p.add_argument('--height', type=int,   default=None)
    p.add_argument('--deg',    action='store_true', help='Degree mode for trig')
    p.add_argument('--no-axes', dest='no_axes', action='store_true')
    args = p.parse_args()

    term = shutil.get_terminal_size((80, 24))
    char_cols = args.width  or max(40, term.columns - 12)
    char_rows = args.height or max(10, (term.lines * 2) // 5)

    angle_mode = 'DEG' if args.deg else 'RAD'
    state = CalcState()
    state.angle_mode = angle_mode
    state.window = WindowVars(xmin=args.xmin, xmax=args.xmax)

    # Auto-fit y bounds from sampled values
    x_probe = np.linspace(args.xmin, args.xmax, char_cols * 2)
    ymin, ymax = _autofit_y(args.equations, state, x_probe)
    ymin = args.ymin if args.ymin is not None else ymin
    ymax = args.ymax if args.ymax is not None else ymax
    if ymin >= ymax:
        ymin, ymax = ymax - 1.0, ymax + 1.0

    # Header
    for i, eq in enumerate(args.equations):
        tag = f'Y{i + 1}' if len(args.equations) > 1 else 'Y'
        print(f'  {tag} = {eq}')
    print()

    plot(
        args.equations,
        xmin=args.xmin,
        xmax=args.xmax,
        ymin=ymin,
        ymax=ymax,
        char_cols=char_cols,
        char_rows=char_rows,
        angle_mode=angle_mode,
        show_axes=not args.no_axes,
    )


if __name__ == '__main__':
    main()
