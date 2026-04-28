# GWFA ISA-Like Rewrite Plan 1 — Review Gate (Structural Changes)

## Goal Description

Close out Plan 1 (structural changes to GWFA magic instructions in `pe_array.cpp` and
`pe.cpp`) with an evidence-backed review verdict for every tracked item — both "Completed
Tasks" and "Known Issues Deferred to Plan 2". Replace the soft "MOSTLY MET" status in the
original draft with a four-valued outcome set per item: `MET`, `APPROVED_DEVIATION`,
`DEFERRED_BY_DECISION`, `NOT_MET`. Emit a document-level verdict (`ACCEPTED`,
`ACCEPTED_WITH_DEVIATIONS`, or `REJECTED`) so Plans 2a/2b/2c can build on a stable base.
No new implementation is in scope; review findings become new items for Plan 2+.

Document-level closure semantics:
- Plan 1 is "review-closed" when every tracked item is adjudicated with the evidence
  required by AC-1..AC-10 below. "Review-closed" does NOT mean every item is `MET`; it
  means every item is adjudicated.
- `ACCEPTED`: zero `NOT_MET`, zero `APPROVED_DEVIATION`, zero `DEFERRED_BY_DECISION`.
- `ACCEPTED_WITH_DEVIATIONS`: zero `NOT_MET`; at least one `APPROVED_DEVIATION` or
  `DEFERRED_BY_DECISION`.
- `REJECTED`: any `NOT_MET`.
- Per user decision DEC-1, `mode 2 -t 56` PASS is a hard closure blocker: no verdict can
  be emitted without mode 2 evidence attached.

## Acceptance Criteria

Following TDD philosophy, each criterion includes positive and negative tests for
deterministic verification.

- AC-1: Binary outcome per tracked item — every bullet in the draft's "Completed Tasks"
  AND "Known Issues Deferred to Plan 2" sections ends with exactly one of:
  `MET`, `APPROVED_DEVIATION`, `DEFERRED_BY_DECISION`, `NOT_MET`.
  - Positive Tests (expected to PASS):
    - `grep -E "MOSTLY|PARTIALLY|MET\*" isaLikeAllGwfaPlan1H.md` returns zero hits in the
      adjudicated sections.
    - Every tracked bullet matches one of the four outcome labels.
  - Negative Tests (expected to FAIL):
    - A bullet left as `MET (residual items deferred)` or similar soft phrasing is
      rejected during review.
    - A tracked bullet without any outcome label is rejected.

- AC-2: Evidence traceability — each Completed Task row in the review matrix lists the
  relevant magic(s) or cleanup/scope item, affected file(s), at least one commit SHA on
  the current branch, prior-static-scan evidence where available, and a reviewer-confirmed
  evidence note.
  - Positive Tests:
    - The row for "ISA-lower controller 16/19/39" cites commit `398821f`, lists
      `pe_array.cpp`, includes a reviewer sentence, and tags the static-scan column.
    - Cleanup rows (e.g., `SORT_BIN_REG` rename) cite `d719a69` and list the affected
      files (`sys_def.h`, `pe_array.cpp`, `pe.cpp`).
  - Negative Tests:
    - A completion claim without any commit SHA is rejected.
    - A row missing the reviewer-confirmed note fails review.

- AC-3: Cleanup verified — repository-wide grep demonstrates:
  1. No references to controller magics 2/10/26 on the controller dispatch path.
  2. No occurrences of the identifier `SORT_BIN_REG` remain.
  3. `SORT_BIN_REGION_SIZE` is intact (no "REGION" substring corruption).
  4. Barrier insert exists at 4 insertion sites (8 barrier calls total) between magic 7
     and magic 8 in `scripts/gwfa_instruction_generator.py`.
  5. Dead helper `merge_split_and_load` is fully removed.
  - Positive Tests:
    - `grep -n SORT_BIN_REG` (exact) returns zero hits.
    - `grep -n SORT_BIN_REGION_SIZE` returns intact hits in `sys_def.h` and `pe_array.cpp`.
    - `grep -n merge_split_and_load` returns zero hits.
    - Barrier count between magic 7 and magic 8 in the instruction generator matches
      4 sites / 8 calls.
  - Negative Tests:
    - A live stale reference to magic 2/10/26 or to `SORT_BIN_REG` fails the cleanup AC.
    - A missing or misplaced barrier insert fails the cleanup AC.

- AC-4: Scope partition explicit — every Completed Task row carries exactly one of the
  following scope tags:
  `Plan 1 structural` / `Plan 1 structural + hybrid ISA-lower` / `Deferred to Plan 2x`.
  - Positive Tests:
    - The row for "Magic 19: flip loop + locals → gr[7-10]" is tagged
      `Plan 1 structural + hybrid ISA-lower` (because commit `398821f` is ISA-lowering).
    - The row for "Delete controller magics 2/10/26" is tagged `Plan 1 structural`.
  - Negative Tests:
    - A row with no tag is rejected.
    - A row tagged with a string other than the three allowed values is rejected.

- AC-5: Targeted edge-case review notes — controller magics 20, 28, 32, 36, 38 and PE
  magics 22, 23 each carry at least one explicit named-hazard reviewer note (seam
  boundary, final-tile peel, stride-3 arc fallback, binary-search convergence, buffer-
  switch transition, PE 23 save/resume scope) in addition to any aggregate mode-1 signal.
  - Positive Tests:
    - The controller 32 row includes a reviewer note naming the diag+intv gather
      dependency and the PE-seam-only fixup.
    - The PE 22 row includes a reviewer note naming the buffer-switch transition.
  - Negative Tests:
    - For any of these magics, a review note that cites only "mode 1 passes" and no
      named hazard fails the AC.

- AC-6: Approved Deviations list — a dedicated section lists every deviation from
  original draft intent with current behavior, rationale, and downstream owner. Rows are
  mutually exclusive with Deferred items (AC-9). Default classifications (unless the user
  overrides in Pending User Decisions):
  - Controller 20 stride-3 arcs (pure mvdq infeasible; partial conversion accepted):
    `APPROVED_DEVIATION`, downstream owner Plan 2a.
  - Controller 32 first/last intv via local variable (s1c relocation not done):
    `APPROVED_DEVIATION`, downstream owner Plan 2b (confirmed by user in DEC-2).
  - PE 22 buffer-switch partial hoist (three hoist attempts failed; goto-based structure
    in place but some checks remain in hot loop): `APPROVED_DEVIATION`, downstream
    owner Plan 2c.
  - Positive Tests:
    - Each listed deviation has all four fields (current / rationale / owner / current
      behavior) present.
    - No deviation appears twice or also appears in the Deferred list.
  - Negative Tests:
    - A known deviation implied-met without a record in this list fails AC-6.
    - A row that also appears under AC-9 fails the mutual-exclusivity check.

- AC-7: Mandatory cross-magic ABI/hazard audit — `gendp-isa-reviewer` agent is run on
  every hybrid-lowered magic (controllers 16/19/39; PEs 20/21/22/23) because those commits
  already contain ISA-lowering edits. If the agent is unavailable, a manual ABI/hazard
  checklist covering (a) gr-clobber boundaries, (b) VLIW pair RAW/WAW, (c) SPM 2-cycle
  latency, (d) MM waitLSQ placement, (e) destination restrictions is performed in its
  place. The audit is not optional.
  - Positive Tests:
    - An agent (or manual checklist) summary is attached in the review matrix for
      controllers 16, 19, 39 and PEs 20, 21, 22, 23.
    - The `gr-clobber` BitLesson is cross-referenced from the relevant magic rows.
  - Negative Tests:
    - A hybrid-lowered magic reviewed only by local correctness (no agent/checklist)
      fails AC-7.
    - A review summary that omits gr-clobber checks for magics that touch gr[] across
      magic boundaries fails AC-7.

