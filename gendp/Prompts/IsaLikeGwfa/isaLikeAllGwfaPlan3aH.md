# GWFA ISA-Like Rewrite Plan 3a: ISA Lower Controller 16 / 18 / 19 / 20

## Shared Preamble (duplicated across all active plans)

### Scope
- **Delete**: Controller magics 2, 10, 26 (deprecated) — DONE in Plan 1
- **Exempt (do not touch)**: Controller 1, 3, 4, 5, 6, 17
- **Reference examples (frozen, read-only)**: Controller 7, 8, 9, 12, 14, 15; PE 8, 11,
  13. `fin0_load_batch()` is invoked by frozen magic 15; this plan may rewrite the
  helper body, but the call signature (`void fin0_load_batch(int fin0_base, int
  magic_mask)`) and the `s1c[20..23]` + `gr[2]` + `gr[31]` contracts that magic 15
  relies on remain frozen.
- **In-scope this plan (controller)**: 16, 18, 19, 20 (+ `fin0_load_batch()` helper
  shared with magic 15)
- **Out of this plan (covered by siblings 3b/3c/3d)**: 24, 25, 28, 29, 30, 31, 32, 33,
  34, 35, 36, 37, 38, 39
- **Out of this plan (PE)**: 19, 20, 21, 22, 23

### ISA-like rules (all 12, unchanged from the governing prompt)
1. Each line = one GenDP ISA operation
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired slots
3. Registers only: `gr[]`, `reg[]`, `s1c[]`, `spm[]`, `mm[]`; no C++ runtime variables
   carry architectural state across ISA lines
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

- **DEC-SPM-MODEL** (Plan 2c, user-confirmed): the GWFA prompt is authoritative;
  pipelined back-to-back SPM loads are permitted; only the 2-cycle consumer
  separation is enforced. 3a inherits this.
- **DEC-COMMIT** (Plan 2c, user-confirmed): per-magic additive commits; no rebase,
  reset, amend, force-push, cherry-pick-drop, or `git revert`. On any regression,
  manually undo or patch back the working-tree edit and retry. 3a inherits this.
- **DEC-SEAM-MERGE** (Plan 2a, carry-forward): magic 31/32 seam metadata
  contract at `s1c[176..191]` is preserved (out of 3a scope but do not disturb).
- **DEC-1 Launch-gate** (plan-3a, user-confirmed): a mandatory launch-gate
  task `l0` runs at 3a kickoff to record `git rev-parse HEAD`, verify
  `gwfa_check_correctness.py 2 -t 56 = 295/295` on that SHA, reconcile the
  Cross-Magic Register ABI table against launch HEAD, and absorb/defer any
  still-open Plan-2c `fix-required` items on magics 16 / 18 / 19 / 20 /
  `fin0_load_batch()`. The plan does not pre-bake a SHA.
- **DEC-2 Helper scope** (plan-3a, user-confirmed): `fin0_load_batch()`
  internal rewrite is in-scope under 3a task `l2d1`. Magic 15's call site
  stays FROZEN. The helper's signature and the `s1c[20..23]` + `gr[2]` +
  `gr[31]` contracts are preserved.
- **DEC-3 Half-register extent** (plan-3a, user-confirmed): half-register
  extraction is mandatory on the two flagged hot-path `>> 16` sites in
  `fin0_load_batch()` (pass 2 `ts_off`, pass 3 `w`). Additional
  packed-16-bit sites discovered during `l2d1` are converted when the change
  is local-and-low-risk; otherwise recorded as deferred with reason.
- **DEC-4 Sync-helper waiver** (plan-3a, user-confirmed):
  `gwfa_sync_counters()`, `gwfa_set_ha_n_dirty()`, and `gwfa_get_intv_n()`
  are waived for 3a as cross-magic seam helpers. The `// seam-helper-waived
  (DEC-4)` annotation is applied at CHANGED call sites only (magic 16 and
  magic 18); magic 15's frozen call site is not touched. Formal lowering of
  the three helpers is deferred to a later plan.
- **DEC-CORRECTNESS-BAR** (plan-3a, user-confirmed): the end-of-plan
  `gwfa_check_correctness.py 2 -t 56 = 295/295` is a hard pass/fail bar,
  not a directional target. AC-1 enforces this as the `l3` commit blocker.
- **DEC-HASH-PATH** (plan-3a, user-confirmed 2026-04-22; re-confirmed
  Round 2 + Round 3): the Fibonacci-hash multiply in `fin0_load_batch()`
  pass 3 (`uint32_t hk`, `h`, `b`, and `int ms` around
  `pe_array.cpp:700-722`) is DEFERRED to a 3a follow-on plan.
  Rationale: the controller ISA has no integer-multiply opcode on `gr[]`
  (confirmed by `l0` Codex analyze); emulating `×0x9E3779B9` with a
  shift+add decomposition over the 20 set-bit positions (`{0, 3, 4, 5,
  7, 8, 11, 12, 13, 14, 16, 17, 18, 20, 21, 25, 26, 27, 28, 31}`) would
  add ~50-70 ISA lines and substantial register pressure inside an
  otherwise-clean helper rewrite. In `l2d1`, the block is annotated
  in-code with `// DEC-HASH-PATH carve-out: controller ISA lacks int
  multiply on gr[]; lowering deferred to 3a follow-on plan` and the
  `hk, h, b, ms` values are computed as C++ locals. `cursor`, `pe_rr`,
  and `dst_` still hoist normally. This deferral is narrowly scoped —
  all other AC-2 architectural-state rules apply — and is the ONLY
  explicit AC-2 carve-out 3a allows.

### Cross-Magic Register ABI (Plan 3a initial table; extended by `l1` at launch)

This section documents which architectural-state slots are live across magic
boundaries for the 16 / 18 / 19 / 20 path plus the shared FIN0 pipeline. All ISA
lowering in 3a MUST consult this before allocating temps. Task `l1` in this plan
creates the launch-time authoritative version by reconciling this table against
post-2c HEAD.

**Live `gr[]` across 3a-relevant magic boundaries:**
- `gr[1]`: sort pass number (live across `34→19→24/25`)
- `gr[2]`: two-phase semantics —
  - Sort phase: sort/merge/dedup cursor across tile loops
  - FIN0 phase: "more passes needed" continuation flag written by
    `fin0_load_batch()` (`gr[2] = (cursor < total_fin0) ? 1 : 0`)
  These phases are disjoint in time; both must be preserved by 3a.
- `gr[3]`: MM source base (live across sort loop)
- `gr[4]`: MM destination base (live across sort/merge/dedup loops)
- `gr[6]`: sort-driver loop bound (live across tile load→PE→writeback→reload
  loops). Magic 16 overwrites `gr[6]` intentionally with the new sort loop bound
  in its setup phase; that store is the handoff into the sort pipeline.
- `gr[20]`: `diag_base` (live from phase 1 into magic 16; magic 16 saves it to
  `s1c[144]` before any reuse in later magics)
- `gr[24]`: `n_a` / `n_unsorted` (live across sort/merge/dedup pipeline; magic 16
  saves it to `s1c[145]` and mutates it in-place for the sort phase)
