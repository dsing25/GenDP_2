# GWFA ISA-Like Rewrite Plan

## Goal Description

Rewrite all GWFA magic instructions in `pe_array.cpp` (controller) and `pe.cpp` (PE) to ISA-like C++ that can be directly lowered to GenDP assembly. Each line of the rewritten magic represents one ISA operation, and each pair of lines represents one VLIW cycle. The C++ magic itself does not simulate per-cycle timing, but the structure guarantees correct ISA lowering.

**Scope:**
- **Delete**: Controller magics 2, 10, 26 (deprecated)
- **Exempt (do not touch)**: Controller 1, 3, 4, 5, 6, 17
- **Reference examples (frozen)**: Controller 7, 8, 9, 12, 14, 15; PE 8, 11, 13
- **Rewrite (controller)**: 16, 18, 19, 20, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39
- **Rewrite (PE)**: 19, 20, 21, 22, 23

**ISA-like rules** (apply to all rewrites):
1. Each line = one GenDP ISA operation
2. Each pair of lines = one VLIW cycle; no RAW hazards between paired instructions
3. Registers only: gr[], reg[], s1c[], spm[], mm[]; no C++ runtime variables
4. Gotos with labels instead of if/else/for/while; macro loops (e.g., `for pe in range(4)`) allowed
5. Compile-time constants (`constexpr`) allowed
6. SPM: 2-cycle latency (pipelined OK, but cannot use loaded value for 2 cycles)
7. MM/S2: waitLSQ comment required between load and use
8. S1c: 1-cycle latency
9. mvdq round-robin PE streaming for bulk data transfers; scalar mv only for non-contiguous data
10. No `std::min`/`std::max` on controller; use branch conditions. min/max fine on pe
11. Helper macros acceptable if all live state is in registers/memory
12. PE compute instructions deferred to a future pass

## Acceptance Criteria

- AC-1: Correctness preserved after each magic rewrite
  - `gwfa_check_correctness.py 1 -t 56` passes after each individual magic rewrite
  - `gwfa_check_correctness.py 2 -t 56` passes at each milestone completion
  - AC-1.1: Mode 3 (debug single iteration) used for diagnosing failures

- AC-2: No C++ runtime variables in rewritten magics
  - All state lives in gr[], reg[], s1c[], spm[], mm[], or constexpr
  - Local aliases to register arrays (e.g., `int (&gr)[N] = main_addressing_register`) are acceptable

- AC-3: No runtime C++ control flow in rewritten magics
  - All branching uses goto + labels
  - Macro loops like `for (int pe = 0; pe < 4; pe++)` for PE iteration are acceptable

- AC-4: mvdq round-robin PE streaming where specified by draft
  - Controller 19,20,24,25,28,29,30,31,32,33,34,35 use mvdq round-robin for bulk loads
  - PE 19,20,21 use mvd for two-element loads
  - Loop peeling handles remainder elements at boundaries

- AC-5: Deprecated magics removed with full cleanup
  - Controller magics 2, 10, 26 code deleted from pe_array.cpp
  - References in instruction generator cleaned up
  - Simulator compiles and runs without these magics

- AC-6: VLIW instruction pairing with no RAW hazards
  - Each pair of instructions has no read-after-write dependency
  - gendp-isa-reviewer agent confirms no hazards in rewritten code

- AC-7: Proper latency handling
  - SPM loads have at least 1 instruction gap before use (2-cycle latency, pipelined)
  - MM/S2 loads have `// waitLSQ` comment before use of loaded value
  - Instructions interleaved into latency gaps where possible to mask latency

- AC-8: Specific per-magic requirements from draft
  - Controller 18: function calls replaced with constexpr constants
  - Controller 19: PE loop is innermost (bins outer, PEs inner)
  - Controller 20: fin0_load_batch restructured (mvdq common case + mv fallback, no return value, half-registers, no bitmap bookkeeping)
  - Controller 24: mvdq round-robin, peel only final iteration, tilesize multiple of 4
  - Controller 28: interleaved binary search across PEs, waitLSQ per round
  - Controller 28: mvdq streaming with pre-loop checks, tight mvdq loop
  - Controller 31: autoincrement cursors for writeback
  - Controller 32: first/last intv to s1c for seam merge (no MM lookups for boundary merge)
  - Controller 33: s1c lookup as separate instruction (no nested mm[s1c[X]])
  - Controller 36: no sorted check, mid-diagonal start, boundary fixup via s1c max
  - Controller 38: fused lo/hi binary searches, waitLSQ after each result
  - PE 19: half-registers and mvd where possible
  - PE 20,21: two-element mvd loads
  - PE 22: remove second buffer check, streamline inner merge loop, hoist checks
  - PE 23: minimize state save/restore (use all 48+ registers), no deep functions, keep current intv+diag in registers

