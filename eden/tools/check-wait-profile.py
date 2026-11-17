#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host check of src/wait_profile.c (0.65rc): the wrappers record real waits and change nothing else.

Compiles the production file with the link's --wrap options and a test program that blocks threads in each
wrapped primitive for known times: a contended mutex (held 120 ms), a condition variable timed out after
150 ms, nanosleep 60 ms, usleep 40 ms; an uncontended lock must record nothing. Checks the counts, that
each total is within a tolerance of the real time, that threads get separate indices, that the report
clears the counters, and that the wrapped calls still return the values the real calls do.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
production = root / 'src/wait_profile.c'

fixture = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

size_t eden_wait_profile_format(char *, size_t, unsigned);

static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t cond_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t never = PTHREAD_COND_INITIALIZER;

static void *contender(void *arg) {
  (void)arg;
  pthread_mutex_lock(&gate);   /* blocks until the main thread lets go */
  pthread_mutex_unlock(&gate);
  return NULL;
}

static void *sleeper(void *arg) {
  (void)arg;
  struct timespec ts = {0, 60 * 1000 * 1000};
  assert(nanosleep(&ts, NULL) == 0);
  usleep(40 * 1000);
  pthread_mutex_lock(&cond_lock);
  struct timespec until;
  clock_gettime(CLOCK_REALTIME, &until);
  until.tv_nsec += 150 * 1000 * 1000;
  if (until.tv_nsec >= 1000000000L) { until.tv_sec += 1; until.tv_nsec -= 1000000000L; }
  int r = pthread_cond_timedwait(&never, &cond_lock, &until);
  assert(r == ETIMEDOUT);       /* the wrapper returns the real result */
  pthread_mutex_unlock(&cond_lock);
  return NULL;
}

/* sum of total_ms for a primitive name in one report line */
static long total_ms_of(const char *line, const char *name) {
  long sum = 0;
  const char *p = line;
  while ((p = strstr(p, name)) != NULL) {
    const char *t = strstr(p, "total_ms=");
    if (!t) break;
    sum += atol(t + 9);
    p = t;
  }
  return sum;
}
static long count_of(const char *line, const char *name) {
  const char *p = strstr(line, name);
  if (!p) return 0;
  const char *c = strstr(p, "count=");
  return c ? atol(c + 6) : 0;
}

int main(void) {
  char line[4096];
  /* an uncontended lock records nothing */
  pthread_mutex_t free_mutex = PTHREAD_MUTEX_INITIALIZER;
  assert(pthread_mutex_lock(&free_mutex) == 0);
  pthread_mutex_unlock(&free_mutex);
  assert(eden_wait_profile_format(line, sizeof line, 14) == 0);

  pthread_mutex_lock(&gate);
  pthread_t a, b;
  pthread_create(&a, NULL, contender, NULL);
  pthread_create(&b, NULL, sleeper, NULL);
  usleep(120 * 1000);            /* the contender waits ~120 ms; this wait is recorded as usleep too */
  pthread_mutex_unlock(&gate);
  pthread_join(a, NULL);
  pthread_join(b, NULL);

  size_t n = eden_wait_profile_format(line, sizeof line, 14);
  assert(n > 0);
  puts(line);
  long mutex_ms = total_ms_of(line, "mutex_lock");
  long cond_ms = total_ms_of(line, "cond_timedwait");
  long nano_ms = total_ms_of(line, "nanosleep");
  long usleep_ms = total_ms_of(line, "usleep");
  printf("mutex %ld ms, cond %ld ms, nanosleep %ld ms, usleep %ld ms\n", mutex_ms, cond_ms, nano_ms, usleep_ms);
  assert(mutex_ms >= 100 && mutex_ms <= 400);
  assert(cond_ms >= 140 && cond_ms <= 400);
  assert(nano_ms >= 55 && nano_ms <= 200);
  assert(usleep_ms >= 150 && usleep_ms <= 500);   /* 40 ms (sleeper) + ~120 ms (main) */
  assert(count_of(line, "mutex_lock") == 1);
  /* three threads waited: main (usleep), the contender (mutex), the sleeper (nanosleep, usleep, cond) */
  assert(strstr(line, "threads=3") != NULL);
  /* 0.67rc: every thread is reported with an address and a name ("-" when the system gives none) */
  assert(strstr(line, ",check)") != NULL || strstr(line, ",-)") != NULL);
  /* the report cleared the counters */
  assert(eden_wait_profile_format(line, sizeof line, 14) == 0);
  puts("PASS wait profile");
  return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='eden-wait-profile-') as work:
    work = Path(work)
    (work / 'check.c').write_text(fixture)
    wraps = [f'-Wl,--wrap={n}' for n in ('pthread_cond_wait', 'pthread_cond_timedwait', 'pthread_mutex_lock', 'nanosleep', 'usleep')]
    subprocess.run(['clang-18', '-std=gnu11', '-O1', '-g', '-Wall', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-pthread', str(work / 'check.c'), str(production), *wraps, '-o', str(work / 'check')], check=True)
    result = subprocess.run([str(work / 'check')], capture_output=True, text=True, timeout=60)
    print(result.stdout, end='')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
