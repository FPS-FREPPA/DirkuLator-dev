# DirkuLator 0.69rc

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

