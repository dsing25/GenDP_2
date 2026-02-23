import os
from utils import *
from opcodes import *

def gwfa_main_instruction():
    f = InstructionWriter(
        "instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))
    f.write(write_magic(2))
    f.write(write_magic(3))
    f.write(data_movement_instruction(
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.close()

def gwfa_compute():
    f = InstructionWriter(
        "instructions/gwfa/compute_instruction.txt")
    f.close()

def pe_instruction(pe_id):
    f = InstructionWriter(
        "instructions/gwfa/pe_{}_instruction.txt"
        .format(pe_id))
    f.close()

if not os.path.exists("instructions/gwfa"):
    os.makedirs("instructions/gwfa")
gwfa_compute()
gwfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
