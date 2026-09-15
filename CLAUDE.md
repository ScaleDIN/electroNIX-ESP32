# electroNIX-ESP32

ESP32 firmware rewrite for electroNIX/Nick2 Nixie tube clock boards
(originally ATmega-based; see `WIRING.md` in `electroNIX/` for the
retrofit/rewiring background).

## Where the code lives

- `electroNIX/` — the active Arduino sketch. This is what gets compiled
  and flashed. Files: `electroNIX.ino`, `board.h`, `clock_core.{h,cpp}`,
  `display.h`, `display_nick2.cpp`, `display_testa.cpp`, `web_ui.h`,
  `WIRING.md`.
- `original electronix clock/` — legacy reference material (old .hex
  files, PDFs, schematics for the original ATmega firmware). Not part of
  the ESP32 build; only useful for historical/hardware reference.

## `board.h` — per-device setting, not a code default

`#define BOARD <n>` near the top of `board.h` selects which physical
board this build targets (electroNIX 4, electroNIX 4+S/6T, electroNIX 3,
Nick2 IN-12, etc.). This value is set per the developer's own hardware and
is expected to differ between the repo and a local working copy — don't
"fix" it to match the repo unless the user asks. Everything else in the
sketch keys off the `BOARD_HAS_*` capability flags derived from this
selection, never off `BOARD` directly.

## Workflow

The user edits/reviews here, changes get committed and pushed to GitHub,
and GitHub is the source of truth they pull from on their own machine to
compile and flash via the Arduino IDE. The codebase is reasonably stable;
expect infrequent, targeted changes rather than large refactors.
