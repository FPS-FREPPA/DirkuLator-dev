# DirkuLator

The goal is accurate and useful Nintendo Switch 2 emulation on native PS5
homebrew. Read the expanded [project goals and priorities](../README.md) and
[contribution guide](../CONTRIBUTING.md). The dated modification/provenance
notice is at [NOTICE.md](../NOTICE.md).

Native PS5 emulator development, with a focus on rendering correctness, reliable
controller input, repeatable builds, and evidence-based debugging.

## First development candidate: 0.5.54rc

This repository contains the current working source and patch set. **0.5.54rc is a
development release candidate, not a stable compatibility release.** Its PS5
content version is `00.005.054` and its application title is **DirkuLator**
(`PPSA99863`). The `rc` designation belongs to the release tag and archive name;
the console requires a numeric content version.

The native build, package checks, and component sanitizer regressions passed.
See [BUILD-NOTES.md](../BUILD-NOTES.md) and [VALIDATION.json](../VALIDATION.json) for
exact coverage and limits. This candidate has not been tested on a physical PS5.

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
startup and gameplay; those results do not certify 0.5.54rc. No compatibility or
performance result is implied for games that have not been tested.

## Build

Use Linux/WSL (the current build environment is Ubuntu 26.04):

```sh
make toolchain
make package JOBS=6
```

`make deps` fetches the pinned inputs. Source revisions, source archive hashes,
and the port patches are in `eden/UPSTREAM.json`, `eden/tools/deps.json`, and
`eden/tools/eden-patches/`. Detailed instructions are in
[BUILDING.md](docs/BUILDING.md). Dependencies remain pinned; the initial
snapshot does not silently adopt unrelated upstream changes.

Build output is `eden/build/release/PPSA99863`. Use a published candidate's
checksums and validation notes before installing it. Development code can fail,
render incorrectly, or affect game progress; keep backups of your own data.

## Development and contributions

`DirkuLator` and `DirkuLator-dev` keep the project and development work separate.
The first candidate is published on the development repository. Forks and pull
requests are welcome. Include the revision, reproduction steps, actual test
results, and whether evidence comes from host checks or a physical PS5.

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

ROMs, game keys, proprietary firmware/system modules, saves, credentials,
private console captures, and local build caches are not part of this repository.
