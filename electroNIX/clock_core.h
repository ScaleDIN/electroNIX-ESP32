// ============================================================================
//  clock_core.h — public interface to the board-agnostic clock module
//
//  This header is what a back-end needs to see: the shared Config, the
//  handful of functions the back-end may call back into (to log diagnostics
//  or hand a rendered snapshot to the web UI). It is deliberately small.
// ============================================================================
#pragma once
#include <Arduino.h>
#include "board.h"

// ---- Shared configuration --------------------------------------------------
// One struct, persisted key-by-key in NVS. Back-ends read cfg.trim[],
// cfg.fadeMs, cfg.brSpeed etc. directly; the core owns loading, saving, and
// exposing them to the web UI. Fields not relevant to a given board are
// simply not offered in the UI (board.h capability flags control which
// panels appear) but stay in the struct so the layout is stable across
// builds.
struct Config {
  // ---- network + time ---------------------------------------------------
  char ssid[33]   = "";
  char pass[65]   = "";
  char host[24]   = "electronix";
  char ntp1[48]   = "pool.ntp.org";
  char ntp2[48]   = "time.google.com";
  char tz[48]     = "<+08>-8";          // POSIX TZ; default Singapore
  uint16_t ntpEvery = 60;               // minutes
  bool ntpSmooth  = true;

  // ---- display behaviour -----------------------------------------------
  bool use24      = true;
  bool leadZero   = true;
  uint8_t colon   = 2;                  // see enum in display.h
  uint16_t fadeMs = 600;
  // Only meaningful where BOARD_NEON1_OPTIONAL is 1 (currently just
  // electroNIX 3): whether the SEC_1 bodge described in WIRING.md has
  // actually been wired up. Defaults to false there, since the stock board
  // doesn't have it; on every other dual-neon board SEC_1 is soldered on at
  // the factory, so this defaults true and the web UI doesn't expose it as
  // a choice at all.
#if BOARD_NEON1_OPTIONAL
  bool neon1Fitted = false;
#else
  bool neon1Fitted = true;
#endif
  // Independent brightness for the neon colon lamps, as a percentage of the
  // tube master brightness (which already folds in brMan, auto, night mode,
  // etc.).  100 = same as the tubes; 0 = colon off regardless of mode.
  // Only used by back-ends that drive neon lamps via PWM (display_testa.cpp).
  // WS2812 back-ends have colonBr below for the same purpose.
  uint8_t colonBrNeon = 100;

  // ---- brightness ------------------------------------------------------
  bool brAuto     = false;              // needs BOARD_HAS_SENSOR
  uint8_t brMan   = 85;
  uint8_t brMin   = 15, brMax = 100;
  uint8_t brSpeed = 30;                 // slider 0..100
  uint16_t lightDark   = 2800;
  uint16_t lightBright = 300;

  // ---- night mode ------------------------------------------------------
  bool nightEn    = false;
  bool colonNightOff = false;
  uint16_t nightS = 23 * 60;
  uint16_t nightE = 6 * 60 + 30;
  uint8_t nightBr = 10;

  // ---- cleaning cycles -------------------------------------------------
  uint16_t poisonMin = 20;
  uint8_t  poisonSec = 3;
  uint8_t  poisonStyle = 0;

  // ---- other -----------------------------------------------------------
  uint16_t dateEvery = 0;
  // Date display format.  0 = DD/MM (or DD/MM/YY on 6-digit), 1 = MM/DD
  // (or MM/DD/YY), 2 = YY/MM/DD (6-digit only; falls back to DD/MM on
  // 4-digit builds).  Replaces the old bool dateDMY (true=DMY, false=MDY);
  // loadConfig() migrates the stored value transparently on first boot after
  // an upgrade.
  uint8_t dateDur  = 4;
  uint8_t dateFmt  = 0;                // default: DD/MM
  bool chime      = false;              // needs BOARD_HAS_BUZZER
  // The buzzer now lives on GPIO0, a strapping pin. Fit ≥10 kΩ to 3V3 on
  // GPIO0 before enabling this, or the chip may misboot when GPIO0 is LOW
  // (buzzer silent). See the PIN_BUZZER comment in display_testa.cpp.
  bool buzzerEn   = false;             // needs BOARD_HAS_BUZZER; disabled by default
  bool btnEn      = false;
  uint16_t portalSec = 20;              // seconds the setup AP stays open at boot
                                        // before a STA connection is attempted;
                                        // 0 = start connecting immediately

