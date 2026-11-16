# DirkuLator 0.61rc

Native PS5 title PPSA99862, content version 00.005.061, development channel.

## What 0.60rc showed on the console

One session (New Game, intro cutscenes, control of Link, 12-15 FPS in the house) ended 1030 s after
start, 11 s after Link opened the door of his house. The crash report is not a memory-pool failure of
the kind 0.58rc/0.59rc ended on:

    JIT code cache: the console has no memory for its next part
    SIGABRT on CPUCore_4, pool: 86 MiB free, largest free block 4-9 MiB

The JIT took each 16 MiB step of its code cache as one contiguous direct-memory block. With the pool
cut into pieces of 2-9 MiB (86-94 MiB free in total) no block that large existed and the game's first
translation after the door aborted the app. 0.60rc's retries covered staging buffers and guest
pages, not this path. In the same session:

- `EDEN_HEAP_SPACES` worked and found the waste: of 54 heap spaces (1728 MiB, never given back),
  15 or more were wholly idle at the end (the largest block a space could make was 31 MiB of its
  32 MiB), roughly 400-500 MiB. 0.60rc's heap return retired none: it gave back only pieces lying
  wholly inside the idle stretch, and the heap commits a 32 MiB piece as one block, so no piece did.
- The music mute ran (`EDEN_MUSIC_MUTED` logged); whether what was muted is the game's music was
  not checked by ear.
- The rendering faults of 0.58rc/0.59rc remained (white wash-out, shard slabs and hard rectangles in
  the cutscenes and the house). Nothing in 0.60rc or 0.61rc changes shaders or drawing.

## Changes

1. **JIT code cache in smaller blocks** (`src/memory_pages.cpp`). A step is asked for as one 16 MiB
   block as before; when the pool has none, as 8, 4 and 2 MiB blocks, each its own piece mapped
   into both views. When not even 2 MiB can be had the JIT waits for the pool, 5 ms at a time, up
   to 3 s (a loading burst's blocks come back within 100 ms), before the existing abort.
2. **Heap return splits pieces** (`DecommitHeapRange`). The part of a committed piece inside the
   idle stretch is released and the piece becomes what is left on each side; `RecommitHeapHole` takes
   the memory again when the heap grows. If the console refuses to release part of an allocation,
   the memory is mapped back as it was and the path stops for the session (nothing is lost).
3. Everything in 0.60rc is kept: staging retry (1.5 s), guest write retry (3 s), `EDEN_HEAP_SPACES`,
   `heap-return-off.txt`, music mute (`music-on.txt`).

## Verification

Host checks on Linux: the CPU-heap page backend with a stand-in for the console's physical memory
(a piece committed as one block, a stretch from its middle released, the remains intact, the stretch
taken again zeroed, three pieces given back as one stretch, a refusal leaving everything as it was)
under ASan/UBSan and ThreadSanitizer; the heap-by-pieces harness with give-back; the staging retry
and guest write retry checks. Native build, package and isolation checks are in VALIDATION.json.

Not verified: that the console accepts the release of part of an allocation (the path falls back if
not), that the JIT's smaller blocks run translated code correctly on the console, and that these
changes keep a session alive past the 1030 s of 0.60rc. No 0.61rc gameplay had run when this was written.
