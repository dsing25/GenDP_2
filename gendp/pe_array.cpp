#include "pe_array.h"
#include <cassert>
#include "sys_def.h"
#include "data_buffer.h"
#include "simulator.h"
extern "C" {
#include "kernel/Gwfa/gwfa.h"
}
#include <iomanip>
#include <cstdlib>
#include <cstring>

#define NUM_FRACTION_BITS 16
#define MAX_RANGE NUM_FRACTION_BITS
#define NUM_INTEGER_BITS 5

#ifndef GWFA_DBG_DEFAULT
#define GWFA_DBG_DEFAULT 0
#endif
// Runtime override: env GWFA_DBG=1 enables debug tracing
#ifndef GWFA_DBG_RUNTIME
static int gwfa_dbg_level() {
    const char *e = getenv("GWFA_DBG");
    if (e) return atoi(e);
    return GWFA_DBG_DEFAULT;
}
#define GWFA_DBG_RUNTIME gwfa_dbg_level()
#endif

PerfCounter bankConflictStalls = 0;
PerfCounter totalSpmRequests = 0;
PerfCounter lsqFullStalls = 0;
PerfCounter peHalted = 0;
PerfCounter forwardableBankConflict = 0;
PerfCounter controllerSpinCycles = 0;
PerfCounter fin0DupDiags = 0;

pe_array::pe_array(int input_size, int output_size) {

    int i;
    input_buffer_size = input_size;
    output_buffer_size = output_size;

    input_buffer = (int*)calloc(input_buffer_size, sizeof(int));
    output_buffer = (int*)calloc(output_buffer_size, sizeof(int));
    s2 = new S2(S2_BUFFER_INTS);
    lsq = new CtrlLSQ();

    main_addressing_register[0] = 0;
    main_PC = 0;
    memset(va_regfile, 0, sizeof(va_regfile));
    memset(s1c, 0, sizeof(s1c));
    mm = nullptr;
    //+1 allows addressing full range. 1 is dummy data. Not legal in real hardware
    SPM_unit = new SPM(SPM_ADDR_NUM+1, &active_event_producers);
    for (i = 0; i < PE_NUM; i++)
        pe_unit[i] = new pe(i, SPM_unit);
    pe_unit[3]->fifo_out[0] = &fifo_unit[0][0];
    pe_unit[3]->fifo_out[1] = &fifo_unit[0][1];
    load_data = 0;
    store_data = 0;
    from_fifo = 0;
}

pe_array::~pe_array() {
    int i;
    free(input_buffer);
    free(output_buffer);
    delete s2;
    delete lsq;
    for (i = 0; i < PE_NUM; i++)
        delete pe_unit[i];
    delete SPM_unit;
}

void pe_array::buffer_reset(int* buffer, int num) {
    int i;
    for (i = 0; i < num; i++)
        buffer[i] = 0;
}

void pe_array::reset_shared_spm() { SPM_unit->reset(); }

void pe_array::reset_controller_state() {
    s2->reset();
    lsq->reset();
    active_event_producers.clear();
    ras = 0;
    load_data = 0;
    store_data = 0;
    from_fifo = 0;
}

void pe_array::write_spm_magic(int addr, int value) {
    if (addr < 0 || addr >= SPM_ADDR_NUM) {
        fprintf(stderr, "write_spm_magic addr %d out of range.\n", addr);
        exit(-1);
    }
    SPM_unit->buffer[addr] = value;
}



void pe_array::write_s2(int addr, int value) {
    if (addr < 0 || addr >= s2->buffer_size) {
        fprintf(stderr, "write_s2 addr %d out of range.\n", addr);
        exit(-1);
    }
    s2->buffer[addr] = value;
}

