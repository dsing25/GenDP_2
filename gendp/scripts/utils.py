import inspect
import os

def compute_instruction(op_0, op_1, op_2, in_addr_0, in_addr_1, in_addr_2, in_addr_3, in_addr_4, in_addr_5, out_addr):
    '''
    in_addr_0 can be immediate
    in_addr_4 can be immediate
    '''
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
    
    

def data_movement_instruction(dest, src, reg_immBar_0, reg_auto_increase_0, imm_0, reg_0,
                              reg_immBar_1, reg_auto_increase_1, imm_1, reg_1, opcode):
    '''
    0 dest
    1 src
    2 reg_immBar_0
    3 reg_auto_increase_0
    4 imm_0
    5 reg_0
    6 reg_immBar_1
    7 reg_auto_increase_1
    8 imm_1
    9 reg_1
   10 opcode
    '''
    instr = "0" * 18 \
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
            + "{:0>6b}".format(opcode)
    value = int(instr, 2)
    return hex(value) + "\n"

def write_magic(magic_number):
    '''
    Write instruction with first bit 1 as "magic" instruction. Payload of 32 bits at the end.
    '''
    instr = "1" + "0" * 31 + "{:0>32b}".format(magic_number)
    value = int(instr, 2)
    return hex(value) + "\n"

class InstructionWriter:
    '''
    Instruction writer class. Creates two files: one with raw instructions and another 
    human-readable file with the source instruction "assembly" alongside hex instruction
    '''
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = open(self.filepath, 'w')

        root, ext = os.path.splitext(self.filepath)
        self.hr_path = f"{root}_HR{ext}"
        self.hr_file = open(self.hr_path, 'w')

    def write(self, value):
        self.file.write(value)
        frame = inspect.currentframe().f_back
        line = inspect.getframeinfo(frame).code_context[0].strip()
        expr_text = line[line.find('(')+1:]  # crude extraction
        self.hr_file.write(f"{value[:-1].ljust(18)} {expr_text}\n")

    def close(self):
        self.file.close()



