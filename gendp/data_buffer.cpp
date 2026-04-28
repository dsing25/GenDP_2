#include "data_buffer.h"
#include <iomanip>
#include <cassert>

S2::S2(int size_elements) {
    buffer = new int[size_elements];
    buffer_size = size_elements;
    reset();
}

S2::~S2() {
    delete[] buffer;
}

void S2::reset() {
    for (int i = 0; i < buffer_size; i++)
        buffer[i] = -42;
    for (int b = 0; b < S2_NUM_BANKS; b++)
        for (int s = 0; s < S2_READ_LATENCY; s++)
            outstanding[b][s].valid = false;
}

void S2::issueRead(int addr, int dstAddr,
                   bool singleData) {
    int b = s2Bank(addr);
    for (int s = 0; s < S2_READ_LATENCY; s++) {
        if (!outstanding[b][s].valid) {
            S2PipelineEntry& e = outstanding[b][s];
            e.valid = true;
            e.accessType = AccessT::READ;
            e.addr = addr;
            e.dstAddr = dstAddr;
            e.singleData = singleData;
            e.cyclesLeft = S2_READ_LATENCY;
            return;
        }
    }
    assert(false && "S2::issueRead: bank full");
}

void S2::issueWrite(int addr, int* data,
                    bool singleData) {
    int b = s2Bank(addr);
    for (int s = 0; s < S2_READ_LATENCY; s++) {
        if (!outstanding[b][s].valid) {
            S2PipelineEntry& e = outstanding[b][s];
            e.valid = true;
            e.accessType = AccessT::WRITE;
            e.addr = addr;
            e.dstAddr = 0;
            e.data[0] = data[0];
            e.data[1] = data[1];
            e.singleData = singleData;
            e.cyclesLeft = S2_WRITE_LATENCY;
            return;
        }
    }
    assert(false && "S2::issueWrite: bank full");
}

std::vector<S2::ReadCompletion> S2::tick() {
    std::vector<ReadCompletion> completions;
    for (int b = 0; b < S2_NUM_BANKS; b++) {
        for (int s = 0; s < S2_READ_LATENCY; s++) {
            S2PipelineEntry& e = outstanding[b][s];
            if (!e.valid) continue;
            e.cyclesLeft--;
            if (e.cyclesLeft > 0) continue;

            if (e.accessType == AccessT::READ) {
                ReadCompletion c;
                c.dstAddr = e.dstAddr;
                c.s2Addr = e.addr;
                int base = lineAddr(e.addr);
                c.data[0] = buffer[base];
                c.data[1] = buffer[base + 1];
                completions.push_back(c);
            } else {
                // WRITE: commit to buffer
                if (e.singleData) {
                    int s2 = lineOffset(e.addr);
                    buffer[lineAddr(e.addr) + s2] =
                        e.data[s2];
                } else {
                    int base = lineAddr(e.addr);
                    buffer[base] = e.data[0];
                    buffer[base + 1] = e.data[1];
                }
            }
            e.valid = false;
        }
    }
    return completions;
}

bool S2::hasPendingOps() const {
    for (int b = 0; b < S2_NUM_BANKS; b++)
        for (int s = 0; s < S2_READ_LATENCY; s++)
            if (outstanding[b][s].valid)
                return true;
    return false;
}

// template <typename T>
// data_buffer<T>::data_buffer(int size) {

//     buffer = (T*)malloc(size * sizeof(T));
//     buffer_size = size;
//     reset();

// }

// template <typename T>
// data_buffer<T>::~data_buffer() {
//     free(buffer);
// }

// template <typename T>
// void data_buffer<T>::reset() {

//     int i;

//     for (i = 0; i < buffer_size; i++)
//         buffer[i] = 0;
// }

// template <typename T>
// void data_buffer<T>::write(int write_addr, T write_data) {

//     if (write_addr >= 0 && write_addr < buffer_size)
//         buffer[write_addr] = write_data;
//     else fprintf(stderr, "data_buffer write addr error.\n");

// }

// template <typename T>
// void data_buffer<T>::read(int read_addr, T read_data) {

//     if (read_addr >= 0 && read_addr < buffer_size)
//         read_data = buffer[read_addr];
//     else fprintf(stderr, "data_buffer read addr error.\n");

