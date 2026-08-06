// ============================================================================
//  board.h — pick your board here, and only here
//
//  Everything else in the sketch keys off the BOARD_HAS_* capability flags,
//  never off BOARD itself. Adding a new board is: add a constant, add a
//  profile block below, drop a display_<name>.cpp beside the existing ones.
// ============================================================================
#pragma once

// TESTA-QUADRA boards (2013-2014, originally ATmega16, converted to ESP32)
#define BOARD_ELECTRONIX_4   4       // PCB-061, 4 x LC-513/531, IRLR3110Z
#define BOARD_ELECTRONIX_3   3       // PCB-036, 4 x ZM1080T, IRLR3110Z, SEC_1 optional bodge
#define BOARD_ELECTRONIX_2   2       // PCB-030/031, 6 tubes, IRF840 — see WIRING.md for DS3231 retrofit
#define BOARD_ELECTRONIX_4_6T 7     // electroNIX 4 + seconds tubes: 6 x IN-12, IRLR3110Z,
                                     // no backlight; both colon positions wired in parallel
                                     // (SEC_0 = all top neons, SEC_1 = all bottom neons)
// fourTINY (rev 11-11-2013) users: select BOARD_ELECTRONIX_4. The pin maps
// are identical; only the boost FET differs (IRF840 needs a gate driver or a
// logic-level replacement — see WIRING.md).  fourTINY had its own profile
// only to surface that distinction; with the gate driver fitted it is
// electrically the same build as the electroNIX 4.
//
// electroNIX 2 USB (proposed v2/v3 hybrid): superseded by BOARD_ELECTRONIX_4_6T.
// Feed 5 V into the boost converter's input instead of 12 V and it runs from
// USB; no firmware change needed.

// Native ESP32 boards
#define BOARD_NICK2_IN12   102       // NickTwo IN-12: 74141 + NCH8200HV + WS2812

// ------------------------------------------------------------------ select v
#define BOARD  102
// ------------------------------------------------------------------

// ---- TESTA-only build options ---------------------------------------------
// Set to 1 if the boost gate is driven through an INVERTING level shifter
// (e.g. a 2N7002 with a pull-up to +12 V). Non-inverting gate drivers and
// direct logic-level FETs leave this at 0.
#define HV_PWM_INVERT   0

// The electroNIX 2 and fourTINY carry an IRF840, which will not switch from
// 3.3 V logic. Set this to 1 once a gate driver (or a logic-level FET) is
// fitted; the build stops until you do.
#define HV_GATE_FITTED  0

// ---- Board profiles --------------------------------------------------------
#if BOARD == BOARD_NICK2_IN12
  #define BOARD_NAME       "Nick2 IN-12"
  #define BOARD_TUBES        4
  #define BOARD_HAS_HV       0   // NCH8200HV module - no software control
  #define BOARD_HAS_SENSOR   0   // no light sensor fitted
  #define BOARD_HAS_BUZZER   0   // no MEL circuit
  #define BOARD_HAS_LED_BL   0   // no under-tube backlight
  #define BOARD_HAS_WS2812   1   // five-LED colon column
  #define BOARD_HAS_SECONDS  0
  #define BOARD_USE_SERIAL   0   // WS2812 data is on UART0 RX (GPIO3)
  // Colon LED layout
  #define BOARD_WS_COLS      1
  #define BOARD_WS_PER_COL   5
  #define BOARD_WS_HI_IDX    1   // upper colon dot
  #define BOARD_WS_LO_IDX    3   // lower colon dot
  #define BOARD_WS_WRN_IDX   4   // wifi warning dot

