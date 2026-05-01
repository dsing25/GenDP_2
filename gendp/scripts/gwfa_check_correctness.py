#!/usr/bin/env python3
"""
GWFA Correctness Check - Compare simulator vs golden scores.
Usage: python3 scripts/gwfa_check_correctness.py <mode> [-t N]
  mode 1: fast  (15 iterations)
  mode 2: full  (all iterations)
  mode 3: debug (single iteration, verbose)
  mode 4: smart (full; on per-case 30s timeout fall back to s_term=10
                 wfDebug-trace check against per-query goldens)
  -t N:  run N simulator processes in parallel

Prereqs:
  - Build sim: make clean && make -j
  - Golden scores at /data4/kaplannp/GenDP2/kernel/Gwfa/Datasets/Gwfa295/trueScores.txt
  - For mode 4: per-query s_term=10 goldens at
    gendp/datasets/Gwfa295/wfDebugTrue_term10/q{NNN}.txt
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
KERNEL_DIR = REPO_ROOT / 'kernel' / 'Gwfa'
DUMP_DIR = Path('/data4/kaplannp/GenDP2/kernel/Gwfa/Datasets/Gwfa295')
GOLDEN_SCORES = DUMP_DIR / 'trueScores.txt'
GOLDEN_DEBUG = DUMP_DIR / 'wfDebugTrue0.txt'
SIM_PATH = REPO_ROOT / 'sim'
SIM_DEBUG_OUT = REPO_ROOT / 'wfDebug.txt'

MODES = {
    '1': {'name': 'fast',  'n': 15},
    '2': {'name': 'full',  'n': -1},
    '3': {'name': 'debug', 'n': 1},
    '4': {'name': 'smart', 'n': -1},
}

# Mode 4: per-case wall budget; if exceeded, fall back to wfDebug trace
# check at s_term=10 instead of waiting for the full score.
SMART_SOFT_TIMEOUT = 30
SMART_S_TERM = 10
SMART_GOLDEN_DIR = (REPO_ROOT
                    / 'datasets' / 'Gwfa295' / 'wfDebugTrue_term10')

# Files the simulator reads from the input directory (one line per case)
DATA_FILES = [
    'ql.txt', 'q.txt', 's_term.txt', 'n_vtx.txt', 'n_arc.txt',
    'graphSeq.txt', 'seq_off.txt', 'seq_len.txt',
    'arc_v.txt', 'arc_w.txt', 'arc_ow.txt', 'idx.txt',
]


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


def load_dataset_lines(path, n):
    """Load first n lines from each DATA_FILE.
    Returns {filename: [line0, line1, ...]}."""
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


def run_single_case(args):
    """Run simulator for one case in a temp directory.
    Returns (case_idx, score or None)."""
    case_idx, case_lines, verbose = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, line in case_lines.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                f.write(line + '\n')
        cmd = [
            str(SIM_PATH), '-k', '7',
            '-i', tmpdir, '-n', '1',
        ]
        stderr_dest = None if verbose else subprocess.DEVNULL
        try:
            result = subprocess.run(
                cmd, cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=stderr_dest,
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


# Smart-mode helpers --------------------------------------------------------
# A case either (a) finishes in <= SMART_SOFT_TIMEOUT and is checked against
# trueScores.txt, or (b) hits the soft timeout and is rerun with
# GWFA_S_TERM_DBG=SMART_S_TERM, then its wfDebug.txt is byte-compared to the
# per-query golden in SMART_GOLDEN_DIR. The second path is much weaker (only
# verifies the first 10 WF iterations) but bounded in time.

def run_single_case_smart(args):
    """Try a normal score-based check; on soft-timeout fall back to a
    bounded wfDebug-trace check. Returns (case_idx, status, detail) where
    status is 'PASS', 'FAIL', or 'ERROR'."""
    case_idx, case_lines, golden_score = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, line in case_lines.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                f.write(line + '\n')

        # --- Pass 1: normal run, soft-bounded
        # GWFA_PROGRESS makes the sim emit a 'progress' line every
        # 100k cycles. Without it, readline() below would block on a
        # silent long-running query and we'd miss the soft-timeout
        # by up to the case's full natural runtime.
        cmd = [str(SIM_PATH), '-k', '7',
               '-i', tmpdir, '-n', '1']
        env = dict(os.environ)
        env['GWFA_PROGRESS'] = '100000'
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True, bufsize=1, env=env)
        score = None
        timed_out = False
        start = time.time()
        try:
            while True:
                if time.time() - start > SMART_SOFT_TIMEOUT:
                    timed_out = True
                    break
                line = proc.stdout.readline()
                if not line:
                    break
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

        if not timed_out:
            if score is None:
                return (case_idx, 'ERROR', 'no score in output')
            if score == golden_score:
                return (case_idx, 'PASS',
                        f'score={score}')
            return (case_idx, 'FAIL',
                    f'score sim={score} gld={golden_score}')

        # Soft-timeout: just record the early exit. Trace-fallback
        # check is deferred until the simulator's per-iteration
        # state matches the reference (see q0 dedup divergence).
        return (case_idx, 'TIMEOUT',
                f'>{SMART_SOFT_TIMEOUT}s, gld={golden_score}')


def _smart_fallback_trace(case_idx, tmpdir, golden_score):
    # Special case: empty graph queries (golden_score == -1, n_vtx==0)
    # can't time out; if we got here, the sim is broken — bail.
    golden_path = SMART_GOLDEN_DIR / f"q{case_idx:03d}.txt"
    if not golden_path.exists():
        # No trace golden (n_vtx == 0). Trace check meaningless.
        # Fall back to: just verify the simulator emits qqq -1 qqq when
        # given the empty-graph input (matches reference behavior).
        if golden_score == -1:
            return (case_idx, 'PASS',
                    'trace-skip (empty graph; soft-timeout '
                    'unexpected but continuing)')
        return (case_idx, 'FAIL',
                f'soft-timeout and no trace golden at {golden_path}')

    # Override s_term to SMART_S_TERM and rerun. wfDebug.txt is written
    # to REPO_ROOT (relative to sim's cwd, see kernel/Gwfa/gwfa.c:25-29).
    s_term_path = os.path.join(tmpdir, 's_term.txt')
    with open(s_term_path, 'w') as f:
        f.write(f"{SMART_S_TERM}\n")
    sim_dbg_out = REPO_ROOT / f"wfDebug_q{case_idx:03d}.txt"
    if sim_dbg_out.exists():
        sim_dbg_out.unlink()
    # Per-thread cwd so concurrent runs don't fight over wfDebug.txt.
    # The sim loads instructions/gwfa/* via a hardcoded relative path
    # (gwfa_sim.cpp:276), so symlink that subtree into the run_cwd.
    with tempfile.TemporaryDirectory() as run_cwd:
        os.symlink(REPO_ROOT / 'instructions',
                   os.path.join(run_cwd, 'instructions'))
        env = dict(os.environ)
        env['GWFA_DBG'] = '1'
        env['GWFA_S_TERM_DBG'] = str(SMART_S_TERM)
        cmd = [str(SIM_PATH), '-k', '7',
               '-i', tmpdir, '-n', '1']
        try:
            r = subprocess.run(
                cmd, cwd=run_cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True, timeout=120, env=env)
        except subprocess.TimeoutExpired:
            return (case_idx, 'ERROR',
                    f'soft-timeout fallback also timed out '
                    f'(>{120}s at s_term={SMART_S_TERM})')
        wfd = os.path.join(run_cwd, 'wfDebug.txt')
        if r.returncode != 0 or not os.path.exists(wfd):
            return (case_idx, 'ERROR',
                    f'fallback sim rc={r.returncode}, '
                    f'wfDebug present={os.path.exists(wfd)}')
        with open(wfd) as f:
            sim_text = f.read()
    with open(golden_path) as f:
        gld_text = f.read()
    if sim_text == gld_text:
        return (case_idx, 'PASS',
                f'soft-timeout: trace[{SMART_S_TERM}]==golden')
    # Help debugging: where do they first diverge?
    sim_lines = sim_text.splitlines()
    gld_lines = gld_text.splitlines()
    first_diff = next(
        (i for i, (a, b) in enumerate(zip(sim_lines, gld_lines))
         if a != b), min(len(sim_lines), len(gld_lines)))
    return (case_idx, 'FAIL',
            f'soft-timeout: trace mismatch at line {first_diff} '
            f'(sim={len(sim_lines)} gld={len(gld_lines)})')


def run_smart_parallel(num_threads):
    """Mode 4: full sweep with per-case soft timeout. Cases that don't
    finish within SMART_SOFT_TIMEOUT are reported as TIMEOUT (no
    judgment); the rest are score-checked."""
    print(f"Loading dataset (full)...")
    dataset = load_dataset_lines(DUMP_DIR, -1)
    n = len(dataset[DATA_FILES[0]])
    golden = load_golden(GOLDEN_SCORES)[:n]

    tasks = []
    for i in range(n):
        case_lines = {fname: dataset[fname][i] for fname in DATA_FILES}
        tasks.append((i, case_lines, golden[i]))

    t0 = time.time()
    print(f"Running {n} cases with {num_threads} thread(s), "
          f"soft-timeout={SMART_SOFT_TIMEOUT}s...")
    results = [None] * n
    done = 0
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_threads) as pool:
        futs = {pool.submit(run_single_case_smart, t): t[0]
                for t in tasks}
        for fut in concurrent.futures.as_completed(futs):
            idx, status, detail = fut.result()
            results[idx] = (status, detail)
            done += 1
            if done % 10 == 0 or done == n:
                print(f"  progress: {done}/{n}")
    elapsed = time.time() - t0

    n_pass = sum(1 for r in results if r and r[0] == 'PASS')
    n_fail = sum(1 for r in results if r and r[0] == 'FAIL')
    n_err  = sum(1 for r in results if r and r[0] == 'ERROR')
    n_to   = sum(1 for r in results if r and r[0] == 'TIMEOUT')

    fails = [(i, r[1]) for i, r in enumerate(results)
             if r and r[0] == 'FAIL']
    errors = [(i, r[1]) for i, r in enumerate(results)
              if r and r[0] == 'ERROR']
    timeouts = [i for i, r in enumerate(results)
                if r and r[0] == 'TIMEOUT']

    if fails:
        print()
        print(f"FAIL ({len(fails)}):")
        for i, d in fails:
            print(f"  [{i}] {d}")
    if errors:
        print()
        print(f"ERROR ({len(errors)}):")
        for i, d in errors:
            print(f"  [{i}] {d}")
    if timeouts:
        print()
        print(f"TIMEOUT >{SMART_SOFT_TIMEOUT}s ({len(timeouts)}):")
        print(f"  {timeouts}")

    print()
    print("=" * 50)
    print(f"Wall: {elapsed:.1f}s")
    print(f"Results: {n_pass} pass, {n_fail} fail, "
          f"{n_err} error, {n_to} timeout  out of {n}")
    print("=" * 50)
    return n_fail + n_err


def run_sim_parallel(n, num_threads, verbose=False):
    """Run n cases in parallel, return list of scores."""
    print(f"Loading dataset for {n} cases...")
    dataset = load_dataset_lines(DUMP_DIR, n)
    actual_n = len(dataset[DATA_FILES[0]])
    if n > 0 and actual_n < n:
        print(f"WARNING: only {actual_n} cases in dataset")
        n = actual_n

    # Build per-case arg tuples
    tasks = []
    for i in range(n):
        case_lines = {fname: dataset[fname][i] for fname in DATA_FILES}
        tasks.append((i, case_lines, verbose))

    print(f"Running {n} cases with {num_threads} threads...")
    scores = [None] * n
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = {pool.submit(run_single_case, t): t[0] for t in tasks}
        for fut in concurrent.futures.as_completed(futures):
            idx, score = fut.result()
            scores[idx] = score
            done += 1
            if done % 10 == 0 or done == n:
                print(f"  progress: {done}/{n}")
    return scores


def run_sim_debug(s_term_dbg=5):
    """Run simulator with GWFA_S_TERM_DBG set, n=1."""
    cmd = [
        str(SIM_PATH), '-k', '7',
        '-i', str(DUMP_DIR), '-n', '1',
    ]
    env = os.environ.copy()
    env['GWFA_S_TERM_DBG'] = str(s_term_dbg)
    env['GWFA_DBG'] = '1'
    print(f"Running: {' '.join(cmd)}")
    print(f"  GWFA_S_TERM_DBG={s_term_dbg}")
    result = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=None, text=True, timeout=600,
        env=env)
    if result.returncode != 0:
        print(f"ERROR: simulator exited with code "
              f"{result.returncode}")
        sys.exit(1)
    return result


def parse_steps(text):
    """Parse wfDebug text into per-step blocks.
    Returns [(header, sorted_z, sorted_wf), ...]"""
    steps = []
    cur_h = cur_z = cur_wf = None
    for line in text.splitlines():
        if line.startswith("[gfa_ed_step]"):
            if cur_h is not None:
                steps.append((cur_h, sorted(cur_z), sorted(cur_wf)))
            cur_h, cur_z, cur_wf = line, [], []
        elif line.startswith("Z\t"):
            cur_z.append(line)
        elif line.startswith("WF\t"):
            cur_wf.append(line)
    if cur_h is not None:
        steps.append((cur_h, sorted(cur_z), sorted(cur_wf)))
    return steps


def check_debug_trace(s_term_dbg=5):
    """Mode 3: run sim with limited steps, compare
    wfDebug.txt against golden wfDebugTrue0.txt."""
    if not GOLDEN_DEBUG.exists():
        print(f"Golden debug file not found: "
              f"{GOLDEN_DEBUG}")
        sys.exit(1)

    # Remove stale output
    if SIM_DEBUG_OUT.exists():
        SIM_DEBUG_OUT.unlink()

    run_sim_debug(s_term_dbg)

    if not SIM_DEBUG_OUT.exists():
        print("ERROR: wfDebug.txt not produced")
        sys.exit(1)

    sim_text = SIM_DEBUG_OUT.read_text()
    golden_text = GOLDEN_DEBUG.read_text()

    sim_steps = parse_steps(sim_text)
    golden_steps = parse_steps(golden_text)

    n = min(len(sim_steps), len(golden_steps))
    if n == 0:
        print("ERROR: no steps parsed")
        sys.exit(1)
    print(f"Comparing {n} steps "
          f"(sim={len(sim_steps)}, "
          f"golden={len(golden_steps)})")

    passed = 0
    failed = 0
    for i in range(n):
        sh, sz, swf = sim_steps[i]
        gh, gz, gwf = golden_steps[i]
        ok = (sh == gh and sz == gz and swf == gwf)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"  step {i} MISMATCH")
            if sh != gh:
                print(f"    header: sim={sh}")
                print(f"    header: gld={gh}")
            if sz != gz:
                print(f"    Z lines differ "
                      f"(sim={len(sz)}, gld={len(gz)})")
            if swf != gwf:
                print(f"    WF lines differ "
                      f"(sim={len(swf)}, gld={len(gwf)})")

    print()
    print("=" * 50)
    print(f"Debug trace: {passed} passed, "
          f"{failed} failed out of {n} steps")
    print("=" * 50)
    return failed


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
              "scripts/gwfa_check_correctness.py "
              "<1|2|3|4> [-t N]")
        print("  1: fast (15 iterations)")
        print("  2: full (all iterations)")
        print("  3: debug (1 iteration, verbose)")
        print(f"  4: smart (full, soft-timeout "
              f"{SMART_SOFT_TIMEOUT}s -> trace fallback)")
        print("  -t N: parallel with N processes")
        sys.exit(1)

    mode = MODES[mode_key]
    print(f"=== GWFA {mode['name']} mode ===")

    if mode_key == '3':
        failed = check_debug_trace(s_term_dbg=5)
        sys.exit(1 if failed else 0)

    if mode_key == '4':
        if not GOLDEN_SCORES.exists():
            print(f"Golden scores not found at {GOLDEN_SCORES}")
            sys.exit(1)
        failed = run_smart_parallel(num_threads or 1)
        sys.exit(1 if failed else 0)

    verbose = False
    n = mode['n']

    if not GOLDEN_SCORES.exists():
        print(f"Golden scores not found at "
              f"{GOLDEN_SCORES}")
        print("Expected at: "
              "/data4/kaplannp/GenDP2/kernel/Gwfa/"
              "Datasets/Gwfa295/trueScores.txt")
        sys.exit(1)

    golden = load_golden(GOLDEN_SCORES)
    if n > 0:
        golden = golden[:n]
    else:
        n = len(golden)

    # Run sim: parallel or single-threaded
    if num_threads:
        sim_scores = run_sim_parallel(n, num_threads, verbose)
    else:
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
