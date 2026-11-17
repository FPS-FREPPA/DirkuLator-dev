# DirkuLator 0.77rc

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