- `gr[26]..gr[28]`: counters (live across FIN0 pipeline)
- `gr[29]`: `seq_off_s2` (live across `fin0_load_batch` passes)
- `gr[31]`: `ha_n_dirty` (live across the FIN0 pipeline; initialized in the FIN0
  setup controller path, mutated by magic 18 phase 4, committed to backing store
  via `gwfa_set_ha_n_dirty()` in magics 15 and 18)

**Known magic-local temps (listed for disambiguation; NOT live across
boundaries):**
- `gr[7]..gr[10]`: magic 19 prefix-sum + magic 20 helper temps
- `gr[11]`, `gr[13]`, `gr[14]`: helper inner-loop temps

**Live `s1c[]` across 3a-relevant magic boundaries (phase-disjoint; same
physical slot may alias between the sort phase and the FIN0 phase, which do
not execute concurrently):**
- Sort phase (active during magics 19 / 24 / 25 / ...):
  - `s1c[0..15]`: magic 19 prefix-sum global totals and per-bin globals
  - `s1c[16..79]`: magic 19 per-PE bin counts (64 slots = 4 PE × 16 radix
    bins); written by magic 19 step 1; read by magic 19 steps 3–4 and
    downstream scatter
  - `s1c[80..143]`: running offsets for radix scatter (written by magic 19
    step 5 as zeros; used by downstream magics 24–25)
- FIN0 phase (active during magic 15 setup → `fin0_load_batch()` → magic 18):
  - `s1c[20..23]`: FIN0 multi-pass resume state (`total_fin0`,
    `arc_data_start_hint`, `cursor`, `arc_ptr`). Physically overlaps with the
    sort-phase `s1c[16..79]` range; the phases are temporally disjoint (the
    FIN0 pipeline is drained before the next sort phase begins, and vice
    versa). Any 3a edit must not introduce cross-phase reuse.
- Magic-16 saved state (written at magic 16 entry; read by downstream sort /
  merge / dedup magics):
  - `s1c[144..155]`: `diag_base`, `n_a`, old `intv_n`, `n_phase1_v` clamped,
    `n_a` preserved, `active_intv_base`, `active_diag_base`, `next_intv_n`.
    `s1c[149..150, 154]` are reserved for sibling plans.
- `s1c[176..191]`: magic 31↔32 seam metadata (out-of-3a scope; DEC-SEAM-MERGE
  preserves it)

**Rule**: any magic that uses a slot for temp computation MUST verify that slot is
NOT live across that magic's boundary at launch-time HEAD. Use `s1c` save/restore
if a live register must be temporarily borrowed. The FIN0 / sort s1c overlap is
already safe by construction because the two phases never execute concurrently;
3a must preserve this invariant and not introduce a new cross-phase reuse.

### Validation rules
- After EACH magic (or after the grouped helper + magic-20 commit):
  `make -j ADDRESS_SANITIZER=0`; `gwfa_check_correctness.py 1 -t 56` (must pass
  15/15); `gendp-isa-reviewer` on the changed magic (zero unwaived P0/P1); one
  additive commit (no history rewrite).
- `gwfa_check_correctness.py 1 -t 56` is a full-pipeline run: every magic is
  exercised end-to-end on every test case. Any helper-body change therefore
  revalidates magic 18 automatically via the same run; no separate magic-18
  revalidation step is required after `l2dv`.
- The `l2dv` gate MUST exercise both FIN0 mask variants and both call-site
  variants via the mode-1 suite; see AC-1 positive test for the mechanism.
- At end of plan: `gwfa_check_correctness.py 2 -t 56` — must be 295/295.

---

## Goal Description

ISA-lower controller magics 16, 18, 19, and 20 on top of the post-Plan-2c
`gwfaIsaLikeAll` HEAD. Each magic is lowered one at a time with its own build +
mode-1 verify + `gendp-isa-reviewer` run + additive commit. Magic 20's rewrite
covers both the thin wrapper and the shared helper `fin0_load_batch()` whose body
supplies the real FIN0 batch-load logic; the two land as a single grouped commit
gated by `l2dv`. At end of plan, every touched magic passes the reviewer with
zero unwaived P0/P1 findings and `gwfa_check_correctness.py 2 -t 56` returns
295/295.

## Prerequisites

- Plans 1, 2a, 2b, 2c complete and merged on branch `gwfaIsaLikeAll`.
- Launch HEAD passes `gwfa_check_correctness.py 2 -t 56` = 295/295 (verified by
  task `l0`).
- Launch HEAD's `plan2c_audit_matrix.md` is the input to task `l0`'s
  absorb/defer pass for magics 16 / 18 / 19 / 20 / `fin0_load_batch()`. Open
  `fix-required` items on these magics are NOT a prerequisite blocker; `l0`
  either absorbs each into the corresponding `l2*` task or defers it with a
  recorded reason.

## Acceptance Criteria

Each AC uses TDD-style positive and negative tests. Positive tests should pass and
negative tests should be rejected when the criterion holds.

- AC-1: Correctness is preserved end-to-end on the post-Plan-2c HEAD.
  - Positive Tests:
    - `gwfa_check_correctness.py 1 -t 56` returns 15/15 after every per-magic fix,
      before that magic's commit.
    - `gwfa_check_correctness.py 2 -t 56` returns 295/295 at end of plan (task
      `l3`).
    - FIN0 shared-path coverage at `l2dv`: the mode-1 test-input set is
      confirmed (during `l0`) to drive `fin0_load_batch()` from BOTH magic-15's
      initial call AND magic-20's continuation call, across BOTH `F0A` and
      `F0B` mask variants, within the 15-case run. If analysis at `l0` shows
      any of the four (call-site × mask) combinations is not exercised, a
      targeted test input is added to the mode-1 suite or `l2dv` gates on a
      debug trace that confirms the combination ran.
  - Negative Tests:
    - Any mode-1 regression after a change blocks the magic's commit; manually
      undo or patch back the working-tree edit before retrying (no `git revert`
      / rebase / reset / amend).
    - A `l2dv` pass signed off before the four (call-site × mask) combinations
      are confirmed exercised.

- AC-2: No C++ runtime variables carry architectural state across ISA lines
  inside the four in-scope magics or inside `fin0_load_batch()`, except the
  explicit DEC-HASH-PATH carve-out.
  - Positive Tests:
    - Every C++ local inside a changed magic body or inside the helper either
      (a) is consumed on the same ISA line it is assigned, or (b) is a
      `constexpr` / loop-index / PE macro index that `gendp-isa-reviewer`
      accepts as compile-time, or (c) is inside the DEC-HASH-PATH carve-out
      described below. All other cross-ISA-line architectural state sits in
      `gr`, `reg`, `s1c`, `spm`, or `mm`.
    - The helper-local C++ mirrors `cursor`, `pe_rr`, and `dst_` are hoisted
      out of C++ locals into `gr[]` or `s1c[]` during `l2d1`.
    - DEC-HASH-PATH carve-out: the pass-3 hash block in
      `fin0_load_batch()` (the `uint32_t hk, h, b` and `int ms` computations
      that evaluate the Fibonacci-hash `×0x9E3779B9 >> 10` and derive the
      MM bucket offset) is the ONLY C++-local block allowed to cross ISA
      lines in 3a. The block MUST be annotated in-code with a cited reason
      (`// DEC-HASH-PATH carve-out: controller ISA lacks int multiply on
      gr[]; lowering deferred to 3a follow-on plan`) and MUST be narrowly
      scoped to those four values. Formal lowering (shift+add decomposition
      in `gr[]`) is the subject of a dedicated 3a follow-on plan.
  - Negative Tests:
    - Any plain C++ local assigned on one ISA line and read on a later line
      inside the same magic or helper OUTSIDE the DEC-HASH-PATH carve-out
      (e.g., pre-3a `cursor`, `pe_rr`, `dst_` must be hoisted).
    - A DEC-HASH-PATH carve-out extended beyond `hk, h, b, ms` in the
      pass-3 hash block.
    - A DEC-4-style waiver applied to anything other than
      `gwfa_sync_counters()`, `gwfa_set_ha_n_dirty()`, and
      `gwfa_get_intv_n()`.
    - DEC-4 or any other waiver applied to the hash path (only DEC-HASH-PATH
      authorizes the hash-block carve-out).

