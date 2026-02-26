#!/usr/bin/env python3
"""
GWFA Correctness Check - Compare simulator vs golden scores.
Usage: python3 scripts/gwfa_check_correctness.py <mode>
  mode 1: fast  (15 iterations)
  mode 2: full  (all iterations)
  mode 3: debug (single iteration, verbose)

Prereqs:
  - Build sim: make clean && make -j
  - Golden scores at kernel/Gwfa/Datasets/Gwfa295/trueScores.txt
"""

import sys
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent  # gendp/
KERNEL_DIR = REPO_ROOT / 'kernel' / 'Gwfa'
DUMP_DIR = KERNEL_DIR / 'Datasets' / 'Gwfa295'
GOLDEN_SCORES = DUMP_DIR / 'trueScores.txt'
SIM_PATH = REPO_ROOT / 'sim'

MODES = {
    '1': {'name': 'fast',  'n': 15},
    '2': {'name': 'full',  'n': -1},
    '3': {'name': 'debug', 'n': 1},
}


def load_golden(path, limit=None):
    scores = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                scores.append(int(line))
    if limit and limit > 0:
        scores = scores[:limit]
    return scores


def run_sim(n, verbose=False):
    """Run simulator, return list of scores parsed
    from stdout 'qqq <score> qqq' lines."""
    cmd = [
        str(SIM_PATH), '-k', '7',
        '-i', str(DUMP_DIR),
        '-n', str(n),
    ]
    stderr_dest = None if verbose else subprocess.DEVNULL
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=stderr_dest,
        text=True, timeout=3600)
    if result.returncode != 0:
        print(f"ERROR: simulator exited with code "
              f"{result.returncode}")
        sys.exit(1)
    scores = [
        int(m.group(1))
        for m in re.finditer(r'qqq (-?\d+) qqq',
                             result.stdout)
    ]
    return scores


def main():
    if len(sys.argv) < 2 or \
       sys.argv[1] not in MODES:
        print("Usage: python3 "
              "scripts/gwfa_check_correctness.py "
              "<1|2|3>")
        print("  1: fast (15 iterations)")
        print("  2: full (all iterations)")
        print("  3: debug (1 iteration, verbose)")
        sys.exit(1)

    mode = MODES[sys.argv[1]]
    verbose = sys.argv[1] == '3'
    n = mode['n']
    print(f"=== GWFA {mode['name']} mode ===")

    if not GOLDEN_SCORES.exists():
        print(f"Golden scores not found at "
              f"{GOLDEN_SCORES}")
        print("Expected at: "
              "kernel/Gwfa/Datasets/Gwfa295/"
              "trueScores.txt")
        sys.exit(1)

    golden = load_golden(GOLDEN_SCORES)
    if n > 0:
        golden = golden[:n]
    else:
        n = len(golden)

    sim_scores = run_sim(n, verbose)

    if len(sim_scores) != len(golden):
        print(f"ERROR: score count mismatch: "
              f"sim={len(sim_scores)} "
              f"golden={len(golden)}")
        sys.exit(1)

    passed = 0
    failed = 0
    for i, (s, g) in enumerate(
            zip(sim_scores, golden)):
        if s == g:
            passed += 1
            if verbose:
                print(f"  [{i}] PASS score={s}")
        else:
            failed += 1
            print(f"  [{i}] FAIL "
                  f"sim={s} golden={g}")

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, "
          f"{failed} failed out of {n}")
    print("=" * 50)

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
