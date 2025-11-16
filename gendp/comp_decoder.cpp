#include "comp_decoder.h"

comp_decoder::comp_decoder() {}
comp_decoder::~comp_decoder() {}

void comp_decoder::execute(unsigned long instruction, int* op, int* in_addr, int* out_addr, int* PC) {

    // instruction: op[0] op[1] op[2] in_addr[0] in_addr[1] in_addr[2] in_addr[3] in_addr[4] in_addr[5] out_addr

    unsigned long magic_mask = (unsigned long)((1ul << (63)));
    unsigned long magic_payload_mask = (unsigned long)(0xFFFFFFFF);
    bool is_magic = (instruction & magic_mask);
    int  magic_payload = instruction & magic_payload_mask;
    if (is_magic) {
        //Used as a hook
        printf("Magic!!!!! payload = %d\n", magic_payload);
        instruction = COMP_NOP_INSTRUCTION; //don't crash rest of simulator
    }

    int i;
    unsigned long out_addr_mask, in_addr_mask[6], op_mask[3];

    out_addr_mask = (1 << REGFILE_ADDR_WIDTH) - 1;
    *out_addr = (int)(out_addr_mask & instruction);

    for (i = 0; i < 6; i++) {
        in_addr_mask[i] = (unsigned long)((1 << REGFILE_ADDR_WIDTH) - 1) << (6 - i) * REGFILE_ADDR_WIDTH;
        // printf("%d %lx %lx\n", i, in_addr_mask[i], instruction);
        in_addr[i] = (in_addr_mask[i] & instruction) >> (6 - i) * REGFILE_ADDR_WIDTH;
    }

    for (i = 0; i < 3; i++) {
        op_mask[i] = (unsigned long)((1 << COMP_OPCODE_WIDTH) - 1) << (7 * REGFILE_ADDR_WIDTH + (2 - i) * COMP_OPCODE_WIDTH);
        op[i] = (op_mask[i] & instruction) >> (7 * REGFILE_ADDR_WIDTH + (2 - i) * COMP_OPCODE_WIDTH);
    }

    // zkn I changed this from op[0] < HALT to op[0] != HALT. I think required cause we now have
    // opcodes greater than HALT
    if (op[0] != HALT){
        (*PC)++;
    } else {  //(op[0] == HALT)
        (*PC) = (*PC);
    }

    // printf("%d %d %d %d %d %d %d %d %d %d\t", op[0], op[1], op[2], in_addr[0], in_addr[1], in_addr[2], in_addr[3], in_addr[4], in_addr[5], *out_addr);
//#ifdef PROFILE
//    printf("%d %d %d %d %d %d %d\t", in_addr[0], in_addr[1], in_addr[2], in_addr[3], in_addr[4], in_addr[5], *out_addr);
//#endif
}
