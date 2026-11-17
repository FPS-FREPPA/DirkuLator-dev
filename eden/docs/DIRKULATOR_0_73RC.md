# DirkuLator 0.73rc

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