- AC-3: No runtime `if/else/for/while` in any changed magic body or in
  `fin0_load_batch()`, except approved macro unrolls and `constexpr` forms.
  - Positive Tests:
    - Every control-flow construct inside a changed magic or the helper is one
      of: a `for (int pe = 0; pe < 4; ...)` PE unroll, a compile-time-bounded
      macro expansion the reviewer accepts as fixed, or a label + conditional
      branch (goto / `bge` / `beq`).
    - Every `continue` is rewritten as a label-guarded `goto` past the body.
      Current `continue` sites to convert: magic 18 phases 2 / 3 / 4 (four
      sites) and `fin0_load_batch()` pass 2 and pass 3 (two sites).
    - The `fin0_load_batch()` `F0B_ASSIGN` macro's inner
      `for (int a_ = 0; a_ < gr[10]; a_++)` becomes a label + `bge`
      conditional branch.
  - Negative Tests:
    - Any surviving runtime `while` or `for (int i = 0; i < dynamic_bound; i++)`
      with a non-compile-time bound inside a changed magic or the helper.
    - Any surviving `continue` or `break` that depends on runtime data.
    - A multi-arm `if/else if/else` with data-dependent selection.

- AC-4: Paired VLIW slots in every changed magic are RAW-hazard free.
  - Positive Tests:
    - For each "pair of lines = one cycle" block in a changed magic, the second
      slot does not read a register written by the first slot (pre-cycle read
      semantics).
    - `gendp-isa-reviewer` reports zero paired-slot RAW findings on each
      changed magic.
  - Negative Tests:
    - Any paired-slot RAW where slot 1 reads slot 0's destination on the same
      cycle.
    - A WAW pairing (both slots write the same destination) in a changed magic.

- AC-5: SPM and S1c loads respect their documented latencies, with reordering
  preferred over naked NOP padding where reorderable work exists.
  - Positive Tests:
    - For every `... = spm[...]`, the first consumer of that destination is at
      least 2 VLIW cycles = 4 ISA lines after the load.
    - For every `... = s1c[...]`, the first consumer is at least 1 VLIW cycle =
      2 ISA lines after the load. This applies to magic 19 steps 2, 3, and 4
      (per-PE bin accumulate, per-PE prefix sum, global prefix sum) and any
      s1c load inside the helper.
    - Inside `fin0_load_batch()` pass 2 (ts_off load at the old `>> 16` site)
      and pass 3 (diag-lo/hi + arcmeta-lo/hi + arc load sites), at least one
      useful reorderable instruction fills the SPM gap where such an
      instruction is available in-scope. Each reordered gap carries a brief
      code comment naming the filler op (e.g.
      `// SPM lat 2/3 — filled by: gr[4] = gr[5] + 1`). Naked NOP padding is
      acceptable only where no independent in-scope work exists.
  - Negative Tests:
    - Any consumer reads a SPM-loaded register on the same cycle or on the
      immediately next VLIW cycle (< 4 ISA lines away).
    - Any S1c consumer reads on the same cycle (< 2 ISA lines).
    - A gap filled entirely with NOPs when the same pass contains documented
      independent work that could legally move into the gap.

- AC-6: Every MM / S2 LOAD has a `// waitLSQ` annotation and the required cycle
  separation before its first consumer.
  - Positive Tests:
    - Every MM or S2 load (`... = mm[...]`, `... = s2->buffer[...]`) in a
      changed 3a body is followed by a `// waitLSQ` annotation and at least
      one cycle of unrelated instructions (>= 2 ISA lines) before the first
      reader of the load's destination. Currently known load sites in 3a
      scope: `fin0_load_batch()` pass 2 (S2 ts_off load at
      `s2->buffer[gr[14] + gr[9]]`) and pass 3 (MM HA bucket loads at
      `mm[ms .. ms+3]`).
    - Inter-magic seam: between the magic-20 / helper invocation and magic 18
      (its dependent HA writeback), the waitLSQ is an explicit ISA
      instruction emitted by the instruction generator; this is a
      generator-output check performed during `l2dv` reviewer run, not a
      same-body annotation.
  - Negative Tests:
    - An MM/S2 load whose consumer reads the destination on the immediately
      next ISA line.
    - A consumer correctly delayed but missing the annotation (the ISA
      generator consumes the annotation to emit the LSQ-wait op — missing
      annotation = missing ISA op).
    - The AC asserted on an MM WRITE site (phase 4 of magic 18 is a writeback,
      not a load; it does not require `// waitLSQ`).

- AC-7: Bulk contiguous transfers in the changed magics and helper use `mvdq`
  (or `mvd`) round-robin across PEs; scalar `mv` only where data is
  non-contiguous.
  - Positive Tests:
    - Every contiguous-stride bulk transfer uses `mvdq_copy` or a `mvd`-shaped
      helper.
    - `fin0_load_batch()` pass 1 round-robin fast path uses `mvdq_copy` for
      diag (2-word contiguous) and arcmeta (2-word contiguous); scalar `mv` is
      restricted to the arc loop (3-word destination stride vs 2-word source
      stride) with the existing non-contiguity comment retained.
    - Magic 18 phase 4 retains the existing 4-word HA-bucket `mvd`-shaped
      sequence; no regression to scalar copy.
  - Negative Tests:
    - A scalar `for (int i = ...) { spm[...] = mm[... + i]; }` over contiguous
      data in a changed magic or helper without a cited non-contiguity
      annotation.
    - A round-robin PE loop that hits the same bank group consecutively.

- AC-8: Half-register extraction replaces `>> 16` on packed 16-bit fields inside
  `fin0_load_batch()` hot paths.
  - Positive Tests:
    - The pass-2 `gr[9] = (unsigned)gr[9] >> 16;` site and the pass-3
      `gr[3] = (unsigned)gr[3] >> 16;` site use the half-register extraction
      mechanism (reads of the high half via the half-register syntax) instead
      of an arithmetic shift ISA op.
    - Any additional packed-16-bit field extraction discovered inside the
      helper during `l2d1` is converted to half-register form when the change
      is local and low-risk; otherwise recorded as deferred with reason (per
      DEC-3 lower bound).
  - Negative Tests:
    - A post-load `>> 16` on SPM/MM-loaded data at the two named hot-path
      sites after `l2d1` lands.

