#include "PriorityQueue.h"
#include <iostream>
#include <vector>
#include <array>

int main() {
    const int NUM_NODES = 1000;
    std::vector<QueueNode> buffer(NUM_NODES);

    // Fill buffer with node ids and dummy priorities
    for (int i = 0; i < NUM_NODES; ++i) {
        buffer[i].node_id = i;
        buffer[i].priority = i; // or any function of i
        buffer[i].child_ids.fill(-1); // Initialize children to -1
    }

    // Assign children: every 10th node gets next 3 nodes as children
    for (int i = 0; i < NUM_NODES; i += 10) {
        for (int c = 0; c < 3; ++c) {
            if (i + c + 1 < NUM_NODES)
                buffer[i].child_ids[c] = i + c + 1;
        }
    }

    PriorityQueue pq;

    // Add every 10th node to the queue
    for (int i = 0; i < NUM_NODES; i += 10) {
        pq.push(buffer[i]);
    }

    std::cout << "Initial queue size: " << pq.size() << std::endl;

    // Pop nodes and print their info
    int pop_count = 0;
    while (!pq.empty() && pop_count < 20) { // Limit output for brevity
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
        ++pop_count;
    }

    std::cout << "Queue empty: " << std::boolalpha << pq.empty() << std::endl;
    return 0;
}