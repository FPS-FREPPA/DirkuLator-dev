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

## Development candidate: 0.56rc

This repository contains the current working source and patch set. **0.56rc is a
development release candidate, not a stable compatibility release.** Its PS5
content version is `00.005.056` and its application title is **DirkuLator**
(`PPSA99862`). The `rc` designation belongs to the release tag and archive name;
the console requires a numeric content version.

The candidate adds startup-only compiler affinity, more elastic allocation
retention, and driver source/archive/binary checks after a stale memory-patch
receipt was found in 0.5.55rc. See [BUILD-NOTES.md](BUILD-NOTES.md) for scope and
validation status. Native compilation, component regressions and package checks
passed; [VALIDATION.json](VALIDATION.json) records their coverage and exact source
commit. PS5 performance and sustained stability await testing; no fog/mesh
correction is claimed.

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

This candidate does not claim to fix the observed white/cyan fog, sharp fog
boundaries, or mesh/vertex shattering. Earlier 0.5.21 hardware runs demonstrated
startup and gameplay; those results do not certify 0.56rc. No compatibility or
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
The first candidate is published on the development repository. Both repositories
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
