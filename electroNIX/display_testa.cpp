// ============================================================================
//  display_testa.cpp — TESTA-QUADRA boards converted to ESP32
//
//  Covers four boards that share an electrical design:
//    electroNIX 4+S 6 x IN-12, IRLR3110Z; seconds tubes added to the electroNIX 4,
//                   both colon positions wired in parallel. Also the target for
//                   fresh ESP32 retrofits of the electroNIX 2 PCB
//                   (BOARD_ELECTRONIX_2 is obsolete — use BOARD_ELECTRONIX_4_6T).
//    electroNIX 4   PCB-061, 2014, 4 x LC-513/531, IRLR3110Z boost switch
//    electroNIX 3   PCB-036, 2013, 4 x ZM1080T, single colon neon, IRLR3110Z
//    fourTINY       rev 11-11-2013, 4 x LC-516
//
//  All drive ten cathodes and N anodes from discrete NPN switches behind
//  33 k base resistors, regulate a 170 V boost converter in software from a
//  430 k / 6.2 k feedback divider, and read ambient light from a phototransistor
//  on a 1 M pull-up. See WIRING.md for tap points and the gate-driver
//  requirement on the two boards fitted with an IRF840.
//
//  Colon behaviour: SEC_0/SEC_1 are driven by hardware PWM (see "Neon colon
//  dimming" below) rather than a plain digitalWrite, so they cross-fade
//  smoothly and BREATHE is a real breath rather than degrading to a blink.
//  Whenever core_timeTrusted() is false, SEC_1 is taken over as a dedicated
//  "don't trust this time" indicator and blinks at 1 Hz regardless of the
//  configured mode; SEC_0 is forced off so the warning reads as a distinct
//  state rather than blending into whatever the colon was already doing.
//
//  electroNIX 3 ships with only one colon neon (SEC_0) from the factory --
//  there's no SEC_1 net on that schematic at all -- but the firmware still
//  supports a second one, wired as a bodge (see WIRING.md): PIN_NEON1 = 5,
//  same convention as electroNIX 4 and fourTINY. Whether it's actually there
//  is a runtime choice, cfg.neon1Fitted, exposed in the web UI only on
//  boards where board.h's BOARD_NEON1_OPTIONAL says it's genuinely a
//  per-unit question rather than a fixed hardware fact. applyColon() below
//  is one function that branches on that flag: with SEC_1 available, the
//  usual two-lamp behaviour; without it, SEC_0 does double duty, rendering
//  the configured colon mode most of the time and switching over to the
//  warning blink pattern instead of it being silently invisible. ALTERNATE
//  has nothing to alternate with on one lamp, so it falls back to STEADY.
//
//  That warning blinks from power-on, not just once NTP has had a chance to
//  fail: applyColon() runs from fadeTask, a FreeRTOS task started in
//  display_init(), so it keeps ticking during the up-to-20-second blocking
//  WiFi connection attempt in core_setup() -- core_loop() (and with it, the
//  core's own 100 ms tick) doesn't start until that returns. effBright and
//  hvEnable both start non-zero/true rather than their usual 0/false for the
//  same reason: hvTask is likewise independent of the core, and the neons
//  run off the same 170 V rail as the tubes, so without HV already coming up
//  the warning would have nothing to strike against. One small side effect:
//  on a reboot that happens to land inside a configured night-mode window,
//  the colon may briefly light before the core's first real
//  display_setBrightness() call corrects it a few seconds later.
// ============================================================================
#include "board.h"
#if BOARD == BOARD_ELECTRONIX_4 || BOARD == BOARD_ELECTRONIX_3 || BOARD == BOARD_ELECTRONIX_4_6T

#include "display.h"
#include "clock_core.h"

#if __has_include(<hal/gpio_ll.h>)
  #include <hal/gpio_ll.h>
#endif
#include <soc/gpio_struct.h>

