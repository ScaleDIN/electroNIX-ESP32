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
   auto-reset, DS3231M + CR2032, buzzer, light sensor, SET button.
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

The cost is two GPIOs. Every output-capable pin is already used on the
4-tube build, so the 6-tube build **drops the buzzer and the DS3231**:

| | 4-tube (`kicad/`) | 6-tube (`kicad-6tube/`) |
|---|---|---|
| IO12 | MEL buzzer | W_5 anode (seconds tens) |
| IO15 | DS3231 SDA | W_6 anode (seconds units) |
| IO0 | DS3231 SCL (4k7 pull-up) | 10k pull-up only |
| Colon | NE1 (SEC_0), NE2 (SEC_1) | NE1+NE2 on SEC_0 (upper dots), NE3+NE4 on SEC_1 (lower dots) |
| Firmware | `BOARD_ELECTRONIX_3` + 4 overrides (see below) | **stock `BOARD_ELECTRONIX_4_6T`, no changes** |
| Time source | NTP + DS3231 | NTP |

The 6-tube map is the existing electroNIX 4+S map, `ANODE_PINS {16, 17,
18, 19, 12, 15}`. The firmware still drives GPIO0 as the buzzer pin; with
nothing fitted that does no harm. UART0 stays with the CH340C on both
builds, so USB flashing and the serial log keep working.

Strapping on the 6-tube build:
- IO12 is held low by the W_5 driver base, which is the 3.3 V flash
  setting it needs.
- IO15 is pulled low by the W_6 driver base. The only effect is that the
  ROM boot log is silenced. Don't add the 10k pull-up that `board.h`
  suggests for retrofits: against the 15k base path it would leave IO15
  mid-rail.

With 1/6 duty the tubes are about a third dimmer than at 1/4. If that
shows, drop the anode resistors (10k → 6k8). Average HV current stays
the same.

## GPIO map (4-tube build)

Matches the firmware's `BOARD_ELECTRONIX_3` profile, with three exceptions:

| Function | GPIO | vs. `BOARD_ELECTRONIX_3` |
|---|---|---|
| Cathodes C_0…C_9 | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | same |
| Anodes W_1…W_4 | 16, 17, 18, 19 | same |
| SEC_0 / SEC_1 neons | 4 / 5 | same |
| HV PWM | 2 | same |
| KOMP_170V (HV sense) | 35 | same |
| JASNOSC (light) | 34 | same |
| SET button | 36 | same |
| **MEL buzzer** | **12** | was 0 |
| **DS3231 SDA / SCL** | **15 / 0** | was 1 / 3 |
| USB-UART | 1 (TX), 3 (RX) | now used by the CH340C |

Why the changes:
- **The buzzer moved off GPIO0.** IO0 needs a pull-up to boot normally.
  With the buzzer transistor's base resistor hanging on it, a 10k pull-up
  only reaches about 1.1 V at reset, which reads as low, so the chip enters
  download mode. GPIO12 has to be *low* at reset (3.3 V flash), and a
  transistor base plus a 100k pull-down holds it there.
- **The RTC moved off GPIO1/3** because those pins are now the USB-UART.
  The I²C pull-ups help here: IO15 is meant to be high at reset and IO0 has
  to be high to run.

The firmware therefore needs a small new board profile: `PIN_BUZZER 12`,
`BOARD_RTC_SDA 15`, `BOARD_RTC_SCL 0`, `BOARD_HAS_RTC 1`, and
`BOARD_USE_SERIAL 1`. That isn't written yet.

## Other changes from PCB-036

- The ATmega16, its 32 kHz crystal, the 0.047 F supercap and the ZANIK
  power-fail divider are gone. Time comes from NTP and the DS3231.
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
