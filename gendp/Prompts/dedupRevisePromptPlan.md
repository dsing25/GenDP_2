# GWFA Sort/Merge/Dedup Pipeline Revision Plan

## Goal Description

Revise the GWFA kernel's sort/merge/dedup pipeline in the GenDP simulator to be more
ISA-accurate. Six changes are required: reorder setPC after spin in dedup and scatter
loops, change merge from output-capped to input-capped processing, replace MM data copies
with pointer swaps, and flip the sort order from INTV-first to DIAG-first with pre-computed
split metadata for dedup. All changes must maintain correctness across 295 test cases.

## Acceptance Criteria

- AC-1: Dedup loop steady-state instruction order is spin → setPC → writeback (not
  spin → writeback → setPC)
  - Positive Tests:
    - In gwfa_instruction_generator.py, dedup SS_PONG/SS_PING have setPC immediately
      after spin, before magic 31 writeback
    - All 295 test cases pass: `python scripts/gwfa_check_correctness.py -t 56 2`
  - Negative Tests:
    - Reverting to old order (writeback before setPC) should still pass correctness
      (functional equivalence) but would represent an ISA-inaccurate stall pattern
- AC-2: Scatter loop steady-state instruction order is spin → setPC → writeback (not
  spin → writeback → setPC)
  - Positive Tests:
    - In emit_sort_loop scatter phase, SS_PONG/SS_PING have setPC immediately after spin,
      before magic 25 writeback
    - All 295 test cases pass
  - Negative Tests:
    - Reverting to old order should still pass (functional equivalence) but is ISA-inaccurate
- AC-3: Merge PE kernel uses input-capped processing with budget MERGE_STEP = MERGE_TILE/2
  = 40 inputs consumed per call, producing variable-size output
  - AC-3.1: PE merge kernel loop terminates on consumed inputs (ai + bi - initial) >=
    MERGE_STEP, not on output count >= MERGE_TILE
    - Positive: PE always consumes at most 40 inputs from A+B combined per call
    - Negative: PE never waits for output buffer to fill to MERGE_TILE
  - AC-3.2: "Both buffers empty" early-stop logic removed from PE merge kernel
    - Positive: The `if (!aa && !ba) break` path is removed
    - Negative: No test case triggers a premature exit from merge (was already dead code)
  - AC-3.3: Controller merge writeback (magic 35) handles variable-size output per PE
    without the all_full synchronization gate
    - Positive: gr[2] advances unconditionally each iteration
    - Negative: No PE waits for another PE to fill its output buffer
  - AC-3.4: Merge loop bound (gr[6]) computed from max input count per PE, not output count
    - Positive: Loop bound = ceil(max(a_count + b_count per PE) / MERGE_STEP)
  - All 295 test cases pass
- AC-4: MM data copies in merge finalize magics replaced with pointer/offset swaps
  - AC-4.1: magic 37 (intv merge setup) no longer copies MM_INTV → MM_SWAP
  - AC-4.2: magic 39 (intv finalize) no longer copies MM_SWAP → MM_INTV
  - AC-4.3: magic 36 (diag finalize) no longer copies MM_SORT_BUF → diag_base
  - AC-4.4: Active buffer bases stored in s1c slots; all consumers read from s1c
  - Positive: No for-loop copying entire MM regions in magic 36, 37, or 39
  - Negative: Any code still using hardcoded MM_INTV/MM_SORT_BUF constants without
    indirection through s1c is a bug
  - All 295 test cases pass
- AC-5: Sort order flipped to DIAG sort → DIAG merge → INTV sort → INTV merge → DEDUP
  - Positive: In gwfa_instruction_generator.py, diag sort+merge emitted before intv
    sort+merge
  - Negative: Emitting intv sort before diag sort is incorrect
  - All 295 test cases pass
- AC-6: Diag split metadata (indices and vd values) recorded after diag merge and stored
  in s1c for use by subsequent intv merge and dedup
  - AC-6.1: After diag merge finalize, 5 split indices and 4 boundary vd values computed
    using vd-boundary logic (same as current magic 29) and stored in s1c
    - Positive: Split indices are monotonically increasing and boundary-aligned on vd
      transitions
    - Negative: Split indices that fall mid-vd-group are incorrect