- AC-9: Controller 16 rewritten ISA-like
  - Variables replaced with registers, control flow with gotos
  - gwfa_sync_counters call left as-is (will be removed in future pass)
  - gwfa_get_intv_n/gwfa_get_mm calls replaced with register/constexpr equivalents where feasible

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)
All 18 controller magics and 5 PE magics rewritten to ISA-like style with all draft-specified optimizations applied. mvdq round-robin with loop peeling everywhere specified. Half-registers used where beneficial. All latency gaps filled with useful instructions. Every per-magic specific requirement from the draft fully addressed. No remaining C++ variables or control flow in rewritten magics.

### Lower Bound (Minimum Acceptable Scope)
All listed magics rewritten to ISA-like style (registers, gotos, VLIW pairing, one op per line). mvdq round-robin applied where draft requires it even if loop peeling is simple. Latency comments present even if not all gaps optimally filled. Per-magic requirements addressed even if some optimizations are basic.

### Allowed Choices
- Can use: existing helper macros (mvdq_copy etc.), new helper macros for common ISA patterns, constexpr constants, register array aliases, macro loops for PE iteration
- Can use: gotos with descriptive labels (e.g., `m28_bs_done:`)
- Cannot use: C++ runtime variables, if/else/for/while for data-dependent flow, std::min/max on controller, function calls with return values, heap allocation, lambdas/closures

## Feasibility Hints and Suggestions

> **Note**: This section is for reference and understanding only.

### Conceptual Approach

Each magic rewrite follows this pattern:
1. Read the existing magic code and understand its algorithm
2. Identify all variables — map each to a gr[] or reg[] register
3. Replace control flow with goto + labels
4. Replace scalar mv loops with mvdq round-robin (PEs inner loop)
5. Identify SPM/MM loads and insert latency gaps or waitLSQ comments
6. Pair instructions into VLIW slots, checking for RAW hazards
7. Apply draft-specific optimizations (half-registers, restructuring, etc.)
8. Run `gwfa_check_correctness.py 1 -t 56` to verify correctness
9. Run gendp-isa-reviewer agent to check for ISA hazards

**mvdq round-robin pattern** (reference: controller magic 7):
```
// Peel: handle tile_n % 4 per PE
m_peel:
    if (gr[13] <= 0) goto m_peel_done; gr[13] -= 1;
    spm[gr[dst]] = mm[gr[src]]; spm[gr[dst]+1] = mm[gr[src]+1]; // mvd
    gr[src] += 2; gr[dst] += 2;
    goto m_peel;
m_peel_done:
// Main loop: round-robin across PEs at 8-word (mvdq) granularity
m_outer:
    gr[13] = 0;                                  // any-PE-active flag
    if (gr_pe0_src >= gr_pe0_end) goto m_pe1;    // PE0 done?
    mvdq_copy(&spm[gr_pe0_dst], &mm[gr_pe0_src], 8);
    gr_pe0_src += 8; gr_pe0_dst += 8; gr[13] = 1;
m_pe1:
    if (gr_pe1_src >= gr_pe1_end) goto m_pe2;    // PE1 done?
    mvdq_copy(&spm[gr_pe1_dst], &mm[gr_pe1_src], 8);
    // ... PE2, PE3 ...
    if (gr[13] != 0) goto m_outer;
```

### Relevant References
- `pe_array.cpp` — Controller magic 7 (line ~937): canonical mvdq round-robin with peel
- `pe_array.cpp` — Controller magic 8 (line ~1055): SPM scan with latency handling
- `pe_array.cpp` — Controller magic 9 (line ~1126): writeback with FIFO compare-swap
- `pe.cpp` — PE magic 8 (line ~677): PE-side goto-based extend with half-registers
- `pe.cpp` — PE magic 13 (line ~1120): PE-side branch tree with speculative computation
- `docs.md` — ISA manual, opcode reference, VLIW hazard rules
- `scripts/gwfa_instruction_generator.py` — legal ISA operations and patterns
- `/data4/kaplannp/GenDP2/gdp/gendp/Prompts/` — prior prompt references

### Register/State ABI Table (Cross-Magic Boundaries)

Key state that persists across magic boundaries and must be preserved:

**FIN0 pipeline (15 → 20 → PE19 → 18):**
- s1c[20..31]: FIN0 batch metadata
- gr[24..31]: counter state from Phase 2
- SPM FIN0 tile regions: diag data loaded by 20, processed by PE19, read back by 18

