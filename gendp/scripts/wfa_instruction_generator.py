import sys
import os
import ctrl_opcodes

##MEMORY DESTS
#reg = 0
#gr = 1
#SPM = 2
#comp_ib = 3
#ctrl_ib = 4
#in_buf = 5
#out_buf = 6
#in_port = 7
#in_instr = 8
#out_port = 9
#out_instr = 10
#fifo = [11, 12]
#
##DATA MOVEMENT OPCODES
#add = 0
#sub = 1
#addi = 2
#set_8 = 3
#si = 4
#mv = 5
#add_8 = 6
#addi_8 = 7
#bne = 8
#beq = 9
#bge = 10
#blt = 11
#jump = 12
#set_PC = 13
#none = 14
#halt = 15
#shift_r = 16 #TODO implement
#shift_l = 17 #TODO implement
#MIN = 18 #TODO implement
#AND = 19 #TODO implement
## these instruction tags here are for data movement
## use sys_def.h for compute tags


MEM_BLOCK_SIZE = 1024 # in words
SPM_BANDWIDTH = 4 # in words





def compute_instruction(op_0, op_1, op_2, in_addr_0, in_addr_1, in_addr_2, in_addr_3, in_addr_4, in_addr_5, out_addr):
    instr = "0" * 14 \
            + "{:0>5b}".format(op_0) \
            + "{:0>5b}".format(op_1) \
            + "{:0>5b}".format(op_2) \
            + "{:0>5b}".format(in_addr_0) \
            + "{:0>5b}".format(in_addr_1) \
            + "{:0>5b}".format(in_addr_2) \
            + "{:0>5b}".format(in_addr_3) \
            + "{:0>5b}".format(in_addr_4) \
            + "{:0>5b}".format(in_addr_5) \
            + "{:0>5b}".format(out_addr)
    value = int(instr, 2)
    return hex(value) + "\n"
    
    

def data_movement_instruction(dest, src, reg_immBar_0, reg_auto_increase_0, imm_0, reg_0,
                              reg_immBar_1, reg_auto_increase_1, imm_1, reg_1, opcode):
    instr = "0" * 20 \
            + "{:0>4b}".format(dest) \
            + "{:0>4b}".format(src) \
            + "{:0>1b}".format(reg_immBar_0) \
            + "{:0>1b}".format(reg_auto_increase_0) \
            + "{:0>10b}".format(imm_0 & 0x3ff) \
            + "{:0>4b}".format(reg_0) \
            + "{:0>1b}".format(reg_immBar_1) \
            + "{:0>1b}".format(reg_auto_increase_1) \
            + "{:0>10b}".format(imm_1 & 0x3ff) \
            + "{:0>4b}".format(reg_1) \
            + "{:0>4b}".format(opcode)
    value = int(instr, 2)
    return hex(value) + "\n"
    
    
# dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), flag_2, flag_3, imm/reg_1, reg_1(++), opcode
def bsw_main_instruction():
    
    f = open("instructions/bsw/main_instruction.txt", "w")

    
    # Dump in the instructions
    for i in range(WFA_COMPUTE_INSTRUCTION_NUM):
        f.write(data_movement_instruction(out_port, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv)); # out = instr[i]

    #INIT
    #reg[0] is edit distance, reg[1-4] are n_iters for pe 0-4
    f.write(data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, 0, 0, si))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op

    #ALIGN_LOOP
    #TODO implement these instructions
    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 1, 0, shift_l))                          # gr[5] = gr[0] * 2 = gr[0] << 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 6, 0, 0, 0x3, 0, 0, AND))                            # gr[6] = gr[0] % 4 = gr[0] & 0x3
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 5, shift_r))                          # gr[7] = gr[5] // 4
    f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, 0, 6, beq))                               # beq 0 gr[6] 5
  #if wf_len % 4 == 1:
    #TODO BROADCAST GO SIGNAL
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 0, 0, 0, 0, beq))                                # beq 0 0 4
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
  #else wf_len % 4 == 3:
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 1, 7, addi))                             # out = gr[7] + 1
    f.write(data_movement_instruction(out, 0, 0, 0, 0, 0, 0, 0, 0, 7, mv))                               # out = gr[7]
  #endif
    #TODO INVOKE MEMORY LOAD MAGIC
    #TODO BROADCAST GO SIGNAL
    #TODO WAIT FOR PE_DONE
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 0, addi))                           # gr[0]++ (ed++)
    #JMP ALIGN_LOOP

    f.close()

