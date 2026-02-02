import sys
import os
from utils import *
from opcodes import *
from math import log

SPM_BANDWIDTH = 2 # in words
PE_ALIGN_SYNC = 9 + 5
COMPUTE_LOOP_NEXT = 0
N_PES = 4
MIN_INT = -99
N_WFS = 5
MAX_WF_LEN = 4096
MAX_WF_LEN_LG2 = int(log(MAX_WF_LEN, 2)+1e-9) # in words
MAGIC_MASK_BITS = 8
#locations in PE ctrl
INIT_WF = 2
PE_ALIGN_SYNC = INIT_WF + 6
# locations in compute
COMPUTE_H = 0
COMPUTE_D = COMPUTE_H + SPM_BANDWIDTH // 2 + 1 #1 is halts
COMPUTE_I = COMPUTE_D + SPM_BANDWIDTH // 2 + 1 #1 is halts
#MEMORY LOCATIONS
BANK_SIZE = 1024
MEM_BLOCK_SIZE = 32 # in words
MEM_BLOCK_SIZE_LG2 = int(log(MEM_BLOCK_SIZE, 2)+1e-9) # in words
PADDING_SIZE = 30 # in words, added at end of each mem_block
BLOCK_0_START = 0
BLOCK_1_START = MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE
PATTERN_START = BLOCK_1_START + MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE
SEQ_LEN_ALLOC = (BANK_SIZE-PATTERN_START) // 2
TEXT_START = PATTERN_START + SEQ_LEN_ALLOC
SWIZZLED_PATTERN_START = PATTERN_START << 2 # need to reverse swizzle to hit 226 at the start
SWIZZLED_TEXT_START = TEXT_START << 2 
ALIGN_B0_PC = 7 + 6
ALIGN_B1_PC = 58
EXTRA_O_LOAD_ADDR = 7 * MEM_BLOCK_SIZE



# dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), flag_2, flag_3, imm/reg_1, reg_1(++), opcode
def wfa_main_instruction():
    
    f = InstructionWriter("instructions/wfa/main_instruction.txt");

    def loadSpmRegMapped(prepad_len, postpad_len, affineInd, wf_i_offset, isO):
        '''
        Pre:
            gr[4] = diags per PE
            gr[6] = diags to execute this block
            gr[3] = current_wf_i
            gr[1] = SPM row base
            gr[9] = block_iter (temporary increment already applied)
            gr[10]= next_block_start
            gr[12]= wavefront len
        Post:
            gr[1] preserved, gr[2]/gr[5]/gr[11] destroyed
        '''
        # gr[11] = gr[3] - wf_i_offset (mod N_WFS)
        f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 3, 0, mv))                        # gr[11]=gr[3]
        for _ in range(wf_i_offset):
            f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 1, 11, subi))                 # gr[11]--
            f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 11, 0, bge))                     # if gr[11] >= 0 skip reset
            f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, N_WFS - 1, 0, si))             # gr[11]=N_WFS-1

        # gr[11] = gr[11] * MAX_WF_LEN (power of 2)
        f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, MAX_WF_LEN_LG2, 11, shifti_l))    # gr[11]=gr[11]<<lg2(MAX_WF_LEN)

        # gr[2] = gr[11] * 3
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 11, add))                      # gr[2]=gr[11] + gr[11]
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 2, add))                       # gr[2]+=gr[11]

        # gr[2] = affineInd * MAX_WF_LEN
        if affineInd == 0:
            pass
        elif affineInd == 1:
            f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, MAX_WF_LEN, 2, addi))          # gr[2]+=MAX_WF_LEN
        else:
            f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, MAX_WF_LEN, 2, addi))          # gr[2]+=MAX_WF_LEN
            f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, MAX_WF_LEN, 2, addi))          # gr[2]+=MAX_WF_LEN


        # if isO: gr[5]=gr[2] (wf start for bounds)
        if isO:
            f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 2, 0, mv))                      # gr[5]=gr[2]

        # gr[11] = gr[9] * MEM_BLOCK_SIZE; gr[2] += gr[11]
        f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, MEM_BLOCK_SIZE_LG2, 9, shifti_l)) # gr[11]=gr[9]<<lg2(MEM_BLOCK_SIZE)
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 2, add))                        # gr[2]+=gr[11]

        # Extra O load for EXTRA_O_LOAD_ADDR
        if isO:
            f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 5, 2, subi))                  # gr[11]=gr[2]-5

            for pe_i in range(N_PES):
                # value 0
                f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 1, 0, 11, 5, blt))                 # if gr[11] < gr[5] -> MIN_INT
                f.write(data_movement_instruction(SPM, S2, 0, 0, EXTRA_O_LOAD_ADDR + BANK_SIZE * pe_i, 10, 0, 0, 0, 11, mv)) # SPM[...] = S2[gr[11]]
                f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                 # skip MIN_INT write
                f.write(data_movement_instruction(SPM, 0, 0, 0, EXTRA_O_LOAD_ADDR + BANK_SIZE * pe_i, 10, 0, 0, MIN_INT, 0, si)) # SPM[...] = MIN_INT

                f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 1, 11, addi))             # gr[11]++
                # value 1
                f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 1, 0, 11, 5, blt))                 # if gr[11] < gr[5] -> MIN_INT
                f.write(data_movement_instruction(SPM, S2, 0, 0, EXTRA_O_LOAD_ADDR + BANK_SIZE * pe_i + 1, 10, 0, 0, 0, 11, mv)) # SPM[...] = S2[gr[11]]
                f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                 # skip MIN_INT write
                f.write(data_movement_instruction(SPM, 0, 0, 0, EXTRA_O_LOAD_ADDR + BANK_SIZE * pe_i + 1, 10, 0, 0, MIN_INT, 0, si)) # SPM[...] = MIN_INT

                f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 1, 11, subi))             # gr[11]--
                f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 4, 11, add))              # gr[11]+=gr[4]

        # if first block, prepad + first mvdq
        f.write(data_movement_instruction(0, 0, 0, 0, prepad_len + 15, 0, 1, 0, 9, 0, bne))             # if gr[9] != 0 jump to else
        for j in range(prepad_len):
            f.write(data_movement_instruction(SPM, 0, 0, 0, j, 1, 0, 0, MIN_INT, 0, si))               # prepad MIN_INT
        f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 1, 6, add))                        # gr[5]=gr[1]+gr[6]
        f.write(data_movement_instruction(SPM, S2, 0, 0, prepad_len, 1, 0, 0, 0, 2, mvdq))             # SPM[gr[1]+prepad_len] = S2[gr[2]]
        f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, prepad_len, 6, subi))             # gr[11]=gr[6]-prepad_len
        f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 11, 0, blt))                         # if gr[11] < 0 skip sub
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, prepad_len, 2, subi))              # gr[2]-=prepad_len
        f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 2, 0, mv))                        # gr[11]=gr[2]
        for pe_i in range(1, N_PES):
            auto_inc_0 = 1 if pe_i == N_PES - 1 else 0
            f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 4, 11, add))                  # gr[11]+=gr[4]
            f.write(data_movement_instruction(SPM, S2, 0, auto_inc_0, BANK_SIZE * pe_i, 1, 0, 0, 0, 11, mvdq))  # SPM[BANK_SIZE*pe_i + gr[1]] = S2[gr[11]]
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 8, 2, addi))                       # gr[2]+=8
        f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, 0, 0, jump))                         # jump to loop start

        # else branch setup
        f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 1, 6, add))                        # gr[5]=gr[1]+gr[6]
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, prepad_len, 2, subi))              # gr[2]-=prepad_len

        # main loop: while gr[1] < gr[5]
        f.write(data_movement_instruction(0, 0, 0, 0, 13, 0, 1, 0, 1, 5, bge))                         # if gr[1] >= gr[5] exit
        f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 2, 0, mv))                        # gr[11]=gr[2]
        for pe_i in range(N_PES):
            auto_inc_0 = 1 if pe_i == N_PES - 1 else 0
            f.write(data_movement_instruction(SPM, S2, 0, auto_inc_0, BANK_SIZE * pe_i, 1, 0, 0, 0, 11, mvdq))  # SPM[BANK_SIZE*pe_i + gr[1]] = S2[gr[11]]
            f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 4, 11, add))                  # gr[11]+=gr[4]
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 8, 2, addi))                       # gr[2]+=8
        f.write(data_movement_instruction(0, 0, 0, 0, -11, 0, 0, 0, 0, 0, jump))                       # loop

        # restore gr[1]
        f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 5, 6, sub))                        # gr[1]=gr[5]-gr[6]
    #begining of time magic
    f.write(write_magic(4));

    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0

    #We start with wf_len = 5; score = 4
    f.write(data_movement_instruction(gr, 0, 0, 0, 12, 0, 0, 0, 5, 0, si))                           # gr[12] = 5

    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0

