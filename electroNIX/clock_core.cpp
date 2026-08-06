// ============================================================================
//  clock_core.cpp — everything that isn't board electronics
//
//  Config + NVS, NTP and its fallbacks, brightness policy, cleaning cycles,
//  pin-check modes, night mode, WiFi, OTA, the web server and the diagnostic
//  counters. Talks to the hardware only through display.h.
// ============================================================================
#include "board.h"
#include "display.h"
#include "clock_core.h"
#include "web_ui.h"

#if BOARD == BOARD_NICK2_IN12
  extern void nick2_savePin(const char *kind, uint8_t idx, uint8_t gpio);
#endif

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <esp_mac.h>
#include <ArduinoOTA.h>
#include <Preferences.h>
#include <time.h>
#include <sys/time.h>
#if BOARD_HAS_RTC
  #include <Wire.h>
#endif

#if __has_include(<esp_freertos_hooks.h>)
  #include <esp_freertos_hooks.h>
  #define HAVE_IDLE_HOOK 1
#endif
#if __has_include(<esp_sntp.h>)
  #include <esp_sntp.h>
  #define HAVE_SNTP_CB 1
#endif

#define FW_VERSION "3.0.0"
#define TUBES BOARD_TUBES
static const uint8_t BLANK = 15;

Config cfg;
static Preferences prefs;
WebServer server(80);
static DNSServer dns;

// Forward declarations
static void setupOTA();

// ---- runtime state ---------------------------------------------------------
// SRC_RTC sits between SAVED and BROWSER: more authoritative than a stale
// saved epoch, but the DS3231's absolute accuracy (±2 ppm / ~0.2 s/day)
// isn't externally validated the way NTP or an explicit browser set is.
// core_timeTrusted() treats SRC_RTC and above as trusted, so the
// untrusted-time warning (e.g. the Nick2 bottom dot, amber status colour)
// is suppressed once the DS3231 has given us a time on boot.
enum TimeSrc : uint8_t { SRC_NONE = 0, SRC_SAVED, SRC_RTC, SRC_BROWSER, SRC_NTP };
static volatile TimeSrc timeSrc = SRC_NONE;
static time_t   lastSyncAt = 0;
static bool     timeSynced = false;
static bool     displayOn  = true;
static bool     apMode     = false;
static bool     otaActive  = false;
static uint32_t rebootAt   = 0;
static uint32_t poisonUntil = 0;
#if BOARD_HAS_RTC
static bool rtcAvailable = false;
#endif
// A "try it" or a preview from the web UI can ask for a different length/style
// than what's saved, without touching cfg (and without waiting for a Save).
// 0 / -1 means "not previewing, use the saved value" -- this is also what a
// scheduled/periodic cleaning cycle always sees, since only the explicit
// action handler ever sets these, and they're cleared the moment a cycle ends.
static uint16_t poisonPreviewSec   = 0;
static int8_t   poisonPreviewStyle = -1;
// Per-tube slot-machine spin state (deceleration -- see servicePoison).
static uint8_t  poisonDigit[TUBES];
static uint32_t poisonNextChange[TUBES];
static uint32_t dateUntil   = 0;
static int      lastShownSec = -1;
static int      lastChimeHour = -1;
static uint8_t  effBrightness = 85;
static float    lightPct = 0;
static int8_t   testDigit = -1;
static int8_t   testTube  = -1;
static uint32_t testUntil = 0;

// ---- Boot-phase state machine -----------------------------------------------
// At every boot the captive portal opens for cfg.portalSec seconds before any
// STA connection attempt, so the user can reach 192.168.4.1 regardless of
// whether the saved WiFi network is reachable right now.
enum BootPhase : uint8_t {
  PHASE_PORTAL  = 0,   // AP up, countdown shown on tubes
  PHASE_CONNECT = 1,   // WiFi.begin() running, portal still accessible
  PHASE_IP      = 2,   // STA connected, showing IP octets on tubes
  PHASE_RUN     = 3    // normal clock operation
};
static BootPhase bootPhase    = PHASE_PORTAL;
static uint32_t  phaseUntil   = 0;        // end-of-phase timestamp (millis)
static uint8_t   ipOctet      = 0;        // which IP byte is being shown (0-3)
static uint32_t  ipOctetUntil = 0;        // when to advance to next byte
static uint8_t   ipBytes[4]   = {};       // cached local IP after STA connect
static bool      otaReady     = false;    // true once ArduinoOTA.begin() called

// CPU load counters
static volatile DRAM_ATTR uint32_t idleCnt[2] = {0, 0};
static uint32_t idleMax[2] = {1, 1};
static uint8_t  coreLoad[2] = {0, 0};
#ifdef HAVE_IDLE_HOOK
static bool IRAM_ATTR idleHook0() { idleCnt[0]++; return true; }
static bool IRAM_ATTR idleHook1() { idleCnt[1]++; return true; }
#endif

// Helper function to derive dynamic hostname with MAC suffix when set to default
static String getEffectiveHost() {
  if (cfg.host[0] == '\0' || strcasecmp(cfg.host, "electronix") == 0) {
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char buf[32];
    snprintf(buf, sizeof(buf), "electronix-%02x%02x", mac[4], mac[5]);
    return String(buf);
  }
  return String(cfg.host);
}

// ============================================================================
//  Settings storage — one NVS key per field, so adding a setting in a later
//  firmware version never invalidates the ones already stored.
// ============================================================================
#define CFG_STRINGS(X) \
  X(ssid) X(pass) X(host) X(ntp1) X(ntp2) X(tz)

#define CFG_NUMBERS(X) \
  X(ntpEvery) X(ntpSmooth) X(use24) X(leadZero) X(colon) X(fadeMs) \
  X(brAuto) X(brMan) X(brMin) X(brMax) X(brSpeed) X(lightDark) X(lightBright) \
  X(nightEn) X(colonNightOff) X(nightS) X(nightE) X(nightBr) \
  X(poisonMin) X(poisonSec) X(poisonStyle) \
  X(dateEvery) X(dateFmt) X(dateDur) X(chime) X(btnEn) X(hvSet) \
  X(secEn) X(secMode) X(ledEn) X(ledBr) X(ledNight) \
  X(colonR) X(colonG) X(colonB) X(colonBr) X(colonOuterPct) X(colonAccent) X(colonReversed) \
  X(neon1Fitted) X(accentDim) X(portalSec) X(colonBrNeon) \
  X(fadeCurve) X(fadeCurveFloor)

#define CFG_ARRAYS(X) \
  X(trim) X(cathOrder) X(anodeOrder)

void core_saveConfig() {
  prefs.begin("nixie", false);
#define PUT_S(f) prefs.putString(#f, cfg.f);
#define PUT_N(f) prefs.putULong(#f, (uint32_t)cfg.f);
#define PUT_A(f) prefs.putBytes(#f, cfg.f, sizeof(cfg.f));
  CFG_STRINGS(PUT_S) CFG_NUMBERS(PUT_N) CFG_ARRAYS(PUT_A)
#undef PUT_S
#undef PUT_N
#undef PUT_A
  prefs.putULong("hvTrimx100", (uint32_t)lroundf(cfg.hvTrim * 100.0f));
  prefs.end();
}

