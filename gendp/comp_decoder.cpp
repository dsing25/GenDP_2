#include "comp_decoder.h"

comp_decoder::comp_decoder() {}
comp_decoder::~comp_decoder() {}

void comp_decoder::execute(unsigned long instruction, int* op, int* in_addr, int* out_addr, int* PC) {

    // instruction layout (64 bits, MSB first):
    // op[0](5) op[1](5) op[2](5) in[0](7) in[1](7) in[2](7) in[3](7) in[4](7) in[5](7) out(7)

    int i;
    unsigned long out_addr_mask, in_addr_mask[6], op_mask[3];

    out_addr_mask = (1 << COMP_ADDR_WIDTH) - 1;
    *out_addr = (int)(out_addr_mask & instruction);

    for (i = 0; i < 6; i++) {
        in_addr_mask[i] = (unsigned long)((1 << COMP_ADDR_WIDTH) - 1) << (6 - i) * COMP_ADDR_WIDTH;
        in_addr[i] = (in_addr_mask[i] & instruction) >> (6 - i) * COMP_ADDR_WIDTH;
    }

    for (i = 0; i < 3; i++) {
        op_mask[i] = (unsigned long)((1 << COMP_OPCODE_WIDTH) - 1) << (7 * COMP_ADDR_WIDTH + (2 - i) * COMP_OPCODE_WIDTH);
        op[i] = (op_mask[i] & instruction) >> (7 * COMP_ADDR_WIDTH + (2 - i) * COMP_OPCODE_WIDTH);
    }

    if (op[0] != HALT){
        (*PC)++;
    } else {
        (*PC) = (*PC);
    }
}