- AC-9: Cross-magic register and s1c ABI is preserved; no temp use clobbers a
  live-across-boundary slot without an explicit save/restore.
  - Positive Tests:
    - Magic 16 saves `gr[20]`, `gr[24]`, and the old `intv_n` into
      `s1c[144..146, 155]` before any clamp that mutates `gr[24]`. `gr[20]`
      (diag_base), `gr[24]` (n_a), `gr[26..28]` (counters), and `gr[31]`
      (ha_n_dirty) are preserved for downstream magics where the ABI table
      says they are live.
    - Magic 19 uses only `gr[7..10]` as temps; the sort-driver live set
      `gr[1..4]` and `gr[24]` remain untouched across magic 19. `s1c[0..143]`
      writes are confined to the sort-phase slots listed in the ABI.
    - `fin0_load_batch()` preserves `gr[2]` as its continuation-flag output,
      preserves `gr[31]`, and reads-but-does-not-write `gr[29]`
      (`seq_off_s2`). The helper does not write into the sort-phase semantic
      slots — `s1c[0..15]` (sort prefix-sum globals), `s1c[16..19]` and
      `s1c[24..79]` (sort bin counts outside the FIN0-alias window), and
      `s1c[80..143]` (sort running offsets). Helper writes to
      `s1c[20..23]` are the FIN0 resume contract and are legal because the
      sort phase is drained before the FIN0 phase begins (phase-disjoint
      aliasing, per the ABI table).
    - Magic 18 preserves `gr[31]` semantics: the `gr[31] = gr[31] + 1` dirty
      counter path remains, and the trailing `gwfa_set_ha_n_dirty()` still
      sees the final count.
  - Negative Tests:
    - A new temp allocation in magic 19 that touches `gr[1..4]` or `gr[24]`.
    - A new temp allocation in the helper that clobbers `gr[26..28]` without
      save/restore.
    - A magic-16 edit that omits one of the `s1c[144..146, 155]` saves before
      mutating `gr[24]`.
    - A helper or magic 19 edit that writes into the other phase's s1c slots
      (cross-phase reuse).

- AC-10: `fin0_load_batch()` remains a void helper with explicit round-robin
  fast path and scalar fallback tail; no returned value, no bitmap bookkeeping.
  - Positive Tests:
    - `fin0_load_batch()`'s C++ signature remains `void ...(int fin0_base, int
      magic_mask)` and its continuation output stays in `gr[2]`.
    - Pass 1 keeps the round-robin common-case loop followed by a PE-outer
      scalar fallback; both exits to `s1c[22] = cursor; s1c[23] = gr[11]`
      persist the resume state.
    - Magic 15's call site (frozen) continues to invoke the helper unchanged;
      no signature or `s1c[20..23]` contract change.
  - Negative Tests:
    - A value-returning `fin0_load_batch()` shape.
    - Any bitmap-based "which PE is full" bookkeeping replacing the
      `s1c[pe] >= FIN0_N_MAX_DIAGS` / `gr[7] > FIN0_N_MAX_ARCS` guards.
    - A magic-15 edit of any kind (magic 15 is frozen).

- AC-11: `gendp-isa-reviewer` reports zero unwaived P0/P1 findings on each
  changed magic after its per-magic commit.
  - Positive Tests:
    - Reviewer summary for magic 16, 18, 19, and the magic-20 / helper pair
      shows zero unwaived P0/P1. Every listed P0/P1 is explicitly waived with
      a cited reason (e.g. sync-helper seam waiver under DEC-4).
    - P2 findings are recorded in the per-magic commit message (chosen as
      the single artifact of record for 3a) so the reviewer trail is
      complete.
  - Negative Tests:
    - A per-magic commit lands with an unwaived P0/P1 reviewer finding on the
      changed magic.
    - A P2 finding that is neither fixed nor recorded in the per-magic commit
      message.

- AC-12: Launch-gate ABI reconciliation is recorded in the plan artifacts before
  any coding commit lands.
  - Positive Tests:
    - Task `l0` records the launch-time `git rev-parse HEAD` and a line-by-line
      re-verification of the Cross-Magic Register ABI table against that HEAD;
      any drifted entries are updated in the preamble and the update commit
      precedes `l2a`.
    - Task `l0`'s output names any still-open Plan-2c `fix-required` items on
      magics 16 / 18 / 19 / 20 / `fin0_load_batch()` and either absorbs them
      into the corresponding `l2*` task or defers them to a 3a follow-on with
      a recorded reason.
    - `l0` confirms the mode-1 test-input set exercises all four FIN0
      (call-site × mask) combinations, or opens a follow-up to extend the
      input set before `l2dv`.
  - Negative Tests:
    - A `l2*` coding commit lands before `l0` has recorded the launch SHA and
      the reconciled ABI.
    - The plan proceeds with an ABI table that contradicts the launch-HEAD
      code (e.g. `gr[31]` missing, `s1c[20..23]` missing, or a slot listed as
      live that is no longer live).

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)
All four controller magics (16, 18, 19, 20) and the shared `fin0_load_batch()`
helper are rewritten to pass `gendp-isa-reviewer` with zero unwaived P0/P1
under the DEC-4 sync-helper waiver and the DEC-HASH-PATH carve-out. The ABI
table is reconciled at launch and extended to include `gr[31]`, `s1c[20..23]`
with phase-disjoint aliasing notes, `s1c[144..155]`, and any additional live
slots discovered during `l0`. `l2d1` (helper body) lands under a single grouped
commit with `l2dv` (magic 20 wrapper + reviewer). Half-register extraction
replaces every `>> 16` on packed 16-bit SPM/MM-loaded data in the helper. The
pass-3 hash block (`hk, h, b, ms`) is the ONE DEC-HASH-PATH carve-out:
annotated in-code with a cited reason and kept as C++ locals; formal
shift+add lowering is out of 3a scope. Sync-helper calls
(`gwfa_sync_counters`, `gwfa_set_ha_n_dirty`, `gwfa_get_intv_n`) are annotated
as seam-helper waivers under DEC-4 at their changed-magic call sites (magic 16,
magic 18); magic 15's call site is not annotated (frozen). End-of-plan mode 2
returns 295/295.

### Lower Bound (Minimum Acceptable Scope)
All four controller magics (16, 18, 19, 20) and `fin0_load_batch()` pass
`gendp-isa-reviewer` with zero unwaived P0/P1 under the same waiver set.
The ABI table is reconciled against launch HEAD and includes `gr[31]` +
`s1c[20..23]` + phase-aliasing note. Every `continue` inside magic 18 and
inside the helper is converted to a label + goto. Every MM/S2 LOAD has a
`// waitLSQ` annotation and the required cycle separation. Half-register
extraction is applied to the two flagged hot-path `>> 16` sites. The
pass-3 hash block is kept under the DEC-HASH-PATH carve-out with its
cited in-code reason (not covered by DEC-4); `hk, h, b, ms` stay as C++
locals for 3a. Additional half-register conversions that are not
local-and-low-risk are allowed to defer to a follow-on with a recorded
reason. End-of-plan mode 2 returns 295/295.

