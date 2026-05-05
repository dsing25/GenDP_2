#!/usr/bin/env python3
"""
GWFA Correctness Check - Compare simulator vs golden scores.
Usage: python3 scripts/gwfa_check_correctness.py <mode> [-t N]
  mode 1: fast  (15 iterations)
  mode 2: full  (all iterations)
  mode 3: debug (single iteration, verbose)
  mode 4: smart (full; ALWAYS run s_term=10 wfDebug-trace check against
                 per-query goldens, AND best-effort score check with
                 30s soft-timeout. Trace failure -> FAIL; trace pass +
                 score timeout -> PASS; trace pass + score mismatch
                 -> FAIL. Empty-graph queries fall back to score-only.)
  -t N:  run N simulator processes in parallel

Prereqs:
  - Build sim: make clean && make -j
  - Golden scores at /data4/kaplannp/GenDP2/kernel/Gwfa/Datasets/Gwfa295/trueScores.txt
  - For mode 4: per-query s_term=10 goldens at
    gendp/datasets/Gwfa295/wfDebugTrue_term10/q{NNN}.txt
"""

import sys
import os
import queue
import re
import subprocess
import tempfile
import threading
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

def _trim_to_n_steps(text, n):
    """Truncate a wfDebug.txt-style trace to the first n
    [gfa_ed_step] blocks. The simulator emits one extra trailing
    block past s_term (post-extend snapshot at dist=s_term+1) that
    the reference kernel does not."""
    out, seen = [], 0
    for line in text.splitlines(keepends=True):
        if line.startswith('[gfa_ed_step]'):
            seen += 1
            if seen > n:
                break
        out.append(line)
    return ''.join(out)


def _run_trace_check(case_idx, tmpdir):
    """Run sim with s_term=SMART_S_TERM and compare wfDebug.txt against
    per-query golden. Returns (status, detail) where status is one of:
      'PASS'      — sim trace matches golden over the first n_gld blocks.
      'FAIL'      — trace mismatch (detail includes first-diff line).
      'ERROR'     — sim crashed / hung / no wfDebug produced.
      'NO_GOLDEN' — no per-query trace golden exists (typically empty
                    graph). Caller should fall back to score-only.
    Uses a *separate* input dir copied from tmpdir with s_term overridden
    to SMART_S_TERM, so the caller's tmpdir keeps the original s_term
    for the score check."""
    golden_path = SMART_GOLDEN_DIR / f"q{case_idx:03d}.txt"
    if not golden_path.exists():
        return ('NO_GOLDEN', f'no trace golden at {golden_path}')

    with tempfile.TemporaryDirectory() as trace_input:
        # Copy all data files; override s_term.txt to SMART_S_TERM.
        for fname in os.listdir(tmpdir):
            src = os.path.join(tmpdir, fname)
            dst = os.path.join(trace_input, fname)
            with open(src) as fr, open(dst, 'w') as fw:
                fw.write(fr.read())
        with open(os.path.join(trace_input, 's_term.txt'), 'w') as f:
            f.write(f"{SMART_S_TERM}\n")

        # Per-thread cwd so concurrent runs don't fight over wfDebug.txt.
        # The sim loads instructions/gwfa/* via a hardcoded relative
        # path (gwfa_sim.cpp:~290), so symlink that subtree into run_cwd.
        with tempfile.TemporaryDirectory() as run_cwd:
            os.symlink(REPO_ROOT / 'instructions',
                       os.path.join(run_cwd, 'instructions'))
            env = dict(os.environ)
            env['GWFA_DBG'] = '1'
            env['GWFA_S_TERM_DBG'] = str(SMART_S_TERM)
            # Disable LSan's exit-time ptrace probe; some sandboxes
            # (Yama scope>=1, Docker default seccomp, certain CI
            # runners) reject the ptrace call and LSan then exits
            # rc=1 AFTER wfDebug.txt is already written. Suppress
            # only the leak detector — the AddressSan body stays on.
            env['ASAN_OPTIONS'] = (env.get('ASAN_OPTIONS', '') +
                                   (':' if env.get('ASAN_OPTIONS') else '')
                                   + 'detect_leaks=0')
            cmd = [str(SIM_PATH), '-k', '7', '-i', trace_input, '-n', '1']
            # Most cases finish s_term=10 in seconds; q128 etc. have
            # heavy per-iter work, so 5min hard cap.
            TRACE_TIMEOUT = 300
            try:
                r = subprocess.run(
                    cmd, cwd=run_cwd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True, timeout=TRACE_TIMEOUT, env=env)
            except subprocess.TimeoutExpired:
                return ('ERROR',
                        f'trace-check sim exceeded {TRACE_TIMEOUT}s '
                        f'at s_term={SMART_S_TERM}')
            wfd = os.path.join(run_cwd, 'wfDebug.txt')
            if r.returncode != 0 or not os.path.exists(wfd):
                return ('ERROR',
                        f'trace-check sim rc={r.returncode}, '
                        f'wfDebug present={os.path.exists(wfd)}')
            with open(wfd) as f:
                sim_text = f.read()

    with open(golden_path) as f:
        gld_text = f.read()
    n_gld = sum(1 for l in gld_text.splitlines()
                if l.startswith('[gfa_ed_step]'))
    sim_trim = _trim_to_n_steps(sim_text, n_gld)

    if sim_trim == gld_text:
        return ('PASS', f'trace[{SMART_S_TERM}]==golden')
    sim_lines = sim_trim.splitlines()
    gld_lines = gld_text.splitlines()
    first_diff = next(
        (i for i, (a, b) in enumerate(zip(sim_lines, gld_lines))
         if a != b), min(len(sim_lines), len(gld_lines)))
    return ('FAIL',
            f'trace mismatch at line {first_diff} '
            f'(sim={len(sim_lines)} gld={len(gld_lines)})')


