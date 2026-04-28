# GWFA ISA-Like Rewrite Plan 3c: ISA Lower Controller 32-39

## Goal Description

ISA-lower the eight GWFA-kernel controller "magic" functions numbered 32, 33, 34, 35, 36, 37,
38, 39 in `pe_array.cpp` so each conforms to the 12 ISA-like rules already in force for
Plans 3a/3b. Each magic is lowered, mode-1-verified, and ISA-reviewed individually. Before
any lowering begins, task `l6` commits an ABI-extension artifact that freezes cross-magic
`gr[]` and `s1c[]` slots used by magics 32..39; subsequent shared-slot changes are allowed
only through an explicit amendment commit with rerun of affected prior magics. Cluster
integration gates (`scripts/gwfa_check_correctness.py 2 -t 56`) run after magic 32, after
magic 35, and after magic 39. Final exit gate is `gwfa_check_correctness.py 2 -t 56 =
295/295`.

## Prerequisites

Plans 1 + 2a + 2b + 2c + 3a + 3b complete. Controller magics 16-31 already ISA-lowered and
passing mode 2 -t 56 = 295/295.

## Acceptance Criteria

Each AC is labeled `[Product]` (end-state property of the code), `[Process]` (workflow
control), or `[Product+Process]` (both). Following TDD philosophy, every AC carries
positive tests (expected to PASS) and negative tests (expected to FAIL / be rejected).

- AC-1 `[Process]` Correctness cadence
  - Positive Tests:
    - `gwfa_check_correctness.py 1 -t 56` passes after every edited magic, including
      magics 34, 36, 39 even when the edit is judged trivial.
    - Cluster integration gates pass: `gwfa_check_correctness.py 2 -t 56` after magic 32
      (cluster A), after magic 35 (cluster B), after magic 39 (cluster C).
    - Final gate: `gwfa_check_correctness.py 2 -t 56 = 295/295`.
  - Negative Tests:
    - A magic landing without its mode-1 rerun is rejected.
    - A cluster gate skipped on the grounds that "changes are trivial" is rejected.
    - Any regression below 295/295 on final mode-2 is rejected.

- AC-2 `[Product]` Register-only state across ISA lines
  - Positive Tests:
    - Grep / reviewer inspection of each edited magic (32..39) confirms no C++ local
      variable carries state across ISA lines; all live state is in
      `gr[] / reg[] / s1c[] / spm[] / mm[]`.
    - Helper macros are accepted only if all their state lives in register/memory.
  - Negative Tests:
    - Any sequence such as `int x = ...; <ISA line>; use(x);` carrying `x` across ISA
      lines in the lowered magic fails review.

- AC-3 `[Product]` Structured control flow via gotos
  - Positive Tests:
    - Edited magics contain only labeled goto branches and constexpr macro PE unrolls
      (`for (int pe = 0; pe < 4; ++pe)` style over compile-time PE count).
  - Negative Tests:
    - Any runtime `if / else / for / while` remaining in an edited magic fails review.

- AC-4 `[Product+Process]` No RAW hazards in VLIW pairing
  - Positive Tests:
    - `gendp-isa-reviewer` agent passes on each lowered magic before the next begins.
    - A mechanical pre-check (e.g. grep for paired-slot lines where `slot1_src ==
      slot0_dst` and grep for `// waitLSQ` presence between MM load and first consumer)
      reports no violations. Exact pattern list committed alongside the l6 ABI artifact.
  - Negative Tests:
    - Any reviewer-flagged RAW hazard or SPM/s1c/MM latency violation blocks progression
      to the next magic.

- AC-5 `[Product]` Latency annotations and gaps
  - Positive Tests:
    - Every SPM load is followed by at least 3 non-dependent ISA lines (2-cycle = 4
      ISA lines with pair-alignment accounted) before its first consumer; every
      `s1c[]` load by at least 1; every MM load carries a `// waitLSQ` comment between
      the load and its first consumer.
    - Consistent grep-able comment patterns: `// waitLSQ`, `// SPM settle`,
      `// s1c gap`.
  - Negative Tests:
    - Any SPM/s1c/MM read whose consumer violates the latency rule or omits the
      required comment fails review.

