import sys
import os
from utils import *
from opcodes import *

MEM_BLOCK_SIZE = 1024 # in words
SPM_BANDWIDTH = 4 # in words
PE_LOOP_WF = 0
WFA_COMPUTE_INSTRUCTION_NUM = 28
COMPUTE_LOOP_NEXT = 0





# dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), flag_2, flag_3, imm/reg_1, reg_1(++), opcode
def wfa_main_instruction():
    
    f = InstructionWriter("instructions/wfa/main_instruction.txt");

    
    # Dump in the instructions
    for i in range(WFA_COMPUTE_INSTRUCTION_NUM):
        f.write(data_movement_instruction(out_port, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv)); # out = instr[i]

    #INIT
    #reg[8] is edit distance, reg[1-4] are n_iters for pe 0-4
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, si))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op

    #ALIGN_LOOP
    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 1, 8, shifti_l))                          # gr[5] = gr[8] * 2 = gr[8] << 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 0x3, 8, AND))                            # gr[6] = gr[8] % 4 = gr[8] & 0x3
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 5, shifti_r))                          # gr[7] = gr[5] // 4
    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 0, 6, beq))                               # beq 0 gr[6] 5

  #if wf_len % 4 == 1:
    #sync until all PEs done, then set their PC back
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                               # bne 1 gr[13] 0
    f.write(data_movement_instruction(gr, gr, 0, 0, PE_LOOP_WF, 0, 0, 0, 0, 0, set_PC))                    # PE_PC = PE_LOOP_WF
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 0, 0, beq))                                # beq 0 0 4
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                               # No-op
  #else wf_len % 4 == 3:
    #sync until all PEs done, then set their PC back
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                               # bne 1 gr[13] 0
    f.write(data_movement_instruction(0, 0, 0, 0, PE_LOOP_WF, 0, 0, 0, 0, 0, set_PC))                    # PE_PC = PE_LOOP_WF
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
  #endif
    #TODO INVOKE MEMORY LOAD MAGIC

    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 1, 8, addi))                               # gr[8]++ (ed++)
    #JMP ALIGN_LOOP
    f.write(data_movement_instruction(gr, gr, 0, 0, -19, 0, 0, 0, 0, 0, beq))                              # beq 0 0 -19

    f.close()

def wfa_compute():

    f = InstructionWriter("instructions/wfa/compute_instruction.txt");
    ##############################NEXT STEP#########################################################
    #Register mapping. We have one tile being loaded while the other is being worked on. If you
    #add 16, then you'll get the mappings for second tile.
    #Each val has 4 regs. for example, 
    # nah make em 0,1,2,3
    # |m_r0 |     |m_r1 | Score -4E Reg 123. cursor in gr0
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

    #BANDWIDTH = 4
#COMPUTE_LOOP_NEXT
#COMPUTE H SCORES (note this operates on dummy data first iter)
    for i in range(SPM_BANDWIDTH): #[0,3]
        f.write(compute_instruction(ADD_I, MAXIMUM, MAXIMUM, 8+i, 1, 0, 0, 20+i, 24+i, 28+i))
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) #STALL
    #free reg8,9 also free dest reg post write 24+,20+,28+
#COMPUTE DELETIONS
    for i in range(SPM_BANDWIDTH): #[4,7]
        f.write(compute_instruction(INVALID, MAXIMUM, COPY, 0, 0, 0, 0, 4+i, 16+i, 20+i))
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) #STALL
    #free reg 4+, 16+
#COMPUTE INSERTIONS
    #reg[31] = max(reg[0], reg[12]) + 1
    f.write(compute_instruction(COPY, COPY, INVALID, 4, 0, 0, 0, 0, 0, 2)) #[8]
    f.write(compute_instruction(COPY, COPY, INVALID, 5, 0, 0, 0, 0, 0, 3))
    for i in range(SPM_BANDWIDTH): #[9,12]
        f.write(compute_instruction(COPY_I, MAXIMUM, ADD, 1, 0, 0, 0, 0, 12+i, 24+i)) 
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) #STALL
    f.write(compute_instruction(COPY, COPY, INVALID, 6, 0, 0, 0, 0, 0, 0)) #[13]
    f.write(compute_instruction(COPY, COPY, INVALID, 7, 0, 0, 0, 0, 0, 1))

    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) #STALL
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) #STALL
    #f.write(compute_instruction(COPY, COPY, INVALID, 1, 0, 0, 0, 0, 0, 0))
    #free reg 0+,12+
    f.close()


    