static void loadConfig() {
  prefs.begin("nixie", false);
#define GET_S(f) { String v = prefs.getString(#f, cfg.f); strlcpy(cfg.f, v.c_str(), sizeof(cfg.f)); }
#define GET_N(f) cfg.f = (decltype(cfg.f))prefs.getULong(#f, (uint32_t)cfg.f);
#define GET_A(f) if (prefs.getBytesLength(#f) == sizeof(cfg.f)) prefs.getBytes(#f, cfg.f, sizeof(cfg.f));
  CFG_STRINGS(GET_S) CFG_NUMBERS(GET_N) CFG_ARRAYS(GET_A)
#undef GET_S
#undef GET_N
#undef GET_A
  cfg.hvTrim = prefs.getULong("hvTrimx100",
                 (uint32_t)lroundf(cfg.hvTrim * 100.0f)) / 100.0f;
  if (!cfg.dateDur) cfg.dateDur = 4;
  // One-time migration: dateDMY (bool, stored 1=DMY / 0=MDY) → dateFmt
  // (0=DMY, 1=MDY, 2=YMD).  Only runs when the old key exists and the new
  // one has never been written (i.e. the first boot after a firmware upgrade).
  if (!prefs.isKey("dateFmt") && prefs.isKey("dateDMY"))
    cfg.dateFmt = prefs.getULong("dateDMY", 1) ? 0 : 1;
  if (prefs.isKey("cfg")) { prefs.remove("cfg"); prefs.remove("ver"); }   // legacy blob
  prefs.end();
}

// ============================================================================
//  DS3231 real-time clock (compiled in only when BOARD_HAS_RTC is set)
// ============================================================================
#if BOARD_HAS_RTC

// Convert a UTC struct tm to time_t without calling mktime(), which uses the
// system timezone and returns a wrong result if called before configTzTime().
// restoreTime() runs before applyTime(), so mktime() is unsafe there.
static time_t utcToEpoch(const struct tm &t) {
  // Days-into-year offsets for a non-leap year (Jan=0, Feb=31, …)
  static const uint16_t MOFF[] = {0,31,59,90,120,151,181,212,243,273,304,334};
  const int y = t.tm_year + 1900;
  const bool leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
  // Days from the epoch to the start of year y
  int d = (y - 1970) * 365 + (y - 1969) / 4 - (y - 1901) / 100 + (y - 1601) / 400;
  d += MOFF[t.tm_mon];
  if (t.tm_mon > 1 && leap) d++;  // leap-year correction past February
  d += t.tm_mday - 1;
  return (time_t)d * 86400 + t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec;
}

// Read UTC time from the DS3231 seconds register (0x00, seven bytes).
// Returns true when the read succeeded and the date looks sane (≥ 2020).
static bool rtcRead(struct tm &t) {
  Wire.beginTransmission(0x68);
  Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;
  if (Wire.requestFrom((uint8_t)0x68, (uint8_t)7) != 7) return false;
  auto bcd = [](uint8_t b) -> int { return (b >> 4) * 10 + (b & 0x0F); };
  t.tm_sec  = bcd(Wire.read() & 0x7F);
  t.tm_min  = bcd(Wire.read() & 0x7F);
  t.tm_hour = bcd(Wire.read() & 0x3F);   // assumes 24-hour mode (bit 6 = 0)
  Wire.read();                             // day-of-week, unused
  t.tm_mday = bcd(Wire.read() & 0x3F);
  t.tm_mon  = bcd(Wire.read() & 0x1F) - 1;
  t.tm_year = bcd(Wire.read()) + 100;     // DS3231 stores 00–99; tm_year from 1900
  t.tm_isdst = -1;
  return (t.tm_year + 1900) >= 2020;
}

// Write the current UTC system time to the DS3231.
// Called after NTP sync and after a browser time set.
static void rtcWrite() {
  if (!rtcAvailable) return;
  time_t now = time(nullptr);
  struct tm t;
  gmtime_r(&now, &t);                        // UTC struct tm — no timezone involved
  auto bcd = [](int v) -> uint8_t { return (uint8_t)(((v / 10) << 4) | (v % 10)); };
  Wire.beginTransmission(0x68);
  Wire.write(0x00);                          // start at seconds register
  Wire.write(bcd(t.tm_sec));
  Wire.write(bcd(t.tm_min));
  Wire.write(bcd(t.tm_hour));                // 24-hour mode: bit 6 of this byte = 0
  Wire.write(1);                             // day-of-week (1–7, meaning unused here)
  Wire.write(bcd(t.tm_mday));
  Wire.write(bcd(t.tm_mon + 1));
  Wire.write(bcd(t.tm_year % 100));
  Wire.endTransmission();
}

#endif // BOARD_HAS_RTC

// ============================================================================
//  Time
// ============================================================================
RTC_NOINIT_ATTR static uint32_t rtcEpoch;
RTC_NOINIT_ATTR static uint32_t rtcMagic;
RTC_NOINIT_ATTR static uint32_t rtcSkipApFlag; // Key variable: survives ESP.restart()
static const uint32_t RTC_MAGIC = 0x4E495845;   // "NIXE"
static const uint32_t SKIP_AP_MAGIC = 0x534B4950; // "SKIP"

static bool skipApOnReboot = true;

static void setSkipApFlag() {
  rtcSkipApFlag = SKIP_AP_MAGIC;
}

static void clearSkipApFlag() {
  rtcSkipApFlag = 0;
}

static bool checkAndClearSkipApFlag() {
  bool skip = (rtcSkipApFlag == SKIP_AP_MAGIC);
  rtcSkipApFlag = 0; // Reset flag after reading
  return skip;
}

bool core_secondIsEven() { return (time(nullptr) & 1) == 0; }

uint16_t core_msIntoSecond() {
  timeval tv; gettimeofday(&tv, nullptr);
  return (uint16_t)(tv.tv_usec / 1000);
}

bool core_timeTrusted() { return timeSrc >= SRC_RTC; }

bool core_flashWriteSafe() {
  return (effBrightness == 0) || (poisonUntil != 0) || otaActive;
}

static void onNtpSync(struct timeval *) {
  bool first = (timeSrc != SRC_NTP);
  timeSrc = SRC_NTP;
  lastSyncAt = time(nullptr);
#if BOARD_HAS_RTC
  // Re-calibrate the DS3231 on every NTP sync so the battery-backed clock
  // stays accurate even if WiFi is only available intermittently.
  rtcWrite();
#endif
#ifdef HAVE_SNTP_CB
  // Only slew once the clock is already close. Slewing a badly wrong clock
  // (e.g. one restored from a stale saved time) would take hours.
  if (first && cfg.ntpSmooth) sntp_set_sync_mode(SNTP_SYNC_MODE_SMOOTH);
#endif
}

static void applyTime() {
#ifdef HAVE_SNTP_CB
  sntp_set_time_sync_notification_cb(onNtpSync);
  sntp_set_sync_mode(SNTP_SYNC_MODE_IMMED);
#endif
  configTzTime(cfg.tz, cfg.ntp1, cfg.ntp2);
#ifdef HAVE_SNTP_CB
  sntp_set_sync_interval((uint32_t)cfg.ntpEvery * 60000UL);
  sntp_restart();
#endif
}

