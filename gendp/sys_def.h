#ifndef SYS_DEF
#define SYS_DEF

#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <limits>
#include <cstring>
#include <ostream>
#include <iostream>
#include <fstream>
#include <sstream> 
#include <string>
#include <vector>
#include <pthread.h>

// Parameter
#define MAIN_INSTRUCTION_1 1
#define MAIN_INSTRUCTION_2 2
#define PE_4_SETTING 4
#define PE_64_SETTING 64
#define SIMD_WIDTH8 4
#define PE_NUM 64
#define FIFO_GROUP_NUM 16
#define FIFO_GROUP_SIZE 4
#define FIFO_ID_WIDTH 5
#define FIFO_ADDR_NUM 3072

#define SPM_ACCESS_LATENCY 2
#define SPM_BANDWIDTH 2
#define SPM_ADDR_NUM 2048
#define SPM_BANK_SIZE 512
#define MAIN_ADDR_REGISTER_NUM 16
#define CTRL_INSTR_BUFFER_NUM 512
#define COMP_INSTR_BUFFER_GROUP_NUM 100
#define CTRL_INSTR_BUFFER_GROUP_SIZE 2
#define COMP_INSTR_BUFFER_GROUP_SIZE 2

#define PE_INSTRUCTION_WIDTH 50
#define PE_OPCODE_WIDTH 5

#define REGFILE_ADDR_WIDTH 5
#define REGFILE_ADDR_NUM 32
#define REGFILE_WRITE_PORTS 3
#define REGFILE_READ_PORTS 13

//This is CTRL regfile number of registers
#define ADDR_REGISTER_NUM 16
//I think it's actually like 4 read now.
#define CTRL_REGFILE_READ_PORTS 2
#define CTRL_REGFILE_WRITE_PORTS 2

#define CROSSBAR_IN_NUM 2
#define CROSSBAR_OUT_NUM 2

#define COMP_OPCODE_WIDTH 5
#define MEMORY_COMPONENTS_ADDR_WIDTH 4
#define IMMEDIATE_WIDTH 14
#define GLOBAL_REGISTER_ADDR_WIDTH 4
#define CTRL_OPCODE_WIDTH 6
#define INSTRUCTION_WIDTH ((MEMORY_COMPONENTS_ADDR_WIDTH + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + 2) * 2 + CTRL_OPCODE_WIDTH)

#define NUM_THREADS 5

#define COMP_NOP_INSTRUCTION 0x1ef7800000000
#define CTRL_NOP_INSTRUCTION 0xe
#define MIN_INT -99

// Opcode
#define ADDITION 0
#define SUBTRACTION 1
#define MULTIPLICATION 2
#define CARRY 3
#define BORROW 4
#define MAXIMUM 5
#define MINIMUM 6
#define LEFT_SHIFT 7
#define RIGHT_SHIFT 8
#define COPY 9
#define MATCH_SCORE 10
#define LOG2_LUT 11
#define LOG_SUM_LUT 12
#define COMP_LARGER 13
#define COMP_EQUAL 14
#define INVALID 15
#define HALT 16
#define BWISE_OR 17
#define BWISE_AND 18
#define BWISE_NOT 19
#define BWISE_XOR 20
#define LSHIFT_1  21
#define RSHIFT_WORD 22  // Right shift by 31 bits - can be modified based on word size
#define ADD_I 23 // Dummy TODO implement
#define COPY_I 24 // Dummy TODO implement
#define POPCOUNT 25 // partial dummy TODO
#define CMP_2INP 26 // dummy TODO

inline bool is_immediate_opcode(int opcode) {
    return (opcode == ADD_I || opcode == COPY_I);
}

inline int get_base_opcode(int opcode) {
    if (opcode == ADD_I) return ADDITION;
    if (opcode == COPY_I) return COPY;
    return opcode;
}

// CTRL Opcode
#define CTRL_ADD 0
#define CTRL_SUB 1
#define CTRL_ADDI 2
#define CTRL_SET_8 3
#define CTRL_SI 4
#define CTRL_MV 5
#define CTRL_ADD_8 6
#define CTRL_ADDI_8 7
#define CTRL_BNE 8
#define CTRL_BEQ 9
#define CTRL_BGE 10
#define CTRL_BLT 11
#define CTRL_JUMP 12
#define CTRL_SET_PC 13
#define CTRL_NONE 14
#define CTRL_HALT 15
#define CTRL_SHIFTI_R 16
#define CTRL_SHIFTI_L 17
#define CTRL_ANDI 18
//move double (so does two words)
#define CTRL_MVD 19
#define CTRL_SUBI 20
#define CTRL_MVI 21

// DEST/SRCS
#define CTRL_REG 0
#define CTRL_GR 1
#define CTRL_SPM 2
#define CTRL_COMP_IB 3
#define CTRL_CTRL_IB 4
#define CTRL_IN_BUF 5
#define CTRL_OUT_BUF 6
#define CTRL_IN_PORT 7
#define CTRL_IN_INSTR 8
#define CTRL_OUT_PORT 9
#define CTRL_OUT_INSTR 10
//FIFO [11, 12, 13, 14]

// Address swizzling parameters for mvi instruction
#define N_SWIZZLE_BITS 2
#define ADDR_LEN 11

// DNA sequence start addresses for magic instruction initialization
#define PATTERN_START 226
#define TEXT_START 369

#endif
