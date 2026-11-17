# DirkuLator 0.64rc

Native PS5 title PPSA99862, content version 00.005.064, development channel. **Local candidate: not published
until it has been tested on a console.**

## What 0.63rc showed on the console

One 66-minute session (2026-11-17 03:20-04:26 UTC), the latest autosave (Kokiri Forest) loaded, Link walked,
swam, climbed a ladder and entered his house, driven through the input bridge (random walks, then directed
holds with both sticks). The title ended by an orderly close, not a crash; no crash report, no
`VK_ERROR_OUT_OF_DEVICE_MEMORY`, no `bad_alloc`, no guest abort. Four GPU captures were taken and archived
(114-115 files, 182-196 MiB each).

**Memory** (`EDEN_SESSION_MEMORY`, 3097 samples): 11.9 GiB of 12.4 GiB held at the end, `outside_app_mib=2`.
The largest free block shrank over the session: median per tenth of the run 56, 28, 28, 28, 21, 21, 21, 12, 21,
21 MiB (0.62rc follow-up: 36 MiB steady). Free memory in runs of 2 MiB or more fell from about 516 to 338 MiB;
crumbs stayed flat at about 100 MiB (0.62rc packing holds). Guest 5.8 GiB, CPU heap pieces 1.7 GiB, large CPU
blocks 0.77-0.86 GiB, GPU 2.6-3.3 GiB. The pool is full by design; what shrinks is the largest usable block.

**Refusals** (`EDEN_DMEM_HELD`): 1287 refused direct-memory requests, and the 0.63rc rule ("same as the last one
listed") suppressed only 78 of them, so 1209 were listed and crowded the 4096-event ring. They come from four
callers, symbolized against the 0.63rc image:

- `Common::AllocatePagesAt` (`memory_pages.cpp`, `wrap` path), 12-52 MiB: the CPU heap's first attempt at a block;
- `eden_heap_pages` (`heap_pages.cpp`, `low` path), 10-50 MiB: heap growth;
- `radv_ps5_memory_alloc` (`radv_ps5_platform.c:303`, `wrap` path), 6-48 MiB: the driver's one-piece probe before
  `radv_ps5_memory_alloc_chunked`;
- `FragmentedCommit::Commit` (`HeapCommitOps`, `high` path, 28 MiB): the heap's fallback into pieces (0.61rc design).

Each is a first attempt followed by a fallback; none ended the session. Which of them, if any, is a real loss is
not shown by 0.63rc, because the listing could not tell the callers apart.

**GPU and frame pacing**: five GPU stalls (longest 8.8 s, all recovered by the watchdog), eight memory-drop
events. Frame presentation averaged 6.4 FPS (median 4); 759 of 3742 seconds presented no frame, 482 seconds
reached 15 FPS and 40 reached 30 FPS. GPU captures freeze the game while they run (under a minute for three of the four captures, about three minutes
for one); they were requested on purpose.

**Rendering** (about 1000 phone photos of the TV, taken in bursts of three; observations in the run folder's
`OBSERVATIONS.md`), unchanged by 0.63rc:

- white haze that depends on the view: scenes with distant geometry are washed out, the same place with only near
  geometry (camera against the Deku Tree roots) is clean, and a frame with a hard vertical boundary shows half
  washed and half clean;
- white and blue faceted shard slabs on cliffs, trunks and in doorways (a doorway seen from the side is filled
  with shard polygons);
- black water in the village stream (ripple highlights only); the water-entry splash drawn as a tangled mesh;
- flat black unlit props (shelf mushrooms, leaf billboards) and Link as a near-black silhouette in shade or a
  see-through ghost inside haze, alternating within a second;
- Link's house interior over-exposed yellow-white, Link a flat golden silhouette; a black wedge and thin black line
  fixed at one screen position (a screen-space artifact, not world geometry); a blue-sky disc over the wall;
- a saturated blue patch on a rock, a translucent white slab over Link, a doubled Link-head icon behind the
  hearts, a blurry white-blue rounded fog blob in front of a doorway;
- camera collision (the camera inside a trunk or in Link's face); readable text, faces and bark where the
  pass is clean.

## Changes

1. **Refusals are kept per (size, caller)** (`src/direct_memory.c`). A table of 64 slots keyed by size and caller
   counts every refusal; a slot is listed in the event ring at most once a second. Alternating refusals from several
   callers (the 0.63rc case) are now suppressed too.
2. **The busiest refusals are printed** every 30 reports as `EDEN_DMEM_REFUSED total=N slots=N top: caller=0x...
   size_kib=N count=N; ...`, so the next session says which caller is refused, for how much and how often.
3. `EDEN_DMEM_HELD ... refused=N refused_repeated=N` (0.63rc) stays.
4. Host check: `tools/check-direct-memory-crumbs.py` also covers 1500 refusals alternating between three sizes from one
   call site (counted 1500, listed at most three times).
5. `tools/bridge/hold.py` (continuous movement for the input bridge) and the README are updated; no emulator behaviour
   in them.
6. Everything in 0.63rc and 0.62rc stays. No memory limit, shader or drawing change.

## Not verified

On the console. That the refusal table keeps the ring useful over a long session; that the three callers' fallbacks
always succeed (no session has ended on one yet); that the shrinking largest free block (56 to 12-21 MiB) does not
end a longer session. No allocation owner that would justify changing a memory limit has been proven.
