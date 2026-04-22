import os
from utils import *
from opcodes import *

LAST_SPM_ADDR = 32767

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
MAGIC_7_BUF0  = 7
MAGIC_7_BUF1  = (7 << 8) | 1
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

def emit_merge_loop(f):
    """Emit a PE-parallel merge loop. Caller must set gr[6]=loop bound
    before calling. Uses PE_MERGE_PING/PONG, MAGIC_33 (reload A/B input
    buffers from MM, overlapped with PE compute), MAGIC_35 (writeback).
    Returns PC after the loop."""
    br_skip = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 6, beq))
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))
    f.write(data_movement_instruction(0, 0, 0, 0, PE_MERGE_PING, 0, 0, 0, 0, 0, set_PC))
    br_epilA_pro = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))
    ss_pong = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin (PE wrote OUT_PING)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_MERGE_PONG, 0, 0, 0, 0, 0, set_PC))            # PE starts (writes OUT_PONG)
    f.write(write_magic(MAGIC_35_BUF0))                                                               # writeback OUT_PING (overlapped)
    f.write(write_magic(MAGIC_33))                                                                     # reload tiles (overlapped)
    br_epilB = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin (PE wrote OUT_PONG)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_MERGE_PING, 0, 0, 0, 0, 0, set_PC))            # PE starts (writes OUT_PING)
    f.write(write_magic(MAGIC_35_BUF1))                                                               # writeback OUT_PONG (overlapped)
    f.write(write_magic(MAGIC_33))                                                                     # reload tiles (overlapped)
    br_epilA_ss = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))
    f.write(data_movement_instruction(0, 0, 0, 0, ss_pong - f.write_count, 0, 0, 0, 0, 0, jump))
    epilB = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin last PONG
    f.write(write_magic(MAGIC_35_BUF1))                                                               # writeback last PONG
    br_done_B = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))
    epilA = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin last PING
    f.write(write_magic(MAGIC_35_BUF0))                                                               # writeback last PING
    done = f.write_count
    f.patch_imm0(br_skip, done - br_skip)
    f.patch_imm0(br_epilA_pro, epilA - br_epilA_pro)
    f.patch_imm0(br_epilB, epilB - br_epilB)
    f.patch_imm0(br_epilA_ss, epilA - br_epilA_ss)
    f.patch_imm0(br_done_B, done - br_done_B)

