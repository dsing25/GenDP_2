#NOTE if you update anything in this file, you must also update in the sys_def.h
#MEMORY DESTS
reg = 0
gr = 1
SPM = 2
comp_ib = 3
ctrl_ib = 4
s1c = 4            # Controller scratchpad (repurposed ctrl_ib)
in_buf = 5
out_buf = 6
in_port = 7
gr_lo = 8   # lower 16-bit subregister of gr
out_port = 9
gr_hi = 10  # upper 16-bit subregister of gr
S2 = 15
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
mvdq = 22
mvdqi = 23
barrier = 24
mvi2 = 25
call = 26
ret = 27
retne = 28
# mv2: unswizzled, virtual-addressed 2-bit extract (GSSW). mvi2 stays
# as the swizzled/interleaved 2-bit extract used by WFA/GWFA.
mv2 = 29
mul = 30        # gr[rd] = gr[rs2] * (immBar_1 ? gr[imm_1] : sext_imm_1). Slot-0 only.
# these instruction tags here are for data movement
# use sys_def.h for compute tags

#COMPUTE OPCODES
ADD = 0
SUBTRACTION = 1
MULTIPLICATION = 2
# slot 3 was CARRY (unused by any generator); reclaimed for GSSW paired shift.
SLLI_64 = 3        # paired 64-bit unsigned left shift on reg[r:r+1]
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
ADD_I = 23
COPY_I = 24
POPCOUNT = 25
CMP_2INP = 26
ADDS_EPU8  = 27   # saturating unsigned 8-bit add  (simd only)
SUBS_EPU8  = 28   # saturating unsigned 8-bit sub  (simd only)
MAX_EPU8   = 29   # unsigned 8-bit max             (simd only)
MAX_REDUCE = 30   # horizontal max of 4 lanes -> scalar byte (simd only)
COMP_GT    = 31   # scalar gt / simd any-lane gt; writes 0/1
