# electroNIX → ESP32 rewiring guide

Covers the TESTA-QUADRA boards this firmware supports:

| | **electroNIX 4** (PCB-061, 2014) | **electroNIX 4+S** (PCB-061 + seconds) | **electroNIX 3** (PCB-036, 2013) | **electroNIX 2** (PCB-030/031, 2013) | **fourTINY** (rev 11-11-2013) |
|---|---|---|---|---|---|
| Tubes | 4 × LC-513 / LC-531 | 4 × main + **2 × seconds (user-fitted)** | 4 × ZM1080T | 4 × Z566M + **2 × ZM1080T seconds** | 4 × LC-516 |
| Display | HH:MM | **HH:MM:SS** | HH:MM | HH:MM:SS | HH:MM |
| Anodes | W_1…W_4 | **W_1…W_6** | W_1…W_4 | W_1…W_6 | W_1…W_4 |
| Colon | 2 neons | **2 neons × 2 positions, in parallel** | 1 from factory, **2nd optional** (bodge) | 2 neons | 2 neons |
| Power in | 12 V DC jack | 12 V DC jack | **USB only, no 12 V rail** | 12 V DC jack | 12 V DC jack |
| Extras | IR receiver (OSRB38C9BA) | IR receiver (OSRB38C9BA) | — | 6 × LED under-tube backlight | spare `LED` net, no LED hardware |
| Boost switch | **IRLR3110Z** (logic-level) | **IRLR3110Z** (logic-level) | **IRLR3110ZPBF** (logic-level) | **IRF840** (*not* logic-level) | **IRF840** (*not* logic-level) |
| Sketch setting | `#define BOARD BOARD_ELECTRONIX_4` | `#define BOARD BOARD_ELECTRONIX_4_6T` | `#define BOARD BOARD_ELECTRONIX_3` | `#define BOARD BOARD_ELECTRONIX_2` | `#define BOARD BOARD_FOURTINY` |

Everything else is shared: ATmega16L-8AU, 32.768 kHz crystal, 33 k base resistors
on every driver, the same 430 k / 6.2 k HV feedback divider, and a `JASNOSC`
light sensor pulled up to +5 V. electroNIX 3 is the odd one out on power — see
its own section below rather than "Power — important" further down, which
is written for the three 12 V-jack boards.

The table above includes the **electroNIX 4+S**, which is the electroNIX 4
expanded with two seconds tubes. It gets its own section after the electroNIX 4
section — the three signal reassignments that free up the extra anode pins are
small enough to cover in a short table rather than a full board write-up.

There's also a proposed **electroNIX 2 USB** board further down — a six-tube,
USB-only hybrid of the electroNIX 2 and electroNIX 3 that hasn't been built
yet. Left out of the table above since it isn't a real board this firmware
"supports" so much as a design worked through in advance of one.

> ## ⚠️ 170 V is present on every board here
> The boost output and all the driver stages carry ~170 VDC, and the output
> capacitors hold charge after power-off (C2–C5 470 nF/250 V on the v4;
> C6–C9 470 nF/50 V plus C22 10 µF/350 V on the v2; C41–C44 470 nF/50 V on the
> v3). Unplug, wait, and verify with a meter before touching anything. Never
> rewire with power applied.

## Strategy: leave the ATmega in place, hold it in reset

You don't have to desolder the TQFP-44 on any of these boards. Grounding its
**RESET (pin 4)** puts every AVR pin into high-impedance, freeing all the driver
nets. One short wire from the RESET pad (or the ISP header JP1) to GND and the
chip is out of the picture.

Pick up the signals at the **resistors** they feed — larger pads, no fine-pitch
soldering. Every driver on every board here is an active-high NPN base behind a
series resistor, so 3.3 V logic drives them directly. No level shifters needed
on any output. The one exception is the boost gate on the electroNIX 2 and
fourTINY, below.

---

# electroNIX 2 (6 tubes, with seconds)

## Signal map

| Original net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | see the mapping table below — the designators are **not** in net order | 13, 14, 15, 21, 22, 23, 25, 26, 27, 32 | If digits come out scrambled, reorder `CATHODE_PINS[]` rather than resoldering. |
| `W_1`…`W_4` anodes (big tubes) | **R77, R74, R71, R53** (33 k) | 16, 17, 18, 19 | LAMP1–LAMP4, Z566M. |
| `W_5`, `W_6` anodes (seconds) | **R45, R42** (33 k) | 33, 5 | LAMP5–LAMP6, ZM1080T. |
| `SEC_0` (HH:MM colon) | **R15** (33 k) | 4 | |
| `SEC_1` (MM:SS colon) | **R18** (33 k) | **0** | Lifted from GPIO3, rewired to GPIO0. 10 kΩ pull-up to 3V3 required on GPIO0 — see below. |
| `LED` (backlight chain) | **R17** (33 k, base of Q3) | — | GPIO1 is now I2C SDA; disconnect R17 from GPIO1. The backlight cannot run simultaneously with the DS3231. |
| DS3231 SDA (optional) | I2C bus | **1** | 4.7 kΩ pull-up to 3V3. Same GPIO as every other TESTA board. |
| DS3231 SCL (optional) | I2C bus | **3** | 4.7 kΩ pull-up to 3V3. Same GPIO as every other TESTA board. |
| `PWM` (boost gate) | **R19** (10 Ω at Q5) | 2 | **Needs a gate driver — see the next section.** GPIO2's boot pull-down keeps the switch off during reset and flashing. |
| `KOMP_170V` (HV feedback) | junction of **R52 (430 k) / R51 (6.2 k)** | 35 (input) | ≈2.4 V at 170 V — direct to the ADC. Same divider as the v4. |
| `JASNOSC` (light) | junction of **R11 (1 M) / D7** | 34 (input) | ⚠️ R11 pulls up to **+5V_BUF**. Lift its 5 V end and rewire it to the ESP32's 3V3 pin (or fit a 2:1 divider) before connecting GPIO34. |
| `MEL` (buzzer) | **R12** (2 k, base of Q1) | 12 | GPIO12 must be low at boot; the base network holds it there. |
| Buttons S1–S3 | one switch leg | 36 (optional) | Needs an external 10 k to 3V3 — GPIO36 has no internal pull-up. |
| `ZANIK` (mains-loss detect), Y1 crystal, ISP header | — | unused | NTP and the ESP32's own clock replace them. |
| GND | any GND pad | GND | Required. |

### ⚠️ The cathode resistors are not numbered in net order

This trips people up: on the electroNIX 2 the ten 33 k cathode base resistors
run **R62, R63, R64, R65, R56, R57, R58, R59, R60, R61** for `C_0` through
`C_9`. Wiring R56 → the C_0 pin and counting upward gives a display that is
rotated by four digits. The actual mapping is:

| Net | C_0 | C_1 | C_2 | C_3 | C_4 | C_5 | C_6 | C_7 | C_8 | C_9 |
|---|---|---|---|---|---|---|---|---|---|---|
| Resistor | R62 | R63 | R64 | R65 | R56 | R57 | R58 | R59 | R60 | R61 |
| GPIO | 13 | 14 | 15 | 21 | 22 | 23 | 25 | 26 | 27 | 32 |

The electroNIX 4 numbering is scattered in the same way, so don't assume
ascending designators there either — check each resistor's net label on the
schematic, or just wire them in any order and sort it out with **Pin check**
below. The anodes are well behaved on both boards (v2: R77, R74, R71, R53,
R45, R42 = W_1…W_6).

