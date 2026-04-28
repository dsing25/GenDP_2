# GWFA ISA-Like Rewrite Plan 3d: ISA Lower PE 19-23 + Final Review

## Goal Description

ISA-lower the five GWFA-kernel PE-side "magic" functions numbered 19, 20, 21, 22, 23 in `pe.cpp` so each conforms to the 12 ISA-like rules already in force for Plans 3a/3b/3c. Each magic is lowered, mode-1-verified, and ISA-reviewed individually. Before any lowering begins, task `l8` commits a PE-side ABI artifact that (a) freezes cross-magic `gr[]` / `reg[]` slots used by PE magics 19..23, (b) documents half-register hi/lo ownership, and (c) records the PE 23 `DEDUP_META` register-residency contract (register-residency adopted per user decision DEC-1; see Claude-Codex Deliberation). `l8` also commits `scripts/plan3d_capture_snapshot.sh`, a `plan3d_snap=1` build target (gating a `PLAN3D_TRACE_SNAPSHOT` preprocessor symbol), and the captured frozen oracle under `tests/frozen/plan3d_pre_l8a/`. Cluster mode-2 `-t 56` gates run after PE 21 (sort milestone) and after PE 23 (dedup milestone) per user decision DEC-2. Magic ordering follows the draft (PE 19 → 20 → 21 → 22 → 23) per DEC-3. After all five magics land, a comprehensive cross-magic ISA audit (`l9a` controller 16..39 batch + `l9b` PE 19..23 batch) runs as `analyze` tasks with ABI-collision / cross-magic RAW / latency-discipline scope; any finding is fixed under the controlled-change rule and followed by rerun of the affected earlier magic gates plus the cluster gate(s) if already past them. Final exit gate: `gwfa_check_correctness.py 2 -t 56 = 295/295` (HARD requirement per user confirmation).

## Prerequisites

Plans 1 + 2a + 2b + 2c + 3a + 3b + 3c complete. All controller magics 16..39 ISA-lowered and passing mode 2 -t 56 = 295/295. PE magics 8, 11, 13 frozen; controller magics 1/3/4/5/6/17 exempt; controller magics 2/10/26 deleted.

## Acceptance Criteria

Each AC is labeled `[Product]`, `[Process]`, or `[Product+Process]`. Following TDD philosophy, every AC carries positive tests (expected to PASS) and negative tests (expected to FAIL / be rejected).

- AC-1 `[Process]` Correctness cadence and integration gates.
  - Positive Tests:
    - `make -j ADDRESS_SANITIZER=0` and `python3 scripts/gwfa_check_correctness.py 1 -t 56` pass after every edited PE magic (19, 20, 21, 22, 23) — including magics that feel "trivial" in scope.
    - Cluster mode-2 gates: `gwfa_check_correctness.py 2 -t 56 = 295/295` runs after PE 21 (sort-milestone cluster gate) and after PE 23 (dedup-milestone cluster gate).
    - Final gate: `gwfa_check_correctness.py 2 -t 56 = 295/295` after the cross-magic audit + any fixes.
    - 295/295 is a HARD pass/fail requirement at every mode-2 gate (cluster and final); any case below 295 fails the gate.
  - Negative Tests:
    - Any PE magic landing without its mode-1 rerun is rejected.
    - Either cluster gate (after PE 21 or after PE 23) skipped on "trivial change" grounds is rejected.
    - Any regression below 295/295 on any mode-2 gate is rejected.

- AC-2 `[Product+Process]` PE-side cross-magic ABI artifact with controlled-change rule.
  - Positive Tests:
    - Task `l8` commits a PE ABI artifact (extending Plans 3a/3b/3c ABI tables into PE-side `gr[]` / `reg[]` slots) BEFORE task `l8a` begins. The artifact names live-in / live-out, protected, and scratch slots for PE magics 19..23, and cross-references the frozen PE 8 and PE 13 ABI headers at `pe.cpp:719-755` and `pe.cpp:1155-1172`.
    - The artifact documents half-register hi/lo ownership per slot and records the `// half-reg hi` / `// half-reg lo` greppable comment convention.
    - The artifact records the DEC-1 resolution (register-residency) and lists each moved `DEDUP_META` slot (`+0/+1/+4/+5/+6/+7/+14..+19`) with its new register-resident home; preserves the controller-visible slot set (`+2/+3`) and the controller refill/writeback set (`+10..13`) unchanged.
    - The artifact excludes `gr[10]` from any PE-visible cross-magic reservation, because `gr[10]` is the PE-sync done flag written by the envelope at `scripts/gwfa_instruction_generator.py:666-688`.
    - Any later shared-slot change lands in a dedicated amendment commit that precedes the next magic commit; every already-lowered PE magic whose contract is affected by the amendment is re-run through its mode-1 gate, and any cluster mode-2 gate is re-run if already past it.
  - Negative Tests:
    - Starting any of `l8a..l8e` without the ABI artifact fails AC-2.
    - Silent slot reassignment inside a lowering commit (no preceding amendment commit) fails AC-2.
    - Skipping mode-1 rerun of an affected prior magic after an ABI amendment fails AC-2.

