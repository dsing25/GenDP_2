#include "sys_def.h"
#include "pe_array.h"
#include "bankThrasher.h"
#include <string>
#include <fstream>

void bankThrasher_simulation(char *inputFileName, char *outputFileName, FILE *fp,
                             int show_output, int simulation_cases) {
    printf("Starting bankThrasher simulation...\n");
    fflush(stdout);

    // Create PE array
    pe_array* pe_array_unit = new pe_array(512, 512);

    int pe_group_size = BANKTHRASHER_PE_GROUP_SIZE;
    int n_comp_instructions = BANKTHRASHER_COMPUTE_INSTRUCTION_NUM;

    // Allocate and initialize instruction buffers
    unsigned long compute_instruction[n_comp_instructions][COMP_INSTR_BUFFER_GROUP_SIZE];
    unsigned long main_instruction[CTRL_INSTR_BUFFER_NUM];
    unsigned long pe_instruction[pe_group_size][CTRL_INSTR_BUFFER_NUM][CTRL_INSTR_BUFFER_GROUP_SIZE];

    // Pre-initialize with NOPs
    for (int i = 0; i < pe_group_size; i++) {
        for (int j = 0; j < CTRL_INSTR_BUFFER_NUM; j++) {
            pe_instruction[i][j][0] = CTRL_NOP_INSTRUCTION;  // halt
            pe_instruction[i][j][1] = CTRL_NOP_INSTRUCTION;
        }
    }
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        main_instruction[i] = CTRL_NOP_INSTRUCTION;
    }

    std::string kernel_name = "bankThrasher";
    std::fstream fp_compute, fp_main;
    std::fstream fp_pe[pe_group_size];
    std::string line;
    int read_index;

    // Load compute instructions
    std::string compute_file = "instructions/" + kernel_name + "/compute_instruction.txt";
    fp_compute.open(compute_file, std::ios::in);
    if (fp_compute.is_open()) {
        read_index = 0;
        while (getline(fp_compute, line)) {
            compute_instruction[read_index/2][read_index%2] = std::stoull(line, 0, 0);
            read_index++;
        }
    } else {
        fprintf(stderr, "Cannot open file %s\n", compute_file.c_str());
        exit(-1);
    }
    fp_compute.close();

    // Load main instructions
    std::string main_file = "instructions/" + kernel_name + "/main_instruction.txt";
    fp_main.open(main_file, std::ios::in);
    if (fp_main.is_open()) {
        read_index = 0;
        while (getline(fp_main, line)) {
            main_instruction[read_index] = std::stoull(line, 0, 0);
            read_index++;
        }
    } else {
        fprintf(stderr, "Cannot open file %s\n", main_file.c_str());
        exit(-1);
    }
    fp_main.close();

    // Load PE instructions
    for (int pe_id = 0; pe_id < pe_group_size; pe_id++) {
        std::string pe_file = "instructions/" + kernel_name + "/pe_" +
                              std::to_string(pe_id) + "_instruction.txt";
        fp_pe[pe_id].open(pe_file, std::ios::in);
        if (fp_pe[pe_id].is_open()) {
            read_index = 0;
            while (getline(fp_pe[pe_id], line)) {
                pe_instruction[pe_id][read_index/2][read_index%2] = std::stoull(line, 0, 0);
                read_index++;
            }
        } else {
            fprintf(stderr, "Cannot open file %s\n", pe_file.c_str());
            exit(-1);
        }
        fp_pe[pe_id].close();
    }

    // Write instructions to pe_array
    for (int i = 0; i < n_comp_instructions; i++) {
        pe_array_unit->compute_instruction_buffer_write_from_ddr(i, compute_instruction[i]);
    }
    for (int i = 0; i < pe_group_size; i++) {
        pe_array_unit->pe_comp_instruction_buffer_write_from_ddr(n_comp_instructions,
                                                                 &compute_instruction[0][0], i);
    }

    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = COMP_NOP_INSTRUCTION;
        tmp[1] = main_instruction[i];
        pe_array_unit->main_instruction_buffer_write_from_ddr(i, tmp);
        for (int j = 0; j < pe_group_size; j++) {
            pe_array_unit->pe_instruction_buffer_write_from_ddr(i, pe_instruction[j][i], j);
        }
    }

    printf("Instructions loaded. Running simulation...\n");
    fflush(stdout);

    // Run simulation
    int cycle_limit = 1000000;
    int simd = 0;
    int setting = PE_4_SETTING;
    int main_instruction_setting = MAIN_INSTRUCTION_2;

    pe_array_unit->run(cycle_limit, simd, setting, main_instruction_setting);

    printf("bankThrasher simulation completed.\n");

    delete pe_array_unit;
}
