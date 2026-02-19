import sys
import os
from utils import *
from opcodes import *

def gbv_compute_v3():

    f = InstructionWriter("instructions/gbv/compute_instruction.txt")

    # getScoreBeforeStart (2)
    # f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 11, 0, 0, 0, 23, 0, 25)) # scoreEnd - pc(VP) = temp6
    # f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    # f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 24, 0, 25)) # temp6 + pc(VN) = temp6 
    # f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
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
    # BE CAREFUL HERE LATER SINCE REG 25 MAY NOT BE 0
    
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
    # traces work c22 finished above

    f.write(compute_instruction(SUBTRACTION, INVALID, COPY, 18, 14, 0, 0, 0, 0, 31)) # reg31 = reg18 - reg14
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    # BE CAREFUL ON DATA MOVEMENT HERE AND REGISTER MOVEMENTS
    # in here, you need to move all the left and right things to SPM and store it

    # Stall for SPM writes before we do differencemasks. This is part of the merge2Inputs
    for i in range(9):
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

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
    # traces correct up to here cycle 45 finished
    
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

    # Check in Data if reg22 > 0
    # Start of Jump A Trace (reg23 = 1 here) for i < reg22
    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onebigger - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 27, 0, 0, 0, 0, 23)) # leastSignificant = onebigger & reg23
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 28, 0, 0, 0, 23, 0, 24)) # reg24 = ~twoBigger & leastSignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 24, 27, 0, 0, 0, 0, 27)) # onebigger = onebigger ^ reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 23, 0, 0, 0, 28, 0, 28)) # twobigger &= ~leastSignificant;

    # Jump I Trace
    # return std::make_pair(WordConfiguration<Word>::AllOnes, WordConfiguration<Word>::AllZeros);
    # Jump A Trace Ends Here for Data

    # Jump H Starts Here (remainder of the if reg22 > 0 code) sets reg23 = 1 and reg30 = 1 in Data

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onebigger - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 27, 0, 0, 0, 0, 23)) # leastSignificant = onebigger & reg23
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, COPY, BWISE_OR, 23, 30, 0, 0, 20, 0, 20)) # leftSmaller |= leastSignificant - reg30
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 28, 0, 0, 0, 23, 0, 24)) # reg24 = ~twoBigger & leastSignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 24, 27, 0, 0, 0, 0, 27)) # onebigger = onebigger ^ reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 23, 0, 0, 0, 28, 0, 28)) # twobigger &= ~leastSignificant;

    # Jump H Trace Ends Here
    # we skip the ELSE regfile22 < 0 since the scoredifference is always positive

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

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt                                          
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt   

    f.close()

def gbv_main_instruction():
     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    # mergeTwoSlices 2 Input Data Movement
    # Get Left/Right Slices Into PE Array
    PE_COMPUTE_START = 8
    # changing this pe compute start basically changes when the pe data movement starts
    # making this 9 means the reg11 = reg15 and first compute instruction happen together
    # making this 8 means the compute starts then the reg11=reg15 happens

    f = InstructionWriter("instructions/gbv/main_instruction.txt");

    f.write(write_magic(1)) 

    # f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si)) # gr[1] = 0 counter for input data buffer

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 1, mv)) # out = input[gr[1]++]

    # f.write(data_movement_instruction(0, 0, 0, 0, PE_COMPUTE_START, 0, 0, 0, 0, 0, set_PC))


    for i in range(100):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                           # halt
     
    f.close()

# ONLY USE THIS INSTRUCTION GENERATOR FOR THE TIME BEING