// ---- Pin maps --------------------------------------------------------------
#if BOARD == BOARD_ELECTRONIX_4_6T
  // Six-tube board. GPIO12 (former buzzer) is W_5; GPIO0 is the buzzer.
  // GPIO15 is W_6 when no LED backlight, or becomes PIN_LEDBL when
  // BOARD_HAS_LED_BL is 1 — in that case W_6 moves to GPIO1 (the pin the
  // electroNIX 2 originally used for the LED before the DS3231 retrofit
  // displaced it). board.h guards against BOARD_HAS_RTC being set at the
  // same time, since GPIO1 can only serve one master.
  //
  // Boot-safety pull-ups (≥10 kΩ to 3V3) REQUIRED on GPIO0 and GPIO15:
  // GPIO0 (buzzer, normally LOW) and GPIO15 (W_6 or LED backlight, BJT base
  // load) are both strapping pins; without external pull-ups the 33 kΩ base
  // network pulls them below the 2.31 V HIGH threshold at reset, risking
  // download-mode entry. GPIO12 (W_5) is not a strapping pin — no pull-up.
  //
  // GPIO1 (TX) is briefly driven HIGH by the bootloader at reset. As W_6
  // anode (BOARD_HAS_LED_BL 1 case), the tube cannot strike without HV —
  // harmless glitch, same argument as in the 4+S section of WIRING.md.
#if BOARD_HAS_LED_BL
  // LED backlight fitted: W_6 on GPIO1, LED on GPIO15.
  static const uint8_t ANODE_PINS[BOARD_TUBES] = {16, 17, 18, 19, 12, 1};
  static const uint8_t PIN_LEDBL = 15;
#else
  // No LED backlight: W_6 on GPIO15, GPIO1 free for DS3231 I2C SDA.
  static const uint8_t ANODE_PINS[BOARD_TUBES] = {16, 17, 18, 19, 12, 15};
#endif
  static const uint8_t CATHODE_PINS[10] = {13, 14, 21, 22, 23, 25, 26, 27, 32, 33};
  static const uint8_t PIN_NEON0 = 4;   // SEC_0, unchanged from 4-tube boards
  static const uint8_t PIN_NEON1 = 5;   // SEC_1, unchanged from 4-tube boards
#else
  // Four-tube boards: electroNIX 4 and electroNIX 3.
  // fourTINY users should select BOARD_ELECTRONIX_4 — the pin maps are
  // identical; only the IRF840 boost FET differs (fit a gate driver or a
  // logic-level replacement, then the same firmware applies).
  // Serial is disabled on all builds (BOARD_USE_SERIAL 0); GPIO1 and GPIO3
  // are free for the optional DS3231 RTC module (I2C SDA and SCL).
  static const uint8_t ANODE_PINS[BOARD_TUBES] = {16, 17, 18, 19};
  static const uint8_t CATHODE_PINS[10] = {13, 14, 21, 22, 23, 25, 26, 27, 32, 33};
  static const uint8_t PIN_NEON0 = 4;
  static const uint8_t PIN_NEON1 = 5;   // stock electroNIX 3 has no SEC_1 net --
                                          // this is where to land the bodge if
                                          // you add one (see WIRING.md). Driving
                                          // an unpopulated pin is harmless.
#endif
static const uint8_t PIN_HV_PWM   = 2;     // boot pull-down keeps the FET off
// GPIO0 is a strapping pin (LOW at reset = UART download mode). The buzzer
// is silent at LOW, so without an external pull-up the chip would misboot.
// Fit ≥10 kΩ to 3V3 on GPIO0 — the same requirement as GPIO15 on 6-tube
// boards. The buzzer defaults disabled (cfg.buzzerEn = false, see
// clock_core.h), so GPIO0 is nearly always LOW; the pull-up covers the gap.
// Former GPIO12 is now free on 4-tube boards; on 6-tube boards it carries
// anode W_5 (electroNIX 4+S) or SEC_1 colon neon (electroNIX 2).
static const uint8_t PIN_BUZZER   = 0;
static const uint8_t PIN_HV_SENSE = 35;    // KOMP_170V
static const uint8_t PIN_LIGHT    = 34;    // JASNOSC

// ---- HV regulation ---------------------------------------------------------
static const float    HV_DIV_RATIO = (430.0f + 6.2f) / 6.2f;   // 70.35 on all three
static const uint32_t HV_PWM_FREQ  = 32000;   // matches the original AVR firmware
static const uint8_t  HV_PWM_RES   = 10;
static const uint32_t HV_DUTY_MAX  = 700;     // ~41 % absolute clamp
static const float    HV_OV_CUT    = 12.0f;

