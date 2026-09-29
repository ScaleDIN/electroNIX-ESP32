#!/usr/bin/env python3
"""Rebuild electroNIX-3a copper as CAD primitives from the traced rasters.

Pixel tracing of the 0.12 mm/px JPEG gives ragged edges. This script instead
fits what the original Altium layout was made of:
  * tracks: skeleton centrelines -> straight runs snapped to 0/45/90 degrees,
    widths snapped to a standard set (area / length per run);
  * SMD pads: rotated rectangles, angle snapped to 45 deg, size to 0.05 mm;
  * vias / TH pads / U2: from the measured hole list and footprint;
  * bottom pour: its outline simplified the same way, minus one constant
    clearance around every object that isn't part of it.

usage: vectorize.py [x0 x1 y0 y1]   (region in mm, y measured from the top
edge like the image; default = whole board). Output goes to vector/.
"""
import sys, os, numpy as np, cv2, csv
from collections import defaultdict
from skimage.morphology import skeletonize
from skan import Skeleton
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
z = np.load(os.path.join(HERE, 'layers.npz'))
cls, TOP, BOT = z['cls'], z['top'], z['bot']
S = float(z['S'])                     # px/mm of the rasters (2x image)
BW, BH = 92.0, 56.0
OFF = 0.5 / 8.375                     # raster (0,0) is image px 28,98 = outline + 0.5 px
W, N, R, G, RING, CORE, BEIGE = range(7)

def mm(xp, yp): return xp / S + OFF, BH - (yp / S + OFF)
def px(xm, ym): return (xm - OFF) * S, (BH - ym - OFF) * S

reg = [float(v) for v in sys.argv[1:5]] if len(sys.argv) >= 5 else [0, BW, 0, BH]
CLIP = box(reg[0], BH - reg[3], reg[1], BH - reg[2])
M = 1.5                                # working margin around the region, mm
x0p, y0p = [int(max(0, v)) for v in px(reg[0] - M, BH - reg[2] + M)]
x1p, y1p = [int(min(lim, v)) for v, lim in zip(px(reg[1] + M, BH - reg[3] - M), (cls.shape[1], cls.shape[0]))]
sl = np.s_[y0p:y1p, x0p:x1p]
def mmw(xp, yp): return mm(xp + x0p, yp + y0p)
def pxw(xm, ym): a, b = px(xm, ym); return a - x0p, b - y0p

from PIL import Image
from scipy.ndimage import map_coordinates
_im = np.asarray(Image.open(os.path.join(HERE, 'electroNIX-3a_layout.jpg')).convert('RGB')).astype(float)
REDNESS = np.clip((_im[..., 0] - (_im[..., 1] + _im[..., 2]) / 2 - 20) / 205, 0, 1)
_nb = _im[..., 2] - np.maximum(_im[..., 0], _im[..., 1])       # navy-ness, white/red ~0
NAVYNESS = np.clip((_nb - 20) / 115, 0, 1)
WHITENESS = np.clip((_im.min(2) - 60) / 180, 0, 1)
def img_px(xm, ym): return 27.5 + xm * 8.375, 97.5 + (BH - ym) * 8.375

def profile_width(line, chan):
    """Integrate a colour-fraction image across the track at points along
    it; anti-aliased edges then count proportionally. Only profiles that
    fall back to ~0 on both sides (nothing else touching) are used."""
    ws = []
    for a, b in zip(line.coords[:-1], line.coords[1:]):
        a, b = np.array(a), np.array(b); L = np.hypot(*(b - a))
        if L < 0.5: continue
        u = (b - a) / L; nrm = np.array([-u[1], u[0]])
        for t in np.arange(0.2, L - 0.2, 0.15):
            p = a + u * t
            offs = np.arange(-1.2, 1.2001, 0.03)
            q = p[None] + offs[:, None] * nrm[None]
            xs, ys = img_px(q[:, 0], q[:, 1])
            v = map_coordinates(chan, [ys, xs], order=1)
            # walk out from the centre to where it drops below 0.15
            c0 = len(offs) // 2
            if v[c0] < 0.6: continue
            l = c0
            while l > 0 and v[l] > 0.15: l -= 1
            r = c0
            while r < len(v) - 1 and v[r] > 0.15: r += 1
            if l == 0 or r == len(v) - 1: continue
            ws.append(v[max(0, l - 3):r + 4].sum() * 0.03)
    return float(np.median(ws)) if len(ws) >= 3 else None

# ---- standard values -------------------------------------------------------
MIL = 0.0254
WIDTHS = [8 * MIL, 10 * MIL, 12 * MIL, 15 * MIL, 20 * MIL, 25 * MIL, 30 * MIL, 40 * MIL, 50 * MIL]
def snapw(w): return min(WIDTHS, key=lambda t: abs(t - w))
def snap05(v): return round(v / 0.05) * 0.05

# ---- known objects: holes, vias, U2 ---------------------------------------
holes = []
with open(os.path.join(HERE, 'holes.csv')) as f:
    for row in csv.DictReader(f):
        if row['measured_mm'] == 'NPTH': continue
        holes.append((float(row['x_mm']), float(row['y_mm']), float(row['drill_mm'])))
VIA_PAD = 1.0

