# GWFA ISA-Like Rewrite Plan 3b: ISA Lower Controller 24 / 25 / 28 / 29 / 30 / 31

## Shared Preamble (duplicated across all active plans)

### Scope
- **Delete**: Controller magics 2, 10, 26 (deprecated) — DONE in Plan 1
- **Exempt (do not touch)**: Controller 1, 3, 4, 5, 6, 17
- **Reference examples (frozen, read-only)**: Controller 7, 8, 9, 12, 14, 15; PE 8,
  11, 13. `fin0_load_batch()` is rewritten under Plan 3a; 3b does NOT edit it.
- **In-scope this plan (controller)**: 24, 25, 28, 29, 30, 31
- **Out of this plan (covered by sibling 3a)**: 16, 18, 19, 20 + `fin0_load_batch()`
- **Out of this plan (covered by siblings 3c/3d)**: 32, 33, 34, 35, 36, 37, 38, 39
- **Out of this plan (PE)**: 19, 20, 21, 22, 23

### ISA-like rules (all 12, unchanged from the governing prompt)
1. Each line = one GenDP ISA operation
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired slots
3. Registers only: `gr[]`, `reg[]`, `s1c[]`, `spm[]`, `mm[]`; no C++ runtime
   variables carry architectural state across ISA lines
4. Gotos with labels instead of runtime `if/else/for/while`; macro-style unrolling
   (e.g. `for (int pe = 0; pe < 4; ++pe)`) is allowed
5. Compile-time constants (`constexpr`) allowed
6. SPM: 2-cycle latency (pipelined back-to-back loads OK; consumer of any loaded
   value must still wait 2 cycles = 4 ISA lines before reading)
7. MM/S2: `// waitLSQ` comment required between load and first consumer. Between
   magics the waitLSQ becomes an explicit ISA instruction; within a magic the
   annotation is consumed by the ISA generator to emit the LSQ-wait ISA op.
8. S1c: 1-cycle latency (consumer on the next VLIW cycle = at least 2 ISA lines
   later)
9. `mvdq` round-robin PE streaming for bulk contiguous transfers; scalar `mv` only
   for non-contiguous / graph-lookup-style data
10. No `std::min`/`std::max` on controller (use branch conditions); `min`/`max` OK
    on PE
11. Helper macros acceptable if ALL live state is in registers/memory (no C++
    locals carrying architectural state across ISA lines)
12. PE compute instructions deferred to a future pass

### Decision Log

- **DEC-SPM-MODEL** (Plan 2c, user-confirmed, inherited): the GWFA prompt is
  authoritative; pipelined back-to-back SPM loads are permitted; only the
  2-cycle consumer separation is enforced. 3b inherits this.
- **DEC-COMMIT** (Plan 2c, user-confirmed, inherited): per-magic additive
  commits; no rebase, reset, amend, force-push, cherry-pick-drop, or `git
  revert`. On any regression, manually undo or patch back the working-tree edit
  and retry. 3b inherits this.
- **DEC-SEAM-MERGE** (Plan 2a, carry-forward, now producer-side): magic
  31↔32 seam metadata contract at `s1c[176..191]` is the contract this plan
  edits the PRODUCER side of (magic 31); 3b restates the contract locally and
  AC-9 enforces it.
- **DEC-CORRECTNESS-BAR** (Plan 3a, user-confirmed, inherited): the end-of-plan
  `gwfa_check_correctness.py 2 -t 56 = 295/295` is a hard pass/fail bar, not a
  directional target. AC-1 enforces this as the `l5` commit blocker.
- **DEC-M31-AUTOINC** (Plan 2a, user-confirmed, inherited): magic-31 per-PE
  MM cursor advancement is the C++-stand-in form (per-PE cursors incremented
  after each `mvdq_copy`), NOT a hypothetical native ISA register-autoincrement
  flag. 3b preserves this; no redesign of the cursor model is in scope.
- **DEC-3B-LAUNCH-GATE** (plan-3b, user-confirmed): 3b coding does NOT
  start from an in-flight 3a branch; it waits for Plan 3a to land on a
  recorded git SHA where `gwfa_check_correctness.py 2 -t 56 = 295/295`.
  Task `l4` records the SHA; no `l4*` coding commit lands before `l4abi`.
- **DEC-M24-FAST-PATH** (plan-3b, user-confirmed): magic 24's `all_full`
  fast path IS preserved as an architectural label + goto branch (upper
  bound). The peeled-final path remains intact alongside it. The
  selector is architectural (no C++ `bool`); `l4a` converts the existing
  `if (all_full) { ... } else { ... }` to a label + goto dispatch that
  `gendp-isa-reviewer` accepts under rule 3 / 4.
- **DEC-M31-STAGED-ARRAYS** (plan-3b, user-confirmed): the magic-31
  `nds / d_curs / nis / i_curs` C++ local arrays ARE hoisted into
  `s1c[196..211]` reads inside the mvdq loops via `gr[11]` staging. The
  pre-compute block that materializes these locals is removed; the
  diag-writeback and intv-writeback mvdq inner loops read
  `s1c[196..211]` directly each iteration with 1-NOP s1c gap. This keeps
  the architectural-state invariant intact and removes the
  "register-allocation stand-in" exception; no AC-2 waiver is taken.
- **DEC-3B-SCOPE-SHAPE** (plan-3b, user-confirmed): 3b stays monolithic
  — one plan covering all six magics (24, 25, 28, 29, 30, 31) with a
  single launch gate and single ABI reconciliation. Plan 3c (magics
  32–39) retains its existing shape; no sibling split.
- **DEC-3B-CORRECTNESS-BAR** (plan-3b, user-confirmed): hybrid concrete
  tier split. Magics 24 / 25 / 28 / 30 (`l4av` / `l4bv` / `l4cv` /
  `l4ev`) accept suite citation OR debug-trace assertion in the commit
  message. Magics 29 (`l4dv`) and 31 (`l4fv`) require debug-trace
  assertions UNCONDITIONALLY in the mode-1 log, enumerated in AC-10.
  This strictness split is fixed across the upper / lower path-bound
  axes.

### Cross-Magic Register ABI (Plan 3b extension; authoritative table in Plan 3a)

Plan 3a's preamble is the authoritative Cross-Magic Register ABI. 3b extends that
table with the sort-merge-dedup pipeline live-set for magics 24 / 25 / 28 / 29 /
30 / 31. Task `l4abi` (analyze) reconciles this extension against the launch-HEAD
code before any 3b coding commit lands. The entries below are the draft
extension; `l4abi` may adjust them if post-3a code has drifted.

