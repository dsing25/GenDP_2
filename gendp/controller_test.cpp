#include "PriorityQueue.h"
#include <iostream>
#include <vector>
#include <array>
#include <ctime>
#include <bitset>

int main() {

    struct InputDataNode 
    {
    uint8_t basepair : 2;   // 2-bit basepair (values 0-3)
    int parent_node_id;     // Parent node ID
    };

    // Buffer to store 30 nodes
    InputDataNode input_buffer[30];

    PriorityQueue pq;
    std::srand(std::time(nullptr)); // Seed for random priorities

// After defining input_buffer and before/after queue insertion loop

for (int i = 0; i < 20; ++i) {
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
        node.child_ids[c] = 1 + std::rand() % 100;
    }
    pq.push(node);

// Print what is being inserted into the priority queue
std::cout << "Inserting into PriorityQueue: id=" << node.node_id
          << ", priority=" << node.priority
          << ", num_children=" << num_children
          << ", children=[";
for (int c = 0; c < num_children; ++c) {
    std::cout << node.child_ids[c] << " ";
}
std::cout << "]" << std::endl;

// Print what is being inserted into the input data buffer
std::cout << "Inserting into InputDataBuffer: index=" << i
          << ", parent_node_id=" << input_buffer[i].parent_node_id
          << ", basepair=" << std::bitset<2>(input_buffer[i].basepair)
          << std::endl;
}



    std::cout << "\nQueue size after insertion: " << pq.size() << std::endl;
    // Pop all nodes and print their info in priority order
    while (!pq.empty()) {
        const QueueNode& top = pq.top();
        int child_count = 0;
        for (int c = 0; c < 5; ++c) {
            if (top.child_ids[c] != -1) child_count++;
        }
        std::cout << "Popped node: id=" << top.node_id
                  << ", priority=" << top.priority
                  << ", num_children=" << child_count
                  << ", children=[";
        for (int c = 0; c < child_count; ++c) {
            std::cout << top.child_ids[c] << " ";
        }
        std::cout << "]" << std::endl;
        pq.pop();
    }
    std::cout << "Queue empty: " << std::boolalpha << pq.empty() << std::endl;

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