#include <ctype.h>
#include <string>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <emmintrin.h>
#include <sys/time.h>
#include <getopt.h>
#include <tuple>
#include "omp.h"
#include "../../compute_unit_32.h"
#include "../../comp_decoder.h"

typedef uint32_t Word;

class WordSlice
{
public:
    WordSlice() :
        VP(0),
        VN(0),
        scoreEnd(0)
    {}
    WordSlice(Word VP, Word VN, int scoreEnd) :
        VP(VP),
        VN(VN),
        scoreEnd(scoreEnd)
    {}
    Word VP;
    Word VN;
    int scoreEnd;
};

static inline std::tuple<WordSlice, Word, Word> getNextSlice(Word Eq, WordSlice slice, Word hinP, Word hinN)
{
    //http://www.gersteinlab.org/courses/452/09-spring/pdf/Myers.pdf
    //pages 405 and 408

    Word Xv = Eq | slice.VN; //line 7
    Eq |= hinN; //between lines 7-8
    Word Xh = (((Eq & slice.VP) + slice.VP) ^ slice.VP) | Eq; //line 8
    Word Ph = slice.VN | ~(Xh | slice.VP); //line 9
    Word Mh = slice.VP & Xh; //line 10
    Word tempMh = (Mh << 1) | hinN; //line 16 + between lines 16-17
    hinN = Mh >> (31); //line 11
    Word tempPh = (Ph << 1) | hinP; //line 15 + between lines 16-17
    slice.VP = tempMh | ~(Xv | tempPh); //line 17
    hinP = Ph >> (31); //line 13
    slice.VN = tempPh & Xv; //line 18
    slice.scoreEnd -= hinN; //line 12
    slice.scoreEnd += hinP; //line 14

    return std::make_tuple(slice, Ph, Mh);
}

static inline std::tuple<WordSlice, Word, Word> getNextSlice_debug(Word Eq, WordSlice slice, Word hinP, Word hinN)
{
    std::cout << "Initial: Eq=0x" << std::hex << Eq << " VN=0x" << slice.VN << " VP=0x" << slice.VP
              << " hinP=" << std::dec << hinP << " hinN=" << hinN << " scoreEnd=" << slice.scoreEnd << std::endl;

    Word Xv = Eq | slice.VN; //line 7
    std::cout << "Xv = Eq | VN: 0x" << std::hex << Xv << std::endl;

    Eq |= hinN; //between lines 7-8
    std::cout << "Eq |= hinN: 0x" << std::hex << Eq << std::endl;

    Word Xh = (((Eq & slice.VP) + slice.VP) ^ slice.VP) | Eq; //line 8
    std::cout << "Xh = (((Eq & VP) + VP) ^ VP) | Eq: 0x" << std::hex << Xh << std::endl;

    Word Ph = slice.VN | ~(Xh | slice.VP); //line 9
    std::cout << "Ph = VN | ~(Xh | VP): 0x" << std::hex << Ph << std::endl;

    Word Mh = slice.VP & Xh; //line 10
    std::cout << "Mh = VP & Xh: 0x" << std::hex << Mh << std::endl;

    Word tempMh = (Mh << 1) | hinN; //line 16 + between lines 16-17
    std::cout << "tempMh = (Mh << 1) | hinN: 0x" << std::hex << tempMh << std::endl;

    hinN = Mh >> (31); //line 11
    std::cout << "hinN = Mh >> 31: " << std::dec << hinN << std::endl;

    Word tempPh = (Ph << 1) | hinP; //line 15 + between lines 16-17
    std::cout << "tempPh = (Ph << 1) | hinP: 0x" << std::hex << tempPh << std::endl;

    slice.VP = tempMh | ~(Xv | tempPh); //line 17
    std::cout << "VP = tempMh | ~(Xv | tempPh): 0x" << std::hex << slice.VP << std::endl;

    hinP = Ph >> (31); //line 13
    std::cout << "hinP = Ph >> 31: " << std::dec << hinP << std::endl;
	std::cout << "scoreEnd -= hinN: " << std::dec << slice.scoreEnd << std::endl;

    slice.VN = tempPh & Xv; //line 18
    std::cout << "VN = tempPh & Xv: 0x" << std::hex << slice.VN << std::endl;

    slice.scoreEnd -= hinN; //line 12
    std::cout << "scoreEnd -= hinN: " << std::dec << slice.scoreEnd << std::endl;

    slice.scoreEnd += hinP; //line 14
    std::cout << "scoreEnd += hinP: " << std::dec << slice.scoreEnd << std::endl;

    return std::make_tuple(slice, Ph, Mh);
}


