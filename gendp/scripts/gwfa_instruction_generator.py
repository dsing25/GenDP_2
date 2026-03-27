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

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))                                                                        # PC 0: init
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))          # PC 1: SPM[32767]=0
    # === STEP LOOP ===
    f.write(write_magic(4))                                                                        # PC 2: begin_step
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                       # PC 3: gr[14]=0 (cursor)
    # === PHASE 1 PROLOGUE (buf0, no prev writeback) ===
    f.write(write_magic(MAGIC_7_BUF0))                                                             # PC 4: tile_load buf0
    f.write(write_magic(MAGIC_8_BUF0))                                                             # PC 5: load_seq_info buf0
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 6: set_PC buf0 compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 7: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 8: set_PC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 9: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 17, 0, 1, 0, 14, 15, bge))                     # PC 10: bge cursor>=n_a → +17 (PC 27: P1_EPIL_A)
    # === PHASE 1 STEADY STATE: buf1 half ===
    # Load+compute buf1, writeback buf0 during compute
    f.write(write_magic(MAGIC_7_BUF1))                                                             # PC 11: tile_load buf1
    f.write(write_magic(MAGIC_8_BUF1))                                                             # PC 12: load_seq_info buf1
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 13: set_PC buf1 compute
    f.write(write_magic(MAGIC_9_BUF0))                                                             # PC 14: writeback buf0 ← overlaps PE compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 15: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 16: set_PC buf1 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 17: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 1, 0, 14, 15, bge))                     # PC 18: bge cursor>=n_a → +11 (PC 29: P1_EPIL_B)
    # === PHASE 1 STEADY STATE: buf0 half ===
    # Load+compute buf0, writeback buf1 during compute
    f.write(write_magic(MAGIC_7_BUF0))                                                             # PC 19: tile_load buf0
    f.write(write_magic(MAGIC_8_BUF0))                                                             # PC 20: load_seq_info buf0
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 21: set_PC buf0 compute
    f.write(write_magic(MAGIC_9_BUF1))                                                             # PC 22: writeback buf1 ← overlaps PE compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 23: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 24: set_PC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 25: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, -15, 0, 1, 0, 14, 15, blt))                    # PC 26: blt cursor<n_a → -15 (PC 11: SS buf1)
    # fallthrough: cursor >= n_a → P1_EPIL_A
    # === P1 EPILOGUE A: writeback buf0 ===
    f.write(write_magic(MAGIC_9_BUF0))                                                             # PC 27: writeback buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # PC 28: jump +2 → PC 30 (FIFO_FLUSH)
    # === P1 EPILOGUE B: writeback buf1 ===
    f.write(write_magic(MAGIC_9_BUF1))                                                             # PC 29: writeback buf1
    # fallthrough to FIFO_FLUSH
    # === FIFO FLUSH (guarded by gr[2] from magic 9) ===
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 0, 0, 0, 2, beq))                        # PC 30: beq gr[2]==0 → +4 (PC 34)
    f.write(data_movement_instruction(gr, fifo[0], 0, 0, 3, 0, 0, 0, 0, 0, mv))                  # PC 31: gr[3]=fifo[0]
    f.write(data_movement_instruction(gr, fifo[1], 0, 0, 4, 0, 0, 0, 0, 0, mv))                  # PC 32: gr[4]=fifo[1]
    f.write(write_magic(12))                                                                       # PC 33: flush to s_B_a
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
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR - 1, 0, 0, 0, 2, 0, mv))       # SPM[32766]=gr[2] save multipass
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(write_magic(MAGIC_14_BUF1))                                                              # magic14 BUF1 [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_FIN0
    f.write(data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, 2, 0, mv))                        # gr[23]=gr[2] save tiles_loaded
    f.write(data_movement_instruction(gr, SPM, 0, 0, 2, 0, 0, 0, LAST_SPM_ADDR - 1, 0, mv))       # gr[2]=SPM[32766] restore multipass
    # Multipass FIN0_A
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → +6
    f.write(write_magic(MAGIC_20_F0A))                                                               # magic20 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, -5, 0, 0, 0, 0, 0, jump))                        # jump -5
    br_drainA = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 23, beq))                         # beq gr[23]==0 → DRAIN_AFTER_A
    # --- HALF_B: PE_P2_BUF1 || magic18+magic15, PE_FIN0_B || magic14 ---
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF1, 0, 0, 0, 0, 0, set_PC))              # set_PC PE_P2_BUF1
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A [OVERLAP]
    f.write(write_magic(MAGIC_15_BUF0_F0B))                                                          # magic15 BUF0→FIN0_B [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_P2
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_hb = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR - 1, 0, 0, 0, 2, 0, mv))       # SPM[32766]=gr[2] save multipass
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(write_magic(MAGIC_14_BUF0))                                                              # magic14 BUF0 [OVERLAP]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin PE_FIN0
    f.write(data_movement_instruction(gr, gr, 0, 0, 23, 0, 0, 0, 2, 0, mv))                        # gr[23]=gr[2] save tiles_loaded
    f.write(data_movement_instruction(gr, SPM, 0, 0, 2, 0, 0, 0, LAST_SPM_ADDR - 1, 0, mv))       # gr[2]=SPM[32766] restore multipass
    # Multipass FIN0_B
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 0, 0, 0, 2, beq))                          # beq gr[2]==0 → +6
    f.write(write_magic(MAGIC_20_F0B))                                                               # magic20 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, -5, 0, 0, 0, 0, 0, jump))                        # jump -5
    br_drainB = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 23, beq))                         # beq gr[23]==0 → DRAIN_AFTER_B
    f.write(data_movement_instruction(0, 0, 0, 0, half_a - f.write_count, 0, 0, 0, 0, 0, jump))    # jump → HALF_A
    # --- DRAIN_AFTER_A: P2_BUF0 pending → FIN0_B drain → re-check via prologue ---
    f.patch_imm0(br_drainA, f.write_count - br_drainA)
    f.write(write_magic(MAGIC_15_BUF0_F0B))                                                          # magic15 BUF0→FIN0_B
    # SHARED_FIN0_B_DRAIN (multipass → re-check via PROLOGUE)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, prologue_start - f.write_count, 0, 0, 0, 0, 2, beq))  # beq gr[2]==0 → PROLOGUE
    f.write(write_magic(MAGIC_20_F0B))                                                               # magic20 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_B, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0B))                                                               # magic18 FIN0_B
    f.write(data_movement_instruction(0, 0, 0, 0, -5, 0, 0, 0, 0, 0, jump))                        # jump -5
    # --- DRAIN_AFTER_B: P2_BUF1 pending → FIN0_A drain → re-check via prologue ---
    f.patch_imm0(br_drainB, f.write_count - br_drainB)
    f.write(write_magic(MAGIC_15_BUF1_F0A))                                                          # magic15 BUF1→FIN0_A
    # SHARED_FIN0_A_DRAIN (multipass → re-check via PROLOGUE)
    shared_fin0a_drain = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, prologue_start - f.write_count, 0, 0, 0, 0, 2, beq))  # beq gr[2]==0 → PROLOGUE
    f.write(write_magic(MAGIC_20_F0A))                                                               # magic20 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, PE_FIN0_A, 0, 0, 0, 0, 0, set_PC))               # set_PC PE_FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(write_magic(MAGIC_18_F0A))                                                               # magic18 FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, -5, 0, 0, 0, 0, 0, jump))                        # jump -5
    # --- P2_SINGLE_BUF0: only BUF0 loaded, no overlap ---
    f.patch_imm0(br_single, f.write_count - br_single)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))              # set_PC PE_P2_BUF0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # spin
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # drain check
    br_drain_sg = f.write_count
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 1, bne))                          # bne → DRAIN_EXIT
    f.write(write_magic(MAGIC_15_BUF0_F0A))                                                          # magic15 BUF0→FIN0_A
    f.write(data_movement_instruction(0, 0, 0, 0, shared_fin0a_drain - f.write_count, 0, 0, 0, 0, 0, jump))  # jump → FIN0_A_DRAIN
    # === POST-PHASE 2 ===
    p2_exit = f.write_count
    f.patch_imm0(br_p2exit, p2_exit - br_p2exit)
    f.write(write_magic(16))                                                                          # step finalize
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
    # --- FIN0 buf A ---
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
    # --- FIN0 buf B ---
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
    f.close()

if not os.path.exists("instructions/gwfa"):
    os.makedirs("instructions/gwfa")
gwfa_compute()
gwfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