// }

addr_regfile::addr_regfile(int size) {
    buffer = (int*)malloc(size * sizeof(int));
    buffer_size = size;
    last_write_cycle = (int*)malloc(size * sizeof(int));
    halves_written = (unsigned char*)malloc(size * sizeof(unsigned char));
    last_write_origin = (const char**)malloc(size * sizeof(const char*));
    reset();
}

addr_regfile::~addr_regfile() {
    free(buffer);
    free(last_write_cycle);
    free(halves_written);
    free(last_write_origin);
}

void addr_regfile::reset() {
    int i;
    for (i = 0; i < buffer_size; i++) {
        buffer[i] = 0;
        last_write_cycle[i] = -1;
        halves_written[i] = 0;
        last_write_origin[i] = nullptr;
    }
}

void addr_regfile::write(int* write_addr, int* write_data, int n){
    for(int i = 0; i < n; i++){
        if (write_addr[i] != -1){
            if (write_addr[i] >= 0 && write_addr[i] < buffer_size)
                st(write_addr[i], write_data[i], CTRL_GR, "ctrl_write");
            else fprintf(stderr, "addr_regfile write addr error. %d outside buffsize %d\n", write_addr[i], buffer_size);
        }
    }
}

void addr_regfile::show_data(int addr) {
    if (addr >= 0 && addr < buffer_size) {
        printf("addr_regfile[%d] = %d\n", addr, buffer[addr]);
    } else fprintf(stderr, "addr_regfile show data addr error.\n");
}


SPM::SPM(int size, std::set<EventProducer*>* producers) : active_producers(producers) {
    buffer = (int*)malloc(size * sizeof(int));
    buffer_size = size;
    for (int b = 0; b < SPM_NUM_BANKS; b++) {
        for (int s = 0; s < SPM_ACCESS_LATENCY; s++) {
            requests[b][s] = nullptr;
            cycles_left[b][s] = 0;
        }
    }
    reset();
}

SPM::~SPM() {
    free(buffer);
    for (int b = 0; b < SPM_NUM_BANKS; b++)
        for (int s = 0; s < SPM_ACCESS_LATENCY; s++)
            if (requests[b][s] != nullptr)
                delete requests[b][s];
}

void SPM::reset() {
    for (int i = 0; i < buffer_size; i++)
        buffer[i] = 0;
    for (int b = 0; b < SPM_NUM_BANKS; b++) {
        for (int s = 0; s < SPM_ACCESS_LATENCY; s++) {
            if (requests[b][s] != nullptr) {
                delete requests[b][s];
                requests[b][s] = nullptr;
            }
            cycles_left[b][s] = 0;
        }
    }
}

void SPM::show_data(int addr) {
    if (addr >= 0 && addr < buffer_size) {
        printf("SPM[%d] = %d\n", addr, buffer[addr]);
    } else fprintf(stderr, "SPM show data addr error.\n");
}

void SPM::show_data(int start_addr, int end_addr, int line_width) {
    int i;
    if (start_addr >= 0 && end_addr < buffer_size && start_addr <= end_addr) {
        // print aligned SPM in rows of 64 ints each
        int width = 3;
        for (i = start_addr; i < end_addr; i++) {
            if ((i - start_addr) % line_width == 0)
                std::cout << std::endl;
            std::cout << std::setw(width) << buffer[i];
        }
        std::cout << std::endl;
    } else fprintf(stderr, "SPM show data addr error.\n");
}

