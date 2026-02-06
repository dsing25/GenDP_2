#include "sys_def.h"
#include "gbv.h"

int gbv_simulate(pe_array *pe_array_unit, gbv_align_input_t& align_input, int n, FILE* fp, int show_output) {
    int simd = 0;
    pe_array_unit->buffer_reset(pe_array_unit->main_addressing_register, MAIN_ADDR_REGISTER_NUM);
    pe_array_unit->buffer_reset(pe_array_unit->input_buffer, pe_array_unit->input_buffer_size);
    pe_array_unit->buffer_reset(pe_array_unit->output_buffer, pe_array_unit->output_buffer_size);

    pe_array_unit->main_PC = 0;
    for (int i = 0; i < FIFO_GROUP_NUM; i++)
        for (int j = 0; j < FIFO_GROUP_SIZE; j++)
            pe_array_unit->fifo_unit[i][j].clear();
    for (int i = 0; i < GBV_PE_GROUP_SIZE; i++) {
        pe_array_unit->pe_unit[i]->reset();
    }

    // Example: Write query and ref_basepair to input buffer if needed
    // pe_array_unit->input_buffer_write_from_ddr_unsigned(0, &align_input.query);
    // pe_array_unit->input_buffer_write_from_ddr_unsigned(1, &align_input.ref_basepair);

    pe_array_unit->run(n, simd, PE_4_SETTING, MAIN_INSTRUCTION_1);

    return 0; // TODO: Return actual score/output if needed
    // if (show_output) pe_array_unit->show_output_buffer(fp);
}

void gbv_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, int simulation_cases) {
    pe_array *pe_array_unit = new pe_array(1024, 1024);

    int n_comp_instructions = GBV_COMPUTE_INSTRUCTION_NUM;
    int pe_group_size = GBV_PE_GROUP_SIZE;
    std::string kernel_name = "gbv";
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

    std::string compute_instruction_file = "instructions/" + kernel_name + "/compute_instruction.txt";
    std::string main_instruction_file = "instructions/" + kernel_name + "/main_instruction.txt";
    std::string pe_instruction_file[pe_group_size];
    pe_instruction_file[0] = "instructions/" + kernel_name + "/pe_0_instruction.txt";
    pe_instruction_file[1] = "instructions/" + kernel_name + "/pe_1_instruction.txt";
    pe_instruction_file[2] = "instructions/" + kernel_name + "/pe_2_instruction.txt";
    pe_instruction_file[3] = "instructions/" + kernel_name + "/pe_3_instruction.txt";
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

    // Load instructions into PE array
    for (int i = 0; i < n_comp_instructions; i++) {
        pe_array_unit->compute_instruction_buffer_write_from_ddr(i, compute_instruction[i]);
    }
    for (int i = 0; i < pe_group_size; i++)
        pe_array_unit->pe_comp_instruction_buffer_write_from_ddr(n_comp_instructions, &compute_instruction[0][0], i);

    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = 0x20f7800000000;
        tmp[1] = main_instruction[i];
        pe_array_unit->main_instruction_buffer_write_from_ddr(i, tmp);
        for (int j = 0; j < pe_group_size; j++){
            pe_array_unit->pe_instruction_buffer_write_from_ddr(i, pe_instruction[j][i], j);
        }
    }

    std::vector<int> gbv_output;

    fprintf(stderr, "read input %s\n", inputFileName);
    FILE *input_file = fopen(inputFileName, "r");
    if (input_file == nullptr) {
        fprintf(stderr, "Error opening file '%s': %s\n", inputFileName, strerror(errno));
        exit(EXIT_FAILURE);
    }

        gbv_align_input_t align_input;
    char charline[256];
    while (true) {
        // Read 7 lines for each input struct
        if (!fgets(charline, sizeof(charline), input_file)) break;
        align_input.ref_basepair = (uint8_t)strtoul(charline, nullptr, 10);

        for (int i = 0; i < 4; ++i) {
            if (!fgets(charline, sizeof(charline), input_file)) break;
            align_input.eq_vector[i] = strtoul(charline, nullptr, 10);
        }

        if (!fgets(charline, sizeof(charline), input_file)) break;
        align_input.hinN = atoi(charline);

        if (!fgets(charline, sizeof(charline), input_file)) break;
        align_input.hinP = atoi(charline);

        // Optionally, check for incomplete input here

        int score_out = gbv_simulate(pe_array_unit, align_input, GBV_MAX_CYCLES, fp, show_output);
        gbv_output.push_back(score_out);
    }

    fclose(input_file);

    delete pe_array_unit;
}