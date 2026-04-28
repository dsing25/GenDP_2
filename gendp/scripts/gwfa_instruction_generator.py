import os
from utils import *
from opcodes import *

LAST_SPM_ADDR = 32767

# PING / PONG buffer SPM offsets (consumed by magics 8/14/15 and the
# lowered tile_load subroutine via gr[0]). Mirror sys_def.h:224-225.
GWFA_BUF0_BASE = 0
GWFA_BUF1_BASE = 1280

# PE code locations
PE_BUF0_COMPUTE = 1
PE_BUF0_SORT    = 5
PE_BUF1_COMPUTE = 9
PE_BUF1_SORT    = 13
PE_P2_BUF0      = 17
PE_P2_BUF1      = 21
PE_FIN0_A       = 25
PE_FIN0_B       = 29

# Magic IDs with mask encoding: (magic_id << 8) | mask
# mask bit 0 = buffer index (0=buf0, 1=buf1)
# mask bit 1 = FIN0 buffer index (0=FIN0_A, 2=FIN0_B)
MAGIC_8_BUF0  = 8
MAGIC_8_BUF1  = (8 << 8) | 1
MAGIC_9_BUF0  = 9
MAGIC_9_BUF1  = (9 << 8) | 1
MAGIC_11_BUF0 = 11
MAGIC_11_BUF1 = (11 << 8) | 1
MAGIC_13_BUF0 = 13
MAGIC_13_BUF1 = (13 << 8) | 1
MAGIC_14_BUF0 = 14
MAGIC_14_BUF1 = (14 << 8) | 1
MAGIC_15_BUF0 = 15
MAGIC_15_BUF1 = (15 << 8) | 1
# mask bit 1 = FIN0 buffer (0=FIN0_A, 2=FIN0_B)
MAGIC_15_BUF0_F0A = 15
MAGIC_15_BUF0_F0B = (15 << 8) | 2
MAGIC_15_BUF1_F0A = (15 << 8) | 1
MAGIC_15_BUF1_F0B = (15 << 8) | 3
MAGIC_18_F0A  = 18
MAGIC_18_F0B  = (18 << 8) | 2
MAGIC_19_F0A  = 19
MAGIC_19_F0B  = (19 << 8) | 2
MAGIC_20_F0A  = 20
MAGIC_20_F0B  = (20 << 8) | 2

# Sort phase magic IDs
MAGIC_34_BUF0 = 34
MAGIC_34_BUF1 = (34 << 8) | 1
MAGIC_19      = 19
MAGIC_24_BUF0 = 24
MAGIC_24_BUF1 = (24 << 8) | 1
MAGIC_25_BUF0 = 25
MAGIC_25_BUF1 = (25 << 8) | 1
MAGIC_32      = 32

# PE sort code locations
PE_SORT_BIN_COUNT_PING = 33
PE_SORT_BIN_COUNT_PONG = 37
PE_SORT_SCATTER_PING   = 41
PE_SORT_SCATTER_PONG   = 45

# PE magic IDs for sort
MAGIC_20_BUF0 = 20
MAGIC_20_BUF1 = (20 << 8) | 1
MAGIC_21_BUF0 = 21
MAGIC_21_BUF1 = (21 << 8) | 1

# Dedup phase magic IDs (ctrl)
MAGIC_29      = 29
MAGIC_30_BUF0 = 30
MAGIC_30_BUF1 = (30 << 8) | 1
MAGIC_31_BUF0 = 31
MAGIC_31_BUF1 = (31 << 8) | 1
MAGIC_32      = 32

# Merge phase magic IDs
MAGIC_28      = 28
MAGIC_33      = 33
MAGIC_35_BUF0 = 35
MAGIC_35_BUF1 = (35 << 8) | 1
MAGIC_36      = 36
MAGIC_37      = 37
MAGIC_38      = 38
MAGIC_39      = 39

# PE merge code locations
PE_MERGE_PING = 49
PE_MERGE_PONG = 53

# PE magic IDs for merge
MAGIC_22_BUF0 = 22
MAGIC_22_BUF1 = (22 << 8) | 1

# PE dedup code locations (after merge PCs)
PE_DEDUP_PING = 57
PE_DEDUP_PONG = 61

# PE magic IDs for dedup
MAGIC_23_BUF0 = 23
MAGIC_23_BUF1 = (23 << 8) | 1

# --- Paired-slot emission helpers ---
# The controller now consumes two file lines per PC (slot 0, slot 1).
# write_solo wraps a single-slot op as (NOP, op) so f.pc advances by 1 PC
# per logical instruction. write_paired_call / write_paired_ret emit the
# same call/ret in both slots, as the simulator's pairing checker requires.

def write_solo(f, instr):
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(instr)

def write_paired_call(f, target_pc):
    assert 0 <= target_pc <= 32767, f"call target {target_pc} out of range"
    call_instr = data_movement_instruction(0, 0, 0, 0, target_pc, 0, 0, 0, 0, 0, call)
    i0 = f.write_count
    f.write(call_instr)
    i1 = f.write_count
    f.write(call_instr)
    return i0, i1

def write_paired_ret(f):
    ret_instr = data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ret)
    f.write(ret_instr)
    f.write(ret_instr)

def _slot1(pc):
    """Slot-1 line index of write_solo at PC `pc` (real instr line)."""
    return 2 * pc + 1

