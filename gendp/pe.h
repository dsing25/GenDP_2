#include "data_buffer.h"
#include "comp_decoder.h"
#include "regfile.h"
#include "compute_unit_32.h"
#include "crossbar.h"
#include "simulator.h"

class pe {

    public:
        struct OutstandingReq{
            int dst;
            int addr;       // destination addr (reg/gr)
            int spm_addr;   // original SPM access addr
            bool single_load;
            bool valid;
            int bp_shift;        // shift for 2-bit extract
            bool two_bit_extract; // apply shift+mask
            OutstandingReq()
                : dst(-42), addr(-42), spm_addr(0),
                  single_load(false), valid(false),
                  bp_shift(0), two_bit_extract(false) {}
            void clear() {
                dst = -42;
                addr = -42;
                spm_addr = 0;
                single_load = false;
                valid = false;
                bp_shift = 0;
                two_bit_extract = false;
            }
        };

        pe(int id, SPM* spm);
        ~pe();

        int id;
        int PC[2], comp_PC;
        int src_dest[2][2];

        void run(int simd);

        int decode(unsigned long instruction, int* PC, int src_dest[], int* op, int simd, int* ctrl_write_addr, int* ctrl_write_datum);
        LoadResult load(int pos, int reg_immBar_flag, int rs1, int rs2, int simd, bool single_data=true, bool swizzle=false);
        void store(int pos, int src, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd, int* ctrl_write_addr, int* ctrl_write_datum, bool single_datak=true, bool swizzle=false);
        void ctrl_instr_load_from_ddr(int addr, unsigned long data[]);
        void comp_instr_load_from_ddr(int n_instr, unsigned long data[]);
        int get_gr_10();
        void reset();

        void recieve_spm_data(int data[LINE_SIZE]);

        void show_comp_reg();

        // SPM request port - populated by PE, consumed by pe_array arbitration
        OutstandingRequest* spmReqPort = nullptr;

        bool stalled() const { return spmReqPort != nullptr; }

        // ld/st data
        int load_data, store_data;
        unsigned long store_instruction[COMP_INSTR_BUFFER_GROUP_SIZE], load_instruction[COMP_INSTR_BUFFER_GROUP_SIZE];

        // public for magic instruction initialization
        addr_regfile *addr_regfile_unit = new addr_regfile(ADDR_REGISTER_NUM);

    private:
        //helper
        int* get_output_dest(int dest, int rd);

        unsigned long instruction[2];
        // ld/st control signal
        int comp_reg_load, comp_reg_store, addr_reg_load, addr_reg_store, SPM_load, SPM_store;
        int comp_instr_load, comp_instr_store;
        // ld/st addr
        int comp_reg_load_addr, comp_reg_store_addr, addr_reg_load_addr, addr_reg_store_addr, SPM_load_addr, SPM_store_addr;
        int comp_instr_load_addr, comp_instr_store_addr;
        
        // TODO: Put conponents below to private later
        comp_instr_buffer *comp_instr_buffer_unit = new comp_instr_buffer(COMP_INSTR_BUFFER_GROUP_NUM);
        ctrl_instr_buffer *ctrl_instr_buffer_unit = new ctrl_instr_buffer(CTRL_INSTR_BUFFER_NUM);
        SPM *SPM_unit;
        //write buffer to send to addr_regfile
        int ctrl_write_addrs[CTRL_REGFILE_WRITE_PORTS];
        int ctrl_write_data[CTRL_REGFILE_WRITE_PORTS];
        comp_decoder comp_decoder_unit;
        regfile *regfile_unit = new regfile();
        compute_unit_32 cu_32;
        crossbar crossbar_unit;

        //-1 means there is no outstanding request
        OutstandingReq outstanding_req;

        // Set by load() when reading SPM, consumed by store()
        int last_spm_load_addr = 0;



};