**Live `gr[]` across 3b-relevant magic boundaries (extending Plan 3a's table).
Semantics: READ = consumes a live-in value; WRITE = produces a live-out value;
THROUGH = must not clobber (live-through, preserved unchanged):**

- `gr[1]`: sort pass number. READ by magic 24 as the per-pass shift amount
  (`shift = gr[1] * 4`). THROUGH on magic 25 / 28 / 29. **TEMP on magic 30**
  (l4abi drift: m30's reload-gather stages `s1c[pe]` / `s1c[8+pe]` through
  `gr[1]` at pe_array.cpp:4239-4241 and 4261-4263 — safe because gr[1] is
  caller-dead at m30 entry per the caller-path walk). In magic 31 it is
  used as a secondary "stash" scratch — `l4abi` confirms `gr[1]` is
  caller-dead on magic 30 / 31 entry by walking the full caller path
  (sort loop exit → merge driver → dedup driver → `gr[2] = 0` → magic 30
  reload loop → magic 31), not by citing any single magic boundary in
  isolation.
- `gr[2]`: sort / merge / dedup cursor. WRITE by magic 24
  (`gr[2] = cursor + SORT_TILE`) and magic 31 (`gr[2] += DEDUP_TILE`). The
  dedup driver resets it (`gr[2] = 0`) between magic 29 and magic 30; magic
  29 / 30 are THROUGH.
- `gr[3]`: MM source base (sort). READ by magic 24 as
  `mm_srcs[pe] = gr[3] + (pe_start + cursor) * 2`; THROUGH on magic 25. Magic
  28 reloads its own `diag_base` from `s1c[153]`, does NOT read `gr[3]`, and
  only RESTORES `gr[3] = diag_base` on exit (pe_array.cpp:3749). Magic 29
  similarly reads `diag_base` from `s1c[153]` and does not read `gr[3]`.
- `gr[4]`: MM destination base. WRITE by magic 28 (`gr[4] = MM_SORT_BUF`) and
  by magic 29 (`gr[4] = MM_DEDUP_DIAG_OUT` = opposite of `active_diag_base`).
  READ by magic 25 (MM dst base; `mm_dsts[pe] = gr[4] + diag_off*2`) and
  magic 31 (diag MM writeback base). THROUGH on magic 24 (sort-driver
  live-in before m28 writes it) and magic 30 (live-in from m29, live-out
  to m31).
- `gr[6]`: loop bound. WRITE by magic 28 (`gr[6] = niter`) and by magic 29
  (`gr[6] = (niter == 0) ? DEDUP_TILE : niter`); consumed by the merge /
  dedup driver `bge` check in the instruction generator. THROUGH on magic
  24 / 25 (sort-driver live-through; m24 / m25 do not touch gr[6]).
- `gr[7]`: WRITE by magic 29 (`gr[7] = MM_DEDUP_INTV_OUT`); READ by magic 31
  as the intv MM writeback base. Before magic 29, `gr[7]` is a magic-19
  local temp — the sort → dedup driver transition is where it takes on its
  cross-magic role. THROUGH on magic 30.
- `gr[11]`: CLAUDE-safe controller scratch slot — every SPM-load-to-destination
  is routed through `gr[11]` with 3-NOPs per CLAUDE.md SPM destination rule;
  every `s1c` staged load uses `gr[11]` with 1-NOP gap
  (BL-20260417-ctrl-sync-gr). Magic-local; not live across any 3b magic
  boundary.
- `gr[12]`: GWFA wavefront-distance counter (magic 3 / 5 / 7 live state) —
  THROUGH on every 3b magic; NEVER touch.
- `gr[13]`: PE-sync AND of PE `gr[10]` (`pe_array::tick`) — THROUGH; NEVER
  touch.
- `gr[24]`: sort / merge / dedup count. Semantics shift across phases:
  (a) during the sort driver loop, `gr[24]` is the current sort count (READ
  by magic 24 as `n_a = gr[24]`); (b) at magic 28, it carries the current
  `n_a` for the merge split (magic 28 reloads from `s1c[148]` inside but
  RESTORES `gr[24] = n_a` on exit, preserving the live-out contract);
  (c) at magic 29, it is the post-merge `n_a` (READ `n_a = gr[24]`) and
  preserved live-through on m30 / m31. **Drift correction (l4abi)**:
  magic 32 at HEAD does NOT read `gr[24]` (pe_array.cpp:4538-4722); the
  "live-out to m32" claim in earlier drafts is stale. The value is still
  preserved through m29 / m30 / m31 for any dedup post-processing that
  expects it.
- `gr[28]`: `intv_n`. WRITE by magic 28 on exit (`gr[28] = intv_n`); READ by
  magic 29 (`intv_n = gr[28]`); THROUGH on magic 30 / 31. **Drift
  correction (l4abi)**: magic 32 at HEAD OVERWRITES `gr[28] = intv_n` with
  its own final count at `pe_array.cpp:4722`; the "READ by magic 32
  downstream" claim in earlier drafts is stale. The live-through
  invariant inside the dedup iteration (m29 → m30 → m31) still holds.

**Known magic-local temps (listed for disambiguation; NOT live across
boundaries):**
- `gr[5]`: magic 28 binary-search mid / magic 28 prior-a_sp-stash.
- `gr[11]`: SPM / s1c scratch (recycled per chain).
- `gr[1]`: magic 31 secondary stash (caller-dead on m29 → m31 entry).

**Live `s1c[]` across 3b-relevant magic boundaries:**

- Sort phase (active during magics 24 / 25):
  - `s1c[0..15]`: sort prefix-sum globals (written by magic 19, read by 25)
  - `s1c[16..79]`: per-PE sort bin counts (written by magic 19 step 1, read
    by 25 and downstream scatter)
  - `s1c[80..143]`: sort running offsets (written by magic 19 step 5 as zeros;
    updated by magic 25 via `gr[11]`-staged RMW)
- Merge phase (active during magics 28 / 33 / 35 / 37):
  - `s1c[0..8]`: magic 28 binary-search INTERNAL scratch — `bs_lo[0..2]` at
    `s1c[0..2]`, `bs_hi[0..2]` at `s1c[3..5]`, `bs_target[0..2]` at
    `s1c[6..8]`. OVERWRITTEN at end of magic 28 by the per-PE merge metadata
    writes below — the early-bs scratch is magic-local; the post-bs writes
    are cross-magic and consumed by magic 33 / 35.
  - Post-magic-28 per-PE merge metadata (live across magic 28 → 33 / 35):
    - `s1c[0..3]`: per-PE total output length `pt[pe]` (written
      pe_array.cpp:3612)
    - `s1c[4..7]`: merge output cursor / cumulative output count per PE
      (initialized to 0 by magic 28, updated by magic 35
      pe_array.cpp:3875/3896)
    - `s1c[8..11]`: `src_a[pe]` (written pe_array.cpp:3620, read/updated by
      magic 33 pe_array.cpp:3773/3793)
    - `s1c[12..15]`: `rem_a[pe]` (written pe_array.cpp:3622, updated by
      magic 33)
    - `s1c[16..19]`: `src_b[pe]` (written pe_array.cpp:3623, updated by
      magic 33)
    - `s1c[20..23]`: `rem_b[pe]` (written pe_array.cpp:3625, updated by
      magic 33)
  - `s1c[40..49]`: magic 28 `a_sp / b_sp` split indices (Stage-B
    architectural state; magic-28 internal post-bs compute)
  - `s1c[50..73]`: magic 28 tile-size and source scratch
    (`a0 / a1 / b0 / b1` sizes, `a_srcs / b_srcs`; magic-28 internal only,
    consumed by the four A/B mvdq tile-load sections within the same magic)
- Dedup phase (active during magics 29 / 30 / 31 / 32):
  - `s1c[0..3]`: dedup diag MM sources (written by magic 29)
  - `s1c[4..7]`: dedup diag remaining counts
  - `s1c[8..11]`: dedup intv MM sources
  - `s1c[12..15]`: dedup intv remaining counts
  - `s1c[16..19]`: dedup diag output base per-PE
  - `s1c[20..23]`: dedup diag output cursor per-PE
  - `s1c[24..27]`: dedup intv output base per-PE
  - `s1c[28..31]`: dedup intv output cursor per-PE — also the first-nonzero-tile
    gate for the magic 31 → 32 seam write
- Plan 3a / pipeline seam (read-only for 3b magics):
  - `s1c[144..162]`: magic 16 / 36 / 37 saved state (`diag_base`, `n_a`,
    `intv_n`, `n_phase1`, `active_diag_base`, `active_intv_base`, dedup
    splits). 3b reads these in magic 28 / 29 / 31 via `gr[11]`-staged
    loads; 3b MUST NOT write into this band.
  - `s1c[163..168]`: intv boundary indices (`intv_lo[pe+1]` /
    `intv_hi[pe]` for `pe = 0..2`). **Carve-out (l4abi drift)**: this
    sub-band is WRITTEN by magic 38 (out of 3b scope; pe_array.cpp:3277-
    3278 merge path and no-merge path at :3306-3505) and READ by magic
    29 in 3b scope. The earlier blanket "3b MUST NOT write
    s1c[144..168]" is narrowed: `s1c[163..168]` is still read-only for
    3b code (no 3b magic writes into it), but it is NOT static across
    magic boundaries — m38 is the authoritative writer.
- Magic 31 → 32 seam metadata:
  - `s1c[176..179]`: first-intv lo per PE (written once per PE by magic 31 on
    first nonzero tile, cleared / consumed by magic 32)
  - `s1c[180..183]`: first-intv hi per PE (same gating)
  - `s1c[184..187]`: last-intv lo per PE (updated every nonzero tile)
  - `s1c[188..191]`: last-intv hi per PE (same)
- Magic 31 per-PE writeback state:
  - `s1c[196..199]`: per-call diag count (`nds[pe]`)
  - `s1c[200..203]`: per-call intv count (`nis[pe]`)
  - `s1c[204..207]`: monotonic MM diag cursor per PE
  - `s1c[208..211]`: monotonic MM intv cursor per PE
- Magic 31 magic-local scratch (Round-3 addition; l4abi extension):
  - `s1c[212]`: max_d (diag writeback chunk-outer bound)
  - `s1c[213]`: max_i (intv writeback chunk-outer bound)
  - `s1c[216..219]`: per-PE absolute diag output base
    (`pe_spm + d_out_off`, computed once at m31 entry to eliminate
    the magic_mask runtime ternary)
  - `s1c[220..223]`: per-PE absolute intv output base
    (`pe_spm + i_out_off`)
  - `s1c[224]`: i_off stash (alternate-selector constant)
  Safety: this band (`s1c[212..224]`) is written only at the start of
  magic 31 and is dead by magic 31 exit. It is not read by any other
  magic and not allocated by any other 3b magic. Phase-disjointness:
  the dedup phase does not overlap sort / merge, so this band is free
  within the dedup window. `S1C_SIZE = 8192` per `sys_def.h:158` → the
  range is well below architectural capacity.

**Rule**: any magic in 3b scope that uses a slot for temp computation MUST
verify that slot is NOT live across that magic's boundary at launch-time HEAD.
Use `s1c` save/restore (via `gr[11]`) if a live register must be temporarily
borrowed. The sort / merge / dedup `s1c[0..79]` overlap is safe by construction
because the three phases never execute concurrently, AND magic 28's early-bs
`s1c[0..8]` scratch use is overwritten by that magic's own per-PE metadata
writes before any cross-magic consumer reads; 3b must preserve this invariant
and not introduce a cross-phase reuse.

### Validation rules
- After EACH magic's coding task (`l4av`, `l4bv`, `l4cv`, `l4dv`, `l4ev`,
  `l4fv`):
  - `make -j ADDRESS_SANITIZER=0`
  - `gwfa_check_correctness.py 1 -t 56` — must pass 15/15
  - `gendp-isa-reviewer` on the changed magic — zero unwaived P0/P1 findings
  - one additive commit (no history rewrite)
- `gwfa_check_correctness.py 1 -t 56` is a full-pipeline run; every magic is
  exercised end-to-end on every test case, so a later magic's commit
  automatically revalidates earlier changes on the same mode-1 run.
- The risky-arm edge cases (see AC-10) MUST be exercised by each magic's
  `l4*v` mode-1 suite OR by a targeted debug-trace-confirmed test input
  extended at `l4` launch-gate time.
- At end of plan (`l5`): `gwfa_check_correctness.py 2 -t 56` — must be 295/295.

---

## Goal Description

ISA-lower controller magics 24, 25, 28, 29, 30, and 31 on top of a recorded
post-Plan-3a `gwfaIsaLikeAll` HEAD. Each magic is lowered one at a time with
its own edit-only task, build + mode-1 verify + `gendp-isa-reviewer` run +
additive commit. The magic-31 → magic-32 seam metadata contract at
`s1c[176..191]` is preserved producer-side (first-write-once, last-update-each,
sampled-before-increment). At end of plan, every touched magic passes the
reviewer with zero unwaived P0 / P1 findings and `gwfa_check_correctness.py 2
-t 56` returns 295/295.