- AC-7: PE merge kernel tracks intv split positions during intv merge (both hi-based and
  lo-based boundaries)
  - AC-7.1: Each PE records, for each of 3 internal diag boundaries, the local output
    position of the first intv whose hi > boundary_vd (hi-based)
    - Positive: Per-PE hi-based positions are set correctly; elementwise min across PEs
      gives global intv_lo boundaries
  - AC-7.2: Each PE records, for each of 3 internal diag boundaries, the local output
    position of the first intv whose lo >= boundary_vd (lo-based)
    - Positive: Per-PE lo-based positions are set correctly; elementwise min gives global
      intv_hi boundaries
  - AC-7.3: Controller collects per-PE boundary data and computes global intv_lo and
    intv_hi arrays via elementwise min
  - All 295 test cases pass
- AC-8: Dedup setup (magic 29) uses pre-computed diag splits and intv boundaries from
  s1c/metadata instead of recomputing them
  - Positive: magic 29 reads stored split data; no vd-boundary scan or binary search
    for diag/intv splits
  - Negative: If stored splits are stale or wrong, dedup produces incorrect output
    (detected by 295-case sweep)
  - All 295 test cases pass

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)
All 6 changes implemented, all 295 test cases passing, pointer swaps eliminate all
identified MM copies, PE merge kernel tracks both boundary types during intv merge, and
dedup fully consumes pre-computed split metadata.

### Lower Bound (Minimum Acceptable Scope)
All 6 changes implemented at the simulator/magic-instruction level. Each change verified
independently with 295-case sweep. Pointer swapping covers the three identified copy sites
(magic 36, 37, 39). Intv boundary tracking covers both lo-based and hi-based families.

### Allowed Choices
- Can use: s1c array for storing active buffer bases and split metadata; existing MERGE_META
  SPM region for per-PE boundary tracking data; new s1c slot ranges beyond current usage
- Can use: MERGE_STEP constant defined alongside MERGE_TILE
- Cannot use: gr registers for active buffer bases (gr pressure too high per Codex analysis)
- Cannot use: non-overlapping dedup partitioning (user chose to keep current overlap)
- Fixed: Input budget is MERGE_TILE/2 = 40 per PE merge call
- Fixed: PE tracking (Option A) for intv split computation, not post-merge binary search

## Feasibility Hints and Suggestions

> **Note**: This section is for reference and understanding only.

### Conceptual Approach

**Milestone 1 (setPC reorder):** In gwfa_instruction_generator.py, swap the setPC and
writeback instructions in dedup SS_PONG/SS_PING (lines 376-377, 384-385) and in scatter
SS_PONG/SS_PING (lines 172-173, 177-178). Both are pure instruction reordering.

**Milestone 2 (merge contract):** Three coordinated changes:
1. pe.cpp magic 22: change loop from `while (oi < MERGE_TILE)` to
   `while (consumed < MERGE_STEP)` where consumed = (ai - ai0) + (bi - bi0). Remove the
   `(!aa && !ba)` and `(!aa && !ad)` / `(!ba && !bd)` break conditions.
2. pe_array.cpp magic 35: remove the all_full gate. Writeback whatever each PE produced
   (read MERGE_META+4). Advance gr[2] unconditionally.
3. pe_array.cpp merge_split_and_load: compute loop bound from max(a_count+b_count per PE)
   / MERGE_STEP instead of total_merged / MERGE_TILE.

**Milestone 3 (pointer swap):** Introduce s1c slots for active_intv_base and
active_diag_base. Magic 37: instead of copying MM_INTV → MM_SWAP, set B source = MM_INTV
directly. After merge, active_intv_base = merge output location. Magic 39: swap
active_intv_base instead of copying. Magic 36: swap active_diag_base instead of copying.
Update all downstream consumers (magic 28, 29, 32) to read from s1c.

**Milestone 4 (sort flip + splits):**
Phase A: Reorder instruction generator to emit diag sort+merge before intv sort+merge.
Split magic 39 into diag-finalize and intv-setup magics. Verify 295 cases.
Phase B: After diag merge finalize, compute diag split indices/vd values (vd-boundary
logic from current magic 29 lines 2769-2781) and store in s1c.
Phase C: Augment PE merge kernel (magic 22) to track, for each of 3 internal boundaries,
the first output position where intv.hi > boundary_vd and intv.lo >= boundary_vd.
Store in SPM MERGE_META extension. After intv merge, controller collects and computes
global boundaries via elementwise min.
Phase D: Modify magic 29 to use stored splits instead of recomputing. Verify 295 cases.

