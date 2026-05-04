#include "pe.h"
#include "FIFO.h"
#include "sys_def.h"
#include <cassert>
#include <algorithm>
#include "simulator.h"
// GWFA kernel header: real header when the submodule is present,
// stub header otherwise (see gwfa_stub.h). Matches the gate in
// pe_array.cpp and Makefile.
#ifdef GWFA_BUILD
extern "C" {
#include "kernel/Gwfa/gwfa.h"
}
#else
#include "gwfa_stub.h"
#endif
#include <iostream>
#include "gssw_simd4.h"
#ifdef PLAN3D_TRACE_SNAPSHOT
#include <fstream>
namespace {
inline std::ofstream& plan3d_snap_pe19() {
    static std::ofstream s("plan3d_snapshot_pe19.txt", std::ios::app);
    return s;
}
inline std::ofstream& plan3d_snap_pe22() {
    static std::ofstream s("plan3d_snapshot_pe22.txt", std::ios::app);
    return s;
}
inline std::ofstream& plan3d_snap_pe23() {
    static std::ofstream s("plan3d_snapshot_pe23.txt", std::ios::app);
    return s;
}
}
#endif

// SPM port restriction (PE side): an SPM load may write only to gr (incl
// gr_lo/gr_hi), reg, or out_port; an SPM store may take its data only from
// gr (incl gr_lo/gr_hi) or reg. Anything else would require driving the
// shared SPM port from a path that hardware does not provide.
static bool pe_spm_target_ok(int pos, bool is_load) {
    if (pos == CTRL_REG || pos == CTRL_GR
        || pos == CTRL_GR_LO || pos == CTRL_GR_HI) return true;
    if (is_load && pos == CTRL_OUT_PORT) return true;
    return false;
}

bool check_legal_mv(int src, int dest) {
    // SPM load: src is SPM, dest is the writeback target.
    if (src == CTRL_SPM && dest != CTRL_SPM) return pe_spm_target_ok(dest, true);
    // SPM store: dest is SPM, src is the data source.
    if (dest == CTRL_SPM && src != CTRL_SPM) return pe_spm_target_ok(src, false);
    return true;
}

// Returns true if `instruction` is a data-movement op whose src or dest
// type field is CTRL_SPM. Used by pe::run() to detect two SPM accesses
// issued by a single PE in one VLIW cycle (illegal — one memory port).
// Magic instructions bypass the normal port and are never counted.
static bool slot_does_spm_access(unsigned long instruction) {
    if (instruction & ((unsigned long)1 << 63)) return false;  // magic
    int opcode = instruction & ((1 << CTRL_OPCODE_WIDTH) - 1);
    bool is_dm = (opcode == 4 || opcode == 5
                  || opcode == CTRL_MVD || opcode == CTRL_MVI
                  || opcode == CTRL_MVDQ || opcode == CTRL_MVDQI
                  || opcode == CTRL_MVI2);
    if (!is_dm) return false;
    constexpr int W = INSTRUCTION_WIDTH;
    constexpr int A = MEMORY_COMPONENTS_ADDR_WIDTH;
    int dest_pos = (instruction >> (W - A)) & ((1 << A) - 1);
    int src_pos  = (instruction >> (W - 2 * A)) & ((1 << A) - 1);
    return src_pos == CTRL_SPM || dest_pos == CTRL_SPM;
}

pe::pe(int _id, SPM* spm, int _pc_mode) {

    SPM_unit = spm;
    id = _id;
    pc_mode = _pc_mode;
    comp_reg_load = 0, comp_reg_store = 0, addr_reg_load = 0, addr_reg_store = 0, SPM_load = 0, SPM_store = 0,
    comp_instr_load = 0, comp_instr_store = 0,
    comp_reg_load_addr = 0, comp_reg_store_addr = 0, addr_reg_load_addr = 0, addr_reg_store_addr = 0, SPM_load_addr = 0, SPM_store_addr = 0,
    comp_instr_load_addr = 0, comp_instr_store_addr = 0,
    instruction[0] = 0; instruction[1] = 0;
    comp_PC = COMP_INSTR_BUFFER_GROUP_NUM - 1;
    PC[0] = 0;
    PC[1] = 0;
    ras = 0;
}
pe::~pe() {
    delete comp_instr_buffer_unit;
    delete ctrl_instr_buffer_unit;
    delete addr_regfile_unit;
    delete regfile_unit;
}

void pe::reset_waw_trackers() {
    for (int k = 0; k < ADDR_REGISTER_NUM; k++) {
        addr_regfile_unit->last_write_cycle[k] = -1;
        addr_regfile_unit->halves_written[k] = 0;
        addr_regfile_unit->last_write_origin[k] = nullptr;
    }
    for (int k = 0; k < REGFILE_ADDR_NUM; k++) {
        regfile_unit->last_write_cycle[k] = -1;
        regfile_unit->last_write_origin[k] = nullptr;
    }
}

void pe::reset() {
    SPM_unit->reset();
    addr_regfile_unit->reset();
    regfile_unit->reset();
    comp_reg_load = 0, comp_reg_store = 0, addr_reg_load = 0, addr_reg_store = 0, SPM_load = 0, SPM_store = 0,
    comp_instr_load = 0, comp_instr_store = 0,
    comp_reg_load_addr = 0, comp_reg_store_addr = 0, addr_reg_load_addr = 0, addr_reg_store_addr = 0, SPM_load_addr = 0, SPM_store_addr = 0,
    comp_instr_load_addr = 0, comp_instr_store_addr = 0,
    instruction[0] = 0; instruction[1] = 0;
    comp_PC = COMP_INSTR_BUFFER_GROUP_NUM - 1;
    PC[0] = 0;
    PC[1] = 0;
    ras = 0;
    outstanding_reqs.clear();
    spmReqPort = nullptr;
    halted = false;
    // Clear forwarded in_port/out_port values so a reused PE does not
    // leak a previous case's data into the next case's early reads.
    load_data = 0;
    store_data = 0;
}

void pe::recieve_spm_data(int data[LINE_SIZE]){
    if (outstanding_reqs.empty()){
        fprintf(stderr, "Error: No outstanding request present, but recieve_spm_data called for PE[%d]\n", id);
        exit(-1);
    }
    // FIFO pop: the oldest pending load is the one whose data just landed.
    const OutstandingReq req = outstanding_reqs.front();
    outstanding_reqs.pop_front();
#ifdef PROFILE
    printf("PE[%d] @%d recv SPM: ", id, cycle);
#endif
    switch (req.dst){
        case CTRL_REG:
            if (req.single_load) {
                {
                int val = data[req.spm_addr & 1];
                if (req.two_bit_extract)
                    val = (val >> req.bp_shift) & 0x3;
                regfile_unit->set_delayed(req.addr, val);
                }
#ifdef PROFILE
                printf("reg[%d] = %d\n",
                    req.addr, data[req.spm_addr & 1]);
#endif
            } else {
                for (int i = 0; i < LINE_SIZE; i++)
                    regfile_unit->set_delayed(req.addr + i, data[i]);
#ifdef PROFILE
                printf("reg[%d,%d] = [%d,%d]\n",
                    req.addr, req.addr+1, data[0], data[1]);
#endif
            }
            break;
        case CTRL_GR:
        case CTRL_GR_LO:
        case CTRL_GR_HI:
            if (req.single_load) {
                int val = data[req.spm_addr & 1];
                if (req.two_bit_extract)
                    val = (val >> req.bp_shift) & 0x3;
                addr_regfile_unit->st_delayed(req.addr, val, req.dst);
#ifdef PROFILE
                printf("gr[%d] = %d\n",
                    req.addr, data[req.spm_addr & 1]);
#endif
            } else {
                // mvd to gr: deliver both words to consecutive gr
                // indices (previously only word 0 was written, leaving
                // the second half untouched — broke lowered GSSW).
                for (int i = 0; i < LINE_SIZE; i++)
                    addr_regfile_unit->st_delayed(req.addr + i, data[i], req.dst);
#ifdef PROFILE
                printf("gr[%d,%d] = [%d,%d]\n",
                    req.addr, req.addr + 1, data[0], data[1]);
#endif
            }
            break;
        case CTRL_OUT_PORT:
            {
            int val = data[req.spm_addr & 1];
            if (req.two_bit_extract)
                val = (val >> req.bp_shift) & 0x3;
            store_data = val;
            }
#ifdef PROFILE
            printf("out = %d\n", data[req.spm_addr & 1]);
#endif
            break;
        default:
            fprintf(stderr, "Error: Unsupported dst %d for SPM load in PE[%d]\n", req.dst, id);
            exit(-1);
    }
#ifdef PROFILE
    //if (id == 0){
    //    printf("\nzkn @%d:%d\n", cycle-1, data[0]);
    //}
#endif
}


void pe::run(int simd) {
    int i, op[2][3], input_addr[2][6], output_addr[2], ctrl_op[2];

    //reset write addr and data
    for (i = 0; i < CTRL_REGFILE_WRITE_PORTS; i++) {
        ctrl_write_addrs[i] = -1;
        ctrl_write_data[i] = -42;
    }

#ifdef PROFILE
    //zkn
    //if (id == 0 ){
    //    std::cout << std::dec << std::endl << "qqq @" << cycle << " ";
    //    for (int i = 0; i < 32; i++){
    //        std::cout << " " << regfile_unit->register_file[i];
    //    }
    //    std::cout << std::endl;
    //}
#endif

    // Compute
    instruction[0] = comp_instr_buffer_unit->buffer[comp_PC][0];
    instruction[1] = comp_instr_buffer_unit->buffer[comp_PC][1];
#ifdef PROFILE
    printf("comp_PC = %d\t", comp_PC);
#endif
    comp_decoder_unit.execute(instruction[0], op[0], input_addr[0], &output_addr[0], &comp_PC);
    comp_decoder_unit.execute(instruction[1], op[1], input_addr[1], &output_addr[1], &i);
//#ifdef PROFILE
//    printf("\n");
//#endif
    // Clamp gr addresses to 0 for regfile read (patched below)
    for (i = 0; i < 6; i++) {
        regfile_unit->read_addr[i] = input_addr[0][i] < REGFILE_ADDR_NUM ? input_addr[0][i] : 0;
        regfile_unit->read_addr[i+6] = input_addr[1][i] < REGFILE_ADDR_NUM ? input_addr[1][i] : 0;
    }
    regfile_unit->read(regfile_unit->read_addr, regfile_unit->read_data);
    regfile_unit->write_addr[0] = output_addr[0] < REGFILE_ADDR_NUM ? output_addr[0] : -1;
    regfile_unit->write_addr[1] = output_addr[1] < REGFILE_ADDR_NUM ? output_addr[1] : -1;
    // Suppress regfile write when the slot is halted — a HALT op[0]
    // shouldn't clobber reg[output_addr] with garbage. (Previously any
    // idle HALT with output_addr=0 silently wrote 0 to reg[0].)
    if (op[0][0] == HALT) regfile_unit->write_addr[0] = -1;
    if (op[1][0] == HALT) regfile_unit->write_addr[1] = -1;

    int cu_inputs[2][6];
    for (i = 0; i < 6; i++){
        cu_inputs[0][i] = regfile_unit->read_data[i];
        cu_inputs[1][i] = regfile_unit->read_data[6+i];
    }
    // Patch compute inputs for gr addresses (addr >= 32)
    for (int s = 0; s < 2; s++) {
        for (int j = 0; j < 6; j++) {
            int addr = input_addr[s][j];
            if (addr >= 64)
                cu_inputs[s][j] = addr_regfile_unit->at(addr - 64, CTRL_GR_HI);
            else if (addr >= 48)
                cu_inputs[s][j] = addr_regfile_unit->at(addr - 48, CTRL_GR_LO);
            else if (addr >= 32)
                cu_inputs[s][j] = addr_regfile_unit->at(addr - 32);
        }
    }
    //Patch up for immediates
    if (is_immediate_opcode(op[0][0])){
        cu_inputs[0][0] = input_addr[0][0];
        op[0][0] = get_base_opcode(op[0][0]);
    }
    if (is_immediate_opcode(op[0][1])){
        cu_inputs[0][1] = input_addr[0][4];
        op[0][1] = get_base_opcode(op[0][1]);
    }
    if (is_immediate_opcode(op[1][0])){
        cu_inputs[1][0] = input_addr[1][0];
        op[1][0] = get_base_opcode(op[1][0]);
    }
    if (is_immediate_opcode(op[1][1])){
        cu_inputs[1][1] = input_addr[1][4];
        op[1][1] = get_base_opcode(op[1][1]);
    }

    // Per-slot dispatch: SIMD + gr source -> scalar ALU (GSSW lowering).
    // If any compute input references a gr (input_addr >= 32) while simd
    // mode is active, the lane-packing treatment would corrupt 32-bit gr
    // values — fall back to the scalar ALU for that slot. COMP_GT is the
    // documented exception: it legitimately reads simd reg lanes and writes
    // a scalar 0/1 into gr, so keep it on the simd path regardless.
    auto slot_has_gr_src = [&](int s) {
        for (int j = 0; j < 6; j++) if (input_addr[s][j] >= 32) return true;
        return false;
    };
    for (int s = 0; s < 2; s++) {
        // SLLI_64: paired 64-bit left shift. Both slots see the same opcode;
        // cu_inputs[s][1]=reg[srcReg], cu_inputs[s][2]=reg[srcReg+1]; the
        // shift amount arrives via the immediate path in cu_inputs[s][0].
        // Slot 0 emits the new low word, slot 1 emits the new high word.
        if (op[s][0] == SLLI_64) {
            unsigned shift_imm = (unsigned)cu_inputs[s][0] & 0x3F;  // 0..63
            uint32_t lo = (uint32_t)cu_inputs[s][1];
            uint32_t hi = (uint32_t)cu_inputs[s][2];
            uint64_t pair = ((uint64_t)hi << 32) | lo;
            uint64_t shifted = (shift_imm >= 64) ? 0ULL : (pair << shift_imm);
            regfile_unit->write_data[s] = (s == 0)
                ? (int)(uint32_t)shifted
                : (int)(uint32_t)(shifted >> 32);
            continue;
        }
        bool use_simd = simd
            && !(slot_has_gr_src(s) && op[s][0] != COMP_GT);
        if (use_simd)
            regfile_unit->write_data[s] = cu_32.execute_8bit(op[s], cu_inputs[s]);
        else
            regfile_unit->write_data[s] = cu_32.execute(op[s], cu_inputs[s]);
    }


    // Stage compute writes to gr — defer commit until after control decode
    // so that control reads see pre-cycle gr values (concurrent semantics).
    int comp_gr_idx[2] = {-1, -1};
    int comp_gr_pos[2] = {0, 0};
    for (int s = 0; s < 2; s++) {
        if (op[s][0] == HALT) continue;
        int addr = output_addr[s];
        if (addr >= 64)      { comp_gr_idx[s] = addr - 64; comp_gr_pos[s] = CTRL_GR_HI; }
        else if (addr >= 48) { comp_gr_idx[s] = addr - 48; comp_gr_pos[s] = CTRL_GR_LO; }
        else if (addr >= 32) { comp_gr_idx[s] = addr - 32; comp_gr_pos[s] = CTRL_GR; }
    }
    // regfile_unit->write_addr/write_data already hold staged compute reg
    // writes — leave them; commit moved below to after control decode.
#ifdef PROFILE
    printf("\nPE[%d]\t", id);
#endif

    // Control
    if (PC[1] < 0 || PC[1] >= CTRL_INSTR_BUFFER_NUM) {
        fprintf(stderr, "PE[%d] PC[1]=%d out of bounds\n", id, PC[1]);
        exit(-1);
    }
    if (PC[0] < 0 || PC[0] >= CTRL_INSTR_BUFFER_NUM) {
        fprintf(stderr, "PE[%d] PC[0]=%d out of bounds\n", id, PC[0]);
        exit(-1);
    }
    int old_PC = PC[0];
    // Structural hazard: PE has one SPM port — at most one SPM access per
    // VLIW cycle. Check both slots before either dispatches.
    if (slot_does_spm_access(ctrl_instr_buffer_unit->buffer[PC[0]][0])
        && slot_does_spm_access(ctrl_instr_buffer_unit->buffer[PC[1]][1])) {
        fprintf(stderr,
            "PE[%d] cycle %d PC=[%d/%d]: two SPM accesses in one VLIW"
            " cycle — only one memory port per PE.\n",
            id, cycle, PC[0], PC[1]);
        exit(-1);
    }
    // Inter-slot RAW fix: both control slots must observe the same
    // pre-cycle gr/reg state. Slot 1 decodes first and may commit gr/reg
    // writes during decode (e.g. gr_lo/gr_hi, arithmetic dest=gr); without
    // intervention slot 0 would read those new values. Snapshot, run slot
    // 1, capture its deltas, restore so slot 0 reads pre-cycle, run slot
    // 0, then reapply slot 1's deltas. Slot-0 same-idx writes still hit
    // the WAW tracker (last_write_cycle from slot 1 is preserved across
    // restore) so overlap crashes correctly.
    int gr_snap[ADDR_REGISTER_NUM];
    int reg_snap[REGFILE_ADDR_NUM];
    memcpy(gr_snap, addr_regfile_unit->buffer,
           ADDR_REGISTER_NUM * sizeof(int));
    memcpy(reg_snap, regfile_unit->register_file,
           REGFILE_ADDR_NUM * sizeof(int));

    decode(ctrl_instr_buffer_unit->buffer[PC[1]][1], &PC[1], src_dest[1], &ctrl_op[1], simd, &ctrl_write_addrs[0], &ctrl_write_data[0]);

    // Capture slot 1's gr/reg deltas (changes vs snapshot).
    int s1_gr_changed[ADDR_REGISTER_NUM];
    int s1_gr_val[ADDR_REGISTER_NUM];
    int s1_n_gr = 0;
    for (int k = 0; k < ADDR_REGISTER_NUM; k++) {
        if (addr_regfile_unit->buffer[k] != gr_snap[k]) {
            s1_gr_changed[s1_n_gr] = k;
            s1_gr_val[s1_n_gr] = addr_regfile_unit->buffer[k];
            s1_n_gr++;
        }
    }
    int s1_reg_changed[REGFILE_ADDR_NUM];
    int s1_reg_val[REGFILE_ADDR_NUM];
    int s1_n_reg = 0;
    for (int k = 0; k < REGFILE_ADDR_NUM; k++) {
        if (regfile_unit->register_file[k] != reg_snap[k]) {
            s1_reg_changed[s1_n_reg] = k;
            s1_reg_val[s1_n_reg] = regfile_unit->register_file[k];
            s1_n_reg++;
        }
    }

    // Restore so slot 0 sees pre-cycle. Direct buffer write — leaves the
    // WAW tracker (last_write_cycle) intact, so a slot-0 write to any idx
    // slot 1 wrote will still crash via the instrumented st()/set().
    memcpy(addr_regfile_unit->buffer, gr_snap,
           ADDR_REGISTER_NUM * sizeof(int));
    memcpy(regfile_unit->register_file, reg_snap,
           REGFILE_ADDR_NUM * sizeof(int));

    decode(ctrl_instr_buffer_unit->buffer[PC[0]][0], &PC[0], src_dest[0], &ctrl_op[0], simd, &ctrl_write_addrs[1], &ctrl_write_data[1]);

    // Reapply slot 1's deltas. Any idx slot 0 also wrote would already
    // have crashed via WAW. So at this point the two delta sets are
    // disjoint and we can reapply slot 1's via direct write.
    for (int k = 0; k < s1_n_gr; k++)
        addr_regfile_unit->buffer[s1_gr_changed[k]] = s1_gr_val[k];
    for (int k = 0; k < s1_n_reg; k++)
        regfile_unit->register_file[s1_reg_changed[k]] = s1_reg_val[k];

    // Branch-as-group: both VLIW slots must agree on control flow
    auto is_ctrl_flow = [](int op) {
        return (op >= CTRL_BNE && op <= CTRL_JUMP)
            || op == CTRL_CALL || op == CTRL_RET
            || op == CTRL_RETNE;
    };
    // call/ret/retne must be paired across both VLIW slots — they
    // mutate ras and both PCs in lockstep, and allowing them in only
    // one slot lets the other slot commit side effects before the PC
    // resync below. Mirrors the controller reject at pe_array.cpp
    // ~4617 so the PE path fails fast on illegal traces instead of
    // silently mis-executing.
    auto is_call_ret = [](int op) {
        return op == CTRL_CALL || op == CTRL_RET
            || op == CTRL_RETNE;
    };
    if (is_call_ret(ctrl_op[0]) != is_call_ret(ctrl_op[1])) {
        fprintf(stderr,
            "PE[%d] PC=%d call/ret must be paired"
            " (op0=%d op1=%d)\n",
            id, old_PC, ctrl_op[0], ctrl_op[1]);
        exit(-1);
    }
    bool cf0 = is_ctrl_flow(ctrl_op[0]), cf1 = is_ctrl_flow(ctrl_op[1]);

    // Both slots took control flow: they must agree on the target.
    // Mirrors the controller reject at pe_array.cpp ~4623.
    if (cf0 && cf1 && PC[0] != PC[1]) {
        fprintf(stderr,
            "PE[%d] PC=%d diverging branches:"
            " slot0->%d slot1->%d\n",
            id, old_PC, PC[0], PC[1]);
        exit(-1);
    }

    // One control flow taken: sync other slot (SHARED mode only).
    // PC_MODE_DUAL leaves PC[0]/PC[1] independent — required by POA,
    // whose pe_X traces have a single-slot trailing branch that must
    // not pull the other slot's PC forward.
    bool took0 = (PC[0] != old_PC + 1);
    bool took1 = (PC[1] != old_PC + 1);
    if (pc_mode == PC_MODE_SHARED) {
        if (cf0 && took0 && !cf1) PC[1] = PC[0];
        if (cf1 && took1 && !cf0) PC[0] = PC[1];
    }

    // Track if PE is halted (both slots executing halt instruction)
    halted = (ctrl_op[0] == CTRL_HALT && ctrl_op[1] == CTRL_HALT);

    // Commit deferred compute writes now that control decode has consumed
    // its pre-cycle gr/reg view. Instrumented st()/set() detects any WAW
    // collision against control writes that already committed during decode.
    for (int s = 0; s < 2; s++) {
        if (comp_gr_idx[s] >= 0)
            addr_regfile_unit->st(comp_gr_idx[s],
                regfile_unit->write_data[s], comp_gr_pos[s], "comp");
    }
    if (regfile_unit->write_addr[0] >= 0
        && regfile_unit->write_addr[0] < REGFILE_ADDR_NUM)
        regfile_unit->set(regfile_unit->write_addr[0],
            regfile_unit->write_data[0], "comp");
    if (regfile_unit->write_addr[1] >= 0
        && regfile_unit->write_addr[1] < REGFILE_ADDR_NUM)
        regfile_unit->set(regfile_unit->write_addr[1],
            regfile_unit->write_data[1], "comp");

    addr_regfile_unit->write(ctrl_write_addrs, ctrl_write_data, CTRL_REGFILE_WRITE_PORTS);

#ifdef PROFILE
    printf("\n");
#endif

    if (ctrl_op[0] == 5 && ctrl_op[1] == 5 && src_dest[0][0] == src_dest[1][0] && src_dest[0][0] != CTRL_GR && src_dest[0][0] != CTRL_REG) {
        fprintf(stderr, "PE[%d] PC[%d %d] source position confliction on src %d.\n", id, PC[0], PC[1], src_dest[0][0]);
        exit(-1);
    } 
    //not sure what this was supposed to be, but it's a repeat of above
   // else if (ctrl_op[0] == 5 && ctrl_op[1] == 5 && src_dest[0][1] == src_dest[1][1] && src_dest[0][1] != CTRL_GR && src_dest[0][1] != CTRL_REG) {
   //     fprintf(stderr, "PE[%d] PC[%d %d] dest position confliction.\n", id, PC[0], PC[1]);
   //     exit(-1);
   // }
}

