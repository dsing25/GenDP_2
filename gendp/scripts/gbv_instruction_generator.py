import sys
import os
from utils import *
from opcodes import *

r"""
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
    
# reg[0]=Eq, reg[1]=Vn, reg[2]=Vp, reg[3]=hinN, reg[4]=hinP, reg[5]=Xh, reg[6]=Xv, reg[7]=Ph, reg[8]=Mh, 
# reg[9]=tempMh, reg[10]=tempPh, reg[11]=scoreBefore, reg[12]=scoreEnd, reg[13]=child_vn, reg[14]=child_vp, reg[15]=child_sbefore, reg[16]=child_send
# reg[17]=merged_vn, reg[18]=merged_vp, reg[19]=merged_sbef, reg[20]=merged_send, reg[21]=temp1, reg[22]=temp2, reg[23]=temp3, reg[24]=temp4, 
# reg[25]=temp5, reg[26]=temp6, reg[27]=temp7, reg[28]=temp8, reg[29]=temp9, reg[30]=temp10, reg[31]=temp11

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

"""

def gbv_compute_v3():

    f = InstructionWriter("instructions/gbv/compute_inst.txt")

    # getScoreBeforeStart (2)
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 11, 0, 0, 0, 23, 0, 25)) # scoreEnd - pc(VP) = temp6
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 24, 0, 25)) # temp6 + pc(VN) = temp6 
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # end of getScoreBeforeStart

    # mergeTwoSlices - 2 Input (12)
    # set reg14 to left.getscore
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 15, 0, 0, 0, 13, 0, 25)) # scoreEnd - pc(VP) = temp6
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 12, 0, 14)) # temp6 + pc(VN) = reg14
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # set reg18 to right.getscore
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 19, 0, 0, 0, 17, 0, 25)) # scoreEnd - pc(VP) = temp6
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 16, 0, 18)) # temp6 + pc(VN) = reg18
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    #do the swap(left,right)
    f.write(compute_instruction(COPY, INVALID, COPY, 14, 0, 0, 0, 0, 0, 26)) # Copy so you can swap without worrying
    f.write(compute_instruction(COPY, INVALID, COPY, 18, 0, 0, 0, 0, 0, 27))

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 12, 22, 0, 0, 22)) # temp3 = child_sb > merge_sb ? child_vn : temp3
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 13, 23, 0, 0, 23)) # temp4 = child_sb > merge_sb ? child_vp : temp4

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 15, 24, 0, 0, 24)) # temp5 = child_sb > merge_sb ? child_send : temp5
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 14, 25, 0, 0, 25)) # temp6 = child_sb > merge_sb ? child_sb : temp6

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 16, 12, 0, 0, 12)) # child_vn = child_sb > merge_sb ? merged_vn : child_vn
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 17, 13, 0, 0, 13)) # child_vp = child_sb > merge_sb ? merged_vp : child_vp

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 19, 15, 0, 0, 15)) # child_send = child_sb > merge_sb ? merged_send : child_send
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 18, 14, 0, 0, 14)) # child_sb = child_sb > merge_sb ? merged_sb : child_sb

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 22, 16, 0, 0, 16)) # merged_vn = child_sb > merge_sb ? temp3 : merged_vn
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 23, 17, 0, 0, 17)) # merged_vp = child_sb > merge_sb ? temp4 : merged_vp
    
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 24, 19, 0, 0, 19)) # merged_send = child_sb > merge_sb ? temp5 : merged_send
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 26, 27, 25, 18, 0, 0, 18)) # merged_sb = child_sb > merge_sb ? temp6 : merged_sb

    f.write(compute_instruction(SUBTRACTION, INVALID, COPY, 18, 14, 0, 0, 0, 0, 31)) # reg31 = reg18 - reg14
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # BE CAREFUL ON DATA MOVEMENT HERE AND REGISTER MOVEMENTS

    # differenceMasks (34)
    f.write(compute_instruction(BWISE_AND, INVALID, BWISE_NOT, 13, 17, 0, 0, 0, 0, 23)) # VPcommon = ~(leftVP & rightVP)
    f.write(compute_instruction(BWISE_AND, INVALID, BWISE_NOT, 12, 16, 0, 0, 0, 0, 24)) # VNcommon = ~(leftVN & rightVN)

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 13, 23, 0, 0, 0, 0, 13)) # leftVP &= VPcommon
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 12, 24, 0, 0, 0, 0, 12)) # leftVN &= VNcommon

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 17, 23, 0, 0, 0, 0, 17)) # rightVP = rightVP & VPcommon
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 16, 24, 0, 0, 0, 0, 16)) # rightVN = rightVN & VNcommon

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 12, 17, 0, 0, 0, 0, 25)) # twosmaller = leftVN & rightVP
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 12, 0, 0, 0, 17, 0, 26)) # reg26 = ~leftVN & rightVP
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 17, 0, 0, 0, 12, 0, 27)) # reg27 = ~rightVP & leftVN

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 26, 27, 0, 0, 0, 0, 26)) # onesmaller = reg26 | reg27
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 16, 0, 0, 0, 13, 0, 27)) # reg27 = ~rightVN & leftVP
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 13, 0, 0, 0, 16, 0, 28)) # reg28 = ~leftVP & rightVN

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 27, 28, 0, 0, 0, 0, 27)) # onebigger = reg27 | reg28
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 16, 13, 0, 0, 0, 0, 28)) # twobigger = rightVN & leftVP

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 27, 28, 0, 0, 0, 0, 27)) # onebigger |= twobigger
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 26, 25, 0, 0, 0, 0, 26)) # onesmaller |= twosmaller

    # ADD THE DATA MOVEMENT scoreDifference checks for these (if regfile(22) > 0)
    # do a for loop for the scoreDifference here

    f.write(compute_instruction(ADD_I, INVALID, COPY, 23, 1, 0, 0, 0, 0, 23)) # reg23 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onebigger - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 27, 0, 0, 0, 0, 23)) # leastSignificant = onebigger & reg23
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 28, 0, 0, 0, 23, 0, 24)) # reg24 = ~twoBigger & leastSignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 24, 27, 0, 0, 0, 0, 27)) # onebigger = onebigger ^ reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 23, 0, 0, 0, 28, 0, 28)) # twobigger &= ~leastSignificant;

    # if regfile27 == 0 data movement here and do the following
    # return std::make_pair(WordConfiguration<Word>::AllOnes, WordConfiguration<Word>::AllZeros);
    # end for loop for scoreDifference 

    f.write(compute_instruction(ADD_I, INVALID, COPY, 23, 1, 0, 0, 0, 0, 23)) # reg23 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onebigger - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 27, 0, 0, 0, 0, 23)) # leastSignificant = onebigger & reg23
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(ADD_I, INVALID, COPY, 30, 1, 0, 0, 0, 0, 30)) # reg30 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, COPY, BWISE_OR, 23, 30, 0, 0, 20, 0, 20)) # leftSmaller |= leastSignificant - reg30
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 28, 0, 0, 0, 23, 0, 24)) # reg24 = ~twoBigger & leastSignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 24, 27, 0, 0, 0, 0, 27)) # onebigger = onebigger ^ reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 23, 0, 0, 0, 28, 0, 28)) # twobigger &= ~leastSignificant;

    # END OF if regfile22 > 0 if statement here

    # start of for loop for wordsize i++ 
    # if statement for regfile26 == 0
    # if statement regfile27 == 0 then break DATA MOVEMENT 
    f.write(compute_instruction(ADD_I, INVALID, COPY, 23, 1, 0, 0, 0, 0, 23)) # reg23 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onebigger - reg23) 
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 27, 0, 0, 0, 0, 23)) # leastsignificant = reg23 & onebigger
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 21, 23, 0, 0, 0, 0, 21)) # rightsmaller |= -leastsignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # break statement end of if regfile26 == 0 statement
    # start if reg27 == 0 statement DATA MOVEMENT 
    f.write(compute_instruction(ADD_I, INVALID, COPY, 23, 1, 0, 0, 0, 0, 23)) # reg23 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 26, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onesmaller - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 26, 0, 0, 0, 0, 23)) # leastsignificant = onesmaller & reg23
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 20, 23, 0, 0, 0, 0, 20)) # leftsmaller |= -leastsignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    #break statement end of if regfile27==0 DATA MOVEMENT 
    f.write(compute_instruction(ADD_I, INVALID, COPY, 23, 1, 0, 0, 0, 0, 23)) # reg23 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 29)) # reg29 = ~(onebigger - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 29, 27, 0, 0, 0, 0, 29)) # leastSignificantBigger = onebigger & reg29
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(ADD_I, INVALID, COPY, 23, 1, 0, 0, 0, 0, 23)) # reg23 = 1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 26, 23, 0, 0, 0, 0, 30)) # reg30 = ~(onesmaller - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 30, 26, 0, 0, 0, 0, 30)) # leastSignificantSmaller = onesmaller & reg30
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # if reg29 > reg30 statement start DATA MOVEMENT 
    f.write(compute_instruction(SUBTRACTION, COPY, BWISE_OR, 29, 30, 0, 0, 20, 0, 20)) # leftSmaller |= leastSignificantBigger - leastSignificantSmaller
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # end if statement reg29 > reg30
    # start else statement for that condition so if reg29 is NOT > reg30

    f.write(compute_instruction(SUBTRACTION, COPY, BWISE_OR, 30, 29, 0, 0, 21, 0, 21)) # rightSmaller |= leastSignificantSmaller - leastSignificantBigger
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # end else statement for the reg29 > 30 thing

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 28, 0, 0, 0, 29, 0, 24)) # reg24 = ~twobigger & leastSignificantBIgger
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 27, 24, 0, 0, 0, 0, 27)) # onebigger ^= reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 29, 0, 0, 0, 28, 0, 28)) # twobigger &= ~leastSignificantBigger

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 25, 0, 0, 0, 30, 0, 24)) # reg24 = ~twosmaller & leastsignificantsmaller
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 26, 24, 0, 0, 0, 0, 26)) # onesmaller ^= reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 30, 0, 0, 0, 25, 0, 25)) # twosmaller &= ~leastSignificantSmaller

    # end of for loop for the wordsize loop and end of the program
    # returns a pair make_pair (regfile 20, regfile21)
    # end of differenceMasks

    # continue mergeTwoSlices - 2 Input
    # reg20 and reg21 are set to the outputs from differenceMasks
    # mergeTwoSlices 2 Input returns left, right, reg20, reg21
    # left and right data movement must be done before differencemasks is called to prevent corrupting register state
    # end of mergeTwoSlices - 2 Input

    # mergeTwoSlices - 4 Input (18)
    # set reg14 to left.getscore
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 15, 0, 0, 0, 13, 0, 25)) # scoreEnd - pc(VP) = temp6
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 12, 0, 14)) # temp6 + pc(VN) = reg14
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # set reg18 to right.getscore
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 19, 0, 0, 0, 17, 0, 25)) # scoreEnd - pc(VP) = temp6
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 16, 0, 18)) # temp6 + pc(VN) = reg18
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # make sure to do all the data movement where reg=result.vn etc.
    # compute here
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 20, 21, 0, 0, 0, 0, 22)) # reg22 = leftsmaller | rightsmaller
    f.write(compute_instruction(LSHIFT_1, INVALID, COPY, 21, 0, 0, 0, 0, 0, 23)) # reg23 = rightsmaller << 1

    f.write(compute_instruction(SUBTRACTION, INVALID, COPY, 22, 23, 0, 0, 0, 0, 22)) # reg22 = ((leftSmaller | rightSmaller) - (rightSmaller << 1))
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(BWISE_OR, BWISE_NOT, BWISE_AND, 21, 22, 0, 0, 20, 0, 22)) # reg22 = (rightsmaller | reg22) & ~leftsmaller
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_AND, 21, 0, 0, 0, 20, 0, 23)) # reg23/leftreduction = reg21 << 1 & reg20
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_AND, 20, 0, 0, 0, 21, 0, 24)) # reg24/rightreduction = reg20 << 1 & reg21

    # move the value 1 into regfile 25 here in data movement 
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 21, 25, 0, 0, 0, 0, 26)) # reg26 = reg21 & reg25 (reg21 & 1)
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 18, 14, 25, 0, 0, 0, 27)) # reg27 = reg18 > reg14 ? reg25(1) : reg0 (0)

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 26, 27, 0, 0, 0, 0, 28)) # reg28 = reg26 & reg27
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 24, 25, 0, 0, 0, 0, 26)) # reg26 = reg24 | reg25
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(COMP_EQUAL, INVALID, COPY, 28, 25, 26, 24, 0, 0, 24)) # reg28 == reg25 ? reg26 : reg24
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 23, 0, 0, 0, 12, 0, 12)) # reg12 = leftvn & ~leftreduction
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 24, 0, 0, 0, 16, 0, 16)) # reg16 = rightvn & ~rightreduction

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 22, 0, 0, 0, 12, 0, 26)) # reg26 = ~mask & leftvn
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 16, 22, 0, 0, 0, 0, 27)) # reg27 = rightVN & mask

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 26, 27, 0, 0, 0, 0, 28)) # reg28 = (left.VN & ~mask) | (right.VN & mask);
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(BWISE_AND, BWISE_NOT, COPY, 13, 0, 0, 0, 22, 0, 26)) # reg26 = leftvp & ~mask
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 17, 22, 0, 0, 0, 0, 27)) # reg27 = rightVP & mask

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 26, 27, 0, 0, 0, 0, 29)) # reg29 = (left.VP & ~mask) | (right.VP & mask);
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 15, 19, 19, 15, 0, 0, 30)) # reg15 > reg19, then minimum is reg19, or else reg15. save into reg30
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    # do data movement to finalize the merge slices
    #END OF mergeTwoSlices - 4 Input

    # Cycle 0
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 1, 2, 0, 0, 0, 0, 7))  # Xv = Eq | VN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 1, 4, 0, 0, 0, 0, 1))  # Eq = Eq | hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_AND, COPY, ADD, 1, 3, 3, 0, 0, 0, 20)) # temp1 = ((Eq & VP) copied, then + VP)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_XOR, COPY, BWISE_OR, 20, 3, 1, 0, 0, 0, 6))  # Xh = (temp1 ^ VP) copied, then OR with Eq
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    
    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, 3, 6, 0, 0, 0, 0, 21)) # temp2 = (~(VP | Xh)) after copy
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 2, 21, 0, 0, 0, 0, 8))     # Ph = VN | temp2        
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))                             
    
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 3, 6, 0, 0, 0, 0, 9))  # Mh = VP & Xh
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, 9, 0, 4, 0, 0, 0, 22)) # tempMh = ((Mh << 1) copied, then OR with hinN)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    #Cycle 8 below
    f.write(compute_instruction(RSHIFT_WORD, INVALID, COPY, 9, 0, 0, 0, 0, 0, 4))  # hinN = Mh >> (word)
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, 8, 0, 5, 0, 0, 0, 23)) # tempPh = ((Ph << 1) copied, then OR with hinP)

    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, 7, 23, 0, 0, 0, 0, 20)) # temp1 = (~(Xv | tempPh)) after copy
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 22, 20, 0, 0, 0, 0, 3))    # slice.VP = tempMh | temp1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(RSHIFT_WORD, INVALID, COPY, 8, 0, 0, 0, 0, 0, 5))  # hinP = Ph >> (word), 
    f.write(compute_instruction(BWISE_AND, INVALID, INVALID, 23, 7, 0, 0, 0, 0, 2))  # slice.VN = tempPh & Xv

    f.write(compute_instruction(SUBTRACTION, INVALID, COPY, 11, 4, 0, 0, 0, 0, 11))  # scoreEnd = scoreEnd - hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(ADD, INVALID, COPY, 11, 5, 0, 0, 0, 0, 11))  # scoreEnd = scoreEnd + hinP
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(POPCOUNT, POPCOUNT, SUBTRACTION, 3, 0, 0, 0, 2, 0, 20))  # temp1 = popcount(VP) - popcount(VN)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(ADD, INVALID, ADD, 20, 10, 11, 0, 0, 0, 11)) # scoreEnd = (temp1 + scorebefore) + scoreEnd
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) # cycle 15 finished here

    f.close()

