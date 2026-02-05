#include "sys_def.h"
#include "wfa.h"

namespace {
constexpr int MAX_WF_LEN = 16384;
constexpr int N_WFS = 5;
constexpr int MEM_BLOCK_SIZE = 32;
constexpr int PAST_WFS_SIZE = N_WFS * 3 * MAX_WF_LEN;
constexpr int S2_META_BASE = PAST_WFS_SIZE;
} // namespace

int wfa_simulate(pe_array *pe_array_unit, align_input_t& align_input, int n, FILE* fp, 
                 int show_output) {

    int simd = 0;
    pe_array_unit->buffer_reset(pe_array_unit->main_addressing_register, MAIN_ADDR_REGISTER_NUM);
    pe_array_unit->buffer_reset(pe_array_unit->input_buffer, pe_array_unit->input_buffer_size);
    pe_array_unit->buffer_reset(pe_array_unit->output_buffer, pe_array_unit->output_buffer_size);

    pe_array_unit->main_PC = 0;
    for (int i = 0; i < FIFO_GROUP_NUM; i++)
        for (int j = 0; j < FIFO_GROUP_SIZE; j++)
            pe_array_unit->fifo_unit[i][j].clear();
    for (int i = 0; i < WFA_PE_GROUP_SIZE; i++) {
        pe_array_unit->pe_unit[i]->reset();
    }

    //TODO: eventually, we will need to add this. For now, we're not extending, don't need input
    //// Load data from input file to input buffer
    //unsigned int const_64 = load_constant(64);
    //unsigned int const_minus_6 = load_constant(-6);
    //unsigned int const_minus_1 = load_constant(-1);
    //unsigned int const_1 = load_constant(1);
    //unsigned int const_4 = load_constant(4);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(0, &bsw_input->max_tlen);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(1, &bsw_input->max_qlen);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(2, &bsw_input->min_qlen);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(3, &bsw_input->qlen32);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(4, &bsw_input->tlen32);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(5, &bsw_input->H_row32[0]);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(6, &const_64);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(7, &const_minus_6);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(8, &const_minus_1);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(9, &const_1);
    //pe_array_unit->input_buffer_write_from_ddr_unsigned(10, &const_4);
    //for (i = 0; i < (int)bsw_input->max_tlen; i++) {
    //    pe_array_unit->input_buffer_write_from_ddr_unsigned(i+11, &bsw_input->seqBufRef32[i]);
    //}
    //for (i = 0; i < (int)bsw_input->max_tlen; i++) 
    //    pe_array_unit->input_buffer_write_from_ddr_unsigned(i+11+bsw_input->max_tlen, &bsw_input->H_col32[i]);
    //for (i = 0; i < (int)bsw_input->max_qlen; i++) {
    //    pe_array_unit->input_buffer_write_from_ddr_unsigned(i+11+bsw_input->max_tlen*2, &bsw_input->seqBufQer32[i]);
    //}
    //for (i = 0; i < (int)bsw_input->max_qlen; i++)
    //    pe_array_unit->input_buffer_write_from_ddr_unsigned(i+11+bsw_input->max_tlen*2+bsw_input->max_qlen, &bsw_input->H_row32[i]);

    int pattern_len_raw = align_input.pattern_length;
    int text_len_raw = align_input.text_length;

    std::string pattern_seq(align_input.pattern, pattern_len_raw);
    pattern_seq.push_back('D');
    std::string text_seq(align_input.text, text_len_raw);
    text_seq.push_back('L');

    int first_extend_len = 0;
    int min_len = (pattern_len_raw < text_len_raw) ? pattern_len_raw : text_len_raw;
    while (first_extend_len < min_len &&
           align_input.pattern[first_extend_len] == align_input.text[first_extend_len]) {
        first_extend_len++;
    }

    for (int i = 0; i < PAST_WFS_SIZE; i++) {
        pe_array_unit->write_s2(i, -42);
    }
    auto past_wf_index = [](int wf_i, int affine_i, int idx) {
        return (wf_i * 3 + affine_i) * MAX_WF_LEN + idx;
    };
    constexpr int INITIAL_WF_LEN = MEM_BLOCK_SIZE;
    int wf_i = 0;
    for (int j = 0; j < INITIAL_WF_LEN; j++) {
        for (int k = 0; k < 3; k++) {
            pe_array_unit->write_s2(past_wf_index(wf_i, k, j), MIN_INT);
        }
    }
    wf_i++;
    for (int j = 0; j < INITIAL_WF_LEN; j++) {
        for (int k = 0; k < 3; k++) {
            pe_array_unit->write_s2(past_wf_index(wf_i, k, j), MIN_INT);
        }
    }
    wf_i++;
    for (int j = 0; j < INITIAL_WF_LEN; j++) {
        for (int k = 0; k < 3; k++) {
            pe_array_unit->write_s2(past_wf_index(wf_i, k, j), MIN_INT);
        }
    }
    pe_array_unit->write_s2(past_wf_index(wf_i, 2, 0), first_extend_len);
    wf_i++;
    for (int j = 0; j < INITIAL_WF_LEN; j++) {
        for (int k = 0; k < 3; k++) {
            pe_array_unit->write_s2(past_wf_index(wf_i, k, j), MIN_INT);
        }
    }
    for (int j = 0; j < INITIAL_WF_LEN; j++) {
        for (int k = 0; k < 3; k++) {
            pe_array_unit->write_s2(past_wf_index(wf_i + 1, k, j), MIN_INT);
        }
    }
    pe_array_unit->write_s2(past_wf_index(wf_i, 2, 1), first_extend_len);

    for (int i = 0; i < static_cast<int>(text_seq.size()); i++) {
        int pe_id = i % 4;
        int local_addr = TEXT_START + (i / 4);
        int raw_addr = pe_id * SPM_BANK_SIZE + local_addr;
        pe_array_unit->write_spm_magic(raw_addr, static_cast<int>(text_seq[i]));
    }

    for (int i = 0; i < static_cast<int>(pattern_seq.size()); i++) {
        int pe_id = i % 4;
        int local_addr = PATTERN_START + (i / 4);
        int raw_addr = pe_id * SPM_BANK_SIZE + local_addr;
        pe_array_unit->write_spm_magic(raw_addr, static_cast<int>(pattern_seq[i]));
    }

    pe_array_unit->write_s2(S2_META_BASE + 0, pattern_len_raw);
    pe_array_unit->write_s2(S2_META_BASE + 1, text_len_raw);

    pe_array_unit->run(n, simd, PE_4_SETTING, MAIN_INSTRUCTION_1);

    return 0; //TODO link to score output
    //if (show_output) pe_array_unit->bsw_show_output_buffer(fp);

}

