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

# define register file elsewhere - for reference
# parents:0, scorebefore:1, index:2, 
# Eq:5 , VN:6 , VP:7 , hinN:8, hinP:9, Xh:10, Xv:11, Ph:12, Mh:13, tempMh:14, tempPh:15, scoreEnd:16
# temp1:17, temp2:18, temp3:19, temp4:20, child_vn:21, child_vp:22, child_sbefore:23, child_send:24, 
# merged_vn:25, merged_vp: 26, merged_sbef: 27, merged_send:28


#PE ARRAY General Registers?
# gr1 pe group size, gr2 is input buffer index, gr3 is # of parents, gr4 is child index, gr5 is SPM index

# data movement opcodes below
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
    
    
def gbv_compute_v1():
    
    f = open("instructions/gbv/compute_instruction_v1.txt", "w")

    f.write(compute_instruction(BWISE_OR, halt, halt, Eq, VN, 0, 0, 0, 0, Xv))  # Xv = Eq | VN
    f.write(compute_instruction(BWISE_OR, halt, halt, Eq, hinN, 0, 0, 0, 0, Eq))  # Eq = Eq | hinN

    f.write(compute_instruction(BWISE_AND, halt, halt, Eq, VP, 0, 0, 0, 0, temp1))    # temp1 = Eq & VP
    f.write(compute_instruction(ADDITION, halt, halt, temp1, VP, 0, 0, 0, 0, temp2))  # temp2 = temp1 + VP
    f.write(compute_instruction(BWISE_XOR, halt, halt, temp2, VP, 0, 0, 0, 0, temp3)) # temp3 = temp2 ^ VP
    f.write(compute_instruction(BWISE_OR, halt, halt, temp3, Eq, 0, 0, 0, 0, Xh))  # Xh = temp3 | Eq,

    f.write(compute_instruction(BWISE_OR, halt, halt, VP, Xh, 0, 0, 0, 0, temp1))     # temp1 = VP | Xh
    f.write(compute_instruction(BWISE_NOT, halt, halt, temp1, 0, 0, 0, 0, 0, temp2))  # temp2 = ~temp1
    f.write(compute_instruction(BWISE_OR, halt, halt, VN, temp2, 0, 0, 0, 0, Ph))     # Ph = VN | temp2                                    
    
    f.write(compute_instruction(BWISE_AND, halt, halt, VP, Xh, 0, 0, 0, 0, Mh))  # Mh = VP & Xh
    f.write(compute_instruction(LSHIFT_1, halt, halt, Mh, 0, 0, 0, 0, 0, temp1))      # temp1 = Mh << 1
    f.write(compute_instruction(BWISE_OR, halt, halt, temp1, hinN, 0, 0, 0, 0, tempMh))# tempMh = temp1 | hinN

    f.write(compute_instruction(RSHIFT_WORD, halt, halt, Mh, 0, 0, 0, 0, 0, hinN))  # hinN = Mh >> (word)
    f.write(compute_instruction(LSHIFT_1, halt, halt, Ph, 0, 0, 0, 0, 0, temp1))      # temp1 = Ph << 1
    f.write(compute_instruction(BWISE_OR, halt, halt, temp1, hinP, 0, 0, 0, 0, tempPh))# tempPh = temp1 | hinP

    f.write(compute_instruction(BWISE_OR, halt, halt, Xv, tempPh, 0, 0, 0, 0, temp2))    # temp2 = Xv | tempPh
    f.write(compute_instruction(BWISE_NOT, halt, halt, temp2, 0, 0, 0, 0, 0, temp3))     # temp3 = ~temp2
    f.write(compute_instruction(BWISE_OR, halt, halt, tempMh, temp3, 0, 0, 0, 0, VP))    # slice.VP = tempMh | temp3

    f.write(compute_instruction(RSHIFT_WORD, halt, halt, Ph, 0, 0, 0, 0, 0, hinP))  # hinP = Ph >> (word), 
    f.write(compute_instruction(BWISE_AND, halt, halt, tempPh, Xv, 0, 0, 0, 0, VN))  # slice.VN = tempPh & Xv
    f.write(compute_instruction(SUBTRACTION, halt, halt, scoreEnd, hinN, 0, 0, 0, 0, scoreEnd))  # scoreEnd = scoreEnd - hinN
    # change this compute to account for scorebefore and then scoreend so you dont overwrite
    f.write(compute_instruction(ADDITION, halt, halt, scoreEnd, hinP, 0, 0, 0, 0, scoreEnd))  # scoreEnd = scoreEnd + hinP

    f.close()