### Sorting out a scrambled or offset display

You do not need to resolder anything. The web UI's **Maintenance → Pin check**
row holds a chosen digit on every tube for 15 seconds. Click `0`, see what the
tubes actually show, and write it down; repeat for a couple more digits until
the pattern is obvious. Then permute `CATHODE_PINS[]` to match — the array is
indexed by the digit you want, so entry *n* is simply "the GPIO that lights an
*n*".

Since firmware 2.4.0 you don't edit the sketch for this, and you don't have to
work out any mapping yourself. The web UI's **Wiring order** panel asks for the
one thing you can actually see:

1. In **Maintenance → Pin check**, click `0`. Note the digit the tubes really
   show. Repeat for `1` through `9`.
2. Type those ten observed digits into **Digits shown for 0–9** and save.
3. The display is now correct. Re-open the page and the field reads
   `0,1,2,…,9` again — which is the confirmation that nothing is left to fix.

**Tube positions work the same way.** *Pin check — tubes* has one button per
position, labelled `1 H`, `2 H`, `3 M`, `4 M` (and `5 S`, `6 S` on the six-tube
board). Click `1 H` and the firmware lights the single tube it believes is the
first hours digit, showing a `1` so there's no ambiguity; the rest stay dark.
Work along the row, note the physical order the tubes actually lit in, and type
that into **Tube positions**. A display that lights left to right in the order
you clicked needs `1,2,3,…` — i.e. no change.

Do the digits first if they're also scrambled: during a tube check the *digit*
shown still goes through the cathode mapping, so a wrong digit there is
expected and harmless — only which tube lights matters.

The firmware inverts and composes the mapping internally, so the procedure is
self-correcting: if you mistype, just observe the tubes again and enter the new
observation. There's no way to get permanently lost, and entering `0,1,…,9`
when everything is already right is a no-op. Tube order works the same way via
**Tube positions**, and there are one-click *digits +1 / −1 / reverse tubes*
buttons for the simple cases.

A list is only accepted if every digit appears exactly once; otherwise the page
tells you it was ignored. The stored mapping is shown read-only underneath if
you want to see what it worked out.

> **Earlier firmware (2.2.0–2.3.0) had this backwards.** The field asked for the
> mapping rather than the observation, so typing in what you saw applied the
> inverse of the needed correction and left the digits looking random. If you
> hit that, update to 2.4.0 and run the three steps above — no need to undo
> anything first, since the correction composes with whatever is stored.

## ⚠️ The IRF840 will not switch from 3.3 V

This is the one real electrical difference between the two boards. The v4 uses
an **IRLR3110Z** — an IRL-series logic-level MOSFET that switches fine on 3.3 V.
The v2 uses an **IRF840**, a standard-level part whose gate threshold alone can
be as high as 4 V and which is specified at Vgs = 10 V. It was already being
driven marginally by the AVR's 5 V; at 3.3 V it will either not turn on at all
or turn on partially and overheat. Do not skip this. Pick one:

1. **Add a gate driver (recommended).** A TC4420, MCP1407, or UCC27517 powered
   from the board's +12 V rail: ESP32 GPIO2 → driver input, driver output →
   R19 → Q5 gate. Non-inverting, so leave `#define HV_PWM_INVERT 0`.
2. **Discrete level shifter.** A 2N7002 with a pull-up to +12 V works and costs
   nothing, but it **inverts**. Set `#define HV_PWM_INVERT 1` in the sketch and
   the firmware inverts the duty cycle to match. Note this stage is slower than
   a real driver — check that Q5 doesn't run hot.
3. **Swap Q5** for a logic-level part with the same voltage rating. Genuinely
   logic-level 500 V FETs are uncommon, so options 1 and 2 are usually easier.

Bring this up **before** first power-on with the PWM line connected: a
half-enhanced MOSFET at 32 kHz is exactly how you cook one.

## DS3231 retrofit: why GPIO0 and a pull-up are needed

To give the DS3231 the same GPIO1/GPIO3 SDA/SCL as every other board, two wires
move and one is cut:

1. **Lift the SEC_1 wire from GPIO3 and solder it to GPIO0.** GPIO0 is the
   only free output-capable pin on the electroNIX 2.  It's a strapping pin:
   the ESP32 boot-mode sampler reads it at reset.  Without an external pull-up
   the 33 kΩ base load pulls it to ~1.8 V — below the 2.31 V HIGH threshold —
   which can cause random download-mode entry.
   **Fit a 10 kΩ resistor from GPIO0 to 3V3.**  With 10 kΩ the boot-time
   voltage is ~3.0 V, cleanly above threshold.

2. **Disconnect GPIO1 from the backlight chain** (cut or lift the wire to R17).
   GPIO1 becomes I2C SDA and can't simultaneously drive the LED chain.  If
   the backlight LEDs are not populated, there's nothing to disconnect.

GPIO1 and GPIO3 are then free for the DS3231 module, which connects with 4.7 kΩ
pull-ups to 3V3 on both lines (supplied by the module's on-board resistors on
most breakout boards).

> **If you want to keep the backlight**, the DS3231 can't use GPIO1/GPIO3 on
> this board.  The only alternative is GPIO0 (SDA) and GPIO15 (SCL), but
> GPIO15 is already used as cathode C_2 on the electroNIX 2, which would
> require a further cathode reassignment.  Realistically: either fit the RTC
> or keep the backlight, not both, unless you're willing to add a 74HC595 for
> the cathodes to free up GPIO15.

## Matching the small tubes to the big ones

The ZM1080T seconds tubes sit behind 6.2 k emitter resistors (R47, R41) while
the Z566M tubes use 2 k (R21, R23, R26, R28), so at equal duty the seconds
digits look dimmer. The web UI has a **per-tube trim** row — six percentages —
so you can even them out without touching the hardware. Start with the four big
tubes at 100 % and raise or lower tubes 5 and 6 by eye.

---

# electroNIX 2 USB (proposed — 6 tubes, USB-only power)

**Not a real board yet.** This is a design proposal, not a schematic being
converted — nothing below has been breadboarded, so treat every number here as
a starting point to verify, not a fact. It's a hybrid: six tubes and dual-neon
independent colons (SEC_0 = HH:MM, SEC_1 = MM:SS), powered the way the
electroNIX 3 is — USB only, no 12 V rail, a boost converter feeding a
diode-capacitor multiplier ladder up to 170 V. The GPIO assignments follow the
same "UART pins become extra anodes" approach as the electroNIX 4+S, so the
cathode digit order and neon colon GPIOs are shared across the whole non-backlight
TESTA family.

## Why this needs checking before you build it

Six tubes draw meaningfully more current at 170 V than electroNIX 3's four —
roughly 13 mA average at full brightness (4 main tubes at ~2.5 mA + 2 seconds
tubes at ~1.5 mA) against electroNIX 3's ~8-9 mA. Worked through a realistic
75-85 % boost+multiplier efficiency, that's **roughly 520-590 mA on the 5 V
rail for the HV side alone**, and **850-950 mA total** once you add the
ESP32's own WiFi burst current — against ~425 mA for electroNIX 3's four-tube
case. That's over what a plain USB 2.0 port (500 mA) can supply, and close to
the limit of a basic 1 A charger with the WiFi radio bursting.