void pe::ctrl_instr_load_from_ddr(int addr, unsigned long data[]) {
    if (addr >= 0 && addr < CTRL_INSTR_BUFFER_NUM) {
        ctrl_instr_buffer_unit->buffer[addr][0] = data[0];
        ctrl_instr_buffer_unit->buffer[addr][1] = data[1];
    } else {
        fprintf(stderr, "PE[%d] ctrl instr buffer write addr %d is out of bound\n", id, addr);
        exit(-1);
    }
}

void pe::comp_instr_load_from_ddr(int n_instr, unsigned long* data) {
    for (int i = 0; i < n_instr; i++){
        if (i < COMP_INSTR_BUFFER_GROUP_NUM) {
            comp_instr_buffer_unit->buffer[i][0] = data[2*i];
            comp_instr_buffer_unit->buffer[i][1] = data[2*i+1];
        } else {
            fprintf(stderr, "PE[%d] comp instr buffer write addr %d is out of bound\n", id, i);
            exit(-1);
        }
    }
}


LoadResult pe::load(int source_pos, int reg_immBar_flag, int rs1, int rs2, int simd, bool single_data, bool swizzle, int rs2_pos) {

    LoadResult data{};
    data.data[0] = 0;
    int source_addr = 0;

    // rs2_pos selects full gr / gr_lo / gr_hi for the SPM-offset register.
    // Default CTRL_GR preserves legacy full-32-bit behavior for non-SPM paths.
    if (reg_immBar_flag) source_addr = addr_regfile_unit->at(rs1) + addr_regfile_unit->at(rs2, rs2_pos);
    else source_addr = rs1 + addr_regfile_unit->at(rs2, rs2_pos);

#ifdef DEBUG
    printf("src: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d src_addr: %d\n", source_pos, reg_immBar_flag, rs1, rs2, source_addr);
#endif

    if (source_pos == CTRL_REG) {
        int n_loads = single_data ? 1 : LINE_SIZE;
        for (int i = 0; i < n_loads; i++) {
            int addr = source_addr + i;
            if (addr >= 0 && addr < REGFILE_ADDR_NUM) {
                data.data[i] = regfile_unit->register_file[addr];
            } else {
                fprintf(stderr, "PE[%d] load gr addr %d error.\n", id, addr);
                exit(-1);
            }
#ifdef PROFILE
        if (simd)
            printf("%lx from reg[%d]", data.data[i], source_addr);
        else
            printf("%d from reg[%d]", data.data[i], source_addr);
#endif
        }
#ifdef PROFILE
        printf(" to ");
#endif
    } else if (source_pos == CTRL_GR
            || source_pos == CTRL_GR_LO
            || source_pos == CTRL_GR_HI) {
        int n_loads = single_data ? 1 : LINE_SIZE;
        for (int i = 0; i < n_loads; i++) {
            int addr = source_addr + i;
            if (addr >= 0 && addr < ADDR_REGISTER_NUM) {
                data.data[i] = addr_regfile_unit->at(
                    addr, source_pos);
            } else {
                fprintf(stderr, "PE[%d] load gr addr %d error.\n", id, addr);
                exit(-1);
            }
#ifdef PROFILE
            if (simd)
                printf("%lx from gr[%d]-", data.data[i], addr);
            else
                printf("%d from gr[%d]-", data.data[i], addr);
#endif
        }
#ifdef PROFILE
        printf(" to ");
#endif
    } else if (source_pos == CTRL_SPM) {
        int access_addr = swizzle
            ? apply_address_swizzle(source_addr)
            : source_addr;
        bool isVirtualAddr = !swizzle;
        last_spm_load_addr = access_addr;
        spmReqPort = new OutstandingRequest();
        spmReqPort->addr = access_addr;
        spmReqPort->peid = id;
        spmReqPort->access_t = SpmAccessT::READ;
        spmReqPort->single_data = single_data;
        if (!single_data)
            assert(lineOffset(access_addr) == 0
                && "Double-data SPM read requires "
                   "even addr");
        spmReqPort->isVirtualAddr = isVirtualAddr;
#ifdef PROFILE
    if (simd)
        printf("%lx from SPM[%d]%s to ", SPM_unit->access_magic(id, access_addr), source_addr, swizzle ? " (swizzled)" : "");
    else
        if (isVirtualAddr) {
            printf("%d from SPM[%d]%s to ", SPM_unit->access_magic(id, access_addr), source_addr, swizzle ? " (swizzled)" : "");
        } else {
            printf("%d from SPM[%d]%s to ", SPM_unit->buffer[access_addr], source_addr, swizzle ? " (swizzled)" : "");
        }
#endif
    } else if (source_pos == CTRL_COMP_IB) {
        assert(single_data); //only support single instruction load from comp instr buffer
        comp_instr_load = 1;
        comp_instr_load_addr = source_addr;
        instruction[0] = comp_instr_buffer_unit->buffer[comp_instr_load_addr][0];
        instruction[1] = comp_instr_buffer_unit->buffer[comp_instr_load_addr][1];
#ifdef PROFILE
        printf("%lx %lx from comp instruction buffer[%d] to ", instruction[0], instruction[1], source_addr);
#endif
    } else if (source_pos == CTRL_IN_PORT) {
        assert(single_data); //only support single data load from input port
        data.data[0] = load_data;
#ifdef PROFILE
    if (simd)
        printf("%lx from input data port to ", data.data[0]);
    else
        printf("%d from input data port to ", data.data[0]);
#endif
    } else {
        fprintf(stderr, "source_pos error. source_pos=%d\n",source_pos);
        exit(-1);
    }
    return data;
}

void pe::store(int dest_pos, int src_pos, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd, int* ctrl_write_addr, int* ctrl_write_datum, bool single_data, bool swizzle, int rs2_pos) {

    int dest_addr = 0;

    // rs2_pos selects full gr / gr_lo / gr_hi for the SPM-offset register.
    // Default CTRL_GR preserves legacy full-32-bit behavior for non-SPM paths.
    if (reg_immBar_flag) dest_addr = addr_regfile_unit->at(rs1) + addr_regfile_unit->at(rs2, rs2_pos);
    else dest_addr = rs1 + addr_regfile_unit->at(rs2, rs2_pos);

#ifdef DEBUG
    printf("dest: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d src_addr: %d\n", dest_pos, reg_immBar_flag, rs1, rs2, dest_addr);
#endif
    if (src_pos == CTRL_SPM) {
        //in this case we need to wait a cycle, so we put it into outstanding
        if (dest_pos != CTRL_REG && dest_pos != CTRL_GR
            && dest_pos != CTRL_GR_LO && dest_pos != CTRL_GR_HI
            && dest_pos != CTRL_OUT_PORT) {
            fprintf(stderr,
                "Error: unsupported dest %d for SPM source"
                " store in PE[%d]\n", dest_pos, id);
            exit(-1);
        }
        // Allow up to SPM_ACCESS_LATENCY (=2) loads in flight per PE.
        // Responses are consumed FIFO in recieve_spm_data.
        assert(outstanding_reqs.size() < (size_t)SPM_ACCESS_LATENCY);
        OutstandingReq req;
        req.valid = true;
        req.single_load = single_data;
        req.dst = dest_pos;
        req.addr = dest_addr;
        req.spm_addr = last_spm_load_addr;
        outstanding_reqs.push_back(req);
        //still log the dest we're sending to
#ifdef PROFILE
        switch (dest_pos) {
            case CTRL_REG:
                printf("reg[%d].\t", dest_addr);
                break;
            case CTRL_GR:
                printf("gr[%d].\t", dest_addr);
                break;
            case CTRL_OUT_PORT:
                printf("out port.\t");
                break;
        }
#endif
    } else {
        if (dest_pos == CTRL_REG) {
            comp_reg_store = 1;
            comp_reg_store_addr = dest_addr;
            regfile_unit->write_addr[2] = comp_reg_store_addr;
            regfile_unit->write_data[2] = data.data[0];
            regfile_unit->write(regfile_unit->write_addr, regfile_unit->write_data, 2);
#ifdef PROFILE
            printf("reg[%d].\t", dest_addr);
#endif
        } else if (dest_pos == CTRL_GR
                || dest_pos == CTRL_GR_LO
                || dest_pos == CTRL_GR_HI) {
            if (dest_addr >= 0 && dest_addr < ADDR_REGISTER_NUM) {
                if (dest_pos == CTRL_GR) {
                    *ctrl_write_datum = data.data[0];
                    *ctrl_write_addr = dest_addr;
                } else {
                    // Subregister: write directly, bypass ctrl_write
                    addr_regfile_unit->st(
                        dest_addr, data.data[0], dest_pos);
                }
#ifdef PROFILE
                printf("gr[%d].\t", dest_addr);
#endif
            } else {
                fprintf(stderr, "PE[%d] store gr addr %d error.\n", id, dest_addr);
                exit(-1);
            }
        } else if (dest_pos == 2) {
            int access_addr = swizzle
                ? apply_address_swizzle(dest_addr) : dest_addr;
            bool isVirtualAddr = !swizzle;
            spmReqPort = new OutstandingRequest();
            spmReqPort->peid = id;
            spmReqPort->access_t = SpmAccessT::WRITE;
            spmReqPort->isVirtualAddr = isVirtualAddr;
            spmReqPort->addr = access_addr;
            if (single_data) {
                spmReqPort->single_data = true;
                int s = lineOffset(access_addr);
                spmReqPort->data.data[s] = data.data[0];
            } else {
                assert(lineOffset(access_addr) == 0
                    && "Double-data SPM write "
                       "requires even addr");
                spmReqPort->single_data = false;
                spmReqPort->data = data;
            }
#ifdef PROFILE
            printf("SPM[%d]%s.\t", dest_addr, swizzle ? " (swizzled)" : "");
#endif
        //if (id == 0){
        //    printf("\nzkn w%d:%d\n", cycle, data);
        //}

        } else if (dest_pos == 3) {
            comp_instr_store = 1;
            comp_instr_store_addr = dest_addr;
            comp_instr_buffer_unit->buffer[comp_instr_store_addr][0] = instruction[0];
            comp_instr_buffer_unit->buffer[comp_instr_store_addr][1] = instruction[1];
#ifdef PROFILE
            printf("comp instruction buffer[%d].\t", dest_addr);
#endif
        } else if (dest_pos == 9) {
            store_data = data.data[0];
#ifdef PROFILE
            printf("out port.\t");
#endif
        } else {
            fprintf(stderr, "dest_addr error.\t");
            exit(-1);
        }
    }
}

// ===== Inlined GSSW kernel (8-wide paired-4-lane SIMD version) =====
// Block-copied to avoid linking gssw.c. Each logical 8-lane vector
// occupies a pair of adjacent 32-bit regs / SPM words.

#define GSSW_SEG_LEN    19                           // ceil(148 / 8)
#define GSSW_VEC_WORDS  2                            // 2 SPM words per pair
// 8-byte (1 pair) padding between pvE/pvF and pvF/best absorbs the
// lazy-F last-iter overflow writes so they don't corrupt pvF[0]/best[0].
#define GSSW_SPM_PAD    8
#define GSSW_PROF_OFF   0
#define GSSW_HPING_OFF  (4 * GSSW_SEG_LEN * 8)       // 4 nt × segLen pairs × 8B
#define GSSW_HPONG_OFF  (GSSW_HPING_OFF + GSSW_SEG_LEN * 8)
#define GSSW_E_OFF      (GSSW_HPONG_OFF + GSSW_SEG_LEN * 8)
#define GSSW_F_OFF      (GSSW_E_OFF     + GSSW_SEG_LEN * 8 + GSSW_SPM_PAD)
#define GSSW_BEST_OFF   (GSSW_F_OFF     + GSSW_SEG_LEN * 8 + GSSW_SPM_PAD)
#define GSSW_GRAPH_OFF  (GSSW_BEST_OFF  + GSSW_SEG_LEN * 8)

struct gssw_spm_graph_meta_t {
    uint32_t num_nodes;
    uint32_t total_nexts;
    uint32_t total_seq;
    uint32_t _pad;
};

struct gssw_spm_node_desc_t {
    int16_t seq_off;
    int16_t seq_len;
    int16_t next_off;
    int16_t next_len;
    // Pair slots: 2 uint32 words per logical 8-lane vector.
    uint32_t hSeed[GSSW_SEG_LEN * GSSW_VEC_WORDS];
    uint32_t eSeed[GSSW_SEG_LEN * GSSW_VEC_WORDS];
};

// Word-offset constants (byte offsets / 4) — used by magic 101.
// Each array holds SEG_LEN pair slots = 2*SEG_LEN SPM words.
#define GSSW_PROF_WOFF   (GSSW_PROF_OFF  / 4)         // 0
#define GSSW_HPING_WOFF  (GSSW_HPING_OFF / 4)         // 152
#define GSSW_HPONG_WOFF  (GSSW_HPONG_OFF / 4)         // 190
#define GSSW_E_WOFF      (GSSW_E_OFF     / 4)         // 228
#define GSSW_F_WOFF      (GSSW_F_OFF     / 4)         // 266
#define GSSW_BEST_WOFF   (GSSW_BEST_OFF  / 4)         // 304
#define GSSW_META_WOFF   (GSSW_GRAPH_OFF / 4)         // 342
#define GSSW_NODES_WOFF  (GSSW_META_WOFF + 4)         // 346 (after 4 meta words)
#define GSSW_ND_WORDS    (2 + 2 * GSSW_SEG_LEN * GSSW_VEC_WORDS)  // 78 words
#define GSSW_ND_HSEED_W  2                            // hSeed words offset within nd
#define GSSW_ND_ESEED_W  (2 + GSSW_SEG_LEN * GSSW_VEC_WORDS)      // 40

// The register-mapped kernel now lives inside magic 101.
// See magic 101 handler below.

// ===== End inlined GSSW kernel =====

