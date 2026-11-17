// SPDX-License-Identifier: GPL-3.0-or-later
// 0.65rc wait profiler: where do threads block, and for how long?
//
// The 0.64rc console run showed frames stuck for 300-440 ms in the GPU thread's draw recording with the
// GPU 4 % busy, while every wait counter the performance monitor has (pipeline, lock, fence, guest sync)
// read 0 ms. This file wraps the blocking primitives a thread can sit in (the link wraps the calls, as for
// direct_memory.c) and records, per (thread, primitive, caller), the number of waits and their time.
// The report thread prints the busiest sites every 10 s as EDEN_WAIT_PROFILE; callers are offsets from
// __eden_text_start, symbolised offline against the exact ELF. Nothing here changes what a call does:
// each wrapper calls the real function and only reads the clock around a call that really blocked
// (a mutex is tried first, so an uncontended lock costs one extra trylock).
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

extern const char __eden_text_start[] __attribute__((weak));
/* The thread name API differs between systems (glibc and newer FreeBSD: pthread_getname_np, older FreeBSD:
 * pthread_get_name_np); use whichever the link provides. */
int pthread_getname_np(pthread_t, char *, size_t) __attribute__((weak));
void pthread_get_name_np(pthread_t, char *, size_t) __attribute__((weak));

int __real_pthread_cond_wait(pthread_cond_t *, pthread_mutex_t *);
int __real_pthread_cond_timedwait(pthread_cond_t *, pthread_mutex_t *, const struct timespec *);
int __real_pthread_mutex_lock(pthread_mutex_t *);
int __real_nanosleep(const struct timespec *, struct timespec *);
int __real_usleep(unsigned int);

enum { EDEN_WAIT_COND = 0, EDEN_WAIT_CONDT = 1, EDEN_WAIT_MUTEX = 2, EDEN_WAIT_NANOSLEEP = 3, EDEN_WAIT_USLEEP = 4 };
static const char *const eden_wait_names[] = {"cond_wait", "cond_timedwait", "mutex_lock", "nanosleep", "usleep"};

#define EDEN_WAIT_SLOTS 1024u
#define EDEN_WAIT_THREADS 128u

struct eden_wait_slot {
  _Atomic uint64_t key; /* 0: unused; thread index (16 bits) | primitive (8 bits) | caller offset (40 bits) | 1 << 63 */
  _Atomic uint64_t count;
  _Atomic uint64_t total_ns;
  _Atomic uint64_t max_ns;
};
static struct eden_wait_slot eden_wait_slots[EDEN_WAIT_SLOTS];
static _Atomic uint64_t eden_wait_thread_ids[EDEN_WAIT_THREADS]; /* pthread_t values, in order of first wait */
static char eden_wait_thread_names[EDEN_WAIT_THREADS][24];       /* 0.67rc: the thread's name when it first waited */
static _Atomic unsigned eden_wait_thread_count;
static _Atomic uint64_t eden_wait_dropped;
static __thread int eden_wait_thread_index = -1;

static uint64_t eden_wait_now(void) {
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);
  return (uint64_t)now.tv_sec * 1000000000ull + (uint64_t)now.tv_nsec;
}

static unsigned eden_wait_thread(void) {
  if (eden_wait_thread_index >= 0) return (unsigned)eden_wait_thread_index;
  const uint64_t id = (uint64_t)(uintptr_t)pthread_self();
  unsigned at = atomic_fetch_add_explicit(&eden_wait_thread_count, 1, memory_order_relaxed);
  if (at >= EDEN_WAIT_THREADS) {
    atomic_store_explicit(&eden_wait_thread_count, EDEN_WAIT_THREADS, memory_order_relaxed);
    at = EDEN_WAIT_THREADS - 1;
  } else {
    atomic_store_explicit(&eden_wait_thread_ids[at], id, memory_order_relaxed);
    char *name = eden_wait_thread_names[at];
    name[0] = '\0';
    if (pthread_getname_np) {
      pthread_getname_np(pthread_self(), name, sizeof eden_wait_thread_names[at]);
    } else if (pthread_get_name_np) {
      pthread_get_name_np(pthread_self(), name, sizeof eden_wait_thread_names[at]);
    }
    name[sizeof eden_wait_thread_names[at] - 1] = '\0';
    for (char *p = name; *p; ++p) {
      if (*p == ' ' || *p == ',' || *p == ';' || *p == '(' || *p == ')') *p = '_'; /* keep the report one parseable line */
    }
  }
  eden_wait_thread_index = (int)at;
  return at;
}

static void eden_wait_record(unsigned primitive, const void *caller, uint64_t ns) {
  const uintptr_t text = (uintptr_t)__eden_text_start, at = (uintptr_t)caller;
  const uint64_t offset = __eden_text_start != NULL && at >= text ? (uint64_t)(at - text) & 0xffffffffffull : 0;
  const uint64_t key = ((uint64_t)eden_wait_thread() << 48) | ((uint64_t)primitive << 40) | offset | (1ull << 63);
  const unsigned first = (unsigned)((key * 0x9e3779b97f4a7c15ull) >> 54) % EDEN_WAIT_SLOTS;
  for (unsigned probe = 0; probe < 8; ++probe) {
    struct eden_wait_slot *slot = &eden_wait_slots[(first + probe) % EDEN_WAIT_SLOTS];
    uint64_t have = atomic_load_explicit(&slot->key, memory_order_relaxed);
    if (have == 0) {
      uint64_t expected = 0;
      if (!atomic_compare_exchange_strong_explicit(&slot->key, &expected, key, memory_order_relaxed, memory_order_relaxed))
        have = expected;
      else
        have = key;
    }
    if (have == key) {
      atomic_fetch_add_explicit(&slot->count, 1, memory_order_relaxed);
      atomic_fetch_add_explicit(&slot->total_ns, ns, memory_order_relaxed);
      uint64_t seen = atomic_load_explicit(&slot->max_ns, memory_order_relaxed);
      while (ns > seen && !atomic_compare_exchange_weak_explicit(&slot->max_ns, &seen, ns, memory_order_relaxed, memory_order_relaxed)) {}
      return;
    }
  }
  atomic_fetch_add_explicit(&eden_wait_dropped, 1, memory_order_relaxed);
}

