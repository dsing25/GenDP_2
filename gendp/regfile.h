#include "sys_def.h"

class regfile {

    public:

        regfile();
        ~regfile();

        void reset();

        void write(int* write_addr, int* write_data, int n);
        void read(int* read_addr, int* read_data);
        void show_data(int addr, const char** reg_names = nullptr);
        
        int *write_addr, *write_data;
        
        int *read_addr, *read_data;
        
        //TODO move back to private after debug
        int *register_file;
    private:


};
