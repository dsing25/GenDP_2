#include "pe_array.h"
#include <cassert>
#include "sys_def.h"
#include "data_buffer.h"
#include "simulator.h"
#include <iomanip>

#define NUM_FRACTION_BITS 16
#define MAX_RANGE NUM_FRACTION_BITS
#define NUM_INTEGER_BITS 5

pe_array::pe_array(int input_size, int output_size) {

    int i;
    input_buffer_size = input_size;
    output_buffer_size = output_size;

    input_buffer = (int*)calloc(input_buffer_size, sizeof(int));
    output_buffer = (int*)calloc(output_buffer_size, sizeof(int));

    main_addressing_register[0] = 0;
    main_PC = 0;
    //+1 allows addressing full range. 1 is dummy data. Not legal in real hardware
    SPM_unit = new SPM(SPM_ADDR_NUM+1, &active_event_producers);
    for (i = 0; i < PE_NUM; i++)
        pe_unit[i] = new pe(i, SPM_unit);
    load_data = 0;
    store_data = 0;
    from_fifo = 0;
}

pe_array::~pe_array() {
    int i;
    free(input_buffer);
    free(output_buffer);
    for (i = 0; i < PE_NUM; i++)
        delete pe_unit[i];
    delete SPM_unit;
}

void pe_array::buffer_reset(int* buffer, int num) {
    int i;
    for (i = 0; i < num; i++)
        buffer[i] = 0;
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
#ifdef PROFILE
        printf("main addr register[%d].\n", dest_addr);
#endif
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
    int sext_imm_0 = reg_imm_0 | (reg_imm_0_sign_bit ? 0xFFFFC000 : 0);
    int reg_0 = (instruction & reg_0_mask) >> (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_immBar_flag_1 = (instruction & reg_immBar_flag_1_mask) >> (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_auto_increasement_flag_1 = (instruction & reg_auto_increasement_flag_1_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1 = (instruction & reg_imm_1_mask) >> (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1_sign_bit = (instruction & reg_imm_1_sign_bit_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    int sext_imm_1 = reg_imm_1 | (reg_imm_1_sign_bit ? 0xFFFFC000 : 0);
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
        constexpr int MEM_BLOCK_SIZE = 32;
        constexpr int EXTRA_O_LOAD_ADDR = 7*MEM_BLOCK_SIZE;
        constexpr int BLOCK_0_START = 0;
        constexpr int BLOCK_1_START = MEM_BLOCK_SIZE*7 + 2;
        constexpr int MAX_WF_LEN = 5000;
        constexpr int N_WFS = 5;
        //4 previous scores, 3 affine wavefronts, each wavefront MEM_BLOCK entries. Rotating buffer
        static int past_wfs[N_WFS][3][MAX_WF_LEN];
        static int past_wf_sizes[N_WFS];
        static std::ofstream magic_wfs_out("magic_wfs_out.txt");
        static ModInt current_wf_i(N_WFS);

        if (magic_payload == 4) {
        //INITIALIZATION BEGINING OF TIME
            int current_wf_size = 0;
            const char* pattern_seq = "GTTTAAAAGGTTTAAAAGGTTTAAAAGGTTTAAAAGGTTD";
            const char* text_seq = "GAAAAAAATGAAAAAAATGAAAAAAATGAAAAAAATGAAL";
            int text_len = 40;
            int pattern_len = 40;
            int first_extend_len = 1;
            //loading the first wavefront. Initialization of this alignment
            //initialization logic
            memset(past_wfs, 0, sizeof(past_wfs));
            for (int a = 0; a < 5; a++)
                for (int b = 0; b < 3; b++)
                    for (int c = 0; c< MAX_WF_LEN; c++)
                        past_wfs[a][b][c] = -42;
            constexpr int INITIAL_WF_LEN = MEM_BLOCK_SIZE;
            //WF 0
            past_wf_sizes[current_wf_i] = 1;
            for (int j = 0; j < INITIAL_WF_LEN; j++) {
                for (int k = 0; k < 3; k++) {
                    past_wfs[current_wf_i][k][j] = -99;
                }
            }
            current_wf_i++; //0 wf all zero
            //WF 1
            for (int j = 0; j < INITIAL_WF_LEN; j++) {
                for (int k = 0; k < 3; k++) {
                    past_wfs[current_wf_i][k][j] = -99;
                }
            }
            past_wf_sizes[current_wf_i] = 1;
            current_wf_i++; //2 wf all zero
            //WF 2
            for (int j = 0; j < INITIAL_WF_LEN; j++) {
                for (int k = 0; k < 3; k++) {
                    past_wfs[current_wf_i][k][j] = -99;
                }
            }
            past_wf_sizes[current_wf_i] = 1;
            past_wfs[current_wf_i][2][0] = first_extend_len; //middle m wavefront
            current_wf_i++; //4 should have a 1, but it's never used
            //WF 3
            for (int j = 0; j < INITIAL_WF_LEN; j++) {
                for (int k = 0; k < 3; k++) {
                    past_wfs[current_wf_i][k][j] = -99;
                }
            }
            //Extra: first postpadding misses cause postpad is not on pe3. this lets us ignore that
            for (int j = 0; j < INITIAL_WF_LEN; j++) {
                for (int k = 0; k < 3; k++) {
                    past_wfs[current_wf_i+1][k][j] = -99;
                }
            }
            past_wf_sizes[current_wf_i] = 3;
            past_wfs[current_wf_i][2][1] = first_extend_len; //middle m wavefront

            //at this point the first four wavefronts have been defined initialized with dummy, and 
            //the correct middle m for last two. The score is 2. The size was 3.

            current_wf_size = 5;


            // Write TEXT sequence with round-robin interleaving across PEs
            for (int i = 0; i < text_len; i++) {
                int pe_id = i % 4;
                int local_addr = TEXT_START + (i / 4);
                SPM_unit->access_magic(pe_id, local_addr) = (int)text_seq[i];
            }

            // Write PATTERN sequence with round-robin interleaving across PEs
            for (int i = 0; i < pattern_len; i++) {
                int pe_id = i % 4;
                int local_addr = PATTERN_START + (i / 4);
                SPM_unit->access_magic(pe_id, local_addr) = (int)pattern_seq[i];
            }

            // Initialize register values for each PE
            for (int i = 0; i < 4; i++) {
                pe_unit[i]->addr_regfile_unit->buffer[13] = text_len;
                pe_unit[i]->addr_regfile_unit->buffer[8] = pattern_len;
            }
            magic_wfs_out << "lkjsdfoih"; //helps vimdiff
        } else if (magic_payload == 1){
            int (&regfile)[16] = main_addressing_register;
        //READ FROM MAIN MEM. WRITE TO NEXT_BLOCK_START (gr[10)
            int current_wf_size = main_addressing_register[12];
            int next_block_start = main_addressing_register[10];
            int block_iter = main_addressing_register[9];
            main_addressing_register[3] = current_wf_i;
            int width = 3; // for display


            

            //Rest is about writing the inputs to the SPM for each pe
            auto getInputVec = [&](int prepad, int postpad, int wf_i,
                                int affine_ind) {
                std::vector<int>* vec = new std::vector<int>();
                int j = 0;
                // Write prepadding zeros
                for (; j < prepad; j++)
                    vec->push_back(-99);
                // Copy data from past_wfs
                for (; j < prepad + past_wf_sizes[wf_i]; j++)
                    vec->push_back(past_wfs[wf_i][affine_ind][j - prepad]);
                // Write postpadding zeros
                for (; j < prepad + past_wf_sizes[wf_i] + postpad; j++)
                    vec->push_back(-99);
                return vec;
            };
            auto mvdq = [&](int dst, int src, bool toSPM){
                //TODO this is not realistic. We need to access blocks not arbitrary location.
                std::cout << dst << " " << src << std::endl;
                for (int i =0; i < 8; i++){
                    if (toSPM){
                        SPM_unit->buffer[dst+i] = ((int*)past_wfs)[src+i];
                    } else {
                        ((int*)past_wfs)[dst+i] = SPM_unit->buffer[src+i];
                    }
                }
            };

            std::vector<int>* fullO = getInputVec(3, 5, current_wf_i - 3, 2);
            //std::vector<int>* fullM = getInputVec(2, 2, current_wf_i - 1, 2);  // Now using register-mapped approach
            //std::vector<int>* fullI = getInputVec(2, 0, current_wf_i, 1);
            //std::vector<int>* fullD = getInputVec(0, 2, current_wf_i, 0);


            //Now write to SPMs
            int n_diags_per_pe = current_wf_size / 4 + 1; //ceil div
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                //iterates over wf id. Then add appropriate offsets to get the SPM addr
                for (int j = start; j < end; j++) {
                    //SET O
                    SPM_unit->access_magic(i, 0 * MEM_BLOCK_SIZE + next_block_start + j - start) = (*fullO)[j];
                    //SET M (now using register-mapped approach)
                    //SPM_unit->access_magic(i, 1 * MEM_BLOCK_SIZE + next_block_start + j - start) = (*fullM)[j];
                    //SET I
                    //SPM_unit->access_magic(i, 2 * MEM_BLOCK_SIZE + next_block_start + j - start) = (*fullI)[j];
                    //SET D
            //        SPM_unit->access_magic(i, 3 * MEM_BLOCK_SIZE + next_block_start + j - start) = (*fullD)[j];

                }
                //fix up the extra two Os needed from previous tile
                if (i == 0){
                    SPM_unit->access_magic(i, EXTRA_O_LOAD_ADDR+next_block_start)   = MIN_INT;
                    SPM_unit->access_magic(i, EXTRA_O_LOAD_ADDR+next_block_start+1) = MIN_INT;
                } else {
                    SPM_unit->access_magic(i, EXTRA_O_LOAD_ADDR+next_block_start)   = (*fullO)[start - 2];
                    SPM_unit->access_magic(i, EXTRA_O_LOAD_ADDR+next_block_start+1) = (*fullO)[start - 1];
                }
            }
            //display input vectors
            magic_wfs_out << "Score " << current_wf_size - 1 << ":" << std::endl << std::endl;
            int k = 0;
            for (std::vector<int>* vec : {fullO/*, fullM, fullI, fullD*/}) {
                for (k = 0; k < current_wf_size; k++) {
                    magic_wfs_out << std::setw(width) << (*vec)[k];
                }
                for (; k  < MEM_BLOCK_SIZE; k++) {
                    magic_wfs_out << std::setw(width) << 0; //lines up for easy comparison
                }
                magic_wfs_out << std::endl;
            }

            delete fullO;
            //delete fullM;  // Now using register-mapped approach
            //delete fullI;
            //delete fullD;

            /*
             * Preconditions:
             *      gr4: diags per pe
             *      gr3: current_wf_i
             *      gr1: points to SPM row we're writing to
             *      gr9: holds the iteration
             *      gr12: holds wavefront len
             *   prepadding: the number of MIN_INTS to put at the start of wf. (must be < 8)
             *   postpadding: number of MIN_INTS to put at end of wf. (must be < 8)
             *   affineInd: {D0:I1:H2}. For wf calculation
             * Postconditions:
             *      The wavefront located in 
             *      gr11:destroyed. Used as a tmp
             *      gr2: destroyed.
             *      gr1: preserved
             *      gr5: destroyed. Used as loop end
             */
            auto loadSpmRegMapped = [&](int prepad_len, int postpad_len, int affineInd, 
                    int wf_i_offset){
                //offset into mainMem = wf_i*3*max_wf_len + affine_ind*max_wf_len + block_iter *block_size
                regfile[11] = affineInd * MAX_WF_LEN; //affine_ind * wflen
                regfile[2] = regfile[11]; //initial set = instead of +=
                regfile[11] = regfile[3];
                //modular subtraction
                for (int i=0; i < wf_i_offset; i++){
                    regfile[11] -= 1;
                    if (regfile[11] < 0) {
                        regfile[11] = N_WFS-1;
                    }
                }
                regfile[11] *= MAX_WF_LEN;
                //multiply by 3
                for (int i = 0; i < 3; i++){
                    regfile[2] += regfile[11];
                }
                regfile[11] = regfile[9] * MEM_BLOCK_SIZE; //block iter * block size
                regfile[2] += regfile[11];

                //prepad, we do one full pass through here
                for (int j = 0; j < prepad_len; j++){
                    SPM_unit->buffer[regfile[1]+j+SPM_BANK_SIZE*0] = MIN_INT;
                }
                //end point define - must be set BEFORE incrementing regfile[1]
                regfile[5] = regfile[1] + regfile[4];
                mvdq(regfile[1]+prepad_len, regfile[2], true); //ignore last prepad_len of this
                regfile[2] -= prepad_len;
                regfile[11] = regfile[2] + regfile[4];
                mvdq(regfile[1]+SPM_BANK_SIZE*1,regfile[11],true); //pe1
                regfile[11] += regfile[4];
                mvdq(regfile[1]+SPM_BANK_SIZE*2,regfile[11],true); //pe1
                regfile[11] += regfile[4];
                mvdq(regfile[1]+SPM_BANK_SIZE*3,regfile[11],true); //pe1
                regfile[1] += 8;
                regfile[2] += 8;

                //now we do the remaining passes (if there are any)
                while (regfile[1] < regfile[5]){
                    regfile[11] = regfile[2]; //temp cache
                    for (int i = 0; i < 4; i++){
                        mvdq(regfile[1]+SPM_BANK_SIZE*i, regfile[11], true);
                        if (i != 4) //save a cycle don't need inc
                            regfile[11] += regfile[4];
                    }
                    regfile[1] += 8;
                    regfile[2] += 8;
                }
                //We may have overshot, so we gotta reset to true end of last pe
                regfile[1] = regfile[5] - regfile[4]; //reset to base
                //using gr11 to point to the cell we want to write to
                regfile[11] = regfile[12] - regfile[4];
                regfile[11] -= regfile[4];
                regfile[11] -= regfile[4];
                regfile[11] += regfile[1];
                //gr1 now holds remainder
                regfile[11] -= (postpad_len);

                //postpad
                for (int j = 0; j < postpad_len; j++){
                    //for (int i = 0; i < 4; i++){
                        SPM_unit->buffer[regfile[11]+SPM_BANK_SIZE*3]   = MIN_INT; //only for last
                        std::cout << "zkn " << regfile[11] << std::endl;
                    //}
                    regfile[11] = regfile[11]+1;
                }

            };

            //diags_per_pe
            regfile[4] = regfile[12] >> 2;
            regfile[4] += 1;
            //Write fullMs
            regfile[1] = 1*MEM_BLOCK_SIZE + regfile[10]; //offset into PEs
            loadSpmRegMapped(2, 2, 2, 1);  // prepad=2, postpad=2, affineInd=2
            //Write fullIs
            regfile[1] = 2*MEM_BLOCK_SIZE + regfile[10]; //offset into PEs
            loadSpmRegMapped(2,0,1,0);
            //Write the fullDs
            regfile[1] = 3*MEM_BLOCK_SIZE + regfile[10]; //offset into PEs
            loadSpmRegMapped(0, 2, 0,0);



            //display M
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 1 * MEM_BLOCK_SIZE + next_block_start + j - start);
                    k++;
                }
            }
            for (; k < MEM_BLOCK_SIZE; k++) {
                magic_wfs_out << std::setw(width) << 0;
            }
            magic_wfs_out << std::endl;

            //display I
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                //iterates over wf id. Then add appropriate offsets to get the SPM addr
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 2 * MEM_BLOCK_SIZE + next_block_start + j - start);
                    k++;
                }
            }
            for (; k < MEM_BLOCK_SIZE; k++) {
                magic_wfs_out << std::setw(width) << 0;
            }
            magic_wfs_out << std::endl;

            //display D
            k = 0;
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                //iterates over wf id. Then add appropriate offsets to get the SPM addr
                for (int j = start; j < end; j++) {
                    magic_wfs_out << std::setw(width) << SPM_unit->access_magic(i, 3 * MEM_BLOCK_SIZE + next_block_start + j - start);
                    k++;
                }
            }
            for (; k < MEM_BLOCK_SIZE; k++) {
                magic_wfs_out << std::setw(width) << 0;
            }
            magic_wfs_out << std::endl;

        } else if (magic_payload == 2){
        //INCREMENT CURRENT_WF_I
            printf("score %d:\n", past_wf_sizes[current_wf_i]+3);
            current_wf_i++;
        } else if (magic_payload == 3){
        //WRITE MAIN MEM WITH RESULTS IN CURRENT_BLOCK_START (gr[8])
            int current_wf_size = main_addressing_register[12];
            int this_block_start = main_addressing_register[8];
            int block_iter = main_addressing_register[9];
            int write_wf_i = current_wf_i + 1;
            //store output wavefronts
            int n_diags_per_pe = current_wf_size / 4 + 1; //ceil div
            for (int i = 0; i < 4; i++) {
                int start = i*n_diags_per_pe + block_iter * MEM_BLOCK_SIZE;
                int end_this_pe_comp_region = std::min(n_diags_per_pe*(i+1), current_wf_size);
                int end   = std::min(start + MEM_BLOCK_SIZE, end_this_pe_comp_region);
                for (int j = start; j < end; j++) {
                    past_wfs[write_wf_i][0][j] = SPM_unit->access_magic(i, 5 * MEM_BLOCK_SIZE + this_block_start + j - start); //set d write
                    past_wfs[write_wf_i][1][j] = SPM_unit->access_magic(i, 6 * MEM_BLOCK_SIZE + this_block_start + j - start); //set i write
                    past_wfs[write_wf_i][2][j] = SPM_unit->access_magic(i, 4 * MEM_BLOCK_SIZE + this_block_start + j - start); //set m write
                }
            }
            past_wf_sizes[write_wf_i] = current_wf_size;

            //display the last computed wavefront
            int i = 0;
            int width = 3;
            for (int affine_id : {2,0,1}) {
                for (i = 0; i < past_wf_sizes[write_wf_i]; i++) {
                    magic_wfs_out << std::setw(width) << past_wfs[write_wf_i][affine_id][i];
                }
                for (; i  < MEM_BLOCK_SIZE; i++) {
                    magic_wfs_out << std::setw(width) << 0; //lines up for easy comparison
                }
                magic_wfs_out << std::endl;
            }
        } else {
            fprintf(stderr, "ERROR: PE_ARRAY PC=%d cycle=%d unknown magic instruction payload %d.\n", *PC, cycle, magic_payload);
            exit(-1);
        }

        (*PC)++;
    } else if (opcode == 0) {              // add rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        *get_output_dest(dest, rd) = sum;
#ifdef PROFILE
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 1) {       // sub rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a - add_b;
        *get_output_dest(dest,rd) = sum;
#ifdef PROFILE
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 2) {       // addi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = imm;
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        *get_output_dest(dest,rd) = sum;
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
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd);
        store(dest, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd);
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1]++;
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
    } else if (opcode == 8) {       // bne rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("bne %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
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
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
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
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
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
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
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
        //main_addressing_register
        //TODO is main_addressing_register the correct place to go?
        assert(dest == CTRL_GR);  // only support gr
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = main_addressing_register[rs2];
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
        int operand1 = main_addressing_register[rs2];
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
        int operand1 = main_addressing_register[rs2];
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
        add_a = main_addressing_register[rs2];
        add_b = imm;
        sum = add_a - add_b;
        *get_output_dest(dest,rd) = sum;
#ifdef PROFILE
        printf("subi gr[%d] gr[%d] %d (%d %d %d)\n", rd, rs2, imm, sum, add_a, add_b);
#endif
        (*PC)++;
    } else {
        fprintf(stderr, "main control instruction opcode error. opcode = %d\n", opcode);
        exit(-1);
    }
    return 0;
}

