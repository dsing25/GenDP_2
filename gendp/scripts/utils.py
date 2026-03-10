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
    instr = "0" * 4 \
            + "{:0>4b}".format(dest) \
            + "{:0>4b}".format(src) \
            + "{:0>1b}".format(reg_immBar_0) \
            + "{:0>1b}".format(reg_auto_increase_0) \
            + "{:0>16b}".format(imm_0 & 0xffff) \
            + "{:0>5b}".format(reg_0) \
            + "{:0>1b}".format(reg_immBar_1) \
            + "{:0>1b}".format(reg_auto_increase_1) \
            + "{:0>16b}".format(imm_1 & 0xffff) \
            + "{:0>5b}".format(reg_1) \
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
        self.file = open(self.filepath, 'w+')
        self.write_count = 0

        root, ext = os.path.splitext(self.filepath)
        self.hr_path = f"{root}_HR{ext}"
        self.hr_file = open(self.hr_path, 'w+')

    def write(self, value):
        self.file.write(value)
        frame = inspect.currentframe().f_back
        line = inspect.getframeinfo(frame).code_context[0].strip()
        expr_text = line[line.find('(')+1:]  # crude extraction
        self.hr_file.write(
            f"{value[2:-1].ljust(16)} {expr_text}\n")
        self.write_count += 1

    @property
    def pc(self):
        return self.write_count // 2

    def patch_imm0(self, write_index, new_imm0):
        '''Rewrite imm0 field of a previously written
        instruction (by write_index, 0-based).
        Each write() call increments the index.'''
        self.file.flush()
        self.file.seek(0)
        lines = self.file.readlines()
        val = int(lines[write_index].strip(), 16)
        # imm_0 is at bits [49:34]: reg_0(5)+flag_2(1)+flag_3(1)
        # +imm_1(16)+reg_1(5)+opcode(6) = 34 bits below
        mask = 0xFFFF << 34
        val = (val & ~mask) | ((new_imm0 & 0xFFFF) << 34)
        lines[write_index] = hex(val) + "\n"
        self.file.seek(0)
        self.file.writelines(lines)
        self.file.truncate()
        # Also patch HR file
        self.hr_file.flush()
        self.hr_file.seek(0)
        hr_lines = self.hr_file.readlines()
        old_hr = hr_lines[write_index]
        parts = old_hr.split(None, 1)
        rest = parts[1] if len(parts) > 1 else "\n"
        hr_lines[write_index] = (
            f"{val:x}".ljust(16) + " " + rest)
        self.hr_file.seek(0)
        self.hr_file.writelines(hr_lines)
        self.hr_file.truncate()

    def close(self):
        self.file.close()
        self.hr_file.close()


