# GWFA ISA-Like Rewrite Plan 2c: Global Compliance Audit

## Shared Preamble (duplicated across all active plans)

### Scope
- **Delete**: Controller magics 2, 10, 26 (deprecated) — DONE in Plan 1
- **Exempt (do not touch)**: Controller 1, 3, 4, 5, 6, 17
- **Reference examples (frozen)**: Controller 7, 8, 9, 12, 14, 15; PE 8, 11, 13
- **In-scope (controller)**: 16, 18, 19, 20, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39
- **In-scope (PE)**: 19, 20, 21, 22, 23

### ISA-like rules (all 12, unchanged from draft)
1. Each line = one GenDP ISA operation
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired slots
3. Registers only: `gr[]`, `reg[]`, `s1c[]`, `spm[]`, `mm[]`; no C++ runtime variables carry
   architectural state across ISA lines
4. Gotos with labels instead of runtime `if/else/for/while`; macro-style unrolling such as
   `for (int pe = 0; pe < 4; ++pe)` is allowed
5. Compile-time constants (`constexpr`) allowed
6. SPM: 2-cycle latency. Per the GWFA prompt (user-confirmed in DEC-SPM), pipelined
   back-to-back SPM loads are permitted for this rewrite; the consumer of any loaded value
   must still wait the full 2 cycles (= 4 ISA lines) before reading.
7. MM/S2: `// waitLSQ` comment AND real cycle separation required between load and use;
   between magics, the waitLSQ becomes an explicit ISA instruction
8. S1c: 1-cycle latency (consumer on the next VLIW cycle = at least 2 ISA lines later)
9. mvdq round-robin PE streaming for bulk contiguous data; scalar `mv` only for
   non-contiguous data (graph-lookup-style)
10. No `std::min`/`std::max` on controller (use branch conds); `std::min`/`std::max` OK on PE
11. Helper macros acceptable if ALL live state is in registers/memory (no C++ locals across
    ISA lines)
12. PE compute instructions deferred to a future pass (mark but do not rework)

### Decision Log (carry-over from prior plans + resolved for 2c)
- **DEC-SEAM-MERGE** (from Plan 2a, carry-forward): magic 31 stores per-PE first/last intv to
  s1c[176..191]; magic 32 uses s1c for boundary merge. Preserved in 2c; do not unwind.
- **DEC-SPM-MODEL** (resolved 2c, user-confirmed): the GWFA prompt is authoritative for this
  rewrite. Pipelined back-to-back SPM loads are permitted (as `mvdq_copy` already emits);
  the audit enforces only the 2-cycle consumer separation, not a "one SPM op per cycle"
  bound. The tension with CLAUDE.md is noted and left to a future revision of CLAUDE.md or
  the simulator model; no rework of `mvdq_copy`-shape helpers is required in 2c.
- **DEC-COMMIT** (resolved 2c, user-confirmed): per-magic additive commits, matching the
  draft and Plans 1/2a/2b. No rebase / reset / amend / force-push / cherry-pick-drop /
  `git revert`. On any mode-1 regression, manually undo or patch back the working-tree edit
  before retrying.
- **DEC-1 (stylistic/proxy scope)** (resolved 2c, user-confirmed): stylistic / proxy-rule
  findings on magics that were already `gendp-isa-reviewer`-clean under 2a/2b are included
  in 2c as `fix-preferred`. They land when the fix is local and low-risk; otherwise they
  are recorded as deferred with rationale in the audit matrix.
- **DEC-3 (audit matrix location)** (resolved 2c, user-confirmed): the audit matrix lives
  as a sibling artifact at `plan2c_audit_matrix.md` in the same directory as this plan
  file. All matrix citations in this plan point to that sibling.

### Validation rules
- After EACH per-magic fix: `make -j ADDRESS_SANITIZER=0`; `gwfa_check_correctness.py 1 -t
  56` (must pass 15/15); `gendp-isa-reviewer` on the changed magic(s) (zero unwaived P0/P1);
  then one additive commit per magic (no history rewrite).
- At end of plan: `gwfa_check_correctness.py 2 -t 56` — must be 295/295.

---

## Goal Description