// A flash write stalls the multiplex ISR for a few milliseconds, so the time
// lives in RTC memory (free, survives resets and OTA) and only reaches flash
// every six hours, deferred until the display won't notice.
static void persistTime(bool force = false) {
  static uint32_t nextWrite = 0, deadline = 0;
  if (!timeSynced) return;
  uint32_t now = millis();
  rtcEpoch = (uint32_t)time(nullptr);
  rtcMagic = RTC_MAGIC;
  if (!force) {
    if (now < nextWrite) return;
    if (!deadline) deadline = now + 600000UL;
    if (!core_flashWriteSafe() && (int32_t)(now - deadline) < 0) return;
  }
  nextWrite = now + 6UL * 3600000UL;
  deadline = 0;
  prefs.begin("nixie", false);
  prefs.putULong("epoch", rtcEpoch);
  prefs.end();
}

static void restoreTime() {
#if BOARD_HAS_RTC
  // DS3231 is battery-backed and far more trustworthy than a saved epoch
  // that may have drifted since the last write.  Try it first.
  if (rtcAvailable) {
    struct tm t;
    if (rtcRead(t)) {
      time_t e = utcToEpoch(t);
      timeval tv = { .tv_sec = e, .tv_usec = 0 };
      settimeofday(&tv, nullptr);
      timeSrc   = SRC_RTC;
      timeSynced = true;
      return;
    }
    // If the read failed, the module may have just been fitted without a cell
    // or with the clock not yet set.  Fall through to the NVS epoch.
  }
#endif
  prefs.begin("nixie", true);
  uint32_t e = prefs.getULong("epoch", 0);
  prefs.end();
  if (rtcMagic == RTC_MAGIC && rtcEpoch > e) e = rtcEpoch;
  if (e < 1700000000UL) return;
  timeval tv = { .tv_sec = (time_t)e, .tv_usec = 0 };
  settimeofday(&tv, nullptr);
  timeSrc = SRC_SAVED;
  timeSynced = true;
}

// ============================================================================
//  Brightness policy
// ============================================================================
static bool inNightWindow(int minutesNow) {
  if (!cfg.nightEn || cfg.nightS == cfg.nightE) return false;
  if (cfg.nightS < cfg.nightE) return minutesNow >= cfg.nightS && minutesNow < cfg.nightE;
  return minutesNow >= cfg.nightS || minutesNow < cfg.nightE;      // wraps midnight
}

static void updateBrightness(const tm &t) {
  uint8_t b;
#if BOARD_HAS_SENSOR
  DisplayStatus ds; display_getStatus(ds);
  float span = (float)cfg.lightDark - (float)cfg.lightBright;
  if (fabsf(span) < 50.0f) span = (span < 0) ? -50.0f : 50.0f;
  float lux = constrain(((float)cfg.lightDark - ds.lightMv) / span, 0.0f, 1.0f);
  lightPct = lux * 100.0f;

  if (cfg.brAuto) {
    // One slider sets both the time constant and the slew limit. Exponential
    // map so the slider feels linear: 0.5 s at 100, ~5 s mid, 30 s at 0.
    static float bSmooth = -1.0f;
    float tau_s   = 0.5f * powf(60.0f, (100 - cfg.brSpeed) / 100.0f);
    float alpha   = 1.0f - expf(-0.1f / tau_s);
    float maxStep = 100.0f * 0.1f / tau_s;
    float bTarget = cfg.brMin + (cfg.brMax - cfg.brMin) * lux;
    if (bSmooth < 0.0f) bSmooth = bTarget;
    float diff = bTarget - bSmooth;
    if (fabsf(diff) > 2.0f) {                       // deadband rejects jitter
      float step = diff * alpha;
      if (step >  maxStep) step =  maxStep;
      if (step < -maxStep) step = -maxStep;
      bSmooth += step;
    }
    b = (uint8_t)lroundf(bSmooth);
  } else b = cfg.brMan;
#else
  b = cfg.brMan;
#endif

  if (inNightWindow(t.tm_hour * 60 + t.tm_min)) b = cfg.nightBr;
  if (!displayOn) b = 0;
  effBrightness = b;
  display_setBrightness(b);
}

// ============================================================================
//  What to show
// ============================================================================
static uint16_t fadeLimit() {
#if BOARD_HAS_SECONDS
  // Seconds change every second, so their fade has to finish inside one.
  if (cfg.secEn && cfg.secMode == 0 && cfg.fadeMs > 700) return 700;
#endif
  return cfg.fadeMs;
}

static void fillTime(const tm &t, uint8_t d[TUBES]) {
  int h = t.tm_hour;
  if (!cfg.use24) { h %= 12; if (h == 0) h = 12; }
  d[0] = h / 10; d[1] = h % 10;
  d[2] = t.tm_min / 10; d[3] = t.tm_min % 10;
#if BOARD_HAS_SECONDS
  bool showSec = cfg.secEn &&
    (cfg.secMode == 0 || (cfg.secMode == 2 && t.tm_sec >= 25 && t.tm_sec < 35));
  d[4] = showSec ? t.tm_sec / 10 : BLANK;
  d[5] = showSec ? t.tm_sec % 10 : BLANK;
#endif
  if (d[0] == 0 && !cfg.leadZero) d[0] = BLANK;
}

static void showDate(const tm &t) {
  int day = t.tm_mday, mon = t.tm_mon + 1;
  uint8_t d[TUBES];
  for (int i = 0; i < TUBES; i++) d[i] = BLANK;
#if BOARD_HAS_SECONDS
  // 6-digit: three 2-digit fields, order chosen by dateFmt.
  int yy = (t.tm_year + 1900) % 100;
  int x, y, z;
  switch (cfg.dateFmt) {
    case 1:  x = mon; y = day; z = yy;  break;   // MM/DD/YY
    case 2:  x = yy;  y = mon; z = day; break;   // YY/MM/DD
    default: x = day; y = mon; z = yy;  break;   // DD/MM/YY
  }
  d[0]=x/10; d[1]=x%10; d[2]=y/10; d[3]=y%10; d[4]=z/10; d[5]=z%10;
#else
  // 4-digit: two 2-digit fields.  dateFmt=2 (YMD) is a 6-digit-only
  // layout; fall back to DD/MM so the tubes always show something sensible.
  int a = (cfg.dateFmt == 1) ? mon : day;
  int b = (cfg.dateFmt == 1) ? day : mon;
  d[0]=a/10; d[1]=a%10; d[2]=b/10; d[3]=b%10;
#endif
  display_setDigits(d, fadeLimit());
}

static uint32_t poisonMs()   { return (uint32_t)(poisonPreviewSec ? poisonPreviewSec : cfg.poisonSec) * 1000UL; }
static uint8_t  poisonStyle(){ return (poisonPreviewStyle >= 0) ? (uint8_t)poisonPreviewStyle : cfg.poisonStyle; }

// Called once, right as a cycle starts (both trigger sites below), so the
// slot machine has a clean starting digit and timing reference per tube
// rather than trying to derive everything from an absolute clock reading.
static void poisonBegin() {
  uint32_t now = millis();
  for (int i = 0; i < TUBES; i++) {
    poisonDigit[i] = (uint8_t)((now / 37 + i * 3) % 10);   // arbitrary, just a varied start
    poisonNextChange[i] = now;
  }
}