int pe::decode(unsigned long instruction, int* PC, int src_dest[], int* op, int simd, int* ctrl_write_addr, int* ctrl_write_datum) {
    if (instruction == 0x20f7800000000) {
        fprintf(stderr, "WARNING: PE[%d] PC=%d cycle=%d executing uninitialized instruction.\n", id, *PC, cycle);
    }

    // pe position:   
    // src - 0/1/2/9
    // dest - 0/1/2/10
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

    int rd, rs1, rs2, imm, comp_0 = 0, comp_1 = 0, sum = 0, add_a = 0, add_b = 0;
    LoadResult data;

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

    // Resolve bank selector encoded in the top 2 bits of the 7-bit reg idx.
    // Top 2 bits pick the file; low 5 bits are the physical index (0..31).
    //   idx[0:31]   -> CTRL_GR              (full 32-bit gr[idx])
    //   idx[32:63]  -> CTRL_GR_LO           (gr[idx-32] lo half)
    //   idx[64:95]  -> CTRL_GR_HI           (gr[idx-64] hi half)
    //   idx[96:127] -> CTRL_RESOLVED_REG    (compute reg[idx-96], PE only)
    // The resolved pos overrides src/dest ONLY when the src/dest type field
    // is CTRL_GR; for other types (SPM, fifo, reg-legacy, etc.) the type
    // field governs and top bits of reg_idx are ignored. Note: legacy
    // src/dest = CTRL_REG (0) keeps its existing "compute regfile via mv/li
    // path" meaning for load/store and its "don't-care → read gr" meaning
    // for arithmetic/branch sites.
    auto resolve_reg_field = [](int& reg_idx) -> int {
        int high = reg_idx >> 5;
        reg_idx &= 0x1F;
        if (high == 0) return CTRL_GR;
        if (high == 1) return CTRL_GR_LO;
        if (high == 2) return CTRL_GR_HI;
        return CTRL_RESOLVED_REG;
    };
    int src_resolved  = resolve_reg_field(reg_1);
    int dest_resolved = resolve_reg_field(reg_0);
    if (src  == CTRL_GR) src  = src_resolved;
    if (dest == CTRL_GR) dest = dest_resolved;

    src_dest[0] = src;
    src_dest[1] = dest;
    *op = opcode;

#ifdef PROFILE
    printf("PC = %d @%d:%016lx\t", *PC, cycle, instruction);
#endif

#ifdef DEBUG
    printf("dest: %d src: %d reg_immBar_flag_0: %d reg_auto_increasement_flag_0: %d reg_imm_0_sign_bit: %d sext_imm_0: %d, reg_0: %d reg_immBar_flag_1: %d reg_auto_increasement_flag_1: %d reg_imm_1_sign_bit: %d sext_imm_1: %d reg_1: %d opcode: %d\n", dest, src, reg_immBar_flag_0, reg_auto_increasement_flag_0, reg_imm_0_sign_bit, sext_imm_0, reg_0, reg_immBar_flag_1, reg_auto_increasement_flag_1, reg_imm_1_sign_bit, sext_imm_1, reg_1, opcode);
#endif

    if (is_magic) {
        constexpr int MAGIC_MASK_BITS = 8;
        int magic_id = magic_payload;
        int magic_mask = 0;
        if (magic_payload >= (1 << MAGIC_MASK_BITS)) {
            magic_id = magic_payload >> MAGIC_MASK_BITS;
            magic_mask = magic_payload & ((1 << MAGIC_MASK_BITS) - 1);
        }
        // Magic bodies model multi-ISA-cycle hardware behavior in one C++
        // pass; their internal gr writes are not real same-cycle VLIW
        // writes. Suspend WAW tracking for the duration of the dispatch.
        addr_regfile_unit->waw_suppressed = true;

        // Shared PE register aliases and subroutines for GWFA magic
        constexpr int DIAG_BIAS = 16384; // 0x4000
        auto &gr  = *addr_regfile_unit;
        int *reg  = regfile_unit->register_file;

        // mvi2-style 2-bit extract from interleaved SPM
        auto mvi2_ld = [&](int base_reg, int off_gr) -> int {
            int bp = reg[base_reg] + gr.at(off_gr);
            int phys = apply_address_swizzle(bp >> 4);
            return (int)(((uint32_t)SPM_unit->buffer[phys]
                >> ((bp & 0xF) << 1)) & 0x3);
        };

        // EXTEND subroutine: extend wavefront along diagonal.
        // In: gr[8]=vd(packed), gr[9]=k, gr[11]=ts_off
        // Uses: gr[14]=ql, gr_lo[12]=vl, reg[10]=gs_base,
        //       reg[11]=q_base
        // Out: gr[9]=extended k, gr[2]=d
        // Clobbers: gr[2], gr[4], gr[7], reg[6], reg[7],
        //           reg[8]
        auto extend = [&]() {
            //COMP
            {
                //NOP
                //NOP
            }
            // d = lo(vd) - 0x4000
            gr.st(2, gr.at(8, CTRL_GR_LO) - DIAG_BIAS);
            // precompute char-space offsets (+1 for 1-based)
            gr.st(4, gr.at(11) + gr.at(9) + 1);     // ts_off+k+1

            //COMP
            {
                // max_k = min(ql - d, vl)
                reg[8] = std::min(gr.at(12, CTRL_GR_LO), gr.at(14) - gr.at(2));
                gr.st(7, gr.at(2) + gr.at(9) + 1);      // d+k+1
            }
            //NOP
            //NOP


            while (true){
                //COMP halt
                reg[6] = mvi2_ld(10, 4); gr.st(4, gr.at(4) + 1); //load gs char and cursor++
                //NOP

                reg[7] = mvi2_ld(11, 7); gr.st(7, gr.at(7) + 1); //load q char and cursor++
                gr.st(9, gr.at(9) + 1);              // k++

                if (gr.at(9) >= reg[8]) break;

                if (reg[6] != reg[7]) break;
            }

            gr.st(9, gr.at(9) - 1);
            //NOP
        };

        if (magic_id == 8) {
#if 0   // Reference implementation (for debugging only)
            {
                int buf_base = (magic_mask & 1)
                    ? GWFA_BUF1_BASE : GWFA_BUF0_BASE;
                int *spm_pe = &SPM_unit->buffer[
                    id * SPM_BANK_GROUP_SIZE + buf_base];
                extern void gwfa_tile_compute(int *spm);
                gwfa_tile_compute(spm_pe);
            }
#else
            // Register-mapped magic 8: gwfa extend+emit per tile.
            // All values in gr[]/reg[]/SPM, each op = one ISA instruction.
            //
            // gr[]  | name             | notes
            // ------|------------------|-------------------------------
            //  0    | (zero)           | hardwired 0
            //  1 lo | i                | loop index
            //  1 hi | tile_n           | input diagonal count
            //  2    | scratch          | was ql; now tmp (d, 2*i, etc.)
            //  3 lo | tb_n             | B-tile emit count
            //  3 hi | ta_n             | A-out emit count
            //  4    | emit_vd / scratch| scratch in extend, emit_vd
            //  5    | emit_k           | emit_b k argument
            //  6 lo | node_idx         | current node index
            //  6 hi | prev_v           | previous vertex
            //  7    | scratch          | clobbered by emit_b/check_aout
            //  8 lo | d + 0x4000       | biased diagonal (in vd)
            //  8 hi | v                | vertex index   (in vd)
            //  9    | k                | wavefront offset
            // 10    | (sync)           | sync flag only
            // 11    | ts_off           | text-seq offset for node
            // 12    | vl               | vertex length (full reg, clobbered by mvd)
            // 13    | intv_n           | interval count
            // 14    | ql               | query length (read-only)
            // 15    | tmp1             | scratch
            //
            // reg[] | name    | notes
            // ------|---------|------------------------------------
            //  0    | (zero)  | hardwired 0
            //  1    | pk      | prev-prev k (seq run only)
            //  2    | ppk     | previous k
            //  6    | gs_char | graph-seq 2-bit char (extend)
            //  7    | q_char  | query 2-bit char    (extend)
            //  8    | max_k   | extend loop bound
            //  9    | prev_vd | previous tile_a vd
            // 10    | gs_base | GWFA_GS_START * 16
            // 11    | q_base  | GWFA_Q_START  * 16
            constexpr int TILE_A_OFF    = 0;
            constexpr int NODE_INFO_OFF = 128;
            constexpr int TILE_B_OFF    = 256;
            constexpr int TILE_INTV_OFF = 640;
            constexpr int TILE_AOUT_OFF = 1024;
            constexpr int META_TB_N     = 1152;
            constexpr int META_TA_N     = 1153;
            constexpr int META_TILE_N   = 1155;
            constexpr int META_INTV_N   = 1159;

            // Ping-pong: mask bit 0 selects buffer half
            int buf_base = (magic_mask & 1)
                ? GWFA_BUF1_BASE : GWFA_BUF0_BASE;
            int *spm  = &SPM_unit->buffer[
                id * SPM_BANK_GROUP_SIZE + buf_base];

            // --- EMIT_B subroutine ---
            // In: gr[4]=emit_vd(packed), gr[5]=emit_k (adjacent for mvd)
            // Uses: gr_lo[12]=vl, gr[14]=ql, gr_lo[3]=tb_n,
            //       gr_hi[12]=intv_n
            // Clobbers: gr[2], gr[5](intv only), gr[7], gr[15]
            auto emit_b = [&]() {
                // emit_k == vl → interval
                if (gr.at(5) == gr.at(12, CTRL_GR_LO))
                    goto m8_do_intv;
                gr.st(2, gr.at(4, CTRL_GR_LO) - DIAG_BIAS);

                // emit_k >= vl → done
                if (gr.at(5) >= gr.at(12, CTRL_GR_LO))
                    goto m8_emit_done;
                gr.st(15, gr.at(14) - gr.at(5));          // ql - emit_k

                // d_emit >= ql - emit_k → done
                if (gr.at(2) >= gr.at(15))
                    goto m8_emit_done;
                gr.st(7, gr.at(3, CTRL_GR_LO) + gr.at(3, CTRL_GR_LO));          // 2*tb_n


                {   // B emit: gr[4]=emit_vd, gr[5]=emit_k (mvd)
                    gr.st(3, gr.at(3, CTRL_GR_LO) + 1, CTRL_GR_LO);                       // tb_n++
                    spm[TILE_B_OFF + gr.at(7)] = gr.at(4); spm[TILE_B_OFF + gr.at(7) + 1] = gr.at(5);

                    //NOP
                    return;
                }

            m8_do_intv:
                {   // gr[4]=vd0, gr[5]=vd0+1 (mvd)
                    gr.st(5, gr.at(4) + 1);                // vd0+1
                    gr.st(7, gr.at(13) << 1);                       // 2*intv_n
                                                                   //
                    spm[TILE_INTV_OFF + gr.at(7)] = gr.at(4); spm[TILE_INTV_OFF + gr.at(7) + 1] = gr.at(5);
                    gr.st(13, gr.at(13) + 1);                      // intv_n++

                    return;
                }
            m8_emit_done:
                return;
            };

            // --- CHECK_AOUT subroutine ---
            // Emit (vd, k) to tile_aout if the wavefront reached the
            // end of the vertex (k==vl-1) or the end of the query
            // (d+k==ql-1). These boundary-hitting entries propagate
            // to the next GWFA expansion step.
            // In: gr[8]=vd, gr[9]=k
            // Uses: gr_lo[12]=vl, gr[14]=ql, gr_hi[3]=ta_n
            // Clobbers: gr[2], gr[7], gr[15]
            auto check_aout = [&]() {
                // extract d from vd
                //COMP
                {
                //NOP
                //NOP
                }
                gr.st(2, gr.at(8, CTRL_GR_LO) - DIAG_BIAS);
                // reached end of vertex?
                gr.st(15, gr.at(12, CTRL_GR_LO) - 1);

                gr.st(7, gr.at(3, CTRL_GR_HI) << 1);       // 2*ta_n specualtive. overwrite if no br
                if (gr.at(9) == gr.at(15))
                    goto m8_ca_do;
                //COMP
                {
                    // reached end of query?
                    gr.st(15, gr.at(2) + gr.at(9));
                    gr.st(7, gr.at(14) - 1);
                }

                if (gr.at(15) != gr.at(7)) return;
                //COMP halt
                gr.st(7, gr.at(3, CTRL_GR_HI) << 1);       // 2*ta_n

            m8_ca_do:
                // append (vd, k) to tile_aout[2*ta_n]
                gr.st(3, gr.at(3, CTRL_GR_HI) + 1, CTRL_GR_HI);    // ta_n++
                spm[TILE_AOUT_OFF + gr.at(7)] = gr.at(8); spm[TILE_AOUT_OFF + gr.at(7) + 1] = gr.at(9);
            };

            // === INIT ===
            gr.st(1, spm[META_TILE_N], CTRL_GR_HI);     // tile_n
            gr.st(13, 0);                                 // intv_n = 0
                                                         //
            gr.st(1, 0, CTRL_GR_LO);                     // i = 0
            gr.st(3, 0);                                 // tb_n, ta_n = 0

            if (gr.at(1, CTRL_GR_HI) <= 0)
                goto m8_done;
            gr.st(6, -1);                    // node_idx, prev_v = -1

            reg[10] = GWFA_GS_START * 16;                 // gs_base (char space)
            reg[11] = GWFA_Q_START * 16;                  // q_base (char space)

            // === OUTER_LOOP ===
        m8_outer_loop:
            if (gr.at(1, CTRL_GR_LO) >= gr.at(1, CTRL_GR_HI))
                goto m8_writeback;                        // i >= tile_n
            gr.st(2, gr.at(1, CTRL_GR_LO) << 1);                  // 2*i

            gr.st(8, spm[TILE_A_OFF + gr.at(2)]); gr.st(9, spm[TILE_A_OFF + gr.at(2) + 1]); // vd, k
            //NOP

            //NOP
            //NOP

            // v == prev_v → skip node setup
            if (gr.at(8, CTRL_GR_HI) == gr.at(6, CTRL_GR_HI))
                goto m8_skip_node;
            //set PC comp

            //// node_idx++
            // prev_v = v
            //COMP
            {
                // 2*node_idx
                gr.st(15, gr.at(6, CTRL_GR_LO)+gr.at(6, CTRL_GR_LO)+2);
                // node_idx++
                gr.st(6, gr.at(6, CTRL_GR_LO) + 1, CTRL_GR_LO);
            }
            gr.st(6, gr.at(8, CTRL_GR_HI), CTRL_GR_HI);
            //NOP

            //COMP halt
            gr.st(11, spm[NODE_INFO_OFF + gr.at(15)]); gr.st(12, spm[NODE_INFO_OFF + gr.at(15) + 1]);    // ts_off, vl (intv_n now in gr[13], safe to clobber)

        m8_skip_node:
            extend(); //call
            //set PC comp

            // store k back
            gr.st(15, gr.at(1, CTRL_GR_LO) + gr.at(1, CTRL_GR_LO));                  // 2*i
            gr.st(4, gr.at(8) - 1);                      // emit_vd

            spm[TILE_A_OFF + gr.at(15) + 1] = gr.at(9);
            gr.st(5, gr.at(9) + 1);                     // emit_k

            // emit_b(vd-1, k+1)
            emit_b(); //call
            
            check_aout(); //call
            //set PC comp


            gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO);
            //set PC comp
            
            //COMP (speculative if not last emit
            {
                gr.st(2, gr.at(1, CTRL_GR_LO) + gr.at(1, CTRL_GR_LO));                  // 2*i
                gr.st(15, gr.at(8) + 1);                      // vd+1 (for seq check)
            }
            // === SEQUENTIAL CHECK ===
            // If branching to last_emits, skip reg moves — last_emits
            // uses gr[8](vd) and gr[9](k) directly.
            gr.st(4, gr.at(8));                            // prev_vd = vd
            if (gr.at(1, CTRL_GR_LO) >= gr.at(1, CTRL_GR_HI))
                goto m8_last_emits;                       // i >= tile_n

            //COMP
            {
                // ppk = k, prev_vd = vd
                reg[2] = gr.at(9);
                reg[9] = gr.at(8);
            }
            gr.st(8, spm[TILE_A_OFF + gr.at(2)]); gr.st(9, spm[TILE_A_OFF + gr.at(2) + 1]); // next vd and k
            //NOP

            //COMP halt
            //NOP
            //NOP
            
            if (gr.at(8) != gr.at(15))
                goto m8_non_seq;
            gr.st(15, gr.at(1, CTRL_GR_LO) << 1);                  // 2*i

            // === SEQ_FIRST (2nd diagonal in run) ===
            {
                extend(); //Call
                //set PC comp

                spm[TILE_A_OFF + gr.at(15) + 1] = gr.at(9);
                //set PC comp

                //COMP
                {
                    // emit_k = max(ppk, k) + 1
                    gr.st(5, std::max((int)reg[2], gr.at(9)) + 1);
                    gr.st(4, reg[9]);                         // emit_vd=prev_vd
                }
                emit_b(); //call
                //NOP

                check_aout(); //call
                //set PC comp

                reg[9] = gr.at(8);                        // prev_vd = vd
                gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO);                          // i++

            }
            
            // === SEQ_WHILE (3rd+ diagonals) ===
        m8_seq_while:
            gr.st(2, gr.at(1, CTRL_GR_LO) + gr.at(1, CTRL_GR_LO));
            if (gr.at(1, CTRL_GR_LO) >= gr.at(1, CTRL_GR_HI))
                goto m8_seq_last_swap;


            reg[1] = reg[2];                      // pk = old ppk (before overwrite)
            reg[2] = gr.at(9);                    // ppk = prev extended k
            gr.st(8, spm[TILE_A_OFF + gr.at(2)]); gr.st(9, spm[TILE_A_OFF + gr.at(2) + 1]);

            gr.st(15, reg[9] + 1);

            if (gr.at(8) != gr.at(15))
                goto m8_seq_last;

            {
                extend(); //call
                //set PC comp

                gr.st(15, gr.at(1, CTRL_GR_LO) << 1);
                //set PC comp
    
                //COMP
                { 
                    //NOP
                    //NOP
                }
                spm[TILE_A_OFF + gr.at(15) + 1] = gr.at(9);
                gr.st(15, reg[2] + 1);                    // ppk+1

                //COMP
                {
                    // emit_k = max(pk, ppk+1, k+1)
                    gr.st(5, std::max({(int)reg[1], gr.at(15), gr.at(9) + 1}));
                    gr.st(4, reg[9]);                          // prev_vd
                } //NOTE not illustrated, next COMP will be halt. Will execute during emit_b
                emit_b(); //call
                //NOP

                check_aout(); //call
                //set PC comp
                
            }
            reg[9] = gr.at(8);                    // prev_vd = current vd
            gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO);
            goto m8_seq_while;

            // === SEQ_LAST ===
        m8_seq_last_swap: //same as seq_last, but adds the reg swap
            reg[1] = reg[2];
            reg[2] = gr.at(9);
        m8_seq_last:
            gr.st(15, reg[2] + 1);                        // ppk+1
            //set PC comp

            //COMP
            {
                // emit_k = max(pk, ppk+1)
                gr.st(5, std::max((int)reg[1], gr.at(15)));
            }
            gr.st(4, reg[9]);                              // prev_vd
            //NOP

            emit_b(); //call

            goto m8_trail_emit;

            // === NON_SEQ ===
        m8_non_seq:
            gr.st(4, reg[9]);                              // prev_vd
            gr.st(5, reg[2] + 1);                        // ppk+1

            emit_b(); //call

            // === TRAIL_EMIT ===
        m8_trail_emit:
            gr.st(4, reg[9] + 1);                         // prev_vd+1
            gr.st(5, reg[2]);                             // ppk

            // Cross-PE seam: this trail emits the right-boundary INSERT
            // edit for prev_vd. In the single-thread reference, the
            // right-side mismatch emit at the LAST diag of a global seq
            // run uses k = max(pk, ppk+1) — i.e., includes a +1 on the
            // last diag's post-extend k. When the global seq run spans
            // multiple PE tiles, the leading PE's trail emits use
            // k = ppk (the leading PE's last post-extend k), missing
            // the next-diag's contribution. The reference's max often
            // exceeds emit_b's `d+k < ql` filter and is dropped. The
            // leading PE's trail with the lower k may pass the filter
            // and become a spurious B-queue entry. Mirror the
            // reference's drop condition: if the next PE's first diag
            // (= prev_vd+1) has k_input such that the reference's
            // max(ppk, k_input+1) would fail the filter, skip the
            // trail. This is conservative — it only suppresses trails
            // that the reference itself would have dropped.
            if (id < 3) {
                int *next_spm = &SPM_unit->buffer[
                    (id + 1) * SPM_BANK_GROUP_SIZE + buf_base];
                int next_tile_n = next_spm[META_TILE_N];
                if (next_tile_n > 0
                    && next_spm[TILE_A_OFF] == gr.at(4)) {
                    int next_k_in = next_spm[TILE_A_OFF + 1];
                    int d_emit = (gr.at(4) & 0xFFFF) - DIAG_BIAS;
                    // Reference's right-side k = max(ppk, next_k+1).
                    int ref_k = gr.at(5);
                    if (next_k_in + 1 > ref_k) ref_k = next_k_in + 1;
                    if (d_emit + ref_k >= gr.at(14)) goto m8_trail_skip;
                }
            }

            emit_b(); //call

        m8_trail_skip:
            goto m8_outer_loop;

            // === LAST_EMITS ===
        m8_last_emits:

            //COMP (We don't actually want to run this block, but the trace was executing, so we're gonna hit it, and it doesn't matter
            {
                // ppk = k, prev_vd = vd
                reg[2] = gr.at(9);
                reg[9] = gr.at(8);
            }
            gr.st(5, gr.at(9) + 1);                       // ppk+1 = k+1
            emit_b(); //call

            gr.st(4, gr.at(8) + 1);                       // prev_vd+1 = vd+1
            gr.st(5, gr.at(9));                            // ppk = k

            // Cross-PE seam — same reasoning as m8_trail_emit. The
            // (vd+1, k) emit here is the right-boundary INSERT for the
            // SOLE diag in this tile. Mirror the reference's drop
            // condition using the next PE's first input k.
            if (id < 3) {
                int *next_spm = &SPM_unit->buffer[
                    (id + 1) * SPM_BANK_GROUP_SIZE + buf_base];
                int next_tile_n = next_spm[META_TILE_N];
                if (next_tile_n > 0
                    && next_spm[TILE_A_OFF] == gr.at(4)) {
                    int next_k_in = next_spm[TILE_A_OFF + 1];
                    int d_emit = (gr.at(4) & 0xFFFF) - DIAG_BIAS;
                    int ref_k = gr.at(5);
                    if (next_k_in + 1 > ref_k) ref_k = next_k_in + 1;
                    if (d_emit + ref_k >= gr.at(14)) goto m8_last_emits_done;
                }
            }

            emit_b();
        m8_last_emits_done: ;

            // === WRITEBACK ===
        m8_writeback:
            spm[META_TB_N]   = gr.at(3, CTRL_GR_LO);    // tb_n
            //NOP
            spm[META_TA_N]   = gr.at(3, CTRL_GR_HI);    // ta_n
            //NOP
            spm[META_INTV_N] = gr.at(13);                // intv_n
            //NOP
        m8_done: ;