def gbv_main_instruction():
     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    # mergeTwoSlices 2 Input Data Movement
    # Get Left/Right Slices Into PE Array

    f = InstructionWriter("instructions/gbv/main_inst.txt");

    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si)) # gr[1] = 0 counter for input data buffer
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # no op

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
     
    f.close()


def pe_0_instruction():
     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    f = InstructionWriter("instructions/gbv/pe_0_inst.txt");

    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv)) # reg[12] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv)) # reg[13] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 15, 0, 0, 0, 0, 0, mv)) # reg[15] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 16, 0, 0, 0, 0, 0, mv)) # reg[16] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 17, 0, 0, 0, 0, 0, mv)) # reg[17] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv)) # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv)) # reg[2] = reg[12]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv)) # reg[3] = reg[13]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv)) # reg[14] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv)) # reg[11] = reg[19]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv)) # reg[2] = reg[16]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv)) # reg[3] = reg[17]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv)) # reg[18] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si)) # gr[2] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 2, 0, 0, 12, 0, mv)) # SPM[gr[2]] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 13, 0, mv)) # SPM[gr[2]++] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 15, 0, mv)) # SPM[gr[2]++] = reg[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 16, 0, mv)) # SPM[gr[2]++] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 17, 0, mv)) # SPM[gr[2]++] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 19, 0, mv)) # SPM[gr[2]++] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 22, 0, 0, 0, 31, 0, mv)) # reg[22] = reg[31]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 20, 0, 0, 0, 0, 0, mv)) # reg[20] = reg[0]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 21, 0, 0, 0, 0, 0, mv)) # reg[21] = reg[0] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 4, 0, 0, 0, 22, 0, mv)) # gr[4] = reg[22]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 0, 4, blt)) # blt gr[0] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Fix Data Movement Excel Sheets - Verify this Order Is Correct

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 32, 0, si)) # gr[6] = 32
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 0, 26, 0, mv)) # gr[7] = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
                         
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 7, beq)) # beq gr[0] gr[7] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))    

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 8, 29, 0, mv)) # gr[8] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 9, 0, 0, 0, 30, 0, mv)) # gr[9] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 9, 8, blt)) # blt gr[9] gr[8] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -9, 0, 0, 0, 3, 6, blt)) # blt gr[3] gr[6] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, gr, 0, 0, 15, 0, 0, 0, 0, 0, beq)) # beq 0 0 15    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 1, 0, si)) # gr[3] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, reg, 1, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = reg[0] - 1                        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    # f.write(data_movement_instruction(reg, 0, 0, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = 0xFFFF_FFFF (CHECK THIS?)
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 1, 0, si)) # reg[21] = 0x0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -5, 0, 0, 0, 3, 4, blt)) # blt gr[3] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 1, 0, 2, mv)) # reg[12] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 13, 0, 0, 1, 0, 2, mv)) # reg[13] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 0, 0, 1, 0, 2, mv)) # reg[15] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 1, 0, 2, mv)) # reg[16] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 17, 0, 0, 1, 0, 2, mv)) # reg[17] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 0, 0, 1, 0, 2, mv)) # reg[19] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv))   # reg[2] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv))   # reg[3] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv))  # reg[14] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv))  # reg[11] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv))   # reg[2] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv))   # reg[3] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv))  # reg[18] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 1, 0, si)) # reg[25] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 30, 0, mv))  # reg[11] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 28, 0, mv))   # reg[2] = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 29, 0, mv))   # reg[3] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 10, 0, 0, 0, 25, 0, mv))  # reg[10] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv)) # reg[1] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv)) # reg[4] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv)) # reg[5] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si)) # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 8, 10, 0, 0, 2, 0, mv)) # SPM[8(gr[10])] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 3, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 11, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
           

    f.close()



