#include "pe_array.h"
#include <cassert>
#include "sys_def.h"
#include "data_buffer.h"
#include "simulator.h"
#include <iomanip>
#include <cstdlib>
#include <cstring>

#define NUM_FRACTION_BITS 16
#define MAX_RANGE NUM_FRACTION_BITS
#define NUM_INTEGER_BITS 5

// ==== Graph Structure for Graph Alignment ====
#define MAX_GRAPH_NODES 1000
#define MAX_NODE_SEQ_LEN 256   // Max base pairs per node
#define MAX_NEIGHBORS 10       // Max in/out neighbors per node

struct GraphNode {
    uint32_t node_id;
    char sequence[MAX_NODE_SEQ_LEN];  // DNA sequence as ASCII ('A', 'C', 'G', 'T')
    uint16_t length;                  // Number of base pairs
    uint32_t in_neighbors[MAX_NEIGHBORS];
    uint32_t out_neighbors[MAX_NEIGHBORS];
    uint8_t num_in_neighbors;
    uint8_t num_out_neighbors;
    bool valid;                       // Is this node slot occupied?

    GraphNode() : node_id(0), length(0), num_in_neighbors(0), num_out_neighbors(0), valid(false) {
        memset(sequence, 0, sizeof(sequence));
        memset(in_neighbors, 0, sizeof(in_neighbors));
        memset(out_neighbors, 0, sizeof(out_neighbors));
    }
};

struct Graph {
    GraphNode nodes[MAX_GRAPH_NODES];
    int num_nodes;

    Graph() : num_nodes(0) {}

    // Read-only: Get node by ID
    GraphNode* getNode(uint32_t node_id) {
        for (int i = 0; i < MAX_GRAPH_NODES; i++) {
            if (nodes[i].valid && nodes[i].node_id == node_id) {
                return &nodes[i];
            }
        }
        return nullptr;  // Not found
    }

    // Load graph from external file (e.g., params.bin serialized format)
    // Format: Simple text file with:
    //   Line 1: <num_nodes>
    //   For each node:
    //     <node_id> <length> <sequence> <num_in> <in_neighbor_ids...> <num_out> <out_neighbor_ids...>
    bool loadFromFile(const char* filename) {
        FILE* fp = fopen(filename, "r");
        if (!fp) {
            fprintf(stderr, "Error: Could not open graph file '%s'\n", filename);
            return false;
        }

        int total_nodes = 0;
        if (fscanf(fp, "%d", &total_nodes) != 1) {
            fprintf(stderr, "Error: Could not read num_nodes from graph file\n");
            fclose(fp);
            return false;
        }

        if (total_nodes > MAX_GRAPH_NODES) {
            fprintf(stderr, "Error: Graph has %d nodes but MAX_GRAPH_NODES=%d\n",
                    total_nodes, MAX_GRAPH_NODES);
            fclose(fp);
            return false;
        }

        num_nodes = 0;
        for (int i = 0; i < total_nodes; i++) {
            GraphNode* node = &nodes[i];
            node->valid = true;

            // Read: node_id length sequence
            if (fscanf(fp, "%u %hu %s", &node->node_id, &node->length, node->sequence) != 3) {
                fprintf(stderr, "Error: Failed to read node %d\n", i);
                fclose(fp);
                return false;
            }

            // Read in-neighbors: num_in neighbor_ids...
            if (fscanf(fp, "%hhu", &node->num_in_neighbors) != 1) {
                fprintf(stderr, "Error: Failed to read num_in_neighbors for node %u\n", node->node_id);
                fclose(fp);
                return false;
            }
            for (int j = 0; j < node->num_in_neighbors; j++) {
                if (fscanf(fp, "%u", &node->in_neighbors[j]) != 1) {
                    fprintf(stderr, "Error: Failed to read in_neighbor %d for node %u\n", j, node->node_id);
                    fclose(fp);
                    return false;
                }
            }

            // Read out-neighbors: num_out neighbor_ids...
            if (fscanf(fp, "%hhu", &node->num_out_neighbors) != 1) {
                fprintf(stderr, "Error: Failed to read num_out_neighbors for node %u\n", node->node_id);
                fclose(fp);
                return false;
            }
            for (int j = 0; j < node->num_out_neighbors; j++) {
                if (fscanf(fp, "%u", &node->out_neighbors[j]) != 1) {
                    fprintf(stderr, "Error: Failed to read out_neighbor %d for node %u\n", j, node->node_id);
                    fclose(fp);
                    return false;
                }
            }

            num_nodes++;
        }

        fclose(fp);
        printf("Graph loaded: %d nodes from '%s'\n", num_nodes, filename);
        return true;
    }

    // Hardcoded initialization for verification graph (5 nodes from call #1)
    void initHardcodedGraph() {
        num_nodes = 5;

        // Node 69816: Length=64
        nodes[0].node_id = 69816;
        nodes[0].length = 64;
        strcpy(nodes[0].sequence, "TTTGTATGATTTCAATCTTTTAAAATTTATTGTCCAGGTACGGTTGCTCACACCTGTAATCCCA");
        nodes[0].num_in_neighbors = 2;
        nodes[0].in_neighbors[0] = 69819;
        nodes[0].in_neighbors[1] = 69820;
        nodes[0].num_out_neighbors = 1;
        nodes[0].out_neighbors[0] = 69817;
        nodes[0].valid = true;

        // Node 69819: Length=1, Seq=C
        nodes[1].node_id = 69819;
        nodes[1].length = 1;
        strcpy(nodes[1].sequence, "C");
        nodes[1].num_in_neighbors = 1;
        nodes[1].in_neighbors[0] = 69831;
        nodes[1].num_out_neighbors = 1;
        nodes[1].out_neighbors[0] = 69816;
        nodes[1].valid = true;

        // Node 69820: Length=1, Seq=T
        nodes[2].node_id = 69820;
        nodes[2].length = 1;
        strcpy(nodes[2].sequence, "T");
        nodes[2].num_in_neighbors = 1;
        nodes[2].in_neighbors[0] = 69831;
        nodes[2].num_out_neighbors = 1;
        nodes[2].out_neighbors[0] = 69816;
        nodes[2].valid = true;

        // Node 69830: Length=64
        nodes[3].node_id = 69830;
        nodes[3].length = 64;
        strcpy(nodes[3].sequence, "TTGAGTGTGTTTTTAATTTTCACATATTCGTGAATTATCTTGGTTTTCTTCTATTGATTTCTAG");
        nodes[3].num_in_neighbors = 1;
        nodes[3].in_neighbors[0] = 69829;
        nodes[3].num_out_neighbors = 1;
        nodes[3].out_neighbors[0] = 69831;
        nodes[3].valid = true;

        // Node 69831: Length=28
        nodes[4].node_id = 69831;
        nodes[4].length = 28;
        strcpy(nodes[4].sequence, "CTTCATTCCATTTTAGTCAGAGAAGGTA");
        nodes[4].num_in_neighbors = 1;
        nodes[4].in_neighbors[0] = 69830;
        nodes[4].num_out_neighbors = 2;
        nodes[4].out_neighbors[0] = 69819;
        nodes[4].out_neighbors[1] = 69820;
        nodes[4].valid = true;

        printf("Hardcoded verification graph initialized: 5 nodes (69816, 69819, 69820, 69830, 69831)\n");
    }
};

// Global graph structure
static Graph graphStructure;

// ==== DNA Encoding Utility ====
// Convert DNA character to 2-bit encoding: A=00, C=01, G=10, T=11
inline uint8_t encodeDNABase(char base) {
    switch (base) {
        case 'A': case 'a': return 0;
        case 'C': case 'c': return 1;
        case 'G': case 'g': return 2;
        case 'T': case 't': return 3;
        default: return 0;  // Default to A for invalid bases
    }
}

// Decode 2-bit value back to DNA character
inline char decodeDNABase(uint8_t encoded) {
    const char bases[] = {'A', 'C', 'G', 'T'};
    return bases[encoded & 0x3];
}

// ==== Priority Queue for Graph Alignment ====
#define MAX_QUEUE_SIZE 20
#define MAX_QUEUE_NEIGHBORS 10

// Flag bit positions for QueueEntry.flags
#define FLAG_SKIP_FIRST           0  // Bit 0: skip_first (1 = from previous slice, 0 = from neighbor)
#define FLAG_PREV_SLICE_EXISTS    1  // Bit 1: previousSliceExists
#define FLAG_CURR_SLICE_EXISTS    2  // Bit 2: currentSliceExists
// Bits 3-7: Reserved for future use

struct QueueEntry {
    uint32_t target_node;        // Node ID to process (lookup in graphStructure)
    int32_t  priority;           // Priority (lower = process first)
    uint32_t spm_addr;           // SPM address where slice data (VP, VN, scoreEnd) stored

    // Packed control flags (8 bits total)
    // Bit 0: skip_first (1 = from previous slice, 0 = from neighbor)
    // Bit 1: previousSliceExists
    // Bit 2: currentSliceExists
    // Bits 3-7: Reserved
    uint8_t  flags;

    // DNA sequence chunk (16 basepairs, 2 bits each)
    // Encoding: A=00, C=01, G=10, T=11
    // Example: 0x12 = [A,T,C,A] = [00,11,01,00] (LSB first)
    uint32_t basepairs;          // Stores up to 16 bases

    // Out-neighbors for propagation (stored directly for fast access)
    uint32_t out_neighbors[MAX_QUEUE_NEIGHBORS];
    uint8_t  num_out_neighbors;  // Number of valid out-neighbors (0 to MAX_QUEUE_NEIGHBORS)

    QueueEntry() : target_node(0), priority(0), spm_addr(0),
                   flags(0), basepairs(0), num_out_neighbors(0) {
        memset(out_neighbors, 0, sizeof(out_neighbors));
    }

    bool operator>(const QueueEntry& other) const {
        return priority > other.priority;  // Min-heap: lower priority comes first
    }

    // === Flag Helper Methods ===

    // Set a specific flag bit
    inline void setFlag(uint8_t bit_position) {
        flags |= (1 << bit_position);
    }

    // Clear a specific flag bit
    inline void clearFlag(uint8_t bit_position) {
        flags &= ~(1 << bit_position);
    }

    // Get a specific flag bit (returns 0 or 1)
    inline uint8_t getFlag(uint8_t bit_position) const {
        return (flags >> bit_position) & 1;
    }

    // Set flag to specific value (0 or 1)
    inline void updateFlag(uint8_t bit_position, bool value) {
        if (value) {
            setFlag(bit_position);
        } else {
            clearFlag(bit_position);
        }
    }

    // === Convenience accessors for specific flags ===

    inline void setSkipFirst(bool value) { updateFlag(FLAG_SKIP_FIRST, value); }
    inline bool getSkipFirst() const { return getFlag(FLAG_SKIP_FIRST); }

    inline void setPrevSliceExists(bool value) { updateFlag(FLAG_PREV_SLICE_EXISTS, value); }
    inline bool getPrevSliceExists() const { return getFlag(FLAG_PREV_SLICE_EXISTS); }

