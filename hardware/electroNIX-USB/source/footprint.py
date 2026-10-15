#!/usr/bin/env python3
"""Write the project footprints into electronix.pretty/.

Nixie_RFT_Z573M          tube leads (or socket pins) directly on the tube's
                         9.53 mm lead circle. Tight: 2.12 mm pitch.
Nixie_RFT_Z573M_Adapter  socket pins on the 12.6 mm outer ring of the
                         electroNIX-2 Z573M socket adapter (radial fan-out of
                         the same 13 positions, 2.80 mm pitch). Default.
Neon_P2.54mm             2-lead neon lamp, 0.1" pitch.

Z573M (RFT data book p.103): 13 leads in 14 equal positions (25.71 deg), the
gap opposite wire 7, wire 7 at the front. The data book draws the base from
below with the leads numbered clockwise; a footprint is a top view, so they
run counter-clockwise here. Wire 7 points to +Y = the front edge of the board.

Socket pins (user's part): body 1.48 mm, collar 1.82 mm -> 1.55 mm finished
hole.
"""
import math, os, sys, uuid

STEP = 360 / 14

def u(*k): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'electronix/' + '/'.join(map(str, k))))

def pin_xy(k, r):
    phi = math.radians(90 + k * STEP)
    return round(r * math.cos(phi), 4), round(-r * math.sin(phi), 4), (90 + k * STEP)

def head(name, descr, tags):
    return [f'(footprint "{name}" (version 20221018) (generator pcbnew)',
            '  (layer "F.Cu")', f'  (descr "{descr}")', f'  (tags "{tags}")', '  (attr through_hole)']

def text(kind, s, x, y, layer, size=1.0, tag=''):
    return (f'  (fp_text {kind} "{s}" (at {x} {y}) (layer "{layer}") '
            f'(effects (font (size {size} {size}) (thickness {round(size * 0.15, 3)}))) (tstamp {u(tag or s, x, y)}))')

def circle(r, layer, w, tag):
    return (f'  (fp_circle (center 0 0) (end {r} 0) (stroke (width {w}) (type solid)) (fill none) '
            f'(layer "{layer}") (tstamp {u(tag)}))')

def line(x1, y1, x2, y2, layer, w, tag):
    return (f'  (fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) '
            f'(layer "{layer}") (tstamp {u(tag)}))')

def tube(name, r, drill, pad, oval=None, anode_clear=None, descr=''):
    L = head(name, descr, 'nixie RFT Z573M Z5730M')
    L += [text('reference', 'REF**', 0, -11.5, 'F.SilkS', tag=name + 'ref'),
          text('value', name, 0, 11.5, 'F.Fab', tag=name + 'val'),
          text('user', 'FRONT', 0, 8.4, 'F.SilkS', 0.8, name + 'front'),
          text('user', '${REFERENCE}', 0, 0, 'F.Fab', tag=name + 'fabref'),
          circle(9.5, 'F.SilkS', 0.12, name + 'silk'), circle(9.5, 'F.Fab', 0.1, name + 'fab'),
          circle(10.0, 'F.CrtYd', 0.05, name + 'crt'),
          line(-2, 9.9, 2, 9.9, 'F.SilkS', 0.2, name + 'fl')]
    for k in range(1, 14):
        x, y, ang = pin_xy(k, r)
        if oval:
            # long axis radial; KiCad pad angle is CCW-positive in the y-down frame
            shape, size, rot = 'oval', f'{oval[0]} {oval[1]}', f' {round(ang % 180, 2)}'
        else:
            shape, size, rot = ('rect' if k == 1 else 'circle'), f'{pad} {pad}', ''
        if k == 1 and oval: shape = 'roundrect'
        extra = ' (roundrect_rratio 0.25)' if shape == 'roundrect' else ''
        cl = f' (clearance {anode_clear})' if (anode_clear and k == 13) else ''
        L.append(f'  (pad "{k}" thru_hole {shape} (at {x} {y}{rot}) (size {size}) (drill {drill}) '
                 f'(layers "*.Cu" "*.Mask"){extra}{cl} (tstamp {u(name, "pad", k)}))')
    L.append(')')
    return '\n'.join(L) + '\n'

