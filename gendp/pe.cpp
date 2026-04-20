#include "pe.h"
#include "FIFO.h"
#include "sys_def.h"
#include <cassert>
#include <algorithm>
#include "simulator.h"
extern "C" {
#include "kernel/Gwfa/gwfa.h"
}
#include <iostream>

bool check_legal_mv(int src, int dest) {
    //TODO come back and add this. Right now some traces (cough cough poa) are illegal
    //can't move between SPM and out or in ports
    //if ((src == CTRL_SPM && (dest == CTRL_IN_PORT || dest == CTRL_OUT_PORT)) ||
    //    (dest == CTRL_SPM && (src == CTRL_IN_PORT || src == CTRL_OUT_PORT))) {
    //    return false;
    //}
    return true;
}

pe::pe(int _id, SPM* spm) {

    SPM_unit = spm;
    id = _id;
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
    outstanding_req.clear();
    spmReqPort = nullptr;
    halted = false;
    // Clear forwarded in_port/out_port values so a reused PE does not
    // leak a previous case's data into the next case's early reads.
    load_data = 0;
    store_data = 0;
}

void pe::recieve_spm_data(int data[LINE_SIZE]){
    if (!outstanding_req.valid){
        fprintf(stderr, "Error: No outstanding request present, but recieve_spm_data called for PE[%d]\n", id);
        exit(-1);
    }
#ifdef PROFILE
    printf("PE[%d] @%d recv SPM: ", id, cycle);
#endif
    switch (outstanding_req.dst){
        case CTRL_REG:
            if (outstanding_req.single_load) {
                {
                int val =
                    data[outstanding_req.spm_addr & 1];
                if (outstanding_req.two_bit_extract)
                    val = (val >> outstanding_req.bp_shift)
                        & 0x3;
                regfile_unit->register_file[
                    outstanding_req.addr] = val;
                }
#ifdef PROFILE
                printf("reg[%d] = %d\n",
                    outstanding_req.addr,
                    data[outstanding_req.spm_addr & 1]);
#endif
            } else {
                for (int i = 0;
                     i < LINE_SIZE; i++)
                    regfile_unit->register_file[
                        outstanding_req.addr + i] =
                        data[i];
#ifdef PROFILE
                printf("reg[%d,%d] = [%d,%d]\n",
                    outstanding_req.addr,
                    outstanding_req.addr+1,
                    data[0], data[1]);
#endif
            }
            break;
        case CTRL_GR:
        case CTRL_GR_LO:
        case CTRL_GR_HI:
            {
            int val =
                data[outstanding_req.spm_addr & 1];
            if (outstanding_req.two_bit_extract) {
                val = (val >> outstanding_req.bp_shift)
                    & 0x3;
            }
            addr_regfile_unit->st(
                outstanding_req.addr, val,
                outstanding_req.dst);
            }
#ifdef PROFILE
            printf("gr[%d] = %d\n",
                outstanding_req.addr,
                data[outstanding_req.spm_addr & 1]);
#endif
            break;
        case CTRL_OUT_PORT:
            {
            int val =
                data[outstanding_req.spm_addr & 1];
            if (outstanding_req.two_bit_extract)
                val = (val >> outstanding_req.bp_shift)
                    & 0x3;
            store_data = val;
            }
#ifdef PROFILE
            printf("out = %d\n",
                data[outstanding_req.spm_addr & 1]);
#endif
            break;
        default:
            fprintf(stderr, "Error: Unsupported dst %d for SPM load in PE[%d]\n", outstanding_req.dst, id);
            exit(-1);
    }
    outstanding_req.clear();
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

    if (simd) {
        regfile_unit->write_data[0] = cu_32.execute_8bit(op[0], cu_inputs[0]);
        regfile_unit->write_data[1] = cu_32.execute_8bit(op[1], cu_inputs[1]);        
    } else {
        regfile_unit->write_data[0] = cu_32.execute(op[0], cu_inputs[0]);
        regfile_unit->write_data[1] = cu_32.execute(op[1], cu_inputs[1]);   
    }


    // Write compute outputs to gr if addressed (addr >= 32)
    for (int s = 0; s < 2; s++) {
        int addr = output_addr[s];
        if (addr >= 64)
            addr_regfile_unit->st(addr - 64, regfile_unit->write_data[s], CTRL_GR_HI);
        else if (addr >= 48)
            addr_regfile_unit->st(addr - 48, regfile_unit->write_data[s], CTRL_GR_LO);
        else if (addr >= 32)
            addr_regfile_unit->st(addr - 32, regfile_unit->write_data[s]);
    }
    regfile_unit->write(regfile_unit->write_addr, regfile_unit->write_data, 0);
    regfile_unit->write(regfile_unit->write_addr, regfile_unit->write_data, 1);
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
    decode(ctrl_instr_buffer_unit->buffer[PC[1]][1], &PC[1], src_dest[1], &ctrl_op[1], simd, &ctrl_write_addrs[0], &ctrl_write_data[0]);
    decode(ctrl_instr_buffer_unit->buffer[PC[0]][0], &PC[0], src_dest[0], &ctrl_op[0], simd, &ctrl_write_addrs[1], &ctrl_write_data[1]);

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

    // One control flow taken: sync other slot
    bool took0 = (PC[0] != old_PC + 1);
    bool took1 = (PC[1] != old_PC + 1);
    if (cf0 && took0 && !cf1) PC[1] = PC[0];
    if (cf1 && took1 && !cf0) PC[0] = PC[1];

    // Track if PE is halted (both slots executing halt instruction)
    halted = (ctrl_op[0] == CTRL_HALT && ctrl_op[1] == CTRL_HALT);

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


LoadResult pe::load(int source_pos, int reg_immBar_flag, int rs1, int rs2, int simd, bool single_data, bool swizzle) {

    LoadResult data{};
    data.data[0] = 0;
    int source_addr = 0;
    
    if (reg_immBar_flag) source_addr = addr_regfile_unit->at(rs1) + addr_regfile_unit->at(rs2);
    else source_addr = rs1 + addr_regfile_unit->at(rs2);

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

void pe::store(int dest_pos, int src_pos, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd, int* ctrl_write_addr, int* ctrl_write_datum, bool single_data, bool swizzle) {

    int dest_addr = 0;

    if (reg_immBar_flag) dest_addr = addr_regfile_unit->at(rs1) + addr_regfile_unit->at(rs2);
    else dest_addr = rs1 + addr_regfile_unit->at(rs2);

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
        assert(!outstanding_req.valid);
        outstanding_req.valid = true;
        outstanding_req.single_load = single_data;
        outstanding_req.dst = dest_pos;
        outstanding_req.addr = dest_addr;
        outstanding_req.spm_addr = last_spm_load_addr;
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
            
            emit_b(); //call
            
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
            
            emit_b();

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
            int tile_buf_off = (magic_mask & 1) ? SORT_TILE_BUF1 : SORT_TILE_BUF0;
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];
            int tile_n = spm[SORT_META + 32];
            int shift  = spm[SORT_META + 33];
            int *tile   = &spm[tile_buf_off];
            int *counts = &spm[SORT_META];
            // Process two elements: load contiguous (vd0,k0,vd1,k1)
            int i = 0;
            for (; i + 1 < tile_n; i += 2) {
                // mvd: 4 contiguous words (vd0, k0, vd1, k1)
                int vd0 = tile[i * 2];
                int k0  = tile[i * 2 + 1];   // loaded but unused
                int vd1 = tile[i * 2 + 2];
                int k1  = tile[i * 2 + 3];   // loaded but unused
                (void)k0; (void)k1;
                int bin0 = ((uint32_t)vd0 >> shift) & 0xF;
                int bin1 = ((uint32_t)vd1 >> shift) & 0xF;
                counts[bin0]++;
                counts[bin1]++;
            }
            // Peel: odd last element
            if (i < tile_n) {
                int vd = tile[i * 2];
                int bin = ((uint32_t)vd >> shift) & 0xF;
                counts[bin]++;
            }
        } else if (magic_id == 21) {
            // Sort scatter: two-element mvd loads for bandwidth.
            int tile_buf_off = (magic_mask & 1) ? SORT_TILE_BUF1 : SORT_TILE_BUF0;
            int bin_spm_off  = (magic_mask & 1) ? SORT_BIN_SPM1  : SORT_BIN_SPM0;
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];
            int tile_n = spm[SORT_META + 32];
            int shift  = spm[SORT_META + 33];
            int *tile            = &spm[tile_buf_off];
            int *tile_bin_counts = &spm[SORT_META + 16];
            int bin_cursors[SORT_RADIX_BINS] = {};
            for (int b = 0; b < SORT_RADIX_BINS; b++) tile_bin_counts[b] = 0;
            // Process two elements per iteration (mvd: 4 words)
            int i = 0;
            for (; i + 1 < tile_n; i += 2) {
                // mvd: load element 0 (vd, k)
                int vd0 = tile[i * 2];
                int k0  = tile[i * 2 + 1];
                // mvd: load element 1 (vd, k)
                int vd1 = tile[(i+1) * 2];
                int k1  = tile[(i+1) * 2 + 1];
                // Scatter element 0
                int bin0 = ((uint32_t)vd0 >> shift) & 0xF;
                int off0 = bin0 * SORT_BIN_REGION_SIZE * 2 + bin_cursors[bin0] * 2;
                spm[bin_spm_off + off0]     = vd0;
                spm[bin_spm_off + off0 + 1] = k0;
                bin_cursors[bin0]++;
                tile_bin_counts[bin0]++;
                // Scatter element 1
                int bin1 = ((uint32_t)vd1 >> shift) & 0xF;
                int off1 = bin1 * SORT_BIN_REGION_SIZE * 2 + bin_cursors[bin1] * 2;
                spm[bin_spm_off + off1]     = vd1;
                spm[bin_spm_off + off1 + 1] = k1;
                bin_cursors[bin1]++;
                tile_bin_counts[bin1]++;
            }
            // Peel: handle odd last element
            if (i < tile_n) {
                int vd = tile[i * 2];
                int k  = tile[i * 2 + 1];
                int bin = ((uint32_t)vd >> shift) & 0xF;
                int off = bin * SORT_BIN_REGION_SIZE * 2 + bin_cursors[bin] * 2;
                spm[bin_spm_off + off]     = vd;
                spm[bin_spm_off + off + 1] = k;
                bin_cursors[bin]++;
                tile_bin_counts[bin]++;
            }
        } else if (magic_id == 22) {
            // Merge: input-capped two-pointer merge with ping-pong tiles.
            // Buffer switch is a one-time transition; merge core is tight.
            // Unified path handles single-stream drain (BL-drain-budget).
            int out_off = (magic_mask & 1) ? MERGE_OUT1 : MERGE_OUT0;
            int *spm = &SPM_unit->buffer[id * SPM_BANK_GROUP_SIZE];
            int ai  = spm[MERGE_META + 0];
            int bi  = spm[MERGE_META + 1];
            int aw  = spm[MERGE_META + 7];
            int bw  = spm[MERGE_META + 8];
            int a_n = spm[MERGE_META + 9 + aw];
            int b_n = spm[MERGE_META + 11 + bw];
            int ab  = aw ? MERGE_A_BUF1 : MERGE_A_BUF0;
            int bb  = bw ? MERGE_B_BUF1 : MERGE_B_BUF0;
            int *out = &spm[out_off];
            int oi = 0;
            int ai0 = ai, bi0 = bi;
            uint32_t bvd[3] = {(uint32_t)spm[MERGE_META+13],
                               (uint32_t)spm[MERGE_META+14],
                               (uint32_t)spm[MERGE_META+15]};
            int cum_oi = spm[982];
            int pe_global_base = spm[983];
            // --- Main loop: budget-capped merge ---
        m22_top:
            if ((ai - ai0) + (bi - bi0) >= MERGE_STEP)
                goto m22_done;
            // Buffer transition (special case, outside merge core)
            if (ai >= a_n) {
                int o = aw ^ 1;
                int on = spm[MERGE_META + 9 + o];
                if (on > 0) {
                    spm[MERGE_META + 9 + aw] = 0;
                    aw = o; ab = aw ? MERGE_A_BUF1 : MERGE_A_BUF0;
                    ai = 0; ai0 -= a_n; a_n = on;
                }
            }
            if (bi >= b_n) {
                int o = bw ^ 1;
                int on = spm[MERGE_META + 11 + o];
                if (on > 0) {
                    spm[MERGE_META + 11 + bw] = 0;
                    bw = o; bb = bw ? MERGE_B_BUF1 : MERGE_B_BUF0;
                    bi = 0; bi0 -= b_n; b_n = on;
                }
            }
            if (ai >= a_n && bi >= b_n) goto m22_done;
            // Merge core: compare and copy one element
            if (ai >= a_n || (bi < b_n
                    && (uint32_t)spm[bb+bi*2]
                       < (uint32_t)spm[ab+ai*2])) {
                out[oi*2]   = spm[bb+bi*2];
                out[oi*2+1] = spm[bb+bi*2+1]; bi++; oi++;
            } else {
                out[oi*2]   = spm[ab+ai*2];
                out[oi*2+1] = spm[ab+ai*2+1]; ai++; oi++;
            }
            // Boundary tracking
            { int gpos = pe_global_base + cum_oi + oi - 1;
              uint32_t out_lo = (uint32_t)out[(oi-1)*2];
              uint32_t out_hi = (uint32_t)out[(oi-1)*2+1];
              for (int b = 0; b < 3; b++) {
                  if (spm[976+b] < 0 && out_hi > bvd[b])
                      spm[976+b] = gpos;
                  if (spm[979+b] < 0 && out_lo >= bvd[b])
                      spm[979+b] = gpos;
              }
            }
            goto m22_top;
        m22_done:
            spm[MERGE_META+0]=ai; spm[MERGE_META+1]=bi;
            spm[MERGE_META+4]=oi;
            spm[MERGE_META+7]=aw; spm[MERGE_META+8]=bw;
            spm[982] = cum_oi + oi;
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
            // Restore state from META
            uint32_t pv = (uint32_t)spm[DEDUP_META + 0];
            int pk       = spm[DEDUP_META + 1];
            int n_do = 0, n_io = 0;
            int dc   = spm[DEDUP_META + 4];
            int ic   = spm[DEDUP_META + 5];
            int dw   = spm[DEDUP_META + 6];
            int iw   = spm[DEDUP_META + 7];
            int de = 0, ie = 0;
            int dtn  = spm[DEDUP_META + 10 + dw];
            int don_ = spm[DEDUP_META + 10 + (dw^1)];
            int itn  = spm[DEDUP_META + 12 + iw];
            int ion  = spm[DEDUP_META + 12 + (iw^1)];
            uint32_t clo = (uint32_t)spm[DEDUP_META + 14];
            uint32_t chi = (uint32_t)spm[DEDUP_META + 15];
            int state    = spm[DEDUP_META + 16];
            int pdone    = spm[DEDUP_META + 17];
            uint32_t nv  = (uint32_t)spm[DEDUP_META + 18];
            int nk       = spm[DEDUP_META + 19];
            int db = dw ? DEDUP_DIAG_BUF1 : DEDUP_DIAG_BUF0;
            int ib = iw ? DEDUP_INTV_BUF1  : DEDUP_INTV_BUF0;
            int p = 0;  // processed counter
            bool ad = false, ai = false;  // all_diag/intv done

            // --- Inline helpers (no lambdas for ISA lowering) ---
            // Read next diag: inline buffer-switch + read
            #define M23_RD(vd_out, k_out, fail_label) do { \
                if (dc >= dtn) { \
                    spm[DEDUP_META + 10 + dw] = 0; \
                    dw ^= 1; \
                    db = dw ? DEDUP_DIAG_BUF1 : DEDUP_DIAG_BUF0; \
                    de = 1; dtn = don_; don_ = 0; dc = 0; \
                    if (dtn == 0) { ad = true; goto fail_label; } \
                } \
                vd_out = (uint32_t)spm[db+dc*2]; \
                k_out  = spm[db+dc*2+1]; \
                dc++; p++; \
            } while(0)
            // Read next intv: inline buffer-switch + read
            #define M23_RI(lo_out, hi_out, fail_label) do { \
                if (ic >= itn) { \
                    spm[DEDUP_META + 12 + iw] = 0; \
                    iw ^= 1; \
                    ib = iw ? DEDUP_INTV_BUF1 : DEDUP_INTV_BUF0; \
                    ie = 1; itn = ion; ion = 0; ic = 0; \
                    if (itn == 0) { ai = true; goto fail_label; } \
                } \
                lo_out = (uint32_t)spm[ib+ic*2]; \
                hi_out = (uint32_t)spm[ib+ic*2+1]; \
                ic++; p++; \
            } while(0)
            // Peek next intv without consuming
            #define M23_PI(lo_out, hi_out, fail_label) do { \
                int tc_=ic, tw_=iw, tt_=itn, tb_=ib; \
                if (tc_ >= tt_) { \
                    tw_ ^= 1; \
                    tb_ = tw_ ? DEDUP_INTV_BUF1 : DEDUP_INTV_BUF0; \
                    tt_ = ion; tc_ = 0; \
                    if (tt_ == 0) goto fail_label; \
                } \
                lo_out = (uint32_t)spm[tb_+tc_*2]; \
                hi_out = (uint32_t)spm[tb_+tc_*2+1]; \
            } while(0)
            // Controller-visible output (read by magic 30/31 between calls)
            #define M23_SAVE_OUT do { \
                spm[DEDUP_META+2]=n_do; spm[DEDUP_META+3]=n_io; \
                spm[DEDUP_META+8]=de; spm[DEDUP_META+9]=ie; \
            } while(0)
            // PE-internal resume state (will become registers in ISA)
            #define M23_SAVE_RESUME do { \
                spm[DEDUP_META+0]=(int)pv; spm[DEDUP_META+1]=pk; \
                spm[DEDUP_META+4]=dc; spm[DEDUP_META+5]=ic; \
                spm[DEDUP_META+6]=dw; spm[DEDUP_META+7]=iw; \
                spm[DEDUP_META+14]=(int)clo; \
                spm[DEDUP_META+15]=(int)chi; \
                spm[DEDUP_META+16]=state; \
                spm[DEDUP_META+17]=pdone; \
                spm[DEDUP_META+18]=(int)nv; \
                spm[DEDUP_META+19]=nk; \
            } while(0)
            #define M23_SAVE do { M23_SAVE_OUT; M23_SAVE_RESUME; } while(0)

            if (pdone) { M23_SAVE; goto m23_end; }
            if (state == 1) goto m23_B;
            if (state == 2) goto m23_C;

            // --- State X: merge same-vd diags ---
