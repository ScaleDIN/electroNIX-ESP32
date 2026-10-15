# electroNIX-3a — handoff for the KiCad redraw

**Decision (2026-10):** stop reconstructing the old copper. Redraw the board
in KiCad from the schematic, and use the reconstruction only for mechanical
data and as a placement/routing reference. The USB input will change from
micro-B to USB-C.

Everything here lives in `hardware/electroNIX-3a/`, branch
`claude/sweet-cori-siiic6`.

## 1. Status of what is in this folder

| Path | What it is | Use it for |
|---|---|---|
| `source/electroNIX-3a_schematic.pdf` | Schematic "electroNIXclock 3v1", 2013-11-27, vector PDF | **The design source.** Re-enter it in KiCad |
| `source/electroNIX-3a_layout.jpg` | The only image of the old layout: 1200×638 composite, top view, both copper layers + silk | Placement reference |
| `vector/` | Gerbers rebuilt as CAD primitives (`source/vectorize.py`) | Placement/routing **reference only** |
| `gerbers/` | Earlier pixel trace (`source/jpg2gerber.py`) | Superseded |
| `preview/vector_*.png` | Renders of `vector/` | Quick visual reference |
| `source/holes.csv` | Every hole measured from the JPEG, drill snapped | Mechanical data (see §2) |
| `netcheck_vector.txt` | Connectivity check of `vector/` vs the schematic | Shows why `vector/` can't be fabricated |

**Do not fabricate `vector/` or `gerbers/`.** The netlist check fails:
- U2's GND and VCC pins are not all on their nets.
- Several U2 signal pins are shorted.
- MOSI, MISO and RESET don't reach JP1.
- Only 3 of 10 lamp cathode nets join all four lamps.

The JPEG hides too much copper (under silk text and dense buses) to recover
the exact routing. Section 7 covers the scripts.

## 2. Mechanical data to keep (measured, cross-checked)

Coordinates are in mm, with the origin at the board's **bottom-left** corner, x to the
right and y up, top view (KiCad's y axis points down, so flip y or place
relative to the top-left corner).

**Scale check:** U2's pads span exactly 10 × 0.8 mm, and the outline drawing
says 92 × 56. Both agree to 0.1 %. The rendered copper registers with the
image within 0.06 mm.

- **Board outline:** 92.0 × 56.0 mm rectangle, 2 layers.
- **Mounting holes:** 4 × 3.5 mm, unplated, with 0.2 mm copper keep-out. Same
  as electroNIX-2. Schematic: SR1–SR4, M3.
  - (2.91, 53.07)
  - (89.01, 53.08)
  - (21.44, 5.01)
  - (70.50, 5.00)
- **Nixie tubes (LAMP1–4, ZM1080T), 1.7 mm drills, pads about 2.4–2.5 mm.**
  Each lamp uses 11 positions on a 14-position ring, R = 6.31 mm, pitch
  25.714° (360/14). Ring centres:
  - LAMP1 (10.43, 9.50)
  - LAMP2 (32.45, 9.50)
  - LAMP3 (59.48, 9.51)
  - LAMP4 (81.51, 9.51)

  This matches the electroNIX-2 13-pin socket adapter (its 1.7 mm pins are on
  R = 6.299 mm at the same pitch, see `../electroNIX-2/`). Keep it, so the same
  adapters and tubes fit.

  Number the ring positions as slots, 0 at +x and counting anticlockwise in
  the top view:
  - Used slots: 0, 1, 2, 4, 5, 6, 8, 9, 10, 11, 12.
  - **Slot 2 is the anode.** On the old board it runs to that lamp's 10k
    anode resistor (R28 / R24 / R17 / R11).
  - The other ten slots are cathodes K_0…K_9.
  - The slot-to-digit order was **not** determined. Take it from the
    ZM1080T datasheet / the adapter.
- **Tact switches S1–S3 (TACT-69K-F, 6×6 mm, pin grid 4.5 × 6.5), 1.3 mm
  drills.** Left edge, x = 1.71 / 6.24. Pin pairs at y:
  - 23.80 / 30.31
  - 32.85 / 39.36
  - 41.88 / 48.40

  Silk order from the top: SET, −, +.
- **JP1 ISP header, 2×3, 2.54 mm, 1.0 mm drills.** Columns at x = 10.09 /
  12.63, rows at y = 33.70 / 31.16 / 28.61. The square pin 1 is top-left at
  (10.09, 33.70), numbered odd left, even right, top to bottom. This
  numbering matched U2's MOSI, MISO, SCK and RESET in the pixel trace.
- **N1 neon (NEON-2):** 2 × 1.0 mm holes at (44.69, 5.52) and (47.22, 5.50),
  in the gap between LAMP2 and LAMP3.