def th_pad_shapes():
    """Round TH pads measured from the ring blobs (vias fixed at 1.0 mm)."""
    out = []
    padmask = np.isin(cls[sl], (RING, CORE, BEIGE)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(padmask)
    done = set()
    for x, y, d in holes:
        if d == 0.5:
            out.append(('via', Point(x, y).buffer(VIA_PAD / 2, 32), (x, y))); continue
        a, b = pxw(x, y)
        if not (0 <= a < padmask.shape[1] and 0 <= b < padmask.shape[0]): continue
        i = lab[int(b), int(a)]
        if i == 0 or i in done: continue
        done.add(i)
        ys, xs = np.nonzero(lab == i)
        (cx, cy), (w, h), ang = cv2.minAreaRect(np.c_[xs, ys].astype(np.float32))
        w, h = snap05((w + 1) / S), snap05((h + 1) / S)
        X, Y = mmw(cx, cy)
        if abs(w - h) < 0.3:
            out.append(('th', Point(X, Y).buffer(max(w, h) / 2, 32), (X, Y)))
        else:
            L = max(w, h) - min(w, h); a_ = np.radians(-(ang if w > h else ang + 90))
            dx, dy = L / 2 * np.cos(a_), L / 2 * np.sin(a_)
            out.append(('th', LineString([(X - dx, Y - dy), (X + dx, Y + dy)]).buffer(min(w, h) / 2, 32), (X, Y)))
    return out

QFP_C = ((255 - 27.5) / 8.375, BH - (303 - 97.5) / 8.375)
QFP_ROW, QFP_L, QFP_W, QFP_P = 96 / 8.375, 2.03, 0.5, 0.8
def qfp_shapes():
    out = []; cx, cy = QFP_C
    for side in range(4):
        for k in range(11):
            t = (k - 5) * QFP_P; o = QFP_ROW / 2
            x, y, horiz = [(t, o, False), (t, -o, False), (-o, t, True), (o, t, True)][side]
            w, h = (QFP_L, QFP_W) if horiz else (QFP_W, QFP_L)
            out.append(('qfp', box(cx + x - w / 2, cy + y - h / 2, cx + x + w / 2, cy + y + h / 2), (cx + x, cy + y)))
    return out

def raster(geoms, shape, grow=0.0):
    m = np.zeros(shape, np.uint8)
    for g in geoms:
        g = g.buffer(grow) if grow else g
        for p in getattr(g, 'geoms', [g]):
            if p.is_empty or p.geom_type != 'Polygon': continue
            poly = lambda r: np.round(np.array([pxw(*c) for c in r.coords], np.float32) * 4).astype(np.int32)
            cv2.fillPoly(m, [poly(p.exterior)], 1, shift=2)
            if len(p.interiors):
                cv2.fillPoly(m, [poly(r) for r in p.interiors], 0, shift=2)
    return m.astype(bool)

# ---- rectangles for SMD pads ----------------------------------------------
def fit_pads(mask, exclude):
    """Compact copper blobs wider than any track -> rotated rectangles."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.8 * S) | 1, int(0.8 * S) | 1))
    fat = cv2.morphologyEx((mask & ~exclude).astype(np.uint8), cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(fat)
    pads, pours = [], []
    for i in range(1, n):
        comp = lab == i
        ys, xs = np.nonzero(comp)
        if len(xs) < 0.5 * S * S: continue
        (cx, cy), (w, h), ang = cv2.minAreaRect(np.c_[xs, ys].astype(np.float32))
        fill = len(xs) / max(1.0, w * h)
        vis = (cls[sl][comp] == R).mean()          # letter fill under silk is not a pad
        if fill > 0.85 and max(w, h) / S < 6 and vis > 0.5:
            a45 = round(ang / 45) * 45; da = ang - a45
            w, h = snap05((w + 1) / S), snap05((h + 1) / S)
            X, Y = mmw(cx, cy)
            p = affinity.rotate(box(-w / 2, -h / 2, w / 2, h / 2), -a45, origin=(0, 0))
            pads.append(('smd', affinity.translate(p, X, Y), (X, Y)))
        elif fill <= 0.85 or max(w, h) / S >= 6:
            pours.append(comp)
    pm = np.zeros(mask.shape, bool)
    for comp in pours: pm |= comp
    # the opening rounded the pour's corners: take the real pixels back
    pm = cv2.dilate(pm.astype(np.uint8), k).astype(bool) & mask & ~exclude
    return pads, pm

# ---- tracks ----------------------------------------------------------------
def fit_polyline(pts):
    """pts: (n,2) mm. Douglas-Peucker, then snap every segment to 45 deg and
    rebuild the corners as intersections of the snapped lines."""
    ap = cv2.approxPolyDP(pts.astype(np.float32).reshape(-1, 1, 2), 0.12, False).reshape(-1, 2).astype(float)
    if len(ap) < 2: return None
    lines = []
    for a, b in zip(ap[:-1], ap[1:]):
        d = b - a; L = np.hypot(*d)
        if L < 1e-6: continue
        th = round(np.degrees(np.arctan2(d[1], d[0])) / 45) * 45
        u = np.array([np.cos(np.radians(th)), np.sin(np.radians(th))])
        mid = (a + b) / 2
        if lines and lines[-1][1] == th % 360:          # same direction: merge
            m0, _, L0 = lines[-1]
            lines[-1] = ((m0 * L0 + mid * L) / (L0 + L), th % 360, L0 + L); continue
        lines.append((mid, th % 360, L))
    if not lines: return None
    def u(th): return np.array([np.cos(np.radians(th)), np.sin(np.radians(th))])
    def proj(p, ln): m, th, _ = ln; return m + u(th) * np.dot(p - m, u(th))
    out = [proj(ap[0], lines[0])]
    for l1, l2 in zip(lines[:-1], lines[1:]):
        (m1, t1, L1), (m2, t2, L2) = l1, l2
        A = np.c_[u(t1), -u(t2)]
        # the corner is near the original vertex between these two runs;
        # a far-away intersection (nearly parallel lines) is never right
        guess = m1 + u(t1) * L1 / 2
        if abs(np.linalg.det(A)) < 0.2: out.append((m1 + u(t1) * L1 / 2 + m2 - u(t2) * L2 / 2) / 2); continue
        s = np.linalg.solve(A, m2 - m1)
        X = m1 + s[0] * u(t1)
        out.append(X if np.hypot(*(X - guess)) < max(0.5, 0.5 * min(L1, L2)) else guess)
    out.append(proj(ap[-1], lines[-1]))
    out = np.array(out)
    # remove interior jogs shorter than 0.2 mm by extending their neighbours
    changed = True
    while changed and len(out) > 3:
        changed = False
        seg = np.hypot(*np.diff(out, axis=0).T)
        for k in range(1, len(seg) - 1):
            if seg[k] < 0.2:
                a0, a1, b0, b1 = out[k - 1], out[k], out[k + 1], out[k + 2]
                da, db = a1 - a0, b1 - b0
                A = np.c_[da, -db]
                if abs(np.linalg.det(A)) > 1e-9:
                    t = np.linalg.solve(A, b0 - a0)
                    X = a0 + t[0] * da
                    if np.hypot(*(X - a1)) < 0.4:
                        out = np.vstack([out[:k], X, out[k + 2:]]); changed = True; break
    return out

def vectorize_tracks(mask, anchors, chan):
    """mask: track pixels (pads removed). anchors: list of (shape, centre)
    that dangling ends may be pulled onto. Returns [(LineString, width)]."""
    sk = skeletonize(mask)
    if sk.sum() < 3: return []
    skel = Skeleton(sk)
    paths = [skel.path_coordinates(i) for i in range(skel.n_paths)]
    # width = area / length, area by nearest-path assignment
    labimg = np.zeros(mask.shape, np.int32)
    for i, p in enumerate(paths): labimg[p[:, 0].astype(int), p[:, 1].astype(int)] = i + 1
    inv = (labimg == 0).astype(np.uint8)
    _, lab = cv2.distanceTransformWithLabels(inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    # map voronoi seed labels back to path ids
    seed = {}
    ys, xs = np.nonzero(labimg)
    seedlab = lab[ys, xs]
    lut = np.zeros(lab.max() + 1, np.int32); lut[seedlab] = labimg[ys, xs]
    owner = lut[lab]
    area = np.bincount(owner[mask].ravel(), minlength=len(paths) + 1)
    # node degree to tell dangling ends
    deg = np.bincount(np.r_[skel.paths.indices], minlength=skel.n_paths)
    out = []
    nodes = {}
    degs = skel.degrees
    for i, p in enumerate(paths):
        P = np.array([mmw(c[1], c[0]) for c in p])
        L = np.sum(np.hypot(*np.diff(P, axis=0).T))
        if L < 0.25 and len(paths) > 1: continue
        ids = skel.path(i)
        if degs[ids[0]] >= 3 and degs[ids[-1]] >= 3 and L < 0.8:
            continue                       # short rung between two tracks: bridging artefact
        wid = area[i + 1] / S**2 / max(L, 1e-3)
        f = fit_polyline(P)
        if f is None: continue
        out.append([f, snapw(wid), L])
    # join ends that meet (skeleton junctions) and pull dangling ends onto pads
    ends = [(k, e) for k in range(len(out)) for e in (0, -1)]
    pts = np.array([out[k][0][e] for k, e in ends]) if ends else np.zeros((0, 2))
    used = set()
    for a in range(len(ends)):
        if a in used: continue
        grp = [b for b in range(len(ends)) if b not in used and np.hypot(*(pts[b] - pts[a])) < 0.45]
        if len(grp) > 1:
            c = pts[grp].mean(0)
            for b in grp:
                k, e = ends[b]; out[k][0][e] = c; used.add(b)
    for b, (k, e) in enumerate(ends):
        if b in used: continue
        p = Point(out[k][0][e])
        best = None
        for shp, cen in anchors:
            d = shp.distance(p)
            if d < 0.6 and (best is None or d < best[0]): best = (d, shp, cen)
        if best:
            _, shp, cen = best
            q = np.array(cen)
            f = out[k][0]
            prev = f[e + 1] if e == 0 else f[e - 1]
            dvec = f[e] - prev; nrm = np.hypot(*dvec)
            if nrm > 1e-6:
                u = dvec / nrm
                t = np.dot(q - f[e], u)
                cand = f[e] + max(t, 0) * u
                if shp.buffer(0.02).contains(Point(cand)) and np.hypot(*(cand - q)) < 0.6 * np.sqrt(shp.area):
                    f[e] = cand; continue
                hit = LineString([f[e], f[e] + u * 1.0]).intersection(shp)
                if not hit.is_empty:          # aimed at the pad but off-centre: run into it
                    pts = [np.array(c) for g in getattr(hit, 'geoms', [hit]) for c in g.coords]
                    h = min(pts, key=lambda x: np.hypot(*(x - f[e])))
                    f[e] = h + u * 0.15; continue
            if np.hypot(*(f[e] - q)) < 0.35:  # only nudge ends already at the centre
                f[e] = q
    res = []
    for f, w, L in out:
        if len(f) < 2: continue
        ln = LineString(f)
        pw = profile_width(ln, chan)
        res.append((ln, min(snapw(pw), w) if pw else w))
    return res


def mend(lines, anchors, join=2.5, reach=1.2, lat=0.2, minlen=0.4, hidden=None, far=4.0):
    """lines: [(LineString, w)]. Join collinear fragments broken by hidden
    stretches, extend dangling ends to what they point at, drop orphans.
    With a `hidden` mask, joins and extensions may run up to `far` mm when
    the whole bridge lies over hidden pixels (e.g. under silk text)."""
    def hidden_frac(p, q):
        if hidden is None: return 0.0
        n = max(2, int(np.hypot(*(q - p)) / 0.05))
        pts = [pxw(*(p + (q - p) * t)) for t in np.linspace(0.1, 0.9, n)]
        v = [hidden[int(b), int(a)] for a, b in pts if 0 <= int(b) < hidden.shape[0] and 0 <= int(a) < hidden.shape[1]]
        return float(np.mean(v)) if v else 0.0
    from shapely.strtree import STRtree
    L = [[np.array(l.coords), w] for l, w in lines]
    ancg = [a.boundary if a.geom_type != 'Point' else a for a, _ in anchors]
    state = {}
    def rebuild():
        geoms = [LineString(f[0]) if f is not None else Point(1e6, 1e6) for f in L] + ancg
        state['g'] = geoms; state['t'] = STRtree(geoms)
    def end(i, e):
        f = L[i][0]; p = f[0] if e == 0 else f[-1]; q = f[1] if e == 0 else f[-2]
        d = p - q; n = np.hypot(*d); return p, (d / n if n > 1e-9 else d)
    def near(i, geom, dist):
        idx = state['t'].query(geom, predicate='dwithin', distance=dist)
        return [k for k in idx if k != i and (k >= len(L) or L[k] is not None)]
    def dangling(i, e):
        p, _ = end(i, e); return not near(i, Point(p), 0.1)
    for it in range(2):
        rebuild()
        # 1) collinear joins
        ends = [(i, e) for i in range(len(L)) if L[i] is not None for e in (0, -1) if dangling(i, e)]
        epts = np.array([end(i, e)[0] for i, e in ends]) if ends else np.zeros((0, 2))
        used = set()
        for a, (i, e) in enumerate(ends):
            if (i, e) in used or L[i] is None: continue
            p, u = end(i, e); best = None
            lim = far if hidden is not None else join
            cand = np.nonzero(np.hypot(*(epts - p).T) < lim)[0]
            for b in cand:
                j, f = ends[b]
                if j == i or (j, f) in used or L[j] is None: continue
                q, v = end(j, f); d = q - p; t = d @ u
                if 0 < t < lim and abs(d @ np.array([-u[1], u[0]])) < lat and u @ v < -0.9:
                    if t > join and hidden_frac(p, q) < 0.95: continue
                    if best is None or t < best[0]: best = (t, j, f)
            if best:
                _, j, f = best
                A = L[i][0] if e == -1 else L[i][0][::-1]
                Bq = L[j][0] if f == 0 else L[j][0][::-1]
                L[i] = [np.vstack([A, Bq]), max(L[i][1], L[j][1])]; L[j] = None
                used |= {(i, e), (j, f), (i, -1 if e == 0 else 0), (j, -1 if f == 0 else 0)}
        rebuild()
        # 2) extend dangling ends forward
        for i in range(len(L)):
            if L[i] is None: continue
            for e in (0, -1):
                if not dangling(i, e): continue
                p, u = end(i, e)
                r = reach
                if hidden is not None:        # run on under hidden pixels
                    while r < 3.0 and hidden_frac(p, p + u * (r + 0.3)) > 0.85: r += 0.3
                ray = LineString([p + u * 0.02, p + u * r])
                best = None
                for k in near(i, ray, 0.0):
                    hit = ray.intersection(state['g'][k])
                    for g in getattr(hit, 'geoms', [hit]):
                        if g.is_empty: continue
                        q = np.array(g.coords[0]); dd = np.hypot(*(q - p))
                        if best is None or dd < best[0]: best = (dd, q)
                if best:
                    q = best[1]
                    L[i][0] = np.vstack([q, L[i][0]]) if e == 0 else np.vstack([L[i][0], q])
    rebuild()
    out = []
    for i in range(len(L)):
        if L[i] is None: continue
        f = L[i][0]
        # re-snap after the joins: densify, refit, keep ends that moved < 0.15 mm
        ln0 = LineString(f)
        if ln0.length > 0.3:
            dens = np.array([ln0.interpolate(t).coords[0] for t in np.arange(0, ln0.length, 0.05)] + [f[-1]])
            g = fit_polyline(dens)
            if g is not None and len(g) >= 2:
                for e in (0, -1):
                    if np.hypot(*(g[e] - f[e])) < 0.15: g[e] = f[e]
                f = g
        ln = LineString(f)
        if ln.length < minlen and dangling(i, 0) and dangling(i, -1): continue
        out.append((ln, L[i][1]))
    return out


def march(lines, anchors, red, hidden, maxlen=15.0, step=0.05):
    """Run dangling track ends straight on through pixels that are hidden or
    visible top copper. Keep the run up to the last copper pixel passed, or to
    whatever it hits. Then drop fragments that the runs now cover."""
    from shapely.strtree import STRtree
    L = [[np.array(l.coords), w] for l, w in lines]
    ancg = [a for a, _ in anchors]
    def state(pt):
        a, b = pxw(*pt); a, b = int(round(a)), int(round(b))
        if not (0 <= b < red.shape[0] and 0 <= a < red.shape[1]): return 0
        return 2 if red[b, a] else (1 if hidden[b, a] else 0)
    for rnd in range(2):
        geoms = [LineString(f) for f, _ in L] + ancg
        tree = STRtree(geoms)
        for i in range(len(L)):
            for e in (0, -1):
                f = L[i][0]; p = f[0] if e == 0 else f[-1]; q = f[1] if e == 0 else f[-2]
                d = p - q; n = np.hypot(*d)
                if n < 1e-9: continue
                u = d / n
                if [k for k in tree.query(Point(p), predicate='dwithin', distance=0.1) if k != i]: continue
                last_red, t, hit = None, step, None
                while t < maxlen:
                    c = p + u * t; st = state(c)
                    if st == 0: break
                    if st == 2: last_red = t
                    t += step
                ray = LineString([p + u * 0.02, p + u * max(t, 0.05)])
                for k in tree.query(ray, predicate='intersects'):
                    if k == i: continue
                    h = ray.intersection(geoms[k])
                    for g in getattr(h, 'geoms', [h]):
                        if g.is_empty: continue
                        dd = np.hypot(*(np.array(g.coords[0]) - p))
                        if hit is None or dd < hit: hit = dd
                stop = hit if hit is not None else last_red
                if stop is None or stop < 0.1: continue
                newp = p + u * stop
                L[i][0] = np.vstack([newp, f]) if e == 0 else np.vstack([f, newp])
    # drop fragments now covered by a longer track
    lines2 = [(LineString(f), w) for f, w in L]
    order = sorted(range(len(lines2)), key=lambda k: -lines2[k][0].length)
    kept, keptg = [], []
    for k in order:
        ln, w = lines2[k]
        if keptg and any(g.buffer(0.12).contains(ln) for g in keptg if g.distance(ln) < 0.1):
            continue
        kept.append((ln, w)); keptg.append(ln)
    return kept


CLASSES = [12 * MIL, 20 * MIL, 25 * MIL, 40 * MIL]
def width_class(w):
    m = w / MIL
    return CLASSES[0] if m <= 16 else CLASSES[1] if m <= 22.5 else CLASSES[2] if m <= 32 else CLASSES[3]

def even_widths(tracks):
    """Snap widths to the design's classes (measured peaks: 12 and 20 mil,
    a few 25/40), then give runs joined end to end one width (length-
    weighted majority) and short stubs the width of what they join."""
    if not tracks: return tracks
    T = [[l, width_class(w)] for l, w in tracks]
    ends = []
    for i, (l, _) in enumerate(T):
        ends.append((i, np.array(l.coords[0]))); ends.append((i, np.array(l.coords[-1])))
    P = np.array([p for _, p in ends])
    parent = list(range(len(T)))
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for k, (i, p) in enumerate(ends):
        near = [ends[j][0] for j in np.nonzero(np.hypot(*(P - p).T) < 0.15)[0] if ends[j][0] != i]
        near = list(dict.fromkeys(near))
        if len(near) == 1:                      # plain continuation, not a junction
            parent[find(i)] = find(near[0])
    groups = {}
    for i in range(len(T)): groups.setdefault(find(i), []).append(i)
    for g in groups.values():
        votes = {}
        for i in g: votes[T[i][1]] = votes.get(T[i][1], 0) + T[i][0].length
        best = max(votes, key=votes.get)
        for i in g: T[i][1] = best
    # short stubs at junctions: take the widest-voted neighbour's width
    for i, (l, w) in enumerate(T):
        if l.length > 1.2: continue
        nb = [j for j, p in ends if j != i and min(np.hypot(*(p - np.array(l.coords[0]))), np.hypot(*(p - np.array(l.coords[-1])))) < 0.15]
        nb = [j for j in nb if T[j][0].length > 1.2]
        if nb: T[i][1] = max(nb, key=lambda j: T[j][0].length) and T[max(nb, key=lambda j: T[j][0].length)][1]
    return [(l, w) for l, w in T]


def qfp_stubs(hidden):
    """U2 pads whose copper runs on past the inner end to a via under the
    chip (power pins): follow the visible copper from the pad's inner end
    (other pads masked) and link the pad to any via it reaches within 2.5 mm."""
    cx, cy = QFP_C; vias = [(x, y) for x, y, d in holes if d == 0.5]
    red = (cls[sl] == R) | hidden | np.isin(cls[sl], (RING, CORE, BEIGE))
    qs = qfp_shapes()
    out = []
    for kind, g, (x, y) in qs:
        u = np.array([cx - x, cy - y])
        u = np.array([np.sign(u[0]), 0.0]) if abs(u[0]) > abs(u[1]) else np.array([0.0, np.sign(u[1])])
        tip = np.array([x, y]) + u * (QFP_L / 2 + 0.1)
        others = raster([h for _, h, c in qs if c != (x, y)], red.shape, 0.08)
        win = raster([Point(*tip).buffer(2.5)], red.shape)
        m = (red & ~others & win & ~raster([g], red.shape)).astype(np.uint8)
        a_, b_ = pxw(*tip); a_, b_ = int(round(a_)), int(round(b_))
        if not m[b_, a_]: continue
        n, lab = cv2.connectedComponents(m)
        comp = lab == lab[b_, a_]
        tips = [np.array(c) + np.array([np.sign(cx - c[0]), 0.0] if abs(cx - c[0]) > abs(cy - c[1]) else [0.0, np.sign(cy - c[1])]) * (QFP_L / 2 + 0.1) for _, _, c in qs]
        for vx, vy in vias:
            dmine = np.hypot(vx - tip[0], vy - tip[1])
            if dmine > 2.5 or any(np.hypot(vx - t[0], vy - t[1]) < dmine - 1e-6 for t in tips): continue
            va, vb = pxw(vx, vy)
            if 0 <= int(vb) < comp.shape[0] and 0 <= int(va) < comp.shape[1] and \
                    comp[max(0, int(vb) - 6):int(vb) + 7, max(0, int(va) - 6):int(va) + 7].any():
                out.append((LineString([(x, y), tuple(tip), (vx, vy)]), QFP_W * 0.8)); break
    return out


def declutter(tracks, gap=8 * MIL, rounds=4):
    """Tracks on one layer may not overlap unless they meet end to end.
    1) drop tracks lying (>= 90 %) on top of a longer track: duplicates;
    2) push apart parallel segments closer than half-widths + gap: each
       segment's line moves perpendicular, corners are recomputed as
       intersections with the neighbouring segments' lines (angles kept)."""
    T = [[np.array(l.coords, float), w] for l, w in tracks]
    order = sorted(range(len(T)), key=lambda i: -LineString(T[i][0]).length)
    keep = []
    for i in order:
        ln = LineString(T[i][0])
        cover = unary_union([LineString(T[j][0]).buffer(0.12) for j in keep
                             if LineString(T[j][0]).distance(ln) < 0.12]) if keep else None
        if cover is not None and not cover.is_empty and ln.intersection(cover).length > 0.9 * ln.length:
            continue
        keep.append(i)
    T = [T[i] for i in sorted(keep)]
    def unit(a, b):
        d = b - a; n = np.hypot(*d); return d / n if n > 1e-9 else d
    for r in range(rounds):
        segs = []
        for ti, (f, w) in enumerate(T):
            for k in range(len(f) - 1):
                if np.hypot(*(f[k + 1] - f[k])) > 0.15: segs.append((ti, k))
        shift = defaultdict(lambda: np.zeros(2))
        moved = 0
        for a in range(len(segs)):
            ta, ka = segs[a]; fa, wa = T[ta]; A0, A1 = fa[ka], fa[ka + 1]; ua = unit(A0, A1)
            na = np.array([-ua[1], ua[0]])
            for b in range(a + 1, len(segs)):
                tb, kb = segs[b]
                if tb == ta: continue
                fb, wb = T[tb]; B0, B1 = fb[kb], fb[kb + 1]; ub = unit(B0, B1)
                if abs(abs(ua @ ub) - 1) > 1e-3: continue          # not parallel
                d = (B0 - A0) @ na
                need = (wa + wb) / 2 + gap
                if abs(d) >= need or abs(d) < 0.02: continue
                ta0, ta1 = sorted([0, (A1 - A0) @ ua]); tb0, tb1 = sorted([(B0 - A0) @ ua, (B1 - A0) @ ua])
                if min(ta1, tb1) - max(ta0, tb0) < 0.2: continue   # no side-by-side overlap
                push = (need - abs(d)) / 2 * np.sign(d)
                shift[(ta, ka)] -= na * push; shift[(tb, kb)] += na * push
                moved += 1
        if not moved: break
        for ti, (f, w) in enumerate(T):
            lines = []
            for k in range(len(f) - 1):
                off = shift.get((ti, k), np.zeros(2))
                lines.append((f[k] + off, unit(f[k], f[k + 1])))
            if not lines: continue
            new = [f[0] + shift.get((ti, 0), np.zeros(2))]
            for k in range(1, len(f) - 1):
                (p1, u1), (p2, u2) = lines[k - 1], lines[k]
                A = np.c_[u1, -u2]
                avg = f[k] + (shift.get((ti, k - 1), np.zeros(2)) + shift.get((ti, k), np.zeros(2))) / 2
                if abs(np.linalg.det(A)) < 0.2: new.append(avg)
                else:
                    t = np.linalg.solve(A, p2 - p1); X = p1 + t[0] * u1
                    new.append(X if np.hypot(*(X - avg)) < 0.5 else avg)
            new.append(f[-1] + shift.get((ti, len(f) - 2), np.zeros(2)))
            T[ti][0] = np.array(new)
    return [(LineString(f), w) for f, w in T]

