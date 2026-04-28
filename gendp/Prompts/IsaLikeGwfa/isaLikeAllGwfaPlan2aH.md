# GWFA ISA-Like Rewrite Plan 2a: Controller Structural Residuals (20/31/32)

## Goal Description

Complete the remaining structural ISA-like rewrites for Controller magics 20, 31, and 32 in
`pe_array.cpp`, so that each magic is one step closer to a direct lowering to GenDP ISA:
- Magic 20 (`fin0_load_batch`): converts contiguous diag/arcmeta copies to `mvdq` round-robin
  form, replaces `>>16` extraction with half-register views *only where the source field is
  unsigned-16 and does not need zero-extension* (the arc `w` field is `uint16_t` — see
  DEC-HALFREG-SIGN; the rewrite preserves zero-extension semantics), and masks SPM 2-cycle
  latency by reordering loads and their first consumers.
- Magic 31 (dedup writeback): replaces `base + offset` destination recomputation with
  pre-computed per-PE cursors that autoincrement, and additionally materializes per-PE seam
  metadata (first/last intv per PE) into `s1c` per the DEC-SEAM-MERGE reinterpretation so
  magic 32 can merge boundaries without MM loads.
- Magic 32 (dedup finalize): consumes the seam metadata from `s1c` (no MM reads) for
  boundary merge, keeps the PE-serial bulk `mvdq` interior copy, and clears the seam
  metadata slots during its existing `s1c` reset.

Correctness is preserved under GWFA mode 1 -t 56 after each magic change and 295/295 under
GWFA mode 2 -t 56 at plan end. `gendp-isa-reviewer` is invoked after each commit and its
findings are explicitly dispositioned. The rewrite is structural only — PE compute ops are
deferred to a future plan.

## Acceptance Criteria

Following TDD philosophy, each criterion lists positive tests (expected to PASS) and
negative tests (expected to FAIL when the criterion is violated).

- AC-1: Per-magic correctness — after each of magic 20, 31, 32 is changed and committed,
  `make -j ADDRESS_SANITIZER=0` succeeds and `python3 scripts/gwfa_check_correctness.py 1
  -t 56` returns 15/15.
  - AC-1.1: Magic 20
    - Positive Tests: mode 1 -t 56 returns 15/15 after the magic-20 commit; `make` succeeds
      with no new warnings.
    - Negative Tests: if any of the 15 fin0-exercising cases regresses (mismatch on
      diag/arcmeta/arcs content, wrong `n_diags`/`n_arcs`, or `gr[2]` overflow flag
      desynced), the commit is rejected.
  - AC-1.2: Magic 31
    - Positive Tests: mode 1 -t 56 returns 15/15 after the magic-31 commit; `s1c[20+pe]` and
      `s1c[28+pe]` post-update values match the pre-change run for every tile.
    - Negative Tests: if per-PE diag/intv chunk writeback is off by one element, or if a
      zero-cnt PE perturbs neighboring PE writes, the commit is rejected.
  - AC-1.3: Magic 32
    - Positive Tests: mode 1 -t 56 returns 15/15 after the magic-32 commit; `n_a_final`,
      `intv_n`, `s1c[152]`, and `s1c[153]` match the pre-change run across all 15 cases.
    - Negative Tests: if seam merge loses an element, double-counts a boundary element, or
      keeps stale seam metadata across cases, the commit is rejected.

- AC-2: End-of-plan mode 2 blocker — `python3 scripts/gwfa_check_correctness.py 2 -t 56`
  returns 295/295 after `s_fin`.
  - Positive Tests: command reports 295/295 with all three commits landed.
  - Negative Tests: any score below 295/295 at plan end rejects the plan (per
    DEC-MODE2-BLOCKER = hard blocker, user-confirmed 2026-04-17).

- AC-3: ISA-review clean per magic — after each magic commit, `gendp-isa-reviewer` is run
  against only the changed code region, its report is recorded in the plan's QA ledger,
  and every flagged item is either fixed or given an explicit written disposition signed by
  the human reviewer (user arbitrates per DEC-REVIEWER-ARBITER).
  - Positive Tests: the ledger for each magic shows a list of findings with disposition =
    `fixed`, `exception-approved`, or `false-positive-confirmed`, and every fix has a
    follow-up commit that still passes AC-1 for that magic.
  - Negative Tests: a ledger with open/unresolved findings fails AC-3; an unrecorded
    reviewer run fails AC-3.

