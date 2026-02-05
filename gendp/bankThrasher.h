#ifndef BANKTHRASHER_H
#define BANKTHRASHER_H

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#define BANKTHRASHER_COMPUTE_INSTRUCTION_NUM 8
#define BANKTHRASHER_PE_GROUP_SIZE 4

void bankThrasher_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, int simulation_cases);

#endif