#elif BOARD == BOARD_ELECTRONIX_4
  #define BOARD_NAME       "electroNIX 4"
  #define BOARD_TUBES        4
  #define BOARD_HAS_HV       1
  #define BOARD_HAS_SENSOR   1
  #define BOARD_HAS_BUZZER   1
  #define BOARD_HAS_LED_BL   0
  #define BOARD_HAS_WS2812   0
  #define BOARD_HAS_SECONDS  0
  #define BOARD_USE_SERIAL   0   // GPIO1/GPIO3 reserved for optional DS3231 RTC (I2C SDA/SCL)
  #define BOARD_HV_LOGIC_FET 1   // IRLR3110Z - direct 3.3 V drive is fine
  #define BOARD_DUAL_NEON    1   // SEC_0 and SEC_1 both fitted
  #define BOARD_NEON1_OPTIONAL 0  // fixed at the factory, not a runtime choice

#elif BOARD == BOARD_ELECTRONIX_4_6T
  // electroNIX 4 expanded to six tubes.  Both colon positions share the
  // same SEC_0/SEC_1 drive lines (wired in parallel), so BOARD_DUP_COLON
  // lets the web preview draw them correctly without changing colon logic.
  // GPIO0 and GPIO15 (strapping pins) become anodes W_5/W_6; this frees
  // GPIO1 and GPIO3 for DS3231 I2C, giving the same SDA/SCL as every other
  // non-electroNIX-2 TESTA board.  10 kΩ pull-ups on GPIO0 and GPIO15 are
  // required for safe boot (see WIRING.md).  Every other GPIO is identical
  // to BOARD_ELECTRONIX_4.
  #define BOARD_NAME       "electroNIX 4+S"
  #define BOARD_TUBES        6
  #define BOARD_HAS_HV       1
  #define BOARD_HAS_SENSOR   1
  #define BOARD_HAS_BUZZER   1
  #define BOARD_HAS_LED_BL   0
  #define BOARD_HAS_WS2812   0
  #define BOARD_HAS_SECONDS  1
  #define BOARD_USE_SERIAL   0   // GPIO0/GPIO15 are anodes W_5/W_6; GPIO1/GPIO3 are I2C SDA/SCL
  #define BOARD_HV_LOGIC_FET 1   // IRLR3110Z - direct 3.3 V drive is fine
  #define BOARD_NEON1_OPTIONAL 0
  #define BOARD_DUAL_NEON    1   // SEC_0 and SEC_1 both fitted
  //#define BOARD_DUP_COLON    1   // both colon gaps are wired in parallel;
                                  // SEC_0 = top neon at HH:MM and MM:SS,
                                  // SEC_1 = bottom neon at both positions

#elif BOARD == BOARD_ELECTRONIX_3
  #define BOARD_NAME       "electroNIX 3"
  #define BOARD_TUBES        4
  #define BOARD_HAS_HV       1
  #define BOARD_HAS_SENSOR   1
  #define BOARD_HAS_BUZZER   1
  #define BOARD_HAS_LED_BL   0
  #define BOARD_HAS_WS2812   0
  #define BOARD_HAS_SECONDS  0
  #define BOARD_USE_SERIAL   0   // GPIO1/GPIO3 reserved for optional DS3231 RTC (I2C SDA/SCL)
  #define BOARD_HV_LOGIC_FET 1   // IRLR3110ZPBF - direct 3.3 V drive is fine
  // PCB-036 only brings out one colon neon (SEC_0 / N1) from the factory --
  // there's no SEC_1 net on this schematic. Firmware still supports a second
  // one, wired as a bodge (see WIRING.md), because unlike the other three
  // boards it's genuinely a per-unit choice whether that bodge exists.
  // BOARD_DUAL_NEON says the pin is available to wire up at all;
  // BOARD_NEON1_OPTIONAL is what tells the web UI to offer the "I've fitted
  // it" toggle instead of assuming one way or the other, the way it safely
  // can on the other three boards, whose SEC_1 is soldered on at the factory.
  #define BOARD_DUAL_NEON    1
  #define BOARD_NEON1_OPTIONAL 1