def gbv_compute_v2(): # 16 instruction trace
    # there's 2 threads to deal with for Comp Unit
    # OPCODES: add 0, sub 1, mult 2, carry 3, borrow 4, max 5, min 6, lshift 7, rshift 8, copy 9, match_score 10, 
    # log2_lut 11, log_sum_lut 12, comp_larger 13, comp_equal 14, invalid 15, halt 16, or 17, and 18, not 19, xor 20, lshift_1 21, rshift_word 22, add_i 23, copy_i 24, popcount 25
    f = open("instructions/gbv/compute_instruction_v2.txt", "w")

    # Cycle 0
    f.write(compute_instruction(BWISE_OR, INVALID, INVALID, Eq, VN, 0, 0, 0, 0, Xv))  # Xv = Eq | VN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, INVALID, INVALID, Eq, hinN, 0, 0, 0, 0, Eq))  # Eq = Eq | hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_AND, COPY, ADDITION, Eq, VP, VP, 0, 0, 0, temp1)) # temp1 = ((Eq & VP) copied, then + VP)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_XOR, COPY, BWISE_OR, temp1, VP, Eq, 0, 0, 0, Xh))  # Xh = (temp1 ^ VP) copied, then OR with Eq
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    
    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, VP, Xh, 0, 0, 0, 0, temp2)) # temp2 = (~(VP | Xh)) after copy
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, INVALID, INVALID, VN, temp2, 0, 0, 0, 0, Ph))     # Ph = VN | temp2        
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))                             
    
    f.write(compute_instruction(BWISE_AND, INVALID, INVALID, VP, Xh, 0, 0, 0, 0, Mh))  # Mh = VP & Xh
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, Mh, 0, hinN, 0, 0, 0, tempMh)) # tempMh = ((Mh << 1) copied, then OR with hinN)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    #Cycle 8 below
    f.write(compute_instruction(RSHIFT_WORD, INVALID, INVALID, Mh, 0, 0, 0, 0, 0, hinN))  # hinN = Mh >> (word)
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, Ph, 0, hinP, 0, 0, 0, tempPh)) # tempPh = ((Ph << 1) copied, then OR with hinP)

    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, Xv, tempPh, 0, 0, 0, 0, temp1)) # temp1 = (~(Xv | tempPh)) after copy
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, INVALID, INVALID, tempMh, temp1, 0, 0, 0, 0, VP))    # slice.VP = tempMh | temp1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(RSHIFT_WORD, INVALID, INVALID, Ph, 0, 0, 0, 0, 0, hinP))  # hinP = Ph >> (word), 
    f.write(compute_instruction(BWISE_AND, INVALID, INVALID, tempPh, Xv, 0, 0, 0, 0, VN))  # slice.VN = tempPh & Xv

    f.write(compute_instruction(SUBTRACTION, INVALID, INVALID, scoreEnd, hinN, 0, 0, 0, 0, scoreEnd))  # scoreEnd = scoreEnd - hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(ADDITION, INVALID, INVALID, scoreEnd, hinP, 0, 0, 0, 0, scoreEnd))  # scoreEnd = scoreEnd + hinP
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(POPCOUNT, POPCOUNT, SUBTRACTION, VP, 0, 0, 0, VN, 0, temp1))  # temp1 = popcount(VP) - popcount(VN)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(ADDITION, INVALID, ADDITION, temp1, scoreBefore, scoreEnd, 0, 0, 0, scoreEnd)) # scoreEnd = (temp1 + scorebefore) + scoreEnd
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) # cycle 15 finished here
    
    # another instruction here does a popcount. lets say it takes 2 cycles. probably will take a lot more... unfortunately 
    # add a copy instruction for vp/vn/
    f.write(compute_instruction(COPY, INVALID, INVALID, VN, 0, 0, 0, 0, 0, child_vn)) # copy vn into child_vn
    f.write(compute_instruction(COPY, INVALID, INVALID, VP, 0, 0, 0, 0, 0, child_vp)) # copy vp into child_vp

    # merge is done here
    # minimum of 
    # added new merge operations
    # move temp3 and temp4 as childsbefore and sbefore using data moves instead of compute
    # LOOP this 32 times for each bit with a new bitmask 
    f.write(compute_instruction(BWISE_OR, BWISE_OR, SUBTRACTION, VP, bitmasks[0], 0, 0, VN, bitmasks[0], temp1))  # temp1 = (VP | bitmask0) - (VN | bitmask0)
    f.write(compute_instruction(BWISE_OR, BWISE_OR, SUBTRACTION, child_vp, bitmasks[0], 0, 0, child_vn, bitmasks[0], temp2))  # temp2 = (child_vp | bitmask0) - (child_vn | bitmask0)
    
    f.write(compute_instruction(ADDITION, ADDITION, CMP_2INP, scoreBefore, temp1, 0, 0, child_sbefore, temp2, temp3)) # compares Sa>Sb and sets Ma>b vector
    f.write(compute_instruction(ADDITION, ADDITION, CMP_2INP, scoreBefore, temp1, 0, 0, child_sbefore, temp2, temp4)) # compares Sa>Sb and sets Mb>a vector

    f.write(compute_instruction(BWISE_OR, LSHIFT_1, SUBTRACTION, temp4, temp3, 0, 0, temp3, 0, temp5)) # (Mba | Mab) - Mab <<1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, BWISE_NOT, BWISE_AND, temp5, temp3, 0, 0, temp4, 0, temp6)) # Mp is saved
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # if i am passing through an ALU, do I need to just use copy or invalid? or what
    f.write(compute_instruction(INVALID, LSHIFT_1, BWISE_AND, temp4, 0, 0, 0, temp3, 0, temp7)) # Mba & Mab<<1
    f.write(compute_instruction(INVALID, LSHIFT_1, BWISE_AND, temp3, 0, 0, 0, temp4, 0, temp8)) # Mab & Mba<<1

    f.write(compute_instruction(BWISE_NOT, INVALID, BWISE_AND, temp7, 0, 0, 0, VN, 0, temp1)) # VnA reduced
    f.write(compute_instruction(BWISE_NOT, INVALID, BWISE_AND, temp8, 0, 0, 0, child_vn, 0, temp2)) # VnB reduced

    f.write(compute_instruction(INVALID, INVALID, BWISE_AND, child_vp, 0, 0, 0, temp6, 0, temp5)) # VpB & Mp
    f.write(compute_instruction(BWISE_NOT, INVALID, BWISE_AND, temp6, 0, 0, 0, VP, 0, temp9)) # VpA & ~Mp

    f.write(compute_instruction(INVALID, INVALID, BWISE_AND, temp2, 0, 0, 0, temp6, 0, temp7)) # VnB reduced & Mp
    f.write(compute_instruction(BWISE_NOT, INVALID, BWISE_AND, temp6, 0, 0, 0, temp1, 0, temp8)) # VnA reduced & ~Mp

    f.write(compute_instruction(ADDITION, INVALID, INVALID, temp5, temp9, 0, 0, 0, 0, merged_vp)) # VpOut
    f.write(compute_instruction(ADDITION, INVALID, INVALID, temp7, temp8, 0, 0, 0, 0, merged_vn)) # VnOut

    f.write(compute_instruction(POPCOUNT, POPCOUNT, SUBTRACTION, merged_vp, 0, 0, 0, merged_vn, 0, temp1)) # temp1 = popcount(VP) - popcount(VN)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(ADDITION, INVALID, INVALID, temp1, merged_sbef, 0, 0, 0, 0, merged_send)) # send = sbefore + temp1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.close()