**Use a proper 5 V/2 A power adapter, not a computer's USB port**, and budget
generous input bulk capacitance for the transient peaks. This is the single
most important thing to get right building this board — everything else here
is a normal TESTA-family design.

## Signal map (proposed)

Rather than copying the electroNIX 2's shuffled cathode layout, this board
uses the same pin assignment as the electroNIX 4+S: UART TX and RX become the
two extra anode outputs, and every other GPIO is identical to the 4-tube
electroNIX 4 and electroNIX 3. This makes the cathode digit order the same
across the entire non-backlight TESTA family.

| Net | ESP32 GPIO | Notes |
|---|---|---|
| `C_0`…`C_9` cathodes | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | **Identical** to the electroNIX 4 and electroNIX 3 — no digit-order surprises. |
| `W_1`…`W_4` anodes (main) | 16, 17, 18, 19 | **Identical.** |
| `W_5` anode (seconds tens) | **0** | GPIO0 — strapping pin. 10 kΩ pull-up to 3V3 required (see electroNIX 4+S section). |
| `W_6` anode (seconds units) | **15** | GPIO15 — strapping pin. 10 kΩ pull-up to 3V3 required. |
| `SEC_0` (HH:MM colon) | 4 | **Identical** to the electroNIX 4. |
| `SEC_1` (MM:SS colon) | **5** | **Identical** to the electroNIX 4 — SEC_1 is not displaced onto a UART pin. |
| `PWM` boost gate | 2 | **Pick a logic-level FET** (e.g. IRLR3110Z) — one less thing to get wrong on a board with no room for a gate-driver mistake. |
| `KOMP_170V` | 35 (input) | Same 430 k / 6.2 k divider as every other board. |
| `JASNOSC` | 34 (input) | Same 5 V pull-up caveat: feed from 3V3, not +5V_BUF. |
| `MEL` buzzer | 12 | |
| Button (optional) | 36 | External 10 k to 3V3. |

Flashing over USB and OTA both work normally despite serial being disabled —
the bootloader reclaims the UART pins at reset and OTA runs over WiFi.

> **Note on the bootloader TX pulse.** GPIO1 is driven briefly high by the
> bootloader on every reset. At 3.3 V through a 33 k base resistor with no
> 170 V on the rail yet, the tube cannot strike — no visible flash, no harm.

## Power: this is the electroNIX 3's story, scaled up

Same architecture as electroNIX 3 — see that section's Power write-up for the
detail on why a USB-fed boost+multiplier works at all and how to wire the
ESP32 into it (feed its 5V/VIN pin from `+5V_BUF`, never a GPIO). The parts
that need to scale up for six tubes instead of four:

- **Boost inductor**: size for at least 1.5-2× the current rating of
  whatever electroNIX 3 uses.
- **Multiplier ladder capacitors**: more current through the charge-pump
  chain means more sag per stage. Start around 2.2 µF instead of electroNIX
  3's 1 µF and check the ripple at 170 V is still acceptable — the diodes
  (10MQ100N-class, 1 A rated) have plenty of headroom regardless and don't
  need to change.
- **`HV_DUTY_MAX`** (the firmware's ~41 % duty ceiling, shared by every TESTA
  board): deliberately left unchanged in the sketch rather than guessed at.
  Expect this board to need more headroom than electroNIX 3 does, given the
  added current on top of an already 5 V-fed boost. Watch the `hv` and `duty`
  status fields on first power-up — if `duty` pins at the ceiling without `hv`
  reaching target, raise the constant in `display_testa.cpp` in modest steps
  and retest.
- **Tube current resistors**: depends on which tubes you actually use. If you
  reuse the electroNIX 2's Z566M/ZM1080T pairing, its 2 k / 6.2 k split is a
  reasonable starting point; for anything else, size from that tube's own
  rated current rather than copying those values blindly.

## Firmware — no back-end changes needed

`board.h` has a profile for this already (`BOARD_ELECTRONIX_2USB`). In
`display_testa.cpp` it shares a pin-map branch with `BOARD_ELECTRONIX_4_6T`
— the two boards have identical GPIO assignments, differing only in capability
flags (`BOARD_DUP_COLON 1` on the 4+S for its parallel colon wiring;
`BOARD_DUAL_NEON 1` here for independent HH:MM and MM:SS colons). The HV
loop, colon PWM, and multiplex ISR are unmodified. Rename
`BOARD_ELECTRONIX_2USB` to whatever this board ends up being called once it
has a real PCB number.

---

# fourTINY (4 × LC-516)

Electrically this is the electroNIX 4 with a 2013-era power stage, so it uses
the same GPIO map — **no firmware changes beyond `#define BOARD
BOARD_FOURTINY`**. What differs is where you tap and, importantly, the MOSFET.

| Original net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | **R21, R23, R26, R25, R22, R29, R30, R31, R27, R24** (33 k, in that order) | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | Scattered numbering again — the order above *is* C_0→C_9. |
| `W_1`…`W_4` anodes | **R8, R12, R16, R4** (33 k) | 16, 17, 18, 19 | |
| `SEC_0`, `SEC_1` colons | **R17, R18** (430–470 k) | 4, 5 | N1/N2 are NEON-5, as on the v4. |
| `PWM` boost gate | gate network at **Q50** | 2 | **IRF840 — gate driver required, see below.** |
| `KOMP_170V` | **R53 (430 k 1%) / R54 (6.2 k 1%)** junction | 35 (input) | Same divider ratio as the other boards, so no constant to change. |
| `JASNOSC` | **R57 (1 M) / D25** junction | 34 (input) | D25 is an HPTC3C-44J phototransistor. Same 5 V pull-up caveat: move R57's top end to 3V3. |
| `MEL` buzzer | **R55** (2 k, base of Q51) | 12 | |
| `LED` | MCU pin / header | 15 (optional) | The net is brought out but nothing drives LEDs on this board. If you add some, set `HAS_LED_BL 1` and the backlight controls appear in the web UI. |
| Buttons S1–S3 | switch leg | 36 (optional) | External 10 k to 3V3. |

## ⚠️ fourTINY has the IRF840 too

Q50 here is an **IRF840SPBF**, the same standard-level part as the electroNIX 2
— not the logic-level IRLR3110Z of the v4. It will not switch from 3.3 V. Fit a
gate driver from +12 V (TC4420 / MCP1407 / UCC27517), or an inverting 2N7002
stage with `HV_PWM_INVERT 1`. The sketch now refuses to build for either
IRF840 board until you set `HV_GATE_FITTED 1`, which is deliberate: it's easier
to change a #define than to replace a cooked MOSFET.

**Also check R50 (10 k) before you power up.** On the electroNIX 2 the series
gate resistor is a 10 Ω part (R19) with a separate 10 k pull-down. This board's
schematic shows only R50 at 10 k in the gate network, which is almost certainly
the pull-down — but confirm with a meter which way it sits. If it turns out to
be *in series* with the gate, replace it with ~10 Ω: 10 k against the IRF840's
~1.3 nF input capacitance is microseconds of switching time, hopeless at
32 kHz and a good way to overheat the FET.

## Tube current

The anode emitter resistors here are **15 k** (R5, R9, R13, R1), against 2 k on
the electroNIX 2's large tubes — the LC-516 is a small tube run at low current.
Nothing to change in firmware, but if the display looks dim, that's why, and
the per-tube trims in the web UI let you balance it rather than reworking
resistors.

