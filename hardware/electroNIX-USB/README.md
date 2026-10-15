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
   polyfuse, SMBJ5.0CA TVS, USBLC6-2SC6 on D+/D−, AMS1117-3.3, and CH340C
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
- **Silkscreen:** the Ø19 bulb outline and a FRONT mark.
- **Before ordering:** print it 1:1 and push a tube's leads through, so the
  mirroring is proven before the PCB is made.

### Tube current

PCB-036 used 10k anode resistors. With 170 V − 140 V across them that is
3 mA peak, so at 1/4 duty each tube averaged only ~0.75 mA. That is half
of the 1.5 mA minimum, and running nixies under-current invites uneven
cathode wear ("poisoning"). The resistors are now sized for an average
near the minimum while keeping peaks well under 12 mA:

| Build | R_anode | Peak at 170 V | Peak at 180 V | Average per tube |
|---|---|---|---|---|
| 4 tubes | 5k6 | 5.4 mA | 7.1 mA | 1.3–1.8 mA |
| 6 tubes | 3k9 | 7.7 mA | 10.3 mA | 1.3–1.7 mA |

The current follows (V_HV − 140 V), so the firmware's HV setpoint sets
the brightness. Keep it at 180 V or below on the 6-tube build. The
cathode switches got 6k8 base resistors, about 15 mA capability at
hFE 40.

The extra current costs power. HV output is ~0.9 W (4 tubes) or ~1.3 W
(6 tubes), roughly 0.3 / 0.4 A from 5 V. With the ESP32 that totals
**~0.5–0.8 A**, so the clock needs a USB-C charger rated for at least
1 A at 5 V (any phone charger), not a computer's USB-A port. These
changes follow from the same budget:
- **Ladder caps are now 2.2 µF:** X7R loses about half its value at
  50 V DC bias, and the multiplier droop scales with I / (f·C).
- **The 6-tube build uses a 22 µH inductor.** At the firmware's 41 %
  duty clamp, 33 µH can deliver only ~2 W into the converter. That is
  enough for 4 tubes but marginal for 6.

## 4 and 6 tubes

Both builds use the same circuit. Six tubes need only two more anode
switches and two more neons. Nothing else changes:
- **HV supply:** the tubes are multiplexed, so one tube is lit at a time
  and the converter's load is the same for 4 or 6.
- **Cathode drivers:** shared by all tubes.
- **Anti-ghosting clamp, ESP32, USB and power:** identical.

Both builds run **stock firmware, unchanged**: no buzzer and no RTC,
time from NTP, and UART0 left to the CH340C for USB flashing.

| | 4-tube (`kicad/`) | 6-tube (`kicad-6tube/`) |
|---|---|---|
| Firmware profile | `BOARD_ELECTRONIX_3` | `BOARD_ELECTRONIX_4_6T` |
| Cathodes C_0…C_9 | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | same |
| Anodes W_1…W_4 | 16, 17, 18, 19 | same |
| Anodes W_5 / W_6 | IO12 / IO15 left open | **12 / 15** |
| SEC_0 / SEC_1 neons | 4 / 5: NE1, NE2 | 4 / 5: NE1+NE2 upper dots, NE3+NE4 lower dots |
| HV PWM / KOMP_170V / JASNOSC | 2 / 35 / 34 | same |
| IO36 | not connected | same |
| IO0 | 10k pull-up, auto-reset | same |
| IO1 / IO3 | CH340C | same |

Notes:
- The firmware still drives **GPIO0** as its buzzer pin after boot.
  Nothing is attached apart from the pull-up and the auto-reset, so it
  does no harm. Leave `cfg.buzzerEn` off.
- **Strapping, 4-tube build:** IO12 and IO15 are open, so the ESP32's
  internal pull-down and pull-up give the right reset defaults.
- **Strapping, 6-tube build:** the W_5 driver base holds IO12 low, which
  is the 3.3 V flash setting it needs. The W_6 driver base pulls IO15
  low, which only silences the ROM boot log. Don't add the 10k IO15
  pull-up that `board.h` suggests for retrofits: against the 15k base
  path it would leave IO15 mid-rail.
