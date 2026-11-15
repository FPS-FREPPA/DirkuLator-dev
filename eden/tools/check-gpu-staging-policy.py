#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise production GPU staging policy/trim with roomy fragmentation and pressure."""
from pathlib import Path
import argparse,json,re,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path);args=parser.parse_args()
fixture=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <span>
#include <vector>
#include "POLICY"
using namespace Eden::StagingBuffers;
constexpr std::uint64_t MiB=1ULL<<20;
struct Entry {std::span<unsigned char> mapped_span;unsigned log2_level;bool deferred,busy;int id;};
struct Level {std::vector<Entry> entries;std::size_t iterate_index=0,delete_index=0;};
using Cache=std::array<Level,32>;
static unsigned char* const fake=reinterpret_cast<unsigned char*>(std::uintptr_t{1}<<40);
Entry Make(int id,bool busy=false,bool deferred=false){return {{fake,16*MiB},24,deferred,busy,id};}
constexpr auto idle=[](const Entry& e){return !e.busy&&!e.deferred;};
std::size_t IdleCount(const Cache& cache){std::size_t n=0;for(const auto& level:cache)for(const auto& entry:level.entries)n+=idle(entry);return n;}
bool Has(const Cache& cache,int id){for(const auto& level:cache)for(const auto& entry:level.entries)if(entry.id==id)return true;return false;}
int main(){
 static_assert(IdleAllowance(static_cast<std::size_t>(-1))==256*MiB);
 static_assert(IdleAllowance(64*MiB)==64*MiB);
 static_assert(IdleAllowance(31*MiB)==0);
#ifndef BASELINE
 // Known physical fragmentation no longer implies the old 64 MiB or zero cap.
 static_assert(IdleAllowance(64*MiB,1024*MiB)==256*MiB);
 static_assert(IdleAllowance(2*MiB,2048*MiB)==256*MiB);
 static_assert(IdleAllowance(64*MiB,1024*MiB-1)==128*MiB);
 static_assert(IdleAllowance(64*MiB,512*MiB)==128*MiB);
 static_assert(IdleAllowance(16*MiB,512*MiB-1)==64*MiB);
 static_assert(IdleAllowance(16*MiB,256*MiB)==64*MiB);
 static_assert(IdleAllowance(64*MiB,256*MiB-1)==0);
 static_assert(IdleAllowance(2*MiB-1,2048*MiB)==0);
 static_assert(IdleAllowance(static_cast<std::size_t>(-1),768*MiB)==128*MiB);
#endif
 Cache device{},upload{},download{};
 std::array<Cache*,3> caches{&device,&upload,&download};
 upload[24].entries.push_back(Make(-1,true));
 download[24].entries.push_back(Make(-2,false,true));
 for(int n=0;n<8;++n)upload[24].entries.push_back(Make(n));
 unsigned recreated=0;
 // Same 128 MiB transfer working set over 60 modeled frames. Both headers see
 // the same 768 MiB total/64 MiB largest snapshot. This measures allocation
 // requests in a model, never GPU performance or FPS.
 for(int frame=0;frame<60;++frame){
  const auto released=TrimIdle(caches,idle,IdleAllowance(64*MiB,768*MiB));
  assert(Has(upload,-1)&&Has(download,-2));
  const auto held=IdleCount(upload);assert(held<=8&&released.bytes==(8-held)*16*MiB);
  recreated+=unsigned(8-held);
  for(std::size_t n=held;n<8;++n)upload[24].entries.push_back(Make(int(n)));
 }
#ifdef BASELINE
 assert(recreated==240);
#else
 assert(recreated==0);
#endif
 // Critical total pressure drops every completed idle entry, never in-flight.
 auto released=TrimIdle(caches,idle,IdleAllowance(64*MiB,200*MiB));
 assert(released.bytes==128*MiB&&IdleCount(upload)==0);
 assert(Has(upload,-1)&&Has(download,-2));
 for(int n=0;n<8;++n)upload[24].entries.push_back(Make(n));
 released=TrimIdle(caches,idle,IdleAllowance(1*MiB,2048*MiB));
 assert(released.bytes==128*MiB&&IdleCount(upload)==0);
 assert(Has(upload,-1)&&Has(download,-2));
 std::printf("{\"modeled_frames\":60,\"recreated_buffers\":%u,\"physical_gpu_test\":false}\n",recreated);
}
'''
results={}
with tempfile.TemporaryDirectory(prefix='eden-gpu-staging-') as tmp:
 tmp=Path(tmp)
 targets=[('current',root/'headless/staging_buffers.h')]+([('baseline',args.baseline)] if args.baseline else [])
 for name,header in targets:
  source=tmp/(name+'.cpp');source.write_text(fixture.replace('POLICY',str(header)))
  binary=tmp/name
  command=['clang++-18','-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(source),'-o',str(binary)]
  if name=='baseline':command.insert(1,'-DBASELINE')
  subprocess.run(command,check=True)
  result=subprocess.run([str(binary)],capture_output=True,text=True,check=True)
  results[name]=json.loads(result.stdout)
  print(name,result.stdout.strip())
print('PASS production GPU staging policy/trim: known/unknown headroom, 2 MiB physical bound, pressure transitions, busy/deferred protection and preceding-policy comparison')
