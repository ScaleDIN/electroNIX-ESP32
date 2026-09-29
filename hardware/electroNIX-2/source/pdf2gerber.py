"""Convert the Altium toner-transfer PDF of electroNIX-2 into Gerber/Excellon.

Page 0 = bottom copper (as seen from top), page 1 = top copper (mirrored).
Light gray (0.82) fills = drill holes, light gray strokes = slots,
mid gray (0.35) thin strokes = board outline. Everything darker = copper.
"""
import math, os, sys, zipfile
import pymupdf as fitz
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, box
from shapely.ops import unary_union
from shapely import affinity

PDF = sys.argv[1]
OUT = sys.argv[2]
S = 0.3048 / 1.4355          # mm per pt, calibrated from 12 mil tracks
X0_B, X0_T, Y0 = 74.7679, 1183.7250, 347.0039   # outline left (page0), right (page1), bottom
QS = 24                      # arc segments per quarter circle

def tf(page, x, y):
    if page == 0:
        return ((x - X0_B) * S, (Y0 - y) * S)
    return ((X0_T - x) * S, (Y0 - y) * S)

def bez(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(1, n + 1):
        t = i / n; u = 1 - t
        pts.append((u**3*p0.x + 3*u*u*t*p1.x + 3*u*t*t*p2.x + t**3*p3.x,
                    u**3*p0.y + 3*u*u*t*p1.y + 3*u*t*t*p2.y + t**3*p3.y))
    return pts

def subpaths(items, re_reverse=True):
    """Return list of point lists (page coords)."""
    out, cur = [], None
    for it in items:
        k = it[0]
        if k == 're':
            r = it[1]
            ring = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
            if len(it) > 2 and (it[2] < 0) == re_reverse:   # rect direction matters for nonzero fills
                ring.reverse()
            out.append(ring)
            cur = None; continue
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

def fill_geom(page, d):
    rings = []
    # page 1 is mirrored by its content matrix, which flips the true direction
    # of 're' sub-paths relative to the orientation PyMuPDF reports
    for sp in subpaths(d['items'], page == 0):
        pts = [tf(page, *p) for p in sp]
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) >= 3 and Polygon(pts).buffer(0).area > 1e-6:
            rings.append(pts)
    if not rings:
        return None
    if len(rings) == 1:
        return Polygon(rings[0]).buffer(0)
    # exact fill rule: split the plane into faces bounded by all rings and
    # keep the faces whose winding number satisfies the rule
    from shapely.ops import polygonize
    lines = unary_union([LineString(r + [r[0]]) for r in rings])
    keep = []
    for face in polygonize(lines):
        p = face.representative_point()
        wn = sum(winding(r, p.x, p.y) for r in rings)
        if (wn % 2 != 0) if d.get('even_odd') else (wn != 0):
            keep.append(face)
    return unary_union(keep)

def stroke_geom(page, d):
    w = d['width'] * S
    parts = []
    for sp in subpaths(d['items']):
        pts = [tf(page, *p) for p in sp]
        if d.get('closePath') and len(pts) > 2:
            pts.append(pts[0])
        if len(pts) == 1 or all(math.dist(pts[0], q) < 1e-6 for q in pts):
            parts.append(Point(pts[0]).buffer(w / 2, quad_segs=QS))
        else:
            parts.append(LineString(pts).buffer(w / 2, quad_segs=QS))
    return unary_union(parts)

def is_dark(c):
    return c is not None and c[0] < 0.5
def is_hole_gray(c):
    return c is not None and 0.75 < c[0] < 0.9

