#!/usr/bin/env python3
"""
GWFA Throughput Script - Measure aggregate simulator cycles for GWFA dataset.
Usage: python3 scripts/gwfa_throughput.py <mode> [-t N] [--soft-timeout S]
  mode 1: fast (15 cases)
  mode 2: full (all cases in dataset)
  -t N:           run N simulator processes in parallel (default 1)
  --soft-timeout S: per-case wall budget; when exceeded the sim is
                  killed and the last 'progress cycle=X dist=Y' line is
                  reported as the partial result (default 30s).

Cycle source: each per-case './sim -k 7' run prints 'cycle <N>' on stdout
(see pe_array.cpp 'cycle %d'). We also enable GWFA_PROGRESS so the sim
emits periodic 'progress cycle=X dist=Y' lines that survive a SIGTERM,
allowing partial measurement of long-running queries.
"""

import sys
import os
import re
import subprocess
import tempfile
import time
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

# Sim emits 'progress cycle=X dist=Y' every PROGRESS_PERIOD cycles when
# GWFA_PROGRESS is set. 100k keeps overhead negligible while giving
# sub-second resolution on partial-cycle reports.
PROGRESS_PERIOD = 100000
DEFAULT_SOFT_TIMEOUT = 30  # seconds

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
# Returns (case_idx, cycles, score, partial) where partial is True if the
# sim was SIGTERM'd at the soft timeout and we only have a progress-line
# snapshot. cycles/score are None only on hard failure (no cycle line and
# no progress line ever emitted).
def run_single_case(args, soft_timeout=DEFAULT_SOFT_TIMEOUT):
    case_idx, case_lines = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, line in case_lines.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                f.write(line + '\n')
        cmd = [str(SIM_PATH), '-k', '7', '-i', tmpdir, '-n', '1']
        env = dict(os.environ)
        env['GWFA_PROGRESS'] = str(PROGRESS_PERIOD)

        last_cycle = None  # last 'progress cycle=' value
        last_dist = None
        final_cycle = None  # final 'cycle <N>' value (only on natural exit)
        score = None
        timed_out = False
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True, bufsize=1, env=env)
        start = time.time()
        try:
            while True:
                # Bail out if soft-timeout has elapsed
                remaining = soft_timeout - (time.time() - start)
                if remaining <= 0:
                    timed_out = True
                    break
                line = proc.stdout.readline()
                if not line:
                    break  # sim exited
                m = re.match(r'progress cycle=(\d+) dist=(-?\d+)', line)
                if m:
                    last_cycle = int(m.group(1))
                    last_dist = int(m.group(2))
                    continue
                m = re.match(r'cycle\s+(\d+)', line)
                if m:
                    final_cycle = int(m.group(1))
                    continue
                m = re.match(r'qqq (-?\d+) qqq', line)
                if m:
                    score = int(m.group(1))
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            if proc.stdout:
                proc.stdout.close()

        if timed_out:
            print(f"  [{case_idx}] TIMEOUT after {soft_timeout}s "
                  f"partial cycles={last_cycle} dist={last_dist}")
            return (case_idx, last_cycle, last_dist, True)
        cycles = final_cycle if final_cycle is not None else last_cycle
        if cycles is None and score is None:
            print(f"  [{case_idx}] sim exited "
                  f"with no measurement (rc={proc.returncode})")
            return (case_idx, None, None, False)
        return (case_idx, cycles, score, False)


# Parse mode, optional -t <numThreads>, --soft-timeout <S>.
def parse_args():
    mode_key = None
    num_threads = 1
    soft_timeout = DEFAULT_SOFT_TIMEOUT
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '-t':
            if i + 1 >= len(args):
                print("ERROR: -t requires a number")
                sys.exit(1)
            num_threads = int(args[i + 1])
            i += 2
        elif args[i] == '--soft-timeout':
            if i + 1 >= len(args):
                print("ERROR: --soft-timeout requires seconds")
                sys.exit(1)
            soft_timeout = int(args[i + 1])
            i += 2
        else:
            mode_key = args[i]
            i += 1
    return mode_key, num_threads, soft_timeout


def main():
    mode_key, num_threads, soft_timeout = parse_args()
    if mode_key not in MODES:
        print("Usage: python3 scripts/gwfa_throughput.py <1|2> "
              "[-t N] [--soft-timeout S]")
        print("  1: fast (15 cases)")
        print("  2: full (all cases)")
        print("  -t N: parallel with N processes")
        print(f"  --soft-timeout S: kill case after S seconds and "
              f"report partial cycles (default {DEFAULT_SOFT_TIMEOUT})")
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

    print(f"Running {n} cases with {num_threads} thread(s), "
          f"soft-timeout={soft_timeout}s...")
    cycles_list = [None] * n
    scores_list = [None] * n
    partial_list = [False] * n
    done = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = {pool.submit(run_single_case, t, soft_timeout): t[0]
                   for t in tasks}
        for fut in concurrent.futures.as_completed(futures):
            idx, cycles, score, partial = fut.result()
            cycles_list[idx] = cycles
            scores_list[idx] = score
            partial_list[idx] = partial
            done += 1
            if done % 10 == 0 or done == n:
                print(f"  progress: {done}/{n}")
    elapsed = time.time() - t0

    # Per-case detail (one short line per case)
    for i, (c, s, p) in enumerate(
            zip(cycles_list, scores_list, partial_list)):
        c_str = str(c) if c is not None else "MISSING"
        # On timeout, score column shows the WF distance reached
        # (extracted from the last 'progress dist=' line).
        s_str = str(s) if s is not None else "MISSING"
        tag = " PARTIAL" if p else ""
        print(f"  case {i}: cycles={c_str}, score={s_str}{tag}")

    # Surface any cases that produced no cycle line
    bad = [i for i, c in enumerate(cycles_list) if c is None]
    if bad:
        head = bad[:10]
        ellipsis = '...' if len(bad) > 10 else ''
        print(f"WARNING: {len(bad)} case(s) had no cycle line: "
              f"{head}{ellipsis}")
    timeouts = [i for i, p in enumerate(partial_list) if p]
    if timeouts:
        print()
        print(f"TIMEOUT >{soft_timeout}s ({len(timeouts)}):")
        print(f"  {timeouts}")

    valid_cycles = [c for c in cycles_list if c is not None]

    print()
    print("=" * 50)
    if not valid_cycles:
        print("No valid cycle measurements collected.")
        sys.exit(1)
    print(f"Wall: {elapsed:.1f}s")
    print(f"Cases measured: {len(valid_cycles)}/{n} "
          f"({len(timeouts)} partial)")
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
