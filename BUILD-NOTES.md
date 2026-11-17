# DirkuLator 0.78rc

Title PPSA99863, content version 00.005.078, development channel. Built on 0.77rc.

## What 0.78rc changes

- **A new title ID.** The app is now `PPSA99863` (concept ID 99863, content ID `UP9000-PPSA99863_00-EDENNX2PROTO0001`) instead of
  `PPSA99862`. It installs as its own app in `/data/homebrew/PPSA99863`, so the old PPSA99862 tile is a separate app and is
  removed on the console by hand. Saves, settings, shader caches and logs live in `/data/eden-nx2` and are not tied to the
  title ID, so they carry over. The update notice looks the app up on homebrew.page by title ID; the new ID has no listing
  there. Release notes for builds up to 0.77rc keep the ID they were built with.

---

Previous notes (0.77rc):

Content version 00.005.077, development channel, local candidate. Built on 0.76rc.

## What 0.77rc changes

- **The Ocarina of Time probe finds main.** The emulator's module finder answers with the start of the code region for this
  game, so 0.73rc to 0.76rc never read the actors. The loader now publishes where it loaded main (`EDEN_MAIN_BASE`, the
  address its `[DirkuLator] cheats: ... at 0x...` line already printed) and the probe uses that. Still read-only.
- **Where the intro music goes, second probe.** The 0.76rc run showed the renderer healthy (about 1000 command lists per five
  seconds, none dropping voices, the game updating it throughout) while whole windows had no voice updates: the game was not
  playing the music voices at those times. Eden patch `99zzzzzzg-voice-skip-opus-probe.diff`: `EDEN_AUDIO_VOICES` (voices in use,
  started, started with no wave buffer left (an underrun), commanded, averaged over the renders) and `EDEN_OPUS` (decodes,
  failures, samples, longest decode, per five seconds). They tell a stream the game did not refill from one it stopped.

---

Previous notes (0.76rc):

Content version 00.005.076, development channel, local candidate. Built on 0.75rc.

## What 0.76rc changes

- **Where the intro music goes (probe).** In the 0.75rc run the music came and went at random in the intro and cutscenes while
  the frame rate was steady. The meters showed whole five-second windows with no voice updates at all and a silent output
  (up to 25 s), and the PCM voices that carry the music quiet when they did run. `EDEN_AUDIO_RENDER` (every five seconds) now
  reports how often the game updated the audio renderer, how often a command list was generated, how many of those dropped
  voices for the DSP time budget, how many voices, and whether dropping is on (Eden patch `99zzzzzzf-audio-render-probe.diff`,
  system.cpp). It separates a stopped game audio thread from a renderer that drops the music voice. Read-only.

---

Previous notes (0.75rc):

Content version 00.005.075, development channel, local candidate. Built on 0.74rc.

## What 0.75rc changes

- **Audio level meters, to find where the game's background music goes.** In the 0.74rc new-game run only the narrator was
  heard. Voices run and the output port is fed steadily, so the question is whether the music voice is silent or mixed away.
  `EDEN_AUDIO_OUT` now ends with `mix_peak=` (the loudest sample sent to the port in the five seconds) and `silent_blocks=`
  (blocks that were all zero); `EDEN_AUDIO_VOICE` (every five seconds, per sample format) now ends with `peak=` (the loudest
  sample a voice update produced) and `audible=` (updates that were not silent). Eden patch `99zzzzzzd-voice-levels.diff`
  (decode.cpp). Read-only.
- **The PC sampler also watches the six CPU core threads** (`CPUCore_0` to `CPUCore_5`), not only the GPU threads, so a stall
  like the 0.74rc one (GPU thread parked in a wait, core 0 at 100 %) shows where the game's core is spinning. Same switch
  (`pc-sample.txt`), same `EDEN_PC_SAMPLES ... target=CPUCore_N` lines and run summary. The addresses of a guest core are in
  the JIT's code, not the app's, so what they show is whether a core is in one place (a spin) or moving.

---

Previous notes (0.74rc):

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

---

Previous notes (0.73rc):

Content version 00.005.073, development channel, local candidate. Built on 0.72rc.

## What 0.73rc changes

- **Capture with a touch.** A finger resting on the left half of the touchpad plus L2 now asks for a GPU capture; the touchpad
  does not have to be clicked (the click still works). While the chord is held the game does not see L2 (or the click).
  A finger left on the left half also makes any L2 press in the game a capture request, so lift the finger to play.