def emit_tile_load_subroutine(f):
    """Lowered ISA implementation of former magic 7 (GWFA controller
    `tile_load`, mask=0 for PING / mask=1 for PONG). Copies a tile of A
    diagonals from MM directly into the per-PE SPM A-tile region,
    no S1c staging. PING/PONG selection is now caller-controlled
    via gr[0] = buf_base (= GWFA_BUF0_BASE or GWFA_BUF1_BASE).

    Live-in:
        gr[0]  = buf_base (caller sets via si gr[0] = GWFA_BUF*_BASE)
        gr[14] = cursor (global diag cursor across tiles)
        gr[15] = n_a (total A-diag count)
        gr[19] = s_a_off (MM base for A diags)
    Live-out:
        gr[0]                         = 0 (zero-base invariant restored)
        gr[14] += clamp(n_a - cursor, 0, 256)
        s1c[512..515]                 = per-PE tile_n
        SPM[pe_base + 1155]           = per-PE tile_n (always)
        SPM[pe_base + 1152..1153]     = 0 only on tile_n <= 0 path
        SPM[pe_base + A_TILE_OFF .. ] = new diag tile contents
    Contract amendment vs the plan's AC-4 clobber list: gr[0] is
        consumed by this subroutine. The plan's clobber list omitted
        gr[0] because the plan implicitly assumed buf_base would survive
        the call. It does not — gr[0] is zeroed at entry (after
        stashing buf_base in gr[23] via addi) and restored to 0 before
        return so the rest of the controller code can keep relying on
        the gr[0]=0 zero-base addressing invariant. Caller must
        `si gr[0] = GWFA_BUF*_BASE` before EACH paired call.
    Clobbers: gr[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 17, 23]
        Note vs the plan's AC-4 clobber list: gr[13] is REMOVED (it is
        the simulator-managed PE-sync flag — auto-written each
        controller cycle as the AND of all PE gr[10] values per
        pe_array.cpp:9926-9928 — and therefore unusable as a multi-PC
        scratch register inside the subroutine; the original C++
        magic-7 only got away with using gr[13] as scratch because the
        magic body executes atomically in one simulator cycle, BEFORE
        the AND-loop runs). gr[2] takes gr[13]'s scratch role; this
        is safe because magic 8 (the next magic on every cutover
        path) writes gr[2]=0 before reading it (pe_array.cpp:1480),
        and magic 8 always immediately follows the post-call
        barriers.
    Preserved: gr[12] (step counter); gr[2] is NO LONGER preserved
        (see clobber note above).

    Returns: subroutine entry PC (paired-call target).
    """
    # --- Constants ---
    S1C_TILE_N = 512
    META_OFF = 1152
    META_TILE_N_OFF = META_OFF + 3   # = 1155
    DIAGS_PER_PE = 64
    SPM_BANK_GROUP_SIZE_LOCAL = 8192
    PE_SRC = [1, 5, 8, 11]
    PE_DST = [3, 6, 9, 16]
    # CTR is the multi-PC scratch register used as the Phase-2 setup
    # tmp, the Peel-A loop counter, the Peel-B "any-fired" flag, and
    # the main-loop counter. Was originally gr[13] in the C++ magic
    # body, but gr[13] is the simulator-managed PE-sync AND-flag
    # (auto-written every controller cycle), so we use gr[2] instead.
    CTR = 2
    PE_END = [4, 7, 10, 17]

    entry_pc = f.pc

    # Entry: stash buf_base in gr[23], zero gr[0] for zero-base addressing.
    # mv with src=gr requires gr[reg_1]=0 to read a literal gr index (the
    # encoding is source_addr = imm_1 + gr[reg_1], so reg_1=0 + gr[0]=0
    # yields source_addr = imm_1). At entry gr[0] = buf_base != 0, so
    # we use addi (which directly takes rs2 = reg_1) to capture buf_base
    # before zeroing gr[0]. After this, every literal gr[N] read uses
    # imm_1=N, reg_1=0.
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, 0, 0, addi))                            # gr[23] = gr[0] + 0 (buf_base)
    # mul writes rd directly via set_output_dest (no source_addr arithmetic),
    # so this works even when gr[0]=buf_base != 0 at entry. `si gr[0]=0`
    # would compute dest_addr = 0 + gr[0] = buf_base and write gr[buf_base]
    # instead of gr[0] — which crashes for BUF1 (buf_base=1280, out of range).
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, mul))                              # gr[0] = 0 * gr[0] = 0 (zero-base)

    # === Phase 1: per-PE tile_n -> s1c[512+pe] + SPM meta + zero-guard ===
    for pe in range(4):
        pe_off = pe * SPM_BANK_GROUP_SIZE_LOCAL
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, 10, 0, 0, 0, 15, 14, sub))                       # gr[10] = gr[15] - gr[14]
        if pe > 0:
            write_solo(f, data_movement_instruction(gr, gr, 0, 0, 10, 0, 0, 0, pe * DIAGS_PER_PE, 10, subi))   # gr[10] -= pe*64
        # Upper clamp: bge 64,gr[10] -> skip si gr[10]=64
        br_skip_hi = f.pc
        write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, DIAGS_PER_PE, 10, bge))                # bge 64,gr[10] -> +2 (patched)
        write_solo(f, data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, DIAGS_PER_PE, 0, si))                # gr[10] = 64
        f.patch_imm0(_slot1(br_skip_hi), f.pc - br_skip_hi)
        # Lower clamp: blt 0,gr[10] -> skip si gr[10]=0
        br_skip_lo = f.pc
        write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 10, blt))                           # blt 0,gr[10] -> +2 (patched)
        write_solo(f, data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                           # gr[10] = 0
        f.patch_imm0(_slot1(br_skip_lo), f.pc - br_skip_lo)
        write_solo(f, data_movement_instruction(s1c, gr, 0, 0, S1C_TILE_N + pe, 0, 0, 0, 10, 0, mv))           # s1c[512+pe] = gr[10]
        write_solo(f, data_movement_instruction(SPM, gr, 0, 0, pe_off + META_TILE_N_OFF, 23, 0, 0, 10, 0, mv)) # SPM[pe_off+1155+buf_base] = gr[10]
        # Zero-guard: bne 0,gr[10] -> skip both si zero-clears
        br_skip_zero = f.pc
        write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 10, bne))                           # bne 0,gr[10] -> +3 (patched)
        write_solo(f, data_movement_instruction(SPM, 0, 0, 0, pe_off + META_OFF, 23, 0, 0, 0, 0, si))          # SPM[pe_off+1152+buf_base] = 0
        write_solo(f, data_movement_instruction(SPM, 0, 0, 0, pe_off + META_OFF + 1, 23, 0, 0, 0, 0, si))      # SPM[pe_off+1153+buf_base] = 0
        f.patch_imm0(_slot1(br_skip_zero), f.pc - br_skip_zero)

    # === Phase 2 setup: per-PE src / dst / end pointers ===
    for pe in range(4):
        src_r = PE_SRC[pe]
        dst_r = PE_DST[pe]
        end_r = PE_END[pe]
        pe_off = pe * SPM_BANK_GROUP_SIZE_LOCAL
        if pe == 0:
            write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 14, 0, mv))                    # gr[CTR] = gr[14]
        else:
            write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, pe * DIAGS_PER_PE, 14, addi))  # gr[CTR] = gr[14] + pe*64
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, CTR, CTR, add))                    # gr[CTR] *= 2
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, src_r, 0, 0, 0, CTR, 19, add))                   # gr[src] = gr[CTR] + gr[19]
        write_solo(f, data_movement_instruction(gr, s1c, 0, 0, CTR, 0, 0, 0, S1C_TILE_N + pe, 0, mv))          # gr[CTR] = s1c[512+pe]
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, end_r, 0, 0, 0, CTR, CTR, add))                  # gr[end] = 2 * tile_n
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, end_r, 0, 0, 0, src_r, end_r, add))              # gr[end] = gr[src] + gr[end]
        # Use addi for all PE blocks: addi reads rs2=reg_1 directly (no source_addr/gr[0] dep).
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, dst_r, 0, 0, 0, pe_off, 23, addi))               # gr[dst] = gr[23] + pe*8192

    # === Peel A: per-PE handle (tile_n % 4) remainder via mvd MM->SPM (2 words) ===
    for pe in range(4):
        src_r = PE_SRC[pe]
        dst_r = PE_DST[pe]
        write_solo(f, data_movement_instruction(gr, s1c, 0, 0, CTR, 0, 0, 0, S1C_TILE_N + pe, 0, mv))          # gr[CTR] = s1c[512+pe]
        write_solo(f, data_movement_instruction(gr, 0, 0, 0, CTR, 0, 0, 0, 3, CTR, ANDI))                      # gr[CTR] = gr[CTR] & 3
        loop_top = f.pc
        br_done = f.pc
        write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, CTR, bge))                          # bge 0,gr[CTR] -> done (patched)
        write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 1, CTR, subi))                     # gr[CTR] -= 1
        write_solo(f, data_movement_instruction(SPM, MM, 0, 1, 0, dst_r, 0, 1, 0, src_r, mvd))                 # mvd SPM[gr[dst]++2] = MM[gr[src]++2]
        write_solo(f, data_movement_instruction(0, 0, 0, 0, loop_top - f.pc, 0, 0, 0, 0, 0, jump))             # jump loop_top
        f.patch_imm0(_slot1(br_done), f.pc - br_done)

    # === Peel-B prep: gr[23] = min(end[pe] - src[pe]) ; subtract from each end[pe] ===
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, 4, 1, sub))                             # gr[23] = gr[4] - gr[1] (PE0 resid)
    # PE1
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 7, 5, sub))                            # gr[CTR] = gr[7] - gr[5]
    br_pe1_skip = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, CTR, 23, bge))                             # bge gr[CTR],gr[23] -> +2 (patched)
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, CTR, 0, mv))                            # gr[23] = gr[CTR]
    f.patch_imm0(_slot1(br_pe1_skip), f.pc - br_pe1_skip)
    # PE2
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 10, 8, sub))                           # gr[CTR] = gr[10] - gr[8]
    br_pe2_skip = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, CTR, 23, bge))                             # bge gr[CTR],gr[23] -> +2 (patched)
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, CTR, 0, mv))                            # gr[23] = gr[CTR]
    f.patch_imm0(_slot1(br_pe2_skip), f.pc - br_pe2_skip)
    # PE3
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 17, 11, sub))                          # gr[CTR] = gr[17] - gr[11]
    br_pe3_skip = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, CTR, 23, bge))                             # bge gr[CTR],gr[23] -> +2 (patched)
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, CTR, 0, mv))                            # gr[23] = gr[CTR]
    f.patch_imm0(_slot1(br_pe3_skip), f.pc - br_pe3_skip)
    # end[pe] -= min_resid
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 4, 23, sub))                             # gr[4]  -= gr[23]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 7, 23, sub))                             # gr[7]  -= gr[23]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 10, 0, 0, 0, 10, 23, sub))                           # gr[10] -= gr[23]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 17, 0, 0, 0, 17, 23, sub))                           # gr[17] -= gr[23]

    # === Peel-B loop: serial 1-mvdq-per-PE-per-iter; gr[CTR] = "any-fired" flag ===
    peelb_outer = f.pc
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, CTR, 0, 0, 0, 0, 0, si))                              # gr[CTR] = 0
    # PE0
    br_skip_pe0 = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 1, 4, bge))                                # bge gr[1],gr[4] -> skip (patched)
    write_solo(f, data_movement_instruction(SPM, MM, 0, 1, 0, 3, 0, 1, 0, 1, mvdq))                            # mvdq SPM[gr[3]++8] = MM[gr[1]++8]
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, CTR, 0, 0, 0, 1, 0, si))                              # gr[CTR] = 1
    f.patch_imm0(_slot1(br_skip_pe0), f.pc - br_skip_pe0)
    # PE1
    br_skip_pe1 = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 5, 7, bge))                                # bge gr[5],gr[7] -> skip (patched)
    write_solo(f, data_movement_instruction(SPM, MM, 0, 1, 0, 6, 0, 1, 0, 5, mvdq))                            # mvdq SPM[gr[6]++8] = MM[gr[5]++8]
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, CTR, 0, 0, 0, 1, 0, si))                              # gr[CTR] = 1
    f.patch_imm0(_slot1(br_skip_pe1), f.pc - br_skip_pe1)
    # PE2
    br_skip_pe2 = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 8, 10, bge))                               # bge gr[8],gr[10] -> skip (patched)
    write_solo(f, data_movement_instruction(SPM, MM, 0, 1, 0, 9, 0, 1, 0, 8, mvdq))                            # mvdq SPM[gr[9]++8] = MM[gr[8]++8]
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, CTR, 0, 0, 0, 1, 0, si))                              # gr[CTR] = 1
    f.patch_imm0(_slot1(br_skip_pe2), f.pc - br_skip_pe2)
    # PE3
    br_skip_pe3 = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 11, 17, bge))                              # bge gr[11],gr[17] -> skip (patched)
    write_solo(f, data_movement_instruction(SPM, MM, 0, 1, 0, 16, 0, 1, 0, 11, mvdq))                          # mvdq SPM[gr[16]++8] = MM[gr[11]++8]
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, CTR, 0, 0, 0, 1, 0, si))                              # gr[CTR] = 1
    f.patch_imm0(_slot1(br_skip_pe3), f.pc - br_skip_pe3)
    # if any fired, repeat outer
    write_solo(f, data_movement_instruction(0, 0, 0, 0, peelb_outer - f.pc, 0, 0, 0, 0, CTR, bne))             # bne 0,gr[CTR] -> peelb_outer

    # === Convert PE1-3 cursors to deltas relative to PE0 ; n_iters = min_resid >> 3 ===
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 5, 1, sub))                              # gr[5]  = gr[5]  - gr[1]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 6, 3, sub))                              # gr[6]  = gr[6]  - gr[3]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 8, 1, sub))                              # gr[8]  = gr[8]  - gr[1]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 9, 3, sub))                              # gr[9]  = gr[9]  - gr[3]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 11, 1, sub))                            # gr[11] = gr[11] - gr[1]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 16, 0, 0, 0, 16, 3, sub))                            # gr[16] = gr[16] - gr[3]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 3, 23, shifti_r))                      # gr[CTR] = gr[23] >> 3

    # === Main loop: 4 concurrent PE mvdq's per iter; PE3 carries auto-inc on gr[3]/gr[1] ===
    main_top = f.pc
    br_main_done = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, CTR, bge))                              # bge 0,gr[CTR] -> done (patched)
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, CTR, 0, 0, 0, 1, CTR, subi))                         # gr[CTR] -= 1
    write_solo(f, data_movement_instruction(SPM, MM, 0, 0, 0, 3, 0, 0, 0, 1, mvdq))                            # PE0: SPM[gr[3]] = MM[gr[1]]
    write_solo(f, data_movement_instruction(SPM, MM, 1, 0, 6, 3, 1, 0, 5, 1, mvdq))                            # PE1: SPM[gr[3]+gr[6]] = MM[gr[1]+gr[5]]
    write_solo(f, data_movement_instruction(SPM, MM, 1, 0, 9, 3, 1, 0, 8, 1, mvdq))                            # PE2: SPM[gr[3]+gr[9]] = MM[gr[1]+gr[8]]
    write_solo(f, data_movement_instruction(SPM, MM, 1, 1, 16, 3, 1, 1, 11, 1, mvdq))                          # PE3: SPM[gr[3]+gr[16]] = MM[gr[1]+gr[11]]; gr[3]+=8; gr[1]+=8
    write_solo(f, data_movement_instruction(0, 0, 0, 0, main_top - f.pc, 0, 0, 0, 0, 0, jump))                 # jump main_top
    f.patch_imm0(_slot1(br_main_done), f.pc - br_main_done)

    # === Cursor advance: gr[14] += clamp(n_a - cursor, 0, 256) ===
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 15, 14, sub))                            # gr[7] = gr[15] - gr[14]
    br_clamp_skip = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 256, 7, bge))                              # bge 256,gr[7] -> +2 (patched)
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, 256, 0, si))                              # gr[7] = 256
    f.patch_imm0(_slot1(br_clamp_skip), f.pc - br_clamp_skip)
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 14, 7, add))                            # gr[14] = gr[14] + gr[7]

    # Explicit gr[0]=0 restore before return, documenting the contract:
    # gr[0] is consumed by the subroutine; caller's buf_base does NOT
    # survive the call. The rest of the controller code relies on the
    # gr[0]=0 invariant for s1c / SPM zero-base addressing.
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, 0, 0, si))                                # gr[0] = 0 (restore zero-base invariant)
    write_paired_ret(f)
    return entry_pc