def bsw_compute():

    f = open("instructions/bsw/compute_instruction.txt", "w")
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
    #f.write(compute_instruction(COPY, COPY, INVALID, 1, 0, 0, 0, 0, 0, 0))
    #free reg 0+,12+
    f.close()


    
def pe_0_instruction():
    
    f = open("instructions/bsw/pe_0_instruction.txt", "w")
    #TODO I am assuming that writes to the register file from these must be done to adjacent blocks
    #of register. We'll at very least need something to tell POA not to write the full block. Will
    #require instruction update


#INITIALIZATION NEXT
    #NOTES
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
    #gr[0] points directly to m_r1. first m_r0 is implicitly 0
    for i in range(SPM_BANDWIDTH):
        f.write(data_movement_instruction(gr, 0, 0, 0, i, 0, 0, 0, 0, 0, si))                           # gr[0-4] = 0
    #COPY FIRST PART OF BLOCK LOOP SKIP WRITE THOUGH
    #Load DELETIONS [0,3]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 0, mv))                            # reg[4]=SPM[gr[0]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 0, 0, 0, 0, SPM_BANDWIDTH, 0, addi))              # gr[0] = gr[0] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mv))                           # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))              # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0,0,0,0,COMPUTE_LOOP_NEXT+SPM_BANDWIDTH,0,0,0,0,0,set_PC))        # PE_PC = COMPUTE_LOOP_NEXT + SPM_BANDWIDTH
    #Load INSERTIONS [4,5]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))                           # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))              # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Load H [6,7]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 2, mv))                            # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))              # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op