# electroNIX 4 (4 tubes)

## Signal map

| Original net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | **R22–R31** (33 k) | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | |
| `W_1`…`W_4` anodes | **R15, R14, R17, R16** (33 k) | 16, 17, 18, 19 | |
| `SEC_0`, `SEC_1` colons | **R18, R19** (430 k) | 4, 5 | |
| `PWM` boost gate | **R59** (10 Ω at Q50) | 2 | Q50 is an IRLR3110Z — logic-level, drive it directly. |
| `KOMP_170V` | **R60 / R61** junction | 35 (input) | |
| `JASNOSC` | **R63 / D1** junction | 34 (input) | Same 5 V pull-up caveat: move R63's top end to 3V3. |
| `MEL` buzzer | **R62** (2 k) | 12 | |
| IR receiver (IR1) | IR1 pad | 39 (input, reserved) | Power IR1 from 3V3 rather than +5V_BUF. Not decoded yet. |
| Buttons S1–S3 | switch leg | 36 (optional) | External 10 k to 3V3 required. |

With only 17 outputs in use, GPIO1 and GPIO3 are free for the optional DS3231 RTC module.

---

# electroNIX 4+S (6 tubes, with seconds)

This is the electroNIX 4 expanded to six tubes by adding a seconds pair on the
right. The electrical design is identical — IRLR3110Z boost switch, 430 k /
6.2 k feedback divider, same anode and cathode driver topology — and the GPIO
map changes as little as possible: **every cathode, both neon colons, the HV
PWM pin, the buzzer, and the sensors stay on exactly the same GPIOs as the
4-tube board**.

## The two new anode pins

The electroNIX 4 already uses all 18 comfortable output-capable GPIOs on the
ESP32. The only remaining candidates are the two strapping pins, GPIO0 and
GPIO15. Freeing the UART pins (GPIO1/GPIO3) for I2C moves W_5 and W_6 onto
those instead.

| Role on electroNIX 4 | GPIO | Role on electroNIX 4+S |
|---|---|---|
| Unused (strapping pin) | **0** | Anode `W_5` (seconds tens tube) |
| Unused (strapping pin) | **15** | Anode `W_6` (seconds units tube) |
| Free (UART TX) | 1 | DS3231 RTC SDA (or free if no RTC fitted) |
| Free (UART RX) | 3 | DS3231 RTC SCL (or free if no RTC fitted) |

`SEC_0`, `SEC_1`, and all ten cathodes stay exactly where they were.

## Required pull-ups on GPIO0 and GPIO15

The 33 kΩ base resistor on each new anode loads GPIO0 and GPIO15 enough that
the ESP32's internal pull-up (~45 kΩ) cannot guarantee a clean HIGH for the
boot-mode strapping sampler at reset.  Without external pull-ups, the voltage
at those pins at reset is roughly 1.8 V — below the 2.31 V HIGH threshold —
which can randomly enter download mode.

**Fit 10 kΩ resistors from GPIO0 to 3V3 and from GPIO15 to 3V3.**  These are
permanent board components, independent of whether a DS3231 module is fitted.
With 10 kΩ, the boot-time voltage is ~3.0 V — safely above threshold.

## Signal map

| Net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | **R22–R31** (33 k), same as electroNIX 4 | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | **Identical to the 4-tube board** — digit order preserved. |
| `W_1`…`W_4` anodes (main) | **R15, R14, R17, R16** (33 k), same as electroNIX 4 | 16, 17, 18, 19 | **Identical.** |
| `W_5` anode (seconds tens) | 33 k base resistor for new seconds tube driver | **0** | GPIO0 — strapping pin; 10 kΩ pull-up to 3V3 required (see above). |
| `W_6` anode (seconds units) | 33 k base resistor for new seconds tube driver | **15** | GPIO15 — strapping pin; 10 kΩ pull-up to 3V3 required. |
| `SEC_0` (top neon, both positions) | **R18** (430 k), same as electroNIX 4 | 4 | **Identical.** Drives top neon at both colon positions in parallel — see below. |
| `SEC_1` (bottom neon, both positions) | **R19** (430 k), same as electroNIX 4 | 5 | **Identical.** Bottom neon at both positions, in parallel. |
| `PWM` boost gate | **R59** (10 Ω at Q50) | 2 | IRLR3110Z, logic-level. Identical. |
| `KOMP_170V` | **R60 / R61** junction | 35 (input) | Identical. |
| `JASNOSC` | **R63 / D1** junction | 34 (input) | Same 5 V pull-up caveat: move R63's top end to 3V3. Identical. |
| `MEL` buzzer | **R62** (2 k) | 12 | Identical. |
| DS3231 SDA (optional) | I2C bus | 1 | Same GPIO as every other TESTA board. 4.7 kΩ pull-up to 3V3. |
| DS3231 SCL (optional) | I2C bus | 3 | Same GPIO as every other TESTA board. 4.7 kΩ pull-up to 3V3. |
| Buttons S1–S3 | switch leg | 36 (optional) | Identical. |

## Colon wiring: both positions in parallel

The seconds pair adds a colon gap between MM and SS. Wire both positions to the
existing `SEC_0` / `SEC_1` drivers in parallel — no new driver circuitry needed:

```
R18 → SEC_0 driver (GPIO4) → top neon at HH:MM gap
                           → top neon at MM:SS gap   (both cathodes on the same net)

R19 → SEC_1 driver (GPIO5) → bottom neon at HH:MM gap
                           → bottom neon at MM:SS gap
```

Both positions blink, breathe, and alternate in perfect lockstep. The firmware's
`applyColon()` is unchanged — it drives GPIO4 and GPIO5 exactly as it did on the
4-tube board. ALTERNATE steps the top neons on, then the bottom neons on, across
both positions simultaneously. The web UI emits a `cap-dupcolon` flag for this
board so the preview mirrors the HH:MM dot states onto MM:SS rather than tracking
them independently.

## Flashing

`Serial.begin()` is skipped on this build (as on every other board). Flashing
over USB and OTA both work normally. The bootloader briefly drives GPIO1 (TX)
as UART output at reset; GPIO1 is now the I2C SDA line, so this produces a
harmless glitch on the I2C bus before `Wire.begin()` is called.

## Matching the seconds tubes to the main tubes

The seconds tubes may be physically smaller and sit behind different emitter
resistors. Use the **per-tube trim** row in the web UI (six percentages) to even
them out. Start the four main tubes at 100 % and adjust tubes 5 and 6 by eye
until they match.

## Power

Identical to the electroNIX 4 — 12 V DC jack, 78M05 regulator, same boost
circuit. See **Shared notes for the 12 V-jack boards** for the power supply and
drive-strength guidance. If `hv cuts` rises with six tubes where it didn't with
four, add one or two extra smoothing capacitors at the boost output (same type
and value as C2–C5 on the v4 schematic).

---

# electroNIX 3 (4 tubes, single colon neon — optionally two)

Close electrical relative of the electroNIX 4 — same tube count, same
logic-level **IRLR3110ZPBF** boost switch, no gate driver needed — but two
things are genuinely different, not just relabelled:

1. **Only one colon neon from the factory.** `N1`/`SEC_0` are the only colon
   net and lamp on this schematic; there's no `N2` or `SEC_1` anywhere. The
   firmware defaults to treating this board as single-neon: SEC_0 does double
   duty, rendering the configured colon mode normally and taking over with the
   "time not trusted" warning blink instead of that warning being invisible.
   `ALTERNATE` mode has nothing to alternate with on one lamp, so it falls
   back to acting like `STEADY`. **You can add a second one** — see the bodge
   below — and tell the firmware about it without reflashing.
