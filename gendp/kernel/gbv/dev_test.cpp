#include "../../alu_32.h"
#include "../../sys_def.h"
#include <iostream>
#include <iomanip>
#include "../../PriorityQueue.h"

// alu_execute is 32bit, alu_execute 8bit takes in 8 bits at a time then does 4 loops
// alu execute 4input is basically 2 input 32bit and alu 4inp 8bit is just 4 loops
// execute and 8bit execute work the same as the 4input versions. 

struct Slice {
    int VN;
    int VP;
    int scoreEnd;
};

void print_slice(const Slice& slice) {
    std::cout << "Slice:\n";
    std::cout << "  VN       = 0x" << std::hex << slice.VN << "\n";
    std::cout << "  VP       = 0x" << std::hex << slice.VP << "\n";
    std::cout << "  scoreEnd = 0x" << std::hex << slice.scoreEnd << "\n\n";
}

void gbv_core_v1() { // does 22 individual instructions
    alu_32 alu;
    Slice slice;
    int Eq = 0xDEADBEEF;      
    slice.VN = 0x12345678;    
    slice.VP = 0x9ABCDEF0;   
    int hinN = 0x00000000;    
    int hinP = 0x00000000;              

    int Xv = alu.execute(Eq, slice.VN, BWISE_OR); //line 7
    std::cout << "Xv        = 0x" << std::hex << Xv << "\n\n";

    Eq = alu.execute(Eq, hinN, BWISE_OR); //between lines 7-8
    std::cout << "Eq        = 0x" << std::hex << Eq << "\n\n";

    int temp1 = alu.execute(Eq, slice.VP, BWISE_AND);
    int temp2 = alu.execute(temp1, slice.VP, ADDITION);
    int temp3 = alu.execute(temp2, slice.VP, BWISE_XOR);
    int Xh = alu.execute(temp3, Eq, BWISE_OR); //line 8
    std::cout << "Xh        = 0x" << std::hex << Xh << "\n\n";

   
    temp1 = alu.execute(slice.VP, Xh, BWISE_OR);
    temp2 = alu.execute(temp1, 0, BWISE_NOT);
    int Ph = alu.execute(slice.VN, temp2, BWISE_OR); //line 9
    std::cout << "Ph        = 0x" << std::hex << Ph << "\n\n";

    int Mh = alu.execute(slice.VP, Xh, BWISE_AND); //line 10
    std::cout << "Mh        = 0x" << std::hex << Mh << "\n\n";

    temp1 = alu.execute(Mh, 0, LSHIFT_1); //line 16 + between lines 16-17
    int tempMh = alu.execute(temp1, hinN, BWISE_OR);
    std::cout << "tempMh        = 0x" << std::hex << tempMh << "\n\n";

    hinN = alu.execute(Mh, 0, RSHIFT_WORD); //line 11
    std::cout << "hinN        = 0x" << std::hex << hinN << "\n\n";

    temp1 = alu.execute(Ph, 0, LSHIFT_1); //line 15 + between lines 16-17      
    int tempPh = alu.execute(temp1, hinP, BWISE_OR); 
    std::cout << "tempPh    = 0x" << std::hex << tempPh << "\n\n";

    temp2 = alu.execute(Xv, tempPh, BWISE_OR); //line 17     
    temp3 = alu.execute(temp2, 0, BWISE_NOT);    
    slice.VP = alu.execute(tempMh, temp3, BWISE_OR);   
    std::cout << "slice.VP = 0x" << std::hex << slice.VP << "\n\n";

    hinP = alu.execute(Ph, 0, RSHIFT_WORD); //line 13
    std::cout << "hinP       = 0x" << std::hex << hinP << "\n\n";

    slice.VN = alu.execute(tempPh, Xv, BWISE_AND); //line 18
    std::cout << "slice.VN = 0x" << std::hex << slice.VN << "\n\n";
    
    slice.scoreEnd = alu.execute(slice.scoreEnd, hinN, SUBTRACTION); //line 12
    std::cout << "slice.scoreEnd  = 0x" << std::hex << slice.scoreEnd << "\n\n";
    
    slice.scoreEnd = alu.execute(slice.scoreEnd, hinP, ADDITION); //line 14
    std::cout << "slice.scoreEnd  = 0x" << std::hex << slice.scoreEnd << "\n\n";
    
    print_slice(slice);
    std::cout << "Ph vector = 0x" << std::hex << Ph << "\n";
    std::cout << "Mh vector = 0x" << std::hex << Mh << "\n";
}

