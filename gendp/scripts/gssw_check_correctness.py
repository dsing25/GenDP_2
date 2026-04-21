#!/usr/bin/env python3
"""
GSSW Correctness Check — Compare simulator vs golden scores.
Usage: python3 scripts/gssw_check_correctness.py <mode> [-t N]
  mode 1: fast  (15 iterations)
  mode 2: full  (all iterations)
  -t N:  run N simulator processes in parallel

Prereqs:
  - Build sim: make clean && make -j
  - Generate instructions: python3 scripts/gssw_instruction_generator.py
  - Golden scores at kernel/Gssw/src/Dataset/trueScores.txt
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
KERNEL_DIR = REPO_ROOT / 'kernel' / 'Gssw'
DUMP_DIR = KERNEL_DIR / 'src' / 'Dataset'
GOLDEN_SCORES = DUMP_DIR / 'trueScores.txt'
SIM_PATH = REPO_ROOT / 'sim'

MODES = {
    '1': {'name': 'fast',  'n': 1000},
    '2': {'name': 'full',  'n': -1},
}

# Lines per entry in each dataset file
LINES_PER_ENTRY = {
    'graph.soa': 4,          # header, nodes, nexts, seqs
    'matchProfiles.txt': 5,  # readLen, 4 nucleotide rows
    'readNFilter.txt': 1,    # 0 or 1
}

# Pinned regression cases that have historically exposed
# simulator bugs. Run these every invocation regardless of mode.
# (dataset_index, expected_score)
REGRESSION_CASES = [
    (5178,   50),
    (54989,  22),
    (60726,  48),
    (141509, 44),
]


def load_golden(path, limit=None):
    """Load golden scores (one per line)."""
    scores = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                scores.append(int(line))
    if limit and limit > 0:
        scores = scores[:limit]
    return scores


def run_sim(n):
    """Run simulator sequentially for n entries."""
    cmd = [
        str(SIM_PATH), '-k', '8',
        '-i', str(DUMP_DIR),
        '-n', str(n),
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True, timeout=3600)
    if result.returncode != 0:
        print(f"ERROR: simulator exited with code "
              f"{result.returncode}")
        if result.stdout:
            print("STDOUT:", result.stdout[-2000:])
        sys.exit(1)
    return [
        int(m.group(1))
        for m in re.finditer(r'qqq (-?\d+) qqq',
                             result.stdout)
    ]


def load_dataset_entries(path, n):
    """Load first n entries from each dataset file.
    Returns {filename: [entry0_lines, entry1_lines, ...]}
    where each entry is a string (possibly multi-line)."""
    data = {}
    for fname, lpe in LINES_PER_ENTRY.items():
        entries = []
        with open(path / fname) as f:
            # Skip header line for files that have one
            if fname in ('graph.soa', 'matchProfiles.txt'):
                f.readline()
            for i in range(n):
                lines = []
                for _ in range(lpe):
                    l = f.readline()
                    if not l:
                        break
                    lines.append(l.rstrip('\n'))
                if len(lines) == lpe:
                    entries.append('\n'.join(lines))
                else:
                    break
        data[fname] = entries
    return data


def load_dataset_entry_at(idx):
    """Return {filename: entry_string} for a single dataset index."""
    entries = {}
    for fname, lpe in LINES_PER_ENTRY.items():
        with open(DUMP_DIR / fname) as f:
            if fname in ('graph.soa', 'matchProfiles.txt'):
                f.readline()  # skip count header
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


def run_regression_cases():
    """Run the pinned regression indices. Returns (passed, failed, errors)."""
    print()
    print("=== Regression cases ===")
    passed = failed = errors = 0
    for idx, expected in REGRESSION_CASES:
        try:
            entry = load_dataset_entry_at(idx)
        except Exception as e:
            print(f"  [{idx}] ERROR loading: {e}")
            errors += 1
            continue
        _, score = run_single_case((idx, entry))
        if score is None:
            errors += 1
            continue
        if score == expected:
            print(f"  [{idx}] OK   sim={score} expected={expected}")
            passed += 1
        else:
            print(f"  [{idx}] FAIL sim={score} expected={expected}")
            failed += 1
    print(f"Regression: {passed} passed, {failed} failed"
          + (f", {errors} errors" if errors else ""))
    return passed, failed, errors


def run_single_case(args):
    """Run simulator for one case in a temp directory.
    Returns (case_idx, score or None)."""
    case_idx, case_entries = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, entry in case_entries.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                # Write header (count=1) for files that need it
                if fname in ('graph.soa',
                             'matchProfiles.txt'):
                    f.write('1\n')
                f.write(entry + '\n')
        cmd = [
            str(SIM_PATH), '-k', '8',
            '-i', tmpdir, '-n', '1',
        ]
        try:
            result = subprocess.run(
                cmd, cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True, timeout=3600)
        except subprocess.TimeoutExpired:
            print(f"  [{case_idx}] TIMEOUT")
            return (case_idx, None)
        if result.returncode != 0:
            print(f"  [{case_idx}] sim exited with "
                  f"code {result.returncode}")
            return (case_idx, None)
        m = re.search(r'qqq (-?\d+) qqq', result.stdout)
        if not m:
            print(f"  [{case_idx}] no score in output")
            return (case_idx, None)
        return (case_idx, int(m.group(1)))


def run_sim_parallel(n, num_threads):
    """Run n cases in parallel, return list of scores."""
    print(f"Loading dataset for {n} cases...")
    dataset = load_dataset_entries(DUMP_DIR, n)
    actual_n = min(len(v) for v in dataset.values())
    if actual_n < n:
        print(f"WARNING: only {actual_n} cases in dataset")
        n = actual_n

    tasks = []
    for i in range(n):
        case_entries = {
            fname: dataset[fname][i]
            for fname in LINES_PER_ENTRY
        }
        tasks.append((i, case_entries))

    print(f"Running {n} cases with "
          f"{num_threads} threads...")
    scores = [None] * n
    done = 0
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_threads) as pool:
        futures = {
            pool.submit(run_single_case, t): t[0]
            for t in tasks
        }
        for fut in concurrent.futures.as_completed(futures):
            idx, score = fut.result()
            scores[idx] = score
            done += 1
            if done % 1000 == 0 or done == n:
                print(f"  progress: {done}/{n}")
    return scores


def parse_args():
    """Parse mode and optional -t <numThreads>."""
    mode_key = None
    num_threads = None
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
        print("Usage: python3 "
              "scripts/gssw_check_correctness.py "
              "<1|2> [-t N]")
        print("  1: fast (15 iterations)")
        print("  2: full (all iterations)")
        print("  -t N: parallel with N processes")
        sys.exit(1)

    mode = MODES[mode_key]
    print(f"=== GSSW {mode['name']} mode ===")

    if not GOLDEN_SCORES.exists():
        print(f"Golden scores not found at "
              f"{GOLDEN_SCORES}")
        sys.exit(1)

    golden = load_golden(GOLDEN_SCORES)
    n = mode['n']
    if n <= 0:
        graph_soa = DUMP_DIR / 'graph.soa'
        with open(graph_soa) as f:
            n = int(f.readline().strip())
    print(f"Running {n} iterations...")

    # Run sim: parallel or sequential
    if num_threads:
        sim_scores = run_sim_parallel(n, num_threads)
    else:
        sim_scores = run_sim(n)
    print(f"Got {len(sim_scores)} scores from simulator")

    # -1 = N-filtered (no golden entry exists)
    # -2 = too large for SPM (golden entry exists, skip it)
    # None = error in parallel mode
    g_idx = 0
    passed = 0
    failed = 0
    n_skipped = 0
    size_skipped = 0
    errors = 0
    for i, s in enumerate(sim_scores):
        if s is None:
            errors += 1
            continue
        if s == -1:
            n_skipped += 1
            continue
        if s == -2:
            size_skipped += 1
            g_idx += 1
            continue
        if g_idx >= len(golden):
            failed += 1
            print(f"  [{i}] FAIL sim={s} "
                  f"golden=<exhausted>")
            continue
        g = golden[g_idx]
        g_idx += 1
        if s == g:
            passed += 1
        else:
            failed += 1
            print(f"  [{i}] FAIL sim={s} golden={g}")

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, "
          f"{failed} failed, "
          f"{n_skipped} N-skipped, "
          f"{size_skipped} size-skipped"
          + (f", {errors} errors" if errors else ""))
    print(f"Golden consumed: {g_idx}/{len(golden)}")
    print("=" * 50)

    # Always run the pinned regression cases on top of the
    # mode's batch. Their pass/fail folds into the exit code.
    r_passed, r_failed, r_errors = run_regression_cases()

    sys.exit(1 if (failed or errors or r_failed or r_errors) else 0)


if __name__ == '__main__':
    main()
