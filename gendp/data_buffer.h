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

        // Magic-body scope: while set, WAW tracking is suspended. Magic
        // bodies model multi-ISA-cycle hardware behavior in a single C++
        // pass; their internal writes do not represent real same-cycle
        // VLIW writes and therefore should not trip the WAW detector.
        // Toggled by pe::decode_ctrl and pe_array::decode at the magic
        // dispatch boundary.
        bool waw_suppressed = false;

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
            if (cycle > 0 && !waw_suppressed) {
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

// SPM reads issued by the controller can target three different sinks once
// their data lands. S2 is the legacy SPM<->S2 path; MM and S1C were added
// for the GWFA feature set.
enum class SpmReadDest { S2, MM, S1C };

struct LsqEntry {
    int addr;              // addr in THIS memory
    int data[2];           // line data
    bool ready[2];         // per-slot readiness
    AccessT accessType; // READ or WRITE
    int srcDstAddr;        // addr in OTHER memory
    bool singleData;
    // For SPM-side READ entries only: where does the data go after the SPM
    // read completes? S2 (default) preserves the legacy SPM<->S2 path.
    SpmReadDest dest = SpmReadDest::S2;
    int destAddr = 0;      // MM/S1C addr when dest != S2
    int destNumWords = 2;  // 1 or 2 (drives MM store width; only used for MM)
};

class MM;  // forward decl for hasPendingOps signature

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

    // s1c <-> SPM mvd paths. s1c reads/writes are immediate; only the SPM
    // side is queued. enqueueS1cToSpm reads s1c synchronously and stages a
    // ready-data SPM write. enqueueSpmToS1c stages a tagged SPM read whose
    // completion writes directly into s1c[].
    void enqueueS1cToSpm(int spmPhysAddr,
        const int* s1cData, bool singleData);
    void enqueueSpmToS1c(int spmPhysAddr,
        int s1cAddr, bool singleData);

    // SPM <-> MM paths. MM stores are immediate (the buffer is updated and a
    // counter is bumped); only the SPM side is queued. SPM->MM stages a
    // tagged SPM read whose completion calls mm->issueStore(). MM->SPM is
    // driven from MM::tick() (after MM_LATENCY) which calls
    // enqueueSpmWriteWithData on the resulting line.
    void enqueueSpmReadForMm(int spmPhysAddr,
        int mmAddr, bool singleData);
    void enqueueSpmWriteWithData(int spmPhysAddr,
        const int* lineData, bool singleData);

    // Single tick drains both SPM and S2 queues
    void tick(SPM* spm, S2* s2,
              bool spmBankBusy[SPM_NUM_BANKS]);

    // Callbacks when memory completes. dataReadyFromSpm dispatches by the
    // recorded SpmReadDest tag: S2 (existing scan), MM (synchronous
    // mm->issueStore), or S1C (synchronous write into the s1c[] array).
    void dataReadyFromS2(int s2Addr, int* lineData);
    void dataReadyFromSpm(int bank, int* lineData,
        MM* mm, int* s1c);

    // Status
    bool empty() const;
    bool hasPendingOps(SPM* spm, S2* s2,
        const MM* mm) const;
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
    // Pending controller SPM reads awaiting completion. dest/destAddr
    // mirror the originating LsqEntry so dataReadyFromSpm knows where to
    // route the loaded line (S2 scan, MM store, or s1c write).
    struct PendingCtrlRead {
        bool valid = false;
        int spmPhysAddr;
        int s2Addr;          // legacy: kept for S2-destined reads
        bool singleData;
        SpmReadDest dest = SpmReadDest::S2;
        int destAddr = 0;
        int destNumWords = 2;
    };
    PendingCtrlRead
        pendingCtrlReads[SPM_NUM_BANKS];

    void drainSpm(SPM* spm,
                  bool spmBankBusy[SPM_NUM_BANKS]);
    void drainS2(S2* s2);

    int drainPrioritySpm = 0;
    int drainPriorityS2 = 0;
};

// --- MM (4GB main memory) ---
//
// MM is a large external buffer (allocated by the GWFA library and handed in
// via setBuffer). The simulator wraps it for two reasons:
//   * Stores: bump lastMMStore = MM_LATENCY; barrier blocks until counter
//     ticks below 0. The store data hits the buffer immediately, so the
//     counter is only there to model flush completion for waitLsq.
//   * Loads: enqueue an MMLoadEntry with cyclesLeft = MM_LATENCY. When it
//     expires, route the data: gr -> direct write; SPM -> stage SPM writes
//     via the LSQ (one per line).
struct MMLoadEntry {
    int addr;
    int destId;              // CTRL_GR or CTRL_SPM
    int destAddr;            // gr index, or SPM phys addr
    int data[8];             // up to 8 words (mvdq)
    int numWords;            // 1, 2, or 8
    int cyclesLeft;
    bool singleData;         // for 1-word destined to gr/SPM
};

// Deferred MM store entry. Controller-side `mv gr -> MM` (and the LSQ
// completion path for `mvd SPM -> MM`) call `issueStore` during slot
// decode; the actual buffer write is deferred to end-of-cycle so paired
// VLIW slots both observe pre-cycle MM contents.
struct MMStoreEntry {
    int addr;
    int data[8];   // up to 8 words (matches mvdq line size)
    int numWords;
};

class MM {
public:
    MM();

    void setBuffer(int* buf);
    int* getBuffer() const { return buffer; }

    void issueStore(int addr, const int* data,
                    int numWords);
    void issueLoad(int addr, int destId,
                   int destAddr, int numWords,
                   bool singleData);

    // Advance one cycle. lsq routes SPM-bound completions; gr is the
    // controller's main_addressing_register array for direct writes.
    void tick(CtrlLSQ* lsq, int* gr);

    // Apply queued MM stores to buffer[]. Called at end-of-cycle from
    // pe_array::run after both slot decodes and LSQ tick complete, so
    // a paired-slot pair that issues a store in slot 1 and a load in
    // slot 0 both see the pre-cycle buffer contents.
    void commitPendingStores();

    bool hasPendingOps() const;
    bool loadQueueFull() const;
    // Returns true if the load queue can accept `n` more loads
    // (used by willStallPair to prevent partial-pair commits when
    // the second-decoded slot would overflow MM_LATENCY).
    bool loadQueueCanFit(int n) const;

private:
    int* buffer = nullptr;
    int lastMMStore = -1;
    std::deque<MMLoadEntry> loadQueue;
    std::vector<MMStoreEntry> pendingStores;
};

#endif // DATA_BUFFER_H