- AC-8: Verification boundary declared — per user decision DEC-1, `mode 2 -t 56` IS a
  Plan 1 closure blocker. Mode 2 results (test count passed / failed) are attached to
  the review document before any verdict is emitted. A one-sentence declaration of the
  boundary is present.
  - Positive Tests:
    - The review document contains the sentence "Mode 2 -t 56 is a Plan 1 closure
      blocker per DEC-1" (or equivalent) and attaches the mode 2 result.
    - No document-level verdict is emitted while mode 2 evidence is absent.
  - Negative Tests:
    - A verdict emitted without mode 2 evidence attached fails AC-8.
    - A verification-boundary statement that is implicit or missing fails AC-8.

- AC-9: Deferred items — each bullet in "Known Issues Deferred to Plan 2" is converted
  into a triple: `CURRENT` (what the code does now) / `GAP` (why it is insufficient) /
  `OWNER` (Plan 2a/2b/2c or a named later plan). These items receive the AC-1 outcome
  `DEFERRED_BY_DECISION` and never overlap with Approved Deviations (AC-6).
  - Positive Tests:
    - The "PE 19 half-registers and mvd not done" bullet becomes a 3-part triple with
      owner Plan 2a (or the draft-referenced plan).
    - The "Controller 31 autoincrement cursors not implemented" bullet becomes a 3-part
      triple with explicit owner plan.
  - Negative Tests:
    - A deferred bullet left as a single vague phrase fails AC-9.
    - A bullet that appears in both AC-6 and AC-9 fails the mutual-exclusivity check.

- AC-10: BitLessons cross-referenced — each lesson discovered in the draft (the four
  `BL-*` entries AND the `SORT_BIN_REGION_SIZE corruption` lesson) is mapped to the
  magic(s) or code area it guards AND to at least one AC it supports.
  - Positive Tests:
    - `BL-20260416-m32-gather-dep` maps to controller 32 and supports AC-5 (edge-case
      review for magic 32).
    - `SORT_BIN_REGION_SIZE corruption` maps to the rename-cleanup row and supports
      AC-3 (cleanup verification).
  - Negative Tests:
    - An orphan lesson with no "guards" or "supports" entry fails AC-10.

## Path Boundaries

Path boundaries define the acceptable range of review rigor and choices.

### Upper Bound (Maximum Acceptable Scope)
The reviewed plan covers every Completed Task and Known Issue item with: AC-1 binary
outcomes; AC-2 evidence matrix including prior-static-scan + reviewer-confirmed columns;
AC-3 cleanup greps with attached output; AC-4 scope tag per row; AC-5 edge-case notes
for controllers 20/28/32/36/38 and PEs 22/23; AC-6 Approved Deviations with rationale
and owner; AC-7 full `gendp-isa-reviewer` reports on all hybrid-lowered magics; AC-8
verification boundary sentence plus mode 2 result (pass required per DEC-1); AC-9
deferral triples; AC-10 BitLesson cross-refs. Findings become new Plan 2+ items, never
implementation changes inside this plan.

### Lower Bound (Minimum Acceptable Scope)
Every tracked item (Completed + Deferred) receives an AC-1 outcome label; AC-2 evidence
lines (commit + files + ≥1 reviewer sentence) for every Completed row; AC-3 cleanup greps
executed and attached; AC-4 scope tag on every row; AC-5 at least one short named-hazard
note on each of controllers 20/28/32/36/38 and PEs 22/23; AC-6 Approved Deviations for
at minimum controller 20 stride-3, controller 32 seam, PE 22 partial hoist; AC-7 audit
(agent OR manual checklist) for every hybrid-lowered magic; AC-8 verification-boundary
sentence present and mode 2 result attached (mode 2 PASS required per DEC-1); AC-9
deferral triples for every deferred bullet; AC-10 mapping for every lesson. There is no
escape hatch that skips any of AC-1..AC-10; rigor chosen above the lower bound is the
reviewer's option.

### Allowed Choices
- Can use: `gendp-isa-reviewer` agent; Codex `analyze` pass via `/humanize:ask-codex`;
  repository-wide grep; `git log` / `git blame` on the current branch; existing mode 1
  results; a fresh `mode 2 -t 56` run (required by DEC-1); commit-message cross-refs.
- Can use: documentation-only edits to `isaLikeAllGwfaPlan1H.md` (the plan file) — per
  DEC-3 the annotations live in this file in-place.
- Cannot use: any implementation changes to `pe_array.cpp`, `pe.cpp`, or
  `scripts/gwfa_instruction_generator.py` within this plan's scope. All new code belongs
  in Plan 2+.
- Cannot use: silent upgrade of a claim to `MET` without an AC-2 evidence line;
  reclassification of an `APPROVED_DEVIATION` as `MET`; or a verdict emitted without the
  mode 2 result attached.

> Note on Deterministic Designs: The scope of items to be reviewed is fully determined by
> the draft's Completed Tasks and Known Issues lists; the reviewer does not choose which
> items to cover. Reviewer discretion applies only to the rigor level within the
> AC-specified bounds.

## Feasibility Hints and Suggestions

> Note: This section is for reference and understanding only. These are conceptual
> suggestions, not prescriptive requirements.

### Conceptual Approach

Build a single evidence matrix as a markdown table in the annotated plan, with columns:
`claim | magic(s) or item | files | commits | prior-static-scan | reviewer note | AC-1
outcome | scope tag`. Populate one row per Completed Task bullet. Deferred items live in
a separate table with columns: `item | current | gap | owner-plan | AC-1 outcome
(DEFERRED_BY_DECISION)`. Approved Deviations live in a third table: `deviation | current
behavior | rationale | downstream owner`. Cleanup greps (AC-3) feed the static-scan
column and the cleanup block. The ISA audit (AC-7) attaches per-magic summaries to the
hybrid rows. Edge-case reviewer notes (AC-5) attach to the named magics. BitLesson
mapping (AC-10) appears in a short cross-ref block. Finally the document-level verdict is
emitted once every outcome is filled and the mode 2 result is attached (DEC-1).

### Relevant References

- `pe_array.cpp` — controller magic implementations (dispatcher around the top of the
  magic switch; individual magics at distinct ranges).
- `pe.cpp` — PE magic implementations (PE 20 near `1401`, PE 22 near `1448–1480`, PE 19
  near `1704+`).
- `scripts/gwfa_instruction_generator.py` — barrier insertion sites between magic 7 and
  magic 8 (4 sites at roughly lines `203–238`).
- `sys_def.h` — `SORT_BIN_REGION_SIZE` constant (near line `214`).
- `isaLikeAllGwfaPlan2a.md`, `isaLikeAllGwfaPlan2b.md`, `isaLikeAllGwfaPlan2c.md` — named
  owner plans for Deferred and Approved-Deviation downstream items.
- `docs.md` — ISA rules (VLIW slots, RAW/WAW, SPM 2-cycle latency, MM waitLSQ,
  destination restrictions) used by the AC-7 manual checklist.
- `scripts/wfa_check_correctness.py` — verification runner family (GWFA uses the analogous
  `gwfa_check_correctness.py` with `-t 56` for mode 2).

### Evidence-Matrix Sketch

