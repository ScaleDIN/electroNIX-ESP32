# electroNIX-USB — USB-C powered ESP32 nixie clock (4 or 6 × Z573M)

A new KiCad design: an ESP32 version of the TESTA-QUADRA **electroNIXclock 3**
(PCB-036, 2013). That was the micro-USB powered board; its schematic is filed as
`original electronix clock/z573m/schema_204xZ573M.pdf`. The tube is the RFT Z573M.
A Z566M variant comes later. This revision is **schematic only**; the PCB is
the next step.

| Path | Contents |
|---|---|
| `kicad/` | **4-tube** KiCad project (HH:MM): root sheet plus 4 sub-sheets, project symbol library (`electronix.kicad_sym`: Z573M, `+170V`) |
| `kicad-6tube/` | **6-tube** KiCad project (HH:MM:SS), same layout of sheets |
| `electroNIX-USB-{4,6}tube-schematic.pdf` | Plots of all 5 sheets |
| `electroNIX-USB-{4,6}tube-bom.csv` | BOMs grouped by value and footprint |
| `source/gen.py` | Generator: `python3 source/gen.py kicad` or `python3 source/gen.py kicad-6tube --tubes 6` |

The files are in KiCad 7 format, so KiCad 7, 8 and 9 all open them (8 and 9
upgrade on save). Once you start editing in KiCad, the KiCad files are the
source and the generator is only a record of the first pass. Don't re-run it
over hand edits.

## Sheets

1. **Power & USB:** USB-C receptacle wired as a 5 V sink (5k1 on CC1/CC2),
   polyfuse, SMBJ5.0CA TVS, USBLC6-2SC6 on D+/D−, AMS1117-3.3, and CH340C
   for programming and serial log.
2. **ESP32:** ESP32-WROOM-32E, EN/BOOT buttons, two-transistor DTR/RTS
   auto-reset, light sensor, SET button. No buzzer and no RTC: time
   comes from NTP.
3. **HV supply:** the PCB-036 converter, unchanged. IO2 drives an IRLR3110Z
   into a 33 µH WE 7447715330. The switch node feeds a 7-diode / 7-capacitor
   Cockcroft-Walton ladder (10MQ100N, 1 µF/100 V) that makes 170 V. Feedback
   is 430k/6k2, the same ratio as `HV_DIV_RATIO`.
4. **Display:** 4 × Z573M. Anodes are switched high-side (MMBTA42 level
   shift into MMBTA92, 10k anode resistor). 10 shared MMBTA42 cathode
   switches. The 1N4148 off-cathode clamp to a ~32 V bias is kept from
   PCB-036. Two colon neons.

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
| SET button | 36 (firmware: optional) | same |
| IO0 | 10k pull-up, BOOT button, auto-reset | same |
| IO1 / IO3 | CH340C | same |

Notes:
- The firmware still drives **GPIO0** as its buzzer pin after boot.
  Nothing is attached apart from the pull-up and the BOOT button, so it
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

## Other changes from PCB-036

- The ATmega16, its 32 kHz crystal, the 0.047 F supercap and the ZANIK
  power-fail divider are gone, and so is the buzzer. Time comes from NTP.
- The feedback clamp now goes to **3V3** (BAT54S); the original clamped to
  5 V.
- Base resistors are 15k for 3.3 V drive. The original 33k gives only
  ~80 µA of base current at 3.3 V.
- Neons have a 47k base resistor and 150k series resistor per neon
  (~0.6 mA each; one driver handles two neons on the 6-tube build). The
  original 430k base resistor leaves the transistor current-limited at
  3.3 V.
- Off-cathode bias filter: one 2.2 µF/50 V cap instead of 4 × 470 nF.
- A second colon neon (SEC_1) is fitted from the start. The original Z573M
  kit had one; leave NE2 off for a single dot.

## Open points (check before or during layout)

- **Z573M pinout** is taken from the tube-tester.com Z573M page (the
  frank.pocnet.net Z573M sheet is the better source, but the build
  environment couldn't reach it yet): B13D base,
  pin 7 at front, 1–3 = digits 1–3, 4 = internal connection, 5–9 = digits
  4–8, 10 = PR, 11 = 9, 12 = 0, 13 = anode. I couldn't open the original
  RFT sheet. **Check it with a tube** (light each pin from a current-limited
  supply) before the footprint is drawn.
- **Tube and neon footprints** aren't assigned yet. They'll be drawn with
  the PCB: the B13D pin circle, plus a socket or flying-lead pads.
- **WE 7447715330:** the KiCad footprint is WE-PD "Typ LS" (12 × 12 mm),
  which is the same series as the 7447715906 in its datasheet link.
  Confirm 33 µH and the saturation current (≥ 2.5 A) when ordering.
- **1 µF/100 V ladder caps:** X7R loses about half its capacitance at 50 V
  DC bias. Use 1210 X7R (as drawn) or 2.2 µF if the HV droops at 4 tubes.
- **ERC:** the KiCad 7 command line here has no ERC, so I checked
  connectivity on the exported netlist instead. No single-pin nets, every
  driver chain was traced, and the multiplier matches PCB-036 diode for
  diode. Run *Inspect → ERC* once in KiCad. Expect a few "power input not
  driven" warnings that the PWR_FLAGs should already cover.

## Z566M and other tubes

Only sheet 5 changes: the tube symbol and footprint, and the anode
resistor. The tube count is already a generator option. Z566M is a 30 mm top-view tube (pin 8 at front
according to the RFT data table). Its full pinout still has to be found.
