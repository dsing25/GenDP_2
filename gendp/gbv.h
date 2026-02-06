#ifndef GBV_H
#define GBV_H

#include <stdio.h>
#include <string>
#include "pe_array.h"

// GBV kernel configuration
#define GBV_COMPUTE_INSTRUCTION_NUM 90
#define GBV_PE_GROUP_SIZE 4
#define GBV_MAX_CYCLES 1600

/*
 * Alignment Input for GBV kernel
 * - query: 32-bit integer (can represent 16 2-bit basepairs, or 4 8-bit chars, etc.)
 * - ref_basepair: 2-bit value (0-3, e.g. for A/C/G/T)
 */

typedef struct {
  uint8_t ref_basepair;     // 2-bit basepair (use only 2 bits)
  uint32_t eq_vector[4];    // Equality vector (4 elements, adjust size if needed)
  int hinN;                 // hinN value
  int hinP;                 // hinP value
} gbv_align_input_t;

// High-level simulation function for GBV kernel
void gbv_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, int simulation_cases);

// Low-level simulation function for GBV kernel
int gbv_simulate(pe_array *pe_array_unit, gbv_align_input_t* align_input, int n, FILE* fp, int show_output);

#endif // GBV_H