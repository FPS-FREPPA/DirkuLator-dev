# DirkuLator 0.76rc

Content version 00.005.076, development channel, local candidate. Built on 0.75rc.

## What 0.76rc changes

- **Where the intro music goes (probe).** In the 0.75rc run the music came and went at random in the intro and cutscenes while
  the frame rate was steady. The meters showed whole five-second windows with no voice updates at all and a silent output
  (up to 25 s), and the PCM voices that carry the music quiet when they did run. `EDEN_AUDIO_RENDER` (every five seconds) now
  reports how often the game updated the audio renderer, how often a command list was generated, how many of those dropped
  voices for the DSP time budget, how many voices, and whether dropping is on (Eden patch `99zzzzzzf-audio-render-probe.diff`,
  system.cpp). It separates a stopped game audio thread from a renderer that drops the music voice. Read-only.
