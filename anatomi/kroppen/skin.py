"""Repaint the body-parts figure as plain skin (no organs, bones or vessels).

Reads clean.png (label-free, same pose and pixel coordinates as source.png) and
writes skin.png. The silhouette and pose are unchanged, so the anchor points in
poster.html stay valid.

1. Silhouette: everything not connected to the white border background,
   smoothed at 4x so the contour is not jagged.
2. Skin: one skin tone, shaded like a cylinder across each limb (distance to the
   edge / local half-width) and lit slightly from the upper left.
3. Face and ears: eyes, brows, nose, lips and ear folds are carried over from the
   original as a soft-thresholded high-pass inside small feature masks, so the
   strong strokes survive and the faint skull lines do not.
4. Fingers and toes: the dark skin-outline strokes that separate them are copied
   from the original (only in the finger/toe zones, small specks dropped).
5. Surface lines: a few soft strokes (collarbones, chest, navel, groin, knees,
   elbows, ankles) drawn in source pixel coordinates.
6. Outline: a warm brown contour along the silhouette.

Run: python3 anatomi/kroppen/skin.py
"""
import os
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = cv2.imread(os.path.join(HERE, 'clean.png'), cv2.IMREAD_COLOR).astype(np.float32)
H, W = src.shape[:2]
MID = 485  # the figure's midline (x)
gray = cv2.cvtColor(src.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)

# ---------------------------------------------------------------- silhouette
near_white = (src.min(axis=2) >= 244).astype(np.uint8)
ff = near_white.copy()
flood = np.zeros((H + 2, W + 2), np.uint8)
for x in range(0, W, 4):
    for y in (0, H - 1):
        if ff[y, x] == 1:
            cv2.floodFill(ff, flood, (x, y), 2)
for y in range(0, H, 4):
    for x in (0, W - 1):
        if ff[y, x] == 1:
            cv2.floodFill(ff, flood, (x, y), 2)
body = (ff != 2).astype(np.uint8)
n, lab, stats, _ = cv2.connectedComponentsWithStats(body, 8)
body = np.isin(lab, [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 400]).astype(np.uint8)

# smooth the contour at 4x, then derive alpha and the outline band from it
S = 4
big = cv2.resize(body.astype(np.float32), (W * S, H * S), interpolation=cv2.INTER_LINEAR)
big = cv2.GaussianBlur(big, (0, 0), 3.0)
bigm = (big > 0.5).astype(np.uint8)
din = cv2.distanceTransform(bigm, cv2.DIST_L2, 5) / S  # inside distance, source px
alpha = cv2.resize(bigm.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
line_w = 1.6
edge_big = np.clip((line_w - din) / 0.6 + 0.5, 0, 1) * bigm
edge = cv2.resize(edge_big.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
body = (alpha > 0.5).astype(np.uint8)

# ---------------------------------------------------------------- shading
dist = cv2.distanceTransform(body, cv2.DIST_L2, 5)
halfw = cv2.dilate(dist, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61)))
halfw = cv2.GaussianBlur(halfw, (0, 0), 10)
halfw = np.clip(halfw, 4, 70)  # wide torso: shade only the flanks
t = np.clip(dist / halfw, 0, 1)
cyl = np.sqrt(1 - (1 - t) ** 2)  # 0 at the edge, 1 on the ridge

sm = cv2.GaussianBlur(dist, (0, 0), 3)
gx = cv2.Sobel(sm, cv2.CV_32F, 1, 0, ksize=5)
gy = cv2.Sobel(sm, cv2.CV_32F, 0, 1, ksize=5)
mag = np.sqrt(gx ** 2 + gy ** 2) + 1e-3
facing = (gx * -0.6 + gy * -0.8) / mag  # > 0: the nearest edge is up-left (lit side)
side = np.clip(facing, -1, 1) * (1 - t) * 0.07

shade = 0.80 + 0.20 * cyl + side
base = np.array([168, 196, 232], np.float32)  # BGR, warm light skin
skin = base[None, None, :] * shade[..., None]
skin += np.array([-10, -6, 4], np.float32)[None, None, :] * (1 - cyl)[..., None]


def soft_mask(ellipses, blur):
    m = np.zeros((H, W), np.float32)
    for (cx, cy, rx, ry) in ellipses:
        cv2.ellipse(m, (cx, cy), (rx, ry), 0, 0, 360, 1, -1)
    return cv2.GaussianBlur(m, (0, 0), blur)


# ---------------------------------------------------------------- face, ears
# Multiplicative detail transfer: ratio of each pixel to its local average, in
# log space, soft-thresholded so faint skull lines vanish and the strong eye,
# nose, lip and ear strokes remain. No colour patch is pasted, so no seams.
lum = gray + 1.0
logr = np.log(lum / cv2.GaussianBlur(lum, (0, 0), 3.5))
detail = np.sign(logr) * np.maximum(np.abs(logr) - 0.07, 0)
features = soft_mask([
    (459, 113, 11, 6), (502, 113, 10, 6),     # eyes (not brows: drawn below)
    (484, 146, 11, 9),                        # nose tip and nostrils
    (484, 174, 18, 5),                        # lips (the line between them)
    (422, 130, 6, 22), (556, 130, 6, 22),     # ears
], 2)
EYE_MID = 961  # eyes at x 459 and 502 -> mirror axis x = 480.5
flip_detail = detail[:, ::-1]
flip_detail = np.roll(flip_detail, EYE_MID - (W - 1), axis=1)  # x -> 961 - x
flip_src = np.roll(src[:, ::-1], EYE_MID - (W - 1), axis=1)
left_eye = soft_mask([(502, 113, 13, 8)], 1.5)
detail = detail * (1 - left_eye) + flip_detail * left_eye
src_eyes = src * (1 - left_eye[..., None]) + flip_src * left_eye[..., None]
skin *= np.exp(detail * 1.2 * features)[..., None]
# iris and lip colour, lightly
colour = soft_mask([(459, 113, 4, 4), (502, 113, 4, 4)], 1.2)
skin = skin * (1 - colour[..., None] * 0.5) + src_eyes * (colour[..., None] * 0.5)
lips = soft_mask([(484, 175, 15, 5)], 2.0)
skin = skin * (1 - lips[..., None] * 0.18) + np.array([120, 130, 200], np.float32) * (lips[..., None] * 0.18)

