#!/usr/bin/env python3
"""Reproduce stale receipts, repair real driver layers, and test chunked backing."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
driver = root.parent/'mihawk-vulkan-review/.deps/work/radv-src'
relative = Path('src/amd/vulkan/winsys/ps5')


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening+1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]+'\n'


with tempfile.TemporaryDirectory(prefix='eden-radv-memory-') as temp:
    temp = Path(temp)
    tools = temp/'eden/tools'
    tools.mkdir(parents=True)
    script = tools/'patch-radv-ps5-memory.py'
    shutil.copyfile(root/'tools/patch-radv-ps5-memory.py', script)
    shutil.copytree(root/'tools/radv-patches', tools/'radv-patches')
    source = temp/'mihawk-vulkan-review/.deps/work/radv-src'
    (source/relative).mkdir(parents=True)
    for name in ['radv_ps5_platform.c', 'radv_ps5_platform.h', 'radv_ps5_bo.c']:
        shutil.copyfile(driver/relative/name, source/relative/name)
    # Construct an old unpatched source even when the real driver is already repaired.
    for patch in reversed(sorted((tools/'radv-patches').glob('*.diff'))):
        command = ['patch', '-d', source, '-p1', '-R', '-s', '-f', '-i', patch]
        if subprocess.run(list(map(str, command+['--dry-run'])), capture_output=True).returncode == 0:
            run(command)
    digest = subprocess.check_output(['python3', script, '--digest'], text=True).strip()
    stamp = source/'.eden-ps5-memory-applied'
    stamp.write_text(digest+'\n')
    receipt = temp/'mihawk-vulkan-review/.deps/native/radv-release/PROVENANCE.txt'
    receipt.parent.mkdir(parents=True)
    receipt.write_text('Preserve this old receipt\n')
    assert subprocess.run(['python3', script, '--check', stamp]).returncode != 0
    run(['python3', script])
    run(['python3', script, '--check', stamp])
    assert not receipt.exists() and list(receipt.parent.glob('PROVENANCE.before-memory-*.txt'))
    platform = source/relative/'radv_ps5_platform.c'
    repaired = platform.read_bytes()
    run(['python3', script])
    assert platform.read_bytes() == repaired

    actual = platform.read_text()
    production = '\n'.join(function(actual, signature) for signature in [
        'static bool\nradv_ps5_map_free_at(',
        'static void\nradv_ps5_chunks_release(',
        'static bool\nradv_ps5_memory_alloc_chunked(',
    ])
    prelude = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>
#include <assert.h>
#define MiB (1ULL<<20)
#define RADV_PS5_LARGE_BYTES (2*MiB)
#define RADV_PS5_MAX_CHUNKS 256u
#define RADV_PS5_REGION_BASE 0x4000000000ULL
#define RADV_PS5_GPU_ADDRESS_LIMIT (1ULL<<47)
#define RADV_PS5_DIRECT_TYPE 12
#define RADV_PS5_PROTECTION 0x33
#define MIN2(a,b) ((a)<(b)?(a):(b))
#define MAX2(a,b) ((a)>(b)?(a):(b))
struct radv_ps5_chunk { int64_t physical; uint64_t offset,bytes; };
struct radv_ps5_memory { void *cpu; uint64_t bytes; int64_t physical;
    struct radv_ps5_chunk *chunks; uint32_t chunk_count,granule,granules; };
static int radv_ps5_region;
static unsigned held,mapped,reserved,map_calls,refuse_map,wrong_map,misses;
static bool refuse_range;
static uint64_t align64(uint64_t n,uint64_t a){return (n+a-1)/a*a;}
static unsigned p_atomic_inc_return(unsigned *p){return ++*p;}
static uint32_t radv_ps5_granules_take(int *r,uint32_t n,uint32_t a){
    (void)r;(void)a;if(refuse_range)return UINT32_MAX;assert(!reserved);reserved=n;return 0;}
static void radv_ps5_granules_give(int *r,uint32_t at,uint32_t n){
    (void)r;(void)at;assert(reserved==n);reserved=0;}
static int64_t sceKernelGetDirectMemorySize(void){return 2048*MiB;}
static int sceKernelAvailableDirectMemorySize(int64_t a,int64_t b,size_t align,int64_t *at,size_t *size){
    (void)a;(void)b;(void)align;*at=0;*size=2*MiB;return 0;}
static int sceKernelAllocateDirectMemory(int64_t a,int64_t b,size_t n,size_t align,int type,int64_t *p){
    (void)a;(void)b;(void)align;(void)type;
    if(misses){--misses;return -1;}assert(n<=2*MiB);*p=(int64_t)held*2*MiB;++held;return 0;}
static int sceKernelReleaseDirectMemory(int64_t p,size_t n){
    (void)p;(void)n;assert(held);--held;return 0;}
static int sceKernelMapDirectMemory(void **p,size_t n,int prot,int flags,int64_t physical,size_t align){
    (void)n;(void)prot;(void)physical;(void)align;assert(flags==0);
    ++map_calls;if(map_calls==refuse_map)return -1;
    ++mapped;if(map_calls==wrong_map)*p=(void*)((uintptr_t)*p+0x100000000ULL);return 0;}
static int sceKernelMunmap(void *p,size_t n){(void)p;(void)n;assert(mapped);--mapped;return 0;}
static void reset(void){assert(!held&&!mapped&&!reserved);map_calls=refuse_map=wrong_map=misses=0;refuse_range=false;}
'''
    test = r'''
int main(void){
 struct radv_ps5_memory out={0};reset();
 // 14 MiB succeeds even though no physical hole exceeds 2 MiB.
 assert(radv_ps5_memory_alloc_chunked(13*MiB,2*MiB,&out));
 assert(out.bytes==14*MiB && out.chunk_count==7 && held==7 && mapped==7);
 radv_ps5_chunks_release(out.cpu,out.chunks,out.chunk_count);
 radv_ps5_granules_give(&radv_ps5_region,out.granule,out.granules);
 reset();refuse_map=3;
 assert(!radv_ps5_memory_alloc_chunked(13*MiB,2*MiB,&out));reset();
 wrong_map=3; // refuses relocation; never overwrites another mapping
 assert(!radv_ps5_memory_alloc_chunked(13*MiB,2*MiB,&out));reset();
 refuse_range=true;assert(!radv_ps5_memory_alloc_chunked(13*MiB,2*MiB,&out));reset();
 misses=4;assert(!radv_ps5_memory_alloc_chunked(13*MiB,2*MiB,&out));reset();
 // Bounded chunk ledger: partial allocations are all returned on overflow.
 assert(!radv_ps5_memory_alloc_chunked(513*MiB,2*MiB,&out));reset();
}
'''
    c = temp/'fragmented.c'
    c.write_text(prelude+production+test)
    binary = temp/'fragmented'
    run(['clang-18', '-std=c11', '-O1', '-g', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', c, '-o', binary])
    run([binary])

    # A matching stamp must also reject partial/corrupt code, without modifying it.
    platform.write_text(actual.replace('&& radv_ps5_memory_alloc_chunked(bytes, alignment, out)', '', 1))
    damaged = platform.read_bytes()
    assert subprocess.run(['python3', script, '--check', stamp]).returncode != 0
    assert subprocess.run(['python3', script], capture_output=True).returncode != 0
    assert platform.read_bytes() == damaged
print('PASS stale receipt rejection, real missing-layer repair, idempotence, partial-source refusal, '
      'fragmented backing, collision/map/OOM/chunk-limit rollback under ASan/UBSan')
