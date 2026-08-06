// ============================================================================
//  display_nick2.cpp — NickTwo IN-12 board (schematic rev 2.0, 2021-03-09)
//
//  Very different plumbing from the TESTA-QUADRA boards:
//
//   - Cathodes are driven through a single 74141 BCD-to-decimal decoder. The
//     ESP32 writes a 4-bit nibble (74141_A/B/C/D) and the chip picks the
//     cathode; nibble 15 makes it blank all outputs, which is the same trick
//     the TESTA back-end uses with digit == 10.
//
//   - Anodes go through PNP high-side switches (MMBTA92) driven by NPN
//     level-shifters. The base network sits on a 470 k / 4 x 200 k / 470 k
//     divider from 170 V — so turn-off is meaningfully slower than direct
//     base drive on the TESTA. The multiplex slot dead-time here is 60 us
//     instead of the TESTA's 25 us to keep ghosting out.
//
//   - HV comes from an NCH8200HV module: sealed, ~170 V, always on when USB
//     is connected. No feedback, no gate, no PWM. The core hides its HV panel
//     because board.h declares BOARD_HAS_HV 0.
//
//   - Colons are five WS2812B LEDs in a chain on GPIO3 (which is UART0 RX;
//     the serial console isn't available on this board). They sit in a
//     VERTICAL LINE between digits 2 and 3. Counting LOGICALLY from the top
//     (this is how the code refers to them; see cfg.colonReversed below for
//     how that maps onto the physical chain):
//
//         LED 1   decorative (above the colon)
//         LED 2   upper colon dot     <- these two are the colon
//         LED 3   decorative (centre)
//         LED 4   lower colon dot     <-
//         LED 5   decorative (below the colon) -- also the warning LED
//
//     That geometry makes ALTERNATE mode meaningful — upper dot, then lower
//     dot — which it isn't on a board with a single pair of neons. One colour
//     for the whole column, with LEDs 1 and 3 switchable between off, a dim
//     glow, or matching the colon.
//
//     Whichever LED is first in the data chain is assumed to be logical
//     LED 1 (the top). Some boards are wired the other way round -- first in
//     chain physically at the bottom -- which makes every animation appear
//     upside down. cfg.colonReversed flips the mapping in one place
//     (ws2812_write_all) rather than needing a resolder; every other
//     function in this file keeps addressing LEDs by their logical position.
//
//     Whenever core_timeTrusted() is false -- the clock is showing a restored
//     guess rather than a real NTP/browser sync -- LED 5, the extreme bottom
//     of the column, blinks regardless of the configured colon mode, and the
//     other four LEDs (the real colon) are held off for as long as that
//     lasts. Only the warning LED moves, so there's nothing else on the
//     board competing for attention while the time can't be trusted.
//
//     That warning blinks from power-on, not just once NTP has had a chance
//     to fail: colonTask is a FreeRTOS task started in display_init(), so it
//     keeps ticking during the up-to-20-second blocking WiFi connection
//     attempt in core_setup() -- core_loop() (and with it the core's own
//     100 ms tick) doesn't start until that returns. effBright starts at a
//     visible default rather than the usual 0 for the same reason: without
//     it, colonTask would run the whole time but multiply everything by a
//     brightness of zero.
//
//  Multiplex compatibility with the shared core
//  --------------------------------------------
//  The core's cross-fade splits each tube's on-window between the previously
//  displayed digit and the new one. Doing that with a BCD decoder means
//  rewriting the nibble mid-slot rather than swapping GPIO masks — same idea,
//  different implementation. The 74141's propagation delay is well under a
//  microsecond so there's no visible seam.
// ============================================================================
#include "board.h"
#if BOARD == BOARD_NICK2_IN12

#include "display.h"
#include "clock_core.h"

// The multiplex ISR writes GPIO.out_w1ts / out1_w1tc directly. Arduino.h does
// not reliably pull in the struct that defines these on every core version.
#if __has_include(<hal/gpio_ll.h>)
  #include <hal/gpio_ll.h>
#endif
#include <soc/gpio_struct.h>

// ---- Pin map ---------------------------------------------------------------
// The NickTwo schematic labels which ESP32 IO connects to which named net,
// though the labels are small and easy to misread. These values were taken
// from the schematic rev 2.0 (2021-03-09):
//
//   74141_A  -> IO4     74141_B  -> IO17    74141_C  -> IO5    74141_D  -> IO16
//   ANODE_1  -> IO32    ANODE_2  -> IO33    ANODE_3  -> IO25   ANODE_4  -> IO26
//   RX_TOP (WS2812)  -> IO3      TX_TOP  -> IO1     GPIO0  -> IO0
//
// If you have a different revision, the runtime override endpoint
//   POST /api/action?do=setpin&kind=an&idx=0&gpio=32
// writes to NVS and reboots. kind=an for anode 0..3, kind=bcd for 74141
// inputs 0..3 (A=0, B=1, C=2, D=3). Or #define PIN_BCD_A etc. in board.h.
#ifndef PIN_BCD_A
  #define PIN_BCD_A  4     // 74141 input A (LSB)
