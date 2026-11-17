# DirkuLator 0.65rc

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
