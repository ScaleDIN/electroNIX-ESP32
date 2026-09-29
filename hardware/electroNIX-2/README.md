# electroNIX-2 PCB — reconstructed Gerbers

The original electroNIX-2 board (electroNIXclock.pl, Altium, 2013) is no
longer sold. These Gerbers were rebuilt from the vendor's toner-transfer
PDF (`source/electroNIX_-_2_prasowanka.pdf`), which holds the two copper
layers as vector artwork. Converter: `source/pdf2gerber.py`.

| File | Contents |
|---|---|
| `electroNIX2-gerbers.zip` | Main board, 205.0 × 53.9 mm, 2 layers |
| `electroNIX2-socket-adapter-gerbers.zip` | Round 13-pin tube adapter, Ø16 mm (the PDF has 3 identical copies, so order qty ≥ 3) |
| `preview/` | Top and bottom renders (gold = exposed copper). The bottom is shown mirrored, as seen from below |

Each zip has top/bottom copper (`.gtl/.gbl`), solder mask (`.gts/.gbs`),
paste (`.gtp/.gbp`, main board only), outline (`.gko`), and Excellon drill
files split into `PTH.drl` / `NPTH.drl`. Units are mm.

## Suggested fab settings

2 layers, 1.6 mm FR-4, 1 oz copper, HASL or ENIG. The smallest track is
0.305 mm (12 mil) and the smallest hole is a 0.5 mm via. Some tracks pass
between the 0.8 mm-pitch QFP pads, so any standard 6/6 mil process is enough.

## How it was checked

- Scale comes from the 12 mil and 15 mil track widths (1 pt = 0.21233 mm).
  That gives 205.01 mm for the outline, and the original drawing says 205.00.
- All 357 drill marks sit at the same place on both copper pages, which
  confirms the mirroring and registration between the layers.
- The copper Gerbers were rendered with gerbv and diffed pixel-by-pixel against
  the PDF at 0.05 mm/px. The only differences are sub-0.1 mm anti-aliasing
  on 45° edges, plus the intended 0.2 mm copper clearance added around the
  non-plated holes.

## Not in the source PDF, so reconstructed or missing

- **Silkscreen:** none. Use the original layout pictures for part placement.
- **Solder mask:** made from the pads, expanded by 0.05 mm. Vias are tented.
  Pads are:
  - every simple filled shape (rectangle, quad or circle) that isn't a via;
  - stroke-drawn pads (round, obround, QFP) that sit on a drill hole or slot
    or carry one of Altium's pad labels from the PDF.

  Pad labels are printed on both pages, so each component is assigned to
  the side where most of its labels land on pads. This matters for U2: it
  has decoupling caps directly underneath it on the bottom.

  Copper pours stay covered. So do short track stubs in standard track
  widths.
- **Paste:** SMD pads with no expansion. Only needed for a stencil.
- **Plating:** a hole counts as plated when it has a copper ring. That leaves
  the 3.5 mm mounting holes and the adapter's 6 mm centre hole non-plated.
  The DC-jack slots (1.3 × 3.05 mm) are plated slots (G85) in `PTH.drl`.
- **Hole sizes:** snapped to 0.05 mm from the printed hole marks: 0.5, 1.0,
  1.3, 1.7, 3.5, 6.0 mm.