static void servicePoison(const tm &t) {
  uint32_t now = millis(), dur = poisonMs();
  uint32_t left = poisonUntil - now;
  uint32_t done = (dur > left) ? (dur - left) : 0;
  uint8_t td[TUBES]; fillTime(t, td);
  uint8_t d[TUBES];

  if (poisonStyle() == 1) {
    // Thorough: every cathode gets an equal share of the run.
    uint32_t step = dur / 10; if (!step) step = 1;
    uint8_t k = (uint8_t)((done / step) % 10);
    for (int i = 0; i < TUBES; i++) d[i] = (uint8_t)((k + i) % 10);
  } else {
    // Slot machine: spin, then settle one tube at a time from the left, each
    // one decelerating into its stop rather than spinning at a constant rate
    // and cutting off. Every tube gets its own stop time (settle, as before)
    // and its own spin window (spinDur); how far into that window it is
    // (frac) sets how long to wait before the next digit change -- close to
    // 0 near the start (close to every 100 ms, as fast as this function is
    // even polled) and growing toward ~500 ms by the time it's about to
    // stop, along a curve (frac^2.0) that spends most of the window still
    // near the fast end, the way a real reel does.
    for (int i = 0; i < TUBES; i++) {
      uint32_t settle  = (dur * (uint32_t)(TUBES - 1 - i)) / (2UL * TUBES);
      uint32_t spinDur = (dur > settle) ? (dur - settle) : 1;
      uint32_t elapsed = (done < spinDur) ? done : spinDur;

      if (left <= settle) {
        d[i] = td[i];                                    // stopped
      } else {
        if (now >= poisonNextChange[i]) {
          float frac = (float)elapsed / (float)spinDur;
          float gapF = 20.0f + 480.0f * (frac * frac);   // 100 ms -> 500 ms
          poisonDigit[i] = (poisonDigit[i] + 1) % 10;
          poisonNextChange[i] = now + (uint32_t)gapF;
        }
        d[i] = poisonDigit[i];
      }
    }
  }
  display_setDigits(d, 0);
}

static void serviceClock() {
  uint32_t now32 = millis();

  // ---- Boot-phase state machine -------------------------------------------
  // Runs until bootPhase reaches PHASE_RUN, then falls through to the normal
  // clock logic below.  All paths inside this block return early.
  if (bootPhase != PHASE_RUN) {
    // During all boot phases (portal countdown, STA connect attempt, IP
    // display) apply cfg.brMan unconditionally.  Calling updateBrightness()
    // here with a zeroed tm — which represents midnight — causes any
    // night-mode window that wraps past midnight to trigger, silently
    // dimming the display to cfg.nightBr.  The light sensor is also not a
    // useful input this early: it hasn't settled, and the user chose manual
    // brightness for a reason.  Full brightness policy (night mode, auto
    // sensor, smooth ramping) resumes the moment bootPhase reaches PHASE_RUN.
    display_setBrightness(cfg.brMan);
    effBrightness = cfg.brMan;

    // -- PHASE_PORTAL: countdown visible on tubes, portal accessible --------
    if (bootPhase == PHASE_PORTAL) {
      int32_t left = (int32_t)(phaseUntil - now32);
      if (left > 0) {
        uint8_t secs = (uint8_t)min((uint32_t)left / 1000UL, (uint32_t)99);
        static uint8_t lastPortalSec = 255;
        if (secs != lastPortalSec) {
          lastPortalSec = secs;
          uint8_t d[TUBES];
          for (int i = 0; i < TUBES; i++) d[i] = BLANK;
          d[TUBES - 1] = secs % 10;
          if (secs >= 10) d[TUBES - 2] = secs / 10;
          display_setDigits(d, 0);
        }
        display_setColon(COLON_BLINK);
        return;
      }
      // Window elapsed — start STA attempt if we have credentials and no client
      // is currently connected to our AP hotspot.  A connected client means the
      // user deliberately entered the configuration portal via the hotspot; in
      // that case we stay in AP mode (apMode remains true, PHASE_RUN) so they
      // can finish configuring without the STA connection racing them.
      // The core_loop() reconnect guard (!apMode && ...) ensures no silent
      // reconnect attempt is made while a portal session is in progress.
      if (cfg.ssid[0] && WiFi.softAPgetStationNum() == 0) {
        WiFi.setSleep(false);
        WiFi.config(INADDR_NONE, INADDR_NONE, INADDR_NONE, INADDR_NONE);
        WiFi.setHostname(getEffectiveHost().c_str());
        WiFi.begin(cfg.ssid, cfg.pass);       // AP stays up (WIFI_AP_STA)
        phaseUntil = now32 + 20000UL;         // 20 s STA timeout
        bootPhase  = PHASE_CONNECT;
      } else {
        // No SSID saved, or a client is actively using the hotspot portal —
        // skip the STA connection attempt entirely.
        bootPhase  = PHASE_RUN;
        lastShownSec = -1;
        return;
      }
    }

    // -- PHASE_CONNECT: non-blocking STA connection, portal still up --------
    if (bootPhase == PHASE_CONNECT) {
      if (WiFi.status() == WL_CONNECTED) {
        // Success — drop the AP and set up mDNS + OTA
        apMode = false;
        dns.stop();
        WiFi.mode(WIFI_STA);
        WiFi.setAutoReconnect(true);
        setupOTA();
        // Cache the four IP bytes for tube display
        IPAddress ip = WiFi.localIP();
        for (int i = 0; i < 4; i++) ipBytes[i] = ip[i];
        ipOctet = 0;
        // Push first octet immediately
        { uint8_t d[TUBES]; for (int i=0;i<TUBES;i++) d[i]=BLANK;
          d[TUBES-1] = ipBytes[0] % 10;
          if (ipBytes[0] >=  10) d[TUBES-2] = (ipBytes[0] / 10) % 10;
          if (ipBytes[0] >= 100) d[TUBES-3] =  ipBytes[0] / 100;
          display_setDigits(d, 80); }
        ipOctetUntil = now32 + 1000UL;
        bootPhase = PHASE_IP;
        display_setColon(COLON_OFF);
#if BOARD_USE_SERIAL
        Serial.printf("Connected: %s  http://%s.local\n",
          WiFi.localIP().toString().c_str(), getEffectiveHost().c_str());
#endif
        return;
      }
      if ((int32_t)(now32 - phaseUntil) >= 0) {
        // Timed out — stay in AP mode, show the clock as-is
        WiFi.disconnect(false);      // stop STA attempt; AP stays
        bootPhase  = PHASE_RUN;
        lastShownSec = -1;
#if BOARD_USE_SERIAL
        Serial.println("WiFi: connect timed out, staying in AP mode.");
#endif
        return;
      }
      // Still connecting — rolling animation to show activity
      { uint8_t d[TUBES];
        for (int i=0;i<TUBES;i++) d[i]=(uint8_t)((now32/180+i)%10);
        display_setDigits(d, 0); }
      display_setColon(COLON_BLINK);
      return;
    }

    // -- PHASE_IP: show each octet for 1 s then enter normal operation ------
    if (bootPhase == PHASE_IP) {
      if ((int32_t)(now32 - ipOctetUntil) >= 0) {
        ipOctet++;
        if (ipOctet >= 4) {
          bootPhase = PHASE_RUN;
          lastShownSec = -1;
          return;
        }
        uint8_t d[TUBES]; for (int i=0;i<TUBES;i++) d[i]=BLANK;
        d[TUBES-1] = ipBytes[ipOctet] % 10;
        if (ipBytes[ipOctet] >=  10) d[TUBES-2] = (ipBytes[ipOctet] / 10) % 10;
        if (ipBytes[ipOctet] >= 100) d[TUBES-3] =  ipBytes[ipOctet] / 100;
        display_setDigits(d, 80);
        ipOctetUntil = now32 + 1000UL;
      }
      display_setColon(COLON_OFF);
      return;
    }

    return;  // safety — no unhandled phase should reach here
  }

  // ---- Normal clock operation (PHASE_RUN) ---------------------------------
  tm t;
  bool ok = getLocalTime(&t, 5);
  if (ok && (t.tm_year + 1900) >= 2020) {
    timeSynced = true;
    if (timeSrc == SRC_NONE) timeSrc = SRC_SAVED;
  }

  if (!timeSynced) {                                 // nothing to show yet
    uint8_t d[TUBES];
    for (int i = 0; i < TUBES; i++) d[i] = (uint8_t)((millis() / 180 + i) % 10);
    display_setDigits(d, 0);
    tm z = {}; updateBrightness(z);
    display_setColon(COLON_BLINK);
    return;
  }

  updateBrightness(t);
  display_setColon((inNightWindow(t.tm_hour * 60 + t.tm_min) && cfg.colonNightOff) ? COLON_OFF : (ColonMode)cfg.colon);

  // Pin-check modes hold a fixed pattern
  if (testDigit >= 0 || testTube >= 0) {
    if ((int32_t)(millis() - testUntil) < 0) {
      uint8_t d[TUBES];
      for (int i = 0; i < TUBES; i++) {
        if (testTube >= 0) d[i] = (i == testTube) ? (uint8_t)((testTube + 1) % 10) : BLANK;
        else               d[i] = (uint8_t)testDigit;
      }
      display_setDigits(d, 0);
      return;
    }
    testDigit = testTube = -1;
  }

  if (poisonUntil && (int32_t)(millis() - poisonUntil) < 0) { servicePoison(t); return; }
  poisonUntil = 0;
  // Whatever a "try it" preview asked for, it only applies to that one run --
  // clear it the moment nothing is running, so a scheduled cycle later never
  // inherits settings that were only ever meant to be tried once.
  poisonPreviewSec = 0;
  poisonPreviewStyle = -1;

  if (t.tm_sec == lastShownSec) return;              // once per second below
  lastShownSec = t.tm_sec;

#if BOARD_HAS_BUZZER
  if (cfg.chime && t.tm_min == 0 && t.tm_sec == 0 && t.tm_hour != lastChimeHour
      && !inNightWindow(t.tm_hour * 60) && effBrightness > 0) {
    lastChimeHour = t.tm_hour;
    display_beep(2, 70, 130);
  }
#endif

  if (cfg.poisonMin > 0 && effBrightness > 0 && t.tm_sec == 45
      && (t.tm_min % cfg.poisonMin) == 0) {
    poisonUntil = millis() + poisonMs();
    poisonBegin();
    return;
  }

  if (cfg.dateEvery > 0 && t.tm_sec == 30 && (t.tm_min % cfg.dateEvery) == 0) {
    dateUntil = millis() + (uint32_t)(cfg.dateDur ? cfg.dateDur : 4) * 1000UL;
    showDate(t);
    return;
  }
  if (dateUntil) {
    if ((int32_t)(millis() - dateUntil) < 0) return;
    dateUntil = 0;
  }

  uint8_t d[TUBES]; fillTime(t, d);
  display_setDigits(d, fadeLimit());
}

