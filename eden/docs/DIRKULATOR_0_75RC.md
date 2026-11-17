# DirkuLator 0.75rc

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
