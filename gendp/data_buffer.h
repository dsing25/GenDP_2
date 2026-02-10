#ifndef DATA_BUFFER_H
#define DATA_BUFFER_H
#include "sys_def.h"
#include "simulator.h"
#include <deque>
#include <vector>

enum class SpmAccessT {
    READ,
    WRITE
};

enum class AccessT { READ, WRITE };

struct OutstandingRequest {
    int addr;
    int peid;
    SpmAccessT access_t;
    bool single_data;
    LoadResult data;
    bool isVirtualAddr = true;
};

// S2 outstanding request (shared by reads and writes)
struct S2PipelineEntry {
    bool valid = false;
    AccessT accessType;
    int addr;       // S2 address
    int dstAddr;    // opaque metadata (SPM phys addr)
    int data[2];    // for writes: data to commit
    int cyclesLeft;
    bool singleData;
};

class S2 {

    public:

        explicit S2(int size_elements);
        ~S2();

        void reset();

        int *buffer;
        int buffer_size;

        // Per-bank pipeline slots
        S2PipelineEntry
            outstanding[S2_NUM_BANKS][S2_READ_LATENCY];

        void issueRead(int addr, int dstAddr,
                       bool singleData);
        void issueWrite(int addr, int* data,
                        bool singleData);

        struct ReadCompletion {
            int dstAddr;   // opaque (SPM phys addr)
            int s2Addr;    // original S2 address
            int data[2];   // full line data
        };

        // Tick: advance pipelines. Returns completed
        // reads. Writes auto-commit to buffer.
        std::vector<ReadCompletion> tick();

        bool hasPendingOps() const;
        static int s2Bank(int addr) {
            return (addr >> 1) % S2_NUM_BANKS;
        }
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
        void access(int addr, int peid, SpmAccessT accessT,
                    bool single_data,
                    LoadResult data=LoadResult(),
                    bool isVirtualAddr=true);
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
        SpmDataReadyData(int reqId, int* data,
                         int physAddr);
        int requestorId;
        int data[LINE_SIZE];
        int phys_addr;
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
    int addr;              // addr in THIS memory
    int data[2];           // line data
    bool ready[2];         // per-slot readiness
    AccessT accessType; // READ or WRITE
    int srcDstAddr;        // addr in OTHER memory
    bool singleData;
};

class CtrlLSQ {
public:
    CtrlLSQ();

    // Enqueue paired transfers (S2 read + SPM write,
    // or SPM read + S2 write)
    void enqueueS2ToSpm(int s2Addr, int spmPhysAddr,
                        bool singleData);
    void enqueueSpmToS2(int spmPhysAddr, int s2Addr,
                        bool singleData);

    // Standalone enqueue (for misaligned MVDQ)
    void enqueueS2ReadOnly(int s2Addr);
    void enqueueSpmWriteOnly(int spmPhysAddr,
        int s2SrcAddr, bool singleData);
    void enqueueSpmReadOnly(int spmPhysAddr);
    void enqueueS2WriteOnly(int s2Addr,
        int spmSrcAddr, bool singleData);

    // Single tick drains both SPM and S2 queues
    void tick(SPM* spm, S2* s2,
              bool spmBankBusy[SPM_NUM_BANKS]);

    // Callbacks when memory completes
    void dataReadyFromS2(int s2Addr, int* lineData);
    void dataReadyFromSpm(int bank, int* lineData);

    // Status
    bool empty() const;
    bool hasPendingOps(SPM* spm, S2* s2) const;
    bool spmBankFull(int physAddr) const;
    bool s2BankFull(int addr) const;
    bool canEnqueue(int* spmAddrs, int nSpm,
                    int* s2Addrs, int nS2) const;

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

private:
    // Pending controller SPM reads awaiting completion
    struct PendingCtrlRead {
        bool valid = false;
        int spmPhysAddr;
        int s2Addr;
        bool singleData;
    };
    PendingCtrlRead
        pendingCtrlReads[SPM_NUM_BANKS];

    void drainSpm(SPM* spm,
                  bool spmBankBusy[SPM_NUM_BANKS]);
    void drainS2(S2* s2);

    int drainPrioritySpm = 0;
    int drainPriorityS2 = 0;
};

#endif // DATA_BUFFER_H