**Sort/merge/dedup pipeline (16 → 34 → 19 → 24/25 → 28 → 29/30/31 → 32/33 → 35/36 → 37/38/39):**
- s1c[144]: diag_base (saved by 16, used by sort/merge)
- s1c[145]: n_a (saved by 16)
- s1c[146]: old intv_n (saved by 16)
- s1c[147]: n_phase1_v (saved by 16)
- s1c[148]: n_a again (saved by 16)
- s1c[152]: active_intv_base (saved by 16)
- s1c[153]: active_diag_base (saved by 16)
- s1c[155]: next_intv_n (saved by 16, read by 39)
- s1c[0..15]: global prefix sums (written by 19)
- s1c[16..79]: pe_start_in_bin offsets (written by 19)
- s1c[80..143]: tile_cumulative offsets (written by 19, updated by 25)
- gr[3], gr[4], gr[6], gr[24]: sort loop state (set by 16, used by 34+)

## Dependencies and Sequence

### Milestones

**Strategy: structural changes first, ISA lowering second.** Complex algorithmic restructuring (loop reordering, mvdq patterns, binary search interleaving, seam merge optimization) is done while the code is still readable C++ with variables and control flow. Once all structural changes are verified correct, a separate ISA lowering pass converts everything to registers, gotos, and VLIW pairing. This avoids debugging algorithmic bugs in brittle ISA-like code.

1. **Cleanup and Infrastructure**: Delete deprecated magics 2, 10, 26. Add waitLSQ between magic 7→8 in instruction generator. Rename SORT_BIN_REG to reflect scratchpad region. Establishes a clean baseline.

2. **Complex Structural Changes (Controller)**: The hardest algorithmic restructuring, done first while code is readable.
   - Controller 20: Restructure fin0_load_batch from greedy bitmap to two-loop (mvdq common case + mv fallback), remove return value, remove bitmap bookkeeping
   - Controller 28: Restructure binary search from per-PE sequential to interleaved across all PEs, add mvdq streaming with pre-loop checks
   - Controller 32: Restructure seam merge to write first/last intv to s1c instead of MM lookups
   - Controller 36: Remove linear scan, implement mid-diagonal start with boundary fixup via s1c max
   - Controller 38: Fuse lo/hi binary search while loops into single interleaved loop

3. **Complex Structural Changes (PE)**: Hard PE restructuring, also done while readable.
   - PE 22: Remove second buffer check, restructure inner merge loop (establish tile sizes upfront, iterate fast, handle buffer switch as special case, hoist checks)
   - PE 23: Minimize state save/restore (map 20 words to registers), eliminate deep functions, keep current intv+diag in registers

4. **Medium Structural Changes (Controller)**: Moderate restructuring.
   - Controller 16: Inline variable logic, replace min/max with branches (keep sync_counters as-is)
   - Controller 18: Replace gwfa_get_*_off() function calls with constexpr constants
   - Controller 19: Flip loop order (bins outer, PEs inner) to avoid s1c intermediary
   - Controller 33: Separate nested mm[s1c[X]] into two instructions

5. **mvdq Round-Robin Conversion (All)**: Convert all scalar mv loops to mvdq round-robin with loop peeling. This is a consistent pattern applied across many magics.
   - Controller: 24, 25, 28 (data load portion), 29, 30, 31, 32, 33, 34, 35
   - Controller 31: Also add autoincrement cursors for writeback
   - PE: 19 (mvd + half-registers), 20, 21 (two-element mvd loads)

6. **Structural Changes for Remaining Magics**: Full structural rewrite of 37, 39, and any issues found in general compliance pass.

7. **ISA Lowering Pass (All Magics)**: Now that all structural changes are verified, lower all rewritten magics to ISA-like style in one pass:
   - Variables → gr[]/reg[] registers
   - if/else/for/while → goto + labels
   - VLIW slot pairing (two instructions per cycle, no RAW hazards)
   - Latency annotation (SPM gaps, waitLSQ comments for MM/S2)
   - Half-register usage where beneficial
   - One ISA operation per line

8. **Final Verification and ISA Review**: Mode 2 full verification, gendp-isa-reviewer agent pass on all rewritten magics, fix any remaining issues.

**Dependency graph:**
- Milestone 1 is independent (do first)
- Milestones 2 and 3 are independent of each other (can be parallel)
- Milestone 4 depends on Milestone 1 (clean baseline)
- Milestone 5 depends on Milestones 2-4 (structural changes done before adding mvdq patterns to restructured code)
- Milestone 6 depends on Milestone 5
- Milestone 7 (ISA lowering) depends on all structural milestones (2-6) being verified correct
- Milestone 8 depends on Milestone 7

## Task Breakdown

