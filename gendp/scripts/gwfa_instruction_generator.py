import os
from utils import *
from opcodes import *

LAST_SPM_ADDR = 32767
#Code locations
PE_BATCH = 1
PE_BATCH_BOUND_SORT = 5
PE_P2 = 9

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))                                                                        # PC 0: init
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))          # PC 1: SPM[32767]=0
    # === STEP LOOP ===
    f.write(write_magic(4))                                                                        # PC 2: begin_step
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                       # PC 3: gr[14]=0
    # === PHASE 1 TILE LOOP ===
    f.write(write_magic(7))                                                                        # PC 4: tile_load
    f.write(write_magic(8))                                                                        # PC 5: load_seq_info
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BATCH, 0, 0, 0, 0, 0, set_PC))              # PC 6: set_PC 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 7: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BATCH_BOUND_SORT, 0, 0, 0, 0, 0, set_PC))   # PC 8: set_PC 5
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 9: spin gr[13]
    f.write(write_magic(9))                                                                        # PC 10: writeback
    f.write(data_movement_instruction(0, 0, 0, 0, -7, 0, 1, 0, 14, 15, blt))                     # PC 11: tile loop
    # === FIFO FLUSH (guarded by gr[2] from magic 9) ===
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 0, 0, 0, 2, beq))                        # PC 12: beq gr[2]==0 -> +4 (PC 16)
    f.write(data_movement_instruction(gr, fifo[0], 0, 0, 3, 0, 0, 0, 0, 0, mv))                  # PC 13: gr[3]=fifo[0]
    f.write(data_movement_instruction(gr, fifo[1], 0, 0, 4, 0, 0, 0, 0, 0, mv))                  # PC 14: gr[4]=fifo[1]
    f.write(write_magic(12))                                                                       # PC 15: flush to s_B_a
    # === PHASE 2 TILE LOOP ===
    f.write(write_magic(14))                                                                       # PC 16: p2 tile load
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 0, 0, 0, 2, beq))                        # PC 17: beq gr[2]==0 -> +7 (PC 24)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2, 0, 0, 0, 0, 0, set_PC))                 # PC 18: set_PC 9 (PE phase2)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 19: spin gr[13]
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 20: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 10, 0, 0, 0, 0, 1, bne))                       # PC 21: bne gr[1]!=0 -> +10 (PC 31)
    f.write(write_magic(15))                                                                       # PC 22: p2 writeback
    f.write(data_movement_instruction(0, 0, 0, 0, -7, 0, 0, 0, 0, 0, jump))                      # PC 23: jump -7 -> PC 16
    # === PHASE 2 DONE ===
    f.write(write_magic(16))                                                                       # PC 24: finalize
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, addi))                   # PC 25: gr[12]++ (s++)
    f.write(write_magic(5))                                                                        # PC 26: debug
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 27: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 0, 0, 0, 1, bne))                        # PC 28: bne gr[1]!=0 -> +4 (PC 32, skip set_score)
    f.write(data_movement_instruction(0, 0, 0, 0, -27, 0, 1, 0, 23, 12, bge))                    # PC 29: bge s_term>=s -> PC 2
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # PC 30: s_term exceeded -> +2 (PC 32, skip set_score)
    # === FINISH ===
    f.write(write_magic(17))                                                                       # PC 31: set score (PE termination only)
    f.write(write_magic(3))                                                                        # PC 32: print score
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # PC 33: halt
    f.close()

def gwfa_compute():
    f = InstructionWriter("instructions/gwfa/compute_instruction.txt")
    f.close()

def pe_instruction(pe_id):
    f = InstructionWriter("instructions/gwfa/pe_{}_instruction.txt".format(pe_id))
    # PC 0: halt -- wait for controller
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 1: clear sync flag (phase 1)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 2: phase 1 compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(8))                                                                        # slot1: magic(8)
    # PC 3: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 4: halt -- wait for boundary sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 5: clear sync flag
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 6: boundary sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(11))                                                                       # slot1: magic(11)
    # PC 7: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 8: halt -- wait for next
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Phase 2 (NEW) ---
    # PC 9: clear sync (phase 2)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 10: phase 2 compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(13))                                                                       # slot1: magic(13)
    # PC 11: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 12: halt -- wait for next
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
