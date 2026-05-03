from __future__ import annotations
import numpy as np


# Braille dot bit positions for each (col, row) sub-pixel within a cell.
# Unicode Braille base: U+2800. Final char = chr(0x2800 | mask).
#
# Dot layout (2 cols × 4 rows per character cell):
#   col=0  col=1
#   bit0   bit3   row=0
#   bit1   bit4   row=1
#   bit2   bit5   row=2
#   bit6   bit7   row=3
_BIT_TABLE = np.array([
    [0, 3],  # row 0: col0→bit0, col1→bit3
    [1, 4],  # row 1
    [2, 5],  # row 2
    [6, 7],  # row 3
], dtype=np.uint8)


class BrailleBuffer:
    """
    Pixel buffer backed by Braille character cells.
    char_cols × char_rows cells, each cell = 2×4 pixels.
    Effective resolution: (2*char_cols) × (4*char_rows) pixels.
    """

    def __init__(self, char_cols: int, char_rows: int) -> None:
        self.char_cols = char_cols
        self.char_rows = char_rows
        self.px_cols   = char_cols * 2
        self.px_rows   = char_rows * 4
        self._mask     = np.zeros((char_rows, char_cols), dtype=np.uint8)

    def clear(self) -> None:
        self._mask[:] = 0

    def set_pixel(self, px_col: int, px_row: int) -> None:
        if px_col < 0 or px_col >= self.px_cols:
            return
        if px_row < 0 or px_row >= self.px_rows:
            return
        cc       = px_col // 2
        cr       = px_row // 4
        local_c  = px_col % 2
        local_r  = px_row % 4
        bit      = int(_BIT_TABLE[local_r, local_c])
        self._mask[cr, cc] |= np.uint8(1 << bit)

    def set_pixel_batch(
        self,
        px_cols: np.ndarray,
        px_rows: np.ndarray,
    ) -> None:
        valid = (
            (px_cols >= 0) & (px_cols < self.px_cols) &
            (px_rows >= 0) & (px_rows < self.px_rows)
        )
        c = px_cols[valid].astype(np.int64)
        r = px_rows[valid].astype(np.int64)
        if c.size == 0:
            return
        cc = (c // 2).astype(np.int64)
        cr = (r // 4).astype(np.int64)
        lc = (c % 2).astype(np.int64)
        lr = (r % 4).astype(np.int64)
        bits = _BIT_TABLE[lr, lc]
        np.bitwise_or.at(self._mask, (cr, cc), np.uint8(1) << bits)

    def render(self) -> list[str]:
        rows = []
        for r in range(self.char_rows):
            row_str = ''.join(
                chr(0x2800 | int(self._mask[r, c]))
                for c in range(self.char_cols)
            )
            rows.append(row_str)
        return rows


# ---------------------------------------------------------------------------
# Self-test: render a sine wave and print to stdout
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import math
    COLS, ROWS = 60, 15
    buf = BrailleBuffer(COLS, ROWS)
    px_cols = []
    px_rows = []
    for px in range(buf.px_cols):
        x     = (px / buf.px_cols) * 4 * math.pi
        y     = math.sin(x)
        py    = int((1 - (y + 1) / 2) * (buf.px_rows - 1))
        px_cols.append(px)
        px_rows.append(py)
    buf.set_pixel_batch(
        np.array(px_cols, dtype=np.int64),
        np.array(px_rows, dtype=np.int64),
    )
    print('+' + '-' * COLS + '+')
    for row in buf.render():
        print('|' + row + '|')
    print('+' + '-' * COLS + '+')
    print('Braille sine wave test passed.')