#endif
#ifndef PIN_BCD_B
  #define PIN_BCD_B 17     // 74141 input B
#endif
#ifndef PIN_BCD_C
  #define PIN_BCD_C  5     // 74141 input C
#endif
#ifndef PIN_BCD_D
  #define PIN_BCD_D 16     // 74141 input D (MSB)
#endif
#ifndef PIN_ANODE_1
  #define PIN_ANODE_1 32
#endif
#ifndef PIN_ANODE_2
  #define PIN_ANODE_2 33
#endif
#ifndef PIN_ANODE_3
  #define PIN_ANODE_3 25
#endif
#ifndef PIN_ANODE_4
  #define PIN_ANODE_4 26
#endif
static uint8_t PIN_ANODE[BOARD_TUBES] = { PIN_ANODE_1, PIN_ANODE_2, PIN_ANODE_3, PIN_ANODE_4 };
static uint8_t PIN_BCD[4]             = { PIN_BCD_A, PIN_BCD_B, PIN_BCD_C, PIN_BCD_D };
static const uint8_t PIN_WS2812  =  3;    // RX_TOP -- UART0 RX (explicit in the schematic)
static const uint8_t PIN_LIGHT   = 34;    // optional, if a sensor is added
#define WS2812_COUNT BOARD_WS_PER_COL

// ---- Multiplex timing ------------------------------------------------------
// 40 kHz ISR, same as TESTA. 4 tubes -> 62 ticks/slot -> 100 Hz frame,
// with 3 ticks of dead-time (75 us) to give the slow PNP switches room to
// turn off between slots.
static const uint32_t TICK_US       = 25;
static const uint8_t  SLOT_TICKS    = 62;
static const uint8_t  DEAD_TICKS    = 3;
static const uint8_t  ACTIVE_TICKS  = SLOT_TICKS - DEAD_TICKS;
static const uint8_t  BLANK         = 15;

// ---- Pin overrides via NVS -------------------------------------------------
// Written by the /api/action?do=setpin&kind=X&idx=Y&gpio=Z web endpoint (see
// clock_core), so you can correct a wrong pin guess without a rebuild. Reads
// happen once at display_init(); a restart applies changes.
#include <Preferences.h>
void nick2_savePin(const char *kind, uint8_t idx, uint8_t gpio) {
  Preferences p;
  p.begin("nickpins", false);
  char k[6];
  if (!strcmp(kind, "bcd") && idx < 4)      { snprintf(k,sizeof k,"bcd%d",idx); p.putUChar(k, gpio); }
  else if (!strcmp(kind, "an") && idx < BOARD_TUBES) { snprintf(k,sizeof k,"an%d",idx); p.putUChar(k, gpio); }
  p.end();
}

static void loadPinOverrides() {
  Preferences p;
  p.begin("nickpins", true);
  for (int i = 0; i < 4; i++) {
    char k[6]; snprintf(k, sizeof k, "bcd%d", i);
    PIN_BCD[i]   = p.getUChar(k, PIN_BCD[i]);
  }
  for (int i = 0; i < BOARD_TUBES; i++) {
    char k[6]; snprintf(k, sizeof k, "an%d", i);
    PIN_ANODE[i] = p.getUChar(k, PIN_ANODE[i]);
  }
  p.end();
}

// ---- ISR state -------------------------------------------------------------
static volatile DRAM_ATTR uint32_t tubeWord[BOARD_TUBES];  // fade<<16|new<<8|old
static volatile DRAM_ATTR uint8_t  vOnTicks[BOARD_TUBES];
static volatile DRAM_ATTR bool     muxHold = false;
static volatile DRAM_ATTR uint8_t  isrCurBcd = 255;
static volatile DRAM_ATTR uint32_t muxTicks = 0;

static volatile DRAM_ATTR uint32_t bcdMaskSet0[16], bcdMaskSet1[16];
static volatile DRAM_ATTR uint32_t anodeMask0[BOARD_TUBES], anodeMask1[BOARD_TUBES];
static volatile DRAM_ATTR uint32_t allAnodeMask0 = 0, allAnodeMask1 = 0;
static volatile DRAM_ATTR uint32_t allBcdMask0 = 0, allBcdMask1 = 0;
static hw_timer_t *muxTimer = nullptr;

