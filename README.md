# electroNIX → ESP32 rewiring guide

**Use `BOARD_ELECTRONIX_4` for any 4-tube build and `BOARD_ELECTRONIX_4_6T`
for any 6-tube build.** These two board definitions cover every supported
TESTA-QUADRA PCB. The Nick2 IN-12 is a completely different design and is
documented separately below.

If you are retrofitting an older board that uses an **IRF840** boost MOSFET
(electroNIX 2 PCB, fourTINY) rather than the logic-level **IRLR3110Z** of the
electroNIX 4, you need a gate driver — see the *IRF840 boards* section under
electroNIX 4+S.

> ## ⚠️ 170 V is present on every board
> The boost output and all the driver stages carry ~170 VDC. The output
> capacitors hold charge after power-off. Unplug, wait, and verify with a
> meter before touching anything. Never rewire with power applied.

## Strategy: leave the ATmega in place, hold it in reset

You don't have to desolder the TQFP-44 on any of these boards. Grounding its
**RESET (pin 4)** puts every AVR pin into high-impedance, freeing all the
driver nets. One short wire from the RESET pad (or the ISP header JP1) to GND
and the chip is out of the picture.

Pick up the signals at the **resistors** they feed — larger pads, no
fine-pitch soldering. Every driver on every board is an active-high NPN base
behind a series resistor, so 3.3 V logic drives them directly with no level
shifters needed on any output.

---

# electroNIX 4 — recommended 4-tube target

`#define BOARD BOARD_ELECTRONIX_4`

Logic-level **IRLR3110Z** boost switch — drives directly from 3.3 V, no gate
driver needed.

## Signal map

| Net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | **R22–R31** (33 k) | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | Designators are not in net order — see below. |
| `W_1`…`W_4` anodes | **R15, R14, R17, R16** (33 k) | 16, 17, 18, 19 | |
| `SEC_0`, `SEC_1` colons | **R18, R19** (430 k) | 4, 5 | See *Colon wiring* in the 4+S section. |
| `PWM` boost gate | **R59** (10 Ω at Q50) | 2 | IRLR3110Z, logic-level, drive directly. |
| `KOMP_170V` | **R60 / R61** junction | 35 (input) | |
| `JASNOSC` | **R63 / D1** junction | 34 (input) | R63 pulls up to **+5V_BUF** — lift its supply end and rewire to ESP32 **3V3** before connecting GPIO34. |
| `MEL` buzzer | **R62** (2 k) | **0** | GPIO0 is a strapping pin. Fit ≥10 kΩ pull-up to 3V3. `cfg.buzzerEn` defaults false. GPIO12 is free. |
| IR receiver (IR1) | IR1 pad | 39 (input, reserved) | Power IR1 from 3V3, not +5V_BUF. Not decoded yet. |
| DS3231 SDA (optional) | I2C bus | 1 | 4.7 kΩ pull-up to 3V3. |
| DS3231 SCL (optional) | I2C bus | 3 | 4.7 kΩ pull-up to 3V3. |
| Buttons S1–S3 | switch leg | 36 (optional) | External 10 k to 3V3 required — GPIO36 has no internal pull-up. |

GPIO1, GPIO3, and GPIO12 are all free when no DS3231 is fitted.

## Cathode designators are not in net order

This trips people up on every TESTA board: resistor numbers do not run in the
same order as `C_0`…`C_9`. Wire them in any convenient order, then fix any
scrambling in software using **Pin check** — you never have to resolder.

**Maintenance → Pin check → digits**: hold `0`, note what digit the tubes
actually show, repeat for `1`–`9`. Type the ten observations into the *Digits
shown for 0–9* field and save. The display is then correct. Re-open the page
and the field reads `0,1,2,…,9` — that's the confirmation.

**Tube positions** work the same way via *Pin check → tubes*: click each
position button, note which tube lights, record the physical order in *Tube
positions*. Digits and tube positions can be fixed independently and in either
order.