def pe_instruction(pe_id):

    # Jump offset constants (relative: offset = target_PC - branch_PC)
    # Each VLIW pair (2 written instructions) = 1 PC step
    #
    # Label locations:
    #   Jump A  = PC 59    Jump B  = PC 47    Jump B2 = PC 58
    #   Jump C  = PC 77    Jump D  = PC 71    Jump E  = PC 74
    #   Jump F  = PC 75    Jump G  = PC 76    Jump H  = PC 65
    #   Jump I  = PC 68
    JMPA    = 13   # PC 46 → PC 59 (Jump A)
    JMPB_FWD = -11 # PC 58 → PC 47 (Jump B, from B2)
    JMPC_LOOP = 28 # PC 49 → PC 77 (Jump C, loop exit)
    JMPD    = 19   # PC 52 → PC 71 (Jump D)
    JMPF    = 21   # PC 54 → PC 75 (Jump F)
    JMPG    = 19   # PC 57 → PC 76 (Jump G)
    JMPH    = 6    # PC 60 → PC 65 (Jump H)
    JMPI    = 5    # PC 63 → PC 68 (Jump I)
    JMPA_BACK = -5 # PC 64 → PC 59 (Jump A, loop back)
    JMPB_BACK = -20 # PC 67 → PC 47 (Jump B, from H)
    JMPC_FROM_I = 7 # PC 70 → PC 77 (Jump C, from I)
    JMPE    = 2    # PC 72 → PC 74 (Jump E)
    JMPC_FROM_D = 4 # PC 73 → PC 77 (Jump C, from D)
    JMPC_FROM_E = 3 # PC 74 → PC 77 (Jump C, from E)
    JMPC_FROM_F = 2 # PC 75 → PC 77 (Jump C, from F)
    JMPB2   = -18  # PC 76 → PC 58 (Jump B2, from G)

    f = InstructionWriter("instructions/gbv/pe_{}_instruction.txt".format(pe_id))

     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++), 
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode
    # VLIW is backwards, 2nd instruction in stream runs first

    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                          
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt)) 

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # this is instruction 2 (runs second in VLIW)                         
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # this is instruction 1 (runs first)                                

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

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))                         

    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 0, 0, si)) # set reg25 = 0 to ensure it works for other iterations
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # the compute starts here, and then reg11 = reg15
    # f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # for some reason, there is a cycle stall when this reg11 = reg15 happens
    # may be due to the set pc in controller?

    # skip these moving instructions for now. mainly used for get score i think but we can just have it be part of merge2input possibly

    # f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv)) # reg[2] = reg[12]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv)) # reg[3] = reg[13]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv)) # reg[14] = reg[25]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv)) # reg[11] = reg[19]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv)) # reg[2] = reg[16]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv)) # reg[3] = reg[17]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv)) # reg[18] = reg[25]    
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Data Movement for merge2Input that stores data into SPM 
    # differenceMasks is the next step after this data movement

    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si)) # gr[2] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 12, 0, mv)) # SPM[gr[2]] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 13, 0, mv)) # SPM[gr[2]++] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 15, 0, mv)) # SPM[gr[2]++] = reg[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 16, 0, mv)) # SPM[gr[2]++] = reg[16]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 17, 0, mv)) # SPM[gr[2]++] = reg[17]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 2, 0, 0, 19, 0, mv)) # SPM[gr[2]++] = reg[19]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # cycle 36 and the test compute instruction line up here. above instruction goes through here

    # differenceMasks Data Movement Trace
    
    f.write(data_movement_instruction(reg, reg, 0, 0, 22, 0, 0, 0, 31, 0, mv)) # reg[22] = reg[31]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 20, 0, 0, 0, 0, 0, mv)) # reg[20] = reg[0]    
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 21, 0, 0, 0, 0, 0, mv)) # reg[21] = reg[0] 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 4, 0, 0, 0, 22, 0, mv)) # gr[4] = reg[22]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 1, 0, si)) # gr[3] = 1 (for loop i=1 counter)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPA, 0, 0, 0, 0, 4, blt)) # blt 0 gr[4] jump A (PC 46 → 59, +13)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Jump B (PC 47)
    # happens on cycle 54 right now
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 32, 0, si)) # gr[6] = 32 (wordsize)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0 (for loop i=0 counter)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # jump to here (PC 49) when looping back after the initial conditions are set for jump B

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_LOOP, 0, 1, 0, 3, 6, beq)) # beq gr[3] gr[6] jump C (PC 49 → 77, +28)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 0, 26, 0, mv)) # gr[7] = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPD, 0, 1, 0, 0, 7, beq)) # beq 0 gr[7] jump D (PC 52 → 71, +19)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPF, 0, 1, 0, 0, 5, beq)) # beq 0 gr[5] jump F (PC 54 → 75, +21)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 8, 0, 0, 0, 29, 0, mv)) # gr[8] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 9, 0, 0, 0, 30, 0, mv)) # gr[9] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPG, 0, 1, 0, 9, 8, beq)) # beq gr[9] gr[8] jump G (PC 57 → 76, +19)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # jump B3 in here
    # do some compute maybe set pcs in all these areas?
    # end jump b3 here

    #jump B2 here (PC 58)
    #do some compute in here

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB_FWD, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B (PC 58 → 47, -11)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    #end jump B2 here
    # End of Jump B

    # Jump A (PC 59)

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPH, 0, 1, 0, 3, 4, beq)) # beq gr[3] gr[4] jump H (PC 60 → 66, +6)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    #maybe want to set PC everywhere to make sure compute follows the path

    # Do Some Compute Here - Check if you need data movement

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPI, 0, 0, 0, 0, 5, beq)) # beq 0 gr[5] jump I (PC 63 → 68, +5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPA_BACK, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump A (PC 64 → 59, -5)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump A

    # Jump H (PC 65)
    # Do some compute and then jump to B
    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 30, 0, 0, 0, 1, 0, si)) # reg30 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB_BACK, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B (PC 67 → 47, -20)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump H

    # Jump I (PC 68)
    f.write(data_movement_instruction(gr, gr, 0, 0, 20, 0, 0, 0, 1, 0, subi)) # reg20 = 0 - 1 so FFFFF hopefully
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 0, 0, si)) # reg21 = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_I, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 70 → 77, +7)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump I

    # Jump D (PC 71)
    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPE, 0, 1, 0, 0, 5, beq)) # beq 0 gr[5] jump E (PC 72 → 74, +2)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    #do some compute

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_D, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 73 → 77, +4)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump D

    # Jump E (PC 74)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_E, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 74 → 77, +3)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump E

    # Jump F (PC 75)
    #do some compute
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_F, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 75 → 77, +2)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump F

    # Jump G (PC 76)
    #do some compute
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB2, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B2 (PC 76 → 58, -18)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # End of Jump G

    # Jump C

    # End of Jump C

    # merge 4 inputs data movement

    f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 1, 0, 2, mv)) # reg[12] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  


    f.write(data_movement_instruction(reg, SPM, 0, 0, 13, 0, 0, 1, 0, 2, mv)) # reg[13] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))   

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 0, 0, 1, 0, 2, mv)) # reg[15] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  

    f.write(data_movement_instruction(reg, SPM, 0, 0, 16, 0, 0, 1, 0, 2, mv)) # reg[16] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, SPM, 0, 0, 17, 0, 0, 1, 0, 2, mv)) # reg[17] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 

    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 0, 0, 1, 0, 2, mv)) # reg[19] = SPM[gr[2]++]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) 
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  
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

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 3, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))


    f.write(data_movement_instruction(SPM, reg, 0, 1, 8, 10, 0, 0, 11, 0, mv)) # SPM[8(gr[10]++)] = reg[2]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
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
# pe_0_instruction()
# pe_1_instruction()
# pe_2_instruction()
# pe_3_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
