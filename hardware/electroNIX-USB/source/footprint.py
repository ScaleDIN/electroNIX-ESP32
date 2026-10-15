#!/usr/bin/env python3
"""Write electronix.pretty/Nixie_RFT_Z573M.kicad_mod.

RFT Z573M (data book p.103): 13 flying leads on a 9.53 mm circle, 14
equal positions with the gap opposite wire 7, wire 7 at the front, bulb
19 mm. The data book draws the leads seen from below, numbered clockwise.
A footprint is seen from above, so here they run counter-clockwise. Wire 7
points to +Y (the front edge of the board, toward the viewer).
"""
import math, os, sys, uuid

R = 9.53 / 2
STEP = 360 / 14
DRILL, PAD = 0.8, 1.35          # leads are ~0.45 mm wire
NAME = 'Nixie_RFT_Z573M'

def u(*k): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'electronix/' + '/'.join(map(str, k))))

def pin_xy(k):
    phi = math.radians(90 + k * STEP)       # see derivation in README
    return round(R * math.cos(phi), 4), round(-R * math.sin(phi), 4)

def main(out):
    os.makedirs(out, exist_ok=True)
    L = [f'(footprint "{NAME}" (version 20221018) (generator pcbnew)',
         '  (layer "F.Cu")',
         '  (descr "RFT Z573M / Z5730M side-view nixie, 13 flying leads on 9.53 mm circle, wire 7 at front (+Y). Top view.")',
         '  (tags "nixie RFT Z573M Z5730M")',
         '  (attr through_hole)',
         f'  (fp_text reference "REF**" (at 0 -11.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))) (tstamp {u("ref")}))',
         f'  (fp_text value "{NAME}" (at 0 11.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))) (tstamp {u("val")}))',
         f'  (fp_text user "FRONT" (at 0 8.3) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {u("front")}))',
         f'  (fp_text user "${{REFERENCE}}" (at 0 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))) (tstamp {u("fabref")}))',
         f'  (fp_circle (center 0 0) (end 9.5 0) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS") (tstamp {u("silk")}))',
         f'  (fp_circle (center 0 0) (end 9.5 0) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab") (tstamp {u("fab")}))',
         f'  (fp_circle (center 0 0) (end 10 0) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd") (tstamp {u("crt")}))',
         # front marker: short line at the front edge of the bulb
         f'  (fp_line (start -2 9.9) (end 2 9.9) (stroke (width 0.2) (type solid)) (layer "F.SilkS") (tstamp {u("fl")}))']
    for k in range(1, 14):
        x, y = pin_xy(k)
        shape = 'rect' if k == 1 else 'circle'
        L.append(f'  (pad "{k}" thru_hole {shape} (at {x} {y}) (size {PAD} {PAD}) (drill {DRILL}) '
                 f'(layers "*.Cu" "*.Mask") (tstamp {u("pad", k)}))')
    L.append(')')
    open(os.path.join(out, NAME + '.kicad_mod'), 'w').write('\n'.join(L) + '\n')

if __name__ == '__main__':
    main(sys.argv[1])
