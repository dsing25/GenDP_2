# GWFA ISA-Like Rewrite Plan 2b (Humanized): PE Structural Residuals

## Goal Description

Complete the structural ISA-like rewrites for PE magics 19 (FIN0 finalize), 22
(merge), and 23 (dedup) in `pe.cpp`, preserving correctness and following the
12 ISA-like rules from the shared preamble (one gendp ISA op per VLIW slot,
two slots = one VLIW cycle = one line in pe.cpp macro form, no RAW hazards
between paired instructions, gr/reg/s1c/spm/mm registers only for live state,
goto labels instead of if/else/for/while, 2-cycle SPM latency per AC-7 below,
mvd/mvdq bulk transfers for contiguous data, no `std::min`/`std::max` on the
controller). PE 22 targets elimination of the per-iteration second-buffer
check by turning buffer exhaustion into a labeled transition while still
safely handling stream-tail cases where the alternate tile count is zero.
PE 23 targets a reduced save/resume state plus correct SPM-latency separation
in `M23_RD` / `M23_RI` per AC-7, plus `mvd` for merge-adjacent intv output
writes. PE 19 targets
`mvd` for contiguous FIN0 subfields plus half-register use for 16-bit
extractions, modeled after the frozen PE 8 / PE 13 reference patterns.

Correctness gates: `gwfa_check_correctness.py 1 -t 56 = 15/15` after each of
the three PE magic commits, `gwfa_check_correctness.py 2 -t 56 = 295/295` on
the final tree, and `gendp-isa-reviewer` clean on every changed magic.

Plan 2b also includes a follow-up scope item retroactively added during
the planning workflow (see AC-11 and Milestone F below): an audit-and-fix
pass for SPM-latency scheduling in the Plan 2a controller magics (20,
31, 32). Plan 2a's AC-4 wording was ambiguous about cycle accounting,
and the implementation uses a 2-NOP pattern between SPM load and
consumer that is legal only when the load lands in slot 1 of its VLIW
pair. Chains where the load lands in slot 0 currently have the consumer
in the in-flight cycle and are illegal under the correct AC-7 rule.
Milestone F audits every SPM-load-to-use chain in magics 20, 31, 32 and
applies per-chain fixes (either adding a NOP to push the consumer into
cycle N+2, or reshuffling the pair alignment to move the load into
slot 1). Mode 2 -t 56 = 295/295 must remain on HEAD throughout.

## Acceptance Criteria

Following TDD philosophy, each criterion below defines positive tests
(expected to pass when the criterion is met) and negative tests (expected to
fail or be rejected when something is wrong).

