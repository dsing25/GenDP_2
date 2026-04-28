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