Produce a rule-by-rule compliance audit matrix (`plan2c_audit_matrix.md`) over every
in-scope GWFA magic, triage each finding into `fix-required` / `fix-preferred` /
`waive:<reason>` / `defer:rule12-pe-compute`, then fix every `fix-required` violation (and
low-risk `fix-preferred` items) per magic with build + mode-1 verify +
`gendp-isa-reviewer` + additive commit. The code exits Plan 2c with ISA-lowering-ready
magics: every changed magic passes `gendp-isa-reviewer`, and the full suite passes mode 2
with 295/295.

## Prerequisites

Plans 1, 2a, 2b complete. Code passes `gwfa_check_correctness.py 2 -t 56` with 295/295 at
the head of the `gwfaIsaLikeAll` branch.

## Acceptance Criteria

Each AC uses TDD-style positive/negative checks. Positive tests should pass, negative
tests should fail (i.e., correctly reject the bad code), when the criterion holds.

- AC-1: Correctness is preserved end-to-end.
  - Positive: mode 1 `-t 56` passes (15/15) after every per-magic fix, before the commit.
  - Positive: mode 2 `-t 56` passes 295/295 at end of plan.
  - Negative: any mode 1 regression after a change blocks the commit (manually undo or
    patch back the working-tree edit before retrying; no `git revert` / rebase / reset).

- AC-2: A rule-by-rule compliance audit matrix in `plan2c_audit_matrix.md` covers all 12
  rules × all 23 in-scope magics (18 controller + 5 PE = 276 cells).
  - Cell vocabulary (first-class): `pass` | `fix-required` | `fix-preferred` |
    `waive:<reason>` | `defer:rule12-pe-compute` (reserved specifically for rule 12 cells
    on PE magics).
  - Positive: every (magic, rule) cell has one of the five statuses; `fix-*` and
    `waive:*` cells cite the changed-magic symbol and a short code reference (magic-id +
    subroutine name, not a raw line number, to survive in-place edits).
  - Negative: a cell marked `pass` that is later shown to have an open violation; OR an
    uncategorized cell; OR a `defer:` tag used for any rule other than rule 12.

- AC-3: No `std::min` / `std::max` inside any in-scope controller magic (rule 10).
  - Positive: grep of in-scope controller magic bodies for `std::min`/`std::max` returns
    zero matches.
  - Negative: any controller magic body still contains those tokens.

- AC-4: No illegal indirect-memory data reads in executable logic (rule 3/5/11
  refinement).
  - Positive: any `mm[s1c[X]]` occurrence is the destination/source of an approved
    bulk-transfer helper (e.g. `mvdq_copy(&mm[s1c[204+pe]], …)`); every other use stages
    the inner read into a register first, then dereferences MM.
  - Negative: any executable RHS that reads `mm[s1c[X]]` or `mm[gr[s1c[X]]]` as a nested
    data read in a single expression.

- AC-5: No architectural state carried in C++ locals across ISA lines (rule 3/11).
  - Positive: any C++ local inside a magic body either (a) is consumed on the same ISA
    line it is assigned, or (b) is a `constexpr` / loop-index / PE macro index that the
    reviewer accepts as compile-time. All cross-line live values sit in `gr`, `reg`,
    `s1c`, `spm`, or `mm`.
  - Negative: any plain C++ local assigned on one ISA line and read on a later line
    inside the same magic.

- AC-6: Every MM/S2 load has a `// waitLSQ` annotation AND the required cycle separation
  before its first consumer (rule 7).
  - Positive: every `… = mm[…]` or S2 load inside an in-scope magic is followed by a
    `// waitLSQ` comment and at least one cycle of unrelated instructions (= at least 2
    ISA lines) before the first reader of the load's destination register.
  - Negative: annotation present but consumer reads the load's target on the immediately
    next ISA line; OR consumer is correctly delayed but the annotation is missing (the
    ISA generator consumes `// waitLSQ` to emit the LSQ-wait ISA op — missing annotation
    ≡ missing ISA op).

- AC-7: SPM and S1c loads respect their documented latencies (rules 6, 8).
  - Positive: for every `… = spm[…]`, the first consumer of that destination is at least
    2 VLIW cycles = 4 ISA lines after the load line; for every `… = s1c[…]`, the first
    consumer is at least 1 VLIW cycle = 2 ISA lines after the load.
  - Negative: any consumer reads a SPM-loaded register on the same or immediately next
    VLIW cycle (< 4 ISA lines away); any S1c consumer reads on the same cycle (< 2 ISA
    lines).