#LOOP PROCESS_WF
    #calc num blocks
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2+MEM_BLOCK_SIZE_LG2, 12, shifti_r)) # gr[7] = gr[12] // MEM_BLOCK_SIZE // 4
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 1, 7, addi))                         # gr[7]+=1
    #set current block count to 0
    f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, -1, 0, si))                           # gr[9] = -1
    #BLOCK INIT
    #current block
    f.write(data_movement_instruction(gr, 0, 0, 0, 8, 0, 0, 0, BLOCK_1_START, 0, si))                # gr[8] = BLOCK_1_START
    #next block
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, BLOCK_0_START, 0, si))               # gr[10] = BLOCK_0_START
    #load o, m, i, d inputs to next block
    #magic(1) setup (skip in C++)
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 1, 9, addi))                          # gr[9]+=1
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 2, 12, shifti_r))                      # gr[4]=gr[12]>>2
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 1, 4, addi))                           # gr[4]+=1
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, MEM_BLOCK_SIZE_LG2, 9, shifti_l))     # gr[11]=gr[9]<<lg2(MEM_BLOCK_SIZE)
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 4, 11, sub))                           # gr[2]=gr[4]-gr[11]
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, MEM_BLOCK_SIZE, 0, si))                 # gr[6]=MEM_BLOCK_SIZE
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 2, 6, bge))                              # if gr[2] >= gr[6] skip mv
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 2, 0, mv))                             # gr[6]=gr[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 6, 0, bge))                              # if gr[6] >= gr[0] skip zero
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 0, 0, si))                              # gr[6]=0
    # ISA O/M/I/D loads (skip in C++)
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 10, 0, mv))                            # gr[1]=gr[10]
    loadSpmRegMapped(3, 5, 2, 3, True)                                                                  # O
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, MEM_BLOCK_SIZE, 10, addi))              # gr[1]=gr[10]+1*MEM_BLOCK_SIZE
    loadSpmRegMapped(2, 2, 2, 1, False)                                                                 # M
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 2*MEM_BLOCK_SIZE, 10, addi))            # gr[1]=gr[10]+2*MEM_BLOCK_SIZE
    loadSpmRegMapped(2, 0, 1, 0, False)                                                                 # I
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 3*MEM_BLOCK_SIZE, 10, addi))            # gr[1]=gr[10]+3*MEM_BLOCK_SIZE
    loadSpmRegMapped(0, 2, 0, 0, False)                                                                 # D
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 1, 9, subi))                           # gr[9]-=1
    #flip blocks
    f.write(data_movement_instruction(gr, 0, 0, 0, 8, 0, 0, 0, BLOCK_0_START, 0, si))                 # gr[8] = BLOCK_0_START
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, BLOCK_1_START, 0, si))                 # gr[10] = BLOCK_1_START
    #set PE to INIT_WF
    f.write(data_movement_instruction(gr, gr, 0, 0, INIT_WF, 0, 0, 0, 0, 0, set_PC))                 # PE_PC = INIT_WF
    #send over the wf
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 12, 0, mv))                    # out = gr[12]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 12, 0, mv))                    # out = gr[12]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 12, 0, mv))                    # out = gr[12]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 12, 0, mv))                    # out = gr[12]
    #increment count
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 1, 9, addi))                         # gr[9]+=1
    #optional, branch and skip some extra comps for wf smaller than 128