2. **No 12 V rail at all.** See "Power" below — this is the one board here
   that genuinely runs from a single USB connection.

## Adding a second neon (SEC_1) — optional bodge

The firmware already has GPIO5 reserved for it — the same convention as
electroNIX 4 and fourTINY — so this is a hardware-only change, no different
`BOARD` setting required. To add it:

1. **Build a second driver identical to the existing one**: a 430 k base
   resistor into an MMBTA42 (or equivalent small NPN), collector to the new
   neon's cathode, neon's anode through another 430 k up to the 170 V rail —
   mirror R20/Q15/N1 exactly.
2. **Route the new driver's control line to the ATmega's PB1 pad (pin 41).**
   That pin is unused in the stock design and, with the ATmega held in reset
   the same way as every other signal on this board, it's just a convenient,
   otherwise-dead pad to land a wire on rather than finding space elsewhere on
   the board. It has no special electrical meaning here — you could equally
   solder directly to the new transistor's base resistor.
3. **Run a wire from that pad to ESP32 GPIO5.**
4. **In the web UI, under Display, tick "Second colon neon fitted."** That's
   the only software step — see below.

## The runtime toggle

Rather than a firmware setting that's fixed at flash time, whether SEC_1
exists is a config option: **Display → Second colon neon fitted**, only shown
on this board (every other dual-neon board has SEC_1 soldered on at the
factory, so there's nothing to ask there). Leave it off for a stock board;
tick it once you've done the bodge above, and `applyColon()` in
`display_testa.cpp` switches over to the normal two-lamp behaviour — genuine
`ALTERNATE`, and the "time not trusted" warning moves from SEC_0 to a
dedicated SEC_1 — without a rebuild.

## Signal map

| Original net | Tap point | ESP32 GPIO | Notes |
|---|---|---|---|
| `C_0`…`C_9` cathodes | **R4, R5, R1, R2, R6, R7, R8, R9, R10, R3** (33 k, in that order) | 13, 14, 21, 22, 23, 25, 26, 27, 32, 33 | Scattered numbering, same as every other board here — the order above *is* C_0→C_9. Confirm with **Pin check** before trusting it. |
| `W_1`…`W_4` anodes | **R25, R22, R21, R14** (33 k) | 16, 17, 18, 19 | |
| `SEC_0` colon | **R20** (430 k) | 4 | N1 is a NEON-2 RED. |
| `SEC_1` colon (optional) | new bodge, see above | 5 | Not on the stock board. Tick **Second colon neon fitted** once wired, or leave the toggle off and this pin simply never gets driven. |
| `PWM` boost gate | **R33** (10 Ω) at Q20, **R45** (10 k) pull-down | 2 | Q20 is an IRLR3110ZPBF — logic-level, drive it directly, same as the v4. |
| `KOMP_170V` | **R43 (430 k) / R42 (6.2 k)** junction | 35 (input) | Same divider ratio as every other board, so no constant to change. |
| `JASNOSC` | **R44 (1 M) / D20** junction | 34 (input) | D20 is an HPDB3J-44DA phototransistor. Same 5 V pull-up caveat as elsewhere: move R44's top end to 3V3. |
| `MEL` buzzer | **R34** (2 k, base of Q21) | 12 | |
| Buttons SET / PLUS / MINUS (S1/S3/S2) | switch leg | 36 (optional) | These were the original firmware's on-board clock-set buttons; wire one up the same as any other board's buttons if you want `btnEn`, otherwise leave them. |

## Power — this board runs from USB alone

Every other board in this guide has a 12 V DC barrel jack, a 78M05 linear
regulator making 5 V from it, and a boost converter that also runs from that
12 V. electroNIX 3 has none of that: there's no DC jack anywhere on the
schematic, only a **USB micro-B** connector, fused (F1) straight into
`+5VZAS`. That 5 V rail is all the board has, and it's what the HV boost
(`L2`/`Q20`) runs from directly — helped along by a diode-capacitor
multiplier ladder (`D11`–`D18`, `C3`–`C9`) between the boost stage and the
170 V rail, which does part of the voltage step-up so the switching stage
itself doesn't have to reach the full 34× gain in one hop.

That makes the ESP32 side of this **simpler** than the other boards, not
harder — the "don't power the ESP32 from the 78M05" warning in the shared
Power section doesn't apply here, because there's no lossy 12 V→5 V linear
step in the path to begin with:

- Feed the ESP32 devkit's **5V/VIN pin** from `+5V_BUF` (the filtered,
  diode-isolated copy of the USB rail — D19 plus the bulk caps and supercap
  C55) rather than raw `+5VZAS`. Either works electrically, but `+5V_BUF` is
  already protected against whatever's happening on the USB input.
- One USB cable, one power rail, everything on it including the ESP32 — no
  regulator swap, no separate buck module, nothing to add.
- If you'd rather keep the boards' power paths completely separate for any
  reason (debugging, isolating noise), there's nothing wrong with giving the
  ESP32 devkit its own USB cable into its own port instead of tapping
  `+5V_BUF` — still "just USB", just two connections instead of one.
- As always, never feed `+5V_BUF` or `+5VZAS` into an ESP32 **GPIO**. The 3V3
  pin is only for the JASNOSC pull-up and any button pull-up.

**One thing to watch during bring-up, not something to pre-emptively change:**
reaching 170 V from a 5 V input needs a higher duty cycle than the other
boards' 12 V-fed boost converters do, even with the multiplier ladder sharing
some of the load. The firmware's absolute duty ceiling
(`HV_DUTY_MAX` in `display_testa.cpp`, ~41 % of the PWM range, same constant
on all four boards) was sized around the 12 V boards and may or may not leave
this one enough headroom to actually reach 170 V. Watch the status bar's `hv`
and `duty` fields the first time you power it up:
- If `duty` settles below the ~41 % ceiling once `hv` reaches your configured
  target, it has headroom to spare and nothing needs to change.
- If `duty` pins at the ceiling and `hv` never gets there (or `hvFault`
  trips), raise `HV_DUTY_MAX` in `display_testa.cpp` in modest steps and
  retest — there's no way to derive the right number from the schematic
  alone, since it depends on the multiplier ladder's actual efficiency at
  your build's real component tolerances.

---

# Shared notes for the 12 V-jack boards

The electroNIX 3 is covered above and doesn't need anything in this section —
it has no 78M05, no 12 V input, and nothing to swap. This applies to the
electroNIX 4, electroNIX 4+S, electroNIX 2, and fourTINY.

## Power — important

**Do not power the ESP32 from the 78M05.** It is a linear regulator fed from
12 V; a WiFi ESP32 draws 300–500 mA peaks, which would dissipate ~3 W in it.
Either:

1. **Replace U1** with a pin-compatible switcher (OKI-78SR-5/1.5-W36-C, Traco
   TSR 1-2450) and feed the ESP32's 5V/VIN pin from the board's 5 V rail, or
2. **Add a small buck module** (MP1584 / "mini-360" set to 5 V) from the 12 V
   input to the ESP32's 5V/VIN pin, leaving the 78M05 to serve the original
   5 V loads only.