// ---- Neon colon dimming -----------------------------------------------------
// Neon indicator lamps are cold-cathode glow-discharge devices -- the same
// family as the nixie tubes themselves, just tiny and run at a fraction of
// the current (the schematics spec ~0.3 mA through the 430 k series
// resistor, against a couple of mA for a lit digit). The nixie multiplex
// already proves the underlying idea works: strike at a fixed current,
// vary the fraction of time spent lit, and 100 Hz-plus is fast enough that
// nobody sees the individual strikes. This applies the same principle to
// the colon neons via the ESP32's hardware PWM instead of digitalWrite.
//
// Two things are different from the nixie tubes, though, and both are
// engineering judgement rather than anything measured on real hardware:
//  - 1 kHz (matching the LED backlight's PWM) rather than the nixie
//    multiplex's ~100 Hz frame, to keep comfortably clear of flicker with
//    margin to spare, since a bare glow-discharge lamp has no phosphor
//    persistence to smooth out any judder the way an LED or nixie digit
//    would.
//  - A hard floor on the minimum duty cycle (NEON_PWM_FLOOR). At 0.3 mA
//    already, cutting the average current further via a very short pulse
//    risks the lamp not making it through a full ionise/sustain/deionise
//    cycle before the next strike, which would show up as flicker at the
//    low end rather than a smooth fade to dark. The floor below trades a
//    small jump right at "just lit" for avoiding that.
// If dimming looks uneven or flickery on your board, NEON_PWM_FREQ and
// NEON_PWM_FLOOR are the two constants to retune -- there's no datasheet
// figure for these specific lamps to derive them from.
static const uint32_t NEON_PWM_FREQ  = 1000;
static const uint8_t  NEON_PWM_RES   = 8;     // 0..255
static const uint8_t  NEON_PWM_FLOOR = 18;    // ~7 %, the lowest "on" duty used

// ---- Multiplex timing ------------------------------------------------------
static const uint32_t TICK_US    = 25;
static const uint32_t FRAME_US   = 10000;                       // 100 Hz
static const uint8_t  SLOT_TICKS = FRAME_US / (BOARD_TUBES * TICK_US);
static const uint8_t  ACTIVE_TICKS = SLOT_TICKS - 1;
static const uint8_t  BLANK      = 15;

// ---- ISR state -------------------------------------------------------------
static volatile DRAM_ATTR uint32_t tubeWord[BOARD_TUBES];
static volatile DRAM_ATTR uint8_t  vOnTicks[BOARD_TUBES];
static volatile DRAM_ATTR bool     muxHold = false;
static volatile DRAM_ATTR uint8_t  isrCurCath = 255;
static volatile DRAM_ATTR uint32_t muxTicks = 0;
static DRAM_ATTR uint32_t cathM0[11], cathM1[11];
static DRAM_ATTR uint32_t allCathM0 = 0, allCathM1 = 0;
static DRAM_ATTR uint32_t anodeM0[BOARD_TUBES], anodeM1[BOARD_TUBES];
static DRAM_ATTR uint32_t allAnodeM0 = 0, allAnodeM1 = 0;
static hw_timer_t *muxTimer = nullptr;

static uint8_t shOld[BOARD_TUBES], shNew[BOARD_TUBES], shFade[BOARD_TUBES];
static inline void pushTube(int i) {
  tubeWord[i] = ((uint32_t)shFade[i] << 16) | ((uint32_t)shNew[i] << 8) | shOld[i];
}

// ---- Multiplex ISR ---------------------------------------------------------
// Lock-free: each tube's state is one 32-bit word, stored atomically, so no
// spinlock is needed and nothing in loop() can mask this interrupt.
void IRAM_ATTR onMuxTick() {
  static uint8_t slot = 0, tick = 0;
  uint8_t curCath = isrCurCath;
  muxTicks++;

  if (++tick >= SLOT_TICKS) { tick = 0; if (++slot >= BOARD_TUBES) slot = 0; }

  if (muxHold) {
    GPIO.out_w1tc      = allCathM0 | allAnodeM0;
    GPIO.out1_w1tc.val = allCathM1 | allAnodeM1;
    isrCurCath = 255;
    return;
  }

  if (tick == 0) {                            // dead-time between tubes
    GPIO.out_w1tc      = allCathM0 | allAnodeM0;
    GPIO.out1_w1tc.val = allCathM1 | allAnodeM1;
    isrCurCath = 255;
    return;
  }

  uint8_t on = vOnTicks[slot];
  if (tick > on) {                            // brightness blanking
    if (tick == (uint8_t)(on + 1)) {
      GPIO.out_w1tc      = allCathM0 | allAnodeM0;
      GPIO.out1_w1tc.val = allCathM1 | allAnodeM1;
      isrCurCath = 255;
    }
    return;
  }

  uint32_t w = tubeWord[slot];
  uint8_t oldD = (uint8_t)w, newD = (uint8_t)(w >> 8), fade = (uint8_t)(w >> 16);
  uint8_t newTicks = (uint8_t)(((uint16_t)on * fade + 127) / 255);
  uint8_t d = (tick <= (uint8_t)(on - newTicks)) ? oldD : newD;
  if (d > 9) d = 10;

  if (d != curCath) {
    GPIO.out_w1tc      = allCathM0;
    GPIO.out1_w1tc.val = allCathM1;
    GPIO.out_w1ts      = cathM0[d];
    GPIO.out1_w1ts.val = cathM1[d];
    isrCurCath = d;
  }
  if (d <= 9) { GPIO.out_w1ts = anodeM0[slot]; GPIO.out1_w1ts.val = anodeM1[slot]; }
  else        { GPIO.out_w1tc = anodeM0[slot]; GPIO.out1_w1tc.val = anodeM1[slot]; }
}