### Allowed Choices
- **Can use**: per-magic commits; `l2d1 + l2dv` lands as a single grouped commit
  with a subject enumerating both "ISA-lower fin0_load_batch" and "ISA-lower
  magic 20 wrapper"; `gendp-isa-reviewer` P2 suppressions with recorded
  rationale in the commit message; macro-style PE unrolls; `constexpr`;
  half-registers; `mvdq_copy` / `mvd`-shaped helpers.
- **Cannot use**: runtime `if/else/for/while` inside changed magic bodies or
  inside `fin0_load_batch()` except approved macro forms; `std::min`/`std::max`
  on the controller; nested indirect memory reads (`mm[s1c[X]]` or
  `mm[gr[s1c[X]]]`) in executable logic; helpers that hide live architectural
  state in C++ locals; edits to magic 15 or any reference-example magic; DEC-4
  waivers applied to anything other than the three named sync helpers; `git`
  commands that modify history (rebase / reset / amend / force-push /
  cherry-pick-drop / `git revert`); skipping `gendp-isa-reviewer` on a changed
  magic.

> **Note on Deterministic Designs**: The 12 rules plus the reference-example
> magics anchor a highly deterministic lowering target. Upper and lower bounds
> differ only in whether half-register conversion is applied beyond the two
> named hot-path sites. The pass-3 hash-path deferral under DEC-HASH-PATH is
> FIXED for both bounds (user-confirmed): `hk, h, b, ms` stay as C++ locals
> in 3a with the cited carve-out annotation; formal shift+add lowering is
> the subject of a follow-on plan. AC coverage and per-magic reviewer cadence
> are fixed.

## Feasibility Hints and Suggestions

> **Note**: Conceptual suggestions only.

### Conceptual Approach

1. **Launch gate** (`l0`, analyze): Record `git rev-parse HEAD`, run
   `gwfa_check_correctness.py 2 -t 56 = 295/295` on that SHA, and re-verify the
   Cross-Magic Register ABI table against the launch-HEAD code (especially
   `gr[31]`, `s1c[20..23]`, `s1c[144..155]`). Absorb or defer any still-open
   Plan-2c `fix-required` items on magics 16 / 18 / 19 / 20 /
   `fin0_load_batch()`. Confirm the mode-1 test-input set exercises all four
   FIN0 (call-site × mask) combinations, or open a follow-up to extend it
   before `l2dv`. Commit the reconciled ABI as a plan-artifact-only commit.

2. **ABI extension and clobber audit** (`l1`, analyze): Walk the Cross-Magic
   Register ABI table against the post-2c codebase; identify every `gr[]` /
   `s1c[]` slot read or written by magics 16 / 18 / 19 / 20 /
   `fin0_load_batch()`; classify each as live-in, live-out, temp, or seam
   slot; cross-reference the `BL-20260413-gr-clobber` bitlesson (inline in
   Plan 1; `gr` save/restore via `s1c` on clobber). Output: a phase-scoped
   liveness appendix in this plan file and a per-magic "temp set" for the
   coding tasks.

3. **Magic 16 lowering** (`l2a` → `l2av`): Magic 16 is already mostly
   ISA-lowered in Plan 1 (goto clamp, constexpr caps). Remaining work: verify
   the `s1c[144..146, 155]` saves precede the clamp-mutation; verify VLIW
   pairs and paired-slot RAW freedom; add any missing SPM / s1c latency gaps.
   `gwfa_sync_counters()` call at magic 16's entry is annotated
   `// seam-helper-waived (DEC-4)`. Build, mode 1, reviewer, commit.

4. **Magic 18 lowering** (`l2b` → `l2bv`): Convert all four `continue` sites
   (phase 2, phase 3, phase 4 dirty skip, phase 4 bucket skip) to label +
   goto. Unpack any grouped multi-action lines (reconfirm at launch). Verify
   MM WRITES in phases 2 / 3 / 4 respect their latency but do NOT require
   `// waitLSQ` (writes are not subject to AC-6). Preserve `gr[31]` dirty
   counter and the trailing `gwfa_set_ha_n_dirty()` seam waiver
   (`// seam-helper-waived (DEC-4)`). Build, mode 1, reviewer, commit.

5. **Magic 19 lowering** (`l2c` → `l2cv`): Magic 19 is already partially
   lowered in Plan 1 (`gr[7..10]` temps, SPM 3-NOP settles, goto/pair
   cleanup). Remaining work: verify the step-6 reset-bin-counts loop stays
   PE-inner for bank rotation; confirm the step-2 s1c accumulate 1-cycle gap
   holds across all 16 radix bins × 4 PEs; confirm step-3 per-PE prefix-sum
   and step-4 global prefix-sum s1c-load-to-consumer gaps also hold;
   verify no `gr[1..4]` / `gr[24]` clobber. Build, mode 1, reviewer, commit.

6. **Magic 20 helper rewrite** (`l2d1`, edit-only; no commit): Inside
   `fin0_load_batch()`:
   - Replace the pass-1 `cursor` C++ local with `s1c[22]` load/store on each
     access or with a reserved `gr[]` slot restored at exit; the value is
     persisted to `s1c[22]` already, so the only change is the in-helper
     lifetime.
   - Replace `pe_rr` with a register/constant-rotation pattern (PE index
     derived from `cursor & 3` rather than a C++ local).
   - Replace the `F0B_ASSIGN` macro body's runtime
     `for (int a_ = 0; a_ < gr[10]; a_++)` with a label + `bge` / `goto`;
     move `dst_` into `gr[]`.
   - Replace the pass-2 and pass-3 `>> 16` sites with half-register
     extraction (DEC-3).
   - Leave the pass-3 hash locals `hk, h, b, ms` under the DEC-HASH-PATH
     carve-out (user-confirmed defer): annotate the block with
     `// DEC-HASH-PATH carve-out: controller ISA lacks int multiply on`
     `// gr[]; lowering deferred to 3a follow-on plan` and keep the C++
     arithmetic. Formal shift+add lowering is out of 3a scope.
   - Convert both pass-2 and pass-3 `continue` sites to goto + label.
   - Reorder ISA ops where possible so the 2-cycle SPM gap at pass-2 ts_off
     load and pass-3 diag / arcmeta / arc loads is filled with useful work;
     each reordered gap carries a brief comment naming the filler op (per
     AC-5). The existing Plan 2b AC-11 note documents which chains already
     satisfy the 3-intervening-op minimum — keep those intact, only reorder
     where NOP padding exists today and useful work is available.
   - Preserve `s1c[20..23]` resume contract and `gr[2]` continuation output
     verbatim.

