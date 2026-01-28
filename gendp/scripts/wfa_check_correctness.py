#!/usr/bin/env python3
"""
WFA Validation Script - Compare GenDP simulator output against reference kernel
Usage: python scripts/wfa_check_correctness.py <seq_file> [options]
"""

import sys
import os
import subprocess
import re
import shlex
from pathlib import Path

# Import reference WFA implementation from submodule
sys.path.insert(0, str(Path(__file__).parent / '../kernel/WFA-proxy'))
from wfa_align import wfa_align

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

def run_simulator(pattern, text, sim_path='./sim', verbose=False):
    """
    Run the GenDP simulator with given pattern and text
    Returns the score extracted from output
    """
    # Set environment variables
    env = os.environ.copy()
    env['PATTERN_WFA'] = pattern
    env['TEXT_WFA'] = text

    # Run simulator
    cmd = [sim_path, '-k', '5', '-i', '../../kernel/Datasets/crossBlockSeq.seq',
           '-o', '/dev/null', '-s', '-n', '-1']

    try:
        # Capture stdout for score parsing, but let stderr pass through to the terminal.
        result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE,
                              stderr=None, text=True, timeout=30)

        if verbose:
            print("Simulator output:", result.stdout)

        # Extract score from "qqq <score> qqq" pattern
        match = re.search(r'qqq (\d+) qqq', result.stdout)
        if match:
            return int(match.group(1))
        else:
            print(f"ERROR: Could not extract score from simulator output")
            return None

    except subprocess.TimeoutExpired:
        print(f"ERROR: Simulator timed out")
        return None
    except Exception as e:
        print(f"ERROR: Simulator failed: {e}")
        return None

def run_kernel(pattern, text, verbose=False):
    """
    Run the reference kernel (Python WFA implementation)
    Returns the alignment score
    """
    try:
        # Suppress debug prints from wfa_align
        if not verbose:
            import io
            import contextlib
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                score = wfa_align(pattern, text)
        else:
            score = wfa_align(pattern, text)

        return score
    except Exception as e:
        print(f"ERROR: Kernel failed: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/wfa_check_correctness.py <seq_file> [-v] [-n N]")
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

    # Read sequence pairs
    print(f"Reading sequences from: {seq_file}")
    pairs = read_seq_file(seq_file)

    if limit:
        pairs = pairs[:limit]
        print(f"Testing first {limit} sequence pairs")
    else:
        print(f"Testing {len(pairs)} sequence pairs")

    print()

    # Test each pair
    passed = 0
    failed = 0
    errors = 0

    for i, (pattern, text) in enumerate(pairs):
        print(f"Test {i+1}/{len(pairs)}: ", end='')

        # Run simulator
        sim_score = run_simulator(pattern, text, verbose=verbose)

        # Run kernel
        kernel_score = run_kernel(pattern, text, verbose=verbose)

        # Compare
        if sim_score is None or kernel_score is None:
            print("ERROR (could not get scores)")
            errors += 1
            sys.exit(1)
        elif sim_score == kernel_score:
            print(f"PASS (score={sim_score})")
            passed += 1
        else:
            print(f"FAIL (sim={sim_score}, kernel={kernel_score})")
            sim_cmd = ['./sim', '-k', '5', '-i', '../../kernel/Datasets/crossBlockSeq.seq',
                       '-o', '/dev/null', '-s', '-n', '-1']
            gdb_cmd = ['gdb', '--args'] + sim_cmd
            print(f"  GenDP command: {shlex.join(sim_cmd)}")
            try:
                with open('lastFailedGdb', 'w') as f:
                    f.write('PATTERN_WFA=' + shlex.quote(pattern) + '\n')
                    f.write('TEXT_WFA=' + shlex.quote(text) + '\n')
                    f.write(shlex.join(gdb_cmd) + '\n')
                print("  Wrote gdb command to: lastFailedGdb")
            except Exception as e:
                print(f"WARNING: Failed to write lastFailedGdb: {e}")
            if verbose:
                print(f"  Pattern: {pattern[:50]}...")
                print(f"  Text:    {text[:50]}...")
            
            # Verify trace files exist
            cwd = os.getcwd()
            magic_file = os.path.join(cwd, "magic_wfs_out.txt")
            trace_file = os.path.join(cwd, "wfaTrace.txt")
            
            if os.path.exists(magic_file):
                print(f"Simulator trace generated at: {magic_file}")
            else:
                print(f"WARNING: Simulator trace NOT found at: {magic_file}")
                
            if os.path.exists(trace_file):
                print(f"Kernel trace generated at: {trace_file}")
            else:
                print(f"WARNING: Kernel trace NOT found at: {trace_file}")
                
            sys.exit(1)

    # Summary
    print()
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed, {errors} errors")
    print(f"Success rate: {passed}/{len(pairs)} ({100*passed/len(pairs):.1f}%)")
    print("="*60)

    # Exit with appropriate code
    if failed > 0 or errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