// ---- Core 2.x / 3.x shims --------------------------------------------------
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
static void hvPwmSetup()          { ledcAttach(PIN_HV_PWM, HV_PWM_FREQ, HV_PWM_RES); }
static void hvPwmRaw(uint32_t d)  { ledcWrite(PIN_HV_PWM, d); }
static void neonPwmSetup() {
  ledcAttach(PIN_NEON0, NEON_PWM_FREQ, NEON_PWM_RES);
  ledcAttach(PIN_NEON1, NEON_PWM_FREQ, NEON_PWM_RES);
}
static void neonPwmWrite(uint8_t which, uint32_t duty) {
  ledcWrite(which ? PIN_NEON1 : PIN_NEON0, duty);
}
#if BOARD_HAS_LED_BL
static void blPwmSetup()          { ledcAttach(PIN_LEDBL, 1000, 8); }
static void blPwmWrite(uint32_t d){ ledcWrite(PIN_LEDBL, d); }
#endif
static void muxTimerSetup() {
  muxTimer = timerBegin(1000000);
  timerAttachInterrupt(muxTimer, &onMuxTick);
  timerAlarm(muxTimer, TICK_US, true, 0);
}
#else
static void hvPwmSetup()          { ledcSetup(0, HV_PWM_FREQ, HV_PWM_RES); ledcAttachPin(PIN_HV_PWM, 0); }
static void hvPwmRaw(uint32_t d)  { ledcWrite(0, d); }
// Channels 0 and 2 are already taken by the HV gate and (where fitted) the
// LED backlight; the neons get 3 and 4.
static void neonPwmSetup() {
  ledcSetup(3, NEON_PWM_FREQ, NEON_PWM_RES); ledcAttachPin(PIN_NEON0, 3);
  ledcSetup(4, NEON_PWM_FREQ, NEON_PWM_RES); ledcAttachPin(PIN_NEON1, 4);
}
static void neonPwmWrite(uint8_t which, uint32_t duty) { ledcWrite(which ? 4 : 3, duty); }
#if BOARD_HAS_LED_BL
static void blPwmSetup()          { ledcSetup(2, 1000, 8); ledcAttachPin(PIN_LEDBL, 2); }
static void blPwmWrite(uint32_t d){ ledcWrite(2, d); }
#endif
static void muxTimerSetup() {
  muxTimer = timerBegin(0, 80, true);
  timerAttachInterrupt(muxTimer, &onMuxTick, true);
  timerAlarmWrite(muxTimer, TICK_US, true);
  timerAlarmEnable(muxTimer);
}
#endif

// Maps a 0..1 brightness fraction onto a PWM duty, with the sustain floor
// described above. 0 stays genuinely 0 (lamp fully off); anything above 0
// jumps to at least NEON_PWM_FLOOR rather than fading smoothly through it.
static uint32_t neonDuty(float k) {
  if (k <= 0.0f) return 0;
  if (k >= 1.0f) return (1UL << NEON_PWM_RES) - 1;
  const uint32_t full = (1UL << NEON_PWM_RES) - 1;
  // Ramp linearly through the floor region (k ~0..7%) rather than jumping
  // to NEON_PWM_FLOOR immediately.  The lamp extinguishes naturally as its
  // duty falls through the sustain threshold during a fade-off, giving a
  // smooth dim-out instead of the previous abrupt cut.  Any flicker in the
  // threshold-crossing window is transient and far less jarring than a hard
  // snap to dark.  Above the floor fraction the mapping is unchanged.
  const float floorFrac = NEON_PWM_FLOOR / (float)full;
  if (k < floorFrac)
    return (uint32_t)(k / floorFrac * NEON_PWM_FLOOR);
  return NEON_PWM_FLOOR +
         (uint32_t)((k - floorFrac) / (1.0f - floorFrac) * (full - NEON_PWM_FLOOR));
}

