#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Three PS5 memory fixes from mihawk-99/PS5_Mesa, newer than the pinned driver.

tools/radv-patches holds them unchanged, in the order they were committed:
- 53cc83f: a large buffer is backed by several direct-memory ranges when no single one is free;
- 249fe49: a piece of such a buffer is mapped only where nothing else is;
- f5610fe: a freed buffer keeps its memory until the GPU has run what was submitted before, and an
  allocation that fails waits for the GPU and tries again before reporting out of memory.
Applied to the driver checkout after patch-radv-transfer-split.py; running it again changes nothing.
"""
from pathlib import Path
import hashlib
import subprocess
import sys
import time
import re
import shutil
import tempfile


def memory_checks(src):
    """Check the code, not the receipt: an old stamp survived missing layers."""
    folder = src / 'src/amd/vulkan/winsys/ps5'
    platform = (folder / 'radv_ps5_platform.c').read_text()
    header = (folder / 'radv_ps5_platform.h').read_text()
    bo = (folder / 'radv_ps5_bo.c').read_text()
    return [
        all(token in platform for token in (
            '&& radv_ps5_memory_alloc_chunked(bytes, alignment, out)',
            'radv_ps5_chunks_release', 'if (memory->chunks)',
        )) and 'chunk_count' in header,
        'radv_ps5_map_free_at' in platform and
        'if (!radv_ps5_map_free_at(base + offset, take, physical))' in platform,
        'radv_ps5_retired_wait' in bo and
        '} while (!allocated && radv_ps5_retired_wait(ws->queue));' in bo,
    ]

here = Path(__file__).resolve()
patches = sorted((here.parent / 'radv-patches').glob('*.diff'))
digest = hashlib.sha256(here.read_bytes())
for patch in patches:
    digest.update(patch.read_bytes())
fingerprint = digest.hexdigest()
if sys.argv[1:2] == ['--digest']:
    print(fingerprint)
    raise SystemExit(0)
if sys.argv[1:2] == ['--check']:
    stamp = Path(sys.argv[2])
    src = here.parents[2] / 'mihawk-vulkan-review/.deps/work/radv-src'
    try:
        valid = stamp.is_file() and stamp.read_text().strip() == fingerprint and all(memory_checks(src))
    except OSError:
        valid = False
    raise SystemExit(0 if valid else 1)

root = here.parents[1]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else root.parent / 'mihawk-vulkan-review/.deps/work/radv-src'
assert len(patches) == 3, 'tools/radv-patches changed'
applied = src / '.eden-ps5-memory-applied'
changed = False
relative = Path('src/amd/vulkan/winsys/ps5')
names = ['radv_ps5_platform.c', 'radv_ps5_platform.h', 'radv_ps5_bo.c']
# An old failed application left the header patched but its C implementation
# unpatched. Repair per file, validating every layer in a scratch tree first.
# A changed/unknown hunk leaves all production files untouched.
with tempfile.TemporaryDirectory(prefix='eden-radv-memory-repair-') as folder:
    staged = Path(folder)/'source'
    (staged/relative).mkdir(parents=True)
    for name in names:
        shutil.copy2(src/relative/name, staged/relative/name)
    for index, patch in enumerate(patches):
        if memory_checks(staged)[index]:
            continue
        sections = [part for part in re.split(r'(?=^diff --git )', patch.read_text(), flags=re.M)
                    if part.startswith('diff --git ')]
        assert sections, patch
        for part in sections:
            fragment = Path(folder)/'part.diff'
            fragment.write_text(part)
            command = ['patch', '-d', str(staged), '-p1', '-s', '-f', '--no-backup-if-mismatch', '-i', str(fragment)]
            if subprocess.run(command + ['-N', '--dry-run'], capture_output=True).returncode == 0:
                subprocess.run(command + ['-N'], check=True)
            elif subprocess.run(command + ['-R', '--dry-run'], capture_output=True).returncode != 0:
                raise RuntimeError(f'Unknown partial RADV layer: {patch.name}: {part.splitlines()[0]}')
        assert memory_checks(staged)[index], f'RADV memory layer {patch.name} did not establish its invariants'
    assert all(memory_checks(staged)), 'RADV memory source is incomplete'
    for name in names:
        destination = src/relative/name
        if destination.read_bytes() != (staged/relative/name).read_bytes():
            temporary = destination.with_name(destination.name+'.memory-repair-pending')
            shutil.copy2(staged/relative/name, temporary)
            temporary.replace(destination)
            changed = True
if changed or not applied.is_file() or applied.read_text().strip() != fingerprint:
    # As patch-radv-disk-cache.py: set the receipt aside so the next build compiles what changed.
    provenance = root.parent / 'mihawk-vulkan-review/.deps/native/radv-release/PROVENANCE.txt'
    if provenance.exists():
        provenance.rename(provenance.with_name('PROVENANCE.before-memory-' + str(time.time_ns()) + '.txt'))
    applied.write_text(fingerprint + '\n')
print(f'RADV PS5 memory fixes: {len(patches)} verified, repaired={changed}')