def polys(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [p for p in getattr(g, 'geoms', []) if isinstance(p, Polygon)] + \
           [q for p in getattr(g, 'geoms', []) if not isinstance(p, Polygon) for q in polys(p)]

doc = fitz.open(PDF)
layers = {}        # 0 bottom, 1 top: list of (geom, padlike, kind)
holes = []         # (x, y, dia) per page (deduped later)
slots = []         # (x1,y1,x2,y2,width)
outline_segs = []
pad_marks = {0: [], 1: []}
track_w = {0: set(), 1: set()}   # stroke widths used by real tracks
stroke_w = {}

for pg in (0, 1):
    page = doc[pg]
    prims = []
    for d in page.get_drawings():
        t = d['type']
        if t == 'f' and is_hole_gray(d['fill']):
            r = d['rect']
            cx, cy = tf(pg, (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            holes.append((pg, cx, cy, (r.width + r.height) / 2 * S))
        elif t == 's' and is_hole_gray(d['color']):
            it = d['items'][0]
            a = tf(pg, it[1].x, it[1].y); b = tf(pg, it[2].x, it[2].y)
            slots.append((pg, a, b, d['width'] * S))
        elif t == 's' and d['color'] and 0.3 < d['color'][0] < 0.4:
            if pg == 0:
                for sp in subpaths(d['items']):
                    outline_segs.append([tf(pg, *p) for p in sp])
        elif t == 'f' and is_dark(d['fill']):
            g = fill_geom(pg, d)
            if g is not None and not g.is_empty:
                # pads are simple shapes (rect, quad, circle); pours are either
                # many-vertex outlines or have cut-outs (several sub-paths)
                simple = len(subpaths(d['items'])) == 1 and len(d['items']) <= 8
                prims.append((g, simple, 'fill'))
        elif t == 's' and is_dark(d['color']):
            g = stroke_geom(pg, d)
            it = d['items']
            padlike = False
            if len(it) == 1 and it[0][0] == 'l':
                L = math.dist(it[0][1], it[0][2])
                # round/obround pads are short fat strokes (QFP pads: 0.6 x 2 mm)
                padlike = L <= d['width'] * 3 and d['width'] > 2.5
            prims.append((g, padlike, 'stroke'))
            if not padlike:
                track_w[pg].add(round(d['width'], 2))
            stroke_w[id(g)] = round(d['width'], 2)
        else:
            print('unhandled', pg, t, d.get('fill'), d.get('color'), d['rect'])
    layers[pg] = prims
    for w in page.get_text('words'):
        if w[4].startswith('PA'):
            pad_marks[pg].append(tf(pg, (w[0] + w[2]) / 2, (w[1] + w[3]) / 2))

# ---- drills: dedupe across pages, check alignment between layers
def dedupe(hs):
    out = []
    for pg, x, y, dia in hs:
        for o in out:
            if math.dist((o[0], o[1]), (x, y)) < 0.15:
                o[3].append(pg); break
        else:
            out.append([x, y, dia, [pg]])
    return out
H = dedupe(holes)
single = [h for h in H if len(h[3]) == 1]
print('holes', len(H), 'seen on one page only:', len(single))
SL = []
for pg, a, b, w in slots:
    if not any(math.dist(a, s[0]) < 0.15 and math.dist(b, s[1]) < 0.15 or
               math.dist(a, s[1]) < 0.15 and math.dist(b, s[0]) < 0.15 for s in SL):
        SL.append((a, b, w))
print('slots', len(SL))

def snap_dia(d):
    return round(d / 0.05) * 0.05

# ---- copper
copper = {pg: unary_union([g for g, _, _ in layers[pg]]) for pg in (0, 1)}

# ---- pads
def size(g):
    # width of the shape: minimum side of its minimum rotated rectangle
    r = g.minimum_rotated_rectangle.exterior.coords
    return min(math.dist(r[0], r[1]), math.dist(r[1], r[2]))

PADPRIMS = {pg: [(g, k) for g, padlike, k in layers[pg] if padlike] for pg in (0, 1)}

def find_pads():
    via_centres = [Point(h[0], h[1]) for h in H if h[2] < 0.6]
    # anything plated through: holes and slot ends
    tht = [Point(h[0], h[1]) for h in H if h[2] >= 0.6] + \
          [Point(p) for a, b, w in SL for p in (a, b)]
    marks = [Point(m) for m in pad_marks[0]]   # same annotations on both pages
    single_fills = {pg: unary_union([g for g, k in PADPRIMS[pg] if k == 'fill']) for pg in (0, 1)}
    out = {0: [], 1: []}
    for pg in (0, 1):
        other = single_fills[1 - pg]
        for g, k in PADPRIMS[pg]:
            is_via = g.area < 1.0 and any(g.contains(v) for v in via_centres)
            if is_via:
                continue
            if k == 'fill':
                # single closed outlines are SMD/THT pads (pours have cut-outs)
                out[pg].append(g)
            elif any(g.contains(t) for t in tht):
                # a track-width stroke through a hole is a track, unless it is
                # the only copper drawn for that hole
                own = [t for t in tht if g.contains(t)]
                if stroke_w[id(g)] not in track_w[pg] or not all(
                        any(h is not g and h.contains(t) and (k2 == 'fill' or stroke_w[id(h)] not in track_w[pg])
                            for h, k2 in PADPRIMS[pg]) for t in own):
                    out[pg].append(g)
            elif size(g) >= 0.55 and stroke_w[id(g)] not in track_w[pg]:
                # (a short stroke in a track width is a track stub, not a pad)
                # stroke-drawn SMD pad (QFP, obround): an Altium pad label must sit
                # on it, and not on a filled pad of the other layer
                for m in marks:
                    if g.distance(m) < 0.1 and other.distance(m) > 0.4:
                        out[pg].append(g)
                        break
    return out

pads = find_pads()
print('pads bottom', len(pads[0]), 'top', len(pads[1]))

def pad_has_hole(g):
    return any(g.contains(Point(h[0], h[1])) for h in H) or any(
        g.distance(Point(a)) < 0.01 for a, b, w in SL)

MASK_EXP = 0.05
mask = {pg: unary_union([g.buffer(MASK_EXP, quad_segs=QS) for g in pads[pg]]) for pg in (0, 1)}
paste = {pg: unary_union([g for g in pads[pg] if not pad_has_hole(g)]) for pg in (0, 1)}

# plated vs non plated: copper ring around the hole on either layer
def plated(x, y, r):
    ring = Point(x, y).buffer(r + 0.25).difference(Point(x, y).buffer(r + 0.05))
    return any(copper[pg].intersection(ring).area > 0.6 * ring.area for pg in (0, 1))

# non-plated holes: the PDF shows a copper disc exactly the hole size; clear
# copper (and mask) 0.2 mm around them so the drill never cuts copper
npth = [h for h in H if not plated(h[0], h[1], h[2] / 2)]
keepout = unary_union([Point(h[0], h[1]).buffer(h[2] / 2 + 0.2, quad_segs=QS) for h in npth])
for pg in (0, 1):
    copper[pg] = copper[pg].difference(keepout)
    mask[pg] = unary_union([mask[pg], Point(0, 0).buffer(0)] +
                           [Point(h[0], h[1]).buffer(h[2] / 2 + 0.1, quad_segs=QS) for h in npth])
_plated = plated
def plated(x, y, r):
    return not any(math.dist((x, y), (h[0], h[1])) < 0.01 for h in npth)

# ---- board regions: main board + adapters (circles right of the main board)
main_w = (1040.2903 - X0_B) * S
main_h = (Y0 - 93.052) * S
print('main board %.3f x %.3f mm' % (main_w, main_h))
circles = []
for sp in outline_segs:
    xs = [p[0] for p in sp]; ys = [p[1] for p in sp]
    if max(xs) > main_w + 1:
        circles.append(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(xs) - min(xs)) / 2))
circles = sorted(set((round(a, 3), round(b, 3), round(r, 3)) for a, b, r in circles))
print('adapter circles', circles)

# ---- writers
def fmt(v):
    return str(int(round(v * 1e6)))

def gerber_header(name, func, polarity='Positive'):
    return ['G04 #@! TF.GenerationSoftware,pdf2gerber,electroNIX-2,1*',
            'G04 #@! TF.FileFunction,' + func + '*',
            'G04 #@! TF.FilePolarity,' + polarity + '*',
            '%FSLAX46Y46*%', '%MOMM*%', 'G04 ' + name + '*', '%ADD10C,0.100000*%', '%LPD*%', 'G01*']

def ring_cmds(coords, dx, dy):
    c = list(coords)
    out = ['G36*', 'X%sY%sD02*' % (fmt(c[0][0] - dx), fmt(c[0][1] - dy))]
    for x, y in c[1:]:
        out.append('X%sY%sD01*' % (fmt(x - dx), fmt(y - dy)))
    out.append('G37*')
    return out

def write_gerber(path, name, func, geom, dx, dy):
    L = gerber_header(name, func)
    ps = sorted(polys(geom.simplify(0.0005)), key=lambda p: -p.area)
    for p in ps:
        L += ring_cmds(p.exterior.coords, dx, dy)
        if p.interiors:
            L.append('%LPC*%')
            for h in p.interiors:
                L += ring_cmds(h.coords, dx, dy)
            L.append('%LPD*%')
    L.append('M02*')
    open(path, 'w').write('\n'.join(L) + '\n')

def write_outline(path, shapes, dx, dy):
    L = gerber_header('outline', 'Profile,NP')
    L += ['D10*']
    for sh in shapes:
        c = list(sh.exterior.coords)
        L.append('X%sY%sD02*' % (fmt(c[0][0] - dx), fmt(c[0][1] - dy)))
        for x, y in c[1:]:
            L.append('X%sY%sD01*' % (fmt(x - dx), fmt(y - dy)))
    L.append('M02*')
    open(path, 'w').write('\n'.join(L) + '\n')

def write_drill(path, hs, sls, dx, dy, pth):
    tools = sorted(set([snap_dia(h[2]) for h in hs] + [snap_dia(w) for _, _, w in sls]))
    L = ['M48', '; DRILL file electroNIX-2 (%s)' % ('PTH' if pth else 'NPTH'),
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
            L.append('X%.3fY%.3f' % (h[0] - dx, h[1] - dy))
        for a, b, w in ss:
            L.append('X%.3fY%.3fG85X%.3fY%.3f' % (a[0] - dx, a[1] - dy, b[0] - dx, b[1] - dy))
    L.append('M30')
    open(path, 'w').write('\n'.join(L) + '\n')
    return tools

def emit(tag, region, dx, dy, outline_shapes):
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    clip = region
    names = {
        'F_Cu.gtl': ('Copper,L1,Top', copper[1]),
        'B_Cu.gbl': ('Copper,L2,Bot', copper[0]),
        'F_Mask.gts': ('Soldermask,Top', mask[1]),
        'B_Mask.gbs': ('Soldermask,Bot', mask[0]),
        'F_Paste.gtp': ('Paste,Top', paste[1]),
        'B_Paste.gbp': ('Paste,Bot', paste[0]),
    }
    for fn, (func, g) in names.items():
        write_gerber(os.path.join(d, tag + '-' + fn), fn, func, g.intersection(clip), dx, dy)
    write_outline(os.path.join(d, tag + '-Edge_Cuts.gko'), outline_shapes, dx, dy)
    hs = [h for h in H if clip.contains(Point(h[0], h[1]))]
    ss = [s for s in SL if clip.contains(Point(s[0]))]
    p = [h for h in hs if plated(h[0], h[1], h[2] / 2)]
    n = [h for h in hs if not plated(h[0], h[1], h[2] / 2)]
    ps = [s for s in ss]   # slots are all for the (plated) DC jack
    t1 = write_drill(os.path.join(d, tag + '-PTH.drl'), p, ps, dx, dy, True)
    t2 = write_drill(os.path.join(d, tag + '-NPTH.drl'), n, [], dx, dy, False)
    print(tag, 'PTH', len(p), t1, 'slots', len(ps), 'NPTH', len(n), t2)
    z = zipfile.ZipFile(os.path.join(OUT, tag + '-gerbers.zip'), 'w', zipfile.ZIP_DEFLATED)
    for fn in sorted(os.listdir(d)):
        z.write(os.path.join(d, fn), fn)
    z.close()

main_region = box(-0.5, -0.5, main_w + 0.5, main_h + 0.5)
emit('electroNIX2', main_region, 0, 0, [box(0, 0, main_w, main_h)])
if circles:
    # the three round boards are identical; emit one design (order qty 3+)
    cs = [Point(x, y).buffer(r, quad_segs=64) for x, y, r in circles[:1]]
    reg = unary_union([c.buffer(0.3) for c in cs])
    minx, miny, _, _ = reg.bounds
    emit('electroNIX2-socket-adapter', reg, minx, miny, cs)

