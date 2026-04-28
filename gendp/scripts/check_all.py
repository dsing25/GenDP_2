#!/usr/bin/env python3
"""
check_all.py — Run correctness checks for every working GenDP kernel.

Builds sim once (ADDRESS_SANITIZER=0; chain's input file is too large
for ASAN), regenerates each kernel's reference where needed, runs sim,
and compares output. Prints a per-kernel pass/fail table and a total
elapsed time at the end.

Usage:
    cd gendp/
    python3 scripts/check_all.py
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent     # gendp/
DATASETS  = REPO_ROOT.parent / 'gendp-datasets'        # ../gendp-datasets/
BACKTEST  = REPO_ROOT.parent / 'backtest-datasets'     # ../backtest-datasets/


def section(title):
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print('=' * 64)


def run(cmd, **kw):
    """Run a command, capture stdout+stderr, return CompletedProcess."""
    kw.setdefault('cwd', REPO_ROOT)
    kw.setdefault('text', True)
    kw.setdefault('stdout', subprocess.PIPE)
    kw.setdefault('stderr', subprocess.STDOUT)
    return subprocess.run(cmd, **kw)


def build():
    section("Build sim (ADDRESS_SANITIZER=0)")
    t0 = time.time()
    run(['make', 'clean'])
    r = run(['make', '-j', 'ADDRESS_SANITIZER=0'])
    if r.returncode != 0:
        sys.stdout.write(r.stdout)
        print("\nBUILD FAILED")
        sys.exit(1)
    print(f"  build OK ({time.time()-t0:.1f}s)")


def generate_instructions():
    section("Generate instruction traces (all kernels)")
    t0 = time.time()
    for k in ['wfa', 'bsw', 'phmm', 'poa', 'chain', 'gssw']:
        gen = REPO_ROOT / 'scripts' / f'{k}_instruction_generator.py'
        if gen.exists():
            run(['python3', str(gen)])
    print(f"  generated ({time.time()-t0:.1f}s)")


# ----- per-kernel checks. Each returns (status, detail). -----

def check_bsw():
    sim_in  = DATASETS / 'bsw_147_1m_8bit_input_512.txt'
    ref     = DATASETS / 'bsw_147_1m_8bit_output.txt'
    sim_out = REPO_ROOT / 'bsw_147_1m_8bit_sim_output.txt'
    if not sim_in.exists() or not ref.exists():
        return ('SKIP', 'dataset missing')
    r = run(['./sim', '-k', '1', '-i', str(sim_in),
             '-o', str(sim_out), '-s', '-n', '2000'])
    if r.returncode != 0:
        return ('FAIL', f'sim exit={r.returncode}')
    r = run(['python3', 'scripts/bsw_check_correctness.py',
             str(sim_out), str(ref)])
    diffs = sum(1 for ln in r.stdout.splitlines() if ln.strip())
    return ('PASS', 'n=2000, 0 diffs') if diffs == 0 \
        else ('FAIL', f'{diffs} diff lines')


def check_chain():
    chain_in   = BACKTEST / 'chain' / 'in-3.txt'
    chain_ref  = DATASETS / 'chain_output.txt'
    sim_out    = REPO_ROOT / 'chain_output.txt'
    if not chain_in.exists():
        return ('SKIP', 'backtest in-3.txt missing')
    # Regenerate kernel reference (fast: ~1s)
    r = run([str(REPO_ROOT / 'kernel' / 'chain' / 'chain'),
             '-i', str(chain_in), '-o', str(chain_ref),
             '-s', '4', '-n', '1'],
            cwd=REPO_ROOT / 'kernel' / 'chain')
    if r.returncode != 0:
        return ('FAIL', f'kernel exit={r.returncode}')
    r = run(['./sim', '-k', '4', '-i', str(chain_in),
             '-n', '1', '-o', str(sim_out), '-s'])
    if r.returncode != 0:
        return ('FAIL', f'sim exit={r.returncode}')
    r = run(['python3', 'scripts/chain_check_correctness.py',
             str(chain_ref), str(sim_out)])
    # last line: "<n_err> errors out of <n> scores."
    line = (r.stdout.strip().splitlines() or [''])[-1]
    m = re.match(r'(\d+)\s+errors\s+out\s+of\s+(\d+)', line)
    if not m:
        return ('FAIL', f'unexpected check output: {line!r}')
    n_err, n = int(m.group(1)), int(m.group(2))
    return ('PASS', f'0/{n}') if n_err == 0 \
        else ('FAIL', f'{n_err}/{n} mismatched')


def check_phmm():
    phmm_in  = BACKTEST / 'phmm' / 'tiny.in'
    sim_in   = DATASETS / 'phmm_large_app.txt'
    ref      = DATASETS / 'phmm_large_output.txt'
    sim_out  = REPO_ROOT / 'phmm_large_app_output.txt'
    if not phmm_in.exists():
        return ('SKIP', 'backtest tiny.in missing')
    # Regenerate reference + sim input via ./pairhmm
    with open(ref, 'w') as fout, open(sim_in, 'w') as ferr:
        r = subprocess.run(
            [str(REPO_ROOT / 'kernel' / 'PairHMM' / 'pairhmm'),
             str(phmm_in), '64'],
            stdout=fout, stderr=ferr,
            cwd=REPO_ROOT / 'kernel' / 'PairHMM')
    if r.returncode != 0:
        return ('FAIL', f'kernel exit={r.returncode}')
    r = run(['./sim', '-k', '2', '-i', str(sim_in),
             '-n', '64', '-o', str(sim_out), '-s'])
    if r.returncode != 0:
        return ('FAIL', f'sim exit={r.returncode}')
    r = run(['python3', 'scripts/phmm_check_correctness.py',
             str(ref), str(sim_out)])
    diffs = sum(1 for ln in r.stdout.splitlines() if ln.strip())
    return ('PASS', 'n=64, 0 diffs') if diffs == 0 \
        else ('FAIL', f'{diffs} diff lines')


def check_poa():
    poa_in  = DATASETS / 'poa' / 'input' / 'input_1'
    poa_ref = DATASETS / 'poa' / 'output' / 'output_1'
    sim_out = REPO_ROOT / 'poa_output' / 'output_1'
    sim_out.parent.mkdir(exist_ok=True)
    # Regenerate reference via kernel/poaV2/run.sh (writes input_1+output_1)
    r = run(['bash', 'run.sh'],
            cwd=REPO_ROOT / 'kernel' / 'poaV2')
    if r.returncode != 0:
        return ('FAIL', f'kernel exit={r.returncode}')
    if not poa_in.exists() or not poa_ref.exists():
        return ('SKIP', 'poa input/output_1 missing after regen')
    r = run(['./sim', '-k', '3', '-i', str(poa_in),
             '-o', str(sim_out), '-s'])
    if r.returncode != 0:
        return ('FAIL', f'sim exit={r.returncode}')
    r = run(['python3', 'scripts/poa_check_correctness.py',
             str(sim_out), str(poa_ref), '0'])
    diffs = sum(1 for ln in r.stdout.splitlines() if ln.strip())
    return ('PASS', 'input_1, 0 diffs') if diffs == 0 \
        else ('FAIL', f'{diffs} diff lines')


def check_wfa():
    seq_file = Path('/data4/kaplannp/GenDP2/kernel/Wfa/Datasets/seq10k.seq')
    if not seq_file.exists():
        return ('SKIP', f'{seq_file} missing')
    r = run(['python3', 'scripts/wfa_check_correctness.py',
             str(seq_file), '-n', '50'])
    # wfa_check_correctness prints one "Test i/N: PASS (score=...)" or
    # "Test i/N: FAIL (sim=...)" per case.
    passed = sum(1 for ln in r.stdout.splitlines()
                 if 'PASS (score=' in ln)
    failed = sum(1 for ln in r.stdout.splitlines()
                 if 'FAIL (sim=' in ln)
    if r.returncode != 0 or failed > 0:
        return ('FAIL', f'{passed} passed, {failed} failed')
    return ('PASS', f'n=50, {passed} passed')


def check_gssw():
    r = run(['python3', 'scripts/gssw_check_correctness.py',
             '1', '-t', '16'])
    # Pull out the two summary lines:
    #   "Results: N passed, M failed, ..."
    #   "Regression: N passed, M failed"
    bits = []
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith('Results:') or s.startswith('Regression:'):
            bits.append(s)
    detail = ' | '.join(bits) or '(no summary parsed)'
    return ('PASS' if r.returncode == 0 else 'FAIL', detail)


KERNELS = [
    ('BSW',   check_bsw),
    ('Chain', check_chain),
    ('PHMM',  check_phmm),
    ('WFA',   check_wfa),
    ('GSSW',  check_gssw),
    ('POA',   check_poa),     # POA last: it's the slowest (~2:22)
]


def main():
    if not (REPO_ROOT / 'main.cpp').exists():
        print("ERROR: run from inside gendp/ checkout")
        sys.exit(1)

    t_total = time.time()
    build()
    generate_instructions()

    results = []
    for name, fn in KERNELS:
        section(f"Check {name}")
        t0 = time.time()
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = 'FAIL', f'exception: {e}'
        elapsed = time.time() - t0
        print(f"  {name:6s} {status:5s}  {detail}  ({elapsed:.1f}s)")
        results.append((name, status, detail, elapsed))

    section("Summary")
    print(f"  {'Kernel':8s} {'Result':6s} {'Time':>7s}  Detail")
    print('  ' + '-' * 62)
    for name, status, detail, elapsed in results:
        print(f"  {name:8s} {status:6s} {elapsed:6.1f}s  {detail}")
    print(f"\nTotal wall time: {time.time() - t_total:.1f}s")

    sys.exit(0 if all(r[1] == 'PASS' for r in results) else 1)


if __name__ == '__main__':
    main()