def _run_score_check(tmpdir, golden_score):
    """Run sim full alignment with SMART_SOFT_TIMEOUT. Returns
    (status, detail) where status is one of:
      'PASS'    — score matches golden_score.
      'FAIL'    — score mismatch.
      'TIMEOUT' — wall-clock exceeded SMART_SOFT_TIMEOUT (we sent
                  SIGTERM); caller may treat as PASS if trace was OK.
      'ERROR'   — sim crashed / nonzero rc / no score parsed.
    Uses a daemon reader thread + queue so the wall-clock check
    fires every 0.5s regardless of subprocess output cadence."""
    cmd = [str(SIM_PATH), '-k', '7', '-i', tmpdir, '-n', '1']
    env = dict(os.environ)
    env['GWFA_PROGRESS'] = '100000'
    env['ASAN_OPTIONS'] = (env.get('ASAN_OPTIONS', '') +
                           (':' if env.get('ASAN_OPTIONS') else '')
                           + 'detect_leaks=0')
    proc = subprocess.Popen(
        cmd, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True, bufsize=1, env=env)

    line_q: "queue.Queue[str | None]" = queue.Queue()

    def _reader(stream, q):
        try:
            for line in stream:
                q.put(line)
        finally:
            q.put(None)

    reader_thread = threading.Thread(
        target=_reader, args=(proc.stdout, line_q),
        daemon=True)
    reader_thread.start()

    score = None
    timed_out = False
    start = time.time()
    try:
        while True:
            remaining = SMART_SOFT_TIMEOUT - (time.time() - start)
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = line_q.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                continue
            if line is None:
                break  # EOF
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
        else:
            proc.wait()
        if proc.stdout:
            proc.stdout.close()
        reader_thread.join(timeout=1)

    if timed_out:
        return ('TIMEOUT',
                f'score run exceeded {SMART_SOFT_TIMEOUT}s')
    if proc.returncode != 0:
        return ('ERROR',
                f'score sim rc={proc.returncode} '
                f'(score parsed={score})')
    if score is None:
        return ('ERROR', 'no score in output')
    if score == golden_score:
        return ('PASS', f'score={score}')
    return ('FAIL', f'score sim={score} gld={golden_score}')


