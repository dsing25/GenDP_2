#ifndef DATA_BUFFER_H
#define DATA_BUFFER_H
#include "sys_def.h"
#include "simulator.h"

enum class SpmAccessT {
    READ,
    WRITE
};

struct OutstandingRequest {
    int addr;
    int peid;
    SpmAccessT access_t;
    bool single_data;
    LoadResult data;
    bool isVirtualAddr = true;
};

class S2 {

    public:

        explicit S2(int size_elements);
        ~S2();

        void reset();

        int *buffer;
        int buffer_size;

};

// template <class T>
// class data_buffer {

//     public:

//         data_buffer(int size);
//         ~data_buffer();

//         void reset();

//         void write(int write_addr, T write_data);
//         void read(int read_addr, T read_data);
//         void show_data(int addr);

//         int write_addr, read_addr;
//         T write_data, read_data;

//         T *buffer;
//         int buffer_size;

// };

class addr_regfile {

    public:

        addr_regfile(int size);
        ~addr_regfile();

        void reset();

        void show_data(int addr);

        void write(int* write_addr, int* write_data, int n);

        int *buffer;
        int buffer_size;

};

class SPM : EventProducer{
    private:
        void mark_active_producer();

    public:

        SPM(int size, std::set<EventProducer*>* active_producers);
        ~SPM();

        void reset();

        void show_data(int addr);
        void show_data(int start_addr, int end_addr, int line_width=64);
        void access(int addr, int peid, SpmAccessT accessT, bool single_data, LoadResult data=LoadResult(), bool isVirtualAddr=true);
        int& access_magic(int peid, int addr) { return buffer[peid * SPM_BANK_GROUP_SIZE + addr]; }
        std::pair<bool, std::list<Event>*> tick() override;

        int getBank(int addr, int peid, bool isVirtualAddr);
        bool portIsBusy(int addr, int peid, bool isVirtualAddr);

        int *buffer;
        int buffer_size;

        OutstandingRequest* requests[SPM_NUM_BANKS];  // 8 banks now
        int cycles_left[SPM_NUM_BANKS];  // Tracks latency countdown for each bank

        PushableProducerSet active_producers;

};

class SpmDataReadyData {
    public:
        SpmDataReadyData(int reqId, int* data);
        int requestorId;
        int data[SPM_BANDWIDTH];
};


class ctrl_instr_buffer {

    public:

        ctrl_instr_buffer(int size);
        ~ctrl_instr_buffer();

        void show_data(int addr);

        unsigned long **buffer;
        int buffer_size;

};

class comp_instr_buffer {

    public:

        comp_instr_buffer(int size);
        ~comp_instr_buffer();

        void show_data(int addr);

        unsigned long** buffer;
        int buffer_size;

};

#endif // DATA_BUFFER_H