Each task must include exactly one routing tag:
- `coding`: implemented by Claude
- `analyze`: executed via Codex (`/humanize:ask-codex`)

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| | **Milestone 1: Cleanup and Infrastructure** | | | |
| t1 | Delete controller magics 2, 10, 26 + clean references | AC-5 | coding | - |
| t2 | Add waitLSQ between magic 7 and 8 in instruction generator | AC-7 | coding | - |
| t3 | Rename SORT_BIN_REG to scratchpad region name | AC-8 | coding | - |
| t4 | Verify baseline: mode 1 -t 56 | AC-1 | coding | t1,t2,t3 |
| | **Milestone 2: Complex Structural Changes (Controller)** | | | |
| t5 | Analyze controller 20 (fin0_load_batch) for restructure plan | AC-8 | analyze | t4 |
| t6 | Restructure controller 20: two-loop design (mvdq common + mv fallback), remove return value, remove bitmap bookkeeping | AC-8 | coding | t5 |
| t7 | Analyze controller 28 for interleaved binary search restructure | AC-8 | analyze | t4 |
| t8 | Restructure controller 28: interleave binary search across PEs instead of per-PE sequential | AC-8 | coding | t7 |
| t9 | Analyze controller 32 for seam merge restructure | AC-8 | analyze | t4 |
| t10 | Restructure controller 32: write first/last intv to s1c instead of MM boundary lookups | AC-8 | coding | t9 |
| t11 | Restructure controller 36: remove linear scan, implement mid-diagonal start + s1c boundary fixup | AC-8 | coding | t4 |
| t12 | Restructure controller 38: fuse lo/hi binary search while loops into single interleaved loop | AC-8 | coding | t4 |
| t13 | Remove sanity check and verify_splits from controller 28 | AC-8 | coding | t4 |
| t14 | Remove sorted-output check from controller 36 | AC-8 | coding | t4 |
| t15 | Verify milestone 2: mode 2 -t 56 | AC-1 | coding | t6,t8,t10-t14 |
| | **Milestone 3: Complex Structural Changes (PE)** | | | |
| t16 | Analyze PE 22 for inner loop restructure plan | AC-8 | analyze | t4 |
| t17 | Restructure PE 22: remove second buffer check, establish tile sizes upfront, streamline inner loop, hoist checks | AC-8 | coding | t16 |
| t18 | Analyze PE 23 for state minimization and restructure plan | AC-8 | analyze | t4 |
| t19 | Restructure PE 23: map state to registers (eliminate 20-word save/restore), remove deep functions, keep intv+diag in regs | AC-8 | coding | t18 |
| t20 | Verify milestone 3: mode 2 -t 56 | AC-1 | coding | t17,t19 |
| | **Milestone 4: Medium Structural Changes (Controller)** | | | |
| t21 | Restructure controller 16: replace min/max with branches, inline logic (keep sync_counters) | AC-8,AC-9 | coding | t4 |
| t22 | Restructure controller 18: replace gwfa_get_*_off() calls with constexpr constants | AC-8 | coding | t4 |
| t23 | Restructure controller 19: flip loop order (bins outer, PEs inner), load directly to registers | AC-8 | coding | t4 |
| t24 | Restructure controller 33: separate nested mm[s1c[X]] into two instructions | AC-8 | coding | t4 |
| t25 | Verify milestone 4: mode 2 -t 56 | AC-1 | coding | t21-t24 |
| | **Milestone 5: mvdq Round-Robin Conversion** | | | |
| t26 | Analyze mvdq round-robin pattern for controller 24,25,29,30,31,34,35 | AC-4 | analyze | t15,t25 |
| t27 | Convert controller 24 to mvdq round-robin (peel final iteration only, tilesize multiple of 4) | AC-4,AC-8 | coding | t26 |
| t28 | Convert controller 25 to mvdq round-robin with loop peeling | AC-4,AC-8 | coding | t26 |
| t29 | Convert controller 29 to mvdq round-robin (peel final only) | AC-4,AC-8 | coding | t26 |
| t30 | Convert controller 30 to mvdq round-robin | AC-4,AC-8 | coding | t26 |
| t31 | Convert controller 31 to mvdq round-robin + autoincrement cursors | AC-4,AC-8 | coding | t26 |
| t32 | Convert controller 34 to mvdq round-robin | AC-4 | coding | t26 |
| t33 | Convert controller 35 to mvdq round-robin (multiples of two) | AC-4,AC-8 | coding | t26 |
| t34 | Add mvdq round-robin to controller 28 data load portion (pre-loop checks, tight mvdq loop) | AC-4,AC-8 | coding | t15 |
| t35 | Add mvdq round-robin to controller 32 (both diags and intvs) | AC-4,AC-8 | coding | t15 |
| t36 | Add mvdq round-robin to controller 33 | AC-4,AC-8 | coding | t25 |
| t37 | Convert PE 20 to two-element mvd loads | AC-4,AC-8 | coding | t4 |
| t38 | Convert PE 21 to two-element mvd loads | AC-4,AC-8 | coding | t4 |
| t39 | Convert PE 19 to mvd + half-registers | AC-4,AC-8 | coding | t15 |
| t40 | Verify milestone 5: mode 2 -t 56 | AC-1 | coding | t27-t39 |
| | **Milestone 6: Remaining Structural Changes** | | | |
| t41 | Analyze controller 37, 39 for structural issues | AC-8 | analyze | t40 |
| t42 | Structural rewrite of controller 37 | AC-8 | coding | t41 |
| t43 | Structural rewrite of controller 39 | AC-8 | coding | t41 |
| t44 | General compliance pass: scan all magics for missed structural issues | AC-4,AC-8 | analyze | t40,t20 |
| t45 | Fix any structural issues found in compliance pass | AC-1,AC-8 | coding | t44 |
| t46 | Verify milestone 6: mode 2 -t 56 | AC-1 | coding | t42,t43,t45 |
| | **Milestone 7: ISA Lowering Pass** | | | |
| t47 | Analyze register allocation plan across all rewritten magics | AC-2,AC-3,AC-6 | analyze | t46 |
| t48 | ISA-lower controller 16,18,19,20 (variables→regs, control flow→gotos, VLIW pairing, latency) | AC-2,AC-3,AC-6,AC-7 | coding | t47 |
| t49 | Verify after controller 16,18,19,20 lowering: mode 1 -t 56 | AC-1 | coding | t48 |
| t50 | ISA-lower controller 24,25,28,29,30,31 | AC-2,AC-3,AC-6,AC-7 | coding | t47 |
| t51 | Verify after controller 24-31 lowering: mode 1 -t 56 | AC-1 | coding | t50 |
| t52 | ISA-lower controller 32,33,34,35,36,37,38,39 | AC-2,AC-3,AC-6,AC-7 | coding | t47 |
| t53 | Verify after controller 32-39 lowering: mode 1 -t 56 | AC-1 | coding | t52 |
| t54 | ISA-lower PE 19,20,21,22,23 | AC-2,AC-3,AC-6,AC-7 | coding | t47 |
| t55 | Verify after PE lowering: mode 1 -t 56 | AC-1 | coding | t54 |
| t56 | Verify milestone 7: mode 2 -t 56 | AC-1 | coding | t49,t51,t53,t55 |
| | **Milestone 8: Final Verification and ISA Review** | | | |
| t57 | ISA reviewer pass on all rewritten controller magics | AC-6 | coding | t56 |
| t58 | ISA reviewer pass on all rewritten PE magics | AC-6 | coding | t56 |
| t59 | Fix any ISA hazards or issues found | AC-1,AC-6,AC-7 | coding | t57,t58 |
| t60 | Final verification: mode 2 -t 56 | AC-1 | coding | t59 |