- AC-3 `[Product]` Register / memory-only state across ISA lines.
  - Positive Tests:
    - In each edited PE magic (19..23), no C++ local variable, local array, bool flag, or lambda return-value carries state across ISA lines; all live state lives in `gr[] / reg[] / spm[] / mm[]` (PE body has no direct `s1c[]` access — PE-to-controller seam state uses `spm[]` / `mm[]`).
    - Helper macros are accepted only if all their state lives in register/memory; macros that mutate captured C++ locals are rejected.
    - The PE 21 `bin_cursors[SORT_RADIX_BINS]` array at `pe.cpp:1419`, PE 22 `bvd[3]` at `pe.cpp:1514`, PE 23 `ad/ai` bools at `pe.cpp:1665`, and PE 19 lambda return-values at `pe.cpp:1937-1941` are eliminated or lifted into `gr[] / reg[]` per the AC-2 artifact.
  - Negative Tests:
    - Any `int x = ...;`, `bool flag = ...;`, `uint32_t arr[N];`, or lambda return-value carrying state across ISA lines in the lowered magics fails review.
    - Env-gated debug counters or `getenv("GWFA_AC5_DUMP")` branches remaining inside a lowered magic body fails AC-3.

- AC-4 `[Product]` Structured control flow via gotos and macro PE unrolls only.
  - Positive Tests:
    - Edited PE magics contain only labeled goto branches and constexpr macro unrolls (e.g. `for (int pe = 0; pe < 4; ++pe)` over compile-time PE count, `for (int i = 0; i < SORT_RADIX_BINS; ++i)` over constexpr bin count, constexpr `for (int b = 0; b < 3; ++b)` for PE 22 boundary classes).
  - Negative Tests:
    - Any runtime `if / else / for / while` in an edited magic (PE 19 arc for-loops, PE 20/21 tile for-loops, PE 22 `for (b=0; b<3)` over a runtime-dependent count, PE 23 nested `if/goto` chains on runtime state) fails review.

- AC-5 `[Product+Process]` VLIW pairing and latency discipline.
  - Positive Tests:
    - `gendp-isa-reviewer` passes on each lowered PE magic before the next begins.
    - Mechanical pre-check (regex patterns from the Plan 3c ABI artifact, adapted for PE body) reports no new RAW-pair violations, no missing `// waitLSQ`, no `spm[...]` consumed within 2 ISA lines of load, no `s1c[...]` consumed within 1 ISA line of load (where applicable via controller-side seams).
    - Half-register extractions (`>> 16`, `& 0xFFFF`, or `gr.at(i, CTRL_GR_HI/LO)`-style accessors) are paired-slot legal and carry a `// half-reg hi` or `// half-reg lo` comment so the convention is greppable.
    - Any structural-latency waiver (deferred to the PE ABI artifact) is logged with a `// waiver: <reason>` comment; the artifact's waiver table lists each waiver's magic, code range, justification, and agreed bounding behavior.
  - Negative Tests:
    - Any reviewer-flagged RAW hazard blocks progression.
    - Any SPM load whose first consumer sits less than 2 ISA lines away without explicit waiver fails review.
    - Any MM load without `// waitLSQ` between the load and first consumer fails review.
    - Any PE 20 / PE 21 immediate-SPM-use pattern (flagged in `plan2c_audit_matrix.md:89-96`) remaining after lowering fails review.

- AC-6 `[Product]` PE 19 FIN0 semantics preserved bit-exact.
  - Positive Tests:
    - Rewritten PE 19 preserves FIN0 tile-mask semantics, A/B/HA record byte layout, bucket full-vs-empty handling, and the deletion condition `(nv == 0 || n_ext != nv)` from `pe.cpp:1906-2082`.
    - Character-fetch swizzle (current `mvi2_ld` lambda body at `pe.cpp:1937-1941`) is inlined bit-exact — `apply_address_swizzle` semantics and 2-bit packed-base extraction remain unchanged.
    - Packed `vd` encoding (`v = vd >> 16`, `d = (vd & 0xFFFF) - GWF_DIAG_SHIFT`) is preserved via half-register extractions with the same bit positions.
    - FIN0_META output counts (A-list, B-list, HA-bucket) match pre-lowering byte-for-byte on the frozen PE 19 oracle snapshot.
  - Negative Tests:
    - Any altered bucket-insertion policy, altered `absent` classification, altered deletion condition, altered `vd` encoding, or altered address-swizzle behavior fails AC-6 even if mode-1 happens to pass.

- AC-7 `[Product]` PE 22 merge / boundary invariants preserved exactly.
  - Positive Tests:
    - Rewritten PE 22 preserves the documented entry/switch invariants at `pe.cpp:1466-1500` (ping-pong `aw/bw` selector, `MERGE_A_BUF0/1` / `MERGE_B_BUF0/1` selection, `a_n/b_n` tile bounds).
    - Output byte layout at `spm[976..983]`, `MERGE_META[0..8]`, and `spm[982]` is byte-equal against the frozen PE 22 oracle snapshot on representative merge cases.
    - Any "second buffer always full" simplification (from the draft) is accompanied by a formal invariant proof cited in the commit message (either the code structurally guarantees it, or the check is retained but hoisted out of the hot inner loop).
  - Negative Tests:
    - Any unchecked "second buffer always full" assumption without an invariant proof fails AC-7.
    - Any boundary-position semantic change (tile-switch logic, emit-cursor advance, cum_oi accumulation) not justified by byte-equality on the oracle fails AC-7.