void SPM::access(int addr, int peid, SpmAccessT access_t,
                 bool single_data, LoadResult data,
                 bool isVirtualAddr){
    // Validate physical address (compute from virtual if needed)
    int phys_addr = isVirtualAddr ? (peid * SPM_BANK_GROUP_SIZE + addr) : addr;
    if (phys_addr < 0 || phys_addr >= SPM_ADDR_NUM) {
        fprintf(stderr, "PE[%d] load SPM addr %d (phys %d) error.\n", peid, addr, phys_addr);
        exit(-1);
    }
    // Index by bank, not by peid. Find first free pipeline slot.
    int bank = getBank(addr, peid, isVirtualAddr);
    int slot = -1;
    for (int s = 0; s < SPM_ACCESS_LATENCY; s++) {
        if (requests[bank][s] == nullptr) { slot = s; break; }
    }
    if (slot < 0) {
        fprintf(stderr, "PE[%d] load SPM addr %d error. Bank %d pipeline full\n",
                peid, addr, bank);
        exit(-1);
    }
    OutstandingRequest* newReq = new OutstandingRequest();
    newReq->addr        = addr;
    newReq->peid        = peid;
    newReq->access_t    = access_t;
    newReq->data        = data;
    newReq->single_data = single_data;
    newReq->isVirtualAddr = isVirtualAddr;
    requests[bank][slot]    = newReq;
    cycles_left[bank][slot] = SPM_ACCESS_LATENCY;
    mark_active_producer();
}

void SPM::mark_active_producer(){
    active_producers.push(this);
}

int SPM::getBank(int addr, int peid, bool isVirtualAddr) {
    int phys_addr = isVirtualAddr ? (peid * SPM_BANK_GROUP_SIZE + addr) : addr;
    // 8-bank scheme: bank-group (high bits) + bank-within-group (bit 1)
    // Bank = bank_group * 2 + bank_in_group
    int bank_group = phys_addr / SPM_BANK_GROUP_SIZE;  // 0-3
    int bank_in_group = (phys_addr >> 1) & 1;          // bit[1] selects sub-bank
    return bank_group * 2 + bank_in_group;             // 0-7
}

bool SPM::portIsBusy(int addr, int peid, bool isVirtualAddr) {
    int bank = getBank(addr, peid, isVirtualAddr);
    // Pipeline full iff every slot for this bank is occupied.
    for (int s = 0; s < SPM_ACCESS_LATENCY; s++)
        if (requests[bank][s] == nullptr) return false;
    return true;
}

std::pair<bool, std::list<Event>*> SPM::tick(){
    std::list<Event>* events = new std::list<Event>();
    bool requestsOutstanding = false;
    // Iterate over all banks and their pipeline slots.
    for(int bank = 0; bank < SPM_NUM_BANKS; bank++){
    for(int slot = 0; slot < SPM_ACCESS_LATENCY; slot++){
        OutstandingRequest* req = requests[bank][slot];
        if (req == nullptr) continue;
        int phys_addr = req->isVirtualAddr
            ? (req->peid * SPM_BANK_GROUP_SIZE
               + req->addr)
            : req->addr;
        if (phys_addr < 0
            || phys_addr >= buffer_size) {
            fprintf(stderr,
                "SPM tick error: phys_addr=%d "
                "out of bounds (buf_size=%d) "
                "for PE[%d] vaddr=%d "
                "isVirtual=%d\n",
                phys_addr, buffer_size,
                req->peid, req->addr,
                req->isVirtualAddr);
            exit(-1);
        }
        int base = lineAddr(phys_addr);
        cycles_left[bank][slot]--;
        if(cycles_left[bank][slot] == 0){
            if(req->access_t == SpmAccessT::WRITE){
                if (req->single_data) {
                    int s = lineOffset(phys_addr);
                    buffer[base + s] =
                        req->data.data[s];
#ifdef PROFILE
                    printf(
                        "PE[%d]@%d write "
                        "SPM[%d]=%d\n",
                        req->peid, cycle,
                        base + s,
                        req->data.data[s]);
#endif
                } else {
                    for (int j = 0;
                         j < LINE_SIZE; j++) {
                        buffer[base + j] =
                            req->data.data[j];
#ifdef PROFILE
                        printf(
                            "PE[%d]@%d write "
                            "SPM[%d]=%d\n",
                            req->peid, cycle,
                            base + j,
                            req->data.data[j]);
#endif
                    }
                }
            } else if (
                req->access_t == SpmAccessT::READ) {
                void* data = static_cast<void*>(
                    new SpmDataReadyData(
                        req->peid, &buffer[base],
                        base));
                events->push_back(
                    Event(EventType::SPM_DATA_READY,
                          data));
            } else {
                fprintf(stderr, "SPM tick error: unknown access type.\n");
                exit(-1);
            }
            delete requests[bank][slot];
            requests[bank][slot] = nullptr;
        } else {
            requestsOutstanding = true;
        }
    }
    }
    return std::make_pair(!requestsOutstanding, events);
}