void gbv_core_v2() { // does 16 individual instructions
    alu_32 alu;
    Slice slice;
    int Eq = 0xDEADBEEF;      
    slice.VN = 0x12345678;    
    slice.VP = 0x9ABCDEF0;   
    int hinN = 0x00000000;    
    int hinP = 0x00000000;              

    //can run the next two in parallel if possible ( i dont think it is, needs 2 cycles since 2 outputs)
    int Xv = alu.execute(Eq, slice.VN, BWISE_OR); //line 7
    std::cout << "Xv        = 0x" << std::hex << Xv << "\n\n";

    Eq = alu.execute(Eq, hinN, BWISE_OR); //between lines 7-8
    std::cout << "Eq        = 0x" << std::hex << Eq << "\n\n";

    // combine to 2 instructions 
    int temp1 = alu.execute(Eq, slice.VP, BWISE_AND);
    int temp2 = alu.execute(temp1, slice.VP, ADDITION);
    int temp3 = alu.execute(temp2, slice.VP, BWISE_XOR);
    int Xh = alu.execute(temp3, Eq, BWISE_OR); //line 8
    std::cout << "Xh        = 0x" << std::hex << Xh << "\n\n";

    // combine to 2 instructions
    temp1 = alu.execute(slice.VP, Xh, BWISE_OR);
    temp2 = alu.execute(temp1, 0, BWISE_NOT);
    int Ph = alu.execute(slice.VN, temp2, BWISE_OR); //line 9
    std::cout << "Ph        = 0x" << std::hex << Ph << "\n\n";

    int Mh = alu.execute(slice.VP, Xh, BWISE_AND); //line 10
    std::cout << "Mh        = 0x" << std::hex << Mh << "\n\n";

    // combine to 1 instruciton
    temp1 = alu.execute(Mh, 0, LSHIFT_1); //line 16 + between lines 16-17
    int tempMh = alu.execute(temp1, hinN, BWISE_OR);
    std::cout << "tempMh        = 0x" << std::hex << tempMh << "\n\n";

    hinN = alu.execute(Mh, 0, RSHIFT_WORD); //line 11
    std::cout << "hinN        = 0x" << std::hex << hinN << "\n\n";

    // combine to 1 instruction
    temp1 = alu.execute(Ph, 0, LSHIFT_1); //line 15 + between lines 16-17      
    int tempPh = alu.execute(temp1, hinP, BWISE_OR); 
    std::cout << "tempPh    = 0x" << std::hex << tempPh << "\n\n";

    // combine to 2 instructions
    temp2 = alu.execute(Xv, tempPh, BWISE_OR); //line 17     
    temp3 = alu.execute(temp2, 0, BWISE_NOT);    
    slice.VP = alu.execute(tempMh, temp3, BWISE_OR);   
    std::cout << "slice.VP = 0x" << std::hex << slice.VP << "\n\n";

    hinP = alu.execute(Ph, 0, RSHIFT_WORD); //line 13
    std::cout << "hinP       = 0x" << std::hex << hinP << "\n\n";

    slice.VN = alu.execute(tempPh, Xv, BWISE_AND); //line 18
    std::cout << "slice.VN = 0x" << std::hex << slice.VN << "\n\n";
    
    slice.scoreEnd = alu.execute(slice.scoreEnd, hinN, SUBTRACTION); //line 12
    std::cout << "slice.scoreEnd  = 0x" << std::hex << slice.scoreEnd << "\n\n";
    
    slice.scoreEnd = alu.execute(slice.scoreEnd, hinP, ADDITION); //line 14
    std::cout << "slice.scoreEnd  = 0x" << std::hex << slice.scoreEnd << "\n\n";
    
    print_slice(slice);
    std::cout << "Ph vector = 0x" << std::hex << Ph << "\n";
    std::cout << "Mh vector = 0x" << std::hex << Mh << "\n";
}

void test_popcount() {
    alu_32 alu;
    unsigned int test_vals[] = {0x0, 0x1, 0xF, 0xFF, 0x12345678, 0xFFFFFFFF, 0x80000000};
    int num_tests = sizeof(test_vals) / sizeof(test_vals[0]);

    std::cout << "Testing POPCOUNT:\n";
    for (int i = 0; i < num_tests; ++i) {
        int val = test_vals[i];
        int result = alu.execute_4input(val, 0, 0, 0, POPCOUNT);
        std::cout << "POPCOUNT(0x" << std::hex << val << ") = " << std::dec << result << "\n";
    }
    std::cout << std::endl;
}

void test_popcount_all() {
    alu_32 alu;

    // Test values for 32-bit and 8-bit lanes
    unsigned int test_vals[] = {0x0, 0x1, 0xF, 0xFF, 0x12345678, 0xFFFFFFFF, 0x80000000};
    int num_tests = sizeof(test_vals) / sizeof(test_vals[0]);

    std::cout << "Testing POPCOUNT (execute):\n";
    for (int i = 0; i < num_tests; ++i) {
        unsigned int val = test_vals[i];
        int result = alu.execute(val, 0, POPCOUNT);
        std::cout << "POPCOUNT (execute) 0x" << std::hex << val << " = " << std::dec << result << "\n";
    }
    std::cout << std::endl;

    std::cout << "Testing POPCOUNT (execute_8bit):\n";
    for (int i = 0; i < num_tests; ++i) {
        unsigned int val = test_vals[i];
        int result = alu.execute_8bit(val, 0, POPCOUNT);
        std::cout << "POPCOUNT (execute_8bit) 0x" << std::hex << val << " = " << std::dec << result << "\n";
    }
    std::cout << std::endl;

    std::cout << "Testing POPCOUNT (execute_4input):\n";
    for (int i = 0; i < num_tests; ++i) {
        unsigned int val = test_vals[i];
        int result = alu.execute_4input(val, 0, 0, 0, POPCOUNT);
        std::cout << "POPCOUNT (execute_4input) 0x" << std::hex << val << " = " << std::dec << result << "\n";
    }
    std::cout << std::endl;

    std::cout << "Testing POPCOUNT (execute_4input_8bit):\n";
    for (int i = 0; i < num_tests; ++i) {
        unsigned int val = test_vals[i];
        int result = alu.execute_4input_8bit(val, val, val, val, POPCOUNT);
        std::cout << "POPCOUNT (execute_4input_8bit) 0x" << std::hex << val << " = " << std::dec << result << "\n";
    }
    std::cout << std::endl;
}
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

    // test_popcount_all();
    //test_popcount();
   // gbv_core_v1();
    //gbv_core_v2();
    return 0;
}



