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
#define BOARD_ELECTRONIX_2   2       // PCB-030/031 — OBSOLETE. Fresh retrofits: use BOARD_ELECTRONIX_4_6T.
#define BOARD_ELECTRONIX_4_6T 7     // electroNIX 4 + seconds tubes: 6 x IN-12, IRLR3110Z.
                                     // Also covers electroNIX 2 PCB retrofits (set BOARD_HAS_LED_BL 1
                                     // in the profile below if the under-tube backlight is fitted).
                                     // Both colon positions wired in parallel (SEC_0 = all top neons,
                                     // SEC_1 = all bottom neons).
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
#define BOARD_NICK2_IN12     102     // NickTwo IN-12: 74141 + NCH8200HV + WS2812, 4 tubes (HH:MM)
#define BOARD_NICK2_IN12_6T  103     // NickTwo IN-12: same, 6 tubes (HH:MM:SS)

// ------------------------------------------------------------------ select v
#define BOARD  7
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

// ---- Nick2-specific build options -----------------------------------------
// Set to 1 to substitute neon colon lamps (SEC_0 on GPIO2, SEC_1 on GPIO12
// by default) for the WS2812B LED column. Override the GPIOs with
// #define PIN_NEON0 / PIN_NEON1 in board.h before the profile block.
#define NICK2_USE_NEON  0

// ---- Board profiles --------------------------------------------------------
#if BOARD == BOARD_NICK2_IN12
  #define BOARD_NAME       "Nick2 IN-12"
  #define BOARD_TUBES        4
  #define BOARD_HAS_HV       0         // NCH8200HV module — no software control
  #define BOARD_HAS_SENSOR   0
  #define BOARD_HAS_BUZZER   0
  #define BOARD_HAS_LED_BL   0
  #define BOARD_HAS_SECONDS  0
  #define BOARD_USE_SERIAL   0
  #if NICK2_USE_NEON
    #define BOARD_HAS_WS2812   0
    #define BOARD_DUAL_NEON    1
    #define BOARD_NEON1_OPTIONAL 0
  #else
    #define BOARD_HAS_WS2812   1
    #define BOARD_WS_COLS      1       // one 5-LED column between digits 2 and 3
    #define BOARD_WS_PER_COL   5
    #define BOARD_WS_HI_IDX    1       // upper colon dot
    #define BOARD_WS_LO_IDX    3       // lower colon dot
    #define BOARD_WS_WRN_IDX   4       // time-not-trusted warning (bottom LED)
  #endif