#endif // reference vs PE implementation
        } else if (magic_id == 11) {
            // Boundary sort: 3-step compare-and-swap to fix up to 2
            // entries of disorder at each PE boundary. Runs in parallel
            // on PEs 0-2 (each fixes its own right boundary with the
            // next PE's left boundary). PE3 pushes last B to FIFO.
            int buf_base = (magic_mask & 1)
                ? GWFA_BUF1_BASE : GWFA_BUF0_BASE;
            int *spm = &SPM_unit->buffer[
                id * SPM_BANK_GROUP_SIZE + buf_base];
            int tb_n = spm[1152]; // META_OFF
            int tmp_vd, tmp_k;    // swap registers
            if (id < 3) {
                int *next = &SPM_unit->buffer[
                    (id + 1) * SPM_BANK_GROUP_SIZE + buf_base];
                int next_tb_n = next[1152];
                if (tb_n > 0 && next_tb_n > 0) {
                    int last  = 256 + 2 * (tb_n - 1);
                    int first = 256;
                    // Step 1: compare-and-swap my last ↔ next's first
                    if ((uint32_t)spm[last] > (uint32_t)next[first]) {
                        tmp_vd = spm[last]; tmp_k = spm[last + 1];
                        spm[last] = next[first];
                        spm[last + 1] = next[first + 1];
                        next[first] = tmp_vd;
                        next[first + 1] = tmp_k;
                    }
                    // Step 2: fix my tail (second-to-last vs last)
                    if (tb_n >= 2) {
                        int prev = 256 + 2 * (tb_n - 2);
                        if ((uint32_t)spm[prev] > (uint32_t)spm[last]) {
                            tmp_vd = spm[prev]; tmp_k = spm[prev + 1];
                            spm[prev] = spm[last];
                            spm[prev + 1] = spm[last + 1];
                            spm[last] = tmp_vd;
                            spm[last + 1] = tmp_k;
                        }
                    }
                    // Step 3: fix next PE's head (first vs second)
                    if (next_tb_n >= 2) {
                        int second = 256 + 2;
                        if ((uint32_t)next[first] > (uint32_t)next[second]) {
                            tmp_vd = next[first]; tmp_k = next[first + 1];
                            next[first] = next[second];
                            next[first + 1] = next[second + 1];
                            next[second] = tmp_vd;
                            next[second + 1] = tmp_k;
                        }
                    }
                }
            } else {
                // PE 3: fix tail only (FIFO push moved to magic 9
                // so it's consumed by the NEXT tile group's writeback)
                if (tb_n >= 2) {
                    int last = 256 + 2 * (tb_n - 1);
                    int prev = 256 + 2 * (tb_n - 2);
                    if ((uint32_t)spm[prev] > (uint32_t)spm[last]) {
                        tmp_vd = spm[prev]; tmp_k = spm[prev + 1];
                        spm[prev] = spm[last];
                        spm[prev + 1] = spm[last + 1];
                        spm[last] = tmp_vd;
                        spm[last + 1] = tmp_k;
                    }
                }
            }
        } else if (magic_id == 13) {
            // Phase 2 extend+classify: process diags from A queue.
            // Uses shared extend/mvi2_ld subroutines defined above.
            //
            // gr[]  | name        | notes
            // ------|-------------|-------------------------------
            //  1 lo | i           | loop index
            //  1 hi | tile_n      | input diag count
            //  2    | d           | set by extend
            //  3    | emit_vd     | contiguous with gr[4] for mvd
            //  4    | emit_k/scr  | i_val before branch tree; emit_k after
            //  5 lo | n_pushed    | pushed diag count
            //  5 hi | n_intv      | interval count
            //  6 lo | n_fin0      | finished endQ=0 count
            //  6 hi | n_fin1      | finished endQ=1 count
            //  7    | scratch     | SPM offsets
            //  8    | vd          | current diag (packed v|d_biased)
            //  9    | k           | wavefront offset
            // 11    | ts_off      | seq offset for current diag
            // 12 lo | vl          | vertex length
            // 14    | ql          | query length (read-only)
            // 15    | scratch     |
            constexpr int P2_VK_OFF     = 0;
            constexpr int P2_TS_OFF     = 128;
            constexpr int P2_PUSHED_OFF = 256;
            constexpr int P2_INTV_OFF   = 640;
            constexpr int P2_FIN0_OFF   = 768;
            constexpr int P2_FIN1_OFF   = 896;
            constexpr int P2_META_OFF   = 1024;
            constexpr int P2_M_PUSHED   = 0;
            constexpr int P2_M_INTV     = 1;
            constexpr int P2_M_FIN0     = 2;
            constexpr int P2_M_FIN1     = 3;
            constexpr int P2_M_TILE_N   = 4;
            int tmp;

            int p2_base = (magic_mask & 1) ? GWFA_P2B_BASE : GWFA_P2_BASE;
            int *spm = &SPM_unit->buffer[
                id * SPM_BANK_GROUP_SIZE + p2_base];

            // === INIT ===
            gr.st(1, spm[P2_META_OFF + P2_M_TILE_N], CTRL_GR_HI); // tile_n
            gr.st(1, 0, CTRL_GR_LO);                               // i = 0

            gr.st(5, 0);                                            // n_pushed=0, n_intv=0
            gr.st(6, 0);                                            // n_fin0=0, n_fin1=0

            if (gr.at(1, CTRL_GR_HI) <= 0)
                goto m13_wb; // still write zero metadata
            //NOP

            reg[10] = GWFA_GS_START * 16;  // gs_base
            reg[11] = GWFA_Q_START * 16;   // q_base

            // === LOOP ===
        m13_loop:
            gr.st(7, gr.at(1, CTRL_GR_LO) << 1); // 2*i (paired with branch)
            if (gr.at(1, CTRL_GR_LO) >= gr.at(1, CTRL_GR_HI))
                goto m13_wb;

            // load vd, k from P2_VK_OFF region
            gr.st(8, spm[P2_VK_OFF + gr.at(7)]); gr.st(9, spm[P2_VK_OFF + gr.at(7) + 1]);
            //NOP
            // load ts_off, vl from P2_TS_OFF region (same 2*i index)
            gr.st(11, spm[P2_TS_OFF + gr.at(7)]); gr.st(12, spm[P2_TS_OFF + gr.at(7) + 1]);
            //NOP

            extend(); // sets gr[2]=d, updates gr[9]=k
            //set PC comp

            // === BRANCH TREE ===
            gr.st(15, gr.at(9) + 1); // k+1
            //set PC comp

            //COMP
            tmp = gr.at(15); //This tmp is a little wierd, so I shall explain. In the simulator, the 
                             //comp trace and the data trace happen simultaneously, so the use of 
                             //gr15 does not conflict with the write here. This tmp models that, but
                             //it will not be necessary in the isa. The if statement will use gr15.
                             //In the code you might want to consider something like a to write 
                             //list, and then in all decodes/execs they write the value and dest to 
                             //that list. At the end of pe run you writeback everything
            {
                // k+1 < vl: check i_val+1 vs ql
                gr.st(15, gr.at(2) + gr.at(9) + 1);
                gr.st(7, gr.at(5, CTRL_GR_LO) << 1);  // 2*n_pushed (speculative)
            }
            gr.st(4, gr.at(2) + gr.at(9)); // i_val = d + k
            if (tmp >= gr.at(12, CTRL_GR_LO))
                goto m13_not_mid_v;

            //COMP  (speculative. Assumes we'll make it to midv)
            {
                // gr[7] = 2*n_pushed already computed above
                gr.st(3, gr.at(8) - 1);                // emit_vd = vd-1
                gr.st(4, gr.at(9) + 1);                // emit_k  = k+1
            }
            if (gr.at(15) >= gr.at(14))
                goto m13_only_del;
            //NOP

            // --- MID_V_MID_Q: push 3 diags (gr[3,4] = contiguous mvd pair) ---
            {
                //COMP halt
                // push (vd-1, k+1) — mvd gr[3]
                spm[P2_PUSHED_OFF + gr.at(7)] = gr.at(3); spm[P2_PUSHED_OFF + gr.at(7) + 1] = gr.at(4);
                //set PC comp

                //COMP
                {
                    gr.st(7, gr.at(7) + 2);
                    // push (vd, k+1) — mvd gr[3] (k+1 still in gr[4])
                    gr.st(3, gr.at(8));
                }
                //NOP
                //NOP
                
                spm[P2_PUSHED_OFF + gr.at(7)] = gr.at(3); spm[P2_PUSHED_OFF + gr.at(7) + 1] = gr.at(4); gr.st(7, gr.at(7) + 2); //auto increment
                gr.st(3, gr.at(8) + 1); // push (vd+1, k) — mvd gr[3]
                //COMP
                {
                    gr.st(4, gr.at(9));
                    gr.st(5, gr.at(5, CTRL_GR_LO) + 3, CTRL_GR_LO); // n_pushed+=3
                }

                //COMP halt
                spm[P2_PUSHED_OFF + gr.at(7)] = gr.at(3); spm[P2_PUSHED_OFF + gr.at(7) + 1] = gr.at(4);
                gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO); // i++

                goto m13_loop;
            }

            // --- NOT_MID_V (k+1 >= vl) ---
        m13_not_mid_v:
            //COMP  (overflow. Not desired)
            {
                // gr[7] = 2*n_pushed already computed above
                gr.st(3, gr.at(8) - 1);                // emit_vd = vd-1
                gr.st(4, gr.at(9) + 1);                // emit_k  = k+1
            }
            if (gr.at(15) >= gr.at(14))
                goto m13_end_both;
            //set PC comp

            // --- END_V_MID_Q: intv + finished endQ=0 ---
            {
                //COMP
                {
                    gr.st(7, gr.at(5, CTRL_GR_HI) << 1); // 2*n_intv (speculative)
                    // intv: (vd, vd+1) — mvd gr[3] (gr[3,4] contiguous)
                    // gr[7] = 2*n_intv already computed above
                    gr.st(3, gr.at(8));                    // vd
                }
                gr.st(4, gr.at(8) + 1);               // vd+1
                gr.st(5, gr.at(5, CTRL_GR_HI) + 1, CTRL_GR_HI); // n_intv++

                spm[P2_INTV_OFF + gr.at(7)] = gr.at(3); spm[P2_INTV_OFF + gr.at(7) + 1] = gr.at(4);
                //NOP
                //COMP
                {
                    // finished endQ=0: (vd, k) — mvd gr[8] (gr[8,9] contiguous)
                    gr.st(7, gr.at(6, CTRL_GR_LO) << 1); // 2*n_fin0
                    gr.st(6, gr.at(6, CTRL_GR_LO) + 1, CTRL_GR_LO); // n_fin0++
                }

                //COMP halt
                spm[P2_FIN0_OFF + gr.at(7)] = gr.at(8); spm[P2_FIN0_OFF + gr.at(7) + 1] = gr.at(9);
                gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO); // i++

                goto m13_loop;
            }

            // --- END_BOTH_OR_TERM ---
        m13_end_both:
            // check termination: v==GWFA_END_V(2) && k+1==vl
            if (gr.at(8, CTRL_GR_HI) != 2)
                goto m13_end_both_emit;

            gr.st(15, gr.at(9) + 1);
            //NOP
            
            if (gr.at(15) == gr.at(12, CTRL_GR_LO))
                goto m13_terminate;

        m13_end_both_emit:
            // finished endQ=1: (vd, k)
            {
                //make sure the latter does not overwrite the input of former
                gr.st(7, gr.at(6, CTRL_GR_HI) << 1); // 2*n_fin1
                gr.st(6, gr.at(6, CTRL_GR_HI) + 1, CTRL_GR_HI); // n_fin1++

                spm[P2_FIN1_OFF + gr.at(7)] = gr.at(8); spm[P2_FIN1_OFF + gr.at(7) + 1] = gr.at(9);
                gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO); // i++

                goto m13_loop;
            }

            // --- ONLY_DEL (k+1<vl, i_val+1>=ql) — mvd gr[3] ---
        m13_only_del:
            {
                gr.st(7, gr.at(5, CTRL_GR_LO) << 1); // 2*n_pushed
                gr.st(3, gr.at(8) - 1);               // emit_vd = vd-1

                gr.st(4, gr.at(9) + 1);               // emit_k  = k+1
                gr.st(5, gr.at(5, CTRL_GR_LO) + 1, CTRL_GR_LO); // n_pushed++
                
                spm[P2_PUSHED_OFF + gr.at(7)] = gr.at(3); spm[P2_PUSHED_OFF + gr.at(7) + 1] = gr.at(4);
                gr.st(1, gr.at(1, CTRL_GR_LO) + 1, CTRL_GR_LO); // i++

                goto m13_loop;
            }

        m13_terminate:
            SPM_unit->buffer[32767] = 1;
            //NOP

            goto m13_done;

            // === WRITEBACK ===
        m13_wb:
            spm[P2_META_OFF + P2_M_PUSHED] = gr.at(5, CTRL_GR_LO);
            //NOP
            spm[P2_META_OFF + P2_M_INTV] = gr.at(5, CTRL_GR_HI);
            //NOP
            spm[P2_META_OFF + P2_M_FIN0] = gr.at(6, CTRL_GR_LO);
            //NOP
            spm[P2_META_OFF + P2_M_FIN1] = gr.at(6, CTRL_GR_HI);
            //NOP
        m13_done: ;
        } else if (magic_id == 20) {
            // Sort bin count: contiguous (vd,k,vd,k) mvd loads.
            // Each element is 2 words (vd,k); load 4 contiguous words
            // per iteration to process 2 elements.
            //
            // ISA-lowered per Plan 3d AC-3/AC-4/AC-5: state in
            // gr[]/reg[]; outer for→labeled goto with explicit
            // odd-tail peel; SPM 2-cycle latency between load and
            // bin extraction. tile_buf_off, shift, SPM offsets all
            // kept in full-width slots per BL-20260427-half-reg-
            // truncation-ow (values may exceed int16 range).
            //
            // gr[]  | role
            //  1 lo | i (loop counter; ≤ tile_n ≤ SORT_TILE)
            //  1 hi | tile_n
            //  2    | shift (full)
            //  3    | tile_buf_off (full; SPM offset)
            //  4    | scratch (i*2, i+1)
            //  5    | bin0 (≤ 15)
            //  6    | bin1 (≤ 15)
            //
            // reg[] | role (Plan 3d Round 9 alignment with executable
            //         body — earlier in-code header had stale slot
            //         assignments that didn't match the lowered code)
            //  1    | vd0           (mvd-pair load with reg[2])
            //  2    | k0            (mvd-pair load companion; unused)
            //  3    | vd1           (mvd-pair load with reg[4])
            //  4    | k1            (mvd-pair load companion; unused)
            //  7    | counts[bin] RMW scratch (load -> +1 -> store)
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];

            // === INIT ===
            gr.st(3, (magic_mask & 1) ? SORT_TILE_BUF1 : SORT_TILE_BUF0);
            gr.st(1, spm[SORT_META + 32], CTRL_GR_HI);   // tile_n
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            gr.st(2, spm[SORT_META + 33]);               // shift
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            gr.st(1, 0, CTRL_GR_LO);                     // i = 0

        m20_loop:
            gr.st(4, gr.at(1, CTRL_GR_LO) + 1);          // i+1
            //NOP                                          // RAW break for branch reading gr[4]
            if (gr.at(4) >= gr.at(1, CTRL_GR_HI)) goto m20_tail;
            //NOP                                          // post-branch slot1 guard
            gr.st(4, gr.at(1, CTRL_GR_LO) << 1);         // 2*i
            //NOP

            // 4-word mvd-pair-correct load: (vd0,k0,vd1,k1). k0/k1 are
            // unused at compute time but loaded so the SPM pair reads
            // are contiguous mvd-eligible. Two mvd 2-word loads, each
            // followed by 2-cycle SPM settle.
            reg[1] = spm[gr.at(3) + gr.at(4)];           // mvd: vd0
            reg[2] = spm[gr.at(3) + gr.at(4) + 1];       // mvd: k0 (unused)
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[3] = spm[gr.at(3) + gr.at(4) + 2];       // mvd: vd1
            reg[4] = spm[gr.at(3) + gr.at(4) + 3];       // mvd: k1 (unused)
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle

            gr.st(5, ((uint32_t)reg[1] >> gr.at(2)) & 0xF);   // bin0
            gr.st(6, ((uint32_t)reg[3] >> gr.at(2)) & 0xF);   // bin1

            // counts[bin0]++ — RMW with explicit settle + RAW break.
            reg[7] = spm[SORT_META + gr.at(5)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[7] = reg[7] + 1;
            //NOP                                          // RAW break before store
            spm[SORT_META + gr.at(5)] = reg[7];
            //NOP                                          // SPM port gap before next access

            // counts[bin1]++ — sequential RMW (handles bin0==bin1).
            reg[7] = spm[SORT_META + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[7] = reg[7] + 1;
            //NOP                                          // RAW break before store
            spm[SORT_META + gr.at(6)] = reg[7];

            gr.st(1, gr.at(1, CTRL_GR_LO) + 2, CTRL_GR_LO);  // i += 2
            //NOP                                          // slot-1 guard for goto
            goto m20_loop;

        m20_tail:
            // Odd last element
            if (gr.at(1, CTRL_GR_LO) >= gr.at(1, CTRL_GR_HI))
                goto m20_done;
            //NOP                                          // post-branch slot1 guard
            gr.st(4, gr.at(1, CTRL_GR_LO) << 1);
            //NOP
            reg[1] = spm[gr.at(3) + gr.at(4)];           // mvd: vd
            reg[2] = spm[gr.at(3) + gr.at(4) + 1];       // mvd: k (unused)
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            gr.st(5, ((uint32_t)reg[1] >> gr.at(2)) & 0xF);
            //NOP                                          // RAW break for next reads of gr[5]
            reg[7] = spm[SORT_META + gr.at(5)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[7] = reg[7] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + gr.at(5)] = reg[7];
        m20_done: ;
        } else if (magic_id == 21) {
            // Sort scatter: scatter (vd, k) pairs into per-bin SPM regions.
            //
            // ISA-lowered per Plan 3d AC-3/AC-4/AC-5. Round 3 amendment:
            // bin_cursors[16] moved from reg[16..31] (runtime-indexed
            // register access is not a real ISA op per gendp-isa-reviewer
            // P1) to SPM at SORT_META+34..49 with explicit 2-cycle SPM
            // settle on each access. tile_bin_counts kept SPM-resident
            // at SORT_META+16. Outer pair loop is labeled goto with
            // odd-tail peel; 16-bin init via constexpr unroll over
            // SORT_RADIX_BINS.
            //
            // gr[]  | role
            //  1 lo | i
            //  1 hi | tile_n
            //  2    | shift
            //  3    | tile_buf_off
            //  4    | bin_spm_off
            //  5    | scratch (i*2 / i+1)
            //  6    | bin (current; 0..15)
            //
            // reg[]  | role
            //  1     | vd0/vd
            //  2     | k0/k
            //  3     | vd1
            //  4     | k1
            //  5     | off0/off
            //  6     | off1
            //  7     | bin_cursor scratch (load / RMW)
            //  8     | tile_bin_count scratch
            //
            // SPM-resident state:
            //   spm[SORT_META + 0..15]  : final bin_counts (untouched)
            //   spm[SORT_META + 16..31] : tile_bin_counts (init + inc)
            //   spm[SORT_META + 34..49] : bin_cursors (init + RMW; new
            //                             slot region added by Round 3
            //                             ABI amendment to satisfy
            //                             reviewer P1 on indirect reg)
            constexpr int BIN_CUR_OFF = 34;
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];

            // === INIT ===
            gr.st(3, (magic_mask & 1) ? SORT_TILE_BUF1 : SORT_TILE_BUF0);
            gr.st(4, (magic_mask & 1) ? SORT_BIN_SPM1  : SORT_BIN_SPM0);
            gr.st(1, spm[SORT_META + 32], CTRL_GR_HI);
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            gr.st(2, spm[SORT_META + 33]);
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle

            // bin_cursors[b] = 0 (SPM) + tile_bin_counts[b] = 0 (SPM)
            // Round 4 fix: literal-unrolled 16-store init (no runtime
            // for-loop in lowered magic body per AC-4). Plan 3d Round 7
            // l9c P1 fix per Codex audit (round-7-audit-findings.md):
            // each pair of non-contiguous stores split onto separate
            // ISA lines with explicit SPM port-gap NOPs. Each store
            // occupies its own VLIW cycle; 1 SPM port per PE preserved.
            spm[SORT_META + 16] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  0] = 0; //NOP   // SPM port gap
            spm[SORT_META + 17] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  1] = 0; //NOP   // SPM port gap
            spm[SORT_META + 18] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  2] = 0; //NOP   // SPM port gap
            spm[SORT_META + 19] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  3] = 0; //NOP   // SPM port gap
            spm[SORT_META + 20] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  4] = 0; //NOP   // SPM port gap
            spm[SORT_META + 21] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  5] = 0; //NOP   // SPM port gap
            spm[SORT_META + 22] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  6] = 0; //NOP   // SPM port gap
            spm[SORT_META + 23] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  7] = 0; //NOP   // SPM port gap
            spm[SORT_META + 24] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  8] = 0; //NOP   // SPM port gap
            spm[SORT_META + 25] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF +  9] = 0; //NOP   // SPM port gap
            spm[SORT_META + 26] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF + 10] = 0; //NOP   // SPM port gap
            spm[SORT_META + 27] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF + 11] = 0; //NOP   // SPM port gap
            spm[SORT_META + 28] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF + 12] = 0; //NOP   // SPM port gap
            spm[SORT_META + 29] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF + 13] = 0; //NOP   // SPM port gap
            spm[SORT_META + 30] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF + 14] = 0; //NOP   // SPM port gap
            spm[SORT_META + 31] = 0;             //NOP   // SPM port gap
            spm[SORT_META + BIN_CUR_OFF + 15] = 0; //NOP   // SPM port gap

            gr.st(1, 0, CTRL_GR_LO);

        m21_loop:
            gr.st(5, gr.at(1, CTRL_GR_LO) + 1);
            //NOP                                          // RAW break
            if (gr.at(5) >= gr.at(1, CTRL_GR_HI)) goto m21_tail;
            //NOP                                          // post-branch slot1 guard
            gr.st(5, gr.at(1, CTRL_GR_LO) << 1);          // 2*i
            //NOP

            // 4-word mvd-pair-correct load: (vd0, k0, vd1, k1) split
            // into two 2-word mvds with explicit settle between.
            reg[1] = spm[gr.at(3) + gr.at(5)];           // mvd: vd0
            reg[2] = spm[gr.at(3) + gr.at(5) + 1];       // mvd: k0
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[3] = spm[gr.at(3) + gr.at(5) + 2];       // mvd: vd1
            reg[4] = spm[gr.at(3) + gr.at(5) + 3];       // mvd: k1
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle

            // --- Scatter element 0 ---
            gr.st(6, ((uint32_t)reg[1] >> gr.at(2)) & 0xF);   // bin0
            //NOP                                          // RAW break
            // Read bin_cursors[bin0] from SPM
            reg[7] = spm[SORT_META + BIN_CUR_OFF + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            // off0 = bin0 * (REGION_SIZE * 2) + cursor * 2
            reg[5] = gr.at(6) * (SORT_BIN_REGION_SIZE * 2)
                + (reg[7] << 1);
            //NOP                                          // RAW break
            spm[gr.at(4) + reg[5]]     = reg[1];           // vd0
            spm[gr.at(4) + reg[5] + 1] = reg[2];           // k0
            //NOP                                          // SPM port gap
            // Inc cursor (RMW): reg[7] already holds old cursor value
            reg[7] = reg[7] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + BIN_CUR_OFF + gr.at(6)] = reg[7];
            //NOP                                          // SPM port gap
            // tile_bin_counts[bin0]++ (SPM RMW)
            reg[8] = spm[SORT_META + 16 + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[8] = reg[8] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + 16 + gr.at(6)] = reg[8];
            //NOP                                          // SPM port gap

            // --- Scatter element 1 ---
            gr.st(6, ((uint32_t)reg[3] >> gr.at(2)) & 0xF);   // bin1
            //NOP                                          // RAW break
            reg[7] = spm[SORT_META + BIN_CUR_OFF + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[6] = gr.at(6) * (SORT_BIN_REGION_SIZE * 2)
                + (reg[7] << 1);
            //NOP                                          // RAW break
            spm[gr.at(4) + reg[6]]     = reg[3];           // vd1
            spm[gr.at(4) + reg[6] + 1] = reg[4];           // k1
            //NOP                                          // SPM port gap
            reg[7] = reg[7] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + BIN_CUR_OFF + gr.at(6)] = reg[7];
            //NOP                                          // SPM port gap
            reg[8] = spm[SORT_META + 16 + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[8] = reg[8] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + 16 + gr.at(6)] = reg[8];
            //NOP                                          // SPM port gap

            gr.st(1, gr.at(1, CTRL_GR_LO) + 2, CTRL_GR_LO);
            //NOP                                          // slot-1 guard
            goto m21_loop;

        m21_tail:
            if (gr.at(1, CTRL_GR_LO) >= gr.at(1, CTRL_GR_HI))
                goto m21_done;
            //NOP                                          // post-branch slot1 guard
            gr.st(5, gr.at(1, CTRL_GR_LO) << 1);
            //NOP
            reg[1] = spm[gr.at(3) + gr.at(5)];           // mvd: vd
            reg[2] = spm[gr.at(3) + gr.at(5) + 1];       // mvd: k
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            gr.st(6, ((uint32_t)reg[1] >> gr.at(2)) & 0xF);
            //NOP                                          // RAW break
            reg[7] = spm[SORT_META + BIN_CUR_OFF + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[5] = gr.at(6) * (SORT_BIN_REGION_SIZE * 2)
                + (reg[7] << 1);
            //NOP                                          // RAW break
            spm[gr.at(4) + reg[5]]     = reg[1];
            spm[gr.at(4) + reg[5] + 1] = reg[2];
            //NOP                                          // SPM port gap
            reg[7] = reg[7] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + BIN_CUR_OFF + gr.at(6)] = reg[7];
            //NOP                                          // SPM port gap
            reg[8] = spm[SORT_META + 16 + gr.at(6)];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            reg[8] = reg[8] + 1;
            //NOP                                          // RAW break
            spm[SORT_META + 16 + gr.at(6)] = reg[8];
        m21_done: ;
        } else if (magic_id == 22) {
            // Merge: input-capped two-pointer merge with ping-pong tiles.
            //
            // Plan 2b Milestone A restructure: buffer-exhaustion
            // transitions are labeled (m22_switch_a, m22_switch_b)
            // and execute only after the post-emit exhaustion check,
            // not on every iteration as the prior draft did. Unified
            // compare retained per BL-20260413-drain-budget (no
            // separate drain loop).
            //
            // Durable invariant set (AC-4 evidence):
            //
            //   m22_top: entered iff
            //     - budget: (ai - ai0) + (bi - bi0) < MERGE_STEP.
            //     - streams: (ai < a_n) OR (bi < b_n). At least one
            //       head is available. Both-exhausted never reaches
            //       m22_top's compare: the switch labels route to
            //       m22_done directly.
            //     - aw,bw in {0,1}; ab = MERGE_A_BUFaw,
            //       bb = MERGE_B_BUFbw; a_n = spm[MERGE_META+9+aw],
            //       b_n = spm[MERGE_META+11+bw] (live tile counts).
            //     - ai0, bi0 track this-invocation consumed offset:
            //       ai0 = ai and bi0 = bi on entry; each successful
            //       switch decreases the matching baseline by the
            //       exhausted tile count so (ai - ai0) + (bi - bi0)
            //       still equals items emitted THIS invocation.
            //       Preserves the original budget formula exactly.
            //
            //   m22_switch_a: entered iff ai >= a_n (either just
            //     exhausted by the last emit or pre-existing from a
            //     prior invocation's unfinished tail). Tries a
            //     buffer swap. If no alternate tile (on == 0), A is
            //     globally drained and the unified compare drains
            //     via B. bi state is arbitrary at entry.
            //
            //   m22_switch_b: entered iff bi >= b_n. Symmetric to
            //     m22_switch_a. Also runs the only
            //     both-globally-drained check on a rare path; that
            //     transitions to m22_done.
            //
            //   m22_done: reached iff budget hit OR both streams
            //     globally drained. Saves ai/bi/oi/aw/bw and cum_oi
            //     + oi to SPM. spm[976..983] writes are bit-exact
            //     relative to pre-Plan-2b behavior per AC-5 and
            //     BL-20260413-pe-global-base.
            int out_off = (magic_mask & 1) ? MERGE_OUT1 : MERGE_OUT0;
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];
            // Plan 3d Round 4: m22 within-call state aliases reg[1..15,
            // 28..31] per AC-2 amendment Section 3.2. C++ references
            // alias the register storage; AC-3 compliant.
            int& ai      = reg[1];
            int& bi      = reg[2];
            int& aw      = reg[3];
            int& bw      = reg[4];
            int& a_n     = reg[5];
            int& b_n     = reg[6];
            int& ab      = reg[7];
            int& bb      = reg[8];
            int& oi      = reg[9];
            int& ai0     = reg[10];
            int& bi0     = reg[11];
            int& out_lo  = reg[12];
            int& out_hi  = reg[13];
            int& bvd_0   = reg[14];
            int& bvd_1   = reg[15];
            int& bvd_2   = reg[28];
            int& gpos    = reg[29];
            int& scratch_lo = reg[30];   // head_a_lo / probe_h / o
            int& scratch_hi = reg[31];   // head_b_lo / probe_l / on
            // Initialize from SPM-resident cross-call state.
            // Plan 3d Round 6 l9c: SPM port-gap discipline applied to
            // entry-block loads. Adjacent contiguous pairs annotated
            // mvd: (single ISA op, 1 SPM port). Non-contiguous loads
            // separated by `// SPM port gap` NOPs.
            ai  = spm[MERGE_META + 0];                   // mvd: (ai, bi)
            bi  = spm[MERGE_META + 1];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            aw  = spm[MERGE_META + 7];                   // mvd: (aw, bw)
            bw  = spm[MERGE_META + 8];
            //NOP                                          // SPM settle (also: a_n/b_n below need aw/bw register-resident)
            //NOP                                          // SPM settle
            a_n = spm[MERGE_META + 9 + aw];              // non-contig (depends on aw)
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            b_n = spm[MERGE_META + 11 + bw];             // non-contig (depends on bw)
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            ab  = aw ? MERGE_A_BUF1 : MERGE_A_BUF0;
            bb  = bw ? MERGE_B_BUF1 : MERGE_B_BUF0;
            int *out = &spm[out_off];
            oi  = 0;
            ai0 = ai; bi0 = bi;
            // Plan 3d l8d: bvd[3] C++ local array eliminated per AC-3.
            // Boundary positions (32-bit packed v|d sentinels) loaded
            // into reg[14], reg[15], reg[28]. mvd-pair (bvd_0, bvd_1)
            // at +13/+14; bvd_2 at +15 is a 1-word straggler with port
            // gap separator.
            bvd_0 = spm[MERGE_META+13];                  // mvd: (bvd_0, bvd_1)
            bvd_1 = spm[MERGE_META+14];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            bvd_2 = spm[MERGE_META+15];                  // 1-word straggler
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            // Plan 3d Round 8 l8d (AC-3): cum_oi / pe_global_base
            // migrated to gr[12] / gr[13] full-int register homes.
            //
            // ABI amendment rationale: the committed AC-2 artifact
            // Section 3.1 line 134 originally specified
            // "m22 lo=cum_oi / hi=pe_global_base" (gr[6] half-reg
            // packing). Empirical evidence from the PE 22 frozen
            // snapshot oracle shows cum_oi reaching 1589365 in case 0
            // (PE 0), well above the int16_t [-32768,32767] range. Per
            // BL-20260427-half-reg-truncation-ow, packing such values
            // into a half-register silently truncates to 16 bits and
            // corrupts the snapshot output. Round 8 amends the
            // artifact to assign cum_oi → gr[12] (full int) and
            // pe_global_base → gr[13] (full int); the half-reg
            // packing in the artifact's original specification is
            // documented as a per-AC-2 controlled-change amendment.
            gr.st(12, spm[982]);             // mvd: (cum_oi, pe_global_base)
            gr.st(13, spm[983]);
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            // Entry: reconcile pre-existing exhaustion from prior
            // invocation's tail before the first compare.
            if (ai >= a_n) goto m22_switch_a;
            if (bi >= b_n) goto m22_switch_b;
        m22_top:
            if ((ai - ai0) + (bi - bi0) >= MERGE_STEP) goto m22_done;
            // Unified compare + emit (OPT-1 fast-path: retain emitted
            // values in out_lo/out_hi registers so the boundary block
            // reuses them instead of reloading from SPM — 2 fewer SPM
            // loads per iteration). Per BL-20260413-drain-budget, this
            // single predicate handles dual-stream merge and single-
            // stream drain. No separate drain path.
            //
            // AC-7 cycle accounting for the emit block. Each branch
            // arm has the shape:
            //   cycle N    : mvd: (out_lo, out_hi) = spm[X..X+1]
            //   cycle N+1  : 2 NOPs (SPM settle, AC-7 latency gap)
            //   cycle N+2  : consumer — out[oi*2] = out_lo;
            //                          out[oi*2+1] = out_hi; bi++; oi++;
            // Plan 3d Round 7 l9c P2 fix per Codex audit: removed the
            // earlier "exception-approved" waiver comment block that
            // described an older shape lacking the 2-cycle SPM settle.
            // The current code (lines below) IS cycle-separated; no
            // waiver is needed and ABI Section 5 waiver table remains
            // empty. Boundary block reads out_lo/out_hi as register
            // reads many cycles later (exhaustion checks + gpos
            // compute intervene), so boundary reads are AC-7 legal.
            // Round 5 reviewer P1: staged SPM loads (one port per cycle).
            // Plan 3d Round 4: out_lo/out_hi in reg[12]/reg[13];
            // head_a_lo/head_b_lo time-multiplexed on reg[30]/reg[31].
            scratch_lo = 0; scratch_hi = 0;     // head_a_lo / head_b_lo
            if (ai < a_n) {
                scratch_lo = spm[ab+ai*2];      // head_a_lo
                //NOP                                    // SPM settle
                //NOP                                    // SPM settle
            }
            if (bi < b_n) {
                scratch_hi = spm[bb+bi*2];      // head_b_lo
                //NOP                                    // SPM settle
                //NOP                                    // SPM settle
            }
            if (ai >= a_n
                || (bi < b_n
                    && (uint32_t)scratch_hi < (uint32_t)scratch_lo)) {
                out_lo = spm[bb+bi*2];                  // SPM load N slot 0
                out_hi = spm[bb+bi*2+1];                // SPM load N slot 1
                //NOP                                    // SPM N+1 slot 0
                //NOP                                    // SPM N+1 slot 1
                out[oi*2]   = out_lo;                   // N+2 consumer
                out[oi*2+1] = out_hi; bi++; oi++;
            } else {
                out_lo = spm[ab+ai*2];                  // SPM load N slot 0
                out_hi = spm[ab+ai*2+1];                // SPM load N slot 1
                //NOP                                    // SPM N+1 slot 0
                //NOP                                    // SPM N+1 slot 1
                out[oi*2]   = out_lo;                   // N+2 consumer
                out[oi*2+1] = out_hi; ai++; oi++;
            }
            // Boundary tracking — bit-exact preservation per AC-5/AC-7.
            // Plan 3d l8d: runtime `for (b = 0; b < 3)` boundary loop
            // unrolled to 6 explicit hi/lo comparisons in the same per-b
            // order as the original (b=0 hi → b=0 lo → b=1 hi → b=1 lo
            // → b=2 hi → b=2 lo). Uses bvd_0 / bvd_1 / bvd_2 register
            // homes (post-AC-3 elimination of bvd[3]).
            // Round 4 reviewer P0 fix: each `if (spm[...] < 0 && ...)`
            // line packs SPM load + cmp + cond-store; without explicit
            // settle the SPM 2-cycle latency is violated. Restructured:
            // load `probe_X` into a local, settle 2 cycles, compare,
            // conditional store, port-gap NOP between adjacent SPM ops.
            // Plan 3d Round 4 (AC-3): gpos in reg[29]; probe_h_X /
            // probe_l_X time-multiplexed on reg[30] (scratch_lo).
            gpos = gr.at(13) + gr.at(12) + oi - 1;
            scratch_lo = spm[976];                       // probe_h0
            //NOP                                         // SPM settle
            //NOP                                         // SPM settle
            if (scratch_lo < 0 && (uint32_t)out_hi >  (uint32_t)bvd_0) spm[976] = gpos;
            //NOP                                         // SPM port gap
            scratch_lo = spm[979];                       // probe_l0
            //NOP
            //NOP
            // > (not >=): probe_l_X records the first gpos where intv.vd0
            // strictly exceeds pivot bvd_X. This is the lower-bound seam
            // index for PE_X's interval window. Strict > makes intervals
            // starting AT the pivot (vd0 == pivot) belong to the lower-PE
            // window so that a PE-low diag at vd == pivot (cross-PE
            // same-vd duplicate) is dropped by the interval covering it.
            // Pair with m38 binary-search h-step `<=` change. Symptom of
            // mis-pairing: q002 dist=7 extra WF 61 4305 0.
            if (scratch_lo < 0 && (uint32_t)out_lo > (uint32_t)bvd_0) spm[979] = gpos;
            //NOP                                         // SPM port gap
            scratch_lo = spm[977];                       // probe_h1
            //NOP
            //NOP
            if (scratch_lo < 0 && (uint32_t)out_hi >  (uint32_t)bvd_1) spm[977] = gpos;
            //NOP                                         // SPM port gap
            scratch_lo = spm[980];                       // probe_l1
            //NOP
            //NOP
            if (scratch_lo < 0 && (uint32_t)out_lo > (uint32_t)bvd_1) spm[980] = gpos;
            //NOP                                         // SPM port gap
            scratch_lo = spm[978];                       // probe_h2
            //NOP
            //NOP
            if (scratch_lo < 0 && (uint32_t)out_hi >  (uint32_t)bvd_2) spm[978] = gpos;
            //NOP                                         // SPM port gap
            scratch_lo = spm[981];                       // probe_l2
            //NOP
            //NOP
            if (scratch_lo < 0 && (uint32_t)out_lo > (uint32_t)bvd_2) spm[981] = gpos;
            // Post-emit exhaustion check (rare path).
            if (ai >= a_n) goto m22_switch_a;
            if (bi >= b_n) goto m22_switch_b;
            goto m22_top;
        m22_switch_a:
            // Plan 3d Round 4 (AC-3): o/on time-multiplex on
            // scratch_lo / scratch_hi (reg[30]/reg[31]).
            scratch_lo = aw ^ 1;                            // o
            scratch_hi = spm[MERGE_META + 9 + scratch_lo];  // on
            //NOP                                            // SPM settle
            //NOP                                            // SPM settle
            if (scratch_hi > 0) {
                spm[MERGE_META + 9 + aw] = 0;
                aw = scratch_lo;
                ab = aw ? MERGE_A_BUF1 : MERGE_A_BUF0;
                ai = 0; ai0 -= a_n; a_n = scratch_hi;
            }
            if (bi >= b_n) goto m22_switch_b;
            goto m22_top;
        m22_switch_b:
            scratch_lo = bw ^ 1;                            // o
            scratch_hi = spm[MERGE_META + 11 + scratch_lo]; // on
            //NOP                                            // SPM settle
            //NOP                                            // SPM settle
            if (scratch_hi > 0) {
                spm[MERGE_META + 11 + bw] = 0;
                bw = scratch_lo;
                bb = bw ? MERGE_B_BUF1 : MERGE_B_BUF0;
                bi = 0; bi0 -= b_n; b_n = scratch_hi;
            }
            if (ai >= a_n && bi >= b_n) goto m22_done;
            goto m22_top;
        m22_done:
            // Round 5 reviewer P1 fix: SPM port gaps between m22_done
            // publishes. Adjacent stores (MERGE_META+0/+1 mvd-pair,
            // MERGE_META+4 isolated, MERGE_META+7/+8 mvd-pair, spm[982]
            // isolated) need explicit settle gaps per 1-port-per-PE rule.
            spm[MERGE_META+0]=ai; spm[MERGE_META+1]=bi;
            //NOP                                          // SPM port gap
            spm[MERGE_META+4]=oi;
            //NOP                                          // SPM port gap
            spm[MERGE_META+7]=aw; spm[MERGE_META+8]=bw;
            //NOP                                          // SPM port gap
            spm[982] = gr.at(12) + oi;
            // Plan 3d l8d: GWFA_AC5_DUMP env-gated dump removed
            // (AC-3 — env-gated debug counters / fopen branches not
            // permitted in lowered magic body; PLAN3D_TRACE_SNAPSHOT
            // dump below is the supported probe).