#BLOCK_LOOP NEXT
    #Load DELETIONS [0,3]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 0, mv))                            # reg[4]=SPM[gr[0]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 0, 0, 0, 0, SPM_BANDWIDTH, 0, addi))              # gr[0] = gr[0] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 0, 0, 3, mv))                           # reg[16]=SPM[gr[3]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 3, 0, 0, 0, SPM_BANDWIDTH, 3, addi))              # gr[3] = gr[3] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Load INSERTIONS [4,5]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))                           # reg[12]=SPM[gr[2]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 2, 0, 0, 0, SPM_BANDWIDTH, 2, addi))              # gr[2] = gr[2] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Load H [6,7]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 2, mv))                            # reg[8]=SPM[gr[1]]
    f.write(data_movement_instruction(reg, reg, 1, 0, 1, 0, 0, 0, SPM_BANDWIDTH, 1, addi))              # gr[1] = gr[1] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_LOOP_NEXT, 0, 0, 0, 0, 0, set_PC))            # PE_PC = COMPUTE_LOOP_NEXT
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    #Write H [8,13]
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 4, 0, 0, 20, 0, mv))                           # SPM[gr[4]]=reg[20] //M
    f.write(data_movement_instruction(reg, reg, 1, 0, 4, 0, 0, 0, SPM_BANDWIDTH, 4, addi))              # gr[4] = gr[4] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 5, 0, 0, 24, 0, mv))                           # SPM[gr[5]]=reg[24] //D
    f.write(data_movement_instruction(reg, reg, 1, 0, 5, 0, 0, 0, SPM_BANDWIDTH, 5, addi))              # gr[5] = gr[5] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 6, 0, 0, 28, 0, mv))                           # SPM[gr[6]]=reg[28] //I
    f.write(data_movement_instruction(reg, reg, 1, 0, 6, 0, 0, 0, SPM_BANDWIDTH, 6, addi))              # gr[6] = gr[6] + SPM_BANDWIDTH
    f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 1, blt))                             # blt gr[9] gr[7] -13 #TODO figure out how to autoincrease.
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op

    #TODO HALT. Figure out what's there. How to add this
    
        


















    f.write(data_movement_instruction(reg, SPM, 0, 0, 3, 0, 0, 1, 0, 1, mv)) # reg[3] =SPM[gr[1]++]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 1, 0, 2, mv)) # reg[4] =SPM[gr[2]++]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 5, 0, 0, 1, 0, 3, mv)) # reg[5] =SPM[gr[3]++]
    #write the output from compute
    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 4, 0, 0, 29, 0, mv)) # SPM[gr[4]++]=reg[29] //M
    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 5, 0, 0, 30, 0, mv)) # SPM[gr[5]++]=reg[30] //D
    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 6, 0, 0, 31, 0, mv)) # SPM[gr[5]++]=reg[31] //I
    #update loop counter
    f.write(data_movement_instruction(0, 0, 1, 0, 9, 0, 0, 0, 1, 9, addi)) # gr[9]++
    #jump back to tile
    f.write(data_movement_instruction(0, 0, 0, 0, 12, 0, 1, 0, 9, 8, beq)) # beq gr[9]==gr[8] TILE0

    #TRANSITION BETWEEN TILES

    #REMAINDER_LOOP
    #TODO copy the tile loop here, but branching will check the tilesize instead of blocksize





    #Stall one to get everything going at the right time
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    #LOAD _, _, _, _, _, WRITE m, 
    #deletion at score -E
    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv)) # 0 reg[5] = in
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 31, mv)) # out = reg[31] I

    #insertion at score-E
    f.write(data_movement_instruction(reg, in_port, 1, 0, 4, 0, 0, 0, 0, 0, mv)) # 1 reg[4] = in
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 30, mv)) # out = reg[30] D

    #match at score-2E
    f.write(data_movement_instruction(reg, in_port, 0, 0, 3, 0, 0, 0, 0, 0, mv)) # 2 reg[3] = in
    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 29, mv)) # out = reg[29] M

    #match at score-4E
    f.write(data_movement_instruction(reg, in_port, 1, 0, 2, 0, 0, 0, 0, 0, mv)) # 3 reg[2] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # stall

    #pass data from start to out
    for i in range(2):
        f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC)) # set PC to 0
    f.write(data_movement_instruction(in_port, out_port, 0, 0, 0, 0, 0, 0, 0, 0, mv)) # out = in
    f.write(data_movement_instruction(0, 0, 0, 0, 1, 0, 0, 0, 0, 0, jump)) # jump back to beginning

    f.close()

