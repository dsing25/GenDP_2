#ifndef UTILS_H
#define UTILS_H
#include <string>
#include "pe_array.h"

int load_instructions(std::string kernel_name, size_t n_comp_instructions, size_t pe_group_size, 
                       pe_array *pe_array_unit);

#endif // UTILS_H
