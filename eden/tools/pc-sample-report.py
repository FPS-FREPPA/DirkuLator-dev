#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn the EDEN_PC_SAMPLES lines of a run (0.68rc, headless/pc_sampler.h) into where the GPU threads spend their time.

usage: pc-sample-report.py <stderr.log> --elf <exact llvm-pie ELF> [--perf <perf-monitor.csv>] [--target GPU] [--top 25]

Each report line is a 10 s window with the busiest sampled addresses (relative to __eden_text_start; "abs:" ones are
libraries or JIT code). The addresses are symbolised with llvm-addr2line against the ELF of the build that ran
(run it where the ELF and llvm-addr2line-18 are, e.g. WSL), summed by function, and, when the run's perf-monitor.csv is
given, split into the windows where the game ran slow (10 s mean under 6 FPS) and healthy (10 FPS or more). The
window of a report is matched by its `up_s` against the launch's perf-monitor seconds (both count from the launch,
within a few seconds of each other).
"""
import argparse
import csv
import io
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('log')
parser.add_argument('--elf', required=True)
parser.add_argument('--perf')
parser.add_argument('--target', default='GPU')
parser.add_argument('--top', type=int, default=25)
args = parser.parse_args()

pat = re.compile(r'EDEN_PC_SAMPLES up_s=(\d+) target=(\S+) n=(\d+) lost=(\d+) sent=(\d+) failed=(\d+) base=(0x[0-9a-f]+) top:(.*)')
windows = []
for line in Path(args.log).read_text(errors='replace').splitlines():
    m = pat.match(line)
    if not m or m.group(2) != args.target:
        continue
    entries = []
    for e in m.group(8).split():
        a, c = e.rsplit('=', 1)
        entries.append((a, int(c)))
    windows.append(dict(up=int(m.group(1)), n=int(m.group(3)), lost=int(m.group(4)), entries=entries))
if not windows:
    raise SystemExit('no EDEN_PC_SAMPLES lines for target ' + args.target)

# symbolise every distinct relative address once
rel = sorted({a for w in windows for a, _ in w['entries'] if not a.startswith('abs:')})
names = {}
if rel:
    out = subprocess.run(['llvm-addr2line-18', '-f', '-C', '-e', args.elf] + rel, capture_output=True, text=True).stdout.splitlines()
    for i, a in enumerate(rel):
        func = out[2 * i] if 2 * i < len(out) else '?'
        where = out[2 * i + 1].rsplit('/', 1)[-1] if 2 * i + 1 < len(out) else ''
        names[a] = func + ' (' + where + ')'

# classify windows by the launch's perf seconds
cls = {}
if args.perf:
    text = Path(args.perf).read_text(errors='replace').splitlines()
    last = max(i for i, l in enumerate(text) if l.startswith('# session'))
    rows = list(csv.DictReader(io.StringIO('\n'.join(text[last + 1:]))))
    t = [float(r['t_s']) for r in rows]
    fps = [int(r['frames']) for r in rows]
    for w in windows:
        idx = [i for i in range(len(t)) if w['up'] - 10 <= t[i] < w['up']]
        if idx:
            m = statistics.mean(fps[i] for i in idx)
            cls[w['up']] = 'slow' if m < 6 else ('healthy' if m >= 10 else 'mixed')


def summarise(label, ws):
    total = sum(c for w in ws for _, c in w['entries'])
    if not total:
        return
    byfunc = Counter()
    for w in ws:
        for a, c in w['entries']:
            byfunc[names.get(a, 'library or JIT code (' + a + ')') if not a.startswith('abs:') else 'library or JIT code (' + a[4:] + ')'] += c
    print(f'\n## {label}: {len(ws)} windows, {sum(w["n"] for w in ws)} samples ({total} in the listed addresses)')
    for f, c in byfunc.most_common(args.top):
        print(f'  {100 * c / total:5.1f} %  {f}')


print(f'# {args.target}: {len(windows)} report windows from up_s={windows[0]["up"]} to {windows[-1]["up"]}; lost samples {sum(w["lost"] for w in windows)}')
summarise('all windows', windows)
for c in ('slow', 'healthy'):
    summarise(c + ' windows', [w for w in windows if cls.get(w['up']) == c])
