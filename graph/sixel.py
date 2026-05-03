"""Convert a matplotlib Figure to a sixel byte stream for inline terminal display.

Sixel format summary:
  DCS q <color-defs> <band-data> ST
  Each band = 6 pixel rows.  Each character = bitmask of 6 pixels + 63.
  Color:  #idx;2;r;g;b  (r/g/b in 0-100).
  $  = carriage-return within a band (next colour overlays same band).
  -  = advance to next band.
  !n = repeat next char n times (RLE).
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


def _encode(img: Image.Image, max_colors: int = 128) -> bytes:
    img = img.convert('RGB')
    w, h = img.size

    # Pad height to a multiple of 6 (one sixel band = 6 rows).
    rem = h % 6
    if rem:
        canvas = Image.new('RGB', (w, h + 6 - rem), (255, 255, 255))
        canvas.paste(img, (0, 0))
        img = canvas
        h = img.height

    q   = img.quantize(colors=max_colors, dither=0)
    pal = q.getpalette()          # flat [r,g,b, r,g,b, ...] × 256
    px  = np.array(q, dtype=np.uint8)  # (h, w)

    out = bytearray(b'\x1bPq')

    # Emit colour definitions only for colours actually in the image.
    used = np.unique(px)
    for c in used:
        r = round(pal[c * 3]     * 100 / 255)
        g = round(pal[c * 3 + 1] * 100 / 255)
        b = round(pal[c * 3 + 2] * 100 / 255)
        out += f'#{c};2;{r};{g};{b}'.encode()

    # Sixel bands — 6 pixel rows each.
    for y0 in range(0, h, 6):
        band       = px[y0 : y0 + 6]   # shape (≤6, w)
        n_rows     = band.shape[0]
        band_cols  = np.unique(band)

        need_cr = False
        for c in band_cols:
            # Build per-pixel bitmask: bit k set ↔ row k of this band is colour c.
            mask = np.zeros(w, dtype=np.uint8)
            for bit in range(n_rows):
                mask |= (band[bit] == c).astype(np.uint8) << bit

            if not mask.any():
                continue

            if need_cr:
                out += b'$'     # carriage-return: next colour overlays same band
            need_cr = True
            out += f'#{c}'.encode()

            # RLE-encode sixel characters (sixel char = pixel-mask + 63).
            chars = mask + np.uint8(63)
            diffs  = np.diff(chars.view(np.int16))   # avoid uint wrap
            starts = np.concatenate(([0], np.where(diffs)[0] + 1))
            ends   = np.concatenate((np.where(diffs)[0] + 1, [w]))
            for s, e in zip(starts, ends):
                run = int(e - s)
                ch  = int(chars[s])
                if run >= 4:
                    out += f'!{run}{chr(ch)}'.encode()
                else:
                    out += bytes([ch] * run)

        if y0 + 6 < h:
            out += b'-'     # advance to next band

    out += b'\x1b\\'        # ST — end of sixel data
    return bytes(out)


def fig_to_sixel(fig: Figure) -> bytes:
    """Render a matplotlib Figure and return sixel bytes.

    The figure's canvas must already have been drawn (call canvas.draw()
    or fig.tight_layout() before calling this).
    """
    buf = io.BytesIO()
    fig.canvas.print_png(buf)
    buf.seek(0)
    img = Image.open(buf).copy()    # .copy() detaches from the BytesIO
    return _encode(img)


def emit(sixel_bytes: bytes) -> None:
    """Write sixel bytes to stdout on a fresh line, cursor left after."""
    import sys
    sys.stdout.buffer.write(b'\r')
    sys.stdout.buffer.write(sixel_bytes)
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()