- **Read-only probe of Ocarina of Time's actors** (`oot_probe.h`): groundwork for a fly shortcut. It checks, without writing to
  the game, the layout published by PracticeROM/sloperina (GPL-3.0, docs/FINDINGS.md): the actor manager at main+0x4E90D90,
  its tree of live actors, Link's position at actor+0x31C and velocity at +0x388, and where doubles equal to his position sit
  near the actor (his physics record). `EDEN_OOT_PROBE` lines in stderr.log, each second for a minute and then every five
  seconds. Only for program 0400486024DEC000 with main build E0F3CCFAF50065AE; no other game starts it.

---

Previous notes (0.72rc):

Content version 00.005.072, development channel, local candidate. Built on 0.71rc.

## What 0.72rc changes

- **A message for the controller capture.** After Touchpad (left) + L2 the overlay line shows CAPTURING, and CAPTURE SAVED for
  six seconds once the capture's folder has stopped growing (the game is paused while it is written, so the line comes back
  just as it ends). It shows only while the overlay is on (Touchpad + R1). The 0.71rc shortcut itself is unchanged.
- Games already run docked unless Handheld was saved for them (`LoadGameDocked`); nothing changes there.

---

Previous notes (0.71rc):

Content version 00.005.071, development channel, local candidate (not published until tested). Built on 0.70rc.

## What 0.71rc changes

- **GPU capture from the controller.** Hold the left side of the touchpad and press L2: the next frame's images are written to
  `logs/capture/`, as `capture-now.txt` does. The game does not see the touchpad or L2 during the chord. Only the newest five capture
  folders are kept (a capture is 100-270 MB; the game stalls about 30 s while it is written). The log line
  `EDEN_FRAME_CAPTURE requested from the controller` marks each request. There is no on-screen message yet.

---

Previous notes (0.70rc):

Native PS5 title PPSA99862, content version 00.005.070, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.69rc (the console's own run summary and the PC sampler, neither
yet run on a console as of this build).

## What 0.70rc changes

