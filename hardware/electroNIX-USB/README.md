# electroNIX-USB — USB-C powered ESP32 nixie clock (4 or 6 × Z573M)

A new KiCad design: an ESP32 version of the TESTA-QUADRA **electroNIXclock 3**
(PCB-036, 2013). That was the micro-USB powered board; its schematic is filed as
`original electronix clock/z573m/schema_204xZ573M.pdf`. The tube is the RFT Z573M.
A Z566M variant comes later.

**Status (work in progress):** schematics are done for 4 and 6 tubes. The
4-tube PCB (`kicad/electroNIX-USB.kicad_pcb`, 102 × 66 mm, the original
kit's size) and the 6-tube PCB (`kicad-6tube/`, 150 × 66 mm) are **placed
but not routed**. Route them in KiCad (Freerouting plugin, fanout off),
then add the GND pours on both layers.

| Path | Contents |
|---|---|
| `kicad/` | **4-tube** KiCad project (HH:MM): root sheet plus 4 sub-sheets, project symbol library (`electronix.kicad_sym`: Z573M, `+170V`) and footprint library (`electronix.pretty`: `Nixie_RFT_Z573M`) |
| `kicad-6tube/` | **6-tube** KiCad project (HH:MM:SS), same layout of sheets |
| `electroNIX-USB-{4,6}tube-schematic.pdf` | Plots of all 5 sheets |
| `electroNIX-USB-{4,6}tube-bom.csv` | BOMs grouped by value and footprint |
| `source/gen.py` | Generator: `python3 source/gen.py kicad` or `python3 source/gen.py kicad-6tube --tubes 6` |
| `source/pcb.py` | Board builder: places parts from the netlist, autoroutes with Freerouting, pours GND, runs DRC (`--place-only` stops after placement) |
| `source/fab.sh` | Gerbers, drill files and pick-and-place zip for a board |
| `source/footprint.py` | Writes the Z573M footprint: `python3 source/footprint.py kicad/electronix.pretty` |

The files are in KiCad 7 format, so KiCad 7, 8 and 9 all open them (8 and 9
upgrade on save). Once you start editing in KiCad, the KiCad files are the
source and the generator is only a record of the first pass. Don't re-run it
over hand edits.

## Sheets

1. **Power & USB:** USB-C receptacle wired as a 5 V sink (5k1 on CC1/CC2),
   polyfuse, SMBJ5.0CA TVS, 22 µF/35 V tantalum bulk, USBLC6-2SC6 on D+/D−, AMS1117-3.3, and CH340C
   for programming and serial log.
2. **ESP32:** ESP32-WROOM-32E, two-transistor DTR/RTS auto-reset, and the
   light sensor. **No switches:** the firmware is set up from its web UI
   and reads no button. The CH340C resets the chip and puts it into
   download mode, and unplugging USB is the reset. If auto-reset ever
   fails, short the IO0 pull-up to GND while plugging in. No buzzer and
   no RTC: time
   comes from NTP.
3. **HV supply:** the PCB-036 converter. IO2 drives an IRLR3110Z into a
   33 µH WE 7447715330 (22 µH on the 6-tube build). The switch node feeds a
   7-diode / 7-capacitor Cockcroft-Walton ladder (10MQ100N, 2.2 µF/100 V)
   that makes 170 V. Feedback is 430k/6k2, the same ratio as
   `HV_DIV_RATIO`.
4. **Display:** 4 or 6 × Z573M. Anodes are switched high-side (MMBTA42
   level shift into MMBTA92, 5k6 or 3k9 anode resistor). 10 shared MMBTA42
   cathode switches. The 1N4148 off-cathode clamp to a ~32 V bias is kept
   from PCB-036. Colon neons.

## Z573M (RFT data book p.101/103)

Source: [frank.pocnet.net/sheets/084/z/Z573M.pdf](https://frank.pocnet.net/sheets/084/z/Z573M.pdf).
Z5730M is the same tube without the contrast-filter coating.

- **Tube:** side-view, 13 mm digits, decimal point on the right. Bulb is
  Ø19 × 47.6 mm with 38 mm flying leads.
- **Pinout:** 1–3 = k1–k3, 4 = ic (internal, leave open), 5–9 = k4–k8,
  10 = dp, 11 = k9, 12 = k0, 13 = anode. This matches the symbol.
- **Lead layout:** 13 leads on a **Ø9.53 mm** circle in 14 equal
  positions (25.7°), with the gap opposite **wire 7, which faces the
  front**.
- **Electrical:** V_ign 150 V, V_maint 140 V, V_ext 120 V, minimum supply
  170 V. **Cathode current 1.5–2.5 mA continuous, 12 mA pulse maximum.**

### Footprint `electronix:Nixie_RFT_Z573M`

- **Geometry:** a top view with wire 7 toward +Y, so the board's front
  edge goes toward +Y. The data book draws the leads from below,
  numbered clockwise; on the footprint they run counter-clockwise. Pad 1
  is square.
- **Pads:** 0.8 mm drill, 1.35 mm pad, 2.12 mm centre spacing.
- **Silkscreen:** references are 0.8 mm. Each sits right beside its own
  part (within ~1 mm, and closer to its own part than to any other) or,
  where there's no room, inside the part between its pads (the ladder
  caps). Labels never overlap other labels, part outlines, pads or the
  board edge.
- **KBIAS network** (430k, 100k, 4 × 470 nF series string) sits in the
  free space under the colon, between the tube 2 and tube 3 anode
  clusters.
- **ESP32 footprint:** the stock footprint's 48 mm-wide keep-out and
  matching courtyard are replaced by a body-sized courtyard plus a board
  keep-out under the antenna. The module sits 0.3 mm inside the back edge.
  Minimum drill is 0.2 mm for the module's exposed-pad vias.
- **Known DRC item:** the USB-C footprint's locating pegs are 0.19 mm from
  its own pads (stock GCT USB4105 footprint). Exclude it in DRC.
- **Net classes:** HV (0.4 mm clearance) for +170 V, anodes, the ladder
  and the neon nets; Power (0.5 mm track) for GND/+5V/+3V3/VBUS.

## Open points (check before or during layout)

- **Neon footprints** are still unassigned. Pick the lamp (NE-2 or INS-1)
  with the layout.
- **WE 7447715330:** the KiCad footprint is WE-PD "Typ LS" (12 × 12 mm),
  which is the same series as the 7447715906 in its datasheet link.
  Confirm 33 µH and the saturation current (≥ 2.5 A) when ordering. For
  the 6-tube build's 22 µH, `7447715220` is inferred from the same part
  numbering: check that it exists and that I_sat ≥ 3 A.
- **ERC:** the KiCad 7 command line here has no ERC, so I checked
  connectivity on the exported netlist instead. No single-pin nets, every
  driver chain was traced, and the multiplier matches PCB-036 diode for
  diode. Run *Inspect → ERC* once in KiCad. Expect a few "power input not
  driven" warnings that the PWR_FLAGs should already cover.

## Z566M and other tubes

Only sheet 5 changes: the tube symbol and footprint, and the anode
resistor. The tube count is already a generator option. The Z566M
(30 mm digits) still needs its data sheet for the pinout and lead layout.