- AC-6 `[Product]` Magic 31 → 32 seam contract preserved exactly
  - Positive Tests:
    - Magic 32 reads `s1c[176+pe] / s1c[180+pe]` only under the `intv_n > 0` guard and
      reads `s1c[184+pe] / s1c[188+pe]` only under the `cnt > skip` guard (matching
      `pe_array.cpp:6447` and `pe_array.cpp:6478` pre-lowering semantics).
    - Magic 32 epilogue preserves: clear `s1c[0..143]`, clear seam band `s1c[176..191]`,
      assign `s1c[152] = MM_INTV2`, assign `s1c[153] = diag_base`, publish
      `gr[15] = n_a_final`, publish `gr[28] = intv_n`.
    - Magic 31 producer semantics remain untouched: first-intv `{lo,hi}` at
      `s1c[176+pe] / s1c[180+pe]` written only on the pre-advance `s1c[28+pe] == 0`
      arm; last-intv `{lo,hi}` at `s1c[184+pe] / s1c[188+pe]` written on every
      nonzero-`nis` tile.
  - Negative Tests:
    - Any change to magic 31 producer semantics fails review.
    - Any magic 32 seam read under the wrong guard fails review.
    - Any missing epilogue clear, assignment, or publish fails review.
    - Any new cross-magic dependence on `s1c[176..191]` outside magic 32 fails review.

- AC-7 `[Process+Product]` Cross-magic ABI artifact with controlled-change rule
  - Positive Tests:
    - Task `l6` produces a committed ABI artifact (an extension of the Plan 3a/3b ABI
      table covering all shared `gr[]` and `s1c[]` slots that magics 32..39 read or
      write) BEFORE task `l6a` begins.
    - Any later amendment to a shared slot is made in a dedicated amendment commit that
      precedes the next magic commit; every already-lowered magic whose contract is
      affected by the amendment is re-run through its mode-1 gate.
  - Negative Tests:
    - Starting any `l6a..l6h` task without the ABI artifact fails AC-7.
    - Silently changing a shared slot inside a magic commit (without a preceding
      amendment commit) fails AC-7.
    - Skipping mode-1 rerun of an affected prior magic after an ABI amendment fails AC-7.

- AC-8 `[Product]` Magic 32 PE-serial structure preserved
  - Positive Tests:
    - Magic 32 retains PE-outer / chunk-inner loop shape
      (`for (int pe = 0; pe < 4; ++pe) { per-PE gather + mvdq }`) across both the diag
      gather loop (`pe_array.cpp:6346`) and the intv gather loop
      (`pe_array.cpp:6401`).
    - Cross-PE order-sensitive state — `n_a_final`, `intv_n`, `last_vd`, `last_intv_hi`,
      `skip` — remains updated strictly in PE order 0 → 1 → 2 → 3.
  - Negative Tests:
    - Any reordering that interleaves PE work across chunks within magic 32 fails AC-8
      even if mode-1 still happens to pass.

- AC-9 `[Product]` PE-visible controller-side observables preserved (no PE lowering)
  - Positive Tests:
    - For magics 33, 35, 37: SPM metadata slots consumed by PE compute (`MERGE_META`,
      `TILE_BUF`, drain counters, PE output base/cursor pairs) stay at identical
      addresses/offsets with identical cumulative semantics.
    - MM destination addresses and byte layouts match pre-lowering output byte-for-byte
      on the reference trace defined below.
    - Controller-produced PE input frames are diff-equivalent against the reference
      trace.
  - Reference trace (frozen oracle for this AC): the wavefront and output snapshot
    produced by running `scripts/gwfa_run_validation.sh` on HEAD immediately before
    `l6a` lands. Capture and commit that snapshot (e.g. under
    `tests/frozen/plan3c_pre_l6a/`) as part of `l6`.
  - Negative Tests:
    - Any renumbered SPM metadata slot, reordered drain-counter update, or MM-destination
      diff against the frozen snapshot on the reference trace fails AC-9.