| claim | item | files | commit(s) | static scan | reviewer note | outcome | scope tag |
|-------|------|-------|-----------|-------------|---------------|---------|-----------|
| Delete controller magics 2/10/26 | cleanup | pe_array.cpp, instr gen | d719a69 | confirmed absent from dispatcher | <note> | MET | Plan 1 structural |
| Rename SORT_BIN_REG → SORT_BIN_SPM | cleanup | sys_def.h, pe_array.cpp, pe.cpp | d719a69 | grep clean; REGION_SIZE intact | <note> | MET | Plan 1 structural |
| Magic 19: flip loop + locals → gr[7-10] | ctrl 19 | pe_array.cpp | a28e747, 398821f | bins outer / PEs inner | agent-reviewed | MET | Plan 1 structural + hybrid ISA-lower |
| Magic 32 bulk mvdq + local intv seam | ctrl 32 | pe_array.cpp | ee665b6, e202b4e, af3b08f | local var used instead of s1c | edge-case note | APPROVED_DEVIATION | Plan 1 structural |
| PE 22 goto restructure | pe 22 | pe.cpp | 7ab721e | partial hoist only | edge-case note | APPROVED_DEVIATION | Plan 1 structural |
| ... | ... | ... | ... | ... | ... | ... | ... |

## Dependencies and Sequence

### Milestones

1. Cleanup Grep Checks (AC-3): run all grep commands and capture output.
2. Evidence Matrix Build (AC-1, AC-2): fill row schema for every Completed Task bullet.
3. Scope Tagging (AC-4): apply one of the three tags per row; flag hybrid ISA-lower
   commits (e.g., `398821f`).
4. Hybrid ISA Audit (AC-7): `gendp-isa-reviewer` (or manual checklist fallback) on
   controllers 16/19/39 and PEs 20/21/22/23; attach summaries; cross-reference
   `gr-clobber` BitLesson.
5. Edge-Case Review Notes (AC-5): add one named-hazard note per magic in the
   high-risk list.
6. Approved Deviations + Deferred Triples (AC-6, AC-9): finalize both tables with
   mutual exclusivity.
7. BitLesson Mapping (AC-10): map every lesson (four `BL-*` + `SORT_BIN_REGION_SIZE
   corruption`) to magic(s) and to supporting AC(s).
8. Verification Boundary + Closure (AC-8): run `mode 2 -t 56` per DEC-1, attach the
   result, finalize outcomes, emit document-level verdict.

Dependencies:
- Milestone 1 is independent.
- Milestone 2 depends on Milestone 1 (static-scan column needs grep output).
- Milestone 3 depends on Milestone 2.
- Milestones 4, 5, 6, 7 run in parallel after Milestone 3.
- Milestone 8 depends on Milestones 2–7.

## Task Breakdown

Each task includes exactly one routing tag:
- `coding`: implemented by Claude
- `analyze`: executed via Codex (`/humanize:ask-codex`)

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| t1 | Run AC-3 grep checks (magics 2/10/26, SORT_BIN_REG, SORT_BIN_REGION_SIZE, merge_split_and_load, barrier 7→8 counts); attach output to annotated plan | AC-3 | coding | - |
| t2 | Build Completed Task rows with magic(s)/item, files, commit(s), static-scan, reviewer note columns | AC-1, AC-2 | coding | t1 |
| t3 | Apply one of the three scope tags per row; flag hybrid ISA-lower rows (ctrl 16/19/39) | AC-4 | coding | t2 |
| t4 | Run `gendp-isa-reviewer` on ctrl 16, 19, 39 and PE 20, 21, 22, 23; attach summaries; cross-ref gr-clobber BitLesson. If agent unavailable, run manual ABI/hazard checklist instead | AC-7 | analyze | t3 |
| t5 | Codex `analyze` pass to produce named-hazard edge-case notes for ctrl 20, 28, 32, 36, 38 and PE 22, 23 | AC-5 | analyze | t3 |
| t6 | Write Approved Deviations table with default classifications from DEC-2 and analogous defaults for ctrl 20 / PE 22 | AC-6 | coding | t3 |
| t7 | Convert each "Known Issues Deferred" bullet into a current / gap / owner triple; assign DEFERRED_BY_DECISION outcome; verify mutual exclusivity with AC-6 | AC-9 | coding | t3 |
| t8 | Map every lesson (four BL-* plus SORT_BIN_REGION_SIZE corruption) to guarded magic(s) and supporting AC(s) | AC-10 | coding | t3 |
| t9 | Run `mode 2 -t 56` (per DEC-1 blocker) and attach result; write AC-8 verification-boundary sentence | AC-8 | coding | t1 |
| t10 | Finalize AC-1 outcomes for every tracked item; emit document-level verdict (ACCEPTED / ACCEPTED_WITH_DEVIATIONS / REJECTED) | AC-1 | coding | t2, t4, t5, t6, t7, t9 |
| t11 | Apply all annotations in-place to `isaLikeAllGwfaPlan1H.md` per DEC-3; ensure no implementation-file edits | AC-1..AC-10 | coding | t10 |

## Claude-Codex Deliberation

### Agreements
- "MOSTLY MET" is not a usable review gate; four-valued outcome set (`MET`,
  `APPROVED_DEVIATION`, `DEFERRED_BY_DECISION`, `NOT_MET`) is required.
- A document-level verdict (`ACCEPTED` / `ACCEPTED_WITH_DEVIATIONS` / `REJECTED`) is
  required and is distinct from per-item outcomes.
- An evidence matrix with static-scan + reviewer-confirmed columns is required for
  retrospective traceability.
- Scope must be partitioned between `Plan 1 structural`, `Plan 1 structural + hybrid
  ISA-lower`, and `Deferred to Plan 2x`.
- `gendp-isa-reviewer` (or a manual ABI/hazard checklist if the agent is unavailable)
  is mandatory on the hybrid-lowered magics.
- Approved Deviations and Deferred Items are mutually exclusive tables.
- Deferred bullets must be 3-part triples (current / gap / owner).
- BitLessons must be cross-referenced to magic(s) and to at least one supporting AC.
- No implementation changes to the simulator files are allowed inside this plan.
- Prior static scan of the repository confirms: deprecated magics deleted, rename clean,
  dead helper removed, controller 32 seam still uses local variable, PE 19 still uses
  local-variable code, controller 31 lacks autoincrement cursors, PE 22 hoist is partial.

### Resolved Disagreements
- Soft "MOSTLY MET" classification: resolved into the four-valued outcome set by adding
  `APPROVED_DEVIATION` and `DEFERRED_BY_DECISION`.
- Lower-bound escape hatch ("user explicitly accepts lower coverage"): removed. All
  AC-1..AC-10 must be met at the lower bound; rigor above that is optional.
- Hybrid ISA-lowering review: resolved as mandatory (AC-7), not optional.
- Default classification for known divergences: resolved to `APPROVED_DEVIATION` for
  controller 20 stride-3 arcs, controller 32 seam (confirmed by user via DEC-2), and
  PE 22 partial hoist.
- AC-2 schema ("magic ID" too rigid for cleanup rows): relaxed to "magic(s) or
  cleanup/scope item" so aggregate rows review honestly.
- DEC numbering consistency: `DEC-1` (mode 2 blocker), `DEC-2` (ctrl 32 class), `DEC-3`
  (annotation target). No phantom `DEC-4`.

### Convergence Status
- Final Status: `converged`
- Rounds executed: 3 (Claude candidate v1 → Codex round 1 → Claude revision v2 →
  Codex round 2 → Claude revision v3 → Codex round 3). Codex round 3 returned zero
  `REQUIRED_CHANGES` and zero `DISAGREE`.