  // ---- per-tube trim & wiring order (both up to 10 wide) ---------------
  uint8_t trim[10] = {100,100,100,100,100,100,100,100,100,100};
  uint8_t cathOrder[10] = {0,1,2,3,4,5,6,7,8,9};
  uint8_t anodeOrder[10] = {0,1,2,3,4,5,6,7,8,9};

  // ---- HV (ignored on boards without a boost converter) ----------------
  uint16_t hvSet  = 170;
  float    hvTrim = 1.00f;

  // ---- seconds + backlight (ignored where absent) ----------------------
  bool secEn      = true;
  uint8_t secMode = 0;
  bool ledEn      = true;
  uint8_t ledBr   = 60;
  bool ledNight   = true;

  // ---- WS2812 colon column (BOARD_HAS_WS2812 only) ---------------------
  // The Nick2's five LEDs sit in a vertical line between digits 2 and 3.
  // Counting from the top, LEDs 2 and 4 land where colon dots belong; the
  // remaining three (top, middle, bottom) are decorative.
  uint8_t colonR = 255, colonG = 100, colonB = 20;   // warm amber default
  uint8_t colonBr = 40;                              // % overall
  // Brightness of the two colon-dot LEDs in COLON_CENTERGLOW mode, as a
  // percentage of the centre decorative LED.  0 = dots off, 100 = all even.
  uint8_t colonOuterPct = 50;
  uint8_t colonAccent = 0;   // spare LEDs: 0 off, 1 dim glow, 2 match colon
  uint8_t accentDim = 15;    // % of colon brightness
  // Whichever LED is first in the data chain is assumed to be physically at
  // the top of the column. Some boards are wired the other way round --
  // first-in-chain at the bottom -- which makes every colon animation (and
  // the "time not trusted" warning) appear upside down. Flip this rather
  // than re-soldering; it only changes which end of the chain firmware
  // treats as "top", nothing physical.
  bool colonReversed = false;

  // Brightness curve applied to blink / alternate transitions.
  //   0 = gamma    x³         — slow start, quick finish (concentrates change near top)
  //   1 = sqrt     √x         — quick start, slow finish (perceptually linear on linear LEDs)
  //   2 = smoothstep x²(3-2x) — symmetric S-curve, no velocity discontinuity
  // BREATHE and CENTERGLOW use the same selected curve (without the floor) so
  // continuous animations stay coherent with blink/alternate transitions.
  // Ignored on boards that don't have WS2812 LEDs.
  uint8_t fadeCurve = 0;

  // Minimum brightness floor for blink / alternate, 0–100 %.
  // 0 = the LED goes fully dark in the off half of each blink; any positive
  // value lifts the off-state to that percentage of the configured colon
  // brightness, so the colon dims without ever completely switching off.
  // Has no effect in BREATHE or CENTERGLOW modes, which use accentDim as
  // their own continuous floor.
  uint8_t fadeCurveFloor = 0;
};
extern Config cfg;

// ---- Back-end → core helpers ---------------------------------------------
// Colon animation has to stay locked to the displayed time rather than to
// millis(), or a blink drifts against the seconds. Back-ends use these.
bool     core_secondIsEven();
uint16_t core_msIntoSecond();

// True once the clock is running on a time it actually trusts -- an NTP
// sync or a time set from a browser -- as opposed to a restored guess from
// NVS/RTC memory (SRC_SAVED) or no time at all (SRC_NONE). This is the same
// distinction the web UI already colours amber vs. green in the "time" status
// field. Back-ends can use it to warn the user the displayed time may be
// wrong; see the Nick2 back-end's bottom colon dot.
bool core_timeTrusted();

// True when a flash write would be unobtrusive: tubes dark, a cleaning cycle
// already animating, or an OTA in progress. The core uses this itself; it is
// exposed because a back-end may want to defer its own persistence too.
bool core_flashWriteSafe();

// Entry points invoked from the .ino wrapper
void core_setup();
void core_loop();