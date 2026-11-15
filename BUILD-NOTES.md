# DirkuLator 0.57rc

Native PS5 title PPSA99862, content version 00.005.057, development channel.

## Problem and changes

A 0.56rc PS5 crash stopped on the GPU thread after a 64 MiB CPU heap request.
The refusal snapshot showed 164 MiB total free but only a 5 MiB largest physical
range. The separately released large-block backend required one contiguous
physical allocation. Its fallback tried a permanent 96 MiB heap expansion;
that path could split physical backing only down to 2 MiB and also failed.
A preceding run failed a Vulkan buffer allocation with a largest block of 1 MiB.
These are distinct failures within the same finite CPU/GPU memory pool.

0.57rc adds a fallback confined to the C heap. It reserves one contiguous virtual
range, backs it with scattered direct-memory pieces, zeroes it, and returns each
piece when the block is freed. The initial contiguous allocation remains first.
No allocation is made for bookkeeping inside malloc: 64 fixed ledgers hold up to
1024 pieces each (about 1.5 MiB of static metadata). Exhaustion of either bound
fails with full rollback. Pieces can shrink to the existing 16 KiB CPU page size.
A block is rounded to 2 MiB for its virtual reservation; no extra 2 MiB header is
required on the scattered path. Caller alignment is preserved.

Permanent C-heap growth can also use 16 KiB CPU backing pieces. Its 8192-entry
scratch ledger covers up to 128 MiB at that minimum size and refuses larger
unrepresentable fragmentation safely. Large pages remain selected whenever
physical address, virtual address and size all permit them. Rollback restores
the owned reservation before making physical memory available again.

General page allocations and JIT alias contracts remain contiguous. GPU/RADV
alignment and mapping policy are unchanged. Successful small-heap growth remains
committed for the process lifetime; this does not compact or evict live objects.
The pool can still be exhausted. No OOM elimination is established by host tests.

## Upstream review

AnyPS5 rules were read at d4a1472af96802831ab3a0556aef253ef8a279c1,
including CONTRIBUTING, CONVENTIONS, REVERSE_ENGINEERING and HW_ORACLE.
AnyPS5 is a host relinker/runtime. Its #16474 dma-buf import and #16888 shared
heap budget changes are not native PS5 driver changes and were not transplanted.
The Lichii #1845 stale-image age fix and #1731 collector changes were reviewed.
Our collector has different pressure and retention logic; no unverified shader,
feedback, or texture-content change was included in this allocation candidate.

## Verification and limits

Native compilation and the normal release/package checks passed. The actual
production heap backend and permanent-commit operations passed ASan/UBSan and
TSan checks for the recorded 64 MiB failure with 1 MiB holes, zeroing, contents,
alignment, complete release/reuse, allocation/map/reservation failure rollback,
ledger bounds and eight concurrent threads. The preceding backend reproduces
the allocation failure. The focused pressure regression, package isolation,
capture-archive tests, repository hygiene and all 159 license hashes passed.
The build was incremental with compiler-cache reuse disabled; receipts identify
the exact compiled source and ELF hashes. See VALIDATION.json for coverage.

The installed 0.56rc app was backed up and removed before 0.57rc upload. All 72
new files matched a complete raw FTP read-back. Source and registered metadata
report 00.005.057; the installation manager confirms the title is installed and
closed. RADV, startup-shader and native OpenGL shader caches were backed up and
removed. Saves, ROMs, keys, firmware, settings and diagnostic dumps were retained.
Installation is verified; 0.57rc gameplay and performance are not yet qualified.

The overnight protocol restarts New Game with cold shader caches every run and
repeats one fixed house/ladder/bridge/shop/house route. The gameplay target is
30 FPS, measured at stable repeatable checkpoints. No emulation-speed, accuracy,
frame-generation, shader-suppression or scene-dependent quality change was added
to manufacture that number. See TEST_PROTOCOL_0_57RC.md for the repeat procedure.

0.56rc did not establish sustained hardware stability. White/cyan washout,
rectangular fog and geometry defects remain unresolved. This candidate claims
no shader correction or PS5 speed improvement. Physical validation of 16 KiB
CPU heap mappings and long-session behavior remains required. The existing guest
fine-page path already uses type-12 direct memory with 16 KiB CPU mappings;
that is the mapping contract reused here, not a new GPU-page assumption.

No deployment, save/cache deletion, gameplay, or public release is part of this
build step. The package is intended for the development branch for review/testing.