SpmDataReadyData::SpmDataReadyData(
    int reqId, int* data, int physAddr)
    : requestorId(reqId), phys_addr(physAddr) {
    for (int i = 0; i < LINE_SIZE; i++)
        this->data[i] = data[i];
}

ctrl_instr_buffer::ctrl_instr_buffer(int size) {
    int i;
    buffer = (unsigned long**)malloc(size * sizeof(unsigned long*));
    for (i = 0; i < size; i++) {
        buffer[i] = (unsigned long*)malloc(CTRL_INSTR_BUFFER_GROUP_SIZE * sizeof(unsigned long));
        buffer[i][0] = 0xf;
        buffer[i][1] = 0xf;
    }
        
    buffer_size = size;
}

ctrl_instr_buffer::~ctrl_instr_buffer() {
    int i;
    for (i = 0; i < buffer_size; i++)
        free(buffer[i]);
    free(buffer);
}

void ctrl_instr_buffer::show_data(int addr) {
    if (addr >= 0 && addr < COMP_INSTR_BUFFER_GROUP_NUM) {
        printf("ctrl_instr_buffer[%d][0] = %lx\t", addr, buffer[addr][0]);
        printf("ctrl_instr_buffer[%d][1] = %lx\n", addr, buffer[addr][1]);
    } else fprintf(stderr, "ctrl_instr_buffer show data addr error.\n");
}

comp_instr_buffer::comp_instr_buffer(int size) {
    int i;
    buffer = (unsigned long**)malloc(size * sizeof(unsigned long*));
    for (i = 0; i < size; i++) {
        buffer[i] = (unsigned long*)malloc(COMP_INSTR_BUFFER_GROUP_SIZE * sizeof(unsigned long));
        buffer[i][0] = COMP_HALT_INSTRUCTION;
        buffer[i][1] = COMP_HALT_INSTRUCTION;
    }
        
    buffer_size = size;
}

comp_instr_buffer::~comp_instr_buffer() {
    int i;
    for (i = 0; i < buffer_size; i++)
        free(buffer[i]);
    free(buffer);
}

void comp_instr_buffer::show_data(int addr) {
    if (addr >= 0 && addr < COMP_INSTR_BUFFER_GROUP_NUM) {
        printf("comp_instr_buffer[%d][0] = %lx\t", addr, buffer[addr][0]);
        printf("comp_instr_buffer[%d][1] = %lx\n", addr, buffer[addr][1]);
    } else fprintf(stderr, "comp_instr_buffer show data addr error.\n");
}

// --- CtrlLSQ ---

CtrlLSQ::CtrlLSQ() {
    for (int b = 0; b < SPM_NUM_BANKS; b++)
        pendingCtrlReads[b].valid = false;
}

void CtrlLSQ::reset() {
    for (int b = 0; b < SPM_NUM_BANKS; b++) {
        spmBanks[b].clear();
        pendingCtrlReads[b].valid = false;
    }
    for (int b = 0; b < S2_NUM_BANKS; b++)
        s2Banks[b].clear();
    drainPrioritySpm = 0;
    drainPriorityS2 = 0;
}

// S2->SPM: read S2, write SPM (paired)
void CtrlLSQ::enqueueS2ToSpm(
    int s2Addr, int spmPhysAddr, bool singleData) {
    enqueueS2ReadOnly(s2Addr);
    enqueueSpmWriteOnly(spmPhysAddr, s2Addr,
                        singleData);
}

// SPM->S2: read SPM, write S2 (paired)
void CtrlLSQ::enqueueSpmToS2(
    int spmPhysAddr, int s2Addr, bool singleData) {
    enqueueSpmReadOnly(spmPhysAddr);
    enqueueS2WriteOnly(s2Addr, spmPhysAddr,
                       singleData);
}

