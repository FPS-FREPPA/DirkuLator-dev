# DirkuLator 0.56rc

Native PS5 title PPSA99862, content version 00.005.056.

## Changes

- Startup cached graphics/compute pipeline tasks temporarily use the application's
  verified allowed CPU mask, restoring each worker's previous mask on normal and
  exceptional exit. The pool is capped to the population of that mask. On the
  investigated console, 0.5.55rc had 15 compiler workers confined to six secondary
  SMT lanes. This change is confined to pre-game cache compilation; later runtime
  shader work and guest/GPU placement retain their existing policy.
- CPU heap growth uses 32 MiB pieces instead of 128 MiB. Allocations from 8 MiB
  receive separately releasable backing instead of waiting until 32 MiB; freeing
  such blocks returns their backing. Existing-space fallback, alignment and
  realloc ownership are preserved. Small heap pieces remain committed.
- Idle staging retention uses total free memory as well as the largest free
  block. The low-pressure reuse allowance remains 64 MiB until headroom becomes
  critical (largest below 32 MiB or total free below 256 MiB), when completed,
  non-deferred idle buffers can all be returned. The pool is polled every frame
  below 64 MiB largest free, rather than once every sixteen frames.
- RADV memory layers are checked against actual source instead of a matching
  stamp alone, and missing layers are repaired or fail closed on changed input.
  Isolation verifies hashes of both input and renamed archive. Native checks
  reject a binary without the compiled fragmented-allocation path. The matched
  0.5.55rc ELF lacked that fallback despite a matching patch receipt.

## Verification and limits

Fresh-object native compilation, normal release/package checks, startup-affinity
scope/transform checks, driver repair/fragmentation/rollback sanitizers, eight-thread
heap tests including TSan, staging/reclamation checks, memory-pressure regression,
capture-archive tests and package isolation passed. All 159 dependency license
hashes and repository hygiene checks passed. See VALIDATION.json for the source
commit, binary hash, check-log hashes and limits. No PS5 gameplay pass is claimed.

Mock/sanitizer tests do not measure PS5 compilation speed, whole-chip GPU load,
memory fragmentation over a real play session, or shader numerical correctness.
The physical pool is still finite. Small allocator pieces and live game data
are not moved or evicted. White/cyan washout, rectangular fog boundaries and
incorrect geometry remain unresolved; this candidate claims no fog/mesh fix.

The user requested a clean installation after qualification, including deletion
of the current version, OoT saves and shader caches. After installation the app
is to remain closed pending further orders. No gameplay validation is implied.