## Pending User Decisions

All three user decisions have been resolved.

- DEC-1: Is `mode 2 -t 56` verification a Plan 1 closure blocker?
  - Claude Position: Not a blocker; hand off residual pipeline-boundary risk to Plan 2c.
  - Codex Position: Open question; blocking yields stronger end-to-end confidence.
  - Tradeoff Summary: Cleaner phase boundary vs stronger end-to-end confidence.
  - Decision Status: `Block Plan 1 closure on mode 2 -t 56 PASS` (user override of the
    Claude default). AC-8 reflects this: no verdict is emitted without mode 2 evidence.

- DEC-2: Controller 32 first/last intv via local variable (draft intent was s1c):
  classify how?
  - Claude Position: `APPROVED_DEVIATION` with downstream owner Plan 2b.
  - Codex Position: Either `APPROVED_DEVIATION` or `NOT_MET` depending on strictness.
  - Tradeoff Summary: Pragmatic retrospective closure vs strict fidelity to original
    draft semantics.
  - Decision Status: `APPROVED_DEVIATION, downstream owner Plan 2b` (user confirms
    Claude default).

- DEC-3: Where should review outcome annotations live?
  - Claude Position: Annotate Plan 1 file in place for a single canonical artifact.
  - Codex Position: In-place or companion review file are both acceptable.
  - Tradeoff Summary: Simpler provenance vs cleaner audit separation.
  - Decision Status: `Edit Plan 1 in place (isaLikeAllGwfaPlan1H.md)` (user confirms
    Claude default). AC-1..AC-10 outcomes are applied to this file in-place in Plan 1
    execution.

## Implementation Notes

### Code Style Requirements
- This plan produces documentation, not implementation code. No changes to
  `pe_array.cpp`, `pe.cpp`, or `scripts/gwfa_instruction_generator.py` are permitted.
- If a future plan (Plan 2+) implements follow-up code, that code and its comments must
  NOT contain plan-specific workflow terminology such as `AC-`, `Milestone`, `Step`,
  `Phase`, or similar. These belong in plan documentation, not the codebase.
- Use descriptive, domain-appropriate naming in any follow-up implementation (for
  example, `m28_bs_outer:` not `milestone4_step2:`).

### Procedural Notes (from draft, preserved)
- The original code works; any mode-1 / mode-2 regression discovered during review is
  treated as a review finding and routed to Plan 2+, not fixed inside this plan.
- Checkpoint frequently if the reviewer updates the annotated plan across multiple
  sessions.
- Keep BitLesson provenance intact: do not delete or rewrite the lesson text; only add
  cross-references.

### Optimization Objectives (preserved from draft, reference only)
- mvdq/mvd bandwidth, round-robin PE streaming, hoisted boundary checks, compile-time
  constants, half-register usage, and avoidance of redundant computation are all
  optimization goals tracked across Plans 1/2/3/4. Plan 1 records which goals are met,
  deviated from, or deferred; it does not pursue new optimizations here.

---

# Review Closure Annotations (final)

## Document-Level Verdict

**`ACCEPTED_WITH_DEVIATIONS`**

- Zero `NOT_MET` outcomes.
- Three `APPROVED_DEVIATION` outcomes: ctrl 20 stride-3 arcs (owner Plan 2a); ctrl 32
  first/last intv via local variable (owner Plan 2b, per DEC-2); PE 22 buffer-switch
  partial hoist (owner Plan 2c).
- Four `DEFERRED_BY_DECISION` outcomes: ctrl 20 SPM-latency masking + half-registers
  (Plan 2a); ctrl 31 autoincrement cursors (Plan 2b); PE 19 half-registers + mvd
  (Plan 2a); PE 23 broad `M23_SAVE_RESUME` / no-mvd-merge / no-SPM-gaps (Plan 2c).
- All other tracked items `MET` (including the draft's "Remaining std::min/max in
  controllers 28/29/37" bullet, which is closed as `MET` because residuals live only
  in explicitly frozen magics per the AC-3 static scan).
- AC-8 boundary declaration: `Mode 2 -t 56 is a Plan 1 closure blocker per DEC-1, and
  the attached run below shows 295/295 passing; closure is authorized.`

## AC Outcome Summary

| AC | Outcome | Evidence Anchor |
|----|---------|-----------------|
| AC-1 | MET | Review Matrix + Deferred Items + Approved Deviations (all four-valued). |
| AC-2 | MET | Every Completed row cites magic(s)/item, files, commit SHA(s), static scan, reviewer note. |
| AC-3 | MET | AC-3 Cleanup Grep Results block below. |
| AC-4 | MET | Exact scope-tag strings in every matrix row. |
| AC-5 | MET | Inline edge-case notes on ctrl 20/28/32/36/38 + PE 22/23 (3 CLEAN / 4 WATCH / 0 DEFECT). |
| AC-6 | MET | Approved Deviations table. |
| AC-7 | MET | Inline ABI/hazard audit on ctrl 16/19/39 + PE 20/21/22/23 (2 CLEAN / 5 WATCH / 0 DEFECT); gr-clobber discipline verified. |
| AC-8 | MET | `mode 2 -t 56` run transcript below: 295/295 passed. |
| AC-9 | MET | Deferred items converted to CURRENT/GAP/OWNER triples. |
| AC-10 | MET | BitLesson Cross-References table below. |

## AC-3 Cleanup Grep Results

Commands run from `/data4/kaplannp/GenDP2/gdpW/gendp/`:

1. `grep -n "case 2:\|case 10:\|case 26:" pe_array.cpp` → zero hits on controller
   dispatch. Deprecated controller magics 2/10/26 absent from dispatcher.
2. `grep -rn "\bSORT_BIN_REG\b" *.cpp *.h scripts/*.py` → zero hits. Identifier
   fully removed; rename complete.
3. `grep -rn "SORT_BIN_REGION_SIZE" *.cpp *.h scripts/*.py` → intact hits at
   `sys_def.h:214` (definition), `pe_array.cpp:2460`, `pe.cpp:1401`, `pe.cpp:1408`,
   `pe.cpp:1419`, and `sys_def.h:220/227/228`. Constant preserved; no `REGION`
   substring corruption.
4. `grep -rn "merge_split_and_load" .` → zero live code references. Only occurs
   in plan docs and a descriptive comment `// Inlined from merge_split_and_load.`
   at `pe_array.cpp:2671`.
5. Barrier inserts in `scripts/gwfa_instruction_generator.py` for magic 7 → magic 8
   transitions (4 sites / 8 barrier calls):
   - Site 1: lines 202–205 (`MAGIC_7_BUF0` → 2 barriers → `MAGIC_8_BUF0`).
   - Site 2: lines 207–210 (`MAGIC_7_BUF1` → 2 barriers → `MAGIC_8_BUF1`).
   - Site 3: lines 222–225 (`MAGIC_7_BUF0` → 2 barriers → `MAGIC_8_BUF0`).
   - Site 4: lines 236–239 (`MAGIC_7_BUF1` → 2 barriers → `MAGIC_8_BUF1`).
   - Lines 484 and 509 write `MAGIC_8` standalone (no preceding `MAGIC_7`); no
     barrier required.

## Review Matrix (AC-1, AC-2, AC-4)

AC-4 scope tags use the exact strings `Plan 1 structural` or `Plan 1 structural +
hybrid ISA-lower`. One row per bullet from the draft's Completed Tasks list.

