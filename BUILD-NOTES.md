# DirkuLator 0.63rc

Native PS5 title PPSA99862, content version 00.005.063, development channel.

## What 0.62rc showed on the console

The 101-minute follow-up run (`logs/luna-0.62rc-followup-20261117T010353Z`, to 03:45 Europe/Madrid) ended
with the title still in play and no crash report: 11.7 GiB held of 12.4 GiB, about 600 MiB free in runs of
2 MiB or more, 129 MiB in crumbs, a largest free run of 36 MiB, GPU memory about 2.8 GB, 2.8-12 FPS in
the last samples. 0.61rc ended on a 10 MiB buffer after 1174 s; 0.62rc was still running after 6000 s.
The crumb packing keeps the crumbs together (125-133 MiB, flat), but the usable runs are still short.

- **Who the refused requests are.** The 3410 `EDEN_DMEM ... FAILED` lines of the last telemetry window
  were symbolized against the 0.62rc image: the caller `0x2433dde` is `radv_ps5_memory_alloc`
  (`radv_ps5_platform.c:303`), the Vulkan driver's allocator. Its requests of 32-53 MiB are asked for in
  one piece first; when refused, `radv_ps5_memory_alloc_chunked` takes the same memory in smaller blocks
  (the refusal is followed by `alloc` events of 12-18 MiB from the same caller). Those refusals are the
  driver's normal first probe, not a lost allocation. 756 of them were the same 36 MiB request.
- **They cost evidence.** The ring that keeps the last 4096 allocations and releases was mostly full of
  those refusals, so the events before a crash showed little but probes.
- Rendering faults (white wash-out, shard slabs, hard fog rectangles) were all still there; the last photo
  shows Link in Kokiri Forest with the same wash-out. Nothing in 0.62rc or 0.63rc changes shaders or drawing.
- The input bridge and phone transfers failed in parts of the first 0.62rc run (`session_mismatch`, an
  `adb` device not found, a zero-byte pending photo); the follow-up run's bridge worked. Not changed here.

## Changes

1. **A repeated refusal is listed once** (`src/direct_memory.c`). A refused direct-memory request equal
   to the last one listed (same size, same caller) within a second is counted and not listed. Every
   refusal is still counted.
2. **Refusals in the memory report** (`headless/performance.cpp`). `EDEN_DMEM_HELD` ends with
   `refused=N refused_repeated=N`.
3. Host check: `tools/check-direct-memory-crumbs.py` also covers the counting (1000 repeated refusals
   count 1000 and list once; another size is listed).
4. Everything in 0.62rc stays: buffers wait for the pool, crumb packing, free-run statistics, JIT code
   cache blocks, heap return, music mute.

## Not verified

On the console. That the driver's chunked fallback always succeeds when its first probe is refused (the
events show it did throughout the follow-up run, with no `VK_ERROR_OUT_OF_DEVICE_MEMORY` report); that
the fragmentation (36 MiB largest run against 600 MiB free) does not end a longer session. No memory
limit was changed: no allocation owner that would justify one has been proven.