- AC-10 `[Product]` Magic 37 search invariants preserved
  - Positive Tests:
    - Lowered m37 preserves the 3-partition binary-search shape with split arrays
      `a_sp[] = s1c[40..44]` and `b_sp[] = s1c[45..49]`.
    - Comparator polarity is copied verbatim from pre-lowering: strict `<` for inner
      partition bounds (`pe_array.cpp:3143, 3146, 3149, 3155, 3179, 3203`) and `<=` for
      the a/b merge-split boundary (`pe_array.cpp:3169, 3193, 3217`).
    - Chunk-outer / PE-inner `mvdq_copy` tile-load discipline is preserved.
    - Split arrays computed by the lowered m37 are byte-equal to pre-lowering values on
      the frozen reference trace (same snapshot as AC-9).
  - Negative Tests:
    - Any comparator polarity flip (`<` ↔ `<=`) fails AC-10.
    - Any loss of split-array monotonicity (`a_sp[i] > a_sp[i+1]` or equivalent) fails
      AC-10.
    - Any reorder of the tile-load chunk/PE nesting fails AC-10.

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)

All eight magics (32..39) ISA-lowered. Task `l6` commits an ABI-extension artifact before
`l6a`; cluster mode-2 gates run after magic 32 (cluster A), after magic 35 (cluster B), and
after magic 39 (cluster C). Seam contract (AC-6), PE-serial preservation (AC-8), PE-visible
observables (AC-9), and magic 37 invariants (AC-10) are documented in per-magic commit
messages. A one-page verification matrix (reproduced in Implementation Notes below) maps
each magic to its required checks. The frozen reference trace used as the AC-9 / AC-10
oracle is captured and committed under `l6`. Reviewer approval (`gendp-isa-reviewer`) and
mechanical pre-check pass on every magic.

### Lower Bound (Minimum Acceptable Scope)

All eight magics ISA-lowered. Task `l6` commits an ABI artifact (possibly minimal, possibly
amended once later) before `l6a`. Each magic passes `gwfa_check_correctness.py 1 -t 56` and
`gendp-isa-reviewer`. Final `gwfa_check_correctness.py 2 -t 56 = 295/295`. The 31↔32 seam
(AC-6), magic 32 PE-serial shape (AC-8), and magic 37 search invariants (AC-10) are
preserved.

### Allowed Choices

- Can use: gotos + labels; `constexpr`; macro PE loops
  (`for (int pe = 0; pe < 4; ++pe)`); `mvdq` round-robin bulk transfers; scalar `mv`;
  branch conditions; `// waitLSQ`, `// SPM settle`, `// s1c gap` annotations; scratch via
  `gr[] / reg[] / s1c[] / spm[] / mm[]`; helper macros whose state lives in
  registers/memory.
- Cannot use: C++ locals as inter-ISA-line state; `std::min / std::max` on the controller;
  runtime `if / else / for / while` in edited magics; chunk-outer reorder of the magic 32
  PE-serial path; re-derived split-search scheme in magic 37 (the current 3-partition
  structure must be preserved); silent changes to shared ABI slots without an amendment
  commit.

> **Deterministic Design Note**: The 12 ISA-like rules, the register ABI inherited from
> Plans 3a/3b, the seam contract at `s1c[176..191]`, and the frozen reference examples
> (Controller 7/8/9/12/14/15; PE 8/11/13) together narrow the design space substantially.
> The upper and lower bounds differ mainly in documentation rigor and cluster-gate
> placement, not in implementation freedom.

## Feasibility Hints and Suggestions

> **Note**: This section is for reference and understanding only. These are conceptual
> suggestions, not prescriptive requirements.

### Conceptual Approach — per magic

- **m32** (`pe_array.cpp:6315`, dedup finalize, PE-serial seam consumer): macro-unroll
  per-PE gather (`for constexpr pe in 0..3`); route s1c seam reads through `gr[11]` with
  1-NOP gap; keep PE-outer chunk-inner `mvdq`. Epilogue becomes explicit scalar ISA stores
  (`s1c[152] = MM_INTV2`, `s1c[153] = diag_base`, `gr[15] = n_a_final`,
  `gr[28] = intv_n`) plus two macro-unrolled clears of `s1c[0..143]` and `s1c[176..191]`.
- **m33** (`pe_array.cpp:4616`, merge tile reload): 3-pass s1c metadata gather with 1-NOP
  gaps unrolled per PE; 4 chunk-outer mvdq passes A0 / A1 / B0 / B1 remain PE round-robin;
  reload conditionals → labeled branches.
