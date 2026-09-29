#!/usr/bin/env python3
"""Close gaps in the vector rebuild that break required connections.

Required connections come from the schematic (lamp cathodes multiplexed,
U2 power/ground, ISP header) and from the traced raster where it joins a
small set of pads (large raster nets are unreliable: bridging over-merges).
For each required pair of nets, find the shortest chain of small gaps
(< GAP mm) between copper islands on the same layer -- intermediate islands
must be floating fragments with no pad -- where no bridging segment touches
copper of any other net. Each bridge is a straight 12 mil segment between the
nearest points. Results -> fixes.json (applied by vectorize.py).
"""
import os, sys, json, heapq, pickle, numpy as np
from collections import defaultdict
sys.argv, _args = sys.argv[:1], sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vectorize as V
import netcheck as NC
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
GAP, W, CLR = 1.2, 12 * V.MIL, 0.15
G = pickle.load(open(os.path.join(HERE, 'vector_geom.pkl'), 'rb'))

# islands and their nets (polygon level, joined through plated holes)
isl = []                                        # (layer, polygon)
for layer, geom in (('T', G['top']), ('B', G['bot'])):
    for p in getattr(geom, 'geoms', [geom]): isl.append((layer, p))
trees = {l: STRtree([p for ll, p in isl if ll == l]) for l in 'TB'}
idx = {l: [i for i, (ll, _) in enumerate(isl) if ll == l] for l in 'TB'}
parent = list(range(len(isl)))
def find(a):
    while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b): parent[find(a)] = find(b)
def island_at(layer, x, y):
    for k in trees[layer].query(Point(x, y), predicate='intersects'): return idx[layer][int(k)]
    return None
for x, y, d in V.holes:
    a, b = island_at('T', x, y), island_at('B', x, y)
    if a is not None and b is not None: union(a, b)
pads_xy = [(x, y) for x, y, d in V.holes] + [NC.u2_pin(n) for n in range(1, 45)] + \
          [c for k, g, c in G['pads'] if k == 'smd']
has_pad = set()
for x, y in pads_xy:
    for l in 'TB':
        i = island_at(l, x, y)
        if i is not None: has_pad.add(i)
def net_at(x, y):
    for l in 'TB':
        i = island_at(l, x, y)
        if i is not None: return find(i)
    return None

# candidate bridges between islands (same layer, gap < GAP)
edges = defaultdict(list)                       # island -> [(cost, other, (p, q))]
for l in 'TB':
    polys = [isl[i][1] for i in idx[l]]
    t = trees[l]
    for a_local, pa in enumerate(polys):
        for b_local in t.query(pa, predicate='dwithin', distance=GAP):
            b_local = int(b_local)
            if b_local <= a_local: continue
            pb = polys[b_local]
            p, q = nearest_points(pa, pb)
            d = p.distance(q)
            if d < 1e-3: continue
            seg = LineString([p, q]).buffer(W / 2 + CLR)
            bad = [k for k in t.query(seg, predicate='intersects') if int(k) not in (a_local, b_local)]
            if bad: continue
            a, b = idx[l][a_local], idx[l][b_local]
            edges[a].append((d, b, (p.coords[0], q.coords[0], l)))
            edges[b].append((d, a, (q.coords[0], p.coords[0], l)))

def bridge(na, nb):
    """Cheapest chain of bridges from any island of net na to any of nb,
    through pad-less islands only. Returns [(p, q, layer)] or None."""
    members = defaultdict(list)
    for i in range(len(isl)): members[find(i)].append(i)
    start, goal = set(members[na]), set(members[nb])
    dist = {i: 0.0 for i in start}; prev = {}
    pq = [(0.0, i) for i in start]; heapq.heapify(pq)
    while pq:
        d, i = heapq.heappop(pq)
        if d > dist.get(i, 1e9): continue
        if i in goal:
            path = []
            while i in prev: i, seg = prev[i]; path.append(seg)
            return path[::-1]
        if d > 3 * GAP: continue
        for c, j, seg in edges[i]:
            if j not in goal and (j in has_pad or find(j) in (na,)): continue
            nd = d + c
            if nd < dist.get(j, 1e9): dist[j] = nd; prev[j] = (i, seg); heapq.heappush(pq, (nd, j))
    return None

