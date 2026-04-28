NOTE! when generating the plan, keep in mind that 3a has not finished yet. We are generating this
plan ahead of time so we are prepared to launch as soon as it does finish, but that means the
codebase might change a bit in between
# GWFA ISA-Like Rewrite Plan 3b: ISA Lower Controller 24-31

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

See Plan 3a for the initial register ABI table. This plan extends it for the sort/merge pipeline (magics 24-31). Task l4 must verify and extend the ABI before lowering begins.

---

## Goal Description

ISA-lower controller magics 24, 25, 28, 29, 30, 31. Each lowered, verified, and ISA-reviewed individually.

## Prerequisites

Plans 1+2a+2b+2c+3a complete. Controller 16-20 ISA-lowered. Code passes mode 2.

## Acceptance Criteria

- AC-1: Correctness (mode 1 after EACH magic, mode 2 at end)
- AC-2: No C++ runtime variables
- AC-3: No runtime if/else/for/while
- AC-4: VLIW pairing, no RAW hazards (ISA reviewer per magic)
- AC-5: Latency gaps and waitLSQ comments

## Task Breakdown

| Task ID | Description | Tag |
|---------|-------------|-----|
| l4 | Plan register allocation for magics 24-31. Extend Cross-Magic Register ABI from Plan 3a. Document live gr[] across sort/merge boundaries. | analyze |
| l4a | ISA-lower controller 24: locals→gr, tile size→register ops, mvdq fast path preserved | coding |
| l4av | Verify + ISA review controller 24 | coding |
| l4b | ISA-lower controller 25: locals→gr, bin iteration as macro loop, scatter offset→register ops | coding |
| l4bv | Verify + ISA review controller 25 | coding |
| l4c | ISA-lower controller 28: binary search arrays→s1c or unrolled gr, while→goto | coding |
| l4cv | Verify + ISA review controller 28 | coding |
| l4d | ISA-lower controller 29: locals→gr, tile clamping→branches, intv boundary→gr | coding |
| l4dv | Verify + ISA review controller 29 | coding |
| l4e | ISA-lower controller 30: locals→gr, reload conditionals→goto labels | coding |
| l4ev | Verify + ISA review controller 30 | coding |
| l4f | ISA-lower controller 31: locals→gr, autoincrement cursors from Plan 2a, output loops→goto | coding |
| l4fv | Verify + ISA review controller 31 | coding |
| l5 | Full verification: mode 2 -t 56 | coding |

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
