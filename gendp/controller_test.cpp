#include "PriorityQueue.h"
#include <iostream>
#include <vector>
#include <array>
#include <ctime>
#include <bitset>
#include <fstream>

struct GraphNode 
{
    int node_id;                   // Node ID
    uint8_t basepair : 2;          // 2-bit basepair (values 0-3)
    std::array<int, 15> child_ids;  // Up to 5 children node IDs (-1 for unused)
};

struct InputDataNode 
{
    uint8_t basepair : 2;   // 2-bit basepair (values 0-3)
    int parent_node_id;     // Parent node ID
};

struct SPM {
    int32_t data[1000];

    SPM() {
        // Initialize first 16 elements to 1..16
        for (int i = 0; i < 16; ++i) {
            data[i] = i + 1;
        }
        // Optionally initialize the rest to 0
        for (int i = 16; i < 1000; ++i) {
            data[i] = 0;
        }
    }
};

// Instantiate a 12-register regfile for the PE array (32-bit unsigned ints)
uint32_t pearray_regfile[12] = {0};
uint32_t pe0_regfile[12] = {0};
uint32_t pe1_regfile[12] = {0};
uint32_t pe2_regfile[12] = {0};
uint32_t pe3_regfile[12] = {0};

uint32_t pe0_compfile[32] = {0};
uint32_t pe1_compfile[32] = {0};
uint32_t pe2_compfile[32] = {0};
uint32_t pe3_compfile[32] = {0};

int main() {

    std::ofstream out("conttest.txt");

    InputDataNode input_buffer[30];
    GraphNode graph_memory[200];
    PriorityQueue pq;
    SPM spm;


    std::srand(std::time(nullptr)); // Seed for random priorities

    for (int i = 0; i < 10; ++i) {
        // Generate random parent node id between 100 and 200
        int parent_id = 100 + std::rand() % 101;
        // Generate random basepair between 0 and 3 (00, 01, 10, 11)
        uint8_t basepair = std::rand() % 4;

        // Store in input_buffer
        input_buffer[i].parent_node_id = parent_id;
        input_buffer[i].basepair = basepair;

        // Create and push node to queue as before
        QueueNode node;
        node.priority = std::rand() % 101;
        node.node_id = parent_id; // Use same parent_id for node_id
        int num_children = std::rand() % 6;
        node.child_ids.fill(-1);
        for (int c = 0; c < num_children; ++c) {
            node.child_ids[c] = 1 + std::rand() % 99;
        }
        pq.push(node);

    // Print what is being inserted into the priority queue
    out << "Inserting into PriorityQueue: id=" << node.node_id
            << ", priority=" << node.priority
            << ", num_children=" << num_children
            << ", children=[";
    for (int c = 0; c < num_children; ++c) {
        out << node.child_ids[c] << " ";
    }
    out << "]" << std::endl;

    // Print what is being inserted into the input data buffer
    out << "Inserting into InputDataBuffer: index=" << i
            << ", parent_node_id=" << input_buffer[i].parent_node_id
            << ", basepair=" << std::bitset<2>(input_buffer[i].basepair)
            << std::endl;
    }

    for (int cycle = 0; cycle < 10; ++cycle) {
    // Read from input_buffer[cycle]
    uint8_t basepair = input_buffer[cycle].basepair;
    int parent_id = input_buffer[cycle].parent_node_id;

    // Store into PE array registers
    pearray_regfile[1] = basepair;
    pearray_regfile[2] = parent_id;

    // On each cycle, shift values down the PE chain
    pe3_regfile[1] = pe2_regfile[1];
    pe3_regfile[2] = pe2_regfile[2];

    pe2_regfile[1] = pe1_regfile[1];
    pe2_regfile[2] = pe1_regfile[2];

    pe1_regfile[1] = pe0_regfile[1];
    pe1_regfile[2] = pe0_regfile[2];

    pe0_regfile[1] = pearray_regfile[1];
    pe0_regfile[2] = pearray_regfile[2];

// === SPM access and compfile update ===
    pe0_compfile[0] = spm.data[pe0_regfile[1]];
    pe1_compfile[0] = spm.data[pe1_regfile[1] + 4];
    pe2_compfile[0] = spm.data[pe2_regfile[1] + 4];
    pe3_compfile[0] = spm.data[pe3_regfile[1] + 4];

    // Print the state for this cycle
    out << "Cycle " << cycle << " pipeline state:\n";
    out << "  pearray_regfile[1]=" << pearray_regfile[1]
        << ", pearray_regfile[2]=" << pearray_regfile[2] << "\n";
    out << "  pe0_regfile[1]=" << pe0_regfile[1]
        << ", pe0_regfile[2]=" << pe0_regfile[2]
        << ", pe0_compfile[0]=" << pe0_compfile[0] << "\n";
    out << "  pe1_regfile[1]=" << pe1_regfile[1]
        << ", pe1_regfile[2]=" << pe1_regfile[2]
        << ", pe1_compfile[0]=" << pe1_compfile[0] << "\n";
    out << "  pe2_regfile[1]=" << pe2_regfile[1]
        << ", pe2_regfile[2]=" << pe2_regfile[2]
        << ", pe2_compfile[0]=" << pe2_compfile[0] << "\n";
    out << "  pe3_regfile[1]=" << pe3_regfile[1]
        << ", pe3_regfile[2]=" << pe3_regfile[2]
        << ", pe3_compfile[0]=" << pe3_compfile[0] << "\n";
}



    /* out << "\nQueue size after insertion: " << pq.size() << std::endl;
    // Pop all nodes and print their info in priority order
    while (!pq.empty()) {
        const QueueNode& top = pq.top();
        int child_count = 0;
        for (int c = 0; c < 5; ++c) {
            if (top.child_ids[c] != -1) child_count++;
        }
        out << "Popped node: id=" << top.node_id
                  << ", priority=" << top.priority
                  << ", num_children=" << child_count
                  << ", children=[";
        for (int c = 0; c < child_count; ++c) {
            out << top.child_ids[c] << " ";
        }
        out << "]" << std::endl;
        pq.pop();
    }
    out << "Queue empty: " << std::boolalpha << pq.empty() << std::endl; */

    out.close();
    return 0;
}