### Relevant References
- `scripts/gwfa_instruction_generator.py` - instruction generation (all changes)
- `pe_array.cpp:2511-2620` - magic 37, 39 (intv merge setup/finalize)
- `pe_array.cpp:2694-2721` - magic 35 (merge writeback, all_full gate)
- `pe_array.cpp:2744-2891` - magic 29 (dedup split, current split computation)
- `pe_array.cpp:2988` - magic 32 (dedup finalize)
- `pe_array.cpp:348-428` - merge_split_and_load (loop bound computation)
- `pe.cpp:1396-1471` - magic 22 (PE merge kernel)
- `pe.cpp:1472-1685` - magic 23 (PE dedup kernel)
- `scripts/gwfa_check_correctness.py` - verification script

## Dependencies and Sequence

### Milestones
1. **SetPC Optimization** (Draft Changes 2, 3): Reorder setPC after spin in dedup and
   scatter loops
2. **Merge Contract Change** (Draft Changes 4, 5 combined): Input-capped merge with
   variable output and no all_full gate
   - Depends on: Milestone 1 (clean baseline after setPC changes)
3. **Pointer Swapping** (Draft Change 6): Replace MM copies with s1c-based offset swaps
   - Depends on: Milestone 2 (merge contract finalized before changing buffer ownership)
4. **Sort Order Flip + Split Tracking** (Draft Change 1): Flip to DIAG-first, pre-compute
   splits, PE-tracked intv boundaries
   - Phase A: Reorder sort/merge → Depends on Milestone 3
   - Phase B: Record diag splits → Depends on Phase A
   - Phase C: PE intv boundary tracking → Depends on Phase B
   - Phase D: Dedup consumes stored splits → Depends on Phase C

Each milestone verified independently with `python scripts/gwfa_check_correctness.py -t 56 2`
(295 inputs). Must pass before proceeding to next milestone.

## Task Breakdown

| Task ID | Description | Target AC | Tag | Depends On |
|---------|-------------|-----------|-----|------------|
| T1 | Reorder dedup loop: swap setPC and writeback in SS_PONG/SS_PING | AC-1 | `coding` | - |
| T2 | Reorder scatter loop: swap setPC and writeback in SS_PONG/SS_PING | AC-2 | `coding` | T1 |
| T3 | Verify T1+T2 with 295 cases | AC-1,AC-2 | `coding` | T2 |
| T4 | Review setPC changes for ISA correctness | AC-1,AC-2 | `analyze` | T3 |
| T5 | Change PE merge kernel to input-capped (MERGE_STEP=40) and remove early-stop | AC-3.1,AC-3.2 | `coding` | T4 |
| T6 | Remove all_full gate in magic 35, advance gr[2] unconditionally | AC-3.3 | `coding` | T5 |
| T7 | Update merge loop bound computation for input-based stepping | AC-3.4 | `coding` | T6 |
| T8 | Verify merge contract changes with 295 cases | AC-3 | `coding` | T7 |
| T9 | Review merge contract for correctness and edge cases | AC-3 | `analyze` | T8 |
| T10 | Introduce s1c slots for active_intv_base and active_diag_base | AC-4.4 | `coding` | T9 |
| T11 | Replace MM copy in magic 37 with pointer indirection | AC-4.1 | `coding` | T10 |
| T12 | Replace MM copy in magic 39 with pointer swap | AC-4.2 | `coding` | T11 |
| T13 | Replace MM copy in magic 36 with pointer swap | AC-4.3 | `coding` | T12 |
| T14 | Update downstream consumers (magic 28, 29, 32) to use s1c bases | AC-4.4 | `coding` | T13 |
| T15 | Verify pointer swapping with 295 cases | AC-4 | `coding` | T14 |
| T16 | Review pointer swap for ownership correctness | AC-4 | `analyze` | T15 |
| T17 | Reorder instruction generator: diag sort+merge before intv sort+merge | AC-5 | `coding` | T16 |
| T18 | Split/repurpose magic 39 for new order (diag finalize + intv setup) | AC-5 | `coding` | T17 |
| T19 | Verify sort order flip with 295 cases | AC-5 | `coding` | T18 |
| T20 | Compute and store diag split indices + vd values in s1c after diag merge | AC-6 | `coding` | T19 |
| T21 | Augment PE merge kernel to track hi-based intv boundary positions | AC-7.1 | `coding` | T20 |
| T22 | Augment PE merge kernel to track lo-based intv boundary positions | AC-7.2 | `coding` | T21 |
| T23 | Add controller logic to collect per-PE boundaries and compute global splits | AC-7.3 | `coding` | T22 |
| T24 | Modify magic 29 to use pre-computed splits instead of recomputing | AC-8 | `coding` | T23 |
| T25 | Verify sort flip + split tracking with 295 cases | AC-5-8 | `coding` | T24 |
| T26 | Final review of sort flip + split tracking | AC-5-8 | `analyze` | T25 |

