#!/usr/bin/env python3
"""Run GSSW simulator for a single dataset iteration index.

Usage: python3 scripts/gssw_run_one.py <index> [--keep]
  <index>   0-based dataset index (matches the [N] in check_correctness FAIL lines).
  --keep    Leave the temp dir in place and print its path (for debugging).

Prints: sim score (from 'qqq N qqq' line), and expected golden score.
Also prints the dataset contents for the iteration.
"""

import sys
import os
import re
import subprocess
import tempfile
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
KERNEL_DIR = Path('/data4/kaplannp/GenDP2/kernel/Gssw')
DUMP_DIR = KERNEL_DIR / 'Dataset'
GOLDEN_SCORES = DUMP_DIR / 'trueScores.txt'
SIM_PATH = REPO_ROOT / 'sim'

LINES_PER_ENTRY = {
    'graph.soa': 4,
    'matchProfiles.txt': 5,
    'readNFilter.txt': 1,
}
HAS_HEADER = {'graph.soa', 'matchProfiles.txt'}


def extract_entry(idx):
    """Return {filename: entry_text} for the idx-th entry."""
    entries = {}
    for fname, lpe in LINES_PER_ENTRY.items():
        with open(DUMP_DIR / fname) as f:
            if fname in HAS_HEADER:
                f.readline()  # skip count header
            # Skip idx entries
            for _ in range(idx):
                for _ in range(lpe):
                    f.readline()
            lines = []
            for _ in range(lpe):
                l = f.readline()
                if not l:
                    raise RuntimeError(
                        f"{fname} exhausted at idx {idx}")
                lines.append(l.rstrip('\n'))
            entries[fname] = '\n'.join(lines)
    return entries


def golden_at(idx):
    """Return expected score for dataset index idx.

    Golden score list is indexed by NON-skipped sim entries. To match the
    check script's failure indexing, we need to align sim outputs. The
    simplest: check_correctness prints the sim iteration index (same as
    dataset index) on the FAIL line, so idx IS the dataset index.

    But golden list only contains entries that weren't N-filtered. We'd
    need to walk the readNFilter to count prior N-skips.
    """
    nfilter_path = DUMP_DIR / 'readNFilter.txt'
    g_idx = 0
    with open(nfilter_path) as f:
        for i in range(idx):
            line = f.readline().strip()
            if line == '0':
                g_idx += 1
    with open(GOLDEN_SCORES) as f:
        lines = [l.strip() for l in f if l.strip()]
    if g_idx >= len(lines):
        return None
    return int(lines[g_idx])


def main():
    keep = False
    args = sys.argv[1:]
    if '--keep' in args:
        keep = True
        args.remove('--keep')
    if len(args) != 1:
        print(__doc__)
        sys.exit(1)
    idx = int(args[0])

    entries = extract_entry(idx)
    golden = golden_at(idx)

    # Set up temp dir
    if keep:
        tmpdir = tempfile.mkdtemp(prefix=f"gssw_one_{idx}_")
    else:
        tmp_ctx = tempfile.TemporaryDirectory()
        tmpdir = tmp_ctx.name

    try:
        for fname, entry in entries.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                if fname in HAS_HEADER:
                    f.write('1\n')
                f.write(entry + '\n')

        print(f"=== Dataset idx {idx} ===")
        for fname in LINES_PER_ENTRY:
            print(f"--- {fname} ---")
            print(entries[fname])
        print(f"--- expected golden: {golden} ---")
        print()

        cmd = [str(SIM_PATH), '-k', '8', '-i', tmpdir, '-n', '1']
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, timeout=300)
        print(result.stdout)

        m = re.search(r'qqq (-?\d+) qqq', result.stdout)
        sim_score = int(m.group(1)) if m else None

        print(f"=== sim={sim_score}  golden={golden} ===")
        if keep:
            print(f"temp dir: {tmpdir}")
    finally:
        if not keep:
            tmp_ctx.cleanup()


if __name__ == '__main__':
    main()
