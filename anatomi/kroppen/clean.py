"""Remove the English labels, leader lines and endpoint dots from source.png -> clean.png.

Positions were measured from the image (dark connected components / row profiles of the
thin horizontal leader lines), not guessed. Run: python3 anatomi/kroppen/clean.py
"""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = cv2.imread(os.path.join(HERE, 'source.png'), cv2.IMREAD_COLOR)
img = src.copy()
H, W = img.shape[:2]

# English text boxes (all in the white margin): x0, y0, x1, y1 (inclusive, measured)
TEXT = [
    (781, 92, 862, 120),   # Head
    (781, 208, 862, 236),  # Neck
    (780, 371, 891, 400),  # Thorax
    (77, 585, 160, 614),   # Arms
    (780, 585, 935, 614),  # Abdomen
    (841, 748, 933, 777),  # Pelvis
    (144, 1095, 218, 1124),  # Legs
]

# Leader lines: (x_start, x_end, y_centre, dot_x) — the line is 2-3 px thick, the dot ~6 px wide
LINES = [
    (546, 769, 105.5, 548),   # Head  -> dot at left end
    (534, 769, 221, 536),     # Neck
    (569, 769, 385.5, 571),   # Thorax
    (173, 256, 600.5, 253),   # Arms  -> dot at right end
    (589, 769, 600.5, 591),   # Abdomen
    (610, 830, 761, 612),     # Pelvis (crosses the figure's left hand)
    (226, 364, 1112.5, 360),  # Legs  -> dot at right end
]

PAD = 8  # the labels/lines carry a faint grey halo (~247) a few px wide
for x0, y0, x1, y1 in TEXT:
    img[y0 - PAD:y1 + PAD + 1, x0 - PAD:x1 + PAD + 1] = 255  # pure white margin

# Mask: each line is 2-3 px of near-black plus 1 px anti-aliasing above/below -> rows
# floor(yc)-2 .. ceil(yc)+2; each endpoint dot is ~6 px across -> disc of radius 5.
mask = np.zeros((H, W), bool)
for xa, xb, yc, dx in LINES:
    ya, yb = int(np.floor(yc)) - 2, int(np.ceil(yc)) + 2
    mask[ya:yb + 1, xa - 1:xb + 3] = True
    yy, xx = np.ogrid[:H, :W]
    mask |= (xx - dx) ** 2 + (yy - yc) ** 2 <= 5.5 ** 2

# The lines are horizontal and thin, so fill each masked vertical run by linear interpolation
# between the pixel just above and just below it. This keeps vertical structures (bones,
# outlines, vessels) that the line crossed continuous and sharp, unlike a diffusion inpaint.
out = img.astype(np.float32)
for x in np.where(mask.any(axis=0))[0]:
    col = mask[:, x]
    y = 0
    while y < H:
        if not col[y]:
            y += 1
            continue
        y0 = y
        while y < H and col[y]:
            y += 1
        top, bot = out[y0 - 1, x], out[y, x]
        n = y - y0 + 1
        for i in range(y0, y):
            t = (i - y0 + 1) / n
            out[i, x] = top * (1 - t) + bot * t
out = np.clip(out + 0.5, 0, 255).astype(np.uint8)

# Where a figure outline crossed the masked area at a shallow angle, vertical interpolation leaves
# a gap: redraw those short outline pieces (path measured from the dark outline pixels just
# outside the mask) in the outline colour sampled from the intact outline nearby.
OUTLINES = [
    # (polyline points, point near which to sample the outline colour, polygon outside the figure
    #  in which masked pixels are painted white first)
    ([(551, 99), (551, 104), (550, 109)], (551, 95), None),                 # side of head above the ear
    ([(551, 101), (554, 104), (557, 106), (559, 109)], (551, 95),           # top of the ear
     [(552, 95), (566, 95), (566, 112), (560, 112), (557, 106), (554, 104), (552, 101)]),
    ([(536, 216), (536, 221), (538, 224), (540, 226)], (536, 214),          # side of the neck
     [(537, 210), (552, 210), (552, 229), (541, 229), (538, 224), (537, 221)]),
    ([(784.5, 757), (786, 761), (787.5, 765)], (782, 754),                  # thumb outline (left hand)
     [(785, 752), (800, 752), (800, 768), (788, 766), (786, 761)]),
]
for _, _, poly in OUTLINES:
    if poly:
        outside = np.zeros((H, W), np.uint8)
        cv2.fillPoly(outside, [np.array(poly, np.int32)], 1)
        out[(outside > 0) & mask] = 255
for pts, (sx, sy), _ in OUTLINES:
    win = src[sy - 3:sy + 4, sx - 3:sx + 4].reshape(-1, 3)
    colour = tuple(int(c) for c in win[win.sum(axis=1).argmin()])  # darkest outline pixel nearby
    pts = np.array(pts, np.float64) * 16  # sub-pixel precision (shift=4)
    cv2.polylines(out, [pts.astype(np.int32)], False, colour, 1, cv2.LINE_AA, shift=4)

# Remove the faint grey halo (~247) that runs ~7 px above/below each line in the white margin:
# near-white, unsaturated pixels in a band around the line become pure white. The figure is
# beige/pink (saturated), so it is not affected.
for xa, xb, yc, dx in LINES:
    ya, yb = int(yc) - 10, int(yc) + 11
    band = out[ya:yb, xa - 6:xb + 8].astype(int)
    near_white = (band.min(axis=2) >= 232) & (band.max(axis=2) - band.min(axis=2) <= 8)
    band[near_white] = 255
    out[ya:yb, xa - 6:xb + 8] = band.astype(np.uint8)

# The illustration's paper is slightly off-white (~250-254), which shows as a faint box on the
# pure-white poster. Make the background pure white: near-white, unsaturated pixels that are
# connected to the image border (so never highlights inside the figure).
o = out.astype(int)
near_white = ((o.min(axis=2) >= 238) & (o.max(axis=2) - o.min(axis=2) <= 10)).astype(np.uint8)
n, lab = cv2.connectedComponents(near_white, connectivity=4)
border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
bg = np.isin(lab, list(border))
out[bg] = 255

cv2.imwrite(os.path.join(HERE, 'clean.png'), out)
print('wrote', os.path.join(HERE, 'clean.png'))
