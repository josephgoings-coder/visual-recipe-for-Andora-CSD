"""Remove the English labels, leader lines and endpoint dots from source.png -> clean.png.

The labels and leaders are near-black and neutral (grey), while the muscle figure is
saturated red/brown, so a "dark and unsaturated" threshold isolates them cleanly.
Connected components of that mask are classified as:
  * leader -> long/tall component (a line incl. its endpoint dot)
  * text   -> any component lying in the white side margins (x < 205 or x > 765)
Small neutral-dark specks inside the figure (pupils etc.) are left alone.

Leaders over the muscle are filled by interpolating along the local muscle-fibre direction
(structure tensor), which keeps the fibres continuous instead of the blurry smear of plain
inpainting. Faint grey anti-aliasing / drop-shadow pixels left in the white background
are snapped to white.
Run from anywhere: python3 anatomi/muskler/clean.py
"""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = cv2.imread(os.path.join(HERE, 'source.png'))
H, W = src.shape[:2]
im = src.astype(int)
mx, mn = im.max(axis=2), im.min(axis=2)
dark = ((mx < 120) & (mx - mn < 45)).astype(np.uint8)

n, lab, st, _ = cv2.connectedComponentsWithStats(dark, 8)
text = np.zeros((H, W), np.uint8)
lines = np.zeros((H, W), np.uint8)
for i in range(1, n):
    x, y, w, h, a = st[i]
    if a >= 30 and (w >= 100 or h >= 50):  # leader line (+ dot)
        lines[lab == i] = 1
    elif x + w < 205 or x > 765:          # glyph (incl. i-dots) in the white margin
        text[lab == i] = 1

text = cv2.dilate(text, np.ones((11, 11), np.uint8))
lines = cv2.dilate(lines, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))

# --- orientation-guided fill for the leaders ---------------------------------------
# 1) a plain Telea inpaint (used as fallback and to estimate fibre orientation),
# 2) local fibre direction from a structure tensor, 3) every masked pixel is filled by
# walking along the fibre direction both ways to the first unmasked pixel and linearly
# interpolating between those two source pixels, so fibres continue across the gap.
base = cv2.inpaint(src, lines, 5, cv2.INPAINT_TELEA)
g = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY).astype(np.float32)
gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
# gradients inside/next to the band would describe the band itself, so they get zero weight
wgt = 1.0 - cv2.dilate(lines, np.ones((7, 7), np.uint8)).astype(np.float32)
norm = cv2.GaussianBlur(wgt, (0, 0), 7) + 1e-6
J = [cv2.GaussianBlur(a * wgt, (0, 0), 7) / norm for a in (gx * gx, gx * gy, gy * gy)]
theta = 0.5 * np.arctan2(2 * J[1], J[0] - J[2]) + np.pi / 2  # fibre direction
srcf = src.astype(np.float32)
out = base.astype(np.float32)
ys, xs = np.nonzero(lines)
MAXW = 30
for y, x in zip(ys, xs):
    dx, dy = np.cos(theta[y, x]), np.sin(theta[y, x])
    ends = []
    for sgn in (1, -1):
        for t in range(1, MAXW):
            xx = int(round(x + sgn * dx * t)); yy = int(round(y + sgn * dy * t))
            if not (0 <= xx < W and 0 <= yy < H):
                break
            if not lines[yy, xx]:
                k = t + 2  # sample a little beyond the band edge, clear of any line halo
                ends.append((k, srcf[min(H - 1, max(0, int(round(y + sgn * dy * k)))),
                                     min(W - 1, max(0, int(round(x + sgn * dx * k))))]))
                break
    if len(ends) == 2:
        (t1, c1), (t2, c2) = ends
        paper1, paper2 = c1.min() > 235 and np.ptp(c1) < 15, c2.min() > 235 and np.ptp(c2) < 15
        if paper1 != paper2:   # band crosses the figure outline: keep a crisp edge, no pink blend
            out[y, x] = c1 if t1 <= t2 else c2
        else:
            out[y, x] = (c1 * t2 + c2 * t1) / (t1 + t2)
# a light blur inside the band only, to hide sampling jaggies ...
soft = cv2.GaussianBlur(out, (3, 3), 0)
m = lines > 0
out[m] = soft[m]
# ... then put fine fibre grain back: high-pass detail copied from just above/below the band
hp = srcf - cv2.GaussianBlur(srcf, (0, 0), 1.5)
for y, x in zip(ys, xs):
    for dy in (14, -14, 22, -22):
        yy = y + dy
        if 0 <= yy < H and not lines[yy, x]:
            out[y, x] += 0.9 * hp[yy, x]
            break
out = np.clip(out, 0, 255).astype(np.uint8)

# --- text: all on white background ------------------------------------------------
out[text > 0] = 255

# --- snap faint grey halo / shadow pixels near the removed marks to pure white -------
zone = cv2.dilate(((lines + text) > 0).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
o = out.astype(int)
neutral_light = ((o.max(axis=2) - o.min(axis=2)) < 12) & (o.min(axis=2) > 190)
out[zone & neutral_light] = 255

# --- make the background pure white (source paper is ~253) so the crop has no visible edge
o = out.astype(int)
paper = (((o.min(axis=2) >= 238) & ((o.max(axis=2) - o.min(axis=2)) <= 10))).astype(np.uint8)
nb, blab = cv2.connectedComponents(paper, connectivity=4)
border = set(np.unique(np.concatenate([blab[0], blab[-1], blab[:, 0], blab[:, -1]]))) - {0}
bgmask = np.isin(blab, list(border))
out[bgmask] = 255
# thin pink stubs left where a leader left the figure outline: open the figure mask inside
# the leader zone and paint what the opening removes white
fg = (~bgmask).astype(np.uint8)
opened = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
lzone = cv2.dilate(lines, np.ones((5, 5), np.uint8)) > 0
out[(fg > 0) & (opened == 0) & lzone] = 255

cv2.imwrite(os.path.join(HERE, 'clean.png'), out)
print('clean.png written; leader px', int(lines.sum()), 'text px', int(text.sum()))
