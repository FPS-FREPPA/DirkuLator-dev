# DirkuLator 0.66rc

Native PS5 title PPSA99862, content version 00.005.066, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.65rc (wait profiler); the only behaviour change is audio.

## What 0.66rc changes

1. **The game's music plays.** Since 0.60rc a voice that loops a wave buffer for ever (`loop_count < 0`) was decoded
   but silenced (`decode.cpp`, layer `99zzzzzzb-music-off.diff`; ambient loops went with it). Sound effects and
   voices always played, so in the 0.65rc run the game world had sound but the main menu, which only has music,
   was silent. 0.66rc plays those voices. `/data/eden-nx2/music-off.txt` (new, replaces `music-on.txt`) brings the
   old muting back for an A/B. Voice state, timing and decoding are unchanged either way.
2. **Logged.** `EDEN_MUSIC_PLAYING` / `EDEN_MUSIC_MUTED voice updates=N` print at the first update and at every
   doubling; startup prints `EDEN_MUSIC on` or `EDEN_MUSIC off`.

## What 0.65rc showed on the console (2026-11-17, ~11:23 UTC, one launch, firmware 13.00, warm shader cache)

- Wait profiler works (no dropped records, 83 threads). About 5 min 17 s after gameplay began the frame stream
  turned into alternating 0-frame seconds and 2-7 FPS seconds, with draws swinging between ~50 and ~8,000 per second.
  The longest single wait, about 2.2 s, was in the RADV driver's condition wait (`eden_radv_private_cnd_wait`,
  `threads_posix.c:112`); the other long waits are ordinary thread-pool and sleep waits. Details:
  `logs/luna-0.65rc-20261117T112325Z/run-001/OBSERVATIONS.md`.
- Rendering: haze, a vertical black slab and a white glow in the log arch, and a 3D view rotated about 90 degrees
  relative to the UI for ~3 minutes.

