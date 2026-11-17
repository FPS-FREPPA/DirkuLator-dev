# DirkuLator

Project and AI-assisted contributions are credited in [CONTRIBUTORS.md](CONTRIBUTORS.md).

**The goal is to run Nintendo Switch 2 software accurately and usefully on a
native PS5 homebrew emulator.** The work covers CPU execution, GPU instruction
translation, rendering, memory and synchronization, controllers, audio, and the
native application.

We want games to draw the right picture, respond correctly, and keep running.
That means finding the cause of missing or incorrect behavior, implementing it
in shared emulator code, and keeping a reproducible test for the result.
Performance work should build on correctness and be measured on the target
hardware. This is early development, with substantial work remaining.

## What we are trying to achieve

1. **Correct CPU and GPU behavior.** Improve instruction and API coverage using
   source evidence and focused tests. Unsupported behavior must remain explicit;
   shader acceptance alone is not proof that its calculations are correct.
2. **Correct rendering.** Resolve problems such as the current white/cyan fog,
   hard fog boundaries, and mesh/vertex shattering by tracing the responsible
   draws, state, buffers, and translated instructions. Use difficult scenes as
   regression cases for the shared renderer.
3. **Reliable native execution.** Improve memory handling, GPU completion and
   synchronization, startup/shutdown, input, and long-session stability without
   masking faults by dropping rendering work.
4. **Usable performance.** Profile real bottlenecks and measure under stated
   conditions. Distinguish native PS5 results from desktop or mock tests.
5. **Open, reproducible development.** Publish source, patch provenance, pinned
   dependencies, build instructions, licenses, and honest results so others can
   fork, build, investigate, and contribute.

## Status

**Latest published candidates: 0.78rc** (title PPSA99863, content version 00.005.078, installed and verified on a console,
not yet run) **and 0.77rc** (PPSA99862, 00.005.077, run once). 0.67rc to 0.76rc were diagnostic and feature builds run on
the console and not published; their source is on this branch and what they changed is in [BUILD-NOTES.md](BUILD-NOTES.md).

What the console runs show, from the 0.58rc to 0.66rc history (details in [BUILD-NOTES.md](BUILD-NOTES.md)):

- **Stability is improving, not solved.** 0.60rc and 0.61rc ended on direct-memory exhaustion (a JIT block, then a
  10 MiB buffer). 0.62rc ran 101 minutes and 0.63rc 66 minutes in play without a crash report, with the pool
  full by design (11.5-11.9 GiB of 12.4 GiB held) and a shrinking largest free block (56 MiB at the start, 12-21 MiB
  later). That is a long session, not proof that exhaustion is gone.
- **Refused direct-memory requests are mostly first attempts.** The CPU heap and the Vulkan driver ask for a large
  block in one piece and fall back to pieces or chunks when refused. 0.63rc counted them and 0.64rc attributed them
  per caller (38 in 18 minutes against 1,287 in 66 minutes, and none in a fresh process with a warm shader cache).
- **The slowdown is not memory.** Gameplay runs at about 12-16 FPS and then slows, from about 280 s (0.64rc: for
  good, at 2-4 FPS) to about 5 min (0.65rc and 0.66rc: in waves of about 2 minutes of 2-6 FPS between recoveries),
  with the GPU nearly idle. The 0.65rc wait profiler showed the RADV driver's queue thread idle for up to 2 s while
  nothing was submitted; 0.67rc names the threads to find who the submitting side waits for.
- **Audio.** Since 0.60rc the game's music (any voice that loops for ever) was silenced; 0.66rc plays it. The
  output is fed steadily, so the choppiness is not the output thread. Music is missing at random in the intro and main
  menu (it plays in the game world). The 0.75rc and 0.76rc meters showed the renderer healthy (about 1000 command lists
  per five seconds, never a dropped voice, the game updating it throughout) while up to 25 s windows had no voice
  playing at all, so the game is not feeding or starting the music voices then. 0.77rc counts voice underruns and Opus
  decodes to tell a late feed from a stopped stream.