// void dataflow_accelerator()
// {
//     Word new_parents, current_parent, new_children, spm_index, requeue = 0;

// 	Word gregfile[8];

//     const QueueNode& top = pq.top();
//     int num_children = 0;
//     for (int i = 0; i < 5; ++i) {
//     if (top.child_ids[i] != -1)
//         num_children++;
// }

// 	gregfile[0]  = 
// 	gregfile[1]  = new_parents;
// 	gregfile[2]  = new_children;
// 	gregfile[3]  = spm_index;
// 	gregfile[4]  = requeue;
// 	gregfile[5]  = current_parent;
// 	gregfile[6]  = 
// 	gregfile[7]  = 

//     gregfile[1] = top.node_id;
//     gregfile[3] = gregfile[2] > 0 ? new_parents : 0; // sets index for grabbing data
//     gregfile[4] = regfile[20] < regfile[16] ? 1 : 0; // if requeue is high, push current parent
//     gregfile[5] = gregfile[4] == 1 ? regfile[21] : 0; // parent being worked on in last pe

//     input_buffer = gregfile[3]; 
//     input_buffer = gregfile[2];
//     regfile[6] = SPM[gregfile[3]];
//     regfile[8] = SPM[gregfile[3]++];
//     regfile[9] = SPM[gregfile[3]++];
//     regfile[7] = SPM[gregfile[3]++];
//     regfile[1] = SPM[gregfile[3]++];


//     SPM[gregfile[5]] = regfile[6];
//     SPM[gregfile[5]++] = regfile[8];
//     SPM[gregfile[5]++] = regfile[9];
//     SPM[gregfile[5]++] = regfile[7];
//     SPM[gregfile[5]++] = regfile[1];
   
// }