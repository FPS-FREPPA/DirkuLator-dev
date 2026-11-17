#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check repository hygiene and preservation of the distributed license texts."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path(__file__).resolve().parents[2]


def git(*arguments):
    result = subprocess.run(['git', '-C', str(root), *arguments], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


ignored = [
    'eden/build/release/PPSA99862/eboot.bin', 'eden/build/release/PPSA99863/eboot.bin', 'eden/.deps/input/LICENSE',
    'eden/.local/headless-cache', '.cache/download', 'build-native/object.o',
    'cmake-build-debug/CMakeCache.txt', 'CMakeUserPresets.json', 'compile_commands.json',
    'nested/build.ninja', 'nested/.ninja_log', 'nested/meson-private/coredata.dat',
    '.venv/bin/python', 'nested/__pycache__/tool.cpython-314.pyc', '.pytest_cache/state',
    '.env', '.env.production', 'secret.pem', 'secret.key', '.git-credentials',
    'roms/private.nup', 'games/private.nsp', 'games/private.xci', 'firmware/private.pup',
    'private.keys', 'captures/frame.raw', 'private.pcapng', 'private.prosperodmp',
    'dirkulator-evidence/capture-archive/status.json', 'snapshots for debugging/frame.jpg',
    'save-backup-test/save.dat', 'saves/private.dat', 'eden/user/save.dat',
    'release.zip', 'release.tar.gz', 'program.elf', 'runtime.prx', 'object.obj',
    'library.a', 'program.exe', 'symbols.pdb', 'cache.spv', 'coverage/report.html',
    'profile.profraw', 'debug.log', 'file.cpp.orig', 'file.diff.rej', 'Thumbs.db',
    '.tools/compiler/data', '.wsl/build.vhdx', '.aws/credentials', '.ssh/config',
    '.codex/auth.json', 'PPSA99862/eboot.bin', 'PPSA99863/eboot.bin', 'DirkuLator-0.5.54rc/PPSA99862/eboot.bin',
    'input-bridge-status.json', 'capture-now.txt', 'perf-monitor.csv',
]
retained = [
    'README.md', 'LICENSE', 'NOTICE.md', 'CONTRIBUTING.md', 'THIRD_PARTY_NOTICES.md',
    'SOURCES.md', 'RELEASE.json', 'VALIDATION.json', '.env.example', '.env.sample',
    'eden/Makefile', 'eden/UPSTREAM.json', 'eden/tools/deps.json',
    'eden/tools/eden-patches/example.diff', 'eden/headless/main.cpp',
    'eden/sce_sys/param.json', 'eden/sce_sys/icon0.png', 'eden/sce_sys/pic0.dds',
    'eden/headless/prosperoeden/ui/art/brand.tga', 'eden/fixtures/core-homebrew.S',
    'licenses/README.md', 'licenses/MANIFEST.json',
    'licenses/dependencies/pinned-inputs/dav1d/COPYING',
    'tools/bridge/client.py', 'tools/bridge/test_capture_archive.py',
]
for expected, paths in [(True, ignored), (False, retained)]:
    for path in paths:
        result = subprocess.run(['git', '-C', str(root), 'check-ignore', '--no-index', '-q', path])
        assert result.returncode in (0, 1), path
        assert (result.returncode == 0) == expected, ('wrong ignore policy', path)

assert digest(root / 'LICENSE') == digest(root / 'eden/LICENSE'), 'Original GPL text differs'
manifest = json.loads((root / 'licenses/MANIFEST.json').read_text())
for name, expected in manifest.items():
    path = root / 'licenses/dependencies' / name
    assert path.is_file() and digest(path) == expected['sha256'], name
# Confirm the bytes Git will publish, not only the working-tree copies.
requests = ''.join(':licenses/dependencies/' + name + '\n' for name in manifest)
batch = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch'],
                       input=requests.encode(), capture_output=True, check=True).stdout
position = 0
for name, expected in manifest.items():
    end = batch.index(b'\n', position)
    header = batch[position:end].split()
    assert len(header) == 3 and header[1] == b'blob', name
    size = int(header[2])
    contents = batch[end + 1:end + 1 + size]
    assert hashlib.sha256(contents).hexdigest() == expected['sha256'], ('Git license bytes', name)
    position = end + 1 + size + 1
assert len(manifest) == 159
assert (root / 'NOTICE.md').is_file()
assert b'15 November 2026' in (root / 'NOTICE.md').read_bytes()
tracked_ignored = git('ls-files', '--cached', '--ignored', '--exclude-standard', '-z')
assert not tracked_ignored, 'Tracked files match ignore rules: ' + tracked_ignored.decode(errors='replace').replace('\0', ', ')
for name in git('ls-files', '-z').split(b'\0'):
    if not name:
        continue
    path = Path(name.decode())
    assert path.suffix.lower() not in {'.nup', '.nsp', '.xci', '.nca', '.pup', '.keys',
                                      '.prx', '.elf', '.exe', '.dll', '.pcap', '.pcapng', '.raw'}, str(path)
git('fsck', '--full', '--no-dangling')
print(json.dumps({'ignore_cases': len(ignored), 'retained_source_cases': len(retained),
                  'original_gpl_text_preserved': True, 'dependency_license_hashes': len(manifest),
                  'tracked_ignored_files': 0, 'tracked_private_artifacts': 0,
                  'git_object_integrity': 'pass'}))