- With 1/6 duty the tubes are about a third dimmer than at 1/4. If that
  shows, drop the anode resistors (10k → 6k8). Average HV current stays
  the same.

## Checked against PCB-036

Block by block against `schema_204xZ573M.pdf`:
- **Same topology as PCB-036:** anode switches (MMBTA42 → 430k → MMBTA92
  with 100k B–E, series anode resistor), cathode switches, the off-cathode
  clamp (10 × 1N4148 to KBIAS; 430k/100k with 4 × 470 nF in series), the
  boost stage (22 µ + 100 n in, L, IRLR3110Z, 10R gate, 10k gate–source),
  the 7-diode / 7-capacitor multiplier (diode for diode), the 430k/6k2
  feedback with 100 n, the neon driver, and the light sensor.
- **Intentional differences** are listed below.

## Other changes from PCB-036

- The ATmega16, its 32 kHz crystal, the 0.047 F supercap and the ZANIK
  power-fail divider are gone, and so is the buzzer. Time comes from NTP.
- The feedback clamp now goes to **3V3** (BAT54S); the original clamped to
  5 V.
- Base resistors for 3.3 V drive: 6k8 on the cathode switches, 15k on the
  anode level shifters (they only sink ~0.4 mA). The original 33k gives
  only ~80 µA of base current at 3.3 V.
- Anode resistors are 5k6 (4 tubes) or 3k9 (6 tubes) instead of 10k. See
  *Tube current* above.
- Neons have a 47k base resistor and 150k series resistor per neon
  (~0.6 mA each; one driver handles two neons on the 6-tube build). The
  original 430k base resistor leaves the transistor current-limited at
  3.3 V.
- Off-cathode bias: kept as PCB-036 had it: 430k/100k divider with 4 × 470 nF/50 V
  in series across the 100k (118 nF, 200 V string).
- A second colon neon (SEC_1) is fitted from the start. The original Z573M
  kit had one; leave NE2 off for a single dot.

## PCB (4-tube, in progress)

- **Outline:** 102 × 66 mm with 3 mm corner radius and M3 holes in the
  corners. This is the original kit's footprint (case 102 × 66 mm).
- **Top side:** only the tubes, the colon neons and the BPW34 light
  sensor.
- **Tubes:** each sits on an electroNIX-2 socket adapter. The main board
  takes your bare socket pins on the adapter's 13-pin Ø12.6 mm outer ring
  (2.80 mm pitch, 1.55 mm holes, 2.25 mm pads).
  `electronix:Nixie_RFT_Z573M` is the alternative footprint, with pins
  directly on the tube's Ø9.53 mm circle. It is tight: 2.12 mm pitch and
  ~0.3 mm between pads, with the anode next to k0.
- **Colon:** 0.1" two-lead neon footprints, two stacked in the gap. On the
  4-tube board each lamp has its own output (SEC_0 upper, SEC_1 lower). On
  the 6-tube board the HH:MM pair is on SEC_0 and the MM:SS pair on SEC_1.
- **Bottom side:** everything else, kept clear of the socket-pin rings.
  - Back-left, the boost converter as one compact loop: +5V comes in on
    the left (input caps, L1 pin 1), and the switch node (L1 pin 2, FET
    drain tab) faces right into the multiplier. The multiplier's diode and
    capacitor columns run in chain order from the switch node (top) to
    +170 V (bottom). The gate resistor and pull-down sit at the FET gate.
  - Back-centre: USB-C with its fuse, TVS, ESD array, CC resistors and
    the AMS1117 with its caps.
  - Back-right: CH340C and auto-reset transistors next to the module's
    TXD/RXD/IO0 pins, and the ESP32 with its antenna over the back edge
    (no-copper keepout). Between the module's right-hand pins and the
    edge: 3V3 decoupling at pin 2, the EN RC at pin 3, and the HV
    feedback divider, filter and clamp at IO35.
  - Front band: the output cap and KBIAS at the left, 10 cathode
    switches (base resistor, transistor, clamp diode), and one anode
    cluster under each tube.
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