// loop()-owned shadow copies — only loop writes these
static uint8_t shOld[BOARD_TUBES], shNew[BOARD_TUBES], shFade[BOARD_TUBES];
static inline void pushTube(int i) {
  tubeWord[i] = ((uint32_t)shFade[i] << 16) | ((uint32_t)shNew[i] << 8) | shOld[i];
}

// Starts non-zero on purpose -- see the matching comment in display_testa.cpp.
// colonTask already runs independently of the core from display_init()
// onward; this is what makes its output visible before the core's first
// real display_setBrightness() call, which can be up to 20 s away behind
// the blocking WiFi connection attempt.
static uint8_t effBright = 60;

// Fade timeline owned entirely by this back-end. The core just says "fade for
// N ms" and forgets about it; this task walks it forward every 20 ms.
static volatile uint16_t fadeDurMs = 0;
static volatile uint32_t fadeStartMs = 0;
static void fadeTask(void *) {
  for (;;) {
    if (fadeDurMs) {
      uint32_t el = millis() - fadeStartMs;
      uint16_t dur = fadeDurMs;
      // While seconds are counting on a six-tube board, cap the fade so the
      // digit always settles inside its second. On four tubes this is a no-op.
      uint8_t p = (el >= dur) ? 255 : (uint8_t)((el * 255UL) / dur);
      for (int i = 0; i < BOARD_TUBES; i++) {
        if (shOld[i] == shNew[i]) continue;
        shFade[i] = p;
        if (p == 255) shOld[i] = shNew[i];
        pushTube(i);
      }
      if (p == 255) fadeDurMs = 0;
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// ---- Wiring order ----------------------------------------------------------
// cfg.cathOrder[d] selects which wired cathode lights digit d; cfg.anodeOrder
// does the same for tube positions. Rebuilt live when the user saves.
static void buildMasks() {
  muxHold = true;
  delayMicroseconds(TICK_US * 2);
  
  GPIO.out_w1tc      = allAnodeMask0;
  GPIO.out1_w1tc.val = allAnodeMask1;
  GPIO.out_w1ts      = allBcdMask0;
  GPIO.out1_w1ts.val = allBcdMask1;
  allAnodeMask0 = allAnodeMask1 = 0;
  allBcdMask0 = allBcdMask1 = 0;
  isrCurBcd = 255;

  for (int i = 0; i < 4; i++) {
    if (PIN_BCD[i] < 32) allBcdMask0 |= 1UL << PIN_BCD[i];
    else                 allBcdMask1 |= 1UL << (PIN_BCD[i] - 32);
  }

  for (int i = 0; i < BOARD_TUBES; i++) {
    uint8_t idx = (cfg.anodeOrder[i] < BOARD_TUBES) ? cfg.anodeOrder[i] : i;
    uint8_t pin = PIN_ANODE[idx];
    anodeMask0[i] = (pin < 32) ? (1UL << pin) : 0;
    anodeMask1[i] = (pin < 32) ? 0 : (1UL << (pin - 32));
    allAnodeMask0 |= anodeMask0[i];
    allAnodeMask1 |= anodeMask1[i];
  }

  for (int logicalD = 0; logicalD < 16; logicalD++) {
    uint32_t m0 = 0, m1 = 0;
    uint8_t physD = logicalD;
    
    if (logicalD < 10) {
      physD = (cfg.cathOrder[logicalD] < 10) ? cfg.cathOrder[logicalD] : logicalD;
    }
    
    if (physD & 1) { if (PIN_BCD[0] < 32) m0 |= 1UL << PIN_BCD[0]; else m1 |= 1UL << (PIN_BCD[0] - 32); }
    if (physD & 2) { if (PIN_BCD[1] < 32) m0 |= 1UL << PIN_BCD[1]; else m1 |= 1UL << (PIN_BCD[1] - 32); }
    if (physD & 4) { if (PIN_BCD[2] < 32) m0 |= 1UL << PIN_BCD[2]; else m1 |= 1UL << (PIN_BCD[2] - 32); }
    if (physD & 8) { if (PIN_BCD[3] < 32) m0 |= 1UL << PIN_BCD[3]; else m1 |= 1UL << (PIN_BCD[3] - 32); }
    
    bcdMaskSet0[logicalD] = m0;
    bcdMaskSet1[logicalD] = m1;
  }
  
  muxHold = false;
}

// ---- The multiplex ISR -----------------------------------------------------
// Writes a BCD nibble and asserts one anode. Cross-fade splits the slot's
// on-window between the old and new nibble, same principle as the TESTA
// back-end but writing 4 pins instead of selecting a cathode mask.
void IRAM_ATTR onMuxTick() {
  static uint8_t slot = 0, tick = 0;
  uint8_t curBcd = isrCurBcd;
  muxTicks++;

  if (++tick >= SLOT_TICKS) { tick = 0; if (++slot >= BOARD_TUBES) slot = 0; }

  if (muxHold) {
    GPIO.out_w1tc      = allAnodeMask0;
    GPIO.out1_w1tc.val = allAnodeMask1;
    GPIO.out_w1ts      = allBcdMask0;
    GPIO.out1_w1ts.val = allBcdMask1;
    isrCurBcd = 255;
    return;
  }

  // Dead-time: turn off the anode, blank the decoder, let the PNP recover.
  if (tick < DEAD_TICKS) {
    if (tick == 0) {
      GPIO.out_w1tc      = allAnodeMask0;
      GPIO.out1_w1tc.val = allAnodeMask1;
      GPIO.out_w1ts      = allBcdMask0;
      GPIO.out1_w1ts.val = allBcdMask1;
      isrCurBcd = BLANK;
    }
    return;
  }

  uint8_t tOn = vOnTicks[slot];
  uint8_t tInSlot = tick - DEAD_TICKS;

  // Fix 1: True 0% duty cycle
  if (tOn == 0) return; 

  // Fix 2: Inclusive bound to prevent the 1-tick pulse on 0
  if (tInSlot >= tOn) {
    if (tInSlot == tOn) {
      // Fix 3: Pull anodes LOW (Clear) but BCD pins HIGH (Set to 1111/15)
      GPIO.out_w1tc      = allAnodeMask0;
      GPIO.out1_w1tc.val = allAnodeMask1;
      GPIO.out_w1ts      = allBcdMask0;
      GPIO.out1_w1ts.val = allBcdMask1;
      isrCurBcd = BLANK;
    }
    return;
  }

  uint32_t w = tubeWord[slot];
  uint8_t oldD = (uint8_t)w, newD = (uint8_t)(w >> 8), fade = (uint8_t)(w >> 16);

  uint8_t newTicks = (uint8_t)(((uint16_t)tOn * fade + 127) / 255);
  uint8_t d = (tInSlot <= (uint8_t)(tOn - newTicks)) ? oldD : newD;
  if (d > 9) d = BLANK;

  if (d != curBcd) {
    GPIO.out_w1tc = allBcdMask0;
    GPIO.out1_w1tc.val = allBcdMask1;
    GPIO.out_w1ts = bcdMaskSet0[d];
    GPIO.out1_w1ts.val = bcdMaskSet1[d];
    isrCurBcd = d;
  }
  if (d != BLANK) {
    GPIO.out_w1ts = anodeMask0[slot];
    GPIO.out1_w1ts.val = anodeMask1[slot];
  } else {
    GPIO.out_w1tc = anodeMask0[slot];
    GPIO.out1_w1tc.val = anodeMask1[slot];
  }
}

// ---- WS2812 driver ---------------------------------------------------------
// The RMT peripheral generates the 800 kHz one-wire protocol from a small
// buffer so the CPU never has to bit-bang. One rmt_item32_t per bit, colour
// order is G-R-B for WS2812B.
//
// Using the ESP-IDF RMT driver directly (driver/rmt.h) rather than the
// Arduino wrapper (rmtInit / rmt_obj_t), because the wrapper's shape has
// varied between core versions while the IDF API is stable on 2.x and 3.x.
#include <driver/rmt.h>

static const rmt_channel_t WS_CHAN = RMT_CHANNEL_0;
static const uint8_t WS_CLK_DIV   = 4;         // 80 MHz / 4 = 20 MHz -> 50 ns/tick
static rmt_item32_t rmtBuf[WS2812_COUNT * 24];

// Timing at 50 ns/tick: T0H 8 (400 ns), T0L 17 (850 ns), T1H 16 (800 ns),
// T1L 9 (450 ns). WS2812B tolerance is ~150 ns on each edge.
static const rmt_item32_t WS_BIT0 = { .duration0 =  8, .level0 = 1, .duration1 = 17, .level1 = 0 };
static const rmt_item32_t WS_BIT1 = { .duration0 = 16, .level0 = 1, .duration1 =  9, .level1 = 0 };

// px[] is always indexed in LOGICAL top-to-bottom order (0 = top of the
// column .. WS2812_COUNT-1 = bottom), matching the LED-role comment above.
// Physically, whichever LED is first in the data chain gets written first --
// normally that is assumed to be the top one, but cfg.colonReversed flips it
// for boards wired the other way, so every caller can keep thinking in
// logical "top/bottom" terms and never has to know which way the chain runs.
static void ws2812_write_all(uint8_t px[WS2812_COUNT][3]) {
  int off = 0;
  auto pushByte = [&](uint8_t v) {
    for (int i = 7; i >= 0; i--) rmtBuf[off++] = (v & (1 << i)) ? WS_BIT1 : WS_BIT0;
  };
  for (int chainPos = 0; chainPos < WS2812_COUNT; chainPos++) {
    int logical = cfg.colonReversed ? (WS2812_COUNT - 1 - chainPos) : chainPos;
    pushByte(px[logical][1]);   // G
    pushByte(px[logical][0]);   // R
    pushByte(px[logical][2]);   // B
  }
  rmt_write_items(WS_CHAN, rmtBuf, WS2812_COUNT * 24, true);
  // >50 us of low = latch. RMT idles low after the last item, so a small
  // delay before the next write is enough.
  ets_delay_us(60);
}

static void ws2812_clear() {
  uint8_t px[WS2812_COUNT][3] = {{0}};
  ws2812_write_all(px);
}

// ---- Colon control ---------------------------------------------------------
// LED roles, top to bottom. Index 1 and 3 are the colon dots; 0, 2 and 4 are
// the decorative LEDs above, between and below them. The "time not trusted"
// warning uses LED 4 -- the extreme bottom of the column -- rather than
// either colon dot, so it reads as a distinct indicator light instead of an
// odd-looking colon. The real colon is held off for as long as the warning
// is showing, so it's the only thing moving on the board.
static const uint8_t COLON_DOT_HI  = BOARD_WS_HI_IDX;
static const uint8_t COLON_DOT_LO  = BOARD_WS_LO_IDX;
static const uint8_t COLON_WARN_LED = BOARD_WS_WRN_IDX;
static ColonMode colonMode = COLON_BLINK;

// High-Speed Delta-Sigma Modulator Engine
static void colonTask(void *) {
  static float dsError[WS2812_COUNT][3] = {{0}};
  static uint8_t lastPx[WS2812_COUNT][3] = {{0}};
  
  for (;;) {
    if (muxHold) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    uint8_t px[WS2812_COUNT][3] = {{0}};
    float base = (effBright / 100.0f) * (cfg.colonBr / 100.0f);

    bool even = core_secondIsEven();
    uint16_t ms = core_msIntoSecond();
    
    uint16_t fMs = cfg.fadeMs;
    if (fMs == 0) fMs = 1;
    if (fMs > 1000) fMs = 1000;
    
    float p = (float)ms / fMs;
    if (p > 1.0f) p = 1.0f;

    // Selectable brightness curve, chosen by cfg.fadeCurve:
    //   0 — gamma (x³):       slow start, concentrates change near top of range
    //   1 — square root (√x): quick start, slow finish; perceptually linear on
    //                         the WS2812's linear-output LEDs
    //   2 — smoothstep:       symmetric S-curve, no velocity discontinuity
    //
    // applyGamma()      maps [0..1] through the curve with no floor.
    //                   Used by BREATHE / CENTERGLOW, which manage their own
    //                   continuous floor via accentDim.
    //
    // applyFadeCurve()  adds the floor lift (cfg.fadeCurveFloor %) so the LED
    //                   never goes fully dark between blinks when the floor > 0.
    //                   Used by BLINK and ALTERNATE.
    float floor_k = cfg.fadeCurveFloor / 100.0f;
    auto applyGamma = [&](float t) -> float {
      switch (cfg.fadeCurve) {
        case 1: return sqrtf(t);                        // sqrt
        case 2: return t * t * (3.0f - 2.0f * t);      // smoothstep
        default: return t * t * t;                      // gamma (cubic)
      }
    };
    auto applyFadeCurve = [&](float t) -> float {
      return floor_k + (1.0f - floor_k) * applyGamma(t);
    };
    float g_on  = applyFadeCurve(p);
    float g_off = applyFadeCurve(1.0f - p);

    float hi = 0, lo = 0, warn = 0, centerGlow = 0;
    bool untrusted = !core_timeTrusted();
    if (untrusted) {
      // The clock is showing a restored guess, or hasn't synced at all --
      // the time on the tubes may be wrong. Blink the dedicated warning LED
      // using the same colour/brightness (via `base`, below) and the same
      // blink envelope as COLON_BLINK, regardless of what colon mode is
      // actually configured. The real colon (hi/lo) is forced off for the
      // duration, regardless of the configured colon mode -- the warning
      // LED is the only thing that should be moving, so there's no chance
      // of it blending into whatever the colon would otherwise be doing.
      warn = even ? g_on : g_off;
    }
    switch (colonMode) {
      case COLON_OFF:                                    break;
      case COLON_STEADY:    hi = lo = 1.0f;              break;
      case COLON_BLINK:     hi = lo = even ? g_on : g_off;   break;
      case COLON_ALTERNATE: hi = even ? g_on : g_off;
                            lo = even ? g_off : g_on;        break;
      case COLON_BREATHE: {
        // One full breath per two seconds, phase-locked to the clock.
        // The raw cosine envelope (0..1) is passed through applyGamma() so
        // the selected curve reshapes the animation across its full range:
        // sqrt rises quickly and lingers bright, gamma lingers dark and
        // snaps up, smoothstep stays symmetric.
        // The accentDim floor is applied linearly AFTER the curve so its
        // percentage reads as the actual minimum brightness regardless of
        // which curve is selected (the old sqrtf-compensated minK was
        // calibrated for the former x³ only and broke with the other two).
        float breatheFloor = cfg.accentDim / 100.0f;
        float t = (ms / 1000.0f + (even ? 0.0f : 1.0f)) * 0.5f;
        float cosineK = 0.5f - 0.5f * cosf(t * 6.283185f);
        hi = lo = breatheFloor + (1.0f - breatheFloor) * applyGamma(cosineK);
        break;
      }
      case COLON_CENTERGLOW: {
        // Same breathe envelope as COLON_BREATHE, but the result drives the
        // whole five-LED column: centre at full, dots at outerFrac of that,
        // and the decorative accent LEDs at outerFrac of the outer fraction.
        // applyGamma() now applies to the raw cosine (0..1) before the floor
        // is added — previously k was used raw here so the curve selector had
        // no effect at all on this mode.
        float outerFrac    = cfg.colonOuterPct / 100.0f;
        float breatheFloor = cfg.accentDim / 100.0f;
        float t = (ms / 1000.0f + (even ? 0.0f : 1.0f)) * 0.5f;
        float cosineK = 0.5f - 0.5f * cosf(t * 6.283185f);
        centerGlow = breatheFloor + (1.0f - breatheFloor) * applyGamma(cosineK);
        hi = lo    = centerGlow * sqrtf(outerFrac);
        break;
      }
    }

    if (untrusted) {
      hi = 0;
      lo = 0;
    }

    auto setLed = [&](int i, float k) {
      // Delta-Sigma quantization error tracking with strict clamping. The
      // error term is what makes a fractional-count target look smooth by
      // averaging out over several frames -- e.g. a target of 30.5 renders
      // as 30, 31, 30, 31... which the eye reads as "30.5". That's exactly
      // the wrong thing to do near true black, though: a target under one
      // count still gets its error "paid out" as an occasional stray 1,
      // which reads as a flash against nothing rather than a smooth
      // in-between shade the eye can average. A first attempt fixed that by
      // hard-clamping to (0,0,0) below a brightness floor, but that traded
      // the flash for a visible snap at the bottom of every fade -- see the
      // "near black" branch below for what actually wants to happen instead:
      // still render the plain truncated value (continuous, no snap), just
      // stop feeding its rounding error back into future frames (no more
      // stray flashes) and don't carry over whatever error was already
      // sitting there from before brightness dropped this low.
      float target = base * k;
      //bool nearBlack = (target * maxComp) < 2.0f;   // roughly under a visible count on every channel
      float maxComp = fmaxf(fmaxf((float)cfg.colonR, (float)cfg.colonG), fmaxf((float)cfg.colonB, 1.0f));
      float totalIntensity = target * maxComp;

      float dampening = 1.0f;
      if (totalIntensity < 0.15f) {
        dampening = totalIntensity / 0.15f;
      }

      // Compute the ideal color values including carried-over Delta-Sigma error
      float idealR = cfg.colonR * target + (dsError[i][0] * dampening);
      float idealG = cfg.colonG * target + (dsError[i][1] * dampening);
      float idealB = cfg.colonB * target + (dsError[i][2] * dampening);

      // Quantize to integer levels suitable for 8-bit WS2812 registers
      uint8_t r = (idealR >= 255.0f) ? 255 : ((idealR <= 0.0f) ? 0 : (uint8_t)idealR);
      uint8_t g = (idealG >= 255.0f) ? 255 : ((idealG <= 0.0f) ? 0 : (uint8_t)idealG);
      uint8_t b = (idealB >= 255.0f) ? 255 : ((idealB <= 0.0f) ? 0 : (uint8_t)idealB);

      // Dynamic Error Dampening:
      // Calculate total channel intensity for the current target.
      // As target intensity drops below ~2.0 total 8-bit counts across all channels,
      // decay factor scale smoothly drops from 1.0 down to 0.0.
      // float maxComp = fmaxf(fmaxf((float)cfg.colonR, (float)cfg.colonG), fmaxf((float)cfg.colonB, 1.0f));
      // float totalIntensity = target * maxComp;
      // float dampening = (totalIntensity >= 2.0f) ? 1.0f : (totalIntensity / 2.0f);
      
      // Apply dampening to residual quantization error before passing to the next frame.
      // This prevents temporal error accumulation from triggering visible single-frame flashes
      // while preserving an imperceptible, smooth decay down to absolute zero.
      dsError[i][0] = (idealR - r);
      dsError[i][1] = (idealG - g);
      dsError[i][2] = (idealB - b);
      
      px[i][0] = r;
      px[i][1] = g;
      px[i][2] = b;
    };
    
    if (colonMode == COLON_BREATHE || colonMode == COLON_CENTERGLOW) {
      setLed(COLON_DOT_HI, hi);
      setLed(COLON_DOT_LO, lo);
    } else {
      setLed(COLON_DOT_HI, hi);
      setLed(COLON_DOT_LO, lo);
    }
    if (untrusted) setLed(COLON_WARN_LED, warn);

    // The two purely decorative LEDs (top and middle). The bottom one is
    // skipped here whenever it's doing warning duty, so the accent setting
    // can never fight the blink.
    float acc = 0;
    if (!untrusted) {
      if (cfg.colonAccent == 1) {
        // Use a squared curve instead of cubic one for a gentler roll-off
        float dimLinear = cfg.accentDim / 100.0f;
        acc = dimLinear * sqrtf(dimLinear);
        //if (acc > 0.0f && acc < 0.02f) acc = 0.02f;
      }
      else if (cfg.colonAccent == 2) {
        if (colonMode == COLON_ALTERNATE) {
          acc = 0.0f;                      // Disable match the colon when Alternate is active
        } else {
          acc = (hi > lo ? hi : lo);       // match colon
        }
      }
    }

    
    if (colonMode == COLON_CENTERGLOW && !untrusted) {
      // Centre (2) at full animation; extremes (0, 4) at colonOuterPct% of
      // that level; dots (1, 3) at the geometric mean — already written by
      // the setLed(COLON_DOT_HI/LO, hi/lo) calls above.
      // colonAccent has no separate effect in this mode: all five LEDs are
      // part of the gradient and always lit.
      float outerFrac = cfg.colonOuterPct / 100.0f;
      setLed(2, centerGlow);
      setLed(0,              centerGlow * outerFrac);
      setLed(COLON_WARN_LED, centerGlow * outerFrac);
    } else if (acc > 0) {
      setLed(0, acc);
      setLed(2, acc);
      if (!untrusted) setLed(COLON_WARN_LED, acc);
    }

    // Only trigger the RMT driver if the LED states actually changed
    bool changed = false;
    for (int i = 0; i < WS2812_COUNT; i++) {
      for (int j = 0; j < 3; j++) {
        if (px[i][j] != lastPx[i][j]) changed = true;
        lastPx[i][j] = px[i][j];
      }
    }
    
    if (changed) ws2812_write_all(px);
    
    // Evaluate the fractional brightness at 500Hz for buttery-smooth dithering
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

// ---- Interface implementation ---------------------------------------------

void display_init() {
  // Load any pin overrides that were saved via the web action.
  loadPinOverrides();

  for (int i = 0; i < 4; i++) { pinMode(PIN_BCD[i], OUTPUT); digitalWrite(PIN_BCD[i], LOW); }
  for (int i = 0; i < BOARD_TUBES; i++) { pinMode(PIN_ANODE[i], OUTPUT); digitalWrite(PIN_ANODE[i], LOW); }
  
  buildMasks();

  for (int i = 0; i < BOARD_TUBES; i++) {
    shOld[i] = shNew[i] = BLANK; shFade[i] = 255; pushTube(i); vOnTicks[i] = 0;
  }

  // WS2812 chain via RMT (ESP-IDF driver)
  rmt_config_t rc = {};
  rc.rmt_mode                = RMT_MODE_TX;
  rc.channel                 = WS_CHAN;
  rc.gpio_num                = (gpio_num_t)PIN_WS2812;
  rc.clk_div                 = WS_CLK_DIV;
  rc.mem_block_num           = 1;
  rc.tx_config.loop_en       = false;
  rc.tx_config.carrier_en    = false;
  rc.tx_config.idle_output_en= true;
  rc.tx_config.idle_level    = RMT_IDLE_LEVEL_LOW;
  rmt_config(&rc);
  rmt_driver_install(WS_CHAN, 0, 0);
  ws2812_clear();

  xTaskCreatePinnedToCore(fadeTask, "fade", 2048, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(colonTask, "colon", 2048, nullptr, 3, nullptr, 1);

  // Multiplex timer
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  muxTimer = timerBegin(1000000);
  timerAttachInterrupt(muxTimer, &onMuxTick);
  timerAlarm(muxTimer, TICK_US, true, 0);
#else
  muxTimer = timerBegin(0, 80, true);
  timerAttachInterrupt(muxTimer, &onMuxTick, true);
  timerAlarmWrite(muxTimer, TICK_US, true);
  timerAlarmEnable(muxTimer);
#endif
}

void display_setDigits(const uint8_t digits[BOARD_TUBES], uint16_t fadeMs) {
  bool changed = false;
  for (int i = 0; i < BOARD_TUBES; i++) {
    if (shNew[i] == digits[i] && shOld[i] == digits[i]) continue;
    // If a fade was in progress the "old" value should be whatever is
    // currently visible, so the display doesn't snap backwards.
    shOld[i]  = fadeMs ? shNew[i] : digits[i];
    shNew[i]  = digits[i];
    shFade[i] = fadeMs ? 0 : 255;
    pushTube(i);
    changed = true;
  }
  if (!changed) return;
  if (fadeMs) { fadeStartMs = millis(); fadeDurMs = fadeMs; }
  else        { fadeDurMs = 0; }
}

void display_setColon(ColonMode mode) { colonMode = mode; }

void display_setBrightness(uint8_t percent) {
  effBright = percent;
  // Perceptual gamma, then per-tube trim
  uint16_t g = ((uint16_t)percent * percent) / 100;
  for (int i = 0; i < BOARD_TUBES; i++) {
    uint16_t v = ((uint16_t)ACTIVE_TICKS * g) / 100;
    v = (v * cfg.trim[i]) / 100;
    if (percent > 0 && v == 0) v = 1;
    vOnTicks[i] = (uint8_t)v;
  }
}

void display_tick_100ms() {
  // Re-apply the wiring order if the user changed it in the web UI.
  static uint8_t lastCath[10], lastAnode[BOARD_TUBES];
  static bool first = true;
  if (first || memcmp(lastCath, cfg.cathOrder, 10) || memcmp(lastAnode, cfg.anodeOrder, BOARD_TUBES)) {
    memcpy(lastCath, cfg.cathOrder, 10);
    memcpy(lastAnode, cfg.anodeOrder, BOARD_TUBES);
    if (!first) buildMasks();
    first = false;
  }
}

static uint16_t muxHealth = 100, muxMin = 100;
void display_tick_1s() {
  uint32_t t = muxTicks; muxTicks = 0;
  uint32_t expect = 1000000UL / TICK_US;
  muxHealth = (uint16_t)((t * 100 + expect / 2) / expect);
  if (muxHealth < muxMin) muxMin = muxHealth;
}

void display_park(bool parked) {
  muxHold = parked;
  if (parked) {
    ws2812_clear();
  } else {
    isrCurBcd = 255;
  }
}

void display_snapshot(char *out, int n) {
  int m = BOARD_TUBES < n - 1 ? BOARD_TUBES : n - 1;
  for (int i = 0; i < m; i++)
    out[i] = (shNew[i] <= 9) ? ('0' + shNew[i]) : ' ';
  out[m] = 0;
}

void display_getStatus(DisplayStatus &s) {
  s.hv        = 0;          // NCH8200HV is sealed: nothing to report
  s.duty      = 0;
  s.hvFault   = false;
  s.hvCuts    = 0;
  s.muxHealth = muxHealth;
  s.muxMin    = muxMin;
  bool even   = core_secondIsEven();
  // colon0/colon1 track the two real colon dots. They're forced off during
  // the "time not trusted" warning, same as the real hardware -- see
  // colonTask -- so the preview doesn't show them animating while the
  // actual LEDs are dark. The warning LED itself lives on its own dedicated
  // lamp (see the file header), which this two-dot preview has no slot for
  // and so doesn't show either way.
  if (!core_timeTrusted()) {
    s.colon0 = false;
    s.colon1 = false;
  } else {
    s.colon0  = (colonMode == COLON_STEADY) || (colonMode == COLON_BREATHE) ||
                (colonMode == COLON_BLINK && even) ||
                (colonMode == COLON_ALTERNATE && even);
    s.colon1  = (colonMode == COLON_STEADY) || (colonMode == COLON_BREATHE) ||
                (colonMode == COLON_BLINK && even) ||
                (colonMode == COLON_ALTERNATE && !even);
  }
  s.hasLight  = false;      // no sensor on this board
  s.lightMv   = 0;
  s.lightPP   = 0;
}

// ---- Sanity checks --------------------------------------------------------
#if BOARD_HAS_HV || BOARD_HAS_BUZZER
  #error "board.h capabilities disagree with display_nick2.cpp"
#endif

#endif // BOARD == BOARD_NICK2_IN12