## Prerequisites

- Plans 1, 2a, 2b, 2c, and 3a complete and merged on branch `gwfaIsaLikeAll`.
- Launch HEAD is a recorded SHA that passes `gwfa_check_correctness.py 2 -t 56
  = 295/295` (verified by task `l4` launch gate).
- Launch HEAD's per-magic audit for 24 / 25 / 28 / 29 / 30 / 31 (from Plan 2c's
  `plan2c_audit_matrix.md` plus any 3a-closing audit artifacts) is the input
  to `l4`'s absorb/defer pass. Open `fix-required` items on these magics are
  NOT a prerequisite blocker; `l4` either absorbs each into the corresponding
  `l4*` task or defers it with a recorded reason.

## Acceptance Criteria

Each AC uses TDD-style positive and negative tests. Positive tests should pass
and negative tests should be rejected when the criterion holds.

- AC-1: Correctness is preserved end-to-end on the post-Plan-3a HEAD.
  - Positive Tests:
    - `gwfa_check_correctness.py 1 -t 56` returns 15/15 after every per-magic
      fix, before that magic's commit.
    - `gwfa_check_correctness.py 2 -t 56` returns 295/295 at end of plan
      (task `l5`).
    - Edge-path coverage confirmation at `l4` launch-gate: `l4` confirms the
      mode-1 test-input set exercises all of (a) magic-24 `all_full` fast
      path AND peeled path, (b) magic-28 skip-merge arm
      (`n_phase1 <= 0 || n_tail <= 0`), (c) magic-29 `intv_n == 0` and
      `iv_s > intv_hi[pe]` clamp arms, (d) magic-30 no-refill arms for diag
      and intv, and (e) magic-31 zero-`nis` continuation plus the
      first-nonzero-tile gate. Any arm not exercised by the 15-case mode-1
      suite is covered by a targeted input addition at `l4` time OR by a
      debug-trace-confirmed assertion in the corresponding `l4*v` gate.
  - Negative Tests:
    - Any mode-1 regression after a change blocks the magic's commit; manually
      undo or patch back the working-tree edit before retrying (no `git
      revert` / rebase / reset / amend).
    - A `l4*v` pass signed off before its corresponding edge arm is confirmed
      exercised (either in the 15-case suite or by an explicit trace).

- AC-2: No C++ runtime variables carry architectural state across ISA lines
  inside any 3b-in-scope magic body.
  - Positive Tests:
    - Every C++ local inside a changed magic body is one of: (a) consumed on
      the same ISA line it is assigned, (b) a `constexpr` / loop-index / PE
      macro index that `gendp-isa-reviewer` accepts as compile-time, OR (c)
      an explicitly-architectural staging scratch whose live range ends on
      the same ISA line (e.g. magic 31's `nis` read → immediate `if (nis ==
      0)` branch).
    - C++ local ARRAYS (`tile_ns[4]`, `mm_srcs[4]`, `spm_dsts[4]` in magic 24;
      `ns[4]`, `mm_dsts[4]`, `spm_srcs[4]` in magic 25; `splits[5]`,
      `intv_lo[4]`, `intv_hi[4]`, `dd0/1[4]`, `d_srcs[4]`, `ii0/1[4]`,
      `i_srcs[4]` in magic 29; `d_tile[2][4]`, `d_src[2][4]`, `i_tile[2][4]`,
      `i_src[2][4]` in magic 30) are either hoisted into `s1c[]` architectural
      slots OR proved to be macro-consumed (loop index drives direct read) on
      the same ISA line. The magic 31 arrays `nds[4]`, `d_curs[4]`, `nis[4]`,
      `i_curs[4]` are REMOVED entirely per resolved `DEC-M31-STAGED-ARRAYS`;
      the mvdq inner loops read `s1c[196..211]` directly via `gr[11]`
      staging.
  - Negative Tests:
    - Any plain C++ local assigned on one ISA line and read on a later line
      inside the same magic (e.g. `cursor`, `n_a_per_pe`, `max_words`,
      `pa_s / pa_n / pb_s / pb_n`, `rem_d / rem_i / src_d / src_i`,
      `max_d / max_i`).
    - A C++ local ARRAY whose element is written in one `for (pe ...)` pass
      and read in a later pass without being backed by an `s1c[]` slot.

- AC-3: No runtime `if/else/for/while` in any changed magic body, except
  approved macro unrolls and `constexpr` forms.
  - Positive Tests:
    - Every control-flow construct inside a changed magic is one of: a
      `for (int pe = 0; pe < 4; ...)` or `for (int buf = 0; buf < 2; ...)`
      PE / buffer unroll, a compile-time-bounded macro expansion the reviewer
      accepts as fixed, OR a label + conditional branch (goto / `bge` /
      `beq`).
    - Every `continue` inside a 3b magic is rewritten as a label-guarded
      `goto` past the body. Current `continue` sites to convert: magic 24
      peeled-final loop (`if (j >= words) continue`), magic 25 bin
      writeback (`if (j >= words) continue`), magic 28 tile-load mvdq
      sections (`if (j >= w) continue`, 4 sites), magic 29 mvdq macro
      (`if (j >= w) continue`, expanded 4×), magic 30 mvdq macro (same, 4×),
      magic 31 writeback inner (`if (j >= w) continue`, 2 sites), magic 31
      seam-write (`if (nis == 0) continue`), magic 29 `if (cnt <= 0)
      continue`.
    - Every runtime `if (expr) body` with data-dependent `expr` (e.g.
      `if (remaining < 0) remaining = 0`, `if (w > max_words) max_words = w`,
      `if (all_full) {...} else {...}`, `if (gr[11] == 0 && rem_d > 0)`)
      becomes either a min/max-style branch-label pair or a compile-time
      macro-expanded clamp.
  - Negative Tests:
    - Any surviving runtime `while` or `for (int i = 0; i < dynamic_bound;
      i++)` with a non-compile-time bound inside a changed magic.
    - Any surviving `continue` or `break` that depends on runtime data.
    - A multi-arm `if/else if/else` with data-dependent selection.
    - The magic-24 `if (all_full) { ... } else { ... }` fast/slow split
      surviving as a `bool` dispatch.

- AC-4: Paired VLIW slots in every changed magic are RAW- and WAW-free.
  - Positive Tests:
    - For each "pair of lines = one cycle" block in a changed magic, the
      second slot does not read a register written by the first slot
      (pre-cycle read semantics).
    - `gendp-isa-reviewer` reports zero paired-slot RAW and zero WAW findings
      on each changed magic after its `l4*v` commit.
  - Negative Tests:
    - Any paired-slot RAW where slot 1 reads slot 0's destination on the same
      cycle.
    - A WAW pairing (both slots write the same destination) in a changed
      magic.

- AC-5: SPM and S1c loads respect their documented latencies, with reordering
  preferred over naked NOP padding where reorderable work exists.
  - Positive Tests:
    - For every `... = spm[...]` in a changed magic, the first consumer of
      that destination is at least 2 VLIW cycles = 4 ISA lines after the
      load. The gr[11]-staged 3-NOP discipline (one gr[11] load followed by
      3 NOPs before the consumer) satisfies this.
    - For every `... = s1c[...]` in a changed magic, the first consumer is
      at least 1 VLIW cycle = 2 ISA lines after the load (gr[11]-staged
      1-NOP discipline).
    - Inside magic 29's per-PE tile-sizing loop and magic 28's per-PE
      post-bs compute loop, at least one useful reorderable instruction
      fills each SPM gap where such an instruction is available in-scope.
      Each reordered gap carries a brief code comment naming the filler op
      (e.g. `// SPM lat 2/3 — filled by: gr[4] = gr[11] + gr[1]`). Naked
      NOP padding is acceptable only where no independent in-scope work
      exists.
  - Negative Tests:
    - Any consumer reads a SPM-loaded register on the same cycle or on the
      immediately next VLIW cycle (< 4 ISA lines away).
    - Any S1c consumer reads on the same cycle (< 2 ISA lines).
    - A gap filled entirely with NOPs when the same pass contains documented
      independent work that could legally move into the gap.

- AC-6: Every MM / S2 LOAD has a `// waitLSQ` annotation and the required
  cycle separation before its first consumer.
  - Positive Tests:
    - Every MM load in a changed 3b body is followed by a `// waitLSQ`
      annotation and at least one cycle of unrelated instructions (≥ 2 ISA
      lines) before the first reader of the load's destination. Known MM
      load sites in 3b scope: magic 28 binary-search body (6 MM loads per
      bs step — `abase + mid*2` and `bbase + (bi2-1)*2`, unrolled to 3 p
      steps). Other 3b magics issue only `mvdq_copy` / SPM / s1c loads, not
      scalar MM reads.
    - No 3b magic contains a bare `mm[...]` scalar load without `//
      waitLSQ`.
  - Negative Tests:
    - An MM load whose consumer reads the destination on the immediately
      next ISA line.
    - A consumer correctly delayed but missing the annotation (the ISA
      generator consumes the annotation to emit the LSQ-wait op — missing
      annotation = missing ISA op).
    - The AC asserted on an `mvdq_copy(&mm[...], &spm[...])` MM WRITE site
      (mvdq writes are not subject to AC-6).

