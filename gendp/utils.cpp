#include "utils.h"

int load_instructions(std::string kernel_name, size_t n_comp_instructions, size_t pe_group_size, 
                       pe_array *pe_array_unit) {
    unsigned long compute_instruction[n_comp_instructions][COMP_INSTR_BUFFER_GROUP_SIZE];
    unsigned long main_instruction[CTRL_INSTR_BUFFER_NUM];
    unsigned long pe_instruction[pe_group_size][CTRL_INSTR_BUFFER_NUM][CTRL_INSTR_BUFFER_GROUP_SIZE];
    for (int i = 0; i < pe_group_size; i++) {
        for (int j = 0; j < CTRL_INSTR_BUFFER_NUM; j++) {
            pe_instruction[i][j][0] = 0x20f7800000000;
            pe_instruction[i][j][1] = 0x20f7800000000;
        }
    }
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        main_instruction[i] = -1;
    }

    std::string compute_instruction_file = "instructions/"+kernel_name+"/compute_instruction.txt";
    std::string main_instruction_file = "instructions/"+kernel_name+"/main_instruction.txt";
    std::string pe_instruction_file[pe_group_size];
    pe_instruction_file[0] = "instructions/"+kernel_name+"/pe_0_instruction.txt";
    pe_instruction_file[1] = "instructions/"+kernel_name+"/pe_1_instruction.txt";
    pe_instruction_file[2] = "instructions/"+kernel_name+"/pe_2_instruction.txt";
    pe_instruction_file[3] = "instructions/"+kernel_name+"/pe_3_instruction.txt";
    std::fstream fp_input, fp_compute_instruction, fp_main_instruction;
    std::fstream fp_pe_instruction[pe_group_size];
    std::string line;
    int read_index = 0;

    fp_compute_instruction.open(compute_instruction_file, std::ios::in);
    if (fp_compute_instruction.is_open()) {
        read_index = 0;
        while(getline(fp_compute_instruction, line)) {
            compute_instruction[read_index/2][read_index%2] = std::stol(line, 0, 16);
            read_index++;
        }
    } else {
        fprintf(stderr, "Cannot open file %s.\n", compute_instruction_file.c_str());
        exit(-1);
    }
    fp_compute_instruction.close();

    fp_main_instruction.open(main_instruction_file, std::ios::in);
    if (fp_main_instruction.is_open()) {
        read_index = 0;
        while(getline(fp_main_instruction, line)) {
            main_instruction[read_index] = std::stol(line, 0, 16);
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
                pe_instruction[i][read_index/2][read_index%2] = std::stol(line, 0, 16);
                read_index++;
            }
        } else {
            fprintf(stderr, "Cannot open file %s.\n", pe_instruction_file[i].c_str());
            exit(-1);
        }
        fp_pe_instruction[i].close();
    }

    // Load data from input file to instruction buffer
    for (int i = 0; i < n_comp_instructions; i++) {
        pe_array_unit->compute_instruction_buffer_write_from_ddr(i, compute_instruction[i]);
    }

    // Load main & pe instructions into pe_array instruction buffer
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = 0xe;
        tmp[1] = main_instruction[i];
        pe_array_unit->main_instruction_buffer_write_from_ddr(i, tmp);
        for (int j = 0; j < pe_group_size; j++)
            pe_array_unit->pe_instruction_buffer_write_from_ddr(i, pe_instruction[j][i], j);
    }
}
