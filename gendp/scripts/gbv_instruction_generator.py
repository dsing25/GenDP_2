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

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

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

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

    # Jump H Trace Ends Here
    # we skip the ELSE regfile22 < 0 since the scoredifference is always positive

    # start of for loop for wordsize i++ 

    # Jump D Statement
    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onebigger - reg23) 
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 27, 0, 0, 0, 0, 23)) # leastsignificant = reg23 & onebigger
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 21, 23, 0, 0, 0, 0, 21)) # rightsmaller |= -leastsignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    # End of Jump D
    # break statement end of if regfile26 == 0 statement

    # start if reg27 == 0 statement DATA MOVEMENT 
    # Jump F Starts 
    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 26, 23, 0, 0, 0, 0, 23)) # reg23 = ~(onesmaller - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 26, 0, 0, 0, 0, 23)) # leastsignificant = onesmaller & reg23
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 20, 23, 0, 0, 0, 0, 20)) # leftsmaller |= -leastsignificant
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    # Jump F Ends
    #break statement end of if regfile27==0 DATA MOVEMENT 

    # Remainder of Jump B
    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 27, 23, 0, 0, 0, 0, 29)) # reg29 = ~(onebigger - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 29, 27, 0, 0, 0, 0, 29)) # leastSignificantBigger = onebigger & reg29
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(SUBTRACTION, INVALID, BWISE_NOT, 26, 23, 0, 0, 0, 0, 30)) # reg30 = ~(onesmaller - reg23)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 30, 26, 0, 0, 0, 0, 30)) # leastSignificantSmaller = onesmaller & reg30
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    # End of Jump B

    # Jump G Compute
    f.write(compute_instruction(SUBTRACTION, COPY, BWISE_OR, 29, 30, 0, 0, 20, 0, 20)) # leftSmaller |= leastSignificantBigger - leastSignificantSmaller
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    # End of Jump G 

    # Jump B3 Compute
    f.write(compute_instruction(SUBTRACTION, COPY, BWISE_OR, 30, 29, 0, 0, 21, 0, 21)) # rightSmaller |= leastSignificantSmaller - leastSignificantBigger
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    # Jump B3 Compute

    # Remainder of B2 Compute
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 28, 0, 0, 0, 29, 0, 24)) # reg24 = ~twobigger & leastSignificantBIgger
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 27, 24, 0, 0, 0, 0, 27)) # onebigger ^= reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 29, 0, 0, 0, 28, 0, 28)) # twobigger &= ~leastSignificantBigger

    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 25, 0, 0, 0, 30, 0, 24)) # reg24 = ~twosmaller & leastsignificantsmaller
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 26, 24, 0, 0, 0, 0, 26)) # onesmaller ^= reg24
    f.write(compute_instruction(BWISE_NOT, COPY, BWISE_AND, 30, 0, 0, 0, 25, 0, 25)) # twosmaller &= ~leastSignificantSmaller

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    # End of B2 Compute

    # end of for loop for the wordsize loop and end of the program
    # returns a pair make_pair (regfile 20, regfile21)
    # end of differenceMasks

    # continue mergeTwoSlices - 2 Input
    # reg20 and reg21 are set to the outputs from differenceMasks
    # mergeTwoSlices 2 Input returns left, right, reg20, reg21
    # left and right data movement must be done before differencemasks is called to prevent corrupting register state
    # end of mergeTwoSlices - 2 Input

    # This is technically Jump C 
    # May Add stalls in here for SPM
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


    for i in range(1500):
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
    #   Jump A  = PC 70    Jump B  = PC 47    Jump B2 = PC 64
    #   Jump C  = PC 101   Jump D  = PC 89    Jump E  = PC 94
    #   Jump F  = PC 95    Jump G  = PC 98    Jump H  = PC 77
    #   Jump I  = PC 86
    JMPA    = 26   # PC 44 → PC 70 (Jump A)
    JMPB_FWD = -22 # PC 69 → PC 47 (Jump B, from B2)
    JMPC_LOOP = 54 # PC 47 → PC 101 (Jump C, loop exit)
    JMPD    = 39   # PC 50 → PC 89 (Jump D)
    JMPF    = 43   # PC 52 → PC 95 (Jump F)
    JMPG    = 37   # PC 61 → PC 98 (Jump G)
    JMPH    = 7    # PC 70 → PC 77 (Jump H)
    JMPI    = 11   # PC 75 → PC 86 (Jump I)
    JMPA_BACK = -6 # PC 76 → PC 70 (Jump A, loop back)
    JMPB_BACK = -40 # PC 85 → PC 47 (Jump B, from H)
    JMPC_FROM_I = 13 # PC 88 → PC 101 (Jump C, from I)
    JMPE    = 4    # PC 90 → PC 94 (Jump E)
    JMPC_FROM_D = 8 # PC 93 → PC 101 (Jump C, from D)
    JMPC_FROM_E = 7 # PC 94 → PC 101 (Jump C, from E)
    JMPC_FROM_F = 4 # PC 97 → PC 101 (Jump C, from F)
    JMPB2   = -36  # PC 100 → PC 64 (Jump B2, from G)

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

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPA, 0, 0, 0, 0, 4, blt)) # blt 0 gr[4] jump A (PC 44 → 70, +26)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPA, 0, 0, 0, 0, 4, blt)) # blt 0 gr[4] jump A (PC 44 → 70, +26)

    # Jump B - jump here from H
    f.write(data_movement_instruction(gr, 0, 0, 0, 6, 0, 0, 0, 32, 0, si)) # gr[6] = 32 (wordsize)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0 (for loop i=0 counter)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Temp Jump - jump here every other time when you want to come to jump B
    # jump to here (PC 47) when looping back after the initial conditions are set for jump B

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_LOOP, 0, 1, 0, 3, 6, beq)) # beq gr[3] gr[6] jump C (PC 47 → 101, +54)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_LOOP, 0, 1, 0, 3, 6, beq)) # beq gr[3] gr[6] jump C (PC 47 → 101, +54)

    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 7, 0, 0, 0, 26, 0, mv)) # gr[7] = reg[26]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPD, 0, 1, 0, 0, 7, beq)) # beq 0 gr[7] jump D (PC 50 → 89, +39)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPD, 0, 1, 0, 0, 7, beq)) # beq 0 gr[7] jump D (PC 50 → 89, +39)

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPF, 0, 1, 0, 0, 5, beq)) # beq 0 gr[5] jump F (PC 52 → 95, +43)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPF, 0, 1, 0, 0, 5, beq)) # beq 0 gr[5] jump F (PC 52 → 95, +43)

    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 50, 0, 0, 0, 0, 0, set_PC)) # jump B compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 50, 0, 0, 0, 0, 0, set_PC)) 
    
    for i in range(4):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 8, 0, 0, 0, 29, 0, mv)) # gr[8] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 9, 0, 0, 0, 30, 0, mv)) # gr[9] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPG, 0, 1, 0, 9, 8, blt)) # blt gr[9] gr[8] jump G (PC 61 → 98, +37)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPG, 0, 1, 0, 9, 8, blt)) # if false, move on to the b3 compute trace


    # jump B3 in here
    f.write(data_movement_instruction(0, 0, 0, 0, 57, 0, 0, 0, 0, 0, set_PC)) # jump B3 compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 57, 0, 0, 0, 0, 0, set_PC)) 

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # end jump b3 here

    #jump B2 here (PC 58)
    f.write(data_movement_instruction(0, 0, 0, 0, 59, 0, 0, 0, 0, 0, set_PC)) # jump B2 compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 59, 0, 0, 0, 0, 0, set_PC))

    for i in range(4):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    # may need stalls after all of these

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB_FWD, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B (PC 69 → 47, -22)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB_FWD, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B (PC 69 → 47, -22)
    #end jump B2 here
    # End of Jump B

    # Jump A (PC 70)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPH, 0, 1, 0, 3, 4, beq)) # beq gr[3] gr[4] jump H (PC 70 → 77, +7)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPH, 0, 1, 0, 3, 4, beq)) # beq gr[3] gr[4] jump H (PC 70 → 77, +7)

    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 31, 0, 0, 0, 0, 0, set_PC)) # jump A compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 31, 0, 0, 0, 0, 0, set_PC)) 
 
    # Do Some Compute Here - Check if you need data movement

    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPI, 0, 0, 0, 0, 5, beq)) # beq 0 gr[5] jump I (PC 75 → 86, +11)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPI, 0, 0, 0, 0, 5, beq)) # beq 0 gr[5] jump I (PC 75 → 86, +11)

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPA_BACK, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump A (PC 76 → 70, -6)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPA_BACK, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump A (PC 76 → 70, -6)
    # End of Jump A

    # Jump H (PC 71)
    # Do some compute and then jump to B
    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 30, 0, 0, 0, 1, 0, si)) # reg30 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 36, 0, 0, 0, 0, 0, set_PC)) # jump to compute H
    f.write(data_movement_instruction(0, 0, 0, 0, 36, 0, 0, 0, 0, 0, set_PC))

    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB_BACK, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B (PC 85 → 47, -38)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB_BACK, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B (PC 85 → 47, -38)
    # End of Jump H

    # Jump I (PC 80)
    f.write(data_movement_instruction(gr, gr, 0, 0, 20, 0, 0, 0, 1, 0, subi)) # reg20 = 0 - 1 so FFFFF hopefully
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 0, 0, si)) # reg21 = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_I, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 88 → 101, +13)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_I, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 88 → 101, +13)
    # End of Jump I

    # Jump D (PC 89)
    f.write(data_movement_instruction(gr, reg, 0, 0, 5, 0, 0, 0, 27, 0, mv)) # gr[5] = reg[27]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPE, 0, 1, 0, 0, 5, beq)) # beq 0 gr[5] jump E (PC 90 → 94, +4)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPE, 0, 1, 0, 0, 5, beq)) # beq 0 gr[5] jump E (PC 90 → 94, +4)

    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 42, 0, 0, 0, 0, 0, set_PC)) # go to jump D compute PC
    f.write(data_movement_instruction(0, 0, 0, 0, 42, 0, 0, 0, 0, 0, set_PC))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_D, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 93 → 101, +8)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_D, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 93 → 101, +8)
    # End of Jump D

    # Jump E (PC 94)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_E, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 94 → 101, +7)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_E, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 94 → 101, +7)
    # End of Jump E

    # Jump F (PC 95)
    f.write(data_movement_instruction(reg, 0, 0, 0, 23, 0, 0, 0, 1, 0, si)) # reg23 = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 46, 0, 0, 0, 0, 0, set_PC)) # go to jump F compute PC
    f.write(data_movement_instruction(0, 0, 0, 0, 46, 0, 0, 0, 0, 0, set_PC))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_F, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 97 → 101, +4)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_FROM_F, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump C (PC 97 → 101, +4)
    # End of Jump F

    # Jump G (PC 98)
    f.write(data_movement_instruction(0, 0, 0, 0, 55, 0, 0, 0, 0, 0, set_PC)) # jump G compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 55, 0, 0, 0, 0, 0, set_PC))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB2, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B2 (PC 100 → 64, -36)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPB2, 0, 0, 0, 0, 0, beq)) # beq 0 0 jump B2 (PC 100 → 64, -36)
    # End of Jump G

    # Jump C
    f.write(data_movement_instruction(0, 0, 0, 0, 64, 0, 0, 0, 0, 0, set_PC)) # jump C merge4inp compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 64, 0, 0, 0, 0, 0, set_PC)) 
    # End of Jump C

    for i in range(20):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

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



def pe_1_instruction():
    f = InstructionWriter("instructions/gbv/pe_1_instruction.txt")

    # Just halt - do nothing
    for i in range(1500):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

    f.close()

def pe_2_instruction():
    f = InstructionWriter("instructions/gbv/pe_2_instruction.txt")

    # Just halt - do nothing
    for i in range(1500):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

    f.close()

def pe_3_instruction():
    f = InstructionWriter("instructions/gbv/pe_3_instruction.txt")

    # Just halt - do nothing
    for i in range(1500):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

    f.close()

if not os.path.exists("instructions/gbv"):
    os.makedirs("instructions/gbv")
gbv_compute_v3()
gbv_main_instruction()
pe_instruction(0)
pe_1_instruction()
pe_2_instruction()
pe_3_instruction()