- AC-7: Bulk contiguous transfers in every changed magic use `mvdq` (or
  `mvd`-shaped helpers) round-robin across PEs; scalar `mv` only where data
  is non-contiguous.
  - Positive Tests:
    - Every contiguous-stride bulk transfer uses `mvdq_copy` and is written
      as chunk-outer, PE-inner (`for (j = 0; j < max_words; j += 8) for
      (pe ...) mvdq_copy(...)`). This pattern is already in place at magic
      24 phase 2, magic 25 chunk loop, magic 28's four A/B buf mvdq
      sections, magic 29's M29_MVDQ macro (4 passes), magic 30's M30_MVDQ
      macro (4 passes), and magic 31's diag and intv writeback loops.
    - Magic 28's `M28_MVDQ` and related mvdq tile-load sections and magic
      29 / 30's mvdq passes remain chunk-outer / PE-inner post-rewrite.
    - The magic 24 `all_full` fast path is preserved (per resolved
      DEC-M24-FAST-PATH) as a chunk-outer / PE-inner mvdq loop; its
      selector becomes a label / goto branch architecturally rather
      than a C++ `if`.
  - Negative Tests:
    - A scalar `for (pe...) for (j...) mvdq_copy(...)` loop (PE-outer) in a
      changed magic; this would hit the same bank group consecutively.
    - A `for (pe...) { for (j...) mm[...] = spm[...]; }` scalar copy over
      contiguous data without a cited non-contiguity annotation.
    - Regression of the magic-28 / 29 / 30 / 31 mvdq macros to a serial
      per-PE copy.

- AC-8: Cross-magic register and s1c ABI is preserved; no temp use clobbers a
  live-across-boundary slot without an explicit save/restore.
  - Positive Tests:
    - Magic 24 READS `gr[1]` and `gr[3]` and `gr[24]`; advances `gr[2]`;
      preserves `gr[3]`, `gr[24]` live-out; uses `gr[11]` as scratch.
    - Magic 25 preserves `gr[3]`, `gr[4]`, `gr[24]` live-through; writes
      only `gr[11]` as scratch.
    - Magic 28 WRITES `gr[4] = MM_SORT_BUF` and `gr[6] = niter` and
      `gr[28] = intv_n`; RESTORES `gr[3] = diag_base` and `gr[24] = n_a`
      on exit; uses `gr[5]` / `gr[11]` as binary-search temps; preserves
      `gr[28]` input contract (reads via `s1c[146]`, stores on exit).
    - Magic 29 WRITES `gr[4] = MM_DEDUP_DIAG_OUT`, `gr[7] = MM_DEDUP_INTV_OUT`,
      and `gr[6] = niter`; READS `gr[24]` and `gr[28]` as live-in; preserves
      `gr[24]` and `gr[28]` live-out; uses `gr[11]` only.
    - Magic 30 preserves `gr[4]`, `gr[7]`, `gr[24]`, `gr[28]` live-through
      (reads nothing from that set; writes none); uses `gr[11]` as scratch.
      Magic 30 may also use `gr[1]` as a secondary stash ONLY if `l4abi`
      confirms `gr[1]` is caller-dead at magic 30 entry via the full caller
      path (sort loop → merge driver → dedup driver → `gr[2] = 0` → magic 30).
    - Magic 31 READS `gr[4]`, `gr[7]`; advances `gr[2] += DEDUP_TILE`;
      preserves `gr[24]`, `gr[28]` live-out; uses `gr[11]` as primary scratch
      and `gr[1]` as a secondary stash when `l4abi` confirms `gr[1]` is
      caller-dead on magic 31 entry (the deadness claim is walked over the
      full caller path, NOT established by citing any single magic boundary
      in isolation).
    - No 3b magic writes into the Plan 3a seam `s1c[144..168]` band except
      through an `l4abi`-recorded save/restore.
  - Negative Tests:
    - A new temp allocation in any 3b magic that touches `gr[12]`, `gr[13]`,
      `gr[7..10]` (except magic 29's setting of `gr[7]` as an output) without
      the `l4abi` entry.
    - A magic 31 edit that writes `gr[24]` or `gr[28]` (those are live-out
      for magic 32).
    - A magic 28 edit that loses the `gr[28] = intv_n` final store (magic 29
      reads it).

- AC-9: The magic 31 → magic 32 seam contract at `s1c[176..191]` is preserved.
  - Positive Tests:
    - Magic 31 writes `s1c[176+pe]` (first-intv lo) and `s1c[180+pe]`
      (first-intv hi) exactly once per PE, gated by `s1c[28+pe] == 0`
      (the pre-increment cumulative intv cursor: zero iff magic 31 has
      never produced intv output for this PE on this call chain).
    - Magic 31 updates `s1c[184+pe]` (last-intv lo) and `s1c[188+pe]`
      (last-intv hi) on every call where `nis[pe] > 0`.
    - The seam-write gate samples `s1c[28+pe]` BEFORE the per-call
      cumulative intv cursor is advanced at the end of magic 31.
    - Every SPM load in the seam-write body is gr[11]-staged with a 3-NOP
      gap (so the consumer `s1c[...] = gr[11]` lands cycle N+2).
    - Magic 32's consumption of `s1c[176..191]` is NOT edited by 3b (out of
      scope); `l4abi` records its shape at launch HEAD to confirm the
      contract alignment.
  - Negative Tests:
    - Magic 31 writes `s1c[176+pe]` / `s1c[180+pe]` on every call (loses
      first-write-once gating).
    - Magic 31 samples `s1c[28+pe]` AFTER the cumulative cursor advance
      (gate fires exactly zero times for every PE).
    - Magic 31 omits the seam-write block entirely.
    - Magic 31 writes the seam via a scalar `for (pe...)` where the SPM gap
      is less than 2 VLIW cycles between the SPM load and the s1c store.

- AC-10: Edge-path coverage for the risky data-dependent arms is explicit,
  with tier-specific strictness per `DEC-3B-CORRECTNESS-BAR`.
  - Positive Tests:
    - `l4` launch-gate output names each of the following arms and
      confirms the 15-case mode-1 suite exercises each:
      - magic 24 `all_full` fast path AND peeled-final path
      - magic 28 skip-merge arm (`n_phase1 <= 0 || n_tail <= 0`)
      - magic 29 `intv_n == 0` (the `if (intv_n > 0)` guard around
        `intv_hi[pe] = s1c[166+pe]` and `intv_lo[pe] = s1c[163+pe-1]`
        in pe_array.cpp:3986) AND the `iv_s > intv_hi[pe]` clamp AND
        the `iv_e < intv_hi[pe]` clamp (pe_array.cpp:4001..4003; note
        that `i1r < 0` is dead after the preceding clamps and is NOT
        a risky arm in current code)
      - magic 30 no-refill arm (all four `(pe, buf)` combinations see
        flag already set)
      - magic 31 zero-`nis` continuation, first-nonzero-tile gate
        firing for each PE exactly once, and the last-nonzero-tile
        seam update
    - Lower-risk magics (24, 25, 28, 30): the corresponding `l4av` /
      `l4bv` / `l4cv` / `l4ev` commit message MUST cite either
      (a) which 15-case mode-1 test inputs exercise each AC-10 arm for
      that magic, OR (b) a debug-trace assertion line the mode-1 run
      is required to emit.
    - Higher-risk magics (29, 31): the `l4dv` and `l4fv` mode-1 run MUST
      emit debug-trace assertions UNCONDITIONALLY, as follows:
      - `l4dv`: assertions confirming each of the `intv_n == 0`
        guard path, the `iv_s > intv_hi` clamp path, and the
        `iv_e < intv_hi` clamp path fired at least once on the
        15-case suite.
      - `l4fv`: assertions confirming the first-nonzero-tile seam
        write fired exactly once per PE across the suite AND the
        last-nonzero-tile seam update fired for each PE on a
        nonzero-tile call.
    - Any arm not exercised by the 15-case suite is covered by a
      targeted input addition at `l4` time; this applies to BOTH tiers.
  - Negative Tests:
    - An `l4dv` or `l4fv` signoff without the unconditional
      debug-trace assertions.
    - An `l4av` / `l4bv` / `l4cv` / `l4ev` signoff with no statement
      of edge-arm coverage (neither suite citation nor trace
      assertion).
    - A commit that changes the `all_full` dispatch logic (magic 24)
      without citing a test input that drives the peeled path, or
      vice versa.
    - A magic-31 commit that does not assert the first-write-once
      seam gate fired on the intended test case.

- AC-11: `gendp-isa-reviewer` reports zero unwaived P0 / P1 findings on each
  changed magic after its per-magic commit.
  - Positive Tests:
    - Reviewer summary for magic 24, 25, 28, 29, 30, and 31 shows zero
      unwaived P0 / P1 after the corresponding `l4*v`.
    - Every listed P0 / P1 is explicitly waived with a cited reason (e.g.
      seam waiver inherited from DEC-SEAM-MERGE, or an `l4abi`-authorized
      cross-magic temp).
    - P2 findings are recorded in the per-magic commit message (chosen as
      the single artifact of record for 3b) so the reviewer trail is
      complete.
  - Negative Tests:
    - A per-magic commit lands with an unwaived P0 / P1 reviewer finding
      on the changed magic.
    - A P2 finding that is neither fixed nor recorded in the per-magic
      commit message.