def pe_0_instruction():
    # dest, src, reg_immBar_0, reg_auto_increase_0, imm_0, reg_0, reg_immBar_1, reg_auto_increase_1, imm_1, reg_1, opcode
    f = open("instructions/gbv/pe_0_instruction.txt", "w")

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(gr, in_port, 0, 0, 3, 0, 0, 0, 0, 0, mv))                             # gr[3] = in

    f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 3, mv))                                # reg[0] = SPM[gr[3]]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 3, 0, mv))                            # out = gr[3]

    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 4, 0, mv))                            # out = gr[4]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv))                             # gr[4] = in

    f.write(data_movement_instruction(reg, SPM, 0, 0, 1, 0, 0, 1, 0, 4, mv))                                # reg[1] = SPM[gr[4]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 2, 0, 0, 1, 0, 4, mv))                                # reg[2] = SPM[gr[4]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 3, 0, 0, 1, 0, 4, mv))                                # reg[3] = SPM[gr[4]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 1, 0, 4, mv))                                # reg[4] = SPM[gr[4]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op
    f.write(data_movement_instruction(reg, SPM, 0, 0, 11, 0, 0, 1, 0, 4, mv))                                # reg[11] = SPM[gr[4]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op

    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 12, 0, mv))                            # out = reg[12]
    f.write(data_movement_instruction(reg, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))                             # reg[11] = in

    f.write(data_movement_instruction(0, 0, 0, 0, 1, 0, 0, 0, 230, 21, bge))                                 # bge (line 230?) reg[21] 2
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                                  # No-op


    f.write(data_movement_instruction(SPM, gr, 0, 0, 7, 0, 0, 1, 0, 4, mv))                                 # gr[7] = SPM[gr[4]++]

    f.write(data_movement_instruction(reg, SPM, 0, 0, 3, 0, 0, 0, 272, 8, mv))                              # reg[3] = SPM[gr[3]]
    f.write(data_movement_instruction(gr, SPM, 0, 0, 7, 0, 0, 1, 0, 4, mv))                                 # gr[7] = SPM[gr[4]++]


    f.write(data_movement_instruction(SPM, in_port, 0, 1, 0, 3, 0, 0, 0, 0, mv))                            # SPM[gr[3]++] = in
    f.write(data_movement_instruction(gr, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv))                             # gr[1] = in
    f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 5, 0, mv))                           # out = reg[5]
    f.write(data_movement_instruction(comp_ib, in_instr, 0, 0, 0, 0, 0, 0, 0, 0, mv))                       # ir[0] = in
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 5, 0, mv))                            # out = gr[1]                   

    f.close()



def pe_1_instruction():

f = open("instructions/gbv/pe_1_instruction.txt", "w")



f.close()



def pe_2_instruction():

f = open("instructions/gbv/pe_2_instruction.txt", "w")



f.close()



def pe_3_instruction():

f = open("instructions/gbv/pe_3_instruction.txt", "w")



f.close()

if not os.path.exists("instructions/gbv"):
    os.makedirs("instructions/gbv")
gbv_compute()
bsw_main_instruction()
pe_0_instruction()
pe_1_instruction()
pe_2_instruction()
pe_3_instruction()