- **Slow stretches and stalls.** A slow stretch costs about 350-1700 us per draw against 15-19 us when healthy, with the
  GPU nearly idle. The PC sampler (0.68rc) shows the GPU thread parked in a different system wait during a stall than
  in normal idle; one 0.74rc stall lasted 153 s at 0.1 FPS with 2 GiB of memory free, so it is not only memory.
  0.75rc samples the CPU core threads as well: in a 0.75rc slow stretch every core thread and the GPU thread were
  mostly waiting (the cores 30-40 % of samples at one wait address they barely touch when healthy), with the memory
  nearly full; the system waits rather than computes.
- **Memory.** Several runs end in, or stall on, exhausted console memory (about 12 GiB held, allocations refused);
  OpenGL (0.70rc) crashed at the shader link when its 3 GiB heap filled. Neither is fixed.
- **Debug tools on this branch.** Touchpad (left half, a touch or a click) + L2 requests a GPU capture from the
  controller, with a CAPTURING / CAPTURE SAVED note on the overlay (0.71rc to 0.73rc); a read-only probe of Ocarina of
  Time's actors, groundwork for a debug fly shortcut (0.77rc finally gets the game's main module from the loader).
- **Rendering is not fixed.** In Kokiri Forest the picture still has view-dependent white haze, hard fog
  boundaries, shard-like polygon slabs, black water, unlit black props and characters, and an over-exposed
  yellow interior in Link's house. Close-range views can be clean, which points at the fog/depth blend pass rather
  than at geometry or textures in general.
- **Performance is far below target.** The 0.63rc run averaged about 6 FPS (median 4), with a fifth of the seconds
  presenting no frame and 40 seconds at 30 FPS or more; the later runs sit at 12-16 FPS between stalls.

Hardware stability, geometry and sustained 30 FPS remain unqualified.

## Downloads

Verified development prereleases, each with the matching source ZIP, checksums, validation record and change notes.

- **0.78rc** (title **PPSA99863**, latest): [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.78rc/DirkuLator-0.78rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.78rc/DirkuLator-0.78rc-source.zip) · [SHA256SUMS](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.78rc/SHA256SUMS) · [Validation](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.78rc/VALIDATION.json) · [Notes](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.78rc). Installed and verified on a console, not yet run. A new title ID, so it installs next to an older PPSA99862 app instead of over it.
- **0.77rc** (title PPSA99862): [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.77rc/DirkuLator-0.77rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.77rc/DirkuLator-0.77rc-source.zip) · [SHA256SUMS](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.77rc/SHA256SUMS) · [Validation](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.77rc/VALIDATION.json) · [Notes](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.77rc)

Only these two builds are kept as downloads. Older candidates (0.5.54rc to 0.66rc) keep their release page and notes, but their build files have been removed from the releases page; their source is in this repository's history.