- **D20 (HPDB3J-44DA light sensor):** 2 × 1.0 mm holes at (44.69, 31.20)
  and (47.24, 31.20).
- **Other through-hole pads seen on the board:**
  - A 5 mm pair, 1.7 mm drills, at (58.08, 38.57) and (63.08, 38.57), next to
    the "C2" silk.
  - Two figure-8 pads at x ≈ 42.8 and 49.1, y = 38.6. Each holds two 1.0 mm
    holes 1.3 mm apart.
  - Two more figure-8 pads at x ≈ 69.3 and 73.4, y = 40.7, by the "C1" silk.

  These look like radial electrolytics (C1 2.2 µF/250 V, C2) with two
  lead-spacing options. Check against the parts you buy.
- **U2 ATmega16 (TQFP-44, 0.8 mm):**
  - Centre (27.16, 31.46). Pin 1 is at top-left: the first pin of the left
    side, numbered anticlockwise.
  - Land pattern: pads 2.03 × 0.5 mm, rows 11.46 mm apart, centre to centre.
  - Several power pins (5/6, 17/18, 38/39, 28) went to vias directly inside
    the pad ring.
- **USB (micro-B):** top edge, roughly x 8–18 mm. F1 and D18 sit just below
  it. The USB-C part will need its own placement (§5).

## 3. Design rules seen on the old board (reasonable defaults)

- **Tracks:** 12 mil (0.305 mm) signals; 20 mil (0.508) power and lamp
  buses; a few 25 / 40 mil. The JPEG measured them about 1 mil thin.
- **Bottom ground pour:** 15 mil (0.381 mm) clearance. The thin gaps seen
  inside the pour are 12 mil.
- **Vias:** 0.5 mm drill, 1.0 mm pad, tented.
- **Passives:** mostly 1206 (pads about 1.4 × 1.8 mm).
- **Transistors:** SOT-23 (MMBTA42 / MMBTA92 / BC847; pads about 1.0 ×
  1.3 mm).
- **170 V:** the lamp anode and HV areas need creepage. The old board had
  only 12–20 mil gaps around some HV nets. For the redraw, keep ≥ 0.5 mm
  (better 1 mm) between 170 V and anything else.

## 4. Schematic notes (read before entering it)

- 127 designators:
  - Q1–Q21
  - R1–R28, R31–R34, R41–R47
  - C1–C11, C21–C25, C27–C31, C41–C44, C55
  - D1–D22
  - L1, L2
  - LAMP1–4
  - N1, U2, Y1, JP1, F1, LS1, S1–S3, SR1–SR4
- **Revision mismatch:** the board silk says 23.09.2013; the schematic is
  3v1, 2013-11-27. The schematic carries **red hand edits**:
  - R31 → 4.7k.
  - C10 (100 nF) added across R32, the ZANIK supply-loss divider.

  Several schematic parts are not visible on the board's top side, and may
  be bottom-side SMD or 3v1 additions:
  - D1–D10, the 1N4148 cathode clamps into the anti-ghosting network
    R46/R47/C41–C44
  - C21–C31
  - C55 (0.047 F / 5.5 V backup supercap)
  - L1 (AVCC filter)
  - LS1 buzzer with Q21/R34
  - R41–R47
  - D21/D22

  The bottom layer shows pad-shaped islands under and around U2 (no bottom
  silk), so at least the decoupling caps were on the bottom. Decide per part
  in the redraw; entering the schematic as-is (3v1) is the sensible default.
- **U2 nets (ATmega16, TQFP-44 pin numbers):**

  | Pins | Net |
  |---|---|
  | PB2 42 | SEC_0 (neon N1 via R20/Q15) |
  | PB3 43 | ZANIK (supply-loss sense) |
  | PB5 1 / PB6 2 / PB7 3 | MOSI / MISO / SCK. Shared with JP1 and the switches S1–S3 |
  | RESET 4 | R41 10k to +5V_BUF, C25 to GND, JP1-5 |
  | PD0 9, PD1 10, PD2 11, PD3 12, PD6 15 | C_0, C_9, C_4, C_6, C_5 |
  | PD4 13 | LED |
  | PD5 14 | PWM (R33 → Q20, the HV boost FET) |
  | PC0–PC3 (19–22) | W_1…W_4 (anode drivers) |
  | PC6/PC7 (25/26) | Y1 32.768 kHz |
  | PA0–PA4 (37–33) | C_7, C_8, C_3, C_2, C_1 |
  | PA5 32 | MEL (buzzer) |
  | PA6 31 | KOMP_170V (HV feedback divider R43/R42) |
  | PA7 30 | JASNOSC (light sensor D20/R44) |
  | VCC 5/17/38 | +5V_BUF |
  | AVCC 27 + AREF 29 | via L1 to +5V_BUF, C31 to GND |
  | GND | 6/18/28/39 |
  | Unused | 7, 8 (XTAL), 16, 23, 24, 40, 41, 44 |