def pe_1_instruction():


     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    f = InstructionWriter("instructions/gbv/pe_1_inst.txt");

    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv)) # reg[12] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv)) # reg[13] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 15, 0, 0, 0, 0, 0, mv)) # reg[15] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 16, 0, 0, 0, 0, 0, mv)) # reg[16] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 17, 0, 0, 0, 0, 0, mv)) # reg[17] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv)) # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv)) # reg[2] = reg[12]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv)) # reg[3] = reg[13]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv)) # reg[14] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv)) # reg[11] = reg[19]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv)) # reg[2] = reg[16]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv)) # reg[3] = reg[17]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv)) # reg[18] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si)) # gr[2] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 2, 0, 0, 12, 0, mv)) # SPM[gr[2]] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 13, 0, mv)) # SPM[gr[2]++] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 15, 0, mv)) # SPM[gr[2]++] = reg[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 16, 0, mv)) # SPM[gr[2]++] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 17, 0, mv)) # SPM[gr[2]++] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 19, 0, mv)) # SPM[gr[2]++] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 22, 0, 0, 0, 31, 0, mv)) # reg[22] = reg[31]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 20, 0, 0, 0, 0, 0, mv)) # reg[20] = reg[0]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 21, 0, 0, 0, 0, 0, mv)) # reg[21] = reg[0] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 4, 0, 0, 0, 22, 0, mv)) # gr[4] = reg[22]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 0, 4, blt)) # blt gr[0] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Fix Data Movement Excel Sheets - Verify this Order Is Correct

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 32, 0, si)) # gr[6] = 32
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 0, 26, 0, mv)) # gr[7] = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
                         
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 7, beq)) # beq gr[0] gr[7] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))    

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 8, 29, 0, mv)) # gr[8] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 9, 0, 0, 0, 30, 0, mv)) # gr[9] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 9, 8, blt)) # blt gr[9] gr[8] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -9, 0, 0, 0, 3, 6, blt)) # blt gr[3] gr[6] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, gr, 0, 0, 15, 0, 0, 0, 0, 0, beq)) # beq 0 0 15    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 1, 0, si)) # gr[3] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, reg, 1, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = reg[0] - 1                        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    # f.write(data_movement_instruction(reg, 0, 0, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = 0xFFFF_FFFF (CHECK THIS?)
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 1, 0, si)) # reg[21] = 0x0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -5, 0, 0, 0, 3, 4, blt)) # blt gr[3] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 1, 0, 2, mv)) # reg[12] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 13, 0, 0, 1, 0, 2, mv)) # reg[13] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 0, 0, 1, 0, 2, mv)) # reg[15] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 1, 0, 2, mv)) # reg[16] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 17, 0, 0, 1, 0, 2, mv)) # reg[17] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 0, 0, 1, 0, 2, mv)) # reg[19] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv))   # reg[2] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv))   # reg[3] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv))  # reg[14] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv))  # reg[11] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv))   # reg[2] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv))   # reg[3] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv))  # reg[18] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 1, 0, si)) # reg[25] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 30, 0, mv))  # reg[11] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 28, 0, mv))   # reg[2] = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 29, 0, mv))   # reg[3] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 10, 0, 0, 0, 25, 0, mv))  # reg[10] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv)) # reg[1] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv)) # reg[4] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv)) # reg[5] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si)) # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 8, 10, 0, 0, 2, 0, mv)) # SPM[8(gr[10])] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 3, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 11, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
           

    f.close()




