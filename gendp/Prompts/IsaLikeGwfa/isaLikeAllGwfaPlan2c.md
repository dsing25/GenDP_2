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

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