---

# electroNIX 4+S — recommended 6-tube target

`#define BOARD BOARD_ELECTRONIX_4_6T`

The electroNIX 4 expanded to six tubes with a seconds pair. Every cathode,
both colon outputs, the HV PWM pin, and all sensors stay on exactly the same
GPIOs as the 4-tube board. This definition also covers **fresh ESP32 retrofits
of the electroNIX 2 PCB** — use it in place of the obsolete
`BOARD_ELECTRONIX_2`.

## GPIO changes from the electroNIX 4

The electroNIX 4 uses all comfortable output GPIOs. The two extra anode
outputs and the optional LED backlight come from reassigning the buzzer and
reclaiming the two strapping pins:

| GPIO | Role on electroNIX 4 | Role on electroNIX 4+S |
|---|---|---|
| **0** | Unused | `MEL` buzzer (strapping pin — 10 kΩ pull-up to 3V3 required) |
| **12** | `MEL` buzzer | `W_5` anode — seconds tens tube (no pull-up needed) |
| **15** | Unused | `W_6` anode *or* LED backlight — see below (strapping pin — 10 kΩ pull-up to 3V3 required) |
| **1** | Free | DS3231 SDA — *or* `W_6` anode when LED backlight fitted |
| **3** | Free | DS3231 SCL |

## Pull-ups on GPIO0 and GPIO15

Both are strapping pins. GPIO0 drives the buzzer (normally LOW); GPIO15 drives
the W_6 anode or LED backlight BJT base through a 33 kΩ series resistor. Both
conditions pull those pins below the 2.31 V HIGH threshold at reset, which can
cause spurious download-mode entry.

**Fit 10 kΩ from GPIO0 to 3V3 and 10 kΩ from GPIO15 to 3V3.** GPIO12 (W_5)
is not a strapping pin and needs no pull-up.

## Colon wiring — SEC_0 and SEC_1

`SEC_0` (GPIO4) and `SEC_1` (GPIO5) are two independent drive outputs. The
firmware controls them with whatever colon mode is configured (STEADY, BLINK,
BREATHE, ALTERNATE, etc.) — what you connect to them is entirely up to you.
Common arrangements:

- **Single neon per colon position**: wire one neon to `SEC_0`, leave `SEC_1`
  unconnected. Set `BOARD_DUAL_NEON 0` in `board.h`.
- **Top and bottom dots, both positions**: wire all top neons in parallel to
  `SEC_0` and all bottom neons in parallel to `SEC_1`. ALTERNATE then steps
  top on → bottom on across all positions simultaneously.
- **Independent per-position control**: wire all HH:MM neons to `SEC_0` and
  all MM:SS neons to `SEC_1`.

Any arrangement works — the firmware fires GPIO4 and GPIO5 on every tick
regardless of what's physically connected. Set `BOARD_DUAL_NEON 1` whenever
two outputs are wired; set `BOARD_DUP_COLON 1` only if the web UI preview
should mirror the HH:MM colon state onto MM:SS (no firmware effect otherwise).

## Optional LED backlight (electroNIX 2 PCB only)

The electroNIX 2 PCB has an under-tube LED backlight chain (R17 → Q3). To
enable it:

1. **Wire R17 to GPIO15.** GPIO15 becomes `PIN_LEDBL`, PWM'd at 1 kHz. The
   10 kΩ pull-up already fitted on GPIO15 is sufficient.
2. **Wire W_6 (R42) to GPIO1.** GPIO1 was the original LED drive pin before
   the DS3231 retrofit; it reverts to active use here. The bootloader drives
   it briefly at reset — through a 33 kΩ base resistor with no HV on the
   rail, the tube cannot strike.
3. **Set `BOARD_HAS_LED_BL 1`** in the profile in `board.h`. The firmware
   remaps `ANODE_PINS[5]` to GPIO1 and sets `PIN_LEDBL = 15` automatically.
