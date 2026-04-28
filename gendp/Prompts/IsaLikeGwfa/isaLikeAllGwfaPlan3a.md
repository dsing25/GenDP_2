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