static inline void hvPwmWrite(uint32_t duty) {
#if HV_PWM_INVERT
  hvPwmRaw(((1UL << HV_PWM_RES) - 1) - duty);
#else
  hvPwmRaw(duty);
#endif
}

// ---- HV regulator ----------------------------------------------------------
// hvEnable starts true on purpose, for the same reason effBright starts
// non-zero (see the comment above fadeTask): hvTask already runs
// independently from display_init(), well before the core calls
// display_setBrightness() with a real target. The neons run off this same
// 170 V rail, so without this the boot-time colon warning would be
// commanding PWM into a lamp with no high voltage behind it yet -- visibly
// nothing, regardless of what applyColon() computes. The very first real
// display_setBrightness() call (whether that's after a normal WiFi connect
// or after falling back to the setup AP) immediately overrides this to
// whatever brightness/night-mode policy actually applies, so this only
// affects the first few seconds of boot.
static volatile bool  hvEnable = true, hvFault = false;
static volatile float hvVolts = 0, hvDutyPct = 0;
static volatile uint32_t hvCuts = 0;

// Trimmed mean of four samples. The SAR ADC throws occasional wild readings
// and the 70:1 divider turns one outlier into tens of volts.
static float readHv() {
  float a[4];
  for (int i = 0; i < 4; i++) a[i] = analogReadMilliVolts(PIN_HV_SENSE);
  for (int i = 1; i < 4; i++)
    for (int j = i; j > 0 && a[j] < a[j-1]; j--) { float t=a[j]; a[j]=a[j-1]; a[j-1]=t; }
  return (a[1] + a[2]) * 0.5f * 0.001f * HV_DIV_RATIO * cfg.hvTrim;
}