- **m34** (`pe_array.cpp:2628`, sort bin-count tile load): interleaved mvdq across PEs at
  4-diag (8-word) granularity; `cursor == 0` bin_counts zeroing → labeled branch over a
  macro-unrolled mvdq.
- **m35** (`pe_array.cpp:4718`, merge writeback): SPM load (3-NOP settle) for per-PE
  `out_ns`; s1c load (1-NOP gap) for per-PE `mm_dsts`; chunk-outer PE-inner mvdq SPM→MM
  with cumulative offset in `gr`.
- **m36** (`pe_array.cpp:4764`, diag merge finalize): pointer-swap becomes labeled two-arm
  (`gr[6] != 0` → `s1c[153] = gr[4]`; else → `s1c[153] = gr[3]`); 5 split indices written
  as scalar `s1c[154+k] = ...` lines.
- **m37** (`pe_array.cpp:3082`, intv merge split + load): preserve the 3-partition search;
  keep `a_sp[] / b_sp[]` in `s1c[40..49]`; copy comparator polarity verbatim into labeled
  branch pairs; chunk-outer PE-inner `mvdq_copy` tile-load preserved.
- **m38** (`pe_array.cpp:3441`, intv merge finalize): stage `s1c[149]` through `gr[11]`
  with 1-NOP gap; two-arm labeled branch; restore `gr[24] = s1c[145]`; write intv
  boundary positions as scalar s1c stores.
- **m39** (`pe_array.cpp:3736`, intv sort setup): scalar register sequence (~8 lines):
  `mv s1c[155] → gr[24]`; two constexpr assigns for `gr[3]`, `gr[4]`; `addi` + `shifti_r`
  for `gr[6] = (gr[24] + 3) >> 2`.

### Relevant References

- `pe_array.cpp:6315` — magic 32 current implementation
- `pe_array.cpp:6147, 6166, 6173, 6182, 6188` — magic 31 seam producer conditions
- `pe_array.cpp:6408, 6447, 6478, 6492-6500` — magic 32 consumer guards + epilogue
- `pe_array.cpp:4616, 2628, 4718, 4764, 3082, 3441, 3736` — magics 33..39 entry points
- `pe_array.cpp:3126-3224, 3230-3265` — magic 37 binary search + a_sp/b_sp
- `isaLikeAllGwfaPlan3aH.md` — authoritative Cross-Magic Register ABI (to extend)
- `isaLikeAllGwfaPlan3bH.md` — extended ABI + ISA-lowering style reference
- `scripts/gwfa_check_correctness.py` — mode-1 / mode-2 validator
- `scripts/gwfa_run_validation.sh` — validation wrapper; source of AC-9 frozen snapshot
- `gendp-isa-reviewer` agent — per-magic ISA compliance review

## Dependencies and Sequence

### Milestones

1. **Milestone ABI Freeze**: `l6` commits the ABI-extension artifact for magics 32..39
   and captures the frozen reference trace used by AC-9 / AC-10.
2. **Milestone Cluster A (seam-focused)**: magic 32 alone.
   - Step 1: `l6a` (lower 32)
   - Step 2: `l6av` (mode-1 + ISA review; cluster-A mode-2 gate)
3. **Milestone Cluster B (brackets PE merge compute)**: magics 33, 34, 35.
   - Step 1: `l6b` → `l6bv` (magic 33)
   - Step 2: `l6c` → `l6cv` (magic 34)
   - Step 3: `l6d` → `l6dv` (magic 35; cluster-B mode-2 gate)
4. **Milestone Cluster C (intv / diag handoff pipeline)**: magics 36, 37, 38, 39.
   - Step 1: `l6e` → `l6ev` (magic 36)
   - Step 2: `l6f` → `l6fv` (magic 37)
   - Step 3: `l6g` → `l6gv` (magic 38)
   - Step 4: `l6h` → `l6hv` (magic 39; cluster-C mode-2 gate)
5. **Milestone Final**: `l7` runs `scripts/gwfa_check_correctness.py 2 -t 56` and confirms
   295/295.