- AC-8 `[Product+Process]` PE 23 register-residency contract is explicit and verified.
  - Positive Tests:
    - The PE ABI artifact (AC-2) names every `DEDUP_META[0..19]` slot role for Plan 3d:
      - `DEDUP_META+2 / +3` — controller-visible outputs consumed by controller magic 31 at `pe_array.cpp:6282-6302`: UNCHANGED.
      - `DEDUP_META+10..13` — controller-side refill / writeback state used by controller magics 30/31 at `pe_array.cpp:5817-5916, 6163-6184`: UNCHANGED.
      - `DEDUP_META+0/+1/+4/+5/+6/+7/+14..+19` — PE-local checkpoint state: MOVED to register residency per DEC-1. The artifact lists each moved slot's new register-resident home (per-PE `gr[]` / `reg[]`) and cites the magic-23 call envelope at `scripts/gwfa_instruction_generator.py:666-688` as evidence that the envelope touches only `gr[10]` between invocations (so non-`gr[10]` registers persist across magic 23 PING/PONG calls within a single case).
    - The artifact states that `pe::reset()` at `pe.cpp:43-46` clears both register files and is therefore NOT evidence for cross-call persistence; persistence holds only within the same case between envelope-defined boundaries.
    - Mode-1 `-t 56` and cluster mode-2 `-t 56 = 295/295` pass on PE 23; the PE 23 snapshot is byte-equal against the frozen oracle.
  - Negative Tests:
    - "Most state should stay in regs" without a committed per-slot contract in the AC-2 artifact fails AC-8.
    - Any change that leaves a previously controller-read or handshake slot (`+2/+3/+10..+13`) implicit fails AC-8.
    - Any mismatch in `DEDUP_META+2 / +3` outputs consumed by controller magic 31 fails AC-8.

- AC-9 `[Product+Process]` Frozen PE-visible observables captured before lowering and diffed after risky magics.
  - Positive Tests:
    - Task `l8` commits:
      - `scripts/plan3d_capture_snapshot.sh` — driver script mirroring `scripts/plan3c_capture_snapshot.sh`: `make clean`, `make -j ADDRESS_SANITIZER=0 plan3d_snap=1`, run `./sim -k 7 -i kernel/Gwfa/Datasets/Gwfa295 -n 1`, move the emitted `plan3d_snapshot_pe19.txt`, `plan3d_snapshot_pe22.txt`, `plan3d_snapshot_pe23.txt` into `tests/frozen/plan3d_pre_l8a/`, restore a default build.
      - `plan3d_snap=1` Makefile target gated on the `PLAN3D_TRACE_SNAPSHOT` preprocessor symbol; default build unaffected.
      - Three `#ifdef PLAN3D_TRACE_SNAPSHOT` dump blocks inside `pe.cpp`:
        - At the exit of PE 19 (`pe.cpp` around the current FIN0_META publish site): dump FIN0_META slots and the first N words of A-list, B-list, HA-bucket.
        - At the exit of PE 22: dump `MERGE_META[0..8]`, `spm[976..983]`, `spm[982]`.
        - At entry and exit of PE 23's first PING invocation of case 0 (i.e. the first magic-23 call within the first test case of the dataset): dump the `DEDUP_META[0..19]` entire 20-word block.
      - Score baselines `mode1_t56_scores.txt` and `mode2_t56_scores.txt`.
      - Wavefront trace `wfDebug_HEAD.txt` from `gwfa_check_correctness.py 3`.
    - After PE 19 lands (`l8a`), regenerated `plan3d_snapshot_pe19.txt` is byte-equal to baseline (check in `l8av`).
    - After PE 22 lands (`l8d`), regenerated `plan3d_snapshot_pe22.txt` is byte-equal (check in `l8dv`).
    - After PE 23 lands (`l8e`), regenerated `plan3d_snapshot_pe23.txt` is byte-equal (check in `l8ev`).
  - Negative Tests:
    - Any lowering of PE 19 / 22 / 23 without a pre-change snapshot fails AC-9.
    - Any byte-diff in the frozen observables — even if score-based mode-1 passes — fails AC-9.
    - A snapshot scope so weak it cannot catch seam changes (e.g. score only, no metadata) fails AC-9.

- AC-10 `[Product+Process]` Comprehensive cross-magic audit operationally defined and clean.
  - Positive Tests:
    - `l9a` (controller 16..39 audit) and `l9b` (PE 19..23 audit) are `analyze` tasks routed through Codex / `gendp-isa-reviewer` with explicit scope: ABI-collision audit across magic boundaries (not just a re-run of per-magic checks), cross-magic RAW audit on shared `gr[] / s1c[] / DEDUP_META` slots, latency-discipline audit across magic seams, and verification of every waiver carried forward from AC-5.
    - "No new hazards" means zero new unresolved findings beyond waivers / dispositions already recorded in the Plan 3c ABI artifact and the Plan 3d PE ABI artifact (AC-2).
    - Any finding from `l9a / l9b` that requires a fix triggers: (a) a dedicated ABI-amendment commit per AC-2 controlled-change rule, (b) mode-1 rerun of each affected earlier magic, (c) rerun of any cluster mode-2 gate (after PE 21 and/or after PE 23) already past, (d) rerun of the final mode-2 gate.
  - Negative Tests:
    - A batch audit that is only a re-run of isolated per-magic checks (no cross-magic collision coverage) fails AC-10.
    - Any ABI collision found but not treated as a blocker fails AC-10.
    - Any post-audit fix without rerunning affected earlier gates fails AC-10.

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)

