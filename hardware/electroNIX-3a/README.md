# electroNIX-3a — approximate Gerbers traced from a raster

Rebuilt from a single 1200×638 JPEG (top view, colour-coded layers) by
`source/jpg2gerber.py`. **Not fabrication grade — for reference, re-layout
or as a starting point.** Scale is 8.4 px/mm (~0.12 mm/px), calibrated so the
outline is 92 × 56 mm.

Layers in `gerbers/`: F_Cu (red), B_Cu (navy), F_SilkS (green), F/B_Mask,
Edge_Cuts, PTH.drl, NPTH.drl.

Known limits:
- **Bottom copper is incomplete**: wherever top copper (red) sits over it,
  the bottom layer is hidden in the image and is not recovered.
- Track widths/edges carry ±0.1 mm error and JPEG noise; fine-pitch
  QFP pads are only approximately right.
- **Drill sizes are guesses** (PTH = 0.5 × pad, min 0.3 mm; 3.2 mm mounting
  holes). Not measurable from the image.
- **Solder mask is a heuristic**: through-hole pads plus compact red blobs.
  Fine-pitch and edge-connector pads are likely missing openings.
- Bottom silk, paste, vias' tenting and the board corner cut-outs are not
  reconstructed. The board outline is a plain rectangle.
- The schematic PDF was not used for connectivity, only as reference.
