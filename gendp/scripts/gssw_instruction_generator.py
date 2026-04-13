#!/usr/bin/env python3
"""
GSSW instruction generator.
Generates controller + PE instruction traces for the GSSW kernel.

Controller trace:
  PC 0: magic(100)   — init (copy host data → PE 0 SPM)
  PC 1: set_PC 0     — start PEs at PC 0
  PC 2: bne gr[13],1 — spin until all PEs done
  PC 3: halt

PE 0 trace (2 instructions per PC):
  PC 0: halt | halt
  PC 1: nop  | magic(101)   — run gssw_kernel
  PC 2: nop  | magic(102)   — print score
  PC 3: nop  | si gr[10]=1  — signal done
  PC 4: halt | halt

PEs 1-3 trace:
  PC 0: halt | halt
  PC 1: nop  | si gr[10]=1  — signal done immediately
  PC 2: halt | halt
"""

import os
import sys

# Add scripts dir to path for utils/opcodes imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import InstructionWriter, write_magic, \
    data_movement_instruction
from opcodes import gr, halt, none, set_PC, bne, si


def gssw_main_instruction():
    """Generate controller instruction trace."""
    f = InstructionWriter(
        "instructions/gssw/main_instruction.txt")
    # PC 0: init
    f.write(write_magic(100))
    # PC 1: set PE PC to 1 (skip initial halt at PC 0)
    f.write(data_movement_instruction(
        0, 0, 0, 0, 1, 0, 0, 0, 0, 0, set_PC))
    # PC 2: spin until gr[13]==1
    f.write(data_movement_instruction(
        0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))
    # PC 3: halt
    f.write(data_movement_instruction(
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.close()


def pe_instruction(pe_id):
    """Generate PE instruction trace."""
    f = InstructionWriter(
        f"instructions/gssw/pe_{pe_id}_instruction.txt")

    if pe_id == 0:
        # PC 0: halt | halt (wait for set_PC)
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        # PC 1: nop | magic(101) (run kernel)
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(write_magic(101))
        # PC 2: nop | magic(102) (print score)
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(write_magic(102))
        # PC 3: nop | si gr[10]=1 (signal done)
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(
            gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))
        # PC 4: halt | halt
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    else:
        # PC 0: halt | halt (wait for set_PC)
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        # PC 1: nop | si gr[10]=1 (signal done)
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(
            gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))
        # PC 2: halt | halt
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

    f.close()


if __name__ == '__main__':
    os.makedirs("instructions/gssw", exist_ok=True)
    gssw_main_instruction()
    for i in range(4):
        pe_instruction(i)
    print("Generated instructions/gssw/ traces.")