int __wrap_pthread_cond_wait(pthread_cond_t *cond, pthread_mutex_t *mutex) {
  const uint64_t begin = eden_wait_now();
  const int result = __real_pthread_cond_wait(cond, mutex);
  eden_wait_record(EDEN_WAIT_COND, __builtin_return_address(0), eden_wait_now() - begin);
  return result;
}

int __wrap_pthread_cond_timedwait(pthread_cond_t *cond, pthread_mutex_t *mutex, const struct timespec *until) {
  const uint64_t begin = eden_wait_now();
  const int result = __real_pthread_cond_timedwait(cond, mutex, until);
  eden_wait_record(EDEN_WAIT_CONDT, __builtin_return_address(0), eden_wait_now() - begin);
  return result;
}

int __wrap_pthread_mutex_lock(pthread_mutex_t *mutex) {
  const int tried = pthread_mutex_trylock(mutex);
  if (tried != EBUSY) return tried; /* locked at once, or an error the real call would report the same way */
  const uint64_t begin = eden_wait_now();
  const int result = __real_pthread_mutex_lock(mutex);
  eden_wait_record(EDEN_WAIT_MUTEX, __builtin_return_address(0), eden_wait_now() - begin);
  return result;
}

int __wrap_nanosleep(const struct timespec *request, struct timespec *remain) {
  const uint64_t begin = eden_wait_now();
  const int result = __real_nanosleep(request, remain);
  eden_wait_record(EDEN_WAIT_NANOSLEEP, __builtin_return_address(0), eden_wait_now() - begin);
  return result;
}

int __wrap_usleep(unsigned int microseconds) {
  const uint64_t begin = eden_wait_now();
  const int result = __real_usleep(microseconds);
  eden_wait_record(EDEN_WAIT_USLEEP, __builtin_return_address(0), eden_wait_now() - begin);
  return result;
}

/* The busiest sites since the last call, one line: EDEN_WAIT_PROFILE ... Reads and clears the counters.
 * Returns the number of bytes written (0: nothing waited). */
size_t eden_wait_profile_format(char *out, size_t size, unsigned top) {
  if (size == 0) return 0;
  struct row {
    uint64_t key, count, total, max;
  };
  static struct row rows[EDEN_WAIT_SLOTS]; /* the report thread only */
  unsigned n = 0;
  for (unsigned i = 0; i < EDEN_WAIT_SLOTS; ++i) {
    struct eden_wait_slot *slot = &eden_wait_slots[i];
    const uint64_t count = atomic_exchange_explicit(&slot->count, 0, memory_order_relaxed);
    if (count == 0) continue;
    rows[n].key = atomic_load_explicit(&slot->key, memory_order_relaxed);
    rows[n].count = count;
    rows[n].total = atomic_exchange_explicit(&slot->total_ns, 0, memory_order_relaxed);
    rows[n].max = atomic_exchange_explicit(&slot->max_ns, 0, memory_order_relaxed);
    ++n;
  }
  for (unsigned i = 1; i < n; ++i) { /* insertion sort, longest total first */
    const struct row v = rows[i];
    unsigned j = i;
    while (j > 0 && rows[j - 1].total < v.total) {
      rows[j] = rows[j - 1];
      --j;
    }
    rows[j] = v;
  }
  int at = snprintf(out, size, "EDEN_WAIT_PROFILE sites=%u threads=%u dropped=%llu top:", n,
                    atomic_load_explicit(&eden_wait_thread_count, memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&eden_wait_dropped, memory_order_relaxed));
  if (n == 0) return 0;
  for (unsigned i = 0; i < n && i < top && at > 0 && (size_t)at + 200 < size; ++i) {
    const unsigned thread = (unsigned)((rows[i].key >> 48) & 0x7fff);
    const unsigned primitive = (unsigned)((rows[i].key >> 40) & 0xff);
    const uint64_t id = thread < EDEN_WAIT_THREADS ? atomic_load_explicit(&eden_wait_thread_ids[thread], memory_order_relaxed) : 0;
    at += snprintf(out + at, size - (size_t)at,
                   " t%u(%#llx,%s) %s caller=%#llx count=%llu total_ms=%llu max_ms=%llu;", thread, (unsigned long long)id,
                   thread < EDEN_WAIT_THREADS && eden_wait_thread_names[thread][0] ? eden_wait_thread_names[thread] : "-",
                   primitive < 5 ? eden_wait_names[primitive] : "?",
                   (unsigned long long)(rows[i].key & 0xffffffffffull), (unsigned long long)rows[i].count,
                   (unsigned long long)(rows[i].total / 1000000ull), (unsigned long long)(rows[i].max / 1000000ull));
  }
  return at > 0 ? (size_t)at : 0;
}

/* Called every second by the memory report thread; prints every 10th call. */
void eden_wait_profile_print(void) {
  static unsigned calls;
  if (++calls % 10u != 0u) return;
  char line[4096];
  if (eden_wait_profile_format(line, sizeof line, 14) != 0) fprintf(stderr, "%s\n", line);
}
