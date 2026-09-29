# electroNIX-4 PCB (PCB-061) — reconstructed Gerbers

Gerbers rebuilt from the two toner-transfer PDFs
(`source/electroNIX-4_prasowanka_TOP.pdf`, `..._BOT.pdf`), one copper layer
each. Each PDF holds two boards, so there are two Gerber sets.
Converter: `source/pdf2gerber.py TOP.pdf BOT.pdf OUTDIR`.

| File | Contents |
|---|---|
| `electroNIX4-display-gerbers.zip` | Tube/display board, 131.83 × 34.76 mm, 2 layers (4 × 12-pin tube footprints, 12-pin + 4-pin header) |
| `electroNIX4-main-gerbers.zip` | Controller board, 131.83 × 34.71 mm, 2 layers (44-pin QFP, DC jack, SMD parts) |
| `preview/` | Top and bottom renders (gold = exposed copper, green = covered copper, red = mask opening over non-plated hole). Bottom is shown mirrored, as seen from below |

Each zip has top/bottom copper (`.gtl/.gbl`), solder mask (`.gts/.gbs`),
paste (`.gtp/.gbp`), outline (`.gko`) and Excellon drills split into
`PTH.drl` / `NPTH.drl`. Units are mm.

## Assumptions to confirm

- **Layer assignment:** the PDFs have no text, so nothing in them says which
  is which. The `BOT` PDF is drawn as seen from the top and `TOP` is drawn
  mirrored, which is the toner-transfer convention (the same as the
  electroNIX-2 PDF). The QFP is on the `BOT` layer. If the boards turn out
  mirrored, swap the two PDFs on the command line.
- **Scale:** the artwork is a 1:1 print (600 dpi grid, 1 pt = 25.4/72 mm).
  Every stroke width comes out as a whole mil (10, 12, 15, 20, 30, 40, 60 mil),
  which confirms it. Board size is 5.19 × 1.37 in.
- **Board outline:** rectangles taken from the 10 mil frame lines.
- **Hole sizes:** the printed marks are taken as real drill sizes, clustered
  and snapped to 0.05 mm: 0.5 (vias), 0.8, 1.0, 1.3 (DC jack slots), 1.7
  (tube pins), 2.5 and 3.5 (non-plated mounting holes).

## Suggested fab settings

2 layers, 1.6 mm FR-4, 1 oz copper, HASL or ENIG. Smallest track is 12 mil
(0.30 mm) and the smallest hole is a 0.5 mm via with a 0.88 mm land. A
standard 6/6 mil process is enough. (The 10 mil lines in the PDFs are the
board outline, not copper.)

## How it was checked

- All 97 (display) and 111 (main) drill marks sit at the same place on both
  copper pages after the mirror, and their sizes agree within 0.02 mm.
  That confirms the mirroring and registration.
- The copper Gerbers were rendered with gerbv and diffed against the PDF at
  0.05 mm/px, with drill holes excluded. On the display board nothing
  wider than 2 px is left after a 1 px shift. On the main board the only
  differences are the DC-jack slot ends, where the diff mask uses flat
  slot ends.
- Every plated hole of 0.6 mm or larger has a mask opening on both sides.
  All 44 QFP pads are open.

## Not in the source PDF, so reconstructed or missing

- **Silkscreen:** none, and no component labels either. Use the original
  layout pictures for part placement.
- **Solder mask:** made from the pads, expanded by 0.05 mm. Vias are
  tented. Pads are:
  - every simple filled shape (rectangle or circle) that isn't a via;
  - stroke-drawn pads (round, obround, QFP) that sit on a drill hole or slot,
    or are short and at least 0.53 mm wide and not drawn in a track width.

  There are no pad labels in these PDFs, so unlike electroNIX-2 the rule has
  no label check. Copper pours and short track stubs stay covered.
- **Paste:** SMD pads with no expansion. Only needed for a stencil.
- **Plating:** a hole counts as plated when it has a copper ring. That leaves
  the 3.5 mm mounting holes (6 on the display board, 6 on the main board)
  and the two 2.5 mm holes on the main board non-plated, with 0.2 mm copper
  clearance added. The DC-jack slots (1.3 mm wide) are plated slots (G85) in
  `PTH.drl`.