#ifdef PLAN3D_TRACE_SNAPSHOT
            // Frozen observable dump: MERGE_META[0..8] + spm[976..983].
            {
                std::ofstream &snap22 = plan3d_snap_pe22();
                snap22 << "pe22 pe=" << id;
                for (int i = 0; i <= 8; i++)
                    snap22 << " MM[" << i << "]=" << spm[MERGE_META + i];
                snap22 << " spm976_981=";
                for (int i = 976; i <= 981; i++) snap22 << spm[i] << ",";
                snap22 << " spm982=" << spm[982]
                       << " spm983=" << spm[983] << std::endl;
            }
#endif
        } else if (magic_id == 23) {
            // Tiled dedup: state machine with TILE_SIZE counter,
            // dual input ping-pong, inline intv merge-adjacent.
            // States: X=merge same-vd, B=advance intv, C=drain intv.
            // mask bit 0 selects output ping (OUT0) or pong (OUT1).
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];
            int do_off = (magic_mask & 1)
                ? DEDUP_DIAG_OUT1 : DEDUP_DIAG_OUT0;
            int io_off = (magic_mask & 1)
                ? DEDUP_INTV_OUT1 : DEDUP_INTV_OUT0;
            // DEC-1 phase cookie protocol (Plan 3d Round 2 amendment).
            // Magic 29 (`pe_array.cpp:6513`) sets spm[DEDUP_META+8] =
            // 0xFFFFFFFFU at every per-step dedup init. PE 23 entry:
            //   sentinel set: seed reg[16..27] from SPM moved slots;
            //                 write spm[DEDUP_META+8] = 0 to consume.
            //   sentinel clear: use reg[16..27] directly.
            uint32_t cookie = (uint32_t)spm[DEDUP_META + 8];
            //NOP                                          // SPM settle
            //NOP                                          // SPM settle
            if (cookie == 0xFFFFFFFFU) {
                // Plan 3d Round 6 l9c: cookie-seed adjacent contiguous
                // pairs annotated mvd: (single ISA op per pair). Each
                // mvd-pair followed by 2-NOP SPM settle for AC-5 / AC-7
                // discipline. The final cookie-consume store
                // `spm[DEDUP_META + 8] = 0` is preceded by an SPM port
                // gap so it doesn't collide with the prior load pair.
                reg[16] = spm[DEDUP_META + 0];           // mvd: (pv, pk)
                reg[17] = spm[DEDUP_META + 1];
                //NOP                                      // SPM settle
                //NOP                                      // SPM settle
                reg[18] = spm[DEDUP_META + 4];           // mvd: (dc, ic)
                reg[19] = spm[DEDUP_META + 5];
                //NOP                                      // SPM settle
                //NOP                                      // SPM settle
                reg[20] = spm[DEDUP_META + 6];           // mvd: (dw, iw)
                reg[21] = spm[DEDUP_META + 7];
                //NOP                                      // SPM settle
                //NOP                                      // SPM settle
                reg[22] = spm[DEDUP_META + 14];          // mvd: (clo, chi)
                reg[23] = spm[DEDUP_META + 15];
                //NOP                                      // SPM settle
                //NOP                                      // SPM settle
                reg[24] = spm[DEDUP_META + 16];          // mvd: (state, pdone)
                reg[25] = spm[DEDUP_META + 17];
                //NOP                                      // SPM settle
                //NOP                                      // SPM settle
                reg[26] = spm[DEDUP_META + 18];          // mvd: (nv, nk)
                reg[27] = spm[DEDUP_META + 19];
                //NOP                                      // SPM settle
                //NOP                                      // SPM settle
                spm[DEDUP_META + 8] = 0;                 // cookie consume
                //NOP                                      // SPM port gap
                //NOP                                      // SPM settle
            }
            // Cross-call DEC-1 state aliases (reg[16..27] — Round 9c).
            // C++ references: storage lives in registers; identifiers
            // alias for readable access. AC-3 compliant — no separate
            // C++ local state, since reads/writes resolve to the
            // underlying register slot directly.
            int& pv    = reg[16];
            int& pk    = reg[17];
            int& dc    = reg[18];
            int& ic    = reg[19];
            int& dw    = reg[20];
            int& iw    = reg[21];
            int& clo   = reg[22];
            int& chi   = reg[23];
            int& state = reg[24];
            int& pdone = reg[25];
            int& nv    = reg[26];
            int& nk    = reg[27];
            // Within-call state aliases (reg[9..15, 28..31] — Plan 3d
            // Round 3 amendment, full int). reg[] supports C++
            // operator[] and reference aliasing; gr is `addr_regfile`
            // with .at()/.st() methods only.
            int& p     = reg[9];
            int& n_do  = reg[10];
            int& n_io  = reg[11];
            int& dtn   = reg[12];
            int& don_  = reg[13];
            int& itn   = reg[14];
            int& ion   = reg[15];
            int& db    = reg[28];
            int& ib    = reg[29];
            int& ad    = reg[30];
            int& ai    = reg[31];
            // Initialize within-call state at entry. DEDUP_META+8 was
            // the DEC-1 phase init cookie (consumed above). +9 stays
            // dead (Plan 2b Milestone B). +10..+13 (dtn/don_/itn/ion
            // SPM mirror) remain SPM-resident because controller
            // magics 30/31 read/write them between PE 23 calls.
            n_do = 0; n_io = 0; p = 0; ad = 0; ai = 0;
            // Plan 3d Round 6 l9c: dtn/don_/itn/ion are non-contiguous
            // SPM addresses (depend on dw, iw selectors) so each load
            // is a scalar mv with explicit SPM port gap NOPs separating
            // adjacent loads.
            dtn  = spm[DEDUP_META + 10 + dw];
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            don_ = spm[DEDUP_META + 10 + (dw^1)];
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            itn  = spm[DEDUP_META + 12 + iw];
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            ion  = spm[DEDUP_META + 12 + (iw^1)];
            //NOP                                          // SPM port gap
            //NOP                                          // SPM settle
            db   = dw ? DEDUP_DIAG_BUF1 : DEDUP_DIAG_BUF0;
            ib   = iw ? DEDUP_INTV_BUF1 : DEDUP_INTV_BUF0;