def pe_instruction(i):
    
    f = InstructionWriter("instructions/wfa/pe_{}_instruction.txt".format(i));

#INITIALIZATION NEXT
    #NOTES
    #I assume write to reg file can be done in adjacent blocks. #TODO we need to implement this
    #The general format is, load SPM, update cursor, stall for a cycle until SPM is ready again
    #initialize the counter
    #INITIALIZING REGISTERS
    #gr[1,6] are initialized to cursor positions. Each block is offset by MEM_BLOCK_SIZE
    f.write(data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, 0*MEM_BLOCK_SIZE, 0, si)) 
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 1*MEM_BLOCK_SIZE, 0, si))
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 2*MEM_BLOCK_SIZE, 0, si))
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 3*MEM_BLOCK_SIZE, 0, si))
    f.write(data_movement_instruction(gr, 0, 0, 0, 4, 0, 0, 0, 4*MEM_BLOCK_SIZE, 0, si))
    f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, 5*MEM_BLOCK_SIZE, 0, si))
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 6*MEM_BLOCK_SIZE, 0, si))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op

    #HALT. We're about to recieve input. Wait until controller is ready
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                              # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                              # halt
    # gr[7] holds the number of iterations for this pe in this step of next
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                   # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                   # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                   # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(gr, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                         # gr[7] = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                               # gr[9] = 0 (loop counter)
    #INITIALIZE FIRST LOADS FROM CURSORS
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                               # gr[1] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                               # gr[2] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))                               # gr[3] = 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0, 0, si))                              # gr[4] = 0
    #COPY FIRST PART OF BLOCK LOOP SKIP WRITE THOUGH
    #Load DELETIONS [0,3]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 11, mv))                           # reg[4]=SPM[gr[11]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 11, 0, 0, 0, SPM_BANDWIDTH, 11, addi))            # gr[11] = gr[11] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mv))                           # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))              # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0,0,0,0,COMPUTE_LOOP_NEXT+SPM_BANDWIDTH,0,0,0,0,0,set_PC))        # PE_PC = COMPUTE_LOOP_NEXT + SPM_BANDWIDTH
    #Load INSERTIONS [4,5]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))                           # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))              # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Load H [6,7]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 2, mv))                            # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))              # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op

#BLOCK_LOOP NEXT
    #Load DELETIONS [0,3]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 11, mv))                           # reg[4]=SPM[gr[11]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 11, 0, 0, 0, SPM_BANDWIDTH, 11, addi))            # gr[11] = gr[11] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mv))                           # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))              # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Load INSERTIONS [4,5]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))                           # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))              # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Load H [6,7]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 2, mv))                            # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))              # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_LOOP_NEXT, 0, 0, 0, 0, 0, set_PC))            # PE_PC = COMPUTE_LOOP_NEXT
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Write H [8,13]
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 4, 0, 0, 20, 0, mv))                           # SPM[gr[4]]=reg[20] //M
    f.write(data_movement_instruction(gr, gr, 1, 0, 4, 0, 0, 0, SPM_BANDWIDTH, 4, addi))              # gr[4] = gr[4] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 5, 0, 0, 24, 0, mv))                           # SPM[gr[5]]=reg[24] //D
    f.write(data_movement_instruction(gr, gr, 1, 0, 5, 0, 0, 0, SPM_BANDWIDTH, 5, addi))              # gr[5] = gr[5] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 6, 0, 0, 28, 0, mv))                           # SPM[gr[6]]=reg[28] //I
    f.write(data_movement_instruction(gr, gr, 1, 0, 6, 0, 0, 0, SPM_BANDWIDTH, 6, addi))              # gr[6] = gr[6] + SPM_BANDWIDTH
    f.write(data_movement_instruction(gr, gr, 1, 0, 5, 0, 0, 0, SPM_BANDWIDTH, 5, addi))              # gr[9] = gr[9] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 1, blt))                             # blt gr[9] gr[7] -13 
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 1, blt))                             # blt gr[9] gr[7] -13 

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #write reg[10] because this is used for synchronization. 
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                              # gr[10] = 1
    #jump all the way to top
    f.write(data_movement_instruction(0, 0, 0, 0, -35, 0, 0, 0, 0, 0, beq))                             # beq 0 0 -35
    f.write(data_movement_instruction(0, 0, 0, 0, -35, 0, 0, 0, 0, 0, beq))                             # beq 0 0 -35 


    f.close()



if not os.path.exists("instructions/wfa"):
    os.makedirs("instructions/wfa")
wfa_compute()
wfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
