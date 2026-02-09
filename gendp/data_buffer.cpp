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
            e.accessType = AccessType::READ;
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
            e.accessType = AccessType::WRITE;
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

            if (e.accessType == AccessType::READ) {
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

bool S2::bankFull(int addr) const {
    int b = s2Bank(addr);
    for (int s = 0; s < S2_READ_LATENCY; s++)
        if (!outstanding[b][s].valid) return false;
    return true;
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
    reset();
}

addr_regfile::~addr_regfile() {
    free(buffer);
}

void addr_regfile::reset() {
    int i;
    for (i = 0; i < buffer_size; i++)
        buffer[i] = 0;
}

void addr_regfile::write(int* write_addr, int* write_data, int n){
    for(int i = 0; i < n; i++){
        if (write_addr[i] != -1){
            if (write_addr[i] >= 0 && write_addr[i] < buffer_size)
                buffer[write_addr[i]] = write_data[i];
            else fprintf(stderr, "addr_regfile write addr error. %d outside buffsize %d\n", write_addr[i], buffer_size);
        }
    }
    //ensure no two addrs are the same
    for(int i = 0; i < n; i++){
        for(int j = i + 1; j < n; j++){
            if(write_addr[i] == write_addr[j] && write_addr[i] != -1){
                fprintf(stderr, "addr_regfile write addr error. duplicate addr %d\n", write_addr[i]);
            }
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
    for (int i = 0; i < SPM_NUM_BANKS; i++) {
        requests[i] = nullptr;
        cycles_left[i] = 0;
    }
    reset();
}

SPM::~SPM() {
    free(buffer);
    for (int i = 0; i < SPM_NUM_BANKS; i++)
        if (requests[i] != nullptr)
            delete requests[i];
}

void SPM::reset() {
    int i;
    for (i = 0; i < buffer_size; i++)
        buffer[i] = 0;
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
    // Index by bank, not by peid
    int bank = getBank(addr, peid, isVirtualAddr);
    if (requests[bank] != nullptr) {
        fprintf(stderr, "PE[%d] load SPM addr %d error. Bank %d already has pending request\n",
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
    requests[bank]      = newReq;
    cycles_left[bank]   = SPM_ACCESS_LATENCY;
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
    return requests[bank] != nullptr;  // Check if bank has pending request
}

std::pair<bool, std::list<Event>*> SPM::tick(){
    std::list<Event>* events = new std::list<Event>();
    bool requestsOutstanding = false;
    // Iterate over all 8 banks
    for(int bank = 0; bank < SPM_NUM_BANKS; bank++){
        OutstandingRequest* req = requests[bank];
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
        cycles_left[bank]--;
        if(cycles_left[bank] == 0){
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
                         j < SPM_BANDWIDTH; j++) {
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
            delete requests[bank];
            requests[bank] = nullptr;
        } else {
            requestsOutstanding = true;
        }
    }
    return std::make_pair(!requestsOutstanding, events);
}

SpmDataReadyData::SpmDataReadyData(
    int reqId, int* data, int physAddr)
    : requestorId(reqId), phys_addr(physAddr) {
    for (int i = 0; i < SPM_BANDWIDTH; i++)
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
        buffer[i][0] = 0x20f7800000000;
        buffer[i][1] = 0x20f7800000000;
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

// S2->SPM: read S2, write SPM
void CtrlLSQ::enqueueS2ToSpm(
    int s2Addr, int spmPhysAddr, bool singleData) {
    // S2 read entry
    LsqEntry s2E{};
    s2E.addr = s2Addr;
    s2E.accessType = AccessType::READ;
    s2E.srcDstAddr = spmPhysAddr;
    s2E.singleData = singleData;
    s2E.ready[0] = false;
    s2E.ready[1] = false;
    s2Banks[s2Bank(s2Addr)].push_back(s2E);

    // SPM write entry (unfilled, waiting for S2 data)
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessType::WRITE;
    spmE.srcDstAddr = s2Addr;
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

// SPM->S2: read SPM, write S2
void CtrlLSQ::enqueueSpmToS2(
    int spmPhysAddr, int s2Addr, bool singleData) {
    // SPM read entry
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.accessType = AccessType::READ;
    spmE.srcDstAddr = s2Addr;
    spmE.singleData = singleData;
    spmE.ready[0] = false;
    spmE.ready[1] = false;
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);

    // S2 write entry (unfilled)
    LsqEntry s2E{};
    s2E.addr = s2Addr;
    s2E.accessType = AccessType::WRITE;
    s2E.srcDstAddr = spmPhysAddr;
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

        if (entry.accessType == AccessType::READ) {
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

        if (entry.accessType == AccessType::READ) {
            if (s2->bankFull(entry.addr)) continue;
            s2->issueRead(entry.addr,
                entry.srcDstAddr, entry.singleData);
            s2Banks[b].pop_front();
        } else {  // WRITE
            int slot = lineOffset(entry.addr);
            bool dataReady = entry.singleData
                ? entry.ready[slot]
                : (entry.ready[0] && entry.ready[1]);
            if (!dataReady) continue;
            if (s2->bankFull(entry.addr)) continue;
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

// Called when S2 read completes -> fill SPM write entry
void CtrlLSQ::dataReadyFromS2(
    int spmPhysAddr, int s2Addr, int* lineData) {
    int targetBank = spmBank(spmPhysAddr);
    int readLine = lineAddr(s2Addr);

    for (auto& spmE : spmBanks[targetBank]) {
        if (spmE.accessType != AccessType::WRITE)
            continue;
        int S = spmE.srcDstAddr;  // S2 source addr
        bool matched = false;

        if (spmE.singleData) {
            int slot = lineOffset(spmE.addr);
            if (!spmE.ready[slot]
                && lineAddr(S) == readLine) {
                spmE.data[slot] =
                    lineData[lineOffset(S)];
                spmE.ready[slot] = true;
                return;
            }
        } else {
            if (!spmE.ready[0]
                && lineAddr(S) == readLine) {
                spmE.data[0] =
                    lineData[lineOffset(S)];
                spmE.ready[0] = true;
                matched = true;
            }
            if (!spmE.ready[1]
                && lineAddr(S + 1) == readLine) {
                spmE.data[1] =
                    lineData[lineOffset(S + 1)];
                spmE.ready[1] = true;
                matched = true;
            }
            if (matched) return;
        }
    }
    assert(false &&
        "dataReadyFromS2: no matching SPM write");
}

// Called when SPM read completes -> fill S2 write entry
void CtrlLSQ::dataReadyFromSpm(
    int bank, int* lineData) {
    assert(pendingCtrlReads[bank].valid);
    auto& pr = pendingCtrlReads[bank];
    int readLine = lineAddr(pr.spmPhysAddr);
    int targetS2Bank = s2Bank(pr.s2Addr);

    for (auto& s2E : s2Banks[targetS2Bank]) {
        if (s2E.accessType != AccessType::WRITE)
            continue;
        int S = s2E.srcDstAddr;  // SPM source addr
        bool matched = false;

        if (s2E.singleData) {
            int slot = lineOffset(s2E.addr);
            if (!s2E.ready[slot]
                && lineAddr(S) == readLine) {
                s2E.data[slot] =
                    lineData[lineOffset(S)];
                s2E.ready[slot] = true;
                matched = true;
            }
        } else {
            if (!s2E.ready[0]
                && lineAddr(S) == readLine) {
                s2E.data[0] =
                    lineData[lineOffset(S)];
                s2E.ready[0] = true;
                matched = true;
            }
            if (!s2E.ready[1]
                && lineAddr(S + 1) == readLine) {
                s2E.data[1] =
                    lineData[lineOffset(S + 1)];
                s2E.ready[1] = true;
                matched = true;
            }
        }
        if (matched) {
            pr.valid = false;
            return;
        }
    }
    assert(false &&
        "dataReadyFromSpm: no matching S2 write");
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

bool CtrlLSQ::canEnqueueS2ToSpm(
    int* spmAddrs, int* s2Addrs, int n) const {
    int spmExtra[SPM_NUM_BANKS] = {};
    int s2Extra[S2_NUM_BANKS] = {};
    for (int i = 0; i < n; i++) {
        spmExtra[spmBank(spmAddrs[i])]++;
        s2Extra[s2Bank(s2Addrs[i])]++;
    }
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

bool CtrlLSQ::canEnqueueSpmToS2(
    int* spmAddrs, int* s2Addrs, int n) const {
    int spmExtra[SPM_NUM_BANKS] = {};
    int s2Extra[S2_NUM_BANKS] = {};
    for (int i = 0; i < n; i++) {
        spmExtra[spmBank(spmAddrs[i])]++;
        s2Extra[s2Bank(s2Addrs[i])]++;
    }
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
    SPM* spm, S2* s2) const {
    if (!empty()) return true;
    for (int b = 0; b < SPM_NUM_BANKS; b++) {
        if (pendingCtrlReads[b].valid) return true;
        if (spm->requests[b]
            && spm->requests[b]->peid == CTRL_PEID)
            return true;
    }
    return s2->hasPendingOps();
}