## Claude-Codex Deliberation

### Agreements
- Overall rewrite direction is reasonable: push state into gr[]/s1c[]/spm[]/mm[], explicit control flow, visible latency/hazard comments
- FIN0 pipeline (15→20→PE19→18) is tightly coupled and should be isolated as its own milestone
- Continuous correctness checking (mode 1 per-change, mode 2 per-milestone) is the right model
- Deleting deprecated magics requires cleaning decode paths, generator symbols, and docs together
- The revised test matrix (mode 1/2/3 with -t for parallelism) is correct
- Relaxing AC-2/3 to allow constexpr, macro loops, and register array aliases is reasonable
- Non-ISA compute operations (hash, multiply) are deferred per draft ("compute later")
- VLIW pairing is a review guideline enforced by ISA reviewer agent, not an automated hard gate
- Magics 37 and 39 exist in the codebase and are part of the sort/merge/dedup flow

### Resolved Disagreements
- **Scope authority**: Codex initially suggested splitting core GWFA vs sort/merge/dedup into separate projects. Claude noted the draft treats all non-exempt magics as one scope. Resolved: one project, both subsystems in scope. Draft + code is the scope authority, not magicDirectory.md.
- **Controller 16**: Initially scoped out based on stale magicDirectory.md. Codex correctly identified it as being on the active execution path. User confirmed: include 16, but leave gwfa_sync_counters as-is (being removed later).
- **AC-1 testing semantics**: Claude initially described `-t 56` as "fast" and `-t 2` as "thorough." Codex correctly identified that `-t N` controls thread parallelism while mode 1/2/3 controls coverage. Resolved with correct mode/thread semantics.
- **AC-2/3 rigidity**: Claude initially proposed strict no-variable, no-control-flow rules. Codex noted existing ISA magics use local aliases and bounded setup loops. Resolved: allow constexpr, macro loops, register aliases; forbid runtime variables and data-dependent C++ control flow.
- **Helper abstractions**: Claude recommended existing helpers only. User decided: new helper macros are OK if all live state stays in registers/memory.
- **Magics 34/37/39**: Claude initially proposed review-only. User decided: full rewrite for all three.