def pe_1_instruction():
    
    f = open("instructions/bsw/pe_1_instruction.txt", "w")
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              0
    for i in range(4):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 21, 0, mv))                          # out = reg[21]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 24, 0, 0, 0, 0, 0, mv))                           # reg[24] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 22, 0, mv))                          # out = reg[22]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 2, 0, 0, 0, 0, 0, mv))                            # reg[2] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 24, 0, mv))                          # out = reg[24]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 3, 0, 0, 0, 0, 0, mv))                            # reg[3] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 2, 0, mv))                           # out = reg[2]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv))                            # reg[4] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 3, 0, mv))                           # out = reg[3]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv))                            # reg[5] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 4, 0, mv))                           # out = reg[4]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv))                             # gr[1] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 5, 0, mv))                           # out = reg[5]
    f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, 0, 0, 0, 0, 0, 0, mv))                       # ir[0] = in
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 5, 0, mv))                            # out = gr[1]
    for i in range(BSW_COMPUTE_INSTRUCTION_NUM-1):
        f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, i+1, 0, 0, 0, 0, 0, mv))                 # ir[i+1] = in
        f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv))                  # out = ir[i]
    f.write(data_movement_instruction(reg, reg, 0, 0, 26, 0, 0, 0, 4, 0, mv))                               # reg[26] = reg[4]
    f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, 28, 0, mv))                     # out = ir[28]
    f.write(data_movement_instruction(reg, reg, 0, 0, 27, 0, 0, 0, 4, 0, mv))                               # reg[27] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 28, 0, 0, 0, 4, 0, mv))                               # reg[28] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 29, 0, 0, 0, 4, 0, mv))                               # reg[29] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 30, 0, 0, 0, 0, 0, mv))                               # reg[30] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    for i in range(4):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             47
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                                 # reg[14] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 8, 0, mv))                           # out = reg[8]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                 # reg[10] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 6, 0, mv))                           # out = reg[6]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                 # reg[15] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 7, 0, mv))                           # out = reg[7]
    f.write(data_movement_instruction(reg, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                                  # reg[9] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op

    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 8, 0, mv))                           # out = reg[8]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 6, 0, mv))                           # out = reg[6]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 7, 0, mv))                           # out = reg[7]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    for i in range(13):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              75
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             76
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 14, 0, 0, 0, 0, 0, mv))                           # reg[14] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 8, 0, mv))                           # out = reg[8]
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                 # reg[10] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 14, 0, mv))                          # out = reg[14]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                 # reg[15] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 6, 0, mv))                           # out = reg[6]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                                  # reg[9] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 7, 0, mv))                           # out = reg[7]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op

    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 14, 0, 0, 0, 0, 0, mv))                           # reg[14] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 8, 0, mv))                           # out = reg[8]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 14, 0, mv))                          # out = reg[14]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 6, 0, mv))                           # out = reg[6]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 7, 0, mv))                           # out = reg[7]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op

    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 14, 0, 0, 0, 0, 0, mv))                           # reg[14] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    for i in range(15):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              108
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             109
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))                                # set 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                                  # gr[10] = 1
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             113
    
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 0, set_PC))                                # set 5
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))                           # reg[11] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 11, 0, mv))                          # out = reg[11]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv))                           # reg[12] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 14, 0, mv))                          # out = reg[14]
    for i in range(2):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv))                           # reg[13] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 13, 0, mv))                          # out = reg[13]
    for i in range(2):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             121
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 0, 0, 0, 0, set_PC))                               # set 11
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             124
        
    f.write(data_movement_instruction(0, 0, 0, 0, 15, 0, 0, 0, 0, 0, set_PC))                               # set 15
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(gr, reg, 0, 0, 10, 0, 0, 0, 20, 0, mv))                               # gr[10] = reg[20]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             130
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 18, 0, 0, 0, 0, 0, mv))                           # reg[18] = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                  # gr[10] = 0
    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv))                           # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 20, 0, 0, 0, 0, 0, mv))                           # reg[20] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 24, 0, 0, 0, 0, 0, set_PC))                               # set 24
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 23, 0, 0, 0, 0, 0, mv))                           # reg[23] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 24, 0, mv))                          # out = reg[24]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 27, 0, mv))                          # out = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 26, 0, mv))                          # out = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 28, 0, mv))                          # out = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 29, 0, mv))                          # out = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 30, 0, mv))                          # out = reg[30]
    for i in range(14):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    f.close()
    
