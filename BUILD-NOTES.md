# DirkuLator 0.67rc

Native PS5 title PPSA99862, content version 00.005.067, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.66rc (music on); the changes are diagnostics only, the
emulated result is unchanged.

## What 0.67rc changes

1. **Thread names in the wait profile.** `EDEN_WAIT_PROFILE` entries are now `t<N>(<address>,<name>)`. In the
   0.66rc run the RADV driver's queue thread sat idle up to 1.9 s during the stall waves but the other long waits
   could not be attributed because threads were only numbered. The names come from the table the crash report keeps
   (`Eden::Crash::named_threads`, filled by the `SetCurrentThreadName` hook); `eden_thread_name_of` in
   `headless/performance.cpp` looks them up. The system calls are not used: `pthread_setname_np` hangs on this
   platform and the SDK has no stub for `pthread_get_name_np` (the first 0.67rc build failed on it). `-` when a
   thread never named itself. Host check updated.
2. **Audio output pacing probe.** `EDEN_AUDIO_OUT name=... blocks=... max_gap_ms=... late8= late16= late50=
   max_render_ms= max_output_ms=` every 5 s from the thread that feeds the PS5 AudioOut port one 256-frame
   (5.33 ms) block at a time (`headless/audio.cpp`). The render queue never ran dry in 0.66rc (`EDEN_AUDIO_SINK
   padded=0`, `EDEN_AUDIO_VOICE starved=0`) yet the user heard choppy sound, so the break-up must be on the
   output side; this measures it. The timer restarts after a pause so a pause is not counted as a dropout.

3. **Physical pad log for replay.** `logs/input-record.csv` (`t_ms,buttons_hex,lx,ly,rx,ry,l2,r2`, one line per
   change of the player's physical pad, from the launch; `# launch` comment lines; appended across launches;
   `/data/eden-nx2/input-record-off.txt` switches it off). `tools/input-record-to-route.py` turns a launch of it into
   a route for the bridge's route tool, so a run played by hand can be repeated by the input bridge. The bridge's own
   inputs never reach the log. Host check `tools/check-input-record.py`.

## Reference clones reviewed (nothing taken)

`repos/yuzu-mainline` (the original yuzu, last commit June 2025, GPL-2.0-or-later) and `repos/Ryubing` (Ryujinx
fork, C#, MIT) were compared with the Eden audio core we build. yuzu-mainline's `SinkStream::ProcessAudioOutAndRender`
is the same algorithm as Eden's (underrun repeats the last frame), and nearly every audio_core file differs only by
15 months of divergence and licence headers, so there is no fix to port for the choppy audio. No code from either
clone is in this build; any later use needs the evidence first and a licence check (GPL-2.0-or-later and MIT code in a
GPL-3.0-or-later project).

---

Previous notes (0.66rc):

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

---

Previous notes (0.65rc):

Native PS5 title PPSA99862, content version 00.005.065, development channel. **Local candidate: not published
until it has been tested on a console.**

## What 0.64rc showed on the console

Two launches on 2026-11-17 (04:36 and 05:18 UTC, about 2 h 10 min in total, no crash, orderly close), the
newest autosave loaded each time, driven by the input bridge with human-like routes; 5 GPU captures
(177-275 MB each) and about 1,000 phone photos in bursts of three. Everything below is linked from
`INVESTIGATION-065rc.md` and `PROPOSAL-065rc.md` in the project folder.

- **Refusal attribution works.** `EDEN_DMEM_REFUSED total=38 slots=4` at 18 min (0.63rc: 1287 in 66 min); a fresh
  process with a warm shader cache had none. Callers: `eden_heap_pages`, `AllocatePagesAt`, the driver's probe.
- **Warm shader cache** (kept from the second launch on): game loaded in 3.9 s instead of 15 s; the pool stays
  unfragmented (largest free block 440-675 MiB instead of 28-100 MiB); slow seconds fell from 60 % to 39 %.
- **A reproducible collapse after ~280 s of gameplay.** Both launches ran at ~12 FPS (30 ms/frame draw recording)
  for 281 / 279 gameplay seconds and then, for good, at 2-4 FPS with 300-440 ms/frame draw recording at ~1000
  draws/frame, GPU 4 % busy. It starts with GPU stalls (2-10 s) and a 20-30k jump of the guest syncpoint count.
  Not memory (900 MiB free, 0 refusals), not the captures, not Link's position. Every wait counter the
  performance monitor has (pipeline, lock, fence, guest sync) reads 0 ms in those seconds: the wait is somewhere
  not counted.
- **Haze** (white veil with hard diagonal/curved edges): the scene colour before the fog blend pass
  (PS `4b2adcc4d5577ed1`) is correct, that pass alone adds the veil; its 360x202 distance input is 99.6 % unwritten;
  it reads three 3D volumes that captures do not record. **Dark/black/blue frames**: null texture and shadow
  handles (EDEN_TEXTURE_HANDLE_ZERO, dozens of pixel-shader keys); a 13-minute blue void was probably a stuck load
  screen. **Bolt/shards**: crisp geometry drawn very early in the frame. Rendering faults are unchanged and
  nothing in 0.64rc or 0.65rc changes shaders or drawing.

## Changes

1. **Wait profiler** (`src/wait_profile.c`, wrapped in `tools/link-headless-native.sh`, reported from
   `headless/performance.cpp`). It wraps `pthread_cond_wait`, `pthread_cond_timedwait`, `pthread_mutex_lock`
   (try-lock first), `nanosleep` and `usleep`, and records waits and their time per (thread, primitive, caller).
   `EDEN_WAIT_PROFILE sites=N threads=N dropped=N top: tN(id) <primitive> caller=0x... count=N total_ms=N max_ms=N;`
   is printed every 10 s on stderr; callers are offsets from `__eden_text_start`, symbolised against
   `logs/logs-0.65rc/llvm-pie-0.65rc.elf`. It changes no result: each wrapper calls the real function.
   Threads cannot be named on this platform, so threads are numbered in order of their first wait.
2. Host check `tools/check-wait-profile.py` (contended mutex 119 ms, condition variable 150 ms, nanosleep 60 ms,
   usleep 40 ms measured within a few ms; uncontended lock records nothing; counters cleared by the report).
3. Console switches changed outside the build: `dump-shaders.txt` lists the fog pair and the writer of its
   distance input; the shader cache is kept and backed up at the end of each run.
4. Everything in 0.64rc, 0.63rc and 0.62rc stays. No memory limit, shader or drawing change.

## Not verified

On the console: that the wrappers add no measurable cost (a try-lock and two clock reads per blocking call), that
the profile accounts for the draw thread's 300-440 ms/frame in the slow seconds (if the time is not waiting, the
next step is a stack sampler), and that no code depends on the exact symbol resolution of the wrapped calls.
The proposed graphics and performance fixes are in `PROPOSAL-065rc.md`; none of them is built yet.