void wfa_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, int simulation_cases) {

    pe_array *pe_array_unit = new pe_array(1024, 1024);

    
    //BEGIN LOADING INSTRUCTIONS wasn't able to make a function easily due to prior coding style
    int n_comp_instructions = WFA_COMPUTE_INSTRUCTION_NUM;
    int pe_group_size = WFA_PE_GROUP_SIZE;
    std::string kernel_name = "wfa";
//void load_instructions(std::string kernel_name, size_t n_comp_instructions, size_t pe_group_size, pe_array *pe_array_unit) {
    unsigned long compute_instruction[n_comp_instructions][COMP_INSTR_BUFFER_GROUP_SIZE];
    unsigned long main_instruction[CTRL_INSTR_BUFFER_NUM];
    unsigned long pe_instruction[pe_group_size][CTRL_INSTR_BUFFER_NUM][CTRL_INSTR_BUFFER_GROUP_SIZE];
    for (int i = 0; i < pe_group_size; i++) {
        for (int j = 0; j < CTRL_INSTR_BUFFER_NUM; j++) {
            pe_instruction[i][j][0] = 0x42;
            pe_instruction[i][j][1] = 0x42;
        }
    }
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        main_instruction[i] = 0x42;
    }

    std::string compute_instruction_file = "instructions/"+kernel_name+"/compute_instruction.txt";
    std::string main_instruction_file = "instructions/"+kernel_name+"/main_instruction.txt";
    std::string pe_instruction_file[pe_group_size];
    pe_instruction_file[0] = "instructions/"+kernel_name+"/pe_0_instruction.txt";
    pe_instruction_file[1] = "instructions/"+kernel_name+"/pe_1_instruction.txt";
    pe_instruction_file[2] = "instructions/"+kernel_name+"/pe_2_instruction.txt";
    pe_instruction_file[3] = "instructions/"+kernel_name+"/pe_3_instruction.txt";
    std::fstream fp_input, fp_compute_instruction, fp_main_instruction;
    int n_compute_instruction = 0;
    std::fstream fp_pe_instruction[pe_group_size];
    std::string line;
    int read_index = 0;

    fp_compute_instruction.open(compute_instruction_file, std::ios::in);
    if (fp_compute_instruction.is_open()) {
        read_index = 0;
        while(getline(fp_compute_instruction, line)) {
            compute_instruction[read_index/2][read_index%2] = std::stoull(line, 0, 0);
            read_index++;
        }
        n_compute_instruction = read_index/2;
    } else {
        fprintf(stderr, "Cannot open file %s.\n", compute_instruction_file.c_str());
        exit(-1);
    }
    fp_compute_instruction.close();

    fp_main_instruction.open(main_instruction_file, std::ios::in);
    if (fp_main_instruction.is_open()) {
        read_index = 0;
        while(getline(fp_main_instruction, line)) {
            main_instruction[read_index] = std::stoull(line, 0, 0);
            read_index++;
        }
    } else {
        fprintf(stderr, "Cannot open file %s.\n", main_instruction_file.c_str());
        exit(-1);
    }
    fp_main_instruction.close();

    for (int i = 0; i < pe_group_size; i++) {
        fp_pe_instruction[i].open(pe_instruction_file[i], std::ios::in);
        if (fp_pe_instruction[i].is_open()) {
            read_index = 0;
            while(getline(fp_pe_instruction[i], line)) {
                pe_instruction[i][read_index/2][read_index%2] = std::stoull(line, 0, 0);
                read_index++;
            }
        } else {
            fprintf(stderr, "Cannot open file %s.\n", pe_instruction_file[i].c_str());
            exit(-1);
        }
        fp_pe_instruction[i].close();
    }

    //Legacy mode used for POA and prior traces
    // Load data from input file to instruction buffer
    for (int i = 0; i < n_comp_instructions; i++) {
        pe_array_unit->compute_instruction_buffer_write_from_ddr(i, compute_instruction[i]);
    }
    //End legacy mode. Up to date way is to flash to the PE directly
    for (int i = 0; i < pe_group_size; i++)
        pe_array_unit->pe_comp_instruction_buffer_write_from_ddr(n_comp_instructions, &compute_instruction[0][0], i);

    // Load main & pe instructions into pe_array instruction buffer
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = 0x20f7800000000;
        tmp[1] = main_instruction[i];
        pe_array_unit->main_instruction_buffer_write_from_ddr(i, tmp);
        for (int j = 0; j < pe_group_size; j++){
            //ctrl
            pe_array_unit->pe_instruction_buffer_write_from_ddr(i, pe_instruction[j][i], j);
        }
    }
    //END LOADING INSTRUCTIONS

    std::vector<int> wfa_output;

    fprintf(stderr, "read input %s\n", inputFileName);
    FILE *input_file = fopen(inputFileName, "r");
    if (input_file == nullptr) {
        fprintf(stderr, "Error opening file '%s': %s\n", inputFileName, strerror(errno));
        exit(EXIT_FAILURE);
    }

    //At this point we are looping through input file processing each pair
    char *line1 = NULL, *line2 = NULL;
    int line1_length=0, line2_length=0;
    size_t line1_allocated=0, line2_allocated=0;
    align_input_t align_input;
    while (true) {
        line1_length = getline(&line1,&line1_allocated,input_file);
        if (line1_length==-1) break;
        line2_length = getline(&line2,&line2_allocated,input_file);
        if (line1_length==-1) break;
        
        align_input.pattern = line1+1;
        align_input.pattern_length = line1_length-2;
        align_input.pattern[align_input.pattern_length] = '\0';
        align_input.text = line2+1;
        align_input.text_length = line2_length-2;
        align_input.text[align_input.text_length] = '\0';

        int score_out = wfa_simulate(pe_array_unit, align_input, MAX_CYCLES, fp, show_output);
        wfa_output.push_back(score_out);
    }

    // Free
    fclose(input_file);
    free(line1);
    free(line2);
    
    delete pe_array_unit;
}
