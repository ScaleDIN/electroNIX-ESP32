// ============================================================================
//  electroNIX / Nick2 nixie clock firmware  ·  v3.0.0
//
//  One sketch, several boards. Pick yours in board.h — that is the only file
//  you should need to edit.
//
//  Structure
//  ---------
//    board.h            board selection and capability flags
//    clock_core.h/.cpp  config, NVS, NTP, brightness policy, cleaning cycles,
//                       WiFi, OTA, web server, diagnostics
//    display.h          the interface every board back-end implements
//    display_testa.cpp  TESTA-QUADRA boards (electroNIX 4+S / 4 / 3 / 2 / fourTINY)
//    display_nick2.cpp  NickTwo IN-12 (74141 + NCH8200HV + WS2812 colon)
//    web_ui.h           the served web page, HTML/CSS/JS in one string
//
//  Adding a board: add a constant and a profile block to board.h, then write
//  a display_<name>.cpp implementing display.h. Nothing in clock_core needs
//  to change.
//
//  First boot: the clock starts an access point "ElectroNIX-Setup"
//  (password nixie1234). Connect and browse to http://192.168.4.1 to set
//  WiFi and timezone. Afterwards it's at http://<hostname>.local.
//
//  Build: board "ESP32 Dev Module", CPU 240 MHz, Core Debug Level None,
//  Erase All Flash disabled. Works on arduino-esp32 2.x and 3.x.
// ============================================================================
#include "board.h"
#include "clock_core.h"

void setup() { core_setup(); }
void loop()  { core_loop();  }