EXTRA = {}
# ---- per-layer build ------------------------------------------------------
def build_top():
    T = TOP[sl].copy()
    known = th_pad_shapes() + qfp_shapes()
    kmask = raster([g for _, g, _ in known], T.shape, 0.06)
    # silk outlines often run over the gap between neighbouring pads: fit pads
    # on visible copper only, then take pours from what the pads don't explain
    vis = T & (cls[sl] != G)
    pads, _ = fit_pads(vis, kmask)
    rest = T & ~raster([g for _, g, _ in pads], T.shape, 0.3)
    _, pours = fit_pads(rest, kmask)
    # copper joining neighbouring pads (often under a silk line) -> rectangles
    padr = [raster([g], T.shape, 0.12) for _, g, _ in pads]
    link = T & ~raster([g for _, g, _ in pads], T.shape) & ~pours & ~kmask
    link = cv2.morphologyEx(link.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(link)
    links = []
    for i in range(1, n):
        comp = lab == i
        if st[i, 4] < 0.04 * S * S: continue
        if sum(1 for r in padr if (r & comp).any()) < 2: continue
        ys, xs = np.nonzero(comp)
        (cx, cy), (w, h), ang = cv2.minAreaRect(np.c_[xs, ys].astype(np.float32))
        if min(w, h) / S > 1.2 or len(xs) < 0.6 * w * h: continue     # a track, not a link
        a45 = round(ang / 45) * 45
        X, Y = mmw(cx, cy)
        r = affinity.rotate(box(-(w + 2) / S / 2, -(h + 2) / S / 2, (w + 2) / S / 2, (h + 2) / S / 2), -a45, origin=(0, 0))
        links.append(affinity.translate(r, X, Y))
    print('pad-to-pad links: %d' % len(links))
    allpads = known + pads
    pmask = raster([g for _, g, _ in allpads], T.shape, 0.15)
    # silk hides the top layer: use only what is visible, then join across it
    silk = cv2.dilate((cls[sl] == G).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    tr = T & ~pmask & ~silk & ~cv2.dilate(pours.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    tr = cv2.morphologyEx(tr.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    tracks = vectorize_tracks(tr, [(g, c) for _, g, c in allpads], REDNESS)
    hid = silk | (T & ~(cls[sl] == R) & ~pmask)
    tracks = mend(tracks, [(g, c) for _, g, c in allpads], join=1.5, reach=0.8, minlen=0.3, hidden=hid)
    tracks = march(tracks, [(g, c) for _, g, c in allpads], (cls[sl] == R) & ~pmask, hid)
    tracks = [(l, w) for l, w in tracks if l.length >= 0.6]
    tracks = even_widths(tracks)
    n0 = len(tracks)
    tracks = declutter(tracks)
    print('top declutter: %d -> %d tracks' % (n0, len(tracks)))
    stubs = qfp_stubs(hid)
    print('U2 pad-to-via stubs: %d' % len(stubs))
    tracks += stubs
    tpours = pour_polys(pours) if pours.any() else Polygon()
    if not tpours.is_empty:
        tpours = tpours.buffer(-0.1).buffer(0.1)
    EXTRA['links'] = links; EXTRA['tpours'] = tpours
    geoms = [g for _, g, _ in allpads] + [l.buffer(w / 2, 16) for l, w in tracks] + [tpours] + links
    return unary_union(geoms), tracks, allpads

def pour_polys(comp):
    """Outline of a pour component, simplified and snapped to 45 deg."""
    m = comp.astype(np.uint8)
    cs, hi = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = []
    for i, c in enumerate(cs):
        if hi[0][i][3] != -1 or cv2.contourArea(c) < 0.5 * S * S: continue
        def ring(cc):
            P = np.array([mmw(q[0][0], q[0][1]) for q in cc] + [mmw(cc[0][0][0], cc[0][0][1])])
            f = fit_polyline(P)
            return f if f is not None and len(f) >= 4 else None
        ext = ring(c)
        if ext is None: continue
        holes_, k = [], hi[0][i][2]
        while k != -1:
            if cv2.contourArea(cs[k]) > 0.3 * S * S:
                h = ring(cs[k])
                if h is not None: holes_.append(h)
            k = hi[0][k][0]
        p = Polygon(ext, holes_).buffer(0)
        if not p.is_empty: polys.append(p)
    return unary_union(polys)

def build_bottom(clear):
    B = BOT[sl].copy()
    known = th_pad_shapes()
    kmask = raster([g for _, g, _ in known], B.shape, 0.06)
    body = B & ~kmask
    # pour = what survives an opening wider than any track; thin copper is
    # a track (even if a bridging error glued it to the pour)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.1 * S) | 1, int(1.1 * S) | 1))
    core = cv2.morphologyEx(body.astype(np.uint8), cv2.MORPH_OPEN, k).astype(bool)
    n, lab = cv2.connectedComponents(core.astype(np.uint8))
    big = [i for i in range(1, n) if (lab == i).sum() > 3 * S * S]
    core = np.isin(lab, big)
    pour_mask = body & cv2.dilate(core.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    trk_mask = body & ~cv2.dilate(pour_mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(trk_mask.astype(np.uint8))
    trk_mask = np.isin(lab, [i for i in range(1, n) if st[i, 4] > 0.15 * S * S])
    tracks = vectorize_tracks(trk_mask, [(g, c) for _, g, c in known], NAVYNESS)
    # an object is on the pour's net if the pour reaches it (no white ring)
    near = lambda g: raster([g.buffer(clear * 0.6)], B.shape) & ~raster([g.buffer(0.08)], B.shape)
    own, other = [], []
    for kind, g, cc in known:
        r = near(g); frac = pour_mask[r].mean() if r.any() else 0
        (own if frac > 0.5 else other).append(g)
    tr_own, tr_other = [], []
    for l, w in tracks:
        g = l.buffer(w / 2, 16)
        r = near(g); frac = pour_mask[r].mean() if r.any() else 0
        (tr_own if frac > 0.35 else tr_other).append(g)
    obj = other + tr_other
    # outline: pour plus the clearance zones around foreign objects, closed
    objmask = raster(obj, B.shape, clear + 0.2) if obj else np.zeros_like(B)
    filled = pour_mask | (objmask & cv2.dilate(pour_mask.astype(np.uint8), np.ones((int(clear * S) * 2 + 5,) * 2, np.uint8)).astype(bool))
    filled |= raster(own + tr_own, B.shape, 0.1)
    filled = cv2.morphologyEx(filled.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats((~filled).astype(np.uint8))
    filled |= np.isin(lab, [i for i in range(1, n) if st[i, 4] < 0.6 * S * S])   # tiny voids
    outline = pour_polys(filled)
    pour = outline.difference(unary_union([o.buffer(clear, 16) for o in obj])) if obj else outline
    pour = pour.buffer(-0.12).buffer(0.12)
    pour = unary_union([p for p in getattr(pour, 'geoms', [pour]) if p.area > 0.3])
    geoms = [pour] + [g for _, g, _ in known] + [l.buffer(w / 2, 16) for l, w in tracks]
    return unary_union(geoms), tracks

def build_bottom_negative(clear):
    """Bottom copper in two regimes. Large open (white) regions such as the
    lamp area hold ordinary tracks, vectorised directly. Everywhere else the
    copper is a pour: board minus its gaps -- thin white lines of one width
    (45-degree strokes) and rings round pads not on the pour's net. Areas the
    image hides are assumed to be pour; pads there get an isolating ring."""
    B = BOT[sl]; U = z['unres_b'][sl]
    known = th_pad_shapes()
    padm = raster([g for _, g, _ in known], B.shape, 0.04)
    gap = ~B & ~padm & ~U
    seen = ~U
    # open regions: big white areas, closed over 3 mm so the tracks and pads
    # inside them belong to them (but never across solid pour)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.9 * S) | 1, int(0.9 * S) | 1))
    opened = cv2.morphologyEx(gap.astype(np.uint8), cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(opened)
    openm = np.isin(lab, [i for i in range(1, n) if st[i, 4] > 1.0 * S * S]).astype(np.uint8)
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(3.0 * S) | 1, int(3.0 * S) | 1))
    k15 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.5 * S) | 1, int(1.5 * S) | 1))
    solid = cv2.morphologyEx(((B | U) & ~padm).astype(np.uint8), cv2.MORPH_OPEN, k15).astype(bool)
    openc = (cv2.morphologyEx(openm, cv2.MORPH_CLOSE, k3).astype(bool) & ~solid) | openm.astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(openc.astype(np.uint8))
    big = np.isin(lab, [i for i in range(1, n) if st[i, 4] > 10 * S * S])
    areas = pour_polys(cv2.dilate(openc.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool))
    aream = raster([areas], B.shape, 0.05) if not areas.is_empty else np.zeros_like(B)
    rings = []
    for kind, g, cc in known:
        if areas.contains(g.centroid): continue
        ann = raster([g.buffer(clear * 0.8)], B.shape) & ~raster([g.buffer(0.1)], B.shape)
        if not ann.any(): continue
        vis = ann & seen
        if vis.sum() < 0.4 * ann.sum() or gap[vis].mean() > 0.5:
            rings.append(g.buffer(clear, 32))
    ringm = raster(rings, B.shape, 0.05) if rings else np.zeros_like(B)
    thin = gap & ~aream & ~ringm
    thin = cv2.morphologyEx(thin.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(thin.astype(np.uint8))
    thin = np.isin(lab, [i for i in range(1, n) if st[i, 4] > 0.08 * S * S])
    anchors = [(r, r.centroid.coords[0]) for r in rings]
    for a in list(getattr(areas, 'geoms', [areas])):
        if not a.is_empty: anchors.append((a, a.representative_point().coords[0]))
    strokes = vectorize_tracks(thin, anchors, WHITENESS)
    strokes = mend(strokes, anchors)
    widths = sorted(w for _, w in strokes)
    sw = widths[len(widths) // 2] if widths else clear
    print('gap strokes: %d, median width %.3f mm' % (len(strokes), sw))
    cut = [l.buffer(sw / 2, 16) for l, _ in strokes] + rings + [areas]
    cu = box(0, 0, BW, BH).difference(unary_union(cut))
    cu = cu.buffer(-0.1).buffer(0.1)
    cu = unary_union([p for p in getattr(cu, 'geoms', [cu]) if p.area > 0.3])
    # tracks in the open regions, as copper
    inner = raster([areas.buffer(-0.1)], B.shape) if not areas.is_empty else np.zeros_like(B)
    tm = B & inner & ~raster([g for _, g, _ in known], B.shape, 0.15)
    tm = cv2.morphologyEx(tm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    anc2 = [(g, c) for _, g, c in known] + [(p, p.representative_point().coords[0]) for p in getattr(cu, 'geoms', [cu])]
    tracks = vectorize_tracks(tm, anc2, NAVYNESS)
    tracks = mend(tracks, anc2, join=2.0, reach=0.8, minlen=0.6)
    tracks = declutter(even_widths(tracks))
    print('bottom tracks in open regions: %d' % len(tracks))
    return unary_union([cu] + [g for _, g, _ in known] + [l.buffer(w / 2, 16) for l, w in tracks]), strokes

def measure_clearance():
    """Gap between the bottom pour and bottom tracks, from visible pixels."""
    B = BOT[sl]; vis = np.isin(cls[sl], (W, N))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.1 * S) | 1, int(1.1 * S) | 1))
    fat = cv2.morphologyEx(B.astype(np.uint8), cv2.MORPH_OPEN, k).astype(bool)
    n, lab = cv2.connectedComponents(B.astype(np.uint8))
    ids = [i for i in np.unique(lab[fat]) if i and (lab == i).sum() > 20 * S * S]
    pour = np.isin(lab, ids)
    other = B & ~pour
    d = cv2.distanceTransform((~pour).astype(np.uint8), cv2.DIST_L2, 5)
    edge = other & ~cv2.erode(other.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & vis
    v = d[edge] / S
    v = v[(v > 0.1) & (v < 0.6)]
    return float(np.median(v)) if len(v) else 0.3

# ---- gerber ---------------------------------------------------------------
def c(v): return int(round(v * 1e6))
def write_regions(path, func, geom):
    s = ("G04 #@! TF.GenerationSoftware,vectorize*\nG04 #@! TF.FileFunction,%s*\n"
         "G04 #@! TF.FilePolarity,Positive*\n%%FSLAX46Y46*%%\n%%MOMM*%%\n%%ADD10C,0.100000*%%\nG01*\n" % func)
    polys = sorted(getattr(geom, 'geoms', [geom]), key=lambda p: -p.area)
    def ring(r, dark):
        pts = list(r.coords)
        t = '%%LP%s*%%\nG36*\nX%dY%dD02*\n' % ('D' if dark else 'C', c(pts[0][0]), c(pts[0][1]))
        for p in pts[1:]: t += 'X%dY%dD01*\n' % (c(p[0]), c(p[1]))
        return t + 'G37*\n'
    for p in polys:
        if p.is_empty or p.geom_type != 'Polygon': continue
        s += ring(p.exterior, True)
        for h in p.interiors: s += ring(h, False)
    s += '%LPD*%\nD10*\n'
    x0, y0, x1, y1 = CLIP.bounds          # region frame so renders share a bbox
    for x, y, d in [(x0, y0, 2), (x1, y0, 1), (x1, y1, 1), (x0, y1, 1), (x0, y0, 1)]:
        s += 'X%dY%dD0%d*\n' % (c(x), c(y), d) if False else ''
    open(path, 'w').write(s + 'M02*\n')

NPTH = []
with open(os.path.join(HERE, 'holes.csv')) as f:
    for row in csv.DictReader(f):
        if row['measured_mm'] == 'NPTH': NPTH.append((float(row['x_mm']), float(row['y_mm']), float(row['drill_mm'])))

if __name__ == '__main__':
    import shutil
    whole = len(sys.argv) < 5
    out = os.path.join(ROOT, 'vector'); os.makedirs(out, exist_ok=True)
    clear = measure_clearance()
    print('bottom pour clearance measured %.3f mm' % clear)
    clear = min([8 * MIL, 10 * MIL, 12 * MIL, 15 * MIL, 20 * MIL], key=lambda t: abs(t - clear))
    top, ttr, pads = build_top()
    bot, btr = build_bottom_negative(clear)
    raw = {'top': top, 'bot': bot, 'pads': [(k, g, c) for k, g, c in pads], 'ttr': ttr, 'btr': btr, **EXTRA}
    fx = os.path.join(HERE, 'fixes.json')
    if whole and os.path.exists(fx):
        # bridges from repair.py, each as wide as the track it continues
        import json
        add = {'T': [], 'B': []}
        tr_by = {'T': ttr, 'B': [t for t in btr]}
        for b in json.load(open(fx))['bridges']:
            ln = LineString([b['from'], b['to']])
            near = [(l.distance(Point(b['from'])), w) for l, w in tr_by[b['layer']] if l.distance(ln) < 0.3]
            w = min(near)[1] if near and b['layer'] == 'T' else b['width']
            add[b['layer']].append(ln.buffer(w / 2, 16))
        top = unary_union([top] + add['T']); bot = unary_union([bot] + add['B'])
        print('fixes applied: %d top, %d bottom bridges' % (len(add['T']), len(add['B'])))
    keep = unary_union([Point(x, y).buffer(d / 2 + 0.2, 32) for x, y, d in NPTH])
    top, bot = top.difference(keep), bot.difference(keep)
    print('clearance used %.3f; top: %d tracks, %d pads; bottom: %d gap strokes' % (clear, len(ttr), len(pads), len(btr)))
    from collections import Counter
    print('top widths (mil)', sorted(Counter(round(w / MIL) for _, w in ttr).items()))
    P = 'electroNIX3a-' if whole else ''
    write_regions(os.path.join(out, P + 'F_Cu.gtl'), 'Copper,L1,Top', top.intersection(CLIP))
    write_regions(os.path.join(out, P + 'B_Cu.gbl'), 'Copper,L2,Bot', bot.intersection(CLIP))
    # mask: every pad +0.05 mm; vias tented
    mtop = unary_union([g.buffer(0.05, 16) for k, g, _ in pads if k != 'via'])
    mbot = unary_union([g.buffer(0.05, 16) for k, g, _ in pads if k == 'th'])
    write_regions(os.path.join(out, P + 'F_Mask.gts'), 'Soldermask,Top', mtop.intersection(CLIP))
    write_regions(os.path.join(out, P + 'B_Mask.gbs'), 'Soldermask,Bot', mbot.intersection(CLIP))
    if whole:
        g = os.path.join(ROOT, 'gerbers')
        for n in ('Edge_Cuts.gm1', 'PTH.drl', 'NPTH.drl'):
            shutil.copy(os.path.join(g, 'electroNIX3a-' + n), os.path.join(out, 'electroNIX3a-' + n))
    if whole:
        import pickle             # geometry for netcheck.py (not committed)
        with open(os.path.join(HERE, 'vector_geom.pkl'), 'wb') as f:
            pickle.dump(raw, f)                 # before fixes: input to repair.py
        with open(os.path.join(HERE, 'vector_geom_fixed.pkl'), 'wb') as f:
            pickle.dump(dict(raw, top=top, bot=bot), f)
        sys.exit(0)
    with open(os.path.join(out, 'frame.gm1'), 'w') as f:
        f.write('%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.050000*%\nD10*\n')
        x0, y0, x1, y1 = CLIP.bounds
        for x, y, d in [(x0, y0, 2), (x1, y0, 1), (x1, y1, 1), (x0, y1, 1), (x0, y0, 1)]:
            f.write('X%dY%dD0%d*\n' % (c(x), c(y), d))
        f.write('M02*\n')