def pe_2_instruction():


     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    f = InstructionWriter("instructions/gbv/pe_2_inst.txt");

    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv)) # reg[12] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv)) # reg[13] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 15, 0, 0, 0, 0, 0, mv)) # reg[15] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 16, 0, 0, 0, 0, 0, mv)) # reg[16] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 17, 0, 0, 0, 0, 0, mv)) # reg[17] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv)) # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv)) # reg[2] = reg[12]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv)) # reg[3] = reg[13]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv)) # reg[14] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv)) # reg[11] = reg[19]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv)) # reg[2] = reg[16]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv)) # reg[3] = reg[17]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv)) # reg[18] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si)) # gr[2] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 2, 0, 0, 12, 0, mv)) # SPM[gr[2]] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 13, 0, mv)) # SPM[gr[2]++] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 15, 0, mv)) # SPM[gr[2]++] = reg[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 16, 0, mv)) # SPM[gr[2]++] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 17, 0, mv)) # SPM[gr[2]++] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 19, 0, mv)) # SPM[gr[2]++] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 22, 0, 0, 0, 31, 0, mv)) # reg[22] = reg[31]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 20, 0, 0, 0, 0, 0, mv)) # reg[20] = reg[0]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 21, 0, 0, 0, 0, 0, mv)) # reg[21] = reg[0] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 4, 0, 0, 0, 22, 0, mv)) # gr[4] = reg[22]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 0, 4, blt)) # blt gr[0] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Fix Data Movement Excel Sheets - Verify this Order Is Correct

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 32, 0, si)) # gr[6] = 32
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 0, 26, 0, mv)) # gr[7] = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
                         
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 7, beq)) # beq gr[0] gr[7] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))    

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 8, 29, 0, mv)) # gr[8] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 9, 0, 0, 0, 30, 0, mv)) # gr[9] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 9, 8, blt)) # blt gr[9] gr[8] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -9, 0, 0, 0, 3, 6, blt)) # blt gr[3] gr[6] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, gr, 0, 0, 15, 0, 0, 0, 0, 0, beq)) # beq 0 0 15    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 1, 0, si)) # gr[3] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, reg, 1, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = reg[0] - 1                        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    # f.write(data_movement_instruction(reg, 0, 0, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = 0xFFFF_FFFF (CHECK THIS?)
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 1, 0, si)) # reg[21] = 0x0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -5, 0, 0, 0, 3, 4, blt)) # blt gr[3] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 1, 0, 2, mv)) # reg[12] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 13, 0, 0, 1, 0, 2, mv)) # reg[13] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 0, 0, 1, 0, 2, mv)) # reg[15] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 1, 0, 2, mv)) # reg[16] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 17, 0, 0, 1, 0, 2, mv)) # reg[17] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 0, 0, 1, 0, 2, mv)) # reg[19] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv))   # reg[2] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv))   # reg[3] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv))  # reg[14] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv))  # reg[11] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv))   # reg[2] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv))   # reg[3] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv))  # reg[18] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 1, 0, si)) # reg[25] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 30, 0, mv))  # reg[11] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 28, 0, mv))   # reg[2] = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 29, 0, mv))   # reg[3] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 10, 0, 0, 0, 25, 0, mv))  # reg[10] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv)) # reg[1] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv)) # reg[4] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv)) # reg[5] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si)) # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 8, 10, 0, 0, 2, 0, mv)) # SPM[8(gr[10])] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 3, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 11, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
           

    f.close()