- AC-8: Paired VLIW slots in every changed magic are RAW-hazard free (rule 2).
  - Positive: for each "pair of lines = one cycle" block, the second slot does not read
    a register written by the first slot.
  - Negative: any paired-slot RAW where slot 1 reads slot 0's destination.

- AC-9: Control flow inside in-scope magic bodies uses labels+gotos or approved macro
  unrolling only (rule 4).
  - Positive: every `if`/`for`/`while` inside an in-scope magic body is one of: a
    `for (int pe = 0; pe < 4; …)` PE unroll, a `constexpr` switch, a macro-expansion
    loop accepted as "fixed at compile time" by `gendp-isa-reviewer`, or a
    comment-annotated label-driven conditional branch.
  - Negative: any surviving runtime `for`/`while` or multi-arm `if/else` that selects
    data-dependent control flow (must be rewritten as label+conditional-branch).

- AC-10: Bulk contiguous transfers use mvdq (round-robin over PEs) or mvd; scalar `mv`
  only where data is non-contiguous (rule 9).
  - Positive: every contiguous-stride bulk move in an in-scope magic uses `mvdq_copy`
    or a `mvd`-shaped helper; each surviving scalar loop is annotated with a
    non-contiguity comment (e.g. "// arc stride 3 — scalar").
  - Negative: a scalar `for (int i = …) { spm[…] = mm[…+i]; }` over contiguous data
    without a documented reason.

- AC-11: PE compute (rule 12) is explicitly deferred, not reworked in 2c.
  - Positive: audit matrix cells for rule 12 on PE magics are tagged
    `defer:rule12-pe-compute`.
  - Negative: a gratuitous PE compute rewrite lands in 2c; OR rule 12 tagged `defer:`
    on a controller magic (controllers never run PE compute).

- AC-12: `gendp-isa-reviewer` returns no unwaived P0/P1 findings on any magic changed
  by 2c.
  - Positive: the reviewer report on each changed magic lists zero P0/P1 findings, or
    every listed P0/P1 is explicitly waived in the audit matrix with reason. P2
    findings are recorded in the matrix (as either `fix-preferred` or `waive:<reason>`)
    so the reviewer trail is complete.
  - Negative: any changed magic ships with an unwaived P0/P1 reviewer finding, or a P2
    finding that is neither fixed nor recorded in the matrix.

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)
Full 12-rule × 23-magic compliance matrix is authored in `plan2c_audit_matrix.md` (276
cells). Every cell is classified; every `fix-required` is implemented per magic with its
own build + mode-1 verify + reviewer + commit. `fix-preferred` items are also landed
when they are low-risk per DEC-1. Final mode 2 clean (295/295) and audit ledger closed.

### Lower Bound (Minimum Acceptable Scope)
Audit matrix in `plan2c_audit_matrix.md` covers every rule × in-scope magic. Every
`fix-required` (semantic or latency bug, missing `// waitLSQ` annotation, nested
indirect MM read, controller `std::min`/`max`, paired-slot RAW, runtime control flow) is
landed. `fix-preferred` items that are not low-risk-local are recorded as deferred with
rationale and may ship in a follow-on plan. Final mode 2 clean (295/295).

### Allowed Choices
- **Can use**: Codex `analyze` runs for matrix authoring; per-magic commit granularity
  (or grouped commits when magics are tightly coupled, e.g. 31 ↔ 32 seam metadata);
  `gendp-isa-reviewer` P2 suppressions with recorded rationale; macro-style PE-unroll
  loops; `constexpr`; half-registers.
- **Cannot use**: `std::min` / `std::max` on controller; nested indirect memory reads in
  executable logic; runtime `if/else/for/while` inside magic bodies except approved
  macro forms; helpers that hide live architectural state in C++ locals; `git` commands
  that modify history (rebase/reset/amend/force-push/cherry-pick-drop/`git revert`);
  skipping `gendp-isa-reviewer` on a changed magic.

> **Note on Deterministic Designs**: The 12 rules and the reference-example magics
> (controller 7/8/9/12/14/15, PE 8/11/13) anchor a highly deterministic rewrite target.
> Upper and lower bounds differ only in whether `fix-preferred` items land now or defer;
> the `fix-required` set and matrix coverage are fixed.

## Feasibility Hints and Suggestions

