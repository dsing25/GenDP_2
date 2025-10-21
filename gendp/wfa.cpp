#include "sys_def.h"
#include "wfa.h"
#include "utils.h"

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

    pe_array_unit->run(n, simd, PE_4_SETTING, MAIN_INSTRUCTION_1);

    return 0; //TODO link to score output
    //if (show_output) pe_array_unit->bsw_show_output_buffer(fp);

}

void wfa_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, int simulation_cases) {

    pe_array *pe_array_unit = new pe_array(1024, 1024);

    fprintf(stderr, "read input %s\n", inputFileName);
    FILE *pairFile = fopen(inputFileName, "r");
    
    load_instructions("wfa", WFA_COMPUTE_INSTRUCTION_NUM, WFA_PE_GROUP_SIZE, pe_array_unit);

    std::vector<int> wfa_output;

    //At this point we are looping through input file processing each pair
    FILE *input_file = NULL;
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
