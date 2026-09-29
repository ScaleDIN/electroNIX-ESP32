"""Convert the two toner-transfer PDFs of electroNIX-4 (PCB-061) into Gerber/Excellon.

Usage: pdf2gerber.py TOP.pdf BOT.pdf OUTDIR

Each PDF is one copper layer with two boards on the page: the tube (display)
board in the upper half and the controller (main) board in the lower half.
The artwork is 1:1 (600 dpi grid, 1 pt = 25.4/72 mm). BOT is drawn as seen
from the top; TOP is drawn mirrored (toner-transfer convention).

Black fills/strokes = copper, white fills = drill holes, white strokes = slots,
thin (<0.8 pt) black strokes = board outline / page frame.
"""
import math, os, sys, zipfile
import pymupdf as fitz
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union, polygonize

PDF_TOP, PDF_BOT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
S = 25.4 / 72                 # mm per pt: the print is 1:1 (stroke widths are whole mils)
QS = 24                       # arc segments per quarter circle
MASK_EXP = 0.05

doc = {1: fitz.open(PDF_TOP)[0], 0: fitz.open(PDF_BOT)[0]}   # 1 = top copper, 0 = bottom copper

# ---- board frames from the 10 mil outline strokes (same on both pages)
hl, vl = [], []
for d in doc[0].get_drawings():
    if d['type'] == 's' and d['color'] == (0.0, 0.0, 0.0) and d['width'] < 0.8:
        for it in d['items']:
            if it[0] != 'l':
                continue
            a, b = it[1], it[2]
            if abs(a.y - b.y) < 1e-3 and abs(a.x - b.x) > 300:
                hl.append(round(a.y, 2)); XL, XR = min(a.x, b.x), max(a.x, b.x)
            elif abs(a.x - b.x) < 1e-3:
                vl.append(round(a.x, 2))
ys = sorted(set(hl))
assert len(ys) == 4, ys
BOARDS = {'display': (ys[0], ys[1]),        # page y of top edge, bottom edge
          'main': (ys[2], ys[3])}
print('x range', XL, XR, 'boards', BOARDS)

def tf(pg, x, y, ybot):
    xm = (x - XL) * S if pg == 0 else (XR - x) * S
    return (xm, (ybot - y) * S)

def board_of(rect):
    cy = (rect.y0 + rect.y1) / 2
    for name, (yt, yb) in BOARDS.items():
        if yt - 2 <= cy <= yb + 2:
            return name
    return None

def bez(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(1, n + 1):
        t = i / n; u = 1 - t
        pts.append((u**3*p0.x + 3*u*u*t*p1.x + 3*u*t*t*p2.x + t**3*p3.x,
                    u**3*p0.y + 3*u*u*t*p1.y + 3*u*t*t*p2.y + t**3*p3.y))
    return pts

def subpaths(items):
    out, cur = [], None
    for it in items:
        k = it[0]
        if k == 're':
            r = it[1]
            ring = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
            if len(it) > 2 and it[2] < 0:     # keep direction consistent with the other paths
                ring.reverse()
            out.append(ring); cur = None; continue
        if k == 'qu':
            q = it[1]
            out.append([tuple(q.ul), tuple(q.ur), tuple(q.lr), tuple(q.ll), tuple(q.ul)])
            cur = None; continue
        start = it[1]
        if cur is None or math.dist(cur[-1], (start.x, start.y)) > 1e-3:
            cur = [(start.x, start.y)]; out.append(cur)
        if k == 'l':
            cur.append((it[2].x, it[2].y))
        elif k == 'c':
            cur.extend(bez(*it[1:5]))
    return out

def winding(ring, x, y):
    wn = 0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if y1 <= y:
            if y2 > y and (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1) > 0:
                wn += 1
        elif y2 <= y and (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1) < 0:
            wn -= 1
    return wn

def fill_geom(pg, d, ybot):
    rings = []
    for sp in subpaths(d['items']):
        pts = [tf(pg, *p, ybot) for p in sp]
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) >= 3 and Polygon(pts).buffer(0).area > 1e-6:
            rings.append(pts)
    if not rings:
        return None
    if len(rings) == 1:
        return Polygon(rings[0]).buffer(0)
    # exact nonzero/even-odd fill: polygonize all rings, keep faces by winding number
    lines = unary_union([LineString(r + [r[0]]) for r in rings])
    keep = []
    for face in polygonize(lines):
        p = face.representative_point()
        wn = sum(winding(r, p.x, p.y) for r in rings)
        if (wn % 2 != 0) if d.get('even_odd') else (wn != 0):
            keep.append(face)
    return unary_union(keep)