The release notes of every candidate are on the [releases page](https://github.com/FPS-FREPPA/DirkuLator-dev/releases). Check a release's SHA256SUMS before installing it. `VALIDATION.json` is written when a package is built, so its
`hardware_tested` field does not reflect console runs made afterwards; the release notes say what each console run showed.

## Scope

- Native PS5 frontend, launcher, Vulkan/OpenGL integration, game loading, audio,
  controller input, and the existing storage/save interfaces.
- The complete current port patch series, including the GPU idle-fence ordering
  correction and task/mesh/shader diagnostics.
- An application-level input bridge: explicit arming, per-session commands,
  applied acknowledgments, physical-controller cancellation, and automatic
  expiry within three seconds. It is not a console-wide controller service.
- Source-built packages with matching version metadata, source provenance,
  artifact hashes, and retained build/validation results.

These candidates do not claim to fix the observed white fog, sharp fog
boundaries, or mesh/vertex shattering, and they do not change shaders or drawing.
A result for one build does not certify the next. No compatibility or
performance result is implied for games that have not been tested.

## Build

Use Linux/WSL (the current build environment is Ubuntu 26.04):

```sh
cd eden
make toolchain
make package JOBS=6
```

`make deps` fetches the pinned inputs. Source revisions, source archive hashes,
and the port patches are in `eden/UPSTREAM.json`, `eden/tools/deps.json`, and
`eden/tools/eden-patches/`. Detailed instructions are in
[BUILDING.md](eden/docs/BUILDING.md). Dependencies remain pinned; the initial
snapshot does not silently adopt unrelated upstream changes.

Build output is `eden/build/release/PPSA99862`. Use a published candidate's
checksums and validation notes before installing it. Development code can fail,
render incorrectly, or affect game progress; keep backups of your own data.

## Development and contributions

`DirkuLator` and `DirkuLator-dev` keep the project and development work separate.
Candidates are published on the development repository (`DirkuLator-dev`); a
candidate is published after the console test it needs. Both repositories
are public and forkable, with the inherited Git history retained. See
[CONTRIBUTING.md](CONTRIBUTING.md) for contribution and test expectations. Include
the revision, reproduction steps, actual test results, and whether evidence comes
from host checks or a physical PS5.

## Credits

DirkuLator is built on the work of others; the full list with licenses is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [NOTICE.md](NOTICE.md).

**Built on (included in the source and build)**

- [Eden](https://github.com/eden-emulator/mirror): the emulator core, with the libraries it pins.
- [EdGlantine-PS5](https://github.com/Portablelle/EdGlantine-PS5) by Portablelle: the inherited source baseline
  of the PS5 port.
- [PS5 Payload SDK](https://github.com/ps5-payload-dev/sdk) by John Törnblom (ps5-payload-dev) and its
  [pacbrew](https://github.com/ps5-payload-dev/pacbrew-repo) packages.
- [PS5 Mesa](https://github.com/mihawk-99/PS5_Mesa) and [PS5 Vulkan](https://github.com/mihawk-99/PS5_Vulkan) by
  Mihawk, [ps5-vulkan](https://github.com/mpereiraesaa/ps5-vulkan) by mpereiraesaa.
- [PS5 Native App Boilerplate](https://github.com/blackbearreloaded/ps5-native-app-boilerplate),
  [ps5-opengl](https://github.com/blackbearreloaded/ps5-opengl),
  [ProsperoPuzzles](https://github.com/blackbearreloaded/ProsperoPuzzles) and
  [ps5-homebrew-ui](https://github.com/blackbearreloaded/ps5-homebrew-ui) by BlackBearReloaded.
- [PS5-Lapy-JB-Daemon](https://github.com/ArkSama/PS5-Lapy-JB-Daemon) by ArkSama.

**Used alongside it (research, rules and test setup; not part of the build)**

- [AnyPS5](https://github.com/boykopovar/AnyPS5): contribution rules and PR research.
- [PracticeROM/sloperina](https://github.com/PracticeROM/sloperina) (GPL-3.0): its published memory layout of Ocarina of
  Time's Switch 2 build (docs/FINDINGS.md) is what the read-only probe in `oot_probe.h` checks, as groundwork for a debug
  fly shortcut.
- [Lichii](https://github.com/zortos293/Lichii), nxnative ([seedds/nxnative](https://github.com/seedds/nxnative)) and Ocarina Recomp: how other Switch 2
  emulators handle Ocarina of Time rendering (depth invariance, culling, point-topology meshes).
- [NintendoShaders](https://github.com/GRAnimated/NintendoShaders) by GRAnimated: a reference for Nintendo's
  render-library shader conventions.
- The PS5 jailbreak tools used on the test console: the Relapse exploit, kstuff, ShadowMountPlus and etaHEN.

Thanks to the Eden maintainers and contributors, Mihawk, mpereiraesaa, John Törnblom, SvenGDK, Portablelle, and the
PS5 homebrew community. AI assistance is credited in [CONTRIBUTORS.md](CONTRIBUTORS.md).

## License and corresponding source

DirkuLator's port code is distributed under **GPL-3.0-or-later**; see
[LICENSE](LICENSE). Third-party components retain their respective licenses and
copyrights; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), the original
file headers, and the notices bundled under `eden/third_party/`.

Existing upstream Git history and copyright notices are preserved. This
snapshot includes local modifications to the port, branding, controller bridge,
diagnostics, and build/packaging code. Dependency source locations and exact
revisions are retained in the pinned manifests and build scripts. Release
source archives and build instructions must remain available with binary
releases. No exclusive ownership of upstream or third-party code is claimed.

See the dated [modification and provenance notice](NOTICE.md) and the
[collected license texts and manifest](licenses/README.md). Published candidate
tags identify their tested source and are preserved; later documentation and
repository housekeeping changes are recorded separately in Git.

ROMs, game keys, proprietary firmware/system modules, saves, credentials,
private console captures, and local build caches are not part of this repository.