### Convergence Status
- Final Status: `converged`
- Rounds: 2
- All REQUIRED_CHANGES from round 1 addressed in round 2
- No material plan changes between round 2 revision and final

## Pending User Decisions

All user decisions have been resolved during Phase 6:

- DEC-1: Controller magic 16 scope
  - Claude Position: Exclude per magicDirectory
  - Codex Position: Include — on active execution path
  - Tradeoff Summary: magicDirectory is stale; draft does not exclude 16
  - Decision Status: `Include 16, but leave sync_counters as-is (being removed later)`

- DEC-2: Magics 34, 37, 39 scope
  - Claude Position: Review only, fix if needed
  - Codex Position: 37/39 exist, should be in scope
  - Tradeoff Summary: All three are part of the sort/merge/dedup flow
  - Decision Status: `Full rewrite all three`

- DEC-3: ISA-like definition
  - Claude Position: Legal decomposition (directly lowerable)
  - Codex Position: N/A — open question
  - Tradeoff Summary: Each line = 1 ISA op, each pair = 1 VLIW cycle; C++ magic doesn't simulate per-cycle timing
  - Decision Status: `Directly lowerable — structure guarantees correct ISA lowering`

- DEC-4: Helper macros
  - Claude Position: Existing helpers only
  - Codex Position: N/A — open question
  - Tradeoff Summary: New macros add readability but another abstraction layer
  - Decision Status: `New helper macros OK if all live state in registers/memory`

## Implementation Notes

### Code Style Requirements
- Implementation code and comments must NOT contain plan-specific terminology such as "AC-", "Milestone", "Step", "Phase", or similar workflow markers
- These terms are for plan documentation only, not for the resulting codebase
- Use descriptive, domain-appropriate naming in code instead (e.g., `m28_bs_outer:` not `milestone4_step2:`)

### Procedural Requirements (from draft)
- Go slowly. Test incremental changes. One magic at a time where possible.
- Address specific draft feedback first, then do general passes for similar issues.
- The current code works. Any verification failure is a regression introduced by the rewrite.
- Checkpoint frequently (git commits) so changes can be reverted.
- Keep memories of bugs encountered to avoid repeating them.
- Read docs.md and gwfa_instruction_generator.py for legal ISA operations.
- Pipelined SPM access is allowed (two loads back-to-back), but latency is still 2 cycles.

### Optimization Objectives (from draft)
- Use mvdq/mvd for bandwidth
- Stream loads should alternate between PEs to minimize bank conflicts
- Fewer instructions is better
- Hoist boundary checks out of loops
- Use compile-time constants
- Avoid redundant computation
- Use half-registers for more register count and to avoid bitshifts like >> 16

--- Original Design Draft Start ---

# High level
We have created a bunch of magic instructions to do gwfa and we are now ready to bring them one step
closer to ISA like. We will leave them as c++, but you should account for:
+ VLIW slots and RAWs (pair data instructions in blocks of twos that will execute together in the
  same cycle. Make sure no RAWs between these pairs)
+ efficient mvdq round robin pe load loops. streaming load loops from controller should be round 
  robin to hit different bank groups, and they should be mvdq instead of mv so they get good
  bandwidth
