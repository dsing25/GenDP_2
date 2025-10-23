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
#include "omp.h"
#include "ksw.h"
#include "compute_unit_32.h"
#include "comp_decoder.h"



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
    hinN = Mh >> (WordConfiguration<Word>::WordSize-1); //line 11
    Word tempPh = (Ph << 1) | hinP; //line 15 + between lines 16-17
    slice.VP = tempMh | ~(Xv | tempPh); //line 17
    hinP = Ph >> (WordConfiguration<Word>::WordSize-1); //line 13
    slice.VN = tempPh & Xv; //line 18
    slice.scoreEnd -= hinN; //line 12
    slice.scoreEnd += hinP; //line 14

    return std::make_tuple(slice, Ph, Mh);
}


void accelerator_compute(Word Eq, WordSlice &slice, Word hinP, Word hinN)
{
	int Xh = 0, Xv = 0, Ph = 0, Mh = 0, tempMh = 0, tempPh = 0, scoreBefore = 0, scoreEnd = 0;
	int temp1 = 0, temp2 = 0, temp3 = 0;

	int regfile[32];

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
	regfile[12] = scoreEnd;
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
	Word Ph = regfile[7];
	Word Mh = regfile[8];

}

void accelerator_register(const uint8_t *target, const uint8_t *query, int match, int mismatch, int tlen, 
    int qlen, int *begin_origin, int *ending_origin, int *begin_align, int *ending_align, int *H_init, eh_t *eh, 
    int gap_o, int gap_e, int *max, int *max_i, int *max_j, int *max_ie, int *gscore, int *max_off, int64_t* numCellsComputed, int print_score) {
	// printf("accelerator_register\n");
	int tmp, max_H = 0, m_j = 0;
	int H_diag = 0, H_left = 0, E_up = 0, F_left = 0, E, F, H = 0;
	int i = 0, j = 0, beg, end;

	int regfile[32];

	regfile[0] = 0;							// constant
	regfile[1] = match;						// constant	
	regfile[2] = mismatch;					// constant	64
	regfile[3] = -gap_o;					// constant
	regfile[4] = -gap_e;					// constant
	regfile[5] = 1;							// constant

	regfile[6] = target[i];					// row initializaiton
	regfile[7] = i;							// row initialization
	regfile[8] = j;							// row initialization and update in the cell
	regfile[9] = max_H;						// row initialization and update in the cell
	regfile[10] = m_j;						// row initialization and update in the cell	

	regfile[11] = query[j];					// from prev pe
	regfile[12] = H_diag;					// from prev pe / fifo
	regfile[13] = E_up;						// from prev pe / fifo
	regfile[14] = H_left;					// update in the cell
	regfile[15] = F_left;					// update in the cell
	regfile[16] = H;						// update in the cell
	// regfile[17];				tmp
	// regfile[18];				tmp
	// regfile[19];				tmp
	// regfile[20];				tmp

	// regfile[21];	qlen
	// regfile[22]; tlen
	// regfile[23]; mlen		tmp
	// regfile[24]; max			output
	// regfile[25]; exit0
	// regfile[26]; gscore		output
	// regfile[27]; max_ie		output
	// regfile[28]; qle			output
	// regfile[29]; tle			output
	// regfile[30]; max_off		output

	for (i = 0; i < tlen; ++i) {
		F_left = 0; max_H = 0; m_j = 0;
		beg = begin_align[i]; end = ending_align[i]; 

		regfile[7] = i;
		regfile[8] = beg-1;
		regfile[9] = regfile[0];												// max_H = 0
		regfile[10] = regfile[0];												// m_j = 0
		regfile[15] = regfile[0];												// F_left = 0
		regfile[14] = H_init[i];												// H_left = H_init[i]

		// beg = begin_origin[i]; end = ending_origin[i]; 
		H_left = H_init[i];
		int qlen_origin = ending_origin[i] - begin_origin[i];
		if (qlen_origin >= 0) (*numCellsComputed) += qlen_origin;

		// printf("%d %d\n", beg, end);
		for (j = beg; j < end; j++) {
		// for (j = begin_origin[i]; j < ending_origin[i]; j++) {
		// 	(*numCellsComputed)++;
			eh_t *p = &eh[j];

			// comp_mux

			H_diag = p->h;					// H(i-1,j-1)
			E_up = p->e;					// E(i-1,j)

			regfile[12] = p->h;														// H_diag
			regfile[13] = p->e;														// E_up

			regfile[17] = comp_mux(target[i], query[j], match, mismatch);			// S = match_score(query, ref)
			regfile[17] = regfile[12] + regfile[17];								// H_diag_S = H_diag + S
			regfile[8] = regfile[8] + regfile[5];									// j++;

			regfile[12] = regfile[12] > regfile[0] ? regfile[17] : regfile[0];		// H_diag = H_diag > 0 ? H_diag_S : 0
			regfile[18] = regfile[12] + (regfile[3] + regfile[4]);					// tmp = H_diag - (gap_o + gap_e)

			regfile[12] = regfile[12] > regfile[0] ? regfile[17] : regfile[0];		// H_diag = H_diag > 0 ? H_diag_S : 0
			regfile[16] = regfile[15] > regfile[13] ? regfile[15] : regfile[13];	// H = F_left > E_up ? F_left : E_up
			regfile[16] = regfile[16] > regfile[12] ? regfile[16] : regfile[12];	// H = H > H_diag ? H : H_diag;

			regfile[10] = regfile[9] > regfile[16] ? regfile[10] : regfile[8];		// m_j = max_H > H? m_j : j
			regfile[9] = regfile[9] > regfile[16] ? regfile[9] : regfile[16];		// max_H = max_H > H? max_H : H

			regfile[20] = regfile[13] + regfile[4];									// E_up -= gap_e
			regfile[13] = regfile[18] > regfile[0]? regfile[18] : regfile[0];		// tmp = tmp > 0? tmp : 0
			regfile[13] = regfile[13] > regfile[20] ? regfile[13] : regfile[20];	// E = E_up > tmp? E_up : tmp
			
			regfile[19] = regfile[15] + regfile[4];									// F_left -= gap_e
			regfile[15] = regfile[18] > regfile[0]? regfile[18] : regfile[0];		// tmp = tmp > 0? tmp : 0
			regfile[15] = regfile[15] > regfile[19] ? regfile[15] : regfile[19];	// F = F_left > tmp? F_left : tmp

			p->h = regfile[14];
			regfile[14] = regfile[16];
			p->e = regfile[13];

			// p->h = H_left;          		// save H(i,j-1) for the next row
			// H_left = H;						// save H(i,j) to H_left for the next column (no need for HW)
			// p->e = E;						// save E(i+1,j) for the next row (no need for HW)
			// F_left = F;

			max_H = regfile[9];
			m_j = regfile[10];
			H_left = regfile[14];

		}
		eh[end].h = H_left; eh[end].e = 0;

		if (end == qlen) {					// software
			*max_ie = *gscore > H_left? *max_ie : i;
			*gscore = *gscore > H_left? *gscore : H_left;
		}
		if (max_H == 0) {
			// printf("break\n");
			break;
		}
		if (max_H > *max) {
			*max = max_H, *max_i = i, *max_j = m_j;
			*max_off = *max_off > abs(m_j - i)? *max_off : abs(m_j - i);
		}

		// update beg and end for the next round
		for (j = beg; j < end && eh[j].h == 0 && eh[j].e == 0; ++j);
		beg = j;
		for (j = end; j >= beg && eh[j].h == 0 && eh[j].e == 0; --j);
		end = j + 2 < qlen? j + 2 : qlen;
		beg = 0; end = qlen; // uncomment this line for debugging
	}
	// printf("%ld\n", (*numCellsComputed));
}