def emit_merge_loop(f):
    """Emit a PE-parallel merge loop. Caller must set gr[6]=loop bound
    before calling. Uses PE_MERGE_PING/PONG, MAGIC_33 (reload A/B input
    buffers from MM, overlapped with PE compute), MAGIC_35 (writeback).
    Returns PC after the loop."""
    br_skip = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 6, beq))
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_MERGE_PING, 0, 0, 0, 0, 0, set_PC))
    br_epilA_pro = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))
    ss_pong = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                     # spin (PE wrote OUT_PING)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_MERGE_PONG, 0, 0, 0, 0, 0, set_PC))       # PE starts (writes OUT_PONG)
    write_solo(f, write_magic(MAGIC_35_BUF0))                                                          # writeback OUT_PING (overlapped)
    write_solo(f, write_magic(MAGIC_33))                                                               # reload tiles (overlapped)
    br_epilB = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                     # spin (PE wrote OUT_PONG)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_MERGE_PING, 0, 0, 0, 0, 0, set_PC))       # PE starts (writes OUT_PING)
    write_solo(f, write_magic(MAGIC_35_BUF1))                                                          # writeback OUT_PONG (overlapped)
    write_solo(f, write_magic(MAGIC_33))                                                               # reload tiles (overlapped)
    br_epilA_ss = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))
    write_solo(f, data_movement_instruction(0, 0, 0, 0, ss_pong - f.pc, 0, 0, 0, 0, 0, jump))
    epilB = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                     # spin last PONG
    write_solo(f, write_magic(MAGIC_35_BUF1))                                                          # writeback last PONG
    br_done_B = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))
    epilA = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                     # spin last PING
    write_solo(f, write_magic(MAGIC_35_BUF0))                                                          # writeback last PING
    done = f.pc
    f.patch_imm0(_slot1(br_skip), done - br_skip)
    f.patch_imm0(_slot1(br_epilA_pro), epilA - br_epilA_pro)
    f.patch_imm0(_slot1(br_epilB), epilB - br_epilB)
    f.patch_imm0(_slot1(br_epilA_ss), epilA - br_epilA_ss)
    f.patch_imm0(_slot1(br_done_B), done - br_done_B)