Dependencies (relative): `l6` blocks all `l6a..l6h`; each lowering task blocks the matching
verification task; each verification task blocks the next lowering task in its cluster.
Cluster boundaries are enforced by the cluster mode-2 gates at `l6av`, `l6dv`, `l6hv`.

## Task Breakdown

Each task carries exactly one routing tag: `coding` (implemented by Claude) or `analyze`
(executed via Codex / `/humanize:ask-codex`).

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| l6 | Commit cross-magic ABI artifact extending Plans 3a/3b for magics 32..39; capture AC-9/AC-10 frozen reference trace snapshot; commit mechanical pre-check pattern list. | AC-7 | analyze | - |
| l6a | ISA-lower magic 32 (PE-serial shape preserved; 31↔32 seam honored; explicit epilogue). | AC-2, AC-3, AC-5, AC-6, AC-8 | coding | l6 |
| l6av | Mode-1 -t 56 + gendp-isa-reviewer on magic 32; run cluster-A mode-2 -t 56 gate. | AC-1, AC-4 | coding | l6a |
| l6b | ISA-lower magic 33 (reload gather + 4 chunk passes; PE observables preserved). | AC-2, AC-3, AC-5, AC-9 | coding | l6av |
| l6bv | Mode-1 -t 56 + gendp-isa-reviewer on magic 33. | AC-1, AC-4 | coding | l6b |
| l6c | ISA-lower magic 34 (interleaved mvdq + cursor==0 zeroing). | AC-2, AC-3, AC-5 | coding | l6bv |
| l6cv | Mode-1 -t 56 + gendp-isa-reviewer on magic 34. | AC-1, AC-4 | coding | l6c |
| l6d | ISA-lower magic 35 (per-PE SPM out_ns + s1c mm_dsts pre-compute; chunk-outer mvdq). | AC-2, AC-3, AC-5, AC-9 | coding | l6cv |
| l6dv | Mode-1 -t 56 + gendp-isa-reviewer on magic 35; run cluster-B mode-2 -t 56 gate. | AC-1, AC-4 | coding | l6d |
| l6e | ISA-lower magic 36 (pointer-swap two-arm + split indices). | AC-2, AC-3 | coding | l6dv |
| l6ev | Mode-1 -t 56 + gendp-isa-reviewer on magic 36. | AC-1, AC-4 | coding | l6e |
| l6f | ISA-lower magic 37 (preserve 3-partition search, a_sp/b_sp layout, comparator polarity; chunk-outer mvdq_copy). | AC-2, AC-3, AC-5, AC-9, AC-10 | coding | l6ev |
| l6fv | Mode-1 -t 56 + gendp-isa-reviewer on magic 37; confirm AC-10 split-array byte equality against frozen trace. | AC-1, AC-4, AC-10 | coding | l6f |
| l6g | ISA-lower magic 38 (two-arm decision via label; restore `gr[24] = s1c[145]`). | AC-2, AC-3, AC-5 | coding | l6fv |
| l6gv | Mode-1 -t 56 + gendp-isa-reviewer on magic 38. | AC-1, AC-4 | coding | l6g |
| l6h | ISA-lower magic 39 (scalar register sequence). | AC-2, AC-3 | coding | l6gv |
| l6hv | Mode-1 -t 56 + gendp-isa-reviewer on magic 39; run cluster-C mode-2 -t 56 gate. | AC-1, AC-4 | coding | l6h |
| l7 | Final `gwfa_check_correctness.py 2 -t 56` full run; confirm 295/295. | AC-1 | coding | l6hv |

## Claude-Codex Deliberation

### Agreements

- Correctness rests on per-magic mode-1 after each edit and cluster mode-2 gates at
  integration points (m32, m35, m39) with a final mode-2 295/295 exit gate.
- The 31↔32 seam at `s1c[176..191]` must be treated as a first-class product-level
  contract (AC-6), not left implicit.
- Magic 32 bulk gather/emit must remain PE-outer / chunk-inner (AC-8); reordering would
  break cross-PE state accumulation even if mode-1 happens to pass.
- Magic 37 binary search is a correctness hot-spot: split-array layout, comparator
  polarity, and `mvdq_copy` nesting are frozen (AC-10).
- `l6` must produce a committed ABI artifact before any lowering begins (AC-7), but with
  a controlled-change escape valve rather than an absolute freeze.