1. **`TextureHeaderIndex`** (Eden patch `99zzzzzzc-texture-header-index.diff`; the design of Eglantine pull request 900).
   Adds `Tegra::Texture::TextureHeaderIndex` and `UsesHeaderByteOffsetHandles` and uses them where a texture handle
   becomes a header index: the shader-compile read (`GenericEnvironment::ReadTextureInfo`) and the texture cache
   (`VisitImageView`). Some Switch 2 bindless handles (Switch Sports Resort's scenery) hold the header's byte offset
   (index * 32); that reading is switched on only for that title (program id `0x0400000000000849`), only on the
   native-tiling path, and only when the plain index lies past the pool and the offset lands inside it. Ocarina of Time
   has an out-of-range handle (`0xbe000`) that must stay out of range, and does. The shader-compile read no longer
   reads past the end of the header table for an out-of-range index (it was guarded by an assert only): it returns an
   empty header, "no texture", as the runtime path already did. Our core never had the Switch Sports heuristic that
   pull request 900 removes from Eglantine, so this adds the function and the gating without changing what Ocarina of
   Time samples. Compile-time checks in `texture.h`.
2. **Output at 1440p.** The picture the app puts out (Settings > Video > Output resolution) defaults to 1440p
   (`kDefaultOutput`); it was 1080p. The console's `dirkulator.json` was set to 1440p at the user's request. The internal
   rendering scale stays 1x (the game's own 720p handheld output, scaled by the upscaling filter): 2x would be a real
   1440p render but quadruples the render targets, and the game already runs out of memory in about 17 minutes
   (the 0.68rc crash). The launcher still falls back to 1080p if a display refuses the size.
3. **No game autostart.** The one-click start (the app opens straight into the last game, 0.5.14) is off: the launcher
   opens. It happens only while `/data/eden-nx2/autostart.txt` exists; the test scripts create it for a run and remove
   it afterwards. Never after a crash restart, as before.
4. **In-app branding removed.** The Dirk launcher theme and its generated backdrop art are gone (Canopy, the default, and
   Slate remain; a saved `dirk` theme reads as the default), the loading screen's wordmark reads "LOADING" instead of
   "DIRKULATOR" (baked text regenerated), and the on-screen keyboard prompt's title is "Name". The PS5 tile (name,
   icon, background, sound), the config and file names and the credits are unchanged.
5. **Renderer switch in the menu** (already there, checked): Settings > Video > Renderer flips the global renderer between
   Vulkan (recommended) and OpenGL, and each game's own options have a Renderer row with the same two choices. OpenGL is
   Eden's OpenGL backend on the PS5 OpenGL 4.6 SDK 1.0.2 (the SDK the launcher already uses); it has not been run in a
   test run for this project in this session.

---

Previous notes (0.69rc):

Native PS5 title PPSA99862, content version 00.005.069, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.68rc (the PC sampler is included); adds the console's own run
summary. Diagnostics only: the emulated result is unchanged.

## What 0.69rc changes

1. **Run summary written by the console** (`headless/run_summary.h`). `/data/eden-nx2/logs/run-summary-<launch wall
   clock>.txt`, one file per launch, rewritten every 30 s (a crash or power cut leaves one at most 30 s old, written
   through a temp file and a rename) and at a clean exit, so a run nobody watched still leaves its result even though
   the next launch rotates `stderr.log`. Plain `key=value` text: build, elapsed and gameplay seconds (from the first
   second with more than 8,000 draws), FPS mean and median, seconds with no frame, under 8 FPS and 12 FPS or more;
   slow seconds (under 6 frames) and healthy seconds (10 or more) each with FPS, GPU busy, draws, draw time, microseconds
   per draw, submit and fence-drain time; the slow waves (runs of slow seconds with gaps of at most 3 s, at least
   10 slow seconds) with their figures; the audio output pacing totals (`EDEN_AUDIO_OUT`); and, when the PC sampler is
   on, the busiest sampled addresses of the GPU threads in slow and healthy periods (symbolise them with
   `tools/pc-sample-report.py` or addr2line against the exact ELF). On by default; `run-summary-off.txt` switches it off.
   Voice starvation (`EDEN_AUDIO_VOICE`) stays in `stderr.log` only. Host check `tools/check-run-summary.py`.

## Carried over from 0.68rc

The release-safe PC sampler of the GPU threads (`pc-sample.txt`, `EDEN_PC_SAMPLES`; `headless/pc_sampler.h`), untested on a
console as of this build.

---

Previous notes (0.68rc):

Native PS5 title PPSA99862, content version 00.005.068, development channel. **Local candidate: not published
until it has been tested on a console.** Built on 0.67rc; adds a sampler for the GPU threads, off unless a switch
file is present, so the emulated result is unchanged.

## What 0.67rc showed on the console (2026-11-17, ~12:44-12:57 UTC, hand-played, firmware 13.00, warm shader cache)

Full numbers in the run's `ANALYSIS-0.67rc.md`; summary in `INVESTIGATION-065rc.md` section 9.
- 504 of 674 gameplay seconds at 2-3 FPS with the GPU about 3 % busy; the first slow stretch began 25 s after the load.
- Draw recording cost 361 us per draw in slow seconds against 18 us healthy (20x) and 844 ms per second against 393 ms,
  while the game drew a tenth as much. Fence drains, submits and queue waits were lower. The named wait profile showed no
  wrapped wait on the draw side: the draw thread computes.
- Audio: the output thread was on time (149,132 blocks, none over 50 ms late) and the render queue never ran dry, but
  voices were reported starved in most 5 s windows; the choppiness is in the voice layer.
- The pad log (`logs/input-record.csv`) recorded 4,009 changes over 868 s.

## What 0.68rc changes

1. **Release-safe PC sampler** (`headless/pc_sampler.h`). With `/data/eden-nx2/pc-sample.txt` present a sampling thread
   sends SIGUSR2 to the `GPU` and `GPUBack` threads (100 Hz by default, starting 45 s after the first of them names
   itself; `rate_hz=` and `delay_s=` lines in the file change that), the handler stores the interrupted instruction
   pointer in a ring (atomics and array stores only), and every 10 s `EDEN_PC_SAMPLES up_s= target= n= lost= sent=
   failed= base= top: <address relative to __eden_text_start>=<count> ...` is printed. `tools/pc-sample-report.py`
   symbolises them against the exact ELF and splits slow from healthy windows with the run's `perf-monitor.csv`.
   Off (and no signal handler, no thread) without the file. Same mechanism as the development profile's sampler, on
   the same SIGUSR2; the instruction pointer is read from the native signal context (word 28) as there. Host check
   `tools/check-pc-sampler.py` (a thread spinning in a known function: every sample is in it, none lost, no failed signal).

---

Previous notes (0.67rc):

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