All five PE magics 19..23 ISA-lowered. Task `l8` commits the PE ABI artifact (including half-register convention, DEC-1 register-residency resolution, and the waiver table), the `plan3d_capture_snapshot.sh` driver + `plan3d_snap=1` build target + `PLAN3D_TRACE_SNAPSHOT` dump blocks, and the frozen oracle (scores + wfDebug + PE 19 / 22 / 23 snapshots under `tests/frozen/plan3d_pre_l8a/`, with optional additional PE 20 / 21 snapshots for extra coverage) before `l8a`. Cluster mode-2 gates run after PE 21 and after PE 23. After PE 23 lands, `l9a` and `l9b` run as `analyze` audit tasks over the complete lowered set (controller 16..39 + PE 19..23) with explicit ABI-collision, cross-magic RAW, and latency-discipline coverage. Findings are fixed under the controlled-change rule with affected-magic rerun. Commit messages reference AC-6, AC-7, AC-8 rationale per magic. Reviewer approval + mechanical pre-check pass on every magic.

### Lower Bound (Minimum Acceptable Scope)

All five PE magics 19..23 ISA-lowered. Task `l8` commits a minimal PE ABI artifact (possibly amended once later under the controlled-change rule) + the `plan3d_capture_snapshot.sh` mechanism + frozen oracle covering scores, wfDebug, and snapshots for PE 19, PE 22, PE 23 (PE 20 / 21 snapshots are optional). Each magic passes `gwfa_check_correctness.py 1 -t 56` and `gendp-isa-reviewer`. Cluster mode-2 gates run after PE 21 and after PE 23. `l9a / l9b` cross-magic audit runs; any finding is fixed under the controlled-change rule. Final `gwfa_check_correctness.py 2 -t 56 = 295/295` (HARD). PE 19 FIN0 bit-exactness (AC-6), PE 22 merge invariants (AC-7), and PE 23 register-residency contract (AC-8) are all preserved.

### Allowed Choices

- Can use: labeled gotos; `constexpr`; macro unrolls over compile-time constants (PE count, bin count, boundary-class count); half-register extracts (with `// half-reg hi/lo` annotation); `mvd` 2-word contiguous loads; `// waitLSQ`, `// SPM settle`, `// s1c gap`, `// half-reg hi/lo`, `// waiver: <reason>` annotations; scratch via `gr[] / reg[] / spm[] / mm[]`; helper macros whose state lives in register/memory; PE-local `min / max` (rule 10 allows PE min/max).
- Cannot use: C++ locals / arrays / bools as inter-ISA-line state; lambdas with return values carrying computed values across ISA lines; runtime `if / else / for / while` in edited magics; altered PE 19 hash / bucket / swizzle semantics; altered PE 22 merge/boundary invariants without oracle byte-equality; silent changes to `DEDUP_META` controller-visible slots (`+2 / +3`) or controller-side refill/writeback slots (`+10..13`); silent changes to shared ABI slots without an amendment commit; use of `gr[10]` for PE-side cross-magic register residency (reserved as PE-sync done flag); PE compute-instruction changes (compute deferred per rule 12).

> **Deterministic Design Note**: The 12 ISA-like rules, the inherited register ABI (Plans 3a/3b/3c), the frozen PE references (PE 8, 11, 13), the DEC-1 register-residency resolution, and the frozen reference examples together narrow the design space substantially. The upper and lower bounds differ mainly in documentation rigor (optional PE 20 / 21 snapshots) and commit-message discipline, not in implementation freedom.

## Feasibility Hints and Suggestions

> **Note**: This section is for reference and understanding only. These are conceptual suggestions, not prescriptive requirements.

### Conceptual Approach — per magic

- **PE 19** (`pe.cpp:1906-2082`, FIN0 hash check + char match): inline `mvi2_ld` lambda to explicit ISA lines (SPM load + `// SPM settle` + 2-bit extract); convert arc for-loop to labeled `m19_arc_loop / m19_arc_done`; use half-registers for `v = vd >> 16` / `d = vd & 0xFFFF` with `// half-reg hi/lo` comments; eliminate debug probe counters (move behind `#ifdef` if retained for dev or drop from magic body entirely); hoist hash-slot computation to a label. Bit-exactness of address swizzle is the dominant constraint (AC-6).
- **PE 20** (`pe.cpp:1380-1409`, sort bin count): two-element `mvd` already present; convert outer for-loop to `m20_loop / m20_done`; peel odd tail with a labeled branch; fix any residual SPM immediate-use flagged in `plan2c_audit_matrix.md:89-96` by placing 2 ISA lines of non-dependent work in the gap.
- **PE 21** (`pe.cpp:1410-1455`, sort scatter): two-element `mvd` already present; map `bin_cursors[SORT_RADIX_BINS]` to a constexpr-unrolled `reg[]` band (per the PE ABI artifact — per-PE reservation inside the `reg[]` file, not the `gr[]` file, since 16 per-bin cursors exceed comfortable `gr[]` headroom); convert scatter outer loop to labeled form; peel odd tail.
- **PE 22** (`pe.cpp:1456-1629`, two-pointer merge): keep the existing `m22_top / m22_switch_a / m22_switch_b / m22_done` state machine; replace `uint32_t bvd[3]` + runtime `for (b=0; b<3)` boundary loop with constexpr macro unroll (b=0,1,2 known at compile time per PE 22 boundary-class count); remove env-gated debug dump from the magic body; either (a) prove `b_n` always full on tile entry and remove the runtime check, or (b) keep the check but hoist it out of the hot inner loop. AC-7 requires the invariant to be explicit in the commit message.
- **PE 23** (`pe.cpp:1630-1850`, tiled dedup state machine, register-residency adopted per DEC-1): move `DEDUP_META+0/+1/+4/+5/+6/+7/+14..+19` into per-PE `gr[] / reg[]` slots per the AC-2 artifact; convert `bool ad, ai` locals to `gr[] / reg[]` flags; replace M23_RD/RI/PI macros' C++ local temps with explicit `gr[] / reg[]` temporaries with 2-cycle SPM settle gaps already present; keep one intv and one diag in registers across macro boundaries for forbidden-pair checks (draft directive); preserve `DEDUP_META+2/+3` controller-visible handshake output and `DEDUP_META+10..13` controller refill/writeback slots; AC-8 gates the per-slot register-residency map.

