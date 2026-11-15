# SPDX-License-Identifier: GPL-3.0-or-later
"""Archive every file of completed DirkuLator GPU captures and their runtime logs."""
import argparse
from datetime import datetime, timezone
from ftplib import FTP, error_perm
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import time

ROOT = Path.cwd() / 'dirkulator-evidence'
LOGS = '/data/eden-nx2/logs'
CAPTURES = LOGS + '/capture'
CAPTURE_NAME = re.compile(r'capture-\d+-frame-\d+')
COMPLETED = re.compile(r'^EDEN_FRAME_CAPTURE frame=(\d+) images=(\d+) folder=(' + re.escape(CAPTURES) + r'/capture-\d+-frame-\d+)\s*$')


def sha_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class FTPSource:
    def __init__(self, ftp):
        self.ftp = ftp

    def list(self, path):
        assert path == LOGS or path.startswith(LOGS + '/')
        rows = []
        self.ftp.retrlines('LIST ' + path, rows.append)
        entries = []
        for row in rows:
            if row.startswith('total '):
                continue
            fields = row.split(maxsplit=8)
            assert len(fields) == 9, row
            name = fields[8]
            if name in ('.', '..'):
                continue
            assert '/' not in name and '\\' not in name and '\x00' not in name
            assert fields[0][0] in ('-', 'd'), 'Unexpected link in diagnostic tree: ' + row
            entries.append((name, fields[0][0] == 'd', int(fields[4]), ' '.join(fields[5:8])))
        return sorted(entries)

    def inventory(self, path, exclude_capture=False, depth=0):
        assert depth < 20
        result = {}
        for name, directory, size, modified in self.list(path):
            child = path + '/' + name
            if exclude_capture and child == CAPTURES:
                continue
            if directory:
                result.update(self.inventory(child, exclude_capture, depth + 1))
            else:
                result[child] = {'bytes': size, 'modified': modified}
        return result

    def retrieve(self, path, receive):
        assert path.startswith(LOGS + '/')
        self.ftp.retrbinary('RETR ' + path, receive, blocksize=262144)

    def bytes(self, path, maximum=1024 * 1024):
        data = bytearray()
        def receive(chunk):
            data.extend(chunk)
            assert len(data) <= maximum, path
        self.retrieve(path, receive)
        return bytes(data)


