import sys
import os
from utils import *
from opcodes import *

MEM_BLOCK_SIZE = 64 # in words
SPM_BANDWIDTH = 2 # in words
WFA_COMPUTE_INSTRUCTION_NUM = 28
PE_ALIGN_SYNC = WFA_COMPUTE_INSTRUCTION_NUM + 9 + 5
COMPUTE_LOOP_NEXT = 0
N_PES = 4
INITIALIZATION_PE_NEXT = WFA_COMPUTE_INSTRUCTION_NUM*2+4+N_PES
COMPUTE_H = 0
COMPUTE_D = COMPUTE_H + SPM_BANDWIDTH + 2 #2 is halts
COMPUTE_I_AND_LOAD_H = COMPUTE_D + SPM_BANDWIDTH + 2 #2 is halts





# dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), flag_2, flag_3, imm/reg_1, reg_1(++), opcode
def wfa_main_instruction():
    
    f = InstructionWriter("instructions/wfa/main_instruction.txt");
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, si))                           # set gr[0]=0 to start

    # Dump in the instructions
    for i in range(WFA_COMPUTE_INSTRUCTION_NUM):
        f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv));          # out = instr[i]
    f.write(write_magic(1));
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0
    f.write(data_movement_instruction(gr, gr, 0, 0, PE_ALIGN_SYNC, 0, 0, 0, 0, 0, set_PC))           # PE_PC = PE_ALIGN_SYNC


    #INIT

    #ALIGN_LOOP
    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 1, 8, shifti_l))                     # gr[5] = gr[8] * 2 = gr[8] << 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 0x3, 8, ANDI))                      # gr[6] = gr[8] % 4 = gr[8] & 0x3
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 5, shifti_r))                     # gr[7] = gr[5] // 4

    f.write(data_movement_instruction(gr, gr, 0, 0, 8+1, 0, 0, 0, 0, 6, beq))                        # beq 0 gr[6] 8 DEBUG+1
  #if wf_len % 4 == 1:
    #sync until all PEs done, then set their PC back
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0
    f.write(write_magic(1));
    f.write(data_movement_instruction(gr, gr, 0, 0, PE_ALIGN_SYNC, 0, 0, 0, 0, 0, set_PC))           # PE_PC = PE_ALIGN_SYNC
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                     # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                     # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                     # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                   # out = gr[7] + 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 7+1, 0, 0, 0, 0, 0, beq))                        # beq 0 0 7 DEBUG +1
  #else wf_len % 4 == 3:
    #sync until all PEs done, then set their PC back
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0
    f.write(write_magic(1));
    f.write(data_movement_instruction(0, 0, 0, 0, PE_ALIGN_SYNC, 0, 0, 0, 0, 0, set_PC))             # PE_PC = PE_ALIGN_SYNC
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                   # out = gr[7] + 1
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                   # out = gr[7] + 1
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                   # out = gr[7] + 1
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                     # out = gr[7]
  #endif
    #TODO INVOKE MEMORY LOAD MAGIC

    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 1, 8, addi))                         # gr[8]++ (ed++)
    #JMP ALIGN_LOOP
    f.write(data_movement_instruction(gr, gr, 0, 0, -20, 0, 0, 0, 0, 0, beq))                        # beq 0 0 -20

    f.close()

def wfa_compute():

    f = InstructionWriter("instructions/wfa/compute_instruction.txt");
    ##############################NEXT STEP#########################################################
    #Register mapping. We have one tile being loaded while the other is being worked on. If you
    #add 16, then you'll get the mappings for second tile.
    #Each val has 4 regs. for example, 
    # nah make em 0,1,2,3
    # |m_r0 |     |m_r1 | Score -4E Reg 123. cursor in gr11
    # |-----|-----|-----| 
    # |     |     |     | Score -3E
    # |-----|-----|-----|
    # |     |m_r2 |     | Score -2E cursor in gr1
    # |-----|-----|-----|
    # |i_r3 |     |d_r4 | Score -E cursorI in gr2, cursorD in gr3
    # |-----|-----|-----|
    # |     |COMP |     | Current Score, m/d/i cursors in gr4, gr5, gr6
    #                     start the comps at 16
    # gr7 = Tilesize // Tilesize is the tile of the wf this pe processes.
    # gr8 = blocksize // value of i when we switch blocks
    # gr9 = i // the current iteration


#COMPUTE H SCORES [0]
    for i in range(SPM_BANDWIDTH):
        f.write(compute_instruction(ADD_I, MAXIMUM, MAXIMUM, 8+i, 1, 0, 0, 20+i, 24+i, 28+i))
    #free reg8,9 also free dest reg post write 24+,20+,28+
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

#COMPUTE DELETIONS [4]
    for i in range(SPM_BANDWIDTH):
        f.write(compute_instruction(INVALID, MAXIMUM, COPY, 0, 0, 0, 0, 4+i, 16+i, 20+i))
    #free reg 4+, 16+
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