void getNextSlice_accelerator(Word Eq, WordSlice &slice, Word hinP, Word hinN, Word &Ph, Word &Mh)
{
	Word Xh = 0, Xv = 0, tempMh = 0, tempPh = 0, scoreBefore = 0, scoreEnd = 0;
	Word temp1 = 0, temp2 = 0, temp3 = 0;

	Word regfile[32];

	regfile[0]  = Eq;
	regfile[1]  = slice.VN;
	regfile[2]  = slice.VP;
	regfile[3]  = hinN;
	regfile[4]  = hinP;
	regfile[5]  = Xh;
	regfile[6]  = Xv;
	regfile[7]  = Ph;
	regfile[8]  = Mh;
	regfile[9]  = tempMh;
	regfile[10] = tempPh;
	regfile[11] = scoreBefore;
	regfile[12] = slice.scoreEnd;
	// regfile[13] = child_vn;
	// regfile[14] = child_vp;
	// regfile[15] = child_sbefore;
	// regfile[16] = child_send;
	// regfile[17] = merged_vn;
	// regfile[18] = merged_vp;
	// regfile[19] = merged_sbef;
	// regfile[20] = merged_send;
	// regfile[21] = parents;
	// regfile[22] = Eq_index;
	regfile[23] = temp1;
	regfile[24] = temp2;
	regfile[25] = temp3;
	// regfile[26] = temp4;
	// regfile[27] = temp5;
	// regfile[28] = temp6;
	// regfile[29] = temp7;
	// regfile[30] = temp8;
	// regfile[31] = temp9;

	// main compute starts here

	regfile[6] = regfile[0] | regfile[1]; 									// Xv = Eq | VN
	regfile[0] = regfile[0] | regfile[3];             						// Eq |= hinN

	regfile[23] = regfile[0] & regfile[2];      							// temp1 = Eq & VP
	regfile[24] = regfile[23] + regfile[2];     							// temp2 = temp1 + VP
	regfile[25] = regfile[24] ^ regfile[2];     							// temp3 = temp2 ^ VP
	regfile[5]  = regfile[25] | regfile[0];     							// Xh = temp3 | Eq

	regfile[23] = regfile[2] | regfile[5];      							// temp1 = VP | Xh
	regfile[24] = ~regfile[23];                 							// temp2 = ~temp1
	regfile[7]  = regfile[1] | regfile[24];     							// Ph = VN | temp2

	regfile[8] = regfile[2] & regfile[5]; 									// Mh =  VP & Xh
	regfile[23] = regfile[8] << 1;         									// temp1 = Mh << 1
	regfile[9]  = regfile[23] | regfile[3]; 								// tempMh = temp1 | hinN

	regfile[3]  = regfile[8] >> 31; 										// hinN = Mh >> (word)
	regfile[23] = regfile[7] << 1;                                       	// temp1 = Ph << 1
	regfile[10] = regfile[23] | regfile[4];                              	// tempPh = temp1 | hinP

	regfile[24] = regfile[6] | regfile[10];      							// temp2 = Xv | tempPh
	regfile[25] = ~regfile[24];                  							// temp3 = ~temp2
	regfile[2]  = regfile[9] | regfile[25];      							// VP = tempMh | temp3

	regfile[4]  = regfile[7] >> 31;        									// hinP = Ph >> (word)
	regfile[1]  = regfile[10] & regfile[6];									// VN = tempPh & Xv

	regfile[12] = regfile[12] - regfile[3]; 								// scoreEnd -= hinN
	regfile[12] = regfile[12] + regfile[4]; 								// scoreEnd += hinP

	slice.VN = regfile[1];
	slice.VP = regfile[2];
	slice.scoreEnd = regfile[12];
	Ph = regfile[7];
	Mh = regfile[8];

}

