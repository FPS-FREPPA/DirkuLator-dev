# Source and rebuilding

The source for 0.71rc is on the `DirkuLator-dev` branch at
https://github.com/FPS-FREPPA/DirkuLator-dev. The package's VALIDATION.json
identifies the exact compiled source commit; its accompanying source archive
contains that commit. Existing candidate tags remain unchanged.
The Git history, port modifications, patch series, and build/packaging scripts
are included. From the source root, run `cd eden` and `make package JOBS=6` on
the Linux/WSL environment described in `eden/docs/BUILDING.md`.

Exact upstream revisions, archive hashes and download locations are retained in
`eden/UPSTREAM.json` and `eden/tools/deps.json`. `make deps` fetches those inputs;
`eden/tools/prepare-build.sh` applies the supplied patch series in filename order.
The source dependencies and original notices remain under their own licenses.
The original public source URLs are also recorded in THIRD_PARTY_NOTICES.md.
The native runtime source is pinned by the boilerplate entry in the manifests;
no proprietary console system libraries are distributed.

The release includes collected original license/copyright texts under
`licenses/dependencies/`. The bridge regression can be run with
`python3 eden/tools/check-input-bridge.py`; ordinary core and package checks are
part of the provided build scripts. Private captured shaders used for extra local
diagnostics are excluded from the public source and are not required to build it.

Keep the matching source, dependency pins, notices, and build instructions
available whenever redistributing a binary, and follow each included license.

## Repository documentation review

The dated modification notice, license inventory, contribution guide, expanded
project goals, and ignore/line-ending rules are maintained on the repository
branches. Follow-up documentation commits preserve the original `v0.5.54rc`
candidate tag and its tested emulator code. The development release also carries
a repository-review supplement with those updated notices and documents.
