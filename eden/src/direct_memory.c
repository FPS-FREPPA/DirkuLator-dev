// SPDX-License-Identifier: GPL-3.0-or-later
// Where the app's long-lived memory goes in the pool the CPU shares with the GPU.
//
// The system gives out direct memory from the bottom of the pool: the lowest room that fits.
// A game's own memory (4 GiB) and its graphics come and go with each session, while two kinds
// of blocks stay for good: the pieces the heap grows by (headless/heap_arenas.inc) and the
// stacks of threads (the Payload SDK takes 2 MiB of direct memory for each, and keeps freed
// ones for the next threads). Taken from the bottom like the rest, those landed between a
// running game's graphics memory, and when the game ended they were left spread over the
// middle of the pool. The next game's graphics get the largest free stretch, which was then
// much smaller than what was free in total, and smaller again after every game.
//
// So blocks that stay are taken from the top of the pool downwards, and everything a session
// takes and gives back is left to the system as before. The link wraps the calls
// (tools/link-headless-native.sh): the heap asks for the top itself (eden_direct_high), and
// the other blocks that stay are known by their size: a thread's stack is 2 MiB, and so is the
// one block the graphics driver keeps for good (its zero block, taken in the middle of a game
// and then left where it was). The driver's command ring and marker page are known by who
// asks. The app's own 2 MiB blocks, the slots of the guest page tables, go back when a game
// ends: they ask below the wrap (eden_direct_low) and stay where the system puts them.
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

int __real_sceKernelAllocateDirectMemory(int64_t, int64_t, size_t, size_t, int, int64_t *);
int __real_sceKernelReleaseDirectMemory(int64_t, size_t);
int64_t sceKernelGetDirectMemorySize(void);

#define EDEN_DIRECT_STEP ((int64_t)2 << 20)       /* blocks at the top are placed in 2 MiB steps */
#define EDEN_DIRECT_SMALL ((size_t)2 << 20)       /* a thread's stack; the driver's zero block */

/* ---- 041: who takes the pool, event by event ----
 * In 040 the pool lost ~723 MiB between the last 1 s sample (256.3 s) and the crash (257 s), of
 * which new guest backing explained ~371 MiB. Every direct allocation and release of the app goes
 * through here (the link wraps the calls; the heap and the guest's slots call the real function
 * from eden_direct_high/low below), so each is recorded in a ring that never allocates: sequence,
 * time, kind, start, size, the path it took, its caller and the app's running total. The memory
 * report prints new events every second (eden_direct_events_print) and the crash report the last
 * ones (eden_direct_events_format, no C library formatting). What the pool has lost beyond the
 * app's running total belongs to callers outside the link (system libraries). */
#include <stdio.h>
#include <time.h>
extern const char __eden_text_start[] __attribute__((weak));
extern const char __eden_text_end[] __attribute__((weak));
enum { EDEN_DMEM_ALLOC = 1, EDEN_DMEM_RELEASE = 2, EDEN_DMEM_FAILED = 3 };
enum { EDEN_DMEM_WRAP = 0, EDEN_DMEM_HIGH = 1, EDEN_DMEM_LOW = 2 }; /* the path: link wrap, heap/kept, guest */
#define EDEN_DMEM_EVENTS 4096u
struct eden_dmem_event {
  _Atomic uint64_t seq; /* 0: never written; set last */
  int64_t ns;
  int64_t start;
  uint64_t size;
  uint64_t caller;      /* offset from __eden_text_start; 0 unknown */
  uint32_t deep[3];     /* 043: further code addresses on the stack (who asked the caller), offsets */
  int64_t held;         /* the app's direct memory after the event */
  uint8_t kind, path;
};
static struct eden_dmem_event eden_dmem_events[EDEN_DMEM_EVENTS];
static _Atomic uint64_t eden_dmem_next;
static _Atomic int64_t eden_dmem_held;
static uint64_t eden_dmem_printed; /* the memory report's thread only */