void getNextSlice_accelerator_debug(Word Eq, WordSlice &slice, Word hinP, Word hinN, Word &Ph, Word &Mh)
{
	Word Xh = 0, Xv = 0, tempMh = 0, tempPh = 0, scoreBefore = 0, scoreEnd = 0;
	Word temp1 = 0, temp2 = 0, temp3 = 0;

	Word regfile[32];

	regfile[0]  = Eq;
	regfile[1]  = slice.VN;
	regfile[2]  = slice.VP;
	regfile[3]  = hinN;
	regfile[4]  = hinP;
	regfile[5]  = Xh;
	regfile[6]  = Xv;
	regfile[7]  = Ph;
	regfile[8]  = Mh;
	regfile[9]  = tempMh;
	regfile[10] = tempPh;
	regfile[11] = scoreBefore;
	regfile[12] = slice.scoreEnd;
	// regfile[13] = child_vn;
	// regfile[14] = child_vp;
	// regfile[15] = child_sbefore;
	// regfile[16] = child_send;
	// regfile[17] = merged_vn;
	// regfile[18] = merged_vp;
	// regfile[19] = merged_sbef;
	// regfile[20] = merged_send;
	// regfile[21] = parents;
	// regfile[22] = Eq_index;
	regfile[23] = temp1;
	regfile[24] = temp2;
	regfile[25] = temp3;
	// regfile[26] = temp4;
	// regfile[27] = temp5;
	// regfile[28] = temp6;
	// regfile[29] = temp7;
	// regfile[30] = temp8;
	// regfile[31] = temp9;

	// main compute starts here
	std::cout << "\n" << std::endl;
	std::cout << "\n" << std::endl;

	std::cout << "Initial: Eq=0x" << std::hex << regfile[0]
			<< " VN=0x" << regfile[1]
			<< " VP=0x" << regfile[2]
			<< " hinP=" << std::dec << regfile[4]
			<< " hinN=" << regfile[3]
			<< " scoreEnd=" << regfile[12] << std::endl;

    regfile[6] = regfile[0] | regfile[1]; // Xv
    std::cout << "Xv = Eq | VN: 0x" << std::hex << regfile[6] << std::endl;

    regfile[0] = regfile[0] | regfile[3]; // Eq |= hinN
    std::cout << "Eq |= hinN: 0x" << std::hex << regfile[0] << std::endl;

    regfile[23] = regfile[0] & regfile[2]; // temp1
    regfile[24] = regfile[23] + regfile[2]; // temp2
    regfile[25] = regfile[24] ^ regfile[2]; // temp3
    regfile[5]  = regfile[25] | regfile[0]; // Xh
    std::cout << "Xh = (((Eq & VP) + VP) ^ VP) | Eq: 0x" << std::hex << regfile[5] << std::endl;

    regfile[23] = regfile[2] | regfile[5]; // temp1
    regfile[24] = ~regfile[23]; // temp2
    regfile[7]  = regfile[1] | regfile[24]; // Ph
    std::cout << "Ph = VN | ~(Xh | VP): 0x" << std::hex << regfile[7] << std::endl;

    regfile[8] = regfile[2] & regfile[5]; // Mh
    std::cout << "Mh = VP & Xh: 0x" << std::hex << regfile[8] << std::endl;

    regfile[23] = regfile[8] << 1; // temp1
    regfile[9]  = regfile[23] | regfile[3]; // tempMh
    std::cout << "tempMh = (Mh << 1) | hinN: 0x" << std::hex << regfile[9] << std::endl;

    regfile[3]  = regfile[8] >> 31; // hinN
    std::cout << "hinN = Mh >> 31: " << std::dec << regfile[3] << std::endl;

    regfile[23] = regfile[7] << 1; // temp1
    regfile[10] = regfile[23] | regfile[4]; // tempPh
    std::cout << "tempPh = (Ph << 1) | hinP: 0x" << std::hex << regfile[10] << std::endl;

    regfile[24] = regfile[6] | regfile[10]; // temp2
    regfile[25] = ~regfile[24]; // temp3
    regfile[2]  = regfile[9] | regfile[25]; // VP
    std::cout << "VP = tempMh | ~(Xv | tempPh): 0x" << std::hex << regfile[2] << std::endl;

    regfile[4]  = regfile[7] >> 31; // hinP
    std::cout << "hinP = Ph >> 31: " << std::dec << regfile[4] << std::endl;

    regfile[1]  = regfile[10] & regfile[6]; // VN
    std::cout << "VN = tempPh & Xv: 0x" << std::hex << regfile[1] << std::endl;

    regfile[12] = regfile[12] - regfile[3]; // scoreEnd -= hinN
    std::cout << "scoreEnd -= hinN: " << std::dec << regfile[12] << std::endl;

    regfile[12] = regfile[12] + regfile[4]; // scoreEnd += hinP
    std::cout << "scoreEnd += hinP: " << std::dec << regfile[12] << std::endl;

    slice.VN = regfile[1];
    slice.VP = regfile[2];
    slice.scoreEnd = regfile[12];
    Ph = regfile[7];
    Mh = regfile[8];

}