4. **Leave `BOARD_HAS_RTC 0`.** GPIO1 cannot be both W_6 and DS3231 SDA. The
   firmware issues a compile-time error if both flags are set.

## Signal map

| Net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | **R22–R31** (33 k) | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | **Identical to the electroNIX 4.** |
| `W_1`…`W_4` anodes | **R15, R14, R17, R16** (33 k) | 16, 17, 18, 19 | **Identical.** |
| `W_5` anode (seconds tens) | 33 k base resistor | **12** | GPIO12, former buzzer. No pull-up needed. |
| `W_6` anode (seconds units) | 33 k base resistor | **15** *(no LED)* or **1** *(LED)* | See LED backlight section above. |
| `LED` backlight | **R17** (33 k, base of Q3) — electroNIX 2 PCB only | **15** *(when fitted)* | Mutually exclusive with DS3231 RTC. |
| `SEC_0`, `SEC_1` colons | 430 k base resistors | 4, 5 | **Identical to the electroNIX 4.** See *Colon wiring* above. |
| `PWM` boost gate | **R59** (10 Ω at Q50) | 2 | IRLR3110Z, logic-level. Identical. |
| `KOMP_170V` | **R60 / R61** junction | 35 (input) | Identical. |
| `JASNOSC` | **R63 / D1** junction | 34 (input) | Lift R63's +5V_BUF end to 3V3. Identical. |
| `MEL` buzzer | **R62** (2 k) | **0** | Strapping pin. 10 kΩ pull-up to 3V3. `cfg.buzzerEn` defaults false. |
| DS3231 SDA (optional) | I2C bus | **1** *(no LED)* | Unavailable when LED backlight fitted. 4.7 kΩ pull-up to 3V3. |
| DS3231 SCL (optional) | I2C bus | 3 | 4.7 kΩ pull-up to 3V3. |
| Buttons S1–S3 | switch leg | 36 (optional) | External 10 k to 3V3. |

## Matching the seconds tubes

Seconds tubes often sit behind different emitter resistors and look dimmer at
equal duty. Use the **per-tube trim** row in the web UI — six percentages — to
even them out without touching the hardware.

## IRF840 boards — gate driver required

The electroNIX 2 PCB and fourTINY use an **IRF840** boost MOSFET. This is a
standard-level part specified at Vgs = 10 V; at 3.3 V it will either not turn
on at all or turn on partially and overheat. **Fit a gate driver before
connecting the PWM wire.** Options:

1. **Gate driver (recommended):** TC4420, MCP1407, or UCC27517 from the
   board's +12 V rail. ESP32 GPIO2 → driver input, driver output → gate
   resistor → Q5 gate. Non-inverting — leave `HV_PWM_INVERT 0`.
2. **Discrete level shifter:** a 2N7002 with a pull-up to +12 V. This
   **inverts** — set `HV_PWM_INVERT 1`. Check Q5 doesn't run hot; the 2N7002
   is slower than a real driver.
3. **Swap the FET:** replace with a logic-level 500 V part. Uncommon;
   options 1 and 2 are usually easier.

The sketch refuses to build for an IRF840 board until `HV_GATE_FITTED 1` is
set in `board.h` — this is deliberate.

Also check the gate resistor on the fourTINY: **R50** is shown as 10 k on
that schematic, which may be a pull-down rather than a series resistor — 10 k
in series with the gate at 32 kHz is far too slow. Confirm with a meter before
powering up.

---

# Nick2 IN-12 — different architecture

`#define BOARD BOARD_NICK2`

The Nick2 is not a TESTA-QUADRA board. Where TESTA drives cathodes directly
from individual GPIOs, Nick2 uses a **74141 BCD decoder** — four GPIO bits
select which of the ten cathodes conducts, so a single chip replaces ten
transistors. The colon is a column of **five WS2812B addressable LEDs** rather
than neon lamps.

