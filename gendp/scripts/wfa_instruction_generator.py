import sys
import os
from utils import *
from opcodes import *

SPM_BANDWIDTH = 2 # in words
PE_ALIGN_SYNC = 9 + 5
COMPUTE_LOOP_NEXT = 0
N_PES = 4
MIN_INT = -99
#locations in PE ctrl
INIT_PE_NEXT = 2
PE_ALIGN_SYNC = INIT_PE_NEXT + 6
# locations in compute
COMPUTE_H = 0
COMPUTE_D = COMPUTE_H + SPM_BANDWIDTH // 2 + 1 #1 is halts
COMPUTE_I = COMPUTE_D + SPM_BANDWIDTH // 2 + 1 #1 is halts
#MEMORY LOCATIONS
BANK_SIZE = 512
MEM_BLOCK_SIZE = 32 # in words
PATTERN_START = MEM_BLOCK_SIZE*7 + 2
SEQ_LEN_ALLOC = (BANK_SIZE-PATTERN_START) // 2
TEXT_START = PATTERN_START + SEQ_LEN_ALLOC
SWIZZLED_PATTERN_START = PATTERN_START << 2 # need to reverse swizzle to hit 226 at the start
SWIZZLED_TEXT_START = TEXT_START << 2 



# dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), flag_2, flag_3, imm/reg_1, reg_1(++), opcode
def wfa_main_instruction():
    
    f = InstructionWriter("instructions/wfa/main_instruction.txt");
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0

    #TODO initialize somehow
    #This will require doing extend at score=8 after two matches on center diag, and 2 
    #gr8 is the wavefront len, which is also the score + 1. We start with wf_len = 5; score = 4
    f.write(data_movement_instruction(gr, 0, 0, 0, 8, 0, 0, 0, 5, 0, si))                           # gr[8] = 5

#FOR EACH WAVEFRONT
    # calculate number of iterations
    #f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 8, shifti_r))                     # gr[7] = gr[8] // 4
    #f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 1, 7, addi))                         # gr[7] += 1
    #sync until PES are done 
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0
    # send number of iterations
    f.write(write_magic(1));
    f.write(data_movement_instruction(gr, gr, 0, 0, INIT_PE_NEXT, 0, 0, 0, 0, 0, set_PC))           # PE_PC = INIT_PE_NEXT
    #f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 7, 0, mv))                     # out = gr[7]
    #f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 7, 0, mv))                     # out = gr[7]
    #f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 7, 0, mv))                     # out = gr[7]
    #f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 7, 0, mv))                     # out = gr[7]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 8, 0, mv))                     # out = gr[8]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 8, 0, mv))                     # out = gr[8]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 8, 0, mv))                     # out = gr[8]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 8, 0, mv))                     # out = gr[8]
    # increment wf_len
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 2, 8, addi))                         # gr[8]+=2
    #JMP ALIGN_LOOP
    f.write(data_movement_instruction(gr, gr, 0, 0, -8, 0, 0, 0, 0, 0, beq))                        # beq 0 0 -8

    f.close()

def wfa_compute():

    f = InstructionWriter("instructions/wfa/compute_instruction.txt");
    ##############################NEXT STEP#########################################################
    #Register mapping. We have one tile being loaded while the other is being worked on. If you
    #add 16, then you'll get the mappings for second tile.
    #Each val has 4 regs. Affine is e=2, o=6, m=4
    #NOTE reg 0 is a permanent zero reg, so we start at reg 1
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
        f.write(compute_instruction(ADD_I, MAXIMUM, MAXIMUM, 1, 8+i, 0, 0, 20+i, 24+i, 28+i))
    #free reg8,9 also free dest reg post write 24+,20+,28+
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

#COMPUTE DELETIONS [4]
    for i in range(SPM_BANDWIDTH):
        f.write(compute_instruction(MAXIMUM, INVALID, COPY, 4+i, 16+i, 0, 0, 0, 0, 20+i))
    #free reg 4+, 16+
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