### Relevant References

- `pe.cpp:1906-2082` — PE 19 current implementation (FIN0).
- `pe.cpp:1380-1409` — PE 20 current implementation (sort bin count).
- `pe.cpp:1410-1455` — PE 21 current implementation (sort scatter).
- `pe.cpp:1456-1629` — PE 22 current implementation (two-pointer merge).
- `pe.cpp:1630-1850` — PE 23 current implementation (tiled dedup state machine).
- `pe.cpp:708-1085` — PE 8 frozen reference (goto labels, `gr[]/reg[]` ABI header, half-register pattern).
- `pe.cpp:1087-1150` — PE 11 frozen reference.
- `pe.cpp:1151-1380` — PE 13 frozen reference.
- `pe.cpp:43-46` — `pe::reset()` (clears register files; called on PE construction / test-case boundary; NOT evidence of cross-magic persistence).
- `scripts/gwfa_instruction_generator.py:666-688` — magic 23 call envelope (touches only `gr[10]` between PING/PONG; non-`gr[10]` registers persist within a case).
- `pe_array.cpp:6282-6302` — controller magic 31 read of `DEDUP_META+2/+3` (controller-visible output).
- `pe_array.cpp:5817-5916, 6163-6184` — controller magics 30/31 use of `DEDUP_META+10..13` (controller-side refill / writeback).
- `scripts/plan3c_capture_snapshot.sh` — pattern to mirror for `scripts/plan3d_capture_snapshot.sh`.
- `isaLikeAllGwfaPlan3aH.md`, `isaLikeAllGwfaPlan3bH.md`, `isaLikeAllGwfaPlan3c_ABI.md` — inherited ABI artifacts to extend.
- `plan2c_audit_matrix.md` — pre-recorded rule-6 / rule-9 issues in PE 20 / 21 / 22 / 23.
- `scripts/gwfa_check_correctness.py` — mode-1 / mode-2 / mode-3 validator.
- `gendp-isa-reviewer` agent.

## Dependencies and Sequence

### Milestones

1. **Milestone PE ABI Freeze**: `l8` commits (a) the PE ABI artifact including DEC-1 register-residency resolution + half-register convention + waiver table, (b) `scripts/plan3d_capture_snapshot.sh` + `plan3d_snap=1` Makefile target + `PLAN3D_TRACE_SNAPSHOT` dump blocks in `pe.cpp`, (c) the frozen oracle under `tests/frozen/plan3d_pre_l8a/`.
2. **Milestone Sort cluster (PE 19, 20, 21)**: FIN0 hash + sort bin count + sort scatter. Per-magic mode-1 + `gendp-isa-reviewer`. PE 19 snapshot diff in `l8av`. Cluster mode-2 `-t 56 = 295/295` gate after PE 21 (per DEC-2).
   - Step 1: `l8a` → `l8av` (PE 19).
   - Step 2: `l8b` → `l8bv` (PE 20).
   - Step 3: `l8c` → `l8cv` (PE 21; sort-milestone cluster mode-2 gate here).
3. **Milestone Merge+Dedup cluster (PE 22, 23)**: two-pointer merge + dedup. Per-magic mode-1 + `gendp-isa-reviewer`. PE 22 snapshot diff in `l8dv`. PE 23 snapshot diff + dedup-milestone cluster mode-2 gate in `l8ev`.
   - Step 1: `l8d` → `l8dv` (PE 22).
   - Step 2: `l8e` → `l8ev` (PE 23; dedup-milestone cluster mode-2 gate here).
4. **Milestone Cross-magic audit + final**: `l9a` controller 16..39 audit (`analyze`), `l9b` PE 19..23 audit (`analyze`), `l9c` fixes under the controlled-change rule (if any), `l9cv` mode-1 revalidation of affected magics (plus cluster-gate rerun if in scope), `l10` final mode-2 `-t 56 = 295/295`.

Dependencies (relative): `l8` blocks all `l8a..l8e`; each lowering task blocks its matching verify task; each verify task blocks the next lowering. `l9a / l9b` block `l9c`; `l9c` blocks `l9cv` blocks `l10`. Cluster boundaries are enforced by the cluster mode-2 gates at `l8cv` and `l8ev`.

