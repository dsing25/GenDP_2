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

    # Jump G Compute (if reg30 < reg29) 
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
    # lol i had them flipped that sucked to debug
    f.write(compute_instruction(COPY, BWISE_NOT, BWISE_AND, 13, 0, 0, 0, 22, 0, 26)) # reg26 = leftvp & ~mask
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 17, 22, 0, 0, 0, 0, 27)) # reg27 = rightVP & mask

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 26, 27, 0, 0, 0, 0, 29)) # reg29 = (left.VP & ~mask) | (right.VP & mask);
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 

    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 15, 19, 19, 15, 0, 0, 30)) # reg15 > reg19, then minimum is reg19, or else reg15. save into reg30
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) 



    # do data movement to finalize the merge slices
    #END OF mergeTwoSlices - 4 Input

    # do result.getScore for some reason?
    # f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 30, 0, 0, 0, 29, 0, 25)) # scoreEnd - pc(VP) = temp6
    # f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # f.write(compute_instruction(COPY, POPCOUNT, ADD, 25, 0, 0, 0, 28, 0, 11)) # temp6 + pc(VN) = reg14
    # f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # EQUALITY VECTOR DOESNT WORK FIX HERE USING SPM. CHANGE ALL PREVIOUS SPM MAPPINGS SO EQ is the FIRST 4 ENTRIES IN SPM
    # AT ALL TIMES
    # SEND IN BASEPAIR USING CONTROLLER

    # Cycle 0
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 1, 2, 0, 0, 0, 0, 7))  # Xv = Eq | VN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 1, 4, 0, 0, 0, 0, 1))  # Eq = Eq | hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_AND, COPY, ADD, 1, 3, 0, 0, 3, 0, 20)) # temp1 = ((Eq & VP) copied, then + VP)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_XOR, COPY, BWISE_OR, 20, 3, 1, 0, 0, 0, 6))  # Xh = (temp1 ^ VP) copied, then OR with Eq
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    
    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, 3, 6, 0, 0, 0, 0, 21)) # temp2 = (~(VP | Xh)) after copy
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 2, 21, 0, 0, 0, 0, 8))     # Ph = VN | temp2        
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))                             
    
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 3, 6, 0, 0, 0, 0, 9))  # Mh = VP & Xh
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, 9, 0, 0, 0, 4, 0, 22)) # tempMh = (Mh << 1) | hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    #Cycle 8 below
    f.write(compute_instruction(RSHIFT_WORD, INVALID, COPY, 9, 0, 0, 0, 0, 0, 4))  # hinN = Mh >> (word)
    f.write(compute_instruction(LSHIFT_1, COPY, BWISE_OR, 8, 0, 0, 0, 5, 0, 23)) # tempPh = (Ph << 1) | hinP

    f.write(compute_instruction(BWISE_OR, COPY, BWISE_NOT, 7, 23, 0, 0, 0, 0, 20)) # temp1 = (~(Xv | tempPh)) after copy
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 22, 20, 0, 0, 0, 0, 3))    # slice.VP = tempMh | temp1
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(RSHIFT_WORD, INVALID, COPY, 8, 0, 0, 0, 0, 0, 5))  # hinP = Ph >> (word), 
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 23, 7, 0, 0, 0, 0, 2))  # slice.VN = tempPh & Xv

    f.write(compute_instruction(SUBTRACTION, INVALID, COPY, 11, 4, 0, 0, 0, 0, 11))  # scoreEnd = scoreEnd - hinN
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    f.write(compute_instruction(ADD, INVALID, COPY, 11, 5, 0, 0, 0, 0, 11))  # scoreEnd = scoreEnd + hinP
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # f.write(compute_instruction(POPCOUNT, POPCOUNT, SUBTRACTION, 3, 0, 0, 0, 2, 0, 20))  # temp1 = popcount(VP) - popcount(VN)
    # f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    
    # f.write(compute_instruction(ADD, INVALID, ADD, 20, 10, 11, 0, 0, 0, 11)) # scoreEnd = (temp1 + scorebefore) + scoreEnd
    # f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0)) # cycle 15 finished here

    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt
    f.write(compute_instruction(16, 15, 15, 0, 0, 0, 0, 0, 0, 0))       # halt

    # ============================================================
    # Step 7 Compute: forceEq XOR operation (PC 85)
    # ============================================================
    # Pad to reach PC 85 (plenty of margin past getNextSlice)
    for i in range(6):  # 6 PCs of padding to ensure we reach PC 85
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
        f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # PC 85: Step 7 XOR operation
    # reg[10] = reg[31] XOR reg[20] (AllOnes XOR 1 = 0xFFFFFFFFFFFFFFFE)
    f.write(compute_instruction(BWISE_XOR, INVALID, COPY, 31, 20, 0, 0, 0, 0, 10))  # reg[10] = reg[31] ^ reg[20]
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # PC 86: Step 9 - Apply forceEq: reg[1] = reg[1] & reg[10]
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 1, 10, 0, 0, 0, 0, 1))  # reg[1] &= reg[10]
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # PC 87: Step 10 - forceMask: VP &= (AllOnes XOR 1), i.e. reg[3] &= 0xFFFFFFFFFFFFFFFE
    # Uses reg[20] which should have 0xFFFFFFFFFFFFFFFE from Step 7 FALSE path, or we recompute
    f.write(compute_instruction(BWISE_AND, INVALID, COPY, 3, 10, 0, 0, 0, 0, 3))  # reg[3] &= reg[10] (forceEq has the mask)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # PC 88: Step 10 - forceMask: VN |= 1
    f.write(compute_instruction(BWISE_OR, INVALID, COPY, 2, 20, 0, 0, 0, 0, 2))  # reg[2] |= reg[20] (reg[20]=1 from setup)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # ============================================================
    # Step 11 Compute: Score comparison for hinP/hinN
    # ============================================================
    # PC 89: Compute mergeScore = reg[30] - popcount(reg[29]) + popcount(reg[28])
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 30, 0, 0, 0, 29, 0, 21))  # reg[21] = scoreEnd - pc(VP)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(COPY, POPCOUNT, ADD, 21, 0, 0, 0, 28, 0, 21))  # reg[21] = reg[21] + pc(VN) = mergeScore
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # PC 91: Compute wsScore = reg[11] - popcount(reg[3]) + popcount(reg[2])
    f.write(compute_instruction(COPY, POPCOUNT, SUBTRACTION, 11, 0, 0, 0, 3, 0, 22))  # reg[22] = scoreEnd - pc(VP)
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))
    f.write(compute_instruction(COPY, POPCOUNT, ADD, 22, 0, 0, 0, 2, 0, 22))  # reg[22] = reg[22] + pc(VN) = wsScore
    f.write(compute_instruction(INVALID, INVALID, INVALID, 0, 0, 0, 0, 0, 0, 0))

    # PC 93: hinP = (mergeScore > wsScore) ? 1 : 0, hinN = (mergeScore < wsScore) ? 1 : 0
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 21, 22, 20, 0, 0, 0, 5))  # reg[5] = (reg[21] > reg[22]) ? reg[20](1) : 0 = hinP
    f.write(compute_instruction(COMP_LARGER, INVALID, COPY, 22, 21, 20, 0, 0, 0, 4))  # reg[4] = (reg[22] > reg[21]) ? reg[20](1) : 0 = hinN

    # PC 94: hinP = Ph >> 31, hinN = Mh >> 31 (for scoreEnd == -1 case)
    f.write(compute_instruction(RSHIFT_WORD, INVALID, COPY, 8, 0, 0, 0, 0, 0, 5))  # reg[5] = Ph >> word = hinP
    f.write(compute_instruction(RSHIFT_WORD, INVALID, COPY, 9, 0, 0, 0, 0, 0, 4))  # reg[4] = Mh >> word = hinN

    f.close()

