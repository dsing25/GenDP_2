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

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
