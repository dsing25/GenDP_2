#include "comp_decoder.h"

comp_decoder::comp_decoder() {}
comp_decoder::~comp_decoder() {}

#ifdef PROFILE
const char* opcode_to_string(int opcode) {
    switch(opcode) {
        case ADDITION: return "add";
        case SUBTRACTION: return "sub";
        case MULTIPLICATION: return "mul";
        case CARRY: return "carry";
        case BORROW: return "borrow";
        case MAXIMUM: return "max";
        case MINIMUM: return "min";
        case LEFT_SHIFT: return "lshift";
        case RIGHT_SHIFT: return "rshift";
        case COPY: return "copy";
        case MATCH_SCORE: return "match";
        case LOG2_LUT: return "log2";
        case LOG_SUM_LUT: return "logsum";
        case COMP_LARGER: return "gt";
        case COMP_EQUAL: return "eq";
        case INVALID: return "invalid";
        case HALT: return "halt";
        case BWISE_OR: return "or";
        case BWISE_AND: return "and";
        case BWISE_NOT: return "not";
        case BWISE_XOR: return "xor";
        case LSHIFT_1: return "lshift1";
        case RSHIFT_WORD: return "rshift_w";
        case ADD_I: return "addi";
        case COPY_I: return "copyi";
        case POPCOUNT: return "popcount";
        case CMP_2INP: return "cmp2";
        default: return "unknown";
    }
}
#endif

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

#ifdef PROFILE
    // Print human-readable instruction format
    printf("[%s:%s:%s] ", opcode_to_string(op[0]), opcode_to_string(op[1]), opcode_to_string(op[2]));
    printf("in[%d,%d,%d,%d,%d,%d] out[%d]\t",
           in_addr[0], in_addr[1], in_addr[2], in_addr[3], in_addr[4], in_addr[5], *out_addr);
#endif
}