def pe_2_instruction():
    
    f = open("instructions/bsw/pe_2_instruction.txt", "w")

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              0
    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 21, 0, mv))                          # out = reg[21]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 24, 0, 0, 0, 0, 0, mv))                           # reg[24] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 22, 0, mv))                          # out = reg[22]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 2, 0, 0, 0, 0, 0, mv))                            # reg[2] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 24, 0, mv))                          # out = reg[24]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 3, 0, 0, 0, 0, 0, mv))                            # reg[3] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 2, 0, mv))                           # out = reg[2]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv))                            # reg[4] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 3, 0, mv))                           # out = reg[3]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv))                            # reg[5] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 4, 0, mv))                           # out = reg[4]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv))                             # gr[1] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 5, 0, mv))                           # out = reg[5]
    f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, 0, 0, 0, 0, 0, 0, mv))                       # ir[0] = in
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 5, 0, mv))                            # out = gr[1]
    for i in range(BSW_COMPUTE_INSTRUCTION_NUM-1):
        f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, i+1, 0, 0, 0, 0, 0, mv))                 # ir[i+1] = in
        f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv))                  # out = ir[i]
    f.write(data_movement_instruction(reg, reg, 0, 0, 26, 0, 0, 0, 4, 0, mv))                               # reg[26] = reg[4]
    f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, 28, 0, mv))                     # out = ir[28]
    f.write(data_movement_instruction(reg, reg, 0, 0, 27, 0, 0, 0, 4, 0, mv))                               # reg[27] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 28, 0, 0, 0, 4, 0, mv))                               # reg[28] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 29, 0, 0, 0, 4, 0, mv))                               # reg[29] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 30, 0, 0, 0, 0, 0, mv))                               # reg[30] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    for i in range(2):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    for i in range(8):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             47
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                                 # reg[14] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 8, 0, mv))                           # out = reg[8]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                 # reg[10] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 6, 0, mv))                           # out = reg[6]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                 # reg[15] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 7, 0, mv))                           # out = reg[7]
    f.write(data_movement_instruction(reg, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                                  # reg[9] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op

    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    for i in range(25):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              75
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    for i in range(8):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             76
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 14, 0, 0, 0, 0, 0, mv))                           # reg[14] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 8, 0, mv))                           # out = reg[8]
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                 # reg[10] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 14, 0, mv))                          # out = reg[14]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                 # reg[15] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 6, 0, mv))                           # out = reg[6]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                                  # reg[9] = 0
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 7, 0, mv))                           # out = reg[7]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op

    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 14, 0, 0, 0, 0, 0, mv))                           # reg[14] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    for i in range(29):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              108
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             109
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))                                # set 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                                  # gr[10] = 1
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             113
    
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 0, set_PC))                                # set 5
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))                           # reg[11] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 11, 0, mv))                          # out = reg[11]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv))                           # reg[12] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 14, 0, mv))                          # out = reg[14]
    for i in range(2):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv))                           # reg[13] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 13, 0, mv))                          # out = reg[13]
    for i in range(2):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             121
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 0, 0, 0, 0, set_PC))                               # set 11            
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             124
        
    f.write(data_movement_instruction(0, 0, 0, 0, 15, 0, 0, 0, 0, 0, set_PC))                               # set 15            
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(gr, reg, 0, 0, 10, 0, 0, 0, 20, 0, mv))                               # gr[10] = reg[20]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             130
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                  # gr[10] = 0        
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 24, 0, mv))                          # out = reg[24]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 27, 0, mv))                          # out = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 26, 0, mv))                          # out = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 28, 0, mv))                          # out = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 29, 0, mv))                          # out = reg[29]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 18, 0, 0, 0, 0, 0, mv))                           # reg[18] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 30, 0, mv))                          # out = reg[30]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv))                           # reg[19] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 18, 0, mv))                          # out = reg[18]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 20, 0, 0, 0, 0, 0, mv))                           # reg[20] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 19, 0, mv))                          # out = reg[19]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 20, 0, mv))                          # out = reg[20]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 21, 0, mv))                          # out = reg[21]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 23, 0, 0, 0, 0, 0, mv))                           # reg[23] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 22, 0, mv))                          # out = reg[22]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 23, 0, mv))                          # out = reg[23]
    for i in range(12):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.close()
    
