# DirkuLator 0.62rc

Native PS5 title PPSA99862, content version 00.005.062, development channel.

## What 0.61rc showed on the console

One session: the latest autosave (Kokiri Forest) loaded, Link walked to the door of his house and
opened it, the forest cutscenes with Saria played, and the app ran 1174 s. That is past the 1030 s at
which 0.60rc aborted (its JIT code cache could not get a 16 MiB block), and the JIT did not fail
again. The session ended on the next scene change, right after A was pressed to move Saria's
dialogue on (about 3 minutes after the door):

    VK_ERROR_OUT_OF_DEVICE_MEMORY, GPU thread
    buffer of 10289152 bytes, usage 0xbff: refused, and refused outside the allocator's budget
    the pool has 102 MiB free, its largest free block is 3 MiB;
    the allocator holds 3086 MiB in blocks, 2803 MiB of it in use

Findings behind 0.62rc:

- **The buffer was not a staging buffer.** 0.60rc/0.61rc wait for the pool only in the staging pool's
  `MakeOrReclaim`. This 10 MiB buffer (a buffer cache buffer, usage 0xbff) went through
  `MemoryAllocator::CreateBuffer` directly: one more ask outside the budget, then the session's end.
- **The free memory was not usable.** For the 800 s before, the pool stood at 440-950 MiB free with a
  largest free block of 29-88 MiB; at the end 102 MiB free and 3 MiB. The GPU takes memory in pieces of
  2 MiB or more, so free runs under 2 MiB ("crumbs") are free for the CPU only. Blocks under 2 MiB
  (the guest's compact blocks, the CPU heap's 16 KiB pieces when it is taken whole) were placed by the
  system like everything else, from the bottom, among the graphics memory that comes and goes.
- **The heap's return worked**: 14 of 54 heap spaces were retired and 392 MiB given back
  (`EDEN_HEAP_SPACES retired=14 returned_mib=392`), as designed in 0.61rc. The 40 spaces still in use
  held 0-10 MiB free each at the end; the heap has nothing more to give.
- **The GPU stalled 4 times** (8.5 s, 8.4 s, 2.5 s, 15.2 s, all recovered by the watchdog).
- The guest held 6.0 GiB, the allocator 3.0 GiB (2.8 in use), the heap 1.3 GiB and the large CPU
  blocks 0.75 GiB for the whole session; the pool is full by design and 0.5 GiB of headroom is what
  keeps a session alive.
- Rendering faults of 0.58rc-0.60rc were all still there (white wash-out, shard slabs, hard fog
  rectangles); nothing in 0.62rc changes shaders or drawing.

## Changes

1. **Buffers wait for the pool too** (`MemoryAllocator::CreateBuffer`, `tools/prepare-vulkan-port.py`).
   A buffer refused outside the budget is asked for again every 20 ms for up to 1.5 s. Not when the
   staging retry is already waiting on the thread (`Eden::StagingBuffers::in_make_or_reclaim`).
2. **Crumbs are packed** (`src/direct_memory.c`). Direct-memory blocks under 2 MiB are placed in the
   first room at or above the start of the top 3 GiB of the pool, where they lie together, instead of
   among the session's graphics memory; where that region has no room they are placed as before.
   `EDEN_NX2_CRUMBS_OFF` (`crumbs-off.txt`) disables it. Host check: `tools/check-direct-memory-crumbs.py`
   (a stand-in 4 GiB pool, 4000 rounds of 2-9 MiB blocks and 16 KiB-1.9 MiB crumbs taken and given back:
   with packing the largest free run of the bottom GiB stays 958 MiB, without it 202 MiB).
3. **Free-run statistics** (`headless/performance.cpp`). `EDEN_SESSION_MEMORY` now ends with
   `free_runs=N free_usable=B free_crumbs=B`: the free memory in runs of 2 MiB or more, and the free
   memory in runs under 2 MiB. The next session says whether crumbs were the problem.
4. Everything in 0.61rc stays: JIT code cache blocks and wait, heap return with split pieces, staging
   and guest-fault waits, `EDEN_HEAP_SPACES`, music mute.

## Verification

Host checks on Linux: the crumb placement check above (both modes, ASan/UBSan), the CPU-heap page backend
and heap-by-pieces checks, the generated staging pool and allocator checks (`check-vram-reclaim`,
`check-staging-idle-trim`), the JIT allocator check. Native build, package and isolation checks are in
VALIDATION.json.

Not verified: that the crumb packing keeps the pool usable for the GPU on the console (the statistics
will show), that waiting for the pool is enough when a burst holds it (a refusal that outlasts the wait
still ends the session), and that no allocation relied on the placement of small blocks.
