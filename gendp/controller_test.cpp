#include "PriorityQueue.h"
#include <iostream>
#include <vector>
#include <array>

int main() {
PriorityQueue pq;

    // Create some nodes
    QueueNode node1;
    node1.priority = 30;
    node1.node_id = 101;
    node1.child_ids = {201, 202, -1, -1, -1};

    QueueNode node2;
    node2.priority = 15;
    node2.node_id = 102;
    node2.child_ids = {203, -1, -1, -1, -1};

    QueueNode node3;
    node3.priority = 32;
    node3.node_id = 103;
    node3.child_ids = {-1, -1, -1, -1, -1};

    // Push nodes into the queue
    pq.push(node1);
    pq.push(node2);
    pq.push(node3);

    std::cout << "Initial queue size: " << pq.size() << std::endl;

    // Pop all nodes and print their info
    while (!pq.empty()) {
        const QueueNode& top = pq.top();
        std::cout << "Popped node: id=" << top.node_id
                  << ", priority=" << top.priority
                  << ", children=[";
        for (int i = 0; i < 5; ++i) {
            if (top.child_ids[i] != -1)
                std::cout << top.child_ids[i] << " ";
        }
        std::cout << "]" << std::endl;
        pq.pop();
    }

    std::cout << "Queue empty: " << std::boolalpha << pq.empty() << std::endl;

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