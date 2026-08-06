// ============================================================================
//  display.h — the interface every board back-end implements
//
//  clock_core talks to the display only through these functions. That is what
//  lets one core drive a TESTA board (10 cathode GPIOs, software boost
//  regulator, neon colons) and a Nick2 board (BCD into a 74141, sealed HV
//  module, WS2812 colon column) with no conditional compilation in the core.
//
//  Back-ends are self-contained: they own multiplexing, cross-fade timing,
//  HV regulation, colon hardware, brightness gamma, per-tube trim and any
//  local sensors. The core supplies intent ("show these digits, fading over
//  600 ms") and policy ("run at 45% brightness"), never mechanism.
// ============================================================================
#pragma once
#include <Arduino.h>
#include "board.h"

// ---- Colon behaviours (shared enum) ---------------------------------------
enum ColonMode : uint8_t {
  COLON_OFF = 0,
  COLON_STEADY,
  COLON_BLINK,       // both dots together, on even seconds
  COLON_ALTERNATE,   // upper dot, then lower dot
  COLON_BREATHE,     // smooth fade in/out; WS2812 boards only
  COLON_CENTERGLOW   // centre decorative LED at full; colon dots at colonOuterPct%; WS2812 only
};

// ---- Diagnostics reported back to the core --------------------------------
// Back-ends fill in what applies to them. The core hides fields belonging to
// capabilities the board doesn't declare.
struct DisplayStatus {
  float    hv;             // volts, 0 where there is no controllable HV
  float    duty;           // %, 0 likewise
  bool     hvFault;
  uint32_t hvCuts;         // over-voltage back-offs since boot
  uint16_t muxHealth;      // % of expected ISR tick rate, 100 nominal
  uint16_t muxMin;         // worst second seen since boot
  bool     colon0, colon1; // current lamp states, for the web preview
  bool     hasLight;       // true if this board reads a light sensor
  float    lightMv;        // filtered sensor reading
  uint16_t lightPP;        // peak-to-peak spread of the raw samples
};

// ---- Lifecycle -------------------------------------------------------------
// Called after NVS is loaded but before WiFi, so the tubes light during
// network setup rather than after it. May start its own tasks.
void display_init();

// ---- Content ---------------------------------------------------------------
// Values 0..9 light that digit; 15 blanks that tube.
// fadeMs = 0 is an instant swap; anything positive is a cross-fade the
// back-end runs on its own timeline. Calling again mid-fade replaces the
// target, continuing from whatever is currently visible.
void display_setDigits(const uint8_t digits[BOARD_TUBES], uint16_t fadeMs);

// Colon behaviour. The back-end animates it, using core_secondIsEven() and
// core_msIntoSecond() so blinking stays locked to the clock rather than to
// millis().
void display_setColon(ColonMode mode);

// Effective brightness 0..100, already resolved by the core for auto/manual,
// night mode and the on/off toggle. The back-end applies gamma and the
// per-tube trims from cfg.
void display_setBrightness(uint8_t percent);

// ---- Periodic hooks --------------------------------------------------------
void display_tick_100ms();
void display_tick_1s();

// ---- Housekeeping ----------------------------------------------------------
// The core parks the display around flash writes and OTA updates, because a
// stalled multiplex can leave one cathode conducting continuously.
void display_park(bool parked);

// Snapshot of the visible digits for the web preview: '0'..'9', or space for
// a blanked tube, NUL terminated.
void display_snapshot(char *out, int n);

void display_getStatus(DisplayStatus &out);

#if BOARD_HAS_BUZZER
// The buzzer is board hardware, so the back-end owns it; the core decides
// when to sound it (hourly chime, button feedback, OTA start).
void display_beep(uint8_t count, uint16_t onMs, uint16_t offMs);
#endif