// s1c -> SPM (mvd): s1c reads have no latency, so the write entry's data is
// already known at enqueue time. ready[] flags are set so drainSpm can issue
// the SPM write as soon as the bank is free.
void CtrlLSQ::enqueueS1cToSpm(
    int spmPhysAddr, const int* s1cData,
    bool singleData) {
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessT::WRITE;
    spmE.srcDstAddr = 0;
    spmE.singleData = singleData;
    if (singleData) {
        int slot = lineOffset(spmPhysAddr);
        spmE.data[slot] = s1cData[0];
        spmE.ready[slot] = true;
        spmE.ready[1 - slot] = true;  // unused
    } else {
        spmE.data[0] = s1cData[0];
        spmE.data[1] = s1cData[1];
        spmE.ready[0] = true;
        spmE.ready[1] = true;
    }
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

// SPM -> s1c (mvd): tag a standalone SPM read so its completion lands in
// s1c[] rather than scanning s2Banks for matches.
void CtrlLSQ::enqueueSpmToS1c(
    int spmPhysAddr, int s1cAddr, bool singleData) {
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessT::READ;
    spmE.srcDstAddr = 0;
    spmE.singleData = singleData;
    spmE.ready[0] = false;
    spmE.ready[1] = false;
    spmE.dest = SpmReadDest::S1C;
    spmE.destAddr = s1cAddr;
    spmE.destNumWords = singleData ? 1 : 2;
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

// SPM -> MM: tag a standalone SPM read so its completion calls
// mm->issueStore. MM itself handles the latency counter; the SPM read still
// has SPM_ACCESS_LATENCY before its data arrives.
void CtrlLSQ::enqueueSpmReadForMm(
    int spmPhysAddr, int mmAddr, bool singleData) {
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessT::READ;
    spmE.srcDstAddr = 0;
    spmE.singleData = singleData;
    spmE.ready[0] = false;
    spmE.ready[1] = false;
    spmE.dest = SpmReadDest::MM;
    spmE.destAddr = mmAddr;
    spmE.destNumWords = singleData ? 1 : 2;
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

// MM -> SPM: MM::tick has just finished a 100-cycle load and is staging the
// resulting line as an SPM write. Mirrors enqueueS1cToSpm — data is fully
// ready at enqueue time.
void CtrlLSQ::enqueueSpmWriteWithData(
    int spmPhysAddr, const int* lineData,
    bool singleData) {
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessT::WRITE;
    spmE.srcDstAddr = 0;
    spmE.singleData = singleData;
    if (singleData) {
        int slot = lineOffset(spmPhysAddr);
        spmE.data[slot] = lineData[0];
        spmE.ready[slot] = true;
        spmE.ready[1 - slot] = true;
    } else {
        spmE.data[0] = lineData[0];
        spmE.data[1] = lineData[1];
        spmE.ready[0] = true;
        spmE.ready[1] = true;
    }
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

// Standalone S2 read (no paired SPM write)
void CtrlLSQ::enqueueS2ReadOnly(int s2Addr) {
    LsqEntry s2E{};
    s2E.addr = s2Addr;
    s2E.accessType = AccessT::READ;
    s2E.srcDstAddr = 0;  // unused for standalone
    s2E.singleData = false;
    s2E.ready[0] = false;
    s2E.ready[1] = false;
    s2Banks[s2Bank(s2Addr)].push_back(s2E);
}

// Standalone SPM write (no paired S2 read)
void CtrlLSQ::enqueueSpmWriteOnly(
    int spmPhysAddr, int s2SrcAddr,
    bool singleData) {
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessT::WRITE;
    spmE.srcDstAddr = s2SrcAddr;
    spmE.singleData = singleData;
    if (singleData) {
        int slot = lineOffset(spmPhysAddr);
        spmE.ready[slot] = false;     // waiting
        spmE.ready[1 - slot] = true;  // unused
    } else {
        spmE.ready[0] = false;
        spmE.ready[1] = false;
    }
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

// Standalone SPM read (no paired S2 write)
void CtrlLSQ::enqueueSpmReadOnly(int spmPhysAddr) {
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessT::READ;
    spmE.srcDstAddr = 0;  // unused for standalone
    spmE.singleData = false;
    spmE.ready[0] = false;
    spmE.ready[1] = false;
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

// Standalone S2 write (no paired SPM read)
void CtrlLSQ::enqueueS2WriteOnly(
    int s2Addr, int spmSrcAddr,
    bool singleData) {
    LsqEntry s2E{};
    s2E.addr = s2Addr;
    s2E.accessType = AccessT::WRITE;
    s2E.srcDstAddr = spmSrcAddr;
    s2E.singleData = singleData;
    if (singleData) {
        int slot = lineOffset(s2Addr);
        s2E.ready[slot] = false;
        s2E.ready[1 - slot] = true;
    } else {
        s2E.ready[0] = false;
        s2E.ready[1] = false;
    }
    s2Banks[s2Bank(s2Addr)].push_back(s2E);
}

// Drain SPM bank queues: issue reads/writes to SPM
void CtrlLSQ::drainSpm(
    SPM* spm, bool spmBankBusy[SPM_NUM_BANKS]) {
    for (int bi = 0; bi < SPM_NUM_BANKS; bi++) {
        int b = (drainPrioritySpm + bi)
                % SPM_NUM_BANKS;
        if (spmBanks[b].empty()) continue;
        if (spmBankBusy[b]) continue;
        LsqEntry& entry = spmBanks[b].front();

        if (entry.accessType == AccessT::READ) {
            // One controller read per bank in flight at a time:
            // pendingCtrlReads[b] is a single slot tracker, and SPM read
            // completions arrive in issue order but this queue can't
            // distinguish multiple outstanding controller reads.
            if (pendingCtrlReads[b].valid) continue;
            // Issue read to SPM
            spm->access(entry.addr, CTRL_PEID,
                SpmAccessT::READ, false,
                LoadResult(), false);
            pendingCtrlReads[b].valid = true;
            pendingCtrlReads[b].spmPhysAddr =
                entry.addr;
            pendingCtrlReads[b].s2Addr =
                entry.srcDstAddr;
            pendingCtrlReads[b].singleData =
                entry.singleData;
            pendingCtrlReads[b].dest = entry.dest;
            pendingCtrlReads[b].destAddr =
                entry.destAddr;
            pendingCtrlReads[b].destNumWords =
                entry.destNumWords;
            spmBankBusy[b] = true;
            spmBanks[b].pop_front();
        } else {  // WRITE
            int slot = lineOffset(entry.addr);
            bool dataReady = entry.singleData
                ? entry.ready[slot]
                : (entry.ready[0] && entry.ready[1]);
            if (!dataReady) continue;
            LoadResult lr;
            lr.data[0] = entry.data[0];
            lr.data[1] = entry.data[1];
            spm->access(entry.addr, CTRL_PEID,
                SpmAccessT::WRITE, entry.singleData,
                lr, false);
            spmBankBusy[b] = true;
            spmBanks[b].pop_front();
        }
    }
    drainPrioritySpm =
        (drainPrioritySpm + 1) % SPM_NUM_BANKS;
}

// Drain S2 bank queues: issue reads/writes to S2
void CtrlLSQ::drainS2(S2* s2) {
    for (int bi = 0; bi < S2_NUM_BANKS; bi++) {
        int b = (drainPriorityS2 + bi)
                % S2_NUM_BANKS;
        if (s2Banks[b].empty()) continue;
        LsqEntry& entry = s2Banks[b].front();

        if (entry.accessType == AccessT::READ) {
            s2->issueRead(entry.addr,
                entry.srcDstAddr, entry.singleData);
            s2Banks[b].pop_front();
        } else {  // WRITE
            int slot = lineOffset(entry.addr);
            bool dataReady = entry.singleData
                ? entry.ready[slot]
                : (entry.ready[0] && entry.ready[1]);
            if (!dataReady) continue;
            s2->issueWrite(entry.addr, entry.data,
                entry.singleData);
            s2Banks[b].pop_front();
        }
    }
    drainPriorityS2 =
        (drainPriorityS2 + 1) % S2_NUM_BANKS;
}

void CtrlLSQ::tick(
    SPM* spm, S2* s2,
    bool spmBankBusy[SPM_NUM_BANKS]) {
    drainSpm(spm, spmBankBusy);
    drainS2(s2);
}

// Called when S2 read completes -> fill SPM write entries.
// Scans ALL SPM banks so one completion can serve
// multiple writes (needed for misaligned MVDQ).
void CtrlLSQ::dataReadyFromS2(
    int s2Addr, int* lineData) {
    int readLine = lineAddr(s2Addr);

    for (int b = 0; b < SPM_NUM_BANKS; b++) {
        for (auto& spmE : spmBanks[b]) {
            if (spmE.accessType != AccessT::WRITE)
                continue;
            int S = spmE.srcDstAddr;

            if (spmE.singleData) {
                int slot = lineOffset(spmE.addr);
                if (!spmE.ready[slot]
                    && lineAddr(S) == readLine) {
                    spmE.data[slot] =
                        lineData[lineOffset(S)];
                    spmE.ready[slot] = true;
                }
            } else {
                if (!spmE.ready[0]
                    && lineAddr(S) == readLine) {
                    spmE.data[0] =
                        lineData[lineOffset(S)];
                    spmE.ready[0] = true;
                }
                if (!spmE.ready[1]
                    && lineAddr(S + 1) == readLine) {
                    spmE.data[1] =
                        lineData[lineOffset(S+1)];
                    spmE.ready[1] = true;
                }
            }
        }
    }
    // No assert: duplicate S2 reads may not match
}

// Called when SPM read completes. Dispatches by dest tag:
//   S2  -> scan S2 write entries and fill matching slots (legacy path)
//   MM  -> synchronously call mm->issueStore for the loaded line
//   S1C -> synchronously write into s1c[] at destAddr
void CtrlLSQ::dataReadyFromSpm(
    int bank, int* lineData, MM* mm, int* s1c) {
    assert(pendingCtrlReads[bank].valid);
    auto& pr = pendingCtrlReads[bank];

    if (pr.dest == SpmReadDest::S2) {
        int readLine = lineAddr(pr.spmPhysAddr);
        for (int sb = 0; sb < S2_NUM_BANKS; sb++) {
            for (auto& s2E : s2Banks[sb]) {
                if (s2E.accessType != AccessT::WRITE)
                    continue;
                int S = s2E.srcDstAddr;

                if (s2E.singleData) {
                    int slot = lineOffset(s2E.addr);
                    if (!s2E.ready[slot]
                        && lineAddr(S) == readLine) {
                        s2E.data[slot] =
                            lineData[lineOffset(S)];
                        s2E.ready[slot] = true;
                    }
                } else {
                    if (!s2E.ready[0]
                        && lineAddr(S) == readLine) {
                        s2E.data[0] =
                            lineData[lineOffset(S)];
                        s2E.ready[0] = true;
                    }
                    if (!s2E.ready[1]
                        && lineAddr(S + 1) == readLine) {
                        s2E.data[1] =
                            lineData[lineOffset(S+1)];
                        s2E.ready[1] = true;
                    }
                }
            }
        }
    } else if (pr.dest == SpmReadDest::MM) {
        // MM store is immediate. For singleData we forward only the
        // requested word; otherwise the full 2-word line.
        if (pr.singleData) {
            int slot = lineOffset(pr.spmPhysAddr);
            mm->issueStore(pr.destAddr,
                &lineData[slot], 1);
        } else {
            mm->issueStore(pr.destAddr, lineData, 2);
        }
    } else { // SpmReadDest::S1C
        if (pr.singleData) {
            int slot = lineOffset(pr.spmPhysAddr);
            s1c[pr.destAddr] = lineData[slot];
        } else {
            s1c[pr.destAddr] = lineData[0];
            s1c[pr.destAddr + 1] = lineData[1];
        }
    }
    pr.valid = false;
}

bool CtrlLSQ::spmBankFull(int physAddr) const {
    int b = spmBank(physAddr);
    return (int)spmBanks[b].size()
        >= LSQ_MAX_ENTRIES_PER_BANK;
}

bool CtrlLSQ::s2BankFull(int addr) const {
    int b = s2Bank(addr);
    return (int)s2Banks[b].size()
        >= LSQ_MAX_ENTRIES_PER_BANK;
}

bool CtrlLSQ::canEnqueue(
    int* spmAddrs, int nSpm,
    int* s2Addrs, int nS2) const {
    int spmExtra[SPM_NUM_BANKS] = {};
    int s2Extra[S2_NUM_BANKS] = {};
    for (int i = 0; i < nSpm; i++)
        spmExtra[spmBank(spmAddrs[i])]++;
    for (int i = 0; i < nS2; i++)
        s2Extra[s2Bank(s2Addrs[i])]++;
    for (int b = 0; b < SPM_NUM_BANKS; b++)
        if ((int)spmBanks[b].size() + spmExtra[b]
            > LSQ_MAX_ENTRIES_PER_BANK)
            return false;
    for (int b = 0; b < S2_NUM_BANKS; b++)
        if ((int)s2Banks[b].size() + s2Extra[b]
            > LSQ_MAX_ENTRIES_PER_BANK)
            return false;
    return true;
}

bool CtrlLSQ::empty() const {
    for (int b = 0; b < SPM_NUM_BANKS; b++)
        if (!spmBanks[b].empty()) return false;
    for (int b = 0; b < S2_NUM_BANKS; b++)
        if (!s2Banks[b].empty()) return false;
    return true;
}

bool CtrlLSQ::hasPendingOps(
    SPM* spm, S2* s2, const MM* mm) const {
    if (!empty()) return true;
    for (int b = 0; b < SPM_NUM_BANKS; b++) {
        if (pendingCtrlReads[b].valid) return true;
        // Any pipeline slot for this bank issued by the controller?
        for (int s = 0; s < SPM_ACCESS_LATENCY; s++) {
            if (spm->requests[b][s]
                && spm->requests[b][s]->peid == CTRL_PEID)
                return true;
        }
    }
    if (mm && mm->hasPendingOps()) return true;
    return s2->hasPendingOps();
}

// --- MM ---

MM::MM() {}

void MM::setBuffer(int* buf) {
    buffer = buf;
}

void MM::issueStore(int addr, const int* data,
                    int numWords) {
    assert(buffer != nullptr
           && "MM::issueStore before setBuffer");
    for (int i = 0; i < numWords; i++)
        buffer[addr + i] = data[i];
    lastMMStore = MM_LATENCY;
}

void MM::issueLoad(int addr, int destId,
                   int destAddr, int numWords,
                   bool singleData) {
    assert(buffer != nullptr
           && "MM::issueLoad before setBuffer");
    assert(numWords == 1 || numWords == 2
           || numWords == 8);
    MMLoadEntry e{};
    e.addr = addr;
    e.destId = destId;
    e.destAddr = destAddr;
    e.numWords = numWords;
    e.cyclesLeft = MM_LATENCY;
    e.singleData = singleData;
    for (int i = 0; i < numWords; i++)
        e.data[i] = buffer[addr + i];
    loadQueue.push_back(e);
}

void MM::tick(CtrlLSQ* lsq, int* gr) {
    if (lastMMStore >= 0) lastMMStore--;
    // Decrement every entry, then drain expired heads in FIFO order.
    for (auto& e : loadQueue) e.cyclesLeft--;
    while (!loadQueue.empty()
           && loadQueue.front().cyclesLeft <= 0) {
        MMLoadEntry e = loadQueue.front();
        loadQueue.pop_front();
        if (e.destId == CTRL_GR) {
            // 1-word direct write into the controller gr file.
            gr[e.destAddr] = e.data[0];
        } else { // CTRL_SPM
            // Stage SPM writes via LSQ. mvdq covers 8 words = 4 lines;
            // mv/mvd cover 1 or 2 words = 1 line.
            if (e.numWords == 8) {
                for (int i = 0; i < 4; i++) {
                    int spmA = e.destAddr + 2 * i;
                    int line[2] = {
                        e.data[2 * i],
                        e.data[2 * i + 1]
                    };
                    lsq->enqueueSpmWriteWithData(
                        spmA, line, false);
                }
            } else {
                lsq->enqueueSpmWriteWithData(
                    e.destAddr, e.data, e.singleData);
            }
        }
    }
}

bool MM::hasPendingOps() const {
    return lastMMStore >= 0 || !loadQueue.empty();
}

bool MM::loadQueueFull() const {
    return (int)loadQueue.size() >= MM_LATENCY;
}