static void eden_dmem_record(int kind, int path, int64_t start, size_t size, const void *caller) {
  int64_t held = atomic_load_explicit(&eden_dmem_held, memory_order_relaxed);
  if (kind == EDEN_DMEM_ALLOC)
    held = atomic_fetch_add_explicit(&eden_dmem_held, (int64_t)size, memory_order_relaxed) + (int64_t)size;
  else if (kind == EDEN_DMEM_RELEASE)
    held = atomic_fetch_sub_explicit(&eden_dmem_held, (int64_t)size, memory_order_relaxed) - (int64_t)size;
  if (size < ((size_t)1 << 20) && kind != EDEN_DMEM_FAILED)
    return; /* counted, not listed */
  const uint64_t seq = atomic_fetch_add_explicit(&eden_dmem_next, 1, memory_order_relaxed) + 1;
  struct eden_dmem_event *event = &eden_dmem_events[seq % EDEN_DMEM_EVENTS];
  atomic_store_explicit(&event->seq, 0, memory_order_relaxed);
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);
  event->ns = (int64_t)now.tv_sec * 1000000000ll + now.tv_nsec;
  event->start = start;
  event->size = size;
  const uintptr_t text = (uintptr_t)__eden_text_start, at = (uintptr_t)caller;
  event->caller = __eden_text_start != NULL && at >= text ? at - text : 0;
  event->held = held;
  /* 043: the driver's allocations all come from one function; a few more code addresses above this
   * frame tell which of the app's paths asked (texture upload, staging, VMA block...). */
  event->deep[0] = event->deep[1] = event->deep[2] = 0;
  if (__eden_text_start != NULL && __eden_text_end != NULL) {
    const uintptr_t end = (uintptr_t)__eden_text_end;
    const uintptr_t *stack = (const uintptr_t *)__builtin_frame_address(0);
    for (int w = 0, found = 0; w < 96 && found < 3; ++w)
      if (stack[w] >= text && stack[w] < end && stack[w] - text != event->caller)
        event->deep[found++] = (uint32_t)(stack[w] - text);
  }
  event->kind = (uint8_t)kind;
  event->path = (uint8_t)path;
  atomic_store_explicit(&event->seq, seq, memory_order_release);
}

int64_t eden_direct_events_held(void) { return atomic_load_explicit(&eden_dmem_held, memory_order_relaxed); }

static const char *const eden_dmem_kinds[] = {"?", "alloc", "release", "FAILED"};
static const char *const eden_dmem_paths[] = {"wrap", "high", "low"};

/* New events since the last call, one EDEN_DMEM line each, on stderr (the memory report's thread). */
void eden_direct_events_print(void) {
  const uint64_t last = atomic_load_explicit(&eden_dmem_next, memory_order_acquire);
  uint64_t seq = eden_dmem_printed + 1;
  if (last >= EDEN_DMEM_EVENTS && seq + EDEN_DMEM_EVENTS <= last) {
    fprintf(stderr, "EDEN_DMEM lost=%llu (ring overrun)\n", (unsigned long long)(last - EDEN_DMEM_EVENTS + 1 - seq));
    seq = last - EDEN_DMEM_EVENTS + 1;
  }
  for (; seq <= last; ++seq) {
    const struct eden_dmem_event *event = &eden_dmem_events[seq % EDEN_DMEM_EVENTS];
    if (atomic_load_explicit(&event->seq, memory_order_acquire) != seq)
      continue;
    fprintf(stderr,
            "EDEN_DMEM seq=%llu t_ms=%lld %s path=%s start=%#llx size_kib=%llu caller=%#llx held_mib=%lld "
            "deep=%#x,%#x,%#x\n",
            (unsigned long long)seq, (long long)(event->ns / 1000000), eden_dmem_kinds[event->kind & 3],
            eden_dmem_paths[event->path % 3], (unsigned long long)event->start,
            (unsigned long long)(event->size >> 10), (unsigned long long)event->caller,
            (long long)(event->held >> 20), event->deep[0], event->deep[1], event->deep[2]);
  }
  eden_dmem_printed = last;
}

/* The last `count` events as text, without the C library (the crash report's handler). */
static size_t eden_dmem_put(char *out, size_t at, size_t size, const char *text) {
  while (*text && at + 1 < size) out[at++] = *text++;
  return at;
}
static size_t eden_dmem_number(char *out, size_t at, size_t size, uint64_t value, int hex) {
  char digits[24];
  int n = 0;
  do {
    const unsigned digit = (unsigned)(value % (hex ? 16 : 10));
    digits[n++] = (char)(digit < 10 ? '0' + digit : 'a' + digit - 10);
    value /= hex ? 16 : 10;
  } while (value != 0 && n < 24);
  if (hex) at = eden_dmem_put(out, at, size, "0x");
  while (n > 0 && at + 1 < size) out[at++] = digits[--n];
  return at;
}
size_t eden_direct_events_format(char *out, size_t size, unsigned count) {
  if (size == 0) return 0;
  size_t at = 0;
  const uint64_t last = atomic_load_explicit(&eden_dmem_next, memory_order_acquire);
  const uint64_t first = last > count ? last - count + 1 : 1;
  at = eden_dmem_put(out, at, size, "direct memory events (last ");
  at = eden_dmem_number(out, at, size, last - first + 1, 0);
  at = eden_dmem_put(out, at, size, "; the app holds ");
  at = eden_dmem_number(out, at, size, (uint64_t)(eden_direct_events_held() >> 20), 0);
  at = eden_dmem_put(out, at, size, " MiB):\n");
  for (uint64_t seq = first; seq <= last && at + 160 < size; ++seq) {
    const struct eden_dmem_event *event = &eden_dmem_events[seq % EDEN_DMEM_EVENTS];
    if (atomic_load_explicit(&event->seq, memory_order_acquire) != seq) continue;
    at = eden_dmem_put(out, at, size, "  #");
    at = eden_dmem_number(out, at, size, seq, 0);
    at = eden_dmem_put(out, at, size, " t_ms=");
    at = eden_dmem_number(out, at, size, (uint64_t)(event->ns / 1000000), 0);
    at = eden_dmem_put(out, at, size, " ");
    at = eden_dmem_put(out, at, size, eden_dmem_kinds[event->kind & 3]);
    at = eden_dmem_put(out, at, size, " ");
    at = eden_dmem_put(out, at, size, eden_dmem_paths[event->path % 3]);
    at = eden_dmem_put(out, at, size, " size_kib=");
    at = eden_dmem_number(out, at, size, event->size >> 10, 0);
    at = eden_dmem_put(out, at, size, " caller=");
    at = eden_dmem_number(out, at, size, event->caller, 1);
    at = eden_dmem_put(out, at, size, " held_mib=");
    at = eden_dmem_number(out, at, size, (uint64_t)(event->held > 0 ? event->held >> 20 : 0), 0);
    at = eden_dmem_put(out, at, size, "\n");
  }
  out[at] = '\0';
  return at;
}