def transfer(source, remote, target, expected=None, stopped=lambda: False):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.partial')
    if expected is not None and shutil.disk_usage(target.parent).free < expected + 512 * 1024 * 1024:
        raise RuntimeError('Insufficient free space to archive all requested data: ' + remote)
    digest = hashlib.sha256()
    size = 0
    with temporary.open('wb') as stream:
        def receive(chunk):
            nonlocal size
            if stopped():
                raise InterruptedError('Archive collection stopped')
            stream.write(chunk); digest.update(chunk); size += len(chunk)
        source.retrieve(remote, receive)
    if expected is not None and size != expected:
        raise RuntimeError('Capture file changed or transfer is incomplete: ' + remote)
    assert sha_file(temporary) == digest.hexdigest(), 'Local read-back hash mismatch'
    temporary.replace(target)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def archive_capture(source, remote, target, stopped=lambda: False):
    assert remote.startswith(CAPTURES + '/') and CAPTURE_NAME.fullmatch(remote.rsplit('/', 1)[-1])
    before = source.inventory(remote)
    assert remote + '/index.txt' in before
    before_index = source.bytes(remote + '/index.txt')
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    manifest = {}
    # No extension, size, stage or buffer filters: every produced capture file is retained.
    for path, metadata in before.items():
        relative = path[len(remote) + 1:]
        assert relative and '..' not in Path(relative).parts
        local = target / relative
        assert local.resolve().is_relative_to(target.resolve())
        manifest[relative] = transfer(source, path, local, metadata['bytes'], stopped)
    after = source.inventory(remote)
    if before != after or source.bytes(remote + '/index.txt') != before_index:
        raise RuntimeError('Capture generation changed during collection: ' + remote)
    for index in target.rglob('index.txt'):
        for line in index.read_text().splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            fields = line.split()
            assert len(fields) >= 14
            referenced = index.parent / fields[13]
            assert referenced.resolve().is_relative_to(target.resolve())
            assert referenced.is_file() and referenced.stat().st_size == int(fields[7]), referenced
    result = {'remote': remote, 'collected_utc': datetime.now(timezone.utc).isoformat(),
              'complete': True, 'file_count': len(manifest),
              'total_bytes': sum(value['bytes'] for value in manifest.values()), 'files': manifest}
    (target / 'ARCHIVE-MANIFEST.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def archive_partial(source, remote, target):
    assert remote.startswith(CAPTURES + '/') and '..' not in remote.split('/')
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    before = source.inventory(remote)
    files = {}
    for path, metadata in before.items():
        relative = path[len(remote) + 1:]
        local = target / relative
        assert local.resolve().is_relative_to(target.resolve())
        files[relative] = transfer(source, path, local, metadata['bytes'])
    result = {'remote': remote, 'complete': False, 'reason': 'Title closed before a capture-completed marker was observed',
              'inventory_stable': source.inventory(remote) == before, 'files': files,
              'file_count': len(files), 'total_bytes': sum(value['bytes'] for value in files.values())}
    (target / 'ARCHIVE-MANIFEST.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def request_capture(ftp, read, write, record, output):
    before = read(LOGS + '/stderr.log', 64 * 1024 * 1024).decode(errors='replace').splitlines()
    prior = {line for line in before if COMPLETED.match(line)}
    write('/data/eden-nx2/capture-now.txt', b'1\n')
    # A synchronous native dump can take several minutes on console storage.
    # Keep observing the same request; do not encourage another overlapping dump.
    deadline = time.monotonic() + 600
    remote = None
    reported_begin = set()
    while time.monotonic() < deadline:
        time.sleep(1)
        lines = read(LOGS + '/stderr.log', 64 * 1024 * 1024).decode(errors='replace').splitlines()
        for line in lines[len(before):]:
            if line.startswith('EDEN_FRAME_CAPTURE_BEGIN ') and line not in reported_begin:
                reported_begin.add(line)
                record('native synchronous capture began', native=line)
                print('GPU capture in progress: rendering is paused by the native dump; waiting for completion.', flush=True)
        found = [COMPLETED.match(line) for line in lines if line not in prior and COMPLETED.match(line)]
        if found:
            remote = found[-1].group(3)
            break
    if remote is None:
        raise RuntimeError('No completed GPU capture observed within 600 seconds; do not overlap requests. Collector will retain a later completion')
    record('GPU capture completed', remote=remote)
    latest = ROOT / 'capture-archive/LATEST.json'
    if latest.is_file():
        watcher = json.loads(latest.read_text())
        boot = read(LOGS + '/boot-trace.txt', 1024 * 1024).decode(errors='replace').splitlines()[0]
        session = hashlib.sha256(boot.encode()).hexdigest()[:16]
        try:
            os.kill(watcher['pid'], 0)
            running = True
        except (ProcessLookupError, PermissionError):
            running = False
        if running:
            index = Path(watcher['directory']) / 'capture-index.json'
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if index.is_file():
                    matches = [item for item in json.loads(index.read_text()) if item['remote'] == remote and item['session'] == session]
                    if matches:
                        record('complete unfiltered archive', **matches[-1])
                        print('FULL_GPU_ARCHIVE', matches[-1]['directory'], flush=True)
                        return
                time.sleep(1)
            raise RuntimeError('Capture completed but full archival is still pending; inspect collector state')
    result = archive_capture(FTPSource(ftp), remote, output / 'capture')
    record('complete unfiltered archive', directory=str(output / 'capture'), files=result['file_count'], bytes=result['total_bytes'])
    print('FULL_GPU_ARCHIVE', output / 'capture', flush=True)


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--stop-when-title-exits', action='store_true')
    parser.add_argument('--maximum-seconds', type=int, default=7200)
    parser.add_argument('--evidence-dir', default=str(ROOT))
    args = parser.parse_args()
    ROOT = Path(args.evidence_dir).resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'capture-archive' / stamp
    output.mkdir(parents=True)
    (output / 'pid.txt').write_text(str(os.getpid()) + '\n')
    (output.parent / 'LATEST.json').write_text(json.dumps({'pid': os.getpid(), 'directory': str(output)}, indent=2) + '\n')
    stop = False
    def request_stop(signum, frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    events_file = (output / 'events.jsonl').open('a', buffering=1)
    def record(operation, **values):
        value = {'utc': datetime.now(timezone.utc).isoformat(), 'operation': operation, **values}
        events_file.write(json.dumps(value) + '\n')
        if operation in ('capture archived', 'error', 'collector stopped'):
            print(json.dumps(value), flush=True)
    known = set()
    archived_remotes = set()
    baseline = None
    capture_index = []
    total_bytes = captures = 0
    started = time.monotonic()
    seen_active = False
    absent = 0
    live_metadata = {}
    next_logs = 0
    session = 'waiting'
    completed = False
    record('collector started', pid=os.getpid(), scope='All files of every completed capture generated during this watch; associated log tree is mirrored without capture-file filtering')
    print('CAPTURE_ARCHIVE_WATCH', output, flush=True)
    try:
        while not stop and time.monotonic() - started < args.maximum_seconds:
            try:
                with FTP() as ftp:
                    ftp.connect(args.host, 2121, timeout=20); ftp.login()
                    response = ftp.sendcmd('SELF')
                    assert 'disabled' in response.lower(), response
                    source = FTPSource(ftp)
                    if baseline is None:
                        baseline = {}
                        for name, directory, size, modified in source.list(CAPTURES):
                            if directory and (CAPTURE_NAME.fullmatch(name) or name == 'stages-pending'):
                                try:
                                    baseline[name] = hashlib.sha256(source.bytes(CAPTURES + '/' + name + '/index.txt')).hexdigest()
                                except error_perm:
                                    baseline[name] = None
                        (output / 'preexisting-capture-index.json').write_text(json.dumps(baseline, indent=2) + '\n')
                    boot = source.bytes(LOGS + '/boot-trace.txt').decode(errors='replace').splitlines()[0]
                    session = hashlib.sha256(boot.encode()).hexdigest()[:16]
                    live = output / 'sessions' / session / 'live-logs'
                    try:
                        previous = ftp.pwd()
                        ftp.cwd('/mnt/sandbox/PPSA99862_000')
                        active = True
                        ftp.cwd(previous)
                    except error_perm:
                        active = False
                    is_bridge = 'diagnostic build ' in boot and 'pid ' in boot
                    if active and is_bridge:
                        seen_active = True; absent = 0
                    elif seen_active:
                        absent += 1
                    refresh = time.monotonic() >= next_logs or (seen_active and not active)
                    if refresh:
                        listing = source.inventory(LOGS, exclude_capture=True)
                        essential = {'boot-trace.txt', 'stderr.log', 'perf-monitor.csv', 'heap.log', 'eden_log.txt', 'input-bridge-status.json'}
                        for remote, metadata in sorted(listing.items(), key=lambda item: (item[0].rsplit('/', 1)[-1] not in essential, item[0])):
                            relative = remote[len(LOGS) + 1:]
                            identity = (session, remote)
                            if live_metadata.get(identity) == metadata and remote.rsplit('/', 1)[-1] not in essential:
                                continue
                            target = live / relative
                            target.parent.mkdir(parents=True, exist_ok=True)
                            old_size = target.stat().st_size if target.exists() else 0
                            if target.exists() and metadata['bytes'] < old_size:
                                history = target.with_name(target.name + '.before-rotation-' + datetime.now(timezone.utc).strftime('%H%M%S'))
                                target.rename(history)
                            copied = transfer(source, remote, target, stopped=lambda: stop)
                            live_metadata[identity] = metadata
                            record('runtime log mirrored', remote=remote, local=str(target.relative_to(output)), **copied)
                        next_logs = time.monotonic() + 15
                        boot_after = source.bytes(LOGS + '/boot-trace.txt').decode(errors='replace').splitlines()[0]
                        if boot_after != boot:
                            record('runtime changed during log snapshot', original_boot=boot, current_boot=boot_after,
                                   attribution='transitional log snapshot; do not attribute its captures to the old runtime')
                            next_logs = 0
                            continue
                    stderr = live / 'stderr.log'
                    lines = stderr.read_text(errors='replace').splitlines() if stderr.exists() else []
                    for ordinal, line in enumerate(lines):
                        match = COMPLETED.match(line)
                        if not match:
                            continue
                        frame, images, remote = match.groups()
                        key = session + ':' + str(ordinal) + ':' + remote
                        if key in known:
                            continue
                        # The original stderr copy at watch startup may describe preexisting captures.
                        # Preserve them too, under their observed runtime; no new-build attribution.
                        target = output / 'sessions' / session / 'captures' / (remote.rsplit('/', 1)[-1] + '-event-' + str(ordinal))
                        result = archive_capture(source, remote, target, lambda: stop)
                        logs_at_capture = target / 'runtime-logs'
                        for local in live.rglob('*'):
                            if local.is_file():
                                destination = logs_at_capture / local.relative_to(live)
                                destination.parent.mkdir(parents=True, exist_ok=True)
                                try:
                                    os.link(local, destination)
                                except OSError:
                                    shutil.copyfile(local, destination)
                        known.add(key); captures += 1; total_bytes += result['total_bytes']
                        archived_remotes.add(remote)
                        capture_index.append({'remote': remote, 'session': session, 'directory': str(target),
                                              'files': result['file_count'], 'bytes': result['total_bytes']})
                        temporary_index = output / 'capture-index.json.tmp'
                        temporary_index.write_text(json.dumps(capture_index, indent=2) + '\n')
                        temporary_index.replace(output / 'capture-index.json')
                        record('capture archived', session=session, boot=boot, frame=int(frame), reported_images=int(images),
                               directory=str(target.relative_to(output)), files=result['file_count'], bytes=result['total_bytes'])
                    (output / 'status.json').write_text(json.dumps({'pid': os.getpid(), 'session': session,
                        'native_bridge_seen_active': seen_active, 'title_active': active, 'captures': captures,
                        'capture_bytes': total_bytes, 'running': True, 'updated_utc': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')
                    if args.stop_when_title_exits and seen_active and absent >= 3:
                        for name, directory, size, modified in source.list(CAPTURES):
                            if not directory or not (CAPTURE_NAME.fullmatch(name) or name == 'stages-pending'):
                                continue
                            remote = CAPTURES + '/' + name
                            if remote in archived_remotes:
                                continue
                            try:
                                fingerprint = hashlib.sha256(source.bytes(remote + '/index.txt')).hexdigest()
                            except error_perm:
                                fingerprint = None
                            if name in baseline and fingerprint == baseline[name] and name != 'stages-pending':
                                continue
                            target = output / 'sessions' / session / 'incomplete-captures' / name
                            result = archive_partial(source, remote, target)
                            record('incomplete capture preserved', remote=remote, directory=str(target.relative_to(output)),
                                   files=result['file_count'], bytes=result['total_bytes'])
                        completed = True
                        break
            except InterruptedError:
                stop = True
            except Exception as exc:
                record('error', error=type(exc).__name__ + ': ' + str(exc))
            for _ in range(20):
                if stop:
                    break
                time.sleep(0.1)
    finally:
        result = {'pid': os.getpid(), 'running': False, 'captures': captures, 'capture_bytes': total_bytes,
                  'native_bridge_seen_active': seen_active, 'title_close_observed': completed,
                  'reason': 'title exit observed' if completed else 'stop requested or observation time limit',
                  'closed_by': 'not inferred; correlate with user statement or reviewed close-helper evidence'}
        (output / 'status.json').write_text(json.dumps(result, indent=2) + '\n')
        record('collector stopped', **result)
        events_file.close()


if __name__ == '__main__':
    main()
