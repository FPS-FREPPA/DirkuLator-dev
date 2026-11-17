#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host check of headless/input_record.h (0.67rc): the physical pad log that lets a hand-played run be replayed.

Feeds a recorder fixed samples in a temporary data folder and checks the CSV: the launch comment, a line for a
button press and its release, a line for a stick move of 3 or more steps and none for jitter of 1-2, one line for
a move held back by the 20 ms limit that is picked up by a later sample (a return to centre is never lost), no
line for an unusable sample (disconnected or intercepted), the append on a second launch, and the off switch.
Then runs tools/input-record-to-route.py on the result and checks the route it writes.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

fixture = r'''
#include <cassert>
#include <chrono>
#include <cstdio>
#include <string>
#include <thread>
#include "input_record.h"

static ps5::pad::Data sample(std::uint32_t buttons, int lx, int ly, int rx, int ry, int l2 = 0, int r2 = 0, int connected = 1) {
  auto d = ps5::pad::neutral_data();
  d.buttons = buttons;
  d.left_stick = {static_cast<std::uint8_t>(lx), static_cast<std::uint8_t>(ly)};
  d.right_stick = {static_cast<std::uint8_t>(rx), static_cast<std::uint8_t>(ry)};
  d.triggers.l2 = static_cast<std::uint8_t>(l2);
  d.triggers.r2 = static_cast<std::uint8_t>(r2);
  d.connected = connected;
  return d;
}
static void pause_ms(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

int main(int argc, char **argv) {
  assert(argc == 2);
  const std::string dir = argv[1];
  {
    Eden::InputRecorder recorder{dir};
    recorder.Observe(sample(0, 128, 128, 128, 128));              // first sample: always a line
    recorder.Observe(sample(0, 129, 127, 128, 128));              // jitter of 1: no line
    pause_ms(30);
    recorder.Observe(sample(0, 128, 0, 128, 128));                // stick forward: a line
    pause_ms(25);
    recorder.Observe(sample(ps5::pad::kButtonTriangle, 128, 0, 128, 128));  // button: a line, never held back
    pause_ms(45);
    recorder.Observe(sample(ps5::pad::kButtonTriangle | ps5::pad::kButtonIntercepted, 0, 0, 0, 0));  // intercepted: none
    recorder.Observe(sample(0, 128, 0, 128, 128, 0, 0, 0));      // disconnected: none
    recorder.Observe(sample(0, 128, 0, 128, 128));                // released: a line
    recorder.Observe(sample(0, 128, 128, 128, 128));              // back to centre inside 20 ms: held back
    pause_ms(30);
    recorder.Observe(sample(0, 128, 128, 128, 128));              // the held-back centre is written now
  }
  {
    Eden::InputRecorder second{dir};                              // appends with its own launch comment
    second.Observe(sample(ps5::pad::kButtonCircle, 128, 128, 128, 128));
  }
  return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='eden-input-record-') as work:
    work = Path(work)
    (work / 'data' / 'logs').mkdir(parents=True)
    (work / 'check.cpp').write_text(fixture)
    subprocess.run(['clang++-18', '-std=c++20', '-O1', '-g', '-Wall', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', f'-I{root / "headless"}', f'-I{root / "third_party"}',
                    str(work / 'check.cpp'), '-o', str(work / 'check')], check=True)
    result = subprocess.run([str(work / 'check'), str(work / 'data')], capture_output=True, text=True, timeout=60)
    print(result.stdout, end='')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    csv = (work / 'data' / 'logs' / 'input-record.csv').read_text().splitlines()
    print('\n'.join(csv))
    comments = [l for l in csv if l.startswith('#')]
    rows = [l.split(',') for l in csv if not l.startswith('#')]
    assert len(comments) == 2 and csv[0].startswith('# launch wall_unix='), 'one comment per launch'
    first = rows[:5]
    assert [r[1:] for r in first] == [
        ['00000000', '128', '128', '128', '128', '0', '0'],      # first sample
        ['00000000', '128', '0', '128', '128', '0', '0'],        # stick forward (jitter before it left no line)
        ['00001000', '128', '0', '128', '128', '0', '0'],        # triangle
        ['00000000', '128', '0', '128', '128', '0', '0'],        # released
        ['00000000', '128', '128', '128', '128', '0', '0'],      # centre, written by a later sample
    ], first
    assert rows[5][1] == '00002000', rows[5]                     # second launch: circle
    times = [int(r[0]) for r in rows[:5]]
    assert times == sorted(times) and times[1] >= 20, times

    # the off switch
    (work / 'off').mkdir()
    (work / 'off' / 'logs').mkdir()
    (work / 'off' / 'input-record-off.txt').write_text('')
    subprocess.run([str(work / 'check'), str(work / 'off')], check=True, capture_output=True, timeout=60)
    assert not (work / 'off' / 'logs' / 'input-record.csv').exists(), 'off switch must not write a log'

    # the converter
    route = work / 'route.txt'
    subprocess.run(['python3', str(root / 'tools' / 'input-record-to-route.py'), str(work / 'data' / 'logs' / 'input-record.csv'),
                    '--output', str(route), '--launch', '1', '--grid', '0.02'], check=True)
    text = route.read_text()
    print(text)
    assert 'move' in text and 'triangle' in text, text

print('PASS input record')
