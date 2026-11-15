#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the patched collector's real pressure block against rapid pool changes."""
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]) / 'src/video_core/texture_cache/texture_cache.h'
body = source.read_text()
start = body.index('    if (eden_direct_memory_free) {', body.index('void TextureCache<P>::TickFrame()'))
opening = body.index('{', start)
depth = 1
end = opening + 1
while depth:
    depth += (body[end] == '{') - (body[end] == '}')
    end += 1
block = body[start:end]
program = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstddef>
using u64 = std::uint64_t;
using u32 = std::uint32_t;
constexpr u64 operator""_MiB(unsigned long long n) { return n << 20; }
constexpr u64 operator""_GiB(unsigned long long n) { return n << 30; }
std::int64_t next_free = 3_GiB;
unsigned queries = 0;
bool ps5_pool_tight = false;
void eden_direct_memory_free(std::int64_t* free, std::size_t* largest) {
    ++queries; *free = next_free; *largest = 8_MiB;
}
u64 Step() {
    u64 total_used_memory = 5_GiB;
    const u64 expected_memory = 4_GiB, critical_memory = 6_GiB;
BLOCK
    return total_used_memory;
}
int main() {
    assert(Step() < 4_GiB); // Fragmentation alone must not force eviction.
    next_free = 1792_MiB;
    for (int n = 0; n < 8; ++n) Step();
    unsigned before = queries;
    next_free = 1280_MiB;
    assert(Step() >= 6_GiB + 512_MiB);
    assert(queries == before + 1); // Rapid guest growth cannot wait eight frames.
    assert(!ps5_pool_tight);
    next_free = 900_MiB;
    assert(Step() >= 7_GiB && ps5_pool_tight);
    next_free = 173_MiB; // Recorded failed-allocation pool state.
    assert(Step() >= 7_GiB && ps5_pool_tight);
    next_free = 3_GiB;
    assert(Step() < 4_GiB && !ps5_pool_tight);
    next_free = -1;
    for (int n = 0; n < 8; ++n) Step();
    assert(Step() == 5_GiB); // Unknown query must preserve runtime accounting.
}
'''.replace('BLOCK', block)
with tempfile.TemporaryDirectory(prefix='dirkulator-pressure-') as directory:
    root = Path(directory)
    (root / 'check.cpp').write_text(program)
    subprocess.run(['c++', '-std=c++20', '-O1', '-fsanitize=address,undefined',
                    str(root / 'check.cpp'), '-o', str(root / 'check')], check=True)
    subprocess.run([str(root / 'check')], check=True)
print('PASS actual patched collector: rapid guest growth, tight recorded crash state, fragmentation-only pool, recovery, unknown queries')