m23_X:      if (p >= DEDUP_TILE) { state = 0; M23_SAVE; goto m23_end; }
            { uint32_t vd; int k;
              M23_RD(vd, k, m23_X_diags_done);
              if (pv == 0xFFFFFFFFU) { pv = vd; pk = k; goto m23_X; }
              if (vd == pv) { if (k > pk) pk = k; goto m23_X; }
              nv = vd; nk = k;
              goto m23_B;
m23_X_diags_done:
              if (pv != 0xFFFFFFFFU) { nv = 0xFFFFFFFFU; goto m23_B; }
              goto m23_C;
            }

m23_B:      // Advance intv past pv (State B)
            state = 1;
m23_B_loop:
            if (clo == 0xFFFFFFFFU) {
                if (ai) goto m23_B_done;
                { uint32_t lo, hi;
                  M23_RI(lo, hi, m23_B_done);
                  if (p >= DEDUP_TILE) {
                      clo = lo; chi = hi; M23_SAVE; goto m23_end;
                  }
                  clo = lo; chi = hi;
                }
            }
            // Merge overlapping intervals via peek
m23_B_peek:
            { uint32_t l2, h2;
              M23_PI(l2, h2, m23_B_peek_done);
              if (l2 <= chi) {
                  uint32_t d1, d2;
                  M23_RI(d1, d2, m23_B_peek_done);
                  if (h2 > chi) chi = h2;
                  if (p >= DEDUP_TILE) { M23_SAVE; goto m23_end; }
                  goto m23_B_peek;
              }
            }