- ACs should be labeled `[Product]` vs `[Process]` for traceability.
- Positive and negative test phrasing (TDD) is required on every AC.

### Resolved Disagreements

- **ABI freeze absoluteness**: Codex v1 called for an absolute ABI freeze before any
  lowering; Claude proposed iterative extension. **Resolved** in v2 as a controlled-change
  rule (AC-7): artifact committed before `l6a`; shared-slot changes allowed only through
  explicit amendment commits with rerun of affected prior magics.
- **AC-9 verifiability**: Codex round-2 flagged "PE-visible protocol preserved" as
  review-language rather than an acceptance criterion. **Resolved** by specifying concrete
  controller-side observables (identical SPM metadata slots, identical drain-counter
  semantics, byte-for-byte MM destination matching) and anchoring them to a committed
  frozen-reference-trace oracle captured under `l6`.
- **AC-4 reviewer-only vs mechanical**: Codex round-2 UNRESOLVED asked whether AC-4 should
  depend on reviewer judgment alone. **Resolved** by adding a mechanical pre-check (grep
  patterns committed with the ABI artifact) alongside `gendp-isa-reviewer` approval.
- **Cluster-A mode-2 gate after m32**: Codex agreed that m32 is a cross-magic state
  republisher (`gr[15], gr[28], s1c[152..153]`, seam band clear) and warrants its own
  mode-2 gate, not just mode-1.
- **`cnt == 1 && skip == 1` branch wording**: Codex v1 assumed an explicit special branch;
  code verification showed the pre-lowering code folds this into the unified `cnt > skip`
  check. AC-6 wording uses `cnt > skip`, matching pre-lowering.