Magic ordering (`PE 19 → 20 → 21 → 22 → 23`) is confirmed per DEC-3.

## Task Breakdown

Each task carries exactly one routing tag: `coding` (Claude) or `analyze` (Codex / `/humanize:ask-codex`).

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| l8 | Commit PE-side ABI artifact (extending Plans 3a/3b/3c) covering PE `gr[]/reg[]` slots for PE 19..23, half-register hi/lo convention, waiver table, DEC-1 register-residency contract with per-slot map for `DEDUP_META+0/+1/+4/+5/+6/+7/+14..+19`; commit `scripts/plan3d_capture_snapshot.sh` + `plan3d_snap=1` Makefile target + `PLAN3D_TRACE_SNAPSHOT` dump blocks in `pe.cpp`; capture frozen oracle (scores, wfDebug, PE 19/22/23 snapshots) under `tests/frozen/plan3d_pre_l8a/`. | AC-2, AC-8, AC-9 | analyze | - |
| l8a | ISA-lower PE 19 (inline `mvi2_ld` lambda bit-exact; arc for-loop → goto; half-reg for v/d; eliminate debug probes; FIN0 semantics preserved). | AC-3, AC-4, AC-5, AC-6 | coding | l8 |
| l8av | `make -j ADDRESS_SANITIZER=0` + mode-1 -t 56 + `gendp-isa-reviewer` + PE 19 snapshot diff vs oracle. | AC-1, AC-5, AC-9 | coding | l8a |
| l8b | ISA-lower PE 20 (goto form; odd-tail peel; fix SPM immediate-use from `plan2c_audit_matrix.md:89-96`). | AC-3, AC-4, AC-5 | coding | l8av |
| l8bv | mode-1 -t 56 + `gendp-isa-reviewer` on PE 20. | AC-1, AC-5 | coding | l8b |
| l8c | ISA-lower PE 21 (goto form; `bin_cursors[16]` → `reg[]` band per ABI artifact; odd-tail peel; two-element `mvd` preserved). | AC-3, AC-4, AC-5 | coding | l8bv |
| l8cv | mode-1 -t 56 + `gendp-isa-reviewer` on PE 21 + sort-milestone cluster mode-2 `-t 56 = 295/295` gate. | AC-1, AC-5 | coding | l8c |
| l8d | ISA-lower PE 22 (`bvd[3]` → constexpr-unrolled regs; env-debug → removed; boundary-loop → constexpr unroll; invariant set preserved or strengthened with commit-message proof). | AC-3, AC-4, AC-5, AC-7 | coding | l8cv |
| l8dv | mode-1 -t 56 + `gendp-isa-reviewer` on PE 22 + PE 22 snapshot diff vs oracle. | AC-1, AC-5, AC-7, AC-9 | coding | l8d |
| l8e | ISA-lower PE 23 (ad/ai bools → regs; M23_RD/RI/PI macro temps → regs; register-residency for `DEDUP_META+0/+1/+4/+5/+6/+7/+14..+19` per DEC-1; one intv + one diag kept in regs; controller-visible `+2/+3` and refill/writeback `+10..13` preserved). | AC-3, AC-4, AC-5, AC-8 | coding | l8dv |
| l8ev | mode-1 -t 56 + `gendp-isa-reviewer` on PE 23 + PE 23 snapshot diff vs oracle + dedup-milestone cluster mode-2 `-t 56 = 295/295` gate. | AC-1, AC-5, AC-8, AC-9 | coding | l8e |
| l9a | Cross-magic ABI-collision / RAW / latency audit over ALL lowered controller magics 16..39 (Codex + `gendp-isa-reviewer` batched); output structured findings. | AC-10 | analyze | l8ev |
| l9b | Cross-magic audit over ALL lowered PE magics 19..23. | AC-10 | analyze | l8ev |
| l9c | Fix any findings from `l9a / l9b` under controlled-change rule (AC-2); dedicated amendment commits; list each fix with affected-magic list. | AC-2, AC-10 | coding | l9a, l9b |
| l9cv | Rerun mode-1 -t 56 for every affected earlier magic; rerun cluster mode-2 gate(s) if any magic in scope of the fix was at or below the gate boundary. | AC-1, AC-2, AC-10 | coding | l9c |
| l10 | Final `gwfa_check_correctness.py 2 -t 56 = 295/295`. | AC-1 | coding | l9cv |

## Claude-Codex Deliberation

### Agreements

- PE ABI artifact must land before any lowering (AC-2), mirroring Plan 3c `l6` precedent.
- Frozen PE-visible oracle required for PE 19 / 22 / 23 (the risky magics). Score alone is not enough.
- Oracle capture mechanism must be concrete (script + build flag + dump blocks + output files), mirroring Plan 3c's `scripts/plan3c_capture_snapshot.sh` + `plan3c_snap=1` pattern.
- PE 23 `DEDUP_META` checkpoint contract is pinned in the AC-2 artifact (AC-8) — not left implicit. `+2/+3` (controller-visible) and `+10..13` (controller refill/writeback) are invariant across Plan 3d; only `+0/+1/+4/+5/+6/+7/+14..+19` are subject to DEC-1.
- `pe::reset()` at `pe.cpp:43-46` clears registers and is NOT evidence of cross-magic persistence. Persistence evidence is the magic-23 call envelope at `scripts/gwfa_instruction_generator.py:666-688`, which touches only `gr[10]`.
- `gr[10]` is the PE-sync done flag and is excluded from any PE-side cross-magic register residency.
- `l9a / l9b` are audit tasks and route as `analyze`, not `coding`.
- Cross-magic audit scope must be explicit ABI-collision / RAW / latency — not a re-run of per-magic checks.
- AC labeling + TDD-style positive / negative tests are carried forward from Plan 3c precedent.
- Controlled-change rule on ABI amendments carries forward from Plan 3c.
- Commit messages may reference AC identifiers; source code + comments may not.
- 295/295 on every mode-2 gate (cluster and final) is a HARD requirement per user confirmation.

