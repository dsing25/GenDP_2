#include "pe.h"
#include "sys_def.h"
#include <cassert>
#include "simulator.h"
#include <iostream>

// Apply address swizzling for mvi instruction
// Moves lower N_SWIZZLE_BITS to high positions of address
inline int apply_address_swizzle(int addr) {
    if (addr < 0 || addr > SPM_ADDR_NUM) {
        fprintf(stderr, "Error: address %d out of bound for swizzling\n", addr);
        exit(-1);
    }
    int addr_masked = addr & ((1u << ADDR_LEN) - 1);
    int lower_bits = addr_masked & ((1u << N_SWIZZLE_BITS) - 1);
    int upper_bits = addr_masked >> N_SWIZZLE_BITS;
    int new_addr = upper_bits | (lower_bits << (ADDR_LEN - N_SWIZZLE_BITS));
    return new_addr;
}

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
    store_instruction[0] = 0; store_instruction[1] = 0;
    load_instruction[0] = 0; load_instruction[1] = 0;
    instruction[0] = 0; instruction[1] = 0;
    comp_PC = COMP_INSTR_BUFFER_GROUP_NUM - 1;
    PC[0] = 0;
    PC[1] = 0;
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
    store_instruction[0] = 0; store_instruction[1] = 0;
    load_instruction[0] = 0; load_instruction[1] = 0;
    instruction[0] = 0; instruction[1] = 0;
    comp_PC = COMP_INSTR_BUFFER_GROUP_NUM - 1;
    PC[0] = 0;
    PC[1] = 0;
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
                regfile_unit->register_file[
                    outstanding_req.addr] =
                        data[outstanding_req.spm_addr & 1];
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
            addr_regfile_unit->buffer[
                outstanding_req.addr] =
                    data[outstanding_req.spm_addr & 1];
#ifdef PROFILE
            printf("gr[%d] = %d\n",
                outstanding_req.addr,
                data[outstanding_req.spm_addr & 1]);
