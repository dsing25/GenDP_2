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

// PE control-PC mode (per pe_array instance, set at construction).
// SHARED: when only one VLIW slot is a control-flow op and takes its
//   branch, the other slot's PC is force-synced to the branch target.
//   This is the default and what GSSW/WFA/PHMM/Chain/BSW expect.
// DUAL:  the two slot PCs evolve fully independently — no cross-slot
//   sync. Required by POA, whose pe_X traces have an asymmetric
//   single-slot branch at the end of each PE that must NOT pull the
//   other slot's PC forward.
#define PC_MODE_SHARED 0
#define PC_MODE_DUAL   1
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
#define COMP_INSTR_BUFFER_GROUP_NUM 48
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
#define GLOBAL_REGISTER_ADDR_WIDTH 7
#define CTRL_OPCODE_WIDTH 5
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
// GSSW-lowering additions. CARRY (slot 3) was unused by any generator and is
// reclaimed for SLLI_64 to stay within the 5-bit COMP_OPCODE_WIDTH budget.
#define SLLI_64    3    // paired 64-bit unsigned left shift (reg[r:r+1])
#define ADDS_EPU8  27   // saturating unsigned 8-bit add (simd only)
#define SUBS_EPU8  28   // saturating unsigned 8-bit sub (simd only)
#define MAX_EPU8   29   // unsigned 8-bit max (simd only)
#define MAX_REDUCE 30   // horizontal max of 4 lanes -> scalar byte (simd only)
#define COMP_GT    31   // scalar gt / simd any-lane gt; writes 0/1 scalar