### Resolved Disagreements

- **`pe::reset()` as persistence evidence**: Codex round-1 flagged that `pe::reset()` clears registers and therefore argues against, not for, cross-call persistence. **Resolved** in v2 by removing `pe::reset()` from the DEC-1 Claude Position and replacing it with the magic-23 call envelope as the actual evidence source. The artifact (AC-2) states this explicitly.
- **Lower-bound snapshot scope consistency**: v1 allowed PE 23-only snapshots in the lower bound, contradicting AC-9's PE 19 / 22 / 23 scope. **Resolved** in v2 by requiring PE 19 / 22 / 23 snapshots at the lower bound; PE 20 / 21 snapshots remain optional (Upper Bound).
- **Oracle mechanism concreteness**: v1 said `l8` "commits" the oracle without a capture mechanism. **Resolved** in v2 by specifying `scripts/plan3d_capture_snapshot.sh`, `plan3d_snap=1` Makefile target, `PLAN3D_TRACE_SNAPSHOT` preprocessor symbol, and the three per-PE dump blocks — all modeled after Plan 3c.
- **AC-9 task-reference typo**: v1 said "After PE 22 lands (l8c)" but PE 22 is `l8d`. **Resolved** in v2 to `l8d` / `l8dv`.
- **DEC-1 blocking `l8`**: v1 pinned DEC-1 at `l8` without explicitly blocking `l8` on DEC-1. **Resolved** in v2 by adding DEC-1 as an `l8` prerequisite; now folded into the v3 plan (DEC-1 resolved = register-residency).
- **DEC-1 (PE 23 register-residency)**: Codex first-pass flagged as high-stakes, requiring explicit user sign-off. **Resolved** by user: register-residency adopted for `DEDUP_META+0/+1/+4/+5/+6/+7/+14..+19`; `+2/+3` and `+10..13` remain in SPM unchanged.
- **DEC-2 (cluster gate placement)**: Codex preferred two gates (after PE 21 and after PE 23); Claude preferred one gate (after PE 23). **Resolved** by user: TWO gates. The plan now runs a sort-milestone gate after PE 21 and a dedup-milestone gate after PE 23.
- **DEC-3 (magic ordering)**: Codex first-pass suggested deferring PE 19 to the end; Claude preferred draft ordering (PE 19 first). **Resolved** by user: draft ordering retained (PE 19 → 20 → 21 → 22 → 23).
- **PE 23 snapshot dump boundary**: v2 left "representative case iteration" ambiguous. **Resolved** in v3 by specifying the first PING invocation of magic 23 within case 0 of the dataset.

### Convergence Status

- Final Status: `converged`.
- Rounds: 1 Codex first-pass analysis; 1 Claude candidate (v1); 2 Codex convergence reviews (round 1 produced 3 DISAGREEs + 5 REQUIRED_CHANGES addressed in v2; round 2 produced no REQUIRED_CHANGES, no DISAGREE, only two optional polishes). User decisions DEC-1 / DEC-2 / DEC-3 and the 295/295 HARD gate were resolved through `AskUserQuestion` in Phase 6.

## Pending User Decisions

None. All items raised during Codex first-pass, convergence rounds, and user-decision gate were resolved. DEC-1 (register-residency), DEC-2 (two cluster gates), DEC-3 (draft ordering), and the 295/295 HARD requirement are each reflected in the relevant ACs and task breakdown.

## Implementation Notes

### Code Style Requirements

- Implementation code and comments must NOT contain plan-specific terminology such as "AC-", "Milestone", "Step", "Phase", or similar workflow markers. These terms are for plan documentation only, not the resulting codebase.
- Use descriptive, domain-appropriate naming in code (e.g. `m19_arc_loop`, `m22_b_done`, `m23_dedup_vd`, `fin0_hash_miss`).
- Commit messages may reference AC identifiers; source files may not.

### Half-register convention

- `// half-reg hi` and `// half-reg lo` comments mark any 16-bit packed-half access (e.g. `gr[X] = (unsigned)gr[Y] >> 16;  // half-reg hi` or `gr[X] = gr[Y] & 0xFFFF;  // half-reg lo`).
- Greppable for `gendp-isa-reviewer` and the mechanical pre-check.

### Verification Matrix