## Signal map (schematic rev 2.0, 2021-03-09)

| Net | ESP32 GPIO | Notes |
|---|---|---|
| 74141 input A (LSB) | 4 | BCD digit select — shared across all tubes. |
| 74141 input B | 17 | |
| 74141 input C | 5 | |
| 74141 input D (MSB) | 16 | |
| Anode 1 | 32 | One GPIO per tube — multiplexed by the ISR. |
| Anode 2 | 33 | |
| Anode 3 | 25 | |
| Anode 4 | 26 | |
| WS2812B chain | 3 (UART RX) | 5 LEDs per column: 1 decorative top, 2 colon dots, 1 colon dot, 1 decorative / warning bottom. |
| `JASNOSC` (optional) | 34 (input) | If a light sensor is fitted. |
| DS3231 SDA (optional) | 21 | Standard ESP32 I2C pins — no strapping-pin concerns. |
| DS3231 SCL (optional) | 22 | |

If your board revision uses different GPIOs, the runtime endpoint
`POST /api/action?do=setpin&kind=an&idx=0&gpio=32` writes to NVS and
reboots. `kind=an` for anode 0–3, `kind=bcd` for 74141 inputs A–D (0–3).
Alternatively define `PIN_BCD_A` etc. in `board.h` before including it.

## Colon LEDs

The five WS2812B LEDs are addressed 0–4 top to bottom. LEDs 1 and 3 (the two
colon dots) are driven by the colon mode; LEDs 0, 2, and 4 are decorative and
configurable separately. LED 4 (bottom) doubles as the *time not trusted*
warning — it blinks regardless of colon mode until a trusted time source
(NTP, RTC, or browser sync) is established.

If your column is physically upside-down, tick **colonReversed** in the web
UI to flip the mapping without rewiring.

---

# Deprecated board targets

The following board definitions remain in the firmware but are no longer
the recommended retrofit target. Use `BOARD_ELECTRONIX_4` or
`BOARD_ELECTRONIX_4_6T` for new builds.

## electroNIX 3 (`BOARD_ELECTRONIX_3`)

4-tube, logic-level IRLR3110ZPBF boost switch, **USB power only** (no 12 V
rail — a boost + diode-capacitor multiplier ladder runs directly from 5 V).
The GPIO map is identical to the electroNIX 4 except the light sensor pull-up
resistor is 1 M (R44) to +5V rather than +5V_BUF — lift it to 3V3 the same
way.

Only one colon neon is fitted from the factory (`SEC_0` only); a second can
be added as a bodge to the ATmega's PB1 pad and wired to GPIO5. Tick **Second
colon neon fitted** in the web UI once done.

Power: feed the ESP32's **5V/VIN** from `+5V_BUF` (D19 + bulk caps). Do not
feed a GPIO from the USB rail. The boost duty ceiling (`HV_DUTY_MAX` in
`display_testa.cpp`) may need raising on this board — watch `duty` and `hv`
in the status bar on first power-up.

## electroNIX 2 (`BOARD_ELECTRONIX_2` — obsolete)

PCB-030/031, 6-tube, **IRF840** boost switch. Use `BOARD_ELECTRONIX_4_6T`
for fresh retrofits of this PCB. A gate driver is required — see the *IRF840
boards* section above. Set `BOARD_HAS_LED_BL 1` if the under-tube LED
backlight chain (R17/Q3) is fitted. The cathode resistors are numbered R56–R65
in a scrambled order; use **Pin check** to sort them out in software rather
than reordering the wires.

## fourTINY (`BOARD_FOURTINY`)

4-tube (LC-516), **IRF840** boost switch — gate driver required. GPIO map is
identical to the electroNIX 4; use `BOARD_ELECTRONIX_4` for new builds unless
you have a specific reason to keep `BOARD_FOURTINY`. Confirm R50 is a
pull-down (not a series gate resistor) before powering up.

---

# Shared notes

## Power

