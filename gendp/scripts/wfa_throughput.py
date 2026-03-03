#!/usr/bin/env python3
"""
WFA Throughput Script - Measure performance of GenDP WFA simulator
Usage: python scripts/wfa_throughput.py <seq_file> [options]
"""

import sys
import os
import subprocess
import re
import tempfile
from pathlib import Path

def read_seq_file(filename):
    """
    Read .seq file and return list of (pattern, text) tuples
    Format: >pattern then <text
    """
    pairs = []
    with open(filename, 'r') as f:
        lines = f.readlines()

    for i in range(0, len(lines), 2):
        if i+1 < len(lines):
            pattern = lines[i].strip()
            text = lines[i+1].strip()

            # Remove > and < prefixes
            if pattern.startswith('>'):
                pattern = pattern[1:]
            if text.startswith('<'):
                text = text[1:]

            pairs.append((pattern, text))

    return pairs


def run_simulator(pattern, text, sim_path='./sim_o3', verbose=False):
    """
    Run the GenDP simulator with given pattern and text
    Returns dict with performance metrics
    """
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False,
                                         suffix='.seq') as tmp:
            temp_path = tmp.name
            tmp.write(f">{pattern}\n")
            tmp.write(f"<{text}\n")

        # Run simulator
        cmd = [sim_path, '-k', '5', '-i', temp_path,
               '-o', '/dev/null', '-s', '-n', '1']

        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, timeout=3600)

        if verbose:
            print("Simulator output:", result.stdout)

        # Parse performance metrics
        metrics = {}

        # Extract cycle count
        cycle_match = re.search(r'cycle\s+(\d+)', result.stdout)
        if cycle_match:
            metrics['cycles'] = int(cycle_match.group(1))

        # Extract performance counters
        spm_match = re.search(r'TotalSpmRequests:\s+(\d+)', result.stdout)
        if spm_match:
            metrics['spm_requests'] = int(spm_match.group(1))

        conflict_match = re.search(r'BankConflictStalls:\s+(\d+)', result.stdout)
        if conflict_match:
            metrics['bank_conflicts'] = int(conflict_match.group(1))

        lsq_match = re.search(r'LsqFullStalls:\s+(\d+)', result.stdout)
        if lsq_match:
            metrics['lsq_stalls'] = int(lsq_match.group(1))

        halted_match = re.search(r'PeHalted:\s+(\d+)', result.stdout)
        if halted_match:
            metrics['pe_halted'] = int(halted_match.group(1))

        fwd_match = re.search(
            r'ForwardableBankConflict:\s+(\d+)', result.stdout)
        if fwd_match:
            metrics['fwd_conflicts'] = int(fwd_match.group(1))

        spin_match = re.search(
            r'SyncSpinBNEs:\s+(\d+)', result.stdout)
        if spin_match:
            metrics['sync_spins'] = int(spin_match.group(1))

        return metrics

    except subprocess.TimeoutExpired:
        print(f"ERROR: Simulator timed out")
        return None
    except Exception as e:
        print(f"ERROR: Simulator failed: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/wfa_throughput.py <seq_file> [-v] [-n N]")
        print("  <seq_file>  : Path to .seq file with test sequences")
        print("  -v          : Verbose mode (show debug output)")
        print("  -n N        : Only test first N sequence pairs")
        sys.exit(1)

    seq_file = sys.argv[1]
    verbose = '-v' in sys.argv

    # Parse -n option
    limit = None
    if '-n' in sys.argv:
        n_idx = sys.argv.index('-n')
        if n_idx + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[n_idx + 1])
            except ValueError:
                print("ERROR: -n requires an integer argument")
                sys.exit(1)

    # Check if sim_o3 exists
    if not os.path.exists('./sim_o3'):
        print("ERROR: sim_o3 not found. Please build it first with 'make sim_o3'")
        sys.exit(1)

    # Read sequence pairs
    print(f"Reading sequences from: {seq_file}")
    pairs = read_seq_file(seq_file)

    if limit:
        pairs = pairs[:limit]
        print(f"Testing first {limit} sequence pairs")
    else:
        print(f"Testing {len(pairs)} sequence pairs")

    print()

    # Collect metrics for all runs
    all_cycles = []
    all_spm_requests = []
    all_bank_conflicts = []
    all_lsq_stalls = []
    all_pe_halted = []
    all_fwd_conflicts = []
    all_sync_spins = []

    for i, (pattern, text) in enumerate(pairs):
        metrics = run_simulator(pattern, text, verbose=verbose)

        if metrics is None:
            print(f"Run {i+1}/{len(pairs)}: ERROR")
            sys.exit(1)

        cycles = metrics.get('cycles', 0)
        spm_req = metrics.get('spm_requests', 0)
        conflicts = metrics.get('bank_conflicts', 0)
        lsq = metrics.get('lsq_stalls', 0)
        halted = metrics.get('pe_halted', 0)
        fwd = metrics.get('fwd_conflicts', 0)
        spins = metrics.get('sync_spins', 0)

        print(
            f"Run {i+1}/{len(pairs)}: cycles={cycles}, "
            f"SPM_req={spm_req}, conflicts={conflicts}, "
            f"fwd_conflicts={fwd}, LSQ_stalls={lsq}, "
            f"PE_halted={halted/4:.2f}, "
            f"sync_spins={spins}")

        all_cycles.append(cycles)
        all_spm_requests.append(spm_req)
        all_bank_conflicts.append(conflicts)
        all_lsq_stalls.append(lsq)
        all_pe_halted.append(halted)
        all_fwd_conflicts.append(fwd)
        all_sync_spins.append(spins)

    # Print summary statistics
    print()
    print("=" * 60)
    print("=== Summary ===")
    print(f"Total runs: {len(pairs)}")

    if all_cycles:
        print(f"Avg cycles: {sum(all_cycles)/len(all_cycles):.1f}")
        print(f"Min cycles: {min(all_cycles)}")
        print(f"Max cycles: {max(all_cycles)}")
        print(f"Total cycles: {sum(all_cycles)}")

    if all_spm_requests:
        print(f"Avg SPM requests: {sum(all_spm_requests)/len(all_spm_requests):.1f}")

    if all_bank_conflicts:
        print(f"Avg bank conflicts: {sum(all_bank_conflicts)/len(all_bank_conflicts):.1f}")

    if all_fwd_conflicts:
        avg = sum(all_fwd_conflicts)/len(all_fwd_conflicts)
        print(f"Avg fwd conflicts: {avg:.1f}")

    if all_lsq_stalls:
        avg = sum(all_lsq_stalls)/len(all_lsq_stalls)
        print(f"Avg LSQ stalls: {avg:.1f}")

    if all_pe_halted:
        avg = sum(all_pe_halted)/len(all_pe_halted)/4
        print(f"Avg PE halted: {avg:.2f}")

    if all_sync_spins:
        avg = sum(all_sync_spins)/len(all_sync_spins)
        print(f"Avg sync spins: {avg:.1f}")

    print("=" * 60)


if __name__ == '__main__':
    main()
