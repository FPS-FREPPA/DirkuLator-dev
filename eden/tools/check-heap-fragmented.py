#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the production C-heap page backend against fragmented, file-backed physical memory."""
from pathlib import Path
import argparse
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', type=Path)
parser.add_argument('--tsan', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
production = root / 'headless/heap_pages.cpp'
memory = (root / 'src/memory_pages.cpp').read_text()
a = memory.index('std::array<FragmentedCommit::Piece, 8192> heap_commit_scratch;')
b = memory.index('\n} // namespace', a)
ops = memory[a:b]
a = memory.index('bool CommitMemoryRange(void* address, std::size_t size) noexcept {')
b = memory.index('\n// ---- A range that fills:', a)
commit = memory[a:b]
fixture = r'''
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <mutex>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <thread>
#include <unistd.h>
#include <vector>
constexpr std::size_t Page = 0x4000, Large = 0x200000, Pool = 256ULL << 20;
std::mutex physical_lock;
std::array<bool, Pool / Page> used;
std::size_t held = 0, virtual_bytes = 0, hole = 1ULL << 20, available = Pool;
unsigned map_calls = 0, map_fail = 0;
bool reserve_fail = false, direct_ok = false, refuse_partial_release = false;
int backing_fd;
std::atomic<unsigned> direct_frees{0};
int TestMunmap(void* at, std::size_t size) {
    std::lock_guard lock(physical_lock);
    assert(size <= virtual_bytes);
    virtual_bytes -= size;
    return static_cast<int>(syscall(SYS_munmap, at, size));
}
extern "C" int eden_direct_low(std::size_t size, std::size_t alignment, int type, std::int64_t* physical) {
    std::lock_guard lock(physical_lock);
    assert(type == 12 && size % Page == 0 && alignment >= Page);
    if (size > hole || size > available - held) return -1;
    for (std::size_t at = 0; at + size <= Pool; at += alignment) {
        const auto first = at / Page, count = size / Page;
        bool free = true;
        for (std::size_t i = 0; i < count; ++i) if (used[first + i]) { free = false; break; }
        if (!free) continue;
        for (std::size_t i = 0; i < count; ++i) used[first + i] = true;
        held += size;
        *physical = static_cast<std::int64_t>(at);
        return 0;
    }
    return -1;
}
extern "C" int eden_direct_high(std::size_t size, std::size_t alignment, int type, std::int64_t* physical) {
    return eden_direct_low(size, alignment, type, physical);
}
extern "C" int sceKernelReleaseDirectMemory(std::int64_t physical, std::size_t size) {
    std::lock_guard lock(physical_lock);
    if (refuse_partial_release) return -1;
    assert(physical >= 0 && std::size_t(physical) + size <= Pool && size <= held);
    for (std::size_t i = std::size_t(physical) / Page; i < (std::size_t(physical) + size) / Page; ++i) {
        assert(used[i]); used[i] = false;
    }
    held -= size;
    return 0;
}
extern "C" int sceKernelMapDirectMemory(void** at, std::size_t size, int prot, int flags,
                                         std::int64_t physical, std::size_t alignment) {
    std::lock_guard lock(physical_lock);
    assert(flags == MAP_FIXED && size % Page == 0 && alignment >= Page);
    assert(std::uintptr_t(*at) % alignment == 0 && std::size_t(physical) % alignment == 0);
    if (++map_calls == map_fail) return -1;
    void* mapped = mmap(*at, size, prot, MAP_SHARED | MAP_FIXED, backing_fd, physical);
    if (mapped == MAP_FAILED) return -1;
    assert(mapped == *at);
    return 0;
}
extern "C" int sceKernelReserveVirtualRange(void** at, std::size_t size, int flags, std::size_t alignment) {
    std::lock_guard lock(physical_lock);
    assert(flags == MAP_FIXED && std::uintptr_t(*at) % alignment == 0);
    void* mapped = mmap(*at, size, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (mapped == MAP_FAILED) return -1;
    assert(mapped == *at); virtual_bytes += size; return 0;
}
extern "C" int sceKernelDebugOutText(int, const char*) { return 0; }
#include "fragmented_commit.h"
#define munmap TestMunmap
#include "PRODUCTION"
#undef munmap
namespace Common {
void* AllocateMemoryPages(std::size_t size) noexcept {
    if (!direct_ok) { errno = ENOMEM; return nullptr; }
    void* at = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    return at == MAP_FAILED ? nullptr : at;
}
void FreeMemoryPages(void* at, std::size_t size) noexcept {
    if (!at) return;
    ++direct_frees;
    assert(munmap(at, size) == 0);
}
void* ReserveMemoryRange(std::size_t size) noexcept {
    if (reserve_fail) return nullptr;
    void* raw = mmap(nullptr, size + Large, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (raw == MAP_FAILED) return nullptr;
    const auto begin = std::uintptr_t(raw), aligned = (begin + Large - 1) / Large * Large;
    if (aligned > begin) assert(munmap(raw, aligned - begin) == 0);
    const auto tail = begin + size + Large - aligned - size;
    if (tail) assert(munmap(reinterpret_cast<void*>(aligned + size), tail) == 0);
    { std::lock_guard lock(physical_lock); virtual_bytes += size; }
    return reinterpret_cast<void*>(aligned);
}
namespace {
namespace FragmentedCommit = Common::FragmentedCommit;
constexpr std::size_t LargePage = Large;
void Note(const char*) noexcept {}
#define munmap TestMunmap
OPS
#undef munmap
}
#define munmap TestMunmap
COMMIT
#undef munmap
}
void clean() { assert(held == 0 && virtual_bytes == 0); assert(std::none_of(used.begin(), used.end(), [](bool x){return x;})); }
int main() {
    backing_fd = static_cast<int>(syscall(SYS_memfd_create, "fragmented-heap-test", 0));
    assert(backing_fd >= 0 && ftruncate(backing_fd, Pool) == 0);
    // Recorded crash: a 64 MiB request cannot get a contiguous physical block.
    auto* p = static_cast<unsigned char*>(eden_heap_pages(64ULL << 20));
    assert(p != nullptr && held == (64ULL << 20));
    for (std::size_t i = 0; i < (64ULL << 20); ++i) assert(p[i] == 0);
    std::memset(p, 0xa5, 64ULL << 20);
    for (std::size_t i = 0; i < (64ULL << 20); i += Page) assert(p[i] == 0xa5);
    eden_heap_pages_free(p, 64ULL << 20); clean();
    p = static_cast<unsigned char*>(eden_heap_pages((13ULL << 20) + 1));
    assert(p && held == (14ULL << 20));
    for (std::size_t i = 0; i < (13ULL << 20) + 1; ++i) assert(p[i] == 0);
    eden_heap_pages_free(p, (13ULL << 20) + 1); clean();
    map_fail = map_calls + 3;
    assert(!eden_heap_pages(8ULL << 20)); clean(); map_fail = 0;
    available = 5ULL << 20;
    assert(!eden_heap_pages(8ULL << 20)); clean(); available = Pool;
    reserve_fail = true; assert(!eden_heap_pages(8ULL << 20)); clean(); reserve_fail = false;
    hole = Page;
    // The bounded ledger refuses an allocation it cannot represent and rolls back.
    assert(!eden_heap_pages(64ULL << 20)); clean(); hole = 1ULL << 20;
    direct_ok = true;
    p = static_cast<unsigned char*>(eden_heap_pages(8ULL << 20));
    assert(p && held == 0); eden_heap_pages_free(p, 8ULL << 20); assert(direct_frees == 1); direct_ok = false;
    assert(!eden_heap_pages(0) && !eden_heap_pages((std::numeric_limits<std::size_t>::max)())); clean();
    // Distinct allocations retain ownership and data under concurrent allocation/free.
    std::array<std::thread, 8> threads;
    for (unsigned thread = 0; thread < threads.size(); ++thread) threads[thread] = std::thread([thread] {
        for (unsigned n = 0; n < 8; ++n) {
            auto* data = static_cast<unsigned char*>(eden_heap_pages((2ULL << 20) + 7));
            assert(data && std::uintptr_t(data) % Large == 0);
            std::memset(data, int(thread + 1), (2ULL << 20) + 7);
            std::this_thread::yield();
            for (std::size_t at = 0; at < (2ULL << 20) + 7; at += Page) assert(data[at] == thread + 1);
            eden_heap_pages_free(data, (2ULL << 20) + 7);
        }
    });
    for (auto& thread : threads) thread.join(); clean();
    std::array<void*, 64> blocks;
    for (auto& block : blocks) { block = eden_heap_pages(Large); assert(block); }
    assert(!eden_heap_pages(Large));
    for (auto* block : blocks) eden_heap_pages_free(block, Large); clean();
    // Permanent growth must also use sub-2-MiB holes, with the real production ops.
    hole = 1ULL << 20;
    void* range = Common::ReserveMemoryRange(32ULL << 20);
    assert(Common::CommitMemoryRange(range, 32ULL << 20));
    assert(held == (32ULL << 20));
    // Production growth intentionally retains successful commits for process lifetime.
    assert(TestMunmap(range, 32ULL << 20) == 0);
    used.fill(false); held = 0; clean();
    range = Common::ReserveMemoryRange(32ULL << 20); available = 5ULL << 20;
    assert(!Common::CommitMemoryRange(range, 32ULL << 20));
    assert(held == 0 && virtual_bytes == (32ULL << 20));
    assert(TestMunmap(range, 32ULL << 20) == 0); clean();
    // 0.61rc: memory the heap no longer uses goes back to the pool even from the middle of a piece
    // committed as one block (0.60rc gave back nothing: no piece lay wholly inside the range).
    {
        hole = Pool; available = Pool; used.fill(false); held = 0; Common::heap_ledger_count = 0; // earlier checks gave their memory back by hand
        const std::size_t MiB = 1ULL << 20;
        auto* base = static_cast<unsigned char*>(Common::ReserveMemoryRange(32 * MiB));
        assert(base && Common::CommitMemoryRange(base, 32 * MiB) && held == 32 * MiB);
        std::memset(base, 0x5a, 2 * MiB);
        std::memset(base + 30 * MiB, 0x6b, 2 * MiB);
        Common::HeapHole holes[4];
        unsigned n = Common::DecommitHeapRange(std::uintptr_t(base) + 2 * MiB, std::uintptr_t(base) + 30 * MiB, holes, 4);
        assert(n == 1 && holes[0].address == std::uintptr_t(base) + 2 * MiB && holes[0].size == 28 * MiB);
        assert(held == 4 * MiB && virtual_bytes >= 28 * MiB);
        for (std::size_t i = 0; i < 2 * MiB; i += Page) assert(base[i] == 0x5a && base[30 * MiB + i] == 0x6b);
        assert(Common::RecommitHeapHole(holes[0]) && held == 32 * MiB);
        for (std::size_t i = 2 * MiB; i < 30 * MiB; i += Page) assert(base[i] == 0);
        for (std::size_t i = 0; i < 2 * MiB; i += Page) assert(base[i] == 0x5a && base[30 * MiB + i] == 0x6b);
        // The three pieces it became are given back as one stretch, and taken again.
        n = Common::DecommitHeapRange(std::uintptr_t(base), std::uintptr_t(base) + 32 * MiB, holes, 4);
        assert(n == 1 && holes[0].address == std::uintptr_t(base) && holes[0].size == 32 * MiB && held == 0);
        assert(Common::RecommitHeapHole(holes[0]) && held == 32 * MiB);
        // Outside the range, and a range of nothing, give nothing back.
        assert(Common::DecommitHeapRange(std::uintptr_t(base) + 64 * MiB, std::uintptr_t(base) + 96 * MiB, holes, 4) == 0);
        assert(Common::DecommitHeapRange(std::uintptr_t(base) + 4 * MiB, std::uintptr_t(base) + 4 * MiB, holes, 4) == 0);
        // The console refuses to give back a part of a piece: nothing changes, and it is not asked again.
        std::memset(base, 0x5a, 2 * MiB);   // the whole range was taken again, zeroed
        refuse_partial_release = true;
        assert(Common::DecommitHeapRange(std::uintptr_t(base) + 2 * MiB, std::uintptr_t(base) + 30 * MiB, holes, 4) == 0);
        refuse_partial_release = false;
        assert(held == 32 * MiB);
        for (std::size_t i = 0; i < 2 * MiB; i += Page) assert(base[i] == 0x5a);
        base[3 * MiB] = 1; assert(base[3 * MiB] == 1);   // still mapped and writable
        assert(Common::DecommitHeapRange(std::uintptr_t(base) + 2 * MiB, std::uintptr_t(base) + 30 * MiB, holes, 4) == 0);
        assert(TestMunmap(base, 32 * MiB) == 0);
        used.fill(false); held = 0; clean();
    }
    close(backing_fd);
    std::puts("PASS production CPU heap: 64 MiB in 1 MiB holes, zeroing, alignment, release/reuse, failure rollback, ledger bounds, eight threads, permanent growth, partial give-back of a piece");
}
'''.replace('OPS', ops).replace('COMMIT', commit)
with tempfile.TemporaryDirectory(prefix='eden-heap-fragmented-') as work:
    work = Path(work)
    (work / 'common').mkdir()
    (work / 'common/sparse_large_vector.h').write_text('#pragma once\n#include <cstddef>\nnamespace Common { void* AllocateMemoryPages(std::size_t) noexcept; void FreeMemoryPages(void*, std::size_t) noexcept; }\n')
    for source, label, expected_failure in [(production, 'current', False)] + ([(args.baseline, 'baseline', True)] if args.baseline else []):
        text = fixture.replace('PRODUCTION', str(source))
        (work / 'check.cpp').write_text(text)
        binary = work / label
        subprocess.run(['clang++-18', '-std=c++20', '-DPS5_NATIVE', '-O1', '-g', '-pthread',
                        '-fsanitize=thread' if args.tsan else '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I' + str(work),
                        '-I' + str(root / 'src'), str(work / 'check.cpp'), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        if expected_failure:
            assert result.returncode != 0 and 'p != nullptr' in result.stderr, result.stderr
            print('PASS preceding backend reproduces the 64 MiB allocation failure')
        else:
            print(result.stdout, end='')
            if result.returncode: raise RuntimeError(result.stderr)
