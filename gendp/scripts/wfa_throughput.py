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
from concurrent.futures import ThreadPoolExecutor, as_completed

def read_seq_file(filename):
    pairs = []
    with open(filename, 'r') as f:
        lines = f.readlines()
    for i in range(0, len(lines), 2):
        if i+1 < len(lines):
            pattern = lines[i].strip()
            text = lines[i+1].strip()
            if pattern.startswith('>'):
                pattern = pattern[1:]
            if text.startswith('<'):
                text = text[1:]
            pairs.append((pattern, text))
    return pairs


def run_simulator(idx, pattern, text, sim_path='./sim_o3', verbose=False):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.seq') as tmp:
            temp_path = tmp.name
            tmp.write(f">{pattern}\n")
            tmp.write(f"<{text}\n")
        cmd = [sim_path, '-k', '5', '-i', temp_path, '-o', '/dev/null', '-s', '-n', '1']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3600)
        if verbose:
            print("Simulator output:", result.stdout)
        metrics = {}
        for name, pat in [
            ('cycles',         r'cycle\s+(\d+)'),
            ('spm_requests',   r'TotalSpmRequests:\s+(\d+)'),
            ('bank_conflicts', r'BankConflictStalls:\s+(\d+)'),
            ('lsq_stalls',     r'LsqFullStalls:\s+(\d+)'),
            ('pe_halted',      r'PeHalted:\s+(\d+)'),
            ('fwd_conflicts',  r'ForwardableBankConflict:\s+(\d+)'),
            ('sync_spins',     r'SyncSpinBNEs:\s+(\d+)'),
            ('pe_comp_halted', r'PeCompHalted:\s+(\d+)'),
            ('pe_ctrl_nops',   r'PeCtrlNops:\s+(\d+)'),
            ('pe_comp_nops',   r'PeCompNops:\s+(\d+)'),
            ('controller_nops',
                r'ControllerNops:\s+(\d+)'),
            ('extend_match_iters',
                r'PeExtendMatchIters:\s+(\d+)'),
            ('extend_diags',
                r'PeExtendDiags:\s+(\d+)'),
        ]:
            m = re.search(pat, result.stdout)
            if m:
                metrics[name] = int(m.group(1))
        score_match = re.search(r'qqq (\d+) qqq', result.stdout)
        if score_match:
            metrics['score'] = int(score_match.group(1))
        return idx, metrics
    except subprocess.TimeoutExpired:
        return idx, None
    except Exception as e:
        print(f"ERROR: Simulator failed on pair {idx}: {e}")
        return idx, None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/wfa_throughput.py <seq_file> [-v] [-n N]")
        sys.exit(1)

    seq_file = sys.argv[1]
    verbose = '-v' in sys.argv

    limit = None
    if '-n' in sys.argv:
        n_idx = sys.argv.index('-n')
        if n_idx + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[n_idx + 1])
            except ValueError:
                print("ERROR: -n requires an integer argument")
                sys.exit(1)

    if not os.path.exists('./sim_o3'):
        print("ERROR: sim_o3 not found. Build with 'make sim_o3'")
        sys.exit(1)

    print(f"Reading sequences from: {seq_file}")
    pairs = read_seq_file(seq_file)
    if limit:
        pairs = pairs[:limit]
    print(f"Testing {len(pairs)} sequence pairs")

    scores_file = os.path.splitext(seq_file)[0] + '.scores'
    golden_scores = None
    if os.path.exists(scores_file):
        with open(scores_file, 'r') as sf:
            golden_scores = [int(line.strip()) for line in sf if line.strip()]
        if limit:
            golden_scores = golden_scores[:limit]

    n_workers = os.cpu_count() or 1
    print(f"Using {n_workers} threads\n")

    results = [None] * len(pairs)
    errors = False

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(run_simulator, i, p, t, verbose=verbose): i
            for i, (p, t) in enumerate(pairs)
        }
        done = 0
        for future in as_completed(futures):
            idx, metrics = future.result()
            results[idx] = metrics
            done += 1
            if metrics is None:
                print(f"  [{done}/{len(pairs)}] Run {idx+1}: ERROR")
                errors = True
            else:
                c = metrics.get('cycles', 0)
                print(f"  [{done}/{len(pairs)}] Run {idx+1}: cycles={c}")

    if errors:
        print("\nSome runs failed.")
        sys.exit(1)

    keys = ['cycles', 'spm_requests', 'bank_conflicts',
            'lsq_stalls', 'pe_halted', 'fwd_conflicts',
            'sync_spins', 'pe_comp_halted',
            'pe_ctrl_nops', 'pe_comp_nops',
            'controller_nops', 'extend_match_iters',
            'extend_diags']
    totals = {k: [] for k in keys}
    for i, m in enumerate(results):
        vals = {k: m.get(k, 0) for k in keys}
        totals_line = (
            f"Run {i+1}/{len(pairs)}: cycles={vals['cycles']}, "
            f"SPM_req={vals['spm_requests']}, "
            f"conflicts={vals['bank_conflicts']}, "
            f"fwd_conflicts={vals['fwd_conflicts']}, "
            f"LSQ_stalls={vals['lsq_stalls']}, "
            f"PE_halted={vals['pe_halted']/4:.2f}, "
            f"PE_comp_halted={vals['pe_comp_halted']/4:.2f}, "
            f"sync_spins={vals['sync_spins']}, "
            f"ctrl_nops={vals['pe_ctrl_nops']}, "
            f"comp_nops={vals['pe_comp_nops']}, "
            f"ctrl_nops_arr={vals['controller_nops']}")
        print(totals_line)
        if golden_scores is not None:
            sim_score = m.get('score')
            expected = golden_scores[i]
            if sim_score is None:
                print(f"ERROR: Run {i+1} produced no score")
                sys.exit(1)
            if sim_score != expected:
                print(f"ERROR: Run {i+1} score mismatch: got {sim_score}, expected {expected}")
                sys.exit(1)
        for k in keys:
            totals[k].append(vals[k])

    n = len(pairs)
    print()
    print("=" * 60)
    print("=== Summary ===")
    print(f"Total runs: {n}")
    if totals['cycles']:
        print(f"Avg cycles: {sum(totals['cycles'])/n:.1f}")
        print(f"Min cycles: {min(totals['cycles'])}")
        print(f"Max cycles: {max(totals['cycles'])}")
        print(f"Total cycles: {sum(totals['cycles'])}")
    for k, label in [('spm_requests', 'SPM requests'), ('bank_conflicts', 'bank conflicts'),
                      ('fwd_conflicts', 'fwd conflicts'), ('lsq_stalls', 'LSQ stalls'),
                      ('sync_spins', 'sync spins')]:
        if totals[k]:
            print(f"Avg {label}: {sum(totals[k])/n:.1f}")
    if totals['pe_halted']:
        print(f"Avg PE halted: {sum(totals['pe_halted'])/n/4:.2f}")
    if totals['pe_comp_halted']:
        print(
            f"Avg PE comp halted: "
            f"{sum(totals['pe_comp_halted'])/n/4:.2f}"
        )
    for k, label in [
        ('pe_ctrl_nops', 'PE ctrl NOPs'),
        ('pe_comp_nops', 'PE comp NOPs'),
        ('controller_nops', 'controller NOPs'),
        ('extend_match_iters', 'extend-match iters'),
        ('extend_diags', 'extend diags'),
    ]:
        if totals[k]:
            print(f"Avg {label}: {sum(totals[k])/n:.1f}")
    if golden_scores is not None:
        print("SCORES VERIFIED")
    else:
        print("SCORES NOT VERIFIED")
    print("=" * 60)


if __name__ == '__main__':
    main()
