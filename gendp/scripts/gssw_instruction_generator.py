#!/usr/bin/env python3
"""
GSSW instruction generator.

Magic-101 -> ISA lowering. Section A (prologue/init), section B (outer
node loop head + per-node metadata load), section H (seed push to
children), and section I (final reduce) are emitted as real ISA on
PE 0. The remaining sections (C, D, E, F, G, lazy-F) are delegated
to a C++ mini-magic in pe.cpp (currently magic_id 107) that assumes
sections A+B have already run for the current node and the ISA outer
loop advances n between nodes.

Traces produced:
  instructions/gssw/main_instruction.txt    (controller)
  instructions/gssw/pe_<0..3>_instruction.txt (each PE)
  instructions/gssw/compute_instruction.txt (shared compute trace)

Controller trace:
  PC 0: magic(100) - init SPM from host
  PC 1: set_PC 1   - start all PEs at their PC 1
  PC 2: bne gr[13]!=1, 0 - spin until PE 0 signals done
  PC 3: halt

PE 0 trace (see pe_0_instruction()):
  PC 0        : halt | halt   (wait for controller)
  PC 1..K     : lowered sections A, B, outer-loop head, H, outer-loop
                tail, I
  PC ...      : magic(107) between section B tail and section H
                (runs C..G for one node; H and outer n++ run in ISA)
  PC ...      : magic(102) - print score
  PC ...      : si gr[10]=1 - signal done
  PC ...      : halt | halt

PE 1-3 trace (unchanged):
  PC 0: halt | halt
  PC 1: nop  | si gr[10]=1  (idle PEs signal done immediately)
  PC 2: halt | halt

---------------------------------------------------------------------------
Stage 3b.0 audit documentation (established as a reference for stages
3b-3g that lower sections H, C, D+G, F, E, and lazy-F into ISA). No
functional code below this comment block changes as part of 3b.0 — the
block is purely an ABI / operand-usage / stall-rules reference.
---------------------------------------------------------------------------

Subregister-operand usage contract (AC-1).
Every control-trace opcode in the simulator accepts `gr_lo[r]` /
`gr_hi[r]` operands via the register-address encoding at
`pe.cpp:709-723` (src/dest side) and — after stage 3b.0's simulator
extension — for the SPM-offset register side of `mv`/`mvd`/`mvi`/
`mvi2`/`si` via `pe.cpp:363-372` and `pe.cpp:470-478`. Covered classes:
data-movement (mv/mvd/mvi/mvi2/si/set_8), arithmetic (add/sub/addi/
subi), shifts (shifti_l/shifti_r), logical (ANDI/ORI), branches
(bne/beq/bge/blt), jump, set_PC. `reg_lo`/`reg_hi` are NOT supported
anywhere, and `mvdq` is NOT implemented on PE at all
(`pe.cpp:2820-2825` aborts CTRL_MVDQ). Any ISA emission whose semantics require only the low or
high 16 bits of a packed-half home (see the packed-half table below)
MUST read the value via `gr_lo[r]` / `gr_hi[r]` rather than as the
full 32-bit `gr[r]`. Full-width reads of a packed-half home are
rejected at review.

Packed-half values (magic-101 ABI preserved per DEC-5).
  gr[0]     -- RESERVED 0; never written, used as the 0-base for
               reg_0 / reg_1 = 0 addressing.
  gr[1].lo  -- n (outer node counter, 0..numNodes-1).
     .hi  -- numNodes (kernel constant after section A).
  gr[2].lo  -- col (column counter, 0..seq_len-1). Repurposed to
               full-width `c` inside section H after `gr.st(2, 0)`.
     .hi  -- seq_len (per-node, set by section B).
  gr[3].lo  -- section-local j counter (seed-load, pvF-zero, main,
               lazy-F, best-copy, push-j, final-reduce). Always
               resets to 0 at the start of each loop.
     .hi  -- next_len (per-node, set by section B; stays live until
               the next section-B execution overwrites it). MUST be
               read as `gr_hi[3]` by section H's entry guard and outer
               push-c exit branch.
  gr[4]     -- nd_word_off (full-width).
  gr[5]     -- hPing_word_base (full-width; swapped with gr[6] in G).
  gr[6]     -- hPong_word_base (full-width; swapped with gr[5] in G).
  gr[7]     -- seq_base_idx = graphSeq*16 + seq_off (2-bit mvi2
               index, full-width).
  gr[8]     -- vP_word_base / scratch (full-width).
  gr[9]     -- graphSeq_word_base (full-width; kernel constant).
  gr[10]    -- sync flag (set by ISA stream at kernel exit).
  gr[11]    -- 78 (hoisted multiplier; clobbered by G swap; re-hoisted
               at section H entry).
  gr[12]    -- scratch. When section B loads (next_off|next_len) into
               gr[12:13] via mvd, `gr[12].lo` carries next_off and
               `gr[12].hi` duplicates next_len until stripped.
  gr[13]    -- scratch (MUL output, seq[col] mvi2 result, lazy-F cmp
               flag, misc).
  gr[14].lo -- overallMax (persists across outer loop).
     .hi  -- scratch / unused.
  gr[15]    -- final score (section I output).

Consumer sites that MUST read a packed-half as a subregister operand
(rather than the full 32-bit gr) once stages 3b-3g land. Branches on
packed halves are legal either via subregister operands or via prior
`mv gr[temp] = gr_hi[r]` into a clean full-width temp.
  next_len (gr[3].hi) - section H (3b): entry `beq 0, gr_hi[3],
    push_done`; outer push-c bound `gr[2] < gr_hi[3]`.
  col (gr[2].lo) - section D (3d): `mvi2 SPM[gr[7] + gr_lo[2]]` for
    seq[col]; loop-head `bge gr_lo[2], gr_hi[2], col_done`; G `addi
    gr_lo[2] += 1`.
  seq_len (gr[2].hi) - section D (3d): loop-head branch rhs.
  next_off (gr[12].lo) - section H (3b): `mv gr[12] = gr_lo[12]` or
    equivalent before the `gr[13]<<2 + gr[12]<<1` child-ids base math.
  j counters (gr[3].lo) - every inner loop in sections C (3c), E (3f),
    F (3e best-copy), H (3b push-j), lazy-F (3g), and section I
    (already in trunk).

Section I contract update (landed round 1 commit `c02430b`). Section
I's final-reduce mvd now reads `gr_lo[3]` (via the `spm_lo(3)`
helper) so it is robust to a non-zero `gr[3].hi = next_len` of the
last processed node. Every 16-bit read of a packed-half home in
stages 3b-3g follows the same pattern via `spm_lo` / `spm_hi` or
via `gr_lo` / `gr_hi` src-aliasing in non-SPM ops.

Stall rules (AC-1, DEC-7, rederived against current trunk).
  Cycle costs below are relative to instruction issue. Source cites
  give the enforcement sites in the simulator for spot-checking.
  mvd load  (PE SPM -> reg/gr/out):
      dst visible to consumer:     +2 cycles
      next same-PE reissue:        +2 cycles (outstanding_req depth=1)
      source: pe.h:13-34,101-104; pe.cpp:62-151,419-495,2877-2884
  mvd store (PE reg/gr -> SPM):
      subsequent SPM read sees it: +2 cycles
      next store issue:            +1 cycle (subject to bank avail.)
      source: data_buffer.cpp:240-356
  mv gr <-> gr:                    next-cycle dst, next-cycle reissue
      source: pe.cpp:302-304,323,520-531
  mv into SPM (single-word store): same as mvd store
      source: data_buffer.cpp:240-269,285-290
  mvi2 (PE 2-bit SPM -> gr/reg):   same as mvd load (+2 cycles)
      source: pe.cpp:62-151,490-495
  set_PC (PE compute dispatch):    fires next cycle
      source: pe.cpp:180-187,2731-2736

Structural hazards (AC-1).
- PE `outstanding_req` depth = 1. Back-to-back PE-side SPM loads from
  the same PE must be spaced by >=2 cycles. Violating this triggers
  an assertion in the mvd handler (pe.cpp:62-151).
- Two SPM accesses from the same PE in the same VLIW cycle are
  unsafe: only one `spmReqPort` per PE; a later request overwrites
  an earlier one before arbitration (pe_array.cpp:4459-4495).
- Same-bank PE-vs-PE and PE-vs-LSQ accesses serialize via the SPM
  arbiter (pe_array.cpp:4450-4512; sys_def.h:29 is SPM_ACCESS_LATENCY).
- Current trunk does NOT enforce many historical bans (mvdq+mvdq,
  mvdq+mv, slot-1 magic/branch/jump/halt/set_PC/barrier/IO si|mv);
  pair admission only checks LSQ capacity and branch agreement
  (pe_array.cpp:3955-3982,4360-4396). Generators remain conservative
  anyway — keep slot-1 off those opcodes to stay portable.
- `gr[0]` is writable (not hardwired zero); reset initializes it to 0
  (data_buffer.h:126-146). Never emit a write to gr[0] — the zero-
  base addressing mode depends on it.
- Multi-`mv` src-position conflict: two `mv` ops reading from the same
  non-`gr`/non-`reg` src position in the same VLIW cycle abort
  (pe.cpp:329-332).
- `set_PC` only lands on the next control cycle because the compute
  fetch/execute happens before PE control decode (pe.cpp:180-187).
- PE `mvd` into `gr` writes both words to consecutive gr[n], gr[n+1]
  (pe.cpp:118-124).

Controller pairing now lives in pe_array.cpp; PE local decode is
pe.cpp::decode() (the historical `decode_ctrl`). Mentioning it for
future audit references.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import InstructionWriter, write_magic, \
    data_movement_instruction, compute_instruction
from opcodes import (gr, gr_hi, gr_lo, reg, SPM, halt, none, set_PC,
                     bne, beq, bge, blt, jump, si, mv, mvd, mvi2, addi,
                     shifti_l, shifti_r, ANDI, set_8, add,
                     MULTIPLICATION, HALT, INVALID, COPY,
                     MAX_EPU8, MAX_REDUCE, ADDS_EPU8, SUBS_EPU8, SLLI_64)

# Pre-made NOP (two-slot-agnostic data-movement no-op).
NOP = data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)

# --- GSSW SPM word-offset constants (mirror pe.cpp macros) ---
GSSW_SEG_LEN     = 19        # ceil(148 / 8)
GSSW_VEC_WORDS   = 2         # 2 SPM words per 8-lane pair
GSSW_SPM_PAD     = 8         # bytes
GSSW_PROF_WOFF   = 0
GSSW_HPING_WOFF  = (4 * GSSW_SEG_LEN * 8) // 4        # 152
GSSW_HPONG_WOFF  = GSSW_HPING_WOFF + GSSW_SEG_LEN * 2 # 190
GSSW_E_WOFF      = GSSW_HPONG_WOFF + GSSW_SEG_LEN * 2 # 228
GSSW_F_WOFF      = GSSW_E_WOFF + GSSW_SEG_LEN * 2 + GSSW_SPM_PAD // 4  # 266
GSSW_BEST_WOFF   = GSSW_F_WOFF + GSSW_SEG_LEN * 2 + GSSW_SPM_PAD // 4  # 304
GSSW_META_WOFF   = GSSW_BEST_WOFF + GSSW_SEG_LEN * 2                   # 342
GSSW_NODES_WOFF  = GSSW_META_WOFF + 4                                   # 346
GSSW_ND_WORDS    = 2 + 2 * GSSW_SEG_LEN * GSSW_VEC_WORDS               # 78
GSSW_ND_HSEED_W  = 2                                                    # hSeed within nd
GSSW_ND_ESEED_W  = 2 + GSSW_SEG_LEN * GSSW_VEC_WORDS                    # 40
# Magic 101 hoists gr[11] = GSSW_ND_WORDS (78) as the multiplier for the
# per-node base computation. The inline comment in pe.cpp says "76" but
# the actual value written is 78; follow the code, not the comment.
GSSW_ND_MUL_WORDS = GSSW_ND_WORDS  # 78

# --- Compute trace region PCs (indexes into compute_instruction.txt) ---
# PC 0 is the idle HALT. Other PCs are assigned at generation time.
CPC_MUL          = 1   # gr[13] = gr[1].hi * gr[11]   (section A)
CPC_FINAL_MAX    = 3   # reg[14:15] = max_epu8_pair(reg[14:15], reg[20:21])
CPC_FINAL_TAIL   = 5   # reg[20] = max(reg[14],reg[15]); gr[15] = max_reduce
CPC_MUL_N_78     = 8   # gr[4] = gr[1].lo * gr[11]    (section B)
CPC_MUL_CHILD_78 = 10  # gr[8] = gr[7]    * gr[11]    (section H)
CPC_PUSH_MAX     = 12  # reg[20:21] = max_epu8_pair(reg[20:21], reg[22:23])
CPC_MAXCOL       = 14  # reg[20] = max(reg[14],reg[15]); gr[11] = max_reduce (section F)
# Stage 3f: section E main body compute regions. Each region is one PC
# with two slots (lo/hi) that compute the paired 8-lane step.
CPC_E_SHIFT      = 17  # reg[8:9] = SLLI_64(reg[8:9], 8)  — cross-lane byte shift
CPC_MAIN_S1      = 19  # vH = subs(adds(vH, profScore), vBias)
CPC_MAIN_S2      = 21  # vH = max(max(vH, e), vF)
CPC_MAIN_S3      = 23  # vMaxColumn = max(vMaxColumn, vH)
CPC_MAIN_S4      = 25  # e = max(subs(e, vGapE), subs(vH, vGapO))
CPC_MAIN_S5      = 27  # vF = max(subs(vF, vGapE), subs(vH, vGapO))


# --- Subregister-offset encoding helpers for SPM addressing -----------------
# When src==SPM / dest==SPM in data_movement_instruction, utils.py's
# gr_lo / gr_hi type aliasing does not activate. The simulator's
# resolve_reg_field decodes the top 2 bits of the 7-bit reg index:
# idx[0..31]=CTRL_GR, idx[32..63]=CTRL_GR_LO, idx[64..95]=CTRL_GR_HI.
# After stage 3b.0's pe::load / pe::store rs2_pos plumbing, the simulator
# honors the selector for SPM-offset reads. These helpers encode the
# offset-register field accordingly.
def spm_lo(r):
    return r + 32


def spm_hi(r):
    return r + 64


# ---------------------------------------------------------------------------
# Compute trace
# ---------------------------------------------------------------------------
# Compute address convention: 0-31=reg, 32-47=gr, 48-63=gr_lo, 64-79=gr_hi.
COMP_REG = 0    # base offset for compute reg addressing
COMP_GR  = 32   # base offset for compute gr addressing


def _chalt():
    """Emit a compute HALT pair (one idle VLIW cycle).  Uses the same
    encoding as WFA/BSW: op[0]=HALT and op[1..2]=INVALID so the
    simulator's idle dispatch doesn't accidentally clobber registers."""
    return [compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0),
            compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)]


def gssw_compute_instructions():
    """Emit the shared compute-trace file.

    Layout (PC ordering matches the CPC_* constants above):
      PC 0 : idle HALT
      PC 1 : CPC_MUL           gr[13] = gr[1].hi * gr[11]
      PC 2 : halt tail (after MUL returns to idle)
      PC 3 : CPC_FINAL_MAX     reg[14:15] = max_epu8_pair(reg[14:15], reg[20:21])
      PC 4 : halt tail
      PC 5 : CPC_FINAL_TAIL[0] reg[20] = max_epu8(reg[14], reg[15])  (8->4)
      PC 6 : CPC_FINAL_TAIL[1] gr[15]  = max_reduce(reg[20])
      PC 7 : halt tail
      PC 8 : CPC_MUL_N_78      gr[4]  = gr[1].lo * gr[11]
      PC 9 : halt tail
      PC 10: CPC_MUL_CHILD_78  gr[8]  = gr[7]    * gr[11]
      PC 11: halt tail
      PC 12: CPC_PUSH_MAX[0]   reg[20] = max_epu8(reg[20], reg[22])
      PC 13: CPC_PUSH_MAX[1]   reg[21] = max_epu8(reg[21], reg[23])
      PC 14: halt tail
    """
    f = InstructionWriter("instructions/gssw/compute_instruction.txt")
    # PC 0 — idle.
    for ins in _chalt(): f.write(ins)
    # PC 1 — CPC_MUL : gr[13] = gr[1].hi * gr[11].
    f.write(compute_instruction(MULTIPLICATION, HALT, HALT, 65, 43, 0, 0, 0, 0, COMP_GR + 13))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 2 — halt tail for MUL.
    for ins in _chalt(): f.write(ins)
    # PC 3 — CPC_FINAL_MAX : reg[14] = max(reg[14], reg[20]); reg[15] = max(reg[15], reg[21]).
    # op_0 = MAX_EPU8 produces lane-wise max; op_2 = COPY forwards the
    # 4-input ALU result to the output.
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 14, 20, 0, 0, 0, 0, 14))
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 15, 21, 0, 0, 0, 0, 15))
    # PC 4 — halt tail for FINAL_MAX.
    for ins in _chalt(): f.write(ins)
    # PC 5 — CPC_FINAL_TAIL[0] : reg[20] = max_epu8(reg[14], reg[15]).
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 14, 15, 0, 0, 0, 0, 20))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 6 — CPC_FINAL_TAIL[1] : gr[15] = max_reduce(reg[20]).
    f.write(compute_instruction(MAX_REDUCE, INVALID, COPY, 20, 0, 0, 0, 0, 0, COMP_GR + 15))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 7 — halt tail.
    for ins in _chalt(): f.write(ins)
    # PC 8 — CPC_MUL_N_78 : gr[4] = gr[1].lo * gr[11]  (section B).
    # gr[1].lo compute address = 48 + 1 = 49, gr[11] = 32+11 = 43,
    # output gr[4] = 32 + 4 = 36.
    f.write(compute_instruction(MULTIPLICATION, HALT, HALT, 49, 43, 0, 0, 0, 0, COMP_GR + 4))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 9 — halt tail.
    for ins in _chalt(): f.write(ins)
    # PC 10 — CPC_MUL_CHILD_78 : gr[8] = gr[7] * gr[11]  (section H).
    # gr[7] = 32+7 = 39, gr[11] = 43, output gr[8] = 32+8 = 40.
    f.write(compute_instruction(MULTIPLICATION, HALT, HALT, 39, 43, 0, 0, 0, 0, COMP_GR + 8))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 11 — halt tail for CPC_MUL_CHILD_78.
    for ins in _chalt(): f.write(ins)
    # PC 12 — CPC_PUSH_MAX : paired MAX_EPU8 on reg[20:21] vs reg[22:23].
    # Matches magic 101 section H's inner push_j max(hSeed, hPing) and
    # max(eSeed, pvE). slot 0 writes reg[20], slot 1 writes reg[21].
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 20, 22, 0, 0, 0, 0, 20))
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 21, 23, 0, 0, 0, 0, 21))
    # PC 13 — halt tail for CPC_PUSH_MAX.
    for ins in _chalt(): f.write(ins)
    # PC 14 — CPC_MAXCOL[0] : reg[20] = max_epu8(reg[14], reg[15]).
    # Section F (stage 3e) colMax = reduce of vMaxColumn pair.
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 14, 15, 0, 0, 0, 0, 20))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 15 — CPC_MAXCOL[1] : gr[11] = max_reduce(reg[20]).
    f.write(compute_instruction(MAX_REDUCE, INVALID, COPY, 20, 0, 0, 0, 0, 0, COMP_GR + 11))
    f.write(compute_instruction(HALT, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # PC 16 — halt tail for CPC_MAXCOL.
    for ins in _chalt(): f.write(ins)
    # PC 17 — CPC_E_SHIFT (section E prologue): reg[8:9] = SLLI_64(reg[8:9], 8).
    # SLLI_64 is an immediate opcode (sys_def.h:117); cu_inputs[s][0] is
    # taken from input_addr[0] field directly (not a regfile read), so we
    # pass 8 as the shift amount. Slot 0 emits the new low word (reg[8]);
    # slot 1 emits the new high word (reg[9]).
    f.write(compute_instruction(SLLI_64, HALT, HALT, 8, 8, 9, 0, 0, 0, 8))
    f.write(compute_instruction(SLLI_64, HALT, HALT, 8, 8, 9, 0, 0, 0, 9))
    # PC 18 — halt tail for CPC_E_SHIFT.
    for ins in _chalt(): f.write(ins)
    # PC 19 — CPC_MAIN_S1 (section E step 1): vH = subs(adds(vH,profScore),vBias).
    f.write(compute_instruction(ADDS_EPU8, COPY, SUBS_EPU8, 8, 16, 0, 0, 0, 0, 8))
    f.write(compute_instruction(ADDS_EPU8, COPY, SUBS_EPU8, 9, 17, 0, 0, 1, 0, 9))
    # PC 20 — halt tail for CPC_MAIN_S1.
    for ins in _chalt(): f.write(ins)
    # PC 21 — CPC_MAIN_S2: vH = max(max(vH, e), vF).
    f.write(compute_instruction(MAX_EPU8, COPY, MAX_EPU8, 8, 12, 0, 0, 10, 0, 8))
    f.write(compute_instruction(MAX_EPU8, COPY, MAX_EPU8, 9, 13, 0, 0, 11, 0, 9))
    # PC 22 — halt tail for CPC_MAIN_S2.
    for ins in _chalt(): f.write(ins)
    # PC 23 — CPC_MAIN_S3: vMaxColumn = max(vMaxColumn, vH).
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 14, 8, 0, 0, 0, 0, 14))
    f.write(compute_instruction(MAX_EPU8, INVALID, COPY, 15, 9, 0, 0, 0, 0, 15))
    # PC 24 — halt tail for CPC_MAIN_S3.
    for ins in _chalt(): f.write(ins)
    # PC 25 — CPC_MAIN_S4: e = max(subs(e, vGapE), subs(vH, vGapO)).
    f.write(compute_instruction(SUBS_EPU8, SUBS_EPU8, MAX_EPU8, 12, 4, 0, 0, 8, 2, 12))
    f.write(compute_instruction(SUBS_EPU8, SUBS_EPU8, MAX_EPU8, 13, 5, 0, 0, 9, 3, 13))
    # PC 26 — halt tail for CPC_MAIN_S4.
    for ins in _chalt(): f.write(ins)
    # PC 27 — CPC_MAIN_S5: vF = max(subs(vF, vGapE), subs(vH, vGapO)).
    f.write(compute_instruction(SUBS_EPU8, SUBS_EPU8, MAX_EPU8, 10, 4, 0, 0, 8, 2, 10))
    f.write(compute_instruction(SUBS_EPU8, SUBS_EPU8, MAX_EPU8, 11, 5, 0, 0, 9, 3, 11))
    # PC 28 — halt tail for CPC_MAIN_S5.
    for ins in _chalt(): f.write(ins)
    f.close()


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
def gssw_main_instruction():
    f = InstructionWriter("instructions/gssw/main_instruction.txt")
    # PC 0: magic(100) - init SPM from host
    f.write(write_magic(100))
    # PC 1: set_PC 1 -> start all PEs at their PC 1
    f.write(data_movement_instruction(0, 0, 0, 0, 1, 0, 0, 0, 0, 0, set_PC))
    # PC 2: spin until gr[13] == 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))
    # PC 3: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.close()


# ---------------------------------------------------------------------------
# PE 0 : lowered section A + magic(103) + magic(102) + signal done
# ---------------------------------------------------------------------------
def pe_0_instruction(f):
    # PC 0: halt | halt (wait for controller set_PC 1)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

    # === Section A (lowered) ===
    # Broadcast constants into reg[0..7].  Each set_8 writes
    # (imm8 & 0xFF) * 0x01010101 to one compute register.
    # reg[0:1] = vBias (0x04040404)
    f.write(data_movement_instruction(reg, 0, 0, 0, 0, 0, 0, 0, 4, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 1, 0, 0, 0, 4, 0, set_8))
    # reg[2:3] = vGapO (0x06060606)
    f.write(data_movement_instruction(reg, 0, 0, 0, 2, 0, 0, 0, 6, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 3, 0, 0, 0, 6, 0, set_8))
    # reg[4:5] = vGapE (0x01010101)
    f.write(data_movement_instruction(reg, 0, 0, 0, 4, 0, 0, 0, 1, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 5, 0, 0, 0, 1, 0, set_8))
    # reg[6:7] = vZero
    f.write(data_movement_instruction(reg, 0, 0, 0, 6, 0, 0, 0, 0, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 7, 0, 0, 0, 0, 0, set_8))

    # Load gr[11]=numNodes, gr[12]=total_nexts from SPM[GSSW_META_WOFF].
    # mvd loads 2 consecutive words. Pair with NOP.
    f.write(data_movement_instruction(gr, SPM, 0, 0, 11, 0, 0, 0, GSSW_META_WOFF, 0, mvd))
    f.write(NOP)
    # SPM latency (2 cycles).
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # mv gr[1].hi = gr[11]  |  NOP
    # Writes the upper 16 bits of gr[1] to numNodes. gr[11] is preserved.
    f.write(data_movement_instruction(gr_hi, gr, 0, 0, 1, 0, 0, 0, 11, 0, mv))
    f.write(NOP)

    # si gr[11] = GSSW_ND_MUL_WORDS  |  addi gr[12] = gr[12] + 1
    # gr[11] is now 76 (ready as the MUL multiplier).
    # slot 1 addi pre-computes (total_nexts + 1) while the compute trace
    # hasn't started yet.
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, GSSW_ND_MUL_WORDS, 0, si))
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, addi))

    # set_PC CPC_MUL  |  shifti_r gr[12] = gr[12] >> 1
    # Launches the compute-trace MUL. It fires next cycle and writes
    # gr[13] = gr[1].hi * gr[11] = numNodes * 76.
    # Slot 1 finishes the (total_nexts+1)/2 computation (no dep on gr[13]).
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MUL, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, shifti_r))

    # Cycle for compute MUL to fire; no gr[13] use here.
    f.write(NOP); f.write(NOP)

    # addi gr[13] = gr[13] + GSSW_NODES_WOFF  |  NOP
    # gr[13] now holds graphSeq_word_base minus the tail term.
    f.write(data_movement_instruction(gr, gr, 0, 0, 13, 0, 0, 0, GSSW_NODES_WOFF, 13, addi))
    f.write(NOP)

    # add gr[9] = gr[13] + gr[12]  |  si gr[14].lo = 0
    # gr[9] is graphSeq_word_base. overallMax reset.
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 13, 12, add))
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))

    # si gr[1].lo = 0  |  si gr[3].lo = 0
    # n = 0 and the best_zero loop counter = 0.
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))

    # best_zero loop.
    #   for gr[3].lo in 0..SEG_LEN-1:
    #       SPM[GSSW_BEST_WOFF + gr[3].lo] = 0
    #
    # Body (2 VLIW cycles):
    #   Cycle 1:  si SPM[gr[3].lo + GSSW_BEST_WOFF] = 0  |  addi gr[3].lo += 1
    #   Cycle 2:  blt gr[3].lo, SEG_LEN, -1              |  NOP
    best_zero_pc = f.pc  # capture PC of loop-head (the si cycle)
    f.write(data_movement_instruction(
        SPM, 0, 0, 0, GSSW_BEST_WOFF, 3, 0, 0, 0, 0, si))
    f.write(data_movement_instruction(
        gr_lo, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi))
    blt_pc = f.pc
    branch_off = best_zero_pc - blt_pc  # negative
    # bne imm, gr[rs2], offset: branches while imm != gr[rs2].
    # At loop end gr[3].lo == SEG_LEN so the bne falls through.
    # gr[3].hi is still 0, so reading gr[3] full == gr[3].lo.
    f.write(data_movement_instruction(
        0, 0, 0, 0, branch_off, 0, 0, 0, GSSW_SEG_LEN, 3, bne))
    f.write(NOP)

    # End of section A.

    # === Section B (lowered): outer node loop wiring + per-node meta ===
    # Section A has already set gr[1].lo=0 (n=0), gr[1].hi=numNodes,
    # gr[9]=graphSeq_word_base, gr[11]=78, gr[14].lo=0.  Each iteration
    # here runs one node of sections C..H via magic(106), then n++.

    node_pc = f.pc  # label: m_101_node (top of outer loop)

    # Move halves for the exit check (bge reads gr full; no subregister).
    # Use gr[13] and gr[15] as temps. (gr[0] is the implicit 0-base for
    # addressing-mode decodes where reg_0/reg_1=0 — never write to it.
    # gr[13] was nN*78 from section A, section B will overwrite it via MUL.
    # gr[15] is the final score; section I reassigns it so clobber is fine.)
    f.write(data_movement_instruction(gr, gr_lo, 0, 0, 13, 0, 0, 0, 1, 0, mv))
    f.write(data_movement_instruction(gr, gr_hi, 0, 0, 15, 0, 0, 0, 1, 0, mv))

    # Exit check: bge gr[13] (=n), gr[15] (=numNodes), off_exit
    # (Patched after the loop body so off_exit targets the fall-through
    # PC just past the jump-back below.)
    bge_exit_wi = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 13, 15, bge))
    f.write(NOP)

    # Compute n*78 -> gr[4]. Fire CPC_MUL_N_78.
    # slot 0: set_PC CPC_MUL_N_78   slot 1: NOP
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MUL_N_78, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    # Wait one cycle; compute fires MUL next cycle writing gr[4].
    f.write(NOP); f.write(NOP)

    # addi gr[4] += GSSW_NODES_WOFF   (nd_word_off)
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, GSSW_NODES_WOFF, 4, addi))
    f.write(NOP)

    # mvd gr[12:13] = SPM[gr[4]]     (seq_off|seq_len , next_off|next_len)
    f.write(data_movement_instruction(gr, SPM, 0, 0, 12, 0, 0, 0, 0, 4, mvd))
    f.write(NOP)
    # SPM latency: 1 NOP cycle so gr[12]/gr[13] valid on the next cycle.
    f.write(NOP); f.write(NOP)

    # mv gr[2].hi = gr[12].hi   (slot 0)  |  NOP
    # The simulator rejects two mv's sharing a non-gr/reg src position
    # in the same cycle, so we can't pair two gr_hi reads.  Split into
    # back-to-back cycles.
    f.write(data_movement_instruction(gr_hi, gr_hi, 0, 0, 2, 0, 0, 0, 12, 0, mv))
    f.write(NOP)
    # DEC-5 relaxation (round 6-7): route next_len via gr[15] full-width.
    # The older `mv gr_hi[3] = gr_hi[13]` is dropped because (a) section H
    # ISA reads gr[15], not gr[3].hi, and (b) keeping gr[3].hi = 0 lets
    # section C's full-gr `bne gr[3] != 38` fall through correctly without
    # a subregister encoding on the bne rs2.
    f.write(data_movement_instruction(gr, gr_hi, 0, 0, 15, 0, 0, 0, 13, 0, mv))
    f.write(NOP)

    # shifti_l gr[7] = gr[9] << 4   |   mv gr[8] = gr[12].lo
    # (seq_base_idx = graphSeq_word_base * 16 + seq_off)
    f.write(data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, 4, 9, shifti_l))
    f.write(data_movement_instruction(gr, gr_lo, 0, 0, 8, 0, 0, 0, 12, 0, mv))

    # add gr[7] = gr[7] + gr[8]    |   NOP
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 7, 8, add))
    f.write(NOP)

    # === Section C (lowered): seed load =====================================
    # Copy the current node's hSeed → hPing and eSeed → pvE (19 paired
    # 8-lane words). Inputs: gr[4] = nd_word_off. Outputs consumed by D..G:
    # gr[5] = HPING_WOFF, gr[6] = HPONG_WOFF. Scratch: gr[13] = hSeed_base,
    # gr[8] = eSeed_base. CRITICAL: do NOT write gr[10] (sync flag).

    f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, GSSW_HPING_WOFF, 0, si))
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, GSSW_HPONG_WOFF, 0, si))

    f.write(data_movement_instruction(gr, gr, 0, 0, 13, 0, 0, 0, GSSW_ND_HSEED_W, 4, addi))
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, GSSW_ND_ESEED_W, 4, addi))

    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))
    f.write(NOP)

    # Inner seed-load loop: 19 iters (j = 0..36 step 2).
    seed_load_pc = f.pc
    f.write(data_movement_instruction(reg, SPM, 0, 0, 20, 0, 1, 0, 13, spm_lo(3), mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(reg, SPM, 0, 0, 22, 0, 1, 0, 8, spm_lo(3), mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(SPM, reg, 1, 0, 5, spm_lo(3), 0, 0, 20, 0, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    # pvE store + j+=2, slot-swap:
    #   slot 0 = addi gr_lo[3] += 2 (WRITE)
    #   slot 1 = mvd SPM[E_WOFF + gr_lo[3]] = reg[22:23] (READ gr_lo[3])
    # Slot 1 decodes first and reads OLD gr_lo[3] for the store addr;
    # slot 0 addi then writes the NEW gr_lo[3] for the next iter's bne.
    # Saves one VLIW per iter × 19 iters vs the earlier split form.
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 3, 0, 0, 0, 2, 3, addi))
    f.write(data_movement_instruction(SPM, reg, 0, 0, GSSW_E_WOFF, spm_lo(3), 0, 0, 22, 0, mvd))
    seed_load_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, seed_load_pc - seed_load_back_pc, 0, 0, 0,
        GSSW_SEG_LEN * GSSW_VEC_WORDS, 3, bne))
    f.write(NOP)

    # Drain pipelines before the magic call (SPM writes have 2-cycle commit;
    # magic-108's C++ body reads SPM buffer directly).
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # === Section D+G (lowered): column loop wrapping (stage 3d) ==============
    # ISA owns the outer column iteration; magic(109) runs one column's
    # body (E + lazy-F + F) per call. Strategy:
    #   - Copy gr[2].hi (seq_len) into gr[12] (full width) BEFORE the loop
    #     so the D-head bge can compare gr[2].lo to gr[12].lo without
    #     straddling a subregister/full-gr boundary.
    #   - D-head per iter: mvi2 seq[col] → gr[13], bge col >= seq_len.
    #   - magic(109): runs E + lazy-F + F for this column.
    #   - G-tail per iter: swap gr[5]/gr[6] via gr[11] temp, addi
    #     gr[2].lo += 1, jump back to col head.
    #
    # Simulator note: mvi2's SPM-offset subregister support was added this
    # stage (pe.cpp:2861 now passes src_resolved into the addr_regfile
    # read of reg_1), so `gr_lo[2]` encodes correctly as the mvi2 offset.

    # Copy seq_len to gr[12] (full). mv gr[12] = gr_hi[2] sign-extends the
    # 16-bit seq_len into the full 32-bit gr[12]; seq_len is positive, so
    # gr[12].lo = seq_len and gr[12].hi = 0.
    f.write(data_movement_instruction(gr, gr_hi, 0, 0, 12, 0, 0, 0, 2, 0, mv))
    f.write(NOP)

    # col = 0
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))
    f.write(NOP)

    col_pc = f.pc

    # mvi2 gr[13] = SPM[gr[7] + gr[2].lo] — seq[col] as 2-bit extract.
    f.write(data_movement_instruction(gr, SPM, 0, 0, 13, 0, 1, 0, 7, spm_lo(2), mvi2))
    f.write(NOP)
    # SPM latency (2 cycles) + mvi2 delivery.
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # bge gr[2].lo >= gr[12].lo, col_done_fwd_patch. src=gr with
    # reg_1 = spm_lo(12) forces both comp_0 and comp_1 to use
    # CTRL_GR_LO; comp_0 reads gr[imm_1=2].lo = col, comp_1 reads
    # gr[reg_1=12].lo = seq_len.
    bge_col_wi = f.write_count
    bge_col_pc = f.pc
    f.write(data_movement_instruction(0, gr, 0, 0, 0, 0, 1, 0, 2, spm_lo(12), bge))
    f.write(NOP)

    # === Section E (lowered): prologue + 19-iter main inner DP loop =========
    # State at entry: gr[5]=hPing_base, gr[6]=hPong_base (per current
    # col parity), gr[13]=seq[col] (just mvi2'd), gr[2].lo=col,
    # gr[12].lo=seq_len. reg[0:1]=vBias, reg[2:3]=vGapO, reg[4:5]=vGapE,
    # reg[6:7]=vZero (from section A).
    # At exit: reg[8:9]=vH, reg[10:11]=vF, reg[12:13]=e (next iter's),
    # reg[14:15]=vMaxColumn. gr[3]=0 (bne fell through at 38, .hi=0).
    # Magic 111 (lazy-F only) is called after; section F + G ISA continue.

    # Prologue: mvd reg[8:9] = hPing[last pair] (vH init).
    f.write(data_movement_instruction(
        reg, SPM, 0, 0, 8, 0, 0, 0,
        (GSSW_SEG_LEN - 1) * GSSW_VEC_WORDS, 5, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # mvd reg[12:13] = pvE[0:1] (e init).
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, GSSW_E_WOFF, 0, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # vF = 0.
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 11, 0, 0, 0, 0, 0, set_8))
    # vMaxColumn = 0.
    f.write(data_movement_instruction(reg, 0, 0, 0, 14, 0, 0, 0, 0, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, set_8))

    # vP_word_base = gr[13]*38 + PROF_WOFF via unrolled shift-add.
    # 38 = 32 + 4 + 2 = (<<5) + (<<2) + (<<1). Use gr[11] and overwrite
    # gr[13] for scratch. gr[11] is clobbered by section F anyway.
    # Cycle a: slot 0 shifti_l gr[11]=gr[13]<<5 | slot 1 shifti_l gr[8]=gr[13]<<2.
    # Slot 1 decodes first, reads original gr[13]; slot 0 reads original gr[13].
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 5, 13, shifti_l))
    f.write(data_movement_instruction(gr, 0, 0, 0, 8, 0, 0, 0, 2, 13, shifti_l))
    # Cycle b: shifti_l gr[13] = gr[13] << 1 (destructive on gr[13]).
    f.write(data_movement_instruction(gr, 0, 0, 0, 13, 0, 0, 0, 1, 13, shifti_l))
    f.write(NOP)
    # Cycle c: add gr[8] = gr[8] + gr[11].
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 8, 11, add))
    f.write(NOP)
    # Cycle d: add gr[8] = gr[8] + gr[13].
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 8, 13, add))
    f.write(NOP)
    # Cycle e: addi gr[8] += PROF_WOFF.
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, GSSW_PROF_WOFF, 8, addi))
    f.write(NOP)

    # Compute-trace barrier + cross-lane byte shift: reg[8:9] <<= 8.
    # Park compute at PC 0 (idle HALT) first to drain any in-flight writes,
    # then set_PC CPC_E_SHIFT. Immediate shift amount = 8 (encoded in
    # input_addr[0] of CPC_E_SHIFT).
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_E_SHIFT, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # pvF_zero loop: 19 iters clearing SPM[F_WOFF + 0..37] to 0 using
    # reg[6:7] = vZero. Slot-swap: addi in slot 0, mvd store in slot 1.
    # Slot 1 decodes first -> reads OLD gr[3].lo for the store addr;
    # slot 0 addi writes NEW gr[3].lo for the next iter.
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))
    f.write(NOP)
    pvf_pc = f.pc
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 3, 0, 0, 0, 2, 3, addi))
    f.write(data_movement_instruction(SPM, reg, 0, 0, GSSW_F_WOFF, spm_lo(3), 0, 0, 6, 0, mvd))
    pvf_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, pvf_pc - pvf_back_pc, 0, 0, 0,
        GSSW_SEG_LEN * GSSW_VEC_WORDS, 3, bne))
    f.write(NOP)
    # SPM drain.
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # Initial profScore load: reg[16:17] = SPM[gr[8] + 0]; gr[8] += 2.
    # Slot-swap: addi in slot 0, mvd in slot 1. mvd reads OLD gr[8]
    # (= vP_word_base); addi then writes gr[8] = vP_word_base + 2.
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 2, 8, addi))
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 1, 0, 8, 0, mvd))
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # Reset main-loop j counter.
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))
    f.write(NOP)

    # --- Main inner DP loop body (19 iters × 15 VLIW cycles) -----------------
    # Interleaving (each step fires its CPC region; compute executes next
    # cycle on the regfile reads of THIS cycle; result committed by end of
    # that next cycle; the step AFTER that reads the committed result).
    #
    # The 2-cycle spacing between set_PCs (set_PC + NOP | SPM-op, then
    # set_PC of the next step) ensures the next step's compute reads the
    # previous step's output.
    main_pc = f.pc
    # Cycle 1: set_PC CPC_MAIN_S1 | NOP
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MAIN_S1, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    # Cycle 2: mvd load next profScore | NOP
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 1, 0, 8, spm_lo(3), mvd))
    f.write(NOP)
    # Cycle 3: set_PC CPC_MAIN_S2 | NOP
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MAIN_S2, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    # Cycle 4: mvd store pvF[j] = reg[10:11] (old vF) | NOP
    f.write(data_movement_instruction(SPM, reg, 0, 0, GSSW_F_WOFF, spm_lo(3), 0, 0, 10, 0, mvd))
    f.write(NOP)
    # Cycle 5: set_PC CPC_MAIN_S3 | NOP
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MAIN_S3, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    # Cycle 6: mvd store hPong[j] = reg[8:9] | NOP
    f.write(data_movement_instruction(SPM, reg, 1, 0, 6, spm_lo(3), 0, 0, 8, 0, mvd))
    f.write(NOP)
    # Cycle 7: set_PC CPC_MAIN_S4 | NOP
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MAIN_S4, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    # Cycle 8: mvd reg[20:21] = hPing[j:j+1] (preload next iter vH) | NOP
    f.write(data_movement_instruction(reg, SPM, 0, 0, 20, 0, 1, 0, 5, spm_lo(3), mvd))
    f.write(NOP)
    # Cycle 9: set_PC CPC_MAIN_S5 | NOP
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MAIN_S5, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    # Cycle 10: mvd store pvE[j] = reg[12:13] | NOP
    f.write(data_movement_instruction(SPM, reg, 0, 0, GSSW_E_WOFF, spm_lo(3), 0, 0, 12, 0, mvd))
    f.write(NOP)
    # Cycle 11: mv reg[8]=reg[20] | mv reg[9]=reg[21]
    f.write(data_movement_instruction(reg, reg, 0, 0, 8, 0, 0, 0, 20, 0, mv))
    f.write(data_movement_instruction(reg, reg, 0, 0, 9, 0, 0, 0, 21, 0, mv))
    # Cycle 12: SPM drain pair
    f.write(NOP); f.write(NOP)
    # Cycle 13: addi gr[3].lo += 2 (slot 0) | mvd reg[12:13] = SPM[E_WOFF+2+gr[3].lo] (slot 1)
    # Slot 1 decodes first -> reads OLD gr[3].lo; mvd reads e[j+2:j+3]
    # (= NEXT iter's e). Slot 0 addi writes NEW gr[3].lo for next iter's bne.
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 3, 0, 0, 0, 2, 3, addi))
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, GSSW_E_WOFF + 2, spm_lo(3), mvd))
    # Cycle 14: drain
    f.write(NOP); f.write(NOP)
    # Cycle 15: bne gr[3] != 38, main_pc
    main_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, main_pc - main_back_pc, 0, 0, 0,
        GSSW_SEG_LEN * GSSW_VEC_WORDS, 3, bne))
    f.write(NOP)

    # Drain compute before magic 111.
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # Body: run lazy-F only via magic(111). State at entry:
    # reg[8:9]=vH, reg[10:11]=vF (post-step5), reg[12:13]=e_next,
    # reg[14:15]=vMaxColumn. gr[5]/gr[6]=hPing/hPong (pre-G swap).
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))
    f.write(write_magic(111))

    # === Section F (lowered): horizontal max + conditional best_copy =========
    # Fire CPC_MAXCOL: slot 0 of PC 14 does reg[20] = max_epu8(reg[14],
    # reg[15]); slot 0 of PC 15 does gr[11] = MAX_REDUCE(reg[20]). Total
    # 2 compute cycles. Give 3 NOP pairs before reading gr[11] so the
    # control-side bge sees the committed MAX_REDUCE output.
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MAXCOL, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # bge gr_lo[14] (overallMax) >= gr_lo[11] (colMax), skip_best_fwd.
    # src=gr with reg_1 = spm_lo(11) forces both operands via CTRL_GR_LO.
    skip_best_wi = f.write_count
    skip_best_pc = f.pc
    f.write(data_movement_instruction(0, gr, 0, 0, 0, 0, 1, 0, 14, spm_lo(11), bge))
    f.write(NOP)

    # overallMax = colMax. mv gr_lo[14] = gr_lo[11].
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 14, 0, 0, 0, 11, 0, mv))
    f.write(NOP)

    # j = 0 (best-copy counter).
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))
    f.write(NOP)

    # best_copy loop: hPong[j:j+1] -> best[j:j+1], step 2, 19 iters.
    # hPong is at gr[6] (pre-G swap, so still hPong). Structure:
    #   C0: mvd reg[20:21] = SPM[gr[6] + gr[3].lo]   | NOP
    #   C1-C2: NOPs (SPM latency, 2 cycles).
    #   C3: addi gr[3].lo += 2                        | mvd SPM[BEST + gr[3].lo] = reg[20:21]
    # The slot swap (addi in slot 0, mvd-store in slot 1) leverages the
    # slot-1-decodes-first rule: slot 1 reads OLD gr[3].lo for the store
    # address, then slot 0 writes NEW gr[3].lo via set_output_dest. Saves
    # one cycle per iter vs the stage-3b pattern of addi-on-its-own-cycle.
    #   C4: bne gr[3] != 38, loop_head                | NOP
    best_copy_pc = f.pc
    f.write(data_movement_instruction(reg, SPM, 0, 0, 20, 0, 1, 0, 6, spm_lo(3), mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 3, 0, 0, 0, 2, 3, addi))
    f.write(data_movement_instruction(SPM, reg, 0, 0, GSSW_BEST_WOFF, spm_lo(3), 0, 0, 20, 0, mvd))
    best_copy_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, best_copy_pc - best_copy_back_pc, 0, 0, 0,
        GSSW_SEG_LEN * GSSW_VEC_WORDS, 3, bne))
    f.write(NOP)

    # skip_best: patch the bge target.
    skip_best_target_pc = f.pc
    f.patch_imm0(skip_best_wi, skip_best_target_pc - skip_best_pc)

    # Section G (lowered): swap gr[5] (hPing) and gr[6] (hPong) via gr[11]
    # temp. gr[11] holds colMax after the section-F CPC_MAXCOL; clobbered
    # here, then re-inited to 78 at section H entry. Three separate VLIW
    # cycles avoid src-position conflicts between paired mv's.
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 5, 0, mv))
    f.write(NOP)
    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 6, 0, mv))
    f.write(NOP)
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 11, 0, mv))
    f.write(NOP)

    # col += 1 on its own cycle (matches magic 101's CTRL_GR_LO semantic).
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 2, 0, 0, 0, 1, 2, addi))
    f.write(NOP)

    # Jump back to col_pc.
    col_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, col_pc - col_back_pc, 0, 0, 0, 0, 0, jump))
    f.write(NOP)

    # col_done: patch the D-head bge to land here.
    col_done_pc = f.pc
    f.patch_imm0(bge_col_wi, col_done_pc - bge_col_pc)

    # === Section H (lowered): seed push to children =========================
    # Per-node post-column-loop step. gr[15] = next_len (DEC-5 relaxed).
    # Register plan documented in round-5 summary.

    # H1: mv gr[12] = SPM[gr[4]+1] | si gr[11] = 78
    f.write(data_movement_instruction(gr, SPM, 0, 0, 12, 0, 0, 0, 1, 4, mv))
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, GSSW_ND_MUL_WORDS, 0, si))
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # H4: set_PC CPC_MUL | mv gr[12] = gr_lo[12]
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MUL, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(gr, gr_lo, 0, 0, 12, 0, 0, 0, 12, 0, mv))
    f.write(NOP); f.write(NOP)

    # H6: addi gr[13] += NODES_WOFF | shifti_l gr[12] = gr[12] << 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 13, 0, 0, 0, GSSW_NODES_WOFF, 13, addi))
    f.write(data_movement_instruction(gr, 0, 0, 0, 12, 0, 0, 0, 1, 12, shifti_l))

    # H7: shifti_l gr[13] = gr[13] << 2 | si gr[2] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 13, 0, 0, 0, 2, 13, shifti_l))
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))

    # H8: add gr[12] = gr[13] + gr[12] | NOP
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 13, 12, add))
    f.write(NOP)

    # H9: beq 0, gr[15], push_done_fwd | NOP
    push_done_wi = f.write_count
    push_done_branch_pc = f.pc
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 15, beq))
    f.write(NOP)

    push_pc = f.pc
    # H10-H11: compute byte addr of childIds[next_off + c]
    f.write(data_movement_instruction(gr, 0, 0, 0, 13, 0, 0, 0, 1, 2, shifti_l))
    f.write(NOP)
    f.write(data_movement_instruction(gr, gr, 0, 0, 13, 0, 0, 0, 13, 12, add))
    f.write(NOP)
    # H12: gr[7] = word idx, gr[8] = byte offset
    f.write(data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, 2, 13, shifti_r))
    f.write(data_movement_instruction(gr, 0, 0, 0, 8, 0, 0, 0, 3, 13, ANDI))
    # H13: mv gr[7] = SPM[gr[7]]
    f.write(data_movement_instruction(gr, SPM, 0, 0, 7, 0, 0, 0, 0, 7, mv))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    # H16: beq 0, gr[8], child_b0_fwd
    child_b0_wi = f.write_count
    child_b0_branch_pc = f.pc
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 8, beq))
    f.write(NOP)
    # b2 arm
    f.write(data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, 16, 7, shifti_r))
    f.write(NOP)
    f.write(data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, 0xFFFF, 7, ANDI))
    f.write(NOP)
    child_done_jump_wi = f.write_count
    child_done_jump_pc = f.pc
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))
    f.write(NOP)
    # b0 arm
    child_b0_target_pc = f.pc
    f.patch_imm0(child_b0_wi, child_b0_target_pc - child_b0_branch_pc)
    f.write(data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, 0xFFFF, 7, ANDI))
    f.write(NOP)
    # child_done
    child_done_target_pc = f.pc
    f.patch_imm0(child_done_jump_wi, child_done_target_pc - child_done_jump_pc)
    # child * 78
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_MUL_CHILD_78, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    # gr[6] = cd_word_off
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, GSSW_NODES_WOFF, 8, addi))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    # hSeed_base, eSeed_base — split into separate cycles to avoid slot
    # 0/1 read contention on gr[6] (which was just written one cycle ago).
    f.write(data_movement_instruction(gr, gr, 0, 0, 13, 0, 0, 0, GSSW_ND_HSEED_W, 6, addi))
    f.write(NOP)
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, GSSW_ND_ESEED_W, 6, addi))
    f.write(NOP)
    # reset push_j counter
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 0, 0, si))
    f.write(NOP)
    # Inner push-j loop
    push_j_pc = f.pc
    f.write(data_movement_instruction(reg, SPM, 0, 0, 20, 0, 1, 0, 13, 6, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(reg, SPM, 0, 0, 22, 0, 1, 0, 5, 6, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_PUSH_MAX, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(SPM, reg, 1, 0, 13, 6, 0, 0, 20, 0, mvd))
    f.write(NOP)
    f.write(data_movement_instruction(reg, SPM, 0, 0, 20, 0, 1, 0, 8, 6, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(reg, SPM, 0, 0, 22, 0, 0, 0, GSSW_E_WOFF, 6, mvd))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(data_movement_instruction(0, 0, 0, 0, CPC_PUSH_MAX, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    # eSeed store + j+=2, slot-swap:
    #   slot 0 = addi gr[6] += 2 (WRITE)
    #   slot 1 = mvd SPM[gr[8]+gr[6]] = reg[20:21] (READ gr[6])
    # Slot 1 decodes first (pe.cpp:303-304) and reads OLD gr[6] (= 36 on
    # iter 19) for the store addr; slot 0 addi then writes gr[6] = 38 for
    # the next iter's bne. This replaces the earlier split-into-two-cycles
    # form and saves one VLIW per iter × 19 iters.
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 2, 6, addi))
    f.write(data_movement_instruction(SPM, reg, 1, 0, 8, 6, 0, 0, 20, 0, mvd))
    push_j_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, push_j_pc - push_j_back_pc, 0, 0, 0,
        GSSW_SEG_LEN * GSSW_VEC_WORDS, 6, bne))
    f.write(NOP)
    # Outer c++
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 1, 2, addi))
    f.write(NOP)
    push_c_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, push_pc - push_c_back_pc, 0, 1, 0, 2, 15, blt))
    f.write(NOP)
    push_done_target_pc = f.pc
    f.patch_imm0(push_done_wi, push_done_target_pc - push_done_branch_pc)

    # n++.   addi gr[1].lo += 1   |   NOP
    f.write(data_movement_instruction(gr_lo, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))
    f.write(NOP)

    # Jump back to top of outer loop.
    jump_back_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, node_pc - jump_back_pc, 0, 0, 0, 0, 0, jump))
    f.write(NOP)

    # Loop exit lands here — patch the forward bge offset now that we
    # know the target PC.
    loop_exit_pc = f.pc
    bge_exit_pc = bge_exit_wi // 2
    f.patch_imm0(bge_exit_wi, loop_exit_pc - bge_exit_pc)

    # === Section I (lowered): final reduce over best[] into gr[15] ===
    # Compute barrier: park compute at PC 0 (idle HALT) so any in-flight
    # writes from section H's CPC_PUSH_MAX (or earlier regions) drain
    # before set_8 resets reg[14:15]. Without this, stage 3c's longer
    # pre-section-I ISA prologue shifts the cycle parity enough that
    # a late CPC_PUSH_MAX writeback can clobber reg[14:15]'s LSB after
    # set_8, producing over-scores in multi-node cases (ISSUE-5).
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)
    f.write(NOP); f.write(NOP)

    # Reset vMax pair. reg[14]=0 | reg[15]=0 via paired set_8.
    f.write(data_movement_instruction(reg, 0, 0, 0, 14, 0, 0, 0, 0, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, set_8))
    # Reset j counter. si gr[3].lo = 0 | NOP
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))
    f.write(NOP)

    # Loop body (3 VLIW cycles per iter). Iterates 19 times (j 0..36 step 2).
    #   C0: mvd reg[20:21] = SPM[BEST_WOFF + gr_lo[3]]     | NOP
    #   C1: set_PC CPC_FINAL_MAX                           | addi gr[3].lo += 2
    #       -> compute fires MAX_EPU8 pair on NEXT cycle using the
    #          just-delivered reg[20:21].
    #   C2: bne (gr[3].lo != SEG_LEN*VEC_WORDS) back to C0 | NOP
    # gr_lo[3] (not gr[3]): gr[3].hi holds next_len of the last processed
    # node when we arrive here, and full-width gr[3] would fold that into
    # the SPM offset. ISSUE-2 (3b.0 audit block). Relies on the stage 3b.0
    # simulator extension for SPM-offset subregister decoding.
    final_pc = f.pc
    # C0
    f.write(data_movement_instruction(
        reg, SPM, 0, 0, 20, 0, 0, 0, GSSW_BEST_WOFF, spm_lo(3), mvd))
    f.write(NOP)
    # C1
    f.write(data_movement_instruction(
        0, 0, 0, 0, CPC_FINAL_MAX, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(
        gr_lo, gr, 0, 0, 3, 0, 0, 0, 2, 3, addi))
    # C2
    final_branch_pc = f.pc
    f.write(data_movement_instruction(
        0, 0, 0, 0, final_pc - final_branch_pc, 0, 0, 0,
        GSSW_SEG_LEN * GSSW_VEC_WORDS, 3, bne))
    f.write(NOP)

    # Tail: 8->4 max + horizontal reduce into gr[15].
    # Control set_PC hands off to the compute tail region; three NOP
    # pairs give compute time to fire the two tail instructions before
    # magic(102) below reads gr[15].
    f.write(data_movement_instruction(
        0, 0, 0, 0, CPC_FINAL_TAIL, 0, 0, 0, 0, 0, set_PC))
    f.write(NOP)
    f.write(NOP); f.write(NOP)   # compute: reg[20] = max_epu8(reg[14], reg[15])
    f.write(NOP); f.write(NOP)   # compute: gr[15]  = max_reduce(reg[20])

    # Print score (unchanged).
    f.write(NOP)
    f.write(write_magic(102))

    # Signal done.
    f.write(NOP)
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))

    # Halt.
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))


# ---------------------------------------------------------------------------
# PE 1-3 : trivial (signal done immediately, stay halted)
# ---------------------------------------------------------------------------
def pe_other_instruction(f):
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.write(NOP)
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))


def pe_instruction(pe_id):
    f = InstructionWriter(
        f"instructions/gssw/pe_{pe_id}_instruction.txt")
    if pe_id == 0:
        pe_0_instruction(f)
    else:
        pe_other_instruction(f)
    f.close()


if __name__ == '__main__':
    os.makedirs("instructions/gssw", exist_ok=True)
    gssw_main_instruction()
    gssw_compute_instructions()
    for i in range(4):
        pe_instruction(i)
    print("Generated instructions/gssw/ traces.")
