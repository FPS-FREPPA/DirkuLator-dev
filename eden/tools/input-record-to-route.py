#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn the physical pad log of a hand-played run (logs/input-record.csv, 0.67rc) into a bridge route.

usage: input-record-to-route.py <input-record.csv> --output <route.txt> [--launch N] [--grid SECONDS]

The log has one line per change of the pad state: t_ms,buttons_hex,lx,ly,rx,ry,l2,r2 (see headless/input_record.h),
and a "# launch" comment before each launch. --launch picks one (1 = the first, default: the last). The state is
sampled on a grid (default 0.1 s) and equal neighbours are merged, so the route reproduces the timing of the run
to about a tenth of a second:

    move SECONDS LX LY RX RY [buttons...]      sticks 0-255 (128 centred), buttons by the bridge's names
    wait SECONDS                               nothing held

Replay it with the route tool (tools/bridge/route.py or the project's logs/tools/bridge-route.py) with --jitter 0.
A trigger pressed far enough to count as a button (L2, R2) is written as that button; the analogue depth is not
replayed. Buttons the bridge cannot press (the touchpad) are left out.
"""
import argparse
from pathlib import Path

BUTTONS = [(0x1, 'create'), (0x2, 'l3'), (0x4, 'r3'), (0x8, 'options'), (0x10, 'up'), (0x20, 'right'),
           (0x40, 'down'), (0x80, 'left'), (0x100, 'l2'), (0x200, 'r2'), (0x400, 'l1'), (0x800, 'r1'),
           (0x1000, 'triangle'), (0x2000, 'circle'), (0x4000, 'cross'), (0x8000, 'square')]


def parse(path, launch):
    launches = []
    for line in Path(path).read_text().splitlines():
        if line.startswith('#'):
            launches.append([])
            continue
        if not line.strip():
            continue
        if not launches:
            launches.append([])
        w = line.split(',')
        launches[-1].append((int(w[0]), int(w[1], 16), *map(int, w[2:8])))
    launches = [l for l in launches if l]
    if not launches:
        raise SystemExit('no pad samples in ' + str(path))
    return launches[(launch - 1) if launch else -1]


def names(mask):
    return [n for bit, n in BUTTONS if mask & bit]


def convert(rows, grid_ms):
    states = []
    end = rows[-1][0]
    t = rows[0][0]
    i = 0
    while t <= end:
        while i + 1 < len(rows) and rows[i + 1][0] <= t:
            i += 1
        _, buttons, lx, ly, rx, ry, l2, r2 = rows[i]
        states.append((buttons & 0xFFFF, lx, ly, rx, ry))
        t += grid_ms
    steps = []
    for state in states:
        if steps and steps[-1][0] == state:
            steps[-1][1] += grid_ms
        else:
            steps.append([state, grid_ms])
    lines = []
    for (buttons, lx, ly, rx, ry), ms in steps:
        seconds = ms / 1000.0
        if buttons == 0 and abs(lx - 128) < 3 and abs(ly - 128) < 3 and abs(rx - 128) < 3 and abs(ry - 128) < 3:
            lines.append(f'wait {seconds:.2f}')
        else:
            lines.append(' '.join([f'move {seconds:.2f}', str(lx), str(ly), str(rx), str(ry)] + names(buttons)))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('csv')
    parser.add_argument('--output', required=True)
    parser.add_argument('--launch', type=int, default=0)
    parser.add_argument('--grid', type=float, default=0.1)
    args = parser.parse_args()
    rows = parse(args.csv, args.launch)
    lines = convert(rows, max(20, int(args.grid * 1000)))
    header = [f'# replay of {Path(args.csv).name}, {len(rows)} pad changes over {(rows[-1][0] - rows[0][0]) / 1000:.1f} s,'
              f' sampled every {args.grid:g} s; run with --jitter 0']
    Path(args.output).write_text('\n'.join(header + lines) + '\n')
    print('wrote', args.output, len(lines), 'steps')


if __name__ == '__main__':
    main()