// ============================================================================
//  Web server
// ============================================================================
static String jsonEscape(const char *s) {
  String o; for (const char *p = s; *p; p++) { if (*p == '"' || *p == '\\') o += '\\'; o += *p; }
  return o;
}

static void handleStatus() {
  DisplayStatus ds; display_getStatus(ds);
  char dig[TUBES + 1]; display_snapshot(dig, sizeof(dig));
  tm t; char db[20] = "-";
  if (getLocalTime(&t, 5)) strftime(db, sizeof(db), "%a %Y-%m-%d", &t);

  String j = "{";
  j += "\"digits\":\"" + String(dig) + "\",";
  j += "\"date\":\"" + String(db) + "\",";
  j += "\"synced\":" + String(timeSynced ? "true" : "false") + ",";
  j += "\"on\":" + String(displayOn ? "true" : "false") + ",";
  j += "\"bright\":" + String(effBrightness) + ",";
  j += "\"colon0\":" + String(ds.colon0 ? "true" : "false") + ",";
  j += "\"colon1\":" + String(ds.colon1 ? "true" : "false") + ",";
#if BOARD_HAS_HV
  j += "\"hv\":" + String(ds.hv, 1) + ",";
  j += "\"duty\":" + String(ds.duty, 1) + ",";
  j += "\"hvFault\":" + String(ds.hvFault ? "true" : "false") + ",";
  j += "\"hvcuts\":" + String(ds.hvCuts) + ",";
#endif
#if BOARD_HAS_SENSOR
  j += "\"lightmv\":" + String(ds.lightMv, 0) + ",";
  j += "\"lightpct\":" + String(lightPct, 0) + ",";
  j += "\"lightpp\":" + String(ds.lightPP) + ",";
#endif
  j += "\"mode\":\"" + String(apMode ? "ap" : "sta") + "\",";
  j += "\"rssi\":" + String(apMode ? 0 : WiFi.RSSI()) + ",";
  j += "\"src\":" + String((unsigned)timeSrc) + ",";
  j += "\"age\":" + String((long)(lastSyncAt ? (time(nullptr) - lastSyncAt) : -1)) + ",";
#if BOARD_HAS_RTC
  j += "\"rtcOk\":" + String(rtcAvailable ? "true" : "false") + ",";
#endif
  j += "\"cpu0\":" + String(coreLoad[0]) + ",";
  j += "\"cpu1\":" + String(coreLoad[1]) + ",";
  j += "\"mux\":" + String(ds.muxHealth) + ",";
  j += "\"muxmin\":" + String(ds.muxMin) + ",";
  j += "\"heap\":" + String((unsigned)ESP.getFreeHeap()) + ",";
  j += "\"ver\":\"" FW_VERSION "\"}";
  server.send(200, "application/json", j);
}