static atomic_flag eden_direct_lock = ATOMIC_FLAG_INIT;
static int64_t eden_direct_floor;                 /* the lowest block taken at the top; 0: none yet */
static int64_t eden_direct_holes[1024];           /* 2 MiB blocks given back above the floor */
static unsigned eden_direct_hole_count;

static void eden_direct_acquire(void) {
  while (atomic_flag_test_and_set_explicit(&eden_direct_lock, memory_order_acquire)) {}
}
static void eden_direct_release(void) { atomic_flag_clear_explicit(&eden_direct_lock, memory_order_release); }

/* Memory from as high in the pool as there is room; from anywhere when the top has none. */
static int eden_direct_high_raw(size_t size, size_t alignment, int type, int64_t *start) {
  const int64_t total = sceKernelGetDirectMemorySize();
  const int64_t bytes = (int64_t)size;
  if (bytes <= 0 || total <= 0) return __real_sceKernelAllocateDirectMemory(0, total, size, alignment, type, start);
  eden_direct_acquire();
  /* A block given back earlier left a hole of its size. */
  while (size == EDEN_DIRECT_SMALL && eden_direct_hole_count != 0) {
    const int64_t hole = eden_direct_holes[--eden_direct_hole_count];
    if (__real_sceKernelAllocateDirectMemory(hole, hole + bytes, size, alignment, type, start) == 0) {
      eden_direct_release();
      return 0;
    }
  }
  /* Below what is at the top already; past what something else has put there, for a while. */
  int64_t next = eden_direct_floor != 0 ? eden_direct_floor : total;
  for (unsigned tries = 0; tries < 512 && next >= bytes; ++tries) {
    const int64_t at = (next - bytes) / EDEN_DIRECT_STEP * EDEN_DIRECT_STEP;
    next = at;
    if (__real_sceKernelAllocateDirectMemory(at, at + bytes, size, alignment, type, start) == 0) {
      eden_direct_floor = at;
      eden_direct_release();
      return 0;
    }
  }
  eden_direct_release();
  return __real_sceKernelAllocateDirectMemory(0, total, size, alignment, type, start);
}

int eden_direct_high(size_t size, size_t alignment, int type, int64_t *start) {
  const int result = eden_direct_high_raw(size, alignment, type, start);
  eden_dmem_record(result == 0 ? EDEN_DMEM_ALLOC : EDEN_DMEM_FAILED, EDEN_DMEM_HIGH, result == 0 && start ? *start : -1,
                   size, __builtin_return_address(0));
  return result;
}

/* 0.62rc: blocks of under 2 MiB ("crumbs": the CPU heap's 16 KiB pieces, the guest's compact blocks)
 * are packed into the top EDEN_DIRECT_CRUMBS of the pool. The system gives memory out from the bottom,
 * the lowest room that fits, so crumbs taken and given back among a session's graphics memory left
 * the pool as many free runs under 2 MiB, which the GPU cannot use (it takes memory in pieces of 2 MiB
 * at least): 0.61rc ended on a 10 MiB buffer with 102 MiB free and a largest free block of 3 MiB.
 * The first room at or above the start of that region is taken, so the crumbs lie together there
 * (with the blocks that stay, which are taken from the very top), and where it has none the block
 * is placed as before. EDEN_NX2_CRUMBS_OFF disables it. */