| Claim | Item | Files | Commit(s) | Static Scan | Reviewer Note | Outcome | AC-4 Scope Tag |
|-------|------|-------|-----------|-------------|---------------|---------|----------------|
| Delete controller magics 2/10/26 + clean references | cleanup | `pe_array.cpp`, `scripts/gwfa_instruction_generator.py` | `d719a69` | Dispatcher has no `case 2/10/26`; PE-side `MAGIC_2/10/26` constants refer to PE-level magics (not controller) | Cleanup of controller dispatch confirmed; no stale references observed. | MET | Plan 1 structural |
| Add barrier between magic 7→8 in generator (4 sites / 8 calls) | cleanup | `scripts/gwfa_instruction_generator.py` | `d719a69` | 4 sites / 8 barrier calls confirmed | Barrier count matches AC-3 requirement. | MET | Plan 1 structural |
| Rename `SORT_BIN_REG` → `SORT_BIN_SPM` | cleanup | `sys_def.h`, `pe_array.cpp`, `pe.cpp` | `d719a69`, `4e8b3a2` | `SORT_BIN_REG` grep clean; `SORT_BIN_REGION_SIZE` intact | Rename complete; accidental `REGION` corruption from earlier round fixed by `4e8b3a2`. | MET | Plan 1 structural |
| Remove dead `merge_split_and_load` helper | cleanup | `pe_array.cpp` | `e0ec8a7`, `1775412` | No live references; one descriptive comment remains | Helper gone; comment at `pe_array.cpp:2671` retained intentionally as provenance. | MET | Plan 1 structural |
| Magic 16: min/max → branches, goto clamping, division → shift, use `gr[]` directly | ctrl 16 | `pe_array.cpp` | `a28e747`, `398821f` | gr-clobber fix applied per `BL-20260413-gr-clobber` | AC-7 audit: saves `gr[20/24/28]` to `s1c[144/145/155]` before clamp-mutating `gr[24]`, honoring BL-20260413-gr-clobber. Goto clamp avoids min/max intrinsics; SPM stores only, no MM/S2 loads, no waitLSQ required; controller arithmetic destinations all legal. Finding: CLEAN. | MET | Plan 1 structural + hybrid ISA-lower |
| Magic 18: `gwfa_get_mm_ha_off`/`ha_dirty_off` → constexpr constants | ctrl 18 | `pe_array.cpp` | `a28e747` | Function calls removed | Constant substitution straightforward; low-risk. | MET | Plan 1 structural |
| Magic 19: flip loop (bins outer / PEs inner), locals → `gr[7..10]` | ctrl 19 | `pe_array.cpp` | `a28e747`, `398821f` | Bins outer / PEs inner confirmed | AC-7 audit: scopes temps to `gr[7..10]` preserving BL-20260413-gr-clobber. `gr[7]=spm[...]` → downstream `s1c[...]=gr[7]` has no NOP spacer in C++ — lowerer must inject the 2-cycle SPM-load gap or reorder across the PE loop. No MM/S2 loads. Destinations `gr`/`s1c`/`spm` all legal. Finding: WATCH (lowering-time load-use scheduling; not a magic-level defect). | MET | Plan 1 structural + hybrid ISA-lower |
| Magic 20: two-loop `fin0_load_batch` (mvdq common + mv fallback), remove bitmap, remove return value, lambda → `F0B_ASSIGN` macro | ctrl 20 | `pe_array.cpp` | `6f2678c`, `7ab721e` | Two-loop structure present | AC-5 (stride-3 arc fallback hazard): the two-loop split cleanly separates the mvdq fast path from the stride-3 `mv` fallback, so stride-3 arc shapes cannot be silently dropped through the fast path. Finding: CLEAN. APPROVED_DEVIATION owner Plan 2a. | APPROVED_DEVIATION | Plan 1 structural |
| Magic 24: full-tile fast path + peeled final iteration, interleaved mvdq | ctrl 24 | `pe_array.cpp` | `4e8b3a2`, `e202b4e` | mvdq + peel structure present | Reviewer note: final-tile peel at boundary is the only residual path; fast path dominant. | MET | Plan 1 structural |
| Magic 25: chunk-outer PE-inner round-robin scatter writeback | ctrl 25 | `pe_array.cpp` | `4e8b3a2`, `1775412` | Chunk-outer / PE-inner pattern present | Reviewer note: writeback pattern matches ctrl 7 reference. | MET | Plan 1 structural |
| Magic 28: remove sanity check, inline `merge_split_and_load`, interleaved binary search across PEs, mvdq tile loads, waitLSQ comments | ctrl 28 | `pe_array.cpp` | `ee665b6`, `e0ec8a7`, `4c5e798` | mvdq tile-load section annotated | AC-5 (binary-search convergence hazard): per-PE round stepping plus waitLSQ creates a real risk of livelock / premature exit if the termination condition is not tied to all PEs reaching quiescence; the controller's per-round "all PEs stopped stepping" condition is the structurally correct choice. Finding: WATCH. | MET | Plan 1 structural |
| Magic 29: interleaved mvdq tile loads (diag BUF0/1, intv BUF0/1) | ctrl 29 | `pe_array.cpp` | `0e51a2b` | Interleaved mvdq structure present | Branch-style min/max substitution confirmed; computational path clean. | MET | Plan 1 structural |
| Magic 30: `mvdq_copy` for dedup reload, std::min → branch | ctrl 30 | `pe_array.cpp` | `1775412` | Branch-style replacement confirmed | No residuals observed. | MET | Plan 1 structural |
| Magic 31: chunk-outer PE-inner round-robin writeback | ctrl 31 | `pe_array.cpp` | `1775412` | Writeback loop confirmed; autoincrement cursors NOT implemented | Autoincrement cursors deferred; see Deferred Items. | MET | Plan 1 structural |
| Magic 32: mid-diag start boundary max-merge, local variable for intv seam merge (no MM read-back), bulk mvdq diag+intv gather with PE-seam-only fixup | ctrl 32 | `pe_array.cpp` | `ee665b6`, `e202b4e`, `af3b08f` | Local intv seam variable confirmed; s1c relocation not done | AC-5 (diag+intv gather dependency hazard): keeping the gather PE-serial and confining the special-case repair to the PE seam preserves the producer/consumer dependency ordering that BL-20260416-m32-gather-dep calls out; a parallel gather would smear that dependency. Finding: CLEAN. Per DEC-2: APPROVED_DEVIATION owner Plan 2b. | APPROVED_DEVIATION | Plan 1 structural |
| Magic 33: separate nested `mm[s1c[X]]` into register load + `mm[reg]`, `mvdq_copy` for reload, std::min → branch | ctrl 33 | `pe_array.cpp` | `a28e747`, `1775412` | Nested lookup decomposition confirmed | Decomposition eliminates illegal instruction shape. | MET | Plan 1 structural |
| Magic 34: already ISA-like (reference pattern) | ctrl 34 | `pe_array.cpp` | `af3b08f`, `398821f` | Reference pattern preserved; `af3b08f` cleaned std::min/max instances in magic 34; `398821f` applied gr-clobber fix affecting the cross-magic ABI boundary magic 34 sits on | Pre-existing ISA-like shape retained; the two Plan 1 commits that touched this magic are cleanup-only (no shape change). | MET | Plan 1 structural |
| Magic 35: chunk-outer PE-inner round-robin merge writeback | ctrl 35 | `pe_array.cpp` | `1775412` | Writeback pattern confirmed | Boundary condition: multiples of two across PEs. | MET | Plan 1 structural |
| Magic 36: remove sorted-output check, mid-diagonal start (nominal splits, no forward scan) | ctrl 36 | `pe_array.cpp` | `ee665b6` | Sorted check removed; mid-diag start present | AC-5 (boundary fixup hazard): with forward scanning removed, correctness pressure moves to the handoff between consecutive tiles; the explicit max-merge across merged diagonal boundaries is the necessary structural repair. Finding: CLEAN. | MET | Plan 1 structural |
| Magic 37: inline `merge_split_and_load` with interleaved binary search | ctrl 37 | `pe_array.cpp` | `1775412` | Interleaved binary search inline | Ternary/branch substitution confirmed; computational path clean. | MET | Plan 1 structural |
| Magic 38: fuse lo/hi binary search into single interleaved loop, waitLSQ comments | ctrl 38 | `pe_array.cpp` | `ee665b6` | Fused loop present with waitLSQ comments | AC-5 (fused search convergence hazard): the joint post-loop is safe only once both lo and hi binary searches have terminated; the fused shape makes this guarantee easier to erode than in separately staged loops. Current code correctly treats the post-loop as a joint exit. Finding: WATCH. | MET | Plan 1 structural |
| Magic 39: restructured to use `gr[]` directly, division → shift | ctrl 39 | `pe_array.cpp` | `1775412`, `398821f` | Direct gr[] usage + shift confirmed | AC-7 audit: restores `gr[24]` from `s1c[155]` at entry (mirrors BL-20260413-gr-clobber's pattern using the Plan-1-saved `next_intv_n` slot). RAW chain `gr[6]=gr[24]+3` → `gr[6] >> 2` separated by `//NOP` spacer. No SPM/MM loads; destinations all `gr`, legal. Finding: CLEAN. | MET | Plan 1 structural + hybrid ISA-lower |
| PE 20: two-element contiguous (vd,k,vd,k) mvd loads with peel | PE 20 | `pe.cpp` | `4c5e798`, `af3b08f` | Two-element mvd with peel confirmed | AC-7 audit: no cross-magic gr[] state — gr-clobber not applicable. Main loop reads `tile[i*2 .. i*2+3]` per iteration modeling one mvd of 4 words (one SPM transaction per iter). Lowering must budget SPM load-use latency and not pair mvd with the `counts[]++` store in the same cycle (1 port/PE). No MM/S2 access. Finding: WATCH. | MET | Plan 1 structural + hybrid ISA-lower |
| PE 21: two-element mvd scatter with peel | PE 21 | `pe.cpp` | `4c5e798` | Two-element scatter confirmed | AC-7 audit: no cross-magic gr[] state. Scatter path (vd → bin → off → `spm[...]`) has load-compute-store chain per element; lowering must space across cycles. `bin_cursors[]` should live in `gr` not SPM to avoid added port pressure. No MM/S2 access; destinations legal. Finding: WATCH. | MET | Plan 1 structural + hybrid ISA-lower |
| PE 22: goto-based restructure (`m22_top`/`m22_eval`/`m22_merge`/`m22_done`), buffer transitions labeled | PE 22 | `pe.cpp` | `7ab721e` | Goto-based structure present; partial hoist only | AC-5 (buffer-switch transition hazard): goto structure makes correctness depend on exact labeled transitions; failed hoist attempts demonstrate the transitions do not tolerate casual motion across drain-budget or PE/global-base boundaries. Finding: WATCH. AC-7 audit: (a) gr-clobber — no gr[] carried across magic boundary (PE scope); BL-20260413-pe-global-base handled via `spm[982]`/`spm[983]` persistent merge-boundary state read at entry. (b) VLIW RAW/WAW — tight `m22_top → m22_done` loop interleaves `spm[bb+bi*2]`/`spm[ab+ai*2]` loads with `out[oi*2]` stores; load→compare→store chain must be cycle-separated at lowering. (c) SPM 2-cycle latency — boundary-tracking block issues 6 SPM reads/writes per merge step (reads of `spm[976+b]`/`spm[979+b]` three times per direction); dominates per-iter cycle count, lowering-time scheduling puzzle. (d) waitLSQ — no MM/S2 accesses; not applicable. (e) destination restrictions — `MERGE_STEP` budget cap honors BL-20260413-drain-budget; all SPM writes to META at end target legal PE destinations. AC-7 Finding: WATCH (boundary-block port pressure; correctness fine). APPROVED_DEVIATION owner Plan 2c. | APPROVED_DEVIATION | Plan 1 structural + hybrid ISA-lower |
| PE 23: lambda → `M23_RD`/`M23_RI`/`M23_PI` macros, `M23_SAVE` split into `M23_SAVE_OUT` + `M23_SAVE_RESUME` | PE 23 | `pe.cpp` | `6318deb`, `7ab721e` | Macro substitution confirmed | AC-5 (save/resume scope hazard): split into `M23_SAVE_OUT` (checkpoint boundary) and `M23_SAVE_RESUME` (resume-boundary restoration) is the right shape; broad resume macro remains worth guarding. AC-7 audit: state restored from DEDUP_META at entry, saved at every exit (no gr[] carried across boundary). `M23_RD/RI/PI` each touch 2 SPM words; `pdone` early-exit path correctly flushes `M23_SAVE` before `goto m23_end`, leaving the fall-through save at `pe.cpp:1696` as dead code (cleanliness note). No MM/S2 reads. Finding: WATCH. Broad `M23_SAVE_RESUME` scope deferred — see Deferred Items. | MET | Plan 1 structural + hybrid ISA-lower |
| std::min/max cleanup in controller 28 (6 instances → branch-style) | cleanup | `pe_array.cpp` | `af3b08f` | Static scan of magic 28 (`pe_array.cpp:2668–2840`) finds no `std::min`/`std::max` in the computational path | Substitution confirmed; no residual inside magic 28. | MET | Plan 1 structural |
| std::min/max cleanup in controller 29 (2 instances → branch-style) | cleanup | `pe_array.cpp` | `af3b08f` | Static scan of magic 29 (`pe_array.cpp:2963–3092`) finds no `std::min`/`std::max` | Substitution confirmed; magic 29 computational path clean. | MET | Plan 1 structural |
| std::min/max cleanup in controller 34 (3 instances → branch-style) | cleanup | `pe_array.cpp` | `af3b08f` | Static scan of magic 34 (`pe_array.cpp:2282–2335` region) shows earlier `std::min(n_a_per_pe, n_a - pe_start)` / `std::max(0, pe_remain - cursor)` lines removed by `af3b08f` | Branch-style substitution confirmed for the pre-existing ISA-like magic 34. | MET | Plan 1 structural |
| std::min/max residuals in rewritten controllers 28/29/37 (draft deferred bullet, closed) | cleanup | `pe_array.cpp`, `pe.cpp` | `af3b08f` | Zero `std::min`/`std::max` in rewritten magics 28/29/37; residuals at `pe_array.cpp:3301/3358/3389/3402/3415/3428/3441` live in frozen `magic_id == 6` debug; residuals at `pe.cpp:653/931/979/1004` live in frozen PE magic 8 (draft states "min/max fine on pe") | Original draft bullet "Remaining std::min/max in controllers 28/29/37" satisfied: no residuals in rewritten magics; all remaining occurrences in explicitly out-of-scope frozen code. | MET | Plan 1 structural |

## Approved Deviations (AC-6)

| Deviation | Current Behavior | Rationale | Downstream Owner |
|-----------|------------------|-----------|------------------|
| Controller 20 stride-3 arc loads | Pure mvdq not used for arc loads due to 3-word stride; partial conversion applies mvdq where stride permits, scalar `mv` elsewhere. | 3-word arc stride cannot be packed into contiguous mvdq blocks without either padding or a separate gather pass. Accepted as structural reality. | Plan 2a |
| Controller 32 first/last intv seam via local variable | First/last intv of each PE held in a local variable during dedup; no s1c writeback for boundary merge. | Per DEC-2 (user override): pragmatic retrospective closure; keeps traceability while the s1c relocation is scheduled for Plan 2b. | Plan 2b |
| PE 22 buffer-switch partial hoist | Goto-based structure (`m22_top`/`m22_eval`/`m22_merge`/`m22_done`) hoists the buffer-switch transition but leaves some checks in the hot merge loop. Three hoist attempts failed. | Correctness is stable at 295/295 per `BL-20260413-drain-budget` + `BL-20260413-pe-global-base`. Additional hoisting risks destabilizing the merge; routed to Plan 2c. | Plan 2c |

## Deferred Items — CURRENT / GAP / OWNER (AC-9)

All entries receive outcome `DEFERRED_BY_DECISION`. Mutually exclusive with AC-6.

| Deferred Item | CURRENT | GAP | OWNER |
|---------------|---------|-----|-------|
| Controller 20 SPM latency masking + half-registers | `fin0_load_batch` uses two-loop structure (mvdq common + mv fallback); half-registers not employed; SPM-load latency not masked by interleaved instructions. | Draft asks for SPM latency masked via interleaving and half-register usage to widen effective bandwidth; current code meets structural shape but leaves latency/density on the table. | Plan 2a |
| Controller 31 autoincrement cursors | Writeback uses explicit `mvdq_copy()` calls with manual s1c cursor updates. | Draft asks for `mv`-autoincrement cursors so destination addresses aren't recomputed per iteration. | Plan 2b |
| PE 19 half-registers + mvd | Local-variable code using scalar shift/mask for 2-bit extraction; no mvd loads. | Draft asks for half-register usage and mvd loads to increase bandwidth and reduce bitshift overhead. | Plan 2a |
| PE 23 broad `M23_SAVE_RESUME` + no mvd merge writes + no SPM latency gaps | Macro split is coarse (`M23_SAVE_OUT` / `M23_SAVE_RESUME`); merge writes use scalar stores; SPM gaps not inserted between consecutive loads. | Draft asks for tighter resume scope, mvd for overlapping merge writes, and explicit 2-cycle SPM gaps before use. | Plan 2c |

> The draft's original "Remaining std::min/max in controllers 28/29/37" bullet was
> closed as `MET` and recorded in the Review Matrix — AC-3 static scan shows no
> residuals in any rewritten magic; remaining occurrences live only in explicitly
> frozen code (magic 6 debug + PE magic 8). The draft's "PE 22 buffer-switch checks
> still in hot loop" and "Controller 32 first/last intv to s1c" bullets are
> `APPROVED_DEVIATION` (AC-6), not deferred.

## BitLesson Cross-References (AC-10)

| Lesson ID | Guards | Supports AC |
|-----------|--------|-------------|
| `BL-20260413-drain-budget` | `pe.cpp` PE magic 22 (merge kernel drain) | AC-5 (PE 22 edge-case note), AC-6 (PE 22 deviation rationale), AC-7 (PE 22 destination-restriction check) |
| `BL-20260413-gr-clobber` | `pe_array.cpp` magics 16/19/28/38/39 and `scripts/gwfa_instruction_generator.py` (cross-magic ABI boundary) | AC-7 (mandatory audit on hybrid-lowered magics — gr-clobber check is explicit in the manual ABI/hazard checklist; verified in ctrl 16 / 19 / 39 audits) |
| `BL-20260413-pe-global-base` | `pe.cpp` magic 22 and `pe_array.cpp` magics 37/38 (merge boundary global base in SPM[983]) | AC-5 (PE 22 + ctrl 37/38 edge-case notes), AC-6 (PE 22 deviation rationale), AC-7 (PE 22 gr-clobber-not-applicable + SPM-state check) |
| `BL-20260416-m32-gather-dep` | `pe_array.cpp` magic 32 (dedup finalize gather) | AC-5 (ctrl 32 edge-case note), AC-6 (ctrl 32 deviation rationale) |
| `SORT_BIN_REGION_SIZE corruption` (non-BL) | `sys_def.h`, `pe_array.cpp`, `pe.cpp` (rename-cleanup for SORT_BIN_REG → SORT_BIN_SPM) | AC-3 (cleanup verification grep for `SORT_BIN_REGION_SIZE` intact) |

## AC-8 Verification (mode 2 -t 56, DEC-1 blocker)

Fresh run executed:

```
$ python3 scripts/gwfa_check_correctness.py 2 -t 56
...
  progress: 295/295

==================================================
Results: 295 passed, 0 failed out of 295
==================================================
```

Captured log: `.humanize/rlcr/2026-04-17_08-46-50/mode2-run.log`. Exit code 0.

AC-8 declaration: `Mode 2 -t 56 is a Plan 1 closure blocker per DEC-1, and the
attached run above shows 295/295 passing; closure is authorized.`

## Open Issues (for Plan 2+ follow-up)

| Issue | Blocking AC | Resolution Path |
|-------|-------------|-----------------|
| `pe.cpp:1696` contains a dead `M23_SAVE` macro expansion after every PE 23 exit path already saves explicitly | none (cleanliness only) | Remove in Plan 2c PE 23 polish |
| ctrl 19 has no NOP spacer between `gr[7]=spm[...]` and downstream `s1c[...]=gr[7]`; lowerer must inject SPM 2-cycle latency padding | none (structural shape correct) | Track in Plan 3 ISA-lowering pass |
| PE 20/21 scatter/mvd port pairing concerns — lowerer must not pair mvd with `counts[]++` or scatter store in the same cycle | none | Track in Plan 3 ISA-lowering pass |
| PE 22 boundary-tracking block issues 6 SPM reads/writes per merge step; cycle-budget validation recommended | none | Track in Plan 2c PE 22 polish |

---

--- Original Design Draft Start ---

# GWFA ISA-Like Rewrite Plan 1: Structural Changes (CODE IMPLEMENTED, PENDING REVIEW)

## Goal Description

Perform all major structural changes to GWFA magic instructions: delete deprecated magics, restructure algorithms (binary search interleaving, seam merge, mid-diagonal start, fin0_load_batch two-loop), convert scalar loops to mvdq round-robin, and begin ISA-style patterns (gotos, register usage). Each magic verified after change.

## Status: REVIEW-CLOSED (Round 2) — `ACCEPTED_WITH_DEVIATIONS`

Structural changes implemented and passing mode 1 (15/15) and mode 2 -t 56 (295/295
passed this round). Full ISA review complete per the Review Closure Annotations block
above. Three approved deviations and four deferred items routed to Plans 2a/2b/2c.

## Acceptance Criteria (draft-original)

The draft's AC-1..AC-6 were the initial soft-status set. They are superseded by the
review gate's AC-1..AC-10 defined at the top of this plan and adjudicated in the
Review Closure Annotations block above. Draft labels (for historical reference) are
retained here with their final review-gate mapping:

- Draft AC-1: Correctness preserved (mode 1 after each change) — MET (mode 1 + mode 2
  both pass; see review gate's AC-8).
- Draft AC-2: Deprecated magics 2, 10, 26 deleted with full cleanup — MET (review
  gate's AC-3 cleanup grep confirms).
- Draft AC-3: mvdq round-robin streaming where specified — MET on every rewritten
  magic except PE 19 (DEFERRED_BY_DECISION for half-registers + mvd, owner Plan 2a)
  and ctrl 20 arc stride (APPROVED_DEVIATION, owner Plan 2a). Review gate's AC-4 /
  AC-6 / AC-9 adjudicate per magic.
- Draft AC-4: All specific per-magic structural requirements addressed — review
  gate's AC-1 adjudicates this bullet-by-bullet. Outcome set: 25 MET, 3
  APPROVED_DEVIATION, 0 NOT_MET in the Completed Tasks list; 4 DEFERRED_BY_DECISION
  in the Known Issues list.
- Draft AC-5: Barrier added between magic 7→8 in instruction generator — MET (review
  gate's AC-3 grep confirms 4 sites / 8 calls).
- Draft AC-6: SORT_BIN_REG renamed to SORT_BIN_SPM — MET (review gate's AC-3 grep
  confirms identifier gone; `SORT_BIN_REGION_SIZE` intact).

## Completed Tasks (by magic)

### Cleanup (M1)
- ✅ Delete controller magics 2, 10, 26 + clean references — MET
- ✅ Add barrier between magic 7→8 in instruction generator (4 locations) — MET
- ✅ Rename SORT_BIN_REG → SORT_BIN_SPM across sys_def.h, pe_array.cpp, pe.cpp — MET
- ✅ Remove dead merge_split_and_load function (after 28/37 inlining) — MET

### Controller structural changes
- ✅ Magic 16: min/max→branches, goto clamping, division→shift, use gr[] directly — MET
- ✅ Magic 18: gwfa_get_mm_ha_off/ha_dirty_off → constexpr constants — MET
- ✅ Magic 19: flip loop (bins outer, PEs inner), all locals→gr[7-10] — MET
- ✅ Magic 20: two-loop fin0_load_batch (round-robin + fallback), remove bitmap, remove return value, lambda→F0B_ASSIGN macro — APPROVED_DEVIATION (stride-3 arcs; owner Plan 2a)
- ✅ Magic 24: full-tile fast path + peeled final iteration, interleaved mvdq — MET
- ✅ Magic 25: true chunk-outer PE-inner round-robin scatter writeback — MET
- ✅ Magic 28: remove sanity check, inline merge_split_and_load with interleaved binary search across PEs, mvdq tile loads, waitLSQ comments — MET
- ✅ Magic 29: interleaved mvdq tile loads (diag BUF0/1, intv BUF0/1) — MET
- ✅ Magic 30: mvdq_copy for dedup reload, std::min→branch — MET
- ✅ Magic 31: chunk-outer PE-inner round-robin writeback — MET
- ✅ Magic 32: mid-diagonal start boundary max-merge, local variable for intv seam merge (no MM read-back), bulk mvdq diag+intv gather with PE-seam-only fixup — APPROVED_DEVIATION (local-variable seam per DEC-2; owner Plan 2b)
- ✅ Magic 33: separate nested mm[s1c[X]] into register load + mm[reg], mvdq_copy for reload, std::min→branch — MET
- ✅ Magic 34: already ISA-like (reference pattern) — MET
- ✅ Magic 35: chunk-outer PE-inner round-robin merge writeback — MET
- ✅ Magic 36: remove sorted-output check, mid-diagonal start (nominal splits, no forward scan) — MET
- ✅ Magic 37: inline merge_split_and_load with interleaved binary search — MET
- ✅ Magic 38: fuse lo/hi binary search into single interleaved loop, waitLSQ comments — MET
- ✅ Magic 39: restructured to use gr[] directly, division→shift — MET

### PE structural changes
- ✅ PE 20: two-element contiguous (vd,k,vd,k) mvd loads with peel — MET
- ✅ PE 21: two-element mvd scatter with peel — MET
- ✅ PE 22: goto-based restructure (m22_top/m22_eval/m22_merge/m22_done), buffer transitions labeled — APPROVED_DEVIATION (partial hoist; owner Plan 2c)
- ✅ PE 23: lambda→M23_RD/M23_RI/M23_PI inline macros, M23_SAVE split into M23_SAVE_OUT + M23_SAVE_RESUME — MET

### std::min/max cleanup
- ✅ Controller 28: 6 instances replaced with branch-style — MET
- ✅ Controller 29: 2 instances replaced — MET
- ✅ Controller 34: 3 instances replaced — MET

## Known Issues Deferred to Plan 2 (adjudicated Round 2)

- Controller 20: arc stride (3-word) prevents pure mvdq — APPROVED_DEVIATION (owner
  Plan 2a, see Approved Deviations table above); SPM latency masking and
  half-registers not done — DEFERRED_BY_DECISION (owner Plan 2a).
- Controller 31: autoincrement cursors not implemented — DEFERRED_BY_DECISION (owner
  Plan 2b).
- Controller 32: first/last intv to s1c not done (uses local variable instead) —
  APPROVED_DEVIATION per DEC-2 (owner Plan 2b, see Approved Deviations table above).
- PE 19: half-registers and mvd not done (still local-variable code) —
  DEFERRED_BY_DECISION (owner Plan 2a).
- PE 22: buffer-switch checks still in hot loop (3 restructure attempts failed) —
  APPROVED_DEVIATION (owner Plan 2c, see Approved Deviations table above).
- PE 23: broad M23_SAVE_RESUME, no mvd for merge writes, no SPM latency gaps —
  DEFERRED_BY_DECISION (owner Plan 2c).
- Remaining std::min/max in controllers 28/29/37 — MET (closed Round 2: AC-3 static
  scan shows zero residuals in any rewritten magic; remaining occurrences live only
  in frozen `magic_id == 6` debug output and frozen PE magic 8, both explicitly out
  of scope per draft).

## BitLessons Discovered

- **BL-20260413-drain-budget**: PE merge drain must use unified loop, not separate drain paths
- **BL-20260413-gr-clobber**: gr registers live across magic boundaries must be saved to s1c
- **BL-20260413-pe-global-base**: PE merge boundary tracking needs global output base
- **BL-20260416-m32-gather-dep**: Controller 32 gather has sequential destination dependency; PE-serial bulk mvdq is correct form
- **SORT_BIN_REGION_SIZE corruption**: replace_all for BIN_REG→BIN_SPM accidentally caught REGION substring

## Commits (chronological)

1. `d719a69` — M1: cleanup deprecated magics, barrier, rename
2. `ee665b6` — M2 partial: structural changes to controller 28, 32, 36, 38
3. `e0ec8a7` — Restructure controller 28: inlined interleaved binary search
4. `a28e747` — M4: structural changes to controller 16, 18, 19, 33
5. `6f2678c` — Restructure controller 20: two-loop fin0_load_batch
6. `6318deb` — PE 23 lambda→macro restructure
7. `4e8b3a2` — M5 partial: mvdq for controller 24/25, fix REGION_SIZE
8. `7ab721e` — PE 22 goto, PE 23 save split, controller 20 lambda removal
9. `1775412` — Round 4: mvdq fixes for 25/30/31/33/35, controller 37 inline, 39 restructure
10. `4c5e798` — PE 20/21 two-element mvd, controller 28 tile load mvdq
11. `398821f` — ISA-lower controller 16/19/39 + gr-clobber fix
12. `0e51a2b` — Controller 29 interleaved mvdq tile loads
13. `e202b4e` — Controller 32 bulk mvdq gather, controller 24 peel, dead code removal
14. `af3b08f` — Controller 32 intv bulk mvdq, PE 20 contiguous, std::min cleanup

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---

--- Original Design Draft End ---