**Do not power the ESP32 from the 78M05.** WiFi current peaks (300–500 mA)
dissipate ~3 W in a linear regulator fed from 12 V. Either:

1. Replace U1 with a pin-compatible switcher (OKI-78SR-5/1.5-W36-C, Traco
   TSR 1-2450) and feed the ESP32's **5V/VIN** from the board's 5 V rail, or
2. Add a small buck module (MP1584 / "mini-360" set to 5 V) from the 12 V
   input directly to the ESP32's **5V/VIN**, leaving the 78M05 to serve the
   original 5 V loads.

Never feed `+5V_BUF` into an ESP32 GPIO. The 3V3 pin powers only the
`JASNOSC` pull-up and any button pull-ups.

## Drive strength

At 3.3 V through 33 k base resistors the MPSA42 switches get ~80 µA of base
drive — enough for typical cathode current, but with less margin than at 5 V.
If a digit looks dim or ghosting appears, parallel the relevant 33 k with
another 33 k (or drop to 10 k). Most builds don't need this.

## Bring-up procedure

1. Set `BOARD` in the sketch. Wire everything **except** the `PWM` line.
   Ground the ATmega's RESET.
2. Power up. The ESP32 starts an access point **ElectroNIX-Setup** (password
   `nixie1234`). Connect, open `http://192.168.4.1`, enter WiFi and timezone,
   save — it reboots and joins your network as `http://electronix.local`.
3. Check the status bar: **HV** should read ≈0 V and duty should climb, then
   report *FAULT* after about a second — that's the sense-fault protection
   confirming the feedback wire on GPIO35 is being read. Power-cycle to clear.
4. Power off, discharge, connect the `PWM` wire (through the gate driver on
   IRF840 boards). Power on: HV should ramp to 170 V within a second and the
   tubes light. Measure the real voltage and set *HV sense trim* so the
   reported value matches.
5. Fix any digit or tube-order scrambling with **Pin check** as described in
   the electroNIX 4 section above.

## Settings and firmware updates

From **2.13.0** settings survive firmware updates — each setting lives under
its own NVS key, so a new version that adds a setting finds that key missing
and uses its default; everything else is read back untouched.

Use **Back up settings** and **Restore** before flashing anything
experimental or when setting up a second clock. The wiring order and per-tube
trims come along with it; the WiFi password is deliberately excluded.

## Running without NTP

Three fallbacks in order of accuracy:

1. **NTP** — shown as `time  NTP · 3m ago` in the status bar. Default poll
   interval 60 minutes, adjustable from 5 minutes to a day; *correct smoothly*
   slews rather than steps, so corrections never make seconds tubes skip.
2. **Browser sync** — opening the web page silently takes the time from your
   device if no network time is available. Works over the clock's own AP with
   no internet at all.
3. **Restored estimate** — written to flash hourly, shown as *estimated* in
   amber until a real sync arrives.

For a permanently offline clock, add a DS3231 — see below.

## Cleaning cycles

Nixie cathodes that rarely light can develop a haze; running them clears it.
Under *Maintenance*, set **Cleaning cycle** (how often, in minutes; 0 to
disable), **Cycle length** (1–60 seconds), and **Cycle style**:

- *Slot machine* — all tubes spin, then settle one at a time from the left.
- *Every digit in turn* — steps through 0–9 in equal slices, offset per tube.
  This one actually does the job: every cathode gets exactly the same
  conduction time.

## If the display flickers

**Check the status bar first.** The second line shows **core 0 / core 1**
load, **mux** (multiplex interrupt rate as a percentage of expected 40 kHz),
and **hv cuts**.

- **mux dips below 100%** — an interrupt stalled. From 2.15.0 the time
  snapshot is written to RTC memory (free, survives resets) and flash only
  every six hours, and that write waits for tubes-dark moments. If mux still
  dips, check that *Core Debug Level* is set to **None** in the IDE.
