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
# parents:0, offset:1, scorebefore:2, 
# Eq:5 , VN:6 , VP:7 , hinN:8, hinP:9, Xh:10, Xv:11, Ph:12, Mh:13, tempMh:14, tempPh:15, scoreEnd:16
# temp1:17, temp2:18, temp3:19, gr1: 20, gr2: 21, gr3: 22, gr4: 23
# 

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
BWISE_OR 17
BWISE_AND 18
BWISE_NOT 19
BWISE_XOR 20
LSHIFT_1  21
RSHIFT_WORD 22

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
    
    f = open("instructions/gbv/compute_instruction_v2.txt", "w")

    f.write(compute_instruction(BWISE_OR, halt, halt, Eq, VN, 0, 0, 0, 0, Xv))  # Xv = Eq | VN
    f.write(compute_instruction(BWISE_OR, halt, halt, Eq, hinN, 0, 0, 0, 0, Eq))  # Eq = Eq | hinN

    f.write(compute_instruction(BWISE_AND, COPY, ADDITION, Eq, VP, VP, 0, 0, 0, temp2)) # temp2 = ((Eq & VP) copied, then + VP)
    f.write(compute_instruction(BWISE_XOR, COPY, BWISE_OR, temp2, VP, Eq, 0, 0, 0, Xh))  # Xh = (temp2 ^ VP) copied, then OR with Eq
    
    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, VP, Xh, 0, 0, 0, 0, temp2)) # temp2 = (~(VP | Xh)) after copy
    f.write(compute_instruction(BWISE_OR, halt, halt, VN, temp2, 0, 0, 0, 0, Ph))     # Ph = VN | temp2                                    
    
    f.write(compute_instruction(BWISE_AND, halt, halt, VP, Xh, 0, 0, 0, 0, Mh))  # Mh = VP & Xh
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, Mh, 0, hinN, 0, 0, 0, tempMh)) # tempMh = ((Mh << 1) copied, then OR with hinN)

    f.write(compute_instruction(RSHIFT_WORD, halt, halt, Mh, 0, 0, 0, 0, 0, hinN))  # hinN = Mh >> (word)
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, Ph, 0, hinP, 0, 0, 0, tempPh)) # tempPh = ((Ph << 1) copied, then OR with hinP)

    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, Xv, tempPh, 0, 0, 0, 0, temp3)) # temp3 = (~(Xv | tempPh)) after copy
    f.write(compute_instruction(BWISE_OR, halt, halt, tempMh, temp3, 0, 0, 0, 0, VP))    # slice.VP = tempMh | temp3

    f.write(compute_instruction(RSHIFT_WORD, halt, halt, Ph, 0, 0, 0, 0, 0, hinP))  # hinP = Ph >> (word), 
    f.write(compute_instruction(BWISE_AND, halt, halt, tempPh, Xv, 0, 0, 0, 0, VN))  # slice.VN = tempPh & Xv
    f.write(compute_instruction(SUBTRACTION, halt, halt, scoreEnd, hinN, 0, 0, 0, 0, scoreEnd))  # scoreEnd = scoreEnd - hinN
    f.write(compute_instruction(ADDITION, halt, halt, scoreEnd, hinP, 0, 0, 0, 0, scoreEnd))  # scoreEnd = scoreEnd + hinP

    f.close()

def pe_0_instruction():
    
    f = open("instructions/gbv/pe_0_instruction.txt", "w")



    f.close()

if not os.path.exists("instructions/gbv"):
    os.makedirs("instructions/gbv")
gbv_compute()
bsw_main_instruction()
pe_0_instruction()
pe_1_instruction()
pe_2_instruction()
pe_3_instruction()
