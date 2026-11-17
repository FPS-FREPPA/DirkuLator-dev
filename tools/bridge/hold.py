# SPDX-License-Identifier: GPL-3.0-or-later
"""Continuous movement through DirkuLator's native PS5 bridge.

The native bridge accepts one pulse of at most 3000 ms and expires it by itself. A hold chains
overlapping pulses (each new one replaces the one running: 3000 ms long, one every 2000 ms) for the
requested time, so a stick stays held without a gap while every pulse still expires on its own: if
this program or the connection dies, the input ends within 3 s.

The hold ends early when the bridge cancels it (the physical controller was touched), stops or
changes session, when the stop file appears, or on Ctrl+C. It ends with a neutral 1 ms input, which
keeps the bridge armed; only when the bridge itself stopped does it send an explicit stop (a stop
disarms the bridge).

    hold.py --host 192.168.18.8 --seconds 60 --ly 0                 # walk forward for a minute
    hold.py --host 192.168.18.8 --seconds 600 --random              # both sticks at random, 3-6 s each
    hold.py --host 192.168.18.8 --seconds 20 --lx 200 --ly 0 --buttons triangle

Arm the bridge first with client.py (`arm`). Evidence (every command and the final status) goes to
`<evidence-dir>/bridge-hold/<time>-hold/events.json`.
"""
import argparse
from datetime import datetime, timezone
from ftplib import FTP
import io
import json
from pathlib import Path
import random
import re
import time

DATA = '/data/eden-nx2'
BUTTONS = dict(create=1, l3=2, r3=4, options=8, up=16, right=32, down=64, left=128,
               l2=256, r2=512, l1=1024, r1=2048, triangle=4096, circle=8192, cross=16384, square=32768)
PULSE_MS, PERIOD = 3000, 2.0
NEUTRAL = [128, 128, 128, 128, 0, 0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', required=True)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--random', action='store_true', help='random stick directions, changed every 3-6 s')
    parser.add_argument('--buttons', nargs='*', choices=list(BUTTONS), default=[])
    for axis in ['lx', 'ly', 'rx', 'ry', 'l2', 'r2']:
        parser.add_argument('--' + axis, type=int, default=128 if axis[1] in 'xy' else 0)
    parser.add_argument('--evidence-dir', default=str(Path.cwd() / 'dirkulator-evidence'))
    parser.add_argument('--stop-file', default='bridge-hold-stop.txt')
    args = parser.parse_args()
    assert 0 < args.seconds <= 900
    assert all(0 <= getattr(args, n) <= 255 for n in ['lx', 'ly', 'rx', 'ry', 'l2', 'r2'])
    out = Path(args.evidence_dir).resolve() / 'bridge-hold' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-hold')
    out.mkdir(parents=True)
    events = []

    def record(operation, **values):
        events.append({'utc': datetime.now(timezone.utc).isoformat(), 'operation': operation, **values})
        (out / 'events.json').write_text(json.dumps(events, indent=2) + '\n')

    stop_file = Path(args.stop_file)
    mask = sum(BUTTONS[n] for n in set(args.buttons))
    values = [args.lx, args.ly, args.rx, args.ry, args.l2, args.r2]
    rng = random.Random()
    sequence = 0
    reason = 'time elapsed'

    def randomize():
        # left stick: mostly forward with a random heading; right stick: a camera sweep; no buttons
        return [rng.choice([0, 0, 64, 192, 255, 128]), rng.choice([0, 0, 0, 60, 255]),
                rng.choice([128, 128, 60, 200]), rng.choice([128, 128, 100, 160]), 0, 0]

    with FTP() as ftp:
        ftp.connect(args.host, 2121, timeout=10)
        ftp.login()

        def read(path):
            body = bytearray()
            ftp.retrbinary('RETR ' + path, body.extend)
            return bytes(body)

        def status():
            value = json.loads(read(DATA + '/logs/input-bridge-status.json'))
            assert value.get('version') == 1 and re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value['session'])
            return value

        def send(session, operation, duration, buttons, axes):
            nonlocal sequence
            sequence = max(time.time_ns(), sequence + 1)
            body = f'v1 {session} {sequence} {operation} {duration} {buttons} ' + ' '.join(map(str, axes)) + '\n'
            temporary = DATA + '/.hold-input-bridge-command.txt.upload'
            ftp.storbinary('STOR ' + temporary, io.BytesIO(body.encode()))
            ftp.rename(temporary, DATA + '/input-bridge-command.txt')
            record('command', body=body.strip())

        current = status()
        assert current.get('ready') and current.get('enabled'), 'Arm the bridge first (client.py arm)'
        session = current['session']
        sequence = max(current['sequence'], current['rejected_sequence'])
        end = time.monotonic() + args.seconds
        next_send = change_at = time.monotonic()
        try:
            while time.monotonic() < end:
                if stop_file.exists():
                    reason = 'stop file'
                    break
                now = time.monotonic()
                if args.random and now >= change_at:
                    values = randomize()
                    change_at = now + rng.uniform(3, 6)
                    next_send = now
                if now >= next_send:
                    send(session, 'input', PULSE_MS, mask, values)
                    next_send = now + PERIOD
                time.sleep(0.25)
                value = status()
                if value['session'] != session or not value.get('ready'):
                    reason = 'bridge stopped or session changed'
                    break
                if value.get('rejected_sequence') == sequence:
                    reason = 'rejected: ' + value.get('error', 'unknown')
                    break
                if value.get('state') not in ('pending', 'active', 'expired') and value.get('applied_sequence') == sequence:
                    reason = 'canceled: ' + value.get('state', 'unknown')
                    break
        except KeyboardInterrupt:
            reason = 'interrupted'
        finally:
            try:
                if reason in ('time elapsed', 'stop file', 'interrupted'):
                    send(session, 'input', 1, 0, NEUTRAL)
                else:
                    send(session, 'stop', 0, 0, NEUTRAL)
            except Exception as exc:
                record('stop failed', error=str(exc))
            record('hold ended', reason=reason, last_status=status())
    print('HOLD_ENDED', reason, flush=True)
    print('BRIDGE_EVIDENCE', out, flush=True)


if __name__ == '__main__':
    main()
