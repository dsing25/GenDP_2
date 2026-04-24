#!/usr/bin/env python3
"""
GSSW Throughput — aggregate per-case performance counters over the dataset.

Usage:
  python3 scripts/gssw_throughput.py <mode> [-t N]
    mode 1: fast (1000 iterations)
    mode 2: full (entire dataset)
    -t N:   number of parallel sim processes (default: cpu_count())

Prereqs:
  - Build sim: make clean && make -j
  - Generate instructions: python3 scripts/gssw_instruction_generator.py
  - Dataset under /data4/kaplannp/GenDP2/kernel/Gssw/Dataset/
"""

import os
import re
import sys
import subprocess
import tempfile
import concurrent.futures
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
KERNEL_DIR = Path('/data4/kaplannp/GenDP2/kernel/Gssw')
DUMP_DIR = KERNEL_DIR / 'Dataset'
SIM_PATH = REPO_ROOT / 'sim'

MODES = {
    '1': {'name': 'fast', 'n': 1000},
    '2': {'name': 'full', 'n': -1},
}

# Lines per dataset entry (matches gssw_check_correctness.py)
LINES_PER_ENTRY = {
    'graph.soa': 4,
    'matchProfiles.txt': 5,
    'readNFilter.txt': 1,
}

# Counter keys printed by pe_array.cpp in the per-case block
COUNTER_KEYS = [
    'CaseCycles',
    'TotalSpmRequests',
    'PeCtrlHalted',
    'PeComputeHalted',
    'PeCtrlNops',
    'PeComputeNops',
    'BankConflictStalls',
    'LsqFullStalls',
    'SyncSpinBNEs',
    'ForwardableBankConflict',
]

# Number of PEs the kernel runs on; perf counters accumulate across PEs,
# so dividing by this gives a per-PE-per-case value.
NUM_PES = 4


def load_dataset_entries(path, n):
    """Load first n entries from each dataset file.
    Returns {filename: [entry0_str, entry1_str, ...]}."""
    data = {}
    for fname, lpe in LINES_PER_ENTRY.items():
        entries = []
        with open(path / fname) as f:
            if fname in ('graph.soa', 'matchProfiles.txt'):
                f.readline()  # skip count header
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


def parse_counters(stdout):
    """Extract the per-case counter block into a dict of int values."""
    vals = {}
    for k in COUNTER_KEYS:
        m = re.search(rf'^{k}:\s+(-?\d+)\s*$', stdout, re.MULTILINE)
        if m:
            vals[k] = int(m.group(1))
    return vals


def run_single_case(args):
    """Run one sim process for a single case.
    Returns (idx, score, counters_or_None)."""
    case_idx, case_entries = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, entry in case_entries.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                if fname in ('graph.soa', 'matchProfiles.txt'):
                    f.write('1\n')
                f.write(entry + '\n')
        cmd = [str(SIM_PATH), '-k', '8', '-i', tmpdir, '-n', '1']
        try:
            result = subprocess.run(cmd, cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=3600)
        except subprocess.TimeoutExpired:
            return (case_idx, None, None)
        if result.returncode != 0:
            return (case_idx, None, None)
        m = re.search(r'qqq (-?\d+) qqq', result.stdout)
        score = int(m.group(1)) if m else None
        counters = parse_counters(result.stdout)
        return (case_idx, score, counters)


def run_parallel(n, num_threads):
    """Run n cases in parallel. Returns list of (score, counters) tuples."""
    print(f"Loading dataset for {n} cases...")
    dataset = load_dataset_entries(DUMP_DIR, n)
    actual_n = min(len(v) for v in dataset.values())
    if actual_n < n:
        print(f"WARNING: only {actual_n} cases in dataset")
        n = actual_n

    tasks = []
    for i in range(n):
        case_entries = {fname: dataset[fname][i] for fname in LINES_PER_ENTRY}
        tasks.append((i, case_entries))

    print(f"Running {n} cases with {num_threads} threads...")
    results = [(None, None)] * n
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = {pool.submit(run_single_case, t): t[0] for t in tasks}
        for fut in concurrent.futures.as_completed(futures):
            idx, score, counters = fut.result()
            results[idx] = (score, counters)
            done += 1
            if done % 500 == 0 or done == n:
                print(f"  progress: {done}/{n}")
    return results


def parse_args():
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


def summarize(results):
    """Compute and print aggregate stats over usable cases."""
    # Filter: cases with real scores and parsed counters.
    # Sentinel scores (-1 N-filtered, -2 too-large) don't run the kernel;
    # their counters are trivial and would pollute averages.
    usable = []
    skipped_sentinel = 0
    errors = 0
    for score, counters in results:
        if score is None or counters is None:
            errors += 1
            continue
        if score in (-1, -2):
            skipped_sentinel += 1
            continue
        if not all(k in counters for k in COUNTER_KEYS):
            errors += 1
            continue
        usable.append(counters)

    n = len(usable)
    print()
    print("=" * 60)
    print("=== GSSW Throughput Summary ===")
    print(f"Total cases run: {len(results)}")
    print(f"Usable cases:    {n}")
    print(f"Sentinel skips:  {skipped_sentinel}")
    print(f"Errors:          {errors}")
    if n == 0:
        print("No usable cases — nothing to summarize.")
        print("=" * 60)
        return

    cycles = [c['CaseCycles'] for c in usable]
    spm = [c['TotalSpmRequests'] for c in usable]
    ctrl_halt = [c['PeCtrlHalted'] for c in usable]
    comp_halt = [c['PeComputeHalted'] for c in usable]
    ctrl_nops = [c['PeCtrlNops'] for c in usable]
    comp_nops = [c['PeComputeNops'] for c in usable]

    print()
    print(f"Avg cycles:           {sum(cycles) / n:.1f}")
    print(f"Min cycles:           {min(cycles)}")
    print(f"Max cycles:           {max(cycles)}")
    print(f"Total cycles:         {sum(cycles)}")
    print()
    print(f"Avg SPM requests:     {sum(spm) / n:.1f}")
    print()
    # Per-PE averages (counters accumulate across all NUM_PES PEs)
    print(f"Avg PE ctrl halted:   {sum(ctrl_halt) / n / NUM_PES:.1f}")
    print(f"Avg PE comp halted:   {sum(comp_halt) / n / NUM_PES:.1f}")
    print(f"Avg PE ctrl NOPs:     {sum(ctrl_nops) / n / NUM_PES:.1f}")
    print(f"Avg PE comp NOPs:     {sum(comp_nops) / n / NUM_PES:.1f}")
    print("=" * 60)


def main():
    mode_key, num_threads = parse_args()
    if mode_key not in MODES:
        print("Usage: python3 scripts/gssw_throughput.py <1|2> [-t N]")
        print("  1: fast (1000 cases)")
        print("  2: full (entire dataset)")
        print("  -t N: parallel processes (default: cpu_count())")
        sys.exit(1)
    if not SIM_PATH.exists():
        print(f"ERROR: sim not found at {SIM_PATH}. Run 'make -j' first.")
        sys.exit(1)

    mode = MODES[mode_key]
    print(f"=== GSSW throughput {mode['name']} mode ===")

    n = mode['n']
    if n <= 0:
        with open(DUMP_DIR / 'graph.soa') as f:
            n = int(f.readline().strip())
    if num_threads is None:
        num_threads = os.cpu_count() or 1

    results = run_parallel(n, num_threads)
    summarize(results)


if __name__ == '__main__':
    main()