static void handleConfigGet() {
  String caps = "[";
#if BOARD_HAS_HV
  caps += "\"hv\",";
#endif
#if BOARD_HAS_SENSOR
  caps += "\"sensor\",";
#endif
#if BOARD_HAS_BUZZER
  caps += "\"buzzer\",";
#endif
#if BOARD_HAS_LED_BL
  caps += "\"led\",";
#endif
#if BOARD_HAS_WS2812
  caps += "\"ws2812\",";
#endif
#if BOARD_HAS_SECONDS
  caps += "\"sec\",";
#endif
#if BOARD_NEON1_OPTIONAL
  caps += "\"neon1opt\",";
#endif
#if BOARD_DUP_COLON
  // Both colon gap positions are wired in parallel; the web preview mirrors
  // the HH:MM dot states onto MM:SS rather than tracking them independently.
  caps += "\"dupcolon\",";
#endif
#if BOARD_HAS_RTC
  caps += "\"rtc\",";
#endif
  if (caps.endsWith(",")) caps.remove(caps.length() - 1);
  caps += "]";

  String j = "{";
  j += "\"board\":\"" BOARD_NAME "\",";
  j += "\"tubes\":" + String(TUBES) + ",";
  j += "\"caps\":" + caps + ",";
  j += "\"hasWs2812\":" + String(BOARD_HAS_WS2812) + ",";
#if BOARD_HAS_WS2812
  #ifdef BOARD_WS_PER_COL
    j += "\"wsPerCol\":" + String(BOARD_WS_PER_COL) + ",";
    j += "\"wsCols\":" + String(BOARD_WS_COLS) + ",";
    j += "\"wsHiIdx\":" + String(BOARD_WS_HI_IDX) + ",";
    j += "\"wsLoIdx\":" + String(BOARD_WS_LO_IDX) + ",";
  #endif
#endif

  j += "\"ssid\":\"" + jsonEscape(cfg.ssid) + "\",";
  j += "\"host\":\"" + jsonEscape(cfg.host) + "\",";
  j += "\"effHost\":\"" + jsonEscape(getEffectiveHost().c_str()) + "\",";
  j += "\"ntp1\":\"" + jsonEscape(cfg.ntp1) + "\",";
  j += "\"ntp2\":\"" + jsonEscape(cfg.ntp2) + "\",";
  j += "\"tz\":\"" + jsonEscape(cfg.tz) + "\",";
#define J_N(f) j += "\"" #f "\":" + String(cfg.f) + ",";
  CFG_NUMBERS(J_N)
#undef J_N
  j += "\"hvTrim\":" + String(cfg.hvTrim, 2) + ",";
  j += "\"trim\":[";
  for (int i = 0; i < TUBES; i++) { j += String(cfg.trim[i]); if (i < TUBES - 1) j += ","; }
  j += "],\"cathOrder\":\"";
  for (int i = 0; i < 10; i++) { j += String(cfg.cathOrder[i]); if (i < 9) j += ","; }
  j += "\",\"anodeOrder\":\"";
  for (int i = 0; i < TUBES; i++) { j += String(cfg.anodeOrder[i]); if (i < TUBES - 1) j += ","; }
  j += "\"}";
  server.send(200, "application/json", j);
}

static void handleConfigPost() {
  auto S  = [&](const char *k, char *dst, size_t n) {
    if (server.hasArg(k)) strlcpy(dst, server.arg(k).c_str(), n); };
  auto B  = [&](const char *k, bool &v) { if (server.hasArg(k)) v = server.arg(k).toInt() != 0; };
  auto U8 = [&](const char *k, uint8_t &v, int lo, int hi) {
    if (server.hasArg(k)) v = constrain(server.arg(k).toInt(), lo, hi); };
  auto U16 = [&](const char *k, uint16_t &v, int lo, int hi) {
    if (server.hasArg(k)) v = constrain(server.arg(k).toInt(), lo, hi); };

  char oldSsid[33], oldPass[65], oldHost[24];
  strlcpy(oldSsid, cfg.ssid, 33); strlcpy(oldPass, cfg.pass, 65); strlcpy(oldHost, cfg.host, 24);

  S("ssid", cfg.ssid, 33); S("pass", cfg.pass, 65); S("host", cfg.host, 24);
  S("ntp1", cfg.ntp1, 48); S("ntp2", cfg.ntp2, 48); S("tz", cfg.tz, 48);
  B("use24", cfg.use24); B("leadZero", cfg.leadZero); B("brAuto", cfg.brAuto);
  B("nightEn", cfg.nightEn); B("colonNightOff", cfg.colonNightOff); B("chime", cfg.chime);
  B("secEn", cfg.secEn); B("ledEn", cfg.ledEn); B("ledNight", cfg.ledNight);
  B("ntpSmooth", cfg.ntpSmooth);
  B("colonReversed", cfg.colonReversed);
  U8("colon", cfg.colon, 0, 5);
  U8("secMode", cfg.secMode, 0, 2);
  U8("ledBr", cfg.ledBr, 0, 100);
  U8("brSpeed", cfg.brSpeed, 0, 100);
  U8("brMan", cfg.brMan, 5, 100);
  U8("brMin", cfg.brMin, 5, 100); U8("brMax", cfg.brMax, 5, 100);
  if (cfg.brMin > cfg.brMax) { uint8_t x = cfg.brMin; cfg.brMin = cfg.brMax; cfg.brMax = x; }
  U8("nightBr", cfg.nightBr, 0, 100);
  U8("poisonSec", cfg.poisonSec, 1, 60);
  U8("poisonStyle", cfg.poisonStyle, 0, 1);
  U8("colonR", cfg.colonR, 0, 255); U8("colonG", cfg.colonG, 0, 255);
  U8("colonB", cfg.colonB, 0, 255); U8("colonBr", cfg.colonBr, 0, 100);
  U8("colonOuterPct", cfg.colonOuterPct, 0, 100);
  U8("colonAccent", cfg.colonAccent, 0, 2);
  U8("accentDim", cfg.accentDim, 0, 50);
  U8("colonBrNeon", cfg.colonBrNeon, 0, 100);
  U8("fadeCurve", cfg.fadeCurve, 0, 2);
  U8("fadeCurveFloor", cfg.fadeCurveFloor, 0, 100);
  B("neon1Fitted", cfg.neon1Fitted);
  U16("fadeMs", cfg.fadeMs, 0, 2000);
  U16("lightDark", cfg.lightDark, 0, 3300);
  U16("lightBright", cfg.lightBright, 0, 3300);
  U16("nightS", cfg.nightS, 0, 1439); U16("nightE", cfg.nightE, 0, 1439);
  U16("poisonMin", cfg.poisonMin, 0, 120);
  U16("dateEvery", cfg.dateEvery, 0, 60);
  U8("dateDur", cfg.dateDur, 1, 30);
  U8("dateFmt", cfg.dateFmt, 0, 2);
  U16("hvSet", cfg.hvSet, 150, 180);
  U16("ntpEvery", cfg.ntpEvery, 5, 1440);
  U16("portalSec", cfg.portalSec, 0, 300);
  if (server.hasArg("hvTrim"))
    cfg.hvTrim = constrain(server.arg("hvTrim").toFloat(), 0.8f, 1.2f);
  for (int i = 0; i < TUBES; i++) {
    char key[8]; snprintf(key, sizeof(key), "trim%d", i);
    U8(key, cfg.trim[i], 20, 100);
  }

  // Wiring order. The UI sends what the tubes ACTUALLY SHOW, observed through
  // whatever mapping is already in force, so the correction is
  //     new[d] = current[ seen^-1[d] ]
  // which is self-correcting and idempotent.
  bool orderBad = false;
  auto parsePerm = [&](const char *k, uint8_t *out, uint8_t n) -> bool {
    if (!server.hasArg(k)) return false;
    String v = server.arg(k);
    uint16_t got = 0; uint8_t c = 0; int start = 0;
    while (c < n && start <= (int)v.length()) {
      int comma = v.indexOf(',', start);
      String tok = (comma < 0) ? v.substring(start) : v.substring(start, comma);
      tok.trim();
      if (!tok.length()) break;
      int x = tok.toInt();
      if (x < 0 || x >= n || (got & (1 << x))) { orderBad = true; return false; }
      got |= (1 << x); out[c++] = (uint8_t)x;
      if (comma < 0) break;
      start = comma + 1;
    }
    if (c != n) { orderBad = true; return false; }
    return true;
  };
  auto applySeen = [&](const char *k, uint8_t *cur, uint8_t n) {
    uint8_t seen[10];
    if (!parsePerm(k, seen, n)) return;
    uint8_t inv[10], out[10];
    for (uint8_t j = 0; j < n; j++) inv[seen[j]] = j;
    for (uint8_t d = 0; d < n; d++) out[d] = cur[inv[d]];
    memcpy(cur, out, n);
  };
  applySeen("seenDigits", cfg.cathOrder, 10);
  applySeen("seenTubes",  cfg.anodeOrder, TUBES);

  // Direct setters, used when restoring a backup rather than correcting by eye
  uint8_t raw[10];
  if (parsePerm("cathOrderRaw", raw, 10))     memcpy(cfg.cathOrder, raw, 10);
  if (parsePerm("anodeOrderRaw", raw, TUBES)) memcpy(cfg.anodeOrder, raw, TUBES);

  core_saveConfig();
  applyTime();

  if (orderBad) {
    server.send(200, "text/plain",
      "Saved, but the wiring order was ignored: each digit (or tube) must appear exactly once.");
    return;
  }
  bool wifiChanged = strcmp(oldSsid, cfg.ssid) || strcmp(oldPass, cfg.pass)
                     || strcmp(oldHost, cfg.host);
  if (wifiChanged && strlen(cfg.ssid)) {
    server.send(200, "text/plain", "Saved. Restarting to join \"" + String(cfg.ssid) + "\"...");
    rebootAt = millis() + 900;
  } else {
    server.send(200, "text/plain", "Saved.");
  }
}

