#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host check of the pool placement in src/direct_memory.c (0.62rc: blocks under 2 MiB are packed).

Compiles the production file against a stand-in for the console's direct-memory calls: a 4 GiB pool
that gives out the lowest room that fits (as the system does), as a list of free runs. Checks that
blocks under 2 MiB lie in the top 3 GiB together while blocks of 2 MiB or more are left to the
system (the bottom), that a crumb falls back to the whole pool when its region is full, that the
EDEN_NX2_CRUMBS_OFF switch restores the old placement, and that the GPU's view of the pool (the
largest free run) stays large after many crumbs are taken and given back among 2 MiB blocks.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
production = root / 'src/direct_memory.c'

fixture = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <vector>
#include <time.h>

namespace {
constexpr int64_t MiB = int64_t{1} << 20, GiB = int64_t{1} << 30;
constexpr int64_t Total = 4 * GiB;
std::map<int64_t, int64_t> free_runs{{0, Total}};   // start -> size

int64_t largest_free(int64_t below = Total) {   // the largest free run inside [0, below)
    int64_t best = 0;
    for (const auto& run : free_runs) {
        if (run.first >= below) break;
        best = std::max(best, std::min(run.first + run.second, below) - run.first);
    }
    return best;
}
}  // namespace

extern "C" {
int64_t sceKernelGetDirectMemorySize(void) { return Total; }
int __real_sceKernelAllocateDirectMemory(int64_t from, int64_t to, size_t size, size_t alignment, int, int64_t* start) {
    assert(alignment != 0 && (alignment & (alignment - 1)) == 0);
    for (auto it = free_runs.begin(); it != free_runs.end(); ++it) {
        const int64_t run_start = it->first, run_end = it->first + it->second;
        int64_t at = std::max(run_start, from);
        at = (at + int64_t(alignment) - 1) / int64_t(alignment) * int64_t(alignment);
        if (at + int64_t(size) > std::min(run_end, to)) continue;
        // take [at, at + size) out of the run
        const int64_t before = at - run_start, after = run_end - (at + int64_t(size));
        free_runs.erase(it);
        if (before > 0) free_runs[run_start] = before;
        if (after > 0) free_runs[at + int64_t(size)] = after;
        *start = at;
        return 0;
    }
    return -1;
}
int __real_sceKernelReleaseDirectMemory(int64_t start, size_t size) {
    int64_t at = start, bytes = int64_t(size);
    auto next = free_runs.lower_bound(at);
    if (next != free_runs.end() && at + bytes == next->first) {  // joins the run after it
        bytes += next->second;
        next = free_runs.erase(next);
    }
    if (next != free_runs.begin()) {
        auto before = std::prev(next);
        if (before->first + before->second == at) {            // joins the run before it
            at = before->first;
            bytes += before->second;
            free_runs.erase(before);
        }
    }
    free_runs[at] = bytes;
    return 0;
}
int eden_direct_low(size_t, size_t, int, int64_t*);
int eden_direct_high(size_t, size_t, int, int64_t*);
int __wrap_sceKernelAllocateDirectMemory(int64_t, int64_t, size_t, size_t, int, int64_t*);
int __wrap_sceKernelReleaseDirectMemory(int64_t, size_t);
}

#include "PRODUCTION"

namespace {
constexpr int64_t CrumbFrom = Total - 3 * GiB;   // the top 3 GiB (EDEN_DIRECT_CRUMBS)
int64_t take_low(size_t size, size_t alignment) {
    int64_t at = -1;
    const int result = eden_direct_low(size, alignment, 12, &at);
    if (result != 0) std::fprintf(stderr, "eden_direct_low(%zu, %zu) refused (%d); largest free %lld MiB\n", size, alignment,
                                  result, static_cast<long long>(largest_free() / MiB));
    assert(result == 0);
    return at;
}
}  // namespace