inline bool is_immediate_opcode(int opcode) {
    return (opcode == ADD_I || opcode == COPY_I || opcode == SLLI_64);
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
// mv2: unswizzled, virtual-addressed 2-bit extract (GSSW path).
#define CTRL_MV2 29
// gr[rd] = gr[rs2] * (immBar_1 ? gr[imm_1] : sext_imm_1). Slot-0 only.
#define CTRL_MUL 30

// DEST/SRCS
#define CTRL_REG 0
#define CTRL_GR 1
#define CTRL_SPM 2
#define CTRL_COMP_IB 3
#define CTRL_CTRL_IB 4
#define CTRL_S1C 4         // Controller scratchpad (repurposed ctrl_ib)
#define S1C_SIZE 8192
#define CTRL_IN_BUF 5
#define CTRL_OUT_BUF 6
#define CTRL_IN_PORT 7
#define CTRL_IN_INSTR 8   // legacy: instruction-chain input
#define CTRL_GR_LO 8      // lower 16-bit subregister of gr (shares code with IN_INSTR)
#define CTRL_OUT_PORT 9
#define CTRL_OUT_INSTR 10  // legacy: instruction-chain output
#define CTRL_GR_HI 10     // upper 16-bit subregister of gr (shares code with OUT_INSTR)
#define CTRL_S2 15
//FIFO [11, 12, 13, 14]

// Internal-only resolved pos code for "compute reg addressed via gr-field"
// (reg idx bits [6:5]=11, i.e. wire reg_idx in [96:127] with src/dest type = CTRL_GR).
// Never appears on the wire; produced only by the decoder's resolve_reg_field.
// Kept distinct from CTRL_REG (=0) so arithmetic/branch sites that pass src=0
// as a don't-care still fall through to gr reads, while an explicit gr-field
// encoding routes to the compute regfile.
#define CTRL_RESOLVED_REG 16

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
// Phase 1 and phase 2 compute tiles alias the same addresses
// (phases don't overlap, so no conflict)
#define GWFA_BUF0_BASE  0
#define GWFA_BUF1_BASE  1280
#define GWFA_P2_BASE    0       // aliases BUF0 during phase 2
#define GWFA_P2B_BASE   1280    // aliases BUF1 during phase 2
#define GWFA_FIN0_BASE  2560    // fin0 hash dedup tile A
#define GWFA_FIN0B_BASE 4288    // fin0 hash dedup tile B (each 1728w)

// FIN0_TILE layout (static offsets within each FIN0 region per PE)
// N_MAX_DIAGS=64, N_MAX_ARCS=100. Shared A/B output.
// Total: 8+128+128+300+400+528+200 = 1692w (36 spare of 1728)
#define FIN0_META       0       // 8w: n_diags, n_arcs, n_A, n_B, n_HA
#define FIN0_DIAGS      8       // 128w: (vd, k) × 64
#define FIN0_ARCMETA    136     // 128w: (lo, hi) × 64
#define FIN0_ARCS       264     // 300w: (packed_vw, ow, ts_off) × 100
#define FIN0_HA         564     // 400w: HA buckets (4 words) × 100
#define FIN0_OUT        964     // 528w: combined A+B output
#define FIN0_OUT_SIZE   528     // A forward from 0, B backward from end
#define FIN0_OUT_HA     1492    // 200w: HA dirty × 100
#define FIN0_N_MAX_ARCS  100
#define FIN0_N_MAX_DIAGS 64
#define FIN0_ARC_WORDS   3      // words per arc: packed_vw, ow, ts_off
// FIN0_OUT: A from start, B from end. Max = 2*100+64 = 264 entries.

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
//   [320..2879] BIN_SPM0   ping scatter bins (SORT_RADIX_BINS * SORT_BIN_REGION_SIZE * 2)
//   [2880..5439] BIN_SPM1  pong scatter bins
//   [5440..5489] SORT_META  metadata (bin_counts[16], tile_bin_counts[16], tile_n, shift, bin_cursors[16])
//   Total: 5490 < GWFA_Q_START/4 = 6016 ✓
#define SORT_TILE_BUF0  0
#define SORT_TILE_BUF1  (SORT_TILE * 2)
#define SORT_BIN_SPM0   (SORT_TILE * 4)
#define SORT_BIN_SPM1   (SORT_TILE * 4 + SORT_RADIX_BINS * SORT_BIN_REGION_SIZE * 2)
#define SORT_META       (SORT_TILE * 4 + 2 * SORT_RADIX_BINS * SORT_BIN_REGION_SIZE * 2)
// SORT_META sub-offsets: [0..15]=bin_counts (accumulated), [16..31]=tile_bin_counts (per-tile),
//                        [32]=tile_n, [33]=shift, [34..49]=bin_cursors (per-tile, PE 21)

// GWFA dedup phase SPM layout (per-PE, reuses stale sort/merge buffers)
// Tiled dedup with ping-pong input AND output buffers.
// DEDUP_TILE = elements processed per PE call (counted across diag+intv reads).
// Each input buffer holds DEDUP_TILE entries. PE reads at most DEDUP_TILE
// elements per call, so it can exhaust at most one buffer per stream per call.
//   [0..19]       DEDUP_META      metadata (20 words)
//   [20..179]     DEDUP_DIAG_BUF0 diag input 0 (TILE×2 words = 160)
//   [180..339]    DEDUP_DIAG_BUF1 diag input 1
//   [340..499]    DEDUP_INTV_BUF0 intv input 0
//   [500..659]    DEDUP_INTV_BUF1 intv input 1
//   [660..819]    DEDUP_DIAG_OUT0 diag output ping (TILE×2 words = 160)
//   [820..979]    DEDUP_DIAG_OUT1 diag output pong
//   [980..1139]   DEDUP_INTV_OUT0 intv output ping
//   [1140..1299]  DEDUP_INTV_OUT1 intv output pong
//   Total: 1300 words < 6016 ✓
#define DEDUP_TILE        SORT_TILE              // 80
#define DEDUP_META_SIZE   20
#define DEDUP_META        0
#define DEDUP_DIAG_BUF0   (DEDUP_META + DEDUP_META_SIZE)       // 20
#define DEDUP_DIAG_BUF1   (DEDUP_DIAG_BUF0 + DEDUP_TILE * 2)  // 180
#define DEDUP_INTV_BUF0   (DEDUP_DIAG_BUF1 + DEDUP_TILE * 2)  // 340
#define DEDUP_INTV_BUF1   (DEDUP_INTV_BUF0 + DEDUP_TILE * 2)  // 500
#define DEDUP_DIAG_OUT0   (DEDUP_INTV_BUF1 + DEDUP_TILE * 2)  // 660
#define DEDUP_DIAG_OUT1   (DEDUP_DIAG_OUT0 + DEDUP_TILE * 2)  // 820
#define DEDUP_INTV_OUT0   (DEDUP_DIAG_OUT1 + DEDUP_TILE * 2)  // 980
#define DEDUP_INTV_OUT1   (DEDUP_INTV_OUT0 + DEDUP_TILE * 2)  // 1140
// DEDUP_META sub-offsets (PE writes [0..9,14..19]; controller writes [10..13]):
//   [0]=pending_vd, [1]=pending_k, [2]=n_diag_out, [3]=n_intv_out,
//   [4]=diag_cursor, [5]=intv_cursor, [6]=diag_which, [7]=intv_which,
//   [8]=diag_exhausted, [9]=intv_exhausted,
//   [10]=diag_BUF0_tile_n, [11]=diag_BUF1_tile_n,
//   [12]=intv_BUF0_tile_n, [13]=intv_BUF1_tile_n,
//   [14]=cur_intv_lo (0xFFFFFFFF=none), [15]=cur_intv_hi,
//   [16]=state (0=X, 1=B, 2=C), [17]=pe_done,
//   [18]=new_vd, [19]=new_k

// GWFA merge phase SPM layout (per-PE, reuses stale sort/dedup region)
// Merge runs BEFORE dedup, so this area is reused by dedup afterward.
//   [0..15]       MERGE_META  metadata (16 words)
//   [16..175]     MERGE_OUT0  ping output (MERGE_TILE*2 words)
//   [176..335]    MERGE_OUT1  pong output
//   [336..495]    MERGE_A_BUF0 A ping tile (MERGE_TILE*2 words)
//   [496..655]    MERGE_A_BUF1 A pong tile
//   [656..815]    MERGE_B_BUF0 B ping tile
//   [816..975]    MERGE_B_BUF1 B pong tile
#define MERGE_TILE         SORT_TILE          // 80 entries per tile/output block
#define MERGE_STEP         (MERGE_TILE / 2)   // 40 inputs consumed per PE call
#define MERGE_META         0                  // 16 words
#define MERGE_OUT0         16                 // 160 words
#define MERGE_OUT1         (MERGE_OUT0 + MERGE_TILE * 2)  // 176
#define MERGE_A_BUF0       (MERGE_OUT1 + MERGE_TILE * 2)  // 336
#define MERGE_A_BUF1       (MERGE_A_BUF0 + MERGE_TILE * 2) // 496
#define MERGE_B_BUF0       (MERGE_A_BUF1 + MERGE_TILE * 2) // 656
#define MERGE_B_BUF1       (MERGE_B_BUF0 + MERGE_TILE * 2) // 816
// MERGE_META sub-offsets:
//   [0]=a_cursor, [1]=b_cursor, [2]=a_tile_n, [3]=b_tile_n,
//   [4]=out_n, [5]=a_global_done, [6]=b_global_done

// Apply address swizzling for mvi instruction
// Keeps bit[0] as line offset, moves bits[2:1] to top
inline int apply_address_swizzle(int addr) {
    // Bounds: valid addresses are [0, SPM_ADDR_NUM - 1]. SPM_ADDR_NUM
    // itself is one past the end and must be rejected — otherwise the
    // mask below turns it into 0 and silently corrupts SPM address 0.
    // (Codex R9 P3.)
    if (addr < 0 || addr >= SPM_ADDR_NUM) {
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