int* pe_array::get_output_dest(int dest, int rd){
    // write out only supported for GR or out buffer
    if (dest == CTRL_GR){
        return &main_addressing_register[rd];
    } else if (dest == CTRL_OUT_BUF){
        return &output_buffer[rd];
    } else if (dest == CTRL_OUT_PORT){
        return &store_data;
    } else {
        fprintf(stderr, 
                "Only dest CTRL_GR and CTRL_OUT_BUF are supported for pe_array, non MV CTRL instr. dest = %d. PC = %d\n", dest, main_PC);
        exit(-1);
    }
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
    int sext_imm_0 = reg_imm_0 | (reg_imm_0_sign_bit ? 0xFFFFC000 : 0);
    int reg_0 = (instruction & reg_0_mask) >> (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_immBar_flag_1 = (instruction & reg_immBar_flag_1_mask) >> (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_auto_increasement_flag_1 = (instruction & reg_auto_increasement_flag_1_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1 = (instruction & reg_imm_1_mask) >> (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1_sign_bit = (instruction & reg_imm_1_sign_bit_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    int sext_imm_1 = reg_imm_1 | (reg_imm_1_sign_bit ? 0xFFFFC000 : 0);
    int reg_1 = (instruction & reg_1_mask) >> CTRL_OPCODE_WIDTH;
    int opcode = instruction & opcode_mask;

#ifdef PROFILE
    printf("PC = %d\t", *PC);
#endif
    if (main_instruction_setting == MAIN_INSTRUCTION_2) {
        if (((opcode == 4 || opcode == 5) && (dest != 5 && dest != 6 && dest != 11 && dest != 12 && dest != 13 && dest != 14)) || opcode == 14) {
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
    } else if (opcode == 5) {       // mv dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("Move ");
#endif
        data = load(src, reg_immBar_flag_1, sext_imm_1, reg_1, simd);
        store(dest, reg_immBar_flag_0, sext_imm_0, reg_0, data, simd);
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1]++;
    }
    // } else fprintf(stderr, "decode_output opcode error %d.\n", opcode);
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

void pe_array::handle_spm_data_ready(SpmDataReadyData* evData) {
    pe_unit[evData->requestorId]->recieve_spm_data(evData->data);
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


void pe_array::run(int cycle_limit, int simd, int setting, int main_instruction_setting) {
    int i, j, flag, old_PC;
    cycle = 0;

    while (1) {
        cycle++;
        old_PC = main_PC;
        process_events();
        flag = decode(main_instruction_buffer[main_PC][1], &main_PC, simd, setting, main_instruction_setting);
        pe_unit[0]->load_data = store_data;
        pe_unit[0]->load_instruction[0] = PE_instruction[0];
        pe_unit[0]->load_instruction[1] = PE_instruction[1];

        if (setting == PE_4_SETTING) {
            for (i = 0; i < 4; i++) {
#ifdef PROFILE
                printf("PE[%d]\t", i);
#endif
                pe_unit[i]->run(simd);
                //zkn pass through systolic connections
                if (i < 3) {
                    pe_unit[i+1]->load_data = pe_unit[i]->store_data;
                    pe_unit[i+1]->load_instruction[0] = pe_unit[i]->store_instruction[0];
                    pe_unit[i+1]->load_instruction[1] = pe_unit[i]->store_instruction[1];
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
                    pe_unit[j*4]->load_instruction[0] = pe_unit[j*4-1]->store_instruction[0];
                    pe_unit[j*4]->load_instruction[1] = pe_unit[j*4-1]->store_instruction[1];
                }

                for (i = 0; i < 4; i++) {
#ifdef PROFILE
                    printf("PE[%d]\t", j*4+i);
#endif
                    pe_unit[j*4+i]->run(simd);
                    if (i < 3) {
                        pe_unit[j*4+i+1]->load_data = pe_unit[j*4+i]->store_data;
                        pe_unit[j*4+i+1]->load_instruction[0] = pe_unit[j*4+i]->store_instruction[0];
                        pe_unit[j*4+i+1]->load_instruction[1] = pe_unit[j*4+i]->store_instruction[1];
                    } else if (j*4+i == 63) {
                        load_data = pe_unit[63]->store_data;
                    }
                }
            }
        }
        from_fifo = 0;
        
        if (main_instruction_setting == MAIN_INSTRUCTION_1)
            decode_output(main_instruction_buffer[old_PC][1], &old_PC, simd, setting, main_instruction_setting);
        else if (main_instruction_setting == MAIN_INSTRUCTION_2)
            decode_output(main_instruction_buffer[old_PC][0], &old_PC, simd, setting, main_instruction_setting);

        //zkn TODO I don't know if these should be in the above else or not
        main_addressing_register[13] = pe_unit[0]->get_gr_10() && pe_unit[1]->get_gr_10();
        for (i = 2; i < setting; i++)
            main_addressing_register[13] = main_addressing_register[13] && pe_unit[i]->get_gr_10();
        if (flag == -1 || cycle == cycle_limit) {
            printf("cycle %d\n", cycle);
            break;
        }
    }

    // fprintf(stderr, "Finish simulation.\n");
}
