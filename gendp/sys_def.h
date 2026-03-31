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
#define LINE_SIZE 2
#define SPM_ADDR_NUM 32768
#define SPM_BANK_GROUP_SIZE 8192  // Size of each bank-group (1 per PE)
#define SPM_BANK_SIZE 4096        // Actual bank size (2 banks per bank-group)
#define SPM_NUM_BANKS 8           // 4 bank-groups × 2 banks each
#define S2_BUFFER_BYTES (1024 * 1024) // 1 MB, int-addressable (4 bytes per int)
#define S2_BUFFER_INTS (S2_BUFFER_BYTES / 4)
#define S2_NUM_BANKS 4
#define S2_READ_LATENCY 6
#define S2_WRITE_LATENCY 3
#define LSQ_MAX_ENTRIES_PER_BANK 8
#define CTRL_PEID 656
#define MAIN_ADDR_REGISTER_NUM 32
#define CTRL_INSTR_BUFFER_NUM 8192
#define COMP_INSTR_BUFFER_GROUP_NUM 33
#define CTRL_INSTR_BUFFER_GROUP_SIZE 2
#define COMP_INSTR_BUFFER_GROUP_SIZE 2

#define PE_INSTRUCTION_WIDTH 64
#define PE_OPCODE_WIDTH 5

#define COMP_ADDR_WIDTH 7
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
#define IMMEDIATE_WIDTH 16
#define GLOBAL_REGISTER_ADDR_WIDTH 5
#define CTRL_OPCODE_WIDTH 6
#define INSTRUCTION_WIDTH ((MEMORY_COMPONENTS_ADDR_WIDTH + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + 2) * 2 + CTRL_OPCODE_WIDTH)

#define NUM_THREADS 5

#define COMP_NOP_INSTRUCTION  0x7BDE000000000000UL
#define COMP_HALT_INSTRUCTION 0x83DE000000000000UL
#define CTRL_NOP_INSTRUCTION 0xe
#define MIN_INT -9999

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
#define CTRL_MVDQ 22
#define CTRL_MVDQI 23
#define CTRL_BARRIER 24
#define CTRL_MVI2 25
#define CTRL_CALL 26
#define CTRL_RET 27
#define CTRL_RETNE 28

// DEST/SRCS
#define CTRL_REG 0
#define CTRL_GR 1
#define CTRL_SPM 2
#define CTRL_COMP_IB 3
#define CTRL_CTRL_IB 4
#define CTRL_S1C 4         // Controller scratchpad (repurposed ctrl_ib)
#define S1C_SIZE 4096
#define CTRL_IN_BUF 5
#define CTRL_OUT_BUF 6
#define CTRL_IN_PORT 7
#define CTRL_GR_LO 8   // lower 16-bit subregister of gr
#define CTRL_OUT_PORT 9
#define CTRL_GR_HI 10  // upper 16-bit subregister of gr
#define CTRL_S2 15
//FIFO [11, 12, 13, 14]

// Address swizzling parameters for mvi instruction
#define N_SWIZZLE_BITS 2
#define ADDR_LEN 15

// DNA sequence start addresses for magic instruction initialization. No swizzle start
#define PATTERN_START 512
#define TEXT_START 1160

// GWFA interleaved SPM regions (pre-swizzle addresses)
#define GWFA_Q_START  24064  // 94KB
#define GWFA_GS_START 25088  // 98KB

// GWFA ping-pong buffer bases (per-PE SPM offsets)
#define GWFA_BUF0_BASE 0
#define GWFA_BUF1_BASE 1280
#define GWFA_P2_BASE   2560
#define GWFA_P2B_BASE  3840

// GWFA graph topology in S2 (controller access)
#define GRAPH_START 0