## Claude-Codex Deliberation

### Agreements
- Dedup and scatter instruction reordering (spin → setPC → writeback) is correct and low risk
- Merge PE already writes output count metadata (MERGE_META+4), reusable for variable output
- Splitting/repurposing magic 39 is necessary for sort order flip
- s1c is the right storage for active buffer bases (not gr registers)
- Current overlap semantics (two boundary families) must be preserved in dedup
- diagSplits must include both indices (for tile loading) and vd values (for boundary checks)

### Resolved Disagreements
- **Milestones 2+3 coupling:** Codex wanted Changes 4 and 5 merged into one step. Claude
  initially had them separate. Resolution: merged into one milestone (Milestone 2) since
  the PE loop condition and controller writeback must change together.
- **intvSplits computation method:** Codex preferred Option B (post-merge binary search) for
  simplicity. User chose Option A (PE tracking during merge). Resolution: Option A with both
  hi-based and lo-based boundary tracking augmented.
- **diagSplits storage:** Codex noted vd values alone are insufficient; indices needed too.
  Resolution: store both in s1c (5 indices + 4 vd values = 9 slots).
- **Risk assessment of Change 4:** Codex noted removing early-stop depends on invariants not
  explicitly enforced. Resolution: remove alongside input-capping (Milestone 2) so the
  invariant is enforced by the new budget.

### Convergence Status
- Final Status: `converged`

## Pending User Decisions

- DEC-1: intvSplits computation method
  - Claude Position: Option B (post-merge binary search) for simplicity
  - Codex Position: Option B acceptable only if it reproduces full overlap semantics
  - Tradeoff Summary: Option A is more complex but captures data as produced; Option B is
    simpler but adds a post-merge scan
  - Decision Status: `User chose Option A (PE tracking)`
- DEC-2: Dedup interval partitioning overlap semantics
  - Claude Position: Keep current overlap (safest)
  - Codex Position: Keep current overlap (agrees)
  - Decision Status: `User chose: keep current overlap`
- DEC-3: Merge input budget per PE call
  - Claude Position: MERGE_TILE/2 = 40 inputs
  - Codex Position: Define explicit MERGE_STEP constant
  - Decision Status: `User chose MERGE_TILE/2 = 40; MERGE_STEP constant to be defined`
- DEC-4: Implementation order
  - Claude Position: Risk-ascending (2,3 → 4+5 → 6 → 1)
  - Codex Position: Did not express preference
  - Decision Status: `User chose risk-ascending order`

## Implementation Notes

### Code Style Requirements
- Implementation code and comments must NOT contain plan-specific terminology such as
  "AC-", "Milestone", "Step", "Phase", or similar workflow markers
- These terms are for plan documentation only, not for the resulting codebase
- Use descriptive, domain-appropriate naming in code instead

### Verification Protocol
- Each milestone verified with: `python scripts/gwfa_check_correctness.py -t 56 2`
  (295 inputs, parallelized with 56 threads)
- Quick check (not sufficient for proceeding): use `1` instead of `2` at the end
- After each milestone passes, submit for Codex review via `analyze` tagged tasks

### Key Constants
- SORT_TILE = MERGE_TILE = DEDUP_TILE = 80
- MERGE_STEP = MERGE_TILE / 2 = 40 (new constant for input-capped merge)
- DIAG_CAP_V = 16 << 20, INTV_CAP_V = 1 << 21
- MM_INTV = DIAG_CAP_V * 6, MM_SORT_BUF = DIAG_CAP_V * 6 + INTV_CAP_V * 6

### s1c Slot Allocation for New Metadata
Existing usage: s1c[0..31] (dedup per-PE tracking), s1c[144..151] (cross-phase state).
New slots needed:
- active_intv_base: 1 slot (e.g., s1c[152])
- active_diag_base: 1 slot (e.g., s1c[153])
- diag split indices: 5 slots (e.g., s1c[154..158])
- diag split vd values: 4 slots (e.g., s1c[159..162])
- intv_lo boundaries: 4 slots (e.g., s1c[163..166])
- intv_hi boundaries: 4 slots (e.g., s1c[167..170])

