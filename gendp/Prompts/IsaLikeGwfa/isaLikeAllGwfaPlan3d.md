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

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