    inline void setCurrSliceExists(bool value) { updateFlag(FLAG_CURR_SLICE_EXISTS, value); }
    inline bool getCurrSliceExists() const { return getFlag(FLAG_CURR_SLICE_EXISTS); }

    // Set a basepair at specific position (0-15)
    void setBasepair(int pos, char base) {
        if (pos >= 0 && pos < 16) {
            uint8_t encoded = encodeDNABase(base);
            uint32_t mask = ~(0x3 << (pos * 2));  // Clear 2 bits at position
            basepairs = (basepairs & mask) | (encoded << (pos * 2));
        }
    }

    // Get basepair at specific position (0-15)
    char getBasepair(int pos) const {
        if (pos >= 0 && pos < 16) {
            uint8_t encoded = (basepairs >> (pos * 2)) & 0x3;
            return decodeDNABase(encoded);
        }
        return 'A';
    }
};

struct PriorityQueue {
    QueueEntry entries[MAX_QUEUE_SIZE];
    int size;

    PriorityQueue() : size(0) {}

    void clear() {
        size = 0;
    }

    bool empty() const {
        return size == 0;
    }

    bool full() const {
        return size >= MAX_QUEUE_SIZE;
    }

    // Insert with priority ordering (min-heap: lowest priority at index 0)
    bool insert(const QueueEntry& entry) {
        if (full()) return false;

        // Find insertion position (sorted insert)
        int pos = size;
        while (pos > 0 && entries[pos - 1].priority > entry.priority) {
            entries[pos] = entries[pos - 1];  // Shift right
            pos--;
        }

        // Insert at position
        entries[pos] = entry;
        size++;
        return true;
    }

    // Convenience insert with basic parameters
    bool insert(uint32_t target, int32_t priority, uint32_t spm_addr, uint8_t skip_first) {
        QueueEntry entry;
        entry.target_node = target;
        entry.priority = priority;
        entry.spm_addr = spm_addr;
        entry.skip_first = skip_first;
        entry.force_calc = 0;
        entry.first_calc = 0;
        entry.basepairs = 0;
        entry.num_out_neighbors = 0;
        return insert(entry);
    }

    // Get top (lowest priority) without removing
    QueueEntry top() const {
        if (empty()) return QueueEntry();
        return entries[0];
    }

    // Remove top element
    bool pop() {
        if (empty()) return false;

        // Shift all elements left
        for (int i = 0; i < size - 1; i++) {
            entries[i] = entries[i + 1];
        }
        size--;
        return true;
    }
};

// Global priority queue for graph alignment
static PriorityQueue graphAlignQueue;

PerfCounter bankConflictStalls = 0;
PerfCounter totalSpmRequests = 0;
PerfCounter lsqFullStalls = 0;
PerfCounter peHalted = 0;
PerfCounter forwardableBankConflict = 0;
PerfCounter controllerSpinCycles = 0;

pe_array::pe_array(int input_size, int output_size) {

    int i;
    input_buffer_size = input_size;
    output_buffer_size = output_size;

    input_buffer = (int*)calloc(input_buffer_size, sizeof(int));
    output_buffer = (int*)calloc(output_buffer_size, sizeof(int));
    s2 = new S2(S2_BUFFER_INTS);
    lsq = new CtrlLSQ();

    main_addressing_register[0] = 0;
    main_PC = 0;
    //+1 allows addressing full range. 1 is dummy data. Not legal in real hardware
    SPM_unit = new SPM(SPM_ADDR_NUM+1, &active_event_producers);
    for (i = 0; i < PE_NUM; i++)
        pe_unit[i] = new pe(i, SPM_unit);
    load_data = 0;
    store_data = 0;
    from_fifo = 0;
    compute_reg_names = nullptr;

    // Initialize hardcoded verification graph
    graphStructure.initHardcodedGraph();
}

pe_array::~pe_array() {
    int i;
    free(input_buffer);
    free(output_buffer);
    delete s2;
    delete lsq;
    for (i = 0; i < PE_NUM; i++)
        delete pe_unit[i];
    delete SPM_unit;
}

void pe_array::buffer_reset(int* buffer, int num) {
    int i;
    for (i = 0; i < num; i++)
        buffer[i] = 0;
}

void pe_array::write_spm_magic(int addr, int value) {
    if (addr < 0 || addr >= SPM_ADDR_NUM) {
        fprintf(stderr, "write_spm_magic addr %d out of range.\n", addr);
        exit(-1);
    }
    SPM_unit->buffer[addr] = value;
}



void pe_array::write_s2(int addr, int value) {
    if (addr < 0 || addr >= s2->buffer_size) {
        fprintf(stderr, "write_s2 addr %d out of range.\n", addr);
        exit(-1);
    }
    s2->buffer[addr] = value;
}