def emit_sort_loop(f):
    """Emit one radix sort pass loop (42 instructions). Position-independent.
    Caller must set gr[1]=0 before calling. Uses gr[1..7,24], s1c[], SPM."""
    # --- BIN COUNT PHASE ---
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # +0: gr[2]=0 (cursor=0)
    f.write(write_magic(MAGIC_34_BUF0))                                                            # +1: load tile→PING
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PING, 0, 0, 0, 0, 0, set_PC)) # +2: set_PC bin count PING
    f.write(data_movement_instruction(0, 0, 0, 0, 12, 0, 1, 0, 2, 6, bge))                      # +3: bge cursor>=nape → +12 (+15)
    f.write(write_magic(MAGIC_34_BUF1))                                                            # +4: SS_PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +5: spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PONG, 0, 0, 0, 0, 0, set_PC)) # +6: set_PC bin count PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 1, 0, 2, 6, bge))                       # +7: bge → +6 (+13)
    f.write(write_magic(MAGIC_34_BUF0))                                                            # +8: SS_PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +9: spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PING, 0, 0, 0, 0, 0, set_PC)) # +10: set_PC bin count PING
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 1, 0, 2, 6, bge))                       # +11: bge → +4 (+15)
    f.write(data_movement_instruction(0, 0, 0, 0, -8, 0, 0, 0, 0, 0, jump))                      # +12: jump -8 (+4: SS_PONG)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +13: EPIL_B: spin
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # +14: jump +2 (+16)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +15: EPIL_A: spin
    f.write(write_magic(MAGIC_19))                                                                  # +16: prefix sum
    # --- SCATTER PHASE ---
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # +17: gr[2]=0
    f.write(write_magic(MAGIC_24_BUF0))                                                            # +18: load tile→PING
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PING, 0, 0, 0, 0, 0, set_PC))  # +19: set_PC scatter PING
    f.write(data_movement_instruction(0, 0, 0, 0, 15, 0, 1, 0, 2, 6, bge))                      # +20: bge → +15 (+35)
    f.write(write_magic(MAGIC_24_BUF1))                                                            # +21: SS_PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +22: spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PONG, 0, 0, 0, 0, 0, set_PC))  # +23: set_PC scatter PONG
    f.write(write_magic(MAGIC_25_BUF0))                                                            # +24: writeback PING (overlapped)
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 2, 6, bge))                       # +25: bge → +7 (+32)
    f.write(write_magic(MAGIC_24_BUF0))                                                            # +26: SS_PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +27: spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PING, 0, 0, 0, 0, 0, set_PC))  # +28: set_PC scatter PING
    f.write(write_magic(MAGIC_25_BUF1))                                                            # +29: writeback PONG (overlapped)
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 1, 0, 2, 6, bge))                       # +30: bge → +5 (+35)
    f.write(data_movement_instruction(0, 0, 0, 0, -10, 0, 0, 0, 0, 0, jump))                     # +31: jump -10 (+21: SS_PONG)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +32: SEPIL_B: spin
    f.write(write_magic(MAGIC_25_BUF1))                                                            # +33: writeback PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, 0, 0, jump))                       # +34: jump +3 (+37)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +35: SEPIL_A: spin
    f.write(write_magic(MAGIC_25_BUF0))                                                            # +36: writeback PING
    # --- PASS FOOTER ---
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 3, 0, mv))                      # +37: gr[7]=gr[3] (swap)
    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 4, 0, mv))                      # +38: gr[3]=gr[4]
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 7, 0, mv))                      # +39: gr[4]=gr[7]
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))                    # +40: gr[1]++
    f.write(data_movement_instruction(0, 0, 0, 0, -41, 0, 0, 0, 8, 1, bne))                     # +41: bne 8!=gr[1] → -41 (+0)

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))                                                                        # PC 0: init
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))          # PC 1: SPM[32767]=0
    # === STEP LOOP ===
    f.write(write_magic(4))                                                                        # PC 2: begin_step
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                       # PC 3: gr[14]=0 (cursor)
    # === PHASE 1 PROLOGUE ===
    # Prime buf0 serially (nothing to overlap on first iter), then
    # prime buf1 inside the compute-overlap window so the SS loop
    # can assume both buffers are always ready.
    f.write(write_magic(MAGIC_7_BUF0))                                                             # PC 4: tile_load buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: magic7 writes SPM via MM
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: magic8 reads those SPM values
    f.write(write_magic(MAGIC_8_BUF0))                                                             # load_seq_info buf0
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 6: set_PC buf0 compute
    f.write(write_magic(MAGIC_7_BUF1))                                                             # tile_load buf1 ← overlaps compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: magic7→8 dependency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))
    f.write(write_magic(MAGIC_8_BUF1))                                                             # load_seq_info buf1 ← overlaps compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 9: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 10: set_PC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 11: spin gr[13] (ctrl idle)
    br_pro_exit = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 14, 15, bge))                      # PC 12: bge cursor>=n_a → FINALIZE_B1 (patched)
    # === PHASE 1 STEADY STATE: buf1 half ===
    # buf1 already primed. During buf1 compute, overlap: writeback
    # prev buf0 output, then load NEXT buf0 input.
    ss_buf1 = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 13: set_PC buf1 compute
    f.write(write_magic(MAGIC_9_BUF0))                                                             # PC 14: writeback buf0 ← overlap
    f.write(write_magic(MAGIC_7_BUF0))                                                             # load NEXT buf0 ← overlap
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: magic7→8 dependency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))
    f.write(write_magic(MAGIC_8_BUF0))                                                             # load_seq_info NEXT buf0 ← overlap
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 17: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 18: set_PC buf1 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 19: spin gr[13] (ctrl idle)
    br_ss_b1_exit = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 14, 15, bge))                      # PC 20: bge cursor>=n_a → FINALIZE_B0 (patched)
    # === PHASE 1 STEADY STATE: buf0 half ===
    # buf0 primed by previous buf1 half's overlap. During buf0
    # compute, overlap: writeback prev buf1 output, then load NEXT buf1.
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 21: set_PC buf0 compute
    f.write(write_magic(MAGIC_9_BUF1))                                                             # PC 22: writeback buf1 ← overlap
    f.write(write_magic(MAGIC_7_BUF1))                                                             # load NEXT buf1 ← overlap
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                    # barrier: magic7→8 dependency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))
    f.write(write_magic(MAGIC_8_BUF1))                                                             # load_seq_info NEXT buf1 ← overlap
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 25: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 26: set_PC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 27: spin gr[13] (ctrl idle)
    f.write(data_movement_instruction(0, 0, 0, 0, ss_buf1 - f.write_count, 0, 1, 0, 14, 15, blt)) # PC 28: blt cursor<n_a → SS buf1
    # fallthrough: cursor >= n_a → FINALIZE_B1 (compute pre-loaded buf1)
    # === FINALIZE_B1: compute pre-loaded buf1, writeback both ===
    finalize_b1 = f.write_count
    f.patch_imm0(br_pro_exit, finalize_b1 - br_pro_exit)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # setPC buf1 compute
    f.write(write_magic(MAGIC_9_BUF0))                                                             # m9_b0 [overlap: writeback prev buf0]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_SORT, 0, 0, 0, 0, 0, set_PC))          # setPC buf1 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    f.write(write_magic(MAGIC_9_BUF1))                                                             # m9_b1 writeback buf1
    br_skip_fb0 = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))                       # jump → FIFO_FLUSH (patched)
    # === FINALIZE_B0: compute pre-loaded buf0, writeback both ===
    finalize_b0 = f.write_count
    f.patch_imm0(br_ss_b1_exit, finalize_b0 - br_ss_b1_exit)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # setPC buf0 compute
    f.write(write_magic(MAGIC_9_BUF1))                                                             # m9_b1 [overlap: writeback prev buf1]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # setPC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # spin
    f.write(write_magic(MAGIC_9_BUF0))                                                             # m9_b0 writeback buf0
    # fallthrough to FIFO_FLUSH
    f.patch_imm0(br_skip_fb0, f.write_count - br_skip_fb0)
    # === FIFO FLUSH (guarded by gr[2] from magic 9) ===
    br_fifo_skip = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                        # beq gr[2]==0 → save n_phase1 (patched)
    f.write(data_movement_instruction(gr, fifo[0], 0, 0, 3, 0, 0, 0, 0, 0, mv))                  # PC 31: gr[3]=fifo[0]
    f.write(data_movement_instruction(gr, fifo[1], 0, 0, 4, 0, 0, 0, 0, 0, mv))                  # PC 32: gr[4]=fifo[1]
    f.write(write_magic(12))                                                                       # PC 33: flush to s_B_a
    # fallthrough
    save_n_phase1 = f.write_count
    f.write(data_movement_instruction(s1c, gr, 0, 0, 151, 0, 0, 0, 24, 0, mv))                   # s1c[151]=gr[24] (save n_phase1 diags)
    f.patch_imm0(br_fifo_skip, save_n_phase1 - br_fifo_skip)
    # === PHASE 2 (overlapped: magic18+magic15 during PE_P2, magic14 during PE_FIN0) ===
    # --- Prologue: load both buffers, compute BUF1 to seed HALF_A ---
    prologue_start = f.write_count
    f.write(write_magic(MAGIC_14_BUF0))                                                              # load first tiles
    br_p2exit = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → P2_EXIT
    f.write(write_magic(MAGIC_14_BUF1))                                                              # load second tiles
    br_single = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → SINGLE
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF1, 0, 0, 0, 0, 0, set_PC))              # PE_P2_BUF1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_pro = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    # --- HALF_A: PE_P2_BUF0 || magic18+magic15, PE_FIN0_A || magic14 ---
    half_a = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))              # set_PC PE_P2_BUF0
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B [OVERLAP]
    f.write(write_magic(MAGIC_15_BUF1_F0A))                                                          # magic15 BUF1→FIN0_A [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_P2
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_ha = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    # Multipass intermediate passes (if any) — serial
    br_skip_mp_a = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → skip_mp
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 writeback
    f.write(write_magic(MAGIC_20_F0A))                                                               # magic20 load next, sets gr[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ: m20 MM loads → next m18
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ seam (2x)
    f.write(data_movement_instruction(0, 0, 0, 0, -6, 0, 0, 0, 0, 2, bne))                         # bne gr[2]!=0 → loop (-6)
    # Final/only FIN0 pass — overlapped with magic14
    f.patch_imm0(br_skip_mp_a, f.write_count - br_skip_mp_a)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(write_magic(MAGIC_14_BUF1))                                                              # magic14 BUF1 [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_FIN0
    br_drainA = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → DRAIN_AFTER_A
    # --- HALF_B: PE_P2_BUF1 || magic18+magic15, PE_FIN0_B || magic14 ---
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF1, 0, 0, 0, 0, 0, set_PC))              # set_PC PE_P2_BUF1
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A [OVERLAP]
    f.write(write_magic(MAGIC_15_BUF0_F0B))                                                          # magic15 BUF0→FIN0_B [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_P2
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_hb = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    # Multipass intermediate passes (if any) — serial
    br_skip_mp_b = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → skip_mp
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 writeback
    f.write(write_magic(MAGIC_20_F0B))                                                               # magic20 load next, sets gr[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ: m20 MM loads → next m18
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ seam (2x)
    f.write(data_movement_instruction(0, 0, 0, 0, -6, 0, 0, 0, 0, 2, bne))                         # bne gr[2]!=0 → loop (-6)
    # Final/only FIN0 pass — overlapped with magic14
    f.patch_imm0(br_skip_mp_b, f.write_count - br_skip_mp_b)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(write_magic(MAGIC_14_BUF0))                                                              # magic14 BUF0 [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_FIN0
    br_drainB = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → DRAIN_AFTER_B
    f.write(data_movement_instruction(0, 0, 0, 0, half_a - f.write_count, 0, 0, 0, 0, 0, jump))    # jump → HALF_A
    # --- DRAIN_AFTER_A: flush deferred FIN0_A, writeback P2_BUF0 → FIN0_B drain ---
    f.patch_imm0(br_drainA, f.write_count - br_drainA)
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A (flush deferred)
    f.write(write_magic(MAGIC_15_BUF0_F0B))                                                          # magic15 BUF0→FIN0_B
    # SHARED_FIN0_B_DRAIN (multipass → re-check via PROLOGUE)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, prologue_start - f.write_count, 0, 0, 0, 0, 2, beq))  # beq gr[2]==0 → PROLOGUE
    f.write(write_magic(MAGIC_20_F0B))                                                               # magic20 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ: m20 → m18
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ seam (2x)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, -7, 0, 0, 0, 0, 0, jump))                        # jump -7
    # --- DRAIN_AFTER_B: flush deferred FIN0_B, writeback P2_BUF1 → FIN0_A drain ---
    f.patch_imm0(br_drainB, f.write_count - br_drainB)
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B (flush deferred)
    f.write(write_magic(MAGIC_15_BUF1_F0A))                                                          # magic15 BUF1→FIN0_A
    # SHARED_FIN0_A_DRAIN (multipass → re-check via PROLOGUE)
    shared_fin0a_drain = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, prologue_start - f.write_count, 0, 0, 0, 0, 2, beq))  # beq gr[2]==0 → PROLOGUE
    f.write(write_magic(MAGIC_20_F0A))                                                               # magic20 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ: m20 → m18
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, barrier))                      # waitLSQ seam (2x)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, -7, 0, 0, 0, 0, 0, jump))                        # jump -7
    # --- P2_SINGLE_BUF0: only BUF0 loaded, no overlap ---
    f.patch_imm0(br_single, f.write_count - br_single)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))              # set_PC PE_P2_BUF0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_sg = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    f.write(write_magic(MAGIC_15_BUF0_F0A))                                                          # magic15 BUF0→FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, shared_fin0a_drain - f.write_count, 0, 0, 0, 0, 0, jump))  # jump → FIN0_A_DRAIN
    # === POST-PHASE 2: DIAG SORT → DIAG MERGE → INTV SORT → MERGE → DEDUP ===
    p2_exit = f.write_count
    f.patch_imm0(br_p2exit, p2_exit - br_p2exit)
    # Diag sort setup (magic 16 now sets up diag sort, not intv sort)
    f.write(write_magic(16))                                                                          # sync+setup diag sort
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                           # gr[1]=0
    emit_sort_loop(f)                                                                                  # sort loop 1: diag tail
    # === DIAG MERGE: PE-parallel merge ===
    f.write(write_magic(MAGIC_28))                                                                     # diag split + load
    emit_merge_loop(f)
    f.write(write_magic(MAGIC_36))                                                                     # diag merge finalize
    # === INTV SORT: setup + radix sort ===
    f.write(write_magic(MAGIC_39))                                                                     # intv sort setup
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                           # gr[1]=0
    emit_sort_loop(f)                                                                                  # sort loop 2: intv
    # === INTV MERGE: PE-parallel (sorted new + old) ===
    f.write(write_magic(MAGIC_37))                                                                     # intv merge split + load
    emit_merge_loop(f)
    f.write(write_magic(MAGIC_38))                                                                     # intv merge finalize
    # Dedup (tiled with overlapped writeback+reload)
    # Matches old dedup/merge ISA pattern.
    f.write(write_magic(MAGIC_29))                                                                     # dedup split + initial tile load
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                           # gr[2]=0
    # --- Prologue: load + first PE call ---
    f.write(write_magic(MAGIC_30_BUF0))                                                               # reload (loads BUF1 from remaining data)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PING, 0, 0, 0, 0, 0, set_PC))
    br_exit_ping_pro = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))                           # → EXIT_PING (patch)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop pair
    # --- SS_PONG ---
    ss_pong = f.write_count
    f.write(write_magic(MAGIC_30_BUF0))                                                               # reload (slot0, re-exec safe during spin)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin (slot1)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PONG, 0, 0, 0, 0, 0, set_PC))            # PE starts OUT1
    f.write(write_magic(MAGIC_31_BUF0))                                                               # writeback OUT0 (overlapped)
    br_exit_pong = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))                           # → EXIT_PONG (patch)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop pair
    # --- SS_PING ---
    f.write(write_magic(MAGIC_30_BUF0))                                                               # reload (slot0, re-exec safe during spin)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin (slot1)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PING, 0, 0, 0, 0, 0, set_PC))            # PE starts OUT0
    f.write(write_magic(MAGIC_31_BUF1))                                                               # writeback OUT1 (overlapped)
    br_exit_ping_ss = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 1, 0, 2, 6, bge))                           # → EXIT_PING (patch)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop pair
    f.write(data_movement_instruction(0, 0, 0, 0, ss_pong - f.write_count, 0, 0, 0, 0, 0, jump))    # → SS_PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop pair
    # --- DEDUP_EXIT_PONG ---
    dedup_exit_pong = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop (slot0)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin (slot1)
    f.write(write_magic(MAGIC_31_BUF1))                                                               # writeback last PONG
    br_done_from_pong = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, jump))                          # → DONE (patch)
    # --- DEDUP_EXIT_PING ---
    dedup_exit_ping = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop (slot0)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                          # spin (slot1)
    f.write(write_magic(MAGIC_31_BUF0))                                                               # writeback last PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop pair
    # fallthrough to DONE
    dedup_done = f.write_count
    f.write(write_magic(MAGIC_32))                                                                     # gather + finalize
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          # nop pair
    # Patch dedup branches
    f.patch_imm0(br_exit_ping_pro, dedup_exit_ping - br_exit_ping_pro)
    f.patch_imm0(br_exit_pong, dedup_exit_pong - br_exit_pong)
    f.patch_imm0(br_exit_ping_ss, dedup_exit_ping - br_exit_ping_ss)
    f.patch_imm0(br_done_from_pong, dedup_done - br_done_from_pong)
    # === STEP DONE ===
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 12, 0, 0, 0, 1, 12, addi))               # gr_lo[12]++
    f.write(write_magic(5))                                                                           # magic5
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_post = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    f.write(data_movement_instruction(gr, gr_hi, 0, 0, 5, 0, 0, 0, 12, 0, mv))                     # gr[5]=gr_hi[12]
    f.write(data_movement_instruction(gr, gr_lo, 0, 0, 6, 0, 0, 0, 12, 0, mv))                     # gr[6]=gr_lo[12]
    begin_step = 2
    f.write(data_movement_instruction(0, 0, 0, 0, begin_step - f.write_count, 0, 1, 0, 5, 6, bge)) # bge → step loop
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                         # jump +2 → END
    drain_exit = f.write_count
    f.patch_imm0(br_drain_pro, drain_exit - br_drain_pro)
    f.patch_imm0(br_drain_ha, drain_exit - br_drain_ha)
    f.patch_imm0(br_drain_hb, drain_exit - br_drain_hb)
    f.patch_imm0(br_drain_sg, drain_exit - br_drain_sg)
    f.patch_imm0(br_drain_post, drain_exit - br_drain_post)
    f.write(write_magic(17))                                                                          # magic17 (drain)
    f.write(write_magic(3))                                                                           # magic3 (end)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                         # halt
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