### Deviations from Draft Pseudocode
1. Draft lists Changes 1-6; implementation order is 2,3 → 4+5 → 6 → 1 (risk-ascending)
2. Draft says "diagSplits[4] and intvSplits[4]"; actual implementation uses 5 split indices
   + 4 vd values for diags, and separate intv_lo[4] + intv_hi[4] for intervals (to preserve
   current two-boundary overlap semantics)
3. Draft says "elementwise min" for intvSplits; this is augmented to cover both hi-based
   and lo-based boundary families, each with its own elementwise-min reduction across PEs
4. Draft's Change 4 (remove early-stop) and Change 5 (variable output) are combined into
   one milestone since they must be changed together

--- Original Design Draft Start ---

# High Level
We are working on modifications to the gwfa kernel in order to make it closer to the code we will
eventually write in the gendp ISA.
Recently I implemented some magic instructions which handle the pe/pe_array synchronization, 
parallelization, and overlap. Essentially, the pe_array will be loading data and writing data into
and from the PEs, which do the compute.

This is mostly finished, but there are some things in the current code which are not accurate or
need revision. You will be working on correcting these confusions.

# Process:
You should implement only one step at a time, then verify completely for 295 inputs and query codex.
Once codex has no more inputs, then you may continue to the next step

# Verification:
To verify you run python scripts/gwfa_check_correctness.py -t 56 2. This runs 295 inputs in
parallel. If you are just doing a quick check, you can use 1 at the end instead of 2. This is not
evidence that the code is correct though. To proceed to the next step you must use 2.

# Things to fix
1. Currently we sort intv and then diags. I want to flip the order of this. Should be trivial.  
  1. Before you sort intv you should take note of the diag values at the diag splits that you will
     need for the dedup. You can put these in special locations in SPM metadata.
  2. During the merge step of the the intv, you should check each intv against the diag splits. And
     write to results. So diagSplits[4] and intvSplits[4]
     Psuedocode:
     prelude check if the first intv is greater than any of the diags. Advance currentDiag_i.
     Steady state
     cursor++
     intv = tile[cursor]
     if intv.hi > diagSplits[currentDiag_i]:
       you've found the border. set intvSplits[currentDiag_i] = current location in intv
       currentDiag_i++
     Finally, at the end of the merge you will have 4 intvSplits. You should take an elementwise
     min, which boils down to take pe0, if no pe0 take pe1, if no pe1 take pe2...
  3. In the planning phase we can discuss this because it's a bit complex. I also seem to remember
     trying to do it, but there may have been an issue, so think through carefully
2. In dedup we should set PC to PONG while we writeback the previous OUT buffer. Basically, if you
   ever have a spin, the very next instruction should be a setPC, otherwise the pe is guarenteed to
   be stalled.
3. The same happens in the scatter phase. You should spin and immediately after setPC to avoid
   stalls.
4. The pseudocode says something about stopping early if both buffers are empty in the two pointer
   merge. This should never happen. Tilesize shouldb e twice the size of the output tile. In this
   case you will process no more than Tilesize/2, so you can never exaust a tile and need to move to
   a tile that is not loaded yet.
5. Currently we force the two pointer merge to wait until the entire output buffer is full. This is
   not reasonable. It forces divergence between pes. Instead we should have each pe process
   tilesize/2 inputs each step, this means their output buffers will have variable size. The
   controller will need to deal with this, doing writeback for a variable number of results from
   each pe. The number of outputs will need to be written to metadata somewhere.
6. There are multiple places where we have copies of data in main memory which we then move to other
   locations, e.g. MM_sort_buff, but in an ideal world we would be able to simply swap pointers so
   intv now points to sort buff and tmp points to the old intv. Theoretically, you should not need
   to zero out the old array either, but you can for debugging.

# Psuedocode
This is a summary of the current algorithm for you to reference. You should read the source code as
well of course. If there are any deviations between this pseudocode and the actual code, you should
note them in the planning phase.

================================================================================
GWFA SORT → MERGE → DEDUP PIPELINE
================================================================================
Called after extend phases produce new diags and new intervals.
Inputs:
  - new diags at diag_base (unsorted tail appended after sorted prefix)
  - new intervals at MM_NEXT_INTV (unsorted)
  - old intervals at MM_INTV (sorted from previous step)
  - n_a = total diag count, n_phase1 = sorted prefix count
  - intv_n = old interval count, new_intv_n = new interval count

================================================================================
STEP 1: SORT INTERVALS
================================================================================