static void handleAction() {
  String d = server.arg("do");
  if (d == "poison") {
    // Optional one-off preview: try a length/style that hasn't been saved
    // yet. Absent or out-of-range falls back to whatever's actually saved,
    // same as before this existed.
    int s = server.hasArg("sec") ? server.arg("sec").toInt() : 0;
    poisonPreviewSec = (s >= 1 && s <= 60) ? (uint16_t)s : 0;
    int st = server.hasArg("style") ? server.arg("style").toInt() : -1;
    poisonPreviewStyle = (st == 0 || st == 1) ? (int8_t)st : -1;

    poisonUntil = millis() + poisonMs();
    poisonBegin();
    server.send(200, "text/plain", "Cleaning cycle running for " + String(poisonMs() / 1000) + " s.");
  } else if (d == "toggle") {
    displayOn = !displayOn;
    server.send(200, "text/plain", displayOn ? "Tubes on." : "Tubes off.");
  } else if (d == "clearwifi") {
    cfg.ssid[0] = '\0';
    cfg.pass[0] = '\0';
    core_saveConfig();
    skipApOnReboot = false;
    clearSkipApFlag();
    server.send(200, "text/plain",
      "WiFi credentials cleared. Restarting — clock will stay offline.\n"
      "Connect to the setup AP and open 192.168.4.1 to reconfigure.");
    rebootAt = millis() + 900;
  } else if (d == "restart") {
    server.send(200, "text/plain", "Restarting..."); rebootAt = millis() + 500;
  } else if (d == "resync") {
    applyTime(); server.send(200, "text/plain", "Asking the NTP servers now.");
  } else if (d == "test") {
    int n = server.arg("d").toInt();
    if (n < 0 || n > 9) { server.send(400, "text/plain", "Digit must be 0-9."); return; }
    testDigit = n; testTube = -1; testUntil = millis() + 15000; lastShownSec = -1;
    server.send(200, "text/plain", "Showing digit " + String(n) + " on all tubes for 15 s.");
  } else if (d == "tube") {
    int n = server.arg("d").toInt();
    if (n < 1 || n > TUBES) { server.send(400, "text/plain", "Tube must be 1-" + String(TUBES) + "."); return; }
    testTube = n - 1; testDigit = -1; testUntil = millis() + 15000; lastShownSec = -1;
    server.send(200, "text/plain", "Lighting position " + String(n) + " for 15 s.");
  } else if (d == "testoff") {
    testDigit = testTube = -1; lastShownSec = -1;
    server.send(200, "text/plain", "Back to the time.");
  }
#if BOARD == BOARD_NICK2_IN12
  // Change one of the Nick2 pin assignments at runtime, without a rebuild.
  //   POST /api/action?do=setpin&kind=an&idx=0&gpio=27
  // kind: "an" for anode 0..3, "bcd" for 74141 input 0..3.
  else if (d == "setpin") {
    if (!server.hasArg("kind") || !server.hasArg("idx") || !server.hasArg("gpio")) {
      server.send(400, "text/plain", "setpin needs kind, idx and gpio."); return;
    }
    String kind = server.arg("kind");
    int idx = server.arg("idx").toInt();
    int gpio = server.arg("gpio").toInt();
    if (gpio < 0 || gpio > 33) { server.send(400, "text/plain", "gpio 0..33 please."); return; }
    nick2_savePin(kind.c_str(), (uint8_t)idx, (uint8_t)gpio);
    rebootAt = millis() + 400;
    server.send(200, "text/plain", "Saved " + kind + "[" + String(idx) + "] = GPIO" +
                String(gpio) + ". Restarting...");
  }
#endif
#if BOARD_HAS_SENSOR
  else if (d == "calbdark") {
    DisplayStatus ds; display_getStatus(ds);
    cfg.lightDark = (uint16_t)ds.lightMv; core_saveConfig();
    server.send(200, "text/plain", "Dark point set to " + String((int)ds.lightMv) + " mV.");
  } else if (d == "calbright") {
    DisplayStatus ds; display_getStatus(ds);
    cfg.lightBright = (uint16_t)ds.lightMv; core_saveConfig();
    server.send(200, "text/plain", "Bright point set to " + String((int)ds.lightMv) + " mV.");
  }
#endif
#if BOARD_HAS_BUZZER
  else if (d == "beep") { display_beep(3, 60, 100); server.send(200, "text/plain", "Beep."); }
#endif
  else server.send(400, "text/plain", "Unknown action.");
}

static void startWebServer() {
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html", WEB_UI_HTML); });
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/config", HTTP_GET, handleConfigGet);
  server.on("/api/config", HTTP_POST, handleConfigPost);
  server.on("/api/action", HTTP_POST, handleAction);
  server.on("/api/wifi", HTTP_GET, []() {
    int n = WiFi.scanComplete();
    if (n == -2) {
      // Start an asynchronous background scan (async = true, show_hidden = true)
      WiFi.scanNetworks(true, true); 
      server.send(202, "text/plain", "Scanning...");
    } else if (n == -1) {
      // Scan is still running in the background
      server.send(202, "text/plain", "Scanning...");
    } else {
      // Scan finished! Serve the results.
      String j = "[";
      for (int i = 0; i < n; ++i) {
        if (i > 0) j += ",";
        j += "\"" + jsonEscape(WiFi.SSID(i).c_str()) + "\"";
      }
      j += "]";
      WiFi.scanDelete(); // Free RAM for subsequent scans
      server.send(200, "application/json", j);
    }
  });
  server.on("/api/time", HTTP_POST, []() {
    if (!server.hasArg("epoch")) { server.send(400, "text/plain", "No epoch."); return; }
    double e = server.arg("epoch").toDouble();
    if (e < 1700000000.0) { server.send(400, "text/plain", "Implausible time."); return; }
    timeval tv;
    tv.tv_sec  = (time_t)e;
    tv.tv_usec = (suseconds_t)((e - (double)tv.tv_sec) * 1000000.0);
    settimeofday(&tv, nullptr);
    timeSynced = true;
    if (timeSrc != SRC_NTP) timeSrc = SRC_BROWSER;
    lastSyncAt = time(nullptr);
    lastShownSec = -1;
#if BOARD_HAS_RTC
    // Write the browser-supplied time to the DS3231 so it persists across
    // power cuts even if NTP is never available (e.g. office network blocks
    // NTP, or the user is running offline).
    rtcWrite();
#endif
    persistTime(true);
    server.send(200, "text/plain", "Clock set from your device.");
  });
  server.onNotFound([]() {
    if (apMode) { server.sendHeader("Location", "http://192.168.4.1/", true);
                  server.send(302, "text/plain", ""); }
    else server.send(404, "text/plain", "Not found");
  });
  server.begin();
}

