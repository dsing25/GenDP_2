import os
from utils import *
from opcodes import *

LAST_SPM_ADDR = 8191

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))                                                                          # PC 0: gwfa_init
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))            # PC 1: SPM[8191] = 0
    #LOOP
    f.write(write_magic(4))                                                                          # PC 2: gwfa_reset_step
    f.write(write_magic(2))                                                                          # PC 3: gwfa_extend_step(gr[12])
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, addi))                      # PC 4: gr[12]++ (s++)
    f.write(write_magic(5))                                                                          # PC 5: gwfa_debug_step(gr[12])
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))            # PC 6: gr[1] = SPM[8191]
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 1, bne))                            # PC 7: if gr[1]!=0 → +2 (END)
    f.write(data_movement_instruction(0, 0, 0, 0, -6, 0, 1, 0, 23, 12, bge))                        # PC 8: if s_term>=s → -6 (LOOP)
    #END
    f.write(write_magic(3))                                                                          # PC 9: gwfa_print_score
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                          # PC 10: halt
    f.close()

def gwfa_compute():
    f = InstructionWriter("instructions/gwfa/compute_instruction.txt")
    f.close()

def pe_instruction(pe_id):
    f = InstructionWriter("instructions/gwfa/pe_{}_instruction.txt".format(pe_id))
    f.close()

if not os.path.exists("instructions/gwfa"):
    os.makedirs("instructions/gwfa")
gwfa_compute()
gwfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
