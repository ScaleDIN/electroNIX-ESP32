# electroNIX-ESP32

ESP32 firmware rewrite for electroNIX/Nick2 Nixie tube clock boards
(originally ATmega-based; see `WIRING.md` in `electroNIX/` for the
retrofit/rewiring background).

## Where the code lives

- `electroNIX/` — the active Arduino sketch. This is what gets compiled
  and flashed. Files: `electroNIX.ino`, `board.h`, `clock_core.{h,cpp}`,
  `display.h`, `display_nick2.cpp`, `display_testa.cpp`, `web_ui.h`,
  `WIRING.md`.
- `original electronix clock/` — legacy reference material (old .hex
  files, PDFs, schematics for the original ATmega firmware). Not part of
  the ESP32 build; only useful for historical/hardware reference.

## `board.h` — per-device setting, not a code default

`#define BOARD <n>` near the top of `board.h` selects which physical
board this build targets (electroNIX 4, electroNIX 4+S/6T, electroNIX 3,
Nick2 IN-12, etc.). This value is set per the developer's own hardware and
is expected to differ between the repo and a local working copy — don't
"fix" it to match the repo unless the user asks. Everything else in the
sketch keys off the `BOARD_HAS_*` capability flags derived from this
selection, never off `BOARD` directly.

## Workflow

The user edits/reviews here, changes get committed and pushed to GitHub,
and GitHub is the source of truth they pull from on their own machine to
compile and flash via the Arduino IDE. The codebase is reasonably stable;
expect infrequent, targeted changes rather than large refactors.

## Reconstructing Gerbers from a PDF layout (`hardware/`)

`hardware/electroNIX-2/` holds Gerbers rebuilt from the defunct vendor's
Altium toner-transfer PDF ("prasowanka"). The converter is
`hardware/electroNIX-2/source/pdf2gerber.py` (PyMuPDF + shapely). Tools:
`pip install pymupdf shapely scipy`, `apt-get install gerbv`. To convert
another layout, copy the script and follow the steps below.

### 1. Check the PDF is usable

Open it with PyMuPDF and run `page.get_drawings()`. Vector paths are
convertible; a raster scan is not.

This is what the electroNIX-2 Altium PDF contained:
- One page per copper layer.
  - Page 0 was bottom copper, seen from the top.
  - Page 1 was top copper, mirrored by the page's content matrix.
  - Work out which page is which from the parts: the QFP is on top.
- Colours:
  - Copper is black or dark gray (< 0.5).
  - Drill holes are light-gray (0.82) filled circles.
  - Plated slots are light-gray strokes.
  - The board outline is mid-gray (0.35) thin strokes.
- Strokes all use round caps, so a stroke is a track or a round/obround pad.
- Filled paths are:
  - pads: `re` rectangles, 4-segment quads, or 4-curve circles;
  - vias: circles 1.0 mm across with a 0.5 mm hole;
  - pours: many segments and/or several sub-paths.
- Hidden text gives:
  - `PA<designator><pad>` at each pad centre, printed on both pages;
  - `CO<designator>` for each component.
- Extra small boards (like the round socket adapters) can sit on the same
  page outside the main outline.

### 2. Set the constants (top of script and `emit` calls)

- **Scale `S` (mm per pt):** calibrate it from a known track width. Stroke
  widths of 1.4355 pt = 12 mil and 1.7944 pt = 15 mil gave
  S = 0.21233 mm/pt. Check it against the board dimension drawing.
- **`X0_B`, `X0_T`, `Y0`:** the outline's left edge (unmirrored page), right
  edge (mirrored page) and bottom edge, in page points.
- **Main board extents:** `main_w` and `main_h` use the outline's right and
  top edges.
- **File prefixes:** the names passed to `emit`.
- **Colour thresholds:** check them if the PDF uses different grays.

### 3. Pitfalls already hit

- **Nonzero fills:** evaluate them exactly. Polygonize all the rings, then
  sum winding numbers per face. Shortcuts like "opposite orientation =
  hole" or XOR were wrong for pours.
- **`re` direction:** PyMuPDF's orientation flag for an `re` sub-path is
  reported before the page matrix is applied. On the mirrored page, invert
  it. Getting this wrong fills in the thermal-relief cut-outs.
- **Solder mask is the hard part.** The PDF has no mask layer; it has to be
  inferred from pads. Rules that finally worked:
  - A simple filled shape (one sub-path, ≤ 8 segments) that isn't a via is
    a pad. Pours never are, even single-outline ones: the pour under the
    QFP was 288 segments.
  - A stroke containing a drill hole or slot end is a pad. The exception is
    a track-width stroke through a hole that already has another pad shape.
  - Any other stroke is a pad only if it is short and fat (length ≤ 3 ×
    width, width > 0.53 mm) and a pad label for a component on that layer
    lies within 0.4 mm.
  - Decide each component's layer by majority: the side where most of its
    labels land on pad-like copper. Don't use a per-label "other side has a
    pad here" guard: U2's bottom decoupling caps sit directly under its pads.
  - A short stroke touching an already-opened filled pad is a track stub;
    don't open it. Don't reject strokes just for having a track width: the
    QFP pads (0.61 mm) share a width with some tracks.
  - Pad labels can sit up to about 3 mm from their pad (e.g. the DC jack),
    so also seed pads from holes and slots.
  - Vias are tented. Mask expansion is 0.05 mm.
- **Non-plated holes:** a hole is plated if a copper ring surrounds it. For
  non-plated holes, clear copper and mask 0.2 mm around the hole.
- **Gerber/Excellon compatibility:** write X2 attributes as `G04 #@! TF...`
  comments and define at least one `%ADD` aperture, otherwise old parsers
  such as gerbv mistake the file for RS-274D. Emit regions in descending
  area order with `%LPC%` for their holes, so islands inside holes
  survive. Put slots in the PTH drill file as `G85`.

### 4. Verify before handing over

Always inspect the files that are actually shipped, rendered at high
resolution. A 300 dpi whole-board preview hid covered QFP pads twice.

- **Copper:** render each layer with gerbv (include the outline so the bbox
  is the board) and XOR it against the PDF page rasterised at the same
  scale (mirror the top page). Only anti-aliasing slivers should remain.
- **Mask:**
  - Every plated hole and slot has an opening on both sides.
  - No opening lands on bare board.
  - Every pad label has an opening on at least one side; count the pads of
    fine-pitch parts explicitly (U2: 44 of 44).
  - Zoom renders of mask-over-copper (gold = exposed) at 1200 dpi on the
    QFP and power areas.
- **Drills:** every hole appears on both pages at the same place after the
  transform. That confirms the mirroring and scale.

The source PDF has no silkscreen, so none is generated; say so to the user.