#ifdef PLAN3D_TRACE_SNAPSHOT
            {
                static int dumped_entry[4] = {0, 0, 0, 0};
                if ((magic_mask & 1) == 0 && !dumped_entry[id]) {
                    std::ofstream &snap23 = plan3d_snap_pe23();
                    snap23 << "pe23 pe=" << id << " phase=entry";
                    for (int i = 0; i < 20; i++)
                        snap23 << " dm[" << i << "]="
                               << spm[DEDUP_META + i];
                    snap23 << std::endl;
                    dumped_entry[id] = 1;
                }
            }
#endif

            // --- Inline helpers (no lambdas for ISA lowering) ---
            // Cycle-accounting convention: each code line = 1 gendp
            // ISA instruction (one slot of a VLIW pair); each pair of
            // consecutive lines = 1 VLIW cycle. 2-cycle SPM latency:
            // load in cycle N; data arrives at end of cycle N+1;
            // earliest legal consumer is cycle N+2.
            //
            // Read next diag: inline buffer-switch + read.
            //   SPM loads: cycle N slot 0 (vd_out) + slot 1 (k_out).
            //   sep: cycle N+1 slot 0 (dc++) + slot 1 (p++) — both
            //        ops are independent of the loaded data.
            //   Consumer (first use of vd_out or k_out by the caller)
            //   lands at cycle N+2 or later. Concrete call-site
            //   consumer cycles:
            //     m23_X (line 1737): `if (pv == 0xFFFFFFFFU)` reads
            //       pv at cycle N+2 slot 0; first use of vd at the
            //       `pv = vd` assignment inside the taken branch is
            //       cycle N+3 slot 0 (after the branch separator).
            //     Subsequent checks `if (vd == pv)` (line 1738) and
            //       `nv = vd` (line 1739) all land at cycle N+3 or
            //       later — all >= N+2, so AC-7 legal.
            #define M23_RD(vd_out, k_out, fail_label) do { \
                if (dc >= dtn) { \
                    spm[DEDUP_META + 10 + dw] = 0; \
                    dw ^= 1; \
                    db = dw ? DEDUP_DIAG_BUF1 : DEDUP_DIAG_BUF0; \
                    dtn = don_; don_ = 0; dc = 0; \
                    if (dtn == 0) { ad = 1; goto fail_label; } \
                } \
                vd_out = spm[db+dc*2];             /* cycle N slot 0 */ \
                k_out  = spm[db+dc*2+1];           /* cycle N slot 1 */ \
                dc++;                              /* cycle N+1 slot 0 (sep) */ \
                p++;                               /* cycle N+1 slot 1 (sep) */ \
            } while(0)
            // Read next intv: same cycle-accounting contract as
            // M23_RD. SPM loads at cycle N, independent ic++/p++
            // separators at cycle N+1, consumer at cycle N+2+.
            // Concrete call-site consumer cycles:
            //   m23_B_loop (line 1753): `if (p >= DEDUP_TILE)` reads
            //     p only (not lo/hi) at cycle N+2 slot 0; first use
            //     of lo/hi is `clo = lo; chi = hi` at cycle N+3 or
            //     later.
            //   m23_C_loop (line 1801): same pattern, consumer at
            //     cycle N+3 or later.
            //   m23_B_peek inner (line 1765): the `M23_RI(d1, d2, ...)`
            //     drops d1/d2 (unused), so effectively no consumer —
            //     the load serves only to advance `ic`/`p`.
            #define M23_RI(lo_out, hi_out, fail_label) do { \
                if (ic >= itn) { \
                    spm[DEDUP_META + 12 + iw] = 0; \
                    iw ^= 1; \
                    ib = iw ? DEDUP_INTV_BUF1 : DEDUP_INTV_BUF0; \
                    itn = ion; ion = 0; ic = 0; \
                    if (itn == 0) { ai = 1; goto fail_label; } \
                } \
                lo_out = spm[ib+ic*2];             /* cycle N slot 0 */ \
                hi_out = spm[ib+ic*2+1];           /* cycle N slot 1 */ \
                ic++;                              /* cycle N+1 slot 0 (sep) */ \
                p++;                               /* cycle N+1 slot 1 (sep) */ \
            } while(0)
            // Peek next intv without consuming. Unlike M23_RD / M23_RI
            // which bundle `dc++; p++` (or `ic++; p++`) as natural
            // separator ops, M23_PI has no state mutation and needs
            // explicit NOP-comment separators so the real-ISA
            // lowering inserts 2 NOPs in the cycle-N+1 slots before
            // the consumer line. Pattern mirrors pe_array.cpp's
            // SPM-latency `//NOP` comments.
            //   SPM loads: cycle N slot 0 (lo_out) + slot 1 (hi_out).
            //   sep: cycle N+1 slot 0 + slot 1 (real ISA NOPs).
            //   Consumer cycles per call site:
            //     m23_B_peek (line 1763): `if (l2 <= chi)` reads l2
            //       at cycle N+2 slot 0 — exactly the minimum legal
            //       slot, AC-7 legal.
            //     m23_C_peek (line 1810): `if (lo <= chi)` reads lo
            //       at cycle N+2 slot 0 — same.
            // M23_PI internal temps mapped to reg[5..8] per Round 3
            // ABI amendment: reg[5]=tc_, reg[6]=tw_, reg[7]=tt_,
            // reg[8]=tb_. Within-call only — caller-dead at entry.
            #define M23_PI(lo_out, hi_out, fail_label) do { \
                reg[5] = ic;                              /* tc_ = ic */ \
                reg[6] = iw;                              /* tw_ = iw */ \
                reg[7] = itn;                             /* tt_ = itn */ \
                reg[8] = ib;                              /* tb_ = ib */ \
                if (reg[5] >= reg[7]) { \
                    reg[6] ^= 1; \
                    reg[8] = reg[6] ? DEDUP_INTV_BUF1 : DEDUP_INTV_BUF0; \
                    reg[7] = ion; reg[5] = 0; \
                    if (reg[7] == 0) goto fail_label; \
                } \
                lo_out = spm[reg[8]+reg[5]*2];            /* cycle N slot 0 */ \
                hi_out = spm[reg[8]+reg[5]*2+1];          /* cycle N slot 1 */ \
                /*NOP*/ /* cycle N+1 slot 0 (AC-7 sep; real ISA NOP) */ \
                /*NOP*/ /* cycle N+1 slot 1 (AC-7 sep; real ISA NOP) */ \
            } while(0)
            // Controller-visible output (read by magic 30/31 between calls)
            #define M23_SAVE_OUT do { \
                spm[DEDUP_META+2]=n_do; spm[DEDUP_META+3]=n_io; \
            } while(0)
            // PE-internal resume state — DEC-1 register-resident
            // (Plan 3d Round 2 + Round 3). Cross-call locals
            // (pv/pk/dc/ic/dw/iw/clo/chi/state/pdone/nv/nk) are now
            // C++ references aliasing reg[16..27], so writes during
            // the body update register storage directly. SAVE_RESUME
            // becomes a documentation-only no-op marking the SAVE
            // chokepoint; the actual register state IS the live
            // resume state.
            #define M23_SAVE_RESUME do { } while(0)
            #define M23_SAVE do { M23_SAVE_OUT; M23_SAVE_RESUME; } while(0)
            // M23_SAVE_LIGHT (Plan 2b Milestone C1, p2b): omit the
            // M23_SAVE_RESUME writes at yield points where pv/pk/clo/
            // chi/state/pdone/nv/nk are provably unchanged since
            // entry. Saves 12 SPM stores per light yield. Used at
            // the `pdone`-skip yield (entry-time pass-through when
            // dedup already completed in a prior invocation) where
            // no state was modified this invocation. The resume
            // slots hold the prior invocation's save bytes, which
            // are the correct values for the next entry.
            #define M23_SAVE_LIGHT do { M23_SAVE_OUT; } while(0)

            if (pdone) goto m23_save_light_and_exit;
            if (state == 1) goto m23_B;
            if (state == 2) goto m23_C;

            // --- State X: merge same-vd diags ---
            // M23_RD shares output slots with M23_RI: reg[1]=vd/lo,
            // reg[2]=k/hi (different code paths — RD only fires in
            // m23_X, RI only in m23_B/m23_C).