#COMPUTE INSERTIONS AND LOAD H_left [8]
    for i in range(SPM_BANDWIDTH): #[9,12]
        #reg[31] = max(reg[0], reg[12]) + 1
        f.write(compute_instruction(COPY_I, MAXIMUM, ADD, 1, 0, 0, 0, 1+i, 12+i, 24+i)) 
    #free reg 0+,12+
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.close()


    
def pe_instruction(pe_id):
    
    f = InstructionWriter("instructions/wfa/pe_{}_instruction.txt".format(pe_id));

    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                           # gr[10] = 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, si))                           # set gr[0]=0 to start (just setting const)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt

#PE_NEXT = (2 INIT)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    #mark as busy
    # gr[12] holds wf len
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                           # gr[10] = 0
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                            # gr[9] = 0 (loop counter)
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 3*MEM_BLOCK_SIZE, 0, si))             # gr[3] d
    f.write(data_movement_instruction(gr, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv))                     # gr[12] = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 4, 0, 0, 0, 4*MEM_BLOCK_SIZE, 0, si))             # gr[4] m write


    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 2*MEM_BLOCK_SIZE, 0, si))             # gr[2] i
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0*MEM_BLOCK_SIZE, 0, si))            # gr[11] open
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 1*MEM_BLOCK_SIZE, 0, si))             # gr[1] match          
    #this loads the leftmost Os from previous tile
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 7*MEM_BLOCK_SIZE, 0, mvd))         # reg[4] = SPM[7*MEM_BLOCK_SIZE]

    #Should be able to save 1 cycle with an if, and maybe 3? using compute ALU
    #we are setting gr[14] to be initial k
    #NOTE gr[14] must start at zero (which we do at end of tile loop)
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 12, shifti_r))                    # gr[7] = gr[12] // 4
    f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, 5*MEM_BLOCK_SIZE, 0, si))             # gr[5] d write
    f.write(data_movement_instruction(gr, gr, 1, 0, 7, 0, 0, 0, 1, 7, addi))                         # gr[7] = gr[7] + 1
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 6*MEM_BLOCK_SIZE, 0, si))             # gr[6] i write
    for _ in range(pe_id):
        f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 14, 7, add))                    # gr[14] = gr[14] + gr[7]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
    if pe_id == 3: #fewer iterations for last PE (reduces memory traffic)
        f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 12, 14, sub))                    # gr[7] = gr[12] - gr[14]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op



#BLOCK_LOOP NEXT
    #Load I; No-op
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))             # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mvd))                       # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(reg, reg, 0, 0, 1, 0, 0, 0, 4, 0, mv))                           # reg[1] = reg[4]
    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 5, 0, mv))                           # reg[2] = reg[5]
    #Load D; compute I
    f.write(data_movement_instruction(gr, gr, 1, 0, 11, 0, 0, 0, SPM_BANDWIDTH, 11, addi))           # gr[11] = gr[11] + SPM_BANDWIDTH
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 11, mvd))                       # reg[4]=SPM[gr[11]]
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_I, 0, 0, 0, 0, 0, set_PC))      # PE_PC = COMPUTE_I
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))             # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mvd))                       # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_D, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = COMPUTE_D
    #Load H; compute D
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))             # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 1, mvd))                        # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_H, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = COMPUTE_H
    #Write I; compute H
    f.write(data_movement_instruction(gr, gr, 1, 0, 6, 0, 0, 0, SPM_BANDWIDTH, 6, addi))             # gr[6] = gr[6] + SPM_BANDWIDTH
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 6, 0, 0, 24, 0, mvd))                       # SPM[gr[6]]=reg[24] //I
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    #write D; No-op
    f.write(data_movement_instruction(gr, gr, 1, 0, 5, 0, 0, 0, SPM_BANDWIDTH, 5, addi))             # gr[5] = gr[5] + SPM_BANDWIDTH
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 5, 0, 0, 20, 0, mvd))                       # SPM[gr[5]]=reg[20] //D
    f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, SPM_BANDWIDTH, 9, addi))             #gr[9] = gr[9] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    #Write H; No-op
    f.write(data_movement_instruction(gr, gr, 1, 0, 4, 0, 0, 0, SPM_BANDWIDTH, 4, addi))             # gr[4] = gr[4] + SPM_BANDWIDTH
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 4, 0, 0, 28, 0, mvd))                       # SPM[gr[4]]=reg[28] //M
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                          # blt gr[9] gr[7] -13 
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                          # blt gr[9] gr[7] -13 