7. **Magic 20 / helper verify + grouped commit** (`l2dv`): Build + mode 1 (full
   15/15 -t 56, which exercises both FIN0 mask variants and both call sites
   per AC-1 positive test and `l0`'s test-input confirmation) + reviewer on
   BOTH `fin0_load_batch()` AND magic 20 wrapper (wrapper is effectively
   unchanged but the reviewer runs on the file region regardless) + inter-magic
   waitLSQ check in the instruction-generator output + single grouped commit.

8. **Final verification** (`l3`): `gwfa_check_correctness.py 2 -t 56` = 295/295.
   DEC-HASH-PATH is resolved upstream in the Decision Log as a 3a-follow-on
   deferral and does NOT require closeout at `l3`. Any OTHER deferred items
   that `l0` recorded (e.g., non-trivial half-register conversions per
   DEC-3) are closed or re-deferred here with rationale.

### Relevant References

- `pe_array.cpp` — magic bodies on current HEAD:
  - magic 15 (FROZEN) at the FIN0 init section that calls `fin0_load_batch()`
  - magic 16 at the sort-setup block (`gwfa_sync_counters`, s1c save, clamp)
  - magic 18 at the FIN0 writeback block (phases 1–5 + `gwfa_sync_counters` +
    `gwfa_set_ha_n_dirty`)
  - magic 19 at the sort prefix-sum block (steps 1–6)
  - magic 20 at the FIN0 continuation-call wrapper
  - `fin0_load_batch()` (passes 1–4: assignment, S2 ts_off, MM HA, metadata)
- `pe.cpp` — PE magic bodies (referenced by s1c layout; no edits here in 3a).
- `scripts/gwfa_instruction_generator.py` — sort-loop driver (governs the
  `gr[1..4], gr[24]` live set across the sort pipeline).
- `isaLikeAllGwfaPrompt.md` — governing prompt; the magic-18 / magic-19 /
  magic-20 / magic-23 specific notes; half-register guidance; `>> 16`
  critique.
- `isaLikeAllGwfaPlan1.md` / `isaLikeAllGwfaPlan1H.md` — prior ISA-lowering of
  magic 16 / 19 / 39; `BL-20260413-gr-clobber` bitlesson lives inline here.
- `isaLikeAllGwfaPlan2aH.md` / `isaLikeAllGwfaPlan2bH.md` /
  `isaLikeAllGwfaPlan2cH.md` — inherited invariants (DEC-SPM-MODEL,
  DEC-COMMIT, DEC-SEAM-MERGE, Plan 2b AC-11 SPM latency audit).
- `plan2c_audit_matrix.md` — sibling matrix; the 2c per-magic dispositions on
  magics 16 / 18 / 19 / 20 / `fin0_load_batch()` inform `l0`'s reconciliation.
- `CLAUDE.md` — canonical SPM latency + VLIW hazard rules +
  history-modification prohibition; `docs.md` — full ISA manual.
- Memory entry `feedback_spm_cycle_accounting.md` — consumer cycle must be
  load-cycle + 2; pair alignment within magic body matters.

## Dependencies and Sequence

### Milestones

1. **Milestone A: Launch gate + ABI reconciliation**
   - Phase A1 (`l0`): Record launch SHA; re-run mode 2 = 295/295 on that SHA;
     reconcile Cross-Magic Register ABI table against post-2c HEAD; confirm
     FIN0 test-input coverage; absorb/defer open 2c items.
   - Phase A2 (`l1`): Phase-scoped liveness appendix + per-magic temp sets
     (analyze).

2. **Milestone B: Per-magic ISA lowering**
   - Step B1 (`l2a` + `l2av`): Magic 16 lower + verify + commit.
   - Step B2 (`l2b` + `l2bv`): Magic 18 lower + verify + commit.
   - Step B3 (`l2c` + `l2cv`): Magic 19 lower + verify + commit.
   - Step B4 (`l2d1` + `l2dv`): `fin0_load_batch()` helper body rewrite +
     magic 20 wrapper reviewer + mode 1 on full suite (covers both `F0A` /
     `F0B` and both call sites) + single grouped commit.

3. **Milestone C: Final verification**
   - Step C1 (`l3`): `gwfa_check_correctness.py 2 -t 56` = 295/295. The
     DEC-HASH-PATH carve-out does NOT require closeout at `l3` — it is
     resolved in the Decision Log as an explicit 3a-follow-on deferral,
     not an open item. Any OTHER deferred items recorded during `l0`
     (e.g., non-trivial half-register sites) are closed or re-deferred
     here with rationale.

Dependencies: A1 → A2 → B1 → B2 → B3 → B4 → C1. Within B, each per-magic
commit is a linear-chain rollback point. Mode 1 is a full-pipeline run, so
any helper-body change (B4) automatically revalidates magic 18's (B2) path on
the same mode-1 run — no separate post-B4 magic-18 revalidation step is
needed.

## Task Breakdown

Each `coding` row's pre-commit stage (`l2a`, `l2b`, `l2c`, `l2d1`) is
edit-only; the matching `l2*v` stage runs build + mode-1 verify + reviewer +
commit. `l2d1 + l2dv` lands as one grouped commit. `analyze` tasks commit
plan-artifact updates only (no `pe_array.cpp` change unless the ABI
reconciliation itself requires one, e.g. a typo or drifted constant).

| Task ID | Description                                                                                                                                                         | Target AC                | Tag     | Depends On |
|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|---------|------------|
| l0      | Launch gate: record `git rev-parse HEAD`; run `gwfa_check_correctness.py 2 -t 56 = 295/295`; reconcile Cross-Magic Register ABI; confirm FIN0 test-input coverage (all 4 call-site × mask combinations — targeted dataset if the 15-case default misses any); absorb/defer open 2c items. DEC-HASH-PATH is already resolved (defer) in the Decision Log. | AC-1, AC-2, AC-12      | analyze | -          |
| l1      | Phase-scoped liveness appendix + per-magic temp sets; cross-ref `BL-20260413-gr-clobber`; extend Cross-Magic Register ABI for magics 16 / 18 / 19 / 20 + `fin0_load_batch()`                                                                          | AC-9, AC-12              | analyze | l0         |
| l2a     | ISA-lower magic 16 (edit-only): verify `s1c[144..146, 155]` saves precede the clamp; VLIW-pair check; SPM / s1c latency gaps; `gwfa_sync_counters()` annotated `// seam-helper-waived (DEC-4)`                                                        | AC-2..AC-5, AC-9         | coding  | l1         |
| l2av    | Build + `gwfa_check_correctness.py 1 -t 56 = 15/15` + `gendp-isa-reviewer` on magic 16 + per-magic additive commit                                                                                                                                    | AC-1, AC-11              | coding  | l2a        |
| l2b     | ISA-lower magic 18 (edit-only): rewrite all four `continue` sites as label + goto; verify MM WRITE latency in phases 2/3/4 (no waitLSQ required for writes); preserve `gr[31]` + `gwfa_set_ha_n_dirty()` seam waiver                                   | AC-2..AC-5, AC-9         | coding  | l2av       |
| l2bv    | Build + mode 1 + `gendp-isa-reviewer` on magic 18 + per-magic commit                                                                                                                                                                                  | AC-1, AC-11              | coding  | l2b        |
| l2c     | ISA-lower magic 19 (edit-only): confirm `gr[7..10]` temp set; verify step-2 / step-3 / step-4 s1c 1-cycle gaps hold; step-6 reset loop stays PE-inner; no `gr[1..4]` / `gr[24]` clobber                                                               | AC-2..AC-5, AC-9         | coding  | l2bv       |
| l2cv    | Build + mode 1 + `gendp-isa-reviewer` on magic 19 + per-magic commit                                                                                                                                                                                  | AC-1, AC-11              | coding  | l2c        |
| l2d1    | Rewrite `fin0_load_batch()` body (edit-only): hoist C++ locals `cursor`, `pe_rr`, `dst_` to `gr[]`/`s1c[]`; rewrite macro inner loop + two `continue` sites as label + goto; half-register for the two `>> 16` hot paths (sign-ext `GR_HI` + `andi 0xFFFF`); pass-3 `hk/h/b/ms` block kept as DEC-HASH-PATH carve-out with cited in-code annotation (deferred to 3a follow-on plan) | AC-2..AC-8, AC-9, AC-10 | coding | l2cv |
| l2dv    | Build + mode 1 -t 56 (full suite; the four FIN0 call-site × mask combinations are exercised per the coverage confirmed or extended at `l0`) + `gendp-isa-reviewer` on `fin0_load_batch()` AND magic 20 wrapper + instruction-generator waitLSQ check + single grouped commit | AC-1, AC-6, AC-10, AC-11 | coding  | l2d1       |
| l3      | Final verification: `gwfa_check_correctness.py 2 -t 56 = 295/295`; final plan report. DEC-HASH-PATH is NOT a closeout item — it is resolved upstream (defer) in the Decision Log. Any OTHER deferred items from `l0` are closed or re-deferred here with rationale. | AC-1                     | coding  | l2dv       |

## Claude-Codex Deliberation

### Agreements
- Magic 16 and magic 19 are already partially ISA-lowered in Plan 1; the 3a
  work on them is pairing / latency / ABI verification plus any leftover
  `continue` / locals cleanup. Neither is a from-scratch rewrite.
- The Cross-Magic Register ABI table is the central artifact that must be
  reconciled before any coding commit. `gr[31]` (ha_n_dirty), `s1c[20..23]`
  (FIN0 resume) modeled with explicit phase-disjoint aliasing, and
  `s1c[144..155]` (magic-16 save state) belong in the table.
- `fin0_load_batch()` body rewrite is the real work behind magic 20; the
  wrapper magic 20 is a thin caller. The task breakdown splits magic 20 into
  `l2d1` (helper edit) + `l2dv` (grouped verify + commit covering wrapper +
  helper).
- Magic 18 is not merely "add NOP gaps": its four `continue` sites violate
  rule 3/4 and must become label + goto. Phase 2 / 3 / 4 are MM WRITEs (not
  loads), so they do NOT require `// waitLSQ`; AC-6 is scoped to MM/S2 LOADS
  only, which in 3a live inside `fin0_load_batch()` pass 2 (S2 ts_off) and
  pass 3 (MM HA bucket) plus the inter-magic seam between magic 20 and magic
  18.
- `gwfa_sync_counters()`, `gwfa_set_ha_n_dirty()`, and `gwfa_get_intv_n()` are
  seam helpers that will be lowered in a later plan; 3a waives them under
  DEC-4 with a `// seam-helper-waived (DEC-4)` annotation at each CHANGED
  call site only (magic 16 and magic 18); magic 15's frozen call site is not
  touched.
- Half-register extraction is mandatory on the two flagged `>> 16` sites in
  the helper; additional conversions are an upper-bound item (DEC-3
  resolution limits the lower bound to the two named sites).
- Per-magic reviewer cadence: reviewer runs immediately after each magic's
  coding task, before commit. `l2d1 + l2dv` is a single grouped commit.
- Mode-1 is full-pipeline. A mode-1 pass at `l2dv` revalidates magic 18's
  consumption of the helper's output automatically; no separate magic-18
  re-run is scheduled.

### Resolved Disagreements (Claude ↔ Codex, pre-user)

These are items where Claude and Codex converged during Phase 3–5 without
requiring user input. Items that are genuinely user decisions (DEC-1..DEC-4,
DEC-CORRECTNESS-BAR, DEC-HASH-PATH) are recorded in the Decision Log at the
top of this plan with their resolutions and are NOT listed here.

- **Magic 20 granularity** (structural, no user decision): Codex round 1
  pushed for splitting `l2d` into helper-pass tasks (pass 1 / pass 2 /
  pass 3 / pass 4). Resolution: split into `l2d1` (helper body, all passes,
  edit-only) and `l2dv` (wrapper reviewer + grouped commit). Per-pass
  splitting is rejected because helper correctness is end-to-end tested via
  full-pipeline mode 1 and per-pass commits would fragment the reviewer's
  view.
- **Magic 15 editability** (structural): Codex asked whether magic 15 is
  in-scope for the FIN0 pipeline work. Resolution: magic 15 is FROZEN. Only
  the helper body and magic 20's wrapper are edited.
- **`gr[31]` ABI entry**: Codex flagged `gr[31]` as missing from the draft's
  ABI excerpt. Resolution: added with explicit boundary-crossing notes for
  magic-15 init → magic-18 phase 4 → magic-18 trailing commit.
- **ABI for `s1c[]`**: Codex asked whether the ABI table should cover
  `s1c[]`. Resolution: added `s1c[]` subsection with phase-disjoint aliasing
  for `s1c[16..79]` (sort phase) vs `s1c[20..23]` (FIN0 phase). AC-9
  negative tests define the legal helper-write set explicitly.
- **AC for reordering-over-padding**: Codex pushed for AC-5 to prefer
  reordering over NOP padding. Resolution: AC-5 positive test prefers
  reorder when independent work exists; each reordered gap carries a brief
  filler-op comment.
- **AC for FIN0 shared-path verification**: Codex asked for explicit
  coverage of both `F0A` / `F0B` and both magic-15 / magic-20 call variants.
  Resolution: AC-1 positive test requires `l0` to confirm test-input
  coverage (or extend the input set / require a debug trace); `l2dv` mode 1
  exercises all four combinations only after that confirmation.
- **MM waitLSQ misstatement**: Codex round-1 flagged the original plan's
  claim that magic 18 phase 4 had MM LOADS requiring waitLSQ. In current
  code, phase 4 has MM WRITES; MM reads are confined to the helper pass 3.
  Resolution: AC-6, `l2b` task text, and the conceptual magic-18 step scope
  waitLSQ to LOADS only (helper pass 2 S2 load, helper pass 3 MM HA-bucket
  loads) plus the inter-magic seam between magic 20 and magic 18 as a
  generator-output check.
- **Prerequisites blocking**: Codex flagged the "zero unwaived fix-required
  at launch" prerequisite as contradictory with `l0`'s absorb/defer role.
  Resolution: prerequisites now say `l0` owns the absorb/defer pass; launch
  HEAD is only required to pass mode 2 = 295/295.
- **AC-2 hash-path disposition**: Codex flagged AC-2's original allowance
  for the pass-3 hash locals to be waived under DEC-4. Resolution: DEC-4
  does not cover the hash path. The hash block is governed by its own
  DEC-HASH-PATH entry (user-confirmed 2026-04-22: defer `hk, h, b, ms`
  to a 3a follow-on plan because the controller ISA has no integer-
  multiply opcode on `gr[]` and the ~50-70-line shift+add emulation
  adds substantial register pressure for uncertain 3a scope benefit).
  The Round-2 and Round-3 reviewer pushback to force full in-controller
  lowering was explicitly declined by the user; the defer stance
  stands.
- **Magic 19 step coverage**: Codex flagged that `l2c` originally named
  only step 2 and step 6. Resolution: `l2c` and AC-5 now explicitly cover
  steps 2, 3, 4 (s1c 1-cycle gaps) plus step 6 (PE-inner reset).
- **AC-7 target scope**: Codex suggested magic 19 is not a bulk-transfer
  path and should not target AC-7. Resolution: `l2c` targets removed AC-7;
  the target-AC column reads `AC-2..AC-5, AC-9` for `l2c`.
- **P2 artifact of record**: Codex flagged AC-11 as ambiguous between commit
  message and audit matrix. Resolution: commit message is the single
  artifact of record for 3a P2 bookkeeping; DEC-HASH-PATH is resolved in
  the Decision Log (defer) and has no ongoing pending-decision row.
- **Commit policy for `l2d1`**: Codex flagged ambiguity. Resolution: `l2d1`
  is edit-only; `l2dv` is the sole commit for the helper + wrapper change.
- **`gr[7]` clarification**: Codex suggested removing `gr[7]` from the live
  list. Resolution: moved to "Known magic-local temps" subsection for
  disambiguation.
- **AC-9 sort-phase write ban precision**: Codex round-2 flagged that AC-9's
  "does not write into `s1c[16..79]`" literally forbade the legal
  `s1c[20..23]` FIN0-alias writes. Resolution: AC-9 positive test now names
  `s1c[0..15]`, `s1c[16..19]` ∪ `s1c[24..79]`, and `s1c[80..143]` as the
  banned sort-phase semantic slots and explicitly permits the
  `s1c[20..23]` FIN0 resume writes.

### User Decisions Resolved

All six plan-3a-local decisions (DEC-1 launch-gate, DEC-2 helper scope,
DEC-3 half-register extent, DEC-4 sync-helper waiver, DEC-CORRECTNESS-BAR,
DEC-HASH-PATH) are resolved and recorded in the Decision Log at the top
of this file. The first five were resolved during Phase 6 in favor of the
Claude-recommended positions; DEC-HASH-PATH was resolved on 2026-04-22
(defer to 3a follow-on) after an initial l0 Codex analyze confirmed the
controller ISA has no integer-multiply opcode on `gr[]`, with the defer
stance re-confirmed after Round-2 and Round-3 reviewer pushback.

### Convergence Status
- Final Status: `converged`. Six planning decisions (DEC-1..DEC-4 +
  DEC-CORRECTNESS-BAR + DEC-HASH-PATH) are resolved and no pending user
  input remains. The hash-path deferral is accepted as a narrow, cited
  carve-out of AC-2; a dedicated 3a follow-on plan is expected to
  formally lower the `×0x9E3779B9` Fibonacci multiply when the time
  comes.

## Pending User Decisions

All plan-3a planning-level decisions are resolved and recorded in the
Decision Log at the top of this file. No decisions remain open.

## Implementation Notes

### Code Style Requirements
- Implementation code and comments must NOT contain plan-specific terminology
  such as "AC-", "Milestone", "Step", "Phase", or similar workflow markers.
- These terms are for this plan document only, not for the resulting codebase.
- Use descriptive, domain-appropriate naming. Preserve the `// waitLSQ` and
  SPM-NOP annotation conventions already established in Plans 1, 2a, 2b, 2c.
- When waiving a seam helper call (sync / dirty-count / intv-n), annotate the
  call site with `// seam-helper-waived (DEC-4)` and nothing else. Apply only
  at CHANGED call sites (magic 16, magic 18); magic 15's frozen call site is
  not annotated.
- The pass-3 hash block in `fin0_load_batch()` is the sole DEC-HASH-PATH
  carve-out and must carry the annotation
  `// DEC-HASH-PATH carve-out: controller ISA lacks int multiply on gr[];`
  `// lowering deferred to 3a follow-on plan`
  at the top of the block. The annotation itself is the marker the reviewer
  uses to accept the carve-out; no other annotation form authorizes C++
  locals to cross ISA lines in 3a.

--- Original Design Draft Start ---

NOTE! when generating the plan, keep in mind that 2cH has not finished yet. We are generating this
plan ahead of time so we are prepared to launch as soon as it does finish, but that means the
codebase might change a bit in between
# GWFA ISA-Like Rewrite Plan 3a: ISA Lower Controller 16-20

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

This section documents which gr[] registers are live across magic boundaries in the instruction generator. All ISA lowering plans MUST consult this before allocating registers. Task l1 in this plan creates the initial version; subsequent plans (3b/3c/3d) extend it.

**Known live registers across magic boundaries:**
- gr[1]: sort pass number (live across 34→19→24/25 sequence)
- gr[2]: sort/merge/dedup cursor (live across tile load→PE→writeback→reload loops)
- gr[3]: MM source base (live across sort loop)
- gr[4]: MM destination base (live across sort/merge/dedup loops)
- gr[6]: loop bound (live across tile load→PE→writeback→reload loops)
- gr[7]: used by 19 prefix-sum (NOT live across boundary — temp only within magic 19)
- gr[20]: diag_base (live from phase 1 into magic 16)
- gr[24]: n_a / n_unsorted (live across sort/merge/dedup pipeline)
- gr[26]-gr[28]: counters (live across FIN0 pipeline)
- gr[29]: seq_off_s2 (live across fin0_load_batch passes)

**Rule**: Any magic that uses gr[X] for temporary computation must verify gr[X] is NOT live across that magic's boundary in the instruction generator. Use s1c for save/restore if needed.

---

## Goal Description

ISA-lower controller magics 16, 18, 19, 20. Each lowered, verified, and ISA-reviewed individually.

## Prerequisites

Plans 1+2a+2b+2c complete. All structural rewrites and compliance done. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after EACH magic, mode 2 at end)
- AC-2: No C++ runtime variables
- AC-3: No runtime if/else/for/while (only gotos + macro loops)
- AC-4: VLIW pairing, no RAW hazards (ISA reviewer per magic)
- AC-5: Latency gaps and waitLSQ comments present

## Task Breakdown

| Task ID | Description | Tag |
|---------|-------------|-----|
| l1 | Plan register allocation for magics 16-20. Document which gr[] are live across each magic boundary. Extend the Cross-Magic Register ABI section. Use BL-20260413-gr-clobber. | analyze |
| l2a | ISA-lower controller 16: all locals→gr, if→goto, division→shift. Keep gwfa_sync_counters as-is. | coding |
| l2av | Verify + ISA review controller 16 | coding |
| l2b | ISA-lower controller 18: already mostly ISA-like. Verify VLIW pairing, add NOP gaps. | coding |
| l2bv | Verify + ISA review controller 18 | coding |
| l2c | ISA-lower controller 19: all locals→gr[7-10], verify macro loops bounded. Partially lowered in Plan 1. | coding |
| l2cv | Verify + ISA review controller 19 | coding |
| l2d | ISA-lower controller 20: F0B_ASSIGN body→register ops, for loops→goto/macro, SPM latency gaps. | coding |
| l2dv | Verify + ISA review controller 20 | coding |
| l3 | Full verification: mode 2 -t 56 | coding |

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---

--- Original Design Draft End ---
