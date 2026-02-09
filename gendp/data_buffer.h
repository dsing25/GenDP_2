#ifndef DATA_BUFFER_H
#define DATA_BUFFER_H
#include "sys_def.h"
#include "simulator.h"
#include <deque>

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
    int write_slot = 0;  // for single_data writes: which slot
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
        void access(int addr, int peid, SpmAccessT accessT, bool single_data, LoadResult data=LoadResult(), bool isVirtualAddr=true, int write_slot=0);
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

// --- Controller Load/Store Queue ---

struct LsqEntry {
    int addr;           // address in THIS memory
    int data[2];        // line data (2 ints)
    bool ready[2];      // which data elements are filled
    bool isRead;        // true = read from this memory
    int srcDstAddr;     // address in OTHER memory
    bool singleData;    // true = single word, false = double
};

struct S2OutstandingReq {
    int addr;
    int cyclesLeft;
    bool singleData;
};

struct S2OutstandingWriteReq {
    int addr;
    int data[2];
    int cyclesLeft;
    bool singleData;
};

class CtrlLSQ {
public:
    CtrlLSQ();

    void enqueueS2ToSpm(int s2Addr, int spmPhysAddr,
                        bool singleData, S2* s2);
    void enqueueSpmToS2(int spmPhysAddr, int s2Addr,
                        bool singleData);

    // S2 read/write pipelines
    void tickS2Outstanding(S2* s2);
    void tickS2OutstandingWrites(S2* s2);
    void drainS2Reads(S2* s2);
    void drainSpmReads(SPM* spm,
                       bool spmBankBusy[SPM_NUM_BANKS]);
    void drainSpmWrites(SPM* spm,
                        bool spmBankBusy[SPM_NUM_BANKS]);
    void drainS2Writes(S2* s2);

    bool empty() const;
    bool spmBankFull(int physAddr) const;
    bool s2BankFull(int addr) const;
    // Check if n entries can be enqueued without overflow
    bool canEnqueueS2ToSpm(
        int* spmAddrs, int n) const;
    bool canEnqueueSpmToS2(
        int* spmAddrs, int* s2Addrs, int n) const;

    static int s2Bank(int addr) {
        return (addr >> 1) % S2_NUM_BANKS;
    }
    static int spmBank(int physAddr) {
        int bg = physAddr / SPM_BANK_GROUP_SIZE;
        int big = (physAddr >> 1) & 1;
        return bg * 2 + big;
    }

    std::deque<LsqEntry> spmBanks[SPM_NUM_BANKS];
    std::deque<LsqEntry> s2Banks[S2_NUM_BANKS];
    std::deque<S2OutstandingReq> s2Outstanding[S2_NUM_BANKS];
    std::deque<S2OutstandingWriteReq>
        s2OutstandingWrites[S2_NUM_BANKS];

private:
    int drainPrioritySpm = 0;
    int drainPriorityS2 = 0;
};

#endif // DATA_BUFFER_H
