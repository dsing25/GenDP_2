#!/usr/bin/env python3
"""
GSSW instruction generator.

Stage 1 of the magic-101 -> ISA lowering: section A (prologue/init) is
emitted as real ISA on PE 0. The rest of the kernel (sections B..I) is
still delegated to a C++ "mini-magic" in pe.cpp (magic_id 103) that
assumes section A has already run.

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
  PC 1..K     : lowered section A
  PC K+1      : nop | magic(103)   - run sections B..I
  PC K+2      : nop | magic(102)   - print score
  PC K+3      : nop | si gr[10]=1  - signal done
  PC K+4      : halt | halt

PE 1-3 trace (unchanged):
  PC 0: halt | halt
  PC 1: nop  | si gr[10]=1  (idle PEs signal done immediately)
  PC 2: halt | halt
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import InstructionWriter, write_magic, \
    data_movement_instruction, compute_instruction
from opcodes import (gr, gr_hi, gr_lo, reg, SPM, halt, none, set_PC,
                     bne, si, mv, mvd, addi, shifti_r, set_8, add,
                     MULTIPLICATION, HALT, INVALID, COPY,
                     MAX_EPU8, MAX_REDUCE)

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
# Magic 101 hoists gr[11] = GSSW_ND_WORDS (78) as the multiplier for the
# per-node base computation. The inline comment in pe.cpp says "76" but
# the actual value written is 78; follow the code, not the comment.
GSSW_ND_MUL_WORDS = GSSW_ND_WORDS  # 78

# --- Compute trace region PCs (indexes into compute_instruction.txt) ---
# PC 0 is the idle HALT. Other PCs are assigned at generation time.
CPC_MUL         = 1   # gr[13] = gr[1].hi * gr[11]
CPC_FINAL_MAX   = 3   # reg[14:15] = max_epu8_pair(reg[14:15], reg[20:21])
CPC_FINAL_TAIL  = 5   # reg[20] = max(reg[14],reg[15]); gr[15] = max_reduce


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

    # Delegate sections B..H to magic(104); section I is lowered below.
    # Magic 104 clobbers gr[10] (section C writes it with hSeed base),
    # which would spuriously make the controller's gr[13] sync flag
    # true and end the simulation before lowered section I runs. Pair
    # the magic with si gr[10]=0 in slot 0 so the subsequent ctrl_write
    # phase resets the sync flag back to zero at end of this cycle.
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))
    f.write(write_magic(104))

    # === Section I (lowered): final reduce over best[] into gr[15] ===
    # Reset vMax pair. reg[14]=0 | reg[15]=0 via paired set_8.
    f.write(data_movement_instruction(reg, 0, 0, 0, 14, 0, 0, 0, 0, 0, set_8))
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, set_8))
    # Reset j counter. si gr[3].lo = 0 | NOP
    f.write(data_movement_instruction(gr_lo, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))
    f.write(NOP)

    # Loop body (3 VLIW cycles per iter). Iterates 19 times (j 0..36 step 2).
    #   C0: mvd reg[20:21] = SPM[BEST_WOFF + gr[3]]        | NOP
    #   C1: set_PC CPC_FINAL_MAX                           | addi gr[3].lo += 2
    #       -> compute fires MAX_EPU8 pair on NEXT cycle using the
    #          just-delivered reg[20:21].
    #   C2: bne (gr[3].lo != SEG_LEN*VEC_WORDS) back to C0 | NOP
    final_pc = f.pc
    # C0
    f.write(data_movement_instruction(
        reg, SPM, 0, 0, 20, 0, 0, 0, GSSW_BEST_WOFF, 3, mvd))
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
