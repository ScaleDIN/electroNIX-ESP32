#!/usr/bin/env python3
"""Connectivity checks for the electroNIX-3a rebuild.

Nets are built the same way for two versions of the copper, at the traced
rasters' resolution (16.75 px/mm): copper islands on each layer (8-connected)
joined through every plated hole.
  raster : the traced, bridged pixel layers (layers.npz)
  vector : the rebuilt Gerber geometry (vector_geom.pkl from vectorize.py)

1. Fidelity: pads (holes, U2 pins, SMD pads) connected in one version but
   not the other -> breaks / shorts introduced by vectorising.
2. Schematic (electroNIXclock 3v1): what it fixes unambiguously --
   U2 ATmega16 TQFP-44 (pin 1 at the dot) power/ground groups, crystal, ISP
   header, unused pins, signal pins on separate nets; the four ZM1080 lamps'
   cathodes multiplexed into 10 nets (one pad of each lamp), anodes separate.
usage: netcheck.py [vector|raster]     report -> ../netcheck_<version>.txt
"""
import os, sys, csv, pickle, numpy as np, cv2
from collections import defaultdict
sys.argv, _args = sys.argv[:1], sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vectorize as V

HERE = os.path.dirname(os.path.abspath(__file__))
BH = V.BH
SHAPE = V.cls.shape

def load(version):
    if version == 'raster':
        return V.TOP.copy(), V.BOT.copy()
    G = pickle.load(open(os.path.join(HERE, 'vector_geom_fixed.pkl'), 'rb'))
    return V.raster([G['top']], SHAPE), V.raster([G['bot']], SHAPE)

class Nets:
    def __init__(self, top, bot):
        self.nt, self.lt = cv2.connectedComponents(top.astype(np.uint8), connectivity=8)
        nb, self.lb = cv2.connectedComponents(bot.astype(np.uint8), connectivity=8)
        self.parent = list(range(self.nt + nb))
        for x, y, d in V.holes:
            a, b = V.px(x, y); a, b = int(a), int(b); r = max(2, int(d / 2 * V.S))
            ids = [int(i) for i in np.unique(self.lt[b - r:b + r + 1, a - r:a + r + 1]) if i]
            ids += [self.nt + int(i) for i in np.unique(self.lb[b - r:b + r + 1, a - r:a + r + 1]) if i]
            for i in ids[1:]: self.union(i, ids[0])
    def find(self, a):
        p = self.parent
        while p[a] != a: p[a] = p[p[a]]; a = p[a]
        return a
    def union(self, a, b): self.parent[self.find(a)] = self.find(b)
    def at(self, x, y, layer='T'):
        a, b = V.px(x, y); a, b = int(round(a)), int(round(b))
        for L, off in ((self.lt, 0), (self.lb, self.nt)) if layer == 'T' else ((self.lb, self.nt), (self.lt, 0)):
            v = L[b, a]
            if v: return self.find(off + int(v))
        return None

# ---- identified points ----------------------------------------------------
def img2mm(x, y): return (x - 27.5) / 8.375, BH - (y - 97.5) / 8.375
cx, cy = V.QFP_C
def u2_pin(n):
    s, k = divmod(n - 1, 11); t = (k - 5) * V.QFP_P; o = V.QFP_ROW / 2
    return [(cx - o, cy - t), (cx + t, cy - o), (cx + o, cy + t), (cx - t, cy + o)][s]
JP1_XY = [img2mm(*p) for p in [(112.0, 284.5), (133.2, 284.1), (112.1, 305.4), (133.2, 305.5), (112.0, 326.6), (133.2, 326.6)]]
lamp_pads = []                                 # (lamp, slot, x, y)
L = [(x, y) for x, y, d in V.holes if d == 1.7 and BH - y > 35]
for li, c0 in enumerate((10.4, 32.4, 59.4, 81.5)):
    pts = np.array([p for p in L if abs(p[0] - c0) < 8])
    A = np.c_[2 * pts, np.ones(len(pts))]; b = (pts ** 2).sum(1)
    lx, ly, _ = np.linalg.lstsq(A, b, rcond=None)[0]
    for x, y in pts:
        slot = int(round((np.degrees(np.arctan2(y - ly, x - lx)) % 360) / (360 / 14))) % 14
        lamp_pads.append((li + 1, slot, x, y))

def points(G=None):
    pts = [('H%.1f@%.1f,%.1f' % (d, x, BH - y), x, y) for x, y, d in V.holes]
    pts += [('U2.%d' % n, *u2_pin(n)) for n in range(1, 45)]
    if G:
        pts += [('SMD@%.1f,%.1f' % (c[0], BH - c[1]), c[0], c[1]) for k, g, c in G['pads'] if k == 'smd']
    return pts