def gbv_main_instruction():
     # dest, src, flag_0, flag_1, imm/reg_0, reg_0(++),
     # flag_2, flag_3, imm/reg_1, reg_1(++), opcode

    # mergeTwoSlices 2 Input Data Movement
    # Get Left/Right Slices Into PE Array
    PE_COMPUTE_START = 8 # this isnt used anywhere anymore so doesnt matter for right now
    # changing this pe compute start basically changes when the pe data movement starts
    # making this 9 means the reg11 = reg15 and first compute instruction happen together
    # making this 8 means the compute starts then the reg11=reg15 happens

    f = InstructionWriter("instructions/gbv/main_instruction.txt");

    f.write(write_magic(1))

    # ============================================================
    # Step 1: Pop Node from Queue (Controller)
    # ============================================================
    # magic(5) = peek top of queue
    # After magic(5):
    #   gr[0]  = 0 (ALWAYS - not written by magic)
    #   gr[1]  = target_node (node ID)
    #   gr[2]  = spm_addr
    #   gr[3]  = flags (bit0=skipFirst, bit1=prevSliceExists, bit2=currSliceExists, bit3=valid)
    #   gr[4]  = basepair (single BP value 0-3, from magic(9))
    #   gr[5]  = temp for magic(7) (neighbor index -> neighbor_id)
    #   gr[6]  = num_out_neighbors
    #   gr[7]  = (empty - was num_chunks, no longer needed)
    #   gr[8]  = (empty)
    #   gr[9]  = temp for magic(12) (neighbor's SPM addr)
    #   gr[10] = num_in_neighbors
    #   gr[11] = node_length (total basepairs)
    #   gr[12] = neighbor index counter (for in-neighbor loop)
    #   gr[13] = (hardware sync)
    #   gr[14] = BP sent counter / position index for magic(9)
    #   gr[15] = (empty)
    # Valid check: (gr[3] >> 3) & 1 == 1 means queue has entry
    f.write(write_magic(5))  # peek top of queue

    # TODO: Add branch to handle empty queue case
    # Check: if (gr[3] >> 3) & 1 == 0, queue is empty - jump to halt

    # magic(4) = pop from queue (removes the peeked entry, no register writes)
    f.write(write_magic(4))  # pop from queue

    # ============================================================
    # Step 2: Controller Setup and Basepair Loop
    # ============================================================

    # 2.2: Initialize Controller Loop Variables
    # gr[14] = 0: BP sent counter (also used as position index by magic(9))
    # gr[11] = node_length already set by magic(5) - no computation needed
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))  # PC 3: gr[14] = 0 (BP sent counter)
    # PC 4: NOP (padding to keep PE sends at PC 5-8)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # 2.4: Send Initial Data to PE (PC 5-8)
    # ============================================================
    # Send BEFORE neighbor loop so PE knows num_in_neighbors and can loop to receive pairs
    # PE receives at same PC (no latency): Controller PC 5 -> PE PC 5
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 1, 0, mv))   # PC 5: out = gr[1] (node_id) -> PE gr[1]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 2, 0, mv))   # PC 6: out = gr[2] (spm_addr) -> PE gr[2]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 10, 0, mv))  # PC 7: out = gr[10] (num_in_neighbors) -> PE gr[10]
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 3, 0, mv))   # PC 8: out = gr[3] (flags) -> PE gr[7]

    # ============================================================
    # Step 1.5 / 2.3: In-Neighbor Loop (Controller)
    # ============================================================
    # gr[10] = num_in_neighbors (from magic(5))
    # gr[12] = neighbor index counter (0 to num_in_neighbors-1)
    # gr[5] = temp for magic(7) I/O: input=index, output=neighbor_id
    # gr[9] = temp for magic(12) output: neighbor's SPM address
    #
    # If gr[10] == 0: skip to BP loop (no in-neighbors)
    # Otherwise: loop gr[10] times, each iteration:
    #   1. gr[5] = gr[12] (copy index)
    #   2. magic(7): gr[5] = in_neighbor_id (reads gr[1]=node_id, gr[5]=index)
    #   3. magic(12): gr[9] = spm_addr (reads gr[5]=neighbor_node_id)
    #   4. out_port = gr[5] (send neighbor_id to PE)
    #   5. out_port = gr[9] (send neighbor_spm_addr to PE)
    #   6. gr[12]++ (increment index)
    #   7. gr[10]-- (decrement remaining count)
    #   8. if gr[10] != 0, goto NEIGHBOR_LOOP

    # PC 9: gr[12] = 0 (neighbor index counter)
    f.write(data_movement_instruction(gr, 0, 0, 0, 12, 0, 0, 0, 0, 0, si))  # gr[12] = 0

    # PC 10: if gr[10] == 0, skip neighbor loop (jump to BP_LOOP_START)
    NEIGHBOR_SKIP_OFFSET = 9  # PC 10 -> PC 19
    f.write(data_movement_instruction(gr, gr, 0, 0, NEIGHBOR_SKIP_OFFSET, 0, 0, 0, 0, 10, beq))  # if gr[10] == 0, skip

    # PC 11: NEIGHBOR_LOOP_START - gr[5] = gr[12] (copy index for magic(7) input)
    NEIGHBOR_LOOP_START_PC = 11
    f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 12, 0, mv))  # gr[5] = gr[12]

    # PC 12: magic(7) - get in_neighbor[gr[5]] -> gr[5] = neighbor_id
    f.write(write_magic(7))

    # PC 13: magic(12) - CAM lookup gr[5] -> gr[9] = neighbor's SPM addr
    f.write(write_magic(12))

    # PC 14: Send neighbor_id to PE via out_port
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 5, 0, mv))  # out = gr[5] (neighbor_id)

    # PC 15: Send neighbor's SPM addr to PE via out_port
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 9, 0, mv))  # out = gr[9] (neighbor_spm_addr)

    # PC 16: gr[12]++ (increment neighbor index)
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, addi))  # gr[12]++

    # PC 17: gr[10]-- (decrement remaining in-neighbors count)
    f.write(data_movement_instruction(gr, gr, 0, 0, 10, 0, 0, 0, 1, 10, subi))  # gr[10]--

    # PC 18: if gr[10] != 0, loop back to NEIGHBOR_LOOP_START
    NEIGHBOR_LOOP_BACK = NEIGHBOR_LOOP_START_PC - 18  # = -7
    f.write(data_movement_instruction(gr, gr, 0, 0, NEIGHBOR_LOOP_BACK, 0, 0, 0, 0, 10, bne))  # if gr[10] != 0, goto NEIGHBOR_LOOP

    # ============================================================
    # 2.5: Controller Basepair Loop (1 BP at a time via magic(9))
    # ============================================================
    # Controller PC layout:
    #   PC 0-2:   magic(1), magic(5), magic(4)
    #   PC 3:     gr[14]=0 (BP sent counter / position index)
    #   PC 4:     NOP
    #   PC 5-8:   Send initial data to PE (node_id, spm_addr, num_in_neighbors, flags)
    #   PC 9:     gr[12]=0 (neighbor index counter)
    #   PC 10:    beq gr[10]==0, skip neighbor loop -> PC 19
    #   PC 11-18: NEIGHBOR_LOOP (copy idx, magic(7), magic(12), send pair, incr, decr, branch)
    #   PC 19:    LOOP_START - check if done (bge gr[14] gr[11] -> DONE)
    #   PC 20:    magic(9) - fetch 1 BP into gr[4] (reads gr[1]=node_id, gr[14]=position)
    #   PC 21:    Send BP to PE (out = gr[4])
    #   PC 22:    Wait for PE (spin on gr[13] == 0)
    #   PC 23:    Restart PE at basepair processing PC
    #   PC 24:    Increment gr[14] (BP sent counter / position)
    #   PC 25:    Jump back to LOOP_START
    #   PC 26:    DONE - continue to halt or next phase

    # Jump offsets (relative: offset = target_PC - current_PC)
    BP_LOOP_START_PC = 19
    BP_DONE_PC = 26
    # PE_BP_START_PC: Where PE's BP_LOOP_START is (Step 9 receive BP)
    # This is after: initial setup, neighbor loop, Steps 3.5-7
    # Approximate PC ~115 (calibrate during testing)
    PE_BP_START_PC = 115

    # PC 19: LOOP_START - Check if all basepairs processed
    DONE_OFFSET = BP_DONE_PC - BP_LOOP_START_PC  # = 7
    f.write(data_movement_instruction(gr, gr, 0, 0, DONE_OFFSET, 0, 1, 0, 14, 11, bge))  # if gr[14] >= gr[11], goto DONE

    # PC 20: Fetch 1 basepair via magic(9) -> gr[4] (reads gr[1]=node_id, gr[14]=position)
    f.write(write_magic(9))

    # PC 21: Send basepair to PE
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 4, 0, mv))  # out = gr[4] (basepair value 0-3)

    # PC 22: Wait for PE to complete (spin while gr[13] == 0)
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 13, beq))  # spin while gr[13] == 0

    # PC 23: Restart PE at basepair processing PC
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BP_START_PC, 0, 0, 0, 0, 0, set_PC))  # set_PC for PE

    # PC 24: Increment BP sent counter (also serves as position for next magic(9))
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 14, addi))  # gr[14]++

    # PC 25: Jump back to LOOP_START
    JUMP_BACK_OFFSET = BP_LOOP_START_PC - 25  # = -6
    f.write(data_movement_instruction(gr, gr, 0, 0, JUMP_BACK_OFFSET, 0, 0, 0, 0, 0, beq))  # unconditional jump (beq 0 0)

    # ============================================================
    # Step 14: Push Successors to Queue
    # ============================================================
    # PC 26: DONE - all basepairs processed
    # Wait for PE final sync (gr[13] should be 1 from last BP)
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 13, beq))  # spin while gr[13] == 0

    # Initialize out-neighbor loop counter
    # gr[6] = num_out_neighbors (from queue, set by magic(5))
    # gr[12] = loop counter (reuse from in-neighbor loop)
    f.write(data_movement_instruction(gr, 0, 0, 0, 12, 0, 0, 0, 0, 0, si))  # gr[12] = 0

    # OUT_NEIGHBOR_LOOP_START (PC 28)
    OUT_NEIGHBOR_LOOP_START_PC = 28
    OUT_NEIGHBOR_DONE_PC = 35  # After loop

    # PC 28: Check if done (gr[12] >= gr[6])
    OUT_NEIGHBOR_DONE_OFFSET = OUT_NEIGHBOR_DONE_PC - OUT_NEIGHBOR_LOOP_START_PC  # = 7
    f.write(data_movement_instruction(gr, gr, 0, 0, OUT_NEIGHBOR_DONE_OFFSET, 0, 1, 0, 12, 6, bge))  # if gr[12] >= gr[6], done

    # PC 29: Get out-neighbor node_id via magic(8)
    # magic(8) reads gr[1]=current_node_id, gr[12]=neighbor_index
    # outputs: gr[2]=neighbor_node_id, gr[3]=flags, gr[5]=num_in_neighbors, gr[9]=node_length
    f.write(write_magic(8))

    # PC 30: Set up queue entry for magic(3) push
    # Queue entry format for magic(3):
    # gr[0]=target_node_id, gr[1]=spm_addr, gr[2]=flags, gr[3]=num_out_neighbors (set to 0 for successors)
    # Note: Controller gr[0] can be used (only PE gr[0] must stay 0)
    # For successor: target_node_id=gr[2], spm_addr=from PE SPM, flags=from PE, num_out_neighbors=0

    # Move neighbor_node_id to gr[0] for magic(3) input
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 2, 0, mv))  # gr[0] = gr[2] (neighbor_node_id)

    # For spm_addr (gr[1]), flags (gr[2]), use values from PE's processing
    # These would need to come from PE SPM or be computed
    # For now, use placeholder values (to be filled with actual logic)
    # gr[1] = spm_addr (successor's SPM location)
    # gr[2] = flags (successor's flags)
    # gr[3] = 0 (num_out_neighbors for successor, initially 0)

    # PC 31: magic(3) - Push successor to queue
    f.write(write_magic(3))

    # PC 32: Increment out-neighbor counter
    f.write(data_movement_instruction(gr, gr, 0, 0, 12, 0, 0, 0, 1, 12, addi))  # gr[12]++

    # PC 33: Jump back to OUT_NEIGHBOR_LOOP_START
    OUT_NEIGHBOR_LOOP_BACK = OUT_NEIGHBOR_LOOP_START_PC - 33  # = -5
    f.write(data_movement_instruction(gr, gr, 0, 0, OUT_NEIGHBOR_LOOP_BACK, 0, 0, 0, 0, 0, beq))  # unconditional jump

    # ============================================================
    # Step 15: Restart Main Loop
    # ============================================================
    # PC 34: Jump back to Step 1 (queue pop at PC 0)
    RESTART_MAIN_LOOP_OFFSET = 0 - 34  # = -34
    f.write(data_movement_instruction(gr, gr, 0, 0, RESTART_MAIN_LOOP_OFFSET, 0, 0, 0, 0, 0, beq))  # jump to PC 0

    # PC 35+: Padding and eventual halt (if queue becomes empty, magic(5) would handle exit)
    for i in range(100):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
     
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
    #
    # ============================================================
    # PE/Controller Timing Alignment
    # ============================================================
    # Controller timeline:
    #   PC 0: magic(1)
    #   PC 1: magic(5) - peek queue
    #   PC 2: magic(4) - pop queue
    #   PC 3: gr[14] = 0
    #   PC 4: NOP
    #   PC 5: out = gr[1] (node_id)      ← First send
    #   PC 6: out = gr[2] (spm_addr)
    #   PC 7: out = gr[10] (num_in_neighbors)
    #   PC 8: out = gr[3] (flags)
    #   PC 9-18: Neighbor loop (sends neighbor_id, neighbor_spm_addr pairs)
    #   PC 19+: BP loop
    #
    # PE receives at same PC (no latency):
    #   PC 5: gr[1] = in (node_id)
    #   PC 6: gr[2] = in (spm_addr)
    #   PC 7: gr[13] = in (num_in_neighbors) - NOT gr[10], that's sync only
    #   PC 8: gr[7] = in (flags)
    #   PC 9: beq skip neighbor loop if gr[13]==0 -> PC 19
    #   PC 10-13: NOPs (waiting for controller to reach PC 14)
    #   PC 14: gr[11] = in (neighbor_id)
    #   PC 15: gr[12] = in (neighbor_spm_addr)
    #   PC 16: gr[13]--
    #   PC 17: NOP
    #   PC 18: bne loop back to PC 11 if gr[13]!=0
    #   PC 19: AFTER_NEIGHBOR_LOOP - continue with setup
    # ============================================================

    # PC 0-4: Wait for controller to finish setup and start sending
    for i in range(5):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 5: Receive node_id from controller → PE gr[1]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 1, 0, 0, 0, 0, 0, mv))  # gr[1] = in (node_id)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 6: Receive spm_addr from controller → PE gr[2]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 2, 0, 0, 0, 0, 0, mv))  # gr[2] = in (spm_addr)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 7: Receive num_in_neighbors from controller → PE gr[13] (NOT gr[10] - that's sync only)
    f.write(data_movement_instruction(gr, in_port, 0, 0, 13, 0, 0, 0, 0, 0, mv))  # gr[13] = in (num_in_neighbors)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 8: Receive flags from controller → PE gr[7]
    # flags: bit0=skipFirst, bit1=prevSliceExists, bit2=currSliceExists, bit3=valid
    f.write(data_movement_instruction(gr, in_port, 0, 0, 7, 0, 0, 0, 0, 0, mv))  # gr[7] = in (flags)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # Step 3.5: Receive In-Neighbor Data (PE)
    # ============================================================
    # gr[10] = SYNC FLAG ONLY - never use for anything else
    # gr[11] = temp for neighbor_id (received from controller)
    # gr[12] = neighbor_spm_addr (received from controller, kept for SPM access)
    # gr[13] = num_in_neighbors / loop counter (received above, decremented in loop)
    #
    # Controller timeline:
    #   PC 9:  gr[12]=0 (neighbor index counter)
    #   PC 10: beq skip if no neighbors
    #   PC 11: gr[5] = gr[12]
    #   PC 12: magic(7)
    #   PC 13: magic(12)
    #   PC 14: out = gr[5] (neighbor_id)     ← First send
    #   PC 15: out = gr[9] (neighbor_spm_addr)
    #   PC 16-18: increment, decrement, branch
    #
    # PE must align receives with controller sends at PC 14-15
    #
    # PC 9: If no in-neighbors, skip to AFTER_NEIGHBOR_LOOP (PC 19)
    NEIGHBOR_SKIP_OFFSET = 10  # PC 9 -> PC 19
    f.write(data_movement_instruction(gr, gr, 0, 0, NEIGHBOR_SKIP_OFFSET, 0, 0, 0, 0, 13, beq))  # if gr[13]==0, skip
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 10-13: NOPs to align with controller (controller sends at PC 14)
    for i in range(4):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 14: NEIGHBOR_RECV_LOOP - Receive neighbor_id → gr[11] (aligned with controller PC 14)
    PE_NEIGHBOR_LOOP_PC = 14
    f.write(data_movement_instruction(gr, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))  # gr[11] = in (neighbor_id)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 15: Receive neighbor_spm_addr → gr[12] (aligned with controller PC 15)
    f.write(data_movement_instruction(gr, in_port, 0, 0, 12, 0, 0, 0, 0, 0, mv))  # gr[12] = in (neighbor_spm_addr)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 16: gr[13]-- (decrement loop counter, NOT gr[10] which is sync only)
    f.write(data_movement_instruction(gr, gr, 0, 0, 13, 0, 0, 0, 1, 13, subi))  # gr[13]--
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 17: NOP (align with controller PC 17)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 18: If gr[13] != 0, loop back (aligned with controller PC 18)
    # PE loops back to PC 11 to wait with NOPs for controller to reach PC 14 again
    NEIGHBOR_LOOP_BACK = 11 - 18  # = -7 (back to PC 11)
    f.write(data_movement_instruction(gr, gr, 0, 0, NEIGHBOR_LOOP_BACK, 0, 0, 0, 0, 13, bne))  # if gr[13]!=0, loop
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 19: AFTER_NEIGHBOR_LOOP
    # gr[12] = last neighbor's SPM address (if any neighbors existed, else 0)
    # gr[7] = flags (bit0=skipFirst, bit1=prevSliceExists, bit2=currSliceExists)

    # ============================================================
    # Step 3.6: Check if had incoming neighbors
    # ============================================================
    # If gr[12] != 0: Had neighbors, load neighbor slice from SPM[gr[12]], skip Step 4
    # If gr[12] == 0: No neighbors, do Step 4 (skipFirst check)
    #
    # PC 19: Check if had neighbors
    HAS_NEIGHBORS_OFFSET = 20  # Jump to Step 3.6 path (skip Step 4)
    f.write(data_movement_instruction(gr, gr, 0, 0, HAS_NEIGHBORS_OFFSET, 0, 0, 0, 0, 12, bne))  # if gr[12]!=0, had neighbors
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # Step 4: Handle skipFirst Flag (no neighbors path)
    # ============================================================
    # gr[14] = gr[7] & 1 to extract skipFirst bit
    # PC 20
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 7, ANDI))  # gr[14] = gr[7] & 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # PC 21: If skipFirst (gr[14] != 0), jump to SKIP_FIRST_TRUE
    SKIP_FIRST_TRUE_OFFSET = 12  # Jump over FALSE path
    f.write(data_movement_instruction(gr, gr, 0, 0, SKIP_FIRST_TRUE_OFFSET, 0, 0, 0, 0, 14, bne))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- skipFirst == FALSE path ----
    # Set left slice: reg[12]=0 (VN), reg[13]=0 (VP), reg[15]=-1 (scoreEnd)
    # PC 21-23: Set defaults
    f.write(data_movement_instruction(reg, 0, 0, 0, 12, 0, 0, 0, 0, 0, si))  # reg[12] = 0 (VN)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 13, 0, 0, 0, 0, 0, si))  # reg[13] = 0 (VP)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 15, 0, 0, 0, 0xFFFF, 0, si))  # reg[15] = -1 (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Copy to right slice: reg[16]=0, reg[17]=0, reg[19]=-1
    f.write(data_movement_instruction(reg, 0, 0, 0, 16, 0, 0, 0, 0, 0, si))  # reg[16] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 17, 0, 0, 0, 0, 0, si))  # reg[17] = 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 19, 0, 0, 0, 0xFFFF, 0, si))  # reg[19] = -1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Write defaults to SPM[15-17] for persistence
    f.write(data_movement_instruction(gr, 0, 0, 0, 15, 0, 0, 0, 15, 0, si))  # gr[15] = 15 (SPM addr)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 15, 0, 0, 13, 0, mv))  # SPM[15] = reg[13] (VP=0)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # SPM latency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 1, 0, 15, 0, 0, 12, 0, mv))  # SPM[16] = reg[12] (VN=0)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 15, 0, 0, 15, 0, mv))  # SPM[17] = reg[15] (scoreEnd=-1)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Jump to AFTER_SKIP_FIRST
    AFTER_SKIP_FIRST_OFFSET = 10  # Skip TRUE path
    f.write(data_movement_instruction(gr, gr, 0, 0, AFTER_SKIP_FIRST_OFFSET, 0, 0, 0, 0, 0, beq))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- skipFirst == TRUE path (SKIP_FIRST_TRUE) ----
    # Load extraSlice from SPM[15-17] into left and right slice registers
    f.write(data_movement_instruction(gr, 0, 0, 0, 15, 0, 0, 0, 15, 0, si))  # gr[15] = 15 (SPM addr)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 1, 13, 15, 0, 0, 0, 0, mv))  # reg[13] = SPM[15] (VP)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 1, 12, 15, 0, 0, 0, 0, mv))  # reg[12] = SPM[16] (VN)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 15, 0, 0, 0, 0, mv))  # reg[15] = SPM[17] (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Copy to right slice
    f.write(data_movement_instruction(reg, reg, 0, 0, 17, 0, 0, 0, 13, 0, mv))  # reg[17] = reg[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 16, 0, 0, 0, 12, 0, mv))  # reg[16] = reg[12]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, reg, 0, 0, 19, 0, 0, 0, 15, 0, mv))  # reg[19] = reg[15]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Jump to AFTER_ALL_SLICE_SETUP (skip Step 3.6)
    SKIP_STEP_3_6_OFFSET = 14
    f.write(data_movement_instruction(gr, gr, 0, 0, SKIP_STEP_3_6_OFFSET, 0, 0, 0, 0, 0, beq))  # unconditional
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # Step 3.6: HAS_NEIGHBORS path - Load neighbor slice + extraSlice
    # ============================================================
    # gr[12] = neighbor's SPM address
    # Load neighbor slice from SPM[gr[12], gr[12]+1, gr[12]+2] into left: reg[12,13,15]
    f.write(data_movement_instruction(reg, SPM, 0, 1, 12, 12, 0, 0, 0, 0, mv))  # reg[12] = SPM[gr[12]++] (VN)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 1, 13, 12, 0, 0, 0, 0, mv))  # reg[13] = SPM[gr[12]++] (VP)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 0, 15, 12, 0, 0, 0, 0, mv))  # reg[15] = SPM[gr[12]] (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Load extraSlice from SPM[15-17] into right: reg[16,17,19]
    f.write(data_movement_instruction(gr, 0, 0, 0, 15, 0, 0, 0, 15, 0, si))  # gr[15] = 15
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 1, 17, 15, 0, 0, 0, 0, mv))  # reg[17] = SPM[15++] (VP)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 1, 16, 15, 0, 0, 0, 0, mv))  # reg[16] = SPM[16++] (VN)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 15, 0, 0, 0, 0, mv))  # reg[19] = SPM[17] (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- AFTER_ALL_SLICE_SETUP ----
    # Left slice: reg[12,13,15] = VN, VP, scoreEnd
    # Right slice: reg[16,17,19] = VN, VP, scoreEnd
    # Ready for Step 5 merge

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 0, 0, si))  # reg25 = 0 for other iterations
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Data Movement for merge2Input that stores data into SPM
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 4, 0, si))  # gr[2] = 4 (offset to avoid magic SPM[0-3])
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
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # in here so code works, can be deleted later
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # COMMENT THIS OUT LATER AND MAKE SURE THE OFFSETS WORK PROPERLY

    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si)) # gr[3] = 0 (for loop i=0 counter)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Temp Jump - jump here every other time when you want to come to jump B
    # jump to here (PC 47) when looping back after the initial conditions are set for jump B

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_LOOP, 0, 0, 0, 32, 3, beq)) # beq 32 gr[3] jump C (PC 47 → 101, +54)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPC_LOOP, 0, 0, 0, 32, 3, beq)) # beq 32 gr[3] jump C (PC 47 → 101, +54)

    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi)) # gr[3] = gr[3] + 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, reg, 0, 0, 4, 0, 0, 0, 26, 0, mv)) # gr[4] = reg[26] (reusing gr[4] after reg22 no longer needed)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPD, 0, 1, 0, 0, 4, beq)) # beq 0 gr[4] jump D (PC 50 → 89, +39)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPD, 0, 1, 0, 0, 4, beq)) # beq 0 gr[4] jump D (PC 50 → 89, +39)

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

    f.write(data_movement_instruction(gr, gr, 0, 0, JMPG, 0, 1, 0, 9, 8, bltu)) # blt gr[9] gr[8] jump G (PC 61 → 98, +37)
    f.write(data_movement_instruction(gr, gr, 0, 0, JMPG, 0, 1, 0, 9, 8, bltu)) # if false, move on to the b3 compute trace


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
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 4, 0, si)) # gr[2] = 4 (offset to avoid magic SPM[0-3])
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
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

    f.write(data_movement_instruction(0, 0, 0, 0, 64, 0, 0, 0, 0, 0, set_PC)) # jump C merge4inp compute trace
    f.write(data_movement_instruction(0, 0, 0, 0, 64, 0, 0, 0, 0, 0, set_PC)) 

    # f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 15, 0, mv)) # reg[11] = reg[15] 
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 12, 0, mv))   # reg[2] = reg[12]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 13, 0, mv))   # reg[3] = reg[13]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 14, 0, 0, 0, 25, 0, mv))  # reg[14] = reg[25]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 19, 0, mv))  # reg[11] = reg[19]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 16, 0, mv))   # reg[2] = reg[16]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 17, 0, mv))   # reg[3] = reg[17]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # f.write(data_movement_instruction(reg, reg, 0, 0, 18, 0, 0, 0, 25, 0, mv))  # reg[18] = reg[25]
    # f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 25, 0, 0, 0, 1, 0, si)) # reg[25] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(reg, 0, 0, 0, 5, 0, 0, 0, 1, 0, si)) # reg[5] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # REMOVE THIS LATER. Currently used to set hinP as a workaround

    f.write(data_movement_instruction(reg, SPM, 0, 0, 1, 0, 0, 0, 0, 6, mv))  # reg[1] = SPM[gr[6]]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # this is the Eq vector being grabbed from the SPM

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     # SPM latency cycle 2
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     # Data ready

    # HERE WE should grab from SPM instead from the previous node value based on flags. safer to do this rather than pass the values
    # between the registers
    # reg > reg is fine passing when working on the same node
    # this stops when the node is done executing and we go to a new node (this happens when diff Masks scoreDiff = 0)
    # when scoreDiff = 0, we want to 
    # probably dont do this here actually. 



    f.write(data_movement_instruction(reg, reg, 0, 0, 2, 0, 0, 0, 28, 0, mv))   # reg[2] = reg[28]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # reg[28] has result VN

    f.write(data_movement_instruction(reg, reg, 0, 0, 3, 0, 0, 0, 29, 0, mv))   # reg[3] = reg[29]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # reg[29] has result VP

    f.write(data_movement_instruction(reg, reg, 0, 0, 11, 0, 0, 0, 30, 0, mv))  # reg[11] = reg[30]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)) # reg[30] has result scoreEnd

    # ============================================================
    # Step 6: Save WS (Merge Output) to SPM[10,11,12]
    # ============================================================
    # Store VN to SPM[10]
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 10, 0, si))  # gr[14] = 10 (SPM addr)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 14, 0, 0, 28, 0, mv))  # SPM[10] = reg[28] (VN)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # SPM latency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Store VP to SPM[11]
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 14, addi))  # gr[14] = 11
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 14, 0, 0, 29, 0, mv))  # SPM[11] = reg[29] (VP)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Store scoreEnd to SPM[12]
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 14, addi))  # gr[14] = 12
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 14, 0, 0, 30, 0, mv))  # SPM[12] = reg[30] (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # Step 7: Set forceEq Based on prevSliceExists
    # ============================================================
    # prevSliceExists = (gr[7] >> 1) & 1
    # If prevSliceExists: forceEq = AllOnes
    # If !prevSliceExists: forceEq = AllOnes XOR 1 = 0xFFFFFFFFFFFFFFFE

    # Extract prevSliceExists: gr[14] = (gr[7] >> 1) & 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 7, shifti_r))  # gr[14] = gr[7] >> 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 14, ANDI))  # gr[14] = gr[14] & 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # If prevSliceExists (gr[14] != 0): jump to FORCE_EQ_ALLONES
    # FALSE path has: si, set_PC, nop, beq = 4 instructions, so offset = 5 to reach TRUE path
    FORCE_EQ_ALLONES_OFFSET = 5  # Skip FALSE path (4 instrs)
    f.write(data_movement_instruction(gr, gr, 0, 0, FORCE_EQ_ALLONES_OFFSET, 0, 0, 0, 0, 14, bne))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- prevSliceExists == FALSE: forceEq = AllOnes XOR 1 = 0xFFFFFFFFFFFFFFFE ----
    # Load reg[20] = 1 for the XOR operation
    f.write(data_movement_instruction(reg, 0, 0, 0, 20, 0, 0, 0, 1, 0, si))  # reg[20] = 1 (for XOR)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Execute compute PC 85 to do: reg[10] = reg[31] XOR reg[20]
    STEP7_XOR_COMPUTE_PC = 85
    f.write(data_movement_instruction(0, 0, 0, 0, STEP7_XOR_COMPUTE_PC, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(0, 0, 0, 0, STEP7_XOR_COMPUTE_PC, 0, 0, 0, 0, 0, set_PC))

    # Wait for compute to finish (1 cycle for XOR)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Jump to AFTER_FORCE_EQ
    AFTER_FORCE_EQ_OFFSET = 2  # Skip TRUE path
    f.write(data_movement_instruction(gr, gr, 0, 0, AFTER_FORCE_EQ_OFFSET, 0, 0, 0, 0, 0, beq))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- prevSliceExists == TRUE: forceEq = AllOnes ----
    f.write(data_movement_instruction(reg, reg, 0, 0, 10, 0, 0, 0, 31, 0, mv))  # reg[10] = reg[31] (AllOnes)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- AFTER_FORCE_EQ ----
    # forceEq is now in reg[10]

    # ============================================================
    # Step 8: Initialize BP loop counter
    # ============================================================
    f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0, 0, si))  # gr[3] = 0 (BP loop counter)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Prepare reg[20] = 1 for forceMask VN |= 1 (used if !prevSliceExists)
    f.write(data_movement_instruction(reg, 0, 0, 0, 20, 0, 0, 0, 1, 0, si))  # reg[20] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # Step 9: BP_LOOP_START - Receive and process basepair
    # ============================================================
    # Controller restarts PE here (PE_BP_START_PC should match this PC)
    # Current PC estimate: ~after all the previous code

    # 9.1: Receive basepair from controller into gr[6]
    f.write(data_movement_instruction(gr, in_port, 0, 0, 6, 0, 0, 0, 0, 0, mv))  # gr[6] = in (basepair 0-3)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # 9.2: Load Eq vector from SPM[gr[6]] into reg[1]
    f.write(data_movement_instruction(reg, SPM, 0, 0, 1, 6, 0, 0, 0, 0, mv))  # reg[1] = SPM[gr[6]]
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # SPM latency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # 9.3: Apply forceEq via compute PC 86: reg[1] &= reg[10]
    f.write(data_movement_instruction(0, 0, 0, 0, 86, 0, 0, 0, 0, 0, set_PC))  # set_PC 86 for forceEq AND
    f.write(data_movement_instruction(0, 0, 0, 0, 86, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # wait for compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # 9.4: Call getNextSlice via compute PC 64
    f.write(data_movement_instruction(0, 0, 0, 0, 64, 0, 0, 0, 0, 0, set_PC))  # set_PC 64 for getNextSlice
    f.write(data_movement_instruction(0, 0, 0, 0, 64, 0, 0, 0, 0, 0, set_PC))

    # Wait for getNextSlice to complete (~16 cycles)
    for i in range(8):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ============================================================
    # Step 10: Handle forceMask (if !prevSliceExists)
    # ============================================================
    # Check prevSliceExists = (gr[7] >> 1) & 1
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 7, shifti_r))  # gr[14] = gr[7] >> 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 14, ANDI))  # gr[14] = gr[14] & 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # If prevSliceExists (gr[14] != 0), skip forceMask
    SKIP_FORCEMASK_OFFSET = 3  # Skip 2 compute set_PC + 1 wait
    f.write(data_movement_instruction(gr, gr, 0, 0, SKIP_FORCEMASK_OFFSET, 0, 0, 0, 0, 14, bne))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # !prevSliceExists: Apply forceMask via compute PC 87-88
    # PC 87: reg[3] &= reg[10] (VP &= mask), PC 88: reg[2] |= reg[20] (VN |= 1)
    f.write(data_movement_instruction(0, 0, 0, 0, 87, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(0, 0, 0, 0, 87, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # wait for compute (2 cycles)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- AFTER_FORCEMASK ----

    # ============================================================
    # Step 11: ExtraSlice Merge Check
    # ============================================================
    # Load extraSlice scoreEnd from SPM[17] into reg[20]
    f.write(data_movement_instruction(gr, 0, 0, 0, 15, 0, 0, 0, 17, 0, si))  # gr[15] = 17
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(reg, SPM, 0, 0, 20, 15, 0, 0, 0, 0, mv))  # reg[20] = SPM[17] (extraSlice scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # SPM latency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Check if scoreEnd == -1 (compare with 0xFFFF sign-extended to -1)
    f.write(data_movement_instruction(reg, 0, 0, 0, 21, 0, 0, 0, 0xFFFF, 0, si))  # reg[21] = -1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # If reg[20] == reg[21] (scoreEnd == -1), skip merge path
    SKIP_MERGE_OFFSET = 23  # Skip merge operations (load slices, merge, score compute)
    f.write(data_movement_instruction(reg, reg, 0, 0, SKIP_MERGE_OFFSET, 0, 0, 0, 20, 21, beq))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- MERGE PATH: scoreEnd != -1 ----
    # Move current WS to left slice: reg[2,3,11] → reg[12,13,15]
    f.write(data_movement_instruction(reg, reg, 0, 0, 12, 0, 0, 0, 2, 0, mv))  # reg[12] = reg[2] (VN)
    f.write(data_movement_instruction(reg, reg, 0, 0, 13, 0, 0, 0, 3, 0, mv))  # reg[13] = reg[3] (VP)
    f.write(data_movement_instruction(reg, reg, 0, 0, 15, 0, 0, 0, 11, 0, mv))  # reg[15] = reg[11] (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Load extraSlice from SPM[15-17] to right slice: reg[16,17,19]
    f.write(data_movement_instruction(gr, 0, 0, 0, 15, 0, 0, 0, 15, 0, si))  # gr[15] = 15
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(reg, SPM, 0, 1, 17, 15, 0, 0, 0, 0, mv))  # reg[17] = SPM[15] (VP)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(reg, SPM, 0, 1, 16, 15, 0, 0, 0, 0, mv))  # reg[16] = SPM[16] (VN)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(reg, SPM, 0, 0, 19, 15, 0, 0, 0, 0, mv))  # reg[19] = SPM[17] (scoreEnd)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Call mergeTwoSlices (compute PC 0)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))  # set_PC 0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))
    # Wait for merge (~12 cycles)
    for i in range(6):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Compute hinP/hinN from score comparison (compute PC 89)
    f.write(data_movement_instruction(0, 0, 0, 0, 89, 0, 0, 0, 0, 0, set_PC))  # set_PC 89
    f.write(data_movement_instruction(0, 0, 0, 0, 89, 0, 0, 0, 0, 0, set_PC))
    for i in range(3):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # Jump to AFTER_STEP11
    AFTER_STEP11_OFFSET = 2  # Skip NO_MERGE path
    f.write(data_movement_instruction(gr, gr, 0, 0, AFTER_STEP11_OFFSET, 0, 0, 0, 0, 0, beq))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- NO_MERGE PATH: scoreEnd == -1 ----
    # hinP = Ph >> 31, hinN = Mh >> 31 (compute PC 94)
    f.write(data_movement_instruction(0, 0, 0, 0, 94, 0, 0, 0, 0, 0, set_PC))  # set_PC 94
    f.write(data_movement_instruction(0, 0, 0, 0, 94, 0, 0, 0, 0, 0, set_PC))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # ---- AFTER_STEP11 ----
    # hinP in reg[5], hinN in reg[4]

    # 9.5: Save Ph (reg[8]) to SPM[13], Mh (reg[9]) to SPM[14]
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 13, 0, si))  # gr[14] = 13
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 14, 0, 0, 8, 0, mv))  # SPM[13] = reg[8] (Ph)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # SPM latency
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(gr, gr, 0, 0, 14, 0, 0, 0, 1, 14, addi))  # gr[14] = 14
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 14, 0, 0, 9, 0, mv))  # SPM[14] = reg[9] (Mh)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # 9.6: Increment loop counter gr[3]++
    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 1, 3, addi))  # gr[3]++
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    # 9.7: Signal done to controller: gr[10] = 1, then halt
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))  # gr[10] = 1 (sync signal)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))  # halt - wait for controller
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))               
           

    f.close()