static void hvTask(void *) {
  uint32_t duty = 0;
  uint16_t faultCnt = 0;
  uint8_t  ovCnt = 0;
  for (;;) {
    float v = readHv();
    hvVolts = v;
    float target = (float)cfg.hvSet;
    float err = target - v;

    if (!hvEnable || hvFault) { duty = 0; ovCnt = 0; }
    else if (v > target + HV_OV_CUT) {
      // Require persistence before acting, and back off rather than to zero,
      // so a glitch is a brief dip instead of a half-second fade back up.
      if (++ovCnt >= 3) { duty = (duty * 7) / 10; ovCnt = 0; hvCuts++; }
    } else {
      ovCnt = 0;
      if      (err >  25.0f) duty += 4;
      else if (err >   2.0f) duty += 1;
      else if (err < -25.0f) duty = (duty > 4) ? duty - 4 : 0;
      else if (err <  -2.0f) duty = (duty > 1) ? duty - 1 : 0;
      if (duty > HV_DUTY_MAX) duty = HV_DUTY_MAX;
    }

    // Near-max duty with no voltage means the divider or converter is open;
    // shut down rather than run open-loop.
    if (duty >= HV_DUTY_MAX && v < 40.0f) {
      if (++faultCnt > 500) { hvFault = true; duty = 0; }
    } else faultCnt = 0;

    hvDutyPct = 100.0f * duty / ((1 << HV_PWM_RES) - 1);
    hvPwmWrite(duty);
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

// ---- Light sensor ----------------------------------------------------------
static float    lightMv = 2000;
static uint16_t lightPP = 0;

// The sensor sits behind a 1 M pull-up, far above what the SAR ADC likes, so
// oversample and discard the extremes. The raw spread is reported so the web
// UI can show how much noise is arriving.
static float readLight() {
  float a[16];
  for (int i = 0; i < 16; i++) a[i] = analogReadMilliVolts(PIN_LIGHT);
  for (int i = 1; i < 16; i++)
    for (int j = i; j > 0 && a[j] < a[j-1]; j--) { float t=a[j]; a[j]=a[j-1]; a[j-1]=t; }
  lightPP = (uint16_t)(a[15] - a[0]);
  float sum = 0;
  for (int i = 4; i < 12; i++) sum += a[i];
  return sum / 8.0f;
}

// ---- Colon neons -----------------------------------------------------------
static ColonMode colonMode = COLON_BLINK;
static bool colon0On = false, colon1On = false;
// Starts non-zero on purpose: applyColon() runs from fadeTask from the
// moment display_init() returns, well before the core has connected to
// WiFi and called display_setBrightness() with a real target (connectWiFi()
// blocks setup() for up to 20 s). Without this, the "time not trusted"
// warning -- and the colon generally -- would render at 0% and be
// invisible for that whole window instead of showing the clock is alive.
static uint8_t effBright = 60;

// Whether SEC_1 exists on this board at all (a hardware fact, board.h) is
// separate from whether it's actually wired up on this particular unit (a
// runtime choice, cfg.neon1Fitted -- see the comment on that field). This
// function branches on the second, guarded by the first, so a board with no
// PIN_NEON1 in its pin map at all can't be told at runtime to drive one.
static void applyColon() {
  if (muxHold) return;   // display parked (OTA, flash write, wiring rebuild)
  bool even = core_secondIsEven();
  uint16_t ms = core_msIntoSecond();

  // Ease across the second boundary instead of snapping, the same idea as
  // the digit cross-fade and the Nick2's colon dots -- capped well inside a
  // second so it always settles before the next tick regardless of what
  // cfg.fadeMs is set to (that setting is really about the nixie digits).
  uint16_t fMs = cfg.fadeMs; if (fMs == 0) fMs = 1; if (fMs > 900) fMs = 900;
  float p = (float)ms / fMs; if (p > 1.0f) p = 1.0f;
  // Gentler than the WS2812 colon's cubic curve: these lamps have far less
  // usable dimming range, so spending less of it right at the low end
  // leaves more of the fade actually visible rather than compressed near
  // full brightness.
  auto gamma = [](float x) { return x * x; };
  float g_on = gamma(p), g_off = gamma(1.0f - p);

  bool dual = BOARD_DUAL_NEON && cfg.neon1Fitted;

  float a = 0, b = 0;
  if (effBright > 0) {
    if (dual) {
      switch (colonMode) {
        case COLON_OFF:                                   break;
        case COLON_CENTERGLOW:  // no independent centre LED on neon boards
        case COLON_STEADY:    a = b = 1.0f;               break;
        case COLON_BLINK:     a = b = even ? g_on : g_off;   break;
        case COLON_ALTERNATE: a = even ? g_on : g_off;
                              b = even ? g_off : g_on;        break;
        case COLON_BREATHE: {
          // One full breath every two seconds, smoothly eased by the cosine.
          // k is used directly here (no gamma()) because eGamma in the master
          // below already applies the perceptual correction; squaring k on top
          // of that (as gamma(k) would do) compresses the low end so hard that
          // the breathe minimum drops below the lamp's sustain threshold and
          // it extinguishes -- which looks identical to blink.
          float t = (ms / 1000.0f + (even ? 0.0f : 1.0f)) * 0.5f;
          float k = 0.15f + 0.85f * (0.5f - 0.5f * cosf(t * 6.283185f));
          a = b = k;
          break;
        }
      }
      // SEC_1 is dedicated to the "don't trust this time" warning when the
      // time isn't trusted; SEC_0 is forced off so it reads as a distinct
      // state rather than blending into whatever the colon was doing.
      if (!core_timeTrusted()) { b = even ? g_on : g_off; a = 0.0f; }
    } else {
      // One lamp only -- SEC_0 does double duty. ALTERNATE has nothing to
      // alternate with, so it falls back to STEADY.
      switch (colonMode) {
        case COLON_OFF:                                 break;
        case COLON_CENTERGLOW:  // no independent centre LED on neon boards
        case COLON_STEADY:
        case COLON_ALTERNATE: a = 1.0f;                 break;
        case COLON_BLINK:     a = even ? g_on : g_off;  break;
        case COLON_BREATHE: {
          float t = (ms / 1000.0f + (even ? 0.0f : 1.0f)) * 0.5f;
          float k = 0.15f + 0.85f * (0.5f - 0.5f * cosf(t * 6.283185f));
          a = k;   // no gamma() — see dual branch above
          break;
        }
      }
      if (!core_timeTrusted()) a = even ? g_on : g_off;   // takes over the one lamp
    }
  }

  // Apply the same perceptual gamma as display_setBrightness() uses for the
  // nixie tubes (g = effBright² / 10000), so the colon tracks the perceived
  // tube brightness rather than the raw linear percentage.  Without this,
  // the tubes dim quadratically at low effBright (night mode, manual low
  // setting) while the colon only dims linearly, leaving it visibly brighter
  // than the tubes -- most noticeable in night mode.
  //
  // colonBrNeon is then applied on top of that corrected level, so the
  // slider still lets the user set the colon relative to the tubes as
  // intended: 50 means "half as bright as the tubes", at any brightness.
  //
  // 0 → treated as 100 for backward compat (see clock_core.h comment).
  float eGamma = (effBright / 100.0f) * (effBright / 100.0f);
  uint8_t cnBr = cfg.colonBrNeon ? cfg.colonBrNeon : 100;
  float master = eGamma * (cnBr / 100.0f);
  a *= master; b *= master;

  colon0On = a > 0.02f;   // simple on/off for the web preview and getStatus
  colon1On = dual && (b > 0.02f);
  neonPwmWrite(0, neonDuty(a));
  neonPwmWrite(1, neonDuty(b));   // b is already 0 when !dual -- harmless either way
}

// ---- Buzzer ----------------------------------------------------------------
#if BOARD_HAS_BUZZER
static uint8_t  beepLeft = 0;
static uint16_t beepOn = 60, beepOff = 120;
static uint32_t beepNext = 0;
static bool     beepState = false;

void display_beep(uint8_t count, uint16_t onMs, uint16_t offMs) {
  if (!cfg.buzzerEn) return;   // disabled by default — enable in the web UI
  beepLeft = count; beepOn = onMs; beepOff = offMs;
  beepState = false; beepNext = millis();
}

static void serviceBeeper() {
  if (!beepLeft && !beepState) return;
  uint32_t now = millis();
  if ((int32_t)(now - beepNext) < 0) return;
  if (!beepState && beepLeft) {
    digitalWrite(PIN_BUZZER, HIGH); beepState = true; beepNext = now + beepOn;
  } else if (beepState) {
    digitalWrite(PIN_BUZZER, LOW); beepState = false; beepLeft--;
    beepNext = now + beepOff;
  }
}
#endif

// ---- Fade timeline (owned by this back-end) --------------------------------
// This task also drives the colon (applyColon, below) rather than leaving
// that to display_tick_100ms(). The core only calls display_tick_100ms()
// from its own loop, which doesn't run at all for the first several seconds
// of boot -- connectWiFi() blocks setup() for up to 20 s before core_loop()
// ever starts. A task started here in display_init() runs the whole time,
// which is what lets the "time not trusted" warning (see applyColon) blink
// from power-on instead of the colon sitting dark while WiFi connects.
static volatile uint16_t fadeDurMs = 0;
static volatile uint32_t fadeStartMs = 0;

static void fadeTask(void *) {
  for (;;) {
    if (fadeDurMs) {
      uint32_t el = millis() - fadeStartMs;
      uint16_t dur = fadeDurMs;
      uint8_t p = (el >= dur) ? 255 : (uint8_t)((el * 255UL) / dur);
      for (int i = 0; i < BOARD_TUBES; i++) {
        if (shOld[i] == shNew[i]) continue;
        shFade[i] = p;
        if (p == 255) shOld[i] = shNew[i];
        pushTube(i);
      }
      if (p == 255) fadeDurMs = 0;
    }
    applyColon();
#if BOARD_HAS_BUZZER
    serviceBeeper();
#endif
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ---- Wiring order ----------------------------------------------------------
// cfg.cathOrder[d] selects which wired cathode lights digit d; cfg.anodeOrder
// does the same for tube positions. Rebuilt live when the user saves.
static void buildMasks() {
  muxHold = true;
  delayMicroseconds(TICK_US * 2);
  GPIO.out_w1tc      = allCathM0 | allAnodeM0;
  GPIO.out1_w1tc.val = allCathM1 | allAnodeM1;
  allCathM0 = allCathM1 = allAnodeM0 = allAnodeM1 = 0;
  isrCurCath = 255;

  for (int d = 0; d < 10; d++) {
    uint8_t idx = (cfg.cathOrder[d] < 10) ? cfg.cathOrder[d] : d;
    uint8_t pin = CATHODE_PINS[idx];
    cathM0[d] = (pin < 32) ? (1UL << pin) : 0;
    cathM1[d] = (pin < 32) ? 0 : (1UL << (pin - 32));
    allCathM0 |= cathM0[d]; allCathM1 |= cathM1[d];
  }
  cathM0[10] = cathM1[10] = 0;                        // blank entry

  for (int i = 0; i < BOARD_TUBES; i++) {
    uint8_t idx = (cfg.anodeOrder[i] < BOARD_TUBES) ? cfg.anodeOrder[i] : i;
    uint8_t pin = ANODE_PINS[idx];
    anodeM0[i] = (pin < 32) ? (1UL << pin) : 0;
    anodeM1[i] = (pin < 32) ? 0 : (1UL << (pin - 32));
    allAnodeM0 |= anodeM0[i]; allAnodeM1 |= anodeM1[i];
  }
  muxHold = false;
}

// ============================================================================
//  Interface
// ============================================================================
void display_init() {
  for (int i = 0; i < 10; i++) { pinMode(CATHODE_PINS[i], OUTPUT); digitalWrite(CATHODE_PINS[i], LOW); }
  for (int i = 0; i < BOARD_TUBES; i++) { pinMode(ANODE_PINS[i], OUTPUT); digitalWrite(ANODE_PINS[i], LOW); }
  pinMode(PIN_BUZZER, OUTPUT); digitalWrite(PIN_BUZZER, LOW);

  for (int i = 0; i < BOARD_TUBES; i++) {
    shOld[i] = shNew[i] = BLANK; shFade[i] = 255; pushTube(i); vOnTicks[i] = 0;
  }

  analogSetAttenuation(ADC_11db);
  buildMasks();
  hvPwmSetup();
  hvPwmWrite(0);
  neonPwmSetup();
  neonPwmWrite(0, 0);
  neonPwmWrite(1, 0);
#if BOARD_HAS_LED_BL
  blPwmSetup();
  blPwmWrite(0);
#endif
  muxTimerSetup();

  xTaskCreatePinnedToCore(hvTask,   "hv",   3072, nullptr, 3, nullptr, 0);
  xTaskCreatePinnedToCore(fadeTask, "fade", 2048, nullptr, 2, nullptr, 1);
}

void display_setDigits(const uint8_t digits[BOARD_TUBES], uint16_t fadeMs) {
  bool changed = false;
  for (int i = 0; i < BOARD_TUBES; i++) {
    if (shNew[i] == digits[i] && shOld[i] == digits[i]) continue;
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
  // Perceptual gamma, then the per-tube trim. The trim matters most on the
  // electroNIX 2, where the small seconds tubes run through 6.2 k emitter
  // resistors against 2 k for the large ones.
  uint16_t g = ((uint16_t)percent * percent) / 100;
  for (int i = 0; i < BOARD_TUBES; i++) {
    uint16_t v = ((uint16_t)ACTIVE_TICKS * g) / 100;
    v = (v * cfg.trim[i]) / 100;
    if (percent > 0 && v == 0) v = 1;
    vOnTicks[i] = (uint8_t)v;
  }
  hvEnable = (percent > 0);

#if BOARD_HAS_LED_BL
  uint8_t lb = (!cfg.ledEn || percent == 0) ? 0 : cfg.ledBr;
  if (cfg.ledNight && percent > 0 && percent <= cfg.nightBr)
    lb = (cfg.nightBr == 0) ? 0 : (lb * cfg.nightBr) / 100;
  blPwmWrite((uint32_t)lb * lb * 255 / 10000);        // gamma on the LEDs too
#endif
}

void display_tick_100ms() {
  lightMv += 0.02f * (readLight() - lightMv);          // tau ~5 s
  // Re-apply the wiring order if the user changed it. Cheap comparison; the
  // masks are only rebuilt when something actually differs.
  static uint8_t lastCath[10], lastAnode[BOARD_TUBES];
  static bool first = true;
  if (first || memcmp(lastCath, cfg.cathOrder, 10) ||
      memcmp(lastAnode, cfg.anodeOrder, BOARD_TUBES)) {
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
    hvEnable = false;
    hvPwmWrite(0);
    neonPwmWrite(0, 0);
    neonPwmWrite(1, 0);
#if BOARD_HAS_LED_BL
    blPwmWrite(0);
#endif
  } else {
    isrCurCath = 255;
  }
}

void display_snapshot(char *out, int n) {
  int m = BOARD_TUBES < n - 1 ? BOARD_TUBES : n - 1;
  for (int i = 0; i < m; i++) out[i] = (shNew[i] <= 9) ? ('0' + shNew[i]) : ' ';
  out[m] = 0;
}

void display_getStatus(DisplayStatus &s) {
  s.hv        = hvVolts;
  s.duty      = hvDutyPct;
  s.hvFault   = hvFault;
  s.hvCuts    = hvCuts;
  s.muxHealth = muxHealth;
  s.muxMin    = muxMin;
  s.colon0    = colon0On;
  s.colon1    = colon1On;
  s.hasLight  = true;
  s.lightMv   = lightMv;
  s.lightPP   = lightPP;
}

#endif // TESTA boards