def stroke_geom(pg, d, ybot):
    w = d['width'] * S
    parts = []
    for sp in subpaths(d['items']):
        pts = [tf(pg, *p, ybot) for p in sp]
        if d.get('closePath') and len(pts) > 2:
            pts.append(pts[0])
        if len(pts) == 1 or all(math.dist(pts[0], q) < 1e-6 for q in pts):
            parts.append(Point(pts[0]).buffer(w / 2, quad_segs=QS))
        else:
            parts.append(LineString(pts).buffer(w / 2, quad_segs=QS))
    return unary_union(parts)

def polys(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [q for p in getattr(g, 'geoms', []) for q in polys(p)]

WHITE, BLACK = (1.0, 1.0, 1.0), (0.0, 0.0, 0.0)
# per board: layers[pg] = list of dict(g, simple, kind, w, L)
layers = {b: {0: [], 1: []} for b in BOARDS}
holes = {b: [] for b in BOARDS}      # (pg, x, y, dia)
slots = {b: [] for b in BOARDS}      # (pg, a, b, width)

for pg in (0, 1):
    for d in doc[pg].get_drawings():
        b = board_of(d['rect'])
        if b is None:
            continue
        ybot = BOARDS[b][1]
        t = d['type']
        if t == 'f' and d['fill'] == WHITE:
            r = d['rect']
            cx, cy = tf(pg, (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, ybot)
            holes[b].append((pg, cx, cy, (r.width + r.height) / 2 * S))
        elif t == 's' and d['color'] == WHITE:
            it = d['items'][0]
            slots[b].append((pg, tf(pg, it[1].x, it[1].y, ybot), tf(pg, it[2].x, it[2].y, ybot), d['width'] * S))
        elif t == 'f' and d['fill'] == BLACK:
            g = fill_geom(pg, d, ybot)
            if g is not None and not g.is_empty:
                simple = len(subpaths(d['items'])) == 1 and len(d['items']) <= 8
                layers[b][pg].append(dict(g=g, simple=simple, kind='fill', w=0, L=0))
        elif t == 's' and d['color'] == BLACK:
            if d['width'] < 0.8:
                continue                       # outline / page frame
            L = sum(math.dist(i[1], i[2]) for i in d['items'] if i[0] == 'l')
            layers[b][pg].append(dict(g=stroke_geom(pg, d, ybot), simple=len(d['items']) == 1,
                                      kind='stroke', w=round(d['width'], 2), L=L,
                                      pw=d['width'], wmm=d['width'] * S))
        else:
            print('unhandled', pg, t, d.get('fill'), d.get('color'), d['rect'])

def dedupe(hs):
    out = []
    for pg, x, y, dia in hs:
        for o in out:
            if math.dist((o[0], o[1]), (x, y)) < 0.15:
                o[3].append(pg); o[4].append(dia); break
        else:
            out.append([x, y, dia, [pg], [dia]])
    for o in out:
        o[2] = sum(o[4]) / len(o[4])
    return out

_SNAP = {}
def build_snap(dias):
    """Cluster the printed mark sizes (they scatter by +-1 grid unit = 0.04 mm) and
    snap each cluster to 0.05 mm. Marks read ~0.03 mm below nominal, so add it back."""
    cl = []
    for d in sorted(dias):
        if cl and d - cl[-1][-1] < 0.08:
            cl[-1].append(d)
        else:
            cl.append([d])
    for c in cl:
        v = round((sum(c) / len(c) + 0.03) / 0.05) * 0.05
        for d in c:
            _SNAP[round(d, 6)] = round(v, 3)

def snap_dia(d):
    return _SNAP[round(d, 6)]

def size(g):
    r = g.minimum_rotated_rectangle.exterior.coords
    return min(math.dist(r[0], r[1]), math.dist(r[1], r[2]))

# ---- writers
def fmt(v):
    return str(int(round(v * 1e6)))

def gerber_header(name, func, board, polarity='Positive'):
    return ['G04 #@! TF.GenerationSoftware,pdf2gerber,electroNIX-4 %s,1*' % board,
            'G04 #@! TF.FileFunction,' + func + '*',
            'G04 #@! TF.FilePolarity,' + polarity + '*',
            '%FSLAX46Y46*%', '%MOMM*%', 'G04 ' + name + '*', '%ADD10C,0.100000*%', '%LPD*%', 'G01*']

def ring_cmds(coords):
    c = list(coords)
    out = ['G36*', 'X%sY%sD02*' % (fmt(c[0][0]), fmt(c[0][1]))]
    for x, y in c[1:]:
        out.append('X%sY%sD01*' % (fmt(x), fmt(y)))
    out.append('G37*')
    return out

def write_gerber(path, name, func, geom, board):
    L = gerber_header(name, func, board)
    for p in sorted(polys(geom.simplify(0.0005)), key=lambda p: -p.area):
        L += ring_cmds(p.exterior.coords)
        if p.interiors:
            L.append('%LPC*%')
            for h in p.interiors:
                L += ring_cmds(h.coords)
            L.append('%LPD*%')
    L.append('M02*')
    open(path, 'w').write('\n'.join(L) + '\n')

def write_outline(path, w, h, board):
    L = gerber_header('outline', 'Profile,NP', board) + ['D10*']
    pts = [(0, 0), (w, 0), (w, h), (0, h), (0, 0)]
    L.append('X%sY%sD02*' % (fmt(pts[0][0]), fmt(pts[0][1])))
    for x, y in pts[1:]:
        L.append('X%sY%sD01*' % (fmt(x), fmt(y)))
    L.append('M02*')
    open(path, 'w').write('\n'.join(L) + '\n')

def write_drill(path, hs, sls, pth, board):
    tools = sorted(set([snap_dia(h[2]) for h in hs] + [snap_dia(w) for _, _, w in sls]))
    L = ['M48', '; DRILL file electroNIX-4 %s (%s)' % (board, 'PTH' if pth else 'NPTH'),
         '; #@! TF.FileFunction,%s,1,2,%s' % ('Plated' if pth else 'NonPlated', 'PTH' if pth else 'NPTH'),
         'METRIC']
    for i, t in enumerate(tools, 1):
        L.append('T%dC%.3f' % (i, t))
    L += ['%', 'G90', 'G05']
    for i, t in enumerate(tools, 1):
        items = [h for h in hs if snap_dia(h[2]) == t]
        ss = [s for s in sls if snap_dia(s[2]) == t]
        if not items and not ss:
            continue
        L.append('T%d' % i)
        for h in items:
            L.append('X%.3fY%.3f' % (h[0], h[1]))
        for a, b, w in ss:
            L.append('X%.3fY%.3fG85X%.3fY%.3f' % (a[0], a[1], b[0], b[1]))
    L.append('M30')
    open(path, 'w').write('\n'.join(L) + '\n')
    return tools

os.makedirs(OUT, exist_ok=True)
NAMES = {'display': 'electroNIX4-display', 'main': 'electroNIX4-main'}

for b, (yt, yb) in BOARDS.items():
    W, Hh = (XR - XL) * S, (yb - yt) * S
    tag = NAMES[b]
    print('== %s: %.3f x %.3f mm' % (tag, W, Hh))
    H = dedupe(holes[b])
    single = [h for h in H if len(h[3]) == 1]
    print('holes', len(H), 'seen on one page only:', len(single),
          'max dia mismatch between pages %.3f' % max(abs(h[4][0] - h[4][-1]) for h in H))
    SL = []
    for pg, a, c, w in slots[b]:
        if not any(math.dist(a, s[0]) < 0.15 and math.dist(c, s[1]) < 0.15 or
                   math.dist(a, s[1]) < 0.15 and math.dist(c, s[0]) < 0.15 for s in SL):
            SL.append((a, c, w))
    print('slots', len(SL), 'slot pages agree:', len(slots[b]) == 2 * len(SL))
    _SNAP.clear()
    build_snap([h[2] for h in H] + [s[2] for s in SL])

    copper = {pg: unary_union([p['g'] for p in layers[b][pg]]) for pg in (0, 1)}

    # ---- pads (solder mask openings)
    via_centres = [Point(h[0], h[1]) for h in H if h[2] < 0.6]
    tht = [Point(h[0], h[1]) for h in H if h[2] >= 0.6] + [Point(p) for a, c, w in SL for p in (a, c)]
    # widths used by long/multi-segment strokes = real tracks
    track_w = {pg: {p['w'] for p in layers[b][pg] if p['kind'] == 'stroke' and (not p['simple'] or p['L'] > 3 * p['pw'])}
               for pg in (0, 1)}
    # short fat strokes (>= 0.53 mm) are round/obround pads; thin ones (<= 20 mil) are track pieces
    def padlike_stroke(p):
        return p['simple'] and p['L'] <= p['pw'] * 3 and p['wmm'] > 0.53
    single_fills = {pg: unary_union([p['g'] for p in layers[b][pg] if p['kind'] == 'fill' and p['simple']])
                    for pg in (0, 1)}
    pads = {0: [], 1: []}
    for pg in (0, 1):
        for p in layers[b][pg]:
            g = p['g']
            if p['kind'] == 'fill':
                if not p['simple']:
                    continue                                   # pour
                # vias are tented
                if g.area < 1.0 and any(g.contains(v) for v in via_centres):
                    continue
                pads[pg].append(g)
            else:
                own = [t for t in tht if g.contains(t)]
                if own:
                    # a track-width stroke through a hole is a track, unless it is the only copper for that hole
                    if p['w'] not in track_w[pg] or not all(
                            any(q['g'] is not g and q['g'].contains(t) and
                                (q['kind'] == 'fill' and q['simple'] or q['w'] not in track_w[pg])
                                for q in layers[b][pg]) for t in own):
                        pads[pg].append(g)
                elif padlike_stroke(p):
                    if p['L'] > 0.05 and p['w'] in track_w[pg]:
                        continue                               # short piece of track, not a pad
                    if g.area < 1.0 and any(g.contains(v) for v in via_centres):
                        continue                               # stroke-drawn via land
                    if g.intersects(single_fills[pg]):
                        continue                               # stub of a track leaving a filled pad
                    pads[pg].append(g)
    print('pads bottom', len(pads[0]), 'top', len(pads[1]))

    def pad_has_hole(g):
        return any(g.contains(Point(h[0], h[1])) for h in H) or any(
            g.distance(Point(a)) < 0.01 for a, c, w in SL)

    mask = {pg: unary_union([g.buffer(MASK_EXP, quad_segs=QS) for g in pads[pg]]) for pg in (0, 1)}
    paste = {pg: unary_union([g for g in pads[pg] if not pad_has_hole(g)]) for pg in (0, 1)}

    # plated if a copper ring surrounds the hole on either layer
    def plated_test(x, y, r):
        ring = Point(x, y).buffer(r + 0.25).difference(Point(x, y).buffer(r + 0.05))
        return any(copper[pg].intersection(ring).area > 0.6 * ring.area for pg in (0, 1))
    npth = [h for h in H if not plated_test(h[0], h[1], h[2] / 2)]
    keepout = unary_union([Point(h[0], h[1]).buffer(h[2] / 2 + 0.2, quad_segs=QS) for h in npth] + [Point(0, 0).buffer(0)])
    for pg in (0, 1):
        copper[pg] = copper[pg].difference(keepout)
        mask[pg] = unary_union([mask[pg]] + [Point(h[0], h[1]).buffer(h[2] / 2 + 0.1, quad_segs=QS) for h in npth])
    npth_ids = {id(h) for h in npth}

    clip = box(-0.5, -0.5, W + 0.5, Hh + 0.5)
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    files = {
        'F_Cu.gtl': ('Copper,L1,Top', copper[1]),
        'B_Cu.gbl': ('Copper,L2,Bot', copper[0]),
        'F_Mask.gts': ('Soldermask,Top', mask[1]),
        'B_Mask.gbs': ('Soldermask,Bot', mask[0]),
        'F_Paste.gtp': ('Paste,Top', paste[1]),
        'B_Paste.gbp': ('Paste,Bot', paste[0]),
    }
    for fn, (func, g) in files.items():
        write_gerber(os.path.join(d, tag + '-' + fn), fn, func, g.intersection(clip), b)
    write_outline(os.path.join(d, tag + '-Edge_Cuts.gko'), W, Hh, b)
    p_ = [h for h in H if id(h) not in npth_ids]
    n_ = [h for h in H if id(h) in npth_ids]
    t1 = write_drill(os.path.join(d, tag + '-PTH.drl'), p_, SL, True, b)
    t2 = write_drill(os.path.join(d, tag + '-NPTH.drl'), n_, [], False, b)
    print(tag, 'PTH', len(p_), t1, 'slots', len(SL), 'NPTH', len(n_), t2)
    z = zipfile.ZipFile(os.path.join(OUT, tag + '-gerbers.zip'), 'w', zipfile.ZIP_DEFLATED)
    for fn in sorted(os.listdir(d)):
        z.write(os.path.join(d, fn), fn)
    z.close()