m23_B_peek_done:
            if (chi > pv) goto m23_B_done;
            // Flush cur_intv (behind pv)
            spm[io_off + n_io*2] = (int)clo;
            spm[io_off + n_io*2+1] = (int)chi;
            n_io++;
            clo = 0xFFFFFFFFU;
            goto m23_B_loop;
m23_B_done:
            // Forbidden check: skip diag if inside current intv
            { bool forb = (clo != 0xFFFFFFFFU
                && clo <= pv && pv < chi);
              if (!forb) {
                  spm[do_off + n_do*2] = (int)pv;
                  spm[do_off + n_do*2+1] = pk;
                  n_do++;
              }
            }
            if (nv == 0xFFFFFFFFU) { pv = 0xFFFFFFFFU; goto m23_C; }
            pv = nv; pk = nk;
            goto m23_X;

            // --- State C: drain remaining intervals ---
m23_C:      state = 2;
m23_C_loop: if (p >= DEDUP_TILE) { M23_SAVE; goto m23_end; }
            if (clo == 0xFFFFFFFFU) {
                { uint32_t lo, hi;
                  M23_RI(lo, hi, m23_C_done_all);
                  if (p >= DEDUP_TILE) {
                      clo = lo; chi = hi; M23_SAVE; goto m23_end;
                  }
                  clo = lo; chi = hi;
                }
            }