# required connections
req = []                                        # (reason, xy_a, xy_b)
slots = defaultdict(dict)
for li, s, x, y in NC.lamp_pads: slots[s][li] = (x, y)
anode = 2                                       # slot 2 runs to each lamp's anode resistor
for s, lp in slots.items():
    if s == anode: continue
    for li in (2, 3, 4): req.append(('lamp cathode slot %d: LAMP1-LAMP%d' % (s, li), lp[1], lp[li]))
big = max((p for l, p in isl if l == 'B'), key=lambda p: p.area)
gxy = big.representative_point().coords[0]
for n in (6, 18, 28, 39): req.append(('U2 pin %d GND' % n, NC.u2_pin(n), gxy))
for n in (17, 38): req.append(('U2 pin %d VCC with pin 5' % n, NC.u2_pin(n), NC.u2_pin(5)))
req.append(('U2 AREF 29 with AVCC 27', NC.u2_pin(29), NC.u2_pin(27)))
for u, j in ((1, 4), (2, 1), (3, 3), (4, 5)): req.append(('U2 pin %d to JP1 pin %d' % (u, j), NC.u2_pin(u), NC.JP1_XY[j - 1]))
req.append(('JP1 pin 6 GND', NC.JP1_XY[5], gxy))
req.append(('JP1 pin 2 +5V_BUF', NC.JP1_XY[1], NC.u2_pin(5)))
# raster: small pad groups it joins
R = NC.Nets(*NC.load('raster'))
grp = defaultdict(list)
for name, x, y in NC.points(G): grp[R.at(x, y)].append((name, x, y))
for k, v in grp.items():
    if k is None or len(v) < 2 or len(v) > 6: continue
    for name, x, y in v[1:]: req.append(('raster net: %s with %s' % (v[0][0], name), v[0][1:], (x, y)))

# schematic classes: nets holding points of two different classes must not join
cls_pts = [('GND', NC.u2_pin(n)) for n in (6, 18, 28, 39)] + [('GND', NC.JP1_XY[5]), ('GND', gxy)]
cls_pts += [('VCC', NC.u2_pin(n)) for n in (5, 17, 38)] + [('VCC', NC.JP1_XY[1])]
cls_pts += [('AVCC', NC.u2_pin(n)) for n in (27, 29)]
isp = {1: 4, 2: 1, 3: 3, 4: 5}
for n in range(1, 45):
    if n in (5, 6, 17, 18, 27, 28, 29, 38, 39): continue
    cls_pts.append(('U2.%d' % n, NC.u2_pin(n)))
    if n in isp: cls_pts.append(('U2.%d' % n, NC.JP1_XY[isp[n] - 1]))
for s_, lp in slots.items():
    for li, xy in lp.items(): cls_pts.append((('A%d' % li) if s_ == anode else ('K%d' % s_), xy))
def classes(net):
    return {c for c, xy in cls_pts if net_at(*xy) == net}
fixes, unresolved = [], []
for reason, a, b in req:
    na, nb = net_at(*a), net_at(*b)
    if na is None or nb is None: unresolved.append((reason, 'point not on copper')); continue
    if na == nb: continue
    ca, cb = classes(na), classes(nb)
    if ca and cb and ca != cb or len(ca | cb) > 1:
        unresolved.append((reason, 'would join %s' % sorted(ca | cb))); continue
    path = bridge(na, nb)
    if path is None: unresolved.append((reason, 'no gap < %.1f mm without touching other nets' % GAP)); continue
    for p, q, l in path:
        fixes.append({'layer': l, 'from': [round(p[0], 3), round(p[1], 3)], 'to': [round(q[0], 3), round(q[1], 3)],
                      'width': round(W, 4), 'reason': reason})
        i, j = island_at(l, *p), island_at(l, *q)
        if i is not None and j is not None: union(i, j)
json.dump({'bridges': fixes, 'unresolved': [{'reason': r, 'why': w} for r, w in unresolved]},
          open(os.path.join(HERE, 'fixes.json'), 'w'), indent=1)
print('%d required connections, %d bridges added, %d unresolved' % (len(req), len(fixes), len(unresolved)))
for r, w in unresolved: print('  UNRESOLVED %s: %s' % (r, w))
