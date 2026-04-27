#include <stdio.h>
#include <stdlib.h>
#include "regfile.h"

extern int cycle;

regfile::regfile() {

    register_file = (int*)malloc(REGFILE_ADDR_NUM * sizeof(int));
    write_addr = (int*)calloc(REGFILE_WRITE_PORTS, sizeof(int));
    write_data = (int*)calloc(REGFILE_WRITE_PORTS, sizeof(int));
    read_addr = (int*)calloc(REGFILE_READ_PORTS, sizeof(int));
    read_data = (int*)calloc(REGFILE_READ_PORTS, sizeof(int));
    last_write_cycle = (int*)malloc(REGFILE_ADDR_NUM * sizeof(int));
    last_write_origin =
        (const char**)malloc(REGFILE_ADDR_NUM * sizeof(const char*));

    reset();

}

regfile::~regfile() {
    free(register_file);
    free(write_addr);
    free(write_data);
    free(read_addr);
    free(read_data);
    free(last_write_cycle);
    free(last_write_origin);
}

void regfile::reset() {

    int i;

    for (i = 0; i < REGFILE_ADDR_NUM; i++) {
        register_file[i] = 0;
        last_write_cycle[i] = -1;
        last_write_origin[i] = nullptr;
    }

}

void regfile::set(int idx, int val, const char* origin) {
    if (idx < 0 || idx >= REGFILE_ADDR_NUM) {
        fprintf(stderr, "regfile::set addr %d out of bound\n", idx);
        exit(-1);
    }
    if (cycle > 0) {
        if (last_write_cycle[idx] == cycle) {
            fprintf(stderr,
                "regfile WAW: reg[%d] written twice in cycle %d"
                " (prev: %s, now: %s)\n",
                idx, cycle,
                last_write_origin[idx] ? last_write_origin[idx] : "?",
                origin);
            exit(-1);
        }
        last_write_cycle[idx] = cycle;
        last_write_origin[idx] = origin;
    }
    register_file[idx] = val;
}

void regfile::set_delayed(int idx, int val) {
    if (idx < 0 || idx >= REGFILE_ADDR_NUM) {
        fprintf(stderr, "regfile::set_delayed addr %d out of bound\n", idx);
        exit(-1);
    }
    register_file[idx] = val;
}

void regfile::write(int* write_addr, int* write_data, int n) {
    if (write_addr[n] >= 0 && write_addr[n] < REGFILE_ADDR_NUM) {
        set(write_addr[n], write_data[n], "regfile_write");
    }
}

void regfile::read(int* read_addr, int* read_data) {

    int i;

    for (i = 0; i < REGFILE_READ_PORTS; i++)
        if (read_addr[i] >= 0 && read_addr[i] < REGFILE_ADDR_NUM) {
            // if (read_addr[i] == write_addr[0]) read_data[i] = write_data[0];
            // else if (read_addr[i] == write_addr[1]) read_data[i] = write_data[1];
            // else if (read_addr[i] == write_addr[2]) read_data[i] = write_data[2];
            // else 
            read_data[i] = register_file[read_addr[i]];
        } else fprintf(stderr, "regfile addr %d out of bound.\n", read_addr[i]);

}

void regfile::show_data(int addr) {

    if (addr >= 0 && addr < REGFILE_ADDR_NUM)
        printf("regfile[%d] = %d\n", addr, register_file[addr]);
    else fprintf(stderr, "regfile show data addr error.\n");

}