#!/usr/bin/env python3
"""Show the chain of copper elements joining two points in the vector rebuild
(top: pads, tracks, links, pours; bottom: copper islands; joined through
plated holes). Used to find where an unwanted short happens.
usage: trace.py x1 y1 x2 y2      (mm, y from the TOP edge like the image)"""
import os, sys, pickle, json
args = sys.argv[1:]; sys.argv = sys.argv[:1]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import networkx as nx
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree
import vectorize as V

HERE = os.path.dirname(os.path.abspath(__file__))
G = pickle.load(open(os.path.join(HERE, 'vector_geom.pkl'), 'rb'))
el = []
for k, g, c in G['pads']: el.append(('T', 'pad-%s @%.2f,%.2f' % (k, c[0], V.BH - c[1]), g))
for l, w in G['ttr']:
    el.append(('T', 'track %dmil %s' % (round(w / V.MIL), [(round(a, 2), round(V.BH - b, 2)) for a, b in l.coords]), l.buffer(w / 2)))
for r in G.get('links', []): el.append(('T', 'link @%.2f,%.2f' % (r.centroid.x, V.BH - r.centroid.y), r))
tp = G.get('tpours')
if tp is not None and not tp.is_empty:
    for p in getattr(tp, 'geoms', [tp]): el.append(('T', 'top copper area @%.1f,%.1f (%.1f mm2)' % (p.centroid.x, V.BH - p.centroid.y, p.area), p))
fx = os.path.join(HERE, 'fixes.json')
if os.path.exists(fx):
    for b in json.load(open(fx))['bridges']:
        el.append((b['layer'], 'bridge %s' % b['reason'], LineString([b['from'], b['to']]).buffer(b['width'] / 2)))
for p in getattr(G['bot'], 'geoms', [G['bot']]):
    el.append(('B', 'bottom island @%.1f,%.1f (%.1f mm2)' % (p.centroid.x, V.BH - p.centroid.y, p.area), p))
trees = {l: STRtree([g for ll, _, g in el if ll == l]) for l in 'TB'}
ids = {l: [i for i, (ll, _, _) in enumerate(el) if ll == l] for l in 'TB'}
g = nx.Graph(); g.add_nodes_from(range(len(el)))
for l in 'TB':
    for i in ids[l]:
        for j in trees[l].query(el[i][2], predicate='intersects'):
            j = ids[l][int(j)]
            if j != i: g.add_edge(i, j)
for x, y, d in V.holes:
    a = [ids['T'][int(k)] for k in trees['T'].query(Point(x, y), predicate='intersects')]
    b = [ids['B'][int(k)] for k in trees['B'].query(Point(x, y), predicate='intersects')]
    for i in a + b:
        for j in a + b:
            if i != j: g.add_edge(i, j, hole=(x, V.BH - y))
def at(x, y):
    p = Point(x, V.BH - y)
    return [ids[l][int(k)] for l in 'TB' for k in trees[l].query(p, predicate='intersects')]
if __name__ == '__main__':
    x1, y1, x2, y2 = map(float, args)
    a, b = at(x1, y1), at(x2, y2)
    if not a or not b: sys.exit('a point is not on copper')
    try:
        path = nx.shortest_path(g, a[0], b[0])
    except nx.NetworkXNoPath:
        sys.exit('not connected')
    for i in path: print('%s  %s' % (el[i][0], el[i][1]))