Never feed +5V_BUF into an ESP32 GPIO. The 3V3 pin powers only the JASNOSC
pull-up and, on the v4, the IR receiver and any button pull-up.

## Drive strength

At 3.3 V through 33 k base resistors the MPSA42 switches get ~80 µA of base
drive — enough for the few mA of cathode current with typical gain, but with
less margin than at 5 V. If a digit looks dim or you see faint ghosting,
parallel the relevant 33 k with another 33 k (or drop it to 10 k). Most boards
won't need it.

## What the original firmware confirmed

Disassembling `electroNIXclock_4xLC531_23102017_Slot_Machine.hex` (14.1 KiB of
the ATmega16's 16 KiB, AVR-GCC, stack top 0x045F = 1 KiB SRAM) settled the
things the schematics leave open, and those findings apply to both boards since
they share an MCU and a peripheral layout:

| Finding | Consequence for this port |
|---|---|
| Only TIMER2_OVF, TIMER0_OVF and ADC vectors populated | Timer2 ran async off the 32.768 kHz crystal as a 1 Hz RTC; Timer0 was the multiplexer; the ADC ISR did the sensing. Same split here, with NTP replacing the RTC. |
| `TCCR0 = 0x04` (÷256), `TCNT0` reloaded to 0xFF | Multiplex tick ≈32 µs. This firmware uses 25 µs so that a 100 Hz frame divides evenly across 4 *or* 6 tubes. |
| `ADMUX` alternating 0x07 / 0x06 | ADC7 = `JASNOSC`, ADC6 = `KOMP_170V` — both taps above are the ones the original used. |
| Timer1 fast PWM on OC1A, ICR1 top, no prescaler | The converter ran at ~30 kHz. Hence 32 kHz here rather than an invented number. |
| `DDRA/DDRC/DDRD` = 0x3F / 0xFF / 0xFF | Cathodes split across PORTA and PORTD, anodes plus `MEL` on PORTC — matches both schematics' nets. |
| EEPROM (EECR/EEAR/EEDR) accesses | Settings lived in EEPROM; here they live in ESP32 NVS and are editable over the web. |

That hex is the LC-531 build of the v4; the tube type is the only difference.

## About the PCB artwork

`PCB-061_electroNIX-4_-_prasowanka_TOP/BOT.pdf` are toner-transfer copper
artworks: two layers, ~132 × 96 mm of routing, **no silkscreen and no reference
designators**. Use the schematic to find R59 or R15, and the artwork to confirm
the trace you're about to tap. Printed at 1:1 (mirrored, as transfer artwork is)
it lays over the board nicely for following a track.

## A note on building the sketch

The multiplex ISR writes the GPIO output registers directly for speed, which
needs the low-level register definitions that `Arduino.h` doesn't always pull
in. The sketch includes them itself:

```cpp
#if __has_include(<hal/gpio_ll.h>)
  #include <hal/gpio_ll.h>
#endif
#include <soc/gpio_struct.h>
```

If your core version wants only one of the two, the guard sorts it out.

## Bring-up procedure

1. Set `BOARD` in the sketch. Wire everything **except** the `PWM` line, and
   ground the ATmega's RESET.
2. Power up. The ESP32 starts an access point **ElectroNIX-Setup**
   (password `nixie1234`). Connect, open `http://192.168.4.1`, enter WiFi and
   timezone, save — it reboots and joins your network as
   `http://electronix.local`.
3. Check the status bar: **HV** should read ≈0 V and duty should climb, then
   report *FAULT* after about a second — that's the sense-fault protection
   proving the feedback wire on GPIO35 is being read. Power-cycle to clear.
4. Power off, discharge, connect the `PWM` wire (**on the v2, through the gate
   driver**). Power on: HV should ramp smoothly to 170 V within a second and
   the tubes light. Measure the real voltage and set *HV sense trim* so the
   reported value matches (trim = measured ÷ reported).
5. Fix any digit or tube-order scrambling in `CATHODE_PINS[]` / `ANODE_PINS[]`,
   then even out the tube brightness with the per-tube trims.

## Settings and firmware updates

From **2.13.0** settings survive firmware updates. Each setting lives under its
own NVS key named after its field, so a new version that adds a setting simply
finds that one key missing and uses its default — everything else is read back
untouched.

Earlier versions (2.0.0–2.12.0) stored the whole settings struct as a single
blob and had to discard it whenever the struct changed size, which is why
updates kept resetting the display settings. **2.13.0 is the last update that
resets anything**; it starts from defaults once as it migrates to the new
layout, then keeps them from there on. WiFi credentials are unaffected, as
they have been since 2.0.1.

There are also **Back up settings** and **Restore** buttons at the top of the
page. The backup is a small JSON file, useful before flashing something
experimental or when setting up a second clock — the wiring order and per-tube
trims come along with it, so a replacement ESP32 can be configured in one go.
The WiFi password is deliberately excluded from the export.

## Running without NTP

The ESP32 has no battery-backed clock, so from firmware 2.6.0 there are three
fallbacks in order of accuracy:

1. **NTP**, whenever the clock can reach the internet. The status bar reads
   `time  NTP · 3m ago`, so you can always see how stale the sync is. The poll
   interval is set under *Time & NTP* — **60 minutes** by default, adjustable
   from 5 minutes to a day, with a **sync now** button next to it. Hourly is
   ample: the ESP32 drifts by a couple of seconds a day, so it can only be a
   fraction of a second out between polls. Note that firmware before 2.9.0 had
   no setting and used the SNTP default, which is also one hour.
   **Correct smoothly** (on by default) slews the clock with `adjtime` instead
   of stepping it, so a correction never makes the seconds tubes skip or repeat
   a digit; offsets beyond about 35 minutes are stepped regardless.
2. **Browser sync.** Open the web page and, if the clock has no network time,
   it silently takes the time from the device you're browsing with — good to a
   fraction of a second. There's also a **Set time from this device** button to
   do it on demand. This works over the clock's own access point with no
   internet at all: connect a phone to **ElectroNIX-Setup**, open
   `http://192.168.4.1`, and the clock is set. Your POSIX timezone string still
   does the local-time and DST work, so set that correctly first.
3. **Restored estimate.** The time is written to flash once an hour and
   reloaded at boot, so after a power cut the tubes light immediately rather
   than sitting on the searching animation. It will be behind by roughly the
   length of the outage, and the status bar shows `estimated` in amber until a
   real sync replaces it.

Free-running accuracy between syncs comes from the ESP32's 40 MHz crystal —
expect a couple of seconds of drift per day, which NTP erases on every
reconnect. For a clock that's meant to live permanently offline, add a DS3231
module on any two spare GPIOs (there's room on the four-tube board; the
six-tube build would need the 74HC595 cathode option first to free up pins).
The original board's supercap (C15 on the v2, C9 on the v4) backed up the
ATmega's crystal RTC and can't help the ESP32 here.

## Cleaning cycles

Nixie cathodes that never light develop a haze over years of use, and running
them clears it. Three settings under *Maintenance* control this:

- **Cleaning cycle** — how often, in minutes. `0` disables it. The cycle is
  skipped whenever the tubes are dark, so night mode isn't interrupted.
- **Cycle length** — how long the digits keep moving, 1 to 60 seconds. There's
  a **try it** button next to it so you can watch the effect while adjusting.
- **Cycle style**:
  - *Slot machine* — all tubes spin, then settle one at a time from the left.
    The settle timing scales with the length you chose, so a longer cycle
    spins longer rather than just pausing at the end.
  - *Every digit in turn* — steps through 0–9 in ten equal slices, offset per
    tube. Less of a party trick, but it's the one that actually does the job:
    every cathode gets exactly the same conduction time, which a random spin
    doesn't guarantee.

If you're running this for maintenance rather than looks, the thorough style
for 10–20 seconds a few times a day does more good than a two-second flourish
every twenty minutes.

## If the display flickers

Occasional flicker is background work stealing time from the multiplex
interrupt, and firmware 2.7.0 removes the three causes:

- **Spinlocks in the main loop.** The display state used to be guarded by a
  critical section, and taking one masks interrupts on that core — including
  the multiplex ISR. Each tube's state is now packed into a single 32-bit word,
  which the ESP32 stores atomically, so the ISR reads a consistent snapshot
  with no lock at all.
- **Networking on the display's core.** The web server, DNS and OTA handling
  used to run in `loop()` on core 1, alongside the display interrupt. They now
  run in their own task pinned to core 0 next to the WiFi stack, leaving core 1
  with almost nothing to do but feed the tubes. Loading the web page or pushing
  an OTA update no longer disturbs the display.
- **Flash writes.** Saving settings or the hourly time snapshot disables the
  flash cache for a few milliseconds. The ISR was already in IRAM, but the mask
  arrays it reads are now `DRAM_ATTR` too, so nothing it touches can be stalled
  by a write. WiFi modem sleep is also disabled, since it wakes the radio in
  bursts that were visible on the tubes.

The status bar carries a second line to check all this against: **core 0** and
**core 1** load, **mux** and **heap**. Core 0 carries networking and the HV
regulator, core 1 the display. The *mux* figure is the one that matters for
flicker — it's the measured multiplex interrupt rate as a percentage of the
expected 40 kHz, so a steady `100%` means no ticks are being missed, and it
turns amber if it strays. Watch it while loading the page or running an OTA.

The core loads are approximate: they're derived from per-core idle-task counts
measured against the busiest-idle second the clock has seen, so treat them as a
relative indicator rather than a calibrated figure.

### Flicker during an OTA is a different problem

Core pinning cannot fix this one, and there's no Arduino IDE setting that
enables it either — the dual-core split is done in the sketch (tasks pinned
with `xTaskCreatePinnedToCore`) and is already active.

Writing firmware to SPI flash disables the flash cache **on both cores** for
each erase and program cycle, tens of milliseconds at a time. Any interrupt
whose handler isn't entirely IRAM-resident is deferred for that window. Our ISR
is `IRAM_ATTR` and its data is `DRAM_ATTR`, but the Arduino timer dispatcher
that calls it isn't IRAM-safe in the stock core, so the multiplex stalls
regardless.

Worse than the flicker: a stall can freeze the multiplex mid-slot, leaving one
cathode conducting continuously at full duty — a good way to poison a digit
over a long update.

So since 2.10.0 the display is deliberately **parked** for the transfer: one
beep, tubes and colons blank, backlight off, HV shut down, then the clock
reboots into the new firmware. A failed update beeps three times and restores
the display instead. A clean blank reads as intentional, and nothing is at risk
while the flash is busy.

The same applies in miniature to saving settings, but an NVS write is a couple
of milliseconds rather than half a minute, so it isn't worth parking for.

### Board settings that do matter

Nothing here is about cores, but check these in the IDE:

- **CPU Frequency: 240 MHz.** At 80 MHz the 40 kHz ISR has far less headroom.
- **Core Debug Level: None.** Verbose logging writes to the UART from
  interrupt-adjacent code; on most boards GPIO1 and/or GPIO3 are display
  outputs, so enabling this will corrupt the display or cause erratic behaviour.
- **Erase All Flash Before Sketch Upload: Disabled**, unless you want to lose
  your saved settings.
- If your board menu offers **Arduino Runs On**, leave it at Core 1 — the
  sketch assumes `loop()` is off the WiFi core.

### An occasional whole-display blink

A brief blink of everything at once, every so often, has two likely causes, and
the status bar now tells you which. Watch **mux min** (the worst one-second
multiplex rate since boot) and **hv cuts**:

- **mux min dips below 100%** → the display interrupt was stalled. Writing to
  flash disables the flash cache for a few milliseconds, and the Arduino timer
  dispatcher isn't IRAM-resident, so the multiplex freezes for the duration.
  Until 2.15.0 the clock committed its time to flash **every hour**, which fits
  an occasional blink almost exactly. Now the time lives in RTC memory (free,
  and it survives resets and OTA reboots), flash is written only every six
  hours, and even that write waits for a moment when the tubes are dark or a
  cleaning cycle is already running.
- **hv cuts climbing** → the boost regulator backed off. The old loop cut the
  duty to zero the instant a single ADC sample read high, and the ESP32's SAR
  ADC does throw the occasional wild sample — amplified 70× by the feedback
  divider, one glitch looks like tens of volts. Recovery then ramped back over
  hundreds of milliseconds, which is exactly a visible dip on every tube. The
  loop now takes a trimmed mean of four samples, requires the over-voltage to
  persist across three readings, and backs off to 70% of duty instead of zero.
  If this counter still climbs, the HV really is overshooting: check the sense
  trim calibration and the smoothing capacitors.

Both counters should sit at `100%` and `0`. They're cleared by a restart.

If flicker persists outside OTAs while *mux* stays at 100%, the remaining
suspects are electrical rather than software: check the HV smoothing capacitors (C6–C9 on the v2, C2–C5 on the v4)
and confirm the ESP32 isn't being fed from the 78M05, whose sag under WiFi
current peaks shows up as a brightness wobble.

## If the light sensor isn't doing anything

The status bar shows the sensor live as `light  1840 mV · 42%` — raw ADC volts
and the level derived from your calibration. Watch that number while you cover
the tube with your hand. Then work down this list:

1. **The reading says "railed" (above ~3050 mV) and never moves.** This is the
   usual one, and it means the 5 V pull-up mod hasn't been done. `JASNOSC` is
   pulled to **+5V_BUF** through R11 (v2) / R63 (v4), so in anything short of
   direct sunlight the node sits well above the ESP32's 3.3 V input range and
   the ADC just clamps at full scale. Lift that resistor's supply end and
   rewire it to the ESP32's **3V3** pin — or, if you'd rather not lift it, add
   a divider (e.g. 100 k from the node to GND) so the swing lands under 3.3 V.
   The 1 M series resistance means the pin isn't being damaged meanwhile, but
   it will never read anything useful.
2. **The reading moves but the tubes don't.** Auto brightness has to be ticked
   on — with it off, the sensor is shown but ignored, which is easy to miss.
   Also check that *min* and *max* aren't set to the same value.
3. **It moves the wrong way, or only over a narrow band.** Calibrate it:
   cover the sensor and click **use current as dark**, shine a lamp on it and
   click **as bright**. Each capture is stored immediately and the two number
   fields update to match. The firmware interpolates between whatever two
   values you capture, and it copes with either polarity — if your sensor reads
   higher in the light, capturing the points that way round simply works.

   *(Firmware before 2.14.0 had a bug here: the capture was saved, but the two
   number fields on the page still held the old values, so the next press of
   **Save settings** posted them straight back over the calibration. If your
   calibration kept reverting, that was why.)*
4. **The reading wanders and the tubes pulse with it.** Two things cause this,
   both handled since 2.16.0. The sensor is filtered more slowly (about a
   five-second time constant), and auto brightness now has a 2% deadband and a
   slew limit of roughly 5% per second, so small wobble is ignored and real
   changes arrive gently. That also breaks the optical feedback path — the
   tubes light the room the sensor is measuring, so a fast loop can chase its
   own output.

   The other half is the calibration span, now shown next to the calibration
   fields. If dark and bright readings are only a couple of hundred millivolts
   apart, ordinary ADC noise becomes a large fraction of the range: simulated
   at 18 mV of noise, a 250 mV span swung brightness by about 5%, against 0.6%
   for a 2500 mV span. If yours reads narrow, adjust the sensor's pull-up so
   the swing uses more of the ADC range, and recapture both points.

### Taming sensor noise

The status bar shows **sensor noise** as the peak-to-peak spread of sixteen raw
conversions, in millivolts. Under about 20 mV is fine; it turns amber above
60 mV. Firmware 2.17.0 already oversamples sixteen times and discards the
extremes, but that only cleans up what arrives — these are the fixes at the
hardware end, in the order worth trying:

1. **Add a capacitor from the ADC pin to ground.** This is the big one and it's
   one part. `100 nF` ceramic right at GPIO34, or `1 µF` for more filtering.
   The ESP32's SAR ADC charges a small sampling capacitor from whatever it's
   connected to, and behind a 1 M pull-up (R57 / R11 / R63 depending on board)
   there's nowhere near enough current to settle it — that alone accounts for
   most of the noise. A local capacitor supplies the sampling charge instead.
   With 1 M and 100 nF the node's time constant is around 50 ms, which is
   nothing for ambient light.
2. **Lower the pull-up.** The ESP32 wants to see a source impedance in the tens
   of kilohms, not megohms. Replacing that 1 M with **100 k** cuts it tenfold
   and stiffens the node considerably. It shifts both calibration points, so
   recapture dark and bright afterwards — and it widens the swing, which the
   calibration-span readout will show.
3. **Move the wire.** The boost converter switches at 32 kHz a few centimetres
   away, and the sensor lead is a high-impedance antenna. Keep it short, route
   it away from the inductor, the MOSFET drain and the tube anode leads, and
   run it alongside a ground wire (twisted, if it's flying).
4. **Watch the ground return.** If the sensor's ground shares a path with the
   HV switching current, the switching ripple appears directly in your reading.
   Take the sensor's ground from a quiet point near the ESP32 rather than near
   the converter.

Steps 1 and 2 together typically bring the reading to a couple of millivolts of
spread, at which point auto brightness is rock steady.

5. **Still nothing.** Check the phototransistor's orientation (D7 on the v2,
   D1 on the v4 — they're polarised), and confirm your tap is on the
   resistor/sensor junction rather than on the supply side of the resistor.

# DS3231 real-time clock module (optional, all boards)

Fitting a battery-backed DS3231 module lets the clock wake up at the correct
time immediately after a mains power cut, without waiting for a WiFi connection
or an NTP sync.  It connects over I2C, needs only two GPIOs plus 3V3 and GND,
and the firmware treats its reading as trusted — the status panel shows **RTC**
in green on boot rather than "estimated" in amber.

## Enable in firmware

In `board.h`, add one line **above** the `#define BOARD ...` line:

```c
#define BOARD_HAS_RTC 1
```

That's it.  Serial is already disabled on every board, so no other flag needs
changing.  To override the default SDA/SCL pins, add the overrides first:

```c
#define BOARD_RTC_SDA  0   // example: use GPIO0 instead of the default
#define BOARD_RTC_SCL 15
#define BOARD_HAS_RTC  1
```

## Default I2C pin assignments

| Board | SDA | SCL | Notes |
|---|---|---|---|
| All TESTA boards | GPIO1 | GPIO3 | See per-board sections for extra pull-up requirements. |
| Nick2 IN-12 | **GPIO21** | **GPIO22** | Standard ESP32 I2C pins — free, no strapping-pin issues. |

## Wiring

**TESTA boards:**
```
DS3231 module      ESP32
─────────────      ─────
VCC          →     3V3
GND          →     GND
SDA          →     GPIO1
SCL          →     GPIO3
```

**Nick2 IN-12:**
```
DS3231 module      ESP32
─────────────      ─────
VCC          →     3V3
GND          →     GND
SDA          →     GPIO21
SCL          →     GPIO22
```

**4.7 kΩ pull-up resistors** from SDA to 3V3 and from SCL to 3V3 are required
on all boards.  Most DS3231 breakout modules include them — check the silkscreen
for `R2`/`R3` before adding external ones.

## Nick2 note: no complications

GPIO21 and GPIO22 are not strapping pins, not used by any existing Nick2
circuit, and not shared with the WS2812 chain (which is on GPIO3).  Just wire
the module and set `BOARD_HAS_RTC 1`.  The untrusted-time warning — the bottom
LED of the colon column blinking — will stop immediately on boot once the DS3231
provides a valid time, since `core_timeTrusted()` returns true for `SRC_RTC`.

## Strapping pins (TESTA only)

The DS3231 I2C pins (GPIO1 and GPIO3) are not strapping pins, so there are no
boot complications on TESTA boards either.  The 10 kΩ pull-up requirements
mentioned in the 4+S and electroNIX 2 sections are for *other* GPIOs (anode
and colon drivers on strapping pins), not for the I2C lines themselves.

## Fit the CR2032 backup cell

Insert a CR2032 coin cell into the DS3231 module's holder **before** powering
up.  Without the cell the DS3231 loses its time the moment the clock is
unplugged, making it no more useful than the existing NVS epoch fallback.

The cell lasts several years in standby.  When it's exhausted the DS3231 resets
to 2000-01-01 00:00:00 — the firmware detects this (year < 2020) and falls
back to the NVS epoch rather than setting the clock to the year 2000.

## How it integrates with NTP and the browser

- **At boot**: the DS3231 is read before WiFi starts.  The clock shows the
  correct time within milliseconds.  `timeSrc = SRC_RTC` is set, and
  `core_timeTrusted()` returns true, so back-ends that animate an
  untrusted-time warning (e.g. the Nick2 bottom colon dot) show as trusted
  immediately.
- **At NTP sync**: the DS3231 is re-calibrated to the NTP-corrected time.
  This happens every `ntpEvery` minutes (default 60) while WiFi is connected.
- **"Set time from this device"**: the browser-posted epoch is written to
  the DS3231 so it persists even without NTP.  Useful for the office-network
  scenario where NTP is blocked: set the time once from the browser, and the
  DS3231 keeps it across power cuts.
- **No WiFi at all**: the DS3231 keeps time at ±2 ppm (roughly ±0.2 seconds
  per day) indefinitely on the backup cell.  The status panel shows **RTC**
  rather than "estimated", and `age` is blank (we don't track when it was
  last calibrated against an external source).

---

## Firmware safety features

- Boost gate is off during boot and flashing (GPIO2 boot pull-down).
- Software regulation with an absolute duty clamp (~41 %), soft-start ramp,
  hard over-voltage cut at target +12 V, and a shutdown if the feedback divider
  ever reads open — it will not run open-loop.
- HV shuts down whenever the tubes are off (night mode at 0 %, web toggle).
- 25 µs inter-digit blanking dead-time prevents ghosting between tubes.
