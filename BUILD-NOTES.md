# DirkuLator 0.60rc

Native PS5 title PPSA99862, content version 00.005.060, development channel.

## Why

Every 0.58rc and 0.59rc session ended by running out of the 12,416 MiB shared pool, not by a leak.
From about five minutes in the guest held ~5.8 GiB, graphics ~2.7 GiB, the CPU heap 1.7 GiB (never
given back: it had grown while shaders compiled in the first minutes) and large CPU blocks ~0.8 GiB;
total free sat near 250 MiB for 15+ minutes. A loading burst (60-140 MiB of staging blocks allocated
and let go again within 100 ms) then found the pool empty:

- 0.58rc: a 36 MiB texture upload was refused three times within a millisecond with ~100 MiB free
  (largest free block 6 MiB), `VK_ERROR_OUT_OF_DEVICE_MEMORY`, GPU thread, 1929 s.
- 0.59rc: a 4 KiB guest write needed a 2 MiB block to promote a zero page, the pool had 31 MiB free
  in no usable piece, the 32 MiB reserve had been used 18 times, SIGSEGV "game memory exhausted",
  GPU thread, 1467 s.

## Changes

1. **Waiting out a transient peak (GPU).** `MakeOrReclaim` (`headless/staging_buffers.h`) keeps asking
   for a refused staging buffer every 50 ms for up to 1.5 s after the third refusal, running the
   idle-buffer release and texture reclaim again every 250 ms. Before, the third refusal ended the app.
2. **Waiting out a transient peak (guest).** `HandleGuestWriteFault` (`src/guest_memory_service.inc`):
   when no block can be had, the slot stays as it was, the thread sleeps 5 ms and the instruction
   repeats, for up to 3 s from the first refusal; only then does the failure count and the process
   end. The wait holds no lock. `fault_patience_ms` is 3000.
3. **Idle heap spaces go back to the pool** (`headless/heap_arenas.inc`, `src/memory_pages.cpp`).
   A heap space in which nothing is alive (a block of nearly the whole space can be made only then)
   keeps that block and returns the memory behind it; the allocator's own records at both ends stay.
   When the heap has to grow it takes a retired space's memory back first, then commits new pieces.
   Only done while the pool's largest free block is under 2 GiB, checked every 5 s.
   `heap-return-off.txt` (`EDEN_NX2_HEAP_RETURN_OFF`) disables it. Threads' kept small blocks count as
   alive, so a space with one is not idle: how much this returns in practice is what the log shows.
4. **Heap statistics.** `EDEN_HEAP_SPACES spaces=.. retired=.. newly_retired=.. returned_mib=..
   committed_mib=.. in=pieces:largest_mib ...` every 30 s and whenever a space is retired: for each
   heap space its pieces and the largest block it can make (probed), `R` for a retired one.
5. **Music removed.** A voice that loops a wave buffer for ever (`loop_count < 0`) is decoded as
   before, so voice state and timing do not change, but its output is silenced
   (`src/audio_core/renderer/command/data_source/decode.cpp`, layer `99zzzzzzb-music-off.diff`).
   Ambient loops (wind, water) go with it; voices, sound effects and the launcher's UI sounds stay.
   `EDEN_MUSIC_MUTED` logs the first and every doubling of silenced updates.
   `/data/eden-nx2/music-on.txt` plays the music again. The classification (infinite loop = music)
   is a rule of thumb, not proven against the game's audio engine.

## Verification

Host checks (Linux): the heap-by-pieces harness (8 threads, checked and ThreadSanitizer) with the
new retire/take-back cycle over a stand-in that makes a retired stretch unreadable; the staging
retry with patience (succeeds after 8 refusals; gives up after its patience); the guest write fault
with patience (retries while the pool is empty, fails when it is spent) and the existing OOM report
checks. Native compilation and package checks are in VALIDATION.json.

No hardware gameplay has been run on 0.60rc. That the changes stop the 0.58rc/0.59rc crashes, how
much heap memory is returned, and that no wanted sound is lost are all unconfirmed until a session
on the console shows them. A refusal that outlasts the waits still ends the session as before.