void pe_array::input_buffer_write_from_ddr(int addr, int* data) {

    if (addr >= 0 && addr < input_buffer_size) {
        input_buffer[addr] = *data;
    } else {
        fprintf(stderr, "data buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::input_buffer_write_from_ddr_unsigned(int addr, unsigned int* data) {

    if (addr >= 0 && addr < input_buffer_size) {
        input_buffer[addr] = *data;
    } else {
        fprintf(stderr, "data buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::compute_instruction_buffer_write_from_ddr(int addr, unsigned long data[]) {

    if (addr >= 0 && addr < COMP_INSTR_BUFFER_GROUP_NUM) {
        compute_instruction_buffer[addr][0] = data[0];
        compute_instruction_buffer[addr][1] = data[1];
    } else {
        fprintf(stderr, "PE instruction buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::main_instruction_buffer_write_from_ddr(int addr, unsigned long data[]) {

    if (addr >= 0 && addr < CTRL_INSTR_BUFFER_NUM) {
        main_instruction_buffer[addr][0] = data[0];
        main_instruction_buffer[addr][1] = data[1];
    } else {
        fprintf(stderr, "main instruction buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::pe_instruction_buffer_write_from_ddr(int addr, unsigned long data[], int id) {

    pe_unit[id]->ctrl_instr_load_from_ddr(addr, data);

};

void pe_array::pe_comp_instruction_buffer_write_from_ddr(int n_instr, unsigned long* data, int id) {

    pe_unit[id]->comp_instr_load_from_ddr(n_instr, data);

};


LoadResult pe_array::load(int source_pos, int reg_immBar_flag, int rs1, int rs2, int simd) {

    LoadResult data{};
    int source_addr = 0;
    
    if (reg_immBar_flag) source_addr = main_addressing_register[rs1] + main_addressing_register[rs2];
    else source_addr = rs1 + main_addressing_register[rs2];


#ifdef DEBUG
    printf("src: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d src_addr: %d\n", source_pos, reg_immBar_flag, rs1, main_addressing_register[rs2], source_addr);
#endif

    if (source_pos == 1) {
        data.data[0] = main_addressing_register[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from main addr reg[%d] to ", data.data[0], source_addr);
    else
        printf("%d from main addr reg[%d] to ", data.data[0], source_addr);
#endif
    } else if (source_pos == CTRL_GR_LO) {
        data.data[0] = (int)(int16_t)(main_addressing_register[source_addr] & 0xFFFF);
#ifdef PROFILE
        printf("%d from gr_lo[%d] to ", data.data[0], source_addr);
#endif
    } else if (source_pos == CTRL_GR_HI) {
        data.data[0] = (int)(int16_t)((main_addressing_register[source_addr] >> 16) & 0xFFFF);
#ifdef PROFILE
        printf("%d from gr_hi[%d] to ", data.data[0], source_addr);
#endif
    } else if (source_pos == CTRL_SPM) {
        if (source_addr >= 0 && source_addr < SPM_unit->buffer_size) {
            data.data[0] = SPM_unit->buffer[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from SPM[%d] to ", data.data[0], source_addr);
    else
        printf("%d from SPM[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load SPM addr %d error.\n", source_addr);
            exit(-1);
        }
    } else if (source_pos == CTRL_S2) {
        if (source_addr >= 0 && source_addr < s2->buffer_size) {
            data.data[0] = s2->buffer[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from S2[%d] to ", data.data[0], source_addr);
    else
        printf("%d from S2[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load S2 addr %d error.\n", source_addr);
            exit(-1);
        }
    } else if (source_pos == CTRL_S1C) {
        if (source_addr >= 0 && source_addr < S1C_SIZE) {
            data.data[0] = s1c[source_addr];
#ifdef PROFILE
        printf("%d from S1c[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load S1c addr %d error.\n",
                source_addr);
            exit(-1);
        }
    } else if (source_pos == 3) {
        PE_instruction[0] = compute_instruction_buffer[source_addr][0];
        PE_instruction[1] = compute_instruction_buffer[source_addr][1];
#ifdef PROFILE
        printf("%lx %lx from main comp instr buffer[%d] to ", PE_instruction[0], PE_instruction[1], source_addr);
#endif
    } else if (source_pos == 5) {
        if (source_addr >= 0 && source_addr < input_buffer_size) {
            data.data[0] = input_buffer[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from input buffer[%d] to ", data.data[0], source_addr);
    else
        printf("%d from input buffer[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load input buffer addr %d error.\n", source_addr);
            exit(-1);
        }
    } else if (source_pos == 7) {
        data.data[0] = load_data;
#ifdef PROFILE
    if (simd)
        printf("%lx from last PE to ", data.data[0]);
    else
        printf("%d from last PE to ", data.data[0]);
#endif
    } else if (source_pos >= 11 && source_pos <=14) {
        data.data[0] = fifo_unit[0][source_pos - 11].pop();
        from_fifo = 1;
#ifdef PROFILE
    if (simd)
        printf("%lx from fifo[%d] to ", data.data[0], source_pos - 11);
    else {
        printf("%d from fifo[%d] to (size is %d)", data.data[0], source_pos - 11, fifo_unit[0][source_pos - 11].size());
        fifo_unit[0][source_pos - 11].show();
    }
#endif
    } else {
        fprintf(stderr, "source_pos error. source_pos = %d\n",source_pos);
        exit(-1);
    }
    return data;
}

void pe_array::store(int dest_pos, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd) {

    int dest_addr = 0;

    if (reg_immBar_flag) dest_addr = main_addressing_register[rs1] + main_addressing_register[rs2];
    else dest_addr = rs1 + main_addressing_register[rs2];

#ifdef DEBUG
    printf("dest: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d gr[reg_1]: %d dest_addr: %d\n", dest_pos, reg_immBar_flag, rs1, rs2, main_addressing_register[rs2], dest_addr);
#endif

    if (dest_pos == 1) {
        main_addressing_register[dest_addr] = data.data[0];
        if (dest_addr == 0) printf("%d\n", data.data[0]);
    } else if (dest_pos == CTRL_GR_LO) {
        int old = main_addressing_register[dest_addr];
        main_addressing_register[dest_addr] = (old & (int)0xFFFF0000) | (data.data[0] & 0xFFFF);
#ifdef PROFILE
        printf("gr_lo[%d].\n", dest_addr);
#endif
    } else if (dest_pos == CTRL_GR_HI) {
        int old = main_addressing_register[dest_addr];
        main_addressing_register[dest_addr] = (old & 0x0000FFFF) | ((data.data[0] & 0xFFFF) << 16);
#ifdef PROFILE
        printf("gr_hi[%d].\n", dest_addr);
#endif
#ifdef PROFILE
        printf("main addr register[%d].\n", dest_addr);
#endif
    } else if(dest_pos == CTRL_SPM) {
        if (dest_addr >= 0 && dest_addr < SPM_unit->buffer_size) {
            SPM_unit->buffer[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("SPM[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store SPM addr %d error.\n", dest_addr);
            exit(-1);
        }
    } else if(dest_pos == CTRL_S2) {
        if (dest_addr >= 0 && dest_addr < s2->buffer_size) {
            s2->buffer[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("S2[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store S2 addr %d error.\n", dest_addr);
            exit(-1);
        }
    } else if(dest_pos == CTRL_S1C) {
        if (dest_addr >= 0 && dest_addr < S1C_SIZE) {
            s1c[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("S1c[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store S1c addr %d error.\n",
                dest_addr);
            exit(-1);
        }
    } else if(dest_pos == 6) {
        if (dest_addr >= 0 && dest_addr < output_buffer_size) {
            output_buffer[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("output buffer[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store output buffer addr %d error.\n", dest_addr);
            exit(-1);
        }
    } else if (dest_pos == 9) {
        store_data = data.data[0];
#ifdef PROFILE
        printf("PE[0].\n");
#endif
    } else if (dest_pos >= 11 && dest_pos <= 14) {
        // fprintf(stderr, "fifo[0] ");
        fifo_unit[0][dest_pos - 11].push(data.data[0]);
#ifdef PROFILE
    printf("fifo[%d]. size is %d\n", dest_pos - 11, fifo_unit[0][dest_pos - 11].size());
    fifo_unit[0][dest_pos - 11].show();
#endif
    }
}

// Copy up to 8 words between two int arrays
inline void mvdq_copy(int *dst, const int *src, int n) {
    for (int i = 0; i < n && i < 8; i++) dst[i] = src[i];
}

// Read controller gr with subregister support based on src component
inline int pe_array_read_gr(int *gr, int src, int idx) {
    int val = gr[idx];
    if (src == CTRL_GR_LO) return (int)(int16_t)(val & 0xFFFF);
    if (src == CTRL_GR_HI) return (int)(int16_t)((val >> 16) & 0xFFFF);
    return val;
}

// Load one batch of fin0 diags into FIN_0_TILE.
// Two-loop design: round-robin common case + per-PE fallback.
// Multi-pass state: s1c[22]=cursor, s1c[23]=arc_data_ptr.
// s1c[0..3]=nd, s1c[4..7]=na, s1c[8..11]=pe_spm_base, s1c[12..15]=pai
// Sets gr[2]=1 if more passes needed, 0 if done.
void pe_array::fin0_load_batch(int fin0_base, int magic_mask) {
    // Magic-20 SPM-load-to-use chains are slot-safe under the
    // 2-cycle SPM latency rule: each chain has >=3 intervening ISA
    // ops between the load and its first consumer, so the consumer
    // lands in cycle N+2 regardless of whether the load is in slot 0
    // or slot 1 of its VLIW pair. Pass 2 ts_off load (line ~530),
    // pass 3 outer diag/arcmeta pairs (lines ~567/578), and pass 3
    // inner arc load (line ~597) all meet this 3-intervening-op
    // minimum. The two back-to-back SPM-load patterns in pass 3
    // (diag lo/hi and arcmeta lo/hi) carry a separate 1-port SPM
    // structural-hazard note when both lines lower into the same
    // VLIW cycle; this is adjacent to AC-7 and is dispositioned as
    // observed-correct under mode-1/mode-2 passes on HEAD, to be
    // revisited only if a lowering pass forces cycle-separation.
    // Full chain-by-chain enumeration (load line, consumer line,
    // separation, verdict) lives in the Plan 2b AC-11 audit note
    // in .humanize/rlcr/2026-04-20_20-46-30/ac11-audit-table.md.
    int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
    int *spm = SPM_unit->buffer;
    constexpr int ARC_META_BASE = 544;
    constexpr int DIAG_CAP_F = (16 << 20);
    constexpr int INTV_CAP_F = (1 << 21);
    constexpr int HA_CAP_F   = (4 << 20);
    constexpr int ha_off = DIAG_CAP_F * 8 + INTV_CAP_F * 6;
    // R3/R5 fix: no 'int total_fin0' or 'int cursor' C++ local mirrors.
    // s1c[20] is the authoritative limit, s1c[22] the authoritative
    // cursor. Compares and arithmetic below reference them directly;
    // the ISA generator lowers each as a gr-staged load + compare/op.
    // pe_rr is a pass-1-only scratch derived from s1c[22] at RR entry
    // and advanced in-scope after each successful F0B_ASSIGN.

    // === Pass 1: Round-robin + fallback assignment ===
    // Common case: assign diags sequentially to PEs in round-robin.
    // Fallback: if round-robin PE is full, fill remaining PEs one by one.
    // No bitmap needed — unloaded diags are simply cursor..total_fin0-1.
    for (int pe = 0; pe < 4; pe++) {
        s1c[pe] = 0;                                     // nd=0
        s1c[4 + pe] = 0;                                // na=0
        s1c[8 + pe] = pe * SPM_BANK_GROUP_SIZE + fin0_base;
    }
    // Arc data pointer: resume from saved position or compute initial
    if (s1c[22] == 0) {
        gr[11] = s1c[21] * 2 + ARC_META_BASE;           // arc_data_start
    } else {
        gr[11] = s1c[23];                                // resume arc_ptr
    }

    // Inline assignment: copy diag+arcmeta+arcs from s1c to PE's SPM.
    // diag (2w contiguous) and arcmeta (2w contiguous) use mvdq_copy
    // for bulk bandwidth; arcs use a label-driven per-arc loop
    // because the 3-word dst stride (vs 2-word src stride) prevents
    // pure mvdq.
    //
    // Round-7+8 rewrite: the F0B_ASSIGN helper macro has been
    // inlined at both call sites (f0b_rr and f0b_mv). Each site
    // has its own set of f0b_arc_loop/done labels (rr vs mv) to
    // preserve unique function-scope names. gr[11] is the persistent
    // arc_ptr across per-diag assignments; gr[1] holds the per-diag
    // src_ptr stash. Arc loop architectural state: gr[9] = arc
    // counter, gr[7] = dst_ptr, gr[10] = nv. Each s1c read stages
    // through gr[3] with a 1-cycle gap; each SPM store is its own
    // ISA line.

    // Round-robin common-case loop: one diag per PE cycling 0,1,2,3.
    // pe_rr held architecturally in gr[2]; derived from s1c[22] at
    // entry via gr[4] (dead here; gr[11] holds persistent arc_ptr
    // and must not be clobbered) and advanced in-register after
    // each successful assign.
    {
        gr[4] = s1c[22];
        //NOP                                    // s1c 1-cycle gap
        gr[2] = gr[4] & 3;                       // pe_rr = cursor & 3
    f0b_rr:
        if (s1c[22] >= s1c[20]) goto f0b_rr_done;
        gr[9] = s1c[22] + s1c[22];
        // R8: split 'gr[10] = s1c[A+1] - s1c[A]' via gr[4] stash.
        gr[4] = s1c[ARC_META_BASE + gr[9]];
        //NOP                                    // s1c 1-cycle gap
        gr[10] = s1c[ARC_META_BASE + gr[9]+1];
        //NOP                                    // s1c 1-cycle gap
        gr[10] = gr[10] - gr[4];
        //NOP                                    // RAW barrier
        if (s1c[gr[2]] >= FIN0_N_MAX_DIAGS) goto f0b_rr_break;
        gr[7] = s1c[4 + gr[2]] + gr[10];
        if (gr[7] > FIN0_N_MAX_ARCS) goto f0b_rr_break;
        // === Inlined F0B_ASSIGN(s1c[22], gr[2], rr) ===
        gr[5] = s1c[8 + gr[2]];
        gr[6] = s1c[gr[2]];
        gr[7] = gr[6] + gr[6];
        gr[9] = s1c[22] + s1c[22];
        mvdq_copy(&spm[gr[5]+FIN0_ARCMETA+gr[7]],
                  &s1c[ARC_META_BASE+gr[9]], 2);
        mvdq_copy(&spm[gr[5]+FIN0_DIAGS+gr[7]],
                  &s1c[32+gr[9]], 2);
        gr[4] = s1c[ARC_META_BASE+gr[9]];
        //NOP                                    // s1c gap
        gr[10] = s1c[ARC_META_BASE+gr[9]+1];
        //NOP                                    // s1c gap
        gr[10] = gr[10] - gr[4];                 // nv
        //NOP                                    // RAW barrier
        gr[8] = s1c[4 + gr[2]];
        gr[1] = gr[11];                          // src_ptr = arc_ptr
        gr[7] = gr[8] + gr[8];                   // 2*na
        //NOP                                    // RAW barrier
        gr[7] = gr[7] + gr[8];                   // 3*na
        //NOP                                    // RAW barrier
        gr[7] = gr[7] + gr[5];                   // + pe_spm
        //NOP                                    // RAW barrier
        gr[7] = gr[7] + FIN0_ARCS;               // dst_ptr
        gr[9] = 0;                               // arc counter
    f0b_arc_loop_rr:
        if (gr[9] >= gr[10]) goto f0b_arc_done_rr;
        gr[3] = s1c[gr[1]];                      // arc.lo
        //NOP                                    // s1c gap
        spm[gr[7]] = gr[3];
        gr[3] = s1c[gr[1]+1];                    // arc.hi
        //NOP                                    // s1c gap
        spm[gr[7]+1] = gr[3];
        gr[9] = gr[9] + 1;
        gr[1] = gr[1] + 2;
        gr[7] = gr[7] + 3;
        goto f0b_arc_loop_rr;
    f0b_arc_done_rr:
        s1c[4+gr[2]] = gr[8] + gr[10];
        s1c[gr[2]] = gr[6] + 1;
        gr[11] = gr[11] + gr[10];                // += nv
        //NOP                                    // RAW barrier
        gr[11] = gr[11] + gr[10];                // += nv (= 2*nv)
        // === End inlined F0B_ASSIGN (rr) ===
        s1c[22] = s1c[22] + 1;
        gr[2] = gr[2] + 1;
        //NOP                                    // WAW barrier for gr[2]
        gr[2] = gr[2] & 3;
        goto f0b_rr;
    f0b_rr_break:
        (void)0;
    f0b_rr_done:
        (void)0;
    }

    // Per-PE fallback: fill remaining PEs sequentially
    for (int pe = 0; pe < 4 && s1c[22] < s1c[20]; pe++) {
    f0b_mv:
        if (s1c[22] >= s1c[20]) goto f0b_mv_next;
        gr[9] = s1c[22] + s1c[22];
        // R8: split 'gr[10] = s1c[A+1] - s1c[A]' via gr[4] stash.
        gr[4] = s1c[ARC_META_BASE + gr[9]];
        //NOP                                    // s1c 1-cycle gap
        gr[10] = s1c[ARC_META_BASE + gr[9]+1];
        //NOP                                    // s1c 1-cycle gap
        gr[10] = gr[10] - gr[4];
        //NOP                                    // RAW barrier
        if (s1c[pe] >= FIN0_N_MAX_DIAGS) goto f0b_mv_next;
        gr[7] = s1c[4 + pe] + gr[10];
        if (gr[7] > FIN0_N_MAX_ARCS) goto f0b_mv_next;
        // === Inlined F0B_ASSIGN(s1c[22], pe, mv) ===
        gr[5] = s1c[8 + pe];
        gr[6] = s1c[pe];
        gr[7] = gr[6] + gr[6];
        gr[9] = s1c[22] + s1c[22];
        mvdq_copy(&spm[gr[5]+FIN0_ARCMETA+gr[7]],
                  &s1c[ARC_META_BASE+gr[9]], 2);
        mvdq_copy(&spm[gr[5]+FIN0_DIAGS+gr[7]],
                  &s1c[32+gr[9]], 2);
        gr[4] = s1c[ARC_META_BASE+gr[9]];
        //NOP                                    // s1c gap
        gr[10] = s1c[ARC_META_BASE+gr[9]+1];
        //NOP                                    // s1c gap
        gr[10] = gr[10] - gr[4];                 // nv
        //NOP                                    // RAW barrier
        gr[8] = s1c[4 + pe];
        gr[1] = gr[11];                          // src_ptr = arc_ptr
        gr[7] = gr[8] + gr[8];                   // 2*na
        //NOP                                    // RAW barrier
        gr[7] = gr[7] + gr[8];                   // 3*na
        //NOP                                    // RAW barrier
        gr[7] = gr[7] + gr[5];                   // + pe_spm
        //NOP                                    // RAW barrier
        gr[7] = gr[7] + FIN0_ARCS;               // dst_ptr
        gr[9] = 0;                               // arc counter
    f0b_arc_loop_mv:
        if (gr[9] >= gr[10]) goto f0b_arc_done_mv;
        gr[3] = s1c[gr[1]];                      // arc.lo
        //NOP                                    // s1c gap
        spm[gr[7]] = gr[3];
        gr[3] = s1c[gr[1]+1];                    // arc.hi
        //NOP                                    // s1c gap
        spm[gr[7]+1] = gr[3];
        gr[9] = gr[9] + 1;
        gr[1] = gr[1] + 2;
        gr[7] = gr[7] + 3;
        goto f0b_arc_loop_mv;
    f0b_arc_done_mv:
        s1c[4+pe] = gr[8] + gr[10];
        s1c[pe] = gr[6] + 1;
        gr[11] = gr[11] + gr[10];                // += nv
        //NOP                                    // RAW barrier
        gr[11] = gr[11] + gr[10];                // += nv (= 2*nv)
        // === End inlined F0B_ASSIGN (mv) ===
        s1c[22] = s1c[22] + 1;
        goto f0b_mv;
    f0b_mv_next:
        (void)0;
    }

    // s1c[22] is already authoritative cursor; no write-back needed.
    s1c[23] = gr[11]; // save arc_ptr for next pass

    // === Pass 2: Batch S2 loads for ts_off (PE-inner) ===
    {
        gr[5] = 0;                                       // si: max_na
        for (int pe = 0; pe < 4; pe++) {
            gr[7] = s1c[4 + pe];                         // mv
            //NOP
            if (gr[7] > gr[5]) gr[5] = gr[7];
        }
        gr[14] = gr[29] & 0xFFFF;                       // andi: seq_off_s2
        gr[11] = 0;                                      // si: a=0
        //NOP
    f0b_p2:
        if (gr[11] >= gr[5]) goto f0b_p2_done;          // bge
        //NOP
        for (int pe = 0; pe < 4; pe++) {
            gr[10] = s1c[4 + pe];                        // mv: na[pe]
            //NOP
            if (gr[11] >= gr[10]) continue;               // bge: skip
            gr[7] = s1c[8 + pe];                         // mv: pe_spm
            gr[8] = gr[11] + gr[11];                     // add: 2*a
            gr[8] = gr[8] + gr[11];                      // add: 3*a
            //NOP
            gr[8] = gr[7] + FIN0_ARCS + gr[8];          // add: arc addr
            //NOP
            gr[9] = spm[gr[8]];                          // mv: SPM load
            //NOP                                        // SPM lat 1/3 (AC-11 slot-safe)
            //NOP                                        // SPM lat 2/3
            //NOP                                        // SPM lat 3/3
            gr[9] = (unsigned)gr[9] >> 16;               // shifti_r: w (zero-ext)
            //NOP
            // R7: stage S2 load through gr[13] with waitLSQ+NOP before
            // the SPM store so the ts_off value has settled.
            gr[13] = s2->buffer[gr[14] + gr[9]];        // S2 load
            // waitLSQ
            //NOP                                        // LSQ settle
            spm[gr[8]+2] = gr[13];                      // mv: ts_off
        }
        gr[11] = gr[11] + 1;                            // addi
        goto f0b_p2;
    f0b_p2_done:
        // waitLSQ
        (void)0;
    }

    // === Pass 3: Batch MM loads for HA (diag-outer, PE-inner) ===
    {
        gr[2] = 0;                                       // si: max_nd
        for (int pe = 0; pe < 4; pe++) {
            gr[7] = s1c[pe];                             // mv
            //NOP
            if (gr[7] > gr[2]) gr[2] = gr[7];
        }
        s1c[12]=0; s1c[13]=0; s1c[14]=0; s1c[15]=0;    // pai[0..3]=0
        gr[14] = 0;                                      // si: d=0
        //NOP
    f0b_p3_d:
        if (gr[14] >= gr[2]) goto f0b_p3_done;          // bge
        //NOP
        for (int pe = 0; pe < 4; pe++) {
            gr[13] = s1c[pe];                            // mv: nd[pe]
            //NOP
            if (gr[14] >= gr[13]) continue;               // bge: skip
            gr[7] = s1c[8 + pe];                         // mv: pe_spm
            gr[9] = gr[14] + gr[14];                     // add: 2*d
            //NOP
            // Read diag from SPM for i_val (pipelined loads, rule 6)
            gr[3] = spm[gr[7] + FIN0_DIAGS + gr[9]];     // mv: vd
            gr[4] = spm[gr[7] + FIN0_DIAGS + gr[9] + 1]; // mv: k
            //NOP                                         // SPM lat 1/3 (AC-11 slot-safe)
            //NOP                                         // SPM lat 2/3
            //NOP                                         // SPM lat 3/3
            gr[5] = gr[3] & 0xFFFF;                      // andi: vd.lo
            //NOP
            gr[5] = gr[5] - GWF_DIAG_SHIFT;              // subi
            //NOP
            gr[5] = gr[5] + gr[4];                       // add: i_val
            // Arc count from SPM arcmeta (pipelined loads, rule 6)
            gr[8] = spm[gr[7] + FIN0_ARCMETA + gr[9]];   // mv: lo
            gr[13] = spm[gr[7] + FIN0_ARCMETA + gr[9]+1]; // mv: hi
            //NOP                                         // SPM lat 1/3 (AC-11 slot-safe)
            //NOP                                         // SPM lat 2/3
            //NOP                                         // SPM lat 3/3
            gr[10] = gr[13] - gr[8];                      // sub: nv
            gr[1] = 0;                                   // si: a=0
            //NOP
        f0b_p3_a:
            if (gr[1] >= gr[10]) goto f0b_p3_a_done;    // bge
            //NOP
            {
                gr[8] = s1c[12 + pe];                    // mv: pai
                //NOP
                gr[9] = gr[8] + gr[8];                   // add: 2*pai
                //NOP                                    // RAW barrier
                gr[9] = gr[9] + gr[8];                   // add: 3*pai
                //NOP
                gr[9] = gr[7] + FIN0_ARCS + gr[9];      // add: arc addr
                //NOP
                gr[3] = spm[gr[9]];                      // mv: SPM load
                gr[4] = gr[5] + 1;                       // addi: i_val+1 (fills gap 1/3)
                //NOP                                    // SPM lat 2/3 (AC-11 slot-safe)
                //NOP                                    // SPM lat 3/3
                gr[3] = (unsigned)gr[3] >> 16;           // shifti_r: w (zero-ext)
                // non-ISA: hash multiply
                uint32_t hk = ((uint32_t)gr[3] << 16)
                    | ((uint32_t)gr[4] & 0xFFFF);
                uint32_t h = hk * 2654435769U >> (32-22);
                uint32_t b = (h >> 2) & 0xFFFFF;
                // 4*pai for HA addr
                gr[9] = gr[8] + gr[8];                   // add: 2*pai
                //NOP                                    // RAW barrier
                gr[9] = gr[9] + gr[9];                   // add: 4*pai
                //NOP
                gr[9] = gr[7] + FIN0_HA + gr[9];        // add: ha addr
                int ms = ha_off + (int)(b * 4);
                // R7/R9: use mvdq_copy for contiguous 4-word HA
                // bucket MM->SPM transfer; waitLSQ + 2-NOP settle.
                mvdq_copy(&spm[gr[9]], &mm[ms], 4);
                // waitLSQ
                //NOP                                    // LSQ settle
                //NOP
                s1c[12 + pe] = gr[8] + 1;               // addi: pai++
            }
            gr[1] = gr[1] + 1;                          // addi
            goto f0b_p3_a;
        f0b_p3_a_done:
            (void)0;
        }
        gr[14] = gr[14] + 1;                            // addi
        goto f0b_p3_d;
    f0b_p3_done:
        // waitLSQ
        (void)0;
    }

    // === Pass 4: Write metadata ===
    for (int pe = 0; pe < 4; pe++) {
        gr[7] = s1c[8 + pe];                            // mv: pe_spm
        gr[8] = s1c[pe];                                 // mv: nd
        gr[9] = s1c[4 + pe];                            // mv: na
        //NOP
        spm[gr[7] + FIN0_META]     = gr[8];              // mv: n_diags
        spm[gr[7] + FIN0_META + 1] = gr[9];              // mv: n_arcs
        spm[gr[7] + FIN0_META + 2] = 0;                  // si
        spm[gr[7] + FIN0_META + 3] = 0;                  // si
        spm[gr[7] + FIN0_META + 4] = 0;                  // si
    }

    // Final completion flag: re-read s1c[22] (cursor) and s1c[20]
    // (total_fin0) through gr with 1-NOP staging. Passes 2-3 have
    // operated long after the pass-1 C++ locals were written; the
    // authoritative values live in s1c[22]/s1c[20] and must be
    // re-read here.
    gr[11] = s1c[22];
    //NOP                                       // s1c gap
    gr[10] = s1c[20];
    //NOP                                       // s1c gap
    gr[2] = (gr[11] < gr[10]) ? 1 : 0;
}

int pe_array::decode(unsigned long instruction, int* PC, int simd, int setting, int main_instruction_setting) {
#ifdef PROFILE
    // printf("main j=%d\t", main_addressing_register[12]);
    // printf("main j=%d\t", main_addressing_register[4]);
    printf("main i=%d j=%d\t", main_addressing_register[8]/20 - 1, main_addressing_register[5]);
#endif

    // pe_array position:   
    // src - 1/3/4/5/6/7/10
    // dest - 1/3/4/5/6/8/9
    // 0 - Compute register
    // 1 - Addressing register
    // 2 - Scratchpad memory
    // 3-6 FIFO[0-3]
    // 7 - Input buffer
    // 8 - Output buffer
    // 9 - In data port
    // 10 - Out data port
    // 11 - imm
    // 12 - none
    if (instruction == 0x20f7800000000) {
        fprintf(stderr, "WARNING: PE_ARRAY PC=%d cycle=%d executing uninitialized instruction.\n", *PC, cycle);
    }

    int i, rd, rs1, rs2, imm, comp_0 = 0, comp_1 = 0, sum = 0, add_a = 0, add_b = 0;
    LoadResult data{};

    int8_t rs[4];
        
    unsigned long dest_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long src_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long reg_immBar_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    unsigned long reg_auto_increasement_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    unsigned long reg_imm_0_sign_bit_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    unsigned long reg_imm_0_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_0_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_immBar_flag_1_mask = (unsigned long)1 << (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_auto_increasement_flag_1_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_imm_1_sign_bit_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    unsigned long reg_imm_1_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_1_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << CTRL_OPCODE_WIDTH;
    unsigned long opcode_mask = (unsigned long)((1 << CTRL_OPCODE_WIDTH) - 1);
    unsigned long magic_mask = (unsigned long)((1ul << (63)));
    unsigned long magic_payload_mask = (unsigned long)(0xFFFFFFFF);

    int dest = (instruction & dest_mask) >> (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    int src = (instruction & src_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    int reg_immBar_flag_0 = (instruction & reg_immBar_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    int reg_auto_increasement_flag_0 = (instruction & reg_auto_increasement_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    int reg_imm_0 = (instruction & reg_imm_0_mask) >> (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_0_sign_bit = (instruction & reg_imm_0_sign_bit_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    int imm_sign_extend_mask = ~((1 << IMMEDIATE_WIDTH) - 1);
    int sext_imm_0 = reg_imm_0 | (reg_imm_0_sign_bit ? imm_sign_extend_mask : 0);
    int reg_0 = (instruction & reg_0_mask) >> (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_immBar_flag_1 = (instruction & reg_immBar_flag_1_mask) >> (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_auto_increasement_flag_1 = (instruction & reg_auto_increasement_flag_1_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1 = (instruction & reg_imm_1_mask) >> (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1_sign_bit = (instruction & reg_imm_1_sign_bit_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    int sext_imm_1 = reg_imm_1 | (reg_imm_1_sign_bit ? imm_sign_extend_mask : 0);
    int reg_1 = (instruction & reg_1_mask) >> CTRL_OPCODE_WIDTH;
    int opcode = instruction & opcode_mask;

    bool is_magic = (instruction & magic_mask);
    int  magic_payload = instruction & magic_payload_mask;

#ifdef PROFILE
    printf("PC = %d @%d:%016lx\t", *PC, cycle, instruction);
#endif
    if (main_instruction_setting == MAIN_INSTRUCTION_2) {
        if (((opcode == 4 || opcode == 5) && (dest == 5 || dest == 6 || dest == 11 || dest == 12 || dest == 13 || dest == 14)) || opcode == 14) {
            (*PC)++;
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    } else if (main_instruction_setting == MAIN_INSTRUCTION_1) {
        if (dest == 5 || dest == 6 || dest == 11 || dest == 12 || dest == 13 || dest == 14) {
            (*PC)++;
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    }

#ifdef DEBUG
    printf("dest: %d src: %d reg_immBar_flag_0: %d reg_auto_increasement_flag_0: %d reg_imm_0_sign_bit: %d sext_imm_0: %d, reg_0: %d reg_immBar_flag_1: %d reg_auto_increasement_flag_1: %d reg_imm_1_sign_bit: %d sext_imm_1: %d reg_1: %d opcode: %d\n", dest, src, reg_immBar_flag_0, reg_auto_increasement_flag_0, reg_imm_0_sign_bit, sext_imm_0, reg_0, reg_immBar_flag_1, reg_auto_increasement_flag_1, reg_imm_1_sign_bit, sext_imm_1, reg_1, opcode);
#endif

    if (is_magic) {
        constexpr int MAGIC_MASK_BITS = 8;
        constexpr int MAGIC_MASK = (1 << MAGIC_MASK_BITS) - 1;
        int magic_id = magic_payload;
        int magic_mask = 0;
        if (magic_payload >= (1 << MAGIC_MASK_BITS)) {
            magic_id = magic_payload >> MAGIC_MASK_BITS;
            magic_mask = magic_payload & MAGIC_MASK;
        }

        if (magic_id == 1) {
            // GWFA init: reconstruct sub, call gwfa_init
            if (va_regfile[0] != 0) {
                subgfa_subgraph_t sub;
                sub.graphSeq = (uint32_t*)(uintptr_t)va_regfile[0];
                sub.seq_off = (uint32_t*)(uintptr_t)va_regfile[1];
                sub.seq_len = (int32_t*)(uintptr_t)va_regfile[2];
                sub.arc = (subgfa_arc_t*)(uintptr_t)va_regfile[3];
                sub.arc_off = (uint32_t*)(uintptr_t)va_regfile[4];
                sub.n_vtx = main_addressing_register[17];
                sub.n_arc = main_addressing_register[18];
                const uint32_t *q = (const uint32_t*)(uintptr_t)va_regfile[5];
                gwfa_init(main_addressing_register[16], q, &sub, GWFA_DBG_RUNTIME);
                // Load query (2-bit packed) into interleaved SPM
                int32_t ql = main_addressing_register[16];
                int q_words = (ql + 15) / 16;
                for (int i = 0; i < q_words; i++)
                    SPM_unit->buffer[apply_address_swizzle(GWFA_Q_START + i)] = (int)q[i];
                // Load graphSeq (2-bit packed) into interleaved SPM.
                // Vertex order in seq_off doesn't match offset order in graphSeq,
                // so scan all vertices for max extent.
                int gs_total = 0;
                for (int v = 0; v < (int)sub.n_vtx; v++) {
                    int end = (int)sub.seq_off[v] + sub.seq_len[v];
                    if (end > gs_total) gs_total = end;
                }
                int gs_words = (gs_total + 15) / 16;
                for (int i = 0; i < gs_words; i++)
                    SPM_unit->buffer[apply_address_swizzle(GWFA_GS_START + i)] = (int)sub.graphSeq[i];
                // Set PE gr[14] = ql
                for (int pe = 0; pe < 4; pe++)
                    pe_unit[pe]->addr_regfile_unit->st(14, ql);

                // Load graph topology into S2
                int off = GRAPH_START;
                s2->buffer[off++] = (int)sub.n_vtx;
                s2->buffer[off++] = (int)sub.n_arc;
                int seq_off_s2 = off;
                for (uint32_t v = 0; v < sub.n_vtx; v++)
                    s2->buffer[off++] = (int)sub.seq_off[v];
                if (off & 1) off++; // even-align
                int seq_len_s2 = off;
                for (uint32_t v = 0; v < sub.n_vtx; v++)
                    s2->buffer[off++] = sub.seq_len[v];
                if (off & 1) off++;
                int arc_off_s2 = off;
                for (uint32_t v = 0; v <= sub.n_vtx; v++)
                    s2->buffer[off++] = (int)sub.arc_off[v];
                if (off & 1) off++;
                int arc_s2 = off;
                for (uint32_t a = 0; a < sub.n_arc; a++) {
                    uint32_t vw = (uint32_t)sub.arc[a].v
                        | ((uint32_t)sub.arc[a].w << 16);
                    s2->buffer[off++] = (int)vw;
                    s2->buffer[off++] = sub.arc[a].ow;
                }

                // Packed registers: gr[29]=lo:seq_off_s2, hi:seq_len_s2
                //                   gr[18]=lo:n_arc, hi:arc_off_s2
                //                   gr[16]=lo:ql, hi:n_vtx
                //                   gr[12]=lo:s, hi:s_term
                main_addressing_register[12] =
                    (main_addressing_register[23] & 0xFFFF) << 16; // s=0, s_term in hi
                main_addressing_register[29] =
                    (seq_off_s2 & 0xFFFF) | (seq_len_s2 << 16);
                main_addressing_register[18] =
                    ((int)sub.n_arc & 0xFFFF) | (arc_off_s2 << 16);
                main_addressing_register[16] =
                    (ql & 0xFFFF) | ((int)sub.n_vtx << 16);
                main_addressing_register[30] = arc_s2;  // S2 base of arc[] data

                // Set MM pointer and base offsets
                mm = gwfa_get_mm();
                main_addressing_register[19] = gwfa_get_s_a_mm_off();
                main_addressing_register[20] = 0; // set by magic 4
                main_addressing_register[21] = gwfa_get_mm_A_off();
                main_addressing_register[22] = gwfa_get_mm_intv_off();
                // Zero runtime counters
                main_addressing_register[24] = 0;
                main_addressing_register[25] = 0;
                main_addressing_register[26] = 0;
                main_addressing_register[27] = 0;
                main_addressing_register[28] = 0;
            }
            main_addressing_register[15] = gwfa_get_n_a();
        } else if (magic_id == 3) {
            // GWFA print score, zero va_regfile
            printf("qqq %d qqq\n", gwfa_get_score());
            memset(va_regfile, 0, sizeof(va_regfile));
        } else if (magic_id == 4) {
            // GWFA begin step: sync gr→statics, call, refresh gr
            gwfa_sync_counters(
                main_addressing_register[24],
                (uint32_t)main_addressing_register[25],
                (uint32_t)main_addressing_register[26],
                (uint32_t)main_addressing_register[27],
                main_addressing_register[28]);
            gwfa_begin_step();
            // Refresh gr[] from gwfa.c (begin_step clears/swaps)
            main_addressing_register[19] = gwfa_get_s_a_mm_off();
            main_addressing_register[20] = gwfa_get_s_B_a_mm_off();
            main_addressing_register[24] = 0; // s_B_n
            main_addressing_register[25] = 0; // A_head
            main_addressing_register[26] = 0; // A_tail
            main_addressing_register[27] = 0; // A_count
            main_addressing_register[28] = 0; // intv_buf_n
            main_addressing_register[31] = 0; // ha_n_dirty
        } else if (magic_id == 5 && va_regfile[0] != 0) {
            // GWFA debug: print wavefront trace at distance gr_lo[12]
            gwfa_debug_step((int16_t)(main_addressing_register[12] & 0xFFFF));
        } else if (magic_id == 5) {
            // WFA print final score
            int score = main_addressing_register[12] - 1;
            printf("qqq %d qqq\n", score);
        } else if (magic_id == 7) {
            // GWFA tile load diags: MM → SPM directly (no S1c staging)
            // ISA-like: all state in gr[]/s1c[]/mm[]/spm[]
            constexpr int S1C_TILE_N = 512;
            constexpr int META_OFF = 1152;
            constexpr int DIAGS_PER_PE = 64;
            constexpr int A_TILE_OFF = 0;
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int *spm = SPM_unit->buffer;
            int buf_base = (magic_mask & 1)
                ? GWFA_BUF1_BASE : GWFA_BUF0_BASE;
            // Phase 1: compute per-PE tile_n → s1c + SPM metadata
            for (int pe = 0; pe < 4; pe++) {
                int pe_spm = pe * SPM_BANK_GROUP_SIZE + buf_base;
                gr[10] = gr[15] - gr[14];              // sub: n_a - cursor
                gr[10] = gr[10] - pe * DIAGS_PER_PE;   // subi: remaining
                //NOP
                if (gr[10] > DIAGS_PER_PE)              // blt
                    gr[10] = DIAGS_PER_PE;              // si
                if (gr[10] < 0)                          // blt
                    gr[10] = 0;                          // si
                //NOP
                s1c[S1C_TILE_N + pe] = gr[10];          // mv gr→S1c
                spm[pe_spm + META_OFF + 3] = gr[10];   // si (tile_n)
                if (gr[10] <= 0) {                       // bgt → skip
                    spm[pe_spm + META_OFF] = 0;         // si
                    spm[pe_spm + META_OFF + 1] = 0;     // si
                }
            }
            // Phase 2: hoisted peel + mvdq MM → SPM (direct, no S1c)
            // PE alloc: PE0=gr[1,3,4] PE1=gr[5,6,7] PE2=gr[8,9,10]
            //           PE3=gr[11,16,17]  gr[13]=peel/flag
            {
                // Setup per-PE src (MM), dst (SPM), end
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    // MM src = s_a_off + (cursor + pe*64)*2
                    gr[13] = gr[14] + pe * DIAGS_PER_PE;  // addi
                    gr[13] = gr[13] + gr[13];             // add: *2
                    src = gr[13] + gr[19];                // add: + s_a_off
                    // end = src + 2*tile_n
                    gr[13] = s1c[S1C_TILE_N + pe];        // mv: tile_n
                    //NOP
                    end = gr[13] + gr[13];                // add: 2*tile_n
                    //NOP
                    end = src + end;                       // add: end
                    // SPM dst = pe_base + A_TILE_OFF
                    dst = pe * SPM_BANK_GROUP_SIZE + buf_base + A_TILE_OFF;
                }
                // Peel (handle tile_n%4 remainder)
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[S1C_TILE_N + pe] & 3;   // andi: n%4
                    //NOP
                m7_peel:
                    if (gr[13] <= 0) goto m7_peel_done; gr[13] -= 1;
                    spm[dst] = mm[src]; spm[dst+1] = mm[src+1]; // mvd MM→SPM
                    src += 2; dst += 2;
                    goto m7_peel;
                m7_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main loop
                gr[23] = gr[4] - gr[1];
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23];
            m7_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m7_sp_pe1;
                mvdq_copy(&spm[gr[3]], &mm[gr[1]], 8);   // PE0: MM→SPM
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m7_sp_pe1:
                if (gr[5] >= gr[7]) goto m7_sp_pe2;
                mvdq_copy(&spm[gr[6]], &mm[gr[5]], 8);   // PE1
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m7_sp_pe2:
                if (gr[8] >= gr[10]) goto m7_sp_pe3;
                mvdq_copy(&spm[gr[9]], &mm[gr[8]], 8);   // PE2
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m7_sp_pe3:
                if (gr[11] >= gr[17]) goto m7_sp_check;
                mvdq_copy(&spm[gr[16]], &mm[gr[11]], 8);  // PE3
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m7_sp_check:
                if (gr[13] != 0) goto m7_sp_outer;
                // Convert PE1-3 cursors to deltas for main loop
                gr[5] = gr[5] - gr[1];
                gr[6] = gr[6] - gr[3];
                gr[8] = gr[8] - gr[1];
                gr[9] = gr[9] - gr[3];
                gr[11] = gr[11] - gr[1];
                gr[16] = gr[16] - gr[3];
                gr[13] = (unsigned)gr[23] >> 3;
            m7_main_outer:
                if (gr[13] <= 0) goto m7_all_done; gr[13] -= 1;
                mvdq_copy(&spm[gr[3]], &mm[gr[1]], 8);                   // PE0
                mvdq_copy(&spm[gr[3]+gr[6]], &mm[gr[1]+gr[5]], 8);      // PE1
                mvdq_copy(&spm[gr[3]+gr[9]], &mm[gr[1]+gr[8]], 8);      // PE2
                mvdq_copy(&spm[gr[3]+gr[16]], &mm[gr[1]+gr[11]], 8);    // PE3
                gr[1] += 8; gr[3] += 8;
                goto m7_main_outer;
            m7_all_done:
                (void)0;
            }
            // Advance cursor
            gr[7] = gr[15] - gr[14];
            //NOP
            if (gr[7] > 256) gr[7] = 256;
            //NOP
            gr[14] = gr[14] + gr[7];
        } else if (magic_id == 8) {
            // GWFA tile load seq info: vertex extract from SPM + S2 → SPM
            // Diag data already in SPM (loaded by magic 7 directly).
            // Phase 1: scan SPM A_TILE to extract unique vertices → S1c
            // Phase 2: iterate vertex list, S2 lookup → SPM SEQ_INFO
            constexpr int A_TILE_OFF = 0;
            constexpr int SEQ_INFO_OFF = 128;
            constexpr int META_OFF = 1152;
            constexpr int S1C_TILE_N = 512;
            constexpr int S1C_NNODES = 516;
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int *spm = SPM_unit->buffer;
            int buf_base = (magic_mask & 1)
                ? GWFA_BUF1_BASE : GWFA_BUF0_BASE;
            // === Phase 1: scan SPM diags, extract unique vertices → S1c ===
            gr[5] = 0;                                   // si: vtx write_ptr
            for (int pe = 0; pe < 4; pe++) {
                int pe_spm = pe * SPM_BANK_GROUP_SIZE + buf_base;
                gr[10] = s1c[S1C_TILE_N + pe];          // mv (tile_n)
                //NOP
                gr[2] = 0;                               // si: n_nodes
                gr[6] = -1;                              // si: prev_v
                gr[1] = gr[10] + gr[10];                 // add: pe_words
                gr[11] = 0;                              // si: word offset
                //NOP
            m8_scan:
                if (gr[11] >= gr[1]) goto m8_scan_done;
                // Read vd from SPM (data already there from magic 7)
                gr[7] = spm[pe_spm + A_TILE_OFF + gr[11]]; // mv SPM→gr
                //NOP
                gr[7] = (unsigned)gr[7] >> 16;           // shifti_r (v)
                //NOP
                if (gr[7] == gr[6]) goto m8_scan_skip;   // beq: same vertex
                //NOP
                s1c[gr[5]++] = gr[7];                    // mv gr→S1c
                gr[2] = gr[2] + 1;                       // addi (n_nodes++)
                gr[6] = gr[7];                           // mv (prev_v = v)
            m8_scan_skip:
                gr[11] = gr[11] + 2;                     // addi (next diag)
                goto m8_scan;                             // jump
            m8_scan_done:
                s1c[S1C_NNODES + pe] = gr[2];           // mv (n_nodes)
                spm[pe_spm + META_OFF + 2] = gr[2];     // mv → SPM
            }
            // === Phase 2: vertex list → S2 lookup → SPM SEQ_INFO ===
            gr[8] = gr[29] & 0xFFFF;                     // andi (seq_off_s2)
            gr[9] = (unsigned)gr[29] >> 16;              // shifti_r (seq_len_s2)
            gr[1] = 0;                                   // si: vtx read_ptr
            //NOP
            for (int pe = 0; pe < 4; pe++) {
                int pe_spm = pe * SPM_BANK_GROUP_SIZE + buf_base;
                gr[10] = s1c[S1C_NNODES + pe];          // mv (n_nodes)
                //NOP
                if (gr[10] <= 0) goto m8_seq_next; gr[11] = 0; // bgt; si (paired)
            m8_seq_loop:
                if (gr[11] >= gr[10]) goto m8_seq_done; gr[7] = s1c[gr[1]]; // bge; mv (paired)
                //NOP
                gr[3] = gr[8] + gr[7];                  // add (seq_off_s2+v)
                gr[4] = gr[9] + gr[7];                  // add (seq_len_s2+v)
                // Write directly S2→SPM (no gr intermediate; avoids S2 latency hazard)
                gr[7] = gr[11] + gr[11];                         // add: 2*node_idx
                //NOP
                spm[pe_spm + SEQ_INFO_OFF + gr[7]] = s2->buffer[gr[3]];     // mv S2→SPM (seq_off)
                spm[pe_spm + SEQ_INFO_OFF + gr[7] + 1] = s2->buffer[gr[4]]; // mv S2→SPM (seq_len)
                gr[1] = gr[1] + 1;                       // addi (read_ptr++)
                gr[11] = gr[11] + 1;                     // addi (node_idx++)
                goto m8_seq_loop;                         // jump
            m8_seq_done:
            m8_seq_next:
                (void)0;
            }
        } else if (magic_id == 9) {
            // GWFA tile writeback: SPM → MM
            // ISA-like: all state in gr[]/spm[]/mm[]/s1c[]
            // s1c layout: [0..3]=tb_n, [4..7]=ta_n, [8..11]=n_intv,
            //             [12..15]=b_dst, [16..19]=intv_dst
            constexpr int B_TILE_OFF = 256;
            constexpr int INTV_TILE_OFF = 640;
            constexpr int A_OUT_OFF = 1024;
            constexpr int META_OFF = 1152;
            constexpr int A_MASK_VAL = (16 << 20) - 1;
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int *spm = SPM_unit->buffer;
            int buf_base = (magic_mask & 1)
                ? GWFA_BUF1_BASE : GWFA_BUF0_BASE;
            // === Section 1: FIFO pop + compare-swap ===
            {
                int pe0_base = buf_base; // pe0 * SPM_BANK_GROUP_SIZE = 0
                if (gr[14] <= 0) goto m9_s1_skip;         // bgt (cursor>0)
                //NOP
                if (fifo_unit[0][0].size() <= 0)           // FIFO empty?
                    goto m9_s1_skip;
                gr[3] = fifo_unit[0][0].pop();             // mv FIFO→gr
                gr[4] = fifo_unit[0][1].pop();             // mv FIFO→gr
                // check tb_n[0] > 0
                gr[7] = spm[pe0_base + META_OFF];          // mv SPM→gr
                //NOP; //NOP
                if (gr[7] <= 0) goto m9_s1_write;          // bgt
                // compare fifo_vd > B[0].vd (unsigned)
                gr[8] = spm[pe0_base + B_TILE_OFF];        // mv SPM→gr
                //NOP; //NOP
                if ((uint32_t)gr[3] <= (uint32_t)gr[8])
                    goto m9_s1_write;                       // bge unsigned
                // swap: gr[3,4] ↔ spm[B_TILE+0,1]
                gr[9] = spm[pe0_base + B_TILE_OFF + 1];   // mv SPM→gr
                //NOP; //NOP
                spm[pe0_base + B_TILE_OFF] = gr[3];        // mv gr→SPM
                spm[pe0_base + B_TILE_OFF + 1] = gr[4];   // mv gr→SPM
                gr[3] = gr[8];                              // mv
                gr[4] = gr[9];                              // mv
                // Fix PE0[0] vs PE0[1]: after swap, PE0[0] may be > PE0[1]
                if (gr[7] >= 2) {                           // bgt: tb_n >= 2
                    gr[8] = spm[pe0_base + B_TILE_OFF + 2]; // mv: PE0[1].vd
                    if ((uint32_t)spm[pe0_base + B_TILE_OFF]
                        > (uint32_t)gr[8]) {
                        int tmp_vd = spm[pe0_base + B_TILE_OFF];
                        int tmp_k  = spm[pe0_base + B_TILE_OFF + 1];
                        spm[pe0_base + B_TILE_OFF]     = gr[8];
                        spm[pe0_base + B_TILE_OFF + 1] =
                            spm[pe0_base + B_TILE_OFF + 3];
                        spm[pe0_base + B_TILE_OFF + 2] = tmp_vd;
                        spm[pe0_base + B_TILE_OFF + 3] = tmp_k;
                    }
                }
            m9_s1_write:
                // write to MM: mm[s_B_a_base + 2*s_B_n]
                gr[7] = gr[20] + gr[24];                   // add
                //NOP
                mm[gr[7] + gr[24]] = gr[3]; mm[gr[7] + gr[24] + 1] = gr[4]; // mvd (register-offset)
                gr[24] = gr[24] + 1;                        // addi
            m9_s1_skip:
                (void)0;
            }
            // === Section 2: Read per-PE metadata → s1c ===
            for (int pe = 0; pe < 4; pe++) {
                int pe_base = pe * SPM_BANK_GROUP_SIZE + buf_base;
                gr[7] = spm[pe_base + META_OFF];           // mv (tb_n)
                gr[8] = spm[pe_base + META_OFF + 1];      // mv (ta_n)
                gr[9] = spm[pe_base + META_OFF + 7];      // mv (n_intv)
                //NOP; //NOP
                s1c[pe] = gr[7];                            // mv gr→S1c
                s1c[4 + pe] = gr[8];                       // mv gr→S1c
                s1c[8 + pe] = gr[9];                       // mv gr→S1c
            }
            // === Section 2b: Push PE3 last B entry to FIFO ===
            // Consumed by NEXT tile group's writeback (Section 1)
            {
                int pe3_base = 3 * SPM_BANK_GROUP_SIZE + buf_base;
                gr[7] = spm[pe3_base + META_OFF];          // mv SPM→gr
                //NOP; //NOP
                if (gr[7] > 0) {
                    int off = pe3_base + B_TILE_OFF + 2 * (gr[7] - 1);
                    fifo_unit[0][0].push(spm[off]);        // mv SPM→FIFO
                    fifo_unit[0][1].push(spm[off + 1]);    // mv SPM→FIFO
                    s1c[3] = gr[7] - 1;                    // subi (adjust for writeback)
                }
                gr[2] = fifo_unit[0][0].size() > 0 ? 1 : 0;
            }
            // === Section 3: B diags SPM → MM (hoisted peel + mvdq) ===
            // PE alloc: PE0=gr[1,3,4] PE1=gr[5,6,7] PE2=gr[8,9,10]
            //           PE3=gr[11,16,17]  gr[13]=peel/flag
            {
                // Cumulative B destinations → s1c[12..15]
                gr[7] = gr[20] + gr[24];                   // add
                gr[7] = gr[7] + gr[24];                    // add (base+2*s_B_n)
                s1c[12] = gr[7];                            // mv
                for (int pe = 1; pe < 4; pe++) {
                    gr[8] = s1c[pe - 1];                   // mv S1c→gr
                    //NOP
                    gr[8] = gr[8] + gr[8];                 // add: 2*tb_n[pe-1]
                    gr[7] = gr[7] + gr[8];                 // add
                    s1c[12 + pe] = gr[7];                  // mv
                }
                // Setup per-PE src, dst, end
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base =
                        pe * SPM_BANK_GROUP_SIZE + buf_base;
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    gr[13] = s1c[pe];                      // mv: tb_n
                    //NOP
                    src = pe_base + B_TILE_OFF;            // si: src
                    end = gr[13] + gr[13];                 // add: 2*n
                    //NOP
                    end = src + end;                        // add: end
                    dst = s1c[12 + pe];                    // mv: dst
                }
                // Phase 1: Peel (handle n%4 remainder via mvd)
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[pe] & 3;                  // andi: n%4
                    //NOP
                m9_b_peel:
                    if (gr[13] <= 0) goto m9_b_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    mm[dst] = spm[src]; mm[dst+1] = spm[src+1]; // mvd
                    src += 2; dst += 2;                    // addi
                    goto m9_b_peel;                         // jump
                m9_b_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main unmasked loop
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3 → gr[23]=min_words
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23]; // adjust ends
            m9_b_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m9_b_sp_pe1;
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m9_b_sp_pe1:
                if (gr[5] >= gr[7]) goto m9_b_sp_pe2;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m9_b_sp_pe2:
                if (gr[8] >= gr[10]) goto m9_b_sp_pe3;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m9_b_sp_pe3:
                if (gr[11] >= gr[17]) goto m9_b_sp_check;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m9_b_sp_check:
                if (gr[13] != 0) goto m9_b_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;                // min_iters = min_words/8
            m9_b_main_outer:
                if (gr[13] <= 0) goto m9_b_done; gr[13] -= 1;  // bgt; subi (paired)
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m9_b_main_outer;
            m9_b_done:
                // Update s_B_n: gr[24] += sum(tb_n)
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[pe];                       // mv
                    //NOP
                    gr[24] = gr[24] + gr[7];               // add
                }
                // Debug: check B array sorted after each magic 9
            }
            // === Section 4: A-out diags SPM → MM circular queue ===
            {
                // Compute max_ta → gr[5]
                gr[5] = 0;                                  // si
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[4 + pe];                   // mv (ta_n)
                    //NOP
                    if (gr[7] > gr[5]) gr[5] = gr[7];      // bge; mv
                }
                // Strided single-word copy
                gr[11] = 0;                                 // si: j
                //NOP
            m9_a_outer:
                if (gr[11] >= gr[5]) goto m9_a_done;       // bge
                //NOP
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base =
                        pe * SPM_BANK_GROUP_SIZE + buf_base;
                    gr[10] = s1c[4 + pe];                  // mv (ta_n)
                    //NOP
                    gr[8] = gr[11] + gr[11];               // add: 2*j (slot 1 of branch cycle)
                    if (gr[11] >= gr[10]) continue;         // bge (slot 0, paired with add)
                    // idx = A_tail & A_MASK (concurrent with mvd)
                    gr[7] = gr[26] & A_MASK_VAL;           // andi
                    gr[9] = spm[pe_base + A_OUT_OFF + gr[8]]; gr[1] = spm[pe_base + A_OUT_OFF + gr[8] + 1]; // mvd

                    gr[7] = gr[7] + gr[7];                 // add: 2*idx
                    gr[27] = gr[27] + 1;                   // addi (A_count++)

                    mm[gr[7] + gr[21]] = gr[9]; mm[gr[7] + gr[21] + 1] = gr[1]; // mvd gr→MM (register-offset)
                    gr[26] = gr[26] + 1;                   // addi (A_tail++)
                    //NOP
                }
                gr[11] = gr[11] + 1;                       // addi
                goto m9_a_outer;                            // jump
            m9_a_done:
                (void)0;
            }
            // === Section 5: Intervals SPM → MM (hoisted peel + mvdq) ===
            {
                // Cumulative intv destinations → s1c[16..19]
                gr[7] = gr[22] + gr[28];                   // add
                gr[7] = gr[7] + gr[28];                    // add (base+2*n)
                s1c[16] = gr[7];                            // mv
                for (int pe = 1; pe < 4; pe++) {
                    gr[8] = s1c[8 + pe - 1];               // mv
                    //NOP
                    gr[8] = gr[8] + gr[8];                 // add: 2*n_intv
                    gr[7] = gr[7] + gr[8];                 // add
                    s1c[16 + pe] = gr[7];                  // mv
                }
                // Setup per-PE src, dst, end
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base =
                        pe * SPM_BANK_GROUP_SIZE + buf_base;
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    gr[13] = s1c[8 + pe];                  // mv: n_intv
                    //NOP
                    src = pe_base + INTV_TILE_OFF;         // si: src
                    end = gr[13] + gr[13];                 // add: 2*n
                    //NOP
                    end = src + end;                        // add: end
                    dst = s1c[16 + pe];                    // mv: dst
                }
                // Phase 1: Peel (handle n%4 remainder via mvd)
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[8 + pe] & 3;              // andi: n%4
                    //NOP
                m9_i_peel:
                    if (gr[13] <= 0) goto m9_i_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    mm[dst] = spm[src]; mm[dst+1] = spm[src+1]; // mvd
                    src += 2; dst += 2;                    // addi
                    goto m9_i_peel;                         // jump
                m9_i_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main unmasked loop
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3 → gr[23]=min_words
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23]; // adjust ends
            m9_i_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m9_i_sp_pe1;
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m9_i_sp_pe1:
                if (gr[5] >= gr[7]) goto m9_i_sp_pe2;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m9_i_sp_pe2:
                if (gr[8] >= gr[10]) goto m9_i_sp_pe3;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m9_i_sp_pe3:
                if (gr[11] >= gr[17]) goto m9_i_sp_check;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m9_i_sp_check:
                if (gr[13] != 0) goto m9_i_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;                // min_iters = min_words/8
            m9_i_main_outer:
                if (gr[13] <= 0) goto m9_i_done; gr[13] -= 1;  // bgt; subi (paired)
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m9_i_main_outer;
            m9_i_done:
                // Update intv_buf_n: gr[28] += sum(n_intv)
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[8 + pe];                   // mv
                    //NOP
                    gr[28] = gr[28] + gr[7];               // add
                }
            }
            // Section 6 (cursor advance) moved to magic 7 for overlap
        } else if (magic_id == 12) {
            // GWFA FIFO flush: write boundary element to B in MM
            // ISA-like: all state in gr[]/mm[]
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            gr[7] = gr[20] + gr[24];           // add: s_B_a_base + s_B_n
            gr[7] = gr[7] + gr[24];            // add: offset = 2*s_B_n
            //NOP
            mm[gr[7]] = gr[3];                 // mv MM ← gr (fifo_vd)
            mm[gr[7] + 1] = gr[4];             // mv MM ← gr (fifo_k)
            gr[24] = gr[24] + 1;               // addi (s_B_n++)
        } else if (magic_id == 14) {
            // Phase 2 tile load: pop A queue (MM) → SPM
            // ISA-like: all state in gr[]/spm[]/s1c[]/mm[]/s2[]
            //
            // SPM layout per PE (relative to pe_base):
            //   P2_VK_OFF  =   0: [vd, k] × tile_n      (2 words/entry, ≤64 entries = 128 words)
            //   P2_TS_OFF  = 128: [ts_off, vl] × tile_n  (2 words/entry, ≤64 entries = 128 words)
            //   P2_META_OFF = 1024: metadata
            //
            // Phase A: batch MM → SPM (vd/k), pe interleaved, then waitLSQ
            // Phase B: S2 → SPM (ts_off/vl), pe interleaved, then waitLSQ
            constexpr int P2_VK_OFF   = 0;
            constexpr int P2_TS_OFF   = 128;
            constexpr int P2_META_OFF = 1024;
            constexpr int P2_M_TILE_N = 4;
            constexpr int P2_TILE_SIZE = 64;
            constexpr int A_MASK_VAL = (16 << 20) - 1;
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int *spm = SPM_unit->buffer;
            int p2_base = (magic_mask & 1) ? GWFA_P2B_BASE : GWFA_P2_BASE;

            // Compute tile_n[pe] → s1c[0..3], a_head_start[pe] → s1c[4..7]
            // gr[2] = remaining A_count, gr[6] = cumulative a_off
            gr[2] = gr[27];                              // mv (A_count)
            gr[6] = 0;                                   // si
            for (int pe = 0; pe < 4; pe++) {
                gr[13] = gr[2];                          // mv: remaining
                //NOP
                if (gr[13] > P2_TILE_SIZE) gr[13] = P2_TILE_SIZE; // blt; si
                s1c[pe] = gr[13];                        // mv: tile_n[pe]
                gr[7] = gr[25] + gr[6];                  // add: A_head + a_off
                s1c[4 + pe] = gr[7];                     // mv: a_head_start[pe]
                gr[6] = gr[6] + gr[13];                  // add: cumulative a_off
                gr[2] = gr[2] - gr[13];                  // sub: remaining
            }
            gr[25] = gr[25] + gr[6];                     // add: A_head += total
            gr[27] = gr[27] - gr[6];                     // sub: A_count -= total

            // Compute max_tile_n → gr[10]
            gr[10] = 0;                                  // si
            for (int pe = 0; pe < 4; pe++) {
                gr[13] = s1c[pe];                        // mv
                //NOP
                if (gr[13] > gr[10]) gr[10] = gr[13];   // bge; mv
            }

            // Save max_tile_n (Phase A mvdq will clobber gr[10])
            s1c[8] = gr[10];                             // mv gr→S1c

            // Phase A: batch MM → SPM (vd/k) via mvdq, pe interleaved
            {
                constexpr int A_QUEUE_SIZE = A_MASK_VAL + 1;
                // Wrap check: does range cross queue boundary? (rare)
                gr[2] = s1c[4] & A_MASK_VAL;            // andi: masked A_head
                //NOP
                gr[2] = gr[2] + gr[6];                  // add: start + total
                if (gr[2] > A_QUEUE_SIZE) goto m14_a_wrap; // bgt (rare)
                //NOP

                // No wrap (common): setup per-PE src, dst, end
                // PE0=gr[1,3,4] PE1=gr[5,6,7] PE2=gr[8,9,10] PE3=gr[11,16,17]
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    gr[13] = s1c[4 + pe] & A_MASK_VAL;  // andi: masked a_head
                    //NOP
                    gr[13] = gr[13] + gr[13];            // add: *2 (word offset)
                    src = gr[13] + gr[21];               // add: A_base + 2*idx
                    gr[13] = s1c[pe];                    // mv: tile_n
                    //NOP
                    end = gr[13] + gr[13];               // add: 2*tile_n (words)
                    //NOP
                    end = src + end;                      // add: end addr in MM
                    dst = pe_base + P2_VK_OFF;           // si: SPM dst
                }
                // Peel (tile_n%4 remainder)
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[pe] & 3;                // andi: n%4
                    //NOP
                m14_a_peel:
                    if (gr[13] <= 0) goto m14_a_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    spm[dst] = mm[src]; spm[dst+1] = mm[src+1]; // mvd MM→SPM
                    src += 2; dst += 2;                  // addi
                    goto m14_a_peel;
                m14_a_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23];
            m14_a_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m14_a_sp_pe1;
                mvdq_copy(&spm[gr[3]], &mm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m14_a_sp_pe1:
                if (gr[5] >= gr[7]) goto m14_a_sp_pe2;
                mvdq_copy(&spm[gr[6]], &mm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m14_a_sp_pe2:
                if (gr[8] >= gr[10]) goto m14_a_sp_pe3;
                mvdq_copy(&spm[gr[9]], &mm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m14_a_sp_pe3:
                if (gr[11] >= gr[17]) goto m14_a_sp_check;
                mvdq_copy(&spm[gr[16]], &mm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m14_a_sp_check:
                if (gr[13] != 0) goto m14_a_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;          // min_iters
            m14_a_main:
                if (gr[13] <= 0) goto m14_a_done; gr[13] -= 1; // bgt; subi (paired)
                mvdq_copy(&spm[gr[3]], &mm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&spm[gr[6]], &mm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&spm[gr[9]], &mm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&spm[gr[16]], &mm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m14_a_main;
            m14_a_done:
                goto m14_a_end;

            m14_a_wrap: {
                // Wrap (rare): per-PE copy with queue boundary split
                constexpr int A_Q = A_MASK_VAL + 1;
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    int tn = s1c[pe];
                    if (tn <= 0) continue;
                    int si = s1c[4 + pe] & A_MASK_VAL;
                    int sd = pe_base + P2_VK_OFF;
                    if (si + tn > A_Q) {
                        int c1 = A_Q - si;
                        // Segment 1: start_idx to end of queue
                        mvdq_copy(&spm[sd], &mm[gr[21] + 2*si], 2*c1);
                        // Segment 2: queue start to remaining
                        mvdq_copy(&spm[sd + 2*c1], &mm[gr[21]], 2*(tn - c1));
                    } else {
                        mvdq_copy(&spm[sd], &mm[gr[21] + 2*si], 2*tn);
                    }
                }
            }
            m14_a_end:
                (void)0;
            }
            // Restore max_tile_n for Phase B
            gr[10] = s1c[8];                             // mv S1c→gr
            //NOP
            // waitLSQ: barrier instruction needed here in ISA

            // Phase B: S2 → SPM (ts_off/vl), pe interleaved.
            // Load v from vd in SPM (safe after barrier), then write S2 → SPM directly.
            gr[8] = gr[29] & 0xFFFF;                     // andi: seq_off_s2
            gr[9] = (unsigned)gr[29] >> 16;              // shifti_r: seq_len_s2
            gr[11] = 0;                                  // si: spm offset
            gr[1] = 0;                                   // si: i
        m14_b_outer:
            if (gr[1] >= gr[10]) goto m14_b_done;        // bge
            //NOP
            for (int pe = 0; pe < 4; pe++) {
                int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                gr[13] = s1c[pe];                        // mv: tile_n[pe]
                //NOP
                if (gr[1] >= gr[13]) goto m14_b_skip; gr[7] = spm[pe_base + P2_VK_OFF + gr[11]]; // bge; mv (paired)
                //NOP; //NOP
                gr[7] = (unsigned)gr[7] >> 16;           // shifti_r: v
                //NOP
                gr[3] = gr[8] + gr[7];                   // add: seq_off_s2 + v
                gr[4] = gr[9] + gr[7];                   // add: seq_len_s2 + v
                // Write directly S2 → SPM (no gr intermediate; avoids S2 latency hazard)
                spm[pe_base + P2_TS_OFF + gr[11]] = s2->buffer[gr[3]];         // mv S2→SPM (ts_off)
                spm[pe_base + P2_TS_OFF + gr[11] + 1] = s2->buffer[gr[4]];     // mv S2→SPM (vl)
            m14_b_skip:
                (void)0;
            }
            gr[11] = gr[11] + 2;                         // addi: spm offset += 2
            gr[1] = gr[1] + 1;                           // addi: i++
            goto m14_b_outer;
        m14_b_done: {
            // waitLSQ: barrier instruction needed here in ISA
        }

            // Write tile_n metadata and compute gr[2] = total > 0 flag
            gr[2] = 0;                                   // si
            for (int pe = 0; pe < 4; pe++) {
                int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                gr[13] = s1c[pe];                        // mv: tile_n[pe]
                //NOP
                spm[pe_base + P2_META_OFF + P2_M_TILE_N] = gr[13]; // mv gr→SPM
                gr[2] = gr[2] + gr[13];                  // add: total
            }
            if (gr[2] > 0) gr[2] = 1;                   // bgt; si
        } else if (magic_id == 15) {
            // Phase 2 tile writeback — ISA-like register-mapped code.
            // Processes PE output: pushed diags, intervals, fin0, fin1.
            constexpr int P2_PUSHED_OFF = 256;
            constexpr int P2_INTV_OFF   = 640;
            constexpr int P2_FIN0_OFF   = 768;
            constexpr int P2_FIN1_OFF   = 896;
            constexpr int P2_META_OFF   = 1024;
            constexpr int P2_M_PUSHED = 0, P2_M_INTV = 1;
            constexpr int P2_M_FIN0 = 2, P2_M_FIN1 = 3;
            constexpr int A_MASK_VAL = (16 << 20) - 1;
            constexpr int ARC_META_BASE = 544;
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int *spm = SPM_unit->buffer;
            int p2_base = (magic_mask & 1) ? GWFA_P2B_BASE : GWFA_P2_BASE;

            // === Section 1: Pushed diags SPM → MM (hoisted peel + mvdq) ===
            // PE alloc: PE0=gr[1,3,4] PE1=gr[5,6,7] PE2=gr[8,9,10]
            //           PE3=gr[11,16,17]  gr[13]=peel/flag
            {
                // Read n_pushed per PE from SPM → s1c[0..3]
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    gr[13] = spm[pe_base + P2_META_OFF + P2_M_PUSHED];
                    //NOP; //NOP
                    s1c[pe] = gr[13];                    // mv
                }
                // Cumulative B destinations → s1c[16..19]
                gr[7] = gr[20] + gr[24];                 // add
                gr[7] = gr[7] + gr[24];                  // add (base+2*B_n)
                s1c[16] = gr[7];                         // mv
                for (int pe = 1; pe < 4; pe++) {
                    gr[8] = s1c[pe - 1];                 // mv
                    //NOP
                    gr[8] = gr[8] + gr[8];               // add: 2*n_pushed
                    gr[7] = gr[7] + gr[8];               // add
                    s1c[16 + pe] = gr[7];                // mv
                }
                // Setup per-PE src, dst, end
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    gr[13] = s1c[pe];                    // mv: n_pushed
                    //NOP
                    src = pe_base + P2_PUSHED_OFF;       // si: src
                    end = gr[13] + gr[13];               // add: 2*n
                    //NOP
                    end = src + end;                      // add: end
                    dst = s1c[16 + pe];                  // mv: dst
                }
                // Peel
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[pe] & 3;                // andi: n%4
                    //NOP
                m15_p_peel:
                    if (gr[13] <= 0) goto m15_p_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    mm[dst] = spm[src]; mm[dst+1] = spm[src+1];
                    src += 2; dst += 2;                  // addi
                    goto m15_p_peel;
                m15_p_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main unmasked loop
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3 → gr[23]=min_words
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23]; // adjust ends
            m15_p_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m15_p_sp_pe1;
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m15_p_sp_pe1:
                if (gr[5] >= gr[7]) goto m15_p_sp_pe2;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m15_p_sp_pe2:
                if (gr[8] >= gr[10]) goto m15_p_sp_pe3;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m15_p_sp_pe3:
                if (gr[11] >= gr[17]) goto m15_p_sp_check;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m15_p_sp_check:
                if (gr[13] != 0) goto m15_p_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;                // min_iters = min_words/8
            m15_p_main_outer:
                if (gr[13] <= 0) goto m15_p_done; gr[13] -= 1; // bgt; subi (paired)
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m15_p_main_outer;
            m15_p_done:
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[pe];                     // mv
                    //NOP
                    gr[24] = gr[24] + gr[7];             // add (B_n+=)
                }
            }

            // === Section 2: Intervals SPM → MM (hoisted peel + mvdq) ===
            {
                // Read n_intv per PE from SPM → s1c[4..7]
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    gr[13] = spm[pe_base + P2_META_OFF + P2_M_INTV];
                    //NOP; //NOP
                    s1c[4 + pe] = gr[13];                // mv
                }
                // Cumulative intv destinations → s1c[20..23]
                gr[7] = gr[22] + gr[28];                 // add
                gr[7] = gr[7] + gr[28];                  // add (base+2*n)
                s1c[20] = gr[7];                         // mv
                for (int pe = 1; pe < 4; pe++) {
                    gr[8] = s1c[4 + pe - 1];             // mv
                    //NOP
                    gr[8] = gr[8] + gr[8];               // add: 2*n_intv
                    gr[7] = gr[7] + gr[8];               // add
                    s1c[20 + pe] = gr[7];                // mv
                }
                // Setup per-PE src, dst, end
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    gr[13] = s1c[4 + pe];                // mv: n_intv
                    //NOP
                    src = pe_base + P2_INTV_OFF;         // si: src
                    end = gr[13] + gr[13];               // add: 2*n
                    //NOP
                    end = src + end;                      // add: end
                    dst = s1c[20 + pe];                  // mv: dst
                }
                // Peel
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[4 + pe] & 3;            // andi: n%4
                    //NOP
                m15_i_peel:
                    if (gr[13] <= 0) goto m15_i_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    mm[dst] = spm[src]; mm[dst+1] = spm[src+1];
                    src += 2; dst += 2;                  // addi
                    goto m15_i_peel;
                m15_i_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main unmasked loop
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3 → gr[23]=min_words
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23]; // adjust ends
            m15_i_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m15_i_sp_pe1;
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m15_i_sp_pe1:
                if (gr[5] >= gr[7]) goto m15_i_sp_pe2;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m15_i_sp_pe2:
                if (gr[8] >= gr[10]) goto m15_i_sp_pe3;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m15_i_sp_pe3:
                if (gr[11] >= gr[17]) goto m15_i_sp_check;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m15_i_sp_check:
                if (gr[13] != 0) goto m15_i_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;                // min_iters = min_words/8
            m15_i_main_outer:
                if (gr[13] <= 0) goto m15_i_done; gr[13] -= 1; // bgt; subi (paired)
                mvdq_copy(&mm[gr[3]], &spm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&mm[gr[6]], &spm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&mm[gr[9]], &spm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&mm[gr[16]], &spm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m15_i_main_outer;
            m15_i_done:
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[4 + pe];                 // mv
                    //NOP
                    gr[28] = gr[28] + gr[7];             // add (intv_n+=)
                }
            }

            // === Section 3: Load fin0+fin1 from PE SPM → S1c ===
            // Layout: all PE fin0 first, then all PE fin1
            // s1c[20]=total_fin0, s1c[21]=total_diags
            {
                // Read n_fin0, n_fin1 from SPM → s1c[8..15]
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    gr[14] = spm[pe_base + P2_META_OFF + P2_M_FIN0];
                    gr[13] = spm[pe_base + P2_META_OFF + P2_M_FIN1];
                    //NOP; //NOP
                    s1c[8 + pe] = gr[14];                // n_fin0
                    s1c[12 + pe] = gr[13];               // n_fin1
                }
                // Setup per-PE src, dst, end for fin0 copy (SPM → S1c)
                // gr[14] = running cumulative S1c destination
                gr[14] = 32;                             // si: base
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    gr[13] = s1c[8 + pe];                // n_fin0
                    //NOP
                    src = pe_base + P2_FIN0_OFF;         // SPM src
                    end = gr[13] + gr[13];               // 2*n
                    //NOP
                    end = src + end;                      // end
                    dst = gr[14];                         // S1c dst
                    gr[13] = s1c[8 + pe];                // re-read n_fin0
                    gr[13] = gr[13] + gr[13];            // 2*n_fin0
                    gr[14] = gr[14] + gr[13];            // advance dst base
                }
                // Peel fin0
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[8 + pe] & 3;            // andi
                    //NOP
                m15_f0_peel:
                    if (gr[13] <= 0) goto m15_f0_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    s1c[dst] = spm[src]; s1c[dst+1] = spm[src+1]; // mvd
                    src += 2; dst += 2;                  // addi
                    goto m15_f0_peel;
                m15_f0_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main unmasked loop
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3 → gr[23]=min_words
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23]; // adjust ends
            m15_f0_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m15_f0_sp_pe1;
                mvdq_copy(&s1c[gr[3]], &spm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m15_f0_sp_pe1:
                if (gr[5] >= gr[7]) goto m15_f0_sp_pe2;
                mvdq_copy(&s1c[gr[6]], &spm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m15_f0_sp_pe2:
                if (gr[8] >= gr[10]) goto m15_f0_sp_pe3;
                mvdq_copy(&s1c[gr[9]], &spm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m15_f0_sp_pe3:
                if (gr[11] >= gr[17]) goto m15_f0_sp_check;
                mvdq_copy(&s1c[gr[16]], &spm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m15_f0_sp_check:
                if (gr[13] != 0) goto m15_f0_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;                // min_iters = min_words/8
            m15_f0_main_outer:
                if (gr[13] <= 0) goto m15_f0_done; gr[13] -= 1; // bgt; subi (paired)
                mvdq_copy(&s1c[gr[3]], &spm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&s1c[gr[6]], &spm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&s1c[gr[9]], &spm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&s1c[gr[16]], &spm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m15_f0_main_outer;
            m15_f0_done:
                // Compute total_fin0 → s1c[20]
                gr[7] = 0;                                // si
                for (int pe = 0; pe < 4; pe++) {
                    gr[8] = s1c[8 + pe];                  // n_fin0
                    //NOP
                    gr[7] = gr[7] + gr[8];                // add
                }
                s1c[20] = gr[7];                          // total_fin0
                // Setup for fin1 copy (SPM → S1c)
                // gr[14] = running cumulative S1c destination for fin1
                gr[14] = gr[7] + gr[7];                  // 2*total_fin0
                //NOP
                gr[14] = gr[14] + 32;                    // fin1 s1c base
                for (int pe = 0; pe < 4; pe++) {
                    int pe_base = pe * SPM_BANK_GROUP_SIZE + p2_base;
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    int &end = (pe==0)?gr[4]:(pe==1)?gr[7]:(pe==2)?gr[10]:gr[17];
                    gr[13] = s1c[12 + pe];                // n_fin1
                    //NOP
                    src = pe_base + P2_FIN1_OFF;          // SPM src
                    end = gr[13] + gr[13];                // 2*n
                    //NOP
                    end = src + end;                       // end
                    dst = gr[14];                          // S1c dst
                    gr[13] = s1c[12 + pe];                // re-read n_fin1
                    gr[13] = gr[13] + gr[13];             // 2*n_fin1
                    gr[14] = gr[14] + gr[13];             // advance dst base
                }
                // Peel fin1
                for (int pe = 0; pe < 4; pe++) {
                    int &src = (pe==0)?gr[1]:(pe==1)?gr[5]:(pe==2)?gr[8]:gr[11];
                    int &dst = (pe==0)?gr[3]:(pe==1)?gr[6]:(pe==2)?gr[9]:gr[16];
                    gr[13] = s1c[12 + pe] & 3;            // andi
                    //NOP
                m15_f1_peel:
                    if (gr[13] <= 0) goto m15_f1_peel_done; gr[13] -= 1; // bgt; subi (paired)
                    s1c[dst] = spm[src]; s1c[dst+1] = spm[src+1]; // mvd
                    src += 2; dst += 2;                  // addi
                    goto m15_f1_peel;
                m15_f1_peel_done:
                    (void)0;
                }
                // Second peel: equalize PE counts; then main unmasked loop
                gr[23] = gr[4] - gr[1];                        // PE0 remaining
                gr[13] = gr[7] - gr[5];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE1
                gr[13] = gr[10] - gr[8];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE2
                gr[13] = gr[17] - gr[11];
                if (gr[13] < gr[23]) gr[23] = gr[13];          // min with PE3 → gr[23]=min_words
                gr[4] -= gr[23]; gr[7] -= gr[23]; gr[10] -= gr[23]; gr[17] -= gr[23]; // adjust ends
            m15_f1_sp_outer:
                gr[13] = 0;
                if (gr[1] >= gr[4]) goto m15_f1_sp_pe1;
                mvdq_copy(&s1c[gr[3]], &spm[gr[1]], 8);
                gr[1] += 8; gr[3] += 8; gr[13] = 1;
            m15_f1_sp_pe1:
                if (gr[5] >= gr[7]) goto m15_f1_sp_pe2;
                mvdq_copy(&s1c[gr[6]], &spm[gr[5]], 8);
                gr[5] += 8; gr[6] += 8; gr[13] = 1;
            m15_f1_sp_pe2:
                if (gr[8] >= gr[10]) goto m15_f1_sp_pe3;
                mvdq_copy(&s1c[gr[9]], &spm[gr[8]], 8);
                gr[8] += 8; gr[9] += 8; gr[13] = 1;
            m15_f1_sp_pe3:
                if (gr[11] >= gr[17]) goto m15_f1_sp_check;
                mvdq_copy(&s1c[gr[16]], &spm[gr[11]], 8);
                gr[11] += 8; gr[16] += 8; gr[13] = 1;
            m15_f1_sp_check:
                if (gr[13] != 0) goto m15_f1_sp_outer;
                gr[13] = (unsigned)gr[23] >> 3;                // min_iters = min_words/8
            m15_f1_main_outer:
                if (gr[13] <= 0) goto m15_f1_done; gr[13] -= 1; // bgt; subi (paired)
                mvdq_copy(&s1c[gr[3]], &spm[gr[1]], 8); gr[1] += 8; gr[3] += 8;
                mvdq_copy(&s1c[gr[6]], &spm[gr[5]], 8); gr[5] += 8; gr[6] += 8;
                mvdq_copy(&s1c[gr[9]], &spm[gr[8]], 8); gr[8] += 8; gr[9] += 8;
                mvdq_copy(&s1c[gr[16]], &spm[gr[11]], 8); gr[11] += 8; gr[16] += 8;
                goto m15_f1_main_outer;
            m15_f1_done:
                // Compute total_diags → s1c[21]
                gr[7] = s1c[20];                          // total_fin0
                //NOP
                for (int pe = 0; pe < 4; pe++) {
                    gr[8] = s1c[12 + pe];                 // n_fin1
                    //NOP
                    gr[7] = gr[7] + gr[8];
                }
                s1c[21] = gr[7];                          // total_diags

                // --- Non-ISA performance counter: duplicate fin0 diags ---
                {
                    int tf = s1c[20];
                    for (int i = 0; i < tf; i++)
                        for (int j = i + 1; j < tf; j++)
                            if (s1c[32+2*i] == s1c[32+2*j] &&
                                s1c[32+2*i+1] == s1c[32+2*j+1])
                                fin0DupDiags++;
                }
                // --- End non-ISA performance counter ---

                // === Section 4: Prefetch arc_off pairs S2 → S1c ===
                // s1c[ARC_META+2*d]=arc_off[v], s1c[ARC_META+2*d+1]=arc_off[v+1]
                gr[13] = (unsigned)gr[18] >> 16;          // shifti_r: arc_off_s2
                gr[1] = 32;                               // si: data ptr
                gr[3] = ARC_META_BASE;                    // si: arc_meta ptr
                gr[14] = s1c[21];                         // total_diags
                gr[14] = gr[14] + gr[14];                 // 2*total_diags
                //NOP
                gr[14] = gr[14] + 32;                     // end ptr
                //NOP
            m15_s4_loop:
                if (gr[1] >= gr[14]) goto m15_s4_done; gr[7] = s1c[gr[1]]; // bge; mv (paired)
                //NOP
                gr[7] = (unsigned)gr[7] >> 16;            // shifti_r: v
                //NOP
                // Write directly S2→S1c (no gr intermediate; avoids S2 latency hazard)
                s1c[gr[3]] = s2->buffer[gr[13] + gr[7]];       // mv S2→S1c: arc_off[v]
                s1c[gr[3]+1] = s2->buffer[gr[13] + gr[7] + 1]; // mv S2→S1c: arc_off[v+1]
                gr[1] = gr[1] + 2;                        // addi
                gr[3] = gr[3] + 2;                        // addi
                goto m15_s4_loop;                          // jump
            m15_s4_done:

                // === Section 5: Block load arcs S2→S1c, process fin1 ===
                // Step 1: Load arcs for all diags into S1c
                gr[1] = ARC_META_BASE;                    // arc_meta read ptr
                gr[7] = s1c[21];                          // total_diags
                //NOP
                gr[14] = gr[7] + gr[7];                   // 2*total_diags
                //NOP
                gr[3] = gr[14] + ARC_META_BASE;           // arc data write ptr
                gr[14] = gr[14] + ARC_META_BASE;          // arc_meta end ptr
                //NOP
            m15_s5_load:
                if (gr[1] >= gr[14]) goto m15_s5_load_done; gr[7] = s1c[gr[1]]; // bge; mv (paired)
                gr[8] = s1c[gr[1]+1];                     // hi = arc_off[v+1]
                //NOP
                gr[9] = gr[8] - gr[7];                    // n_arcs
                gr[10] = gr[7] + gr[7];                   // 2*lo
                //NOP
                gr[10] = gr[10] + gr[30];                 // S2 src base
                gr[11] = 0;                               // arc counter
                //NOP
            m15_s5_arc:
                gr[4] = gr[11] + gr[11];                  // add: 2*a (slot 1 of branch cycle)
                if (gr[11] >= gr[9]) goto m15_s5_arc_done; // bge (slot 0, paired with add)
                //NOP
                s1c[gr[3]] = s2->buffer[gr[10] + gr[4]];          // mvd S2→S1c
                s1c[gr[3]+1] = s2->buffer[gr[10] + gr[4] + 1];
                gr[3] = gr[3] + 2;                        // addi
                gr[11] = gr[11] + 1;                      // addi
                goto m15_s5_arc;
            m15_s5_arc_done:
                gr[1] = gr[1] + 2;                        // next arc_meta
                goto m15_s5_load;
            m15_s5_load_done:

                // Step 2: Process fin1 diags — push arcs to B
                // Skip fin0 arcs to find fin1 arc data start
                gr[1] = ARC_META_BASE;                    // arc_meta ptr
                gr[7] = s1c[20];                          // total_fin0
                //NOP
                gr[14] = gr[7] + gr[7];                   // 2*total_fin0
                //NOP
                gr[14] = gr[14] + ARC_META_BASE;          // fin0 arc_meta end
                gr[7] = s1c[21];                          // total_diags
                //NOP
                gr[11] = gr[7] + gr[7];                   // 2*total_diags
                //NOP
                gr[11] = gr[11] + ARC_META_BASE;          // total arc_meta end
                // Arc data read ptr = arc_data_start
                gr[7] = s1c[21];                          // total_diags
                //NOP
                gr[3] = gr[7] + gr[7];                    // 2*total_diags
                //NOP
                gr[3] = gr[3] + ARC_META_BASE;            // arc data base
                // Skip fin0 arcs
            m15_s5_skip:
                if (gr[1] >= gr[14]) goto m15_s5_skip_done; gr[7] = s1c[gr[1]]; // bge; mv (paired)
                gr[8] = s1c[gr[1]+1];                     // hi
                //NOP
                gr[9] = gr[8] - gr[7];                    // n_arcs
                gr[9] = gr[9] + gr[9];                    // 2*n_arcs words
                //NOP
                gr[3] = gr[3] + gr[9];                    // advance read ptr
                gr[1] = gr[1] + 2;                        // next arc_meta
                goto m15_s5_skip;
            m15_s5_skip_done:
                // gr[1]=first fin1 arc_meta, gr[3]=first fin1 arc data
                // Fin1 diag data pointer
                gr[4] = s1c[20];                          // total_fin0
                //NOP
                gr[4] = gr[4] + gr[4];                    // 2*total_fin0
                //NOP
                gr[4] = gr[4] + 32;                       // fin1 data ptr
                //NOP
            m15_s5_fin1:
                if (gr[1] >= gr[11]) goto m15_s5_fin1_done;
                //NOP
                gr[5] = s1c[gr[4]];                       // vd
                gr[6] = s1c[gr[4]+1];                     // k
                //NOP
                gr[7] = gr[5] & 0xFFFF;                   // andi: vd.lo
                //NOP
                gr[7] = gr[7] - GWF_DIAG_SHIFT;           // subi: d_val
                gr[7] = gr[7] + gr[6];                    // add: i_val
                // Arc count for this diag
                gr[8] = s1c[gr[1]];                       // lo
                gr[9] = s1c[gr[1]+1];                     // hi
                //NOP
                gr[10] = gr[9] - gr[8];                   // n_arcs
                gr[14] = 0;                               // arc counter
                //NOP
            m15_s5_fin1_arc:
                if (gr[14] >= gr[10]) goto m15_s5_fin1_arc_done;
                //NOP
                {
                    // Read arc from S1c (block-loaded)
                    uint32_t w = (uint32_t)s1c[gr[3]] >> 16;
                    int ow = s1c[gr[3]+1];
                    int32_t new_d = gr[7] - ow;
                    uint32_t new_vd = (w << 16)
                        | ((GWF_DIAG_SHIFT + new_d) & 0xFFFF);
                    gr[5] = gr[20] + gr[24];
                    gr[5] = gr[5] + gr[24];               // B_base + 2*B_n
                    //NOP
                    mm[gr[5]] = (int)new_vd;
                    mm[gr[5] + 1] = ow;
                    gr[24] = gr[24] + 1;                  // B_n++
                }
                gr[3] = gr[3] + 2;                        // next arc
                gr[14] = gr[14] + 1;                      // addi
                goto m15_s5_fin1_arc;
            m15_s5_fin1_arc_done:
                gr[1] = gr[1] + 2;                        // next arc_meta
                gr[4] = gr[4] + 2;                        // next diag data
                goto m15_s5_fin1;
            m15_s5_fin1_done:
                (void)0;

                // === Section 6 (15a): Init + load first FIN0 batch ===
                // Multi-pass state: s1c[22]=cursor, s1c[23]=arc_ptr.
                // gr[2] = 1 if more passes needed, 0 if done.
                {
                    int fin0_base = (magic_mask & 2)
                        ? GWFA_FIN0B_BASE : GWFA_FIN0_BASE;
                    s1c[22] = 0;
                    s1c[23] = 0;
                    fin0_load_batch(fin0_base, magic_mask);
                }
            }

            // === Section 7: Counter sync ===
            gwfa_sync_counters(gr[24], (uint32_t)gr[25],
                (uint32_t)gr[26], (uint32_t)gr[27], gr[28]);
            gwfa_set_ha_n_dirty((uint32_t)gr[31]);
        } else if (magic_id == 20) {
            // Magic 20: FIN0 subsequent batch load (15a-only).
            // Resumes multi-pass state from s1c, loads next batch.
            // gr[2] = 1 if more passes needed, 0 if done.
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int fin0_base = (magic_mask & 2)
                ? GWFA_FIN0B_BASE : GWFA_FIN0_BASE;
            fin0_load_batch(fin0_base, magic_mask);
        } else if (magic_id == 18) {
            // Magic 18: FIN0 writeback — read PE output from
            // FIN_0_TILE, write A/B queues and HA buckets to MM.
            // Element-outer, PE-inner pattern.
            constexpr int A_MASK_VAL = (16 << 20) - 1;
            constexpr int DIAG_CAP_18 = (16 << 20);
            constexpr int INTV_CAP_18 = (1 << 21);
            constexpr int HA_CAP_18 = (4 << 20);
            constexpr int ha_off = DIAG_CAP_18 * 8 + INTV_CAP_18 * 6;
            constexpr int ha_dirty_off = ha_off + HA_CAP_18;
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            int *spm = SPM_unit->buffer;
            int fin0_base = (magic_mask & 2)
                ? GWFA_FIN0B_BASE : GWFA_FIN0_BASE;

            // --- Phase 1: Read metadata from all 4 PEs ---
            // ISA lowering: each SPM meta read stages through gr[11]
            // with 3 //NOPs before the s1c store (AC-7 rule 6:
            // SPM 2-cycle = 4 ISA lines between load and consumer).
            for (int pe = 0; pe < 4; pe++) {
                gr[7] = pe * SPM_BANK_GROUP_SIZE + fin0_base; // si
                s1c[12 + pe] = gr[7];                    // mv: pe_spm_base
                //NOP; //NOP
                gr[11] = spm[gr[7] + FIN0_META + 2];    // SPM load n_A
                //NOP                                    // SPM lat 1/3
                //NOP                                    // SPM lat 2/3
                //NOP                                    // SPM lat 3/3
                s1c[pe] = gr[11];                        // mv
                gr[11] = spm[gr[7] + FIN0_META + 3];    // SPM load n_B
                //NOP; //NOP; //NOP                      // SPM settle
                s1c[4 + pe] = gr[11];                    // mv
                gr[11] = spm[gr[7] + FIN0_META + 4];    // SPM load n_HA
                //NOP; //NOP; //NOP                      // SPM settle
                s1c[8 + pe] = gr[11];                    // mv
            }

            // --- Phase 2: A writeback SPM → MM (circular A queue) ---
            {
                gr[5] = 0;                                // si: max_nA
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[pe];                      // mv: n_A
                    //NOP
                    if (gr[7] > gr[5]) gr[5] = gr[7];    // max
                }
                // Per-PE forward src ptrs → s1c[16..19]
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[12 + pe];                 // mv: pe_spm
                    //NOP
                    s1c[16 + pe] = gr[7] + FIN0_OUT;      // addi: src
                }
                gr[11] = 0;                               // si: i
                //NOP
            m18_a_outer:
                if (gr[11] >= gr[5]) goto m18_a_done;     // bge
                //NOP
                for (int pe = 0; pe < 4; pe++) {
                    gr[10] = s1c[pe];                     // mv: n_A[pe]
                    //NOP
                    if (gr[11] >= gr[10]) continue;        // bge: skip
                    gr[7] = s1c[16 + pe];                 // mv: src
                    //NOP
                    gr[9] = spm[gr[7]];                   // mv: vd
                    gr[1] = spm[gr[7]+1];                 // mv: ow
                    gr[3] = gr[26] & A_MASK_VAL;          // andi: masked tail
                    //NOP
                    gr[3] = gr[3] + gr[3];                // add: 2*idx
                    gr[3] = gr[3] + gr[21];               // add: + A_base
                    //NOP
                    mm[gr[3]] = gr[9];                    // mv: vd → MM
                    mm[gr[3]+1] = gr[1];                  // mv: ow → MM
                    gr[26] = gr[26] + 1;                  // addi: A_tail++
                    gr[27] = gr[27] + 1;                  // addi: A_count++
                    gr[7] = gr[7] + 2;                    // addi: src+=2
                    s1c[16 + pe] = gr[7];                 // mv: update src
                }
                gr[11] = gr[11] + 1;                      // addi
                goto m18_a_outer;
            m18_a_done:
                (void)0;
            }

            // --- Phase 3: B writeback SPM → MM (backward read) ---
            {
                gr[5] = 0;                                // si: max_nB
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[4 + pe];                  // mv: n_B
                    //NOP
                    if (gr[7] > gr[5]) gr[5] = gr[7];    // max
                }
                // Per-PE backward src ptrs → s1c[16..19]
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[12 + pe];                 // mv: pe_spm
                    //NOP
                    s1c[16 + pe] = gr[7] + (FIN0_OUT + FIN0_OUT_SIZE - 2);
                }
                gr[11] = 0;                               // si: i
                //NOP
            m18_b_outer:
                if (gr[11] >= gr[5]) goto m18_b_done;     // bge
                //NOP
                for (int pe = 0; pe < 4; pe++) {
                    gr[10] = s1c[4 + pe];                 // mv: n_B[pe]
                    //NOP
                    if (gr[11] >= gr[10]) continue;        // bge: skip
                    gr[7] = s1c[16 + pe];                 // mv: src
                    //NOP
                    gr[9] = spm[gr[7]];                   // mv: vd
                    gr[1] = spm[gr[7]+1];                 // mv: k_or_ow
                    gr[3] = gr[20] + gr[24];              // add
                    gr[3] = gr[3] + gr[24];               // add: B_base+2*B_n
                    //NOP
                    mm[gr[3]] = gr[9];                    // mv: vd → MM
                    mm[gr[3]+1] = gr[1];                  // mv: k_or_ow → MM
                    gr[24] = gr[24] + 1;                  // addi: B_n++
                    gr[7] = gr[7] - 2;                    // subi: backward
                    s1c[16 + pe] = gr[7];                 // mv: update src
                }
                gr[11] = gr[11] + 1;                      // addi
                goto m18_b_outer;
            m18_b_done:
                (void)0;
            }
            // --- Phase 4: HA writeback SPM → MM (conditional dirty) ---
            {
                gr[5] = 0;                                // si: max_nHA
                for (int pe = 0; pe < 4; pe++) {
                    gr[7] = s1c[8 + pe];                  // mv: n_HA
                    //NOP
                    if (gr[7] > gr[5]) gr[5] = gr[7];    // max
                }
                gr[11] = 0;                               // si: i
                //NOP
            m18_ha_outer:
                if (gr[11] >= gr[5]) goto m18_ha_done;    // bge
                //NOP
                for (int pe = 0; pe < 4; pe++) {
                    gr[10] = s1c[8 + pe];                 // mv: n_HA[pe]
                    //NOP
                    if (gr[11] >= gr[10]) continue;        // bge: skip
                    gr[7] = s1c[12 + pe];                 // mv: pe_spm
                    gr[8] = gr[11] + gr[11];              // add: 2*i
                    //NOP
                    gr[9] = spm[gr[7] + FIN0_OUT_HA + gr[8]];     // mv: arc_idx
                    gr[1] = spm[gr[7] + FIN0_OUT_HA + gr[8] + 1]; // mv: b_raw
                    //NOP
                    gr[3] = gr[1] & 0xFFFFF;              // andi: bucket idx
                    gr[4] = gr[1] & (1 << 20);            // andi: new_bucket
                    // HA SPM addr: pe_spm + FIN0_HA + 4*arc_idx
                    gr[8] = gr[9] + gr[9];                // add: 2*arc_idx
                    gr[8] = gr[8] + gr[8];                // add: 4*arc_idx
                    //NOP
                    gr[8] = gr[7] + FIN0_HA + gr[8];      // add: ha_spm
                    // MM dest: ha_off + b*4
                    gr[9] = gr[3] + gr[3];                // add: 2*b
                    gr[9] = gr[9] + gr[9];                // add: 4*b
                    //NOP
                    gr[9] = gr[9] + ha_off;               // add: mm_dst
                    //NOP
                    mm[gr[9]]   = spm[gr[8]];             // mvd: bucket → MM
                    mm[gr[9]+1] = spm[gr[8]+1];
                    mm[gr[9]+2] = spm[gr[8]+2];
                    mm[gr[9]+3] = spm[gr[8]+3];
                    if (gr[4] == 0) continue;              // beq: skip dirty
                    mm[ha_dirty_off + gr[31]] = gr[3];    // mv: record bucket
                    gr[31] = gr[31] + 1;                  // addi: dirty_n++
                }
                gr[11] = gr[11] + 1;                      // addi
                goto m18_ha_outer;
            m18_ha_done:
                (void)0;
            }

            // --- Phase 5: Clear output metadata ---
            for (int pe = 0; pe < 4; pe++) {
                gr[7] = s1c[12 + pe];                     // mv: pe_spm
                //NOP
                spm[gr[7] + FIN0_META + 2] = 0;          // si: n_A=0
                spm[gr[7] + FIN0_META + 3] = 0;          // si: n_B=0
                spm[gr[7] + FIN0_META + 4] = 0;          // si: n_HA=0
            }

            // Counter sync
            gwfa_sync_counters(gr[24], (uint32_t)gr[25],
                (uint32_t)gr[26], (uint32_t)gr[27], gr[28]);
            gwfa_set_ha_n_dirty((uint32_t)gr[31]);
        } else if (magic_id == 16) {
            // Sync counters, save state, setup DIAG sort (DIAG-first order).
            auto &gr = main_addressing_register;
            gwfa_sync_counters(gr[24], (uint32_t)gr[25],
                (uint32_t)gr[26], (uint32_t)gr[27], gr[28]);
            int *mm = gwfa_get_mm();
            constexpr int DIAG_CAP_V  = (16 << 20);
            constexpr int INTV_CAP_V  = (1 << 21);
            constexpr int MM_INTV     = DIAG_CAP_V * 6;
            constexpr int MM_SORT_BUF = DIAG_CAP_V * 6 + INTV_CAP_V * 6;
            // Save state for later phases
            s1c[144] = gr[20];                       // diag_base
            s1c[145] = gr[24];                       // n_a
            s1c[146] = (int)gwfa_get_intv_n();       // old intv_n
            s1c[155] = gr[28];                       // next_intv_n
            s1c[152] = MM_INTV;                      // active_intv_base
            s1c[153] = gr[20];                       // active_diag_base
            // Clamp n_phase1_v to [0, n_a] using branches
            gr[1] = s1c[151];                        // n_phase1_v
            //NOP                                    // s1c 1-cycle latency gap
            if (gr[1] >= 0) goto m16_clamp_hi;
            gr[1] = 0;
        m16_clamp_hi:
            if (gr[1] <= gr[24]) goto m16_clamped;
            gr[1] = gr[24];
        m16_clamped:
            s1c[147] = gr[1];                        // mv: n_phase1_v
            s1c[148] = gr[24];                       // mv: n_a
            gr[7]  = gr[1] + gr[1];                  // add: 2 * n_phase1
            gr[4]  = MM_SORT_BUF;                    // si (constexpr)
            //NOP
            gr[3]  = gr[20] + gr[7];                 // add: diag_base + 2*n_phase1
            gr[24] = gr[24] - gr[1];                 // sub: n_unsorted
            //NOP
            gr[6]  = gr[24] + 3;                     // addi
            //NOP
            gr[6]  = (unsigned)gr[6] >> 2;           // shifti_r (div 4)
        } else if (magic_id == 17) {
            // Set score = gr_lo[12] (current edit distance, packed)
            gwfa_set_score(
                (int16_t)(main_addressing_register[12] & 0xFFFF));
        } else if (magic_id == 34) {
            // Sort bin-count tile load: MM → SPM TILE_BUF for all 4 PEs.
            // gr[1]=pass, gr[2]=cursor, gr[3]=src MM base, gr[24]=n_a.
            // mask bit 0 = ping/pong (0=TILE_BUF0, 1=TILE_BUF1).
            // Advances gr[2] by SORT_TILE. If cursor==0, zeros bin_counts.
            // Interleaved mvdq across PEs at 4-diag (8-word) granularity.
            {
                int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int tile_buf_off = (magic_mask & 1)
                    ? SORT_TILE_BUF1 : SORT_TILE_BUF0;
                int n_a = gr[24];
                int cursor = gr[2];
                int shift = gr[1] * 4;
                int n_a_per_pe = (n_a + 3) / 4;
                bool first_tile = (cursor == 0);
                // Phase 1: compute tile_n, write metadata
                int tile_ns[4], mm_srcs[4], spm_dsts[4];
                for (int pe = 0; pe < 4; pe++) {
                    int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                    int pe_start = pe * n_a_per_pe;
                    int pe_remain = n_a_per_pe;
                    if (pe_remain > n_a - pe_start) pe_remain = n_a - pe_start;
                    int remaining = pe_remain - cursor;
                    if (remaining < 0) remaining = 0;
                    tile_ns[pe] = remaining;
                    if (tile_ns[pe] > SORT_TILE) tile_ns[pe] = SORT_TILE;
                    mm_srcs[pe] = gr[3] + (pe_start + cursor) * 2;
                    spm_dsts[pe] = pe_spm + tile_buf_off;
                    spm[pe_spm + SORT_META + 32] = tile_ns[pe];
                    spm[pe_spm + SORT_META + 33] = shift;
                    if (first_tile)
                        for (int b = 0; b < SORT_RADIX_BINS; b++)
                            spm[pe_spm + SORT_META + b] = 0;
                }
                // Phase 2: interleaved mvdq load (round-robin across PEs)
                int max_words = 0;
                for (int pe = 0; pe < 4; pe++) {
                    int w = tile_ns[pe] * 2;
                    if (w > max_words) max_words = w;
                }
                for (int j = 0; j < max_words; j += 8) {
                    for (int pe = 0; pe < 4; pe++) {
                        int words = tile_ns[pe] * 2;
                        if (j >= words) continue;
                        int n = words - j; if (n > 8) n = 8;
                        mvdq_copy(&spm[spm_dsts[pe] + j],
                                  &mm[mm_srcs[pe] + j], n);
                    }
                }
                gr[2] = cursor + SORT_TILE;
            }
        } else if (magic_id == 19) {
            // Sort prefix-sum: ISA-lowered, gr[7]-gr[10] for temp
            // (gr[1]-gr[4] are live across this magic from sort loop).
            // ISA lowering: SPM load -> 3-NOP settle -> s1c store;
            // each s1c accumulate has a //NOP 1-cycle gap between load
            // and the gr consumer.
            {
                int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
                int *spm = SPM_unit->buffer;
                // Step 1: save per-PE bin counts → s1c[16..79]
                for (int b = 0; b < SORT_RADIX_BINS; b++) {
                    for (int pe = 0; pe < 4; pe++) {
                        gr[7] = spm[pe * SPM_BANK_GROUP_SIZE + SORT_META + b];
                        //NOP                                      // SPM 1/3
                        //NOP                                      // SPM 2/3
                        //NOP                                      // SPM 3/3
                        s1c[16 + pe * SORT_RADIX_BINS + b] = gr[7];
                    }
                }
                // Step 2: global totals → s1c[0..15]
                for (int b = 0; b < SORT_RADIX_BINS; b++) {
                    gr[7] = 0;
                    for (int pe = 0; pe < 4; pe++) {
                        gr[8] = s1c[16 + pe * SORT_RADIX_BINS + b];
                        //NOP                                      // s1c 1-cycle gap
                        gr[7] = gr[7] + gr[8];
                    }
                    s1c[b] = gr[7];
                }
                // Step 3: per-PE prefix sums within each bin
                for (int b = 0; b < SORT_RADIX_BINS; b++) {
                    gr[9] = 0;                            // cumsum
                    for (int pe = 0; pe < 4; pe++) {
                        gr[7] = s1c[16 + pe * SORT_RADIX_BINS + b];
                        s1c[16 + pe * SORT_RADIX_BINS + b] = gr[9];
                        gr[9] = gr[9] + gr[7];
                    }
                }
                // Step 4: global prefix sums
                gr[10] = 0;                               // total
                for (int b = 0; b < SORT_RADIX_BINS; b++) {
                    gr[7] = s1c[b];
                    s1c[b] = gr[10];
                    gr[10] = gr[10] + gr[7];
                }
                // Step 5: zero running offsets
                for (int i = 0; i < 64; i++) s1c[80 + i] = 0;
                // Step 6: reset bin_counts (PEs inner)
                for (int b = 0; b < SORT_RADIX_BINS; b++) {
                    for (int pe = 0; pe < 4; pe++)
                        spm[pe * SPM_BANK_GROUP_SIZE + SORT_META + b] = 0;
                }
            }
        } else if (magic_id == 24) {
            // Sort scatter tile load: MM → SPM TILE_BUF.
            // Interleaved mvdq round-robin across PEs (like magic 34).
            {
                int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int tile_buf_off = (magic_mask & 1)
                    ? SORT_TILE_BUF1 : SORT_TILE_BUF0;
                int n_a = gr[24];
                int cursor = gr[2];
                int shift = gr[1] * 4;
                int n_a_per_pe = (n_a + 3) / 4;
                // Phase 1: compute tile sizes and write metadata
                int tile_ns[4], mm_srcs[4], spm_dsts[4];
                int max_words = 0;
                for (int pe = 0; pe < 4; pe++) {
                    int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                    int pe_start = pe * n_a_per_pe;
                    int pe_remain = n_a_per_pe;
                    if (pe_remain > n_a - pe_start)
                        pe_remain = n_a - pe_start;
                    int remaining = pe_remain - cursor;
                    if (remaining < 0) remaining = 0;
                    tile_ns[pe] = (remaining < SORT_TILE)
                        ? remaining : SORT_TILE;
                    mm_srcs[pe] = gr[3] + (pe_start + cursor) * 2;
                    spm_dsts[pe] = pe_spm + tile_buf_off;
                    spm[pe_spm + SORT_META + 32] = tile_ns[pe];
                    spm[pe_spm + SORT_META + 33] = shift;
                    int w = tile_ns[pe] * 2;
                    if (w > max_words) max_words = w;
                }
                // Phase 2: full-tile fast path + peeled final
                // Common case: all PEs have SORT_TILE elements (no checks)
                int full_words = SORT_TILE * 2; // full tile word count
                bool all_full = (max_words == full_words);
                if (all_full) {
                    // Fast path: no per-PE bounds check needed
                    for (int j = 0; j < full_words; j += 8)
                        for (int pe = 0; pe < 4; pe++)
                            mvdq_copy(&spm[spm_dsts[pe] + j],
                                      &mm[mm_srcs[pe] + j], 8);
                } else {
                    // Peeled: per-PE bounds checks for final iteration
                    for (int j = 0; j < max_words; j += 8) {
                        for (int pe = 0; pe < 4; pe++) {
                            int words = tile_ns[pe] * 2;
                            if (j >= words) continue;
                            int n = words - j;
                            if (n > 8) n = 8;
                            mvdq_copy(&spm[spm_dsts[pe] + j],
                                      &mm[mm_srcs[pe] + j], n);
                        }
                    }
                }
                gr[2] = cursor + SORT_TILE;
            }
        } else if (magic_id == 25) {
            // Sort scatter writeback: SPM BIN_REGIONS → MM dst.
            // Chunk outer, PE inner: true round-robin streaming.
            {
                int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int bin_spm_off = (magic_mask & 1)
                    ? SORT_BIN_SPM1 : SORT_BIN_SPM0;
                for (int b = 0; b < SORT_RADIX_BINS; b++) {
                    // Pre-compute per-PE metadata for this bin.
                    // ISA lowering: SPM meta loads stage through gr[11]
                    // with 3 //NOPs; each s1c load stages with a 1-cycle
                    // gap so the S1c consumer is separated by >= 2 ISA
                    // lines (BL-20260417-ctrl-sync-gr).
                    int ns[4], mm_dsts[4], spm_srcs[4];
                    int max_words = 0;
                    for (int pe = 0; pe < 4; pe++) {
                        int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                        gr[11] = spm[pe_spm + SORT_META + 16 + b];  // SPM
                        //NOP                                        // SPM 1/3
                        //NOP                                        // SPM 2/3
                        //NOP                                        // SPM 3/3
                        ns[pe] = gr[11];
                        spm_srcs[pe] = pe_spm + bin_spm_off
                            + b * SORT_BIN_REGION_SIZE * 2;
                        gr[11] = s1c[b];                             // s1c
                        //NOP                                        // s1c gap
                        int diag_off = gr[11];
                        gr[11] = s1c[16 + pe * SORT_RADIX_BINS + b]; // s1c
                        //NOP                                        // s1c gap
                        diag_off += gr[11];
                        gr[11] = s1c[80 + pe * SORT_RADIX_BINS + b]; // s1c
                        //NOP                                        // s1c gap
                        diag_off += gr[11];
                        mm_dsts[pe] = gr[4] + diag_off * 2;
                        int w = ns[pe] * 2;
                        if (w > max_words) max_words = w;
                    }
                    // Interleaved mvdq: chunk outer, PE inner
                    for (int j = 0; j < max_words; j += 8) {
                        for (int pe = 0; pe < 4; pe++) {
                            int words = ns[pe] * 2;
                            if (j >= words) continue;
                            int cnt = words - j;
                            if (cnt > 8) cnt = 8;
                            mvdq_copy(&mm[mm_dsts[pe] + j],
                                      &spm[spm_srcs[pe] + j], cnt);
                        }
                    }
                    // Running-offset update: s1c += ns with explicit
                    // gr[11]-staged read-modify-write (s1c gap).
                    for (int pe = 0; pe < 4; pe++) {
                        gr[11] = s1c[80 + pe * SORT_RADIX_BINS + b];
                        //NOP                                        // s1c gap
                        gr[11] = gr[11] + ns[pe];
                        s1c[80 + pe * SORT_RADIX_BINS + b] = gr[11];
                    }
                }
            }
        } else if (magic_id == 37) {
            // Intv new+old merge split + load (pointer-swap version).
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                constexpr int DIAG_CAP_V  = (16 << 20);
                constexpr int INTV_CAP_V  = (1 << 21);
                constexpr int MM_INTV     = DIAG_CAP_V * 6;
                constexpr int MM_NEXT_INTV = MM_INTV + INTV_CAP_V * 2;
                constexpr int MM_SWAP     = MM_NEXT_INTV + INTV_CAP_V * 2;
                int n_new  = gr[24];
                // R8 fix: stage s1c[146], s1c[152] through gr[11] + 1-NOP.
                gr[11] = s1c[146];
                //NOP                                    // s1c 1-cycle gap
                int intv_n = gr[11];
                int n_total = n_new + intv_n;
                gr[11] = s1c[152];
                //NOP                                    // s1c 1-cycle gap
                int active_intv = gr[11]; // current intv buffer base
                if (n_new <= 0 || intv_n <= 0) {
                    // Only one source: just point active base there
                    if (n_new > 0)
                        s1c[152] = MM_NEXT_INTV;
                    // else: active_intv stays (old intv already there)
                    gr[6] = 0; s1c[149] = -1;
                } else {
                    // Merge: inlined interleaved binary search + load
                    int out_buf = (active_intv == MM_INTV) ? MM_SWAP : MM_INTV;
                    int abase = MM_NEXT_INTV, bbase = active_intv;
                    int n_total2 = n_new + intv_n;
                    int nape = (n_total2 + 3) / 4;
                    int a_sp[5], b_sp[5];
                    a_sp[0] = 0; b_sp[0] = 0;
                    a_sp[4] = n_new; b_sp[4] = intv_n;
                    // Interleaved binary search for split points
                    int bs_lo[3], bs_hi[3], bs_tgt[3];
                    for (int p = 0; p < 3; p++) {
                        bs_tgt[p] = ((p+1)*nape < n_total2) ? (p+1)*nape : n_total2;
                        bs_lo[p] = (bs_tgt[p] - intv_n > 0) ? bs_tgt[p] - intv_n : 0;
                        bs_hi[p] = (n_new < bs_tgt[p]) ? n_new : bs_tgt[p];
                    }
                    // R4 fix: replace 'while (any) ... for p=0..2' with
                    // label/goto outer loop + macro-unrolled per-p step
                    // bodies. MM reads stage through gr[11] with
                    // // waitLSQ + //NOP separation before compare (R7).
                m37_bs_top:
                    if (bs_lo[0] >= bs_hi[0]
                        && bs_lo[1] >= bs_hi[1]
                        && bs_lo[2] >= bs_hi[2]) goto m37_bs_done;
                    // p = 0 step
                    if (bs_lo[0] < bs_hi[0]) {
                        int mid = (bs_lo[0] + bs_hi[0]) / 2;
                        int bi2 = bs_tgt[0] - mid;
                        gr[11] = (bi2 > 0) ? mm[bbase+(bi2-1)*2] : 0;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        gr[3] = gr[11];                          // stash bv
                        gr[11] = (mid < n_new) ? mm[abase+mid*2] : (int)0xFFFFFFFF;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        if (bi2 > 0 && mid < n_new
                            && (uint32_t)gr[3] > (uint32_t)gr[11])
                            bs_lo[0] = mid+1;
                        else bs_hi[0] = mid;
                    }
                    // p = 1 step
                    if (bs_lo[1] < bs_hi[1]) {
                        int mid = (bs_lo[1] + bs_hi[1]) / 2;
                        int bi2 = bs_tgt[1] - mid;
                        gr[11] = (bi2 > 0) ? mm[bbase+(bi2-1)*2] : 0;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        gr[3] = gr[11];                          // stash bv
                        gr[11] = (mid < n_new) ? mm[abase+mid*2] : (int)0xFFFFFFFF;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        if (bi2 > 0 && mid < n_new
                            && (uint32_t)gr[3] > (uint32_t)gr[11])
                            bs_lo[1] = mid+1;
                        else bs_hi[1] = mid;
                    }
                    // p = 2 step
                    if (bs_lo[2] < bs_hi[2]) {
                        int mid = (bs_lo[2] + bs_hi[2]) / 2;
                        int bi2 = bs_tgt[2] - mid;
                        gr[11] = (bi2 > 0) ? mm[bbase+(bi2-1)*2] : 0;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        gr[3] = gr[11];                          // stash bv
                        gr[11] = (mid < n_new) ? mm[abase+mid*2] : (int)0xFFFFFFFF;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        if (bi2 > 0 && mid < n_new
                            && (uint32_t)gr[3] > (uint32_t)gr[11])
                            bs_lo[2] = mid+1;
                        else bs_hi[2] = mid;
                    }
                    goto m37_bs_top;
                m37_bs_done: ;
                    for (int p = 0; p < 3; p++) {
                        a_sp[p+1] = bs_lo[p]; b_sp[p+1] = bs_tgt[p] - bs_lo[p];
                        if (a_sp[p+1] < a_sp[p]) { a_sp[p+1] = a_sp[p]; b_sp[p+1] = bs_tgt[p] - a_sp[p+1]; }
                        if (b_sp[p+1] < b_sp[p]) { b_sp[p+1] = b_sp[p]; a_sp[p+1] = bs_tgt[p] - b_sp[p+1]; }
                    }
                    // R9 fix: replace scalar per-PE MM->SPM tile loads
                    // with chunk-outer / PE-inner mvdq_copy (same pattern
                    // as m28 A_BUF0/A_BUF1/B_BUF0/B_BUF1 round-robin).
                    int max_pt = 0;
                    int a0s[4], a1s[4], b0s[4], b1s[4];
                    int a_srcs[4], b_srcs[4];
                    for (int pe = 0; pe < 4; pe++) {
                        int pa_s = a_sp[pe], pa_n = a_sp[pe+1] - pa_s;
                        int pb_s = b_sp[pe], pb_n = b_sp[pe+1] - pb_s;
                        if (pa_n < 0) pa_n = 0; if (pb_n < 0) pb_n = 0;
                        int pt = pa_n + pb_n;
                        if (pt > max_pt) max_pt = pt;
                        s1c[pe] = pt; s1c[4+pe] = 0;
                        int a0 = (pa_n < MERGE_TILE) ? pa_n : MERGE_TILE;
                        int a1 = (pa_n-a0 < MERGE_TILE) ? (pa_n-a0>0?pa_n-a0:0) : MERGE_TILE;
                        int b0 = (pb_n < MERGE_TILE) ? pb_n : MERGE_TILE;
                        int b1 = (pb_n-b0 < MERGE_TILE) ? (pb_n-b0>0?pb_n-b0:0) : MERGE_TILE;
                        s1c[8+pe] = abase + (pa_s+a0+a1)*2;
                        s1c[12+pe] = (pa_n-a0-a1 > 0) ? pa_n-a0-a1 : 0;
                        s1c[16+pe] = bbase + (pb_s+b0+b1)*2;
                        s1c[20+pe] = (pb_n-b0-b1 > 0) ? pb_n-b0-b1 : 0;
                        a0s[pe]=a0; a1s[pe]=a1; b0s[pe]=b0; b1s[pe]=b1;
                        a_srcs[pe] = abase + pa_s*2;
                        b_srcs[pe] = bbase + pb_s*2;
                        int *spm2 = &SPM_unit->buffer[pe * SPM_BANK_GROUP_SIZE];
                        spm2[MERGE_META+0]=0; spm2[MERGE_META+1]=0; spm2[MERGE_META+4]=0;
                        spm2[MERGE_META+5]=(pa_n<=a0+a1)?1:0;
                        spm2[MERGE_META+6]=(pb_n<=b0+b1)?1:0;
                        spm2[MERGE_META+7]=0; spm2[MERGE_META+8]=0;
                        spm2[MERGE_META+9]=a0; spm2[MERGE_META+10]=a1;
                        spm2[MERGE_META+11]=b0; spm2[MERGE_META+12]=b1;
                    }
                    // Chunk-outer / PE-inner mvdq for 4 tiles
                    int *spm_all = SPM_unit->buffer;
                    #define M37_MVDQ(buf_off, sizes, srcs, extra) do { \
                        int mw = 0; \
                        for (int pe = 0; pe < 4; pe++) { \
                            int w = sizes[pe]*2; if (w > mw) mw = w; } \
                        for (int j = 0; j < mw; j += 8) \
                            for (int pe = 0; pe < 4; pe++) { \
                                int w = sizes[pe]*2; \
                                if (j >= w) continue; \
                                int cnt = w-j; if (cnt > 8) cnt = 8; \
                                mvdq_copy(&spm_all[pe*SPM_BANK_GROUP_SIZE+buf_off+j], \
                                          &mm[srcs[pe]+extra+j], cnt); \
                            } \
                    } while(0)
                    M37_MVDQ(MERGE_A_BUF0, a0s, a_srcs, 0);
                    { int a1_srcs[4]; \
                      for (int pe=0; pe<4; pe++) a1_srcs[pe] = a_srcs[pe] + a0s[pe]*2; \
                      M37_MVDQ(MERGE_A_BUF1, a1s, a1_srcs, 0); }
                    M37_MVDQ(MERGE_B_BUF0, b0s, b_srcs, 0);
                    { int b1_srcs[4]; \
                      for (int pe=0; pe<4; pe++) b1_srcs[pe] = b_srcs[pe] + b0s[pe]*2; \
                      M37_MVDQ(MERGE_B_BUF1, b1s, b1_srcs, 0); }
                    #undef M37_MVDQ
                    int niter = ((max_pt+MERGE_STEP-1)/MERGE_STEP)*MERGE_STEP;
                    gr[6] = (niter == 0) ? 0 : niter;
                    gr[4] = out_buf;
                    s1c[152] = out_buf;
                    s1c[149] = 0;
                }
                s1c[148] = n_total;
                // Load boundary vd values and init PE tracking.
                // R8 fix: pre-load boundary_vd[0..2] and per-PE pt counts
                // into gr-staged C++ locals before the PE-unroll so the
                // SPM stores inside the loop read from settled locals.
                gr[11] = s1c[159];
                //NOP                                    // s1c 1-cycle gap
                int bvd0 = gr[11];
                gr[11] = s1c[160];
                //NOP                                    // s1c 1-cycle gap
                int bvd1 = gr[11];
                gr[11] = s1c[161];
                //NOP                                    // s1c 1-cycle gap
                int bvd2 = gr[11];
                int pts[4];
                for (int pe = 0; pe < 4; pe++) {
                    gr[11] = s1c[pe];
                    //NOP                                // s1c 1-cycle gap
                    pts[pe] = gr[11];
                }
                int pe_base = 0;
                for (int pe = 0; pe < 4; pe++) {
                    int *spm = &SPM_unit->buffer[pe * SPM_BANK_GROUP_SIZE];
                    spm[MERGE_META + 13] = bvd0; // boundary_vd[0]
                    spm[MERGE_META + 14] = bvd1; // boundary_vd[1]
                    spm[MERGE_META + 15] = bvd2; // boundary_vd[2]
                    for (int i = 0; i < 6; i++) spm[976+i] = -1; // hi/lo_pos
                    spm[982] = 0; // cumulative output count
                    spm[983] = pe_base; // global output base for this PE
                    pe_base += pts[pe]; // prefix sum (pre-staged)
                }
            }
        } else if (magic_id == 38) {
            // Intv merge finalize: compute intv_n, restore gr[24]=n_a,
            // compute intv boundary positions (AC-7).
            {
                int *mm = gwfa_get_mm();
                auto &mgr = main_addressing_register;
                // R8: stage s1c[149] through mgr[11] with 1-NOP gap.
                mgr[11] = s1c[149];
                //NOP                                    // s1c 1-cycle gap
                bool merge_skipped = (mgr[11] < 0);
                int intv_n;
                if (merge_skipped) {
                    mgr[11] = s1c[148];
                    //NOP                                // s1c 1-cycle gap
                    intv_n = mgr[11];
                } else {
                    intv_n = 0;
                    for (int pe = 0; pe < 4; pe++) {
                        mgr[11] = s1c[4 + pe];
                        //NOP                            // s1c 1-cycle gap
                        intv_n += mgr[11];
                    }
                }
                s1c[149] = intv_n;
                mgr[11] = s1c[145];                     // n_a
                //NOP                                    // s1c 1-cycle gap
                mgr[24] = mgr[11];
                mgr[28] = intv_n;
                // Compute intv boundary positions (AC-7)
                mgr[11] = s1c[152];                     // active_intv_base
                //NOP                                    // s1c 1-cycle gap
                int ib = mgr[11];
                if (!merge_skipped) {
                    // Collect per-PE absolute boundary positions via min.
                    // R6 fix: stage each spm[976+b] / spm[979+b] load
                    // through mgr[11] with 3-NOP SPM settle before the
                    // hp/lp consumer.
                    for (int b = 0; b < 3; b++) {
                        int best_hi = intv_n, best_lo = intv_n;
                        for (int pe = 0; pe < 4; pe++) {
                            int *spm = &SPM_unit->buffer[
                                pe * SPM_BANK_GROUP_SIZE];
                            mgr[11] = spm[976+b];            // SPM hp
                            //NOP                              // SPM 1/3
                            //NOP                              // SPM 2/3
                            //NOP                              // SPM 3/3
                            int hp = mgr[11];
                            mgr[11] = spm[979+b];            // SPM lp
                            //NOP                              // SPM 1/3
                            //NOP                              // SPM 2/3
                            //NOP                              // SPM 3/3
                            int lp = mgr[11];
                            if (hp >= 0 && hp < best_hi) best_hi = hp;
                            if (lp >= 0 && lp < best_lo) best_lo = lp;
                        }
                        s1c[163+b] = best_hi; // intv_lo[pe+1]
                        s1c[166+b] = best_lo; // intv_hi[pe]
                    }
                } else {
                    // No merge: compute boundaries via fused binary
                    // search, lowered to explicit label/goto state
                    // machines per boundary (AC-9 rule 4 close).
                    // Triple-unrolled for b in {0,1,2} with unique
                    // label suffixes because C++ function-scope labels
                    // cannot be reused across a for-loop body.
                    auto &main_gr = main_addressing_register;
                    // b = 0
                    {
                        main_gr[11] = s1c[159];
                        //NOP                                    // s1c 1-cycle gap
                        main_gr[3] = main_gr[11];                // stash vd pivot
                        int h_lo_b0 = 0, h_hi_b0 = intv_n;
                        int l_lo_b0 = 0, l_hi_b0 = intv_n;
                    m38_b0_top:
                        if (h_lo_b0 >= h_hi_b0 && l_lo_b0 >= l_hi_b0)
                            goto m38_b0_done;
                        if (h_lo_b0 >= h_hi_b0) goto m38_b0_skip_h;
                        {
                            int mid = (h_lo_b0 + h_hi_b0) / 2;
                            main_gr[11] = mm[ib + 2*mid];       // MM load
                            // waitLSQ
                            //NOP                                // LSQ settle
                            if ((uint32_t)main_gr[11] < (uint32_t)main_gr[3]) h_lo_b0 = mid + 1;
                            else h_hi_b0 = mid;
                        }
                    m38_b0_skip_h:
                        if (l_lo_b0 >= l_hi_b0) goto m38_b0_top;
                        {
                            int mid = (l_lo_b0 + l_hi_b0) / 2;
                            main_gr[11] = mm[ib + 2*mid + 1];   // MM load
                            // waitLSQ
                            //NOP                                // LSQ settle
                            if ((uint32_t)main_gr[11] <= (uint32_t)main_gr[3]) l_lo_b0 = mid + 1;
                            else l_hi_b0 = mid;
                        }
                        goto m38_b0_top;
                    m38_b0_done:
                        s1c[166] = h_lo_b0;
                        s1c[163] = l_lo_b0;
                    }
                    // b = 1
                    {
                        main_gr[11] = s1c[160];
                        //NOP                                    // s1c 1-cycle gap
                        main_gr[3] = main_gr[11];                // stash vd pivot
                        int h_lo_b1 = 0, h_hi_b1 = intv_n;
                        int l_lo_b1 = 0, l_hi_b1 = intv_n;
                    m38_b1_top:
                        if (h_lo_b1 >= h_hi_b1 && l_lo_b1 >= l_hi_b1)
                            goto m38_b1_done;
                        if (h_lo_b1 >= h_hi_b1) goto m38_b1_skip_h;
                        {
                            int mid = (h_lo_b1 + h_hi_b1) / 2;
                            main_gr[11] = mm[ib + 2*mid];       // MM load
                            // waitLSQ
                            //NOP                                // LSQ settle
                            if ((uint32_t)main_gr[11] < (uint32_t)main_gr[3]) h_lo_b1 = mid + 1;
                            else h_hi_b1 = mid;
                        }
                    m38_b1_skip_h:
                        if (l_lo_b1 >= l_hi_b1) goto m38_b1_top;
                        {
                            int mid = (l_lo_b1 + l_hi_b1) / 2;
                            main_gr[11] = mm[ib + 2*mid + 1];   // MM load
                            // waitLSQ
                            //NOP                                // LSQ settle
                            if ((uint32_t)main_gr[11] <= (uint32_t)main_gr[3]) l_lo_b1 = mid + 1;
                            else l_hi_b1 = mid;
                        }
                        goto m38_b1_top;
                    m38_b1_done:
                        s1c[167] = h_lo_b1;
                        s1c[164] = l_lo_b1;
                    }
                    // b = 2
                    {
                        main_gr[11] = s1c[161];
                        //NOP                                    // s1c 1-cycle gap
                        main_gr[3] = main_gr[11];                // stash vd pivot
                        int h_lo_b2 = 0, h_hi_b2 = intv_n;
                        int l_lo_b2 = 0, l_hi_b2 = intv_n;
                    m38_b2_top:
                        if (h_lo_b2 >= h_hi_b2 && l_lo_b2 >= l_hi_b2)
                            goto m38_b2_done;
                        if (h_lo_b2 >= h_hi_b2) goto m38_b2_skip_h;
                        {
                            int mid = (h_lo_b2 + h_hi_b2) / 2;
                            main_gr[11] = mm[ib + 2*mid];       // MM load
                            // waitLSQ
                            //NOP                                // LSQ settle
                            if ((uint32_t)main_gr[11] < (uint32_t)main_gr[3]) h_lo_b2 = mid + 1;
                            else h_hi_b2 = mid;
                        }
                    m38_b2_skip_h:
                        if (l_lo_b2 >= l_hi_b2) goto m38_b2_top;
                        {
                            int mid = (l_lo_b2 + l_hi_b2) / 2;
                            main_gr[11] = mm[ib + 2*mid + 1];   // MM load
                            // waitLSQ
                            //NOP                                // LSQ settle
                            if ((uint32_t)main_gr[11] <= (uint32_t)main_gr[3]) l_lo_b2 = mid + 1;
                            else l_hi_b2 = mid;
                        }
                        goto m38_b2_top;
                    m38_b2_done:
                        s1c[168] = h_lo_b2;
                        s1c[165] = l_lo_b2;
                    }
                }
            }
        } else if (magic_id == 39) {
            // Intv sort setup: ISA-lowered register operations.
            {
                int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
                constexpr int DIAG_CAP_V  = (16 << 20);
                constexpr int INTV_CAP_V  = (1 << 21);
                constexpr int MM_INTV     = DIAG_CAP_V * 6;
                constexpr int MM_NEXT_INTV = MM_INTV + INTV_CAP_V * 2;
                constexpr int MM_SWAP     = MM_NEXT_INTV + INTV_CAP_V * 2;
                gr[24] = s1c[155];                       // mv s1c→gr
                gr[3]  = MM_NEXT_INTV;                   // si (constexpr)
                //NOP
                gr[4]  = MM_SWAP;                        // si (constexpr)
                gr[6]  = gr[24] + 3;                     // addi
                //NOP
                gr[6]  = (unsigned)gr[6] >> 2;           // shifti_r (div by 4)
            }
        } else if (magic_id == 28) {
            // Diag merge split + tile load.
            // Interleaved binary search across PEs for split points,
            // then load initial tiles. Inlined from merge_split_and_load.
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                constexpr int DIAG_CAP_V  = (16 << 20);
                constexpr int INTV_CAP_V  = (1 << 21);
                constexpr int MM_SORT_BUF = DIAG_CAP_V * 6 + INTV_CAP_V * 6;
                // R8 fix: stage each s1c head load through gr[11] + 1-NOP.
                gr[11] = s1c[147];
                //NOP                                    // s1c 1-cycle gap
                int n_phase1 = gr[11];
                gr[11] = s1c[148];
                //NOP                                    // s1c 1-cycle gap
                int n_a = gr[11];
                gr[11] = s1c[146];
                //NOP                                    // s1c 1-cycle gap
                int intv_n = gr[11];
                gr[11] = s1c[153];
                //NOP                                    // s1c 1-cycle gap
                int diag_base = gr[11];
                if (n_phase1 < 0) n_phase1 = 0;
                if (n_phase1 > n_a) n_phase1 = n_a;
                int n_tail = n_a - n_phase1;
                int abase = diag_base;
                int bbase = diag_base + n_phase1 * 2;
                if (n_phase1 <= 0 || n_tail <= 0) {
                    gr[6] = 0; // skip merge
                } else {
                    int n_total = n_phase1 + n_tail;
                    int nape = (n_total + 3) / 4;
                    int a_sp[5], b_sp[5];
                    a_sp[0] = 0; b_sp[0] = 0;
                    a_sp[4] = n_phase1; b_sp[4] = n_tail;
                    // Interleaved binary search: 3 searches (pe=1,2,3)
                    // one step per PE per round with waitLSQ between
                    int bs_lo[3], bs_hi[3], bs_target[3];
                    for (int p = 0; p < 3; p++) {
                        bs_target[p] = (p+1) * nape;
                        if (bs_target[p] > n_total) bs_target[p] = n_total;
                        bs_lo[p] = bs_target[p] - n_tail;
                        if (bs_lo[p] < 0) bs_lo[p] = 0;
                        bs_hi[p] = bs_target[p];
                        if (bs_hi[p] > n_phase1) bs_hi[p] = n_phase1;
                    }
                    // R4 fix: replace 'while (any_active) ... for p=0..2'
                    // with label/goto outer loop + macro-unrolled per-p
                    // step bodies. Each step's MM reads stage through
                    // gr[11] with '// waitLSQ' + //NOP separation
                    // before the compare (R7).
                m28_bs_top:
                    if (bs_lo[0] >= bs_hi[0]
                        && bs_lo[1] >= bs_hi[1]
                        && bs_lo[2] >= bs_hi[2]) goto m28_bs_done;
                    // p = 0 step (compile-time-bounded unroll)
                    if (bs_lo[0] < bs_hi[0]) {
                        int mid = (bs_lo[0] + bs_hi[0]) / 2;
                        int bi2 = bs_target[0] - mid;
                        gr[11] = (bi2 > 0)
                            ? mm[bbase + (bi2-1)*2] : 0;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        gr[3] = gr[11];                          // stash b_val
                        gr[11] = (mid < n_phase1)
                            ? mm[abase + mid*2] : (int)0xFFFFFFFF;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        if (bi2 > 0 && mid < n_phase1
                            && (uint32_t)gr[3] > (uint32_t)gr[11])
                            bs_lo[0] = mid + 1;
                        else bs_hi[0] = mid;
                    }
                    // p = 1 step
                    if (bs_lo[1] < bs_hi[1]) {
                        int mid = (bs_lo[1] + bs_hi[1]) / 2;
                        int bi2 = bs_target[1] - mid;
                        gr[11] = (bi2 > 0)
                            ? mm[bbase + (bi2-1)*2] : 0;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        gr[3] = gr[11];                          // stash b_val
                        gr[11] = (mid < n_phase1)
                            ? mm[abase + mid*2] : (int)0xFFFFFFFF;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        if (bi2 > 0 && mid < n_phase1
                            && (uint32_t)gr[3] > (uint32_t)gr[11])
                            bs_lo[1] = mid + 1;
                        else bs_hi[1] = mid;
                    }
                    // p = 2 step
                    if (bs_lo[2] < bs_hi[2]) {
                        int mid = (bs_lo[2] + bs_hi[2]) / 2;
                        int bi2 = bs_target[2] - mid;
                        gr[11] = (bi2 > 0)
                            ? mm[bbase + (bi2-1)*2] : 0;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        gr[3] = gr[11];                          // stash b_val
                        gr[11] = (mid < n_phase1)
                            ? mm[abase + mid*2] : (int)0xFFFFFFFF;
                        // waitLSQ
                        //NOP                                    // LSQ settle
                        if (bi2 > 0 && mid < n_phase1
                            && (uint32_t)gr[3] > (uint32_t)gr[11])
                            bs_lo[2] = mid + 1;
                        else bs_hi[2] = mid;
                    }
                    goto m28_bs_top;
                m28_bs_done: ;
                    for (int p = 0; p < 3; p++) {
                        a_sp[p+1] = bs_lo[p];
                        b_sp[p+1] = bs_target[p] - bs_lo[p];
                        if (a_sp[p+1] < a_sp[p]) {
                            a_sp[p+1] = a_sp[p];
                            b_sp[p+1] = bs_target[p] - a_sp[p+1];
                        }
                        if (b_sp[p+1] < b_sp[p]) {
                            b_sp[p+1] = b_sp[p];
                            a_sp[p+1] = bs_target[p] - b_sp[p+1];
                        }
                    }
                    // Pre-compute tile sizes for mvdq interleaved load
                    int max_pt = 0;
                    int a0s[4], a1s[4], b0s[4], b1s[4];
                    int a_srcs[4], b_srcs[4];
                    for (int pe = 0; pe < 4; pe++) {
                        int pa_s = a_sp[pe];
                        int pa_n = a_sp[pe+1] - pa_s;
                        if (pa_n < 0) pa_n = 0;
                        int pb_s = b_sp[pe];
                        int pb_n = b_sp[pe+1] - pb_s;
                        if (pb_n < 0) pb_n = 0;
                        int pt = pa_n + pb_n;
                        if (pt > max_pt) max_pt = pt;
                        s1c[pe]     = pt;
                        s1c[4+pe]   = 0;
                        int a0 = pa_n; if (a0 > MERGE_TILE) a0 = MERGE_TILE;
                        int a1r = pa_n - a0; if (a1r < 0) a1r = 0;
                        int a1 = a1r; if (a1 > MERGE_TILE) a1 = MERGE_TILE;
                        int b0 = pb_n; if (b0 > MERGE_TILE) b0 = MERGE_TILE;
                        int b1r = pb_n - b0; if (b1r < 0) b1r = 0;
                        int b1 = b1r; if (b1 > MERGE_TILE) b1 = MERGE_TILE;
                        s1c[8+pe]  = abase + (pa_s + a0 + a1) * 2;
                        int rem_a = pa_n - a0 - a1; if (rem_a < 0) rem_a = 0;
                        s1c[12+pe] = rem_a;
                        s1c[16+pe] = bbase + (pb_s + b0 + b1) * 2;
                        int rem_b = pb_n - b0 - b1; if (rem_b < 0) rem_b = 0;
                        s1c[20+pe] = rem_b;
                        int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                        int *spm2 = &SPM_unit->buffer[pe_spm];
                        a0s[pe]=a0; a1s[pe]=a1; b0s[pe]=b0; b1s[pe]=b1;
                        a_srcs[pe] = abase + pa_s * 2;
                        b_srcs[pe] = bbase + pb_s * 2;
                        spm2[MERGE_META+0] = 0;
                        spm2[MERGE_META+1] = 0;
                        spm2[MERGE_META+4] = 0;
                        spm2[MERGE_META+5] = (pa_n<=a0+a1) ? 1 : 0;
                        spm2[MERGE_META+6] = (pb_n<=b0+b1) ? 1 : 0;
                        spm2[MERGE_META+7] = 0;
                        spm2[MERGE_META+8] = 0;
                        spm2[MERGE_META+9] = a0;
                        spm2[MERGE_META+10] = a1;
                        spm2[MERGE_META+11] = b0;
                        spm2[MERGE_META+12] = b1;
                    }
                    // Interleaved mvdq tile loads across PEs
                    int *spm = SPM_unit->buffer;
                    // A_BUF0
                    { int mw = 0;
                      for (int pe=0; pe<4; pe++)
                          if (a0s[pe]*2 > mw) mw = a0s[pe]*2;
                      for (int j = 0; j < mw; j += 8)
                          for (int pe = 0; pe < 4; pe++) {
                              int w = a0s[pe]*2;
                              if (j >= w) continue;
                              int cnt = w-j; if (cnt>8) cnt=8;
                              mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE+MERGE_A_BUF0+j], &mm[a_srcs[pe]+j], cnt);
                          }
                    }
                    // A_BUF1
                    { int mw = 0;
                      for (int pe=0; pe<4; pe++)
                          if (a1s[pe]*2 > mw) mw = a1s[pe]*2;
                      for (int j = 0; j < mw; j += 8)
                          for (int pe = 0; pe < 4; pe++) {
                              int w = a1s[pe]*2;
                              if (j >= w) continue;
                              int cnt = w-j; if (cnt>8) cnt=8;
                              mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE+MERGE_A_BUF1+j], &mm[a_srcs[pe]+a0s[pe]*2+j], cnt);
                          }
                    }
                    // B_BUF0
                    { int mw = 0;
                      for (int pe=0; pe<4; pe++)
                          if (b0s[pe]*2 > mw) mw = b0s[pe]*2;
                      for (int j = 0; j < mw; j += 8)
                          for (int pe = 0; pe < 4; pe++) {
                              int w = b0s[pe]*2;
                              if (j >= w) continue;
                              int cnt = w-j; if (cnt>8) cnt=8;
                              mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE+MERGE_B_BUF0+j], &mm[b_srcs[pe]+j], cnt);
                          }
                    }
                    // B_BUF1
                    { int mw = 0;
                      for (int pe=0; pe<4; pe++)
                          if (b1s[pe]*2 > mw) mw = b1s[pe]*2;
                      for (int j = 0; j < mw; j += 8)
                          for (int pe = 0; pe < 4; pe++) {
                              int w = b1s[pe]*2;
                              if (j >= w) continue;
                              int cnt = w-j; if (cnt>8) cnt=8;
                              mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE+MERGE_B_BUF1+j], &mm[b_srcs[pe]+b0s[pe]*2+j], cnt);
                          }
                    }
                    int niter = ((max_pt + MERGE_STEP - 1)
                        / MERGE_STEP) * MERGE_STEP;
                    gr[6] = (niter == 0) ? 0 : niter;
                    gr[4] = MM_SORT_BUF;
                }
                gr[3]=diag_base; gr[24]=n_a; gr[28]=intv_n;
            }
        } else if (magic_id == 33) {
            // Merge tile reload (overlapped with PE compute).
            // Chunk-outer / PE-inner round-robin (AC-9 R9 close).
            // 3-pass restructure: (1) determine per-(pe,buf) reload
            // params monotonically consuming s1c rem counters through
            // gr[11]; (2) four chunk-outer mvdq passes (A0, A1, B0,
            // B1) round-robined across PEs; (3) update SPM meta +
            // drain flags.
            // BL-20260416-m32-gather-dep applies to m32 GATHER (MM->
            // MM with cross-PE skip dependencies), NOT to m30/m33
            // RELOAD (MM->per-PE-SPM with no cross-PE state).
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int a_tile[2][4] = {};
                int a_src[2][4]  = {};
                int b_tile[2][4] = {};
                int b_src[2][4]  = {};
                // Pass 1: reload-param gather through gr[11]/gr[1]
                for (int pe = 0; pe < 4; pe++) {
                    int *s = &spm[pe * SPM_BANK_GROUP_SIZE];
                    gr[11] = s1c[12+pe];                  // s1c rem_a
                    //NOP                                  // s1c gap
                    int rem_a = gr[11];
                    gr[1]  = s1c[8+pe];                   // s1c src_a
                    //NOP                                  // s1c gap
                    int src_a = gr[1];
                    for (int buf = 0; buf < 2; buf++) {
                        gr[11] = s[MERGE_META+9+buf];     // SPM flag_a
                        //NOP                              // SPM 1/3
                        //NOP                              // SPM 2/3
                        //NOP                              // SPM 3/3
                        if (gr[11] == 0 && rem_a > 0) {
                            int tile = rem_a;
                            if (tile > MERGE_TILE) tile = MERGE_TILE;
                            a_tile[buf][pe] = tile;
                            a_src[buf][pe]  = src_a;
                            src_a += tile * 2;
                            rem_a -= tile;
                        }
                    }
                    s1c[8+pe]  = src_a;
                    s1c[12+pe] = rem_a;
                    gr[11] = s1c[20+pe];                  // s1c rem_b
                    //NOP                                  // s1c gap
                    int rem_b = gr[11];
                    gr[1]  = s1c[16+pe];                  // s1c src_b
                    //NOP                                  // s1c gap
                    int src_b = gr[1];
                    for (int buf = 0; buf < 2; buf++) {
                        gr[11] = s[MERGE_META+11+buf];    // SPM flag_b
                        //NOP                              // SPM 1/3
                        //NOP                              // SPM 2/3
                        //NOP                              // SPM 3/3
                        if (gr[11] == 0 && rem_b > 0) {
                            int tile = rem_b;
                            if (tile > MERGE_TILE) tile = MERGE_TILE;
                            b_tile[buf][pe] = tile;
                            b_src[buf][pe]  = src_b;
                            src_b += tile * 2;
                            rem_b -= tile;
                        }
                    }
                    s1c[16+pe] = src_b;
                    s1c[20+pe] = rem_b;
                }
                // Pass 2: chunk-outer round-robin mvdq
                #define M33_MVDQ(buf_off, tile_arr, src_arr) do { \
                    int mw = 0; \
                    for (int pe = 0; pe < 4; pe++) { \
                        int w = tile_arr[pe]*2; if (w > mw) mw = w; } \
                    for (int j = 0; j < mw; j += 8) \
                        for (int pe = 0; pe < 4; pe++) { \
                            int w = tile_arr[pe]*2; \
                            if (j >= w) continue; \
                            int cnt = w-j; if (cnt>8) cnt=8; \
                            mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE+buf_off+j], \
                                      &mm[src_arr[pe]+j], cnt); \
                        } \
                } while(0)
                M33_MVDQ(MERGE_A_BUF0, a_tile[0], a_src[0]);
                M33_MVDQ(MERGE_A_BUF1, a_tile[1], a_src[1]);
                M33_MVDQ(MERGE_B_BUF0, b_tile[0], b_src[0]);
                M33_MVDQ(MERGE_B_BUF1, b_tile[1], b_src[1]);
                #undef M33_MVDQ
                // Pass 3: update SPM meta + drain flags
                for (int pe = 0; pe < 4; pe++) {
                    int *s = &spm[pe * SPM_BANK_GROUP_SIZE];
                    for (int buf = 0; buf < 2; buf++) {
                        if (a_tile[buf][pe] > 0)
                            s[MERGE_META+9+buf] = a_tile[buf][pe];
                        if (b_tile[buf][pe] > 0)
                            s[MERGE_META+11+buf] = b_tile[buf][pe];
                    }
                    // Drain flags (post-buf-loop)
                    if (s1c[12+pe] <= 0 && s[MERGE_META+9]==0
                        && s[MERGE_META+10]==0) s[MERGE_META+5] = 1;
                    if (s1c[20+pe] <= 0 && s[MERGE_META+11]==0
                        && s[MERGE_META+12]==0) s[MERGE_META+6] = 1;
                }
            }
        } else if (magic_id == 35) {
            // Merge writeback: SPM output → MM.
            // Chunk outer, PE inner: round-robin streaming.
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int out_off = (magic_mask & 1) ? MERGE_OUT1 : MERGE_OUT0;
                int mm_out = gr[4];
                // Pre-compute per-PE output info.
                // ISA lowering: route SPM→gr[11] with 3-NOP settle and
                // s1c→gr[11] with 1-NOP gap (BL-20260417-ctrl-sync-gr).
                int out_ns[4], mm_dsts[4], spm_srcs[4];
                int max_words = 0, cum = 0;
                for (int pe = 0; pe < 4; pe++) {
                    int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                    gr[11] = spm[pe_spm + MERGE_META + 4];   // SPM load out_n
                    //NOP                                     // SPM lat 1/3
                    //NOP                                     // SPM lat 2/3
                    //NOP                                     // SPM lat 3/3
                    out_ns[pe] = gr[11];
                    spm_srcs[pe] = pe_spm + out_off;
                    gr[11] = s1c[4+pe];                      // s1c load
                    //NOP                                     // s1c 1-cycle gap
                    mm_dsts[pe] = mm_out + (cum + gr[11]) * 2;
                    int w = out_ns[pe] * 2;
                    if (w > max_words) max_words = w;
                    gr[11] = s1c[pe];                        // s1c load for cum
                    //NOP                                     // s1c 1-cycle gap
                    cum += gr[11];
                }
                // Interleaved mvdq: chunk outer, PE inner
                for (int j = 0; j < max_words; j += 8) {
                    for (int pe = 0; pe < 4; pe++) {
                        int words = out_ns[pe] * 2;
                        if (j >= words) continue;
                        int cnt = words - j;
                        if (cnt > 8) cnt = 8;
                        mvdq_copy(&mm[mm_dsts[pe] + j],
                                  &spm[spm_srcs[pe] + j], cnt);
                    }
                }
                for (int pe = 0; pe < 4; pe++)
                    s1c[4+pe] += out_ns[pe];
                gr[2] += MERGE_STEP;
            }
        } else if (magic_id == 36) {
            // Diag merge finalize (pointer-swap version).
            // If merge happened, active_diag_base = gr[4] (MM_SORT_BUF).
            // If merge skipped (gr[6]==0), active_diag_base stays = gr[3].
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                int n_a = gr[24];
                if (gr[6] != 0) {
                    s1c[153] = gr[4]; // active_diag_base = MM_SORT_BUF
                } else {
                    s1c[153] = gr[3]; // active_diag_base = original diag_base
                }
                // Compute diag split metadata for dedup.
                // Mid-diagonal start: use nominal splits directly.
                // Boundary fixup happens in magic 32 finalize (max merge).
                int db = s1c[153];
                int nape = (n_a + 3) / 4;
                // 5 split indices in s1c[154..158]: nominal positions
                s1c[154] = 0;
                for (int pe = 1; pe < 4; pe++) {
                    int nom = pe * nape;
                    s1c[154+pe] = (nom < n_a) ? nom : n_a;
                }
                s1c[158] = n_a;
                // 4 boundary vd values in s1c[159..162]
                // vd at split[1], split[2], split[3] (internal boundaries)
                // + sentinel for split[4]=n_a (use vd at n_a-1 or max)
                // ISA lowering: s1c→gr w/ 1-cycle gap; MM→gr w/ waitLSQ+NOP
                // staging before the s1c store. gr[11] is the CLAUDE-safe
                // controller scratch (BL-20260417-ctrl-sync-gr).
                for (int pe = 0; pe < 3; pe++) {
                    gr[11] = s1c[155+pe];              // s1c load sp
                    //NOP                                // s1c 1-cycle gap
                    if (gr[11] < n_a) {
                        gr[11] = mm[db + 2*gr[11]];    // MM load (vd at split)
                        // waitLSQ
                        //NOP                            // latency settle
                        s1c[159+pe] = gr[11];
                    } else {
                        s1c[159+pe] = (int)0xFFFFFFFF; // sentinel
                    }
                }
                if (n_a > 0) {
                    gr[11] = mm[db + 2*(n_a-1)];      // MM load (last vd)
                    // waitLSQ
                    //NOP                                // latency settle
                    s1c[162] = gr[11];
                } else {
                    s1c[162] = (int)0xFFFFFFFF;
                }
            }
        } else if (magic_id == 29) {
            // Tiled dedup: split search + initial tile load.
            // Inputs: gr[3]=diag_base, gr[24]=n_a, gr[28]=intv_n.
            // Loads first tile of diags+intv into BUF0 per PE, inits META.
            // s1c layout: [0..3]=diag_mm_src, [4..7]=diag_remaining,
            //   [8..11]=intv_mm_src, [12..15]=intv_remaining,
            //   [16..19]=diag_out_base, [20..23]=diag_out_cursor,
            //   [24..27]=intv_out_base, [28..31]=intv_out_cursor.
            // Sets gr[6]=loop bound, gr[4]=MM_SORT_BUF.
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                constexpr int DIAG_CAP_V = (16 << 20);
                constexpr int INTV_CAP_V = (1 << 21);
                constexpr int MM_INTV = DIAG_CAP_V * 6;
                constexpr int MM_SORT_BUF =
                    DIAG_CAP_V * 6 + INTV_CAP_V * 6;
                // Use MM_SWAP region (free during dedup)
                constexpr int MM_DEDUP_INTV_OUT =
                    DIAG_CAP_V * 6 + INTV_CAP_V * 4;
                // Use pre-computed splits from s1c (AC-8)
                int diag_base = s1c[153]; // active_diag_base
                int intv_base = s1c[152]; // active_intv_base
                int n_a       = gr[24];
                int intv_n    = gr[28];

                // Read pre-computed diag splits from s1c[154..158]
                int splits[5];
                for (int i = 0; i < 5; i++) splits[i] = s1c[154+i];

                // Read pre-computed intv boundaries from s1c[163..168]
                // intv_lo[pe]: first intv whose hi > vd(split[pe])
                // intv_hi[pe]: first intv whose lo >= vd(split[pe+1])
                int intv_lo[4] = {0, 0, 0, 0};
                int intv_hi[4] = {intv_n, intv_n, intv_n, intv_n};
                if (intv_n > 0) {
                    for (int pe = 0; pe < 3; pe++)
                        intv_hi[pe] = s1c[166+pe];
                    for (int pe = 1; pe < 4; pe++)
                        intv_lo[pe] = s1c[163+pe-1];
                }

                // Loop bound: max(diag_n + intv_n) across PEs
                int max_total = 0;
                int diag_out_cum = 0, intv_out_cum = 0;
                int dd0[4], dd1[4], d_srcs[4];
                int ii0[4], ii1[4], i_srcs[4];
                for (int pe = 0; pe < 4; pe++) {
                    int d_n = splits[pe+1] - splits[pe];
                    int iv_s = intv_lo[pe];
                    if (iv_s > intv_hi[pe]) iv_s = intv_hi[pe];
                    int iv_e = intv_lo[pe];
                    if (iv_e < intv_hi[pe]) iv_e = intv_hi[pe];
                    int iv_n = iv_e - iv_s;
                    int total = d_n + iv_n;
                    if (total > max_total) max_total = total;

                    // Pre-compute tile sizes for mvdq interleaved load
                    int d0 = (d_n < DEDUP_TILE) ? d_n : DEDUP_TILE;
                    int d1r = d_n - d0; if (d1r < 0) d1r = 0;
                    int d1 = (d1r < DEDUP_TILE) ? d1r : DEDUP_TILE;
                    int d_src = diag_base + splits[pe] * 2;
                    int i0 = (iv_n < DEDUP_TILE) ? iv_n : DEDUP_TILE;
                    int i1r = iv_n - i0; if (i1r < 0) i1r = 0;
                    int i1 = (i1r < DEDUP_TILE) ? i1r : DEDUP_TILE;
                    int i_src = intv_base + iv_s * 2;
                    dd0[pe]=d0; dd1[pe]=d1; d_srcs[pe]=d_src;
                    ii0[pe]=i0; ii1[pe]=i1; i_srcs[pe]=i_src;
                    // s1c: track MM sources and remaining
                    s1c[pe]      = d_src + (d0+d1) * 2;
                    s1c[4 + pe]  = d_n - d0 - d1;
                    s1c[8 + pe]  = i_src + (i0+i1) * 2;
                    s1c[12 + pe] = iv_n - i0 - i1;
                    s1c[16 + pe] = diag_out_cum;         // diag_out_base
                    s1c[20 + pe] = 0;                    // diag_out_cursor
                    s1c[24 + pe] = intv_out_cum;         // intv_out_base
                    s1c[28 + pe] = 0;                    // intv_out_cursor
                    diag_out_cum += d_n;  // max possible output
                    intv_out_cum += iv_n;

                    // Init META words (per PE, using pre-computed sizes)
                    int *spm2 = &SPM_unit->buffer[pe * SPM_BANK_GROUP_SIZE];
                    spm2[DEDUP_META+0] = (int)0xFFFFFFFF;
                    spm2[DEDUP_META+1] = 0;
                    for (int m = 2; m < 10; m++) spm2[DEDUP_META+m] = 0;
                    spm2[DEDUP_META+10] = dd0[pe];
                    spm2[DEDUP_META+11] = dd1[pe];
                    spm2[DEDUP_META+12] = ii0[pe];
                    spm2[DEDUP_META+13] = ii1[pe];
                    spm2[DEDUP_META+14] = (int)0xFFFFFFFF;
                    for (int m = 15; m < 20; m++) spm2[DEDUP_META+m] = 0;
                }
                // Interleaved mvdq tile loads across PEs
                int *spm = SPM_unit->buffer;
                #define M29_MVDQ(buf_off, sizes, srcs, extra) do { \
                    int mw = 0; \
                    for (int pe=0; pe<4; pe++) { \
                        int w = sizes[pe]*2; if (w > mw) mw = w; } \
                    for (int j = 0; j < mw; j += 8) \
                        for (int pe = 0; pe < 4; pe++) { \
                            int w = sizes[pe]*2; \
                            if (j >= w) continue; \
                            int cnt = w-j; if (cnt>8) cnt=8; \
                            mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE \
                                +buf_off+j], &mm[srcs[pe]+extra+j], cnt); \
                        } \
                } while(0)
                // Diag BUF0 and BUF1
                M29_MVDQ(DEDUP_DIAG_BUF0, dd0, d_srcs, 0);
                { int d1_srcs[4];
                  for (int pe=0; pe<4; pe++) d1_srcs[pe] = d_srcs[pe] + dd0[pe]*2;
                  M29_MVDQ(DEDUP_DIAG_BUF1, dd1, d1_srcs, 0);
                }
                // Intv BUF0 and BUF1
                M29_MVDQ(DEDUP_INTV_BUF0, ii0, i_srcs, 0);
                { int i1_srcs[4];
                  for (int pe=0; pe<4; pe++) i1_srcs[pe] = i_srcs[pe] + ii0[pe]*2;
                  M29_MVDQ(DEDUP_INTV_BUF1, ii1, i1_srcs, 0);
                }
                #undef M29_MVDQ
                int niter = ((max_total + DEDUP_TILE - 1)
                    / DEDUP_TILE) * DEDUP_TILE;
                gr[6] = (niter == 0) ? DEDUP_TILE : niter;
                // Dedup diag output goes to opposite of active_diag_base
                gr[4] = (diag_base == MM_SORT_BUF)
                    ? s1c[144] : MM_SORT_BUF;
                gr[7] = MM_DEDUP_INTV_OUT;
                // Save original counts for reference dedup in M32
            }
        } else if (magic_id == 30) {
            // Dedup reload: refill exhausted input buffers from MM.
            // Chunk-outer / PE-inner round-robin (AC-9 R9 close).
            // 3-pass restructure mirrors m33: (1) per-(pe,buf) param
            // gather through gr[11]/gr[1] monotonically consuming
            // s1c rem counters; (2) four chunk-outer mvdq passes
            // (DIAG_BUF0, DIAG_BUF1, INTV_BUF0, INTV_BUF1); (3)
            // update SPM meta.
            // BL-20260416-m32-gather-dep applies to m32 GATHER
            // (cross-PE skip deps), NOT this reload (per-PE SPM
            // banks, no cross-PE state).
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int d_tile[2][4] = {};
                int d_src[2][4]  = {};
                int i_tile[2][4] = {};
                int i_src[2][4]  = {};
                // Pass 1: reload-param gather through gr[11]/gr[1]
                for (int pe = 0; pe < 4; pe++) {
                    int *s = &spm[pe * SPM_BANK_GROUP_SIZE];
                    gr[11] = s1c[4+pe];                   // s1c rem_d
                    //NOP                                  // s1c gap
                    int rem_d = gr[11];
                    gr[1]  = s1c[pe];                     // s1c src_d
                    //NOP                                  // s1c gap
                    int src_d = gr[1];
                    for (int buf = 0; buf < 2; buf++) {
                        gr[11] = s[DEDUP_META+10+buf];    // SPM flag_d
                        //NOP                              // SPM 1/3
                        //NOP                              // SPM 2/3
                        //NOP                              // SPM 3/3
                        if (gr[11] == 0 && rem_d > 0) {
                            int tile = rem_d;
                            if (tile > DEDUP_TILE) tile = DEDUP_TILE;
                            d_tile[buf][pe] = tile;
                            d_src[buf][pe]  = src_d;
                            src_d += tile * 2;
                            rem_d -= tile;
                        }
                    }
                    s1c[pe]   = src_d;
                    s1c[4+pe] = rem_d;
                    gr[11] = s1c[12+pe];                  // s1c rem_i
                    //NOP                                  // s1c gap
                    int rem_i = gr[11];
                    gr[1]  = s1c[8+pe];                   // s1c src_i
                    //NOP                                  // s1c gap
                    int src_i = gr[1];
                    for (int buf = 0; buf < 2; buf++) {
                        gr[11] = s[DEDUP_META+12+buf];    // SPM flag_i
                        //NOP                              // SPM 1/3
                        //NOP                              // SPM 2/3
                        //NOP                              // SPM 3/3
                        if (gr[11] == 0 && rem_i > 0) {
                            int tile = rem_i;
                            if (tile > DEDUP_TILE) tile = DEDUP_TILE;
                            i_tile[buf][pe] = tile;
                            i_src[buf][pe]  = src_i;
                            src_i += tile * 2;
                            rem_i -= tile;
                        }
                    }
                    s1c[8+pe]  = src_i;
                    s1c[12+pe] = rem_i;
                }
                // Pass 2: chunk-outer round-robin mvdq
                #define M30_MVDQ(buf_off, tile_arr, src_arr) do { \
                    int mw = 0; \
                    for (int pe = 0; pe < 4; pe++) { \
                        int w = tile_arr[pe]*2; if (w > mw) mw = w; } \
                    for (int j = 0; j < mw; j += 8) \
                        for (int pe = 0; pe < 4; pe++) { \
                            int w = tile_arr[pe]*2; \
                            if (j >= w) continue; \
                            int cnt = w-j; if (cnt>8) cnt=8; \
                            mvdq_copy(&spm[pe*SPM_BANK_GROUP_SIZE+buf_off+j], \
                                      &mm[src_arr[pe]+j], cnt); \
                        } \
                } while(0)
                M30_MVDQ(DEDUP_DIAG_BUF0, d_tile[0], d_src[0]);
                M30_MVDQ(DEDUP_DIAG_BUF1, d_tile[1], d_src[1]);
                M30_MVDQ(DEDUP_INTV_BUF0, i_tile[0], i_src[0]);
                M30_MVDQ(DEDUP_INTV_BUF1, i_tile[1], i_src[1]);
                #undef M30_MVDQ
                // Pass 3: update SPM meta tile counts
                for (int pe = 0; pe < 4; pe++) {
                    int *s = &spm[pe * SPM_BANK_GROUP_SIZE];
                    for (int buf = 0; buf < 2; buf++) {
                        if (d_tile[buf][pe] > 0)
                            s[DEDUP_META+10+buf] = d_tile[buf][pe];
                        if (i_tile[buf][pe] > 0)
                            s[DEDUP_META+12+buf] = i_tile[buf][pe];
                    }
                }
            }
        } else if (magic_id == 31) {
            // Dedup writeback: DIAG_OUTx + INTV_OUTx → MM.
            // Chunk outer, PE inner: round-robin streaming.
            // Per-PE state lives in s1c (no new C++ locals — ISA rule 3):
            //   s1c[196+pe] = nds[pe]      per-call diag count
            //   s1c[200+pe] = nis[pe]      per-call intv count
            //   s1c[204+pe] = d_cur[pe]    monotonic MM diag cursor
            //   s1c[208+pe] = i_cur[pe]    monotonic MM intv cursor
            // Seam metadata for magic 32 merge lives in s1c[176..191]:
            //   s1c[176+pe] first-intv lo, s1c[180+pe] first-intv hi
            //   s1c[184+pe] last-intv  lo, s1c[188+pe] last-intv  hi
            // First-write is gated by s1c[28+pe] == 0 (pre-increment
            // cumulative intv cursor) so the "first nonzero tile per
            // PE" case fires exactly once across repeated magic-31
            // calls. Last is updated on every nonzero tile.
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                int *spm = SPM_unit->buffer;
                int d_off = (magic_mask & 1)
                    ? DEDUP_DIAG_OUT1 : DEDUP_DIAG_OUT0;
                int i_off = (magic_mask & 1)
                    ? DEDUP_INTV_OUT1 : DEDUP_INTV_OUT0;
                // Pre-compute per-PE counts and MM cursors into s1c.
                // Every SPM→s1c path is routed through gr[11] per the
                // CLAUDE.md SPM destination rule; every s1c arithmetic
                // store is routed through gr[11] per the controller
                // arithmetic-destination rule. The 3-NOP gap after
                // each SPM load makes the consumer slot-safe under
                // AC-7. max_d / max_i remain C++ loop-ephemeral
                // scalars (non-ISA accepted).
                int max_d = 0, max_i = 0;
                for (int pe = 0; pe < 4; pe++) {
                    int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                    gr[11] = spm[pe_spm + DEDUP_META + 2];   // mv: SPM→gr nds
                    //NOP                                     // SPM lat 1/3 slot-safe
                    //NOP                                     // SPM lat 2/3
                    //NOP                                     // SPM lat 3/3
                    s1c[196+pe] = gr[11];                    // mv: gr→s1c nds
                    gr[11] = spm[pe_spm + DEDUP_META + 3];   // mv: SPM→gr nis
                    //NOP                                     // SPM lat 1/3 slot-safe
                    //NOP                                     // SPM lat 2/3
                    //NOP                                     // SPM lat 3/3
                    s1c[200+pe] = gr[11];                    // mv: gr→s1c nis
                    // ISA lowering (AC-7 R8/R2 close): split
                    // 'gr[11] = s1c[A] + s1c[B]' into per-load
                    // gr[11]→gr[1] stash→gr[11] form with 1-NOP
                    // s1c gaps and //NOP barriers before each
                    // dependent gr[11] arithmetic (prevents
                    // paired-slot RAW). gr[1] is caller-dead on
                    // magic-29→31 entry (m29 sets gr[4,6,7],
                    // not gr[1]); gr[11] remains the CLAUDE-safe
                    // SPM scratch per BL-20260417-ctrl-sync-gr.
                    gr[11] = s1c[16+pe];                     // s1c diag_base
                    //NOP                                     // s1c 1-cycle gap
                    gr[1]  = gr[11];                         // stash diag_base
                    gr[11] = s1c[20+pe];                     // s1c diag_cur
                    //NOP                                     // s1c 1-cycle gap
                    gr[11] = gr[11] + gr[1];                 // diag_base+cur
                    //NOP                                     // RAW barrier
                    gr[11] = gr[11] + gr[11];                // *2
                    //NOP                                     // RAW barrier
                    gr[11] = gr[11] + gr[4];                 // + diag_base MM
                    //NOP                                     // RAW barrier
                    s1c[204+pe] = gr[11];                    // mv: gr→s1c
                    gr[11] = s1c[24+pe];                     // s1c intv_base
                    //NOP                                     // s1c 1-cycle gap
                    gr[1]  = gr[11];                         // stash intv_base
                    gr[11] = s1c[28+pe];                     // s1c intv_cur
                    //NOP                                     // s1c 1-cycle gap
                    gr[11] = gr[11] + gr[1];                 // intv_base+cur
                    //NOP                                     // RAW barrier
                    gr[11] = gr[11] + gr[11];                // *2
                    //NOP                                     // RAW barrier
                    gr[11] = gr[11] + gr[7];                 // + intv_base MM
                    //NOP                                     // RAW barrier
                    s1c[208+pe] = gr[11];                    // mv: gr→s1c
                    gr[11] = s1c[196+pe];                    // s1c nds
                    //NOP                                     // s1c 1-cycle gap
                    gr[11] = gr[11] + gr[11];                // nds*2
                    //NOP                                     // RAW barrier
                    if (gr[11] > max_d) max_d = gr[11];      // max
                    gr[11] = s1c[200+pe];                    // s1c nis
                    //NOP                                     // s1c 1-cycle gap
                    gr[11] = gr[11] + gr[11];                // nis*2
                    //NOP                                     // RAW barrier
                    if (gr[11] > max_i) max_i = gr[11];      // max
                }
                // Seam metadata: first-write-once, last-update-each.
                // Each SPM load lands in gr (controller SPM dest
                // rule — CLAUDE.md §SPM), then waits two non-SPM
                // cycles, then migrates to s1c. Loads are serialized
                // through gr[11] (single-register ping-pong) so only
                // one SPM request is in flight at a time. gr[11] is
                // the only live-safe scratch slot we can clobber
                // here: gr[12] is the GWFA wavefront-distance
                // counter (magic 3/5/7 live state), gr[13] is the
                // PE-sync AND (pe_array::tick line 4713), and
                // gr[7..10] is the AC-7 protected band.
                // s1c[28+pe] is the pre-increment cumulative intv
                // cursor; == 0 iff magic 31 has never produced intv
                // output for this PE, so this is the first nonzero
                // tile for that PE.
                //
                // Magic-31 seam-metadata SPM chains (4 per PE: first
                // lo, first hi under the s1c[28+pe]==0 gate, plus
                // last lo and last hi unconditionally). Each chain
                // is gr[11] = spm[...]; 3 x //NOP; s1c[X] = gr[11];
                // The 3-NOP gap makes the consumer slot-safe — it
                // lands in cycle N+2 regardless of load slot, so
                // every chain is LEGAL under AC-7. The serial-
                // through-gr[11] discipline keeps BL-20260417-ctrl-
                // sync-gr intact (gr[12]/gr[13]/gr[7..10] reserved).
                // Enumeration in .humanize/rlcr/2026-04-20_20-46-30/
                // ac11-audit-table.md.
                for (int pe = 0; pe < 4; pe++) {
                    gr[11] = s1c[200+pe];                   // s1c nis
                    //NOP                                    // s1c 1-cycle gap
                    int nis = gr[11];
                    if (nis == 0) continue;
                    int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                    int first_src = pe_spm + i_off;
                    int last_src  = first_src + (nis - 1) * 2;
                    gr[11] = s1c[28+pe];                    // s1c cum
                    //NOP                                    // s1c 1-cycle gap
                    int cum = gr[11];
                    if (cum == 0) {
                        gr[11] = spm[first_src];            // mv: SPM->gr
                        //NOP                                // SPM lat 1/3 (AC-11 slot-safe)
                        //NOP                                // SPM lat 2/3
                        //NOP                                // SPM lat 3/3
                        s1c[176+pe] = gr[11];               // mv: gr->s1c
                        gr[11] = spm[first_src + 1];        // mv: SPM->gr
                        //NOP                                // SPM lat 1/3 (AC-11 slot-safe)
                        //NOP                                // SPM lat 2/3
                        //NOP                                // SPM lat 3/3
                        s1c[180+pe] = gr[11];               // mv: gr->s1c
                    }
                    gr[11] = spm[last_src];                 // mv: SPM->gr
                    //NOP                                    // SPM lat 1/3 (AC-11 slot-safe)
                    //NOP                                    // SPM lat 2/3
                    //NOP                                    // SPM lat 3/3
                    s1c[184+pe] = gr[11];                   // mv: gr->s1c
                    gr[11] = spm[last_src + 1];             // mv: SPM->gr
                    //NOP                                    // SPM lat 1/3 (AC-11 slot-safe)
                    //NOP                                    // SPM lat 2/3
                    //NOP                                    // SPM lat 3/3
                    s1c[188+pe] = gr[11];                   // mv: gr->s1c
                }
                // R8 fix: pre-compute per-PE nds / d_curs / nis /
                // i_curs via gr[11] + 1-NOP staging so the chunk-
                // outer mvdq loops below read from C++-local arrays
                // (register-allocated in real ISA) instead of
                // same-cycle s1c loads.
                int nds[4], d_curs[4], nis[4], i_curs[4];
                for (int pe = 0; pe < 4; pe++) {
                    gr[11] = s1c[196+pe];
                    //NOP                                    // s1c gap
                    nds[pe] = gr[11];
                    gr[11] = s1c[204+pe];
                    //NOP                                    // s1c gap
                    d_curs[pe] = gr[11];
                    gr[11] = s1c[200+pe];
                    //NOP                                    // s1c gap
                    nis[pe] = gr[11];
                    gr[11] = s1c[208+pe];
                    //NOP                                    // s1c gap
                    i_curs[pe] = gr[11];
                }
                // Diag writeback: chunk outer, PE inner, monotonic
                // per-PE MM cursor advances after each mvdq_copy.
                for (int j = 0; j < max_d; j += 8) {
                    for (int pe = 0; pe < 4; pe++) {
                        int w = nds[pe] * 2;
                        if (j >= w) continue;
                        int cnt = w - j;
                        if (cnt > 8) cnt = 8;
                        int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                        mvdq_copy(&mm[d_curs[pe]],
                                  &spm[pe_spm + d_off + j], cnt);
                        d_curs[pe] += cnt;
                    }
                }
                // Intv writeback: same pattern, monotonic cursor.
                for (int j = 0; j < max_i; j += 8) {
                    for (int pe = 0; pe < 4; pe++) {
                        int w = nis[pe] * 2;
                        if (j >= w) continue;
                        int cnt = w - j;
                        if (cnt > 8) cnt = 8;
                        int pe_spm = pe * SPM_BANK_GROUP_SIZE;
                        mvdq_copy(&mm[i_curs[pe]],
                                  &spm[pe_spm + i_off + j], cnt);
                        i_curs[pe] += cnt;
                    }
                }
                // Write back advanced cursors to s1c.
                for (int pe = 0; pe < 4; pe++) {
                    s1c[204+pe] = d_curs[pe];
                    s1c[208+pe] = i_curs[pe];
                }
                // Advance persistent per-PE cumulative counts AFTER
                // the seam-write gate has sampled s1c[28+pe].
                // ISA lowering: each s1c += s1c stages through
                // gr[11] load + gr[1] stash + second gr[11] load +
                // add + RAW barrier + store.
                for (int pe = 0; pe < 4; pe++) {
                    gr[11] = s1c[196+pe];
                    //NOP                                    // s1c gap
                    gr[1]  = gr[11];
                    gr[11] = s1c[20+pe];
                    //NOP                                    // s1c gap
                    gr[11] = gr[11] + gr[1];
                    //NOP                                    // RAW barrier
                    s1c[20+pe] = gr[11];
                    gr[11] = s1c[200+pe];
                    //NOP                                    // s1c gap
                    gr[1]  = gr[11];
                    gr[11] = s1c[28+pe];
                    //NOP                                    // s1c gap
                    gr[11] = gr[11] + gr[1];
                    //NOP                                    // RAW barrier
                    s1c[28+pe] = gr[11];
                }
                gr[2] += DEDUP_TILE;
            }
        } else if (magic_id == 32) {
            // Dedup finalize: gather diag+intv outputs from MM to
            // diag_base / MM_INTV. Boundary merge-adjacent for intv.
            // gr[4]=MM_SORT_BUF, gr[7]=MM_DEDUP_INTV_OUT.
            // s1c: [16..19]=diag_out_base, [20..23]=diag_out_cursor,
            //   [24..27]=intv_out_base, [28..31]=intv_out_cursor.
            //
            // Magic 32 has zero SPM loads: it reads only mm[]
            // (waitLSQ-disciplined) and s1c[] (1-cycle rule-8
            // latency). AC-7 compliant by construction. See
            // .humanize/rlcr/2026-04-20_20-46-30/ac11-audit-table.md.
            {
                auto &gr = main_addressing_register;
                int *mm = gwfa_get_mm();
                constexpr int DIAG_CAP_V2 = (16 << 20);
                constexpr int MM_INTV2 = DIAG_CAP_V2 * 6;
                // s1c[144] stages through gr[11] with 1-NOP gap.
                gr[11] = s1c[144];
                //NOP                                       // s1c gap
                int diag_base   = gr[11]; // original diag_base
                int mm_sort_buf = gr[4];
                int mm_intv_out = gr[7];

                // Gather deduped diags → diag_base
                // Bulk mvdq per PE, boundary max-merge at PE seams only.
                // Within each PE, output is already unique (no dup vd).
                // ISA lowering: s1c loads route through gr[11] with
                // 1-NOP gap; MM boundary reads route through gr[11]
                // with // waitLSQ + //NOP settle before consumer.
                int n_a_final = 0;
                uint32_t last_vd = 0xFFFFFFFF;
                for (int pe = 0; pe < 4; pe++) {
                    gr[11] = s1c[16 + pe];                   // s1c base
                    //NOP                                     // s1c 1-cycle gap
                    int base = gr[11];
                    gr[11] = s1c[20 + pe];                   // s1c cnt
                    //NOP                                     // s1c 1-cycle gap
                    int cnt = gr[11];
                    if (cnt <= 0) continue;
                    int skip = 0;
                    // Boundary check: first element vs last output
                    if (n_a_final > 0) {
                        gr[11] = mm[mm_sort_buf + base*2];   // MM load vd0
                        // waitLSQ
                        //NOP                                 // LSQ settle
                        if ((uint32_t)gr[11] == last_vd) {
                            gr[11] = mm[mm_sort_buf + base*2 + 1];  // MM k0
                            // waitLSQ
                            //NOP                             // LSQ settle
                            int k0 = gr[11];
                            gr[11] = mm[diag_base+(n_a_final-1)*2+1]; // MM pk
                            // waitLSQ
                            //NOP                             // LSQ settle
                            if (k0 > gr[11])
                                mm[diag_base+(n_a_final-1)*2+1] = k0;
                            skip = 1; // skip merged element
                        }
                    }
                    // Bulk mvdq copy interior (skip boundary element)
                    int src = mm_sort_buf + (base + skip) * 2;
                    int dst = diag_base + n_a_final * 2;
                    int words = (cnt - skip) * 2;
                    for (int j = 0; j < words; j += 8) {
                        int c = words - j; if (c > 8) c = 8;
                        mvdq_copy(&mm[dst + j], &mm[src + j], c);
                    }
                    n_a_final += cnt - skip;
                    if (cnt > skip) {
                        gr[11] = mm[mm_sort_buf
                            + (base + cnt - 1) * 2];         // MM load last_vd
                        // waitLSQ
                        //NOP                                 // LSQ settle
                        last_vd = (uint32_t)gr[11];
                    }
                }
                // Gather intv from MM_DEDUP_INTV_OUT → MM_INTV
                // Gather intv: bulk mvdq per PE interior, s1c-based
                // seam merge at PE boundaries only. PE 23 already
                // merges adjacent intvs within each PE's output.
                // Boundary compare uses s1c[176..191] (written by
                // magic 31 during writeback): first intv lo/hi at
                // s1c[176+pe]/s1c[180+pe], last intv lo/hi at
                // s1c[184+pe]/s1c[188+pe]. S1c rule-8 latency is
                // 1 cycle, vs MM waitLSQ; no MM reads in merge.
                int intv_n = 0;
                uint32_t last_intv_hi = 0;
                for (int pe = 0; pe < 4; pe++) {
                    gr[11] = s1c[24 + pe];                   // s1c base
                    //NOP                                     // s1c 1-cycle gap
                    int base = gr[11];
                    gr[11] = s1c[28 + pe];                   // s1c cnt
                    //NOP                                     // s1c 1-cycle gap
                    int cnt = gr[11];
                    if (cnt <= 0) continue;
                    int skip = 0;
#ifdef PLAN2A_SEAM_ASSERT
                    // AC-9 evidence hook: confirm the s1c first/last
                    // seam values written by magic 31 match the
                    // first/last intv observed in MM for this PE's
                    // cumulative output region. Enable with
                    // `-DPLAN2A_SEAM_ASSERT` and re-run mode 1.
                    {
                        int mm_first_lo = mm[mm_intv_out + base*2];
                        int mm_first_hi = mm[mm_intv_out + base*2 + 1];
                        int mm_last_lo  = mm[mm_intv_out
                            + (base + cnt - 1) * 2];
                        int mm_last_hi  = mm[mm_intv_out
                            + (base + cnt - 1) * 2 + 1];
                        assert(s1c[176+pe] == mm_first_lo
                               && "AC-9 first-lo mismatch");
                        assert(s1c[180+pe] == mm_first_hi
                               && "AC-9 first-hi mismatch");
                        assert(s1c[184+pe] == mm_last_lo
                               && "AC-9 last-lo mismatch");
                        assert(s1c[188+pe] == mm_last_hi
                               && "AC-9 last-hi mismatch");
                        fprintf(stderr,
                            "[SEAM pe=%d] s1c_first=0x%x/0x%x "
                            "mm_first=0x%x/0x%x s1c_last=0x%x/0x%x "
                            "mm_last=0x%x/0x%x cnt=%d base=%d\n",
                            pe, (unsigned)s1c[176+pe],
                            (unsigned)s1c[180+pe],
                            (unsigned)mm_first_lo,
                            (unsigned)mm_first_hi,
                            (unsigned)s1c[184+pe],
                            (unsigned)s1c[188+pe],
                            (unsigned)mm_last_lo,
                            (unsigned)mm_last_hi, cnt, base);
                    }
#endif
                    // Boundary merge: use s1c first intv of this PE.
                    // s1c reads stage through gr[11] with 1-NOP gap.
                    if (intv_n > 0) {
                        gr[11] = s1c[176 + pe];              // s1c lo0
                        //NOP                                 // s1c 1-cycle gap
                        uint32_t lo0 = (uint32_t)gr[11];
                        gr[11] = s1c[180 + pe];              // s1c hi0
                        //NOP                                 // s1c 1-cycle gap
                        uint32_t hi0 = (uint32_t)gr[11];
                        if (lo0 <= last_intv_hi) {
                            // Merge into last output's hi
                            if (hi0 > last_intv_hi) {
                                last_intv_hi = hi0;
                                mm[MM_INTV2+(intv_n-1)*2+1]
                                    = (int)hi0;
                            }
                            skip = 1;
                        }
                    }
                    // Bulk mvdq copy PE interior (skip first if merged)
                    int src = mm_intv_out + (base + skip) * 2;
                    int dst = MM_INTV2 + intv_n * 2;
                    int words = (cnt - skip) * 2;
                    for (int j = 0; j < words; j += 8) {
                        int c = words - j; if (c > 8) c = 8;
                        mvdq_copy(&mm[dst + j], &mm[src + j], c);
                    }
                    intv_n += cnt - skip;
                    // Last hi for next PE seam compare: s1c, not MM.
                    // cnt==skip (single-element merged away) path:
                    // last_intv_hi already reflects the merged tail
                    // (possibly bumped to hi0 at the merge branch),
                    // so no further update is needed here.
                    if (cnt > skip) {
                        gr[11] = s1c[188 + pe];
                        //NOP                                 // s1c 1-cycle gap
                        last_intv_hi = (uint32_t)gr[11];
                    }
                }

                // Clear sort/dedup SPM region per PE
                for (int pe = 0; pe < 4; pe++) {
                    int *s = &SPM_unit->buffer[
                        pe * SPM_BANK_GROUP_SIZE];
                    memset(s, 0,
                        (GWFA_Q_START / 4) * sizeof(int));
                }
                memset(s1c, 0, 144 * sizeof(int));
                // Clear seam metadata band (plan 2a AC-8)
                memset(&s1c[176], 0, 16 * sizeof(int));
                // Reset active bases after dedup gather
                s1c[152] = MM_INTV2;    // intv gathered to MM_INTV
                s1c[153] = diag_base;   // diags gathered to diag_base
                gwfa_finalize_sync(n_a_final, (size_t)intv_n);
                gr[15] = n_a_final;
                gr[28] = intv_n;
                if (n_a_final == 0) write_spm_magic(32767, 1);
            }
        } else if (magic_id == 6) {
            //WFA initializations
            int MEM_BLOCK_SIZE = 32;
            int PADDING_SIZE = 30;
            int EXTRA_O_LOAD_ADDR = 7*MEM_BLOCK_SIZE;
            int BLOCK_0_START = 0;
            int BLOCK_1_START = MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE;
            int MAX_WF_LEN = 16384;
            int N_WFS = 5;
            int PAST_WFS_SIZE = N_WFS * 3 * MAX_WF_LEN;
            //4 previous scores, 3 affine wavefronts, each wavefront MEM_BLOCK entries. Rotating buffer
            auto past_wf_at = [&](int wf_i, int affine_i, int idx) -> int& {
                return s2->buffer[(wf_i * 3 + affine_i) * MAX_WF_LEN + idx];
            };
            static std::ofstream magic_wfs_out("magic_wfs_out.txt");
            assert(S2_BUFFER_INTS >= PAST_WFS_SIZE);
            int (&gr)[MAIN_ADDR_REGISTER_NUM] = main_addressing_register;
            auto mvdq = [&](int dst, int src, bool toSPM){
                //TODO this is not realistic. We need to access blocks not arbitrary location.
                for (int i =0; i < 8; i++){
                    if (toSPM){
                        SPM_unit->buffer[dst+i] = s2->buffer[src+i];
                    } else {
                        s2->buffer[dst+i] = SPM_unit->buffer[src+i];
                    }
                }
            };
            auto mvdqi = [&](int dst, int val, bool toSPM){
                for (int i =0; i < 8; i++){
                    if (toSPM){
                        SPM_unit->buffer[dst+i] = val;
                    } else {
                        s2->buffer[dst+i] = val;
                    }
                }
            };

            // Display inputs and outputs for the same wavefront block
            int current_wf_size = main_addressing_register[12];
            int this_block_start = main_addressing_register[10];
            int next_block_start = main_addressing_register[8];
            int block_iter = main_addressing_register[9];
            int display_block_iter = block_iter;  // Display previous block (just computed)
            int write_wf_i = gr[3] + 1;
            if (write_wf_i >= N_WFS) write_wf_i = 0;
            int width = 3;
            int k = 0;
            static std::ofstream magic_spm_out("magic_spm_out.txt");

            // Calculate PE distribution
            int n_diags_per_pe = current_wf_size / 4 + 1; //ceil div

            // DEBUG: dump SPM output regions (M/D/I) for comparison with past_wfs
            magic_spm_out << "Block " << display_block_iter << " (Score " << current_wf_size - 1 << ") SPM_OUT:" << std::endl << std::endl;
            auto dump_spm_region = [&](int region_offset) {
                for (int i = 0; i < 4; i++) {
                    int start = i * n_diags_per_pe + display_block_iter * MEM_BLOCK_SIZE;
                    int end_this_pe_comp_region = std::min(n_diags_per_pe * (i + 1), current_wf_size);
                    int end = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                    for (int j = start; j < end; j++) {
                        magic_spm_out << std::setw(width) << SPM_unit->access_magic(i, region_offset + this_block_start + j - start);
                    }
                }
                magic_spm_out << std::endl;
            };
            // M output region (4*MEM_BLOCK_SIZE), then D (5*MEM_BLOCK_SIZE), then I (6*MEM_BLOCK_SIZE)
            dump_spm_region(4 * MEM_BLOCK_SIZE);
            dump_spm_region(5 * MEM_BLOCK_SIZE);
            dump_spm_region(6 * MEM_BLOCK_SIZE);
            // Extra O load scratch region (two values per PE)
            magic_spm_out << "EXTRA_O:" << std::endl;
            for (int i = 0; i < 4; i++) {
                int base = EXTRA_O_LOAD_ADDR;
                magic_spm_out << std::setw(width) << SPM_unit->access_magic(i, base)
                              << std::setw(width) << SPM_unit->access_magic(i, base + 1);
            }
            magic_spm_out << std::endl;

            // Section header
            magic_wfs_out << "Block " << display_block_iter << " (Score " << current_wf_size - 1 << "):" << std::endl << std::endl;

            // Display INPUT wavefronts (O, M, I, D) from SPM
            // Read from THIS_BLOCK (the block that was just computed)

            //display O
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + display_block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 0 * MEM_BLOCK_SIZE + this_block_start + j - start);
                    k++;
                }
            }
            magic_wfs_out << std::endl;

            //display M
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + display_block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 1 * MEM_BLOCK_SIZE + this_block_start + j - start);
                    k++;
                }
            }
            magic_wfs_out << std::endl;

            //display I
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + display_block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 2 * MEM_BLOCK_SIZE + this_block_start + j - start);
                    k++;
                }
            }
            magic_wfs_out << std::endl;

            //display D
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + display_block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 3 * MEM_BLOCK_SIZE + this_block_start + j - start);
                    k++;
                }
            }
            magic_wfs_out << std::endl;

            // Display OUTPUT wavefronts (M, D, I) from past_wfs
            for (int affine_id : {2, 0, 1}) {  // M, D, I order
                for (int pe_i = 0; pe_i < 4; pe_i++) {
                    int start = pe_i * n_diags_per_pe + display_block_iter * MEM_BLOCK_SIZE;
                    int end_pe = std::min(n_diags_per_pe * (pe_i + 1), current_wf_size);
                    int end = std::min(start + MEM_BLOCK_SIZE, end_pe);
                    for (int j = start; j < end; j++) {
                        magic_wfs_out << std::setw(width) << past_wf_at(write_wf_i, affine_id, j);
                    }
                }
                magic_wfs_out << std::endl;
            }

            magic_wfs_out << std::endl;
        } else {
            fprintf(stderr, "ERROR: PE_ARRAY PC=%d cycle=%d unknown magic id %d (payload %d mask 0x%x).\n",
                    *PC, cycle, magic_id, magic_payload, magic_mask);
            exit(-1);
        }

        (*PC)++;
    } else if (opcode == 0) {              // add rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = read_gr_src(src, rs1);
        add_b = read_gr_src(src, rs2);
        sum = add_a + add_b;
        set_output_dest(dest, rd, sum);
#ifdef PROFILE
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 1) {       // sub rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = read_gr_src(src, rs1);
        add_b = read_gr_src(src, rs2);
        sum = add_a - add_b;
        set_output_dest(dest, rd, sum);
#ifdef PROFILE
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 2) {       // addi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = imm;
        add_b = read_gr_src(src, rs2);
        sum = add_a + add_b;
        set_output_dest(dest, rd, sum);
#ifdef PROFILE
        printf("addi gr[%d] %d gr[%d] (%d %d %d)\n", rd, imm, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 3) {       // set_8 rd rs2
        rd = reg_imm_0;
        rs2 = reg_1;
        memcpy(rs, &main_addressing_register[rs2], 4*sizeof(int8_t));

        for (i = 0; i < 4; i++) {
            rs[i] = main_addressing_register[rs2] & 0xFF;
        }
        memcpy(get_output_dest(dest,rd), rs, 4*sizeof(int8_t));
#ifdef PROFILE
        printf("set_8 gr[%d] gr[%d] (%d %lx)\n", rd, rs2, main_addressing_register[rs2], main_addressing_register[rd]);
#endif
        (*PC)++;
    } else if (opcode == 4) {       // si dest imm/reg(reg(++))
#ifdef PROFILE
    if (simd)
        printf("Store %lx to ", sext_imm_1);
    else
        printf("Store %d to ", sext_imm_1);
#endif
        LoadResult immediate_data{};
        immediate_data.data[0] = sext_imm_1;
        store(dest, reg_immBar_flag_0, sext_imm_0, reg_0, immediate_data, simd);
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        (*PC)++;
    } else if (opcode == 5) {       // mv dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("Move ");
#endif
        if (src == CTRL_S2 && dest == CTRL_SPM) {
            int s2Addr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int spmAddr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            if (lsq->spmBankFull(spmAddr) ||
                lsq->s2BankFull(s2Addr)) {
                lsqFullStalls++;
                return 0;
            }
#ifdef PROFILE
            printf("S2[%d] -> SPM[%d] via LSQ\n",
                   s2Addr, spmAddr);
#endif
            lsq->enqueueS2ToSpm(
                s2Addr, spmAddr, true);
        } else if (src == CTRL_SPM && dest == CTRL_S2) {
            int spmAddr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int s2Addr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            if (lsq->spmBankFull(spmAddr) ||
                lsq->s2BankFull(s2Addr)) {
                lsqFullStalls++;
                return 0;
            }
#ifdef PROFILE
            printf("SPM[%d] -> S2[%d] via LSQ\n",
                   spmAddr, s2Addr);
#endif
            lsq->enqueueSpmToS2(
                spmAddr, s2Addr, true);
        } else {
            data = load(src, reg_immBar_flag_1,
                        sext_imm_1, reg_1, simd);
            store(dest, reg_immBar_flag_0,
                  sext_imm_0, reg_0, data, simd);
        }
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1]++;
        (*PC)++;
    } else if (opcode == CTRL_MVDQ) {      // mvdq dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("MoveDoubleQuad ");
#endif
        int dest_addr = 0;
        int src_addr = 0;
        if (reg_immBar_flag_0)
            dest_addr = main_addressing_register[sext_imm_0] + main_addressing_register[reg_0];
        else
            dest_addr = sext_imm_0 + main_addressing_register[reg_0];
        if (reg_immBar_flag_1)
            src_addr = main_addressing_register[sext_imm_1] + main_addressing_register[reg_1];
        else
            src_addr = sext_imm_1 + main_addressing_register[reg_1];

        bool src_is_spm = (src == CTRL_SPM);
        bool src_is_s2 = (src == CTRL_S2);
        bool dest_is_spm = (dest == CTRL_SPM);
        bool dest_is_s2 = (dest == CTRL_S2);

        if (!((src_is_spm && dest_is_s2) || (src_is_s2 && dest_is_spm))) {
            fprintf(stderr, "main mvdq only supports SPM <-> S2. src=%d dest=%d PC=%d\n", src, dest, *PC);
            exit(-1);
        }

        int src_limit = src_is_spm ? SPM_unit->buffer_size : s2->buffer_size;
        int dest_limit = dest_is_spm ? SPM_unit->buffer_size : s2->buffer_size;
        if (src_addr < 0 || src_addr + 8 > src_limit) {
            fprintf(stderr, "main mvdq src addr %d out of bounds (limit %d). PC=%d\n", src_addr, src_limit, *PC);
            exit(-1);
        }
        if (dest_addr < 0 || dest_addr + 8 > dest_limit) {
            fprintf(stderr, "main mvdq dest addr %d out of bounds (limit %d). PC=%d\n", dest_addr, dest_limit, *PC);
            exit(-1);
        }

        // Determine S2 and SPM side addresses
        int s2A = src_is_s2 ? src_addr : dest_addr;
        int spmA = dest_is_spm ? dest_addr:src_addr;
        bool s2ToSpm = src_is_s2 && dest_is_spm;
        bool srcOdd = src_addr % 2 != 0;
        bool dstOdd = dest_addr % 2 != 0;

        // Capacity check: compute all entry addrs.
        // Even side: 4 doubles. Odd side: sgl,3dbl,sgl
        int spmList[5], s2List[5];
        int nSpm = 0, nS2 = 0;
        if (spmA % 2 == 0) {
            for (i = 0; i < 4; i++)
                spmList[nSpm++] = spmA + 2*i;
        } else {
            spmList[nSpm++] = spmA;
            spmList[nSpm++] = spmA + 1;
            spmList[nSpm++] = spmA + 3;
            spmList[nSpm++] = spmA + 5;
            spmList[nSpm++] = spmA + 7;
        }
        if (s2A % 2 == 0) {
            for (i = 0; i < 4; i++)
                s2List[nS2++] = s2A + 2*i;
        } else {
            s2List[nS2++] = s2A;
            s2List[nS2++] = s2A + 1;
            s2List[nS2++] = s2A + 3;
            s2List[nS2++] = s2A + 5;
            s2List[nS2++] = s2A + 7;
        }
        if (!lsq->canEnqueue(
                spmList, nSpm, s2List, nS2)) {
            lsqFullStalls++;
            return 0;
        }

        // Helper lambdas for enqueue
        auto enqPaired = [&](int s2, int spm,
                             bool sd) {
            if (s2ToSpm)
                lsq->enqueueS2ToSpm(s2, spm, sd);
            else
                lsq->enqueueSpmToS2(spm, s2, sd);
        };

        if (!srcOdd && !dstOdd) {
            // Both even: 4 paired doubles
            for (i = 0; i < 4; i++)
                enqPaired(s2A + 2*i,
                          spmA + 2*i, false);

        } else if (srcOdd && dstOdd) {
            // Both odd: 5 paired (sgl,dbl,dbl,dbl,sgl)
            enqPaired(s2A, spmA, true);
            enqPaired(s2A+1, spmA+1, false);
            enqPaired(s2A+3, spmA+3, false);
            enqPaired(s2A+5, spmA+5, false);
            enqPaired(s2A+7, spmA+7, true);

        } else if (srcOdd && !dstOdd) {
            // src odd, dest even.
            // Writes: 4 doubles at even dest addrs.
            // Reads: 5 lines from odd source.
            // Create writes and reads separately
            // since srcDstAddr != read addr.
            if (s2ToSpm) {
                for (i = 0; i < 4; i++)
                    lsq->enqueueSpmWriteOnly(
                        spmA + 2*i,
                        s2A + 2*i, false);
                // 5 S2 reads covering all src lines
                for (i = 0; i < 4; i++)
                    lsq->enqueueS2ReadOnly(
                        s2A + 2*i);
                lsq->enqueueS2ReadOnly(s2A + 7);
            } else {
                for (i = 0; i < 4; i++)
                    lsq->enqueueS2WriteOnly(
                        s2A + 2*i,
                        spmA + 2*i, false);
                for (i = 0; i < 4; i++)
                    lsq->enqueueSpmReadOnly(
                        spmA + 2*i);
                lsq->enqueueSpmReadOnly(spmA + 7);
            }

        } else {
            // src even, dest odd.
            // Writes: 5 (sgl, dbl, dbl, dbl, sgl)
            //   at odd dest boundary addrs.
            // Reads: 4 doubles from even source.
            // Create separately.
            if (s2ToSpm) {
                lsq->enqueueSpmWriteOnly(
                    spmA, s2A, true);
                for (i = 0; i < 3; i++)
                    lsq->enqueueSpmWriteOnly(
                        spmA + 1 + 2*i,
                        s2A + 1 + 2*i, false);
                lsq->enqueueSpmWriteOnly(
                    spmA + 7, s2A + 7, true);
                for (i = 0; i < 4; i++)
                    lsq->enqueueS2ReadOnly(
                        s2A + 2*i);
            } else {
                lsq->enqueueS2WriteOnly(
                    s2A, spmA, true);
                for (i = 0; i < 3; i++)
                    lsq->enqueueS2WriteOnly(
                        s2A + 1 + 2*i,
                        spmA + 1 + 2*i, false);
                lsq->enqueueS2WriteOnly(
                    s2A + 7, spmA + 7, true);
                for (i = 0; i < 4; i++)
                    lsq->enqueueSpmReadOnly(
                        spmA + 2*i);
            }
        }

        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0] += 8;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1] += 8;
        (*PC)++;
    } else if (opcode == CTRL_MVDQI) {      // mvdqi dest imm/reg(reg(++)) imm
#ifdef PROFILE
        printf("MoveDoubleQuadImm ");
#endif
        int dest_addr = 0;
        if (reg_immBar_flag_0)
            dest_addr = main_addressing_register[sext_imm_0] + main_addressing_register[reg_0];
        else
            dest_addr = sext_imm_0 + main_addressing_register[reg_0];

        bool dest_is_spm = (dest == CTRL_SPM);
        bool dest_is_s2 = (dest == CTRL_S2);
        if (!(dest_is_spm || dest_is_s2)) {
            fprintf(stderr, "main mvdqi only supports SPM or S2 destinations. dest=%d PC=%d\n", dest, *PC);
            exit(-1);
        }

        int dest_limit = dest_is_spm ? SPM_unit->buffer_size : s2->buffer_size;
        if (dest_addr < 0 || dest_addr + 7 >= dest_limit) {
            fprintf(stderr, "main mvdqi dest addr %d out of bounds (limit %d). PC=%d\n", dest_addr, dest_limit, *PC);
            exit(-1);
        }

        int imm_val = sext_imm_1;
        if (dest_is_spm) {
            for (i = 0; i < 8; i++)
                SPM_unit->buffer[dest_addr + i] = imm_val;
        } else {
            for (i = 0; i < 8; i++)
                s2->buffer[dest_addr + i] = imm_val;
        }

        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0] += 8;
        (*PC)++;
