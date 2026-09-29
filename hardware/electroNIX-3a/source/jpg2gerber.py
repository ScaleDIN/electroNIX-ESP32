#!/usr/bin/env python3
"""Reconstruct electroNIX-3a Gerbers from a single colour-coded top-view JPEG.

The image draws bottom copper (navy), then top copper (red) over it, then
silk (green); through-hole pads are a dark ring with the drill shown as a
lighter core (steel for component pads, beige for vias). White is bare
board. Bottom copper hidden under red/silk is bridged across when the hidden
strip is thin (step 1); wider hidden areas are left empty and written to
unresolved.png for the schematic-driven step.

usage: jpg2gerber.py <image.jpg> <outdir>
"""
import sys, os, numpy as np, cv2
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
PRE = 'electroNIX3a'

# ---- geometry -------------------------------------------------------------
BW, BH = 92.0, 56.0                  # board size from the dimension drawing
X0, Y0 = 27.5, 97.5                  # outline top-left, image px (line centre)
PX = 8.375                           # px/mm: U2 TQFP-44 11 pads span 67.0 px = 10 x 0.8 mm
UP = 2                               # work at 2x for smoother edges
S = PX * UP

# ---- palette (k-means of the board area) ---------------------------------
PAL = np.array([
    (251, 252, 251),   # 0 white  : bare board
    (13, 2, 137),      # 1 navy   : bottom copper
    (248, 2, 4),       # 2 red    : top copper
    (12, 132, 12),     # 3 green  : silk
    (6, 36, 55),       # 4 ring   : TH pad / via annulus
    (39, 69, 110),     # 5 core   : component hole
    (190, 166, 152),   # 6 beige  : via hole
], float)
W, N, R, G, RING, CORE, BEIGE = range(7)

img = Image.open(SRC).convert('RGB')
x1, y1 = X0 + BW * PX, Y0 + BH * PX
crop = img.crop((int(X0) + 1, int(Y0) + 1, int(x1), int(y1)))
ox, oy = int(X0) + 1 - X0, int(Y0) + 1 - Y0          # crop origin rel. outline, px
big = np.asarray(crop.resize((crop.width * UP, crop.height * UP), Image.BICUBIC)).astype(float)
Hh, Ww = big.shape[:2]
def classify(px):
    """Label each pixel with the palette colour that best explains it: either
    a pure colour, or an anti-aliased blend of two colours (then the nearer
    end). Without the blend model, navy/white edges read as via/pad colours."""
    flat = px.reshape(-1, 3)
    best = ((flat[:, None, :] - PAL[None]) ** 2).sum(-1)
    lab = best.argmin(1); bd = best.min(1)
    for i in range(len(PAL)):
        for j in range(i + 1, len(PAL)):
            if {i, j} & {RING, CORE, BEIGE} and {i, j} != {RING, CORE}: continue
            d = PAL[j] - PAL[i]
            t = np.clip(((flat - PAL[i]) @ d) / (d @ d), 0, 1)
            e = ((flat - PAL[i] - t[:, None] * d) ** 2).sum(1)
            better = e < bd - 60                       # a blend must clearly beat a pure colour
            lab[better] = np.where(t[better] < 0.5, i, j); bd[better] = e[better]
    return lab.reshape(px.shape[:2]).astype(np.uint8)
cls = classify(big)

def to_mm(xp, yp):                    # 2x-pixel -> board mm (y up)
    return xp / S + ox / PX, BH - (yp / S + oy / PX)
def to_px(xm, ym):
    return (xm - ox / PX) * S, (BH - ym - oy / PX) * S

