#pragma once
#include <queue>
#include <vector>
#include <functional>
#include <cstddef>
#include <array>

// Struct for queue elements
struct QueueNode {
    int priority;
    int node_id;
    std::array<int, 5> child_ids;

    // Comparison operator for min-heap (smallest priority first)
    bool operator>(const QueueNode& other) const {
        return priority > other.priority;
    }
};

class PriorityQueue {
public:
    // Push an item
    void push(const QueueNode& item);

    // Pop the smallest priority item
    void pop();

    // Get the smallest priority item
    const QueueNode& top() const;

    // Get the number of items
    size_t size() const;

    // Check if the queue is empty
    bool empty() const;

private:
    std::priority_queue<QueueNode, std::vector<QueueNode>, std::greater<QueueNode>> pq;
};