#elif BOARD == BOARD_NICK2_IN12_6T
  #define BOARD_NAME       "Nick2 IN-12 6T"
  #define BOARD_TUBES        6
  #define BOARD_HAS_HV       0
  #define BOARD_HAS_SENSOR   0
  #define BOARD_HAS_BUZZER   0
  #define BOARD_HAS_LED_BL   0
  #define BOARD_HAS_SECONDS  1
  #define BOARD_USE_SERIAL   0
  #if NICK2_USE_NEON
    #define BOARD_HAS_WS2812   0
    #define BOARD_DUAL_NEON    1
    #define BOARD_NEON1_OPTIONAL 0
  #else
    // Two 5-LED WS2812B columns daisy-chained on GPIO3:
    // column 0 = HH:MM gap, column 1 = MM:SS gap.
    #define BOARD_HAS_WS2812   1
    #define BOARD_WS_COLS      2
    #define BOARD_WS_PER_COL   5
    #define BOARD_WS_HI_IDX    1
    #define BOARD_WS_LO_IDX    3
    #define BOARD_WS_WRN_IDX   4
  #endif

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
  // electroNIX 4 expanded to six tubes. Also the target for fresh ESP32
  // retrofits of the electroNIX 2 PCB (BOARD_ELECTRONIX_2 is obsolete).
  //
  // GPIO pin summary (after the buzzer/W_5 reassignment vs. the original
  // electroNIX 4+S design):
  //   GPIO0  = buzzer (strapping pin; fit ≥10 kΩ pull-up to 3V3)
  //   GPIO12 = W_5 anode (seconds tens tube; was buzzer)
  //   GPIO15 = W_6 anode *or* LED backlight — see BOARD_HAS_LED_BL below
  //   GPIO1/GPIO3 = DS3231 I2C SDA/SCL when BOARD_HAS_LED_BL is 0
  //
  // BOARD_HAS_LED_BL: set to 1 if the under-tube LED backlight chain is
  // fitted (electroNIX 2 PCBs have this; electroNIX 4+S PCBs do not).
  // When 1, GPIO15 becomes PIN_LEDBL and W_6 moves to GPIO1 — the pin the
  // electroNIX 2 used for the LED before the DS3231 retrofit displaced it.
  // GPIO1 can then no longer serve as DS3231 SDA, so BOARD_HAS_RTC must be
  // 0. A ≥10 kΩ pull-up to 3V3 is required on GPIO15 regardless (strapping
  // pin; same reason as GPIO0 above — see WIRING.md).
  #define BOARD_NAME       "electroNIX 4+S"
  #define BOARD_TUBES        6
  #define BOARD_HAS_HV       1
  #define BOARD_HAS_SENSOR   1
  #define BOARD_HAS_BUZZER   1
  #define BOARD_HAS_LED_BL   0   // set to 1 for electroNIX 2 PCB LED backlight
  #define BOARD_HAS_WS2812   0
  #define BOARD_HAS_SECONDS  1
  #define BOARD_USE_SERIAL   0   // GPIO1/GPIO3 free for I2C (or W_6/unused if BOARD_HAS_LED_BL)
  #define BOARD_HV_LOGIC_FET 1   // IRLR3110Z - direct 3.3 V drive is fine
  #define BOARD_NEON1_OPTIONAL 0
  // Colon wiring is user-defined. The firmware always drives SEC_0 (GPIO4)
  // and SEC_1 (GPIO5); what you connect to them is up to you. Common
  // arrangements: all neons in parallel on one signal, top-dot / bottom-dot
  // split across both, or independent HH:MM / MM:SS control. See WIRING.md.
  // BOARD_DUP_COLON only affects the web UI preview (mirrors HH:MM colon
  // state onto MM:SS); it has no effect on firmware behaviour.
  #define BOARD_DUAL_NEON    1   // both SEC_0 (GPIO4) and SEC_1 (GPIO5) driven
  //#define BOARD_DUP_COLON  1   // web preview only: mirrors HH:MM onto MM:SS

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
  // BOARD_DUAL_NEON says the pin is available to wire up at all;
  // BOARD_NEON1_OPTIONAL tells the web UI to offer the "I've fitted the
  // second neon" toggle, since unlike every other board this is a bodge
  // rather than a factory-fitted part. SEC_0 (GPIO4) and SEC_1 (GPIO5) are
  // driven independently; see WIRING.md for colon wiring arrangements.
  #define BOARD_DUAL_NEON    1
  #define BOARD_NEON1_OPTIONAL 1

#elif BOARD == BOARD_ELECTRONIX_2
  #error "BOARD_ELECTRONIX_2 is obsolete. For a fresh ESP32 retrofit of an " \
         "electroNIX 2 PCB, select BOARD_ELECTRONIX_4_6T (#define BOARD 7). " \
         "Set BOARD_HAS_LED_BL 1 in that profile if the LED backlight is " \
         "fitted (note: LED backlight and DS3231 RTC share GPIO1 and are " \
         "mutually exclusive — see WIRING.md). The IRF840 gate-driver " \
         "requirement (HV_GATE_FITTED) still applies."

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
// electroNIX 4+S (BOARD_ELECTRONIX_4_6T): additionally fit ≥10 kΩ to 3V3
// on GPIO0 (buzzer, strapping pin) and GPIO15 (W_6 or LED backlight,
// strapping pin). GPIO12 (W_5 anode) does not need a pull-up.
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

#if BOARD_HAS_LED_BL && BOARD_HAS_RTC
  #error "LED backlight (BOARD_HAS_LED_BL 1) uses GPIO1 for the W_6 anode. " \
         "DS3231 (BOARD_HAS_RTC 1) also needs GPIO1 for I2C SDA. " \
         "Enable one or the other, not both. See WIRING.md."
#endif