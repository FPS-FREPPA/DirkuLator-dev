# DirkuLator 0.74rc

Content version 00.005.074, development channel, local candidate. Built on 0.73rc.

## What 0.74rc changes

- **The Ocarina of Time probe finds the game's main module.** In 0.73rc it asked for the main module before the loader had
  mapped it and read from the start of the code region (0x8000000, "actor manager not readable" every tick); the real main was
  at 0x80864000. It now asks again every tick until the answer differs from the code region's start, and logs
  `EDEN_OOT_PROBE on main=...` when it has it. Still read-only.
- **The controller capture logs the free memory** (`EDEN_FRAME_CAPTURE requested from the controller ..., free memory N MiB`).
  In the 0.73rc run the fourth capture (frame 3274) never finished: the game stopped drawing for about three minutes with
  190 s of no frames, after captures that took 11 s, 12 s and 40 s while free memory had fallen to about 300-700 MiB. The log
  line lets the next run tie capture time to free memory before any limit is chosen.
