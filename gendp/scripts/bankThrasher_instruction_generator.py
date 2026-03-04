#!/usr/bin/env python3
"""
bankThrasher instruction generator
Creates simple test case where all 4 PEs read from SPM address 0 repeatedly
to stress-test bank conflict detection.
"""

import sys
import os
from utils import *
from opcodes import *

N_PES = 4
LOOP_ITERATIONS = 10000
BANK_GROUP_SIZE = 8192  # Size of each bank group in bytes

def nop():
    """Generate a no-op instruction"""
    return data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)

def halt_instr():
    """Generate a halt instruction (for both VLIW slots when waiting)"""
    return data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt)

PE_START = 10  # PEs start executing at PC=10 after main calls set_PC

def pe_instruction(pe_id):
    """
    Generate PE instruction trace.
    Each PE:
    1. Waits at halt until main calls set_PC
    2. Initializes loop counter to 10000
    3. Loops: reads SPM address 0 into reg[0]
    4. Signals done via gr[10] = 1

    VLIW pairs: each line is one slot, 2 lines = 1 PC increment
    """
    f = InstructionWriter(f"instructions/bankThrasher/pe_{pe_id}_instruction.txt")

    # Calculate address that maps to PE0's bank for this PE
    # PE0: 0, PE1: -8192, PE2: -16384, PE3: -24576
    # This creates bank conflicts since all access PE0's physical bank

    # PC=0 to PC=9: Halts - PEs wait here until main calls set_PC
    # Both VLIW slots must be halt so both PC[0] and PC[1] stay frozen
    for _ in range(PE_START):
        f.write(halt_instr())
        f.write(halt_instr())

    # PC=10: Initialize gr[0] = 0 (keep 0 for base)
    f.write(data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, 0, 0, si))
    f.write(nop())

    
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, -pe_id*BANK_GROUP_SIZE + pe_id, 0, si))
    f.write(nop())

    # PC=12: Initialize gr[2] = LOOP_ITERATIONS (counter)
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, LOOP_ITERATIONS, 0, si))
    f.write(nop())

    # PC=13 (LOOP_START): Load from SPM[gr[1]] into reg[0] (virtual addr, maps to PE0's bank)
    f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))
    f.write(nop())

    # PC=14: decrement gr[2] (slot 0) + bne (slot 1)
    # In VLIW, slot 1 executes FIRST. So bne executes first checking old gr[2],
    # then subi in slot 0 is skipped if branch taken.
    # To fix: put decrement BEFORE the branch instruction (separate PC)
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 1, 2, subi))
    f.write(nop())

    # PC=15: bne - if gr[2] != gr[0], jump to PC=13 (offset = 13 - 15 = -2)
    f.write(data_movement_instruction(0, 0, 0, 0, -2, 0, 1, 0, 2, 0, bne))
    f.write(nop())

    # PC=18: Signal done gr[10] = 1
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))
    f.write(nop())

    # PC=17: halt (both slots to keep PC[0] and PC[1] frozen)
    f.write(halt_instr())
    f.write(halt_instr())

    f.close()

def main_instruction():
    """
    Generate main (controller) instruction trace.
    Controller:
    1. Initializes SPM with test data
    2. Starts all PEs at PE_START
    3. Waits for all PEs to finish
    """
    f = InstructionWriter("instructions/bankThrasher/main_instruction.txt")

    # For si: imm_0 = dest gr index, imm_1 = value, reg_1=0
    # gr[1] = 0 (address)
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))
    # gr[2] = 42 (data to write)
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 42, 0, si))

    # Write to SPM[gr[1]] = gr[2]
    # dest=SPM, src=gr, use gr[1] for dest addr (slot 0), gr[2] for src data (slot 1)
    f.write(data_movement_instruction(SPM, gr, 0, 0, 0, 1, 0, 0, 0, 2, mv))
    f.write(nop())
    f.write(nop())
    f.write(nop())

    # Start PEs at PC = PE_START (where actual code begins)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_START, 0, 0, 0, 0, 0, set_PC))
    f.write(nop())  # Complete this PC before the spin loop

    # Wait for all PEs to finish (gr[13] = AND of all PE gr[10])
    # Spin until gr[13] == 1 (loop back to same PC if not equal)
    f.write(data_movement_instruction(gr, gr, 0, 0, -1, 0, 0, 0, 1, 13, bne))
    f.write(nop())

    # All done - halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

    f.close()

def compute_instructions():
    """
    Generate compute instruction trace (minimal, not used for this test)
    """
    f = InstructionWriter("instructions/bankThrasher/compute_instruction.txt")

    # Just add a few NOP compute instructions
    for _ in range(8):
        f.write(compute_instruction(HALT, HALT, HALT, 0, 0, 0, 0, 0, 0, 0))

    f.close()

if __name__ == "__main__":
    print("Generating bankThrasher instructions...")

    # Create directory if it doesn't exist
    os.makedirs("instructions/bankThrasher", exist_ok=True)

    # Generate instructions
    main_instruction()
    compute_instructions()

    for pe_id in range(N_PES):
        pe_instruction(pe_id)

    print(f"Generated instructions for {N_PES} PEs")
    print(f"Each PE will execute {LOOP_ITERATIONS} SPM reads from address 0")
    print("Done!")
