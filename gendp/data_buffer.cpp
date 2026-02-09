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
    int i;
    for (i = 0; i < buffer_size; i++)
        buffer[i] = -42;
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

void SPM::access(int addr, int peid, SpmAccessT access_t, bool single_data, LoadResult data, bool isVirtualAddr, int write_slot){
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
    newReq->write_slot  = write_slot;
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
        // Use req->peid for physical address calculation (not the bank index)
        int phys_addr = req->isVirtualAddr ? (req->peid * SPM_BANK_GROUP_SIZE + req->addr) : req->addr;
        if (phys_addr < 0 || phys_addr >= buffer_size) {
            fprintf(stderr, "SPM tick error: phys_addr=%d out of bounds (buf_size=%d) for PE[%d] "
                    "vaddr=%d isVirtual=%d\n",
                    phys_addr, buffer_size, req->peid, req->addr, req->isVirtualAddr);
            exit(-1);
        }
        cycles_left[bank]--;
        if(cycles_left[bank] == 0){
            if(req->access_t == SpmAccessT::WRITE){
                if (req->single_data) {
                    int s = req->write_slot;
                    buffer[phys_addr + s] =
                        req->data.data[s];
#ifdef PROFILE
                    printf("PE[%d]@%d write SPM[%d]=%d\n",
                           req->peid, cycle,
                           req->addr + s,
                           req->data.data[s]);
#endif
                } else {
                    for (int j = 0; j < SPM_BANDWIDTH; j++){
                        buffer[phys_addr + j] =
                            req->data.data[j];
#ifdef PROFILE
                        printf(
                            "PE[%d]@%d write SPM[%d]=%d\n",
                            req->peid, cycle,
                            req->addr + j,
                            req->data.data[j]);
#endif
                    }
                }
            } else if (req->access_t == SpmAccessT::READ){
                // generate SpmDataReadyEv - use req->peid as requestor ID
                void* data = static_cast<void*>(new SpmDataReadyData(req->peid, &buffer[phys_addr]));
                events->push_back(Event(EventType::SPM_DATA_READY, data));
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

SpmDataReadyData::SpmDataReadyData(int reqId, int* data) : requestorId(reqId) {
    for (int i = 0; i < SPM_BANDWIDTH; i++) {
        this->data[i] = data[i];
    }
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

CtrlLSQ::CtrlLSQ() {}

void CtrlLSQ::enqueueS2ToSpm(int s2Addr, int spmPhysAddr,
                              bool singleData, S2* s2) {
    // Controller reads S2 directly and pre-fills SPM
    // write entry. No S2 read pipeline needed since the
    // controller has direct access to S2 data.
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.isRead = false;
    spmE.srcDstAddr = s2Addr;
    spmE.singleData = singleData;
    if (singleData) {
        spmE.data[0] = s2->buffer[s2Addr];
        spmE.ready[0] = true;
        spmE.ready[1] = false;
    } else {
        int base = (s2Addr >> 1) << 1;
        spmE.data[0] = s2->buffer[base];
        spmE.data[1] = s2->buffer[base + 1];
        spmE.ready[0] = true;
        spmE.ready[1] = true;
    }
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);
}

void CtrlLSQ::enqueueSpmToS2(int spmPhysAddr, int s2Addr,
                              bool singleData) {
    // SPM read entry
    LsqEntry spmE{};
    spmE.addr = spmPhysAddr;
    spmE.isRead = true;
    spmE.srcDstAddr = s2Addr;
    spmE.singleData = singleData;
    spmE.ready[0] = false;
    spmE.ready[1] = false;
    spmBanks[spmBank(spmPhysAddr)].push_back(spmE);

    // S2 write entry
    LsqEntry s2e{};
    s2e.addr = s2Addr;
    s2e.isRead = false;
    s2e.srcDstAddr = spmPhysAddr;
    s2e.singleData = singleData;
    s2e.ready[0] = false;
    s2e.ready[1] = false;
    s2Banks[s2Bank(s2Addr)].push_back(s2e);
}

void CtrlLSQ::tickS2Outstanding(S2* s2) {
    // S2→SPM reads are now pre-filled at enqueue time,
    // so this pipeline is unused for that direction.
    // Kept for potential future use.
    for (int b = 0; b < S2_NUM_BANKS; b++) {
        if (s2Outstanding[b].empty()) continue;
        S2OutstandingReq& req = s2Outstanding[b].front();
        req.cyclesLeft--;
        if (req.cyclesLeft <= 0) {
            // Match against SPM write entries
            bool found = false;
            for (int sb = 0; sb < SPM_NUM_BANKS
                 && !found; sb++) {
                for (auto& spmE : spmBanks[sb]) {
                    if (!spmE.isRead &&
                        spmE.srcDstAddr == req.addr &&
                        !spmE.ready[0]) {
                        if (req.singleData) {
                            spmE.data[0] =
                                s2->buffer[req.addr];
                            spmE.ready[0] = true;
                        } else {
                            int base =
                                (req.addr >> 1) << 1;
                            spmE.data[0] =
                                s2->buffer[base];
                            spmE.data[1] =
                                s2->buffer[base + 1];
                            spmE.ready[0] = true;
                            spmE.ready[1] = true;
                        }
                        found = true;
                        break;
                    }
                }
            }
            if (!found) {
                fprintf(stderr,
                    "LSQ: S2 read completed at addr=%d "
                    "single=%d but no matching SPM write "
                    "entry found!\n",
                    req.addr, req.singleData);
            }
            s2Outstanding[b].pop_front();
        }
    }
}

void CtrlLSQ::drainS2Reads(S2* s2) {
    for (int bi = 0; bi < S2_NUM_BANKS; bi++) {
        int b = (drainPriorityS2 + bi) % S2_NUM_BANKS;
        if (s2Banks[b].empty()) continue;
        LsqEntry& entry = s2Banks[b].front();
        if (!entry.isRead) continue;

        // Issue to S2 outstanding pipeline
        S2OutstandingReq req{};
        req.addr = entry.addr;
        req.cyclesLeft = S2_READ_LATENCY - 1;
        req.singleData = entry.singleData;
        s2Outstanding[b].push_back(req);
        s2Banks[b].pop_front();
    }
    drainPriorityS2 =
        (drainPriorityS2 + 1) % S2_NUM_BANKS;
}

void CtrlLSQ::drainSpmWrites(SPM* spm,
                              bool spmBankBusy[SPM_NUM_BANKS]) {
    for (int bi = 0; bi < SPM_NUM_BANKS; bi++) {
        int b = (drainPrioritySpm + bi) % SPM_NUM_BANKS;
        if (spmBanks[b].empty()) continue;
        LsqEntry& entry = spmBanks[b].front();
        if (entry.isRead) continue;
        if (spmBankBusy[b]) continue;

        bool dataReady = entry.singleData
            ? entry.ready[0]
            : (entry.ready[0] && entry.ready[1]);
        if (!dataReady) continue;

        // Magic write to SPM buffer
        if (entry.singleData) {
            spm->buffer[entry.addr] = entry.data[0];
        } else {
            int base = (entry.addr >> 1) << 1;
            spm->buffer[base]     = entry.data[0];
            spm->buffer[base + 1] = entry.data[1];
        }
        spmBanks[b].pop_front();
    }
    drainPrioritySpm =
        (drainPrioritySpm + 1) % SPM_NUM_BANKS;
}

void CtrlLSQ::drainSpmReads(SPM* spm,
                             bool spmBankBusy[SPM_NUM_BANKS]) {
    for (int bi = 0; bi < SPM_NUM_BANKS; bi++) {
        int b = (drainPrioritySpm + bi) % SPM_NUM_BANKS;
        if (spmBanks[b].empty()) continue;
        LsqEntry& entry = spmBanks[b].front();
        if (!entry.isRead) continue;
        if (spmBankBusy[b]) continue;

        // Match against S2 write entries
        bool found = false;
        for (int sb = 0; sb < S2_NUM_BANKS
             && !found; sb++) {
            for (auto& s2e : s2Banks[sb]) {
                if (!s2e.isRead &&
                    s2e.srcDstAddr == entry.addr &&
                    !s2e.ready[0]) {
                    if (entry.singleData) {
                        s2e.data[0] =
                            spm->buffer[entry.addr];
                        s2e.ready[0] = true;
                    } else {
                        int base =
                            (entry.addr >> 1) << 1;
                        s2e.data[0] =
                            spm->buffer[base];
                        s2e.data[1] =
                            spm->buffer[base + 1];
                        s2e.ready[0] = true;
                        s2e.ready[1] = true;
                    }
                    found = true;
                    break;
                }
            }
        }
        spmBankBusy[b] = true;
        spmBanks[b].pop_front();
    }
}

void CtrlLSQ::drainS2Writes(S2* s2) {
    for (int bi = 0; bi < S2_NUM_BANKS; bi++) {
        int b = (drainPriorityS2 + bi) % S2_NUM_BANKS;
        if (s2Banks[b].empty()) continue;
        LsqEntry& entry = s2Banks[b].front();
        if (entry.isRead) continue;

        bool dataReady = entry.singleData
            ? entry.ready[0]
            : (entry.ready[0] && entry.ready[1]);
        if (!dataReady) continue;

        // Issue to S2 write pipeline
        S2OutstandingWriteReq wreq{};
        wreq.addr = entry.addr;
        wreq.data[0] = entry.data[0];
        wreq.data[1] = entry.data[1];
        wreq.cyclesLeft = S2_WRITE_LATENCY - 1;
        wreq.singleData = entry.singleData;
        s2OutstandingWrites[b].push_back(wreq);
        s2Banks[b].pop_front();
    }
}

void CtrlLSQ::tickS2OutstandingWrites(S2* s2) {
    for (int b = 0; b < S2_NUM_BANKS; b++) {
        if (s2OutstandingWrites[b].empty()) continue;
        S2OutstandingWriteReq& req =
            s2OutstandingWrites[b].front();
        req.cyclesLeft--;
        if (req.cyclesLeft <= 0) {
            if (req.singleData) {
                s2->buffer[req.addr] = req.data[0];
            } else {
                int base = (req.addr >> 1) << 1;
                s2->buffer[base]     = req.data[0];
                s2->buffer[base + 1] = req.data[1];
            }
            s2OutstandingWrites[b].pop_front();
        }
    }
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
        int* spmAddrs, int n) const {
    // S2→SPM only adds to spmBanks (pre-filled)
    int extra[SPM_NUM_BANKS] = {};
    for (int i = 0; i < n; i++)
        extra[spmBank(spmAddrs[i])]++;
    for (int b = 0; b < SPM_NUM_BANKS; b++)
        if ((int)spmBanks[b].size() + extra[b]
            > LSQ_MAX_ENTRIES_PER_BANK)
            return false;
    return true;
}

bool CtrlLSQ::canEnqueueSpmToS2(
        int* spmAddrs, int* s2Addrs, int n) const {
    // SPM→S2 adds to both spmBanks and s2Banks
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
    for (int b = 0; b < S2_NUM_BANKS; b++)
        if (!s2Outstanding[b].empty()) return false;
    for (int b = 0; b < S2_NUM_BANKS; b++)
        if (!s2OutstandingWrites[b].empty()) return false;
    return true;
}
