#!/usr/bin/env python3
"""Approximate Gerber reconstruction from a colour-coded top-view raster
(red = top copper, navy = visible bottom copper, green = silk, steel-blue
discs = through-hole pads). Board is 92 x 56 mm; scale is taken from the
outline in pixels. Resolution is ~0.12 mm/px -- NOT fabrication grade."""
import sys, os, numpy as np, cv2
from PIL import Image

SRC = sys.argv[1]; OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
BW, BH = 92.0, 56.0
X0, X1, Y0, Y1 = 27, 798, 97, 566          # outline pixel bbox (measured)
UP = 4                                       # supersampling for smooth contours
pxmm = ((X1 - X0) / BW + (Y1 - Y0) / BH) / 2
im = np.array(Image.open(SRC).convert('RGB')).astype(int)[Y0+2:Y1-1, X0+2:X1-1]
ox, oy = X0+2, Y0+2
r, g, b = im[..., 0], im[..., 1], im[..., 2]

red   = (r > 150) & (g < 110) & (b < 110)
navy  = (b > 70) & (r < 70) & (g < 70) & (b > r + 50)
green = (g > 90) & (r < 90) & (b < 90) & (g > b + 40)
steel = ((r < 70) & (g > 25) & (b > 60) & (g >= r + 15) & (b > g)) | ((r < 40) & (g < 70) & (b < 70) & (b > 15) & ~navy & ~green)
steel = cv2.morphologyEx(steel.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0

# ---- pads / holes from steel discs -------------------------------------
n, lab, st, cen = cv2.connectedComponentsWithStats(steel.astype(np.uint8))
pads = []      # (x_mm, y_mm, d_mm)
for i in range(1, n):
    a = st[i, cv2.CC_STAT_AREA]; w = st[i, 2]; h = st[i, 3]
    if a < 8 or max(w, h) > 60 and not (32 < max(w, h) < 60) or abs(w - h) > 0.35 * max(w, h) or a < 0.6 * w * h:
        continue
    d = 2 * np.sqrt(a / np.pi) / pxmm
    d = max(d, max(w, h) / pxmm * 0.9)
    pads.append(((cen[i][0] + ox - X0) / pxmm, BH - (cen[i][1] + oy - Y0) / pxmm, d))
print(len(pads), 'pads/holes found')

def mm(x, y):  # upsampled px -> board mm
    return x / UP / pxmm + (ox - X0) / pxmm, BH - (y / UP / pxmm + (oy - Y0) / pxmm)

def smooth(mask):
    m = cv2.resize(mask.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(m, (0, 0), UP * 0.45)
    return (m > 0.5).astype(np.uint8)

def rings(mask, eps=0.7, minarea=6):
    m = smooth(mask)
    cs, hi = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for i, c in enumerate(cs):
        if hi[0][i][3] != -1: continue
        a = cv2.contourArea(c)
        if a < minarea * UP * UP: continue
        kids = []
        k = hi[0][i][2]
        while k != -1:
            if cv2.contourArea(cs[k]) >= 3 * UP * UP: kids.append(k)
            k = hi[0][k][0]
        f = lambda cc: [mm(*p[0]) for p in cv2.approxPolyDP(cc, eps, True)]
        out.append((a, f(c), [f(cs[k]) for k in kids]))
    out.sort(key=lambda t: -t[0])
    return out

HDR = ("G04 #@! TF.GenerationSoftware,jpg2gerber*\n%%FSLAX46Y46*%%\n%%MOMM*%%\n"
       "G04 #@! TF.FileFunction,%s*\nG04 #@! TF.FilePolarity,%s*\n%%ADD10C,0.100000*%%\nG01*\n")
def c(v): return int(round(v * 1e6))
def region(poly, dark):
    s = '%%LP%s*%%\nG36*\n' % ('D' if dark else 'C')
    s += 'X%dY%dD02*\n' % (c(poly[0][0]), c(poly[0][1]))
    for p in poly[1:] + [poly[0]]:
        s += 'X%dY%dD01*\n' % (c(p[0]), c(p[1]))
    return s + 'G37*\n'
def write(name, func, pol, rs, extra=''):
    with open(os.path.join(OUT, name), 'w') as f:
        f.write(HDR % (func, pol) + '%LPD*%\n')
        for a, o, hs in rs:
            f.write(region(o, True))
            for h in hs: f.write(region(h, False))
        f.write(extra + 'M02*\n')
def flash(x, y, d, dark=True):
    return '%%LP%s*%%\n%%ADD%dC,%.4f*%%\nD%d*\nX%dY%dD03*\n' % ('D' if dark else 'C', flash.n, d, flash.n, c(x), c(y))
def flashes(sizes_pos, dark=True):
    s = ''; tools = {}
    for x, y, d in sizes_pos:
        d = round(d, 2)
        if d not in tools:
            tools[d] = 11 + len(tools); s0 = '%%ADD%dC,%.4f*%%\n' % (tools[d], d)
            s = s0 + s if False else s
        s += ''
    return s

def flash_block(items, dark=True):
    """items: (x,y,d). Emits aperture defs inline (legal in RS-274X)."""
    s = '%%LP%s*%%\n' % ('D' if dark else 'C'); tools = {}
    for x, y, d in items:
        d = round(d, 2)
        if d not in tools:
            tools[d] = 20 + len(tools) + (100 if not dark else 0)
            s += '%%ADD%dC,%.4f*%%\n' % (tools[d], d)
        s += 'D%d*\nX%dY%dD03*\n' % (tools[d], c(x), c(y))
    return s

MOUNT = 3.0   # discs wider than this are unplated mounting holes (no copper)
for x, y, d in pads:
    if d > MOUNT:
        cv2.circle(steel_u8 := steel.astype(np.uint8), (int(round(x * pxmm + X0 - ox)), int(round((BH - y) * pxmm + Y0 - oy))), int(d * pxmm / 2 + 1), 0, -1)
        steel = steel_u8 > 0
padflash = [(x, y, d) for x, y, d in pads if d <= MOUNT]
# copper layers: colour regions + pads; clearance ring inside the pad is the hole (drilled later)
top = red | steel;  bot = navy | steel
# bottom under red is unknown: keep navy where visible only
bot_r = rings(bot); top_r = rings(top)
write('electroNIX3a-F_Cu.gtl', 'Copper,L1,Top', 'Positive', top_r)
write('electroNIX3a-B_Cu.gbl', 'Copper,L2,Bot', 'Positive', bot_r)
write('electroNIX3a-F_SilkS.gto', 'Legend,Top', 'Positive', rings(green, minarea=1))

# solder mask (Negative-style: openings drawn dark in a positive "opening" file)
def mask_items(sel):
    return [(x, y, d + 0.1) for x, y, d in sel]
open_th = mask_items(padflash)
# SMD pads guess: compact red blobs, wider than a track
k = np.ones((5, 5), np.uint8)
core = cv2.morphologyEx(red.astype(np.uint8), cv2.MORPH_OPEN, k)
nn, lb, ss, cc = cv2.connectedComponentsWithStats(core)
smd = np.zeros_like(red)
for i in range(1, nn):
    w, h, a = ss[i, 2], ss[i, 3], ss[i, 4]
    if a >= 0.7 * w * h and w * h < (5.0 * pxmm) ** 2:
        smd |= (lb == i)
smd = cv2.dilate(smd.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
smd &= red
smd_r = rings(cv2.dilate(smd.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
write('electroNIX3a-F_Mask.gts', 'Soldermask,Top', 'Negative', smd_r, flash_block(open_th))
write('electroNIX3a-B_Mask.gbs', 'Soldermask,Bot', 'Negative', [], flash_block(open_th))

# outline
with open(os.path.join(OUT, 'electroNIX3a-Edge_Cuts.gm1'), 'w') as f:
    f.write(HDR % ('Profile,NP', 'Positive') + 'D10*\n')
    for x, y, cmd in [(0, 0, 2), (BW, 0, 1), (BW, BH, 1), (0, BH, 1), (0, 0, 1)]:
        f.write('X%dY%dD0%d*\n' % (c(x), c(y), cmd))
    f.write('M02*\n')

# drills: mounting holes (large disc) NPTH at disc dia; others PTH at 0.5 * pad, min 0.3
pth, npth = [], []
for x, y, d in pads:
    if d > MOUNT: npth.append((x, y, 3.2))
    else: pth.append((x, y, round(max(0.3, min(d * 0.5, d - 0.6)), 1)))
def excellon(name, items, plated):
    ds = sorted({d for _, _, d in items})
    with open(os.path.join(OUT, name), 'w') as f:
        f.write('M48\n; #@! TF.FileFunction,%s\nMETRIC,TZ\n' % ('Plated,1,2,PTH' if plated else 'NonPlated,1,2,NPTH'))
        for i, d in enumerate(ds): f.write('T%dC%.3f\n' % (i + 1, d))
        f.write('%\nG90\nG05\n')
        for i, d in enumerate(ds):
            f.write('T%d\n' % (i + 1))
            for x, y, dd in items:
                if dd == d: f.write('X%.3fY%.3f\n' % (x, y))
        f.write('T0\nM30\n')
excellon('electroNIX3a-PTH.drl', pth, True)
excellon('electroNIX3a-NPTH.drl', npth, False)
print('PTH', len(pth), 'NPTH', len(npth), 'SMD-ish blobs', len(smd_r))
