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

**Latest published candidate: 0.63rc** (title PPSA99862, content version 00.005.063). A candidate is
published after the console test it needs.

What the console runs show, from the 0.58rc to 0.63rc history (details in [BUILD-NOTES.md](BUILD-NOTES.md)):

- **Stability is improving, not solved.** 0.60rc and 0.61rc ended on direct-memory exhaustion (a JIT block, then a
  10 MiB buffer). 0.62rc ran 101 minutes and 0.63rc 66 minutes in play without a crash report, with the pool
  full by design (11.5-11.9 GiB of 12.4 GiB held) and a shrinking largest free block (56 MiB at the start, 12-21 MiB
  later). That is a long session, not proof that exhaustion is gone.
- **Refused direct-memory requests are mostly first attempts.** The CPU heap and the Vulkan driver ask for a large
  block in one piece and fall back to pieces or chunks when refused. 0.63rc counted them; attributing them per
  caller, so a run can show which request, if any, is a real loss, is the next step.
- **Rendering is not fixed.** In Kokiri Forest the picture still has view-dependent white haze, hard fog
  boundaries, shard-like polygon slabs, black water, unlit black props and characters, and an over-exposed
  yellow interior in Link's house. Close-range views can be clean, which points at the fog/depth blend pass rather
  than at geometry or textures in general.
- **Performance is far below target.** The 0.63rc run averaged about 6 FPS (median 4), with a fifth of the seconds
  presenting no frame and 40 seconds at 30 FPS or more.

Hardware stability, geometry and sustained 30 FPS remain unqualified.

## Downloads

Verified development prereleases, each with the matching source ZIP, checksums, validation record and change notes.

- **0.63rc** (latest published): [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.63rc/DirkuLator-0.63rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.63rc/DirkuLator-0.63rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.63rc).
- **0.62rc**: [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.62rc/DirkuLator-0.62rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.62rc/DirkuLator-0.62rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.62rc).
- **0.61rc**: [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.61rc/DirkuLator-0.61rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.61rc/DirkuLator-0.61rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.61rc).
- **0.60rc**: [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.60rc/DirkuLator-0.60rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.60rc/DirkuLator-0.60rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.60rc).
- **0.59rc**: [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.59rc/DirkuLator-0.59rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.59rc/DirkuLator-0.59rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.59rc).
- **0.58rc**: [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.58rc/DirkuLator-0.58rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.58rc/DirkuLator-0.58rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.58rc).
- **0.57rc**: [PS5 ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.57rc/DirkuLator-0.57rc-PS5.zip) · [Source ZIP](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/download/v0.57rc/DirkuLator-0.57rc-source.zip) · [Notes and checksums](https://github.com/FPS-FREPPA/DirkuLator-dev/releases/tag/v0.57rc).

Earlier candidates (0.5.54rc and before) are on the [releases page](https://github.com/FPS-FREPPA/DirkuLator-dev/releases). Check a release's SHA256SUMS and
VALIDATION.json before installing it; `hardware_tested` in VALIDATION.json says whether a console ran that build.

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

PR research may reference **AnyPS5**, **Lichii**, and **Eden**. A relevant PR is a
research lead until its changes have been reviewed, integrated, and tested;
no unreviewed PR is advertised as an incorporated fix.

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
