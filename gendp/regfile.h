#include "sys_def.h"

class regfile {

    public:

        regfile();
        ~regfile();

        void reset();

        void write(int* write_addr, int* write_data, int n);
        void read(int* read_addr, int* read_data);
        void show_data(int addr);

        // Single-register write with WAW detection. Use this for ISA-level
        // writes (compute outputs, mv/li to reg, set_8 broadcast) so the
        // tracker catches same-cycle duplicates.
        void set(int idx, int val, const char* origin);

        // Untracked write — use only for delayed-effect writes whose
        // originating instruction is from an earlier cycle (e.g. SPM load
        // completion arriving SPM_ACCESS_LATENCY cycles after the load
        // was issued). These should not contend with this-cycle ISA writes
        // for WAW purposes.
        void set_delayed(int idx, int val);

        int *write_addr, *write_data;

        int *read_addr, *read_data;

        //TODO move back to private after debug
        int *register_file;
        int *last_write_cycle;
        const char **last_write_origin;
    private:


};
