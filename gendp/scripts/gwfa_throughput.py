#!/usr/bin/env python3
"""
GWFA Throughput Script - Measure aggregate simulator cycles for GWFA dataset.
Usage: python3 scripts/gwfa_throughput.py <mode> [-t N]
  mode 1: fast (15 cases)
  mode 2: full (all cases in dataset)
  -t N:   run N simulator processes in parallel (default 1)

Cycle source: each per-case './sim -k 7' run prints 'cycle <N>' on stdout
(see pe_array.cpp:9920  printf("cycle %d\\n", cycle);). We regex-match
r'cycle\\s+(\\d+)' and aggregate across cases. Mirrors the pattern in
scripts/wfa_throughput.py:43.

Note: scripts/gwfa_check_correctness.py validates correctness but does NOT
extract cycles; this script is the cycle-metric source.
"""

import sys
import os
import re
import subprocess
import tempfile
import concurrent.futures
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent  # gendp/
DUMP_DIR = Path('/data4/kaplannp/GenDP2/kernel/Gwfa/Datasets/Gwfa295')
SIM_PATH = REPO_ROOT / 'sim'

MODES = {
    '1': {'name': 'fast', 'n': 15},
    '2': {'name': 'full', 'n': -1},
}

# Files the simulator reads from the input directory (one line per case)
DATA_FILES = [
    'ql.txt', 'q.txt', 's_term.txt', 'n_vtx.txt', 'n_arc.txt',
    'graphSeq.txt', 'seq_off.txt', 'seq_len.txt',
    'arc_v.txt', 'arc_w.txt', 'arc_ow.txt', 'idx.txt',
]


# Load the first n lines from each DATA_FILE; n<=0 means all lines.
def load_dataset_lines(path, n):
    data = {}
    for fname in DATA_FILES:
        lines = []
        with open(path / fname) as f:
            for i, line in enumerate(f):
                if n > 0 and i >= n:
                    break
                lines.append(line.rstrip('\n'))
        data[fname] = lines
    return data


# Run simulator for one case in a temp directory.
# Returns (case_idx, cycles or None, score or None).
def run_single_case(args):
    case_idx, case_lines = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, line in case_lines.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                f.write(line + '\n')
        cmd = [str(SIM_PATH), '-k', '7', '-i', tmpdir, '-n', '1']
        try:
            result = subprocess.run(
                cmd, cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True, timeout=3600)
        except subprocess.TimeoutExpired:
            print(f"  [{case_idx}] TIMEOUT")
            return (case_idx, None, None)
        if result.returncode != 0:
            print(f"  [{case_idx}] sim exited with code {result.returncode}")
            return (case_idx, None, None)
        cm = re.search(r'cycle\s+(\d+)', result.stdout)
        sm = re.search(r'qqq (-?\d+) qqq', result.stdout)
        cycles = int(cm.group(1)) if cm else None
        score = int(sm.group(1)) if sm else None
        return (case_idx, cycles, score)


# Parse mode and optional -t <numThreads>.
def parse_args():
    mode_key = None
    num_threads = 1
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '-t':
            if i + 1 >= len(args):
                print("ERROR: -t requires a number")
                sys.exit(1)
            num_threads = int(args[i + 1])
            i += 2
        else:
            mode_key = args[i]
            i += 1
    return mode_key, num_threads


def main():
    mode_key, num_threads = parse_args()
    if mode_key not in MODES:
        print("Usage: python3 scripts/gwfa_throughput.py <1|2> [-t N]")
        print("  1: fast (15 cases)")
        print("  2: full (all cases)")
        print("  -t N: parallel with N processes")
        sys.exit(1)

    mode = MODES[mode_key]
    print(f"=== GWFA throughput {mode['name']} mode ===")

    if not SIM_PATH.exists():
        print(f"ERROR: simulator not found at {SIM_PATH}. Build with 'make'.")
        sys.exit(1)
    if not DUMP_DIR.exists():
        print(f"ERROR: GWFA dataset not found at {DUMP_DIR}.")
        sys.exit(1)

    # Load dataset
    dataset = load_dataset_lines(DUMP_DIR, mode['n'])
    n = len(dataset[DATA_FILES[0]])
    print(f"Loaded {n} cases from {DUMP_DIR}")

    tasks = [(i, {fname: dataset[fname][i] for fname in DATA_FILES}) for i in range(n)]

    print(f"Running {n} cases with {num_threads} thread(s)...")
    cycles_list = [None] * n
    scores_list = [None] * n
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = {pool.submit(run_single_case, t): t[0] for t in tasks}
        for fut in concurrent.futures.as_completed(futures):
            idx, cycles, score = fut.result()
            cycles_list[idx] = cycles
            scores_list[idx] = score
            done += 1
            if done % 10 == 0 or done == n:
                print(f"  progress: {done}/{n}")

    # Per-case detail (one short line per case)
    for i, (c, s) in enumerate(zip(cycles_list, scores_list)):
        c_str = str(c) if c is not None else "MISSING"
        s_str = str(s) if s is not None else "MISSING"
        print(f"  case {i}: cycles={c_str}, score={s_str}")

    # Surface any cases that produced no cycle line
    bad = [i for i, c in enumerate(cycles_list) if c is None]
    if bad:
        head = bad[:10]
        ellipsis = '...' if len(bad) > 10 else ''
        print(f"WARNING: {len(bad)} case(s) had no cycle line: {head}{ellipsis}")

    valid_cycles = [c for c in cycles_list if c is not None]

    print()
    print("=" * 50)
    if not valid_cycles:
        print("No valid cycle measurements collected.")
        sys.exit(1)
    print(f"Cases measured: {len(valid_cycles)}/{n}")
    print(f"Aggregate cycles: {sum(valid_cycles)}")
    print(f"Min per-case cycles: {min(valid_cycles)}")
    print(f"Max per-case cycles: {max(valid_cycles)}")
    print(f"Avg per-case cycles: {sum(valid_cycles) / len(valid_cycles):.1f}")
    print("=" * 50)

    # Exit nonzero if any case was missing a cycle measurement, so CI/scripts
    # can detect partial measurements.
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