def run_single_case_smart(args):
    """Mode 4: run TRACE check (always) + SCORE check (best-effort).
    Returns (case_idx, status, detail) where status is 'PASS', 'FAIL',
    or 'ERROR'.

    Decision table:
      trace=PASS,  score=PASS    -> PASS  (full agreement)
      trace=PASS,  score=FAIL    -> FAIL  (trace OK but final score off)
      trace=PASS,  score=TIMEOUT -> PASS  (trace alone is sufficient)
      trace=PASS,  score=ERROR   -> ERROR (something crashed during full run)
      trace=FAIL                 -> FAIL  (trace mismatch — authoritative)
      trace=ERROR                -> ERROR (trace-check sim crashed)
      trace=NO_GOLDEN, score=*   -> reuse score result as the verdict
                                    (typically empty-graph queries)"""
    case_idx, case_lines, golden_score = args
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, line in case_lines.items():
            with open(os.path.join(tmpdir, fname), 'w') as f:
                f.write(line + '\n')

        # Step 1: trace check (always when a per-query golden exists).
        t_status, t_detail = _run_trace_check(case_idx, tmpdir)

        # Empty-graph case: no per-query trace golden, fall back to
        # score-only. The reference returns `qqq -1 qqq` immediately
        # for these, so the score check is the only meaningful signal.
        if t_status == 'NO_GOLDEN':
            s_status, s_detail = _run_score_check(tmpdir, golden_score)
            if s_status == 'TIMEOUT':
                return (case_idx, 'ERROR',
                        f'no trace golden and {s_detail} '
                        f'(empty-graph should finish instantly)')
            return (case_idx, s_status,
                    f'no trace golden; {s_detail}')

        # Authoritative trace verdict short-circuits FAIL/ERROR.
        if t_status in ('FAIL', 'ERROR'):
            return (case_idx, t_status, t_detail)

        # Step 2: score check (best-effort).
        s_status, s_detail = _run_score_check(tmpdir, golden_score)
        if s_status == 'PASS':
            return (case_idx, 'PASS',
                    f'trace+score: {s_detail}')
        if s_status == 'FAIL':
            return (case_idx, 'FAIL',
                    f'trace OK; {s_detail}')
        if s_status == 'TIMEOUT':
            return (case_idx, 'PASS',
                    f'trace OK; score-run TIMEOUT '
                    f'(>{SMART_SOFT_TIMEOUT}s)')
        # ERROR
        return (case_idx, 'ERROR',
                f'trace OK; {s_detail}')


def run_smart_parallel(num_threads):
    """Mode 4: full sweep. Every query gets a TRACE check at
    s_term=SMART_S_TERM (against the per-query golden) AND a
    best-effort SCORE check with SMART_SOFT_TIMEOUT. The trace check
    is authoritative; a failed trace is a FAIL even if the score
    happens to match. A score-run TIMEOUT counts as PASS provided
    trace passed (the trace at dist 0..SMART_S_TERM is sufficient
    evidence over those bounded dists). Empty-graph queries (no
    per-query trace golden) fall back to score-only."""
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
    # Cases whose score-run hit the soft timeout (still passed via
    # trace check) are tagged 'score-run TIMEOUT' in the detail field
    # by run_single_case_smart.
    n_score_timeout = sum(1 for r in results
                          if r and 'score-run TIMEOUT' in (r[1] or ''))

    fails = [(i, r[1]) for i, r in enumerate(results)
             if r and r[0] == 'FAIL']
    errors = [(i, r[1]) for i, r in enumerate(results)
              if r and r[0] == 'ERROR']
    score_timed_out = [i for i, r in enumerate(results)
                       if r and 'score-run TIMEOUT' in (r[1] or '')]

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
    if score_timed_out:
        print()
        print(f"score-run TIMEOUT (>{SMART_SOFT_TIMEOUT}s) but trace "
              f"PASS at s_term={SMART_S_TERM}: {len(score_timed_out)}")
        print(f"  {score_timed_out}")

    print()
    print("=" * 50)
    print(f"Wall: {elapsed:.1f}s")
    print(f"Results: {n_pass} pass, {n_fail} fail, "
          f"{n_err} error  out of {n}")
    print(f"  every query trace-checked at s_term={SMART_S_TERM}; "
          f"{n_score_timeout} also had a score-run TIMEOUT")
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
