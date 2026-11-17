#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host check of headless/pc_sampler.h (0.68rc): the release-safe program-counter sampler of the GPU threads.

Builds a fixture that starts a thread, names it "GPU" through NoteThread and spins in a function called spin_hot,
while the sampler (switch file, 200 Hz, no delay) sends SIGUSR2 to it. Checks that: without pc-sample.txt nothing is
switched on and no thread is started; with it the samples arrive (hundreds in about two seconds), at least 90 % of
them lie in spin_hot (looked up with dladdr), nothing is lost and no signal fails; a thread with another name is
never sampled; the report line has the documented shape (target, n, lost, sent, failed, base, top list, addresses
absolute on the host because there is no __eden_text_start). Runs with address and undefined-behaviour sanitizers.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

fixture = r'''
#include <cassert>
#include <chrono>
#include <cstdio>
#include <dlfcn.h>
#include <string>
#include <thread>
#include "pc_sampler.h"

extern "C" __attribute__((noinline)) double spin_hot(double x) {
  for (int i = 0; i < 2000; ++i) x = x * 1.0000001 + 0.5 / (1.0 + x * x);
  return x;
}
extern "C" __attribute__((noinline)) double spin_other(double x) {
  for (int i = 0; i < 2000; ++i) x = x * 1.0000002 + 0.25 / (1.0 + x * x);
  return x;
}

int main(int argc, char **argv) {
  assert(argc == 3);
  const std::string data = argv[1];
  const bool expect_on = std::string(argv[2]) == "on";
  const bool on = Eden::PcSampler::Init(data, /*start_thread=*/false);
  assert(on == expect_on);
  if (!on) {
    // switched off: a named thread is not registered and nothing is sampled
    std::thread([] { Eden::PcSampler::NoteThread("GPU"); }).join();
    assert(Eden::PcSampler::targets[0].thread.load() == 0);
    std::puts("PASS off");
    return 0;
  }
  std::atomic<bool> stop{false};
  std::thread gpu([&] {
    Eden::PcSampler::NoteThread("GPU");
    double x = 1.0;
    while (!stop.load()) x = spin_hot(x);
    std::printf("%g\n", x);
  });
  std::thread other([&] {  // another name: never a target
    Eden::PcSampler::NoteThread("SomethingElse");
    double x = 1.0;
    while (!stop.load()) x = spin_other(x);
    std::printf("%g\n", x);
  });
  while (Eden::PcSampler::targets[0].thread.load() == 0) std::this_thread::sleep_for(std::chrono::milliseconds(1));
  assert(Eden::PcSampler::targets[1].thread.load() == 0);
  // the sampler loop of detail::Run, driven here for two seconds at 200 Hz
  const auto end = std::chrono::steady_clock::now() + std::chrono::seconds(2);
  while (std::chrono::steady_clock::now() < end) {
    for (auto &t : Eden::PcSampler::targets) {
      const auto id = t.thread.load();
      if (!id) continue;
      if (pthread_kill(Eden::PcSampler::FromId(id), SIGUSR2) == 0) ++Eden::PcSampler::signals_sent;
      else ++Eden::PcSampler::signals_failed;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  stop = true;
  gpu.join();
  other.join();
  const auto pcs = Eden::PcSampler::Drain(0);
  assert(pcs.size() > 150);
  assert(Eden::PcSampler::Drain(1).empty());
  std::size_t hot = 0;
  for (const auto pc : pcs) {
    Dl_info info;
    if (dladdr(reinterpret_cast<void *>(pc), &info) && info.dli_sname && std::string(info.dli_sname) == "spin_hot") ++hot;
  }
  std::printf("samples %zu in spin_hot %zu sent %llu failed %llu lost %u\n", pcs.size(), hot,
              Eden::PcSampler::signals_sent.load(), Eden::PcSampler::signals_failed.load(), Eden::PcSampler::targets[0].lost);
  assert(hot * 10 >= pcs.size() * 9);
  assert(Eden::PcSampler::signals_failed.load() == 0);
  assert(Eden::PcSampler::targets[0].lost == 0);
  const std::string line = Eden::PcSampler::FormatReport(0, pcs, 12.0);
  std::puts(line.c_str());
  assert(line.rfind("EDEN_PC_SAMPLES up_s=12 target=GPU n=", 0) == 0);
  assert(line.find(" lost=0 ") != std::string::npos && line.find(" failed=0 ") != std::string::npos);
  assert(line.find(" base=0 top: abs:0x") != std::string::npos);
  assert(Eden::PcSampler::FormatReport(1, {}, 0).empty());
  std::puts("PASS on");
  return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='eden-pc-sampler-') as work:
    work = Path(work)
    (work / 'on').mkdir()
    (work / 'off').mkdir()
    (work / 'on' / 'pc-sample.txt').write_text('rate_hz=200\ndelay_s=0\n')
    (work / 'check.cpp').write_text(fixture)
    subprocess.run(['clang++-18', '-std=c++20', '-O1', '-g', '-Wall', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-pthread', '-rdynamic', f'-I{root / "headless"}',
                    str(work / 'check.cpp'), '-o', str(work / 'check'), '-ldl'], check=True)
    for mode in ('off', 'on'):
        result = subprocess.run([str(work / 'check'), str(work / mode), mode], capture_output=True, text=True, timeout=120)
        print(result.stdout, end='')
        print(result.stderr, end='')
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

print('PASS pc sampler')
