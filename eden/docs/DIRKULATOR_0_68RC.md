# DirkuLator 0.68rc

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