# ---------------------------------------------------------------- fingers, toes
zones = np.zeros((H, W), np.uint8)
zones[800:900, 150:360] = 1     # fingers, figure's right hand
zones[800:900, 620:850] = 1     # fingers, figure's left hand
zones[1438:1500, 340:690] = 1   # toes
core = ((gray < 150) & (zones > 0)).astype(np.uint8)
n, lab, stats, _ = cv2.connectedComponentsWithStats(core, 8)
core = np.isin(lab, [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 25]).astype(np.uint8)
region = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
# continuous (anti-aliased) darkness of the original strokes, so lines stay unbroken
dark = np.clip((185 - gray) / 60, 0, 1) * region * (dist > 2.5)
dark = cv2.GaussianBlur(dark, (0, 0), 0.5) * 0.8

# ---------------------------------------------------------------- form shadows
shadow = np.zeros((H, W), np.float32)


def shade_stroke(pts, w, a, mirror=True):
    for p in ([pts, [(2 * MID - x, y) for x, y in pts]] if mirror else [pts]):
        layer = np.zeros((H, W), np.float32)
        cv2.polylines(layer, [np.array(p, np.int32)], False, a, w, cv2.LINE_AA)
        np.maximum(shadow, layer, out=shadow)


shade_stroke([(452, 214), (468, 224), (485, 228)], 10, 0.7)                 # under the jaw
shade_stroke([(400, 392), (422, 406), (450, 410), (474, 400)], 10, 0.55)    # under the chest
shade_stroke([(475, 276), (440, 274), (405, 278)], 6, 0.35)                 # below the collarbone
shade_stroke([(485, 420), (485, 590)], 6, 0.25, mirror=False)               # abdomen midline
shade_stroke([(392, 1050), (405, 1052), (418, 1050)], 10, 0.4)              # below the kneecap
shadow = cv2.GaussianBlur(shadow, (0, 0), 6) * (body > 0)
skin *= (1 - 0.16 * shadow)[..., None]

# ---------------------------------------------------------------- surface lines
ink = np.zeros((H, W), np.float32)


def stroke(pts, w=2, a=1.0, mirror=True):
    for p in ([pts, [(2 * MID - x, y) for x, y in pts]] if mirror else [pts]):
        layer = np.zeros((H, W), np.float32)
        cv2.polylines(layer, [np.array(p, np.int32)], False, a, w, cv2.LINE_AA)
        np.maximum(ink, layer, out=ink)


stroke([(474, 271), (452, 267), (422, 265), (394, 270)], 2, 0.5)           # collarbone
stroke([(477, 262), (485, 268)], 2, 0.4)                                   # sternal notch
stroke([(398, 384), (420, 398), (448, 402), (472, 392)], 2, 0.45)          # lower edge of chest
stroke([(410, 655), (432, 700), (458, 742), (474, 770)], 2, 0.4)           # groin line
stroke([(447, 101), (458, 97), (471, 100)], 3, 0.9, mirror=False)          # brows
stroke([(490, 100), (503, 97), (515, 101)], 3, 0.9, mirror=False)
cv2.ellipse(ink, (MID, 600), (3, 5), 0, 0, 360, 0.7, 2, cv2.LINE_AA)       # navel
for cx in (405, 563):                                                      # kneecap: lower edge only
    cv2.ellipse(ink, (cx, 1030), (15, 15), 0, 30, 150, 0.35, 2, cv2.LINE_AA)
for (cx, cy, a0, a1) in [(290, 540, 20, 120), (680, 540, 60, 160)]:        # elbow creases
    cv2.ellipse(ink, (cx, cy), (9, 6), 0, a0, a1, 0.4, 2, cv2.LINE_AA)
ink = cv2.GaussianBlur(ink, (0, 0), 1.0)

inkcol = np.array([95, 120, 165], np.float32)   # soft brown (BGR)
skin = skin * (1 - ink[..., None] * 0.5) + inkcol * (ink[..., None] * 0.5)
outline = np.array([62, 88, 132], np.float32)   # darker brown (BGR)
skin = skin * (1 - dark[..., None] * 0.8) + outline * (dark[..., None] * 0.8)
skin = skin * (1 - edge[..., None] * 0.9) + outline * (edge[..., None] * 0.9)

# ---------------------------------------------------------------- composite
out = 255 * (1 - alpha[..., None]) + skin * alpha[..., None]
cv2.imwrite(os.path.join(HERE, 'skin.png'), np.clip(out, 0, 255).astype(np.uint8))
print('wrote', os.path.join(HERE, 'skin.png'))