static WordSlice flattenWordSlice_accelerator(WordSlice slice, size_t row)
	{
		Word mask = 0;

		regfile[1] = slice.VN;
		regfile[2] = slice.VP;
		regfile[12] = slice.scoreEnd;
		regfile[23] = row; // this would cause a bitshift that is unknown, implementing in ISA will be hard
		regfile[24] = mask;

		regfile[24] = WordConfiguration<Word>::AllOnes << regfile[23]; 
		regfile[24] = ~regfile[24]; // gets mask

		regfile[25] = ~regfile[24]; // gets ~mask
		regfile[26] = regfile[2] & regfile[25]; // VP & ~mask
		regfile[27] = WordConfiguration<Word>::popcount(regfile[26]); // popcount of vp & ~mask
		regfile[12] = regfile[12] - regfile[27]; // update scoreend - popcount

		regfile[26] = regfile[1] & regfile[25]; // VN & ~mask
		regfile[27] = WordConfiguration<Word>::popcount(regfile[26]); // popcount of vn & ~mask
		regfile[12] = regfile[12] + regfile[27]; // update scoreend + popcount

		regfile[2] = regfile[2] & regfile[24];
		regfile[1] = regfile[1] & regfile[24];

		slice.VN = regfile[1];
		slice.VP = regfile[2];
		slice.scoreEnd = regfile[12];

		return slice;
	}


int main() {
    // Example input values
    Word Eq = 0xF0F0F0F0;
    WordSlice slice_ref(0xAAAAAAAA, 0x55555555, 0);
    WordSlice slice_acc = slice_ref; 
    Word hinP = 1;
    Word hinN = 0;

    // Run reference implementation
    auto result_tuple = getNextSlice(Eq, slice_ref, hinP, hinN);
    WordSlice slice_ref_out = std::get<0>(result_tuple);
    Word Ph_ref = std::get<1>(result_tuple);
    Word Mh_ref = std::get<2>(result_tuple);

    // Run accelerator implementation
	Word Ph_acc, Mh_acc;
	getNextSlice_accelerator(Eq, slice_acc, hinP, hinN, Ph_acc, Mh_acc);

    // Print results
    std::cout << "getNextSlice results:" << std::endl;
    std::cout << "  VP:       0x" << std::hex << slice_ref_out.VP << std::endl;
    std::cout << "  VN:       0x" << std::hex << slice_ref_out.VN << std::endl;
    std::cout << "  scoreEnd: " << std::dec << slice_ref_out.scoreEnd << std::endl;
    std::cout << "  Ph:       0x" << std::hex << Ph_ref << std::endl;
    std::cout << "  Mh:       0x" << std::hex << Mh_ref << std::endl;

    std::cout << "\naccelerator_compute results:" << std::endl;
    std::cout << "  VP:       0x" << std::hex << slice_acc.VP << std::endl;
    std::cout << "  VN:       0x" << std::hex << slice_acc.VN << std::endl;
    std::cout << "  scoreEnd: " << std::dec << slice_acc.scoreEnd << std::endl;
    std::cout << "  Ph:       0x" << std::hex << Ph_acc << std::endl;
    std::cout << "  Mh:       0x" << std::hex << Mh_acc << std::endl;

    // Compare results
    bool match = (slice_ref_out.VP == slice_acc.VP) &&
                 (slice_ref_out.VN == slice_acc.VN) &&
                 (slice_ref_out.scoreEnd == slice_acc.scoreEnd);

    std::cout << "\nComparison: " << (match ? "PASS" : "FAIL") << std::endl;

    return 0;
}