- **Circuit blocks:**
  - Cathode drivers: Q1–Q10 MMBTA42 with 33k base resistors, driven by C_n
    and switching K_n.
  - Anode drivers: Q11/Q13/Q16/Q18 MMBTA42 → Q12/Q14/Q17/Q19 MMBTA92, plus
    100k/430k/33k/10k resistors, driven by W_n, feeding 170 V to anodes A1–A4.
  - HV boost: L2 + Q20 IRLR3110 + diode/cap multiplier D11–D17 / C3–C9,
    output 170 V, sensed by KOMP_170V.
  - Supply: +5VZAS → D19 MBRS130 → +5V_BUF, with C55 as backup.

## 5. USB-C input (replaces "USB microB")

The old input is **power only**: micro-B pin 1 (VBUS) → F1 (0805, 0.5 A
polyfuse) → +5VZAS, pin 5 → GND, D18 (10MQ100N) from +5VZAS to GND. No
data lines are used. For USB-C as a power-only sink:

- **CC resistors:** fit **two separate 5.1 kΩ pull-downs**, CC1 → GND and
  CC2 → GND. One resistor shared between them does not work. Without them, a
  C-to-C cable or charger supplies no VBUS at all.
- **Receptacle:** a 6-pin power-only receptacle is enough: VBUS, GND, CC1,
  CC2 and the shell, for example GCT USB4125 or a similar "Type-C 6P". A
  16-pin receptacle works too; leave D+/D− unconnected or tie them together.
  Tie the shell to GND.
- **Fuse:** check F1's rating against the real input current. The 170 V
  boost from 5 V can exceed 0.5 A at start-up and full brightness. A 1206
  polyfuse rated around 1–1.5 A hold is a safer choice.
- **Default USB current:** with 5.1k Rd, a USB-C source offers default USB
  power (500 mA / 900 mA) unless it is a charger that advertises 1.5 or 3 A.
  No negotiation is needed for 5 V.
- **Mechanical:** USB-C shells usually have through-hole or SMD tabs, and
  the receptacle must sit flush at the board edge. Reserve about 9 × 8 mm at
  the top edge where micro-B was, and check the case/enclosure opening.
- **ESD (optional):** add a TVS on VBUS (for example SMBJ5.0A); D18's
  position is a natural place. CC lines don't strictly need protection for a
  sink.

## 6. Suggested KiCad workflow

1. Enter the schematic (3v1 plus the red edits) in KiCad, with the USB-C
   change. Run ERC.
2. Make footprints:
   - The Nixie ring: 14 positions, R = 6.31 mm, 1.7 mm drill, about 2.5 mm
     pad, only the 11 used positions populated, slot 0 at +x. Check it
     against the electroNIX-2 adapter's Gerbers.
   - The figure-8 electrolytic pads, if you keep them.
3. Board setup:
   - Outline 92 × 56 mm.
   - Fixed parts from §2: mounting holes, lamps, switches, JP1, N1, D20,
     USB-C.
   - Net classes:
     - Default 0.305 / 0.25 mm.
     - Power 0.508 mm.
     - HV with ≥ 0.5 mm clearance.
   - Vias 0.5 / 1.0.
4. **Reference image:** load `preview/vector_top.png` and
   `preview/vector_bottom_seen_from_top.png` as background images, at
   92 × 56 mm. Or import `vector/*.gtl/.gbl` into a user layer through
   GerbView → File → Export to PCB editor. This copies the old placement and
   routing intent, but KiCad's own netlist decides the connections.
5. Route, add the bottom GND zone, then run DRC and the netlist check in
   KiCad itself.

## 7. Tools in this folder

`source/`. Not needed for the KiCad route, but kept and working.

| Script | Purpose |
|---|---|
| `jpg2gerber.py` | Pixel trace of the JPEG. Writes `layers.npz` and `holes.csv`, which everything else reads |
| `vectorize.py` | CAD-primitive rebuild into `vector/`. `vectorize.py x0 x1 y0 y1` rebuilds one region |
| `preview.py` | Renders `vector/` against the source image |
| `netcheck.py [vector\|raster]` | Schematic structure checks and vector-vs-pixel comparison |
| `trace.py x1 y1 x2 y2` | Prints the copper chain joining two points (y from the top edge) |
| `repair.py` | Proposes gap bridges for required connections. `fixes_proposed.json` is **not applied**; it did not make the check pass |

Requirements: `pip install pymupdf shapely scipy scikit-image skan
networkx opencv-python-headless pillow` and `apt-get install gerbv`.