#EXTEND INIT
    f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                            # gr[9] = 0
    f.write(data_movement_instruction(gr, gr, 0, 0, 15, 0, 0, 0, 1, 12, shifti_r))                   # gr[15] = gr[12] // 2
#EXTEND DIAG LOOP
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, MEM_BLOCK_SIZE*4, 9, mv))           # gr[1]=SPM[gr[9] + MEM_BLOCK_SIZE*4]
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 1, 0, 9, 14, add))                         # gr[2] = gr[9] + gr[14]

    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 2, 15, sub))                         # gr[2] = gr[2] - gr[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 1, 2, sub))                          # gr[2] = gr[1] - gr[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    #early exits: offset < 0 || v >= pattern len || h >= text end
    f.write(data_movement_instruction(0, 0, 0, 0, 9, 0, 1, 0, 1, 0, blt))                            # blt gr[1] gr[0]  9
    f.write(data_movement_instruction(0, 0, 0, 0, 9, 0, 1, 0, 1, 0, blt))                            # blt gr[1] gr[0]  9
    f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 8, bge))                            # bge gr[2] gr[8]  8
    f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 8, bge))                            # bge gr[2] gr[8]  8
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 1, 13, bge))                           # bge gr[1] gr[13] 7
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 1, 13, bge))                           # bge gr[1] gr[13] 7
#EXTEND MATCH LOOP
    f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, 1, 2, addi))                         # gr[2] = gr[2] + 1
    f.write(data_movement_instruction(gr, SPM, 0, 0, 3, 0, 0, 0, SWIZZLED_PATTERN_START, 2, mvi))    # gr[3] = SPM[gr[2]+PATTERN_START]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, 1, 1, addi))                         # gr[1] = gr[1] + 1
    f.write(data_movement_instruction(gr, SPM, 0, 0, 5, 0, 0, 0, SWIZZLED_TEXT_START, 1, mvi))       # gr[5] = SPM[gr[1]+TEXT_START]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, -4, 0, 1, 0, 3, 5, beq))                           # beq gr[3] gr[5] -4
    f.write(data_movement_instruction(0, 0, 0, 0, -4, 0, 1, 0, 3, 5, beq))                           # beq gr[3] gr[5] -4
#FINISH EXTEND MATCH LOOP
    f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, 1, 1, subi))                         # gr[1] = gr[1] - 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, 1, 9, addi))                         # gr[9] = gr[9] + 1
    f.write(data_movement_instruction(SPM, gr, 0, 0, MEM_BLOCK_SIZE*4, 9, 0, 0, 1, 0, mv))           # SPM[gr[9] + MEM_BLOCK_SIZE*4]=gr[1]
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                          # blt gr[9] gr[7] -13 
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                          # blt gr[9] gr[7] -13 
    
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                           # gr[10] = 1
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                           # gr[14] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt

    #jump all the way to top. TODO for multiblocks we need to reset pointers and such
    f.write(data_movement_instruction(0, 0, 0, 0, -32, 0, 0, 0, 0, 0, beq))                          # beq 0 0 -32
    f.write(data_movement_instruction(0, 0, 0, 0, -32, 0, 0, 0, 0, 0, beq))                          # beq 0 0 -32 


    f.close()



if not os.path.exists("instructions/wfa"):
    os.makedirs("instructions/wfa")
wfa_compute()
wfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