#BLOCK LOOP
    #load inputs o,m,i,d to NEXT_BLOCK magic(2)
    #magic(1) setup (skip in C++)
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 1, 9, addi))                          # gr[9]+=1
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 2, 12, shifti_r))                      # gr[4]=gr[12]>>2
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 1, 4, addi))                           # gr[4]+=1
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, MEM_BLOCK_SIZE_LG2, 9, shifti_l))     # gr[11]=gr[9]<<lg2(MEM_BLOCK_SIZE)
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 4, 11, sub))                           # gr[2]=gr[4]-gr[11]
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, MEM_BLOCK_SIZE, 0, si))                 # gr[6]=MEM_BLOCK_SIZE
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 2, 6, bge))                              # if gr[2] >= gr[6] skip mv
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 2, 0, mv))                             # gr[6]=gr[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 6, 0, bge))                              # if gr[6] >= gr[0] skip zero
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 0, 0, si))                              # gr[6]=0
    # ISA O/M/I/D loads (skip in C++)
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 10, 0, mv))                            # gr[1]=gr[10]
    loadSpmRegMapped(3, 5, 2, 3, True)                                                                  # O
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, MEM_BLOCK_SIZE, 10, addi))              # gr[1]=gr[10]+1*MEM_BLOCK_SIZE
    loadSpmRegMapped(2, 2, 2, 1, False)                                                                 # M
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 2*MEM_BLOCK_SIZE, 10, addi))            # gr[1]=gr[10]+2*MEM_BLOCK_SIZE
    loadSpmRegMapped(2, 0, 1, 0, False)                                                                 # I
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 3*MEM_BLOCK_SIZE, 10, addi))            # gr[1]=gr[10]+3*MEM_BLOCK_SIZE
    loadSpmRegMapped(0, 2, 0, 0, False)                                                                 # D
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 1, 9, subi))                           # gr[9]-=1
    #TODO wait lsq
    #wait pe
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))                         # bne 1 gr[13] 0
    #set PE to align next block
    #TODO since the PE will not get to this stage yet, we don't actually set pc
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, gr, 0, 0, ALIGN_B0_PC, 0, 0, 0, 0, 0, set_PC))             # PE_PC = ALIGN_B0_PC
    f.write(data_movement_instruction(0, 0, 0, 0, 1, 0, 1, 0, 0, 8, beq))                            # beq gr[0] gr[8] 1
    f.write(data_movement_instruction(gr, gr, 0, 0, ALIGN_B1_PC, 0, 0, 0, 0, 0, set_PC))             # PE_PC = ALIGN_B1_PC
    # magic(3) setup (skip in C++)
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 2, 12, shifti_r))                     # gr[4]=gr[12]>>2
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 1, 4, addi))                          # gr[4]+=1
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, MEM_BLOCK_SIZE_LG2, 9, shifti_l))    # gr[11]=gr[9]<<lg2(MEM_BLOCK_SIZE)
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0, 4, 11, sub))                          # gr[6]=gr[4]-gr[11]
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 0, mv))                           # gr[2]=gr[11]
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 1, 3, addi))                         # gr[11]=gr[3]+1
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, N_WFS, 11, bne))                      # if gr[11] != N_WFS, skip reset
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0, 0, si))                            # gr[11]=0
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, MAX_WF_LEN_LG2, 11, shifti_l))       # gr[11]=gr[11]<<lg2(MAX_WF_LEN)
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 2, add))                          # gr[2]+=gr[11]
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 2, add))                          # gr[2]+=gr[11]
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 11, 2, add))                          # gr[2]+=gr[11]
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, MEM_BLOCK_SIZE, 6, bge))                # if MEM_BLOCK_SIZE >= gr[6], skip clamp
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, MEM_BLOCK_SIZE, 0, si))                # gr[6]=MEM_BLOCK_SIZE
    #load results m,i,d of THIS_BLOCK magic(3)
    f.write(write_magic((3 << MAGIC_MASK_BITS) | 0x10));
    # Display combined inputs/outputs for debugging
    f.write(write_magic(6));
    #TODO wait lsq
    #SWAP THIS_BLOCK, NEXT_BLOCK
    f.write(data_movement_instruction(gr, gr, 0, 0, 11, 0, 0, 0, 10, 0, mv))                         # gr[11] = gr[10]
    f.write(data_movement_instruction(gr, gr, 0, 0, 10, 0, 0, 0, 8, 0, mv))                          # gr[10] = gr[8]
    f.write(data_movement_instruction(gr, gr, 0, 0, 8, 0, 0, 0, 11, 0, mv))                          # gr[8] = gr[11]
    #increment count
    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 1, 9, addi))                         # gr[9]+=1
    f.write(data_movement_instruction(gr, gr, 0, 0, -256, 0, 1, 0, 9, 7, blt))                       # blt gr[9] gr[7] -256
