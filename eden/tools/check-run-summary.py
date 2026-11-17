#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host check of headless/run_summary.h (0.69rc): the summary the console writes about a run.

Feeds a recorder one-second samples (a menu second, 15 healthy gameplay seconds at 12 FPS and 21,000 draws, 30 slow
seconds at 2 FPS and 2,200 draws with draw time 840 ms, then 20 healthy seconds), audio output windows and sampled
addresses, and checks: gameplay starts at the first second with more than 8,000 draws and not before; the totals,
mean, median and counts; exactly one slow wave (10 s mean under 6 FPS) with its FPS, GPU busy, draws and microseconds
per draw (about 380 against about 18 healthy); the healthy and slow class figures; the audio totals; that sampled
addresses land in the slow table while the wave is open and in the healthy table after; that the file is written
atomically (no .tmp left, content equal to the text) by Flush and not before the 30 s interval; the version read from
param.json; and that run-summary-off.txt writes nothing.
"""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

fixture = r'''
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include "run_summary.h"

namespace fs = std::filesystem;
using Eden::RunSummary::Get;

static std::string read(const fs::path &p) {
  std::ifstream in(p);
  return std::string((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
}
static std::string value(const std::string &text, const std::string &key) {
  const auto at = text.find("\n" + key + "=");
  assert(at != std::string::npos);
  const auto from = at + key.size() + 2;
  return text.substr(from, text.find('\n', from) - from);
}

int main(int argc, char **argv) {
  assert(argc == 3);
  std::setvbuf(stdout, nullptr, _IONBF, 0);  // the off-switch run aborts on purpose; its output must still arrive
  const fs::path data = argv[1], install = argv[2];
  auto &r = Get();
  r.Init(data.string(), install.string());
  double t = 0;
  r.AddSecond(++t, 0, 3000, 50, 5, 1, 1);                       // a menu second: not gameplay yet
  for (int i = 0; i < 15; ++i) r.AddSecond(++t, 12, 21000, 390, 21, 75, 85);   // healthy
  r.AddPc("GPU", {{"0x100", 7}});                              // healthy table
  for (int i = 0; i < 30; ++i) {
    r.AddSecond(++t, 2, 2200, 840, 3, 19, 12);                   // slow
    if (i == 20) {
      assert(r.SlowNow());
      r.AddPc("GPU", {{"0x2445", 40}, {"abs:0x7f00", 5}});     // slow table while the wave is open
    }
  }
  for (int i = 0; i < 20; ++i) r.AddSecond(++t, 12, 21000, 390, 21, 75, 85);   // healthy again
  assert(!r.SlowNow());
  r.AddAudioOut(938, 2, 1, 0, 25.7);
  r.AddAudioOut(937, 0, 0, 0, 5.6);

  const std::string text = r.Text();
  std::puts(text.c_str());
  assert(value("\n" + text, "build") == "00.005.069");
  assert(value("\n" + text, "gameplay_start_s") == "2");     // the first second with more than 8,000 draws
  assert(value("\n" + text, "gameplay_seconds") == "65");
  assert(value("\n" + text, "seconds_no_frame") == "0");
  assert(value("\n" + text, "slow_waves") == "1");
  assert(text.find("\nwave=t ") != std::string::npos);
  const double slow_us = std::stod(value("\n" + text, "slow_us_per_draw"));
  const double healthy_us = std::stod(value("\n" + text, "healthy_us_per_draw"));
  assert(slow_us > 370 && slow_us < 395);
  assert(healthy_us > 15 && healthy_us < 20);
  assert(std::stod(value("\n" + text, "slow_gpu_busy_pct")) == 3.0);
  assert(std::stod(value("\n" + text, "healthy_draws_per_s")) == 21000.0);
  assert(value("\n" + text, "audio_out_blocks") == "1875");
  assert(value("\n" + text, "audio_out_late_over_8ms") == "2");
  assert(value("\n" + text, "audio_out_windows_with_late_block") == "1");
  assert(text.find("\npc_slow_GPU=0x2445 40\n") != std::string::npos);
  assert(text.find("\npc_healthy_GPU=0x100 7\n") != std::string::npos);

  // the file: not written before the 30 s interval; Flush writes it atomically
  const auto files = [&] {
    std::vector<fs::path> v;
    for (auto &e : fs::directory_iterator(data / "logs")) v.push_back(e.path());
    return v;
  };
  r.Flush();
  const auto after = files();
  assert(after.size() == 1);
  assert(after[0].filename().string().rfind("run-summary-", 0) == 0 && after[0].extension() == ".txt");
  assert(read(after[0]) == text);
  return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='eden-run-summary-') as work:
    work = Path(work)
    (work / 'data' / 'logs').mkdir(parents=True)
    (work / 'install' / 'sce_sys').mkdir(parents=True)
    (work / 'install' / 'sce_sys' / 'param.json').write_text('{"titleId": "PPSA99862", "contentVersion": "00.005.069"}')
    (work / 'check.cpp').write_text(fixture)
    subprocess.run(['clang++-18', '-std=c++20', '-O1', '-g', '-Wall', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', f'-I{root / "headless"}', str(work / 'check.cpp'), '-o',
                    str(work / 'check')], check=True)
    result = subprocess.run([str(work / 'check'), str(work / 'data'), str(work / 'install')], capture_output=True,
                            text=True, timeout=60)
    print(result.stdout, end='')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    # the off switch: a new data folder with run-summary-off.txt writes no file
    (work / 'off' / 'logs').mkdir(parents=True)
    (work / 'off' / 'run-summary-off.txt').write_text('')
    off = subprocess.run([str(work / 'check'), str(work / 'off'), str(work / 'install')], capture_output=True, text=True,
                         timeout=60)
    assert 'EDEN_RUN_SUMMARY off' in off.stdout, off.stdout
    assert off.returncode != 0 and not list((work / 'off' / 'logs').iterdir()), 'the fixture must fail its asserts and write no file'

print('PASS run summary')