#COMPUTE INSERTIONS AND LOAD H_left [8]
    f.write(compute_instruction(COPY, COPY, INVALID, 4, 0, 0, 0, 0, 0, 0)) #[8]
    f.write(compute_instruction(COPY, COPY, INVALID, 5, 0, 0, 0, 0, 0, 1))
    for i in range(SPM_BANDWIDTH): #[9,12]
        #reg[31] = max(reg[0], reg[12]) + 1
        f.write(compute_instruction(COPY_I, MAXIMUM, ADD, 1, 0, 0, 0, 0, 12+i, 24+i)) 
    #free reg 0+,12+
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.close()


    
def pe_instruction(pe_id):
    
    f = InstructionWriter("instructions/wfa/pe_{}_instruction.txt".format(pe_id));

    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, si))                           # set gr[0]=0 to start
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op 

    for i in range(pe_id):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op 
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op 
    for j in range(WFA_COMPUTE_INSTRUCTION_NUM-1):
        f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, j+1, 0, 0, 0, 0, 0, mv))          # ir[j+1] = in
        f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, j, 0, mv))           # out = ir[j]
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                           # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op 
    for i in range(4 - pe_id): #just here to align the instructions between PEs
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op 
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt

#INITIALIZATION NEXT CYCLE=WFA_COMPUTE_INSTRUCTION_NUM*2+4+N_PES
    #NOTES
    #I assume write to reg file can be done in adjacent blocks. #TODO we need to implement this
    #The general format is, load SPM, update cursor, stall for a cycle until SPM is ready again
    #initialize the counter
    #INITIALIZING REGISTERS
    #mark busy
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                           # gr[10] = 0
    #gr[1,6] are initialized to cursor positions. Each block is offset by MEM_BLOCK_SIZE
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0*MEM_BLOCK_SIZE, 0, si))            # gr[11] open
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 1*MEM_BLOCK_SIZE, 0, si))             # gr[1] match          
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 2*MEM_BLOCK_SIZE, 0, si))             # gr[2] i
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 3*MEM_BLOCK_SIZE, 0, si))             # gr[3] d
    f.write(data_movement_instruction(gr, 0, 0, 0, 4, 0, 0, 0, 4*MEM_BLOCK_SIZE, 0, si))             # gr[4] m write
    f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, 5*MEM_BLOCK_SIZE, 0, si))             # gr[5] d write
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 6*MEM_BLOCK_SIZE, 0, si))             # gr[6] i write

    #mark ready then halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                           # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt

    #PE_ALIGN_SYNC = WFA_COMPUTE_INSTRUCTION_NUM + 18(instruction mv) + 12(start align loop)
    #mark as busy
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                           # gr[10] = 0

    # gr[7] holds the number of iterations for this pe in this step of next
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                      # gr[7] = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                            # gr[9] = 0 (loop counter)
    #INITIALIZE FIRST LOADS FROM CURSORS
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                            # gr[1] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                            # gr[2] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))                            # gr[3] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0, 0, si))                           # gr[4] = 0
    #COPY FIRST PART OF BLOCK LOOP SKIP WRITE THOUGH
    #Load DELETIONS [0,3]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 11, mv))                        # reg[4]=SPM[gr[11]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 11, 0, 0, 0, SPM_BANDWIDTH, 11, addi))           # gr[11] = gr[11] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mv))                        # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))             # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_H, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = COMPUTE_H
    #Load INSERTIONS [4,5]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))                        # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))             # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_I_AND_LOAD_H, 0, 0, 0, 0, 0, set_PC))      # PE_PC = COMPUTE_I_AND_LOAD_H
    #Load H [6,7]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 2, mv))                         # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))             # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_D, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = COMPUTE_D

#BLOCK_LOOP NEXT
    #Load DELETIONS [0,3]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 11, mv))                        # reg[4]=SPM[gr[11]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 11, 0, 0, 0, SPM_BANDWIDTH, 11, addi))           # gr[11] = gr[11] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mv))                        # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))             # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_H, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = COMPUTE_H
    #Load INSERTIONS [4,5]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))                        # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))             # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_I_AND_LOAD_H, 0, 0, 0, 0, 0, set_PC))      # PE_PC = COMPUTE_I_AND_LOAD_H
    #Load H [6,7]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 2, mv))                         # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))             # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_D, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = COMPUTE_D
    #Write H [8,13]
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 4, 0, 0, 20, 0, mv))                        # SPM[gr[4]]=reg[20] //M
    f.write(data_movement_instruction(gr, gr, 1, 0, 4, 0, 0, 0, SPM_BANDWIDTH, 4, addi))             # gr[4] = gr[4] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 5, 0, 0, 24, 0, mv))                        # SPM[gr[5]]=reg[24] //D
    f.write(data_movement_instruction(gr, gr, 1, 0, 5, 0, 0, 0, SPM_BANDWIDTH, 5, addi))             # gr[5] = gr[5] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 6, 0, 0, 28, 0, mv))                        # SPM[gr[6]]=reg[28] //I
    f.write(data_movement_instruction(gr, gr, 1, 0, 6, 0, 0, 0, SPM_BANDWIDTH, 6, addi))             # gr[6] = gr[6] + SPM_BANDWIDTH
    f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, SPM_BANDWIDTH, 9, addi))             #gr[9] = gr[9] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, -14, 0, 1, 0, 9, 7, blt))                          # blt gr[9] gr[7] -14 
    f.write(data_movement_instruction(0, 0, 0, 0, -14, 0, 1, 0, 9, 7, blt))                          # blt gr[9] gr[7] -14 

    #jump all the way to top
    f.write(data_movement_instruction(0, 0, 0, 0, -35, 0, 0, 0, 0, 0, beq))                          # beq 0 0 -36
    f.write(data_movement_instruction(0, 0, 0, 0, -35, 0, 0, 0, 0, 0, beq))                          # beq 0 0 -36 


    f.close()



if not os.path.exists("instructions/wfa"):
    os.makedirs("instructions/wfa")
wfa_compute()
wfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
