"""Remove the English labels, leader lines and endpoint dots from source.png -> clean.png.

Run from anywhere:  python3 anatomi/skelett/clean.py

How it works
- Each English label has a search box (text + leader + dot). Inside a box, the leader is the
  long (>40 px wide) connected component of dark, neutral (black/grey, not brown) pixels;
  the text is every other dark-neutral pixel beyond the leader's outer end.
- Text lies on the white margin -> its padded bounding box is painted white.
- Horizontal leaders + dots are filled column by column (vertical interpolation), which keeps
  the outlines of the bones they cross; the bent clavicle leader is filled row by row
  (horizontal interpolation), which keeps the clavicle's upper edge. (TELEA inpainting was
  tried first: it smeared white into the bone edges.)
- The chest stretch of the sternum leader and both sternum dots are filled from the mirror
  image of the clean left half of the chest (the figure is symmetric about x = 510).
- The faint grey anti-alias halo of each leader (values ~245-251) is flattened to white where
  it lies on the neutral background.
- "Sternum" has a second pointer (dot on the lower sternum with a short stub); it is masked
  from its own small box.
"""
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
src = np.array(Image.open(os.path.join(HERE, 'source.png')).convert('RGB'))
img = src.astype(int)
mx, mn = img.max(2), img.min(2)
dark = ((mx < 140) & (mx - mn < 35)).astype(np.uint8)  # black/grey ink, excludes brown bone shading

# (x0, y0, x1, y1) search boxes and which side the text is on (R = text right of line)
BOXES = {
    'Skull':             ((560, 80, 860, 122), 'R'),
    'Clavicle':          ((115, 240, 435, 300), 'L'),
    'Sternum':           ((512, 312, 895, 352), 'R'),
    'Ribcage':           ((618, 405, 895, 445), 'R'),
    'Humerus':           ((95, 460, 332, 505), 'L'),
    'Vertebral column':  ((528, 585, 1005, 625), 'R'),
    'Radius':            ((112, 690, 305, 732), 'L'),
    'Ulna':              ((722, 688, 870, 728), 'R'),
    'Pelvis':            ((618, 795, 890, 835), 'R'),
    'Femur':             ((140, 970, 420, 1010), 'L'),
    'Tibia':             ((582, 1150, 850, 1195), 'R'),
    'Fibula':            ((155, 1220, 422, 1262), 'L'),
}
STERNUM_2ND = (515, 343, 552, 363)  # lower sternum dot + short stub

line_mask = np.zeros(dark.shape, np.uint8)
out = src.copy()
for name, ((x0, y0, x1, y1), side) in BOXES.items():
    sub = dark[y0:y1, x0:x1]
    n, lab, st, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
    longs = [i for i in range(1, n) if st[i][2] > 40]
    assert longs, name
    lx0 = min(st[i][0] for i in longs) + x0
    lx1 = max(st[i][0] + st[i][2] for i in longs) + x0
    for i in longs:
        line_mask[y0:y1, x0:x1][lab == i] = 1
    # text = remaining dark pixels beyond the outer end of the leader
    ys, xs = np.nonzero(sub)
    xs = xs + x0; ys = ys + y0
    sel = xs > lx1 + 3 if side == 'R' else xs < lx0 - 3
    tx0, tx1, ty0, ty1 = xs[sel].min(), xs[sel].max(), ys[sel].min(), ys[sel].max()
    out[ty0 - 5:ty1 + 6, tx0 - 5:tx1 + 6] = 255
    print(f'{name:17s} leader x {lx0}-{lx1}   text {tx0},{ty0}-{tx1},{ty1}')

sx0, sy0, sx1, sy1 = STERNUM_2ND
line_mask[sy0:sy1, sx0:sx1] |= dark[sy0:sy1, sx0:sx1]

# Horizontal leaders (incl. their dots): fill each column of the masked band by linear
# interpolation between the clean pixels just above and below it. This keeps the vertical
# outlines of the bones they cross (humerus, forearm, hand, fibula) intact.
# The rest (bent clavicle leader, second sternum stub) is filled row by row below.
horiz = np.zeros_like(line_mask)
n, lab, st, _ = cv2.connectedComponentsWithStats(line_mask, connectivity=8)
for i in range(1, n):
    if st[i][3] <= 12 and st[i][2] > 40:
        horiz[lab == i] = 1