- AC-12: Launch-gate ABI reconciliation is recorded in the plan artifacts
  before any coding commit lands.
  - Positive Tests:
    - Task `l4` records the launch-time `git rev-parse HEAD` and confirms
      `gwfa_check_correctness.py 2 -t 56 = 295/295` on that SHA.
    - Task `l4abi` walks the Cross-Magic Register ABI extension above
      against launch-HEAD code; any drifted entries are updated in the
      preamble and the update commit precedes `l4a`.
    - `l4abi` output confirms the edge-path arms named in AC-10 are either
      exercised by the 15-case suite or that a trace / input-extension
      plan is recorded before `l4*v` signoff.
    - `l4abi` explicitly enumerates every `s1c[]` slot written by each 3b
      magic and confirms none alias the Plan 3a seam band `s1c[144..168]`
      without a recorded save/restore pair.
  - Negative Tests:
    - A `l4*` coding commit lands before `l4abi` has recorded the
      reconciled ABI.
    - The plan proceeds with an ABI extension that contradicts the launch-
      HEAD code (e.g. a `gr[]` listed as live that is no longer live, or a
      missing `s1c[]` slot).

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)
Everything in the Lower Bound is satisfied AND: every SPM / s1c gap in every
changed magic is filled with in-scope independent reorderable work (no naked
NOP padding where filler work exists), per AC-5 positive test. Optionally,
the four lower-risk `l4*v` commit messages cite debug-trace assertions in
addition to mode-1 suite coverage (not instead of). End-of-plan mode 2
returns 295/295.

### Lower Bound (Minimum Acceptable Scope)
All six controller magics pass `gendp-isa-reviewer` with zero unwaived P0 / P1.
Every C++ local array is hoisted into `s1c[]` OR proved to be macro-consumed
(read on the same ISA line as the driving PE index). Every runtime `continue`
in mvdq inner loops is converted to label + goto past the body. Every MM
load in magic 28's binary search body has a `// waitLSQ` annotation plus the
required cycle separation. The magic 31 → 32 seam contract (first-write-once,
last-update-each, sampled-before-increment) is preserved verbatim. The magic
24 `all_full` fast path is preserved as an architectural label / goto branch
with the peeled path intact (DEC-M24-FAST-PATH is resolved; both paths are
mandatory). The magic 31 `nds / d_curs / nis / i_curs` C++ local arrays are
removed and replaced with direct `s1c[196..211]` reads inside the mvdq loops
(DEC-M31-STAGED-ARRAYS is resolved HOIST). For magics 24 / 25 / 28 / 30, the
`l4*v` commit message cites either mode-1 suite coverage OR a debug-trace
assertion for each AC-10 edge arm. For magics 29 and 31, `l4dv` and `l4fv`
emit unconditional debug-trace assertions per AC-10. SPM / s1c gap filling
via reordering is preferred but not required where no in-scope reorderable
work is available; naked NOP padding is acceptable there. End-of-plan mode 2
returns 295/295.

### Allowed Choices
- **Can use**: per-magic edit-only + verify-commit split (`l4a` → `l4av`,
  etc.); per-magic additive commits; `gendp-isa-reviewer` P2 suppressions
  with recorded rationale in the commit message; macro-style PE unrolls
  (`for (int pe = 0; pe < 4; ++pe)`) and buffer unrolls
  (`for (int buf = 0; buf < 2; ++buf)`); `constexpr`; `mvdq_copy` / `mvd`-shaped
  helpers; `s1c[]` architectural staging in place of C++ local arrays; the
  existing `gr[11]`-staged SPM 3-NOP and s1c 1-NOP disciplines
  (BL-20260417-ctrl-sync-gr); `gr[1]` as a secondary stash register in
  magic 31 when confirmed caller-dead by `l4abi`.
- **Cannot use**: runtime `if/else/for/while` inside changed magic bodies
  except approved macro forms; `std::min`/`std::max` on the controller;
  nested indirect memory reads (`mm[s1c[X]]` or `mm[gr[s1c[X]]]`) in
  executable logic; helpers that hide live architectural state in C++
  locals; edits to magic 15, 16, 18, 19, 20, 32, 33, 34, 35, 36, 37, 38,
  39 (all out of 3b scope); edits to `fin0_load_batch()` (Plan 3a scope);
  redefining the `DEC-M31-AUTOINC` C++ per-PE cursor semantics;
  `git` commands that modify history; skipping `gendp-isa-reviewer` on a
  changed magic.

> **Note on Deterministic Designs**: The 12 rules, the inherited Plan 3a
> decisions (DEC-SPM-MODEL, DEC-COMMIT, DEC-SEAM-MERGE, DEC-CORRECTNESS-BAR,
> DEC-M31-AUTOINC), the resolved plan-3b decisions (DEC-3B-LAUNCH-GATE,
> DEC-M24-FAST-PATH, DEC-M31-STAGED-ARRAYS, DEC-3B-SCOPE-SHAPE,
> DEC-3B-CORRECTNESS-BAR), and the existing code shape anchor a highly
> deterministic lowering target. After Phase 6 resolution, upper and
> lower bounds now differ on only two axes:
> (a) whether every staged SPM / s1c gap is filled with useful work
> (upper) or NOP-padded where no reorderable work exists (lower), and
> (b) whether the four lower-risk magics (24 / 25 / 28 / 30) emit
> optional debug-trace assertions in addition to mode-1 suite coverage
> (upper) or rely on suite coverage alone (lower). Magic 24 fast-path
> preservation, magic 31 array hoist, monolithic scope shape, the
> hybrid tier-concrete correctness bar with mandatory traces for m29 /
> m31, launch-gate sequencing, AC-1 / AC-2 / AC-3 / AC-4 / AC-7 / AC-8 /
> AC-9 / AC-11 / AC-12 coverage, per-magic reviewer cadence, and
> per-magic additive commit are ALL fixed and do not vary between
> bounds.

## Feasibility Hints and Suggestions

> **Note**: Conceptual suggestions only.

### Conceptual Approach

1. **Launch gate** (`l4`, analyze): Record `git rev-parse HEAD` on the
   post-3a landed SHA (per resolved DEC-3B-LAUNCH-GATE); run
   `gwfa_check_correctness.py 2 -t 56 = 295/295` on that SHA; confirm
   Plan 3a has closed; enumerate the 15-case mode-1 suite's coverage
   of the AC-10 edge arms and either extend the suite with targeted
   inputs OR mandate a trace-emit requirement per `l4*v` (the strictness
   tier split is already fixed by resolved DEC-3B-CORRECTNESS-BAR — m29 /
   m31 traces are unconditional; m24 / m25 / m28 / m30 use suite-OR-trace).
   Absorb / defer any still-open Plan-2c or Plan-3a fix-required items on
   magics 24 / 25 / 28 / 29 / 30 / 31. Commit the reconciled ABI + launch
   record as a plan-artifact-only commit.

2. **ABI extension and clobber audit** (`l4abi`, analyze): Walk the
   Cross-Magic Register ABI extension above against post-3a HEAD; identify
   every `gr[]` / `s1c[]` slot read or written by each in-scope magic;
   classify each as live-in, live-out, temp, or seam slot; cross-reference
   the `BL-20260413-gr-clobber` and `BL-20260417-ctrl-sync-gr` bitlessons.
   Output: phase-scoped liveness appendix in this plan file and a per-magic
   "temp set" for the coding tasks. Confirm `gr[1]` caller-dead on magic 31
   entry.

3. **Magic 24 lowering** (`l4a` → `l4av`): Hoist `tile_ns[4]`, `mm_srcs[4]`,
   `spm_dsts[4]`, `max_words`, `shift`, and `n_a_per_pe` into `s1c[]` (or
   consume them on the same ISA line as the driving PE index). Convert the
   `if (remaining < 0) remaining = 0` and `if (w > max_words) max_words = w`
   patterns to label + goto `min`/`max` macros. Per `DEC-M24-FAST-PATH`
   (user-confirmed), preserve BOTH the `all_full` fast path AND the
   peeled-final path, converting `if (all_full) { fast } else { peeled }`
   into an architectural label + goto dispatch (no C++ `bool`; the
   selector is a compare + `bge` / `beq` / `bne` branch). Convert `if (j
   >= words) continue` inside the peeled mvdq to a label + goto. Verify
   the chunk-outer / PE-inner `mvdq_copy` pattern is preserved in both
   paths. `gr[2] += SORT_TILE` advance remains as-is (architectural
   cursor update). Build, mode 1, reviewer, commit.

4. **Magic 25 lowering** (`l4b` → `l4bv`): Magic 25 is already mostly
   gr[11]-staged. Remaining work: hoist `ns[4]`, `mm_dsts[4]`, `spm_srcs[4]`,
   `max_words` into `s1c[]` or same-ISA-line consumption; convert
   `if (w > max_words) max_words = w` to label + branch; convert the mvdq
   `if (j >= words) continue` to label + goto; verify the per-bin bin
   iteration macro-unrolls cleanly for `SORT_RADIX_BINS` (constexpr bound);
   preserve the gr[11]-staged running-offset RMW pattern. Build, mode 1,
   reviewer, commit.

5. **Magic 28 lowering** (`l4c` → `l4cv`): Magic 28 already has the
   3-unrolled binary search converted to label + goto with `s1c[0..8]`
   architectural state and per-p goto labels (m28_bs_top, m28_bs_step_any,
   m28_bs_step0/1/2, m28_bs_p{0,1,2}_hi, m28_bs_step_end, m28_bs_done). The
   remaining work is:
   - Hoist post-bs C++ locals `pa_s`, `pa_n`, `pb_s`, `pb_n`, `pt`,
     `max_pt`, `a0 / a1 / b0 / b1 / rem_a / rem_b` into `s1c[50..73]`
     staging OR prove same-ISA-line consumption.
   - Convert the runtime `if (n_phase1 < 0) n_phase1 = 0;
     if (n_phase1 > n_a) n_phase1 = n_a` clamps to label + branch.
   - Convert the runtime `if (pt > max_pt) max_pt = pt` to a label +
     branch max.
   - Confirm every `mm[abase + ...]` / `mm[bbase + ...]` load inside the
     bs body is followed by `// waitLSQ` + NOP (already in place; verify
     no regression).
   - Convert the four tile-load mvdq sections' `if (j >= w) continue` and
     `if (v > mw) mw = v` to label + goto.
   - Preserve the existing `s1c[0..23]` overwrite at end-of-bs (per-PE
     metadata writes); this is safe by construction per the ABI note.
   Build, mode 1, reviewer, commit.