- AC-4: SPM latency masking in magic 20 — every controller SPM load-to-first-use chain in
  magic 20 is enumerated in the plan note and each chain has a rule-compliant 2-cycle gap
  or a direct non-consuming pass-through (see rule 6 of ISA-like rules).

  **RETROACTIVE CLARIFICATION (2026-04-20, updated)**: The original Plan 2a AC-4 wording
  left the cycle-accounting convention implicit. During Plan 2b generation the user
  provided the authoritative convention, which is:

  - Each line of ISA-like code in `pe_array.cpp` controller magic bodies represents
    **one gendp ISA instruction** (one slot of a VLIW pair), NOT one full VLIW cycle.
  - Each pair of consecutive lines = **one VLIW cycle** (slot 0 + slot 1). A blank
    line typically separates one pair from the next but is not required in existing
    code; when absent, pair boundaries are inferred from a known alignment point
    (the first instruction of the magic body).
  - "SPM 2-cycle latency" = load issued in cycle N; data received at END of cycle N+1
    (the in-flight cycle); earliest legal consumer is in cycle N+2.
  - Equivalently, if the load is ins1 or ins2 of its pair (cycle N), then ins1,
    ins2, ins3, ins4 CANNOT consume the load. ins5 or ins6 (cycle N+2) CAN consume.
  - The clean rule: **consumer's VLIW cycle must be >= load's VLIW cycle + 2.**

  Implication for Plan 2a's implementation: the 2-NOP pattern in `pe_array.cpp`
  around line 500-503 is LEGAL or ILLEGAL depending on pair alignment:
  - If the SPM load lands in slot 1 of its pair (cycle N slot 1 = load; cycle N+1
    slots 0+1 = 2 NOPs; cycle N+2 slot 0 = consumer), the 2-NOP gap is legal.
  - If the SPM load lands in slot 0 of its pair (cycle N slot 0 = load; cycle N
    slot 1 + cycle N+1 slot 0 = 2 NOPs; cycle N+1 slot 1 = consumer IN-FLIGHT),
    the 2-NOP gap is ILLEGAL.

  Plan 2a's code happens to pass mode 2 -t 56 = 295/295 in simulation because the
  magic body's C++ `spm[...]` access executes synchronously in the simulator — the
  cycle-latency rule is a static-analysis / real-HW-lowering constraint, not a
  runtime check. A per-chain audit is required to determine which Plan 2a chains
  are latently broken under the correct rule and which are correctly aligned.

  Plan 2b Milestone F (AC-11) performs that audit and applies per-chain fixes
  (add NOP, reshuffle for slot-1 alignment, or replace NOP with useful work).

  - Positive Tests: a table in the magic-20 QA note lists every `spm[...]` load
    inside magic 20 with the first consuming instruction and its VLIW-cycle
    alignment; each chain is classified LEGAL or ILLEGAL under the corrected rule.
  - Negative Tests: any listed chain whose consumer shares the load's VLIW cycle
    or falls in the immediately following (in-flight) cycle fails AC-4; any SPM
    load that is not enumerated fails AC-4. (Historical note: the original Plan 2a
    wording here said "0- or 1-cycle gap fails". Under the corrected convention
    that wording is ambiguous — "cycle" was not explicitly tied to a VLIW cycle —
    and the implementation reading it chose a 2-NOP pattern that is correctness-
    dependent on pair alignment. Plan 2b's AC-11 + Milestone F address this.)

- AC-5: Bulk transfer rule — magic 20 uses `mvdq`-shape copies (in the C++ helper
  `mvdq_copy`) for the diag (2-word contiguous) and arcmeta (2-word contiguous) payloads,
  and magic 31 uses chunk-outer / PE-inner `mvdq_copy` for both diag writeback and intv
  writeback. Scalar copy remains for the stride-3 arc payload in magic 20 (DEC-M20-ARCS
  default = "keep stride-3 arcs scalar").
  - Positive Tests: `grep -n mvdq_copy pe_array.cpp` inside the magic-20 body shows at
    least one call for diag copy and one for arcmeta copy per PE per iteration; the magic-
    31 body has a diag-streaming `mvdq_copy` loop and an intv-streaming `mvdq_copy` loop.
  - Negative Tests: the magic-20 diag or arcmeta payload still reaching MM/SPM via scalar
    `spm[...] = s1c[...]` element-wise, where contiguous 2-word chunks were available,
    fails AC-5. A magic-31 writeback path that regresses to scalar `mm[...] = spm[...]`
    fails AC-5.

- AC-6: Zero-extension preserved for unsigned 16-bit extractions — for every 16-bit field
  extraction touched by the rewrite, the post-change code reproduces the pre-change
  bit-exact value on both a low-range test value and a test value with bit 15 set. The
  magic-20 `w` field is `uint16_t` (see `kernel/Gwfa/gwfa.h` and the SPM packing at
  `pe_array.cpp:755-758`), so its extraction must remain zero-extending — either by keeping
  `(unsigned)x >> 16` or by emitting a paired zero-extension (`gr_hi`-view read followed by
  an explicit mask / logical-AND, or equivalent `andi 0xFFFF`). Bare signed `gr_hi`
  substitution is not acceptable for `w`.
  - Positive Tests: the QA note cites two evaluated values (low and bit-15-set) and shows
    the extracted value equals the pre-change `(unsigned)x >> 16` / `x & 0xFFFF` at every
    changed site.
  - Negative Tests: a site that silently switches from unsigned semantics to signed
    half-register semantics without a zero-extension step fails AC-6. A site that uses
    bare `gr_hi` for the `w` extraction fails AC-6.

- AC-7: Live-gr preservation — code paths in magics 20, 31, 32, on every exit (including
  early returns, empty-PE branches, and the zero-count path), do not clobber `gr[7..10]`
  without a matched save/restore. (Plan-1 carryover: BL-20260413-gr-clobber.)
  - Positive Tests: a QA-ledger audit enumerates each in-magic assignment to `gr[7..10]`
    and shows either (a) the register is restored before any exit, or (b) the register was
    already dead at magic entry per the caller contract.
  - Negative Tests: any live-gr assignment not covered by the audit fails AC-7.

- AC-8: `s1c` seam layout documented and isolated — the plan reserves an explicit `s1c`
  index range (`s1c[176..191]`) for seam metadata (first-intv-per-PE lo/hi and
  last-intv-per-PE lo/hi), documents the init point, update point, consume point, and
  clear point, and the chosen range does not collide with existing dedup state
  (`s1c[0..31]`, `s1c[144]`, `s1c[152..168]`). The "first nonzero tile" predicate uses
  the already-live per-PE intv cursor `s1c[28+pe] == 0` (pre-increment) instead of a
  dedicated sentinel word, so no extra sentinel band is reserved.
  - Positive Tests: the plan's "s1c Layout" note shows the reserved indices `s1c[176..
    191]`, and a `grep -n "s1c\[1[78][0-9]" pe_array.cpp` confirms writes only inside
    magics 31 and 32 for the diff of this plan.
  - Negative Tests: any overlap with existing dedup `s1c` ranges, or a missing clear step
    in magic 32's finalize over `s1c[176..191]`, fails AC-8.

- AC-9: Seam merge edge-case coverage — magic 32's boundary merge is correct for each of
  five enumerated cases: (a) no previous output (first nonzero PE), (b) overlap with
  `cnt==1` at current PE (the single element merges into the previous PE's tail), (c)
  overlap with `cnt>1`, (d) no overlap (non-adjacent intvs), and (e) a PE whose first
  *nonzero* tile arrives after one or more zero-output tiles for that PE (the real stress
  case for the write-once-first semantics of magic 31's seam writes).
  - Positive Tests: mode 1 -t 56 includes cases exercising each of the five shapes, and
    the per-case diff against the pre-change reference run is zero. In addition, a per-PE
    sanity check records the seam `first_intv` and `last_intv` written by magic 31 and
    confirms they equal the first and last intv observed in MM for that PE's final region
    on at least one multi-tile case.
  - Negative Tests: the `cnt==1 + merge` case producing a stale `last_intv_hi` from a
    nonexistent copied element fails AC-9; a zero-cnt PE triggering a compare/copy path
    fails AC-9; a PE whose `first_intv` is overwritten by a later nonzero tile fails
    AC-9.

- AC-10: Canonical seam PE order — magic 31 writes seam metadata indexed by producer PE in
  order `0..3`, and magic 32 reads/merges seams in the same order. The plan documents this
  contract explicitly.
  - Positive Tests: the layout note states "seam[0..3] indexed by producer PE"; magic 32's
    reader uses PE indices `0..3` against those slots; the end-to-end mode-1 diff is zero.
  - Negative Tests: any index swap between writer and reader fails AC-10.

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)

The implementation covers all ten acceptance criteria; magic 20 converts diag and arcmeta
to `mvdq`-shape bulk copy while scalar stride-3 arc copy remains (with an optional
arc-prologue peel that aligns the first arc into a 4-wide bulk form if it can be proven
correctness-preserving under mode 2); magic 31 uses pre-computed per-PE cursors with
autoincrement-style advancement for both diag and intv streams, emits first-intv and
last-intv per PE to reserved `s1c` slots with write-once-first / update-on-each-nonzero
semantics; magic 32 consumes seam metadata from `s1c` exclusively for boundary merge, keeps
the PE-serial bulk mvdq interior copy (BL-20260416-m32-gather-dep carryover), clears seam
slots in its existing reset; every SPM load-to-use chain inside magic 20 is enumerated and
masked; `gr[7..10]` is audited clean across all three magics; `gendp-isa-reviewer` is run
after every commit with a disposition ledger.

### Lower Bound (Minimum Acceptable Scope)

The implementation satisfies AC-1 through AC-10; magic 20 converts only diag and arcmeta
to `mvdq`-shape bulk copy (arcs stay scalar, no prologue peel); magic 31 implements per-PE
autoincrement-style cursors and the write-once-first / update-on-each-nonzero seam writes;
magic 32 consumes `s1c` seam metadata and clears it; each magic passes mode 1 -t 56 after
its commit; plan end passes mode 2 -t 56 = 295/295; each magic has a reviewer ledger with
every finding dispositioned.

### Allowed Choices

- Can use: `gr[]`, `reg[]`, `s1c[]`, `spm[]`, `mm[]` only for live state (ISA rule 3);
  `constexpr` compile-time constants; labeled `goto` control flow; macro loops like
  `for (int pe = 0; pe < 4; pe++)`; helper macros if all live state is in registers/memory
  (ISA rule 11); `gr_hi`/`gr_lo` half-register views when signedness matches the source;
  the existing C++ `mvdq_copy` helper as a stand-in for bulk ISA `mvdq`; `waitLSQ` as a
  comment between MM/S2 load and use.
- Cannot use: `std::min` / `std::max` on the controller (ISA rule 10); new C++ runtime
  variables outside registers/memory (ISA rule 3); `if/else/for/while` for real control
  flow except macro-unroll loops (ISA rule 4); RAW between paired VLIW slot-0 and slot-1
  (ISA rule 2).

> **Note on Deterministic Designs**: The ISA-like rules are a fixed specification; the
> bulk transfer structure (mvdq round-robin across PEs, stride-3 scalar fallback) is
> fixed; the mode-2 295/295 target is fixed (unless DEC-MODE2-BLOCKER is relaxed). The
> only real choice surface is per-magic instruction ordering, `s1c` slot assignment, and
> whether arcs get a mvdq-compliant prologue peel (upper bound only).

## Feasibility Hints and Suggestions

> **Note**: Reference only. One plausible implementation path, not a mandate.

### Conceptual Approach

Magic 20 (`fin0_load_batch`):
- Keep the two-phase structure (Pass 1 round-robin + fallback; Pass 2 S2 batch; Pass 3 MM
  batch; Pass 4 metadata write).
- In the `F0B_ASSIGN` helper, split the body into three clear sub-ops:
  1. `mvdq_copy` for diag (2 words contiguous) from `s1c[32 + 2*di]` to
     `spm[pe_spm + FIN0_DIAGS + 2*nd]`.
  2. `mvdq_copy` for arcmeta (2 words contiguous) from `s1c[ARC_META_BASE + 2*di]` to
     `spm[pe_spm + FIN0_ARCMETA + 2*nd]`.
  3. Scalar stride-3 loop for arcs (unchanged, stride-3 prevents pure `mvdq`).
- For pass 2 (`pe_array.cpp:498`) and pass 3 (`pe_array.cpp:557`), change
  `gr[9] = spm[gr[8]] >> 16` from a single fused op to a load-then-consume sequence:
  load into `gr[9]`, insert two non-consuming paired instructions (or real work that has
  no RAW on `gr[9]`), then extract. Because `w` is `uint16_t`, the extraction must stay
  zero-extending — either retain `(unsigned)x >> 16` verbatim (no signed `gr_hi`
  substitution) or emit an explicit zero-extension (`andi 0xFFFF`) after the half-register
  read. Reorder neighboring ops to fill the 2-cycle gap with real work where possible.
- Audit every other SPM load in pass 3 (diag, arcmeta, arc-word for hash) and document
  the gap for each.

Magic 31 (dedup writeback):
- Precompute at entry, once per PE, per-PE destination cursors held in `gr`/`s1c` slots
  (no new C++ locals — ISA rule 3):
  `d_cur[pe] = gr[4] + (s1c[16+pe] + s1c[20+pe]) * 2`
  `i_cur[pe] = gr[7] + (s1c[24+pe] + s1c[28+pe]) * 2`
- Inside the chunk-outer / PE-inner streaming, advance `d_cur[pe] += cnt` /
  `i_cur[pe] += cnt` after each `mvdq_copy` instead of recomputing from base + offset.
  The acceptance bar for AC-5 is: the inner streaming body never recomputes `base +
  cursor` — it uses the monotonic per-PE cursor register.
- For seam metadata, at the head of each PE inner (if `nis[pe] > 0`):
  - Gate "first nonzero tile for this PE" on the live cursor: `if (s1c[28+pe] == 0)`
    (the pre-increment intv cursor; guaranteed zero-exactly-once across magic-31 calls
    per PE because magic 31 only advances it after producing output). When the gate fires,
    write the first intv lo/hi to `s1c[176+pe]` / `s1c[180+pe]`.
  - Always (after any nonzero tile), update the last intv lo/hi to `s1c[184+pe]` /
    `s1c[188+pe]`.
- No separate sentinel band is needed; the existing `s1c[28+pe]` cursor doubles as the
  "has-any-output" predicate for magic 32.
- Reserve `s1c[176..191]` (4 words first-lo, 4 words first-hi, 4 words last-lo, 4 words
  last-hi, indexed by producer PE in 0..3). Range is clear of existing dedup usage
  (`s1c[0..31]`, `s1c[144]`, `s1c[152..168]`); see "s1c Layout" below.

Magic 32 (dedup finalize):
- Replace the MM-based boundary compare with reads from `s1c[176+pe]` (first-lo) and
  `s1c[188+pe]` (last-hi) — 1-cycle latency per rule 8, inserted as a paired non-
  consuming gap if needed. Use `s1c[28+pe] > 0` as the "PE has output" predicate.
- Keep the PE-serial bulk mvdq interior copy (BL-20260416-m32-gather-dep requires this
  shape).
- In the existing reset step (`memset(s1c, 0, 144 * sizeof(int))`), append an explicit
  clear of `s1c[176..191]` (16 words) so seam metadata does not carry over to the next
  dedup invocation. Documented in AC-8.

### s1c Layout (Proposed)

Existing dedup band (do not touch):
- `s1c[0..31]`: per-PE cursors already used by magic 31 inner bookkeeping.
- `s1c[144]`: original diag_base save.
- `s1c[152]`: MM active intv region.
- `s1c[153]`: MM active diag region.
- `s1c[154..168]`: other dedup metadata (conservatively fenced).

Proposed plan-2a seam band (reserved for DEC-SEAM-MERGE):
- `s1c[176..179]`: first-intv per PE (pe in 0..3), lo word.
- `s1c[180..183]`: first-intv per PE, hi word.
- `s1c[184..187]`: last-intv per PE, lo word.
- `s1c[188..191]`: last-intv per PE, hi word.

The "has-any-seam" predicate uses the already-live per-PE intv cursor `s1c[28+pe]` rather
than a dedicated sentinel word: pre-increment it is zero iff magic 31 has never produced
output for this PE. All four sub-blocks (total `s1c[176..191]`) are cleared by magic 32
at finalize.

### Relevant References

- `pe_array.cpp:383-602` — `fin0_load_batch` (magic 20).
- `pe_array.cpp:3141-3193` — magic 31 (dedup writeback).
- `pe_array.cpp:3194-3300` — magic 32 (dedup finalize).
- `pe_array.cpp` — `mvdq_copy` helper used throughout the dedup path.
- `CLAUDE.md` — SPM access constraints, VLIW hazard rules, synchronization pattern.
- `docs.md` — ISA manual (encoding, opcodes, addressing modes).
- `scripts/gwfa_check_correctness.py` — correctness harness invoked with mode 1 and 2.
- Controller magics 7, 8, 9, 12, 14, 15 — frozen reference examples for ISA-like style.
- PE magics 8, 11, 13 — frozen reference examples for PE-side style.
- `isaLikeAllGwfaPlan1H.md` — closed review of Plan 1 (defines approved deviations and
  deferred items inherited here).

## Dependencies and Sequence

### Milestones

1. Milestone A — Magic 20 structural rewrite (independent of 31/32).
   - Phase A1: Split `F0B_ASSIGN` into diag-mvdq / arcmeta-mvdq / scalar-arc sub-ops.
   - Phase A2: Enumerate every SPM load-to-use chain in magic 20; reorder to establish a
     2-cycle gap; rewrite `>>16` sites as load-then-consume while preserving zero-
     extension for `w` (retain `(unsigned)x >> 16` verbatim, or emit an explicit
     `andi 0xFFFF` after a half-register read — see DEC-HALFREG-SIGN / AC-6).
   - Phase A3: `make -j ADDRESS_SANITIZER=0` + `gwfa_check_correctness.py 1 -t 56` = 15/15
     + commit + `gendp-isa-reviewer` ledger entry + fix or dispose of every finding.

2. Milestone B — Magic 31 structural rewrite (depends on A only for branch consistency).
   - Phase B1: Introduce per-PE cursors and autoincrement-style advancement for both diag
     and intv streaming loops.
   - Phase B2: Add seam-metadata writes to `s1c[176..191]` with write-once-first (gated
     by `s1c[28+pe] == 0`) and update-on-each-nonzero semantics for last.
   - Phase B3: mode 1 -t 56 = 15/15 + commit + reviewer ledger.

3. Milestone C — Magic 32 structural rewrite (depends on B for seam metadata contract).
   - Phase C1: Replace MM-based boundary compare with `s1c[176..191]` seam reads; keep
     PE-serial bulk mvdq interior copy.
   - Phase C2: Extend finalize reset to clear `s1c[176..191]`.
   - Phase C3: mode 1 -t 56 = 15/15 + commit + reviewer ledger.

4. Milestone D — Plan-end audit and mode-2 verification.
   - Phase D1: Capture all three reviewer ledgers, AC-4 SPM-chain table, AC-7 gr-preserve
     audit, AC-8 s1c-layout note into the plan's QA ledger.
   - Phase D2: `python3 scripts/gwfa_check_correctness.py 2 -t 56` = 295/295.

Dependency: A → B → C → D. Each milestone's commit must pass before the next begins.

## Task Breakdown

Each task includes exactly one routing tag: `coding` (implemented by Claude) or `analyze`
(executed via Codex through `/humanize:ask-codex`).

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| t1a | Magic 20: split `F0B_ASSIGN` into diag-mvdq, arcmeta-mvdq, scalar-arc sub-ops | AC-5 | coding | - |
| t1b | Magic 20: enumerate every SPM load-to-use chain; reorder for 2-cycle gap; rewrite `>>16` as load-then-consume while preserving zero-extension for `w` (no bare signed `gr_hi`) | AC-4, AC-6 | coding | t1a |
| t1c | Magic 20: gr[7..10]-preservation audit within magic 20 | AC-7 | coding | t1b |
| t1v | Magic 20: `make`, `gwfa_check_correctness.py 1 -t 56` = 15/15, commit, run `gendp-isa-reviewer`, record ledger | AC-1.1, AC-3 | coding | t1c |
| t1r | Magic 20: Codex review of the enumerated SPM-chain table and the half-register sites for pairing hazards and signed/unsigned mismatches | AC-4, AC-6 | analyze | t1v |
| t2a | Magic 31: introduce per-PE diag and intv cursors with autoincrement-style advancement | AC-5 | coding | t1v |
| t2b | Magic 31: add seam-metadata writes (first gated by `s1c[28+pe] == 0`, last updated on each nonzero tile) to `s1c[176..191]` | AC-8, AC-9, AC-10 | coding | t2a |
| t2c | Magic 31: gr[7..10]-preservation audit within magic 31 | AC-7 | coding | t2b |
| t2v | Magic 31: `make`, `gwfa_check_correctness.py 1 -t 56` = 15/15, commit, run `gendp-isa-reviewer`, record ledger | AC-1.2, AC-3 | coding | t2c |
| t2r | Magic 31: Codex review of VLIW slot placement for autoincrement cursors and seam-write ordering | AC-5, AC-8 | analyze | t2v |
| t3a | Magic 32: replace MM-based boundary compare with `s1c` seam reads | AC-9, AC-10 | coding | t2v |
| t3b | Magic 32: extend finalize reset to clear `s1c[176..191]` | AC-8 | coding | t3a |
| t3c | Magic 32: Codex-review the five seam-merge edge cases (empty PE, cnt==1 merge, cnt>1 merge, no overlap, zero-output tiles before first nonzero tile) | AC-9 | analyze | t3b |
| t3v | Magic 32: `make`, `gwfa_check_correctness.py 1 -t 56` = 15/15, commit, run `gendp-isa-reviewer`, record ledger | AC-1.3, AC-3 | coding | t3c |
| t3r | Magics 31+32: Codex review of the cross-magic seam contract (init/update/consume/clear) | AC-8, AC-9, AC-10 | analyze | t3v |
| t_qa | Compile the plan QA ledger: three reviewer ledgers, the AC-4 SPM-chain table, the AC-7 gr-preserve audit, and the AC-8 `s1c` layout note | AC-3, AC-4, AC-7, AC-8 | coding | t3v |
| t_fin | `python3 scripts/gwfa_check_correctness.py 2 -t 56` = 295/295; append numeric evidence to the ledger | AC-2 | coding | t_qa |

## Claude-Codex Deliberation

### Agreements

- Magic 20 stride-3 arcs remain scalar in 2a (no pure `mvdq`); diag and arcmeta are
  converted to bulk form (aligns with Plan 1's known-issue carryover).
- Magic 31 chunk-outer / PE-inner streaming shape is preserved; only destination cursor
  computation and seam-metadata writes change.
- Magic 32 PE-serial bulk mvdq interior is preserved (BL-20260416-m32-gather-dep).
- gr[7..10] preservation is mandatory for all three magics (BL-20260413-gr-clobber).
- gendp-isa-reviewer is advisory + the user is the arbiter of disputed findings
  (DEC-REVIEWER-ARBITER default = user).
- DEC-MODE2-BLOCKER default = hard blocker (295/295 required).

### Resolved Disagreements

- Topic: DEC-SEAM-MERGE location of seam-metadata writes.
  - Claude position (pre-review): Implement the draft literally, meaning magic 32 writes
    seam metadata to `s1c` from the first tile.
  - Codex position: Moving the write into magic 31 is a real reinterpretation; it
    introduces cross-magic state ordering obligations that must be called out (first-
    write-once, last-update-each-nonzero, some predicate for empty PE).
  - Chosen resolution: Adopt the draft's DEC-SEAM-MERGE reinterpretation (magic 31 owns
    the write, magic 32 reads/clears). Add explicit write-once-first (gated by
    `s1c[28+pe] == 0`) and update-each-nonzero semantics; use the already-live cursor
    `s1c[28+pe]` as the empty-PE predicate (no separate sentinel band).
  - Rationale: the user already recorded DEC-SEAM-MERGE in the draft's Decision Log; the
    Codex critique sharpens the contract. AC-8, AC-9, AC-10 codify the obligations.

- Topic: Half-register extraction (`>>16` → `gr_hi`).
  - Claude position (pre-review): Blanket replacement of `>>16` with `gr_hi`.
  - Codex position: `gr_hi` is signed-16; `w` is `uint16_t` (`kernel/Gwfa/gwfa.h`);
    blanket replacement changes semantics when bit 15 is set. Keep `(unsigned)x >> 16`
    verbatim OR emit an explicit zero-extension (`andi 0xFFFF`) after any subregister
    read.
  - Chosen resolution (Round 1): Accept the Codex stance verbatim. Magic 20 keeps
    unsigned zero-extension at every site; AC-6 now explicitly fails bare-`gr_hi` on the
    `w` sites.
  - Rationale: preserves bit-exact behavior; the perceived encoding "win" of bare
    `gr_hi` is not valid for a `uint16_t` field.

- Topic: Magic 31 autoincrement literalness.
  - Claude position: Pre-computed cursors advanced per iteration.
  - Codex position: Real `mvdq` in the ISA is SPM<->S2; MM bulk writes through `mvdq_copy`
    are a C++ stand-in, so "autoincrement" cannot ride a native register-autoincrement
    flag for MM.
  - Chosen resolution: Treat autoincrement as the C++ stand-in form (per-PE cursor
    register that advances by transferred word count after each `mvdq_copy`). Document
    this in the plan as the canonical pattern for this band. If a future plan models
    true MM-stream autoincrement, that's an additive rewrite.
  - Rationale: the draft's intent is "stop recomputing base+offset in the hot loop"; the
    cursor form achieves that without overstating ISA fidelity.

- Topic: Sentinel for "first nonzero tile for this PE" in seam writes.
  - Claude position (v1): Reserve `s1c[192..195]` as a dedicated sentinel flag per PE.
  - Codex position (Round 1): Redundant — magic 31 already advances `s1c[28+pe]` only on
    nonzero tiles, so `s1c[28+pe] == 0` at magic-31 entry is the natural write-once gate
    and `s1c[28+pe] > 0` at magic-32 entry is the "has any seam" predicate.
  - Chosen resolution (Round 1): Drop the sentinel band; use `s1c[28+pe]` as the gate and
    predicate. Seam band contracts to `s1c[176..191]` (16 words). AC-8, `s1c Layout`,
    Milestone C, and the task table all reflect this single range.
  - Rationale: no redundant state, fewer clear targets, simpler reviewer ledger.

- Topic: Cursor form for magic 31.
  - Claude position (v1): Pre-computed cursors, possibly held in C++ locals.
  - Codex position: C++ locals are not rule-3 compliant; state that cursors live in `gr`
    registers or `s1c` slots.
  - Chosen resolution (Round 1): Cursors live in `gr`/`s1c` only; acceptance bar for
    AC-5 is explicitly "inner streaming body never recomputes `base + cursor` — it uses
    the monotonic per-PE cursor register."
  - Rationale: keeps the plan honest about ISA-likeness.

- Topic: Task t3c routing tag.
  - Claude position (v1): `coding`.
  - Codex position: It is review work, should be `analyze`.
  - Chosen resolution (Round 1): Retag `t3c` to `analyze` (Codex-run edge-case review of
    the five seam shapes).
  - Rationale: keeps the coding/analyze split clean.

### Convergence Status

- Final Status: `converged`
  - Round 1 REQUIRED_CHANGES (half-register zero-extension, sentinel removal, clear-range
    consistency at `s1c[176..191]`, cursor wording, `t3c` retag) all applied.
  - Round 1 OPTIONAL_IMPROVEMENTS folded into AC-9 (multi-tile first/last match MM
    reference; zero-output-tiles-before-nonzero-tile stress case).
  - Four of the ten DEC-* items were directly resolved by the user on 2026-04-17:
    DEC-SEAM-MERGE = canonical, DEC-M20-ARCS = scalar-only, DEC-MODE2-BLOCKER = hard
    295/295, DEC-HALFREG-SIGN = closed as fixed zero-extension requirement.
  - Remaining DEC-* items stay `PENDING` with documented defaults; all have Codex
    agreement and do not block plan generation or the RLCR loop.
  - No REQUIRED_CHANGES remain.

## Pending User Decisions

- DEC-SEAM-MERGE: Is the reinterpretation canonical — magic 31 owns writing seam metadata
  to `s1c`, magic 32 reads it — or must plan 2a preserve the original prompt literally
  and keep seam-data production inside magic 32?
  - Claude Position: Keep as canonical (magic 31 writes, magic 32 reads/clears), per the
    draft's existing Decision Log entry, with the added write-once-first / update-each-
    nonzero contract.
  - Codex Position: Either is defensible; if kept canonical, the cross-magic state
    machine must be explicit. (This plan's AC-8/AC-9/AC-10 make it explicit.)
  - Tradeoff Summary: Canonical = no MM waitLSQ in merge, cross-magic contract needed.
    Literal = self-contained magic 32, but one extra MM latency wait at the seam.
  - Decision Status: `DECIDED` (user, 2026-04-17) — canonical (magic 31 writes, magic 32
    reads/clears). AC-8, AC-9, AC-10 carry the contract.

- DEC-S1C-SEAM-LAYOUT: Is `s1c[176..191]` the right band for seam metadata, or should
  plan 2a own updating the shared `s1c` layout doc to record a different band?
  - Claude Position (Round 1): `s1c[176..191]` (16 words: 4 first-lo + 4 first-hi + 4
    last-lo + 4 last-hi, indexed by producer PE in 0..3). Well clear of the existing
    dedup band (`s1c[0..31]`, `s1c[144]`, `s1c[152..168]`). No sentinel word needed
    because `s1c[28+pe]` is already the live "has-output" predicate.
  - Codex Position (Round 1): Agreed with the shrunk `176..191` range and the sentinel
    removal; any disjoint band works, what matters is the documented contract.
  - Tradeoff Summary: Minimal — indices do not materially change implementation
    difficulty, but a clean, documented range is what AC-8 tests.
  - Decision Status: `PENDING` — default to `s1c[176..191]`.

- DEC-HALFREG-SIGN: *Closed as fixed requirement (user, 2026-04-17).* Zero-extension is
  preserved at every `w` site in magic 20 (`w` is `uint16_t` per `kernel/Gwfa/gwfa.h`).
  Bare signed `gr_hi` is rejected; either keep `(unsigned)x >> 16` verbatim or emit an
  explicit zero-extension (`andi 0xFFFF` / logical-AND) after any subregister read.
  Enforced by AC-6. No longer a pending decision.

- DEC-M20-ARCS: For magic 20, is it acceptable in 2a to keep stride-3 arcs scalar (lower
  bound), or must 2a also deliver a stride-3-aware bulk arc path (upper bound)?
  - Claude Position: Keep scalar in 2a (inherits Plan-1 known-issue disposition).
  - Codex Position: Scalar is acceptable; a stride-3 bulk form is a possible upper-bound
    improvement if time allows.
  - Tradeoff Summary: Scalar = simpler + aligned with Plan 1; bulk stride-3 = more
    throughput, more risk of regression.
  - Decision Status: `DECIDED` (user, 2026-04-17) — keep stride-3 arcs scalar in 2a.
    Bulk-arc form is deferred (out of scope for plan 2a).

- DEC-M31-AUTOINC: Is "autoincrement cursors" interpreted as C++ per-PE cursor registers
  that advance after each `mvdq_copy`, or is literal ISA-level autoincrement (register
  auto-increment flag) required?
  - Claude Position: C++ per-PE cursor registers are the right 2a target; ISA-level
    autoincrement flag targeting MM is not clearly modeled.
  - Codex Position: Same — flag the mismatch and state the stand-in form explicitly.
  - Tradeoff Summary: Practical vs strictly-literal ISA correspondence.
  - Decision Status: `PENDING` — default to C++ cursor-register form.

- DEC-GR-PRESERVE: Is BL-20260413-gr-clobber strict for all three magics (gr[7..10]
  untouched on every path), or is save/restore within the magic acceptable?
  - Claude Position: Strict non-clobber preferred; save/restore allowed as a documented
    exception per site.
  - Codex Position: Same.
  - Tradeoff Summary: Strict non-clobber = simpler reasoning; save/restore = more
    register headroom when needed.
  - Decision Status: `PENDING` — default to strict non-clobber, save/restore allowed only
    with documented rationale.

- DEC-REVIEWER-ARBITER: Who makes the final call when `gendp-isa-reviewer` disagrees with
  the human plan owner or flags a known false positive?
  - Claude Position: The user arbitrates; the reviewer's report is advisory and every
    finding must be dispositioned in the QA ledger.
  - Codex Position: Same.
  - Tradeoff Summary: None — consistent with prior plan practice.
  - Decision Status: `PENDING` — default to user arbitration.

- DEC-MODE2-BLOCKER: Is end-of-plan `gwfa_check_correctness.py 2 -t 56` 295/295 a hard
  blocker, or can the plan land with documented partial convergence (e.g., 294/295)?
  - Claude Position: Hard blocker (consistent with Plan 1's DEC-1 carryover).
  - Codex Position: Same.
  - Tradeoff Summary: Hard blocker enforces the quality bar at plan cost; relaxation
    accepts residuals but leaves them for a later plan.
  - Decision Status: `DECIDED` (user, 2026-04-17) — hard 295/295 blocker. AC-2 enforces
    this as a plan-level gate.

- DEC-WRITE-ORDER: Canonical seam PE order = `0..3` for both magic 31 writes and magic
  32 reads?
  - Claude Position: Yes, enforced via AC-10.
  - Codex Position: Same.
  - Tradeoff Summary: None meaningful.
  - Decision Status: `PENDING` — default to `0..3`.

## Implementation Notes

### Code Style Requirements

- Implementation code and comments must NOT contain plan-specific progress terminology
  such as "AC-", "Milestone", "Phase", "Step", "t1a", "t_fin", or similar workflow
  markers. These identifiers live in this plan document only.
- Use descriptive domain names in code: `diag_mvdq`, `arcmeta_mvdq`, `scalar_arc_copy`,
  `seam_first_lo_base`, `seam_first_hi_base`, `seam_last_lo_base`, `seam_last_hi_base`,
  `d_cur`, `i_cur`, etc.
- Obey the project's C++ line-length limit (<=100 chars, flexible for clarity) and avoid
  unnecessary line breaks inside `mvdq_copy` or `spm[...] = ...` lines.
- Comments: add a comment only when the "why" is non-obvious (SPM-latency padding cycle,
  write-once-first seam semantics, stride-3 scalar fallback justification). No WHAT-level
  restatement of the code.

--- Original Design Draft Start ---

# GWFA ISA-Like Rewrite Plan 2a: Controller Structural Residuals

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

### Decision Log
- **DEC-SEAM-MERGE**: The original plan says controller 32 should "write first/last intv to s1c for seam merge." Plan 2a implements this by having magic 31 (writeback) store first/last intv per PE to s1c, so magic 32 (finalize) can do boundary merge from s1c instead of MM. This moves the write to magic 31 rather than magic 32, but achieves the same goal: no MM lookups for boundary comparison. This is a design reinterpretation, not a straight preservation of the original plan's task assignment.

---

## Goal Description

Complete remaining structural changes for controller magics 20, 31, and 32.

## Prerequisites

Plan 1 code implemented. Code passes mode 1 -t 56: 15/15.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after each change, mode 2 at end)
- AC-2: gendp-isa-reviewer finds no hazards in each changed magic
- AC-3: All per-magic draft requirements below addressed

## Task Breakdown

### Controller 20 (fin0_load_batch)
Draft: "line 613: gr[9] = spm[gr[8]] >> 16 — two ISA ins, can't immediately operate on SPM (2-cycle latency), use half registers instead of >>16"
Draft: "begin loading arcs using mvdq and peel the end"

| Task ID | Description | Tag |
|---------|-------------|-----|
| s1a | Separate contiguous data (diag 2w, arcmeta 2w) into mvd-able copies; keep scalar only for strided 3-word arcs | coding |
| s1b | Add SPM latency masking: reorder instructions so SPM loads have 2-cycle gap before use | coding |
| s1c | Use half-registers for 16-bit field extraction instead of >>16 shifts | coding |
| s1v | Verify controller 20: mode 1 + ISA review | coding |

### Controller 31 (dedup writeback)
Draft: "compute cursors for each pe and use mv instruction autoincrement when you writeback"

| Task ID | Description | Tag |
|---------|-------------|-----|
| s2 | Add autoincrement cursors: pre-compute per-PE MM destination, increment after each write instead of recomputing from base+offset | coding |
| s2v | Verify controller 31: mode 1 + ISA review | coding |

### Controller 32 (dedup finalize) — DEC-SEAM-MERGE
Draft: "write the very first tile data element to s1c. Also write the very last intv of each pe to s1c. Compare final intvs without MM lookups."

| Task ID | Description | Tag |
|---------|-------------|-----|
| s3 | Store first intv and last intv of each PE to s1c during magic 31 writeback. Magic 32 uses s1c for boundary merge instead of MM. | coding |
| s3v | Verify controller 31+32: mode 1 + ISA review | coding |

### Final verification

| Task ID | Description | Tag |
|---------|-------------|-----|
| s_fin | Full verification: mode 2 -t 56 | coding |

## Known Issues from Plan 1

- **Controller 20**: Arc stride (3-word) prevents pure mvdq. Diag data and arcmeta (both 2-word contiguous) CAN use mvd.
- **Controller 32**: Sequential destination dependency (BL-20260416-m32-gather-dep). PE-serial bulk mvdq is correct form.
- **BL-20260413-gr-clobber**: Controller 19 uses gr[7-10]. All magics must avoid clobbering live gr registers.

--- Original Design Draft End ---
