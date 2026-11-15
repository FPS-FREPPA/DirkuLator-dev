# DirkuLator 0.5.55rc

This candidate responds to the 0.5.54rc PS5 cutscene run. The GPU worker terminated
with `VK_ERROR_OUT_OF_DEVICE_MEMORY`; the final allocation report showed 173 MiB
free in the shared console memory pool and a largest free block of 8 MiB.
The crash report identifies version `00.005.054`. Disk space does not increase
this CPU/GPU memory pool.

Changes:

- Start texture-cache pressure handling below 2 GiB free, aggressive handling below
  1.5 GiB, and the tight pass below 1 GiB. Previous thresholds were 1.5 GiB, 1 GiB,
  and 512 MiB. Refresh the pool reading every frame below 2 GiB instead of waiting
  eight frames while guest allocations continue. GPU-written images retain their
  existing readback and synchronization rules before eviction.
- Log native GPU-dump start, the fact that rendering pauses synchronously, and its
  elapsed milliseconds. The bridge reports that pause and waits up to ten minutes
  for an explicitly requested dump. The sixth
  dump in the previous run coincided with a 176.2-second zero-frame interval and
  completed immediately before rendering resumed. The native capture remains
  synchronous: this change reports its actual completion rather than treating
  90 seconds as a failed request. Do not issue heavy dumps during cutscenes.
- Recognize diagnostic builds in the archive watcher's title-exit detection,
  removing the hard-coded 0.5.21 check that missed 0.5.54rc.

CPU/GPU emulation correctness is the priority. No audio work is included.
The white/cyan fog, rectangular boundaries, and broken geometry are unresolved.
The earlier collection thresholds are a memory-pressure mitigation; this candidate
requires a console Continue test before claiming the allocation crash is fixed.

Saves, games, keys, firmware, and user settings are preserved during replacement.
Licenses, source history, dependency notices, and build provenance remain included.
