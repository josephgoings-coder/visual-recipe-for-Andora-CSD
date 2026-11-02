#!/usr/bin/env python3
"""Remove the English labels, coloured leader lines and endpoint dots from source.png -> clean.png.

All leader lines in this illustration are horizontal, drawn as a coloured core (~4 px) with a white
halo (total ~10-11 px), ending in a coloured dot with a white ring (outer radius ~7 px). Positions
below were measured from the image (colour-distance runs + zoomed crops, see README of the poster
work), not guessed.

Filling strategy
- Text (always in the near-white margin): colour/darkness mask, dilated, then cv2.inpaint (TELEA).
- Line band and dot (also where they cross organs or skin): filled column by column from the texture
  just above and below the band, following the local structure direction so slanted organ outlines
  continue straight through (see fill_band). Because the lines are horizontal this keeps the organ
  texture (lung vessels, liver sheen, intestine folds) instead of the smooth smear that cv2.inpaint
  leaves on a 13-px band.
"""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = cv2.imread(os.path.join(HERE, 'source.png'))
img = src.copy()
H, W = img.shape[:2]

# name, text colour (BGR), dot centre (x, y), line y, text box (x0, y0, x1, y1), side of text
LEADERS = [
    ('Lungs',           (102, 36, 200), (345.5, 409.5), 409.3, (36, 382, 160, 438), 'L'),
    ('Heart',           (14, 13, 222),  (594.0, 486.8), 486.7, (866, 462, 992, 508), 'R'),
    ('Liver',           (25, 48, 129),  (331.7, 661.3), 662.0, (36, 634, 136, 684), 'L'),
    ('Stomach',         (15, 101, 248), (651.4, 687.2), 687.2, (842, 665, 992, 710), 'R'),
    ('Spleen',          (162, 55, 130), (702.2, 771.0), 771.5, (852, 748, 990, 802), 'R'),
    ('Kidneys',         (190, 99, 11),  (334.3, 878.2), 878.2, (36, 852, 186, 910), 'L'),
    ('Pancreas',        (16, 148, 215), (690.8, 861.6), 861.6, (842, 840, 992, 884), 'R'),
    ('Large Intestine', (75, 125, 43),  (301.7, 1104.8), 1105.6, (36, 1080, 196, 1174), 'L'),
    ('Small Intestine', (129, 86, 208), (631.7, 1117.4), 1117.8, (836, 1088, 990, 1184), 'R'),
]

LINE_HALF = 8     # half height of the line band (core + white halo + antialias)
TELEA_DOTS = {'Small Intestine'}
DOT_R = 11        # radius of the dot mask (dot + white ring + antialias)

def sample(row, xf):
    """Bilinear sample of src along one row at fractional x."""
    x0 = int(np.floor(xf)); f = xf - x0
    x0 = min(max(x0, 0), W - 2)
    return (1 - f) * src[row, x0].astype(float) + f * src[row, x0 + 1].astype(float)


def edge_shift(x, top, bot, G, smax):
    """Horizontal displacement s (over the gap G) that best aligns the structure above and below."""
    gray = srcf_gray
    best, best_s = None, 0
    u = np.arange(-12, 13)
    for s2 in range(-smax, smax + 1):
        s = s2 / 2.0
        cost = 0.0
        for r in (1, 2, 3, 4, 5):
            ya, yb = top - r, bot + r
            da = s * (r - 0.5 + G / 2) / G         # edge position offset at row ya
            xa = np.clip(np.round(x - da + u).astype(int), 0, W - 1)
            xb = np.clip(np.round(x + da + u).astype(int), 0, W - 1)
            cost += np.sum((gray[ya, xa] - gray[yb, xb]) ** 2)
        cost += 40.0 * abs(s)                       # prefer straight down on flat texture
        if best is None or cost < best:
            best, best_s = cost, s
    return best_s