def pe_3_instruction():


     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    f = InstructionWriter("instructions/gbv/pe_3_inst.txt");

    f.write(data_movement_instruction(reg, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv)) # reg[12] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv)) # reg[13] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 15, 0, 0, 0, 0, 0, mv)) # reg[15] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 16, 0, 0, 0, 0, 0, mv)) # reg[16] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 17, 0, 0, 0, 0, 0, mv)) # reg[17] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 19, 0, 0, 0, 0, 0, mv)) # reg[19] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv)) # reg[2] = reg[12]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv)) # reg[3] = reg[13]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv)) # reg[14] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv)) # reg[11] = reg[19]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv)) # reg[2] = reg[16]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv)) # reg[3] = reg[17]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv)) # reg[18] = reg[25]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si)) # gr[2] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 2, 0, 0, 12, 0, mv)) # SPM[gr[2]] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 13, 0, mv)) # SPM[gr[2]++] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 15, 0, mv)) # SPM[gr[2]++] = reg[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 16, 0, mv)) # SPM[gr[2]++] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 17, 0, mv)) # SPM[gr[2]++] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 19, 0, mv)) # SPM[gr[2]++] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 22, 0, 0, 0, 31, 0, mv)) # reg[22] = reg[31]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 20, 0, 0, 0, 0, 0, mv)) # reg[20] = reg[0]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 21, 0, 0, 0, 0, 0, mv)) # reg[21] = reg[0] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 4, 0, 0, 0, 22, 0, mv)) # gr[4] = reg[22]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 0, 4, blt)) # blt gr[0] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Fix Data Movement Excel Sheets - Verify this Order Is Correct

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 32, 0, si)) # gr[6] = 32
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 0, 26, 0, mv)) # gr[7] = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
                         
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 7, beq)) # beq gr[0] gr[7] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))    

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 8, 29, 0, mv)) # gr[8] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 9, 0, 0, 0, 30, 0, mv)) # gr[9] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 9, 8, blt)) # blt gr[9] gr[8] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -9, 0, 0, 0, 3, 6, blt)) # blt gr[3] gr[6] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, gr, 0, 0, 15, 0, 0, 0, 0, 0, beq)) # beq 0 0 15    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 1, 0, si)) # gr[3] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 5, 0, beq)) # beq gr[5] gr[0] 5 (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, reg, 1, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = reg[0] - 1                        
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    # f.write(data_movement_instruction(reg, 0, 0, 0, 20, 0, 0, 0, 1, 0, subi)) # reg[20] = 0xFFFF_FFFF (CHECK THIS?)
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 1, 0, si)) # reg[21] = 0x0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 1, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(gr, gr, 0, 0, -5, 0, 0, 0, 3, 4, blt)) # blt gr[3] gr[4] (FIX THIS OFFSET CURRENTLY 5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 1, 0, 2, mv)) # reg[12] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 13, 0, 0, 1, 0, 2, mv)) # reg[13] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 0, 0, 1, 0, 2, mv)) # reg[15] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 1, 0, 2, mv)) # reg[16] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 17, 0, 0, 1, 0, 2, mv)) # reg[17] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 0, 0, 1, 0, 2, mv)) # reg[19] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv))   # reg[2] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv))   # reg[3] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv))  # reg[14] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv))  # reg[11] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv))   # reg[2] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv))   # reg[3] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv))  # reg[18] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 1, 0, si)) # reg[25] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 30, 0, mv))  # reg[11] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 28, 0, mv))   # reg[2] = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 29, 0, mv))   # reg[3] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 10, 0, 0, 0, 25, 0, mv))  # reg[10] = reg[25]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv)) # reg[1] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                          

    f.write(data_movement_instruction(reg, in_port, 0, 0, 4, 0, 0, 0, 0, 0, mv)) # reg[4] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, in_port, 0, 0, 5, 0, 0, 0, 0, 0, mv)) # reg[5] = in
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si)) # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 8, 10, 0, 0, 2, 0, mv)) # SPM[8(gr[10])] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 3, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 11, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                                  # halt

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))               
           

    f.close()


if not os.path.exists("instructions/gbv"):
    os.makedirs("instructions/gbv")
gbv_compute_v3()
gbv_main_instruction()
pe_0_instruction()
pe_1_instruction()
pe_2_instruction()
pe_3_instruction()


    