> **Note**: Conceptual suggestions, not prescriptive requirements.

### Conceptual Approach

1. **Authoring pass** (tasks c1, c2): Split Codex runs — one for controllers, one for
   PEs — each populating cells in `plan2c_audit_matrix.md`. Use magic-id +
   subroutine-name citations (e.g. "magic 37 binary-search inner loop") rather than raw
   line numbers, so the matrix stays valid as fixes shuffle lines. PE rule-12 cells are
   tagged `defer:rule12-pe-compute`.

2. **Triage pass** (task c_triage): Claude classifies each `fix` cell into
   `fix-required` vs `fix-preferred`. Concrete classification examples:
   - **fix-required**: runtime `while` in a hot path (magic 37 binary search), missing
     `// waitLSQ` on an MM load the ISA generator will consume, paired-slot RAW hazard,
     nested `mm[s1c[X]]` executable read, controller `std::min`/`max`.
   - **fix-preferred**: an `if (cond)` that could be a `beq`+label but sits inside a
     macro-expansion region the reviewer already accepts; a scalar `mv` on data that
     could be mvdq but has stride-3 source layout.
   - **waive**: a pattern that mirrors a reference-example magic's idiom; a rule cell
     that does not apply (e.g. rule 10 on a magic that has no controller `std::min`).
   User signs off on the classification before coding starts.

3. **Controller fix pass** (task c3): Iterate in-scope controller magics, one magic per
   commit:
   - Apply fix-required (and low-risk fix-preferred) items.
   - `make -j ADDRESS_SANITIZER=0`.
   - `gwfa_check_correctness.py 1 -t 56` — must pass 15/15.
   - `gendp-isa-reviewer` on the changed magic — must return zero unwaived P0/P1.
   - One additive commit per magic (no history rewrite). On regression, manually undo
     the working-tree change and retry.

4. **PE fix pass** (task c4): Same cadence over PE 19–23.

5. **Final verification** (task c_fin): `gwfa_check_correctness.py 2 -t 56` = 295/295;
   close the audit ledger by stamping each matrix cell with its final outcome
   (`done` / `deferred:<reason>` / `waived`).

### Relevant References
- `pe_array.cpp` — controller magic bodies (`if (magic_id == N)` at approximate starts:
  16 @ 2285, 18 @ 2111, 19 @ 2378, 20 @ 2103, 24 @ 2424, 25 @ 2482, 28 @ 2711, 29 @ 3006,
  30 @ 3135, 31 @ 3183, 32 @ 3317, 33 @ 2883, 34 @ 2325, 35 @ 2932, 36 @ 2968, 37 @ 2522,
  38 @ 2630, 39 @ 2694 — starts will drift as fixes land).
- `pe.cpp` — PE magic bodies (19 @ 1851, 20 @ 1380, 21 @ 1410, 22 @ 1456, 23 @ 1599).
- `isaLikeAllGwfaPlan2a.md`, `isaLikeAllGwfaPlan2b.md` — prior structural work and
  inherited invariants (seam metadata layout at s1c[176..191], PE 22 labeled
  transitions, PE 23 save-scope reduction under DEC-2, SPM-latency NOP placements in
  magic 20/31/32).
- `isaLikeAllGwfaPrompt.md` — the governing prompt defining the 12 rules.
- `CLAUDE.md` — canonical SPM latency and VLIW hazard rules; also the
  history-modification prohibition that shapes the commit workflow.
- `docs.md` — full ISA manual.
- `plan2c_audit_matrix.md` — sibling artifact (created by task c1/c2) holding the
  12-rule × 23-magic matrix.

## Dependencies and Sequence

### Milestones
1. **Milestone A: Audit matrix authored**
   - Phase A1: Controller audit (Codex, task c1) — 18 magics × 12 rules = 216 cells
     into `plan2c_audit_matrix.md`.
   - Phase A2: PE audit (Codex, task c2) — 5 magics × 12 rules = 60 cells; rule-12 PE
     cells tagged `defer:rule12-pe-compute`.
   - Phase A3: Ledger triage (Claude + user sign-off, task c_triage) — classify each
     `fix` cell as `fix-required` vs `fix-preferred`; waive with reason where
     applicable.

