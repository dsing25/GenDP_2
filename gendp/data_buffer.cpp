#include "data_buffer.h"
#include <iomanip>
#include <cassert>

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
    for (int i = 0; i < PE_4_SETTING; i++)
        requests[i] = nullptr;
    reset();
}

SPM::~SPM() {
    free(buffer);
    for (int i = 0; i < PE_4_SETTING; i++)
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

void SPM::access(int addr, int peid, SpmAccessT access_t, bool single_data, LoadResult data){
    assert(requests[peid] == nullptr); //there was a request already there
    if (addr < 0 || addr >= SPM_ADDR_NUM) {
        fprintf(stderr, "PE[%d] load SPM addr %d error.\n", peid, addr);
        exit(-1);
    }
    OutstandingRequest* newReq = new OutstandingRequest();
    newReq->addr        = addr;
    newReq->cycles_left = SPM_ACCESS_LATENCY;
    newReq->peid        = peid;
    newReq->access_t    = access_t;
    newReq->data        = data;
    newReq->single_data = single_data;
    requests[peid]      = newReq;
    mark_active_producer();
}

void SPM::mark_active_producer(){
    active_producers.push(this);
}

std::pair<bool, std::list<Event>*> SPM::tick(){
    std::list<Event>* events = new std::list<Event>();
    bool requestsOutstanding = false;
    for(int i = 0; i < PE_4_SETTING; i++){
        OutstandingRequest* req = requests[i];
        if (req == nullptr) continue;
        req->cycles_left--;
        if(req->cycles_left == 0){
            if(req->access_t == SpmAccessT::WRITE){
                // write data to SPM
                int n_writes = req->single_data ? 1 : SPM_BANDWIDTH;
                for (int j = 0; j < n_writes; j++){
                    buffer[req->addr+j] = req->data.data[j];
#ifdef PROFILE
                    printf("PE[%d]@%d write SPM[%d] = %d\n", i, cycle, req->addr+j, req->data.data[j]);
#endif
                }
            } else if (req->access_t == SpmAccessT::READ){
                // generate SpmDataReadyEv
                void* data = static_cast<void*>(new SpmDataReadyData(i, &buffer[req->addr]));
                events->push_back(Event(EventType::SPM_DATA_READY, data));
            } else {
                fprintf(stderr, "SPM tick error: unknown access type.\n");
                exit(-1);
            }
            delete requests[i];
            requests[i] = nullptr;
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
