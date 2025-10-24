#ifndef WFA_H
#define WFA_H

#include <stdio.h>
#include <string>
#include "pe_array.h"

//TODO update this
//compute instructions is num / 2. 2 lines is one vliw instr
#define WFA_COMPUTE_INSTRUCTION_NUM 16
#define WFA_PE_GROUP_SIZE 4
#define MAX_CYCLES 100000

/*
 * Alignment Input
 */
typedef struct {
  // Pattern
  char* pattern;
  int pattern_length;
  // Text
  char* text;
  int text_length;
} align_input_t;

void wfa_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, 
		    int simulation_cases);
int wfa_simulate(pe_array *pe_array_unit, align_input_t* align_input, int n, FILE* fp, 
                 int show_output);

#endif // WFA_H