void pe_array::input_buffer_write_from_ddr(int addr, int* data) {

    if (addr >= 0 && addr < input_buffer_size) {
        input_buffer[addr] = *data;
    } else {
        fprintf(stderr, "data buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::input_buffer_write_from_ddr_unsigned(int addr, unsigned int* data) {

    if (addr >= 0 && addr < input_buffer_size) {
        input_buffer[addr] = *data;
    } else {
        fprintf(stderr, "data buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::compute_instruction_buffer_write_from_ddr(int addr, unsigned long data[]) {

    if (addr >= 0 && addr < COMP_INSTR_BUFFER_GROUP_NUM) {
        compute_instruction_buffer[addr][0] = data[0];
        compute_instruction_buffer[addr][1] = data[1];
    } else {
        fprintf(stderr, "PE instruction buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::main_instruction_buffer_write_from_ddr(int addr, unsigned long data[]) {

    if (addr >= 0 && addr < CTRL_INSTR_BUFFER_NUM) {
        main_instruction_buffer[addr][0] = data[0];
        main_instruction_buffer[addr][1] = data[1];
    } else {
        fprintf(stderr, "main instruction buffer write addr %d is out of bound\n", addr);
        exit(-1);
    }
}

void pe_array::pe_instruction_buffer_write_from_ddr(int addr, unsigned long data[], int id) {

    pe_unit[id]->ctrl_instr_load_from_ddr(addr, data);

};

void pe_array::pe_comp_instruction_buffer_write_from_ddr(int n_instr, unsigned long* data, int id) {

    pe_unit[id]->comp_instr_load_from_ddr(n_instr, data);

};


LoadResult pe_array::load(int source_pos, int reg_immBar_flag, int rs1, int rs2, int simd) {

    LoadResult data{};
    int source_addr = 0;
    
    if (reg_immBar_flag) source_addr = main_addressing_register[rs1] + main_addressing_register[rs2];
    else source_addr = rs1 + main_addressing_register[rs2];


// #ifdef DEBUG
//     printf("src: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d src_addr: %d\n", source_pos, reg_immBar_flag, rs1, main_addressing_register[rs2], source_addr);
// #endif

    if (source_pos == 1) {
        data.data[0] = main_addressing_register[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from main addr reg[%d] to ", data.data[0], source_addr);
    else
        printf("%d from main addr reg[%d] to ", data.data[0], source_addr);
#endif
    } else if (source_pos == CTRL_SPM) {
        if (source_addr >= 0 && source_addr < SPM_unit->buffer_size) {
            data.data[0] = SPM_unit->buffer[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from SPM[%d] to ", data.data[0], source_addr);
    else
        printf("%d from SPM[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load SPM addr %d error.\n", source_addr);
            exit(-1);
        }
    } else if (source_pos == CTRL_S2) {
        if (source_addr >= 0 && source_addr < s2->buffer_size) {
            data.data[0] = s2->buffer[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from S2[%d] to ", data.data[0], source_addr);
    else
        printf("%d from S2[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load S2 addr %d error.\n", source_addr);
            exit(-1);
        }
    } else if (source_pos == 3) {
        PE_instruction[0] = compute_instruction_buffer[source_addr][0];
        PE_instruction[1] = compute_instruction_buffer[source_addr][1];
#ifdef PROFILE
        printf("%lx %lx from main comp instr buffer[%d] to ", PE_instruction[0], PE_instruction[1], source_addr);
#endif
    } else if (source_pos == 5) {
        if (source_addr >= 0 && source_addr < input_buffer_size) {
            data.data[0] = input_buffer[source_addr];
#ifdef PROFILE
    if (simd)
        printf("%lx from input buffer[%d] to ", data.data[0], source_addr);
    else
        printf("%d from input buffer[%d] to ", data.data[0], source_addr);
#endif
        } else {
            fprintf(stderr, "main load input buffer addr %d error.\n", source_addr);
            exit(-1);
        }
    } else if (source_pos == 7) {
        data.data[0] = load_data;
#ifdef PROFILE
    if (simd)
        printf("%lx from last PE to ", data.data[0]);
    else
        printf("%d from last PE to ", data.data[0]);
#endif
    } else if (source_pos >= 11 && source_pos <=14) {
        data.data[0] = fifo_unit[0][source_pos - 11].pop();
        from_fifo = 1;
#ifdef PROFILE
    if (simd)
        printf("%lx from fifo[%d] to ", data.data[0], source_pos - 11);
    else {
        printf("%d from fifo[%d] to (size is %d)", data.data[0], source_pos - 11, fifo_unit[0][source_pos - 11].size());
        fifo_unit[0][source_pos - 11].show();
    }
#endif
    } else {
        fprintf(stderr, "source_pos error. source_pos = %d\n",source_pos);
        exit(-1);
    }
    return data;
}

void pe_array::store(int dest_pos, int reg_immBar_flag, int rs1, int rs2, LoadResult data, int simd) {

    int dest_addr = 0;

    if (reg_immBar_flag) dest_addr = main_addressing_register[rs1] + main_addressing_register[rs2];
    else dest_addr = rs1 + main_addressing_register[rs2];

// #ifdef DEBUG
//     printf("dest: %d reg_immBar_flag: %d reg_imm_1: %d reg_1: %d gr[reg_1]: %d dest_addr: %d\n", dest_pos, reg_immBar_flag, rs1, rs2, main_addressing_register[rs2], dest_addr);
// #endif

    if (dest_pos == 1) {
        main_addressing_register[dest_addr] = data.data[0];
        if (dest_addr == 0) printf("%d\n", data.data[0]);
#ifdef PROFILE
        printf("main addr register[%d].\n", dest_addr);
#endif
    } else if(dest_pos == CTRL_SPM) {
        if (dest_addr >= 0 && dest_addr < SPM_unit->buffer_size) {
            SPM_unit->buffer[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("SPM[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store SPM addr %d error.\n", dest_addr);
            exit(-1);
        }
    } else if(dest_pos == CTRL_S2) {
        if (dest_addr >= 0 && dest_addr < s2->buffer_size) {
            s2->buffer[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("S2[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store S2 addr %d error.\n", dest_addr);
            exit(-1);
        }
    } else if(dest_pos == 6) {
        if (dest_addr >= 0 && dest_addr < output_buffer_size) {
            output_buffer[dest_addr] = data.data[0];
#ifdef PROFILE
            printf("output buffer[%d].\n", dest_addr);
#endif
        } else {
            fprintf(stderr, "main store output buffer addr %d error.\n", dest_addr);
            exit(-1);
        }
    } else if (dest_pos == 9) {
        store_data = data.data[0];
#ifdef PROFILE
        printf("PE[0].\n");
#endif
    } else if (dest_pos >= 11 && dest_pos <= 14) {
        // fprintf(stderr, "fifo[0] ");
        fifo_unit[0][dest_pos - 11].push(data.data[0]);
#ifdef PROFILE
    printf("fifo[%d]. size is %d\n", dest_pos - 11, fifo_unit[0][dest_pos - 11].size());
    fifo_unit[0][dest_pos - 11].show();
#endif
    }
}

int pe_array::decode(unsigned long instruction, int* PC, int simd, int setting, int main_instruction_setting) {
#ifdef PROFILE
    // printf("main j=%d\t", main_addressing_register[12]);
    // printf("main j=%d\t", main_addressing_register[4]);
    printf("main i=%d j=%d\t", main_addressing_register[8]/20 - 1, main_addressing_register[5]);
#endif

    // pe_array position:   
    // src - 1/3/4/5/6/7/10
    // dest - 1/3/4/5/6/8/9
    // 0 - Compute register
    // 1 - Addressing register
    // 2 - Scratchpad memory
    // 3-6 FIFO[0-3]
    // 7 - Input buffer
    // 8 - Output buffer
    // 9 - In data port
    // 10 - Out data port
    // 11 - imm
    // 12 - none
    if (instruction == 0x20f7800000000) {
        fprintf(stderr, "WARNING: PE_ARRAY PC=%d cycle=%d executing uninitialized instruction.\n", *PC, cycle);
    }

    int i, rd, rs1, rs2, imm, comp_0 = 0, comp_1 = 0, sum = 0, add_a = 0, add_b = 0;
    LoadResult data{};

    int8_t rs[4];
        
    unsigned long dest_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long src_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long reg_immBar_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    unsigned long reg_auto_increasement_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    unsigned long reg_imm_0_sign_bit_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    unsigned long reg_imm_0_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_0_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_immBar_flag_1_mask = (unsigned long)1 << (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_auto_increasement_flag_1_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_imm_1_sign_bit_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    unsigned long reg_imm_1_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_1_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << CTRL_OPCODE_WIDTH;
    unsigned long opcode_mask = (unsigned long)((1 << CTRL_OPCODE_WIDTH) - 1);
    unsigned long magic_mask = (unsigned long)((1ul << (63)));
    unsigned long magic_payload_mask = (unsigned long)(0xFFFFFFFF);

    int dest = (instruction & dest_mask) >> (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    int src = (instruction & src_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    int reg_immBar_flag_0 = (instruction & reg_immBar_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    int reg_auto_increasement_flag_0 = (instruction & reg_auto_increasement_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    int reg_imm_0 = (instruction & reg_imm_0_mask) >> (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_0_sign_bit = (instruction & reg_imm_0_sign_bit_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    int imm_sign_extend_mask = ~((1 << IMMEDIATE_WIDTH) - 1);
    int sext_imm_0 = reg_imm_0 | (reg_imm_0_sign_bit ? imm_sign_extend_mask : 0);
    int reg_0 = (instruction & reg_0_mask) >> (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_immBar_flag_1 = (instruction & reg_immBar_flag_1_mask) >> (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_auto_increasement_flag_1 = (instruction & reg_auto_increasement_flag_1_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1 = (instruction & reg_imm_1_mask) >> (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1_sign_bit = (instruction & reg_imm_1_sign_bit_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    int sext_imm_1 = reg_imm_1 | (reg_imm_1_sign_bit ? imm_sign_extend_mask : 0);
    int reg_1 = (instruction & reg_1_mask) >> CTRL_OPCODE_WIDTH;
    int opcode = instruction & opcode_mask;

    bool is_magic = (instruction & magic_mask);
    int  magic_payload = instruction & magic_payload_mask;

#ifdef PROFILE
    printf("PC = %d @%d:%016lx\t", *PC, cycle, instruction);
#endif
    if (main_instruction_setting == MAIN_INSTRUCTION_2) {
        if (((opcode == 4 || opcode == 5) && (dest == 5 || dest == 6 || dest == 11 || dest == 12 || dest == 13 || dest == 14)) || opcode == 14) {
            (*PC)++;
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    } else if (main_instruction_setting == MAIN_INSTRUCTION_1) {
        if (dest == 5 || dest == 6 || dest == 11 || dest == 12 || dest == 13 || dest == 14) {
            (*PC)++;
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    }

// #ifdef DEBUG
//     printf("dest: %d src: %d reg_immBar_flag_0: %d reg_auto_increasement_flag_0: %d reg_imm_0_sign_bit: %d sext_imm_0: %d, reg_0: %d reg_immBar_flag_1: %d reg_auto_increasement_flag_1: %d reg_imm_1_sign_bit: %d sext_imm_1: %d reg_1: %d opcode: %d\n", dest, src, reg_immBar_flag_0, reg_auto_increasement_flag_0, reg_imm_0_sign_bit, sext_imm_0, reg_0, reg_immBar_flag_1, reg_auto_increasement_flag_1, reg_imm_1_sign_bit, sext_imm_1, reg_1, opcode);
// #endif

if (is_magic) {
    // Magic instruction: Preload equality vectors into PE0 SPM
    // Payload value can be used to select different magic operations

    if (magic_payload == 1) {
        // Magic payload 1: Load equality vectors into PE0 SPM slots 0-3
        // TODO: Replace these hardcoded values with your actual equality vectors
        SPM_unit->access_magic(0, 0) = 553914624;  // PE0 SPM[0] BA
        SPM_unit->access_magic(0, 1) = 412155976;  // PE0 SPM[1] BT
        SPM_unit->access_magic(0, 2) = 526336;  // PE0 SPM[2] BC
        SPM_unit->access_magic(0, 3) = 3328370359;  // PE0 SPM[3] BG

        // Initialize extraSlice values at SPM[100-104]
        // extraSlice.VN = 0x0000000000000001
        SPM_unit->access_magic(0, 100) = 1;           // VN_lo = 1
        SPM_unit->access_magic(0, 101) = 0;           // VN_hi = 0

        // extraSlice.VP = 0x9249249249249252 (10540996613550711954)
        SPM_unit->access_magic(0, 102) = 1229530258;  // VP_lo = 0x49249252
        SPM_unit->access_magic(0, 103) = 2454267026;  // VP_hi = 0x92492492

        // extraSlice.scoreEnd = 22
        SPM_unit->access_magic(0, 104) = 22;          // scoreEnd

#ifdef PROFILE
        printf("Magic instruction (payload=%d): Loaded equality vectors into PE0 SPM[0-3]\n", magic_payload);
        printf("  Initialized extraSlice into SPM[100-104]:\n");
        printf("    SPM[100] = VN_lo = 1\n");
        printf("    SPM[101] = VN_hi = 0\n");
        printf("    SPM[102] = VP_lo = 1229530258 (0x49249252)\n");
        printf("    SPM[103] = VP_hi = 2454267026 (0x92492492)\n");
        printf("    SPM[104] = scoreEnd = 22\n");
#endif
    }
    else if (magic_payload == 2) {
        // Magic payload 2: Initialize/clear priority queue
        graphAlignQueue.clear();

#ifdef PROFILE
        printf("Magic instruction (payload=%d): Queue cleared\n", magic_payload);
#endif
    }
    else if (magic_payload == 3) {
        // Magic payload 3: Insert into priority queue
        // Input from addressing registers:
        //   gr[0] = target_node (ID in graph)
        //   gr[1] = priority
        //   gr[2] = spm_addr (where VP/VN/scoreEnd stored)
        //   gr[3] = flags (8-bit packed: bit0=skip_first, bit1=prevSliceExists, bit2=currSliceExists)
        //   gr[4] = basepairs (32-bit, 16 bases encoded)
        // Output:
        //   gr[5] = success (1 = inserted, 0 = queue full)
        //   gr[6] = num_out_neighbors (number of neighbors loaded)
        QueueEntry entry;
        entry.target_node = main_addressing_register[0];
        entry.priority = main_addressing_register[1];
        entry.spm_addr = main_addressing_register[2];
        entry.flags = (uint8_t)main_addressing_register[3];  // Load all flags at once
        entry.basepairs = main_addressing_register[4];

        // Automatically populate out-neighbors from graph
        GraphNode* node = graphStructure.getNode(entry.target_node);
        if (node) {
            entry.num_out_neighbors = (node->num_out_neighbors < MAX_QUEUE_NEIGHBORS)
                                      ? node->num_out_neighbors
                                      : MAX_QUEUE_NEIGHBORS;
            for (int i = 0; i < entry.num_out_neighbors; i++) {
                entry.out_neighbors[i] = node->out_neighbors[i];
            }
        } else {
            entry.num_out_neighbors = 0;
        }

        bool success = graphAlignQueue.insert(entry);
        main_addressing_register[5] = success ? 1 : 0;
        main_addressing_register[6] = entry.num_out_neighbors;

#ifdef PROFILE
        if (node) {
            printf("Magic instruction (payload=%d): Queue insert node=%u len=%u prio=%d spm=%u flags=0x%02X (skip=%u prev=%u curr=%u) neighbors=%u -> %s\n",
                   magic_payload, entry.target_node, node->length, entry.priority,
                   entry.spm_addr, entry.flags, entry.getSkipFirst(), entry.getPrevSliceExists(),
                   entry.getCurrSliceExists(), entry.num_out_neighbors, success ? "OK" : "FULL");
        } else {
            printf("Magic instruction (payload=%d): Queue insert node=%u (NOT IN GRAPH) prio=%d spm=%u flags=0x%02X -> %s\n",
                   magic_payload, entry.target_node, entry.priority,
                   entry.spm_addr, entry.flags, success ? "OK" : "FULL");
        }
#endif
    }
    else if (magic_payload == 4) {
        // Magic payload 4: Pop from priority queue
        bool success = graphAlignQueue.pop();

        // Store result in gr[4]: 1 = success, 0 = queue empty
        main_addressing_register[4] = success ? 1 : 0;

#ifdef PROFILE
        printf("Magic instruction (payload=%d): Queue pop -> %s\n",
               magic_payload, success ? "OK" : "EMPTY");
#endif
    }
    else if (magic_payload == 5) {
        // Magic payload 5: Get top element (peek without removing)
        // Output to addressing registers:
        //   gr[0] = target_node
        //   gr[1] = priority
        //   gr[2] = spm_addr
        //   gr[3] = flags (8-bit packed)
        //   gr[4] = basepairs (32-bit)
        //   gr[5] = valid (1 if queue not empty, 0 if empty)
        //   gr[6] = num_out_neighbors
        if (!graphAlignQueue.empty()) {
            QueueEntry top = graphAlignQueue.top();
            main_addressing_register[0] = top.target_node;
            main_addressing_register[1] = top.priority;
            main_addressing_register[2] = top.spm_addr;
            main_addressing_register[3] = top.flags;  // Return all flags at once
            main_addressing_register[4] = top.basepairs;
            main_addressing_register[5] = 1;  // valid
            main_addressing_register[6] = top.num_out_neighbors;

#ifdef PROFILE
            GraphNode* node = graphStructure.getNode(top.target_node);
            if (node) {
                printf("Magic instruction (payload=%d): Queue top -> node=%u len=%u prio=%d spm=%u flags=0x%02X (skip=%u prev=%u curr=%u) neighbors=%u\n",
                       magic_payload, top.target_node, node->length, top.priority,
                       top.spm_addr, top.flags, top.getSkipFirst(), top.getPrevSliceExists(),
                       top.getCurrSliceExists(), top.num_out_neighbors);
            } else {
                printf("Magic instruction (payload=%d): Queue top -> node=%u prio=%d spm=%u flags=0x%02X neighbors=%u\n",
                       magic_payload, top.target_node, top.priority, top.spm_addr, top.flags, top.num_out_neighbors);
            }
#endif
        } else {
            main_addressing_register[5] = 0;  // invalid (queue empty)
            main_addressing_register[6] = 0;

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Queue top -> EMPTY\n", magic_payload);
#endif
        }
    }
    else if (magic_payload == 6) {
        // Magic payload 6: Get queue size
        // Output to gr[0]
        main_addressing_register[0] = graphAlignQueue.size;

#ifdef PROFILE
        printf("Magic instruction (payload=%d): Queue size = %d\n", magic_payload, graphAlignQueue.size);
#endif
    }
    else if (magic_payload == 7) {
        // Magic payload 7: Get in-neighbor ID by index
        // Input:
        //   gr[0] = node_id
        //   gr[1] = neighbor_index (0 to num_in_neighbors-1)
        // Output:
        //   gr[2] = neighbor_id
        //   gr[4] = valid (1 if found, 0 if not)
        uint32_t node_id = main_addressing_register[0];
        int neighbor_idx = main_addressing_register[1];
        GraphNode* node = graphStructure.getNode(node_id);

        if (node && neighbor_idx >= 0 && neighbor_idx < node->num_in_neighbors) {
            main_addressing_register[2] = node->in_neighbors[neighbor_idx];
            main_addressing_register[4] = 1;  // valid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u in_neighbor[%d]=%u\n",
                   magic_payload, node_id, neighbor_idx, node->in_neighbors[neighbor_idx]);
#endif
        } else {
            main_addressing_register[4] = 0;  // invalid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u in_neighbor[%d] -> INVALID\n",
                   magic_payload, node_id, neighbor_idx);
#endif
        }
    }
    else if (magic_payload == 8) {
        // Magic payload 8: Get node info
        // Input: gr[0] = node_id
        // Output:
        //   gr[1] = length
        //   gr[2] = num_in_neighbors
        //   gr[3] = num_out_neighbors
        //   gr[4] = valid (1 if found, 0 if not)
        uint32_t node_id = main_addressing_register[0];
        GraphNode* node = graphStructure.getNode(node_id);

        if (node) {
            main_addressing_register[1] = node->length;
            main_addressing_register[2] = node->num_in_neighbors;
            main_addressing_register[3] = node->num_out_neighbors;
            main_addressing_register[4] = 1;  // valid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u -> len=%u in=%u out=%u\n",
                   magic_payload, node_id, node->length, node->num_in_neighbors, node->num_out_neighbors);
#endif
        } else {
            main_addressing_register[4] = 0;  // not found

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u -> NOT FOUND\n",
                   magic_payload, node_id);
#endif
        }
    }
    else if (magic_payload == 9) {
        // Magic payload 9: Get node sequence base
        // Input:
        //   gr[0] = node_id
        //   gr[1] = position
        // Output:
        //   gr[2] = base (ASCII 'A', 'C', 'G', 'T')
        //   gr[4] = valid
        uint32_t node_id = main_addressing_register[0];
        int pos = main_addressing_register[1];
        GraphNode* node = graphStructure.getNode(node_id);

        if (node && pos < node->length) {
            main_addressing_register[2] = (uint32_t)node->sequence[pos];
            main_addressing_register[4] = 1;  // valid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u seq[%d]='%c'\n",
                   magic_payload, node_id, pos, node->sequence[pos]);
#endif
        } else {
            main_addressing_register[4] = 0;  // invalid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u seq[%d] -> INVALID\n",
                   magic_payload, node_id, pos);
#endif
        }
    }
    else if (magic_payload == 10) {
        // Magic payload 10: Get out-neighbor ID by index
        // Input:
        //   gr[0] = node_id
        //   gr[1] = neighbor_index (0 to num_out_neighbors-1)
        // Output:
        //   gr[2] = neighbor_id
        //   gr[4] = valid (1 if found, 0 if not)
        uint32_t node_id = main_addressing_register[0];
        int neighbor_idx = main_addressing_register[1];
        GraphNode* node = graphStructure.getNode(node_id);

        if (node && neighbor_idx >= 0 && neighbor_idx < node->num_out_neighbors) {
            main_addressing_register[2] = node->out_neighbors[neighbor_idx];
            main_addressing_register[4] = 1;  // valid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u out_neighbor[%d]=%u\n",
                   magic_payload, node_id, neighbor_idx, node->out_neighbors[neighbor_idx]);
#endif
        } else {
            main_addressing_register[4] = 0;  // invalid

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Get node=%u out_neighbor[%d] -> INVALID\n",
                   magic_payload, node_id, neighbor_idx);
#endif
        }
    }
    else if (magic_payload == 11) {
        // Magic payload 11: Get out-neighbor from top queue entry by index
        // Input:
        //   gr[0] = neighbor_index (0 to num_out_neighbors-1)
        // Output:
        //   gr[1] = neighbor_node_id
        //   gr[2] = valid (1 if found, 0 if not)
        if (!graphAlignQueue.empty()) {
            QueueEntry top = graphAlignQueue.top();
            int neighbor_idx = main_addressing_register[0];

            if (neighbor_idx >= 0 && neighbor_idx < top.num_out_neighbors) {
                main_addressing_register[1] = top.out_neighbors[neighbor_idx];
                main_addressing_register[2] = 1;  // valid

#ifdef PROFILE
                printf("Magic instruction (payload=%d): Queue top out_neighbor[%d]=%u\n",
                       magic_payload, neighbor_idx, top.out_neighbors[neighbor_idx]);
#endif
            } else {
                main_addressing_register[2] = 0;  // invalid index

#ifdef PROFILE
                printf("Magic instruction (payload=%d): Queue top out_neighbor[%d] -> INVALID (count=%u)\n",
                       magic_payload, neighbor_idx, top.num_out_neighbors);
#endif
            }
        } else {
            main_addressing_register[2] = 0;  // queue empty

#ifdef PROFILE
            printf("Magic instruction (payload=%d): Queue top out_neighbor -> QUEUE EMPTY\n", magic_payload);
#endif
        }
    }

    (*PC)++;
    return 0;
}

    
    else if (opcode == 0) {              // add rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        *get_output_dest(dest, rd) = sum;
#ifdef PROFILE
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 1) {       // sub rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a - add_b;
        *get_output_dest(dest,rd) = sum;
#ifdef PROFILE
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 2) {       // addi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = imm;
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        *get_output_dest(dest,rd) = sum;
#ifdef PROFILE
        printf("addi gr[%d] %d gr[%d] (%d %d %d)\n", rd, imm, rs2, sum, add_a, add_b);
#endif
        (*PC)++;
    } else if (opcode == 3) {       // set_8 rd rs2
        rd = reg_imm_0;
        rs2 = reg_1;
        memcpy(rs, &main_addressing_register[rs2], 4*sizeof(int8_t));

        for (i = 0; i < 4; i++) {
            rs[i] = main_addressing_register[rs2] & 0xFF;
        }
        memcpy(get_output_dest(dest,rd), rs, 4*sizeof(int8_t));
#ifdef PROFILE
        printf("set_8 gr[%d] gr[%d] (%d %lx)\n", rd, rs2, main_addressing_register[rs2], main_addressing_register[rd]);
#endif
        (*PC)++;
    } else if (opcode == 4) {       // si dest imm/reg(reg(++))
#ifdef PROFILE
    if (simd)
        printf("Store %lx to ", sext_imm_1);
    else
        printf("Store %d to ", sext_imm_1);
#endif
        LoadResult immediate_data{};
        immediate_data.data[0] = sext_imm_1;
        store(dest, reg_immBar_flag_0, sext_imm_0, reg_0, immediate_data, simd);
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        (*PC)++;
    } else if (opcode == 5) {       // mv dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("Move ");
#endif
        if (src == CTRL_S2 && dest == CTRL_SPM) {
            int s2Addr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int spmAddr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            if (lsq->spmBankFull(spmAddr) ||
                lsq->s2BankFull(s2Addr)) {
                lsqFullStalls++;
                return 0;
            }
#ifdef PROFILE
            printf("S2[%d] -> SPM[%d] via LSQ\n",
                   s2Addr, spmAddr);
#endif
            lsq->enqueueS2ToSpm(
                s2Addr, spmAddr, true);
        } else if (src == CTRL_SPM && dest == CTRL_S2) {
            int spmAddr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int s2Addr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            if (lsq->spmBankFull(spmAddr) ||
                lsq->s2BankFull(s2Addr)) {
                lsqFullStalls++;
                return 0;
            }
#ifdef PROFILE
            printf("SPM[%d] -> S2[%d] via LSQ\n",
                   spmAddr, s2Addr);
#endif
            lsq->enqueueSpmToS2(
                spmAddr, s2Addr, true);
        } else {
            data = load(src, reg_immBar_flag_1,
                        sext_imm_1, reg_1, simd);
            store(dest, reg_immBar_flag_0,
                  sext_imm_0, reg_0, data, simd);
        }
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1]++;
        (*PC)++;
    } else if (opcode == CTRL_MVDQ) {      // mvdq dest src imm/reg(reg(++)) imm/reg(reg(++))
#ifdef PROFILE
        printf("MoveDoubleQuad ");
#endif
        int dest_addr = 0;
        int src_addr = 0;
        if (reg_immBar_flag_0)
            dest_addr = main_addressing_register[sext_imm_0] + main_addressing_register[reg_0];
        else
            dest_addr = sext_imm_0 + main_addressing_register[reg_0];
        if (reg_immBar_flag_1)
            src_addr = main_addressing_register[sext_imm_1] + main_addressing_register[reg_1];
        else
            src_addr = sext_imm_1 + main_addressing_register[reg_1];

        bool src_is_spm = (src == CTRL_SPM);
        bool src_is_s2 = (src == CTRL_S2);
        bool dest_is_spm = (dest == CTRL_SPM);
        bool dest_is_s2 = (dest == CTRL_S2);

        if (!((src_is_spm && dest_is_s2) || (src_is_s2 && dest_is_spm))) {
            fprintf(stderr, "main mvdq only supports SPM <-> S2. src=%d dest=%d PC=%d\n", src, dest, *PC);
            exit(-1);
        }

        int src_limit = src_is_spm ? SPM_unit->buffer_size : s2->buffer_size;
        int dest_limit = dest_is_spm ? SPM_unit->buffer_size : s2->buffer_size;
        if (src_addr < 0 || src_addr + 8 > src_limit) {
            fprintf(stderr, "main mvdq src addr %d out of bounds (limit %d). PC=%d\n", src_addr, src_limit, *PC);
            exit(-1);
        }
        if (dest_addr < 0 || dest_addr + 8 > dest_limit) {
            fprintf(stderr, "main mvdq dest addr %d out of bounds (limit %d). PC=%d\n", dest_addr, dest_limit, *PC);
            exit(-1);
        }

        // Determine S2 and SPM side addresses
        int s2A = src_is_s2 ? src_addr : dest_addr;
        int spmA = dest_is_spm ? dest_addr:src_addr;
        bool s2ToSpm = src_is_s2 && dest_is_spm;
        bool srcOdd = src_addr % 2 != 0;
        bool dstOdd = dest_addr % 2 != 0;

        // Capacity check: compute all entry addrs.
        // Even side: 4 doubles. Odd side: sgl,3dbl,sgl
        int spmList[5], s2List[5];
        int nSpm = 0, nS2 = 0;
        if (spmA % 2 == 0) {
            for (i = 0; i < 4; i++)
                spmList[nSpm++] = spmA + 2*i;
        } else {
            spmList[nSpm++] = spmA;
            spmList[nSpm++] = spmA + 1;
            spmList[nSpm++] = spmA + 3;
            spmList[nSpm++] = spmA + 5;
            spmList[nSpm++] = spmA + 7;
        }
        if (s2A % 2 == 0) {
            for (i = 0; i < 4; i++)
                s2List[nS2++] = s2A + 2*i;
        } else {
            s2List[nS2++] = s2A;
            s2List[nS2++] = s2A + 1;
            s2List[nS2++] = s2A + 3;
            s2List[nS2++] = s2A + 5;
            s2List[nS2++] = s2A + 7;
        }
        if (!lsq->canEnqueue(
                spmList, nSpm, s2List, nS2)) {
            lsqFullStalls++;
            return 0;
        }

        // Helper lambdas for enqueue
        auto enqPaired = [&](int s2, int spm,
                             bool sd) {
            if (s2ToSpm)
                lsq->enqueueS2ToSpm(s2, spm, sd);
            else
                lsq->enqueueSpmToS2(spm, s2, sd);
        };

        if (!srcOdd && !dstOdd) {
            // Both even: 4 paired doubles
            for (i = 0; i < 4; i++)
                enqPaired(s2A + 2*i,
                          spmA + 2*i, false);

        } else if (srcOdd && dstOdd) {
            // Both odd: 5 paired (sgl,dbl,dbl,dbl,sgl)
            enqPaired(s2A, spmA, true);
            enqPaired(s2A+1, spmA+1, false);
            enqPaired(s2A+3, spmA+3, false);
            enqPaired(s2A+5, spmA+5, false);
            enqPaired(s2A+7, spmA+7, true);

        } else if (srcOdd && !dstOdd) {
            // src odd, dest even.
            // Writes: 4 doubles at even dest addrs.
            // Reads: 5 lines from odd source.
            // Create writes and reads separately
            // since srcDstAddr != read addr.
            if (s2ToSpm) {
                for (i = 0; i < 4; i++)
                    lsq->enqueueSpmWriteOnly(
                        spmA + 2*i,
                        s2A + 2*i, false);
                // 5 S2 reads covering all src lines
                for (i = 0; i < 4; i++)
                    lsq->enqueueS2ReadOnly(
                        s2A + 2*i);
                lsq->enqueueS2ReadOnly(s2A + 7);
            } else {
                for (i = 0; i < 4; i++)
                    lsq->enqueueS2WriteOnly(
                        s2A + 2*i,
                        spmA + 2*i, false);
                for (i = 0; i < 4; i++)
                    lsq->enqueueSpmReadOnly(
                        spmA + 2*i);
                lsq->enqueueSpmReadOnly(spmA + 7);
            }

        } else {
            // src even, dest odd.
            // Writes: 5 (sgl, dbl, dbl, dbl, sgl)
            //   at odd dest boundary addrs.
            // Reads: 4 doubles from even source.
            // Create separately.
            if (s2ToSpm) {
                lsq->enqueueSpmWriteOnly(
                    spmA, s2A, true);
                for (i = 0; i < 3; i++)
                    lsq->enqueueSpmWriteOnly(
                        spmA + 1 + 2*i,
                        s2A + 1 + 2*i, false);
                lsq->enqueueSpmWriteOnly(
                    spmA + 7, s2A + 7, true);
                for (i = 0; i < 4; i++)
                    lsq->enqueueS2ReadOnly(
                        s2A + 2*i);
            } else {
                lsq->enqueueS2WriteOnly(
                    s2A, spmA, true);
                for (i = 0; i < 3; i++)
                    lsq->enqueueS2WriteOnly(
                        s2A + 1 + 2*i,
                        spmA + 1 + 2*i, false);
                lsq->enqueueS2WriteOnly(
                    s2A + 7, spmA + 7, true);
                for (i = 0; i < 4; i++)
                    lsq->enqueueSpmReadOnly(
                        spmA + 2*i);
            }
        }

        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0] += 8;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1] += 8;
        (*PC)++;
    } else if (opcode == CTRL_MVDQI) {      // mvdqi dest imm/reg(reg(++)) imm
#ifdef PROFILE
        printf("MoveDoubleQuadImm ");
#endif
        int dest_addr = 0;
        if (reg_immBar_flag_0)
            dest_addr = main_addressing_register[sext_imm_0] + main_addressing_register[reg_0];
        else
            dest_addr = sext_imm_0 + main_addressing_register[reg_0];

        bool dest_is_spm = (dest == CTRL_SPM);
        bool dest_is_s2 = (dest == CTRL_S2);
        if (!(dest_is_spm || dest_is_s2)) {
            fprintf(stderr, "main mvdqi only supports SPM or S2 destinations. dest=%d PC=%d\n", dest, *PC);
            exit(-1);
        }

        int dest_limit = dest_is_spm ? SPM_unit->buffer_size : s2->buffer_size;
        if (dest_addr < 0 || dest_addr + 7 >= dest_limit) {
            fprintf(stderr, "main mvdqi dest addr %d out of bounds (limit %d). PC=%d\n", dest_addr, dest_limit, *PC);
            exit(-1);
        }

        int imm_val = sext_imm_1;
        if (dest_is_spm) {
            for (i = 0; i < 8; i++)
                SPM_unit->buffer[dest_addr + i] = imm_val;
        } else {
            for (i = 0; i < 8; i++)
                s2->buffer[dest_addr + i] = imm_val;
        }

        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0] += 8;
        (*PC)++;
//     } else if (opcode == 6) {       // add_8 rd rs1 rs2
//         rd = reg_imm_0;
//         rs1 = reg_imm_1;
//         rs2 = reg_1;
//         memcpy(rs, &main_addressing_register[rs1], 4 * sizeof(int8_t));
//         memcpy(rs_, &main_addressing_register[rs2], 4 * sizeof(int8_t));
//         for (i = 0; i < 4; i++) rd_[i] = rs[i] + rs_[i];
//         memcpy(&main_addressing_register[rd], rd_, 4 * sizeof(int8_t));
// #ifdef PROFILE
//         printf("add_8 gr[%d] gr[%d] gr[%d] (%lx %lx %lx)\n", rd, rs1, rs2, main_addressing_register[rd], main_addressing_register[rs1], main_addressing_register[rs2]);
// #endif
//         (*PC)++;
//     } else if (opcode == 7) {       // addi_8 rd imm rs2
//         rd = reg_imm_0;
//         rs2 = reg_1;
//         memcpy(rs_, &main_addressing_register[rs2], 4 * sizeof(int8_t));
//         for (i = 0; i < 4; i++) rd_[i] = reg_imm_1 && 0xFF + rs_[i];
//         memcpy(&main_addressing_register[rd], rd_, 4 * sizeof(int8_t));
// #ifdef PROFILE
//         printf("addi_8 gr[%d] %d gr[%d] (%lx %d %lx)\n", rd, sext_imm_1, rs2, main_addressing_register[rd], sext_imm_1, main_addressing_register[rs2]);
// #endif
//         (*PC)++;
    } else if (opcode == CTRL_BARRIER) {
        if (!lsq->hasPendingOps(SPM_unit, s2)) {
#ifdef PROFILE
            printf("Barrier: LSQ empty, advance\n");
#endif
            (*PC)++;
        }
#ifdef PROFILE
        else {
            printf("Barrier: LSQ stall\n");
        }
#endif
    } else if (opcode == 8) {       // bne rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
        if (rs2 == 13) controllerSpinCycles++;
#ifdef PROFILE
        printf("bne %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 != comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 9) {       // beq rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("beq %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 == comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 10) {       // bge rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("bge %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 >= comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 11) {       // blt rs1 rs2 offset
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("blt %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
#ifdef PROFILE
        printf(" (%d %d)", comp_0, comp_1);
#endif
        if (comp_0 < comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == CTRL_BLTU) {       // bltu rs1 rs2 offset (unsigned)
        rs1 = sext_imm_1;
        rs2 = reg_1;
#ifdef PROFILE
        printf("bltu %d %d %d", rs1, rs2, sext_imm_0);
#endif
        if (reg_immBar_flag_1) comp_0 = main_addressing_register[rs1];
        else comp_0 = sext_imm_1;
        comp_1 = main_addressing_register[rs2];
#ifdef PROFILE
        printf(" (%u %u)", (unsigned int)comp_0, (unsigned int)comp_1);
#endif
        if ((unsigned int)comp_0 < (unsigned int)comp_1) {
            *PC = *PC + sext_imm_0;
#ifdef PROFILE
            printf(" jump.\n");
#endif
        } else {
            (*PC)++;
#ifdef PROFILE
            printf(" not jump.\n");
#endif
        }
    } else if (opcode == 12) {      // jump
        *PC = *PC + sext_imm_0;
#ifdef PROFILE
        printf("jump %d\n", sext_imm_0);
#endif
    } else if (opcode == 13) {      // set PE_PC
        for (i = 0; i < setting; i++) {
            pe_unit[i]->PC[0] = sext_imm_0;
            pe_unit[i]->PC[1] = sext_imm_0;
        }
#ifdef PROFILE
        printf("set PE PC to %d.\n", sext_imm_0);
#endif
        (*PC)++;
    } else if (opcode == 14) {      // None
        (*PC)++;
#ifdef PROFILE
        printf("No-op.\n");
#endif
    } else if (opcode == 15) {      // halt
#ifdef PROFILE
        printf("halt.\n");
#endif
        return -1;
    } else if (opcode == CTRL_SHIFTI_R) {      // SHIFT_R
        //main_addressing_register
        //TODO is main_addressing_register the correct place to go?
        assert(dest == CTRL_GR);  // only support gr
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = main_addressing_register[rs2];
        //we want arithmetic shift right as below, but this is compiler dependent. Not in c++ std
        //int shift_result = operand1 >> reg_imm_1;
        //so instead of above, we do the following for portability:
        int shift_result = operand1 / (1<<reg_imm_1);
        *get_output_dest(dest,rd) = shift_result;
        (*PC)++;
#ifdef PROFILE
        printf("rShift gr[%d] = gr[%d] >> %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SHIFTI_L) {      // SHIFT_L
        assert(dest == CTRL_GR);  // only support gr
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = main_addressing_register[rs2];
        //we want arithmetic shift right as below, but this is compiler dependent. Not in c++ std
        //int shift_result = operand1 >> reg_imm_1;
        //so instead of above, we do the following for portability:
        int shift_result = operand1 <<reg_imm_1;
        *get_output_dest(dest,rd) = shift_result;
        (*PC)++;
#ifdef PROFILE
        printf("lShift gr[%d] = gr[%d] << %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_ANDI) {      // AND
        rd = reg_imm_0;
        rs2 = reg_1;
        int operand1 = main_addressing_register[rs2];
        int and_result = operand1 & reg_imm_1;
        *get_output_dest(dest,rd) = and_result;
        (*PC)++;
#ifdef PROFILE
        printf("andi gr[%d] = gr[%d] & %d (%d) \n", rd, rs2, reg_imm_1, operand1);
#endif
    } else if (opcode == CTRL_SUBI) {       // subi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs2];
        add_b = imm;
        sum = add_a - add_b;
        *get_output_dest(dest,rd) = sum;
#ifdef PROFILE
        printf("subi gr[%d] gr[%d] %d (%d %d %d)\n", rd, rs2, imm, sum, add_a, add_b);
#endif
        (*PC)++;
    } else {
        fprintf(stderr, "main control instruction opcode error. opcode = %d\n", opcode);
        exit(-1);
    }
    return 0;
}

int* pe_array::get_output_dest(int dest, int rd){
    // write out only supported for GR or out buffer
    if (dest == CTRL_GR){
        return &main_addressing_register[rd];
    } else if (dest == CTRL_OUT_BUF){
        return &output_buffer[rd];
    } else if (dest == CTRL_OUT_PORT){
        return &store_data;
    } else {
        fprintf(stderr, 
                "Only dest CTRL_GR and CTRL_OUT_BUF are supported for pe_array, non MV CTRL instr. dest = %d. PC = %d\n", dest, main_PC);
        exit(-1);
    }
}

int pe_array::decode_output(unsigned long instruction, int* PC, int simd, int setting, int main_instruction_setting) {

#ifdef PROFILE
    printf("main\t");
#endif
    int i, rd, rs1, rs2, imm, sum = 0, add_a = 0, add_b = 0;
    LoadResult data{};
    int8_t rs[4];
        
    unsigned long dest_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long src_mask = (unsigned long)((1 << MEMORY_COMPONENTS_ADDR_WIDTH) - 1) << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    unsigned long reg_immBar_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    unsigned long reg_auto_increasement_flag_0_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    unsigned long reg_imm_0_sign_bit_mask = (unsigned long)1 << (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    unsigned long reg_imm_0_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_0_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_immBar_flag_1_mask = (unsigned long)1 << (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_auto_increasement_flag_1_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_imm_1_sign_bit_mask = (unsigned long)1 << (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    unsigned long reg_imm_1_mask = (unsigned long)((1 << IMMEDIATE_WIDTH) - 1) << (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    unsigned long reg_1_mask = (unsigned long)((1 << GLOBAL_REGISTER_ADDR_WIDTH) - 1) << CTRL_OPCODE_WIDTH;
    unsigned long opcode_mask = (unsigned long)((1 << CTRL_OPCODE_WIDTH) - 1);

    int dest = (instruction & dest_mask) >> (INSTRUCTION_WIDTH - MEMORY_COMPONENTS_ADDR_WIDTH);
    int src = (instruction & src_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH);
    int reg_immBar_flag_0 = (instruction & reg_immBar_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 1);
    int reg_auto_increasement_flag_0 = (instruction & reg_auto_increasement_flag_0_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 2);
    int reg_imm_0 = (instruction & reg_imm_0_mask) >> (2 + IMMEDIATE_WIDTH + 2 * GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_0_sign_bit = (instruction & reg_imm_0_sign_bit_mask) >> (INSTRUCTION_WIDTH - 2*MEMORY_COMPONENTS_ADDR_WIDTH - 3);
    int imm_sign_extend_mask = ~((1 << IMMEDIATE_WIDTH) - 1);
    int sext_imm_0 = reg_imm_0 | (reg_imm_0_sign_bit ? imm_sign_extend_mask : 0);
    int reg_0 = (instruction & reg_0_mask) >> (2 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_immBar_flag_1 = (instruction & reg_immBar_flag_1_mask) >> (1 + IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_auto_increasement_flag_1 = (instruction & reg_auto_increasement_flag_1_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1 = (instruction & reg_imm_1_mask) >> (GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH);
    int reg_imm_1_sign_bit = (instruction & reg_imm_1_sign_bit_mask) >> (IMMEDIATE_WIDTH + GLOBAL_REGISTER_ADDR_WIDTH + CTRL_OPCODE_WIDTH - 1);
    int sext_imm_1 = reg_imm_1 | (reg_imm_1_sign_bit ? imm_sign_extend_mask : 0);
    int reg_1 = (instruction & reg_1_mask) >> CTRL_OPCODE_WIDTH;
    int opcode = instruction & opcode_mask;

#ifdef PROFILE
    printf("PC = %d @%d\t", *PC, cycle);
#endif
    if (main_instruction_setting == MAIN_INSTRUCTION_2) {
        // Arithmetic (opcodes 0-3) now runs pre-PE via
        // decode(). Skip here to avoid double-execution.
        if (opcode <= 3) {
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
        if (((opcode == 4 || opcode == 5)
             && (dest != 5 && dest != 6 && dest != 11
                 && dest != 12 && dest != 13
                 && dest != 14))
            || opcode == 14) {
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    } else if (main_instruction_setting == MAIN_INSTRUCTION_1) {
        if (dest != 5 && dest != 6 && dest != 11 && dest != 12 && dest != 13 && dest != 14) {
#ifdef PROFILE
            printf("\n");
#endif
            return 0;
        }
    }

// #ifdef DEBUG
//     printf("dest: %d src: %d reg_immBar_flag_0: %d reg_auto_increasement_flag_0: %d reg_imm_0_sign_bit: %d sext_imm_0: %d, reg_0: %d reg_immBar_flag_1: %d reg_auto_increasement_flag_1: %d reg_imm_1_sign_bit: %d sext_imm_1: %d reg_1: %d opcode: %d\n", dest, src, reg_immBar_flag_0, reg_auto_increasement_flag_0, reg_imm_0_sign_bit, sext_imm_0, reg_0, reg_immBar_flag_1, reg_auto_increasement_flag_1, reg_imm_1_sign_bit, sext_imm_1, reg_1, opcode);
// #endif

if (opcode == 0) {              // add rd rs1 rs2
    rd = reg_imm_0;
    rs1 = reg_imm_1;
    rs2 = reg_1;
    
    // DEBUG: Print instruction details
    fprintf(stderr, "\n=== ADD INSTRUCTION DEBUG ===\n");
    fprintf(stderr, "PC: %d\n", *PC);
    fprintf(stderr, "Instruction: 0x%lx\n", instruction);
    fprintf(stderr, "rd=%d, rs1=%d, rs2=%d\n", rd, rs1, rs2);
    fprintf(stderr, "reg_imm_0=%d, reg_imm_1=%d, reg_1=%d\n", reg_imm_0, reg_imm_1, reg_1);
    fprintf(stderr, "MAIN_ADDR_REGISTER_NUM=%d\n", MAIN_ADDR_REGISTER_NUM);
    
    if (rd >= MAIN_ADDR_REGISTER_NUM || rs1 >= MAIN_ADDR_REGISTER_NUM || rs2 >= MAIN_ADDR_REGISTER_NUM) {
        fprintf(stderr, "ERROR: Register index out of bounds!\n");
        fprintf(stderr, "  Valid range: 0-%d\n", MAIN_ADDR_REGISTER_NUM-1);
        exit(1);
    }
    
    add_a = main_addressing_register[rs1];
    add_b = main_addressing_register[rs2];
    sum = add_a + add_b;
    main_addressing_register[rd] = sum;

#ifdef PROFILE
        printf("add gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
    } else if (opcode == 1) {       // sub rd rs1 rs2
        rd = reg_imm_0;
        rs1 = reg_imm_1;
        rs2 = reg_1;
        add_a = main_addressing_register[rs1];
        add_b = main_addressing_register[rs2];
        sum = add_a - add_b;
        main_addressing_register[rd] = sum;
#ifdef PROFILE
        printf("sub gr[%d] gr[%d] gr[%d] (%d %d %d)\n", rd, rs1, rs2, sum, add_a, add_b);
#endif
    } else if (opcode == 2) {       // addi rd rs2 imm
        rd = reg_imm_0;
        imm = sext_imm_1;
        rs2 = reg_1;
        add_a = imm;
        add_b = main_addressing_register[rs2];
        sum = add_a + add_b;
        main_addressing_register[rd] = sum;
#ifdef PROFILE
        printf("addi gr[%d] %d gr[%d] (%d %d %d)\n", rd, imm, rs2, sum, add_a, add_b);
#endif
    } else if (opcode == 3) {       // set_8 rd rs2
        rd = reg_imm_0;
        rs2 = reg_1;
        memcpy(rs, &main_addressing_register[rs2], 4*sizeof(int8_t));

        for (i = 0; i < 4; i++) {
            rs[i] = main_addressing_register[rs2] & 0xFF;
        }
        memcpy(&main_addressing_register[rd], rs, 4*sizeof(int8_t));
#ifdef PROFILE
        printf("set_8 gr[%d] gr[%d] (%d %lx)\n", rd, rs2, main_addressing_register[rs2], main_addressing_register[rd]);
#endif
    } else if (opcode == 4) {       // li dest imm/reg(reg(++))
#ifdef PROFILE
    if (simd)
        printf("Store %lx to ", sext_imm_1);
    else
        printf("Store %d to ", sext_imm_1);
#endif
        LoadResult immediate_data{};
        immediate_data.data[0] = sext_imm_1;
        store(dest, reg_immBar_flag_0, sext_imm_0, reg_0, immediate_data, simd);
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
    } else if (opcode == 5) {
#ifdef PROFILE
        printf("Move ");
#endif
        if (src == CTRL_S2 && dest == CTRL_SPM) {
            int s2Addr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int spmAddr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            lsq->enqueueS2ToSpm(
                s2Addr, spmAddr, true);
        } else if (src == CTRL_SPM
                   && dest == CTRL_S2) {
            int spmAddr = reg_immBar_flag_1
                ? main_addressing_register[sext_imm_1]
                  + main_addressing_register[reg_1]
                : sext_imm_1
                  + main_addressing_register[reg_1];
            int s2Addr = reg_immBar_flag_0
                ? main_addressing_register[sext_imm_0]
                  + main_addressing_register[reg_0]
                : sext_imm_0
                  + main_addressing_register[reg_0];
            lsq->enqueueSpmToS2(
                spmAddr, s2Addr, true);
        } else {
            data = load(src, reg_immBar_flag_1,
                        sext_imm_1, reg_1, simd);
            store(dest, reg_immBar_flag_0,
                  sext_imm_0, reg_0, data, simd);
        }
        if (reg_auto_increasement_flag_0)
            main_addressing_register[reg_0]++;
        if (reg_auto_increasement_flag_1)
            main_addressing_register[reg_1]++;
    }
    return 0;
}

void pe_array::show_gr() {
    int i;
    for (i = 0; i < ADDR_REGISTER_NUM; i++)
        printf("main gr[%d] = %d\n", i, main_addressing_register[i]);
}

void pe_array::show_spm_nonzero(int start, int end) {
    if (start < 0 || end > SPM_unit->buffer_size || start > end) {
        fprintf(stderr, "show_spm_nonzero: invalid range [%d, %d]\n", start, end);
        return;
    }

    printf("\n=== Non-zero SPM values [%d-%d] ===\n", start, end);
    int count = 0;

    // Organize by banks for clarity
    for (int bank = 0; bank < 4; bank++) {
        int bank_start = bank * SPM_BANK_SIZE;
        int bank_end = (bank + 1) * SPM_BANK_SIZE;

        // Skip banks outside our range
        if (bank_end <= start || bank_start >= end) continue;

        int search_start = (start > bank_start) ? start : bank_start;
        int search_end = (end < bank_end) ? end : bank_end;

        bool bank_has_data = false;
        for (int i = search_start; i < search_end; i++) {
            if (SPM_unit->buffer[i] != 0) {
                if (!bank_has_data) {
                    printf("\n--- Bank %d (addresses %d-%d) ---\n", bank, bank_start, bank_end - 1);
                    bank_has_data = true;
                }
                printf("  SPM[%5d] = %10d (0x%08x)\n", i, SPM_unit->buffer[i], SPM_unit->buffer[i]);
                count++;
            }
        }
    }

    if (count == 0) {
        printf("  (All values are zero)\n");
    } else {
        printf("\nTotal non-zero values: %d\n", count);
    }
    printf("===================================\n");
}

void pe_array::show_compute_instruction_buffer() {
    int i, j;
    for (i = 0; i < COMP_INSTR_BUFFER_GROUP_NUM; i++)
        for (j = 0; j < COMP_INSTR_BUFFER_GROUP_SIZE; j++)
            printf("compute instruction buffer[%d][%d] = %lx\n", i, j, compute_instruction_buffer[i][j]);
}

void pe_array::show_main_instruction_buffer() {
    int i, j;
    for (i = 0; i < CTRL_INSTR_BUFFER_NUM; i++)
        for (j = 0; j < 2; j++)
            printf("main instruction buffer[%d][%d] = %lx\n", i, j, main_instruction_buffer[i][j]);
}

void pe_array::show_compute_reg(const char* label, const char** reg_names) {
    #ifdef DEBUG
    // Use member variable if no parameter provided
    const char** names_to_use = (reg_names != nullptr) ? reg_names : compute_reg_names;

    printf("\n========== %s ==========\n", label);
    for (int i = 0; i < 1; i++) {
        if (pe_unit[i] == nullptr) continue;

        printf("\n--- PE[%d] ---\n", i);

        // Show compute registers using existing public function
        printf("Compute Registers (reg):\n");
        pe_unit[i]->show_comp_reg(names_to_use);

        // Show addressing registers (directly accessible since it's public)
        printf("\nAddressing Registers (gr):\n");
        for (int j = 0; j < ADDR_REGISTER_NUM; j++) {
            printf("  gr[%d] = %d\n", j, pe_unit[i]->addr_regfile_unit->buffer[j]);
        }
    }
    printf("=======================================\n\n");
    #endif
}


int Float2Fix(float exact_value) {
    int MIN_INTEGER = -pow(2, NUM_FRACTION_BITS+NUM_INTEGER_BITS);
    if (exact_value == - std::numeric_limits<float>::infinity())
        return MIN_INTEGER;
    int result = (int)ceil(exact_value * pow(2, NUM_FRACTION_BITS));
    return result;
}

float Fix2Float(int integer) {
    float result = (float)(integer / pow(2, NUM_FRACTION_BITS));
    return result;
}

int Upper_LOG2_accurate(float num){
    float numLog2 = log(num) / log(2);
    int result = Float2Fix(numLog2);
    return result;
}

void pe_array::phmm_show_output_buffer(FILE* fp) {
    float INITIAL_CONDITION_UP = (float)pow(2, 127);
    // float result = log10(pow(2, Fix2Float(output_buffer[0] - Upper_LOG2_accurate(INITIAL_CONDITION_UP))));
    fprintf(fp, "%d\n", output_buffer[0]);
}

void pe_array::chain_show_output_buffer(int n, FILE* fp) {
    int j;
    for (j = 0; j < n; j++) {
        fprintf(fp, "%d\n", output_buffer[j]);
    }
}

void pe_array::bsw_show_output_buffer(FILE* fp) {
    int i, j;
    int8_t output[6][4];
    for (i = 0; i < 6; i++)
        memcpy(output[i], output_buffer+i, 4*sizeof(int8_t));
    for (j = 0; j < 4; j++) {
        fprintf(fp, "%d ", output[0][j]);
        fprintf(fp, "%d ", output[3][j]);
        fprintf(fp, "%d ", output[4][j]);
        fprintf(fp, "%d ", output[1][j]);
        fprintf(fp, "%d ", output[2][j]);
        fprintf(fp, "%d\n", output[5][j]);
    }
}

void pe_array::poa_show_output_buffer(int len_y, int len_x, FILE* fp) {
    int num = len_y * len_x * 2;
    // printf("Output: %d\n", num);
    fprintf(fp, "Output: %d\n", num);
    int i, j, k;
    int iter = len_x * 8;

    for (i = 0; i < len_y/4; i++) {
        fprintf(fp, "%d ", i*iter);
        fprintf(fp, "x x x x x x %d %d \n", output_buffer[i*iter+6], output_buffer[i*iter+7]);
        fprintf(fp, "%d ", i*iter+8);
        fprintf(fp, "x x x x %d %d %d %d \n", output_buffer[i*iter+8+4], output_buffer[i*iter+8+5], output_buffer[i*iter+8+6], output_buffer[i*iter+8+7]);
        fprintf(fp, "%d ", i*iter+16);
        fprintf(fp, "x x %d %d %d %d %d %d \n", output_buffer[i*iter+16+2], output_buffer[i*iter+16+3], output_buffer[i*iter+16+4], output_buffer[i*iter+16+5], output_buffer[i*iter+16+6], output_buffer[i*iter+16+7]);

        for (j = 3; j < len_x-3; j++) {
            fprintf(fp, "%d ", i*iter+j*8);
            for (k = 0; k < 8; k++)
                fprintf(fp, "%d ", output_buffer[i*iter + j*8 + k]);
            fprintf(fp, "\n");
        }

        fprintf(fp, "%d ", i*iter+(len_x-3)*8);
        fprintf(fp, "%d %d %d %d %d %d x x \n", output_buffer[i*iter+(len_x-3)*8], output_buffer[i*iter+(len_x-3)*8+1], output_buffer[i*iter+(len_x-3)*8+2], output_buffer[i*iter+(len_x-3)*8+3], output_buffer[i*iter+(len_x-3)*8+4], output_buffer[i*iter+(len_x-3)*8+5]);
        fprintf(fp, "%d ", i*iter+(len_x-2)*8);
        fprintf(fp, "%d %d %d %d x x x x \n", output_buffer[i*iter+(len_x-2)*8], output_buffer[i*iter+(len_x-2)*8+1], output_buffer[i*iter+(len_x-2)*8+2], output_buffer[i*iter+(len_x-2)*8+3]);
        fprintf(fp, "%d ", i*iter+(len_x-1)*8);
        fprintf(fp, "%d %d x x x x x x \n", output_buffer[i*iter+(len_x-1)*8], output_buffer[i*iter+(len_x-1)*8+1]);
    }
}

void pe_array::handle_spm_data_ready(
    SpmDataReadyData* evData) {
    if (evData->requestorId == CTRL_PEID) {
        lsq->dataReadyFromSpm(
            CtrlLSQ::spmBank(evData->phys_addr),
            evData->data);
    } else {
        pe_unit[evData->requestorId]
            ->recieve_spm_data(evData->data);
    }
}

void pe_array::process_events() {
    std::list<EventProducer*> to_remove{};
    for (auto event_producer : active_event_producers) {
        std::pair<bool, std::list<Event>*> result = event_producer->tick();
        if (result.first) // Event producer has finished, mark it for removal
            to_remove.push_back(event_producer);
        for (auto& event : *(result.second)) {
#ifdef PROFILE
            printf("main processing event type %d\n\n", event.type);
#endif
            switch (event.type) {
                case EventType::SPM_DATA_READY:
                    handle_spm_data_ready(static_cast<SpmDataReadyData*>(event.data));
                    delete static_cast<SpmDataReadyData*>(event.data);
                    break;
                default:
                    fprintf(stderr, "Unknown event type %d\n", event.type);
                    exit(-1);
            }
        }
        delete result.second;
    }
    // Remove finished event producers
    for (auto event_producer : to_remove) {
        active_event_producers.erase(event_producer);
    }

}

// Pre-check whether executing both VLIW slots would
// cause an LSQ stall. Returns true if either (or both
// combined) would overflow an LSQ bank.
bool pe_array::willStallPair(
    unsigned long slot0, unsigned long slot1)
{
    // Combined address lists for canEnqueue
    int spmAddrs[10], s2Addrs[10];
    int nSpm = 0, nS2 = 0;

    unsigned long instrs[2] = {slot0, slot1};
    for (int s = 0; s < 2; s++) {
        unsigned long instr = instrs[s];
        bool is_magic = (instr >> 63) & 1;
        if (is_magic) continue;

        int opcode = instr & 0x3F;
        int dest   = (instr >> 54) & 0xF;
        int src    = (instr >> 50) & 0xF;
        int riB0   = (instr >> 49) & 1;
        int imm0   = (instr >> 32) & 0xFFFF;
        if (imm0 & 0x8000) imm0 |= ~0xFFFF;
        int r0     = (instr >> 28) & 0xF;
        int riB1   = (instr >> 27) & 1;
        int imm1   = (instr >> 10) & 0xFFFF;
        if (imm1 & 0x8000) imm1 |= ~0xFFFF;
        int r1     = (instr >> 6)  & 0xF;

        bool srcSpm  = (src  == CTRL_SPM);
        bool srcS2   = (src  == CTRL_S2);
        bool destSpm = (dest == CTRL_SPM);
        bool destS2  = (dest == CTRL_S2);
        bool spmS2   = (srcSpm && destS2)
                     || (srcS2 && destSpm);

        if (opcode == 5 && spmS2) {
            // mv SPM<->S2: one spm addr, one s2 addr
            int addr0 = (riB0
                ? main_addressing_register[imm0 & 0xF]
                : imm0)
                + main_addressing_register[r0];
            int addr1 = (riB1
                ? main_addressing_register[imm1 & 0xF]
                : imm1)
                + main_addressing_register[r1];
            // dest uses addr0 (field 0), src uses addr1
            int spmA = destSpm ? addr0 : addr1;
            int s2A  = destS2  ? addr0 : addr1;
            spmAddrs[nSpm++] = spmA;
            s2Addrs[nS2++]   = s2A;
        } else if (opcode == CTRL_MVDQ && spmS2) {
            // mvdq SPM<->S2: 4-5 entries each side
            int addr0 = (riB0
                ? main_addressing_register[imm0 & 0xF]
                : imm0)
                + main_addressing_register[r0];
            int addr1 = (riB1
                ? main_addressing_register[imm1 & 0xF]
                : imm1)
                + main_addressing_register[r1];
            int spmA = destSpm ? addr0 : addr1;
            int s2A  = destS2  ? addr0 : addr1;
            // Even/odd bank patterns (mirrors decode)
            if (spmA % 2 == 0) {
                for (int i = 0; i < 4; i++)
                    spmAddrs[nSpm++] = spmA + 2*i;
            } else {
                spmAddrs[nSpm++] = spmA;
                spmAddrs[nSpm++] = spmA + 1;
                spmAddrs[nSpm++] = spmA + 3;
                spmAddrs[nSpm++] = spmA + 5;
                spmAddrs[nSpm++] = spmA + 7;
            }
            if (s2A % 2 == 0) {
                for (int i = 0; i < 4; i++)
                    s2Addrs[nS2++] = s2A + 2*i;
            } else {
                s2Addrs[nS2++] = s2A;
                s2Addrs[nS2++] = s2A + 1;
                s2Addrs[nS2++] = s2A + 3;
                s2Addrs[nS2++] = s2A + 5;
                s2Addrs[nS2++] = s2A + 7;
            }
        }
        // All other opcodes (including barrier): no stall
    }

    if (nSpm == 0 && nS2 == 0) return false;
    return !lsq->canEnqueue(
        spmAddrs, nSpm, s2Addrs, nS2);
}


void pe_array::run(int cycle_limit, int simd, int setting, int main_instruction_setting) {
    int i, j, flag, old_PC;
    cycle = 0;

    while (1) {
        cycle++;
        old_PC = main_PC;
        process_events();

        // S2 tick: advance pipelines, route completions
        {
            auto completions = s2->tick();
            for (auto& c : completions)
                lsq->dataReadyFromS2(
                    c.s2Addr, c.data);
        }

        // Pre-check: if either slot would stall on LSQ,
        // skip both to prevent double-execution bugs.
        bool pairStalls = false;
        if (main_instruction_setting
            == MAIN_INSTRUCTION_2) {
            pairStalls = willStallPair(
                main_instruction_buffer[main_PC][0],
                main_instruction_buffer[main_PC][1]);
            if (pairStalls) lsqFullStalls++;
        }

        if (!pairStalls) {
            flag = decode(
                main_instruction_buffer[main_PC][1],
                &main_PC, simd, setting,
                main_instruction_setting);
        }

        // Pre-PE decode of slot[0]: arithmetic + non-I/O
        // ops. Uses MI_1 filter to skip I/O-dest instrs
        // (handled post-PE by decode_output).
        if (main_instruction_setting
            == MAIN_INSTRUCTION_2 && !pairStalls) {
            int slot0_PC = old_PC;
            decode(main_instruction_buffer[old_PC][0],
                &slot0_PC, simd, setting,
                MAIN_INSTRUCTION_1);
        }

        pe_unit[0]->load_data = store_data;
        pe_unit[0]->load_instruction[0] = PE_instruction[0];
        pe_unit[0]->load_instruction[1] = PE_instruction[1];

    #ifdef DEBUG
            // GBV Debug
            printf("\n========== Cycle %d ==========\n", cycle);

            // Main controller addressing registers
            //printf("Main Controller (gr):\n  ");
            //show_gr();

            // Input/Output buffers
            // printf("Input buffer: ");
            // for (int k = 0; k < 7; ++k) printf("%d ", input_buffer[k]);
            // printf("\nOutput buffer: ");
            // for (int k = 0; k < 10; ++k) printf("%d ", output_buffer[k]);
            // printf("\n");

            // SPM non-zero values - Bank 0 only
            show_spm_nonzero(0, SPM_BANK_SIZE);

            //show_compute_instruction_buffer();
            //show_main_instruction_buffer();
            show_compute_reg("PE Debug");

            printf("=====================================\n");
    #endif



        if (setting == PE_4_SETTING) {
            for (i = 0; i < 4; i++) {
                // Skip stalled PEs (freeze execution and block systolic forwarding)
                if (pe_unit[i]->stalled()) {
                    continue;
                }
#ifdef PROFILE
                printf("PE[%d]\t", i);
#endif
                pe_unit[i]->run(simd);
                //zkn pass through systolic connections
                if (i < 3) {
                    pe_unit[i+1]->load_data = pe_unit[i]->store_data;
                    pe_unit[i+1]->load_instruction[0] = pe_unit[i]->store_instruction[0];
                    pe_unit[i+1]->load_instruction[1] = pe_unit[i]->store_instruction[1];
                } else if (i == 3) {
                    load_data = pe_unit[3]->store_data;
                }
            }
        } else if (setting == PE_64_SETTING) {
            //TODO note that WAIT/READY is not implemented for 64 setting
            for (j = 0; j < 16; j++) {
                if (j > 0) {
                    if (from_fifo) pe_unit[j*4]->load_data = store_data;
                    else pe_unit[j*4]->load_data = pe_unit[j*4-1]->store_data;
                    pe_unit[j*4]->load_instruction[0] = pe_unit[j*4-1]->store_instruction[0];
                    pe_unit[j*4]->load_instruction[1] = pe_unit[j*4-1]->store_instruction[1];
                }

                for (i = 0; i < 4; i++) {
#ifdef PROFILE
                    printf("PE[%d]\t", j*4+i);
#endif
                    pe_unit[j*4+i]->run(simd);
                    if (i < 3) {
                        pe_unit[j*4+i+1]->load_data = pe_unit[j*4+i]->store_data;
                        pe_unit[j*4+i+1]->load_instruction[0] = pe_unit[j*4+i]->store_instruction[0];
                        pe_unit[j*4+i+1]->load_instruction[1] = pe_unit[j*4+i]->store_instruction[1];
                    } else if (j*4+i == 63) {
                        load_data = pe_unit[63]->store_data;
                    }
                }
            }
        }

        // Count halted PEs and update performance counter
        int num_halted = 0;
        int total_pes = (setting == PE_4_SETTING) ? 4 : 64;
        for (i = 0; i < total_pes; i++) {
            if (pe_unit[i]->halted) {
                num_halted++;
            }
        }
        peHalted += num_halted;

        // SPM bank arbitration with conflict detection (round-robin)
        int start_pe = cycle % 4;
        for (int offset = 0; offset < 4; offset++) {
            int pe_idx = (start_pe + offset) % 4;
            OutstandingRequest* req = pe_unit[pe_idx]->spmReqPort;
            if (req == nullptr) continue;

            totalSpmRequests++;
            // Check if SPM bank is available
            int bank = SPM_unit->getBank(
                req->addr, req->peid, req->isVirtualAddr);
            if (SPM_unit->portIsBusy(
                    req->addr, req->peid, req->isVirtualAddr)) {
                bankConflictStalls++;
                // Perf counter: check if conflict is same-line (forwardable)
                OutstandingRequest* pend = SPM_unit->requests[bank];
                int newPhys = req->isVirtualAddr
                    ? (req->peid * SPM_BANK_GROUP_SIZE + req->addr)
                    : req->addr;
                int pendPhys = pend->isVirtualAddr
                    ? (pend->peid * SPM_BANK_GROUP_SIZE + pend->addr)
                    : pend->addr;
                if (lineAddr(newPhys) == lineAddr(pendPhys))
                    forwardableBankConflict++;
            } else {
                // Grant access
                SPM_unit->access(req->addr, req->peid,
                    req->access_t, req->single_data,
                    req->data, req->isVirtualAddr);
                delete pe_unit[pe_idx]->spmReqPort;
                pe_unit[pe_idx]->spmReqPort = nullptr;
            }
        }

        // LSQ drain
        {
            bool spmBankBusy[SPM_NUM_BANKS] = {};
            // Only mark banks with in-flight SPM requests. Any pending
            // PE spmReqPort entries necessarily target banks that are
            // already busy (otherwise they would have issued above).
            for (int b = 0; b < SPM_NUM_BANKS; b++)
                spmBankBusy[b] =
                    (SPM_unit->requests[b] != nullptr);
            lsq->tick(SPM_unit, s2, spmBankBusy);
        }

        from_fifo = 0;

        if (main_instruction_setting == MAIN_INSTRUCTION_1)
            decode_output(main_instruction_buffer[old_PC][1],
                &old_PC, simd, setting,
                main_instruction_setting);
        else if (main_instruction_setting
                 == MAIN_INSTRUCTION_2 && !pairStalls)
            decode_output(main_instruction_buffer[old_PC][0],
                &old_PC, simd, setting,
                main_instruction_setting);

#ifdef PROFILE
        printf("\n");
#endif
        //zkn TODO I don't know if these should be in the above else or not
        main_addressing_register[13] = pe_unit[0]->get_gr_10() && pe_unit[1]->get_gr_10();
        for (i = 2; i < setting; i++)
            main_addressing_register[13] = main_addressing_register[13] && pe_unit[i]->get_gr_10();
        if (flag == -1 || cycle == cycle_limit) {
            printf("cycle %d\n", cycle);
            break;
        }
    }

    printf("=== Performance Counters ===\n");
    printf("TotalSpmRequests: %d\n", totalSpmRequests);
    printf("BankConflictStalls: %d\n", bankConflictStalls);
    printf("ForwardableBankConflict: %d\n", forwardableBankConflict);
    printf("LsqFullStalls: %d\n", lsqFullStalls);
    printf("PeHalted: %d\n", peHalted);
    printf("SyncSpinBNEs: %d\n", controllerSpinCycles);

    // fprintf(stderr, "Finish simulation.\n");
}