magic 16 (controller): setup intv sort
  gr[3] = new intv source MM addr
  gr[4] = new intv dest MM addr
  gr[5] = 0 (initial shift)
  gr[6] = ceil(new_intv_n / 4)  (tiles per PE)
gr[1] = 0  (pass counter)

emit_sort_loop: 8-pass radix sort (4 bits per pass, 32-bit key)
  for pass = 0..7:

    ---- BIN COUNT PHASE ----
    gr[2] = 0
    Controller                      PE[0..3]
    ─────────────────────────────── ─────────────────────────────
    magic 34 → load tile → PING
    set_PC(BIN_COUNT_PING) ───────→ count 4-bit radix bins for tile
    bge gr[2]≥gr[6]? → epilogue

    SS_PONG:
      magic 34 → load tile → PONG   (overlapped with PE)
      spin                           ...PE counting PING...
      set_PC(BIN_COUNT_PONG) ──────→ count bins for PONG tile
      bge? → epilogue

    SS_PING:
      magic 34 → load tile → PING   (overlapped)
      spin                           ...PE counting PONG...
      set_PC(BIN_COUNT_PING) ──────→ count bins for PING tile
      bge? → epilogue
      jump → SS_PONG

    epilogue: spin

    PE magic 11: for each entry in tile, extract 4-bit radix field
      (shifted by gr[5]), increment bin_count[bin]. Accumulate
      into SORT_META. Also handles PE3 boundary sort entry (FIFO).

    magic 34: loads SORT_TILE entries from MM[gr[3] + cursor]
      into SPM TILE_BUF ping/pong. Advances gr[2] by SORT_TILE.

    ---- PREFIX SUM (magic 19) ----
    Controller reads bin_counts[0..15] from all 4 PEs.
    Computes global prefix sum across PEs → scatter offsets.
    Writes prefix sums back to each PE's SORT_META.

    ---- SCATTER PHASE ----
    gr[2] = 0
    Controller                      PE[0..3]
    ─────────────────────────────── ─────────────────────────────
    magic 24 → load tile → PING
    set_PC(SCATTER_PING) ─────────→ scatter entries to bin positions
    bge gr[2]≥gr[6]? → epilogue

    SS_PONG:
      magic 24 → load tile → PONG   (overlapped)
      spin                           ...PE scattering PING...
      magic 25 → writeback PING      (scatter bins → MM)
      set_PC(SCATTER_PONG) ────────→ scatter PONG tile
      bge? → epilogue

    SS_PING:
      magic 24 → load tile → PING   (overlapped)
      spin                           ...PE scattering PONG...
      magic 25 → writeback PONG
      set_PC(SCATTER_PING) ────────→ scatter PING tile
      bge? → epilogue
      jump → SS_PONG

    epilogue: spin, writeback last

    PE magic 20/21: for each entry, extract radix field, look up
      scatter offset from prefix sum, write (vd,k) to BIN_REG[bin].
    magic 24: load tile from MM into SPM. Advances gr[2].
    magic 25: copy filled bins from SPM BIN_REG → MM[gr[4]].

    ---- PASS FOOTER ----
    swap gr[3] ↔ gr[4]              source/dest ping-pong
    gr[1]++
    bne gr[1]!=8 → top of sort loop

  Result: new intervals sorted in MM at gr[3].

================================================================================
STEP 2: MERGE INTERVALS (PE-parallel)
================================================================================

magic 37 (controller): intv merge split + load
  A = sorted new intv (from sort output)
  B = sorted old intv (from MM_INTV)
  if one is empty: copy the other to MM_SWAP, set skip flag, gr[6]=0
  else:
    merge path binary search → 4 PE split points
    load first A and B tiles into MERGE_A_BUF0/1, MERGE_B_BUF0/1
    set gr[6] = loop bound, gr[4] = MM_INTV (output)