// GWFA dedup/sort phase SPM layout (per-PE, reuses stale extend buffers at base 0)
// Sequences start at per-PE local address GWFA_Q_START/4 = 6016; must stay below.
#define SORT_TILE            80   // diags per PE per tile (multiple of 8 for mvdq)
#define SORT_BIN_REGION_SIZE 80   // max diags per bin per tile (>= SORT_TILE)
#define SORT_RADIX_BINS      16   // 2^4 bins per radix pass
#define SORT_RADIX_PASSES    8    // 8 passes * 4 bits = 32-bit key
// SPM word offsets (per PE, relative to GWFA_DEDUP_BASE = 0):
//   [0..159]    TILE_BUF0  ping tile (SORT_TILE*2 words)
//   [160..319]  TILE_BUF1  pong tile
//   [320..2879] BIN_REG0   ping scatter bins (SORT_RADIX_BINS * SORT_BIN_REGION_SIZE * 2)
//   [2880..5439] BIN_REG1  pong scatter bins
//   [5440..5473] SORT_META  metadata (bin_counts[16], tile_bin_counts[16], tile_n, shift)
//   Total: 5474 < GWFA_Q_START/4 = 6016 ✓
#define SORT_TILE_BUF0  0
#define SORT_TILE_BUF1  (SORT_TILE * 2)
#define SORT_BIN_REG0   (SORT_TILE * 4)
#define SORT_BIN_REG1   (SORT_TILE * 4 + SORT_RADIX_BINS * SORT_BIN_REGION_SIZE * 2)
#define SORT_META       (SORT_TILE * 4 + 2 * SORT_RADIX_BINS * SORT_BIN_REGION_SIZE * 2)
// SORT_META sub-offsets: [0..15]=bin_counts (accumulated), [16..31]=tile_bin_counts (per-tile),
//                        [32]=tile_n, [33]=shift

// GWFA dedup phase SPM layout (per-PE, reuses stale sort buffers; sort must finish first)
// DEDUP_TILE reuses SORT_TILE (= 80). Sequential use of same base address space.
//   [0..159]     DEDUP_BUF0  ping diag tile (DEDUP_TILE*2 words)
//   [160..319]   DEDUP_BUF1  pong diag tile
//   [320..481]   DEDUP_OUT0  ping output tile ((DEDUP_TILE+1)*2 words, +1 for pending flush)
//   [482..643]   DEDUP_OUT1  pong output tile
//   [644..659]   DEDUP_META  metadata (16 words)
//   [660..6015]  DEDUP_INTV  preloaded intv for this PE
#define DEDUP_TILE   SORT_TILE           // 80 diags per PE per tile
#define DEDUP_BUF0   0
#define DEDUP_BUF1   (DEDUP_TILE * 2)              // 160
#define DEDUP_OUT0   (DEDUP_TILE * 4)              // 320
#define DEDUP_OUT1   (DEDUP_OUT0 + (DEDUP_TILE + 1) * 2)  // 482
#define DEDUP_META   (DEDUP_OUT1 + (DEDUP_TILE + 1) * 2)  // 644; 16 words
// DEDUP_META sub-offsets:
//   [0]=pending_vd (0xFFFFFFFF=none), [1]=pending_k, [2]=out_n,
//   [3]=ii (intv cursor), [4]=diag_tile_n, [5]=is_last_diag,
//   [6]=intv_n_pe (full intv count for this PE)
#define DEDUP_INTV   (DEDUP_META + 16)  // 660; full intv preload buffer

// Apply address swizzling for mvi instruction
// Keeps bit[0] as line offset, moves bits[2:1] to top
inline int apply_address_swizzle(int addr) {
    if (addr < 0 || addr > SPM_ADDR_NUM) {
        fprintf(stderr, "Error: address %d out of bound for swizzling (max %d)\n",
            addr, SPM_ADDR_NUM);
        exit(-1);
    }
    int addr_masked = addr & ((1u << ADDR_LEN) - 1);
    int line_off  = addr_masked & 1;
    int bank_bits = (addr_masked >> 1) & ((1u << N_SWIZZLE_BITS) - 1);
    int rest      = addr_masked >> (N_SWIZZLE_BITS + 1);
    return line_off | (rest << 1) | (bank_bits << (ADDR_LEN - N_SWIZZLE_BITS));
}

#endif