m23_X:      if (p >= DEDUP_TILE) { state = 0; goto m23_save_full_and_exit; }
            M23_RD(reg[1], reg[2], m23_X_diags_done);
            if (pv == (int)0xFFFFFFFF) { pv = reg[1]; pk = reg[2]; goto m23_X; }
            if (reg[1] == pv) { if (reg[2] > pk) pk = reg[2]; goto m23_X; }
            nv = reg[1]; nk = reg[2];
            goto m23_B;
m23_X_diags_done:
            if (pv != (int)0xFFFFFFFF) { nv = (int)0xFFFFFFFF; goto m23_B; }
            goto m23_C;

m23_B:      // Advance intv past pv (State B).
            // M23_RI outputs: reg[1]=lo, reg[2]=hi (per Round 3 ABI).
            // M23_PI outputs: reg[3]=lo, reg[4]=hi (per Round 3 ABI).
            state = 1;
m23_B_loop:
            if (clo == (int)0xFFFFFFFF) {
                if (ai) goto m23_B_done;
                M23_RI(reg[1], reg[2], m23_B_done);
                if (p >= DEDUP_TILE) {
                    clo = reg[1]; chi = reg[2]; goto m23_save_full_and_exit;
                }
                clo = reg[1]; chi = reg[2];
            }
            // Merge overlapping intervals via peek
m23_B_peek:
            M23_PI(reg[3], reg[4], m23_B_peek_done);
            if ((uint32_t)reg[3] <= (uint32_t)chi) {
                M23_RI(reg[1], reg[2], m23_B_peek_done);
                if ((uint32_t)reg[4] > (uint32_t)chi) chi = reg[4];
                if (p >= DEDUP_TILE) { goto m23_save_full_and_exit; }
                goto m23_B_peek;
            }
m23_B_peek_done:
            if ((uint32_t)chi > (uint32_t)pv) goto m23_B_done;
            // Flush cur_intv (behind pv). AC-8 mvd site: two
            // contiguous SPM writes from paired (clo, chi) registers
            // — lowerable to a single `mvd` double-word store.
            spm[io_off + n_io*2] = clo;
            spm[io_off + n_io*2+1] = chi;
            n_io++;
            clo = (int)0xFFFFFFFF;
            goto m23_B_loop;
m23_B_done:
            if (clo != (int)0xFFFFFFFF
                && (uint32_t)clo <= (uint32_t)pv
                && (uint32_t)pv  <  (uint32_t)chi)
                goto m23_skip_emit_d;
            spm[do_off + n_do*2] = pv;
            spm[do_off + n_do*2+1] = pk;
            n_do++;
        m23_skip_emit_d:
            if (nv == (int)0xFFFFFFFF) { pv = (int)0xFFFFFFFF; goto m23_C; }
            pv = nv; pk = nk;
            goto m23_X;

            // --- State C: drain remaining intervals ---
m23_C:      state = 2;
m23_C_loop: if (p >= DEDUP_TILE) { goto m23_save_full_and_exit; }
            if (clo == (int)0xFFFFFFFF) {
                M23_RI(reg[1], reg[2], m23_C_done_all);
                if (p >= DEDUP_TILE) {
                    clo = reg[1]; chi = reg[2]; goto m23_save_full_and_exit;
                }
                clo = reg[1]; chi = reg[2];
            }
m23_C_peek:
            M23_PI(reg[3], reg[4], m23_C_flush_last);
            if ((uint32_t)reg[3] <= (uint32_t)chi) {
                M23_RI(reg[1], reg[2], m23_C_flush_last);
                if ((uint32_t)reg[4] > (uint32_t)chi) chi = reg[4];
                if (p >= DEDUP_TILE) { goto m23_save_full_and_exit; }
                goto m23_C_peek;
            }
            // Disjoint: flush cur_intv, start new. AC-8 mvd site:
            // two contiguous SPM writes from paired (clo, chi)
            // registers — lowerable to a single `mvd` double-word
            // store.
            spm[io_off + n_io*2] = clo;
            spm[io_off + n_io*2+1] = chi;
            n_io++;
            M23_RI(reg[1], reg[2], m23_C_done_all);
            clo = reg[1]; chi = reg[2];
            if (p >= DEDUP_TILE) { goto m23_save_full_and_exit; }
            goto m23_C_peek;
m23_C_flush_last:
            if (clo != (int)0xFFFFFFFF) {
                // AC-8 mvd site: contiguous (clo, chi) double-word
                // flush at state-C drain termination.
                spm[io_off + n_io*2] = clo;
                spm[io_off + n_io*2+1] = chi;
                n_io++; clo = (int)0xFFFFFFFF;
            }
m23_C_done_all:
            pdone = 1; goto m23_save_full_and_exit;

            // Single-exit save funnels (Plan 3d Round 1). Every yield
            // path must funnel through one of these two labels so the
            // SAVE semantics are not duplicated inline at each goto
            // site. Prepares for DEC-1 register-residency rewrite.
m23_save_full_and_exit:
            M23_SAVE;
            goto m23_end;
m23_save_light_and_exit:
            M23_SAVE_LIGHT;
m23_end:    ;
#ifdef PLAN3D_TRACE_SNAPSHOT
            {
                static int dumped_exit[4] = {0, 0, 0, 0};
                if ((magic_mask & 1) == 0 && !dumped_exit[id]) {
                    std::ofstream &snap23 = plan3d_snap_pe23();
                    snap23 << "pe23 pe=" << id << " phase=exit";
                    // DEC-1 aware: moved slots come from reg[16..27]
                    // (register-resident); unmoved slots come from SPM
                    // (controller-visible / refill / dead).
                    snap23 << " dm[0]="  << reg[16];
                    snap23 << " dm[1]="  << reg[17];
                    snap23 << " dm[2]="  << spm[DEDUP_META + 2];
                    snap23 << " dm[3]="  << spm[DEDUP_META + 3];
                    snap23 << " dm[4]="  << reg[18];
                    snap23 << " dm[5]="  << reg[19];
                    snap23 << " dm[6]="  << reg[20];
                    snap23 << " dm[7]="  << reg[21];
                    snap23 << " dm[8]="  << spm[DEDUP_META + 8];
                    snap23 << " dm[9]="  << spm[DEDUP_META + 9];
                    snap23 << " dm[10]=" << spm[DEDUP_META + 10];
                    snap23 << " dm[11]=" << spm[DEDUP_META + 11];
                    snap23 << " dm[12]=" << spm[DEDUP_META + 12];
                    snap23 << " dm[13]=" << spm[DEDUP_META + 13];
                    snap23 << " dm[14]=" << reg[22];
                    snap23 << " dm[15]=" << reg[23];
                    snap23 << " dm[16]=" << reg[24];
                    snap23 << " dm[17]=" << reg[25];
                    snap23 << " dm[18]=" << reg[26];
                    snap23 << " dm[19]=" << reg[27];
                    snap23 << std::endl;
                    dumped_exit[id] = 1;
                }
            }