// ============================================================================
//  WiFi + OTA
// ============================================================================
// Extract OTA + mDNS setup so it can be called after a successful STA
// connection rather than at startup, regardless of board type.
static void setupOTA() {
  String effHost = getEffectiveHost();
  if (MDNS.begin(effHost.c_str())) MDNS.addService("http", "tcp", 80);
  ArduinoOTA.onStart([]() {
    otaActive = true;
    display_park(true);
#if BOARD_HAS_BUZZER
    display_beep(1, 60, 60);
#endif
  });
  ArduinoOTA.onEnd([]() {
#if BOARD_HAS_BUZZER
    display_beep(2, 60, 80);
#endif
  });
  ArduinoOTA.onError([](ota_error_t) {
    otaActive = false;
    display_park(false);
    lastShownSec = -1;
#if BOARD_HAS_BUZZER
    display_beep(3, 200, 150);
#endif
  });
  ArduinoOTA.setHostname(effHost.c_str());
  ArduinoOTA.begin();
  otaReady = true;
}

static void startAP() {
  apMode = true;
  WiFi.mode(WIFI_AP_STA);
  WiFi.disconnect(); // Free the STA interface so the radio can execute scans
  
  String apSSID = getEffectiveHost() + "-Setup";
  
  WiFi.softAP(apSSID.c_str(), "nixie1234");
  dns.start(53, "*", WiFi.softAPIP());
}

// connectWiFi() has been replaced by the boot-phase state machine
// in serviceClock(). STA connection is initiated non-blockingly after
// cfg.portalSec seconds; setupOTA() is called on success.

// Networking lives on core 0 next to the WiFi stack, leaving core 1 to feed
// the display. This is the single biggest thing keeping the tubes steady.
static void netTask(void *) {
  for (;;) {
    server.handleClient();
    if (apMode)   dns.processNextRequest();
    if (otaReady) ArduinoOTA.handle();   // set after successful STA connect
    vTaskDelay(1);
  }
}

// ============================================================================
//  Entry points
// ============================================================================
void core_setup() {
#if BOARD_USE_SERIAL
  Serial.begin(115200);
#endif
  loadConfig();
#if BOARD_HAS_RTC
  // Probe the DS3231 before restoreTime() so rtcAvailable is set when
  // restoreTime() runs. Wire.begin() here also claims SDA/SCL before
  // display_init() has a chance to touch any GPIO.
  Wire.begin(BOARD_RTC_SDA, BOARD_RTC_SCL);
  Wire.setClock(100000);   // 100 kHz standard mode; DS3231 is happy up to 400 kHz
  Wire.beginTransmission(0x68);
  rtcAvailable = (Wire.endTransmission() == 0);
#endif
  restoreTime();                   // show something immediately, network or not
  display_init();
  // Apply manual brightness for the brief gap between display_init() and the
  // first serviceClock() call. serviceClock() then holds cfg.brMan for the
  // entire boot phase (portal, connect, IP display) — see the comment there.
  display_setBrightness(cfg.brMan);

#ifdef HAVE_IDLE_HOOK
  esp_register_freertos_idle_hook_for_cpu(idleHook0, 0);
  esp_register_freertos_idle_hook_for_cpu(idleHook1, 1);
#endif

  // Always open the captive portal first so the user can reach 192.168.4.1
  // to configure WiFi regardless of what the saved network is doing.

  bool skipAP = checkAndClearSkipApFlag();

  if (!skipAP) {
    startAP();
  } else {
    WiFi.mode(WIFI_STA); // Set directly to STA mode if skipping AP
  }

  startWebServer();
  applyTime();                     // configure SNTP/TZ now; it syncs once STA connects

  // If portalSec == 0 skip straight to the STA attempt (or PHASE_RUN if no
  // credentials); otherwise serviceClock() drives the countdown and transition.
  if (skipAP || cfg.portalSec == 0) {
    if (cfg.ssid[0]) {
      WiFi.setSleep(false);
      WiFi.config(INADDR_NONE, INADDR_NONE, INADDR_NONE, INADDR_NONE);
      WiFi.setHostname(getEffectiveHost().c_str());
      WiFi.begin(cfg.ssid, cfg.pass);
      phaseUntil = millis() + 20000UL;
      bootPhase  = PHASE_CONNECT;
    } else {
      bootPhase  = PHASE_RUN;
    }
  } else {
    phaseUntil = millis() + (uint32_t)cfg.portalSec * 1000UL;
    // bootPhase stays PHASE_PORTAL; serviceClock() will drive it
  }

  xTaskCreatePinnedToCore(netTask, "net", 12288, nullptr, 1, nullptr, 0);

#if BOARD_USE_SERIAL
  Serial.printf("%s  v%s  portal 192.168.4.1  (%u s window)\n",
    BOARD_NAME, FW_VERSION, (unsigned)cfg.portalSec);
#endif
}

void core_loop() {
  static uint32_t next100 = 0, nextSec = 0;
  uint32_t now = millis();

  if (now >= next100) {
    next100 = now + 100;
    display_tick_100ms();
    serviceClock();
    persistTime();
  }

  if (now >= nextSec) {
    nextSec = now + 1000;
    display_tick_1s();
    for (int c = 0; c < 2; c++) {
      uint32_t n = idleCnt[c]; idleCnt[c] = 0;
      if (n > idleMax[c]) idleMax[c] = n;
      idleMax[c] -= idleMax[c] >> 10;             // bleed off so it can relearn
      coreLoad[c] = (idleMax[c] && n < idleMax[c])
                    ? (uint8_t)(100 - (100 * n) / idleMax[c]) : 0;
    }
  }

  if (rebootAt && (int32_t)(now - rebootAt) >= 0) {
    if (skipApOnReboot) {
      setSkipApFlag();             // Flag RTC memory to skip AP on normal reboots
    } else {
      clearSkipApFlag();           // Ensure AP is NOT skipped on next boot
    }  
    dns.stop();                  // Stop DNS server
    WiFi.softAPdisconnect(true); // Close SoftAP and turn off AP radio
    WiFi.mode(WIFI_OFF);         // Shut down WiFi stack completely
    delay(1000);                 // Wait 1 second so clients register the AP shutdown
    ESP.restart();
  }

  if (!apMode && bootPhase == PHASE_RUN && WiFi.status() != WL_CONNECTED) {
    static uint32_t lastTry = 0;
    if (now - lastTry > 30000) { lastTry = now; WiFi.reconnect(); }
  }
  delay(1);
}