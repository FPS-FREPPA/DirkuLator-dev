// SPDX-License-Identifier: GPL-3.0-or-later
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <sys/mman.h>

#include "common/sparse_large_vector.h"
#include "../src/fragmented_commit.h"

namespace Common {
void* ReserveMemoryRange(std::size_t size) noexcept;
bool CommitMemoryRange(void* address, std::size_t size) noexcept;
} // namespace Common

#ifdef PS5_NATIVE
extern "C" {
int eden_direct_low(std::size_t, std::size_t, int, std::int64_t*);
int sceKernelMapDirectMemory(void**, std::size_t, int, int, std::int64_t, std::size_t);
int sceKernelReserveVirtualRange(void**, std::size_t, int, std::size_t);
int sceKernelReleaseDirectMemory(std::int64_t, std::size_t);
int sceKernelDebugOutText(int, const char*);
}

namespace {
constexpr std::size_t HeapPage = 0x4000;
constexpr std::size_t HeapLargePage = 0x200000;
constexpr std::size_t HeapFragmentedBlocks = 64;
constexpr std::size_t HeapFragmentsPerBlock = 1024;

struct HeapBacking {
    std::atomic<std::uintptr_t> address{0};
    std::size_t requested{};
    std::size_t span{};
    std::size_t count{};
    std::array<Common::FragmentedCommit::Piece, HeapFragmentsPerBlock> pieces{};
};
std::array<HeapBacking, HeapFragmentedBlocks> heap_backings;

struct HeapBackingOps {
    bool Allocate(std::size_t size, std::int64_t& physical) noexcept {
        const auto alignment = size % HeapLargePage == 0 ? HeapLargePage : HeapPage;
        return eden_direct_low(size, alignment, 12, &physical) == 0;
    }
    bool Map(const Common::FragmentedCommit::Piece& piece) noexcept {
        void* at = reinterpret_cast<void*>(piece.address);
        const auto alignment = (piece.address % HeapLargePage == 0 &&
                                piece.physical % HeapLargePage == 0 &&
                                piece.size % HeapLargePage == 0) ? HeapLargePage : HeapPage;
        const auto result = sceKernelMapDirectMemory(&at, piece.size, PROT_READ | PROT_WRITE,
                                                      MAP_FIXED, piece.physical, alignment);
        if (result == 0 && at != reinterpret_cast<void*>(piece.address)) std::abort();
        return result == 0;
    }
    void ReleaseUnmapped(const Common::FragmentedCommit::Piece& piece) noexcept {
        if (sceKernelReleaseDirectMemory(piece.physical, piece.size) != 0) std::abort();
    }
    void UnmapRelease(const Common::FragmentedCommit::Piece& piece) noexcept {
        if (munmap(reinterpret_cast<void*>(piece.address), piece.size) != 0) std::abort();
        ReleaseUnmapped(piece);
    }
    void Rollback(const Common::FragmentedCommit::Piece& piece) noexcept {
        void* const address = reinterpret_cast<void*>(piece.address);
        if (munmap(address, piece.size) != 0) std::abort();
        void* again = address;
        if (sceKernelReserveVirtualRange(&again, piece.size, MAP_FIXED, HeapPage) != 0 || again != address)
            std::abort();
        ReleaseUnmapped(piece);
    }
};

// This path serves only the C heap. General page allocations retain their
// contiguous physical backing contract, which JIT aliases depend on.
void* AllocateFragmentedHeap(std::size_t size) noexcept {
    if (size == 0 || size > (std::numeric_limits<std::size_t>::max)() - (HeapLargePage - 1))
        return nullptr;
    const auto span = (size + HeapLargePage - 1) / HeapLargePage * HeapLargePage;
    for (auto& backing : heap_backings) {
        std::uintptr_t expected = 0;
        if (!backing.address.compare_exchange_strong(expected, 1, std::memory_order_acq_rel)) continue;
        void* const base = Common::ReserveMemoryRange(span);
        if (base == nullptr) {
            backing.address.store(0, std::memory_order_release);
            return nullptr;
        }
        HeapBackingOps ops;
        std::size_t count = 0;
        if (!Common::FragmentedCommit::Commit(reinterpret_cast<std::uintptr_t>(base), span, HeapPage,
                                                backing.pieces, ops, count)) {
            if (munmap(base, span) != 0) std::abort();
            backing.address.store(0, std::memory_order_release);
            return nullptr;
        }
        std::memset(base, 0, span);
        backing.requested = size;
        backing.span = span;
        backing.count = count;
        backing.address.store(reinterpret_cast<std::uintptr_t>(base), std::memory_order_release);
        char line[144];
        std::snprintf(line, sizeof(line), "EDEN_HEAP_FRAGMENTED bytes=%zu held=%zu blocks=%zu va=%p\n",
                      size, span, count, base);
        sceKernelDebugOutText(0, line);
        return base;
    }
    return nullptr;
}

bool FreeFragmentedHeap(void* base, std::size_t size) noexcept {
    for (auto& backing : heap_backings) {
        if (backing.address.load(std::memory_order_acquire) != reinterpret_cast<std::uintptr_t>(base)) continue;
        if (backing.requested != size) std::abort();
        backing.address.store(1, std::memory_order_release);
        HeapBackingOps ops;
        for (std::size_t index = backing.count; index != 0; --index)
            ops.UnmapRelease(backing.pieces[index - 1]);
        backing.address.store(0, std::memory_order_release);
        return true;
    }
    return false;
}
} // namespace
#endif

extern "C" void* eden_heap_pages(std::size_t size) {
    void* const base = Common::AllocateMemoryPages(size);
#ifdef PS5_NATIVE
    if (base == nullptr) {
        if (void* const fragmented = AllocateFragmentedHeap(size)) return fragmented;
        errno = ENOMEM;
    }
#endif
    return base;
}
extern "C" void eden_heap_pages_free(void* base, std::size_t size) {
#ifdef PS5_NATIVE
    if (base != nullptr && FreeFragmentedHeap(base, size)) return;
#endif
    Common::FreeMemoryPages(base, size);
}
extern "C" void* eden_heap_reserve(std::size_t size) {
    return Common::ReserveMemoryRange(size);
}
extern "C" int eden_heap_commit(void* address, std::size_t size) {
    return Common::CommitMemoryRange(address, size) ? 0 : -1;
}