#elif BOARD == BOARD_ELECTRONIX_2
  // Retrofit for DS3231 I2C compatibility: SEC_1 lifted from GPIO3 and
  // soldered to GPIO0 (10 kΩ pull-up required); GPIO1 disconnected from the
  // backlight chain. Both GPIO1 and GPIO3 are then free for DS3231 SDA/SCL,
  // matching every other board in the family.
  // To restore the original wiring (backlight on GPIO1, SEC_1 on GPIO3),
  // set BOARD_HAS_LED_BL 1 and change PIN_NEON1 back to 3 in display_testa.cpp.
  #define BOARD_NAME       "electroNIX 2"
  #define BOARD_TUBES        6
  #define BOARD_HAS_HV       1
  #define BOARD_HAS_SENSOR   1
  #define BOARD_HAS_BUZZER   1
  #define BOARD_HAS_LED_BL   0   // backlight disconnected from GPIO1 in this retrofit
  #define BOARD_HAS_WS2812   0
  #define BOARD_HAS_SECONDS  1
  #define BOARD_USE_SERIAL   0   // GPIO0=SEC_1; GPIO1/GPIO3 are I2C SDA/SCL
  #define BOARD_HV_LOGIC_FET 0   // IRF840 - needs a gate driver
  #define BOARD_DUAL_NEON    1   // SEC_0 (HH:MM) and SEC_1 (MM:SS) both fitted
  #define BOARD_NEON1_OPTIONAL 0

#else
  #error "Set BOARD in board.h to one of the listed profiles."
#endif

// ---- Flags that only some boards set; default to 0 for all others ----------
// BOARD_DUP_COLON: both physical colon gap positions are wired in parallel to
// the same SEC_0 / SEC_1 drive lines.  The firmware colon logic is unchanged;
// only the web UI preview needs to know so it can mirror the HH:MM dots onto
// the MM:SS position rather than tracking colon0/colon1 independently.
#ifndef BOARD_DUP_COLON
#define BOARD_DUP_COLON 0
#endif

// ---- DS3231 real-time clock (optional on all boards) -----------------------
// Set BOARD_HAS_RTC to 1 once the module is physically wired.
// TESTA boards use GPIO1 (SDA) and GPIO3 (SCL) — see WIRING.md.
// Nick2 uses GPIO21 (SDA) and GPIO22 (SCL): the ESP32's standard I2C defaults,
// both free on that board and neither a strapping pin.
// Override before BOARD_HAS_RTC if you need different pins.
//
// All boards: 4.7 kΩ pull-ups to 3V3 on SDA and SCL.
// TESTA 6-tube boards (electroNIX 4+S) and the retrofitted electroNIX 2:
// additionally fit ≥10 kΩ to 3V3 on GPIO0 and, where used, GPIO15.
// See WIRING.md for the voltage calculation and wiring details.
#ifndef BOARD_HAS_RTC
#define BOARD_HAS_RTC 0
#endif
#ifndef BOARD_RTC_SDA
  #if BOARD == BOARD_NICK2_IN12
    #define BOARD_RTC_SDA 21   // GPIO21 — standard I2C SDA, free on Nick2
  #else
    #define BOARD_RTC_SDA  1   // GPIO1 — free on all TESTA boards
  #endif
#endif
#ifndef BOARD_RTC_SCL
  #if BOARD == BOARD_NICK2_IN12
    #define BOARD_RTC_SCL 22   // GPIO22 — standard I2C SCL, free on Nick2
  #else
    #define BOARD_RTC_SCL  3   // GPIO3 — free on TESTA; occupied by WS2812 on Nick2
  #endif
#endif

#if BOARD_HAS_HV && !BOARD_HV_LOGIC_FET && !HV_GATE_FITTED
  #error "This board's boost MOSFET is an IRF840, which will not switch from 3.3 V logic. Fit a gate driver (TC4420 / MCP1407 / UCC27517 from +12 V) or an inverting 2N7002 stage with HV_PWM_INVERT 1, then set HV_GATE_FITTED to 1. See WIRING.md."
#endif