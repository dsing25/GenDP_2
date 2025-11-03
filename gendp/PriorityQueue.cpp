#include "PriorityQueue.h"

void PriorityQueue::push(const QueueNode& item) {
    pq.push(item);
}

void PriorityQueue::pop() {
    pq.pop();
}

const QueueNode& PriorityQueue::top() const {
    return pq.top();
}

size_t PriorityQueue::size() const {
    return pq.size();
}

bool PriorityQueue::empty() const {
    return pq.empty();
}