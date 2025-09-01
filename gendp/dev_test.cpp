#include "alu_32.h"
#include "sys_def.h"
#include <iostream>
#include <iomanip>

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

int main() {
    gbv_core_v1();
    gbv_core_v2();
    return 0;
}



