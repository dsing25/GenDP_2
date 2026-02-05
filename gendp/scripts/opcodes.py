#NOTE if you update anything in this file, you must also update in the sys_def.h
#MEMORY DESTS
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
fifo = [11, 12, 13, 14]

#DATA MOVEMENT OPCODES
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
shifti_r = 16
shifti_l = 17
ANDI = 18
mvd = 19
subi = 20
mvi = 21
# these instruction tags here are for data movement
# use sys_def.h for compute tags

#COMPUTE OPCODES
ADD = 0
SUBTRACTION = 1
MULTIPLICATION = 2
CARRY = 3
BORROW = 4
MAXIMUM = 5
MINIMUM = 6
LEFT_SHIFT = 7
RIGHT_SHIFT = 8
COPY = 9
MATCH_SCORE = 10
LOG2_LUT = 11
LOG_SUM_LUT = 12
COMP_LARGER = 13
COMP_EQUAL = 14
INVALID = 15
HALT = 16
BWISE_OR = 17
BWISE_AND = 18
BWISE_NOT = 19
BWISE_XOR = 20
LSHIFT_1 =  21
RSHIFT_WORD = 22
ADD_I = 23 # Note to Fix -1 not working for ADDI instructions or any negative number
COPY_I = 24
POPCOUNT = 25 