#END BLOCK LOOP. NEW WF
    # Calculate idx = (text_len - pattern_len) + (wf_len / 2)
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 14, 15, sub))                        # gr[1] = gr[14] - gr[15] (target_k)
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 1, 12, shifti_r))                    # gr[2] = gr[12] >> 1 (center)
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 2, add))                          # gr[1] = gr[1] + gr[2] (idx in gr[1])

    # Load M[idx] via magic(7) - reads past_wfs[write_wf_i][2][gr[1]] into gr[2]
    f.write(write_magic(7))

    # Bounds check 1: if idx < 0, skip to CONTINUE
    f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 1, 0, 1, 0, blt))                            # blt gr[1] gr[0] 3 (SKIP)

    # Bounds check 2: if idx >= wf_len, skip to CONTINUE
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 1, 0, 1, 12, bge))                           # bge gr[1] gr[12] 2 (SKIP)

    # Check if M[idx] >= text_len (exit condition)
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 1, 0, 2, 14, bge))                           # bge gr[2] gr[14] 6 (EXIT)

#CONTINUE:
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 2, 12, addi))                       # gr[12]+=2
    #increment current wavefront (gr[3] = (gr[3] + 1) mod N_WFS)
    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi))                          # gr[3] += 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, N_WFS, 3, bne))                       # if gr[3] != N_WFS, skip reset
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))                            # gr[3] = 0
    #JMP LOOP PROCESS_WF
    f.write(data_movement_instruction(0, 0, 0, 0, -510, 0, 0, 0, 0, 0, jump))                        # jump -510 (LOOP)