def pe_3_instruction():
    
    f = open("instructions/bsw/pe_3_instruction.txt", "w")

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              0
    for i in range(8):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 21, 0, mv))                          # out = reg[21]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 24, 0, 0, 0, 0, 0, mv))                           # reg[24] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 22, 0, mv))                          # out = reg[22]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 2, 0, 0, 0, 0, 0, mv))                            # reg[2] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 24, 0, mv))                          # out = reg[24]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 3, 0, 0, 0, 0, 0, mv))                            # reg[3] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 2, 0, mv))                           # out = reg[2]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv))                            # reg[4] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 3, 0, mv))                           # out = reg[3]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv))                            # reg[5] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 4, 0, mv))                           # out = reg[4]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv))                             # gr[1] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 5, 0, mv))                           # out = reg[5]
    f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, 0, 0, 0, 0, 0, 0, mv))                       # ir[0] = in
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 5, 0, mv))                            # out = gr[1]
    for i in range(BSW_COMPUTE_INSTRUCTION_NUM-1):
        f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, i+1, 0, 0, 0, 0, 0, mv))                 # ir[i+1] = in
        f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv))                  # out = ir[i]
    f.write(data_movement_instruction(reg, reg, 0, 0, 26, 0, 0, 0, 4, 0, mv))                               # reg[26] = reg[4]
    f.write(data_movement_instruction(out_instr, comp_ib, 0, 0, 0, 0, 0, 0, 28, 0, mv))                     # out = ir[28]
    f.write(data_movement_instruction(reg, reg, 0, 0, 27, 0, 0, 0, 4, 0, mv))                               # reg[27] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 28, 0, 0, 0, 4, 0, mv))                               # reg[28] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 29, 0, 0, 0, 4, 0, mv))                               # reg[29] = reg[4]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, reg, 0, 0, 30, 0, 0, 0, 0, 0, mv))                               # reg[30] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    for i in range(10):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             47
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                                 # reg[14] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                 # reg[10] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                 # reg[15] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                                  # reg[9] = 0
    for i in range(33):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              75
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    for i in range(10):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             76
    f.write(data_movement_instruction(reg, in_port, 0, 0, 8, 0, 0, 0, 0, 0, mv))                            # reg[8] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 14, 0, 0, 0, 0, 0, mv))                           # reg[14] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                 # reg[10] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))                            # reg[6] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                 # reg[15] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))                            # reg[7] = in        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))                                  # reg[9] = 0
    for i in range(41):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              108

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             109
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))                                # set 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                                  # gr[10] = 1
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             113
    
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 0, set_PC))                                # set 5
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))                           # reg[11] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv))                           # reg[12] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 14, 0, mv))                          # out = reg[14]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv))                           # reg[13] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 13, 0, mv))                          # out = reg[13]
    for i in range(2):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt              120
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             121
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 0, 0, 0, 0, set_PC))                               # set 11            
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op             124
        
    f.write(data_movement_instruction(0, 0, 0, 0, 15, 0, 0, 0, 0, 0, set_PC))                               # set 15            
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                              # No-op
    f.write(data_movement_instruction(gr, reg, 0, 0, 10, 0, 0, 0, 20, 0, mv))                               # gr[10] = reg[20]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op             130
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 18, 0, 0, 0, 0, 0, mv))                           # reg[18] = in
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                                  # gr[10] = 0
    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv))                           # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 20, 0, 0, 0, 0, 0, mv))                           # reg[20] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 24, 0, 0, 0, 0, 0, set_PC))                               # set 24
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 23, 0, 0, 0, 0, 0, mv))                           # reg[23] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 18, 0, 0, 0, 0, 0, mv))                           # reg[18] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv))                           # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 20, 0, 0, 0, 0, 0, mv))                           # reg[20] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 24, 0, 0, 0, 0, 0, set_PC))                               # set 24
    f.write(data_movement_instruction(reg, in_port, 0, 0, 21, 0, 0, 0, 0, 0, mv))                           # reg[21] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 22, 0, 0, 0, 0, 0, mv))                           # reg[22] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, in_port, 0, 0, 23, 0, 0, 0, 0, 0, mv))                           # reg[23] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(0, 0, 0, 0, 29, 0, 0, 0, 0, 0, set_PC))                               # set 29
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 24, 0, mv))                          # out = reg[24]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 27, 0, mv))                          # out = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 26, 0, mv))                          # out = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 28, 0, mv))                          # out = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 29, 0, mv))                          # out = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 30, 0, mv))                          # out = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.close()



if not os.path.exists("instructions/bsw"):
    os.makedirs("instructions/bsw")
bsw_compute()
bsw_main_instruction()
pe_0_instruction()
pe_1_instruction()
pe_2_instruction()
pe_3_instruction()