2. **Milestone B: Controller fixes landed**
   - Steps B1..Bk (one per controller magic): apply fix-required (and low-risk
     fix-preferred) items; build; mode 1 (15/15); `gendp-isa-reviewer` (zero unwaived
     P0/P1); commit.
   - Step Bv: controller roll-up — re-run mode 1 across all controller magics.

3. **Milestone C: PE fixes landed**
   - Steps C1..Cm (one per PE magic): apply fix-required (and low-risk fix-preferred)
     items; build; mode 1 (15/15); `gendp-isa-reviewer` (zero unwaived P0/P1); commit.
   - Step Cv: PE roll-up — mode 1 clean across all PE magics.

4. **Milestone D: Final verification**
   - Step D1: `gwfa_check_correctness.py 2 -t 56` — must be 295/295.
   - Step D2: close audit ledger; any deferred `fix-preferred` items are explicitly
     recorded in the matrix with rationale for a follow-on plan.

Dependencies: A → B → C → D. Within B and C, per-magic commits are independent unless
two magics share seam metadata layout (e.g., controller 31 ↔ 32), in which case the
dependent pair lands in one commit.

## Task Breakdown

Each `coding` row's build + mode-1 + reviewer + commit rolls up into a single per-magic
commit, matching the validation-rules cadence. The `analyze` tasks are one-shot Codex
audits.

| Task ID  | Description                                                                                                                               | Target AC          | Tag     | Depends On |
|----------|-------------------------------------------------------------------------------------------------------------------------------------------|--------------------|---------|------------|
| c1       | Codex audit of 18 in-scope controller magics against all 12 ISA-like rules; populate 216 cells in `plan2c_audit_matrix.md`                 | AC-2               | analyze | -          |
| c2       | Codex audit of 5 in-scope PE magics against all 12 ISA-like rules; populate 60 cells in the matrix; tag rule-12 PE cells as defer         | AC-2, AC-11        | analyze | -          |
| c_triage | Claude walk of matrix + user sign-off: classify each `fix` cell as fix-required / fix-preferred; resolve any `waive` needing user approval | AC-2               | analyze | c1, c2     |
| c3       | Per-magic controller fix pass: apply fixes, build, mode 1 (15/15), `gendp-isa-reviewer`, commit — one additive commit per magic           | AC-3..AC-10, AC-12 | coding  | c_triage   |
| c4       | Per-magic PE fix pass: apply fixes, build, mode 1 (15/15), `gendp-isa-reviewer`, commit — one additive commit per magic                   | AC-3..AC-10, AC-12 | coding  | c_triage   |
| c_fin    | Final verification: `gwfa_check_correctness.py 2 -t 56` = 295/295; close audit ledger; record any deferred fix-preferred items            | AC-1               | coding  | c3, c4     |

## Claude-Codex Deliberation

### Agreements
- An explicit 12-rule × in-scope-magic audit matrix is the right artifact.
- AC-4 must explicitly exempt `mvdq_copy` address expressions (the nested-read violation
  is about data reads in executable logic, not address-expression reuse in bulk
  helpers).
- AC-5 targets live state in C++ locals, not a syntactic "no helper returns" proxy.
- Rules 2 (RAW), 4 (gotos), 6/7/8 (MM/SPM/S1c latencies), 11 (helpers), 12 (PE compute
  deferral) each deserve their own AC rather than being lumped.
- Reviewer cadence is "immediately after each magic change, before commit," not batched;
  task breakdown was folded so c3 and c4 each include the per-magic reviewer run (no
  separate c3v / c4v stage).
- Audit matrix statuses are first-class: `pass` / `fix-required` / `fix-preferred` /
  `waive:<reason>` / `defer:rule12-pe-compute`; no other status values.
- Matrix citations use magic-id + subroutine/symbol names (not raw line numbers) so they
  survive in-place edits.

### Resolved Disagreements
- **AC-7 unit ambiguity**: rewritten to use unambiguous units — SPM consumer at least 2
  VLIW cycles = 4 ISA lines after the load; S1c consumer at least 1 VLIW cycle = 2 ISA
  lines after the load.
- **AC-2 / AC-11 vocabulary mismatch**: matrix now supports `defer:rule12-pe-compute`
  as a first-class status; rule 12 is the only rule where `defer:` is legal.
- **AC-4 exemption wording**: explicit exemption for `mvdq_copy(&mm[s1c[X]], …)`
  bulk-helper address expressions folded into the AC itself; Codex concurred.
