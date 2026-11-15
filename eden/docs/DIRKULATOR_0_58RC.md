# DirkuLator 0.58rc

Native PS5 title PPSA99862, content version 00.005.058, development channel.

## Relaxed GPU transfer-buffer restriction

0.57rc limits completed reusable GPU transfer buffers to 64 MiB when the pool's
largest free physical block is below 512 MiB, and to zero below 32 MiB even if
much more memory is free across several ranges. The compiled RADV allocator can
back a device buffer with several 2 MiB physical ranges. A fragmentation-only
limit can therefore discard reusable buffers despite usable total headroom.

0.58rc chooses the completed-buffer reuse allowance from total shared-pool free
memory when that query is known:

| Total free | Reusable completed staging buffers |
| --- | --- |
| At least 1024 MiB | Up to 256 MiB |
| 512 to below 1024 MiB | Up to 128 MiB |
| 256 to below 512 MiB | Up to 64 MiB |
| Below 256 MiB | None retained |

A known largest physical range below 2 MiB still retains none, matching the
existing driver's minimum fragmented-backing granule. Unknown total headroom
uses the previous conservative rule. The original 256 MiB maximum stays bounded;
this does not enlarge the physical pool or increase the GPU's reported limits.
Actual allocation refusals still release all eligible idle buffers and run the
existing reclaim/retry path. Busy and deferred/in-flight buffers remain protected.

The intended benefit is fewer repeated transfer-buffer allocations and less
allocation churn. This is not a measured FPS claim. Both CPU and GPU share the
same finite pool; increased retained staging can leave less room for other live
objects, and hardware comparison is required. Collector pressure thresholds and
the critical total-free boundary remain unchanged. 0.57rc's CPU heap fix is retained.

No shader lowering, emulated accuracy/timing, resolution, tensor execution,
workgroup hardware limit, GPU mapping alignment or rendering-work suppression is
changed. The target remains measured 30 FPS gameplay with correct emulation.
White/cyan fog, hard boundaries and geometry faults remain unresolved.

## Verification

Production staging-policy and real generated-pool integration checks passed
under ASan/UBSan, covering known/unknown memory queries, all tier boundaries,
sub-2-MiB physical holes, critical pressure transitions and preservation of
busy/deferred buffers. A controlled 60-frame transfer-working-set model reports
240 recreated buffers with the 0.57rc header and zero with 0.58rc. These are
model allocation counts, not GPU timings or FPS measurements.

Native compilation, normal release/package checks, pressure regression,
package isolation, capture-archive tests, repository hygiene and all 159 license
hashes passed. The native ELF contains the new staging-policy diagnostic marker
and inherited CPU fragmented-backing path. The build was incremental with compiler
cache reuse disabled. VALIDATION.json records source, binary and check-log hashes.

The old 0.57rc app was backed up and removed before 0.58rc upload. All 72 new
files matched full raw FTP read-back; source and registered metadata agree on
00.005.058, with the title installed and closed. Shader-cache locations are empty
for a cold start; they had already been cleared for 0.57rc, which was not played.
Saves, ROMs, firmware, keys, settings and diagnostic dumps are preserved.

0.57rc remains an archived comparison baseline with its own package and private
Luna instructions. 0.58rc has a separate version-guarded overnight handoff and
TEST_PROTOCOL_0_58RC.md. Every run starts New Game with cleared shader caches and
repeats the fixed route. Increased cache allowance can reduce churn but consumes
more headroom; sustained PS5 stability and a 30 FPS improvement remain unqualified.
No 0.58rc gameplay was run during build or installation verification.