- **34/36/39 rerun requirement**: folded into AC-1 cadence ("including magics 34, 36, 39
  even when the edit is judged trivial") instead of a separate AC.
- **Commit-message documentation**: kept in the Upper Bound as project hygiene, explicitly
  not an AC.

### Convergence Status

- Final Status: `converged`.
- Rounds: 1 Codex first-pass analysis, 1 Claude candidate, 2 Codex convergence reviews.
  Round 3 (convergence review of v2) returned no REQUIRED_CHANGES, no DISAGREE, no
  UNRESOLVED; only optional-polish suggestions remained and were applied.

## Pending User Decisions

None. All items raised during Codex first-pass and convergence rounds were resolved
during iteration. `l6`-time ABI artifact review will take place as part of task `l6` per
AC-7.

## Implementation Notes

### Code Style Requirements

- Implementation code and comments must NOT contain plan-specific terminology such as
  "AC-", "Milestone", "Step", "Phase", or similar workflow markers. These terms are for
  plan documentation only, not for the resulting codebase.
- Use descriptive, domain-appropriate naming in code instead (e.g. `m32_seam_consume`,
  `m37_bs_p0_hi`, `last_intv_hi`).
- Commit-message documentation of AC-6, AC-8, AC-9, AC-10 rationale (Upper Bound item) is
  a hygiene practice; commit messages may reference AC identifiers, but committed source
  files may not.

### Verification Matrix

| Magic | Lowering task | Product checks | Required runs |
|-------|---------------|----------------|---------------|
| 32 | l6a | AC-6, AC-8, AC-2, AC-3, AC-5 | mode-1; cluster-A mode-2 |
| 33 | l6b | AC-9, AC-2, AC-3, AC-5 | mode-1 |
| 34 | l6c | AC-2, AC-3, AC-5 | mode-1 |
| 35 | l6d | AC-9, AC-2, AC-3, AC-5 | mode-1; cluster-B mode-2 |
| 36 | l6e | AC-2, AC-3 | mode-1 |
| 37 | l6f | AC-10, AC-9, AC-2, AC-3, AC-5 | mode-1 |
| 38 | l6g | AC-2, AC-3, AC-5 | mode-1 |
| 39 | l6h | AC-2, AC-3 | mode-1; cluster-C mode-2 |

### Reference examples (frozen — do NOT modify)

- Controller 7 (`pe_array.cpp:1116`), 8 (`:1234`), 9 (`:1305`), 12 (`:1606`),
  14 (`:1616`), 15 (`:1816`).
- PE 8 (`pe.cpp:708`), 11 (`:1087`), 13 (`:1151`).

### Exempt (do NOT touch)

- Controller 1, 3, 4, 5, 6, 17.

### Deleted / deprecated

- Controller 2, 10, 26 (removed in Plan 1).

### 12 ISA-like rules in force (authoritative wording from draft)

1. Each line = one GenDP ISA operation.
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired instructions.
3. Registers only: `gr[] / reg[] / s1c[] / spm[] / mm[]`; no C++ runtime variables.
4. Gotos with labels instead of if/else/for/while; macro loops
   (e.g. `for pe in range(4)`) allowed.
5. Compile-time constants (`constexpr`) allowed.
6. SPM: 2-cycle latency (pipelined OK, but cannot use loaded value for 2 cycles).
7. MM/S2: `// waitLSQ` comment required between load and use.
8. S1c: 1-cycle latency.
9. `mvdq` round-robin PE streaming for bulk data transfers; scalar `mv` only for
   non-contiguous data.
10. No `std::min` / `std::max` on controller; use branch conditions. `min/max` fine on PE.
11. Helper macros acceptable if all live state is in registers/memory.
12. PE compute instructions deferred to a future pass.

### Per-magic validation rules (authoritative wording from draft)

- After EACH magic: `make -j ADDRESS_SANITIZER=0`,
  `scripts/gwfa_check_correctness.py 1 -t 56`, commit.
- After each commit: run `gendp-isa-reviewer` on the changed magic.
- Fix hazards before next magic.
- At end of plan: `scripts/gwfa_check_correctness.py 2 -t 56` (295/295 required).

## Output File Convention

This plan file is the main output (`isaLikeAllGwfaPlan3cH.md`).

### Translated Language Variant

`alternative_plan_language` resolves to empty in the current humanize config, so no
translated variant is written.

--- Original Design Draft Start ---

# GWFA ISA-Like Rewrite Plan 3c: ISA Lower Controller 32-39

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

See Plans 3a/3b for the register ABI table. This plan extends it for the dedup/finalize pipeline (magics 32-39). Task l6 must verify and extend the ABI before lowering begins.

---

## Goal Description

ISA-lower controller magics 32, 33, 34, 35, 36, 37, 38, 39. Each lowered, verified, and ISA-reviewed individually.

## Prerequisites

Plans 1+2a+2b+2c+3a+3b complete. Controller 16-31 ISA-lowered. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after EACH magic, mode 2 at end)
- AC-2: No C++ runtime variables
- AC-3: No runtime if/else/for/while
- AC-4: VLIW pairing, no RAW hazards (ISA reviewer per magic)
- AC-5: Latency gaps and waitLSQ comments

## Task Breakdown

| Task ID | Description | Tag |
|---------|-------------|-----|
| l6 | Plan register allocation for magics 32-39. Extend register ABI from Plans 3a/3b. | analyze |
| l6a | ISA-lower controller 32: gather loops→goto, boundary merge state→gr, PE-serial bulk mvdq preserved | coding |
| l6av | Verify + ISA review controller 32 | coding |
| l6b | ISA-lower controller 33: reload conditionals→goto, tile clamping→branch | coding |
| l6bv | Verify + ISA review controller 33 | coding |
| l6c | ISA-lower controller 34: already mostly ISA-like. Verify and clean up. | coding |
| l6cv | Verify + ISA review controller 34 | coding |
| l6d | ISA-lower controller 35: writeback loop→goto, pre-computed destinations preserved | coding |
| l6dv | Verify + ISA review controller 35 | coding |
| l6e | ISA-lower controller 36: already has goto labels. Finish register-only, add latency comments. | coding |
| l6ev | Verify + ISA review controller 36 | coding |
| l6f | ISA-lower controller 37: binary search→goto, tile load→register ops | coding |
| l6fv | Verify + ISA review controller 37 | coding |
| l6g | ISA-lower controller 38: already has fused search. Finish register-only. | coding |
| l6gv | Verify + ISA review controller 38 | coding |
| l6h | ISA-lower controller 39: already mostly register-based. Final cleanup. | coding |
| l6hv | Verify + ISA review controller 39 | coding |
| l7 | Full verification: mode 2 -t 56 | coding |

--- Original Design Draft End ---