6. **Magic 29 lowering** (`l4d` → `l4dv`): Magic 29 is the biggest
   contract-risk magic (split semantics + live-out for `gr[4] / gr[6] /
   gr[7] / gr[28]`), not the largest body (magic 28 is the largest
   body; 28 > 31 > 29 by line count). Hoist
   `splits[5]`, `intv_lo[4]`, `intv_hi[4]`, `dd0[4]`, `dd1[4]`, `d_srcs[4]`,
   `ii0[4]`, `ii1[4]`, `i_srcs[4]` into `s1c[]` staging. Convert the
   `if (iv_s > intv_hi[pe]) iv_s = intv_hi[pe]`, `if (iv_e < intv_hi[pe])
   iv_e = intv_hi[pe]`, `if (i1r < 0) i1r = 0`, `if (total > max_total)
   max_total = total` patterns to label + branch. Expand `M29_MVDQ` macro's
   `if (j >= w) continue` and `if (w > mw) mw = w` to goto + label.
   Preserve the `gr[4] = MM_DEDUP_DIAG_OUT`, `gr[7] = MM_DEDUP_INTV_OUT`,
   and `gr[6] = niter` live-out contract. Rely on `l4abi`'s verification
   that magic 38's writer-side `s1c[163..168]` layout matches magic 29's
   reader `intv_lo[pe] = s1c[163 + pe - 1]` and `intv_hi[pe] = s1c[166 +
   pe]`. Build, mode 1, reviewer, commit.

7. **Magic 30 lowering** (`l4e` → `l4ev`): Hoist `d_tile[2][4]`,
   `d_src[2][4]`, `i_tile[2][4]`, `i_src[2][4]` arrays into `s1c[]` or
   confirm same-ISA-line macro consumption (PE-outer, buf-inner is the
   iteration order; each cell is assigned in pass 1 and read in pass 2 via
   the M30_MVDQ expansion — they ARE cross-line architectural state).
   Convert `if (gr[11] == 0 && rem_d > 0)` to label + branch. Convert `if
   (tile > DEDUP_TILE)` clamp to label + branch. Convert M30_MVDQ inner `if
   (j >= w) continue` to goto + label. Preserve the pass-3 meta update
   pattern. Build, mode 1, reviewer, commit.

8. **Magic 31 lowering** (`l4f` → `l4fv`): Magic 31 is the most ISA-lowered
   in 3b scope. Remaining work is concentrated in:
   - Per `DEC-M31-STAGED-ARRAYS` (user-confirmed HOIST): REMOVE the
     `int nds[4] / d_curs[4] / nis[4] / i_curs[4]` pre-compute block
     entirely. The diag-writeback and intv-writeback mvdq inner loops
     must read `s1c[196+pe]` / `s1c[204+pe]` / `s1c[200+pe]` /
     `s1c[208+pe]` directly each iteration via `gr[11]` staging with
     1-NOP s1c gap. The max_d / max_i precomputation continues to run
     as an `s1c`-backed reduction (not as C++ locals) if still needed
     as outer-loop bounds, or is replaced by label + goto break on
     nonzero-count detection. No AC-2 waiver is taken.
   - Convert the seam-write `if (nis == 0) continue` / `if (cum == 0) { ... }`
     pair to label + goto. The first-write-once gate on `s1c[28+pe] == 0`
     MUST be preserved; the goto structure must not change the
     one-sample-before-increment semantics.
   - Convert the diag and intv writeback mvdq inner `if (j >= w) continue`
     to label + goto.
   - Convert the `if (gr[11] > max_d) max_d = gr[11]` to label + branch.
   - Preserve the 4 SPM → gr[11] → s1c chains (first lo, first hi, last lo,
     last hi) exactly; each gets 3-NOP settle and lands cycle N+2.
   - Preserve the `gr[2] += DEDUP_TILE` live-out.
   - Preserve every per-PE cursor monotonic advance post-mvdq
     (`d_curs[pe] += cnt` and `i_curs[pe] += cnt`), per `DEC-M31-AUTOINC`.
   Build, mode 1, reviewer, commit.

9. **Final verification** (`l5`): `gwfa_check_correctness.py 2 -t 56` =
   295/295; close out any deferred items recorded in `l4` (including any
   DEC-3B-* items whose resolution was conditional). Final plan report.

### Relevant References

- `pe_array.cpp` — current HEAD magic bodies (verify line ranges at launch
  HEAD; positions shift as 3a lands):
  - magic 24 at the sort scatter tile-load block (chunk-outer mvdq
    all_full / peeled split)
  - magic 25 at the sort scatter writeback block (per-bin iteration with
    gr[11]-staged SPM / s1c reads and running-offset RMW)
  - magic 28 at the diag merge split + tile-load block (s1c-backed 3-way
    binary search + post-bs a_sp / b_sp compute + 4 mvdq tile loads)
  - magic 29 at the dedup split + tile-load block (pre-computed splits +
    per-PE tile sizing + M29_MVDQ macro expansion 4×)
  - magic 30 at the dedup reload block (pass-1 param gather + M30_MVDQ
    macro 4× + pass-3 meta update)
  - magic 31 at the dedup writeback block (SPM / s1c per-PE cursor
    compute + seam-write gate + 2 mvdq writeback loops + cumulative
    s1c RMW)
- `scripts/gwfa_instruction_generator.py` — sort-driver and merge-driver
  loops (govern the `gr[1..4]`, `gr[6]`, `gr[7]`, `gr[24]`, `gr[28]`
  live-in / live-out contracts across 3b magic boundaries).
- `isaLikeAllGwfaPrompt.md` — governing prompt; the magic-24 / 25 / 28
  / 29 / 30 / 31 specific notes (mvdq round-robin, binary-search wait-
  LSQ cadence, autoincrement intent).
- `isaLikeAllGwfaPlan3a.md` / `isaLikeAllGwfaPlan3aH.md` — sibling plan
  precedent; `l0`, `l1`, `l2*` patterns reused as `l4`, `l4abi`, `l4*`.
  Inherits DEC-SPM-MODEL, DEC-COMMIT, DEC-SEAM-MERGE, DEC-CORRECTNESS-BAR.
- `isaLikeAllGwfaPlan2aH.md` — Plan 2a magic-31 autoincrement decision
  (DEC-M31-AUTOINC) and the current seam-metadata shape at
  `s1c[176..191]`.
- `isaLikeAllGwfaPlan1.md` / `isaLikeAllGwfaPlan1H.md` — `BL-20260413-
  gr-clobber` bitlesson.
- `CLAUDE.md` — canonical SPM latency + VLIW hazard rules + history-
  modification prohibition; `docs.md` — full ISA manual.
- Memory entry `feedback_spm_cycle_accounting.md` — consumer cycle must
  be load-cycle + 2; pair alignment within magic body matters.

## Dependencies and Sequence

### Milestones

1. **Milestone A: Launch gate + ABI reconciliation**
   - Phase A1 (`l4`): Record launch SHA; rerun mode 2 = 295/295 on that
     SHA; enumerate AC-10 edge-arm coverage; absorb / defer open 3a / 2c
     items; resolve `DEC-3B-LAUNCH-GATE` and `DEC-3B-CORRECTNESS-BAR`.
   - Phase A2 (`l4abi`): Phase-scoped liveness appendix + per-magic temp
     sets + `gr[1]` caller-dead confirmation on m29 → m31 entry
     (analyze).

2. **Milestone B: Per-magic ISA lowering** (chained, per-magic commits)
   - Step B1 (`l4a` + `l4av`): Magic 24 lower + verify + commit.
   - Step B2 (`l4b` + `l4bv`): Magic 25 lower + verify + commit.
   - Step B3 (`l4c` + `l4cv`): Magic 28 lower + verify + commit.
   - Step B4 (`l4d` + `l4dv`): Magic 29 lower + verify + commit.
   - Step B5 (`l4e` + `l4ev`): Magic 30 lower + verify + commit.
   - Step B6 (`l4f` + `l4fv`): Magic 31 lower + verify + commit.

3. **Milestone C: Final verification**
   - Step C1 (`l5`): `gwfa_check_correctness.py 2 -t 56` = 295/295; close
     out deferred items.

Dependencies: A1 → A2 → B1 → B2 → B3 → B4 → B5 → B6 → C1. Within B, each
per-magic commit is a linear-chain rollback point. Mode 1 is a full-pipeline
run, so any later magic's commit automatically revalidates earlier magics'
paths on the same mode-1 run; no separate backtrack-revalidation is needed.

## Task Breakdown

Each `coding` row's pre-commit stage (`l4a`, `l4b`, `l4c`, `l4d`, `l4e`,
`l4f`) is edit-only; the matching `l4*v` stage runs build + mode-1 verify
+ reviewer + additive commit. `analyze` tasks commit plan-artifact updates
only (no `pe_array.cpp` change unless the ABI reconciliation itself
requires one, e.g. a typo or drifted constant).