def neon():
    name = 'Neon_P2.54mm'
    L = head(name, 'Neon indicator lamp (NE-2 / INS-1 style), 2 leads, 2.54 mm pitch', 'neon lamp NE-2 INS-1')
    L += [text('reference', 'REF**', 0, -2.3, 'F.SilkS', 0.8, name + 'ref'),
          text('value', name, 0, 2.4, 'F.Fab', 0.8, name + 'val'),
          f'  (fp_rect (start -2.3 -1.35) (end 2.3 1.35) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS") (tstamp {u(name, "silk")}))',
          f'  (fp_rect (start -2.55 -1.6) (end 2.55 1.6) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd") (tstamp {u(name, "crt")}))']
    for k, x in ((1, -1.27), (2, 1.27)):
        L.append(f'  (pad "{k}" thru_hole {"rect" if k == 1 else "circle"} (at {x} 0) (size 1.5 1.5) (drill 0.8) '
                 f'(layers "*.Cu" "*.Mask") (tstamp {u(name, "pad", k)}))')
    L.append(')')
    return '\n'.join(L) + '\n'

def cp_lying():
    """Radial electrolytic folded flat onto the board: leads 2.5 mm apart,
    body (up to 8 mm dia x 12.5 mm) lying along +Y from 1.5 mm past the pads."""
    name = 'CP_Radial_D8mm_P2.50mm_Lying'
    bx0, bx1, by0, by1 = 1.25 - 4.0, 1.25 + 4.0, 1.5, 14.0
    L = head(name, 'Radial electrolytic, 2.5 mm pitch, bent over to lie flat (body up to 8 x 12.5 mm along +Y)',
             'capacitor electrolytic radial horizontal lying')
    L += [text('reference', 'REF**', 1.25, -2.2, 'F.SilkS', 0.8, name + 'ref'),
          text('value', name, 1.25, 8.0, 'F.Fab', 0.8, name + 'val'),
          text('user', '+', -1.6, 0, 'F.SilkS', 1.0, name + 'plus'),
          f'  (fp_rect (start {bx0} {by0}) (end {bx1} {by1}) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS") (tstamp {u(name, "silk")}))',
          f'  (fp_rect (start {bx0} {by0}) (end {bx1} {by1}) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab") (tstamp {u(name, "fab")}))',
          line(0, 0.8, 0, by0, 'F.Fab', 0.1, name + 'l1'), line(2.5, 0.8, 2.5, by0, 'F.Fab', 0.1, name + 'l2'),
          f'  (fp_rect (start {bx0 - 0.25} -1.1) (end {bx1 + 0.25} {by1 + 0.25}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd") (tstamp {u(name, "crt")}))']
    for k, x in ((1, 0.0), (2, 2.5)):
        L.append(f'  (pad "{k}" thru_hole {"rect" if k == 1 else "circle"} (at {x} 0) (size 1.6 1.6) (drill 0.8) '
                 f'(layers "*.Cu" "*.Mask") (tstamp {u(name, "pad", k)}))')
    L.append(')')
    return '\n'.join(L) + '\n'

def main(out):
    os.makedirs(out, exist_ok=True)
    fps = {
        'Nixie_RFT_Z573M': tube('Nixie_RFT_Z573M', 9.53 / 2, 1.55, None, oval=(2.3, 1.8), anode_clear=0.25,
            descr='RFT Z573M side-view nixie, socket pins directly on the 9.53 mm lead circle (2.12 mm pitch, '
                  '~0.3 mm pad gap - tight). Wire 7 at front (+Y). Top view.'),
        'Nixie_RFT_Z573M_Adapter': tube('Nixie_RFT_Z573M_Adapter', 6.30, 1.55, 2.25,
            descr='RFT Z573M on the electroNIX-2 socket adapter: socket pins on the adapter outer ring, '
                  '12.6 mm circle, 2.80 mm pitch, same 13 positions as the tube. Wire 7 at front (+Y). Top view.'),
        'Neon_P2.54mm': neon(),
        'CP_Radial_D8mm_P2.50mm_Lying': cp_lying(),
    }
    for n, s in fps.items():
        open(os.path.join(out, n + '.kicad_mod'), 'w').write(s)

if __name__ == '__main__':
    main(sys.argv[1])