emit_merge_loop:
  if gr[6]==0: skip (nothing to merge)
  gr[2] = 0

  Controller                      PE[0..3]
  ─────────────────────────────── ─────────────────────────────
  set_PC(MERGE_PING) ────────────→ two-pointer merge A+B → OUT0
  bge gr[2]≥gr[6]? → epilogue

  SS_PONG:
    spin                            ...PE merging → OUT0...
    set_PC(MERGE_PONG) ───────────→ merge → OUT1
    magic 35 → writeback OUT0       (overlapped)
    magic 33 → reload A/B tiles     (overlapped)
    bge? → epilogue

  SS_PING:
    spin                            ...PE merging → OUT1...
    set_PC(MERGE_PING) ───────────→ merge → OUT0
    magic 35 → writeback OUT1       (overlapped)
    magic 33 → reload A/B tiles     (overlapped)
    bge? → epilogue
    jump → SS_PONG

  epilogue: spin, writeback last

  PE magic 22: two-pointer merge from A_BUF and B_BUF.
    Uses ping-pong: when current A buffer exhausted, switch to
    other A buffer (zeros tile_count for controller reload).
    Same for B. Produces up to MERGE_TILE sorted output per call.
  magic 35 (writeback): copy OUT → MM_SORT_BUF. gr[2] += TILE.
  magic 33 (reload): scan META for zeroed tile counts, refill
    from MM. Set a_done/b_done when stream fully loaded.

magic 39 (controller): intv finalize + diag sort setup
  compute intv_n from PE output cursors
  if merge skipped: copy MM_SWAP → MM_INTV
  setup s1c[147..150] = (n_phase1, n_a, intv_n, diag_base)

  Result: merged intervals in MM_INTV.

================================================================================
STEP 3: SORT DIAG TAIL
================================================================================

gr[1] = 0
emit_sort_loop: same 8-pass radix sort on the unsorted diag tail
  (diags from n_phase1..n_a, the new diags from this step)
  Phase 1 prefix (0..n_phase1) is already sorted from prior steps.

  Result: diag tail sorted in MM.

================================================================================
STEP 4: MERGE DIAGS (PE-parallel)
================================================================================

magic 28 (controller): diag merge split + load
  A = sorted prefix (diags 0..n_phase1)
  B = sorted tail (diags n_phase1..n_a)
  if one is empty: gr[6]=0 (skip)
  else:
    merge path binary search → 4 PE split points
    load first A/B tiles into MERGE_A_BUF0/1, MERGE_B_BUF0/1
    set gr[6] = loop bound, gr[4] = MM_SORT_BUF

emit_merge_loop: same as intv merge

magic 36 (controller): diag merge finalize
  if gr[6]!=0: copy MM_SORT_BUF → diag_base

  Result: all diags fully sorted at diag_base.

================================================================================
STEP 5: DEDUP (tiled, PE-parallel)
================================================================================

magic 29 (controller): dedup split + initial tile load
  merge-adjacent MM_INTV in-place (fix touching intervals)
  split diags at vd-group boundaries → splits[0..4]
  split intv via binary search: PE p gets intv with hi > boundary
  for each PE:
    load 2 tiles diags → DIAG_BUF0, DIAG_BUF1
    load 2 tiles intv → INTV_BUF0, INTV_BUF1
    init META (20 words)
    set s1c: mm_src, remaining, output bases, cursors
  gr[6] = ceil(max(diag_n + intv_n per PE) / TILE) * TILE
  gr[2] = 0
  gr[4] = MM_SORT_BUF, gr[7] = MM_DEDUP_INTV_OUT

ISA dedup loop:
  Controller                      PE[0..3]
  ─────────────────────────────── ─────────────────────────────
  magic 30 → reload               (initial: fills BUF1)
  set_PC(DEDUP_PING) ────────────→ dedup call 1 → DIAG_OUT0, INTV_OUT0
  bge gr[2]≥gr[6]? → EXIT_PING

  SS_PONG:
    magic 30 → reload (slot0)      (re-exec safe during spin)
    spin (slot1)                    ...PE working...
    magic 31 → writeback OUT0       DIAG_OUT0 → MM_SORT_BUF
                                    INTV_OUT0 → MM_DEDUP_INTV_OUT
                                    gr[2] += TILE
    set_PC(DEDUP_PONG) ───────────→ dedup call 2 → OUT1
    bge? → EXIT_PONG

  SS_PING:
    magic 30 → reload (slot0)
    spin (slot1)                    ...PE working...
    magic 31 → writeback OUT1
    set_PC(DEDUP_PING) ───────────→ dedup call 3 → OUT0
    bge? → EXIT_PING
    jump → SS_PONG

  DEDUP_EXIT_PONG: spin, writeback OUT1, jump → DONE
  DEDUP_EXIT_PING: spin, writeback OUT0, fallthrough → DONE

  PE magic 23 — processes TILE_SIZE elements per call
  (counted across BOTH diag and intv reads):

    STATE X: merge same-vd diag groups
      read diag → accumulate max k for same vd
      on new vd → completed group, go to B

    STATE B: advance intervals past completed diag
      loop:
        if no cur_intv: read intv → start cur_intv
        merge overlapping via peek (extend cur_intv)
        if cur_intv passes diag (chi > pv): break
        flush cur_intv → INTV_OUT (behind diag stream)
      forbidden check: cur_intv covers pv?
        if not forbidden: write (pv, pk) → DIAG_OUT
      transition: pv = triggering diag, continue X
      if all diags done: → C

    STATE C: drain remaining intervals
      read intv, merge overlapping, flush disjoint → INTV_OUT
      when all consumed: done

    Buffer switching: when current DIAG/INTV buffer exhausted,
      zero its tile_count in SPM, switch to other buffer.
      Controller reload (magic 30) sees the zero and refills.

  magic 30 (reload): for each PE, for each buffer {0,1}:
    if tile_count==0 and MM data remains: load TILE entries

  magic 31 (writeback): for each PE:
    copy DIAG_OUTx → MM_SORT_BUF[pe_base + cursor]
    copy INTV_OUTx → MM_DEDUP_INTV_OUT[pe_base + cursor]
    advance cursors, gr[2] += TILE