#endif
            break;
        case CTRL_OUT_PORT:
            store_data =
                data[outstanding_req.spm_addr & 1];
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
    for (i = 0; i < 6; i++) {
        regfile_unit->read_addr[i] =  input_addr[0][i];
        regfile_unit->read_addr[i+6] = input_addr[1][i];
    }
    regfile_unit->read(regfile_unit->read_addr, regfile_unit->read_data);
    regfile_unit->write_addr[0] = output_addr[0];
    regfile_unit->write_addr[1] = output_addr[1];

    int cu_inputs[2][6];
    for (i = 0; i < 6; i++){
        cu_inputs[0][i] = regfile_unit->read_data[i];
        cu_inputs[1][i] = regfile_unit->read_data[6+i];
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
    decode(ctrl_instr_buffer_unit->buffer[PC[1]][1], &PC[1], src_dest[1], &ctrl_op[1], simd, &ctrl_write_addrs[0], &ctrl_write_data[0]);
    decode(ctrl_instr_buffer_unit->buffer[PC[0]][0], &PC[0], src_dest[0], &ctrl_op[0], simd, &ctrl_write_addrs[1], &ctrl_write_data[1]);

    // Track if PE is halted (both slots executing halt instruction, opcode 15)
    halted = (ctrl_op[0] == 15 && ctrl_op[1] == 15);

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
    
    if (reg_immBar_flag) source_addr = addr_regfile_unit->buffer[rs1] + addr_regfile_unit->buffer[rs2];
    else source_addr = rs1 + addr_regfile_unit->buffer[rs2];
    

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
    } else if (source_pos == CTRL_GR) {
        int n_loads = single_data ? 1 : LINE_SIZE;
        for (int i = 0; i < n_loads; i++) {
            int addr = source_addr + i;
            if (addr >= 0 && addr < ADDR_REGISTER_NUM) {
                data.data[i] = addr_regfile_unit->buffer[addr];
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
    } else if (source_pos == CTRL_IN_INSTR) {
        instruction[0] = load_instruction[0];
        instruction[1] = load_instruction[1];
#ifdef PROFILE
        printf("%lx %lx from input comp instruction port to ", instruction[0], instruction[1]);
#endif
    } else {
        fprintf(stderr, "source_pos error. source_pos=%d\n",source_pos);
        exit(-1);
    }
    return data;
}

void pe::store(int dest_pos, int src_pos, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd, int* ctrl_write_addr, int* ctrl_write_datum, bool single_data, bool swizzle) {

    int dest_addr = 0;

    if (reg_immBar_flag) dest_addr = addr_regfile_unit->buffer[rs1] + addr_regfile_unit->buffer[rs2];
    else dest_addr = rs1 + addr_regfile_unit->buffer[rs2];

#ifdef DEBUG
    printf("dest: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d src_addr: %d\n", dest_pos, reg_immBar_flag, rs1, rs2, dest_addr);
#endif
    if (src_pos == CTRL_SPM) {
        //in this case we need to wait a cycle, so we put it into outstanding
        if (dest_pos != CTRL_REG && dest_pos != CTRL_GR
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
        } else if (dest_pos == CTRL_GR) {
            if (dest_addr >= 0 && dest_addr < ADDR_REGISTER_NUM) {
                *ctrl_write_datum = data.data[0];
                *ctrl_write_addr = dest_addr;

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
        } else if (dest_pos == 10) {
            store_instruction[0] = instruction[0];
            store_instruction[1] = instruction[1];
#ifdef PROFILE
            printf("output comp instruction port.\t");
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
        //Used to wreak simulator havoc. Put whatever you want here
        printf("Magic!!!!! payload = %d\n", magic_payload);
        (*PC)++;
    } else if (opcode == 0) {              // add rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = addr_regfile_unit->buffer[rs1];
        add_b = addr_regfile_unit->buffer[rs2];
        sum = add_a + add_b;
        *get_output_dest(dest, rd) = sum;
#ifdef PROFILE
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\t", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 1) {       // sub rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = addr_regfile_unit->buffer[rs1];
        add_b = addr_regfile_unit->buffer[rs2];
        sum = add_a - add_b;
        *get_output_dest(dest, rd) = sum;
#ifdef PROFILE
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\t", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 2) {       // addi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = imm;
        add_b = addr_regfile_unit->buffer[rs2];
        sum = add_a + add_b;
        *get_output_dest(dest, rd) = sum;
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
            addr_regfile_unit->buffer[reg_0]++;
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
            addr_regfile_unit->buffer[reg_0]++;
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->buffer[reg_1]++;
        (*PC)++;
    } else if (opcode == 8) {       // bne rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("bne %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->buffer[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->buffer[rs2];
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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->buffer[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->buffer[rs2];
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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->buffer[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->buffer[rs2];
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
        if (reg_immBar_flag_1) comp_0 = addr_regfile_unit->buffer[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = addr_regfile_unit->buffer[rs2];
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
        int operand1 = addr_regfile_unit->buffer[rs2];
        //we want arithmetic shift right as below, but this is compiler dependent. Not in c++ std
        //int shift_result = operand1 >> reg_imm_1;
        //so instead of above, we do the following for portability:
        int shift_result = operand1 / (1<<reg_imm_1);
        *get_output_dest(dest,rd) = shift_result;
        (*PC)++;
#ifdef PROFILE
        printf("rShift gr[%d] = gr[%d] >> %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SHIFTI_L) {      // SHIFT_L
        assert(dest == CTRL_GR);  // only support gr
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = addr_regfile_unit->buffer[rs2];
        //we want arithmetic shift right as below, but this is compiler dependent. Not in c++ std
        //int shift_result = operand1 >> reg_imm_1;
        //so instead of above, we do the following for portability:
        int shift_result = operand1 <<reg_imm_1;
        *get_output_dest(dest,rd) = shift_result;
        (*PC)++;
#ifdef PROFILE
        printf("lShift gr[%d] = gr[%d] << %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_ANDI) {      // AND
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = addr_regfile_unit->buffer[rs2];
        int and_result = operand1 & reg_imm_1;
        *get_output_dest(dest,rd) = and_result;
        (*PC)++;
#ifdef PROFILE
        printf("andi gr[%d] = gr[%d] & %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SUBI) {       // subi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = addr_regfile_unit->buffer[rs2];
        add_b = imm;
        sum = add_a - add_b;
        *get_output_dest(dest, rd) = sum;
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
            addr_regfile_unit->buffer[reg_0]++;
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->buffer[reg_1]++;
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
            addr_regfile_unit->buffer[reg_0]++;
        if (reg_auto_increasement_flag_1)
            addr_regfile_unit->buffer[reg_1]++;
        (*PC)++;
    } else {
        fprintf(stderr, "PE[%d] control instruction opcode error.\n", id);
        exit(-1);
    }
    return 0;
}

int* pe::get_output_dest(int dest, int rd){
    // write out only supported for GR or out buffer
    if (dest == CTRL_GR){
        return &(addr_regfile_unit->buffer[rd]);
    } else if (dest == CTRL_OUT_PORT){
        return &store_data;
    } else {
        fprintf(stderr, 
                "Only dest CTRL_GR and CTRL_OUT_BUF are supported for pe, non MV CTRL instr. dest = %d; PC = %d; cycle = %d\n", dest, *PC, cycle);
        exit(-1);
    }
}

int pe::get_gr_10() {
    return addr_regfile_unit->buffer[10];
}

void pe::show_comp_reg() {
    int i;
    for (i = 0; i < REGFILE_ADDR_NUM; i++)
        regfile_unit->show_data(i);
}
