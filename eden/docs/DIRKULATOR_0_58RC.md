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

Qualification is pending. Check the production policy and trimming behavior
against the preceding header, including fragmented-but-roomy pools, pressure
boundaries, unknown queries, sub-2-MiB holes and preservation of busy/deferred
buffers. The native package and qualification receipt identify actual results.

0.57rc remains the installed overnight baseline for its fixed New Game/cold-cache
route protocol. 0.58rc is a separate comparison candidate; it is not silently
installed or substituted into an ongoing test.
