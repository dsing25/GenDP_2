import sys
import os

reg = 0
gr = 1
SPM = 2
comp_ib = 3
ctrl_ib = 4
in_buf = 5
out_buf = 6
in_port = 7
in_instr = 8
out_port = 9
out_instr = 10
fifo = [11, 12]
mem = 13 # TODO not implemented yet

add = 0
sub = 1
addi = 2
set_8 = 3
si = 4
mv = 5
add_8 = 6
addi_8 = 7
bne = 8
beq = 9
bge = 10
blt = 11
jump = 12
set_PC = 13
none = 14
halt = 15
shift_r = 16
shift_l = 17
# these instruction tags here are for data movement
# use sys_def.h for compute tags

BSW_COMPUTE_INSTRUCTION_NUM = 32

PE_INIT_CONSTANT_AND_INSTRUCTION = 1
PE_GROUP = 47+4
PE_GROUP_1 = 76+4
PE_INIT = 109+4
PE_RUN = 113+4
PE_GSCORE = 121+4
PE_EARLY_BERAK = 124+4
PE_END = 130+4



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
    
    
def data_movement_instruction(dest, src, reg_immBar_0, reg_auto_increase_0, imm_0, reg_0, reg_immBar_1, reg_auto_increase_1, imm_1, reg_1, opcode):
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
    gr[31] = LOCAL_FRAME #magic malloc the stack pointer (gr[31]) #TODO magic local fram malloc
    #magic malloc each prev wf
    for i in range(N_PREV_WF):
        mem[gr[31]+i] = malloc((9-2*i)*3); #9 is the closest. -2 for each layer back, *3 for I, D, M #TODO magic malloc
    #TODO think this line is wrong f.write(data_movement_instruction(gr, 0, 0, 0, 28, 0, 0, 0, 11, 0, si)) # gr[28] = current wf size
    f.write(data_movement_instruction(gr, 0, 0, 0, 28, 0, 0, 0, 0, 0, si)) # sets the edit dist=0

    #LOOP_SINGLE_ALIGNMENT
    '''
    General Note about which registers are storing what for next step
        # STORE CURSORS
        # gr[0] = PE0 i
        # gr[1] = PE0 d
        # gr[3] = PE0 m
        #...
        # gr[11 = PE3 m
        # READ CURSORS
        # gr[12] = PE0 d Score-E
        # gr[13] = PE0 i Score-E
        # gr[14] = PE0 m Score-2E
        # gr[15] = PE1 m Score-4E
        # ...
        # gr[27] = PE3 m Score-4E

        # gr[28] = ed / 2
        # gr[29] loop_counter
        # gr[30] wavefront_len. Divide by 4 for loop end later. 
        # gr[31] stack ptr (for register spilling). 
          Stack[0]=e, Stack[1]=2e, stack[2]=3e stack[3]=4e Needed for the wavefront locations
    '''
    #================================setup the cursors==============================================
    #gr[3] = ed << 1;
    #gr[3] = gr[3] + 1; #wf_len = (ed*2) + 1
    #gr[2] = gr[0] >> 2; #offset per PE
    if (wf_len % 2 == 1):
        #gr[0] = mem[gr[31]+3] #pop the location of score-4E wavefront from stack
        f.write(data_movement_instruction(gr, mem, 0, 0, 0, 0, 0, 0, 3, 31, mv))
        #gr[1] = (gr[28])*2+1 #the length of the padded wf score - 4E wavefront = ((ed)*2) + 1
        f.write(data_movement_instruction(gr, gr, 0, 0, 0, 1, 0, 0, 1, 28, shift_l))
        f.write(data_movement_instruction(gr, gr, 0, 0, 0, 1, 0, 0, 3, 1, addi))
        ###### score -4e M
            #gr[15] = gr[0] + 2*gr[1] # i.e. base of wavefront + 2*(wf_len) gives m
            f.write(data_movement_instruction(gr, gr, 0, 0, 0, 15, 0, 0, 2, 1, shift_l))
            f.write(data_movement_instruction(gr, gr, 0, 0, 0, 15, 0, 0, 0, 0, add))
            #gr[19] = gr[15] + gr[2]+1-1 # 15=PE0 offset. Add gr[2]=n_iters. Add 1 cause gr[19] does 
            # extra work. Minus 1 to start at last computed cell of previous row
            f.write(data_movement_instruction(0, 0, 0, 0, 19, 0, 1, 0, 15, 2, add))                                   # gr[9] = gr[8] + gr[3]              
            #gr[23] = gr[19] + gr[2] # PE2 m is PE0 m + offset
            #gr[27] = gr[23] + gr[2] # PE3 m is PE0 m + offset
        ###### score -2e M
            #gr[14] = gr[0] + 2*gr[1] + 2# i.e. base of wavefront + 2*(wf_len) gives m. +2 counters the padding
            #gr[18] = gr[14] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[22] = gr[18] + gr[2] # PE2 m is PE0 m + offset
            #gr[26] = gr[22] + gr[2] # PE3 m is PE0 m + offset
        ###### score -e i
            #gr[13] = gr[0] + 4# i.e. base of wavefront + 0*(wf_len) gives i. +4 for the padding
            #gr[17] = gr[13] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[21] = gr[17] + gr[2] # PE2 m is PE0 m + offset
            #gr[25] = gr[21] + gr[2] # PE3 m is PE0 m + offset
        ###### score -e d
            #gr[13] = gr[0] + gr[1] + 4# i.e. base of wavefront + (wf_len) gives d. +4 for the padding
            #gr[17] = gr[13] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[21] = gr[17] + gr[2] # PE2 m is PE0 m + offset
            #gr[25] = gr[21] + gr[2] # PE3 m is PE0 m + offset
        pass
    else: #(wf_len % 2 == 3)
        pass
    #gr[0] = offset per PE 
        #gr[0] = mem[gr[31]+3] #pop the location of score-4E wavefront from stack
        #gr[1] = (gr[28])*2+1 #the length of the padded wf score - 4E wavefront = ((ed)*2) + 1
        #gr[2] = gr[1] // 4 # the offset per PE
        #if (wf_len % 2 == 1)
            #gr[15] = gr[0] + 2*gr[1] # i.e. base of wavefront + 2*(wf_len) gives m
            #gr[19] = gr[15] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra.
                                       # PE0 will execute one time extra
            #gr[23] = gr[19] + gr[2] # PE2 m is PE0 m + offset
            #gr[27] = gr[23] + gr[2] # PE3 m is PE0 m + offset
        #else (wf_len %2 == 3)
            #gr[15] = gr[0]  + 2*gr[1] # i.e. base of wavefront + 2*(wf_len) gives m
            #gr[19] = gr[15] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[23] = gr[19] + gr[2]+1 # PE2 m is PE0 m + offset
            #gr[27] = gr[23] + gr[2]+1 # PE3 m is PE0 m + offset
    #score - 2e wf
        #gr[0] = mem[gr[31]+1] #pop the location of score-2E wavefront from stack
        #gr[1] = (gr[28]+2)*2+1 #the length of the padded wf score - 4E wavefront = ((ed)*2) + 1
        #if (wf_len % 2 == 1)
            #gr[14] = gr[0] + 2*gr[1] + 2# i.e. base of wavefront + 2*(wf_len) gives m. +2 counters the padding
            #gr[18] = gr[14] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[22] = gr[18] + gr[2] # PE2 m is PE0 m + offset
            #gr[26] = gr[22] + gr[2] # PE3 m is PE0 m + offset
        #else (wf_len %2 == 3)
            #gr[14] = gr[0] + 2*gr[1] + 2# i.e. base of wavefront + 2*(wf_len) gives m. +2 counters the padding
            #gr[18] = gr[14] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[22] = gr[18] + gr[2]+1 # PE2 m is PE0 m + offset
            #gr[26] = gr[22] + gr[2]+1 # PE3 m is PE0 m + offset
    #score - e wf i
        #gr[0] = mem[gr[31]] #pop the location of score-2E wavefront from stack
        #gr[1] = (gr[28]+3)*2+1 #the length of the padded wf score - 4E wavefront = ((ed)*2) + 1
        #if (wf_len % 2 == 1)
            #gr[13] = gr[0] + 4# i.e. base of wavefront + 0*(wf_len) gives i. +4 for the padding
            #gr[17] = gr[13] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[21] = gr[17] + gr[2] # PE2 m is PE0 m + offset
            #gr[25] = gr[21] + gr[2] # PE3 m is PE0 m + offset
        #else (wf_len %2 == 3)
            #gr[13] = gr[0] + 4# i.e. base of wavefront + 0*(wf_len) gives i. +4 for the padding
            #gr[17] = gr[13] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[21] = gr[17] + gr[2]+1 # PE2 m is PE0 m + offset
            #gr[25] = gr[21] + gr[2]+1 # PE3 m is PE0 m + offset
    #score - e wf d
        #gr[0] = mem[gr[31]] #pop the location of score-2E wavefront from stack
        #gr[1] = (gr[28]+3)*2+1 #the length of the padded wf score - 4E wavefront = ((ed)*2) + 1
        #if (wf_len % 2 == 1)
            #gr[13] = gr[0] + gr[1] + 4# i.e. base of wavefront + (wf_len) gives d. +4 for the padding
            #gr[17] = gr[13] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[21] = gr[17] + gr[2] # PE2 m is PE0 m + offset
            #gr[25] = gr[21] + gr[2] # PE3 m is PE0 m + offset
        #else (wf_len %2 == 3)
            #gr[13] = gr[0] + gr[1] + 4# i.e. base of wavefront + (wf_len) gives d. +4 for the padding
            #gr[17] = gr[13] + gr[2]+1 # PE1 m is PE0 m + offset. Starts 1 after because we have one extra
            #gr[21] = gr[17] + gr[2]+1 # PE2 m is PE0 m + offset
            #gr[25] = gr[21] + gr[2]+1 # PE3 m is PE0 m + offset
    #setup cursors for STORE
    #let gr[30] be the wavefront length for now
    #gr[29] = gr[30] // 4 # hijack 29 as a tmp
    # gr[0] = malloc new wavefront + 5 for padding # I
    # mem[gr[31]+4]] = gr[0] # put this new wavefront on the stack
    # gr[1] = gr[0] + gr[30] # D
    # gr[2] = gr[1] + gr[30] # M
    #if (wf_len % 2 == 1)
        #gr[3]  = gr[0] + gr[29] + 1
        #gr[4]  = gr[1] + gr[29] + 1
        #gr[5]  = gr[2] + gr[29] + 1
        #gr[6]  = gr[3] + gr[29]
        #gr[7]  = gr[4] + gr[29]
        #gr[8]  = gr[5] + gr[29]
        #gr[9]  = gr[6] + gr[29]
        #gr[10] = gr[7] + gr[29]
        #gr[11] = gr[8] + gr[29]
    #if (wf_len % 2 == 3)
        #gr[3]  = gr[0] + gr[29] + 1
        #gr[4]  = gr[1] + gr[29] + 1
        #gr[5]  = gr[2] + gr[29] + 1
        #gr[6]  = gr[3] + gr[29] + 1
        #gr[7]  = gr[4] + gr[29] + 1
        #gr[8]  = gr[5] + gr[29] + 1
        #gr[9]  = gr[6] + gr[29] + 1
        #gr[10] = gr[7] + gr[29] + 1
        #gr[11] = gr[8] + gr[29] + 1
    # update the loop counter and loop end
    #gr[29] = 0
    #gr[30] = (gr[28]*2+1) // 4



    # Do one masked round of computation
    # if ed is even mask 3 outta four PEs
    # else ed is odd. mask 1 outta four PEs
    # if (wf_len % 2 == 1)
        #STALL WRITE
        #out_port = mem[gr[12+3*i]++]
        #STALL WRITE
        #out_port = mem[gr[12+3*i+1]++]
        #STALL WRITE
        #out_port = mem[gr[12+3*i+2]++]
        #STALL WRITE
        #out_port = mem[gr[12+3*i+3]++]
        for i in range(16): # wait a full cycle of compute stalling all
            #STALL
        for i in range(4): # start feeding PEs, but still no data back.
            #STALL WRITE
            #out_port = mem[gr[12+3*i]++]
            #STALL WRITE
            #out_port = mem[gr[12+3*i+1]++]
            #STALL WRITE
            #out_port = mem[gr[12+3*i+2]++]
            #STALL WRITE
            #out_port = mem[gr[12+3*i+3]++]
    #else (wf_len % 2 == 3)
        for i in range(3):
            #STALL_WRITE
            #out_port = mem[gr[12+3*i]++]
            #STALL_WRITE
            #out_port = mem[gr[12+3*i+1]++]
            #STALL_WRITE
            #out_port = mem[gr[12+3*i+2]++]
            #STALL_WRITE
            #out_port = mem[gr[12+3*i+3]++]
        for i in range(4):
            #STALL everything
        for i in range(3): #start feeding and process the stalled instrs
            #mem[gr[3*i]++] = in_port I
            #out_port = mem[gr[12+3*i]++]
            #mem[gr[3*i+1]++] = in_port D
            #out_port = mem[gr[12+3*i+1]++]
            #mem[gr[3*i+2]++] = in_port M
            #out_port = mem[gr[12+3*i+2]++]
            #STALL write. Use this cycle to increment the loop_counter
            #out_port = mem[gr[12+3*i+3]++]
        #no write for the last PE
        #STALL_WRITE
        #out_port = mem[gr[12+3*i]++]
        #STALL_WRITE
        #out_port = mem[gr[12+3*i+1]++]
        #STALL_WRITE
        #out_port = mem[gr[12+3*i+2]++]
        #STALL_WRITE
        #out_port = mem[gr[12+3*i+3]++]

    # LOOP_WAVEFRONT_NEXT STEADY STATE
    for i in range(4):
        #mem[gr[3*i]++] = in_port I
        #out_port = mem[gr[12+3*i]++]
        #mem[gr[3*i+1]++] = in_port D
        #out_port = mem[gr[12+3*i+1]++]
        #mem[gr[3*i+2]++] = in_port M
        #out_port = mem[gr[12+3*i+2]++]
        #STALL write. Use this cycle to increment the loop_counter
        #out_port = mem[gr[12+3*i+3]++]
    #bne loop_counter loop_end LOOP

    #TODO setup Extend
    #TODO extend (in extend check completion)

    #update the loop stack
    #mem[gr[31]+3] = mem[gr[31]+2]
    #mem[gr[31]+2] = mem[gr[31]+1]
    #mem[gr[31]+1] = mem[gr[31]]
    #mem[gr[31]]   = mem[gr[31]+4]
    #ed++
    #jmp
    f.close()

def bsw_compute():
    
    f = open("instructions/bsw/compute_instruction.txt", "w")

    #NEXT
    #first pair is just data movement. Could be optimized out with unrolling
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))             #0
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(COPY, COPY, INVALID, 2, 0, 0, 0, 0, 0, 1))                   #1
    f.write(compute_instruction(COPY, COPY, INVALID, 1, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(ADD_I, MAXIMUM, MAXIMUM, 3, 1, 0, 0, 2, 5, 29))              #2
    f.write(compute_instruction(COPY_I, MAXIMUM, ADD_I, 1, 0, 0, 0, 0, 4, 31))
    f.write(compute_instruction(INVALID, MAXIMUM, COPY, 0, 0, 0, 0, 2, 5, 30))               #3
    f.write(compute_instruction(INVALID, MAXIMUM, COPY, 0, 0, 0, 0, 29, 31, 29))
    #stalls 3-12
    for i in range(3,13):
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    
    f.close()


    
def pe_0_instruction():
    
    f = open("instructions/bsw/pe_0_instruction.txt", "w")

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