+ latency of s1/spm/s2/mm accounted for. We should never use a mm that we have loaded until after a
  waitLSQ. If between magics, put the waitLSQ in the ISA. If within a magic, then wait LSQ should be
  within the magic as a comment. S1 has latency one cylce. spm has latency 2 cycles (means if you
  load you can't have an immediate use. You must wait a cycle. S2 should have a waitlsq between like
  MM.
+ gotos instead of if/else/for/while. Except for macros like for i in range 4
+ each line is one instruction, meaning you can't do more than one genp operation in a line.
+ examples of well polished instructions are controller 7,8,9 and pe 8,13. Don't worry about compute
  instructions for pes. We'll do that later.
+ You can't invent variables. Use registers, and compile time constants when you can.
You're task is to rewrite the magic without changing correctness to make it ready for ISA lowering.
When done, you should be able to directly translate from the code you've written to gendp ISA. The
only remaining thing to be done is fixing up the pe compute instructions for better performance.
# General
+ delete deprecated controller magic: magic 2 and magic 10, magic 26
+ Leave the following magic instructions alone. We will not work on them: 1, 3, 4, 5, 6, 17
+ All other instructions should be lowered to the levels of 7,8,9 for the controller, or 8,13 for
  the pe. For pe, don't worry about the compute instructions just yet, but make sure that the other
  instructions are gotos, isa like, registers no variables, macro loops are fine. Everything should
  be paired VLIW
+ Add an LSQ wait between the controller magic 7 and magic 8 because they are dependent in ISA
  generator
+ Rename SORT_BIN_REG. As far as I can tell, it is a scratchpad region not a register
+ You should always use mvdq with loop peeling round robin in pes. Means mvdq to pe0 then pe1, 2, 3
  then mvdq to pe 0 again. Scalar moves one at a time are only used in very speciallized situations
  where the data is not contiguous (e.g. graph lookups). This is a general rule, and where you see
  such a incorrect loop, you should fix it.
+ On the controller we don't have min or max. You'll need to use simple branch conditions to achieve
  that behaviour.
+ We need to use registers not variables. You don't have access to variables. You're writing
  assembly
# Procedural
+ I have given very specific notes for some things which I have seen, but I have surely missed many
  problems. I expect you to look through all the magic instructions and see if you see the same
  problems in other magic instructions. See if there are similar errors that I have missed. I expect
  there to be many and you should find all of them.
+ Go very slowly. Test incremental changes so you can debug them easily. You should do one magic
  instruction at a time where possible (though some changes affect multiple magic instructions.
+ Do general passes over all instructions, but also make sure you address the specific feedback
  below. I would recommend addressing the specific feedback first.
+ The current code works. Anything that causes the verification to fail is a bug you have introduced
  and must be corrected before moving on. Checkpoint frequently so you can revert changes if
  necessary
+ There are many tasks in this work. Make a very large and detailed plan to address them. Make sure
  you understand the code. For the most part they are independent so you can tackle one magic
  instruction at a time and then clear context, but keep memories of bugs you've encountered so you
  can fix them, and refresh the general principles
+ Read the simulator, and docs and wfa_instruction generator to see what operations are supported by
  gendp
+ Note that we are allowing pipelined spm access, so you can do two spm loads back to back, but the
  latency is still 2 cycles.
# References
+ Take a look at other prompts in this directory as well as in the directory: /data4/kaplannp/GenDP2/gdp/gendp/Prompts
+ Docs and the source code for gendp is good too
+ if you look at instrcution generator especially for wfa you'll get a sense of what is legal.
# Optimization objectives
Keep these in mind:
+ use mvdq, mvd when possible to get good bandwidth
+ stream loads should alternate between pes to minimize bank conflicts
+ fewer instructions is better
+ loops are most important. Hoisting boundary checks out of loops is a great way to improve
  performance.
+ Be efficient
+ compile time constants are great. Use them if you can
+ Try to avoid redundant compuation
+ use the half registers if you can to get more register count and to remove some bitshifts like >>
  16
# Verification
Verify frequently so you can trace bugs directly to changes you made.
Use gwfa_check_correctness -t 56 with 56 threads. 1 is fast but will not catch all bugs. 2 is
slower, but must pass completely.
# Specific Magic Instructions Problems Noted
## Controller:
### magic 18
  + gwfa_get..off is just constants into MM. They should be constants at the start of magic
    instead of function calls.
### Magic 19
  + flip the loop going through radix bins with the pe loop. pes should always be on the inside of
    the loop for avoiding bank conflicts, and I think you can avoid putting this stuff in s1c in
    that case. If you can just load directly into registers it'll be even faster
### Magic 20
  + modify fin0_load_batch such that it does not return a value. Otherwise it looks fine.
  + line 613 of load batch sets gr[9] = spm[gr[8]]] >> 16; Multiple issues. Firstly, this is two isa
  ins, one load one shift. Second, you can't immediately operate on Spm results. There are two
  cycles of latency. You should try to reorder other instructions into the gap between the spm load 
  and the shift. This will allow you to mask the latency. Thirdly, here if just trying to get lower
  16 bits you should use the half registers. That's what they are for. You should take these lessons
  and apply them to all the lines.
  from SPM you 
  + fin0_load_batch should be restructured. Greedy search is expensive, and doesn't make use of the
  mvdq bandwidth. Instead, we should try like this:
  ```
  //mvdq loop. iterate over pes interior so we do mvdq to different pes at each step
  while inputs still exist:
	  1. calculate the storage needed for the next 4 diagonals
	  2. if current_pe doesn't have the storage necessary break
	  3. load 4 diagonals
	  4. begin loading the arcs for those diagonals using mvdq and peel the end (or start)
	  5. update current_pe += 1 modular
  //mv loop. flips loop nested order. iterate pes on outer loop.
  //This loop is like what you have, but not the greedy thing. Just fill pes one after the other
  for each pe:
	while pe has space:
		load next diagonal and its arcs
  ```
  The key insight here is that in the common case, we expect the inputs to fit. It is a rare case
  that the inputs do not fit in the pes. In that case we are willing to pay a penalty, but we should
  make the common case fast.

  This also makes the skiping easier. The bitmap bookeeping is no longer necessary. If we didn't fit
  everyone (which should be rare) then we know that the things we didn't fit are simply the last
  diagonals in the s1c.
### Magic 24
  + This should be modified to do mvdq. Peeling should not be necessary if we always do tilesize
  multiple of 4. Only peel for the final iterations. Should be hiting pes in round robin to avoid 
  bank conflicts. Many examples of this pattern. Take a look at magic 14 or 15. You are loading a
  constant tilesize at each step, except for the last one. Try to move the checks so most of the
  time we don't need to check. Only for the last iteration do we need to resort to loop peeling.
### magic 25
  + Same deal here, we should be using mvdq in round robin manner with loop peeling. Not scalar
  doing all hits to pe0 bank then all hits to pe1. That will be too slow and won't utilize the
  bandwidth
### magic 28
  + remove the sanity check. Was used for debugging.
  + remove the verify splits
  + instead of:
  	for each pe:
		do binary search
     we should do
     while all pes not done with search:
        for each pe:
	  do one step of binary search
     It is essential that we do it this way because between each iteration of the binary search we
     need a wait LSQ because we are doing a load from mm.
     You should add the wait LSQ in a comment within the binary search after each round of 4 pe
     lookups (basically you issue all the pe loads for that iteration. then wait lsq, then process
     the loaded values and determine the next pe to go to)
  + This loop needs to stream data in with mvdq round robin. No peeling necessary because the merge
    buffer tile size should be sized to always fit mvdq. peeling ONLY needed in edge case at the
    end. The tight loop of data transfer should not have these checks. The checks should be done
    ahead of time before the loop, then peel, then tight mvdq without checks. See previous examples.
### magic 29
  + should be mvdq round robin pe no peeling necessary except on final iteration same as magic 28
### magic 30
  + same note for scalar loops. Needs mvdq round robin... like magic 29
### magic 31
  + same note for scalar loops. Needs mvdq round robin... like magic 29
  + You should compute cursors for each pe and use mv instruction autoincrement when you writeback.
    In this way you don't need to recompute the MM destination every time.
### magic 32
  + Right now you do a seam merge for intv at the end over MM which would require a long latency
    wait. Instead, the very first tile that you get back you should write the first data element to
    s1c. After that write directly to MM. Also write the very last intv of each pe to s1c. This way,
    at the end you can compare the final intvs without doing any MM lookups.
  + all loops need to be mvdq round robin. Both diags and intvs
### magic 33
  + loop is not correct again. needs mvdq round robin
  + we have nested lookups mm[s1c[XX]]. Not feasible. You must do slc lookup as a seperate
    instruction
### magic 35
  + looping not correct. mvdq round robin needed. Always multiple of two, even across all pes until
    the boundary finish condition
### magic 36
  + remove the check that output was sorted
  + I'd like to remove the linear scan through diags here. We should make it so that you can start
    in the middle of a diagonal run. Then at the end we do a fixup, almost exactly the same as for
    intv. We store the start and end of diag tiles in s1c. Then we do a max to merge the boundary
    diags before we write them.
    tile at diags // 4 * pe
### magic 38
  + Firstly, we should do the lo and hi binary searches in parallel, so fuse the while loops and
  have two binary searches running so we do two lookups at a time
  + Second, you must add in waitLSQ comment after each binary search result.

## PE
Magic ids 8 and 13 are ideal examples. Read from them and try to replicated
## magic 19
  + There is ample opportunity to use half registers here as well as mvd. Try to use them when you
    can
## magic 20
  + modify sort bin count so we are loading two elements at a time from the tile and then we work on
    those two. We want mvd to get higher bandwidth
## magic 21
  + This should also do two element load, mvd.
## magic 22
  + You shouldn't need to check the second buffer. It will always be full. You only need to check if
    the entire stream is exausted.
  + basically, in this magic you want the inner loop to be cleaner. You should first establish how
    much left you have of A tile and B tile. Then you should iterate really fast on these tiles.
    Handle the switch of buffers as a special case. You only need to do that if you exaust current
    tile, and should try to avoid doing unecessary checks otherwise. Try to streamline the main loop
    if possible. Hoist checks
## magic 23
  + No functions unless they don't have return values and are only one call deep. Even then, it may
    make more sense
## magic 23
  + 20 words to restore/save for state seems like way too much. You should be able to keep almost
    all of these in regsiters. You have 48 registers including gr and reg. 64 if you fit some things
    in half registers. You should be able to maintain state between calls. That way you don't need 
    to do the expensive write/load at start/end.
  + In some places, like merging overlapping diagonals or intvs, you might be able to use mvds.
  + make sure you wait a cycle after spm load for data to be ready
  + generally you should always keep one intv and one diag in registers so you can do the forbidden
    checks. Keep the current one you're working on.


--- Original Design Draft End ---
