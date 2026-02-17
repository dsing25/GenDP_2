#ifndef GBV_H
#define GBV_H

#include <stdio.h>
#include <string>
#include "pe_array.h"

// GBV kernel configuration
#define GBV_COMPUTE_INSTRUCTION_NUM 110
#define GBV_PE_GROUP_SIZE 4
#define GBV_MAX_CYCLES 100

// GBV register names for debugging
static const char* GBV_REG_NAMES[] = {
    "",                 // 0
    "Eq",              // 1
    "Vn",              // 2
    "Vp",              // 3
    "hinN",            // 4
    "hinP",            // 5
    "Xh",              // 6
    "Xv",              // 7
    "Ph",              // 8
    "Mh",              // 9
    "scoreBefore",     // 10
    "scoreEnd",        // 11
    "child_vn",        // 12
    "child_vp",        // 13
    "child_sbefore",   // 14
    "child_send",      // 15
    "merged_vn",       // 16
    "merged_vp",       // 17
    "merged_sbef",     // 18
    "merged_send",     // 19
    "temp1",           // 20
    "temp2",           // 21
    "temp3",           // 22
    "temp4",           // 23
    "temp5",           // 24
    "temp6",           // 25
    "temp7",           // 26
    "temp8",           // 27
    "temp9",           // 28
    "temp10",          // 29
    "temp11",          // 30
    "temp12"           // 31
};

/*
 * Alignment Input for GBV kernel
 * - query: 32-bit integer (can represent 16 2-bit basepairs, or 4 8-bit chars, etc.)
 * - ref_basepair: 2-bit value (0-3, e.g. for A/C/G/T)
 */

typedef struct {
  // Left bitvector slice
  uint32_t left_VN;         // Left VN vector
  uint32_t left_VP;         // Left VP vector
  int left_scoreEnd;        // Left score end

  // Right bitvector slice
  uint32_t right_VN;        // Right VN vector
  uint32_t right_VP;        // Right VP vector
  int right_scoreEnd;       // Right score end
} gbv_align_input_t;

// High-level simulation function for GBV kernel
void gbv_simulation(char *inputFileName, char *outputFileName, FILE *fp, int show_output, int simulation_cases);

// Low-level simulation function for GBV kernel
int gbv_simulate(pe_array *pe_array_unit, gbv_align_input_t* align_input, int n, FILE* fp, int show_output);

#endif // GBV_H