def emit_sort_loop(f):
    """Emit one radix sort pass loop (42 instructions). Position-independent.
    Caller must set gr[1]=0 before calling. Uses gr[1..7,24], s1c[], SPM."""
    # --- BIN COUNT PHASE ---
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # +0: gr[2]=0 (cursor=0)
    write_solo(f, write_magic(MAGIC_34_BUF0))                                                          # +1: load tile→PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PING, 0, 0, 0, 0, 0, set_PC)) # +2: set_PC bin count PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 12, 0, 1, 0, 2, 6, bge))                      # +3: bge cursor>=nape → +12 (+15)
    write_solo(f, write_magic(MAGIC_34_BUF1))                                                          # +4: SS_PONG
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +5: spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PONG, 0, 0, 0, 0, 0, set_PC)) # +6: set_PC bin count PONG
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 6, 0, 1, 0, 2, 6, bge))                       # +7: bge → +6 (+13)
    write_solo(f, write_magic(MAGIC_34_BUF0))                                                          # +8: SS_PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +9: spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PING, 0, 0, 0, 0, 0, set_PC)) # +10: set_PC bin count PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 4, 0, 1, 0, 2, 6, bge))                       # +11: bge → +4 (+15)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -8, 0, 0, 0, 0, 0, jump))                     # +12: jump -8 (+4: SS_PONG)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +13: EPIL_B: spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                      # +14: jump +2 (+16)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +15: EPIL_A: spin
    write_solo(f, write_magic(MAGIC_19))                                                                # +16: prefix sum
    # --- SCATTER PHASE ---
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # +17: gr[2]=0
    write_solo(f, write_magic(MAGIC_24_BUF0))                                                          # +18: load tile→PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PING, 0, 0, 0, 0, 0, set_PC)) # +19: set_PC scatter PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 15, 0, 1, 0, 2, 6, bge))                      # +20: bge → +15 (+35)
    write_solo(f, write_magic(MAGIC_24_BUF1))                                                          # +21: SS_PONG
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +22: spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PONG, 0, 0, 0, 0, 0, set_PC)) # +23: set_PC scatter PONG
    write_solo(f, write_magic(MAGIC_25_BUF0))                                                          # +24: writeback PING (overlapped)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 2, 6, bge))                       # +25: bge → +7 (+32)
    write_solo(f, write_magic(MAGIC_24_BUF0))                                                          # +26: SS_PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +27: spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PING, 0, 0, 0, 0, 0, set_PC)) # +28: set_PC scatter PING
    write_solo(f, write_magic(MAGIC_25_BUF1))                                                          # +29: writeback PONG (overlapped)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 5, 0, 1, 0, 2, 6, bge))                       # +30: bge → +5 (+35)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -10, 0, 0, 0, 0, 0, jump))                    # +31: jump -10 (+21: SS_PONG)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +32: SEPIL_B: spin
    write_solo(f, write_magic(MAGIC_25_BUF1))                                                          # +33: writeback PONG
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, 0, 0, jump))                      # +34: jump +3 (+37)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                      # +35: SEPIL_A: spin
    write_solo(f, write_magic(MAGIC_25_BUF0))                                                          # +36: writeback PING
    # --- PASS FOOTER ---
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 3, 0, mv))                      # +37: gr[7]=gr[3] (swap)
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 4, 0, mv))                      # +38: gr[3]=gr[4]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 7, 0, mv))                      # +39: gr[4]=gr[7]
    write_solo(f, data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))                    # +40: gr[1]++
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -41, 0, 0, 0, 8, 1, bne))                     # +41: bne 8!=gr[1] → -41 (+0)

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    # Forward-reference call sites into the lowered tile_load subroutine.
    # Each entry is (slot0_idx, slot1_idx); both slots get patched with the
    # subroutine's entry PC after the subroutine is emitted at end-of-body.
    tile_load_call_patches = []
    write_solo(f, write_magic(1))                                                                        # PC 0: init
    write_solo(f, data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))          # PC 1: SPM[32767]=0
    # === STEP LOOP ===
    write_solo(f, write_magic(4))                                                                        # PC 2: begin_step
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                       # PC 3: gr[14]=0 (cursor)
    # === PHASE 1 PROLOGUE ===
    # Prime buf0 serially (nothing to overlap on first iter), then
    # prime buf1 inside the compute-overlap window so the SS loop
    # can assume both buffers are always ready.
    # tile_load buf0 (former magic 7 mask=0): caller sets gr[0]=buf_base then paired call
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, GWFA_BUF0_BASE, 0, si))           # gr[0] = GWFA_BUF0_BASE
    tile_load_call_patches.append(write_paired_call(f, 0))                                              # paired call → tile_load (patched at end)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: tile_load writes SPM via MM
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: magic8 reads those SPM values
    write_solo(f, write_magic(MAGIC_8_BUF0))                                                             # load_seq_info buf0
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 6: set_PC buf0 compute
    # tile_load buf1 (former magic 7 mask=1): caller sets gr[0]=buf_base then paired call
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, GWFA_BUF1_BASE, 0, si))           # gr[0] = GWFA_BUF1_BASE
    tile_load_call_patches.append(write_paired_call(f, 0))                                              # paired call → tile_load (patched at end)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: tile_load→magic8 dependency
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))
    write_solo(f, write_magic(MAGIC_8_BUF1))                                                             # load_seq_info buf1 ← overlaps compute
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 9: spin gr[13]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 10: set_PC buf0 sort
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 11: spin gr[13] (ctrl idle)
    br_pro_exit = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 14, 15, bge))                      # PC 12: bge cursor>=n_a → FINALIZE_B1 (patched)
    # === PHASE 1 STEADY STATE: buf1 half ===
    # buf1 already primed. During buf1 compute, overlap: writeback
    # prev buf0 output, then load NEXT buf0 input.
    ss_buf1 = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF1_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 13: set_PC buf1 compute
    write_solo(f, write_magic(MAGIC_9_BUF0))                                                             # PC 14: writeback buf0 ← overlap
    # tile_load NEXT buf0 (former magic 7 mask=0, SS): caller sets gr[0]=buf_base then paired call
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, GWFA_BUF0_BASE, 0, si))           # gr[0] = GWFA_BUF0_BASE
    tile_load_call_patches.append(write_paired_call(f, 0))                                              # paired call → tile_load (patched at end)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: tile_load→magic8 dependency
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))
    write_solo(f, write_magic(MAGIC_8_BUF0))                                                             # load_seq_info NEXT buf0 ← overlap
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 17: spin gr[13]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF1_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 18: set_PC buf1 sort
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 19: spin gr[13] (ctrl idle)
    br_ss_b1_exit = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 14, 15, bge))                      # PC 20: bge cursor>=n_a → FINALIZE_B0 (patched)
    # === PHASE 1 STEADY STATE: buf0 half ===
    # buf0 primed by previous buf1 half's overlap. During buf0
    # compute, overlap: writeback prev buf1 output, then load NEXT buf1.
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 21: set_PC buf0 compute
    write_solo(f, write_magic(MAGIC_9_BUF1))                                                             # PC 22: writeback buf1 ← overlap
    # tile_load NEXT buf1 (former magic 7 mask=1, SS): caller sets gr[0]=buf_base then paired call
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, GWFA_BUF1_BASE, 0, si))           # gr[0] = GWFA_BUF1_BASE
    tile_load_call_patches.append(write_paired_call(f, 0))                                              # paired call → tile_load (patched at end)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: tile_load→magic8 dependency
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))
    write_solo(f, write_magic(MAGIC_8_BUF1))                                                             # load_seq_info NEXT buf1 ← overlap
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 25: spin gr[13]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 26: set_PC buf0 sort
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 27: spin gr[13] (ctrl idle)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, ss_buf1 - f.pc, 0, 1, 0, 14, 15, blt))         # PC 28: blt cursor<n_a → SS buf1
    # fallthrough: cursor >= n_a → FINALIZE_B1 (compute pre-loaded buf1)
    # === FINALIZE_B1: compute pre-loaded buf1, writeback both ===
    finalize_b1 = f.pc
    f.patch_imm0(_slot1(br_pro_exit), finalize_b1 - br_pro_exit)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF1_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # setPC buf1 compute
    write_solo(f, write_magic(MAGIC_9_BUF0))                                                             # m9_b0 [overlap: writeback prev buf0]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF1_SORT, 0, 0, 0, 0, 0, set_PC))          # setPC buf1 sort
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_9_BUF1))                                                             # m9_b1 writeback buf1
    br_skip_fb0 = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))                       # jump → FIFO_FLUSH (patched)
    # === FINALIZE_B0: compute pre-loaded buf0, writeback both ===
    finalize_b0 = f.pc
    f.patch_imm0(_slot1(br_ss_b1_exit), finalize_b0 - br_ss_b1_exit)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # setPC buf0 compute
    write_solo(f, write_magic(MAGIC_9_BUF1))                                                             # m9_b1 [overlap: writeback prev buf1]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # setPC buf0 sort
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_9_BUF0))                                                             # m9_b0 writeback buf0
    # fallthrough to FIFO_FLUSH
    f.patch_imm0(_slot1(br_skip_fb0), f.pc - br_skip_fb0)
    # === FIFO FLUSH (guarded by gr[2] from magic 9) ===
    br_fifo_skip = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → save n_phase1 (patched)
    write_solo(f, data_movement_instruction(gr, fifo[0], 0, 0, 3, 0, 0, 0, 0, 0, mv))                  # PC 31: gr[3]=fifo[0]
    write_solo(f, data_movement_instruction(gr, fifo[1], 0, 0, 4, 0, 0, 0, 0, 0, mv))                  # PC 32: gr[4]=fifo[1]
    write_solo(f, write_magic(12))                                                                       # PC 33: flush to s_B_a
    # fallthrough
    save_n_phase1 = f.pc
    write_solo(f, data_movement_instruction(s1c, gr, 0, 0, 151, 0, 0, 0, 24, 0, mv))                   # s1c[151]=gr[24] (save n_phase1 diags)
    f.patch_imm0(_slot1(br_fifo_skip), save_n_phase1 - br_fifo_skip)
    # === PHASE 2 (overlapped: magic18+magic15 during PE_P2, magic14 during PE_FIN0) ===
    # --- Prologue: load both buffers, compute BUF1 to seed HALF_A ---
    prologue_start = f.pc
    write_solo(f, write_magic(MAGIC_14_BUF0))                                                            # load first tiles
    br_p2exit = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → P2_EXIT
    write_solo(f, write_magic(MAGIC_14_BUF1))                                                            # load second tiles
    br_single = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → SINGLE
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_P2_BUF1, 0, 0, 0, 0, 0, set_PC))            # PE_P2_BUF1
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # drain check
    br_drain_pro = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                        # bne → DRAIN_EXIT
    # --- HALF_A: PE_P2_BUF0 || magic18+magic15, PE_FIN0_A || magic14 ---
    half_a = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))            # set_PC PE_P2_BUF0
    write_solo(f, write_magic(MAGIC_18_F0B))                                                             # magic18 FIN0_B [OVERLAP]
    write_solo(f, write_magic(MAGIC_15_BUF1_F0A))                                                        # magic15 BUF1→FIN0_A [OVERLAP]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin PE_P2
    write_solo(f, data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # drain check
    br_drain_ha = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                        # bne → DRAIN_EXIT
    # Multipass intermediate passes (if any) — serial
    br_skip_mp_a = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → skip_mp
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_18_F0A))                                                             # magic18 writeback
    write_solo(f, write_magic(MAGIC_20_F0A))                                                             # magic20 load next, sets gr[2]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ: m20 MM loads → next m18
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ seam (2x)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -6, 0, 0, 0, 0, 2, bne))                       # bne gr[2]!=0 → loop (-6)
    # Final/only FIN0 pass — overlapped with magic14
    f.patch_imm0(_slot1(br_skip_mp_a), f.pc - br_skip_mp_a)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_A
    write_solo(f, write_magic(MAGIC_14_BUF1))                                                            # magic14 BUF1 [OVERLAP]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin PE_FIN0
    br_drainA = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → DRAIN_AFTER_A
    # --- HALF_B: PE_P2_BUF1 || magic18+magic15, PE_FIN0_B || magic14 ---
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_P2_BUF1, 0, 0, 0, 0, 0, set_PC))            # set_PC PE_P2_BUF1
    write_solo(f, write_magic(MAGIC_18_F0A))                                                             # magic18 FIN0_A [OVERLAP]
    write_solo(f, write_magic(MAGIC_15_BUF0_F0B))                                                        # magic15 BUF0→FIN0_B [OVERLAP]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin PE_P2
    write_solo(f, data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # drain check
    br_drain_hb = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                        # bne → DRAIN_EXIT
    # Multipass intermediate passes (if any) — serial
    br_skip_mp_b = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → skip_mp
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_18_F0B))                                                             # magic18 writeback
    write_solo(f, write_magic(MAGIC_20_F0B))                                                             # magic20 load next, sets gr[2]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ: m20 MM loads → next m18
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ seam (2x)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -6, 0, 0, 0, 0, 2, bne))                       # bne gr[2]!=0 → loop (-6)
    # Final/only FIN0 pass — overlapped with magic14
    f.patch_imm0(_slot1(br_skip_mp_b), f.pc - br_skip_mp_b)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_B
    write_solo(f, write_magic(MAGIC_14_BUF0))                                                            # magic14 BUF0 [OVERLAP]
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin PE_FIN0
    br_drainB = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → DRAIN_AFTER_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, half_a - f.pc, 0, 0, 0, 0, 0, jump))           # jump → HALF_A
    # --- DRAIN_AFTER_A: flush deferred FIN0_A, writeback P2_BUF0 → FIN0_B drain ---
    f.patch_imm0(_slot1(br_drainA), f.pc - br_drainA)
    write_solo(f, write_magic(MAGIC_18_F0A))                                                             # magic18 FIN0_A (flush deferred)
    write_solo(f, write_magic(MAGIC_15_BUF0_F0B))                                                        # magic15 BUF0→FIN0_B
    # SHARED_FIN0_B_DRAIN (multipass → re-check via PROLOGUE)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_18_F0B))                                                             # magic18 FIN0_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, prologue_start - f.pc, 0, 0, 0, 0, 2, beq))    # beq gr[2]==0 → PROLOGUE
    write_solo(f, write_magic(MAGIC_20_F0B))                                                             # magic20 FIN0_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ: m20 → m18
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ seam (2x)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_18_F0B))                                                             # magic18 FIN0_B
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -7, 0, 0, 0, 0, 0, jump))                      # jump -7
    # --- DRAIN_AFTER_B: flush deferred FIN0_B, writeback P2_BUF1 → FIN0_A drain ---
    f.patch_imm0(_slot1(br_drainB), f.pc - br_drainB)
    write_solo(f, write_magic(MAGIC_18_F0B))                                                             # magic18 FIN0_B (flush deferred)
    write_solo(f, write_magic(MAGIC_15_BUF1_F0A))                                                        # magic15 BUF1→FIN0_A
    # SHARED_FIN0_A_DRAIN (multipass → re-check via PROLOGUE)
    shared_fin0a_drain = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_18_F0A))                                                             # magic18 FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, prologue_start - f.pc, 0, 0, 0, 0, 2, beq))    # beq gr[2]==0 → PROLOGUE
    write_solo(f, write_magic(MAGIC_20_F0A))                                                             # magic20 FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ: m20 → m18
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # waitLSQ seam (2x)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))             # set_PC PE_FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, write_magic(MAGIC_18_F0A))                                                             # magic18 FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, -7, 0, 0, 0, 0, 0, jump))                      # jump -7
    # --- P2_SINGLE_BUF0: only BUF0 loaded, no overlap ---
    f.patch_imm0(_slot1(br_single), f.pc - br_single)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))            # set_PC PE_P2_BUF0
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    write_solo(f, data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # drain check
    br_drain_sg = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                        # bne → DRAIN_EXIT
    write_solo(f, write_magic(MAGIC_15_BUF0_F0A))                                                        # magic15 BUF0→FIN0_A
    write_solo(f, data_movement_instruction(0, 0, 0, 0, shared_fin0a_drain - f.pc, 0, 0, 0, 0, 0, jump))  # jump → FIN0_A_DRAIN
    # === POST-PHASE 2: DIAG SORT → DIAG MERGE → INTV SORT → MERGE → DEDUP ===
    p2_exit = f.pc
    f.patch_imm0(_slot1(br_p2exit), p2_exit - br_p2exit)
    # Diag sort setup (magic 16 now sets up diag sort, not intv sort)
    write_solo(f, write_magic(16))                                                                        # sync+setup diag sort
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                         # gr[1]=0
    emit_sort_loop(f)                                                                                  # sort loop 1: diag tail
    # === DIAG MERGE: PE-parallel merge ===
    write_solo(f, write_magic(MAGIC_28))                                                                  # diag split + load
    emit_merge_loop(f)
    write_solo(f, write_magic(MAGIC_36))                                                                  # diag merge finalize
    # === INTV SORT: setup + radix sort ===
    write_solo(f, write_magic(MAGIC_39))                                                                  # intv sort setup
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                         # gr[1]=0
    emit_sort_loop(f)                                                                                  # sort loop 2: intv
    # === INTV MERGE: PE-parallel (sorted new + old) ===
    write_solo(f, write_magic(MAGIC_37))                                                                  # intv merge split + load
    emit_merge_loop(f)
    write_solo(f, write_magic(MAGIC_38))                                                                  # intv merge finalize
    # Dedup (tiled with overlapped writeback+reload)
    # Matches old dedup/merge ISA pattern.
    write_solo(f, write_magic(MAGIC_29))                                                                  # dedup split + initial tile load
    write_solo(f, data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                         # gr[2]=0
    # --- Prologue: load + first PE call ---
    write_solo(f, write_magic(MAGIC_30_BUF0))                                                             # reload (loads BUF1 from remaining data)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PING, 0, 0, 0, 0, 0, set_PC))
    br_exit_ping_pro = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))                         # → EXIT_PING (patch)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop pair
    # --- SS_PONG ---
    ss_pong = f.pc
    write_solo(f, write_magic(MAGIC_30_BUF0))                                                             # reload
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                        # spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PONG, 0, 0, 0, 0, 0, set_PC))          # PE starts OUT1
    write_solo(f, write_magic(MAGIC_31_BUF0))                                                             # writeback OUT0 (overlapped)
    br_exit_pong = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))                         # → EXIT_PONG (patch)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop pair
    # --- SS_PING ---
    write_solo(f, write_magic(MAGIC_30_BUF0))                                                             # reload
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                        # spin
    write_solo(f, data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PING, 0, 0, 0, 0, 0, set_PC))          # PE starts OUT0
    write_solo(f, write_magic(MAGIC_31_BUF1))                                                             # writeback OUT1 (overlapped)
    br_exit_ping_ss = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))                         # → EXIT_PING (patch)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop pair
    write_solo(f, data_movement_instruction(0, 0, 0, 0, ss_pong - f.pc, 0, 0, 0, 0, 0, jump))          # → SS_PONG
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop pair
    # --- DEDUP_EXIT_PONG ---
    dedup_exit_pong = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                        # spin
    write_solo(f, write_magic(MAGIC_31_BUF1))                                                             # writeback last PONG
    br_done_from_pong = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))                        # → DONE (patch)
    # --- DEDUP_EXIT_PING ---
    dedup_exit_ping = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                        # spin
    write_solo(f, write_magic(MAGIC_31_BUF0))                                                             # writeback last PING
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop pair
    # fallthrough to DONE
    dedup_done = f.pc
    write_solo(f, write_magic(MAGIC_32))                                                                  # gather + finalize
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                        # nop pair
    # Patch dedup branches
    f.patch_imm0(_slot1(br_exit_ping_pro), dedup_exit_ping - br_exit_ping_pro)
    f.patch_imm0(_slot1(br_exit_pong), dedup_exit_pong - br_exit_pong)
    f.patch_imm0(_slot1(br_exit_ping_ss), dedup_exit_ping - br_exit_ping_ss)
    f.patch_imm0(_slot1(br_done_from_pong), dedup_done - br_done_from_pong)
    # === STEP DONE ===
    write_solo(f, data_movement_instruction(gr_lo, gr_lo, 0, 0, 12, 0, 0, 0, 1, 12, addi))             # gr_lo[12]++
    write_solo(f, write_magic(5))                                                                         # magic5
    write_solo(f, data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # drain check
    br_drain_post = f.pc
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                        # bne → DRAIN_EXIT
    write_solo(f, data_movement_instruction(gr, gr_hi, 0, 0, 5, 0, 0, 0, 12, 0, mv))                   # gr[5]=gr_hi[12]
    write_solo(f, data_movement_instruction(gr, gr_lo, 0, 0, 6, 0, 0, 0, 12, 0, mv))                   # gr[6]=gr_lo[12]
    begin_step = 2
    write_solo(f, data_movement_instruction(0, 0, 0, 0, begin_step - f.pc, 0, 1, 0, 5, 6, bge))        # bge → step loop
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # jump +2 → END
    drain_exit = f.pc
    f.patch_imm0(_slot1(br_drain_pro), drain_exit - br_drain_pro)
    f.patch_imm0(_slot1(br_drain_ha), drain_exit - br_drain_ha)
    f.patch_imm0(_slot1(br_drain_hb), drain_exit - br_drain_hb)
    f.patch_imm0(_slot1(br_drain_sg), drain_exit - br_drain_sg)
    f.patch_imm0(_slot1(br_drain_post), drain_exit - br_drain_post)
    write_solo(f, write_magic(17))                                                                        # magic17 (drain)
    write_solo(f, write_magic(3))                                                                         # magic3 (end)
    write_solo(f, data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # halt
    # Lowered tile_load subroutine appended after the final halt. Reachable
    # only by paired call (halt blocks fall-through). Entry PC is saved for
    # use by future cutover sites (paired call patching).
    tile_load_entry_pc = emit_tile_load_subroutine(f)
    # Patch every paired call site to target the subroutine's entry PC.
    # Both slots of each call must hold the same imm0 (call-pairing rule).
    for (i0, i1) in tile_load_call_patches:
        f.patch_imm0(i0, tile_load_entry_pc)
        f.patch_imm0(i1, tile_load_entry_pc)
    f.close()

def gwfa_compute():
    f = InstructionWriter("instructions/gwfa/compute_instruction.txt")
    f.close()

def pe_instruction(pe_id):
    f = InstructionWriter("instructions/gwfa/pe_{}_instruction.txt".format(pe_id))
    # PC 0: halt -- wait for controller
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- BUF0: phase 1 compute + boundary sort ---
    # PC 1: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 2: compute buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_8_BUF0))                                                             # slot1: magic(8, mask=0)
    # PC 3: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 4: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 5: clear sync (sort)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 6: boundary sort buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_11_BUF0))                                                            # slot1: magic(11, mask=0)
    # PC 7: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 8: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- BUF1: phase 1 compute + boundary sort ---
    # PC 9: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 10: compute buf1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_8_BUF1))                                                             # slot1: magic(8, mask=1)
    # PC 11: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 12: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 13: clear sync (sort)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 14: boundary sort buf1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_11_BUF1))                                                            # slot1: magic(11, mask=1)
    # PC 15: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 16: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Phase 2 buf0 ---
    # PC 17: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 18: phase 2 compute buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_13_BUF0))                                                            # slot1: magic(13, mask=0)
    # PC 19: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 20: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Phase 2 buf1 ---
    # PC 21: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 22: phase 2 compute buf1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_13_BUF1))                                                            # slot1: magic(13, mask=1)
    # PC 23: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 24: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- FIN0 buf A (PE_FIN0_A = 25) ---
    # PC 25: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 26: FIN0 compute buf A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_19_F0A))                                                             # slot1: magic(19, mask=0)
    # PC 27: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 28: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- FIN0 buf B (PE_FIN0_B = 29) ---
    # PC 29: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 30: FIN0 compute buf B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_19_F0B))                                                             # slot1: magic(19, mask=2)
    # PC 31: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 32: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort bin count PING (PE_SORT_BIN_COUNT_PING = 33) ---
    # PC 33: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 34: bin count PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_20_BUF0))                                                            # slot1: magic(20, mask=0)
    # PC 35: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 36: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort bin count PONG (PE_SORT_BIN_COUNT_PONG = 37) ---
    # PC 37: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 38: bin count PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_20_BUF1))                                                            # slot1: magic(20, mask=1)
    # PC 39: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 40: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort scatter PING (PE_SORT_SCATTER_PING = 41) ---
    # PC 33: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 34: scatter PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_21_BUF0))                                                            # slot1: magic(21, mask=0)
    # PC 35: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 36: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort scatter PONG (PE_SORT_SCATTER_PONG = 37) ---
    # PC 37: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 38: scatter PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_21_BUF1))                                                            # slot1: magic(21, mask=1)
    # PC 39: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 40: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Merge PING (PE_MERGE_PING = 49) ---
    # PC 49: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 50: merge PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_22_BUF0))                                                            # slot1: magic(22, mask=0)
    # PC 51: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 52: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Merge PONG (PE_MERGE_PONG = 53) ---
    # PC 53: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 54: merge PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_22_BUF1))                                                            # slot1: magic(22, mask=1)
    # PC 55: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 56: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Dedup PING (PE_DEDUP_PING = 57) ---
    # PC 57: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 58: dedup PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_23_BUF0))                                                            # slot1: magic(23, mask=0)
    # PC 59: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 60: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Dedup PONG (PE_DEDUP_PONG = 61) ---
    # PC 61: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 62: dedup PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_23_BUF1))                                                            # slot1: magic(23, mask=1)
    # PC 63: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 64: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    f.close()

if not os.path.exists("instructions/gwfa"):
    os.makedirs("instructions/gwfa")
gwfa_compute()
gwfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