# ---- checks ----------------------------------------------------------------
def schematic(N, out):
    def rep(ok, msg): out.append(('PASS ' if ok else 'FAIL ') + msg)
    U = {n: N.at(*u2_pin(n)) for n in range(1, 45)}
    J = {i + 1: N.at(*p) for i, p in enumerate(JP1_XY)}
    big = max(range(1, N.lb.max() + 1), key=lambda i: (N.lb == i).sum())
    gnd = N.find(N.nt + big)
    def pins(v): return sorted(n for n, u in U.items() if u == v and v is not None)
    name = lambda v: 'GND' if v == gnd else ('-' if v is None else 'U2%s' % pins(v))
    rep(all(U[n] == gnd for n in (6, 18, 28, 39)), 'U2 GND pins 6,18,28,39 on the ground pour: %s' % {n: name(U[n]) for n in (6, 18, 28, 39)})
    rep(len({U[n] for n in (5, 17, 38)}) == 1 and U[5] not in (None, gnd), 'U2 VCC pins 5,17,38 one net, not GND: %s' % {n: name(U[n]) for n in (5, 17, 38)})
    rep(U[27] == U[29] and U[27] not in (None, gnd), 'U2 AVCC 27 = AREF 29, not GND: %s' % {n: name(U[n]) for n in (27, 29)})
    for n in (7, 8, 16, 23, 24, 40, 41, 44):
        rep(U[n] is None or pins(U[n]) == [n] and U[n] != gnd, 'U2 pin %d unused, alone: %s' % (n, name(U[n])))
    for u, j, nm in ((1, 4, 'MOSI'), (2, 1, 'MISO'), (3, 3, 'SCK'), (4, 5, 'RESET')):
        rep(U[u] is not None and U[u] == J[j], 'U2 pin %d (%s) -> JP1 pin %d' % (u, nm, j))
    rep(J[6] == gnd, 'JP1 pin 6 on GND')
    rep(J[2] is not None and J[2] == U[5], 'JP1 pin 2 on +5V_BUF (= U2 pin 5)')
    signal = [n for n in range(1, 45) if n not in (5, 6, 7, 8, 16, 17, 18, 23, 24, 27, 28, 29, 38, 39, 40, 41, 44)]
    by = defaultdict(list)
    for n in signal: by[U[n]].append(n)
    rep(not [v for k, v in by.items() if k is not None and len(v) > 1], 'U2 signal pins on separate nets; shared: %s' % [v for k, v in by.items() if k is not None and len(v) > 1])
    rep(not [n for n in signal if U[n] == gnd], 'no U2 signal pin on GND: %s' % [n for n in signal if U[n] == gnd])
    slots = defaultdict(dict)
    for li, s, x, y in lamp_pads: slots[s][li] = N.at(x, y)
    cath = [s for s in slots if len(slots[s]) == 4 and len(set(slots[s].values())) == 1 and None not in slots[s].values()]
    rep(len(cath) == 10, 'lamp cathodes: %d of 10 slots shared by all 4 lamps %s' % (len(cath), sorted(cath)))
    for s in sorted(slots):
        if s in cath: continue
        grp = defaultdict(list)
        for li, v in slots[s].items(): grp[v].append(li)
        out.append('INFO lamp slot %2d: lamps grouped by net %s' % (s, sorted(grp.values())))
    k = [slots[s][1] for s in cath]
    rep(len(set(k)) == len(k), 'lamp cathode nets distinct from each other')
    return U, gnd

def fidelity(R, Vn, pts, out):
    ids_r = [R.at(x, y) for _, x, y in pts]; ids_v = [Vn.at(x, y) for _, x, y in pts]
    gr, gv = defaultdict(list), defaultdict(list)
    for i, (a, b) in enumerate(zip(ids_r, ids_v)):
        if a is not None: gr[a].append(i)
        if b is not None: gv[b].append(i)
    breaks, shorts = [], []
    for s in gr.values():
        parts = defaultdict(list)
        for i in s: parts[ids_v[i]].append(pts[i][0])
        if len(parts) > 1: breaks.append(list(parts.values()))
    for s in gv.values():
        parts = defaultdict(list)
        for i in s: parts[ids_r[i]].append(pts[i][0])
        if len(parts) > 1: shorts.append(list(parts.values()))
    out.append('INFO fidelity: %d raster nets split by the vector rebuild, %d vector nets merging raster nets' % (len(breaks), len(shorts)))
    for b in breaks: out.append('  split: %s' % ' | '.join(', '.join(p[:4]) + (' ...' if len(p) > 4 else '') for p in b))
    for s in shorts: out.append('  merge: %s' % ' | '.join(', '.join(p[:4]) + (' ...' if len(p) > 4 else '') for p in s))
    return breaks, shorts

if __name__ == '__main__':
    which = _args[0] if _args else 'vector'
    out = []
    N = Nets(*load(which))
    out.append('== schematic checks on the %s copper' % which)
    schematic(N, out)
    if which == 'vector':
        G = pickle.load(open(os.path.join(HERE, 'vector_geom.pkl'), 'rb'))
        out.append('== vector vs raster')
        fidelity(Nets(*load('raster')), N, points(G), out)
    txt = '\n'.join(out)
    open(os.path.join(os.path.dirname(HERE), 'netcheck_%s.txt' % which), 'w').write(txt + '\n')
    print(txt)