#EXIT:
    f.write(write_magic(5))                                                                           # magic(5) - print final state
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt

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
    #load wf size in from pe_array
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                           # gr[10] = 0
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))                # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    f.write(data_movement_instruction(gr, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv))                     # gr[12] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op

    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 12, shifti_r))                    # gr[7] = gr[12] // 4
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                           # gr[14] = 0
    f.write(data_movement_instruction(gr, gr, 1, 0, 7, 0, 0, 0, 1, 7, addi))                         # gr[7] = gr[7] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                           # No-op
    for i in range(N_PES):
        if i < pe_id:
            f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 14, 7, add))                # gr[14] = gr[14] + gr[7]
            f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                   # No-op
        else:
            f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                   # No-op
            f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                   # No-op
    def write_block_code(block_start):
        '''
        We hardcode the location of the fields in the SPM (e.g. i, d, m, o. Both input and output
        wavefronts), so we write two blocks of code. One has block_start 0 the other has
        block_start BLOCK_1_START
        '''
        f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # gr[10] = 0
        f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 12, shifti_r))                # gr[7] = gr[12] // 4

        f.write(data_movement_instruction(gr, gr, 1, 0, 7, 0, 0, 0, 1, 7, addi))                     # gr[7] = gr[7] + 1
        f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, 1, 7, addi))                     # gr[9] = gr[7] + 1

        #gr[9] = end range i.e. (gr[12]//4+1)*(peid+1) or gr[12] for the final pe
        for i in range(N_PES-1):
            if pe_id == 3:
                #not quite sure why we need the addi 1 :\ but it works! :)
                f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, 1, 12, addi))            # gr[9] = gr[12] + 1
                f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               # No-op
            else:
                if i < pe_id:
                    f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 9, 7, add))          # gr[9] = gr[9] + gr[7]
                    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))           # No-op
                else:
                    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))           # No-op
                    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))           # No-op
        #gr[9] = gr[9] - gr[14] The range before the end
        f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 9, 14, sub))                     # gr[9] = gr[9] - gr[14]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
    #if we have more work to do than one block, jump just do one block (MEM_BLOCK_SIZE < gr9)
        f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, MEM_BLOCK_SIZE, 9, blt))           # blt MEM_BLOCK_SIZE gr[9] 3
        f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, MEM_BLOCK_SIZE, 9, blt))           # blt MEM_BLOCK_SIZE gr[9] 3
        f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 9, 0, mv))                       # gr[7] = gr[9]
        f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                        # gr[9] = 0 (loop counter)
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 0, 0, beq))                      # beq 0 0 2
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 0, 0, beq))                      # beq 0 0 2
    #else
        f.write(data_movement_instruction(gr, 0, 0, 0, 7, 0, 0, 0, MEM_BLOCK_SIZE, 0, si))           # gr[7] = MEM_BLOCK_SIZE (loop counter)
        f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                        # gr[9] = 0 (loop counter)


        f.write(data_movement_instruction(gr, 0, 0, 0, 4, 0, 0, 0, 4*MEM_BLOCK_SIZE+block_start, 0, si))         # gr[4] m write
        f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 3*MEM_BLOCK_SIZE+block_start, 0, si))         # gr[3] d
        f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 2*MEM_BLOCK_SIZE+block_start, 0, si))         # gr[2] i
        f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0*MEM_BLOCK_SIZE+block_start, 0, si))        # gr[11] open
        f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 1*MEM_BLOCK_SIZE+block_start, 0, si))         # gr[1] match          
        f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 7*MEM_BLOCK_SIZE+block_start, 0, mvd))     # reg[4] = SPM[7*MEM_BLOCK_SIZE+block_start] (leftmost)


        #computation of diag start
        #TODO this will need to change for multiple blocks
        f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, 5*MEM_BLOCK_SIZE+block_start, 0, si))         # gr[5] d write
        f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 6*MEM_BLOCK_SIZE+block_start, 0, si))         # gr[6] i write
        #TODO this might optimize
        #if pe_id == 3: #fewer iterations for last PE (reduces memory traffic)
        #    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 12, 14, sub))                # gr[7] = gr[12] - gr[14]
        #    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                   # No-op
    #BLOCK_LOOP NEXT
        #Load I; No-op
        f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))         # gr[2] = gr[2] + SPM_BANDWIDTH
        f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mvd))                   # reg[12]=SPM[gr[2]]
        f.write(data_movement_instruction(reg, reg, 0, 0, 1, 0, 0, 0, 4, 0, mv))                     # reg[1] = reg[4]
        f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 5, 0, mv))                     # reg[2] = reg[5]
        #Load D; compute I
        f.write(data_movement_instruction(gr, gr, 1, 0, 11, 0, 0, 0, SPM_BANDWIDTH, 11, addi))       # gr[11] = gr[11] + SPM_BANDWIDTH
        f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 11, mvd))                   # reg[4]=SPM[gr[11]]
        f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_I, 0, 0, 0, 0, 0, set_PC))             # PE_PC = COMPUTE_I
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))         # gr[3] = gr[3] + SPM_BANDWIDTH
        f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mvd))                   # reg[16]=SPM[gr[3]]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_D, 0, 0, 0, 0, 0, set_PC))             # PE_PC = COMPUTE_D
        #Load H; compute D
        f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))         # gr[1] = gr[1] + SPM_BANDWIDTH
        f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 1, mvd))                    # reg[8]=SPM[gr[1]]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_H, 0, 0, 0, 0, 0, set_PC))             # PE_PC = COMPUTE_H
        #Write I; compute H
        f.write(data_movement_instruction(gr, gr, 1, 0, 6, 0, 0, 0, SPM_BANDWIDTH, 6, addi))         # gr[6] = gr[6] + SPM_BANDWIDTH
        f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 6, 0, 0, 24, 0, mvd))                   # SPM[gr[6]]=reg[24] //I
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        #write D; No-op
        f.write(data_movement_instruction(gr, gr, 1, 0, 5, 0, 0, 0, SPM_BANDWIDTH, 5, addi))         # gr[5] = gr[5] + SPM_BANDWIDTH
        f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 5, 0, 0, 20, 0, mvd))                   # SPM[gr[5]]=reg[20] //D
        f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, SPM_BANDWIDTH, 9, addi))         #gr[9] = gr[9] + SPM_BANDWIDTH
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        #Write H; No-op
        f.write(data_movement_instruction(gr, gr, 1, 0, 4, 0, 0, 0, SPM_BANDWIDTH, 4, addi))         # gr[4] = gr[4] + SPM_BANDWIDTH
        f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 4, 0, 0, 28, 0, mvd))                   # SPM[gr[4]]=reg[28] //M
        f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                      # blt gr[9] gr[7] -13 
        f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                      # blt gr[9] gr[7] -13 

    #EXTEND INIT
        f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                        # gr[9] = 0
        f.write(data_movement_instruction(gr, gr, 0, 0, 15, 0, 0, 0, 1, 12, shifti_r))               # gr[15] = gr[12] // 2
    #EXTEND DIAG LOOP
        f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, 4*MEM_BLOCK_SIZE+block_start, 9, mv))       # gr[1]=SPM[gr[9] + 4*MEM_BLOCK_SIZE+block_start]
        f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 1, 0, 9, 14, add))                     # gr[2] = gr[9] + gr[14]

        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 2, 15, sub))                     # gr[2] = gr[2] - gr[15]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 1, 2, sub))                      # gr[2] = gr[1] - gr[2]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        #early exits: offset < 0 || v >= pattern len || h >= text end
        f.write(data_movement_instruction(0, 0, 0, 0, 9, 0, 1, 0, 1, 0, blt))                        # blt gr[1] gr[0]  9
        f.write(data_movement_instruction(0, 0, 0, 0, 9, 0, 1, 0, 1, 0, blt))                        # blt gr[1] gr[0]  9
        f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 8, bge))                        # bge gr[2] gr[8]  8
        f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 8, bge))                        # bge gr[2] gr[8]  8
        f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 1, 13, bge))                       # bge gr[1] gr[13] 7
        f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 1, 13, bge))                       # bge gr[1] gr[13] 7
    #EXTEND MATCH LOOP
        f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, 1, 2, addi))                     # gr[2] = gr[2] + 1
        f.write(data_movement_instruction(gr, SPM, 0, 0, 3, 0, 0, 0, SWIZZLED_PATTERN_START, 2, mvi))# gr[3] = SPM[gr[2]+PATTERN_START]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        #OPTIMIZATION Should be able to hoist this into the branches. Will give a good deal of perf
        f.write(data_movement_instruction(gr, SPM, 0, 0, 5, 0, 0, 0, SWIZZLED_TEXT_START, 1, mvi))   # gr[5] = SPM[gr[1]+TEXT_START]
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, 1, 1, addi))                     # gr[1] = gr[1] + 1
        f.write(data_movement_instruction(0, 0, 0, 0, -4, 0, 1, 0, 3, 5, beq))                       # beq gr[3] gr[5] -4
        f.write(data_movement_instruction(0, 0, 0, 0, -4, 0, 1, 0, 3, 5, beq))                       # beq gr[3] gr[5] -4
    #FINISH EXTEND MATCH LOOP
        f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, 1, 1, subi))                     # gr[1] = gr[1] - 1
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # No-op
        f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, 1, 9, addi))                     # gr[9] = gr[9] + 1
        f.write(data_movement_instruction(SPM, gr, 0, 0, 4*MEM_BLOCK_SIZE+block_start, 9, 0, 0, 1, 0, mv))       # SPM[gr[9] + 4*MEM_BLOCK_SIZE+block_start]=gr[1]
        f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                      # blt gr[9] gr[7] -13 
        f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))                      # blt gr[9] gr[7] -13 
        
        f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # gr[10] = 1
        f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, MEM_BLOCK_SIZE, 14, addi))       # gr[14]+= MEM_BLOCK_SIZE
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # halt
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # halt

    write_block_code(BLOCK_0_START)
    write_block_code(BLOCK_1_START)


    f.close()


if not os.path.exists("instructions/wfa"):
    os.makedirs("instructions/wfa")
wfa_compute()
wfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
