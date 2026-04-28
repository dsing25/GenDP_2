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

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