magic 32 (controller): gather + finalize
  gather diag outputs: compact 4 PE chunks → diag_base
  gather intv outputs: compact 4 PE chunks → MM_INTV
    with merge-adjacent at PE boundaries
  clear SPM, clear s1c
  gwfa_finalize_sync(n_a_final, intv_n)

  Result: deduped diags at diag_base, merged intv at MM_INTV.

================================================================================
DATA FLOW SUMMARY
================================================================================

  new_intv ──→ RADIX SORT ──→ MERGE(new + old) ──→ merged intv
                                                        │
  new_diags ─→ RADIX SORT ──→ MERGE(prefix + tail) ──→ sorted diags
                                                        │
                                                   DEDUP(diags, intv)
                                                        │
                                              ┌─────────┴──────────┐
                                         deduped diags        merged intv
                                         → diag_base          → MM_INTV
                                         (for next step)      (for next step)

================================================================================
SPM LAYOUT (per PE)
================================================================================

Sort/merge phase (reused for dedup afterward):
  SORT_TILE_BUF0  [0..159]       ping input tile (80 entries)
  SORT_TILE_BUF1  [160..319]     pong input tile
  SORT_BIN_REG0   [320..2879]    ping scatter bins (16×80×2)
  SORT_BIN_REG1   [2880..5439]   pong scatter bins
  SORT_META       [5440..5473]   bin counts, tile state

Merge phase (aliases sort region):
  MERGE_META      [0..15]        cursors, done flags, tile counts
  MERGE_OUT0      [16..175]      ping output
  MERGE_OUT1      [176..335]     pong output
  MERGE_A_BUF0    [336..495]     A stream ping
  MERGE_A_BUF1    [496..655]     A stream pong
  MERGE_B_BUF0    [656..815]     B stream ping
  MERGE_B_BUF1    [816..975]     B stream pong

Dedup phase (aliases sort/merge region):
  DEDUP_META      [0..19]        20 words: state, cursors, tile counts
  DEDUP_DIAG_BUF0 [20..179]      diag input 0 (80 entries)
  DEDUP_DIAG_BUF1 [180..339]     diag input 1
  DEDUP_INTV_BUF0 [340..499]     intv input 0
  DEDUP_INTV_BUF1 [500..659]     intv input 1
  DEDUP_DIAG_OUT0 [660..819]     diag output ping
  DEDUP_DIAG_OUT1 [820..979]     diag output pong
  DEDUP_INTV_OUT0 [980..1139]    intv output ping
  DEDUP_INTV_OUT1 [1140..1299]   intv output pong

All fit below GWFA_Q_START/4 = 6016 words (sequence data starts there).

================================================================================
MM LAYOUT (relevant regions)
================================================================================

  MM_DIAG_A       [0]                  diag buffer A
  MM_DIAG_B       [DIAG_CAP*2]        diag buffer B
  MM_A            [DIAG_CAP*4]         extend output
  MM_INTV         [DIAG_CAP*6]         intervals (current)
  MM_NEXT_INTV    [DIAG_CAP*6+INTV*2]  new intervals (from extend)
  MM_SWAP         [DIAG_CAP*6+INTV*4]  swap buffer / dedup intv output
  MM_SORT_BUF     [DIAG_CAP*6+INTV*6]  sort/merge scratch
  MM_HA           [SORT_BUF+DIAG*2]    hash table (extend phase)

--- Original Design Draft End ---