- AC-1: Per-magic correctness. After each of the three PE magic commits,
  `gwfa_check_correctness.py 1 -t 56` returns 15/15 on the post-commit tree.
  - Positive Tests:
    - Mode 1 -t 56 returns "15 passed, 0 failed out of 15" after each magic
      commit.
    - `make -j ADDRESS_SANITIZER=0` is clean before every mode-1 run.
  - Negative Tests:
    - Any mode-1 case producing `sim=-1` or a wrong score blocks the magic
      commit until reverted or re-patched.
    - A build warning regressing into the mode-1 run without a clean build
      blocks the commit.
  - AC-1.1: PE 22 commit: mode 1 -t 56 = 15/15, with case 2 (historically
    infinite-looped per the draft's "Known Issues") specifically passing.
    - Positive: case 2 returns its golden score inside the mode-1 run.
    - Negative: case 2 hangs past the mode-1 timeout, or returns `sim=-1`.
  - AC-1.2: PE 23 commits: mode 1 -t 56 = 15/15 after each of the three
    PE 23 commits — `t2a_impl` (ABI reduction), `t2b_impl`
    (always-live save elision), and `t2cd_impl` (latency + mvd).
    - Positive: 15/15 on all three PE 23 commits in the plan sequence
      (`t2a_impl`, `t2b_impl`, `t2cd_impl`).
    - Negative: any of the three PE 23 commits fails mode 1.
  - AC-1.3: PE 19 commit: mode 1 -t 56 = 15/15.
    - Positive: 15/15 on the PE 19 commit.
    - Negative: mode 1 fails; the PE 19 commit is reverted or re-patched.

- AC-2: `gendp-isa-reviewer` clean per magic. After each magic commit, the
  reviewer is run on the changed magic and every finding is dispositioned in
  the round summary as `fixed`, `exception-approved`, or
  `false-positive-confirmed`. Any `exception-approved` disposition MUST
  explicitly name the approver (role or identity) and cite the concrete
  criterion that justifies the exception (for example a referenced
  BitLesson ID or a named plan AC).
  - Positive Tests:
    - Reviewer report for PE 22 / PE 23 / PE 19 shows no open P0 findings
      after disposition.
    - Every P1/P2 finding has a written disposition tied to a specific fix
      or a documented rationale.
    - Every `exception-approved` entry names approver + criterion.
  - Negative Tests:
    - An unresolved P0 finding blocks progress to the next magic.
    - A P1/P2 finding without written disposition blocks review acceptance.
    - An `exception-approved` entry missing approver or criterion blocks
      review acceptance.

- AC-3: End-of-plan mode-2 hard gate. `gwfa_check_correctness.py 2 -t 56 =
  295/295` on the tree after the last of the three magic commits (typically
  PE 19's commit) has landed.
  - Positive Tests:
    - Mode 2 -t 56 returns "295 passed, 0 failed out of 295".
  - Negative Tests:
    - Any mode-2 count below 295 blocks plan exit.
    - A mode-2 run that hits a timeout or crash blocks plan exit.

- AC-4: PE 22 per-label invariants. The new PE 22 code carries a documented
  invariant set at each label (for example `need_a`, `need_b`, `eval`,
  `emit`, `switch`, `done`). Invariants cover the live state of
  `ai`/`bi`/`ai0`/`bi0`/`a_n`/`b_n` at that label's entry. Evidence must
  live in a durable artifact — either an inline comment block in `pe.cpp`
  at the magic 22 body OR a QA-ledger entry referenced by the round
  summary. A commit message alone is NOT sufficient evidence.
  - Positive Tests:
    - A durable artifact (code comment block or QA-ledger row)
      enumerates invariants for every label in the rewrite.
    - Each invariant references concrete register or SPM state.
  - Negative Tests:
    - A label without a documented invariant in the durable artifact
      blocks review acceptance.
    - An invariant documented only in the commit message (and not in
      code comments or ledger) blocks review acceptance.
    - An invariant that contradicts the BL-20260413-drain-budget rule
      (separate drain path forbidden) blocks review acceptance.

- AC-5: PE 22 tail-case preservation. Boundary-position writes at
  `spm[976..983]` and the `cum_oi` slot at `spm[982]` are preserved
  bit-exactly relative to the pre-Plan-2b PE 22 behavior on stream-tail
  cases where the alternate tile count (fields at `MERGE_META+9..12`
  seen in `pe_array.cpp`) reports `MERGE_META+10==0` (next-A-tile zero)
  or `MERGE_META+12==0` (next-B-tile zero). Preservation evidence must
  come from a pre-change capture versus post-change capture pair on at
  least one concrete mode-1 case that exercises a tail with zero
  alternate tile, stored in the QA ledger entry for PE 22.
  - Positive Tests:
    - Pre-change trace snapshot of `spm[976..983]` and `spm[982]` on a
      named mode-1 case that hits `MERGE_META+10==0` or
      `MERGE_META+12==0`.
    - Post-change trace snapshot on the same case, byte-for-byte equal to
      the pre-change snapshot.
    - The `pe_global_base` handling from BL-20260413-pe-global-base is
      unchanged.
  - Negative Tests:
    - Any divergence in the tracked SPM slots on a tail case blocks
      commit.
    - Absence of a pre-change baseline snapshot blocks the PE 22 commit.
    - A rewrite that relies on "second buffer always full" as an
      unconditional invariant (rather than as a labeled transition gated
      on tile-exhausted) is rejected.

- AC-6: PE 23 checkpoint-ABI contract. Before any PE 23 save-scope
  reduction lands, a checkpoint-ABI table for `DEDUP_META[0..19]`
  classifies each slot into one of four roles:
  1. `controller-read` — the slot is read by a controller magic in
     `pe_array.cpp` (for example `DEDUP_META+2` / `+3` consumed by magic
     31 at pe_array.cpp around line 3176).
  2. `controller-write-reload-handshake` — the slot is written by a
     controller magic and read back by PE 23 as part of the reload/resume
     handshake. `DEDUP_META+10..13` fall here: magic 30 in
     `pe_array.cpp` writes these slots around lines 3111-3144 as the
     diag/intv tile-count handshake.
  3. `pe-resume` — the slot is written and read only by PE 23 across
     yield points (no controller magic touches it).
  4. `dead` — the slot is written but never read by any magic (proven
     dead by audit).
  `DEDUP_META+8` and `DEDUP_META+9` are explicitly dispositioned per
  DEC-2 as one of the four roles above (no slot may be left
  "unclassified"). The table MUST also include an explicit generator
  audit note confirming that `scripts/gwfa_instruction_generator.py`
  does NOT reference `DEDUP_META`, so generator changes are not
  required for any PE 23 contract change.
  - Positive Tests:
    - Table present in the round summary before the PE 23 save-scope
      reduction commit lands.
    - Every slot has a stated role (one of the four) backed by a grep or
      audit reference into `pe_array.cpp`.
    - Generator-audit note is present.
  - Negative Tests:
    - A slot whose role is "unknown" or "unclassified" blocks the PE 23
      save-scope reduction commit (`t2a_impl`).
    - A reduction that removes a slot later proven
      `controller-read` or `controller-write-reload-handshake` blocks
      commit.
    - An ABI table that lists `DEDUP_META+10..13` as `pe-resume` (rather
      than `controller-write-reload-handshake`) blocks commit.

- AC-7: PE 23 SPM latency discipline. `M23_RD` and `M23_RI` macros enforce
  the shared preamble rule 6 2-cycle SPM latency.

  **Cycle-accounting convention used by this plan** (authoritative for all
  "N-cycle" references in Plan 2b):
  - Each line of ISA-like code in `pe.cpp` / `pe_array.cpp` magic bodies
    represents **one gendp ISA instruction** (one slot of a VLIW pair).
  - Each pair of consecutive code lines = **one VLIW cycle** (slot 0 +
    slot 1). A blank line typically separates one pair from the next
    but is not required; when absent, pairs are parsed as
    (lines 2k, 2k+1) starting from a known alignment point (the first
    instruction of the magic body, or after an explicit pair boundary
    marker).
  - "SPM 2-cycle latency" = load issued in cycle N; data received at the
    END of cycle N+1 (the in-flight cycle); earliest legal consumer is
    in cycle N+2.
  - Equivalently, if the load is ins1 or ins2 of its pair (cycle N),
    then ins1, ins2, ins3, ins4 (covering cycles N and N+1) CANNOT
    consume the load. ins5 or ins6 (cycle N+2) CAN consume.
  - Minimum legal SEPARATION depends on the load's slot position within
    its VLIW pair:
    - If the load is in slot 0 of its pair, minimum gap = 3 instruction
      lines before the first legal consumer line.
    - If the load is in slot 1 of its pair, minimum gap = 2 instruction
      lines before the first legal consumer line.
    - The simple, slot-agnostic statement: **the consumer's VLIW cycle
      must be at least 2 cycles after the load's VLIW cycle.**

  Concretely for `M23_RD` / `M23_RI`:
  - Each SPM load inside the macro must be followed by enough
    intervening ISA instructions (useful work OR NOPs) to push the
    first consumer into a VLIW cycle at least 2 cycles after the
    load's cycle.
  - Each SPM load must be annotated in the macro body with a short
    comment identifying:
    1. The load's cycle and slot (e.g. `// cycle N slot 0`).
    2. The first-consumer line's cycle and slot.
    3. The intervening instructions used to satisfy the gap.
    Example: `// SPM load cycle N slot 0; sep: add (N slot 1), NOP pair (cycle N+1); use cycle N+2 slot 0.`

  - Positive Tests:
    - Every SPM load in `M23_RD` and `M23_RI` has its consumer in
      a VLIW cycle >= load's cycle + 2.
    - Every SPM load has an inline `// cycle ...; sep: ...; use ...`
      annotation that identifies the load's cycle / slot, the
      separating instructions, and the consumer's cycle / slot.
    - Mode 1 -t 56 = 15/15 after the latency fix.
  - Negative Tests:
    - Any SPM load whose consumer is in the same cycle as the load
      (cycle N) or in the immediately following cycle (cycle N+1 =
      in-flight) blocks commit.
    - An SPM load in the macros missing the cycle/slot annotation
      blocks commit.
    - An inline annotation that claims a gap but does not match the
      actual VLIW pair alignment of the surrounding code blocks
      commit.

- AC-8: PE 23 mvd emission sites. `mvd` (double-word move) for
  merge-adjacent intv output writes is applied only where the state
  machine produces consecutive intvs at contiguous SPM locations. Other
  intv writes remain scalar. All `mvd` sites are listed in the round
  summary with justification.
  - Positive Tests:
    - Round summary lists each applied `mvd` site with its SPM contiguity
      argument.
    - Mode 1 -t 56 = 15/15 post-commit.
  - Negative Tests:
    - A `mvd` applied at a non-contiguous write site blocks commit.
    - A `mvd` emission that silently merges non-adjacent intvs blocks
      commit.

- AC-10: PE 22 optional tail fast-path (user-approved per OPT-1).
  After the labeled-transition commit (`t1_impl`) lands, a separate
  fast-path commit (`t1_fastpath`) hoists invariant comparisons out
  of the `eval` label to optimize the happy-path case (both tiles
  non-zero). The fast-path MUST preserve AC-5 bit-exactness on tail
  cases where `MERGE_META+10==0` or `MERGE_META+12==0`, and MUST
  NOT re-introduce any per-iteration check of the alternate buffer.
  The fast-path is in its own commit so a regression localizes
  cleanly to the optimization rather than the restructure.
  - Positive Tests:
    - Pre/post fast-path comparison on the AC-5 tail case shows
      bit-exact `spm[976..983]` / `spm[982]` match.
    - Mode 1 -t 56 = 15/15 after the fast-path commit.
    - `gendp-isa-reviewer` on the fast-path diff reports no per-
      iteration alternate-buffer checks re-introduced.
  - Negative Tests:
    - Any tail-case divergence in `spm[976..983]` / `spm[982]`
      blocks the fast-path commit.
    - A diff that moves an alternate-buffer check back into the
      per-iteration hot path blocks the fast-path commit.
    - Bundling the fast-path into `t1_impl` (same commit as the
      restructure) blocks review acceptance — the plan requires the
      two changes in separate commits for localization.

- AC-11: Plan-2a controller-magic SPM-latency audit and fix. The
  controller magics rewritten in Plan 2a — magic 20 (FIN0 subsequent
  batch load), magic 31 (dedup writeback), and magic 32 (dedup
  finalize gather) — are audited against the AC-7 cycle-accounting
  convention. Plan 2a's wording was ambiguous about cycle counting
  (see the retroactive clarification added to Plan 2a's AC-4);
  the actual `pe_array.cpp` code uses a 2-NOP pattern between SPM
  load and consumer that is legal only when the load lands in slot 1
  of its VLIW pair (putting the consumer in cycle N+2 slot 0) and
  illegal when the load lands in slot 0 (putting the consumer in
  cycle N+1 slot 1 = in-flight). Every SPM-load-to-use chain in
  magics 20, 31, 32 is enumerated with its actual pair alignment and
  classified under AC-7 as one of:
  - LEGAL — consumer-cycle = load-cycle + 2 (exactly matches the rule).
  - ILLEGAL — consumer-cycle < load-cycle + 2 (rule violation).
  - OVER-PADDED — consumer-cycle > load-cycle + 2 without a documented
    justification (wastes cycles).
  Both ILLEGAL and OVER-PADDED chains are FIXED. Fixes may include:
  (a) Adding an extra NOP to push the consumer into cycle N+2 (safe
      default for ILLEGAL chains).
  (b) Reshuffling surrounding instructions to shift the load into
      slot 1 of its pair (lets a 2-NOP region satisfy the rule; also
      useful to regularize chains so (d) can apply cleanly).
  (c) Replacing NOP padding with real useful work that would otherwise
      wait until after the consumer (best case, saves cycles AND
      satisfies the rule).
  (d) Removing unnecessary NOP lines from OVER-PADDED chains so that
      consumer-cycle lands exactly at load-cycle + 2. This is the
      most common fix for Plan 2a chains where the original
      implementation inserted more padding than the correct rule
      requires.

  Each chain kept intentionally conservative (consumer-cycle >
  load-cycle + 2 deliberately) must carry an inline justification
  comment explaining WHY (for example, a cross-magic hazard the
  strict rule does not catch, or scheduling convenience that
  outweighs the cycle cost). A chain without justification that
  remains over-padded after the fix commit is rejected.

  - Positive Tests:
    - Plan 2b audit note enumerates every SPM-load-to-use chain in
      magics 20, 31, 32, with each chain's load-cycle / slot,
      consumer-cycle / slot, AC-7 verdict, and fix (if any).
    - Every chain in the post-commit code has consumer-cycle >=
      load-cycle + 2.
    - Mode 1 -t 56 = 15/15 after each per-magic fix commit.
    - Mode 2 -t 56 = 295/295 after the final Milestone F commit.
    - `gendp-isa-reviewer` clean on each fixed magic.
  - Negative Tests:
    - A chain in magic 20, 31, or 32 that is NOT enumerated in the
      audit note blocks the fix commit.
    - A fix that leaves any chain with consumer in load-cycle or
      load-cycle+1 (in-flight) is rejected.
    - A chain classified OVER-PADDED in the audit that is not
      trimmed AND has no written justification for the extra
      padding blocks review acceptance.
    - A fix that regresses mode 1 -t 56 or mode 2 -t 56 is rejected
      and reverted.
    - A chain documented as "intentionally conservative" without a
      written justification blocks review acceptance.

- AC-9: PE 19 scope containment. `mvd` conversion is limited to contiguous
  FIN0 subfields (for example diag `[vd,k]` pairs; arc-record
  `[packed_vw, ow]` pairs where contiguous). The three-word arc record
  including `ts_off` remains scalar. Half-register use is limited to 16-bit
  extract sites modeled after the frozen PE 8 / PE 13 reference patterns.
  Swizzled `mvi2_ld` sequence loads and the HA 4-bucket probe/mix remain
  scalar.
  - Positive Tests:
    - Commit diff shows `mvd` only at listed contiguous subfield sites.
    - FIN0 edge cases pass in mode 1: the round summary identifies a
      specific mode-1 case for each of empty bucket, full bucket,
      `nv==0`, and mixed absent/present arc paths (cases selected by
      running the mode-1 dataset once pre-change with bucket / arc
      counters logged, then tagging the specific case indices that
      exercise each condition). The named cases must all pass post-change.
    - Round summary enumerates the half-register sites with a PE 8 or PE
      13 reference.
  - Negative Tests:
    - `mvd` applied to a non-contiguous field (for example across the
      `ts_off` gap in the 3-word arc record) blocks commit.
    - A commit that rewrites swizzled `mvi2_ld` or HA bucket mix without
      an explicit DEC-3 approval is rejected.
    - An edge-case claim without a named mode-1 case backing it blocks
      review acceptance.

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)

Three PE magics (19, 22, 23) each rewritten per the tasks below with: full
ISA-like structural form (goto labels with invariants, VLIW pairing with no
RAW hazards, live state only in gr / reg / s1c / spm / mm, SPM-load-to-use
separation per AC-7 (consumer's VLIW cycle >= load's VLIW cycle + 2;
each SPM load annotated with cycle / slot of load, separators, and
consumer per AC-7), `mvd` bulk transfers for contiguous subfields,
half-register packing for 16-bit fields); per-magic commit with
`make -j ADDRESS_SANITIZER=0`, mode 1 -t 56 = 15/15, and
`gendp-isa-reviewer` clean; PE 23 split into three commits
(checkpoint-ABI reduction, then always-live save elision, then latency
+ mvd cleanup — `t2a_impl` / `t2b_impl` / `t2cd_impl`); PE 22 with
per-label invariants recorded in an inline `pe.cpp` comment block or a
referenced QA-ledger entry (per AC-4; commit message alone is not
sufficient); QA-ledger entries citing each AC; plus a
controller-magic SPM-latency audit-and-fix follow-up (Milestone F,
AC-11) that enumerates every SPM-load-to-use chain in Plan 2a's
magics 20 / 31 / 32 with its pair alignment and fixes any chain
whose consumer currently lands in the load-cycle or the in-flight
cycle. Final tree passes mode 2 -t 56 = 295/295.

### Lower Bound (Minimum Acceptable Scope)

Three PE magics rewritten with: PE 22 buffer-exhaustion as a labeled
transition (not per-iteration) that preserves the original
`(ai-ai0) + (bi-bi0)` budget formula and `spm[976..983]` / `cum_oi` writes;
PE 23 save-scope reduced per a checkpoint-ABI table + SPM load-to-use
separation corrected per AC-7 (consumer's VLIW cycle >= load's VLIW
cycle + 2, verified against actual pair alignment in the pe.cpp
macro body) + `mvd` at identified merge-adjacent sites (three
separate commits: `t2a_impl`, `t2b_impl`, `t2cd_impl`); plus the
AC-11 SPM-latency audit for magics 20 / 31 / 32 in
`pe_array.cpp` with a fix commit for whichever magic has the largest
set of chains that currently violate the rule.; PE 19 `mvd` for contiguous diag / arc subfields + half-register
extractions at PE 8 / PE 13-modeled sites. Mode 1 -t 56 = 15/15 per magic,
mode 2 -t 56 = 295/295 at end, reviewer reports dispositioned.

### Allowed Choices

- Can use: goto labels with documented invariants; `constexpr` constants;
  helper macros when all live state is in registers or memory; `mvd`
  (double-word move) for contiguous SPM-to-SPM or SPM-to-register
  transfers; half-register packing and extraction for 16-bit fields;
  PE-side `std::min` / `std::max` (the controller rule is not relevant in
  these PE-local magics); splitting PE 23 into three commits (ABI
  reduction, always-live save elision, and latency + mvd cleanup, each
  validated separately); reference examples from PE 8 and
  PE 13 for half-register and `mvd` patterns.
- Cannot use: `std::min` / `std::max` on the controller path; C++ runtime
  scratch variables for live ISA state; SPM load-to-use gaps of less than
  what AC-7 requires (i.e. any pe.cpp macro where the consumer line
  immediately follows the SPM load line with no separator line in
  between); rewriting magics outside 19 / 22 / 23; touching Controller
  magics, frozen reference PE magics 8 / 11 / 13, or the compute-instruction
  lowering that the shared preamble defers; the literal "second buffer
  always full" shortcut that would skip the buffer-switch check on
  stream-tail cases where the alternate tile count is zero.

## Feasibility Hints and Suggestions

### Conceptual Approach

PE 22 (merge): refactor the current goto-based merge into explicit labeled
blocks — for example `need_a` (refill A stream state when `ai < a_n`),
`need_b` (refill B stream state when `bi < b_n`), `eval` (compare A and B
heads and decide emit direction), `emit` (write the selected element and
update boundary metadata), `switch` (entered only when `ai >= a_n` or
`bi >= b_n`, performing the buffer swap and adjusting `ai0` / `bi0` per
BL-20260413-drain-budget), `done` (budget exhausted or both streams
drained). Each label opens with a documented invariant over
`ai`/`bi`/`ai0`/`bi0`/`a_n`/`b_n`. Buffer switch becomes a rare labeled
transition rather than a per-iteration check. Boundary-position writes at
`spm[976..983]` and `cum_oi` at `spm[982]` are preserved bit-exactly
relative to the pre-Plan-2b behavior.

PE 23 (dedup): first commit collapses save/resume state to the
always-live set (`pv`, `pk`, `dc`, `ic`, `dw`, `iw`, `clo`, `chi`, `state`,
`pdone`, `nv`, `nk`) per the checkpoint-ABI table. `DEDUP_META+2` /
`DEDUP_META+3` (output counts consumed by magic 31 in `pe_array.cpp` around
line 3176) are classified `controller-read` (role 1 in the AC-6
taxonomy). `DEDUP_META+10..13` (the current / next tile-count pair for
both diag and intv buffers) are classified
`controller-write-reload-handshake` (role 2), since magic 30 in
`pe_array.cpp` (around lines 3111-3144) both writes these slots (after
reloading from MM) and reads them back for the handshake condition;
PE 23 must not treat them as pe-resume-only.
`DEDUP_META+8` / `DEDUP_META+9` disposition follows DEC-2. Current intv
(`clo`, `chi`) and current diag (`pv`, `pk`) stay in registers across yield
points to eliminate redundant reloads. Second commit inserts the
SPM-load-to-use separation required by AC-7 in `M23_RD` and `M23_RI`
(at least 1 full VLIW line between load and first consumer in the
pe.cpp macro form) and applies `mvd` only at intv output writes where
the state machine produces consecutive intvs at contiguous SPM
locations.

PE 19 (FIN0): apply `mvd` only to contiguous subfields (diag `[vd, k]`
pairs at `FIN0_DIAGS+2*d`; arc-record `[packed_vw, ow]` pairs where laid out
contiguously — not across the non-contiguous `ts_off` in the full 3-word
arc record). Apply half-register extraction at 16-bit fields modeled after
PE 8 (roughly lines 708-1150 in `pe.cpp`) and PE 13 (roughly lines
1151-1400+ in `pe.cpp`). Keep swizzled `mvi2_ld` sequence loads and the
4-bucket HA probe/mix scalar.

### Relevant References

- `pe.cpp` — PE magic dispatch; magics 19, 22, 23 targeted; magics 8, 11,
  13 as frozen reference examples.
- `pe_array.cpp` — controller magic dispatch; the `MERGE_META` and
  `DEDUP_META` contracts are consumed by magics 30 / 31 / 32, which must
  remain bit-compatible with PE-side changes. Plan 2b's Milestone F
  (AC-11) also audits and fixes SPM-latency scheduling in magics
  20, 31, 32 inside this file; fixes must not change any SPM
  read-or-write semantics, only the VLIW-cycle position of
  surrounding padding / reshuffling.
- `scripts/gwfa_instruction_generator.py` — GWFA instruction generator
  (not modified by this plan, but must remain consistent with any
  `DEDUP_META` slot reductions).
- `.humanize/bitlesson.md` — BL-20260413-drain-budget,
  BL-20260413-gr-clobber, BL-20260413-pe-global-base,
  BL-20260416-m32-gather-dep, BL-20260417-* (selector, stall-flag,
  PE-reset) rules.
- `CLAUDE.md` — shared preamble rules; rule 6 (SPM 2-cycle latency) is the
  key precedent overriding the draft's p2c wording.
- `kernel/Gwfa/Datasets/Gwfa295` — validation dataset accessed via
  `gwfa_check_correctness.py`.

## Dependencies and Sequence

### Milestones

1. Milestone A — PE 22 merge structural rewrite + optional tail
   fast-path
   - Step A1: enumerate per-label invariants over
     `ai`/`bi`/`ai0`/`bi0`/`a_n`/`b_n`.
   - Step A2: capture pre-change snapshot of `spm[976..983]` / `spm[982]`
     on a named mode-1 case exercising `MERGE_META+10==0` or
     `MERGE_META+12==0` (AC-5 baseline).
   - Step A3: implement labeled transitions in a standalone commit;
     buffer switch gated on `ai >= a_n` or `bi >= b_n` with the
     `ai0`/`bi0` adjust preserved per BL-20260413-drain-budget.
   - Step A4: run `make -j ADDRESS_SANITIZER=0`, mode 1 -t 56 = 15/15
     (case 2 must pass), capture post-change snapshot and diff against
     Step A2 snapshot, `gendp-isa-reviewer` clean.
   - Step A5: implement tail fast-path in a SEPARATE commit (OPT-1
     approved); hoist invariant comparisons out of `eval`; preserve
     AC-5 bit-exactness; no per-iteration alternate-buffer check.
   - Step A6: mode 1 -t 56 = 15/15 post-fast-path; pre/post snapshot
     equality on the AC-5 case; reviewer clean.
   - Step A7: QA ledger entry covering AC-4 (invariants), AC-5
     (tail-case preservation), and AC-10 (fast-path bit-exactness).
2. Milestone B — PE 23 checkpoint-ABI reduction (p2a)
   - Step B1: compile the `DEDUP_META[0..19]` table
     with the AC-6 four-role taxonomy (`controller-read` /
     `controller-write-reload-handshake` / `pe-resume` / `dead`) by
     grepping / auditing
     `pe_array.cpp` magics 30 / 31 / 32 and the PE 23 body.
   - Step B2: apply the save-scope reduction (keep pv / pk / dc / ic /
     dw / iw / clo / chi / state / pdone / nv / nk; remove the duplicated
     n_do / n_io; retain or remove +8 / +9 per DEC-2).
   - Step B3: mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean.
3. Milestone C1 — PE 23 always-live save elision (p2b)
   - Step C1.1: promote current intv (`clo`, `chi`) and current diag
     (`pv`, `pk`) to always-live registers across yield points where they
     have not changed.
   - Step C1.2: commit as a standalone change; mode 1 -t 56 = 15/15;
     `gendp-isa-reviewer` clean. Any regression attributable to this
     commit is localized cleanly before latency / mvd work begins.
4. Milestone C2 — PE 23 latency and mvd cleanup (p2c + p2d)
   - Step C2.1: apply the AC-7 SPM-load-to-use separation in
     `M23_RD` and `M23_RI` (consumer's VLIW cycle >= load's VLIW
     cycle + 2, where each pair of consecutive lines = 1 VLIW
     cycle; this is the shared-preamble rule-6 latency, stronger
     than the draft's p2c "1 instruction" wording). Annotate each
     SPM load with the cycle / slot of load, the separating
     instructions, and the cycle / slot of consumer per AC-7.
   - Step C2.2: identify merge-adjacent intv output write sites and apply
     `mvd` only there.
   - Step C2.3: mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean.
5. Milestone D — PE 19 FIN0 `mvd` + half-register
   - Step D1: enumerate contiguous subfield sites (diag `[vd, k]`; arc
     `[packed_vw, ow]`) and 16-bit extract sites modeled after PE 8 /
     PE 13. Record non-goals (swizzled `mvi2_ld`, HA bucket mix).
   - Step D2: apply `mvd` and half-register conversions only at the
     enumerated sites.
   - Step D3: mode 1 -t 56 = 15/15 (including empty-bucket, full-bucket,
     `nv==0`, mixed absent/present arc edge cases), `gendp-isa-reviewer`
     clean.
6. Milestone F — Plan-2a controller-magic SPM-latency audit and fix
   - Step F1: audit SPM-load-to-use chains in `pe_array.cpp` magics
     20, 31, 32. For each chain record: the load's code line, its
     pair alignment (slot 0 or slot 1 of its VLIW cycle inferred from
     surrounding code), the load's VLIW cycle number relative to the
     magic body start, the first-consumer line and its cycle, the
     AC-7 verdict (LEGAL if consumer-cycle == load-cycle + 2;
     ILLEGAL if consumer-cycle < load-cycle + 2; OVER-PADDED if
     consumer-cycle > load-cycle + 2 without a documented reason),
     and the planned fix (if any). Record the audit table in the
     plan summary; this satisfies the AC-11 enumeration requirement.
   - Step F2: for each ILLEGAL or OVER-PADDED chain, apply a
     per-magic fix in a separate commit (one commit for magic 20
     fixes, one for magic 31, one for magic 32). Fix options per
     chain:
     (a) Add one NOP to push the consumer into cycle N+2 (for
         ILLEGAL chains).
     (b) Reshuffle adjacent instructions to move the load into slot
         1 of its pair, so the existing 2-NOP padding becomes legal.
     (c) Replace NOP padding with useful work that would otherwise
         happen after the consumer.
     (d) Remove unnecessary NOP lines from OVER-PADDED chains so the
         consumer lands exactly at cycle N+2.
     Each fix commit preserves mode 1 -t 56 = 15/15.
   - Step F3: document any chain kept intentionally conservative
     (consumer-cycle > load-cycle + 2) with an inline justification
     comment (for example a cross-magic hazard the strict rule does
     not catch, or scheduling convenience that outweighs the cycle
     cost).
   - Step F4: reviewer clean on each fixed magic. Mode 2 -t 56 =
     295/295 re-verified on the final Milestone F tree.
7. Milestone E — End-of-plan verification
   - `gwfa_check_correctness.py 2 -t 56 = 295/295` (AC-3 hard gate)
     on the tree that includes Milestones A, C, D, and F.

Dependencies:

- Milestone B completes before Milestone C1 (always-live save elision
  depends on the reduced checkpoint ABI).
- Milestone C1 completes before Milestone C2 (latency / mvd cleanup
  depends on the save-elision being validated; this ordering gives
  clean failure localization on the riskiest PE magic).
- Milestones A (including the optional fast-path sub-commit),
  (B → C1 → C2), D, and F are otherwise independent and may land in
  any order.
- Milestone F's audit (Step F1) must complete before any Milestone F
  fix commit (Step F2) lands; within Step F2 the per-magic fix
  commits are independent and may land in any order.
- Milestone E runs only after A's fast-path sub-commit
  (`t1_fastpath_v` if OPT-1 is taken, else `t1_v`), C2, D, and the
  last Milestone F fix commit have all landed.

## Task Breakdown

Each task carries exactly one routing tag: `coding` for Claude-executed
tasks, `analyze` for Codex-executed tasks via `/humanize:ask-codex`.

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| t1_invariants | Enumerate PE 22 per-label invariants (for example `need_a`, `need_b`, `eval`, `emit`, `switch`, `done`) over `ai` / `bi` / `ai0` / `bi0` / `a_n` / `b_n` before implementation. Record in the durable artifact required by AC-4 (inline comment block or QA ledger, NOT commit message only). | AC-4 | coding | - |
| t1_baseline | Identify at least one concrete mode-1 -t 56 case that exercises a PE 22 stream-tail where `MERGE_META+10==0` or `MERGE_META+12==0`. Capture a pre-change snapshot of `spm[976..983]` and `spm[982]` on that case; store it in the QA ledger. This is the AC-5 baseline. | AC-5 | coding | - |
| t1_impl | Implement PE 22 labeled restructure in `pe.cpp`: buffer-switch runs only when `ai >= a_n` or `bi >= b_n`; preserve original `(ai-ai0)+(bi-bi0)` budget formula; preserve `spm[976..983]` and `cum_oi` writes bit-exactly. | AC-1.1, AC-5 | coding | t1_invariants, t1_baseline |
| t1_v | Validate PE 22: `make -j ADDRESS_SANITIZER=0`, `gwfa_check_correctness.py 1 -t 56 = 15/15` (case 2 specifically passing); capture the POST-change snapshot of `spm[976..983]` / `spm[982]` on the AC-5 case and diff against the pre-change snapshot; `gendp-isa-reviewer` clean. Record QA-ledger entry for AC-4 / AC-5. | AC-1.1, AC-2, AC-4, AC-5 | coding | t1_impl |
| t1_fastpath | PE 22 tail fast-path (OPT-1 approved): hoist invariant comparisons out of the `eval` label in a separate commit after `t1_impl`. Must preserve AC-5 bit-exactness and must not re-introduce per-iteration alternate-buffer checks. | AC-10 | coding | t1_v |
| t1_fastpath_v | Validate fast-path: `make`, mode 1 -t 56 = 15/15, AC-5 tail-case pre/post snapshot bit-exact, `gendp-isa-reviewer` confirms no per-iteration alternate-buffer check re-introduced. | AC-1.1, AC-2, AC-5, AC-10 | coding | t1_fastpath |
| t2a_abi | Compile the `DEDUP_META[0..19]` checkpoint-ABI table with the AC-6 four-role taxonomy (`controller-read` / `controller-write-reload-handshake` / `pe-resume` / `dead`) by auditing `pe_array.cpp` magics 30 / 31 / 32 and the PE 23 body. Include the generator-audit note confirming `scripts/gwfa_instruction_generator.py` does not reference `DEDUP_META`. Record DEC-2 disposition. | AC-6 | analyze | - |
| t2a_impl | PE 23 p2a: apply save-scope reduction per the ABI table (keep `pv`/`pk`/`dc`/`ic`/`dw`/`iw`/`clo`/`chi`/`state`/`pdone`/`nv`/`nk`; remove duplicated `n_do`/`n_io`; retain or remove `+8`/`+9` per DEC-2). Must not change any slot classified `controller-read` or `controller-write-reload-handshake`. | AC-6 | coding | t2a_abi |
| t2a_v | Validate PE 23 ABI reduction: `make`, mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean. | AC-1.2, AC-2, AC-6 | coding | t2a_impl |
| t2b_impl | PE 23 p2b (save-elision, standalone commit): promote current intv (`clo`, `chi`) and current diag (`pv`, `pk`) to always-live registers at yield points where they haven't changed. No latency or mvd changes yet — isolates any save-elision regression. | AC-1.2, AC-2 | coding | t2a_v |
| t2b_v | Validate PE 23 save-elision: `make`, mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean. Separate checkpoint from latency / mvd work. | AC-1.2, AC-2 | coding | t2b_impl |
| t2cd_impl | PE 23 p2c + p2d (latency + mvd, separate commit): apply the AC-7 SPM-load-to-use separation in `M23_RD` and `M23_RI` (consumer's VLIW cycle >= load's VLIW cycle + 2, verified against actual pair alignment) with full cycle/slot annotations per AC-7; apply `mvd` at identified merge-adjacent intv output write sites (document each site per AC-8). | AC-7, AC-8 | coding | t2b_v |
| t2cd_v | Validate PE 23 latency + `mvd`: `make`, mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean. | AC-1.2, AC-2, AC-7, AC-8 | coding | t2cd_impl |
| t3_sites | Enumerate PE 19 `mvd` + half-register sites (diag `[vd, k]`, arc `[packed_vw, ow]`, 16-bit extracts modeled after PE 8 / PE 13). Record non-goals (swizzled `mvi2_ld`, HA bucket mix). | AC-9 | coding | - |
| t3_impl | PE 19 implementation at the enumerated sites only. | AC-9 | coding | t3_sites |
| t3_v | Validate PE 19: `make`, mode 1 -t 56 = 15/15 (including empty-bucket, full-bucket, `nv==0`, mixed absent/present arc edge cases), `gendp-isa-reviewer` clean. | AC-1.3, AC-2, AC-9 | coding | t3_impl |
| t4_audit | Audit SPM-load-to-use chains in `pe_array.cpp` magics 20, 31, 32. For each chain record the load line, the load's pair-slot alignment (slot 0 or slot 1 of its VLIW cycle), the load's VLIW cycle relative to magic body start, the first-consumer line and its cycle, the AC-7 verdict (LEGAL if consumer-cycle == load-cycle + 2; ILLEGAL if <; OVER-PADDED if > without justification), and the planned fix (if any). Record the full audit table in the round summary. | AC-11 | analyze | - |
| t4_fix_m20 | Fix ILLEGAL and OVER-PADDED SPM-latency chains in magic 20 per `t4_audit` (pe_array.cpp around lines 500-503 and any other chain the audit flags). Each fix may (a) add a NOP to push consumer into cycle N+2, (b) reshuffle to place the load in slot 1 of its pair, (c) replace NOP padding with useful work, or (d) remove unnecessary NOP lines from an OVER-PADDED chain. Document any chain kept intentionally conservative with a justification comment. | AC-11 | coding | t4_audit |
| t4_fix_m20_v | Validate magic 20 fix: `make`, mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean. | AC-1, AC-2, AC-11 | coding | t4_fix_m20 |
| t4_fix_m31 | Fix ILLEGAL and OVER-PADDED SPM-latency chains in magic 31 per `t4_audit`. Same fix options (a)-(d) as t4_fix_m20. Document any chain kept intentionally conservative. | AC-11 | coding | t4_audit |
| t4_fix_m31_v | Validate magic 31 fix: `make`, mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean. | AC-1, AC-2, AC-11 | coding | t4_fix_m31 |
| t4_fix_m32 | Fix ILLEGAL and OVER-PADDED SPM-latency chains in magic 32 per `t4_audit`. Same fix options (a)-(d) as t4_fix_m20. Document any chain kept intentionally conservative. | AC-11 | coding | t4_audit |
| t4_fix_m32_v | Validate magic 32 fix: `make`, mode 1 -t 56 = 15/15, `gendp-isa-reviewer` clean. | AC-1, AC-2, AC-11 | coding | t4_fix_m32 |
| t_fin | End-of-plan: `gwfa_check_correctness.py 2 -t 56 = 295/295`. | AC-3 | coding | t1_fastpath_v, t2cd_v, t3_v, t4_fix_m20_v, t4_fix_m31_v, t4_fix_m32_v |

## Claude-Codex Deliberation

### Agreements

- All three target PE magics are in `pe.cpp`; no controller or generator
  code changes are in scope.
- PE 22 must preserve the existing `(ai-ai0) + (bi-bi0)` budget formula and
  bit-exact boundary-position writes at `spm[976..983]` and `cum_oi`.
- PE 23's resume path drives the 23 → 30 → 31 → 32 pipeline; any change to
  `DEDUP_META` must be proven safe against controller reads at
  `pe_array.cpp` magic 31 (`DEDUP_META+2` / `+3`).
- PE 19 `mvd` conversion should be limited to truly contiguous subfields.
- Shared preamble rule 6 (SPM 2-cycle latency — 1 cycle issue + 1 cycle
  in flight; data lands at start of cycle 3) takes precedence over the
  draft's p2c "1 instruction" wording. In pe.cpp macro form this means
  a minimum 1-VLIW-line gap between the load line and its first-consumer
  line; AC-7 is the authoritative definition.
- `gendp-isa-reviewer` clean per magic is a hard review gate.

### Resolved Disagreements

- Draft's p2c "1 instruction between SPM load and use" versus shared
  preamble rule 6 "2-cycle latency": resolved in favor of rule 6.
  AC-7 encodes the authoritative cycle-accounting convention: each
  line in `pe.cpp` / `pe_array.cpp` magic bodies = one gendp ISA
  instruction (one slot of a VLIW pair); each pair of consecutive
  lines = one VLIW cycle. A 2-cycle latency load issued in cycle N
  is received at end of cycle N+1; the earliest legal consumer is
  in cycle N+2. Each SPM load in `M23_RD` / `M23_RI` carries an
  inline annotation of the load's cycle / slot, the separating
  instructions, and the consumer's cycle / slot.
- PE 23 as a single commit versus split: resolved to a three-commit
  split. Milestone B (ABI reduction, task `t2a_impl`) precedes
  Milestone C1 (save-elision, task `t2b_impl`) precedes Milestone C2
  (latency + `mvd`, task `t2cd_impl`). Each commit has its own
  validation checkpoint. Failures localize cleanly across three
  narrowly-scoped commits rather than one bundled one.
- PE 19 "convert all contiguous loads" versus "only contiguous
  subfields": resolved to "only contiguous subfields" (AC-9). Swizzled
  `mvi2_ld` and HA bucket mix are explicit non-goals.
- PE 22 "don't check second buffer always" versus "check on stream-tail":
  resolved — the labeled-transition structure runs the buffer-switch
  check only on tile exhaustion, but the tail guard at `MERGE_META+10
  == 0` / `MERGE_META+12 == 0` is MANDATORY via AC-5 (bit-exact
  `spm[976..983]` / `cum_oi` preservation). DEC-1 now concerns only
  optional further fast-path beyond the labeled transition.
- AC-4 evidence scope: commit message alone is NOT sufficient.
  Invariants live in an inline `pe.cpp` comment block at the magic
  22 body OR a QA-ledger entry referenced from the round summary.
- AC-2 `exception-approved` semantics: must name the approver and
  cite a concrete criterion (BitLesson ID or plan AC).
- AC-6 DEDUP_META classification: four roles (`controller-read`,
  `controller-write-reload-handshake`, `pe-resume`, `dead`), with
  `DEDUP_META+10..13` explicitly tagged as
  `controller-write-reload-handshake` since magic 30 in
  `pe_array.cpp` (around lines 3111-3144) both reads and writes those
  slots as the diag/intv tile-count reload handshake. The ABI table
  also includes a generator-audit note confirming
  `scripts/gwfa_instruction_generator.py` does not reference
  `DEDUP_META`.
- DEC-2 PE 23 `DEDUP_META+8` / `DEDUP_META+9` disposition: resolved
  by user to "retain as zero-compat". The slots remain written by the
  controller (controller-side writes are not touched in Plan 2b) but
  are classified `dead` in the PE-side ABI table (no PE 23 reader).
  This decouples `t2a_impl` from a full cross-magic audit. A later
  plan may remove them entirely.
- OPT-1 PE 22 optional tail fast-path: resolved by user to "take
  fast-path". A new AC-10 and a new task `t1_fastpath` land the
  hoisting optimization in a separate commit after the
  labeled-transition commit, so any regression is cleanly attributed
  and reviewed. Fast-path must preserve AC-5 bit-exactness and must
  not re-introduce any per-iteration check of the alternate buffer.
- OPT-2 PE 19 scope depth: resolved by user to "strict cleanup
  only". AC-9 remains the binding scope; swizzled `mvi2_ld` and HA
  bucket mix are non-goals. No plan text changes beyond this note.
- Post-convergence scope addition (2026-04-20): AC-11 + Milestone F
  were added to Plan 2b at user request after surfacing that
  Plan 2a's AC-4 wording was ambiguous about cycle counting. The
  user later provided the authoritative cycle-accounting convention
  captured in AC-7: each line in `pe.cpp` / `pe_array.cpp` magic
  body = 1 gendp ISA instruction (one slot of a VLIW pair); two
  consecutive lines = one VLIW cycle; 2-cycle SPM latency =
  consumer's VLIW cycle must be >= load's VLIW cycle + 2. Under
  this correct convention, Plan 2a's 2-NOP pattern between SPM
  load and consumer is legal only when the load happens to land in
  slot 1 of its pair (cycle N slot 1 = load, cycle N+1 = 2 NOPs,
  cycle N+2 slot 0 = consumer — legal). When the load lands in
  slot 0 of its pair, the 2-NOP pattern places the consumer in
  cycle N+1 slot 1 = in-flight = illegal. Plan 2a's retroactive
  clarification was rewritten to reflect this (the original
  retroactive note incorrectly claimed the 2-NOP pattern was
  over-conservative; the correct interpretation is that pair
  alignment determines legality). AC-11 audits every SPM-load-
  to-use chain in magics 20 / 31 / 32 against the correct rule and
  applies per-chain fixes (add NOP, reshuffle for slot-1 alignment,
  or replace NOP with useful work) in separate per-magic fix
  commits, each validated independently.

### Convergence Status

- Final Status: `converged`. Three convergence rounds completed
  (maximum allowed). All Claude/Codex disagreements from rounds 1-3
  are resolved. All user decisions are resolved:
  - DEC-2 (DEDUP_META+8/+9 disposition): user chose retain-as-zero-
    compat.
  - OPT-1 (PE 22 fast-path): user chose to take the fast-path;
    landed as AC-10 + task `t1_fastpath`.
  - OPT-2 (PE 19 scope depth): user confirmed strict-cleanup only.
  - Quantitative metrics (mode 1 = 15/15, mode 2 = 295/295): user
    confirmed as hard requirements.

## Pending User Decisions

(No pending user decisions remain. See the "Resolved Disagreements"
and "Non-Blocking Optional Decisions" sections for the final
dispositions of DEC-2, OPT-1, and OPT-2.)

## Non-Blocking Optional Decisions

These items were originally surfaced as non-blocking optional
decisions during Phase 6 of the planning workflow. Both have since
been resolved by the user and are recorded here for traceability;
the implementation consequences are already reflected in the
Acceptance Criteria, Task Breakdown, and Milestone sections above.

- OPT-1 (formerly DEC-1): PE 22 optional tail fast-path.
  - Resolved baseline: AC-5 makes the tail guard MANDATORY
    (boundary-position writes at `spm[976..983]` / `spm[982]` must be
    bit-exact on cases where `MERGE_META+10==0` or
    `MERGE_META+12==0`). The literal "second buffer always full"
    shortcut that skips the tail guard is rejected.
  - Open question (resolved): should a further non-mandatory
    fast-path optimize the happy-path case (both tiles non-zero)
    beyond the labeled transition — for example hoisting invariant
    comparisons out of `eval`?
  - Claude Position: skip further fast-path; labeled-transition
    restructure is sufficient.
  - Codex Position: fast-path is optional; if taken, must preserve
    AC-5 bit-exactness and not re-introduce any per-iteration check
    of the alternate buffer.
  - Tradeoff Summary: further fast-path trades reviewer-load and
    case-2 regression risk for a marginal throughput gain.
  - User Decision: **take the fast-path**. AC-10 and tasks
    `t1_fastpath` / `t1_fastpath_v` encode the fast-path as a
    separate commit after `t1_impl`, with AC-5 bit-exactness
    preserved and no per-iteration alternate-buffer check.
  - Decision Status: RESOLVED (take fast-path).

- OPT-2 (formerly DEC-3): PE 19 scope depth.
  - Resolved baseline: default Plan 2b scope is strict AC-9 contiguous
    subfield cleanup only; swizzled `mvi2_ld` and HA bucket mix
    rewrites are non-goals unless the user explicitly approves
    expansion.
  - Open question (resolved): does the user want the strict-cleanup
    default, or an expanded scope that also reduces C++ temporaries
    around `mvi2_ld` and HA bucket probing?
  - Claude Position: stay at the strict-cleanup default.
  - Codex Position: same default; if expanded, add a separate AC.
  - Tradeoff Summary: strict cleanup has low risk and a clean
    validation story; expansion touches harder FIN0 semantics.
  - User Decision: **strict cleanup only**. AC-9 remains binding;
    swizzled `mvi2_ld` and HA bucket mix stay scalar. No additional
    AC or task added.
  - Decision Status: RESOLVED (strict cleanup only).

## Implementation Notes

### Code Style Requirements

- Implementation code and comments must NOT contain plan-specific
  terminology such as `AC-`, `Milestone`, `Step`, `Phase`, or similar
  workflow markers. These terms are for plan documentation only, not for
  the resulting codebase.
- Use descriptive, domain-appropriate naming in code instead.
- Follow `gendp/CLAUDE.md`: lines ≤ 100 chars; do not insert line breaks
  unless a line exceeds 100 chars; comment non-obvious intent only; never
  split a single `f.write` call across lines in generator scripts.

### BitLesson Constraints

- BL-20260413-drain-budget: PE 22 merge must continue to drain via the
  unified buffer-switch + comparison loop. The labeled-transition
  restructure must preserve this invariant; separate drain paths are
  forbidden.
- BL-20260413-pe-global-base: PE 22 boundary positions at `spm[976..983]`
  add the per-PE global output base from `spm[983]`. AC-5 explicitly
  requires this handling to be unchanged.
- BL-20260413-gr-clobber: any gr register reuse across pipeline phases
  requires explicit save/restore. Not expected to apply in these PE-local
  magics, but the reserved set (`gr[7..10]`) must still be respected per
  Plan 2a precedent.
- BL-20260417-ctrl-sync-gr: applies to controller scratch gr routing; not
  directly in scope here, but any new SPM-load scratch register usage
  inside PE 23 macros must follow the serial-through-one-gr discipline if
  the latency fix introduces one. Note: Milestone F's fix work in magic
  31 must preserve this BL — the `gr[11]`-only serial-through-one-gr
  SPM-load routing added in Plan 2a (commits `efb4517` + `751f2e9`) is
  required; any reshuffle done during Milestone F must not convert back
  to multi-gr parallel loads.
- Plan-2a AC-4 cycle-accounting (retroactively clarified 2026-04-20):
  the correct SPM-load-to-use rule is "consumer's VLIW cycle must be
  >= load's VLIW cycle + 2" where each pair of consecutive magic-body
  lines = one VLIW cycle. This is the user-authoritative convention
  used by AC-7 and AC-11 in this plan. Plan 2a's 2-NOP pattern is
  legal or illegal per chain depending on the load's slot alignment
  within its pair; Milestone F audits each chain individually and
  applies the appropriate fix.

### Validation Workflow

Both validation counts — `mode 1 -t 56 = 15/15` and
`mode 2 -t 56 = 295/295` — are HARD requirements (user-confirmed
during Phase 6 of the planning workflow). Any deviation blocks commit
acceptance; trend-toward-target is not sufficient.

After each magic commit — and, for PE 23 specifically, after each of
the three PE 23 commits (`t2a_impl`, `t2b_impl`, `t2cd_impl`), and
for PE 22 after both `t1_impl` and `t1_fastpath`:

1. `make -j ADDRESS_SANITIZER=0` (clean build required).
2. `python3 scripts/gwfa_check_correctness.py 1 -t 56` — must return
   15/15.
3. `gendp-isa-reviewer` on the changed magic — every finding
   dispositioned in the round summary.
4. Commit with no AI authorship in the message.

At end of plan:

- `python3 scripts/gwfa_check_correctness.py 2 -t 56` — must return
  295/295 (AC-3 hard gate).

--- Original Design Draft Start ---

# GWFA ISA-Like Rewrite Plan 2b: PE Structural Residuals

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
- After EACH magic change: `make -j ADDRESS_SANITIZER=0`, `gwfa_check_correctness.py 1 -t 56`, commit
- After each commit: run `gendp-isa-reviewer` on the changed magic
- Fix any issues before moving to the next magic
- At end of plan: `gwfa_check_correctness.py 2 -t 56` (295/295 required)

---

## Goal Description

Complete remaining structural changes for PE magics 19, 22, and 23.

## Prerequisites

Plan 1 code implemented. Code passes mode 1 -t 56: 15/15.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after each change, mode 2 at end)
- AC-2: gendp-isa-reviewer finds no hazards in each changed magic
- AC-3: All per-magic draft requirements below addressed

## Task Breakdown

### PE 22 (merge)
Draft: "You shouldn't need to check the second buffer. It will always be full. Establish how much left of A tile and B tile. Iterate fast. Handle switch of buffers as special case."

| Task ID | Description | Tag |
|---------|-------------|-----|
| p1 | Restructure so buffer exhaustion triggers a labeled transition (runs only when ai>=a_n or bi>=b_n), NOT checked every iteration. Keep original (ai-ai0)+(bi-bi0) budget formula. | coding |
| p1v | Verify PE 22: mode 1 (test case 2 specifically) + ISA review | coding |

### PE 23 (dedup)
Draft: "keep almost all state in registers (48+)", "use mvds for merging overlapping diags/intvs", "wait a cycle after spm load", "keep one intv and one diag in registers for forbidden checks"

| Task ID | Description | Tag |
|---------|-------------|-----|
| p2a | Reduce M23_SAVE_RESUME: remove n_do/n_io (already in M23_SAVE_OUT), remove de/ie (write-only), keep only pv/pk/dc/ic/dw/iw/clo/chi/state/pdone/nv/nk | coding |
| p2b | Keep current intv (clo,chi) and current diag (pv,pk) as "always live" — no save needed at yield points where they haven't changed | coding |
| p2c | Add SPM latency gap: ensure 1 instruction between SPM load and use in M23_RD and M23_RI macros | coding |
| p2d | Use mvd (double-word move) for merge-adjacent intv output writes where consecutive intvs are written to contiguous SPM locations | coding |
| p2v | Verify PE 23: mode 1 + ISA review | coding |

### PE 19 (FIN0)
Draft: "ample opportunity to use half registers as well as mvd"

| Task ID | Description | Tag |
|---------|-------------|-----|
| p3 | Convert contiguous FIN0 diag/arc loads to mvd. Use half-registers for 16-bit vertex/offset fields. Model after PE 8/13 reference patterns. | coding |
| p3v | Verify PE 19: mode 1 + ISA review | coding |

### Final verification

| Task ID | Description | Tag |
|---------|-------------|-----|
| p_fin | Full verification: mode 2 -t 56 | coding |

## Known Issues from Plan 1

- **PE 22**: 3 failed restructure attempts (infinite loop on case 2). Root cause: buffer-switch + budget-check interaction. The goto version using original budget formula works. Focus on making buffer-switch a labeled transition that only runs when a tile is exhausted.
- **BL-20260413-drain-budget**: PE merge drain must use unified loop, not separate drain paths.

--- Original Design Draft End ---