int main(int argc, char** argv) {
    const bool off = argc > 1 && std::strcmp(argv[1], "off") == 0;
    if (off) setenv("EDEN_NX2_CRUMBS_OFF", "1", 1);

    // A 2 MiB block (the guest's slot) and larger are left to the system: the lowest room.
    const int64_t slot = take_low(2 * MiB, 2 * MiB);
    assert(slot == 0);
    const int64_t big = take_low(64 * MiB, 2 * MiB);
    assert(big == 2 * MiB);

    // A crumb (the guest's compact block, a CPU heap piece of 16 KiB) lies in the top 3 GiB.
    const int64_t crumb = take_low(16 * 1024, 16 * 1024);
    if (off) {
        assert(crumb == 66 * MiB);                        // the lowest room, as before
    } else {
        assert(crumb == CrumbFrom);                       // the first room of the region
        const int64_t second = take_low(2000 * 1024, 16 * 1024);   // under 2 MiB: still a crumb
        assert(second >= CrumbFrom && second < CrumbFrom + 4 * MiB);
        __real_sceKernelReleaseDirectMemory(second, 2000 * 1024);
    }
    __real_sceKernelReleaseDirectMemory(crumb, 16 * 1024);

    // The wrapped call (what the driver and the system libraries ask) packs a crumb too, and a
    // thread's 2 MiB stack still goes to the very top, below nothing the crumbs took.
    int64_t at = -1;
    assert(__wrap_sceKernelAllocateDirectMemory(0, Total, 64 * 1024, 64 * 1024, 12, &at) == 0);
    assert(off ? at == 66 * MiB : at >= CrumbFrom);
    __real_sceKernelReleaseDirectMemory(at, 64 * 1024);
    int64_t stack = -1;
    assert(__wrap_sceKernelAllocateDirectMemory(0, Total, 2 * MiB, 2 * MiB, 12, &stack) == 0);
    assert(stack == Total - 2 * MiB);                     // eden_direct_high: the top of the pool

    // Many crumbs taken and given back among blocks of 2 MiB and more (a session's churn): with the
    // packing the bottom of the pool stays one run for the GPU; without it the crumbs are scattered.
    const int64_t before = largest_free(CrumbFrom);
    std::vector<std::pair<int64_t, size_t>> crumbs, blocks;
    unsigned seed = 12345;
    for (int round = 0; round < 4000; ++round) {
        seed = seed * 1664525u + 1013904223u;
        const unsigned action = (seed >> 20) % 20;
        if (blocks.size() < 16 || action < 8) {                                  // a block of 2-9 MiB
            const size_t size = (2 + (seed >> 8) % 8) * MiB;
            blocks.push_back({take_low(size, 2 * MiB), size});
        } else if (action < 14) {                                                // a crumb
            const size_t size = (1 + (seed >> 8) % 120) * 16 * 1024;
            crumbs.push_back({take_low(size, 16 * 1024), size});
        } else if (action < 17 && !crumbs.empty()) {                             // a crumb goes back
            const size_t index = (seed >> 4) % crumbs.size();
            __real_sceKernelReleaseDirectMemory(crumbs[index].first, crumbs[index].second);
            crumbs.erase(crumbs.begin() + index);
        }
        if (blocks.size() > 40 || (action >= 17 && blocks.size() > 16)) {        // a block goes back
            const size_t index = (seed >> 6) % blocks.size();
            __real_sceKernelReleaseDirectMemory(blocks[index].first, blocks[index].second);
            blocks.erase(blocks.begin() + index);
        }
    }
    for (const auto& block : blocks) __real_sceKernelReleaseDirectMemory(block.first, block.second);
    int64_t crumb_bytes_low = 0, crumb_bytes_high = 0;
    for (const auto& crumb_block : crumbs) (crumb_block.first >= CrumbFrom ? crumb_bytes_high : crumb_bytes_low) += int64_t(crumb_block.second);
    const int64_t after = largest_free(CrumbFrom);
    std::printf("%s: largest free run of the bottom GiB %lld MiB before, %lld MiB after the churn (crumbs low %lld KiB, high %lld KiB)\n",
                off ? "packing off" : "packing on", static_cast<long long>(before / MiB),
                static_cast<long long>(after / MiB), static_cast<long long>(crumb_bytes_low / 1024),
                static_cast<long long>(crumb_bytes_high / 1024));
    if (off) {
        assert(crumb_bytes_low > 0 && after < before);                           // scattered from the bottom
    } else {
        assert(crumb_bytes_low == 0);                                            // none among the blocks
        assert(after == before);                                                 // the bottom is as free as it was
    }

    // The crumb region full: a crumb is placed as before, in the whole pool.
    for (const auto& crumb_block : crumbs) __real_sceKernelReleaseDirectMemory(crumb_block.first, crumb_block.second);
    std::vector<int64_t> filler;
    int64_t more = -1;
    while (__real_sceKernelAllocateDirectMemory(CrumbFrom, Total, 2 * MiB, 2 * MiB, 12, &more) == 0)
        filler.push_back(more);                                                  // fill the region with 2 MiB blocks
    const int64_t fallback = take_low(16 * 1024, 16 * 1024);
    assert(fallback >= 0 && fallback < CrumbFrom);                               // below the region: the old placement
    std::puts(off ? "PASS crumb placement with packing off" : "PASS crumb placement: packed into the top 3 GiB, fallback when full");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='eden-direct-crumbs-') as work:
    work = Path(work)
    source = work / 'check.cpp'
    binary = work / 'check'
    # The production file is C: it is compiled alone, with the console's real calls turned into the
    # fixture's stand-ins (the link wraps them the same way), and the fixture, C++, is linked with it.
    subprocess.run(['clang-18', '-std=gnu11', '-O1', '-g', '-c', str(production), '-o', str(work / 'direct_memory.o')],
                   check=True)
    source.write_text(fixture.replace('#include "PRODUCTION"\n', ''))
    subprocess.run(['clang++-18', '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(source), str(work / 'direct_memory.o'), '-Wl,--defsym=sceKernelAllocateDirectMemory=__real_sceKernelAllocateDirectMemory',
                    '-o', str(binary)], check=True)
    for mode in ('on', 'off'):
        result = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=120)
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(mode + ': ' + result.stderr)