#endif
            #undef M23_SAVE
            #undef M23_SAVE_LIGHT
            #undef M23_SAVE_OUT
            #undef M23_SAVE_RESUME
            #undef M23_RD
            #undef M23_RI
            #undef M23_PI
        } else if (magic_id == 19) {
            // PE FIN0: hash check + character match on FIN_0_TILE.
            // Reads: diags, arc_meta, arcs, HA buckets from FIN0 region.
            // Writes: A_list, B_list, HA_dirty_list + counts to FIN0.
            //
            // Plan 2b Milestone D annotations (AC-9): contiguous SPM
            // double-word sites are tagged inline as `mvd` candidates
            // for the real-ISA lowering. Half-register extract/pack
            // sites are tagged `half-reg`. Non-goals (stay scalar per
            // AC-9 scope containment): the `mvi2_ld` lambda (swizzled
            // 2-bit sequence load) and the 4-word HA bucket probe/mix
            // loop. The 3-word arc record (packed_vw, ow, ts_off) is
            // NOT lowerable to a single mvd — only the first two
            // words form a contiguous pair; `ts_off` stays scalar.
            int fin0_base = (magic_mask & 2)
                ? GWFA_FIN0B_BASE : GWFA_FIN0_BASE;
            int *fspm = &SPM_unit->buffer[
                id * SPM_BANK_GROUP_SIZE + fin0_base];
            int n_diags = fspm[FIN0_META];
            // Plan 3d Round 5: m19 within-call state aliases reg[1..15,
            // 28..31] per AC-2 amendment Section 3.2. C++ references
            // alias register storage; AC-3 compliant — no C++ local
            // carries state across ISA lines. v / d_val / i_val / w
            // are derived inline at use sites from vd / k / packed_vw.
            int& d_idx     = reg[1];
            int& n_A       = reg[2];
            int& n_B       = reg[3];
            int& n_HA      = reg[4];
            int& arc_idx   = reg[5];
            int& vd        = reg[6];
            int& k         = reg[7];
            int& nv        = reg[8];
            int& n_ext     = reg[9];
            int& a_idx     = reg[10];
            int& packed_vw = reg[11];
            int& ow        = reg[12];
            int& ts_off    = reg[13];
            int& hkey      = reg[14];
            int& absent    = reg[15];
            int& scratch_a = reg[28];   // probe / q_char / nd / sd / id2 / del_vd / bo
            int& scratch_b = reg[29];   // h2 / b / gs_char / nvd / svd / ivd
            int& scratch_c = reg[30];   // lo / q_phys / gs_phys / q_bp2 / gs_bp2
            int& scratch_d = reg[31];   // hi / gs_pos / general
            // Initialize within-call state at entry.
            n_A = 0; n_B = 0; n_HA = 0; arc_idx = 0; d_idx = 0;
            constexpr int Q_BASE_CONST  = GWFA_Q_START * 16;
            constexpr int GS_BASE_CONST = GWFA_GS_START * 16;

            // Outer diag loop: lowered to label/goto form (AC-4).
        m19_diag_loop:
            if (d_idx >= n_diags) goto m19_diag_done;
            {
                // mvd: contiguous (vd, k) double-word load from FIN0_DIAGS
                vd = fspm[FIN0_DIAGS + 2*d_idx];
                k  = fspm[FIN0_DIAGS + 2*d_idx + 1];
                //NOP                                          // SPM 2-cycle settle
                //NOP                                          // SPM 2-cycle settle
                // v / d_val / i_val derived inline from vd / k:
                //   v     = (uint32_t)vd >> 16            // half-reg hi
                //   d_val = (int)(vd & 0xFFFF) - GWF_DIAG_SHIFT  // half-reg lo
                //   i_val = d_val + k
                // mvd: contiguous (lo, hi) arcmeta double-word load.
                // lo / hi land in scratch_c / scratch_d transiently;
                // nv = hi - lo is the only persistent value.
                scratch_c = fspm[FIN0_ARCMETA + 2*d_idx];     // lo
                scratch_d = fspm[FIN0_ARCMETA + 2*d_idx + 1]; // hi
                //NOP                                          // SPM 2-cycle settle
                //NOP                                          // SPM 2-cycle settle
                nv = scratch_d - scratch_c;                   // nv = hi - lo
                n_ext = 0;

                // Inner arc loop: label/goto form (AC-4).
                a_idx = 0;
            m19_arc_loop:
                if (a_idx >= nv) goto m19_arc_done;
                {
                    int arc_off = FIN0_ARCS
                        + FIN0_ARC_WORDS * arc_idx;
                    // mvd: contiguous (packed_vw, ow) double-word load
                    // from the arc record. ts_off stays scalar (not
                    // lowerable per AC-9 — 3-word arc record).
                    packed_vw = fspm[arc_off];
                    ow        = fspm[arc_off + 1];
                    ts_off    = fspm[arc_off + 2];
                    //NOP                                          // SPM 2-cycle settle (Round 4 reviewer P0)
                    //NOP                                          // SPM 2-cycle settle (Round 4 reviewer P0)
                    // w derived inline at use sites: w = (uint32_t)packed_vw >> 16  // half-reg hi

                    // Hash check: scan bucket for key.
                    // i_val = ((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k
                    hkey = (((uint32_t)packed_vw >> 16) << 16)    // half-reg hi (w)
                        | ((((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k + 1) & 0xFFFF);
                    int *bkt = &fspm[FIN0_HA + 4*arc_idx];
                    absent = -1;
                    // Bucket 4-slot probe: macro-unrolled (AC-4).
                    // probe value time-multiplexed on scratch_a (reg[28]);
                    // h2 / b time-multiplexed on scratch_b (reg[29]).
                    // i = 0
                    scratch_a = bkt[0];                              // probe0
                    //NOP                                          // SPM settle
                    //NOP                                          // SPM settle
                    if ((uint32_t)scratch_a == (uint32_t)hkey) {
                        absent = 0; goto m19_bkt_done;
                    }
                    if (scratch_a != (int)0xFFFFFFFF) goto m19_bkt_1;
                    bkt[0] = hkey;
                    //NOP                                          // SPM port gap
                    absent = 1;
                    fspm[FIN0_OUT_HA + 2*n_HA] = arc_idx;
                    //NOP                                          // SPM port gap
                    scratch_b = (int)((uint32_t)hkey * 2654435769U >> (32 - 22));     // h2
                    scratch_b = (int)(((uint32_t)scratch_b >> 2) & 0xFFFFF);          // b
                    scratch_b |= (1u << 20);                       // bucket-0 = new-bucket flag
                    fspm[FIN0_OUT_HA + 2*n_HA + 1] = scratch_b;
                    n_HA++;
                    goto m19_bkt_done;
                m19_bkt_1:
                    scratch_a = bkt[1];                              // probe1
                    //NOP                                          // SPM settle
                    //NOP                                          // SPM settle
                    if ((uint32_t)scratch_a == (uint32_t)hkey) {
                        absent = 0; goto m19_bkt_done;
                    }
                    if (scratch_a != (int)0xFFFFFFFF) goto m19_bkt_2;
                    bkt[1] = hkey;
                    //NOP                                          // SPM port gap
                    absent = 1;
                    fspm[FIN0_OUT_HA + 2*n_HA] = arc_idx;
                    //NOP                                          // SPM port gap
                    scratch_b = (int)((uint32_t)hkey * 2654435769U >> (32 - 22));
                    scratch_b = (int)(((uint32_t)scratch_b >> 2) & 0xFFFFF);
                    // i != 0: no new-bucket flag
                    fspm[FIN0_OUT_HA + 2*n_HA + 1] = scratch_b;
                    n_HA++;
                    goto m19_bkt_done;
                m19_bkt_2:
                    scratch_a = bkt[2];                              // probe2
                    //NOP                                          // SPM settle
                    //NOP                                          // SPM settle
                    if ((uint32_t)scratch_a == (uint32_t)hkey) {
                        absent = 0; goto m19_bkt_done;
                    }
                    if (scratch_a != (int)0xFFFFFFFF) goto m19_bkt_3;
                    bkt[2] = hkey;
                    //NOP                                          // SPM port gap
                    absent = 1;
                    fspm[FIN0_OUT_HA + 2*n_HA] = arc_idx;
                    //NOP                                          // SPM port gap
                    scratch_b = (int)((uint32_t)hkey * 2654435769U >> (32 - 22));
                    scratch_b = (int)(((uint32_t)scratch_b >> 2) & 0xFFFFF);
                    fspm[FIN0_OUT_HA + 2*n_HA + 1] = scratch_b;
                    n_HA++;
                    goto m19_bkt_done;
                m19_bkt_3:
                    scratch_a = bkt[3];                              // probe3
                    //NOP                                          // SPM settle
                    //NOP                                          // SPM settle
                    if ((uint32_t)scratch_a == (uint32_t)hkey) {
                        absent = 0; goto m19_bkt_done;
                    }
                    if (scratch_a != (int)0xFFFFFFFF) goto m19_bkt_done;
                    bkt[3] = hkey;
                    //NOP                                          // SPM port gap
                    absent = 1;
                    fspm[FIN0_OUT_HA + 2*n_HA] = arc_idx;
                    //NOP                                          // SPM port gap
                    scratch_b = (int)((uint32_t)hkey * 2654435769U >> (32 - 22));
                    scratch_b = (int)(((uint32_t)scratch_b >> 2) & 0xFFFFF);
                    // i != 0: no new-bucket flag
                    fspm[FIN0_OUT_HA + 2*n_HA + 1] = scratch_b;
                    n_HA++;
                m19_bkt_done: ;
                    if (absent == -1) {
                        // Bucket full — treat as not-absent
                        absent = 0;
                    }

                    // Character match (mvi2_ld inlined). q_bp2 / q_phys
                    // and gs_pos / gs_bp2 / gs_phys are block-local
                    // intermediates; q_char / gs_char use scratch_a /
                    // scratch_b (probe slots are dead at this point in
                    // the arc-loop control flow).
                    //   i_val = ((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k
                    scratch_c = Q_BASE_CONST                          // q_bp2
                        + ((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k + 1;
                    scratch_d = apply_address_swizzle(scratch_c >> 4); // q_phys
                    //NOP                                       // SPM swizzle settle
                    scratch_a = (SPM_unit->buffer[scratch_d]          // q_char
                        >> ((scratch_c & 0xF) << 1)) & 0x3;
                    scratch_c = GS_BASE_CONST + ts_off + ow;          // gs_bp2
                    scratch_d = apply_address_swizzle(scratch_c >> 4); // gs_phys
                    //NOP                                       // SPM swizzle settle
                    scratch_b = (SPM_unit->buffer[scratch_d]          // gs_char
                        >> ((scratch_c & 0xF) << 1)) & 0x3;

                    if (scratch_a == scratch_b) {
                        n_ext++;
                        if (absent) {
                            // Match + absent → output A.
                            //   w   = (uint32_t)packed_vw >> 16  // half-reg hi
                            //   nd  = i_val + 1 - ow
                            //   nvd = (w << 16) | ((GWF_DIAG_SHIFT + nd) & 0xFFFF)
                            scratch_b = ((int)((uint32_t)packed_vw & 0xFFFF0000))
                                | ((GWF_DIAG_SHIFT
                                    + (((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k + 1 - ow))
                                   & 0xFFFF);                                  // nvd
                            // mvd: contiguous (nvd, ow) A-queue write
                            fspm[FIN0_OUT + 2*n_A] = scratch_b;
                            fspm[FIN0_OUT + 2*n_A + 1] = ow;
                            n_A++;
                        }
                    } else if (absent) {
                        // Mismatch + absent → output B (sub + ins).
                        //   sd  = i_val - ow
                        //   svd = (w << 16) | ((GWF_DIAG_SHIFT + sd) & 0xFFFF)
                        scratch_b = ((int)((uint32_t)packed_vw & 0xFFFF0000))
                            | ((GWF_DIAG_SHIFT
                                + (((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k - ow))
                               & 0xFFFF);                                      // svd
                        scratch_a = FIN0_OUT_SIZE-2-2*n_B;                     // bo
                        // mvd: contiguous (svd, ow) B-queue write (sub)
                        fspm[FIN0_OUT + scratch_a] = scratch_b;
                        fspm[FIN0_OUT + scratch_a + 1] = ow;
                        n_B++;
                        //   id2 = i_val + 1 - ow
                        //   ivd = (w << 16) | ((GWF_DIAG_SHIFT + id2) & 0xFFFF)
                        scratch_b = ((int)((uint32_t)packed_vw & 0xFFFF0000))
                            | ((GWF_DIAG_SHIFT
                                + (((int)(vd & 0xFFFF) - GWF_DIAG_SHIFT) + k + 1 - ow))
                               & 0xFFFF);                                      // ivd
                        scratch_a = FIN0_OUT_SIZE-2-2*n_B;                     // bo
                        // mvd: contiguous (ivd, ow) B-queue write (ins)
                        fspm[FIN0_OUT + scratch_a] = scratch_b;
                        fspm[FIN0_OUT + scratch_a + 1] = ow;
                        n_B++;
                    }
                    arc_idx++;
                    a_idx++;
                    goto m19_arc_loop;
                }
            m19_arc_done: ;
                // Deletion: if nv==0 || n_ext!=nv
                if (nv != 0 && n_ext == nv) goto m19_diag_advance;
                //   v       = (uint32_t)vd >> 16  // half-reg hi
                //   del_vd  = (v << 16) | ((GWF_DIAG_SHIFT + d_val + 1) & 0xFFFF)
                //           = ((vd & 0xFFFF0000)) | ((GWF_DIAG_SHIFT + d_val + 1) & 0xFFFF)
                //   d_val + 1 = (int)(vd & 0xFFFF) - GWF_DIAG_SHIFT + 1
                //   GWF_DIAG_SHIFT + d_val + 1 = (int)(vd & 0xFFFF) + 1
                scratch_b = ((int)((uint32_t)vd & 0xFFFF0000))
                    | (((int)(vd & 0xFFFF) + 1) & 0xFFFF);                     // del_vd
                scratch_a = FIN0_OUT_SIZE-2-2*n_B;                              // bo
                // mvd: contiguous (del_vd, k) B-queue write (del)
                fspm[FIN0_OUT + scratch_a] = scratch_b;
                fspm[FIN0_OUT + scratch_a + 1] = k;
                n_B++;
            m19_diag_advance:
                d_idx++;
                goto m19_diag_loop;
            }
        m19_diag_done: ;
            // Write output counts to metadata
            fspm[FIN0_META + 2] = n_A;
            fspm[FIN0_META + 3] = n_B;
            fspm[FIN0_META + 4] = n_HA;
#ifdef PLAN3D_TRACE_SNAPSHOT
            // Frozen observable dump: FIN0_META + first N words of A/B/HA.
            {
                std::ofstream &snap19 = plan3d_snap_pe19();
                snap19 << "pe19 pe=" << id;
                for (int i = 0; i <= 4; i++)
                    snap19 << " META[" << i << "]=" << fspm[FIN0_META + i];
                snap19 << "\n";
                int dA = (n_A < 8) ? n_A : 8;
                snap19 << "pe19 pe=" << id << " A=";
                for (int i = 0; i < dA; i++)
                    snap19 << fspm[FIN0_OUT + 2*i] << ","
                           << fspm[FIN0_OUT + 2*i + 1] << ";";
                snap19 << "\n";
                int dB = (n_B < 8) ? n_B : 8;
                snap19 << "pe19 pe=" << id << " B=";
                for (int i = 0; i < dB; i++)
                    snap19 << fspm[FIN0_OUT + (FIN0_OUT_SIZE - 2 - 2*i)] << ","
                           << fspm[FIN0_OUT + (FIN0_OUT_SIZE - 1 - 2*i)] << ";";
                snap19 << "\n";
                int dH = (n_HA < 8) ? n_HA : 8;
                snap19 << "pe19 pe=" << id << " HA=";
                for (int i = 0; i < dH; i++)
                    snap19 << fspm[FIN0_OUT_HA + 2*i] << ","
                           << fspm[FIN0_OUT_HA + 2*i + 1] << ";";
                snap19 << std::endl;
            }
#endif
        m19_done: ;
        } else if (magic_id == 102) {
            printf("qqq %d qqq\n",
                   addr_regfile_unit->at(15));
        }
        // End of magic dispatch — restore WAW tracking for real ISA writes.
        addr_regfile_unit->waw_suppressed = false;
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
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\t", rd, rs1, rs2, sum, add_a, add_b);
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
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\t", rd, rs1, rs2, sum, add_a, add_b);
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
        printf("addi gr[%d] %d gr[%d] (%d %d %d)\t", rd, imm, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == CTRL_MUL) {       // mul rd rs2 imm/gr[imm]
        // gr[rd] = op_a * gr[rs2] where op_a is sext_imm_1 (immBar=0)
        // or gr[imm_1] (immBar=1). Slot-0 only by programmer contract.
        rd = reg_imm_0;
        rs2 = reg_1;
        add_a = reg_immBar_flag_1 ? read_gr_src(src, reg_imm_1) : sext_imm_1;
        add_b = read_gr_src(src, rs2);
        sum = add_a * add_b;
        set_output_dest(dest, rd, sum);
#ifdef PROFILE
        printf("mul gr[%d] %s%d gr[%d] (%d %d %d)\t", rd,
               reg_immBar_flag_1 ? "gr[" : "", reg_immBar_flag_1 ? reg_imm_1 : sext_imm_1,
               rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == CTRL_SET_8) {   // set_8 reg[rd]/gr[rd] = imm8 broadcast
        // Writes (imm8 & 0xFF) * 0x01010101 into the destination so one op
        // materializes a 4-lane byte constant for the SIMD compute path
        // (e.g. vBias=0x04040404 in magic 101's GSSW kernel).
        rd = reg_imm_0;
        int imm8 = sext_imm_1 & 0xFF;
        int broadcast = (int)((uint32_t)imm8 * 0x01010101u);
        if (dest == CTRL_REG) {
            if (rd < 0 || rd >= REGFILE_ADDR_NUM) {
                fprintf(stderr, "PE[%d] set_8 reg[%d] out of range\n", id, rd);
                exit(-1);
            }
            regfile_unit->set(rd, broadcast, "set_8");
        } else if (dest == CTRL_GR
                || dest == CTRL_GR_LO
                || dest == CTRL_GR_HI) {
            set_output_dest(dest, rd, broadcast);
        } else {
            fprintf(stderr, "PE[%d] set_8 to dest %d not supported\n",
                id, dest);
            exit(-1);
        }
#ifdef PROFILE
        printf("set_8 dest=%d [%d] = 0x%08x\t", dest, rd, broadcast);
#endif
        (*PC)++;
    } else if (opcode == 4) {       // li dest imm/reg(reg(++))
#ifdef PROFILE
    if (simd)
        printf("Store %lx to ", sext_imm_1);
    else
        printf("Store %d to ", sext_imm_1);
#endif
        LoadResult immediate_data{};
        immediate_data.data[0] = sext_imm_1;
        // dest_resolved is the subregister selector (CTRL_GR / CTRL_GR_LO / CTRL_GR_HI)
        // for reg_0 / SPM-offset register; enables gr_lo[r] / gr_hi[r] SPM offsets.
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, immediate_data, simd, ctrl_write_addr, ctrl_write_datum, true, false, dest_resolved);
        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 1);
        (*PC)++;
    } else if (opcode == 5) {       // mv dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("Move ");
#endif
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd, true, false, src_resolved);
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd, ctrl_write_addr, ctrl_write_datum, true, false, dest_resolved);

        bool leagal_mv = check_legal_mv(src, dest);
        if (!leagal_mv) {
            fprintf(stderr, "PE[%d] PC=%d illegal mv from %d to %d\n", id, *PC, src, dest);
            exit(-1);
        }

        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 1);
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->st(reg_1, addr_regfile_unit->at(reg_1) + 1);
        (*PC)++;
    } else if (opcode == 8) {       // bne rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
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
            printf(" jump.\t");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\t");
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
            printf(" jump.\t");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\t");
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
            printf(" jump.\t");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\t");
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
            printf(" jump.\t");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\t");
#endif
        }
    } else if (opcode == 12) {      // jump
        *PC = *PC + sext_imm_0;
#ifdef PROFILE
        printf("jump %d\t", sext_imm_0);
#endif
    } else if (opcode == 13) {      // set PE_PC
        comp_PC = sext_imm_0;
#ifdef PROFILE
        printf("set PC to %d.\t", sext_imm_0);
#endif
        (*PC)++;
    } else if (opcode == 14) {      // None
        (*PC)++;
#ifdef PROFILE
        printf("No-op.\t");
#endif
    } else if (opcode == 15) {      // halt
#ifdef PROFILE
        printf("wait.\t");
#endif
    } else if (opcode == CTRL_SHIFTI_R) {      // SHIFT_R
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = read_gr_src(src, rs2);
        //we want arithmetic shift right as below, but this is compiler dependent. Not in c++ std
        //int shift_result = operand1 >> reg_imm_1;
        //so instead of above, we do the following for portability:
        int shift_result = operand1 / (1<<reg_imm_1);
        set_output_dest(dest, rd, shift_result);
        (*PC)++;
#ifdef PROFILE
        printf("rShift gr[%d] = gr[%d] >> %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SHIFTI_L) {      // SHIFT_L
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = read_gr_src(src, rs2);
        //we want arithmetic shift right as below, but this is compiler dependent. Not in c++ std
        //int shift_result = operand1 >> reg_imm_1;
        //so instead of above, we do the following for portability:
        int shift_result = operand1 <<reg_imm_1;
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
        printf("subi gr[%d] gr[%d] %d (%d %d %d)\t", rd, rs2, imm, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == CTRL_MVD) {      // AND
#ifdef PROFILE
        printf("MoveDouble ");
#endif
        assert(src == CTRL_SPM || dest == CTRL_SPM); //only support to/from spm
        bool single_data = false;
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd, single_data, false, src_resolved);
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd, ctrl_write_addr, ctrl_write_datum, single_data, false, dest_resolved);

        bool leagal_mv = check_legal_mv(src, dest);
        if (!leagal_mv) {
            fprintf(stderr, "PE[%d] PC=%d illegal mv from %d to %d\n", id, *PC, src, dest);
            exit(-1);
        }

        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 2);
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->st(reg_1, addr_regfile_unit->at(reg_1) + 2);
        (*PC)++;
    } else if (opcode == CTRL_MVDQ) {
        fprintf(stderr, "not implemented yet\n");
        exit(-1);
    } else if (opcode == CTRL_MVDQI) {
        fprintf(stderr, "not implemented yet\n");
        exit(-1);
    } else if (opcode == CTRL_MVI) {
#ifdef PROFILE
        printf("Move with Index Swizzle ");
#endif
        // mvi requires source or destination to be SPM
        assert(src == CTRL_SPM || dest == CTRL_SPM);
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd, true, true, src_resolved);
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd, ctrl_write_addr, ctrl_write_datum, true, true, dest_resolved);

        bool legal_mv = check_legal_mv(src, dest);
        if (!legal_mv) {
            fprintf(stderr, "PE[%d] PC=%d illegal mvi from %d to %d\n", id, *PC, src, dest);
            exit(-1);
        }

        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 1);
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->st(reg_1, addr_regfile_unit->at(reg_1) + 1);
        (*PC)++;
    } else if (opcode == CTRL_MVI2) {
#ifdef PROFILE
        printf("Move with 2-bit Extract ");
#endif
        assert(src == CTRL_SPM);
        // Compute bp-level address from operands.
        // src_resolved gives the subregister selector for the reg_1
        // offset register (CTRL_GR / CTRL_GR_LO / CTRL_GR_HI) so
        // mvi2 can use gr_lo[r] / gr_hi[r] as a packed-half offset
        // — required for GSSW stage 3d where col = gr[2].lo and
        // gr[2].hi = seq_len would otherwise fold into the addr.
        int bp_addr;
        if (reg_immBar_flag_1)
            bp_addr =
                addr_regfile_unit->at(sext_imm_1)
                + addr_regfile_unit->at(reg_1, src_resolved);
        else
            bp_addr = sext_imm_1
                + addr_regfile_unit->at(reg_1, src_resolved);
        int bp_offset = bp_addr & 0xF;
        int word_addr = bp_addr >> 4;

        // mvi2 reads the interleaved-swizzled SPM layout populated by the
        // WFA/GWFA magic initializers. Use mv2 for GSSW's unswizzled,
        // per-PE-virtual 2-bit extract.
        int access_addr = apply_address_swizzle(word_addr);
        last_spm_load_addr = access_addr;
        spmReqPort = new OutstandingRequest();
        spmReqPort->addr = access_addr;
        spmReqPort->peid = id;
        spmReqPort->access_t = SpmAccessT::READ;
        spmReqPort->single_data = true;
        spmReqPort->isVirtualAddr = false;

        // Set up outstanding req for destination
        int dest_addr;
        if (reg_immBar_flag_0)
            dest_addr =
                addr_regfile_unit->at(sext_imm_0)
                + addr_regfile_unit->at(reg_0);
        else
            dest_addr = sext_imm_0
                + addr_regfile_unit->at(reg_0);
        assert(outstanding_reqs.size() < (size_t)SPM_ACCESS_LATENCY);
        OutstandingReq req;
        req.valid = true;
        req.single_load = true;
        req.dst = dest;
        req.addr = dest_addr;
        req.spm_addr = access_addr;
        req.bp_shift = bp_offset << 1;
        req.two_bit_extract = true;
        outstanding_reqs.push_back(req);

        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 1);
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->st(reg_1, addr_regfile_unit->at(reg_1) + 1);
        (*PC)++;
    } else if (opcode == CTRL_MV2) {
#ifdef PROFILE
        printf("Move with 2-bit Extract (unswizzled) ");
#endif
        assert(src == CTRL_SPM);
        // Same as mvi2, but reads SPM with virtual per-PE addressing
        // (no swizzle). Used by GSSW where magic 100 loads SPM via plain
        // memcpy.
        int bp_addr;
        if (reg_immBar_flag_1)
            bp_addr =
                addr_regfile_unit->at(sext_imm_1)
                + addr_regfile_unit->at(reg_1, src_resolved);
        else
            bp_addr = sext_imm_1
                + addr_regfile_unit->at(reg_1, src_resolved);
        int bp_offset = bp_addr & 0xF;
        int word_addr = bp_addr >> 4;

        last_spm_load_addr = word_addr;
        spmReqPort = new OutstandingRequest();
        spmReqPort->addr = word_addr;
        spmReqPort->peid = id;
        spmReqPort->access_t = SpmAccessT::READ;
        spmReqPort->single_data = true;
        spmReqPort->isVirtualAddr = true;

        int dest_addr;
        if (reg_immBar_flag_0)
            dest_addr =
                addr_regfile_unit->at(sext_imm_0)
                + addr_regfile_unit->at(reg_0);
        else
            dest_addr = sext_imm_0
                + addr_regfile_unit->at(reg_0);
        assert(outstanding_reqs.size() < (size_t)SPM_ACCESS_LATENCY);
        OutstandingReq req;
        req.valid = true;
        req.single_load = true;
        req.dst = dest;
        req.addr = dest_addr;
        req.spm_addr = word_addr;
        req.bp_shift = bp_offset << 1;
        req.two_bit_extract = true;
        outstanding_reqs.push_back(req);

        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 1);
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->st(reg_1, addr_regfile_unit->at(reg_1) + 1);
        (*PC)++;
    } else if (opcode == CTRL_CALL) {
        ras = *PC + 1;
        *PC = sext_imm_0;
#ifdef PROFILE
        printf("call %d (ras=%d)\t", sext_imm_0, ras);
#endif
    } else if (opcode == CTRL_RET) {
        *PC = ras;
#ifdef PROFILE
        printf("ret (PC=%d)\t", ras);
#endif
    } else if (opcode == CTRL_RETNE) {
        rs1 = sext_imm_1;
        rs2 = reg_1;
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->at(rs1);
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->at(rs2);
        if (comp_0 != comp_1) *PC = ras;
        else (*PC)++;
#ifdef PROFILE
        printf("retne %d %d (PC=%d)\t", comp_0, comp_1, *PC);
#endif
    } else {
        fprintf(stderr, "PE[%d] control instruction opcode error.\n", id);
        exit(-1);
    }
    return 0;
}

void pe::set_output_dest(int dest, int rd, int value) {
    if (dest == CTRL_GR || dest == CTRL_GR_LO
            || dest == CTRL_GR_HI) {
        addr_regfile_unit->st(rd, value, dest);
    } else if (dest == CTRL_OUT_PORT) {
        store_data = value;
    } else {
        fprintf(stderr,
                "Unsupported dest %d for pe arithmetic."
                " PC=%d cycle=%d\n", dest, *PC, cycle);
        exit(-1);
    }
}

// Read an operand selected by a src pos code.
//   CTRL_GR_LO / CTRL_GR_HI -> sign-extended half of gr[idx]
//   CTRL_RESOLVED_REG       -> compute regfile read (only produced by the
//                              decoder's resolve_reg_field for a gr-field
//                              reg idx in [96:127])
//   anything else (incl. CTRL_GR and legacy CTRL_REG=0 don't-care)
//                           -> full-width gr[idx]
int pe::read_gr_src(int src, int idx) {
    if (src == CTRL_GR_LO || src == CTRL_GR_HI)
        return addr_regfile_unit->at(idx, src);
    if (src == CTRL_RESOLVED_REG)
        return regfile_unit->register_file[idx];
    return addr_regfile_unit->at(idx);
}

int pe::get_gr_10() {
    return addr_regfile_unit->at(10);
}

void pe::show_comp_reg() {
    int i;
    for (i = 0; i < REGFILE_ADDR_NUM; i++)
        regfile_unit->show_data(i);
}