//     } else if (opcode == 6) {       // add_8 rd rs1 rs2
//         rd = reg_imm_0;
//         rs1 = reg_imm_1;
//         rs2 = reg_1;
//         memcpy(rs, &main_addressing_register[rs1], 4 * sizeof(int8_t));
//         memcpy(rs_, &main_addressing_register[rs2], 4 * sizeof(int8_t));
//         for (i = 0; i < 4; i++) rd_[i] = rs[i] + rs_[i];
//         memcpy(&main_addressing_register[rd], rd_, 4 * sizeof(int8_t));
// #ifdef PROFILE
//         printf("add_8 gr[%d] gr[%d] gr[%d] (%lx %lx %lx)\n", rd, rs1, rs2, main_addressing_register[rd], main_addressing_register[rs1], main_addressing_register[rs2]);
// #endif
//         (*PC)++;
//     } else if (opcode == 7) {       // addi_8 rd imm rs2
//         rd = reg_imm_0;
//         rs2 = reg_1;
//         memcpy(rs_, &main_addressing_register[rs2], 4 * sizeof(int8_t));
//         for (i = 0; i < 4; i++) rd_[i] = reg_imm_1 && 0xFF + rs_[i];
//         memcpy(&main_addressing_register[rd], rd_, 4 * sizeof(int8_t));
// #ifdef PROFILE
//         printf("addi_8 gr[%d] %d gr[%d] (%lx %d %lx)\n", rd, sext_imm_1, rs2, main_addressing_register[rd], sext_imm_1, main_addressing_register[rs2]);
// #endif
//         (*PC)++;
    } else if (opcode == CTRL_BARRIER) {
        if (!lsq->hasPendingOps(SPM_unit, s2)) {
#ifdef PROFILE
            printf("Barrier: LSQ empty, advance\n");
#endif
            (*PC)++;
        }
#ifdef PROFILE
        else {
            printf("Barrier: LSQ stall\n");
        }
#endif
    } else if (opcode == 8) {       // bne rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
        if (rs2 == 13) controllerSpinCycles++;
#ifdef PROFILE
        printf("bne %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = read_gr_src(src, rs1);
        else comp_0 = sext_imm_1;
        comp_1 = read_gr_src(src, rs2);
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 != comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 9) {       // beq rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("beq %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = read_gr_src(src, rs1);
        else comp_0 = sext_imm_1;
        comp_1 = read_gr_src(src, rs2);
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 == comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 10) {       // bge rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("bge %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = read_gr_src(src, rs1);
        else comp_0 = sext_imm_1;
        comp_1 = read_gr_src(src, rs2);
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 >= comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 11) {       // blt rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("blt %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = read_gr_src(src, rs1);
        else comp_0 = sext_imm_1;
        comp_1 = read_gr_src(src, rs2);
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 < comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 12) {      // jump
        *PC = *PC + sext_imm_0;
#ifdef PROFILE
        printf("jump %d\n", sext_imm_0);
#endif
    } else if (opcode == 13) {      // set PE_PC
        for (i = 0; i < setting; i++) {
            pe_unit[i]->PC[0] = sext_imm_0;
            pe_unit[i]->PC[1] = sext_imm_0;
        }
#ifdef PROFILE
        printf("set PE PC to %d.\n", sext_imm_0);
#endif
        (*PC)++;
    } else if (opcode == 14) {      // None
        (*PC)++;
#ifdef PROFILE
        printf("No-op.\n");
#endif
    } else if (opcode == 15) {      // halt
#ifdef PROFILE
        printf("halt.\n");
#endif
        return -1;
    } else if (opcode == CTRL_SHIFTI_R) {      // SHIFT_R
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = read_gr_src(src, rs2);
        int shift_result = operand1 / (1 << reg_imm_1);
        set_output_dest(dest, rd, shift_result);
        (*PC)++;
#ifdef PROFILE
        printf("rShift gr[%d] = gr[%d] >> %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SHIFTI_L) {      // SHIFT_L
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = read_gr_src(src, rs2);
        int shift_result = operand1 << reg_imm_1;
        set_output_dest(dest, rd, shift_result);
        (*PC)++;
#ifdef PROFILE
        printf("lShift gr[%d] = gr[%d] << %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_ANDI) {      // AND
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = read_gr_src(src, rs2);
        int and_result = operand1 & reg_imm_1;
        set_output_dest(dest, rd, and_result);
        (*PC)++;
#ifdef PROFILE
        printf("andi gr[%d] = gr[%d] & %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SUBI) {       // subi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = read_gr_src(src, rs2);
        add_b = imm;
        sum = add_a - add_b;
        set_output_dest(dest, rd, sum);
#ifdef PROFILE
        printf("subi gr[%d] gr[%d] %d (%d %d %d)\n", rd, rs2, imm, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == CTRL_CALL) {
        ras = *PC + 1;
        *PC = sext_imm_0;
#ifdef PROFILE
        printf("call %d (ras=%d)\n", sext_imm_0, ras);
#endif
    } else if (opcode == CTRL_RET) {
        *PC = ras;
#ifdef PROFILE
        printf("ret (PC=%d)\n", ras);
#endif
    } else if (opcode == CTRL_RETNE) {
        rs1 = sext_imm_1;
        rs2 = reg_1;
        if (reg_immBar_flag_1) comp_0 = read_gr_src(src, rs1);
        else comp_0 = sext_imm_1;
        comp_1 = read_gr_src(src, rs2);
        if (comp_0 != comp_1) *PC = ras;
        else (*PC)++;
#ifdef PROFILE
        printf("retne %d %d (PC=%d)\n", comp_0, comp_1, *PC);
#endif
    } else {
        fprintf(stderr, "main control instruction opcode error. opcode = %d\n", opcode);
        exit(-1);
    }
    return 0;
}

int* pe_array::get_output_dest(int dest, int rd){
    if (dest == CTRL_GR) {
        return &main_addressing_register[rd];
    } else if (dest == CTRL_OUT_BUF) {
        return &output_buffer[rd];
    } else if (dest == CTRL_OUT_PORT) {
        return &store_data;
    } else if (dest == CTRL_GR_LO || dest == CTRL_GR_HI) {
        // Subregister write: caller must use set_output_dest instead
        fprintf(stderr, "get_output_dest: use set_output_dest for gr_lo/hi. PC=%d\n", main_PC);
        exit(-1);
    } else {
        fprintf(stderr,
                "Only dest CTRL_GR and CTRL_OUT_BUF are supported for pe_array, non MV CTRL instr. dest = %d. PC = %d\n", dest, main_PC);
        exit(-1);
    }
}

void pe_array::set_output_dest(int dest, int rd, int val) {
    if (dest == CTRL_GR) {
        main_addressing_register[rd] = val;
    } else if (dest == CTRL_GR_LO) {
        int old = main_addressing_register[rd];
        main_addressing_register[rd] = (old & (int)0xFFFF0000) | (val & 0xFFFF);
    } else if (dest == CTRL_GR_HI) {
        int old = main_addressing_register[rd];
        main_addressing_register[rd] = (old & 0x0000FFFF) | ((val & 0xFFFF) << 16);
    } else if (dest == CTRL_OUT_BUF) {
        output_buffer[rd] = val;
    } else if (dest == CTRL_OUT_PORT) {
        store_data = val;
    } else {
        fprintf(stderr, "set_output_dest unsupported dest=%d PC=%d\n", dest, main_PC);
        exit(-1);
    }
}

int pe_array::read_gr_src(int src, int idx) {
    int val = main_addressing_register[idx];
    if (src == CTRL_GR_LO) return (int)(int16_t)(val & 0xFFFF);
    if (src == CTRL_GR_HI) return (int)(int16_t)((val >> 16) & 0xFFFF);
    return val;
}

int pe_array::decode_output(unsigned long instruction, int* PC, int simd, int setting, int main_instruction_setting) {

#ifdef PROFILE
    printf("main\t");
#endif
    int i, rd, rs1, rs2, imm, sum = 0, add_a = 0, add_b = 0;
    LoadResult data{};
    int8_t rs[4];
        
    unsigned long dest_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long src_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long reg_immBar_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    unsigned long reg_auto_increasement_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    unsigned long reg_imm_0_sign_bit_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    unsigned long reg_imm_0_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_0_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_immBar_flag_1_mask = (unsigned long)1 << (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_auto_increasement_flag_1_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_imm_1_sign_bit_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    unsigned long reg_imm_1_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_1_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << CTRL_OPCODE_WIDTH;
    unsigned long opcode_mask = (unsigned long)((1 << CTRL_OPCODE_WIDTH) - 1);

    int dest = (instruction & dest_mask) >> (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    int src = (instruction & src_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    int reg_immBar_flag_0 = (instruction & reg_immBar_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    int reg_auto_increasement_flag_0 = (instruction & reg_auto_increasement_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    int reg_imm_0 = (instruction & reg_imm_0_mask) >> (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_0_sign_bit = (instruction & reg_imm_0_sign_bit_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    int imm_sign_extend_mask = ~((1 << IMMEDIATE_WIDTH) - 1);
    int sext_imm_0 = reg_imm_0 | (reg_imm_0_sign_bit ? imm_sign_extend_mask : 0);
    int reg_0 = (instruction & reg_0_mask) >> (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_immBar_flag_1 = (instruction & reg_immBar_flag_1_mask) >> (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_auto_increasement_flag_1 = (instruction & reg_auto_increasement_flag_1_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1 = (instruction & reg_imm_1_mask) >> (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1_sign_bit = (instruction & reg_imm_1_sign_bit_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    int sext_imm_1 = reg_imm_1 | (reg_imm_1_sign_bit ? imm_sign_extend_mask : 0);
    int reg_1 = (instruction & reg_1_mask) >> CTRL_OPCODE_WIDTH;
    int opcode = instruction & opcode_mask;

#ifdef PROFILE
    printf("PC = %d\t", *PC);
#endif
    if (main_instruction_setting == MAIN_INSTRUCTION_2) {
        // Arithmetic (opcodes 0-3) now runs pre-PE via
        // decode(). Skip here to avoid double-execution.
        if (opcode <= 3 || opcode == CTRL_CALL
            || opcode == CTRL_RET || opcode == CTRL_RETNE) {
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
        if (((opcode == 4 || opcode == 5)
             && (dest != 5 && dest != 6 && dest != 11
                 && dest != 12 && dest != 13
                 && dest != 14))
            || opcode == 14) {
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    } else if (main_instruction_setting == MAIN_INSTRUCTION_1) {
        if (dest != 5 && dest != 6 && dest != 11 && dest != 12 && dest != 13 && dest != 14) {
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    }

#ifdef DEBUG
    printf("dest: %d src: %d reg_immBar_flag_0: %d reg_auto_increasement_flag_0: %d reg_imm_0_sign_bit: %d sext_imm_0: %d, reg_0: %d reg_immBar_flag_1: %d reg_auto_increasement_flag_1: %d reg_imm_1_sign_bit: %d sext_imm_1: %d reg_1: %d opcode: %d\n", dest, src, reg_immBar_flag_0, reg_auto_increasement_flag_0, reg_imm_0_sign_bit, sext_imm_0, reg_0, reg_immBar_flag_1, reg_auto_increasement_flag_1, reg_imm_1_sign_bit, sext_imm_1, reg_1, opcode);
#endif

    if (opcode == 0) {              // add rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        main_addressing_register[rd] = sum;
#ifdef PROFILE
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
    } else if (opcode == 1) {       // sub rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a - add_b;
        main_addressing_register[rd] = sum;
#ifdef PROFILE
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
    } else if (opcode == 2) {       // addi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = imm;
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        main_addressing_register[rd] = sum;
#ifdef PROFILE
        printf("addi gr[%d] %d gr[%d] (%d %d %d)\n", rd, imm, rs2, sum, add_a, add_b);
#endif
    } else if (opcode == 3) {       // set_8 rd rs2
        rd = reg_imm_0;
        rs2 = reg_1;
        memcpy(rs, &main_addressing_register[rs2], 4*sizeof(int8_t));

        for (i = 0; i < 4; i++) {
            rs[i] = main_addressing_register[rs2] & 0xFF;
        }
        memcpy(&main_addressing_register[rd], rs, 4*sizeof(int8_t));
#ifdef PROFILE
        printf("set_8 gr[%d] gr[%d] (%d %lx)\n", rd, rs2, main_addressing_register[rs2], main_addressing_register[rd]);
#endif
    } else if (opcode == 4) {       // li dest imm/reg(reg(++))
#ifdef PROFILE
    if (simd)
        printf("Store %lx to ", sext_imm_1);
    else
        printf("Store %d to ", sext_imm_1);
#endif
        LoadResult immediate_data{};
        immediate_data.data[0] = sext_imm_1;
        store(dest, reg_immBar_flag_0, sext_imm_0, reg_0, immediate_data, simd);
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
    } else if (opcode == 5) {
#ifdef PROFILE
        printf("Move ");
#endif
        if (src == CTRL_S2 && dest == CTRL_SPM) {
            int s2Addr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int spmAddr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            lsq->enqueueS2ToSpm(
                s2Addr, spmAddr, true);
        } else if (src == CTRL_SPM
                   && dest == CTRL_S2) {
            int spmAddr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int s2Addr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            lsq->enqueueSpmToS2(
                spmAddr, s2Addr, true);
        } else {
            data = load(src, reg_immBar_flag_1,
                        sext_imm_1, reg_1, simd);
            store(dest, reg_immBar_flag_0,
                  sext_imm_0, reg_0, data, simd);
        }
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1]++;
    }
    return 0;
}

void pe_array::show_gr() {
    int i;
    for (i = 0; i < ADDR_REGISTER_NUM; i++)
        printf("main gr[%d] = %d\n", i, main_addressing_register[i]);
}

void pe_array::show_compute_instruction_buffer() {
    int i, j;
    for (i = 0; i < COMP_INSTR_BUFFER_GROUP_NUM; i++)
        for (j = 0; j < COMP_INSTR_BUFFER_GROUP_SIZE; j++)
            printf("compute instruction buffer[%d][%d] = %lx\n", i, j, compute_instruction_buffer[i][j]);
}

int Float2Fix(float exact_value) {
    int MIN_INTEGER = -pow(2, NUM_FRACTION_BITS+NUM_INTEGER_BITS);
    if (exact_value == - std::numeric_limits<float>::infinity())
        return MIN_INTEGER;
    int result = (int)ceil(exact_value * pow(2, NUM_FRACTION_BITS));
    return result;
}

float Fix2Float(int integer) {
    float result = (float)(integer / pow(2, NUM_FRACTION_BITS));
    return result;
}

int Upper_LOG2_accurate(float num){
    float numLog2 = log(num) / log(2);
    int result = Float2Fix(numLog2);
    return result;
}

void pe_array::phmm_show_output_buffer(FILE* fp) {
    float INITIAL_CONDITION_UP = (float)pow(2, 127);
    // float result = log10(pow(2, Fix2Float(output_buffer[0] - Upper_LOG2_accurate(INITIAL_CONDITION_UP))));
    fprintf(fp, "%d\n", output_buffer[0]);
}

void pe_array::chain_show_output_buffer(int n, FILE* fp) {
    int j;
    for (j = 0; j < n; j++) {
        fprintf(fp, "%d\n", output_buffer[j]);
    }
}

void pe_array::bsw_show_output_buffer(FILE* fp) {
    int i, j;
    int8_t output[6][4];
    for (i = 0; i < 6; i++)
        memcpy(output[i], output_buffer+i, 4*sizeof(int8_t));
    for (j = 0; j < 4; j++) {
        fprintf(fp, "%d ", output[0][j]);
        fprintf(fp, "%d ", output[3][j]);
        fprintf(fp, "%d ", output[4][j]);
        fprintf(fp, "%d ", output[1][j]);
        fprintf(fp, "%d ", output[2][j]);
        fprintf(fp, "%d\n", output[5][j]);
    }
}

void pe_array::poa_show_output_buffer(int len_y, int len_x, FILE* fp) {
    int num = len_y * len_x * 2;
    // printf("Output: %d\n", num);
    fprintf(fp, "Output: %d\n", num);
    int i, j, k;
    int iter = len_x * 8;

    for (i = 0; i < len_y/4; i++) {
        fprintf(fp, "%d ", i*iter);
        fprintf(fp, "x x x x x x %d %d \n", output_buffer[i*iter+6], output_buffer[i*iter+7]);
        fprintf(fp, "%d ", i*iter+8);
        fprintf(fp, "x x x x %d %d %d %d \n", output_buffer[i*iter+8+4], output_buffer[i*iter+8+5], output_buffer[i*iter+8+6], output_buffer[i*iter+8+7]);
        fprintf(fp, "%d ", i*iter+16);
        fprintf(fp, "x x %d %d %d %d %d %d \n", output_buffer[i*iter+16+2], output_buffer[i*iter+16+3], output_buffer[i*iter+16+4], output_buffer[i*iter+16+5], output_buffer[i*iter+16+6], output_buffer[i*iter+16+7]);

        for (j = 3; j < len_x-3; j++) {
            fprintf(fp, "%d ", i*iter+j*8);
            for (k = 0; k < 8; k++)
                fprintf(fp, "%d ", output_buffer[i*iter + j*8 + k]);
            fprintf(fp, "\n");
        }

        fprintf(fp, "%d ", i*iter+(len_x-3)*8);
        fprintf(fp, "%d %d %d %d %d %d x x \n", output_buffer[i*iter+(len_x-3)*8], output_buffer[i*iter+(len_x-3)*8+1], output_buffer[i*iter+(len_x-3)*8+2], output_buffer[i*iter+(len_x-3)*8+3], output_buffer[i*iter+(len_x-3)*8+4], output_buffer[i*iter+(len_x-3)*8+5]);
        fprintf(fp, "%d ", i*iter+(len_x-2)*8);
        fprintf(fp, "%d %d %d %d x x x x \n", output_buffer[i*iter+(len_x-2)*8], output_buffer[i*iter+(len_x-2)*8+1], output_buffer[i*iter+(len_x-2)*8+2], output_buffer[i*iter+(len_x-2)*8+3]);
        fprintf(fp, "%d ", i*iter+(len_x-1)*8);
        fprintf(fp, "%d %d x x x x x x \n", output_buffer[i*iter+(len_x-1)*8], output_buffer[i*iter+(len_x-1)*8+1]);
    }
}

void pe_array::handle_spm_data_ready(
    SpmDataReadyData* evData) {
    if (evData->requestorId == CTRL_PEID) {
        lsq->dataReadyFromSpm(
            CtrlLSQ::spmBank(evData->phys_addr),
            evData->data);
    } else {
        pe_unit[evData->requestorId]
            ->recieve_spm_data(evData->data);
    }
}

void pe_array::process_events() {
    std::list<EventProducer*> to_remove{};
    for (auto event_producer : active_event_producers) {
        std::pair<bool, std::list<Event>*> result = event_producer->tick();
        if (result.first) // Event producer has finished, mark it for removal
            to_remove.push_back(event_producer);
        for (auto& event : *(result.second)) {
#ifdef PROFILE
            printf("main processing event type %d\n\n", event.type);
#endif
            switch (event.type) {
                case EventType::SPM_DATA_READY:
                    handle_spm_data_ready(static_cast<SpmDataReadyData*>(event.data));
                    delete static_cast<SpmDataReadyData*>(event.data);
                    break;
                default:
                    fprintf(stderr, "Unknown event type %d\n", event.type);
                    exit(-1);
            }
        }
        delete result.second;
    }
    // Remove finished event producers
    for (auto event_producer : to_remove) {
        active_event_producers.erase(event_producer);
    }

}

// Pre-check whether executing both VLIW slots would
// cause an LSQ stall. Returns true if either (or both
// combined) would overflow an LSQ bank.
bool pe_array::willStallPair(
    unsigned long slot0, unsigned long slot1)
{
    // Combined address lists for canEnqueue
    int spmAddrs[10], s2Addrs[10];
    int nSpm = 0, nS2 = 0;

    unsigned long instrs[2] = {slot0, slot1};
    for (int s = 0; s < 2; s++) {
        unsigned long instr = instrs[s];
        bool is_magic = (instr >> 63) & 1;
        if (is_magic) continue;

        int opcode = instr & 0x3F;
        int dest   = (instr >> 56) & 0xF;
        int src    = (instr >> 52) & 0xF;
        int riB0   = (instr >> 51) & 1;
        int imm0   = (instr >> 34) & 0xFFFF;
        if (imm0 & 0x8000) imm0 |= ~0xFFFF;
        int r0     = (instr >> 29) & 0x1F;
        int riB1   = (instr >> 28) & 1;
        int imm1   = (instr >> 11) & 0xFFFF;
        if (imm1 & 0x8000) imm1 |= ~0xFFFF;
        int r1     = (instr >> 6)  & 0x1F;

        bool srcSpm  = (src  == CTRL_SPM);
        bool srcS2   = (src  == CTRL_S2);
        bool destSpm = (dest == CTRL_SPM);
        bool destS2  = (dest == CTRL_S2);
        bool spmS2   = (srcSpm && destS2)
                     || (srcS2 && destSpm);

        if (opcode == 5 && spmS2) {
            // mv SPM<->S2: one spm addr, one s2 addr
            int addr0 = (riB0
                ? main_addressing_register[imm0 & 0x1F]
                : imm0)
                + main_addressing_register[r0];
            int addr1 = (riB1
                ? main_addressing_register[imm1 & 0x1F]
                : imm1)
                + main_addressing_register[r1];
            // dest uses addr0 (field 0), src uses addr1
            int spmA = destSpm ? addr0 : addr1;
            int s2A  = destS2  ? addr0 : addr1;
            spmAddrs[nSpm++] = spmA;
            s2Addrs[nS2++]   = s2A;
        } else if (opcode == CTRL_MVDQ && spmS2) {
            // mvdq SPM<->S2: 4-5 entries each side
            int addr0 = (riB0
                ? main_addressing_register[imm0 & 0x1F]
                : imm0)
                + main_addressing_register[r0];
            int addr1 = (riB1
                ? main_addressing_register[imm1 & 0x1F]
                : imm1)
                + main_addressing_register[r1];
            int spmA = destSpm ? addr0 : addr1;
            int s2A  = destS2  ? addr0 : addr1;
            // Even/odd bank patterns (mirrors decode)
            if (spmA % 2 == 0) {
                for (int i = 0; i < 4; i++)
                    spmAddrs[nSpm++] = spmA + 2*i;
            } else {
                spmAddrs[nSpm++] = spmA;
                spmAddrs[nSpm++] = spmA + 1;
                spmAddrs[nSpm++] = spmA + 3;
                spmAddrs[nSpm++] = spmA + 5;
                spmAddrs[nSpm++] = spmA + 7;
            }
            if (s2A % 2 == 0) {
                for (int i = 0; i < 4; i++)
                    s2Addrs[nS2++] = s2A + 2*i;
            } else {
                s2Addrs[nS2++] = s2A;
                s2Addrs[nS2++] = s2A + 1;
                s2Addrs[nS2++] = s2A + 3;
                s2Addrs[nS2++] = s2A + 5;
                s2Addrs[nS2++] = s2A + 7;
            }
        }
        // All other opcodes (including barrier): no stall
    }

    if (nSpm == 0 && nS2 == 0) return false;
    return !lsq->canEnqueue(
        spmAddrs, nSpm, s2Addrs, nS2);
}


void pe_array::run(int cycle_limit, int simd, int setting, int main_instruction_setting) {
    int i, j, old_PC;
    // Initialize flag to 0 so that a pair-stalled cycle (where the
    // `if (!pairStalls)` block is skipped) does not leave flag at a
    // previous/undefined value for the end-of-cycle `flag == -1` check.
    int flag = 0;
    cycle = 0;

    while (1) {
        cycle++;
        old_PC = main_PC;
        process_events();

        // S2 tick: advance pipelines, route completions
        {
            auto completions = s2->tick();
            for (auto& c : completions)
                lsq->dataReadyFromS2(
                    c.s2Addr, c.data);
        }

        // Pre-check: if either slot would stall on LSQ,
        // skip both to prevent double-execution bugs.
        bool pairStalls = false;
        if (main_instruction_setting
            == MAIN_INSTRUCTION_2) {
            pairStalls = willStallPair(
                main_instruction_buffer[main_PC][0],
                main_instruction_buffer[main_PC][1]);
            if (pairStalls) lsqFullStalls++;
        }

        if (!pairStalls) {
            flag = decode(
                main_instruction_buffer[main_PC][1],
                &main_PC, simd, setting,
                main_instruction_setting);
        }

        // Pre-PE decode of slot[0]: arithmetic + non-I/O
        // ops. Uses MI_1 filter to skip I/O-dest instrs
        // (handled post-PE by decode_output).
        if (main_instruction_setting
            == MAIN_INSTRUCTION_2 && !pairStalls) {
            int slot0_PC = old_PC;
            decode(main_instruction_buffer[old_PC][0],
                &slot0_PC, simd, setting,
                MAIN_INSTRUCTION_1);

            // Branch-as-group: if slot 0 branched, it
            // must agree with slot 1
            int op0 = main_instruction_buffer[old_PC][0]
                & ((1 << CTRL_OPCODE_WIDTH) - 1);
            int op1 = main_instruction_buffer[old_PC][1]
                & ((1 << CTRL_OPCODE_WIDTH) - 1);
            auto is_cf = [](int op) {
                return (op >= CTRL_BNE && op <= CTRL_JUMP)
                    || op == CTRL_CALL || op == CTRL_RET
                    || op == CTRL_RETNE;
            };
            // Call/ret must be paired in both slots
            auto is_call_ret = [](int op) {
                return op == CTRL_CALL || op == CTRL_RET
                    || op == CTRL_RETNE;
            };
            if (is_call_ret(op0) != is_call_ret(op1)) {
                fprintf(stderr,
                    "Controller PC=%d call/ret must be paired"
                    " (op0=%d op1=%d)\n", old_PC, op0, op1);
                exit(-1);
            }
            if (is_cf(op0) && is_cf(op1)
                && slot0_PC != main_PC) {
                fprintf(stderr,
                    "Controller PC=%d diverging branches:"
                    " slot0->%d slot1->%d\n",
                    old_PC, slot0_PC, main_PC);
                exit(-1);
            }
            // One branch taken: sync
            if (is_cf(op0) && slot0_PC != old_PC + 1
                && !is_cf(op1))
                main_PC = slot0_PC;
            if (is_cf(op1) && main_PC != old_PC + 1
                && !is_cf(op0))
                ; // main_PC already correct
        }

        pe_unit[0]->load_data = store_data;

        if (setting == PE_4_SETTING) {
            for (i = 0; i < 4; i++) {
                // Skip stalled PEs (freeze execution and block systolic forwarding)
                if (pe_unit[i]->stalled()) {
                    continue;
                }
#ifdef PROFILE
                printf("PE[%d]\t", i);
#endif
                pe_unit[i]->run(simd);
                // Systolic data forwarding
                if (i < 3) {
                    pe_unit[i+1]->load_data = pe_unit[i]->store_data;
                } else if (i == 3) {
                    load_data = pe_unit[3]->store_data;
                }
            }
        } else if (setting == PE_64_SETTING) {
            //TODO note that WAIT/READY is not implemented for 64 setting
            for (j = 0; j < 16; j++) {
                if (j > 0) {
                    if (from_fifo) pe_unit[j*4]->load_data = store_data;
                    else pe_unit[j*4]->load_data = pe_unit[j*4-1]->store_data;
                }

                for (i = 0; i < 4; i++) {
#ifdef PROFILE
                    printf("PE[%d]\t", j*4+i);
#endif
                    pe_unit[j*4+i]->run(simd);
                    if (i < 3) {
                        pe_unit[j*4+i+1]->load_data = pe_unit[j*4+i]->store_data;
                    } else if (j*4+i == 63) {
                        load_data = pe_unit[63]->store_data;
                    }
                }
            }
        }

        // Count halted PEs and update performance counter
        int num_halted = 0;
        int total_pes = (setting == PE_4_SETTING) ? 4 : 64;
        for (i = 0; i < total_pes; i++) {
            if (pe_unit[i]->halted) {
                num_halted++;
            }
        }
        peHalted += num_halted;

        // SPM bank arbitration with conflict detection (round-robin)
        int start_pe = cycle % 4;
        for (int offset = 0; offset < 4; offset++) {
            int pe_idx = (start_pe + offset) % 4;
            OutstandingRequest* req = pe_unit[pe_idx]->spmReqPort;
            if (req == nullptr) continue;

            totalSpmRequests++;
            // Check if SPM bank is available
            int bank = SPM_unit->getBank(
                req->addr, req->peid, req->isVirtualAddr);
            if (SPM_unit->portIsBusy(
                    req->addr, req->peid, req->isVirtualAddr)) {
                bankConflictStalls++;
                // Perf counter: check if conflict is same-line (forwardable)
                OutstandingRequest* pend = SPM_unit->requests[bank];
                int newPhys = req->isVirtualAddr
                    ? (req->peid * SPM_BANK_GROUP_SIZE + req->addr)
                    : req->addr;
                int pendPhys = pend->isVirtualAddr
                    ? (pend->peid * SPM_BANK_GROUP_SIZE + pend->addr)
                    : pend->addr;
                if (lineAddr(newPhys) == lineAddr(pendPhys))
                    forwardableBankConflict++;
            } else {
                // Grant access
                SPM_unit->access(req->addr, req->peid,
                    req->access_t, req->single_data,
                    req->data, req->isVirtualAddr);
                delete pe_unit[pe_idx]->spmReqPort;
                pe_unit[pe_idx]->spmReqPort = nullptr;
            }
        }

        // LSQ drain
        {
            bool spmBankBusy[SPM_NUM_BANKS] = {};
            // Only mark banks with in-flight SPM requests. Any pending
            // PE spmReqPort entries necessarily target banks that are
            // already busy (otherwise they would have issued above).
            for (int b = 0; b < SPM_NUM_BANKS; b++)
                spmBankBusy[b] =
                    (SPM_unit->requests[b] != nullptr);
            lsq->tick(SPM_unit, s2, spmBankBusy);
        }

        from_fifo = 0;

        if (main_instruction_setting == MAIN_INSTRUCTION_1)
            decode_output(main_instruction_buffer[old_PC][1],
                &old_PC, simd, setting,
                main_instruction_setting);
        else if (main_instruction_setting
                 == MAIN_INSTRUCTION_2 && !pairStalls)
            decode_output(main_instruction_buffer[old_PC][0],
                &old_PC, simd, setting,
                main_instruction_setting);

        //zkn TODO I don't know if these should be in the above else or not
        main_addressing_register[13] = pe_unit[0]->get_gr_10() && pe_unit[1]->get_gr_10();
        for (i = 2; i < setting; i++)
            main_addressing_register[13] = main_addressing_register[13] && pe_unit[i]->get_gr_10();
        if (flag == -1 || cycle == cycle_limit) {
            printf("cycle %d\n", cycle);
            break;
        }
    }

    printf("=== Performance Counters ===\n");
    printf("TotalSpmRequests: %d\n", totalSpmRequests);
    printf("BankConflictStalls: %d\n", bankConflictStalls);
    printf("ForwardableBankConflict: %d\n", forwardableBankConflict);
    printf("LsqFullStalls: %d\n", lsqFullStalls);
    printf("PeHalted: %d\n", peHalted);
    printf("SyncSpinBNEs: %d\n", controllerSpinCycles);
    printf("Fin0DupDiags: %d\n", fin0DupDiags);

    // fprintf(stderr, "Finish simulation.\n");
}
