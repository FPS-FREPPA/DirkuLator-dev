#!/usr/bin/env python3
"""Check actual startup-task rewriting and affinity restoration under sanitizers."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
cache = Path((root/'.local/headless-cache').read_text().strip())
spec = importlib.util.spec_from_file_location('startup', root/'tools/prepare-startup-shaders.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
source = (cache/'source/src/video_core/renderer_vulkan/vk_pipeline_cache.cpp').read_text()
derived = policy.pipeline(source)
assert derived.count('StartupShaderAffinity startup_affinity;') == 2
begin = derived.index('void PipelineCache::LoadDiskResources(')
end = derived.index('void PipelineCache::QueueVulkanPipelineCacheFlush()', begin)
assert 'startup_affinity' not in derived[:begin] + derived[end:]
for broken in [source.replace('&state, &callback', '&state, &changed_callback', 1),
               source.replace('return max_core_threads;', 'return 1;')]:
    try:
        policy.pipeline(broken)
    except RuntimeError:
        pass
    else:
        raise AssertionError('A changed production anchor was accepted')

test = r'''
#include "startup_shader_affinity.h"
#include "staging_buffers.h"
#include <cassert>
#include <thread>
#include <vector>
#include <stdexcept>
using Eden::StartupShader::AffinityScope;
struct Ops {
    uint64_t current=0xaaa, allowed=0x3fff;
    unsigned changes=0;
    bool readable=true, refuse=false;
    uint64_t Allowed() const { return allowed; }
    bool Read(uint64_t& out) const { out=current; return readable; }
    bool Apply(uint64_t mask) {
        if (refuse) return false; // native backend verifies and rolls back failure
        assert(mask && !(mask & ~allowed)); current=mask; ++changes; return true;
    }
};
int main() {
    Ops ops;
    { AffinityScope scope{ops}; assert(ops.current==0x3fff);
      { AffinityScope nested{ops}; assert(ops.current==0x3fff); }
      assert(ops.current==0x3fff); }
    assert(ops.current==0xaaa && ops.changes==2);
    try { AffinityScope scope{ops}; throw std::runtime_error("compile failed"); }
    catch (const std::runtime_error&) {}
    assert(ops.current==0xaaa && ops.changes==4);
    ops.readable=false; {AffinityScope scope{ops};} assert(ops.changes==4);
    ops.readable=true; ops.refuse=true; {AffinityScope scope{ops};} assert(ops.current==0xaaa);
    ops.refuse=false; ops.allowed=0; {AffinityScope scope{ops};} assert(ops.changes==4);
    std::vector<std::thread> threads;
    for(unsigned i=0;i<14;i++) threads.emplace_back([]{
        Ops local;
        for(unsigned j=0;j<1000;j++) {
            { AffinityScope scope{local}; assert(local.current==0x3fff); }
            assert(local.current==0xaaa);
        }
    });
    for(auto& thread:threads) thread.join();
    using namespace Eden::StagingBuffers;
    constexpr uint64_t MiB=1ULL<<20;
    static_assert(IdleAllowance(512*MiB)==256*MiB);
    static_assert(IdleAllowance(128*MiB,1024*MiB)==256*MiB);
    static_assert(IdleAllowance(31*MiB,1024*MiB)==256*MiB);
    static_assert(IdleAllowance(1*MiB,1024*MiB)==0);
    static_assert(IdleAllowance(128*MiB,768*MiB)==128*MiB);
    static_assert(IdleAllowance(128*MiB,255*MiB)==0);
    static_assert(IdleAllowance(32*MiB,256*MiB)==64*MiB);
    static_assert(IdleAllowance(size_t(-1),-1)==256*MiB);
}
'''
with tempfile.TemporaryDirectory(prefix='eden-startup-shaders-') as folder:
    folder = Path(folder)
    (folder/'check.cpp').write_text(test)
    binary = folder/'check'
    subprocess.run(['clang++-18', '-std=c++20', '-pthread', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-I'+str(root/'headless'), str(folder/'check.cpp'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS startup graphics/compute task scopes, runtime exclusion, changed-anchor negative controls, '
      '14-thread affinity restoration and critical staging thresholds under ASan/UBSan')
