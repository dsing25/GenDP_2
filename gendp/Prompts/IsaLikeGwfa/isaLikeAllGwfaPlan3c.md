# GWFA ISA-Like Rewrite Plan 3c: ISA Lower Controller 32-39

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

See Plans 3a/3b for the register ABI table. This plan extends it for the dedup/finalize pipeline (magics 32-39). Task l6 must verify and extend the ABI before lowering begins.

---

## Goal Description

ISA-lower controller magics 32, 33, 34, 35, 36, 37, 38, 39. Each lowered, verified, and ISA-reviewed individually.

## Prerequisites

Plans 1+2a+2b+2c+3a+3b complete. Controller 16-31 ISA-lowered. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after EACH magic, mode 2 at end)
- AC-2: No C++ runtime variables
- AC-3: No runtime if/else/for/while
- AC-4: VLIW pairing, no RAW hazards (ISA reviewer per magic)
- AC-5: Latency gaps and waitLSQ comments

## Task Breakdown

| Task ID | Description | Tag |
|---------|-------------|-----|
| l6 | Plan register allocation for magics 32-39. Extend register ABI from Plans 3a/3b. | analyze |
| l6a | ISA-lower controller 32: gather loops→goto, boundary merge state→gr, PE-serial bulk mvdq preserved | coding |
| l6av | Verify + ISA review controller 32 | coding |
| l6b | ISA-lower controller 33: reload conditionals→goto, tile clamping→branch | coding |
| l6bv | Verify + ISA review controller 33 | coding |
| l6c | ISA-lower controller 34: already mostly ISA-like. Verify and clean up. | coding |
| l6cv | Verify + ISA review controller 34 | coding |
| l6d | ISA-lower controller 35: writeback loop→goto, pre-computed destinations preserved | coding |
| l6dv | Verify + ISA review controller 35 | coding |
| l6e | ISA-lower controller 36: already has goto labels. Finish register-only, add latency comments. | coding |
| l6ev | Verify + ISA review controller 36 | coding |
| l6f | ISA-lower controller 37: binary search→goto, tile load→register ops | coding |
| l6fv | Verify + ISA review controller 37 | coding |
| l6g | ISA-lower controller 38: already has fused search. Finish register-only. | coding |
| l6gv | Verify + ISA review controller 38 | coding |
| l6h | ISA-lower controller 39: already mostly register-based. Final cleanup. | coding |
| l6hv | Verify + ISA review controller 39 | coding |
| l7 | Full verification: mode 2 -t 56 | coding |

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