other = line_mask & (1 - horiz)
hmask = cv2.dilate(horiz, np.ones((5, 3), np.uint8))  # +-2 rows, +-1 column
f = out.astype(float)
for x in np.nonzero(hmask.any(0))[0]:
    col = hmask[:, x]
    ys = np.nonzero(col)[0]
    runs = np.split(ys, np.nonzero(np.diff(ys) > 1)[0] + 1)
    for r in runs:
        a, b = r[0] - 1, r[-1] + 1
        for y in r:
            t = (y - a) / (b - a)
            f[y, x] = (1 - t) * f[a, x] + t * f[b, x]


def directional_fill(f, mask, box, d):
    """Re-fill masked pixels in box by interpolating along direction d = (dx, dy)."""
    x0, y0, x1, y1 = box
    dx, dy = d
    g = f.copy()
    at = lambda y, x, k: (int(round(y + k * dy)), int(round(x + k * dx)))
    for y in range(y0, y1):
        for x in range(x0, x1):
            if not mask[y, x]:
                continue
            ends = []
            for sgn in (-1, 1):
                k = sgn
                while mask[at(y, x, k)]:
                    k += sgn
                ends.append((abs(k), g[at(y, x, k)]))
            (ka, va), (kb, vb) = ends
            f[y, x] = (kb * va + ka * vb) / (ka + kb)


# The thumb metacarpal of the figure's left hand crosses the "Pelvis" leader obliquely; a
# vertical fill cuts its edges, so there the fill follows the bone's own direction
# (measured from its edges: ~0.7 px right per 1 px down).
directional_fill(f, hmask, (756, 800, 800, 825), (0.7, 1.0))
out = np.clip(f + 0.5, 0, 255).astype(np.uint8)
# The bent clavicle leader crosses the (near-horizontal) upper edge of the clavicle at a
# steeper angle, so fill it row by row (horizontal interpolation), which keeps that edge.
omask = cv2.dilate(other, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
f = out.astype(float)
for y in np.nonzero(omask.any(1))[0]:
    xs = np.nonzero(omask[y])[0]
    for r in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1):
        a, b = r[0] - 1, r[-1] + 1
        for x in r:
            t = (x - a) / (b - a)
            f[y, x] = (1 - t) * f[y, a] + t * f[y, b]
out = np.clip(f + 0.5, 0, 255).astype(np.uint8)

# Over the busy front of the ribcage (sternum leader + both sternum dots) interpolation smears
# ribs and cartilage. The skeleton is bilaterally symmetric about x = 510 (measured: mirror
# x -> 1020 - x minimises the difference in the chest), so fill that stretch from the clean
# mirror-image side instead, with a feathered edge.
MZ = (513, 312, 648, 366)  # x0, y0, x1, y1
zone = np.zeros_like(line_mask); zone[MZ[1]:MZ[3], MZ[0]:MZ[2]] = 1
mm = cv2.dilate(line_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) & zone
alpha = cv2.GaussianBlur(mm.astype(float), (5, 5), 1.2)
alpha = np.maximum(alpha, mm)[..., None]
mirror = src.copy(); mirror[:, :1021] = src[:, 1020::-1]
out = np.clip(out * (1 - alpha) + mirror * alpha + 0.5, 0, 255).astype(np.uint8)

# Flatten the faint grey anti-alias halo (values ~245-251) of the leaders on the white
# background. Bone is cream (not neutral) and rib cartilage is darker than 240, so only
# background pixels are touched; the mirror-filled chest zone is skipped.
band = cv2.dilate(line_mask, np.ones((21, 21), np.uint8)).astype(bool)
o = out.astype(int)
halo = band & ~zone.astype(bool) & (o.min(2) >= 240) & (o.max(2) - o.min(2) <= 8)
out[halo] = 255

# The source background is off-white (~254, with faint noise); make the background that is
# connected to the image border pure white so the crop edge cannot show on the white poster.
o = out.astype(int)
nearwhite = ((o.min(2) >= 240) & (o.max(2) - o.min(2) <= 8)).astype(np.uint8)
n, lab = cv2.connectedComponents(nearwhite, connectivity=4)
border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
border = border[border > 0]
out[np.isin(lab, border)] = 255

Image.fromarray(out).save(os.path.join(HERE, 'clean.png'))
print('wrote clean.png')