| Task ID | Description                                                                                                                                                                 | Target AC                         | Tag     | Depends On |
|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|---------|------------|
| l4      | Launch gate: record post-3a `git rev-parse HEAD` (per resolved DEC-3B-LAUNCH-GATE); run `gwfa_check_correctness.py 2 -t 56 = 295/295`; confirm Plan 3a closed; enumerate AC-10 edge-arm suite coverage and extend inputs or mandate per-magic trace emits (the m29 / m31 unconditional-trace tier is fixed by resolved DEC-3B-CORRECTNESS-BAR); absorb / defer open 3a / 2c items | AC-1, AC-10, AC-12                | analyze | -          |
| l4abi   | Phase-scoped liveness appendix + per-magic temp sets; extend Cross-Magic Register ABI for magics 24 / 25 / 28 / 29 / 30 / 31; confirm `gr[1]` caller-dead on magic 31 entry by walking the full caller path (sort loop → merge driver → dedup driver → magic 30 → magic 31); verify magic 38's writer-side `s1c[163..168]` layout matches magic 29's reader (replaces the Codex-v1 DEC-M29-SPLIT-CONTRACT); enumerate which 3b magics read which slots in `s1c[144..168]` and confirm none write into that Plan 3a seam band; cross-ref `BL-20260413-gr-clobber` + `BL-20260417-ctrl-sync-gr` | AC-8, AC-9, AC-12                 | analyze | l4         |
| l4a     | ISA-lower magic 24 (edit-only): hoist C++ local arrays + scalars into `s1c[]` or same-ISA-line macro consumption; PRESERVE `all_full` fast path AND peeled path as a label + goto dispatch per `DEC-M24-FAST-PATH` (user-confirmed); convert clamps and mvdq `continue` to label + goto; preserve chunk-outer / PE-inner mvdq in both paths | AC-2, AC-3, AC-4, AC-5, AC-7, AC-8 | coding  | l4abi      |
| l4av    | Build + `gwfa_check_correctness.py 1 -t 56 = 15/15` + `gendp-isa-reviewer` on magic 24 + per-magic additive commit + AC-10 edge-arm coverage statement in commit message    | AC-1, AC-10, AC-11                | coding  | l4a        |
| l4b     | ISA-lower magic 25 (edit-only): hoist `ns/mm_dsts/spm_srcs/max_words` locals; convert clamps and mvdq `continue` to label + goto; verify `SORT_RADIX_BINS` macro unroll; preserve gr[11]-staged RMW | AC-2, AC-3, AC-4, AC-5, AC-7, AC-8 | coding  | l4av       |
| l4bv    | Build + mode 1 + reviewer on magic 25 + per-magic commit + AC-10 coverage statement                                                                                         | AC-1, AC-10, AC-11                | coding  | l4b        |
| l4c     | ISA-lower magic 28 (edit-only): hoist post-bs scalar locals into `s1c[]` or same-ISA-line consumption; convert clamps to label + branch; convert mvdq tile-load `continue` and `mw` max to goto + label; preserve the existing bs goto structure and `s1c[0..23]` aliasing; verify every MM load in bs body has `// waitLSQ` + NOP | AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8 | coding  | l4bv       |
| l4cv    | Build + mode 1 + reviewer on magic 28 + per-magic commit + AC-10 coverage statement (skip-merge arm)                                                                        | AC-1, AC-10, AC-11                | coding  | l4c        |
| l4d     | ISA-lower magic 29 (edit-only): hoist `splits / intv_lo / intv_hi / dd0/1 / d_srcs / ii0/1 / i_srcs` arrays into `s1c[]`; convert clamps (`iv_s > intv_hi`, `iv_e < intv_hi`, `total > max_total`) and M29_MVDQ inner `continue` to label + goto; preserve live-out `gr[4] / gr[6] / gr[7]` and the `intv_n > 0` guard around `s1c[163..168]` reads; rely on `l4abi`'s verification of m38's writer-side layout for the reader contract | AC-2, AC-3, AC-4, AC-5, AC-7, AC-8 | coding  | l4cv       |
| l4dv    | Build + mode 1 + reviewer on magic 29 + per-magic commit + AC-10 coverage statement (zero-intv, clamp arms)                                                                 | AC-1, AC-10, AC-11                | coding  | l4d        |
| l4e     | ISA-lower magic 30 (edit-only): hoist `d_tile / d_src / i_tile / i_src[2][4]` arrays into `s1c[]`; convert refill conditional to label + branch; convert M30_MVDQ inner `continue` to goto + label; preserve pass-3 meta update | AC-2, AC-3, AC-4, AC-5, AC-7, AC-8 | coding  | l4dv       |
| l4ev    | Build + mode 1 + reviewer on magic 30 + per-magic commit + AC-10 coverage statement (no-refill arms)                                                                        | AC-1, AC-10, AC-11                | coding  | l4e        |
| l4f     | ISA-lower magic 31 (edit-only): REMOVE `nds / d_curs / nis / i_curs` C++ local arrays per `DEC-M31-STAGED-ARRAYS`; read `s1c[196..211]` directly in mvdq inner loops via `gr[11]` 1-NOP staging; convert seam-write `continue` and mvdq inner `continue` to label + goto; PRESERVE `s1c[28+pe]`-gated first-write-once seam to `s1c[176..191]`; preserve per-PE monotonic cursor advance (`DEC-M31-AUTOINC`) | AC-2, AC-3, AC-4, AC-5, AC-7, AC-8, AC-9 | coding  | l4ev       |
| l4fv    | Build + mode 1 + reviewer on magic 31 + per-magic commit + AC-10 coverage statement (zero-`nis`, first-nonzero-tile gate, last-nonzero-tile update)                         | AC-1, AC-9, AC-10, AC-11          | coding  | l4f        |
| l5      | Final verification: `gwfa_check_correctness.py 2 -t 56 = 295/295`; close out any 2c / 3a items deferred by `l4`; final plan report                                           | AC-1                              | coding  | l4fv       |

## Claude-Codex Deliberation

### Agreements
- Plan 3a's monolithic "one plan with milestones, per-magic commits,
  edit-only + verify-commit split" shape is the right template for 3b;
  a sibling split (3b-sort vs 3c-dedup) is not materially safer and adds
  planning overhead (Codex `ALTERNATIVE_DIRECTIONS`).
- The draft AC set is too thin. 3b needs the Plan 3a AC depth: dedicated
  ACs for correctness, no-locals, no-runtime-control, VLIW RAW-free,
  SPM / s1c latency, MM waitLSQ, mvdq round-robin, cross-magic ABI,
  producer-side seam contract, edge-path coverage, reviewer cadence, and
  launch-gate reconciliation — hence AC-1 through AC-12.
- Magic 28's binary search is already converted to label + goto with
  `s1c[0..8]` scratch in current HEAD (verified line 3440+ of
  `pe_array.cpp`); 3b's work there is NOT "while → goto", it is the
  remaining scalar-local hoisting, clamp → branch, and mvdq `continue`
  → goto. The draft's task-`l4c` description is stale and must be
  rewritten (Codex `TECHNICAL_GAPS`).
- Magic 28 is the largest in-scope magic by body size (lines 3393..3750);
  magic 31 is second, and magic 29 is third. However, magic 29 carries the
  biggest cross-magic contract risk (produces `gr[4]`, `gr[6]`, `gr[7]`
  live-outs; reads the magic-38-authored `s1c[163..168]` intv-boundary
  layout). Magic 31 carries the biggest seam-contract risk (the
  `s1c[176..191]` first-write-once / last-update-each producer). All three
  still fit their single `l4x + l4xv` pair; the risk is absorbed by
  per-magic reviewer cadence and by the AC-9 / AC-10 enforcement, not by
  per-pass sub-tasking.
- Magic 31 inherits `DEC-M31-AUTOINC` from Plan 2a (C++ per-PE cursor
  form is acceptable). `DEC-M31-STAGED-ARRAYS` was the remaining
  choice-point for magic 31 and has been resolved (HOIST): the
  `nds / d_curs / nis / i_curs` C++ local arrays are removed and the
  mvdq inner loops read `s1c[196..211]` directly via `gr[11]` staging.
- `DEC-SPM-MODEL`, `DEC-COMMIT`, `DEC-SEAM-MERGE`, `DEC-CORRECTNESS-BAR`
  are inherited from Plan 3a without restatement. `DEC-SEAM-MERGE` is
  producer-side in 3b (magic 31 writes the seam that magic 32 consumes)
  and is enforced by AC-9.
- The sort-phase / merge-phase / dedup-phase `s1c[0..79]` aliasing is
  safe by construction (phases are temporally disjoint). 3b must not
  introduce a new cross-phase reuse. AC-8 negative tests enforce this.
- Magic 24's `all_full` fast path is a measured optimization.
  `DEC-M24-FAST-PATH` (user-confirmed: PRESERVE) fixes the shape:
  both paths are retained and the selector is an architectural label +
  goto branch (no C++ `bool`), so both paths are rule-compliant.
