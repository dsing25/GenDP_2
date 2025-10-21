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
AND = 18
'''
if pe, wait until recieves broadcasted ready from pe_array
if pe_array, wait until all pes have finished and sent ready
'''
wait = 19
'''
if a pe, sends a ready bit to the pe_array
if pe_array, broadcasts ready bit to all pes
'''
send_ready = 20
# these instruction tags here are for data movement
# use sys_def.h for compute tags