def pe_idle_instruction(pe_id):
    """
    Generate instructions for idle PEs (1, 2, 3).
    These PEs set GR10=1 (done signal) and loop infinitely.
    Only PE0 should be doing actual work.
    """
    f = InstructionWriter("instructions/gbv/pe_{}_instruction.txt".format(pe_id))

    # PC 0: Set gr[10] = 1 (signal done to controller)
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))  # gr[10] = 1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))  # nop (slot 2)

    # PC 1: Loop back to PC 1 infinitely (unconditional branch: beq 0 0 offset=0)
    # This keeps the PE spinning while signaling done via gr[10]=1
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, beq))  # beq 0 0, offset=0 (loop to self)
    f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 0, 0, beq))  # beq 0 0, offset=0 (loop to self)

    # Fill rest with nops (shouldn't be reached due to infinite loop above)
    for i in range(100):
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
        f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

    f.close()

def pe_1_instruction():
    pe_idle_instruction(1)

def pe_2_instruction():
    pe_idle_instruction(2)

def pe_3_instruction():
    pe_idle_instruction(3)

if not os.path.exists("instructions/gbv"):
    os.makedirs("instructions/gbv")
gbv_compute_v3()
gbv_main_instruction()
pe_instruction(0)
pe_1_instruction()
pe_2_instruction()
pe_3_instruction()
