# electroNIX-3a PCB — Gerbers traced from a layout JPEG

The only sources for this board are one composite top-view JPEG of the
layout (`source/electroNIX-3a_layout.jpg`, 1200×638, both copper layers
and silk overlaid) and the schematic (`source/electroNIX-3a_schematic.pdf`,
"electroNIXclock 3v1", 2013-11-27). **Use `vector/`** — the copper rebuilt as CAD primitives
(`source/vectorize.py`). `gerbers/` is the earlier pixel trace
(`source/jpg2gerber.py`) that the rebuild starts from. **Neither is
fabrication-ready yet** — see "Status". No silkscreen is produced (not
wanted).

## Vector rebuild (`vector/`)

Pixel tracing a 0.12 mm/px JPEG gives ragged edges, so `vectorize.py` fits
what the Altium original was made of instead:

- **Tracks**: skeleton centrelines → straight runs snapped to 0/45/90°;
  widths measured across each run on the JPEG. The measurements peak at
  11 and 19–20 mil (the JPEG reads ~1 mil thin), so every track is put in a
  12 / 20 / 25 / 40 mil class, runs joined end to end share one width, and
  short stubs take the width of what they join. Duplicate tracks are
  removed and parallel tracks closer than their half-widths + 8 mil are
  pushed apart (keeping 45° corners). Broken runs are joined when collinear, dangling
  ends are extended to what they point at, short rungs between parallel
  tracks (bridging artefacts) are dropped.
- **Under silk**: the top layer is taken only where visible; track ends are
  run straight on through silk-covered pixels, collecting the visible
  pieces between letters (this rebuilt the bus under the big logo text).
- **SMD pads**: rotated rectangles fitted on visible copper (silk outlines
  often cover the gap between neighbouring pads), angle snapped to 45°, size
  to 0.05 mm. Copper joining two pads is kept as a rectangle. U2 comes from
  its measured TQFP-44 footprint; TH pads and vias from `source/holes.csv`.
- **Top copper areas** (L2 / power section): polygons, snapped to 45°.
- **Bottom layer**, two regimes:
  - inside the pour: board minus its gaps — thin white lines of one width
    (measured 12 mil) as 45° strokes, rings of 15 mil clearance
    (measured 0.382 mm) round pads not on the pour's net;
  - large open regions (lamp area, right edge): tracks vectorised directly.
  - Areas the image hides entirely are assumed to be pour; any pad there gets
    an isolating ring (an open is easier to fix than a short).
- **Mask**: every pad + 0.05 mm, vias tented.

`source/preview.py` renders `vector/` in the source's colours
(`preview/vector_vs_source.png`, `vector_top.png`,
`vector_bottom_seen_from_top.png`). `source/vectorize.py x0 x1 y0 y1` rebuilds
just a region (mm, y from the top edge), e.g. the U2 sample in
`preview/u2_sample_before_after.png`.

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

## Connectivity check against the schematic

`source/netcheck.py` builds nets from the copper (islands joined through
plated holes) and checks what the schematic fixes unambiguously: U2's
GND/VCC/AVCC pin groups, crystal, ISP header JP1, unused pins, every other
U2 pin on its own net, and the four lamps' cathodes multiplexed into 10 nets
(slot 2 of each lamp is its anode). It also compares the vector rebuild with
the raw pixel trace. Latest result: `netcheck_vector.txt`.
`source/trace.py x1 y1 x2 y2` prints the chain of copper joining two points
(for locating shorts). `source/repair.py` proposes gap bridges for required
connections, refusing any that would join two different schematic nets;
its output `source/fixes_proposed.json` is **not applied** yet (rename to
`fixes.json` to apply) because the check does not pass with it either.

**Current result: the rebuild does not match the schematic yet.** U2's
power pins are not all on their nets (6/18 GND and 5/17/38 VCC connect
through half-millimetre stubs the JPEG doesn't show), several U2 signal pins
are shorted together or to GND, MOSI/MISO/RESET do not reach JP1, and only 3
of the 10 lamp cathode nets join all four lamps (their routes run through
the bus above the lamps and under silk text). See "Status".

## Status

Vector rebuild: whole board done. Known weak spots, all where the JPEG hides
copper: tracks under the "electroNIX-3a" / website text and the serial box,
the far-right shift-register column (dense, partly under silk), bottom copper
under the large top pours, and a few tracks that stop short of a lamp pad.
These are what the netlist check below should settle.

Pixel trace (`gerbers/`, the input to the rebuild):

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