# ---- holes ------------------------------------------------------------------
DRILLS = (1.0, 1.3, 1.7)              # electroNIX-2 / adapter tool set (0.5 = vias)
def snap(d, tools): return min(tools, key=lambda t: abs(t - d))
holes, pads, npth = [], [], []        # holes: (x,y,drill); pads: (x,y,w,h,angle)
core = (cls == CORE).astype(np.uint8)
core = cv2.morphologyEx(core, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
n, lab, st, cen = cv2.connectedComponentsWithStats(core)
ringish = cv2.dilate((cls == RING).astype(np.uint8), np.ones((5, 5), np.uint8))
for i in range(1, n):
    a = st[i, 4]; w, h = st[i, 2], st[i, 3]
    d = 2 * np.sqrt(a / np.pi) / S
    if d < 0.6 or min(w, h) < 0.7 * max(w, h): continue
    x, y = to_mm(*cen[i])
    if d > 2.8:                                       # plain disc, no ring: mounting hole
        npth.append((x, y, 3.5)); continue
    if not ringish[lab == i].any(): continue          # a hole always has a pad ring
    holes.append((x, y, snap(d, DRILLS), d))

bg = (cls == BEIGE).astype(np.uint8)
n, lab, st, cen = cv2.connectedComponentsWithStats(bg)
for i in range(1, n):
    a = st[i, 4]; w, h = st[i, 2], st[i, 3]
    if not (12 <= a <= 180 and max(w, h) <= 18): continue
    xp, yp = cen[i]
    ring = [cls[int(round(yp + 7 * np.sin(t))), int(round(xp + 7 * np.cos(t)))]
            for t in np.linspace(0, 2 * np.pi, 16, endpoint=False)
            if 0 <= round(yp + 7 * np.sin(t)) < Hh and 0 <= round(xp + 7 * np.cos(t)) < Ww]
    if sum(c == RING for c in ring) < 4: continue
    x, y = to_mm(xp, yp)
    holes.append((x, y, 0.5, 2 * np.sqrt(a / np.pi) / S))

# pads: the ring+core blob around each hole, fitted as a circle or obround
padmask = np.isin(cls, (RING, CORE, BEIGE)).astype(np.uint8)
padmask = cv2.morphologyEx(padmask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
n, lab, st, cen = cv2.connectedComponentsWithStats(padmask)
seen = set()
nopad = []
for x, y, dr, _ in holes:
    if dr == 0.5: continue                            # vias: fixed 1.0 mm pad, tented
    xp, yp = to_px(x, y)
    i = lab[int(round(yp)), int(round(xp))]
    if i == 0: nopad.append((x, y, dr)); continue
    if i in seen: continue
    seen.add(i)
    ys, xs = np.nonzero(lab == i)
    pts = np.c_[xs, ys].astype(np.float32)
    (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
    w, h = (w + 1) / S, (h + 1) / S
    if max(w, h) > 4.5: nopad.append((x, y, dr)); continue
    if abs(w - h) < 0.25 * max(w, h):
        dd = 2 * np.sqrt(len(xs) / np.pi) / S
        w = h = dd
    X, Y = to_mm(cx, cy)
    pads.append((X, Y, w, h, -ang))

for x, y, dr in nopad:                                # fall back to a round pad
    pads.append((x, y, dr + 0.7, dr + 0.7, 0))
print('no pad blob for', [(round(x, 1), round(y, 1)) for x, y, _ in nopad])
print('holes:', {d: sum(1 for h in holes if h[2] == d) for d in (0.5,) + DRILLS},
      'NPTH', len(npth), 'pads', len(pads))

# ---- copper: known / unknown per layer -----------------------------------
padcu = np.isin(cls, (RING, CORE, BEIGE))
known_b = np.isin(cls, (W, N)) | padcu
val_b = (cls == N) | padcu
known_t = np.isin(cls, (W, N, R)) | padcu
val_t = (cls == R) | padcu

MAXSPAN = 2.0 * S                     # step 1: bridge hidden strips up to 2 mm wide
def bridge(known, val):
    """For each hidden pixel, look along 8 axes for the nearest known pixel on
    both sides; take the axis with the shortest span (i.e. straight across the
    covering track) and copy the nearer end. Spans wider than MAXSPAN stay
    unresolved."""
    K = int(MAXSPAN) + 2
    unk = ~known
    best = np.full(known.shape, np.inf); res = np.zeros(known.shape, bool)
    for t in np.arange(8) * np.pi / 8:
        dists, vals = [], []
        for sgn in (1, -1):
            dist = np.full(known.shape, np.inf); v = np.zeros(known.shape, bool)
            todo = unk.copy()
            for k in range(1, K):
                dx = int(round(sgn * k * np.cos(t))); dy = int(round(sgn * k * np.sin(t)))
                sh_k = np.zeros_like(known); sh_v = np.zeros_like(val)
                ys = slice(max(0, -dy), Hh - max(0, dy)); yd = slice(max(0, dy), Hh - max(0, -dy))
                xs = slice(max(0, -dx), Ww - max(0, dx)); xd = slice(max(0, dx), Ww - max(0, -dx))
                sh_k[ys, xs] = known[yd, xd]; sh_v[ys, xs] = val[yd, xd]
                hit = todo & sh_k
                dist[hit] = k; v[hit] = sh_v[hit]; todo &= ~hit
                if not todo.any(): break
            dists.append(dist); vals.append(v)
        span = dists[0] + dists[1]
        pick = np.where(dists[0] <= dists[1], vals[0], vals[1])
        better = unk & (span < best)
        best[better] = span[better]; res[better] = pick[better]
    ok = unk & (best <= MAXSPAN)
    out = val & known
    out[ok] = res[ok]
    # the per-pixel choice is noisy along the covering track's edges: take a
    # local majority over bridged pixels, then drop specks and slivers
    sm = cv2.GaussianBlur(out.astype(np.float32), (0, 0), 1.6) > 0.5
    near = cv2.dilate(ok.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~padcu
    out[near] = sm[near]
    out = despeckle(out)
    return out, unk & ~ok

def despeckle(m, cu_min=0.04, gap_min=0.06):
    m = m.copy()
    for want, amin in ((True, cu_min), (False, gap_min)):
        n, lab, st, _ = cv2.connectedComponentsWithStats((m == want).astype(np.uint8), connectivity=4)
        small = np.nonzero(st[:, 4] < amin * S**2)[0]
        small = small[small > 0]
        m[np.isin(lab, small)] = not want
    return m

bot, unres_b = bridge(known_b, val_b)
top, unres_t = bridge(known_t, val_t)
print('unresolved: bottom %.1f mm2, top %.1f mm2' % (unres_b.sum() / S**2, unres_t.sum() / S**2))

# ---- gerber writing --------------------------------------------------------
def c(v): return int(round(v * 1e6))
HDR = ("G04 #@! TF.GenerationSoftware,jpg2gerber*\nG04 #@! TF.FileFunction,%s*\n"
       "G04 #@! TF.FilePolarity,%s*\n%%FSLAX46Y46*%%\n%%MOMM*%%\n%%ADD10C,0.100000*%%\nG01*\n")

def contours(mask, minarea=0.02):
    m = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 0.7)
    m = cv2.resize(m, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    m = (m > 0.5).astype(np.uint8)
    cs, hi = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    f = lambda cc: [to_mm(p[0][0] / 2, p[0][1] / 2) for p in cv2.approxPolyDP(cc, 0.8, True)]
    for i, cc in enumerate(cs):
        if hi[0][i][3] != -1: continue
        a = cv2.contourArea(cc) / 4 / S**2
        if a < minarea: continue
        kids, k = [], hi[0][i][2]
        while k != -1:
            if cv2.contourArea(cs[k]) / 4 / S**2 >= 0.01: kids.append(f(cs[k]))
            k = hi[0][k][0]
        out.append((a, f(cc), kids))
    out.sort(key=lambda t: -t[0])
    return out

def region(poly, dark):
    s = '%%LP%s*%%\nG36*\nX%dY%dD02*\n' % ('D' if dark else 'C', c(poly[0][0]), c(poly[0][1]))
    for p in poly[1:] + [poly[0]]: s += 'X%dY%dD01*\n' % (c(p[0]), c(p[1]))
    return s + 'G37*\n'

class Ap:
    def __init__(self): self.defs, self.ids = '', {}
    def get(self, spec):
        if spec not in self.ids:
            self.ids[spec] = 11 + len(self.ids)
            self.defs += '%%ADD%d%s*%%\n' % (self.ids[spec], spec)
        return self.ids[spec]

def pad_flashes(ap, grow=0.0, clear=False):
    s = '%%LP%s*%%\n' % ('C' if clear else 'D')
    for x, y, w, h, ang in pads:
        w, h = w + 2 * grow, h + 2 * grow
        if w == h:
            s += 'D%d*\nX%dY%dD03*\n' % (ap.get('C,%.3f' % w), c(x), c(y))
        else:  # obround as a stroked line
            L = max(w, h) - min(w, h); a = np.radians(ang if w >= h else ang + 90)
            dx, dy = L / 2 * np.cos(a), L / 2 * np.sin(a)
            s += 'D%d*\nX%dY%dD02*\nX%dY%dD01*\n' % (ap.get('C,%.3f' % min(w, h)), c(x - dx), c(y - dy), c(x + dx), c(y + dy))
    for x, y, d in npth:
        if clear: s += 'D%d*\nX%dY%dD03*\n' % (ap.get('C,%.3f' % (d + 0.4 + 2 * grow)), c(x), c(y))
    return s

def via_flashes(ap):
    s = '%LPD*%\n'
    for x, y, d, _ in holes:
        if d == 0.5: s += 'D%d*\nX%dY%dD03*\n' % (ap.get('C,1.000'), c(x), c(y))
    return s

# U2 TQFP-44, measured from the image: 11 pads per side at 0.8 mm, pad rows
# 96 px = 11.46 mm apart centre-to-centre, pads 17 px = 2.03 mm long.
QFP_C = ((255 - X0) / PX, BH - (303 - Y0) / PX)
QFP_ROW, QFP_L, QFP_W, QFP_P = 96 / PX, 2.03, 0.5, 0.8
def qfp_flashes(ap, grow=0.0):
    s = '%LPD*%\n'; cx, cy = QFP_C
    for side in range(4):
        for k in range(11):
            t = (k - 5) * QFP_P; o = QFP_ROW / 2
            x, y, horiz = [(t, o, False), (t, -o, False), (-o, t, True), (o, t, True)][side]
            w, h = (QFP_L, QFP_W) if horiz else (QFP_W, QFP_L)
            s += 'D%d*\nX%dY%dD03*\n' % (ap.get('R,%.3fX%.3f' % (w + 2 * grow, h + 2 * grow)), c(cx + x), c(cy + y))
    return s

def write(name, func, pol, rs, flashes_fn=None):
    ap = Ap(); body = ''
    for a, o, hs in rs:
        body += region(o, True)
        for hh in hs: body += region(hh, False)
    if flashes_fn: body += flashes_fn(ap)
    with open(os.path.join(OUT, '%s-%s' % (PRE, name)), 'w') as f:
        f.write(HDR % (func, pol) + ap.defs + '%LPD*%\n' + body + 'M02*\n')

keepout = np.zeros_like(bot)
for x, y, d in npth:
    xp, yp = to_px(x, y); cv2.circle(keepout, (int(xp), int(yp)), int((d / 2 + 0.2) * S), 1, -1)
keepout = keepout.astype(bool)
bot &= ~keepout; top &= ~keepout

write('F_Cu.gtl', 'Copper,L1,Top', 'Positive', contours(top), lambda ap: pad_flashes(ap) + via_flashes(ap) + qfp_flashes(ap))
write('B_Cu.gbl', 'Copper,L2,Bot', 'Positive', contours(bot), lambda ap: pad_flashes(ap) + via_flashes(ap))
write('F_SilkS.gto', 'Legend,Top', 'Positive', contours(cls == G, 0.005))

# solder mask openings: TH pads (+0.05 mm) both sides; vias tented;
# top SMD pads = compact red blobs that aren't tracks.
red = (cls == R).astype(np.uint8)
k = cv2.getStructuringElement(cv2.MORPH_RECT, (int(0.9 * S), int(0.9 * S)))
fat = cv2.morphologyEx(red, cv2.MORPH_OPEN, k)
n, lab, st, _ = cv2.connectedComponentsWithStats(fat)
smd = np.zeros_like(red)
for i in range(1, n):
    w, h, a = st[i, 2], st[i, 3], st[i, 4]
    if a >= 0.75 * w * h and w * h < (4.5 * S) ** 2: smd[lab == i] = 1
smd = cv2.dilate(smd, np.ones((3, 3), np.uint8)) & red
smd = cv2.dilate(smd, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
write('F_Mask.gts', 'Soldermask,Top', 'Negative', contours(smd.astype(bool), 0.01),
      lambda ap: pad_flashes(ap, 0.05) + qfp_flashes(ap, 0.05))
write('B_Mask.gbs', 'Soldermask,Bot', 'Negative', [], lambda ap: pad_flashes(ap, 0.05))

with open(os.path.join(OUT, PRE + '-Edge_Cuts.gm1'), 'w') as f:
    f.write(HDR % ('Profile,NP', 'Positive') + 'D10*\n')
    for x, y, cmd in [(0, 0, 2), (BW, 0, 1), (BW, BH, 1), (0, BH, 1), (0, 0, 1)]:
        f.write('X%dY%dD0%d*\n' % (c(x), c(y), cmd))
    f.write('M02*\n')

def excellon(name, items, plated):
    ds = sorted({d for _, _, d in items})
    with open(os.path.join(OUT, '%s-%s' % (PRE, name)), 'w') as f:
        f.write('M48\n; #@! TF.FileFunction,%s\nMETRIC,TZ\n' % ('Plated,1,2,PTH' if plated else 'NonPlated,1,2,NPTH'))
        for i, d in enumerate(ds): f.write('T%dC%.3f\n' % (i + 1, d))
        f.write('%\nG90\nG05\n')
        for i, d in enumerate(ds):
            f.write('T%d\n' % (i + 1))
            for x, y, dd in items:
                if dd == d: f.write('X%.3fY%.3f\n' % (x, y))
        f.write('T0\nM30\n')
excellon('PTH.drl', [(x, y, d) for x, y, d, _ in holes], True)
excellon('NPTH.drl', npth, False)

# ---- diagnostics for the next step ---------------------------------------
dbg = np.asarray(crop.resize((Ww, Hh))).copy()
dbg[unres_b] = (dbg[unres_b] * 0.3 + np.array([255, 200, 0]) * 0.7).astype(np.uint8)
Image.fromarray(dbg).save(os.path.join(OUT, '..', 'preview', 'unresolved_bottom.jpg'), quality=88)
np.savez_compressed(os.path.join(OUT, '..', 'source', 'layers.npz'),
                    cls=cls, top=top, bot=bot, unres_b=unres_b, unres_t=unres_t, S=S)
with open(os.path.join(OUT, '..', 'source', 'holes.csv'), 'w') as f:
    f.write('x_mm,y_mm,drill_mm,measured_mm\n')
    for x, y, d, m in holes: f.write('%.3f,%.3f,%.1f,%.2f\n' % (x, y, d, m))
    for x, y, d in npth: f.write('%.3f,%.3f,%.1f,NPTH\n' % (x, y, d))