- **Annotation-only findings classification**: decided as `fix-required` — the ISA
  generator consumes `// waitLSQ` comments to emit the LSQ-wait ISA op, so a missing
  annotation ≡ a missing ISA instruction, not merely a documentation gap.
- **Re-scan of already-reviewed magics**: decided as "re-scan all in-scope magics" for
  completeness; Codex effort cost is acceptable given Plan 2c's scope.
- **Reviewer cadence split**: c3v / c4v removed; per-magic reviewer run is part of
  c3 / c4.
- **DEC-1 scope** (user-confirmed): stylistic / proxy-rule findings on already-reviewed
  magics are included as `fix-preferred`; land when low-risk, defer otherwise. Claude's
  position prevailed over Codex's "defer all stylistic" recommendation.
- **DEC-3 matrix location** (user-confirmed): matrix lives as sibling
  `plan2c_audit_matrix.md`. Claude's position prevailed.
- **DEC-SPM model** (user-confirmed): GWFA prompt is authoritative for this rewrite;
  pipelined SPM loads permitted; audit enforces only the 2-cycle consumer separation.
  Claude's position prevailed over Codex's "CLAUDE.md-authoritative" recommendation.
- **DEC-COMMIT workflow** (user-confirmed): per-magic additive commits match draft and
  Plans 1/2a/2b; no history rewrite. Claude's position prevailed over Codex's "remove
  all git-state-changing actions" recommendation.

### Convergence Status
- Final Status: `converged`. Two convergence rounds executed. Round 1 produced v2
  (structural rewrite, AC split, rule-vocabulary normalization). Round 2 flagged
  DEC-SPM and DEC-COMMIT as genuine opposite opinions vs the user's own governing
  prompt; those were escalated to the user. All four pending decisions (DEC-1, DEC-3,
  DEC-SPM, DEC-COMMIT) were resolved in favor of Claude's recommended positions during
  Phase 6 AskUserQuestion. No pending decisions remain.

## Pending User Decisions

_(None — all DEC-* items are recorded in the Decision Log above with user-confirmed
resolutions.)_

## Implementation Notes

### Code Style Requirements
- Implementation code and comments must NOT contain plan-specific terminology such as
  "AC-", "Milestone", "Step", "Phase", or similar workflow markers.
- These terms are for this plan document only, not the resulting codebase.
- Use descriptive, domain-appropriate naming in code; preserve the `// waitLSQ` and
  SPM-NOP annotation conventions already established in 2a/2b.

--- Original Design Draft Start ---

# GWFA ISA-Like Rewrite Plan 2c: Global Compliance Audit

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
- After EACH fix: `make -j ADDRESS_SANITIZER=0`, `gwfa_check_correctness.py 1 -t 56`, commit
- After each commit: run `gendp-isa-reviewer` on changed magics
- At end of plan: `gwfa_check_correctness.py 2 -t 56` (295/295 required)

---

## Goal Description

Comprehensive compliance audit across ALL in-scope magics. Find and fix every remaining violation of the ISA-like rules and draft constraints before ISA lowering begins.

## Prerequisites

Plans 1, 2a, 2b complete. All structural rewrites done. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after fixes, mode 2 at end)
- AC-2: No std::min/max in any in-scope controller magic
- AC-3: No scalar bulk-copy loops where mvdq is feasible
- AC-4: No nested memory expressions (mm[s1c[X]])
- AC-5: No helper functions with return values
- AC-6: No missing waitLSQ annotations for MM/S2 loads
- AC-7: No register-clobber risks across magic boundaries

## Task Breakdown

| Task ID | Description | Tag |
|---------|-------------|-----|
| c1 | Codex audit: scan ALL in-scope controller magics (16-39) for remaining std::min/max, scalar bulk-copy loops, helper-return control flow, nested mm[s1c[X]], missing waitLSQ, register-clobber risks | analyze |
| c2 | Codex audit: scan ALL in-scope PE magics (19-23) for same issues | analyze |
| c3 | Fix all controller issues found in c1 | coding |
| c3v | Verify controller fixes: mode 1 + ISA review on changed magics | coding |
| c4 | Fix all PE issues found in c2 | coding |
| c4v | Verify PE fixes: mode 1 + ISA review on changed magics | coding |
| c_fin | Full verification: mode 2 -t 56 | coding |

--- Original Design Draft End ---