def fill_band(band, cx):
    """Fill a horizontal band (line + dot) from the texture above and below it.

    For every column the local structure direction across the band is estimated (edge_shift);
    each pixel gets its colour from a linear interpolation along that direction between the rows
    just outside the band (seamless; slanted organ outlines run straight through), plus the fine
    detail of a copy taken one band-height above / below along the same direction (keeps the
    texture, e.g. lung vessels). Near strong outlines only the interpolation is used."""
    cols = np.where(band.max(0) > 0)[0]
    shifts = {}
    for x in cols:
        rows = np.where(band[:, x] > 0)[0]
        top, bot = rows.min(), rows.max()
        G = bot - top + 2
        shifts[x] = edge_shift(x, top, bot, G, smax=2 * G)
    xs = sorted(shifts)
    sm = {x: float(np.median([shifts[c] for c in xs[max(0, i - 4):i + 5]])) for i, x in enumerate(xs)}
    # near strong outlines (organ / body contours) use only the directional interpolation: copied
    # texture would put a curved outline in the wrong place. Edge strength = horizontal gradient in
    # the rows just outside the band, within +-3 columns.
    edge = {}
    for x in cols:
        rows = np.where(band[:, x] > 0)[0]
        top, bot = rows.min(), rows.max()
        e = 0.0
        for r in (top - 2, top - 1, bot + 1, bot + 2):
            seg = srcf_gray[r, max(x - 4, 0):x + 5]
            e = max(e, np.abs(np.diff(seg)).max())
        edge[x] = e
    LIN = img.astype(float).copy()   # directional interpolation (structure + colour)
    CP = src.astype(float).copy()    # texture copy (only its fine detail is used)
    WT = np.zeros((H, W), float)
    for x in cols:
        rows = np.where(band[:, x] > 0)[0]
        top, bot = rows.min(), rows.max()
        G = bot - top + 2
        s = sm[x]
        tex = float(np.clip((60.0 - edge[x]) / 35.0, 0.0, 1.0))
        for yy in range(top, bot + 1):
            k = yy - top
            t = (k + 1) / G
            # directional linear interpolation between the rows just outside the band
            LIN[yy, x] = (1 - t) * sample(top - 1, x - t * s) + t * sample(bot + 1, x + (1 - t) * s)
            # texture copies one gap above / below along the structure direction
            up = sample(max(yy - G, 0), x - s)
            dn = sample(min(yy + G, H - 1), x + s)
            CP[yy, x] = (1 - t) * up + t * dn
            d_edge = min(k + 1, G - 1 - k)            # distance to the nearest untouched row
            WT[yy, x] = min(1.0, d_edge / 2.0) * tex
    # colour/brightness from the interpolation, fine texture (vessels, grain) from the copy
    detail = CP - cv2.GaussianBlur(CP, (0, 0), 2.0)
    out = LIN + WT[..., None] * detail
    m = band > 0
    img[m] = np.clip(out[m], 0, 255).astype(np.uint8)

srcf_gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(float)
text_mask = np.zeros((H, W), np.uint8)
band_mask = np.zeros((H, W), np.uint8)

for name, col, (dx, dy), ly, (tx0, ty0, tx1, ty1), side in LEADERS:
    # --- text: anything noticeably different from the white margin inside the text box
    roi = src[ty0:ty1, tx0:tx1].astype(int)
    border = np.concatenate([roi[0], roi[-1], roi[:, 0], roi[:, -1]])
    bg = np.median(border, 0)
    m = ((np.abs(roi - bg).sum(2) > 12).astype(np.uint8)) * 255   # glyphs incl. antialiasing
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    text_mask[ty0:ty1, tx0:tx1] |= m

    # --- line band from the dot to the text box edge
    x_text = tx1 if side == 'L' else tx0
    xa, xb = sorted((int(round(dx)), x_text))
    y = int(round(ly))
    band = np.zeros((H, W), np.uint8)
    band[y - LINE_HALF:y + LINE_HALF + 1, xa:xb + 1] = 255
    cv2.circle(band, (int(round(dx)), int(round(dy))), DOT_R, 255, -1)
    band_mask |= band

    fill_band(band, int(round(dx)))
    if name in TELEA_DOTS:
        # dot sits on tightly curved small-intestine folds: a smooth inpaint looks cleaner there
        dm = np.zeros((H, W), np.uint8)
        cv2.circle(dm, (int(round(dx)), int(round(dy))), DOT_R, 255, -1)
        img[:] = cv2.inpaint(img, dm, 4, cv2.INPAINT_TELEA)

# text in the margin: inpaint (background there is near-white with a faint tint)
img = cv2.inpaint(img, text_mask & ~band_mask, 5, cv2.INPAINT_TELEA)

cv2.imwrite(os.path.join(HERE, 'clean.png'), img)
if os.environ.get('MASK_OUT'):  # optional debug output of the mask
    cv2.imwrite(os.environ['MASK_OUT'], text_mask | band_mask)
print('wrote clean.png')
