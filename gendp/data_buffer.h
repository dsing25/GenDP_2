#ifndef DATA_BUFFER_H
#define DATA_BUFFER_H
#include "sys_def.h"
#include "simulator.h"
#include <cassert>
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

        // Subregister read. pos: CTRL_GR=full,
        // CTRL_GR_LO=lo16, CTRL_GR_HI=hi16
        int at(int idx, int pos = CTRL_GR) const {
            assert(idx >= 0 && idx < buffer_size);
            if (pos == CTRL_GR) return buffer[idx];
            if (pos == CTRL_GR_LO)
                return (int32_t)(int16_t)(
                    buffer[idx] & 0xFFFF);
            if (pos == CTRL_GR_HI)
                return (int32_t)(int16_t)(
                    (uint32_t)buffer[idx] >> 16);
            fprintf(stderr,
                "addr_regfile::at invalid pos %d\n", pos);
            exit(-1);
        }

        // Subregister write. pos: CTRL_GR=full,
        // CTRL_GR_LO=lo16, CTRL_GR_HI=hi16. Detects WAW: two writes to
        // overlapping bit-ranges of the same gr in one global simulation
        // cycle is a hardware-illegal hazard. Disjoint half-writes
        // (gr_lo + gr_hi to the same idx) are permitted because the two
        // halves are independently addressable. Setup writes (cycle == 0)
        // are exempt for per-PE init.
        void st(int idx, int val, int pos = CTRL_GR,
                const char* owner_tag = "anon") {
            assert(idx >= 0 && idx < buffer_size);
            extern int cycle;
            if (cycle > 0) {
                int mask = (pos == CTRL_GR_LO) ? 0x1
                         : (pos == CTRL_GR_HI) ? 0x2 : 0x3;
                if (last_write_cycle[idx] != cycle)
                    halves_written[idx] = 0;
                if (halves_written[idx] & mask) {
                    fprintf(stderr,
                        "%s WAW: gr[%d] written twice in cycle %d"
                        " (prev: %s, pos overlap)\n",
                        owner_tag, idx, cycle,
                        last_write_origin[idx]
                            ? last_write_origin[idx] : "?");
                    exit(-1);
                }
                halves_written[idx] |= mask;
                last_write_cycle[idx] = cycle;
                last_write_origin[idx] = owner_tag;
            }
            if (pos == CTRL_GR) {
                buffer[idx] = val; return;
            }
            if (pos == CTRL_GR_LO) {
                uint16_t v = (uint16_t)(int16_t)val;
                buffer[idx] = (buffer[idx] & (int)0xFFFF0000)
                    | v;
                return;
            }
            if (pos == CTRL_GR_HI) {
                uint16_t v = (uint16_t)(int16_t)val;
                buffer[idx] = (buffer[idx] & 0xFFFF)
                    | ((uint32_t)v << 16);
                return;
            }
            fprintf(stderr,
                "addr_regfile::st invalid pos %d\n", pos);
            exit(-1);
        }

        // Untracked write — for delayed-effect writes whose originating
        // instruction is from an earlier cycle (SPM load completion).
        void st_delayed(int idx, int val, int pos = CTRL_GR) {
            assert(idx >= 0 && idx < buffer_size);
            if (pos == CTRL_GR) {
                buffer[idx] = val; return;
            }
            if (pos == CTRL_GR_LO) {
                uint16_t v = (uint16_t)(int16_t)val;
                buffer[idx] = (buffer[idx] & (int)0xFFFF0000) | v;
                return;
            }
            if (pos == CTRL_GR_HI) {
                uint16_t v = (uint16_t)(int16_t)val;
                buffer[idx] = (buffer[idx] & 0xFFFF)
                    | ((uint32_t)v << 16);
                return;
            }
            fprintf(stderr,
                "addr_regfile::st_delayed invalid pos %d\n", pos);
            exit(-1);
        }

        int *buffer;
        int buffer_size;
        int *last_write_cycle;          // per-idx WAW tracker
        unsigned char *halves_written;  // bit0=lo, bit1=hi written this cyc
        const char **last_write_origin;  // last writer for diagnostics

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

        // 2-stage pipeline per bank: up to SPM_ACCESS_LATENCY in-flight
        // requests per bank, so a new request can be issued each cycle
        // without waiting for the prior one to finish. Full-pipeline means
        // all slots occupied.
        OutstandingRequest* requests[SPM_NUM_BANKS][SPM_ACCESS_LATENCY];
        int cycles_left[SPM_NUM_BANKS][SPM_ACCESS_LATENCY];

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
    void reset();

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