m23_C_peek:
            { uint32_t lo, hi;
              M23_PI(lo, hi, m23_C_flush_last);
              if (lo <= chi) {
                  uint32_t d1, d2;
                  M23_RI(d1, d2, m23_C_flush_last);
                  if (hi > chi) chi = hi;
                  if (p >= DEDUP_TILE) { M23_SAVE; goto m23_end; }
                  goto m23_C_peek;
              }
              // Disjoint: flush cur_intv, start new
              spm[io_off + n_io*2] = (int)clo;
              spm[io_off + n_io*2+1] = (int)chi;
              n_io++;
              { uint32_t d1, d2;
                M23_RI(d1, d2, m23_C_done_all);
                clo = d1; chi = d2;
                if (p >= DEDUP_TILE) { M23_SAVE; goto m23_end; }
              }
              goto m23_C_peek;
            }
m23_C_flush_last:
            if (clo != 0xFFFFFFFFU) {
                spm[io_off + n_io*2] = (int)clo;
                spm[io_off + n_io*2+1] = (int)chi;
                n_io++; clo = 0xFFFFFFFFU;
            }
m23_C_done_all:
            pdone = 1; M23_SAVE; goto m23_end;

            M23_SAVE;
m23_end:    ;
            #undef M23_SAVE
            #undef M23_SAVE_OUT
            #undef M23_SAVE_RESUME
            #undef M23_RD
            #undef M23_RI
            #undef M23_PI
        } else if (magic_id == 19) {
            // PE FIN0: hash check + character match on FIN_0_TILE.
            // Reads: diags, arc_meta, arcs, HA buckets from FIN0 region.
            // Writes: A_list, B_list, HA_dirty_list + counts to FIN0.
            int fin0_base = (magic_mask & 2)
                ? GWFA_FIN0B_BASE : GWFA_FIN0_BASE;
            int *fspm = &SPM_unit->buffer[
                id * SPM_BANK_GROUP_SIZE + fin0_base];
            int n_diags = fspm[FIN0_META];
            int n_A = 0, n_B = 0, n_HA = 0;
            int arc_idx = 0;
            // GET_2BIT from interleaved SPM (Q and GS sequences)
            auto mvi2_ld = [&](int base_char_addr, int char_off) -> int {
                int bp2 = base_char_addr + char_off;
                int phys = apply_address_swizzle(bp2 >> 4);
                return (SPM_unit->buffer[phys]
                    >> ((bp2 & 0xF) << 1)) & 0x3;
            };
            int gs_base = GWFA_GS_START * 16;
            int q_base = GWFA_Q_START * 16;

            for (int d = 0; d < n_diags; d++) {
                uint32_t vd = (uint32_t)fspm[FIN0_DIAGS + 2*d];
                int32_t k = fspm[FIN0_DIAGS + 2*d + 1];
                uint32_t v = vd >> 16;
                int32_t d_val = (int32_t)(vd & 0xFFFF)
                    - GWF_DIAG_SHIFT;
                int32_t i_val = d_val + k;
                int lo = fspm[FIN0_ARCMETA + 2*d];
                int hi = fspm[FIN0_ARCMETA + 2*d + 1];
                int nv = hi - lo;
                int32_t n_ext = 0;

                for (int a = 0; a < nv; a++) {
                    int arc_off = FIN0_ARCS
                        + FIN0_ARC_WORDS * arc_idx;
                    int packed_vw = fspm[arc_off];
                    int ow = fspm[arc_off + 1];
                    int ts_off = fspm[arc_off + 2];
                    uint32_t w = (uint32_t)packed_vw >> 16;

                    // Hash check: scan bucket for key
                    uint32_t hkey = (w << 16)
                        | ((i_val + 1) & 0xFFFF);
                    int *bkt = &fspm[FIN0_HA + 4*arc_idx];
                    int absent = -1;
                    for (int i = 0; i < 4; i++) {
                        if ((uint32_t)bkt[i] == hkey) {
                            absent = 0; break;
                        }
                        if (bkt[i] == (int)0xFFFFFFFF) {
                            bkt[i] = (int)hkey;
                            absent = 1;
                            // Always record modified bucket for writeback
                            fspm[FIN0_OUT_HA + 2*n_HA] = arc_idx;
                            uint32_t h2 = hkey * 2654435769U
                                >> (32 - 22);
                            uint32_t b = (h2 >> 2) & 0xFFFFF;
                            // Bit 20 = new-bucket flag (first key in bucket)
                            if (i == 0) b |= (1u << 20);
                            fspm[FIN0_OUT_HA + 2*n_HA + 1] = (int)b;
                            n_HA++;
                            break;
                        }
                    }
                    if (absent == -1) {
                        // Bucket full — treat as not-absent
                        absent = 0;
                    }

                    // Character match using precomputed ts_off
                    int q_char = mvi2_ld(q_base, i_val + 1);
                    int gs_pos = ts_off + ow;
                    int gs_char = mvi2_ld(gs_base, gs_pos);

                    if (q_char == gs_char) {
                        n_ext++;
                        if (absent) {
                            // Match + absent → output A
                            int32_t nd = i_val + 1 - ow;
                            uint32_t nvd = (w << 16)
                                | ((GWF_DIAG_SHIFT + nd) & 0xFFFF);
                            fspm[FIN0_OUT + 2*n_A] = (int)nvd;
                            fspm[FIN0_OUT + 2*n_A + 1] = ow;
                            n_A++;
                        }
                    } else if (absent) {
                        // Mismatch + absent → output B (sub + ins)
                        int32_t sd = i_val - ow;
                        uint32_t svd = (w << 16)
                            | ((GWF_DIAG_SHIFT + sd) & 0xFFFF);
                        int bo = FIN0_OUT_SIZE-2-2*n_B;
                        fspm[FIN0_OUT + bo] = (int)svd;
                        fspm[FIN0_OUT + bo + 1] = ow;
                        n_B++;
                        int32_t id2 = i_val + 1 - ow;
                        uint32_t ivd = (w << 16)
                            | ((GWF_DIAG_SHIFT + id2) & 0xFFFF);
                        bo = FIN0_OUT_SIZE-2-2*n_B;
                        fspm[FIN0_OUT + bo] = (int)ivd;
                        fspm[FIN0_OUT + bo + 1] = ow;
                        n_B++;
                    }
                    arc_idx++;
                }
                // Deletion: if nv==0 || n_ext!=nv
                if (nv == 0 || n_ext != nv) {
                    uint32_t del_vd = (v << 16)
                        | ((GWF_DIAG_SHIFT + d_val + 1) & 0xFFFF);
                    int bo = FIN0_OUT_SIZE-2-2*n_B;
                    fspm[FIN0_OUT + bo] = (int)del_vd;
                    fspm[FIN0_OUT + bo + 1] = k;
                    n_B++;
                }
            }
            // Write output counts to metadata
            fspm[FIN0_META + 2] = n_A;
            fspm[FIN0_META + 3] = n_B;
            fspm[FIN0_META + 4] = n_HA;
        m19_done: ;
        }
        (*PC)++;
    } else if (opcode == 0) {              // add rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = addr_regfile_unit->at(rs1);
        add_b = addr_regfile_unit->at(rs2);
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
        add_a = addr_regfile_unit->at(rs1);
        add_b = addr_regfile_unit->at(rs2);
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
        add_b = addr_regfile_unit->at(rs2);
        sum = add_a + add_b;
        set_output_dest(dest, rd, sum);
#ifdef PROFILE
        printf("addi gr[%d] %d gr[%d] (%d %d %d)\t", rd, imm, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
//     } else if (opcode == 3) {       // set_8 rd rs2
//         rd = reg_imm_0;
//         rs2 = reg_1;
//         memcpy(rs, &main_addressing_register[rs2], 4*sizeof(int8_t));

//         for (i = 0; i < 4; i++) {
//             rs[i] = main_addressing_register[rs2] & 0xFF;
//         }
//         memcpy(&main_addressing_register[rd], rs, 4*sizeof(int8_t));
// #ifdef PROFILE
//         printf("set_8 gr[%d] gr[%d] (%d %lx)\n", rd, rs2, main_addressing_register[rs2], main_addressing_register[rd]);
// #endif
//         (*PC)++;
    } else if (opcode == 4) {       // li dest imm/reg(reg(++))
#ifdef PROFILE
    if (simd)
        printf("Store %lx to ", sext_imm_1);
    else
        printf("Store %d to ", sext_imm_1);
#endif
        LoadResult immediate_data{};
        immediate_data.data[0] = sext_imm_1;
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, immediate_data, simd, ctrl_write_addr, ctrl_write_datum);
        if (reg_auto_increasement_flag_0)
            addr_regfile_unit->st(reg_0, addr_regfile_unit->at(reg_0) + 1);
        (*PC)++;
    } else if (opcode == 5) {       // mv dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("Move ");
#endif
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd);
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd, ctrl_write_addr, ctrl_write_datum);

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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->at(rs1);
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->at(rs2);
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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->at(rs1);
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->at(rs2);
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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->at(rs1);
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->at(rs2);
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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->at(rs1);
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->at(rs2);
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
        assert(dest == CTRL_GR);  // only support gr
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = addr_regfile_unit->at(rs2);
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
        assert(dest == CTRL_GR);  // only support gr
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = addr_regfile_unit->at(rs2);
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
        int operand1 = addr_regfile_unit->at(rs2);
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
        add_a = addr_regfile_unit->at(rs2);
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
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd, single_data);
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd, ctrl_write_addr, ctrl_write_datum, single_data);

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
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd, true, true);
        store(dest, src, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd, ctrl_write_addr, ctrl_write_datum, true, true);

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
        // Compute bp-level address from operands
        int bp_addr;
        if (reg_immBar_flag_1)
            bp_addr =
                addr_regfile_unit->at(sext_imm_1)
                + addr_regfile_unit->at(reg_1);
        else
            bp_addr = sext_imm_1
                + addr_regfile_unit->at(reg_1);
        int bp_offset = bp_addr & 0xF;
        int word_addr = bp_addr >> 4;

        // Swizzle and issue SPM read
        int access_addr =
            apply_address_swizzle(word_addr);
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
        assert(!outstanding_req.valid);
        outstanding_req.valid = true;
        outstanding_req.single_load = true;
        outstanding_req.dst = dest;
        outstanding_req.addr = dest_addr;
        outstanding_req.spm_addr = access_addr;
        outstanding_req.bp_shift = bp_offset << 1;
        outstanding_req.two_bit_extract = true;

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

int pe::get_gr_10() {
    return addr_regfile_unit->at(10);
}

void pe::show_comp_reg() {
    int i;
    for (i = 0; i < REGFILE_ADDR_NUM; i++)
        regfile_unit->show_data(i);
}
