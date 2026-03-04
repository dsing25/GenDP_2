import os
from utils import *
from opcodes import *

LAST_SPM_ADDR = 32767
#Code locations
PE_BATCH = 1
PE_BATCH_BOUND_SORT = 5

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))                                                                        # PC 0: init
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))          # PC 1: SPM[32767]=0
    # === STEP LOOP ===
    f.write(write_magic(4))                                                                        # PC 2: begin_step
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                       # PC 3: gr[14]=0
    # === TILE LOOP ===
    f.write(write_magic(7))                                                                        # PC 4: tile_load
    f.write(write_magic(8))                                                                        # PC 5: load_seq_info
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BATCH, 0, 0, 0, 0, 0, set_PC))              # PC 6: set_PC 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 7: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BATCH_BOUND_SORT, 0, 0, 0, 0, 0, set_PC))   # PC 8: set_PC 5
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 9: spin gr[13]
    f.write(write_magic(9))                                                                        # PC 10: writeback
    f.write(data_movement_instruction(0, 0, 0, 0, -7, 0, 1, 0, 14, 15, blt))                     # PC 11: tile loop
    # === FIFO FLUSH ===
    f.write(data_movement_instruction(gr, fifo[0], 0, 0, 3, 0, 0, 0, 0, 0, mv))                  # PC 12: gr[3]=fifo[0]
    f.write(data_movement_instruction(gr, fifo[1], 0, 0, 4, 0, 0, 0, 0, 0, mv))                  # PC 13: gr[4]=fifo[1]
    f.write(write_magic(12))                                                                       # PC 14: flush to s_B_a
    # === PHASE 2 ===
    f.write(write_magic(10))                                                                       # PC 15: phase2
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, addi))                   # PC 16: gr[12]++ (s++)
    f.write(write_magic(5))                                                                        # PC 17: debug
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 18: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 1, bne))                        # PC 19: done -> +2
    f.write(data_movement_instruction(0, 0, 0, 0, -18, 0, 1, 0, 23, 12, bge))                    # PC 20: s_term>=s -> PC 2
    # === END ===
    f.write(write_magic(3))                                                                        # PC 21: print score
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # PC 22: halt
    f.close()

def gwfa_compute():
    f = InstructionWriter("instructions/gwfa/compute_instruction.txt")
    f.close()

def pe_instruction(pe_id):
    f = InstructionWriter("instructions/gwfa/pe_{}_instruction.txt".format(pe_id))
    # PC 0: halt -- wait for controller
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 1: clear sync flag
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 2: tile_compute
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
    # PC 8: halt -- wait for next tile
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
