#ifndef PE_ARRAY_H
#define PE_ARRAY_H
#include "pe.h"
#include <set>
#include <cstdint>
#include "simulator.h"
#include "FIFO.h"
#include <list>

typedef struct thread_data {
    int master;
    unsigned long instruction;
    int* PC;
    bool halt;
} thread_data;

class pe_array {

    public:

        pe_array(int input_size, int output_size,
                 int pc_mode = PC_MODE_SHARED);
        ~pe_array();

        int pc_mode;        // PC_MODE_SHARED or PC_MODE_DUAL (forwarded to PEs)
        int main_addressing_register[MAIN_ADDR_REGISTER_NUM];
        // WAW tracking for main gr (one slot per idx). cycle == -1 means
        // never written (or was reset between cases). halves bit0=lo,
        // bit1=hi; CTRL_GR sets both.
        int main_gr_last_cycle[MAIN_ADDR_REGISTER_NUM];
        unsigned char main_gr_halves[MAIN_ADDR_REGISTER_NUM];
        const char* main_gr_origin[MAIN_ADDR_REGISTER_NUM];

        // Single chokepoint for main_addressing_register writes that
        // detects WAW: two writes to overlapping bit-ranges of the same
        // gr in one simulation cycle. Disjoint half writes (lo + hi) are
        // permitted. Setup writes (cycle == 0) are exempt.
        void set_main_gr(int idx, int val, int pos, const char* origin);
        unsigned long main_instruction_buffer[CTRL_INSTR_BUFFER_NUM][CTRL_INSTR_BUFFER_GROUP_SIZE];
        unsigned long compute_instruction_buffer[COMP_INSTR_BUFFER_GROUP_NUM][COMP_INSTR_BUFFER_GROUP_SIZE];
        
        int main_PC;
        int ras = 0;
        int input_buffer_size, output_buffer_size;
        uint64_t va_regfile[16];
        int s1c[S1C_SIZE];     // Controller scratchpad
        int *mm;               // Main memory (4GB block) - raw pointer used
                               // by direct C++ access in magic instructions
        MM *mm_unit;           // Latency-modeled wrapper for ISA-level MM
                               // dispatch; setBuffer'd to the same pointer
                               // as `mm` once gwfa_get_mm() runs.

        void run(int cycle_limit, int simd, int setting, int main_instruction_setting);
        void fin0_load_batch(int fin0_base, int magic_mask);
        void show_gr();
        void show_compute_instruction_buffer();
        void poa_show_output_buffer(int len_y, int len_x, FILE* fp);
        void bsw_show_output_buffer(FILE* fp);
        void chain_show_output_buffer(int n, FILE* fp);
        void phmm_show_output_buffer(FILE* fp);

        void input_buffer_write_from_ddr(int addr, int* data);
        void input_buffer_write_from_ddr_unsigned(int addr, unsigned int* data);
        void compute_instruction_buffer_write_from_ddr(int addr, unsigned long data[]);
        void main_instruction_buffer_write_from_ddr(int addr, unsigned long data[]);
        void pe_instruction_buffer_write_from_ddr(int addr, unsigned long data[], int id);
        void pe_comp_instruction_buffer_write_from_ddr(int addr, unsigned long data[], int id);

        void buffer_reset(int* buffer, int num);
        void reset_shared_spm();
        void reset_controller_state();
        void write_spm_magic(int addr, int value);

        void write_s2(int addr, int value);

        int decode(unsigned long instruction, int* PC, int simd, int setting, int main_instruction_setting);
        int decode_output(unsigned long instruction, int* PC, int simd, int setting, int main_instruction_setting);
        bool willStallPair(unsigned long slot0,
                           unsigned long slot1);

        LoadResult load(int source_pos, int reg_immBar_flag, int rs1, int rs2, int simd);
        void store(int dest_pos, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd);
        unsigned long PE_instruction[2];
        int load_data, store_data, from_fifo;

        int *input_buffer, *output_buffer;
        FIFO fifo_unit[FIFO_GROUP_NUM][FIFO_GROUP_SIZE];
        pe *pe_unit[PE_NUM];

    private:
        //helper
        int* get_output_dest(int dest, int rd);
        void set_output_dest(int dest, int rd, int val);
        int read_gr_src(int src, int idx);
        void process_events();
        void handle_spm_data_ready(SpmDataReadyData* evData);

        std::set<EventProducer*> active_event_producers;

        SPM * SPM_unit;
        S2 * s2;
        CtrlLSQ * lsq;

};

#endif // PE_ARRAY_H
