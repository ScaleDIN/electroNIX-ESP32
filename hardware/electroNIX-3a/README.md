# electroNIX-3a PCB — Gerbers traced from a layout JPEG

The only sources for this board are one composite top-view JPEG of the
layout (`source/electroNIX-3a_layout.jpg`, 1200×638, both copper layers
and silk overlaid) and the schematic (`source/electroNIX-3a_schematic.pdf`,
"electroNIXclock 3v1", 2013-11-27). `source/jpg2gerber.py` traces the JPEG.
**This is a work in progress, not fabrication-ready yet** — see "Status".

Board: 92.0 × 56.0 mm, 2 layers. Units mm.

## How the image is read

The JPEG uses seven colours; everything else is anti-aliasing between two of
them, and each pixel is classified as a pure colour or a two-colour blend
(labelled by the nearer end):

| Colour | Meaning |
|---|---|
| white | bare board |
| navy | bottom copper (only where nothing covers it) |
| red | top copper |
| green | silkscreen |
| dark steel | through-hole pad / via annulus |
| light steel | component hole (the drill, drawn to size) |
| beige | via hole |

## Scale and drills — cross-checked

- **Scale 8.375 px/mm**, from U2 (TQFP-44): its 11 pads per side span
  67.0 px on all four sides = 10 × 0.8 mm. The 92 × 56 mm outline gives
  8.380 / 8.375 px/mm, and the rendered copper correlates best with the
  image at ≤ 0.5 px (0.06 mm) offset.
- **Lamp footprint vs the socket adapter** (`../electroNIX-2`): the 11 pads
  of each lamp fit a circle of R = 6.310 mm (max error 0.024 mm) on a
  25.7° (360/14) pitch; the adapter's 1.7 mm pins sit on R = 6.299 mm at
  the same pitch.
- **Drills are measured**, not guessed: the light hole core of each pad was
  measured (50 % edge of averaged radial profiles) and snapped to the tool
  set the same vendor used on electroNIX-2:

  | Pads | Measured | Drill | Count |
  |---|---|---|---|
  | Lamp sockets, 5 mm pad pair by C2 | 1.65–1.72 | 1.7 | 46 |
  | Tact switches (6×6, 4.5 × 6.5 mm) | 1.18–1.21 | 1.3 | 12 |
  | JP1, N1, D20, figure-8 pads (C1 and by C8) | 0.87–0.99 | 1.0 | 18 |
  | Vias | ≈ 0.5 | 0.5 | 80 |
  | Mounting holes (NPTH, 0.2 mm copper keep-out) | ≈ 3.45 | 3.5 | 4 |

  Per-hole values are in `source/holes.csv`.
- **U2** pads are placed from the measured land pattern: 0.8 mm pitch,
  2.03 × 0.5 mm pads, rows 11.46 mm apart.

## Status

1. **Done — bottom copper under thin top-layer features.** Where a red track,
   SMD pad or silk line hides the bottom layer, each hidden pixel looks
   along 8 directions for visible board on both sides, takes the shortest
   crossing (straight across the covering track) and continues whatever is
   on the nearer side — pour, clearance line or bottom track. Crossings up to
   2.0 mm wide are bridged this way, then smoothed and de-speckled
   (< 0.04 mm² copper / < 0.06 mm² gaps).
2. **Open — wide hidden areas (≈ 240 mm²)**, orange in
   `preview/unresolved_bottom.jpg`: the L2/Q20 power pour, the D12–D17 /
   C3–C9 diode-cap row, the D18/C11 corner, and the silk "serial" box. Bottom
   copper there is currently **left empty**. Next step: extract the netlist
   from the schematic PDF and fill these so the board matches it.
3. **Open — netlist check** of the whole board against the schematic. (The
   schematic is v3.1 dated 2013-11-27; the board silk says 23.09.2013, so
   small revision differences are possible.)

## Other limits

- Edges are good to about ±0.1 mm (the JPEG is 0.12 mm/px).
- Solder mask: TH pads +0.05 mm on both sides, U2 from its footprint, other
  top SMD pads from compact red shapes. Vias are tented. There are no bottom
  SMD parts visible.
- No paste layer, no bottom silk. The outline is a plain rectangle.
- The figure-8 pads (two 1.0 mm holes in one obround pad, likely alternative
  lead spacings) are drawn as two holes; check them against the parts.

`source/layers.npz` holds the classified image and both copper layers at
16.75 px/mm for the next step.