#define EDEN_DIRECT_CRUMBS ((int64_t)3 << 30)
static int eden_direct_crumb(size_t size, size_t alignment, int type, int64_t *start) {
  static int disabled = -1;
  if (disabled < 0) disabled = getenv("EDEN_NX2_CRUMBS_OFF") != NULL;
  const int64_t total = sceKernelGetDirectMemorySize();
  if (disabled || size >= EDEN_DIRECT_SMALL || total <= EDEN_DIRECT_CRUMBS) return -1;
  const int64_t from = (total - EDEN_DIRECT_CRUMBS) / EDEN_DIRECT_STEP * EDEN_DIRECT_STEP;
  return __real_sceKernelAllocateDirectMemory(from, total, size, alignment, type, start);
}

/* As the system places it: for what a session takes and gives back. */
int eden_direct_low(size_t size, size_t alignment, int type, int64_t *start) {
  int result = eden_direct_crumb(size, alignment, type, start);
  if (result != 0)
    result = __real_sceKernelAllocateDirectMemory(0, sceKernelGetDirectMemorySize(), size, alignment, type, start);
  eden_dmem_record(result == 0 ? EDEN_DMEM_ALLOC : EDEN_DMEM_FAILED, EDEN_DMEM_LOW, result == 0 && start ? *start : -1,
                   size, __builtin_return_address(0));
  return result;
}

/* The Vulkan driver makes its command ring (16 MiB) and, right after it, the ring's marker page
 * once, with the first device, and keeps them until the app ends. Taken from the bottom like a
 * session's memory they landed above the first game's (the ring at 4.6 GiB), and every later
 * game found the pool's largest free stretch cut from 10.3 GiB to 5.7. They are known by who
 * asks (the driver's allocator; no such symbol in a build without that driver), by their sizes
 * and by being the first of those sizes in that order. */
extern void eden_radv_private_radv_ps5_memory_alloc(void) __attribute__((weak));
#define EDEN_DIRECT_RING ((size_t)16 << 20)
#define EDEN_DIRECT_PAGE ((size_t)16 << 10)
static atomic_int eden_direct_driver_kept; /* 0: neither yet; 1: the ring; 2: the marker page too */

static int eden_direct_driver_keeps(size_t size, const void *caller) {
  const char *const allocator = (const char *)(uintptr_t)&eden_radv_private_radv_ps5_memory_alloc;
  if (!allocator || (const char *)caller < allocator || (const char *)caller >= allocator + 2048) return 0;
  int kept = atomic_load_explicit(&eden_direct_driver_kept, memory_order_relaxed);
  if (kept == 0 && size == EDEN_DIRECT_RING)
    return atomic_compare_exchange_strong(&eden_direct_driver_kept, &kept, 1);
  if (kept == 1 && size == EDEN_DIRECT_PAGE)
    return atomic_compare_exchange_strong(&eden_direct_driver_kept, &kept, 2);
  return 0;
}

int __wrap_sceKernelAllocateDirectMemory(int64_t from, int64_t to, size_t size, size_t alignment, int type,
                                         int64_t *start) {
  /* A thread's stack or the driver's zero block, asked for anywhere in the pool; and the
   * driver's command ring and marker page. */
  const void *caller = __builtin_return_address(0);
  int result;
  int path = EDEN_DMEM_WRAP;
  if (from == 0 && start && to >= sceKernelGetDirectMemorySize() &&
      (size == EDEN_DIRECT_SMALL || eden_direct_driver_keeps(size, caller))) {
    result = eden_direct_high_raw(size, alignment, type, start);
    path = EDEN_DMEM_HIGH;
  } else {
    result = -1;
    if (from == 0 && start && to >= sceKernelGetDirectMemorySize() && size < EDEN_DIRECT_SMALL) {
      result = eden_direct_crumb(size, alignment, type, start);
      if (result == 0) path = EDEN_DMEM_HIGH;
    }
    if (result != 0)
      result = __real_sceKernelAllocateDirectMemory(from, to, size, alignment, type, start);
  }
  eden_dmem_record(result == 0 ? EDEN_DMEM_ALLOC : EDEN_DMEM_FAILED, path, result == 0 && start ? *start : -1, size,
                   caller);
  return result;
}

int __wrap_sceKernelReleaseDirectMemory(int64_t start, size_t size) {
  const int result = __real_sceKernelReleaseDirectMemory(start, size);
  if (result != 0) return result;
  eden_dmem_record(EDEN_DMEM_RELEASE, EDEN_DMEM_WRAP, start, size, __builtin_return_address(0));
  eden_direct_acquire();
  if (size == EDEN_DIRECT_SMALL && eden_direct_floor != 0 && start >= eden_direct_floor &&
      eden_direct_hole_count < sizeof(eden_direct_holes) / sizeof(eden_direct_holes[0]))
    eden_direct_holes[eden_direct_hole_count++] = start;
  eden_direct_release();
  return result;
}