- **hv cuts climbing** — the boost regulator backed off on a noisy ADC sample.
  Check the HV sense trim calibration and the smoothing capacitors at the boost
  output (C2–C5 on the v4 schematic).

OTA updates deliberately blank the display for the transfer duration and then
reboot — a clean blank rather than a flicker is intentional.

**Arduino IDE settings that matter:**
- CPU Frequency: **240 MHz**
- Core Debug Level: **None**
- Erase All Flash Before Sketch Upload: **Disabled** (unless you want to lose settings)

## If the light sensor isn't doing anything

The status bar shows the sensor live as `light  1840 mV · 42%`. Watch it
while you cover the phototransistor.

1. **Reading says "railed" and never moves** — the 5 V pull-up mod hasn't
   been done. Lift the supply end of R63 (v4) / R11 (v2) / R57 (fourTINY) /
   R44 (v3) and rewire to ESP32 **3V3**.
2. **Reading moves but the tubes don't** — auto brightness must be ticked on.
   Also check that *min* and *max* aren't set to the same value.
3. **Moves over a narrow band** — calibrate using *use current as dark* and
   *as bright* in the web UI. A wider calibration span reduces the effect of
   ADC noise.
4. **Noisy reading** — add **100 nF ceramic** from GPIO34 to GND. This alone
   usually fixes it; the high-impedance pull-up can't recharge the ADC's
   sampling capacitor fast enough without it. Also consider lowering the
   pull-up from 1 M to 100 k, keeping the sensor wire short, and routing it
   away from the boost inductor.

---

# DS3231 real-time clock (optional, all boards)

A battery-backed DS3231 module lets the clock wake at the correct time
immediately after a mains outage without waiting for NTP. The status panel
shows **RTC** in green rather than *estimated* in amber.

## Enable in firmware

In `board.h`, above the `#define BOARD` line:

```c
#define BOARD_HAS_RTC 1
```

To override the default SDA/SCL pins:

```c
#define BOARD_RTC_SDA  0
#define BOARD_RTC_SCL 15
#define BOARD_HAS_RTC  1
```

## Default I2C pins

| Board family | SDA | SCL |
|---|---|---|
| All TESTA boards (4, 4+S, 3) | GPIO1 | GPIO3 |
| Nick2 IN-12 | GPIO21 | GPIO22 |

**4.7 kΩ pull-ups** from SDA to 3V3 and SCL to 3V3 are required. Most DS3231
breakout modules include them — check for R2/R3 on the silkscreen.

The DS3231 I2C pins are not strapping pins on any board. The 10 kΩ pull-up
requirements in the 4+S section above are for GPIO0 (buzzer) and GPIO15
(anode / LED backlight) — not for the I2C lines.

## Fit the CR2032 before powering up

Without it the DS3231 loses its time the moment the clock is unplugged. The
cell lasts several years in standby. When exhausted the DS3231 resets to
2000-01-01; the firmware detects this (year < 2020) and falls back to the NVS
epoch rather than displaying the year 2000.

## How it integrates with NTP

- **At boot**: the DS3231 is read before WiFi starts — the correct time
  appears within milliseconds, and `timeTrusted` is set immediately.
- **At NTP sync**: the DS3231 is updated to the NTP-corrected time.
- **Browser sync**: the posted epoch is written to the DS3231 and persists
  across power cuts — useful when NTP is blocked on your network.
- **No WiFi**: the DS3231 keeps time at ±2 ppm (≈ ±0.2 s/day) on the
  backup cell.

---

## Firmware safety features

- Boost gate is off during boot and flashing (GPIO2 boot pull-down).
- Software regulation: absolute duty clamp (~41 %), soft-start ramp, hard
  over-voltage cut at target + 12 V, shutdown if the feedback divider reads
  open — the converter will not run open-loop.
- HV shuts down whenever the tubes are off (night mode at 0 %, web toggle).
- 25 µs inter-digit blanking prevents ghosting between tubes.