| Magic | Lowering task | Product checks | Required runs |
|-------|---------------|----------------|---------------|
| PE 19 | l8a | AC-3, AC-4, AC-5, AC-6 | mode-1; PE 19 snapshot diff |
| PE 20 | l8b | AC-3, AC-4, AC-5 | mode-1 |
| PE 21 | l8c | AC-3, AC-4, AC-5 | mode-1; sort-milestone cluster mode-2 = 295/295 |
| PE 22 | l8d | AC-3, AC-4, AC-5, AC-7 | mode-1; PE 22 snapshot diff |
| PE 23 | l8e | AC-3, AC-4, AC-5, AC-8 | mode-1; PE 23 snapshot diff; dedup-milestone cluster mode-2 = 295/295 |
| (audit) | l9a / l9b | AC-10 | analyze-only |
| (final) | l10 | AC-1 | mode-2 = 295/295 |

### Reference examples (frozen — do NOT modify)

- Controller: 7, 8, 9, 12, 14, 15 in `pe_array.cpp`.
- PE: 8 (`pe.cpp:708`), 11 (`pe.cpp:1087`), 13 (`pe.cpp:1151`).

### Exempt (do NOT touch)

- Controller 1, 3, 4, 5, 6, 17.

### Deleted / deprecated

- Controller 2, 10, 26 (removed in Plan 1).

### 12 ISA-like rules in force (authoritative wording from draft)

1. Each line = one GenDP ISA operation.
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired instructions.
3. Registers only: `gr[] / reg[] / s1c[] / spm[] / mm[]`; no C++ runtime variables.
4. Gotos with labels instead of if/else/for/while; macro loops (e.g. `for pe in range(4)`) allowed.
5. Compile-time constants (`constexpr`) allowed.
6. SPM: 2-cycle latency (pipelined OK, but cannot use loaded value for 2 cycles).
7. MM/S2: `// waitLSQ` comment required between load and use.
8. S1c: 1-cycle latency.
9. `mvdq` round-robin PE streaming for bulk; scalar `mv` only for non-contiguous.
10. No `std::min / std::max` on controller; use branch conditions. `min / max` fine on PE.
11. Helper macros acceptable if all live state is in registers/memory.
12. PE compute instructions deferred to a future pass.

### Per-magic validation rules (authoritative wording from draft)

- After EACH magic: `make -j ADDRESS_SANITIZER=0`, `scripts/gwfa_check_correctness.py 1 -t 56`, commit.
- After each commit: run `gendp-isa-reviewer` on the changed magic.
- Fix hazards before next magic.
- At end of plan: `scripts/gwfa_check_correctness.py 2 -t 56` (295/295 required).

## Output File Convention

This plan file is the main output (`isaLikeAllGwfaPlan3dH.md`). `alternative_plan_language` resolves to empty in the current humanize config; no translated variant is written.

--- Original Design Draft Start ---

# GWFA ISA-Like Rewrite Plan 3d: ISA Lower PE 19-23 + Final Review

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

See Plans 3a/3b/3c for controller register ABI. This plan creates the PE register ABI (gr[]/reg[] usage across PE magic boundaries). PE magics 8 and 13 are reference examples.

---

## Goal Description

ISA-lower PE magics 19, 20, 21, 22, 23. Then run comprehensive cross-magic ISA review and final verification.

## Prerequisites

Plans 1+2a+2b+2c+3a+3b+3c complete. All controller magics ISA-lowered. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after EACH magic, mode 2 at end)
- AC-2: No C++ runtime variables (except PE compute deferred)
- AC-3: No runtime if/else/for/while
- AC-4: VLIW pairing, no RAW hazards (ISA reviewer per magic)
- AC-5: Latency gaps and waitLSQ comments
- AC-6: Comprehensive cross-magic ISA review finds no new hazards
- AC-7: Final mode 2 -t 56: 295/295 pass

## Task Breakdown

### Phase 1: PE ISA lowering

| Task ID | Description | Tag |
|---------|-------------|-----|
| l8 | Plan PE register allocation. Document gr[]/reg[] usage. Reference PE 8/13. Half-register opportunities. | analyze |
| l8a | ISA-lower PE 19: lambdas→inline, locals→gr/reg, half-regs for hash/vertex, mvd for contiguous, gotos for control | coding |
| l8av | Verify + ISA review PE 19 | coding |
| l8b | ISA-lower PE 20: locals→gr/reg, contiguous (vd,k) load already done, bin count loop→goto | coding |
| l8bv | Verify + ISA review PE 20 | coding |
| l8c | ISA-lower PE 21: locals→gr/reg, scatter loop→goto, bin_cursors→s1c or unrolled regs | coding |
| l8cv | Verify + ISA review PE 21 | coding |
| l8d | ISA-lower PE 22: remaining locals→gr/reg, SPM latency gaps, merge loop already goto-based | coding |
| l8dv | Verify + ISA review PE 22 (test case 2) | coding |
| l8e | ISA-lower PE 23: M23 macros→register ops, state machine already goto-based, locals→gr/reg, intv+diag stay in regs | coding |
| l8ev | Verify + ISA review PE 23 | coding |

### Phase 2: Comprehensive final review

| Task ID | Description | Tag |
|---------|-------------|-----|
| l9a | Comprehensive ISA reviewer: ALL controller magics 16-39 as batch — catch cross-magic register clobber | coding |
| l9b | Comprehensive ISA reviewer: ALL PE magics 19-23 as batch | coding |
| l9c | Fix any cross-magic hazards found | coding |
| l9cv | Verify fixes: mode 1 -t 56 | coding |
| l10 | Final verification: mode 2 -t 56 (295/295 required) | coding |

--- Original Design Draft End ---