- `gr[11]` is the CLAUDE-safe controller scratch per
  `BL-20260417-ctrl-sync-gr`; `gr[12]` / `gr[13]` / `gr[7..10]`
  (magic 31's protected band) are off-limits for 3b temps.

### Resolved Disagreements (Claude ↔ Codex, pre-user)

These are items where Claude and Codex converged during Phase 3–5 without
requiring user input. Items that are genuinely user decisions
(DEC-3B-LAUNCH-GATE, DEC-M24-FAST-PATH, DEC-M31-STAGED-ARRAYS,
DEC-M29-SPLIT-CONTRACT, DEC-3B-SCOPE-SHAPE, DEC-3B-CORRECTNESS-BAR)
appear instead under `## Pending User Decisions` below and are NOT listed
here.

- **Magic 28 task-scope correction**: Codex flagged the draft's "binary
  search arrays → s1c or unrolled gr, while → goto" description as
  stale. Resolution: rewrote `l4c` as "hoist post-bs scalar locals;
  convert clamps to label + branch; convert mvdq `continue` and `mw`
  max to goto + label; preserve the existing bs goto structure and
  `s1c[0..23]` aliasing; verify every MM load in bs body has
  `// waitLSQ`".
- **AC decomposition**: Codex pushed to split the draft's 5 ACs into 12
  ACs matching Plan 3a's granularity. Resolution: adopted the 12-AC
  split with Plan-3a-style TDD positive/negative tests.
- **Edge-path coverage AC**: Codex flagged that mode-1 + mode-2 alone
  does not cover risky data-dependent arms (m24 all_full vs peeled,
  m28 skip-merge, m29 zero-intv, m30 no-refill, m31 zero-nis +
  first-write). Resolution: added AC-10 with explicit arm enumeration
  and `l4` / `l4*v` ownership split.
- **Seam contract AC**: Codex flagged the 31 → 32 seam contract needs
  a dedicated AC (AC-9). Resolution: added AC-9 with first-write-once,
  last-update-each, sampled-before-increment positive / negative tests.
- **Sibling-plan split rejection**: Codex considered but rejected
  splitting into 3b-sort (24 / 25 / 28) vs 3c-dedup (29 / 30 / 31);
  3b stays monolithic. Resolution: path boundaries and task table
  reflect one plan, six magics.
- **Per-magic split (`l4x` + `l4xv`)**: the draft already proposes
  this pattern; Codex agreed. Resolution: pattern adopted verbatim from
  Plan 3a.
- **`l4` + `l4abi` split**: Codex suggested separating launch-gate
  from ABI reconciliation, mirroring Plan 3a's `l0` + `l1`.
  Resolution: adopted as two analyze tasks.
- **Magic 31 `nds / d_curs / nis / i_curs` treatment**: Codex called
  this a real unresolved issue distinct from `DEC-M31-AUTOINC`.
  Resolution: opened as `DEC-M31-STAGED-ARRAYS` in Pending User
  Decisions; candidate v1 does not pre-resolve.
- **AC-1 coverage confirmation at `l4`**: Codex pushed for `l4` to own
  the edge-arm test-input confirmation / extension (mirror Plan 3a's
  `l0`). Resolution: AC-1 positive test now requires `l4` to enumerate
  coverage and either extend the suite or mandate debug-trace
  assertions per `l4*v`.
- **Magic 29 split-contract verification**: Codex round-2 flagged
  `DEC-M29-SPLIT-CONTRACT` as not a user decision but an `l4abi`
  verification item. The writer-side semantics are already defined
  in magic 38 (`s1c[163+b] = intv_lo[pe+1]`, `s1c[166+b] = intv_hi[pe]`
  at pe_array.cpp:3143). Resolution: removed from Pending User
  Decisions; added to `l4abi`'s scope as an explicit verify step that
  confirms magic 29's reader shape matches magic 38's writer shape on
  launch HEAD. AC-8 / AC-10 already carry the enforcement.
- **`l2dv`-style grouped commit**: Plan 3a used a grouped commit for
  `l2d1 + l2dv` because the helper body and magic 20 wrapper were
  symbiotic. Codex agreed 3b has no such symbiosis (each magic is
  independent). Resolution: all six 3b magics use single per-magic
  commits.

### Convergence Status
- Final Status (post round-2): `converged` on structural plan shape,
  AC set (AC-1..AC-12), task breakdown (`l4` / `l4abi` / six
  `l4x + l4xv` pairs / `l5`), path boundaries, and Cross-Magic
  Register ABI extension. Round 1 produced candidate v1 (12 ACs,
  Plan-3a-style structure, 6 DEC-3B-* pending). Round 2 returned
  9 required changes; all were applied in round-2 revision
  (merge-phase `s1c[]` map precision, `gr[]` semantics with
  READ/WRITE/THROUGH vocabulary, `gr[1]` deadness walked over full
  caller path, AC-10 m29 arm list corrected, DEC-M29-SPLIT-CONTRACT
  resolved to `l4abi` verification, DEC-3B-CORRECTNESS-BAR made
  concrete as tier-split in AC-10, magic-29-largest claim
  corrected, deterministic-design note re-axed, l4abi scope
  extended). Round 2 returned `UNRESOLVED: none new`. All five
  `DEC-3B-*` items surfaced for user decision were resolved in
  Phase 6 in favor of Claude's recommended positions (recorded
  post-3a SHA, m24 fast-path preserved as label/goto, m31 arrays
  hoisted to s1c[196..211], monolithic one-plan shape, hybrid
  tier-concrete correctness bar). DEC-M29-SPLIT-CONTRACT was
  reclassified to an `l4abi` verification item (see Resolved
  Disagreements). No decisions remain pending.

## Pending User Decisions

All five plan-3b-local planning-level decisions (DEC-3B-LAUNCH-GATE,
DEC-M24-FAST-PATH, DEC-M31-STAGED-ARRAYS, DEC-3B-SCOPE-SHAPE,
DEC-3B-CORRECTNESS-BAR) were resolved during Phase 6 and moved into the
Decision Log at the top of this file. DEC-M29-SPLIT-CONTRACT was
reclassified during round 2 as an `l4abi` analyze verification item
(not a user decision) because magic 38's writer-side semantics at
`s1c[163..168]` are already defined in pe_array.cpp:3143 — the task
is to verify the reader in magic 29 matches the writer on launch HEAD.

No user decisions remain pending. DEC-HASH-PATH (Plan 3a-local) is out
of 3b scope.

## Implementation Notes

### Code Style Requirements
- Implementation code and comments must NOT contain plan-specific
  terminology such as "AC-", "Milestone", "Step", "Phase", or similar
  workflow markers.
- These terms are for this plan document only, not for the resulting
  codebase.
- Use descriptive, domain-appropriate naming. Preserve the `// waitLSQ`
  and SPM-NOP / s1c-NOP annotation conventions already established in
  Plans 1, 2a, 2b, 2c, 3a.
- When hoisting a C++ local into `s1c[]`, add a short inline comment
  naming the ABI slot (e.g. `// nds → s1c[196+pe]`) the first time the
  slot is used inside the magic body.

--- Original Design Draft Start ---

NOTE! when generating the plan, keep in mind that 3a has not finished yet. We are generating this
plan ahead of time so we are prepared to launch as soon as it does finish, but that means the
codebase might change a bit in between
# GWFA ISA-Like Rewrite Plan 3b: ISA Lower Controller 24-31

## Shared Preamble (duplicated across all active plans)

### Scope
- **Delete**: Controller magics 2, 10, 26 (deprecated) — DONE in Plan 1
- **Exempt (do not touch)**: Controller 1, 3, 4, 5, 6, 17
- **Reference examples (frozen)**: Controller 7, 8, 9, 12, 14, 15; PE 8, 11, 13
- **Rewrite (controller)**: 16, 18, 19, 20, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39
- **Rewrite (PE)**: 19, 20, 21, 22, 23

### ISA-like rules (all 12)
1. Each line = one GenDP ISA operation
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired instructions
3. Registers only: gr[], reg[], s1c[], spm[], mm[]; no C++ runtime variables
4. Gotos with labels instead of if/else/for/while; macro loops (e.g., `for pe in range(4)`) allowed
5. Compile-time constants (`constexpr`) allowed
6. SPM: 2-cycle latency (pipelined OK, but cannot use loaded value for 2 cycles)
7. MM/S2: waitLSQ comment required between load and use
8. S1c: 1-cycle latency
9. mvdq round-robin PE streaming for bulk data transfers; scalar mv only for non-contiguous data
10. No `std::min`/`std::max` on controller; use branch conditions. min/max fine on PE
11. Helper macros acceptable if all live state is in registers/memory
12. PE compute instructions deferred to a future pass

### Validation rules
- After EACH magic: `make -j ADDRESS_SANITIZER=0`, `gwfa_check_correctness.py 1 -t 56`, commit
- After each commit: run `gendp-isa-reviewer` on the changed magic
- Fix hazards before next magic
- At end of plan: `gwfa_check_correctness.py 2 -t 56` (295/295 required)

### Cross-Magic Register ABI (shared across Plans 3a-3d)

See Plan 3a for the initial register ABI table. This plan extends it for the sort/merge pipeline (magics 24-31). Task l4 must verify and extend the ABI before lowering begins.

---

## Goal Description

ISA-lower controller magics 24, 25, 28, 29, 30, 31. Each lowered, verified, and ISA-reviewed individually.

## Prerequisites

Plans 1+2a+2b+2c+3a complete. Controller 16-20 ISA-lowered. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after EACH magic, mode 2 at end)
- AC-2: No C++ runtime variables
- AC-3: No runtime if/else/for/while
- AC-4: VLIW pairing, no RAW hazards (ISA reviewer per magic)
- AC-5: Latency gaps and waitLSQ comments

## Task Breakdown

| Task ID | Description | Tag |
|---------|-------------|-----|
| l4 | Plan register allocation for magics 24-31. Extend Cross-Magic Register ABI from Plan 3a. Document live gr[] across sort/merge boundaries. | analyze |
| l4a | ISA-lower controller 24: locals→gr, tile size→register ops, mvdq fast path preserved | coding |
| l4av | Verify + ISA review controller 24 | coding |
| l4b | ISA-lower controller 25: locals→gr, bin iteration as macro loop, scatter offset→register ops | coding |
| l4bv | Verify + ISA review controller 25 | coding |
| l4c | ISA-lower controller 28: binary search arrays→s1c or unrolled gr, while→goto | coding |
| l4cv | Verify + ISA review controller 28 | coding |
| l4d | ISA-lower controller 29: locals→gr, tile clamping→branches, intv boundary→gr | coding |
| l4dv | Verify + ISA review controller 29 | coding |
| l4e | ISA-lower controller 30: locals→gr, reload conditionals→goto labels | coding |
| l4ev | Verify + ISA review controller 30 | coding |
| l4f | ISA-lower controller 31: locals→gr, autoincrement cursors from Plan 2a, output loops→goto | coding |
| l4fv | Verify + ISA review controller 31 | coding |
| l5 | Full verification: mode 2 -t 56 | coding |

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---

--- Original Design Draft End ---
