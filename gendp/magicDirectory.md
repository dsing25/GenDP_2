Magic Instruction Directory
===========================

Encoding: (magic_id << 8) | mask
  Mask bit 0 = P2 buffer select
  Mask bit 1 = FIN0 tile select


Controller Magic Instructions (pe_array.cpp)
---------------------------------------------

ID  Mask        Phase  Description
--  ----------  -----  --------------------------------------------------------
 1  --          init   Reconstruct subgraph, call gwfa_init, init counters
 2  --          P1     Extend one step at distance gr[12]
 3  --          P1     Print score, zero va_regfile
 4  --          P1     Begin step: sync gr->statics, call gwfa_begin_step_tiled
 5  --          debug  va_regfile[0]!=0: dump wavefront trace; else: final score
 6  --          debug  Dump SPM M/D/I wavefront regions to files
 7  bit0        P1     Tile load diags: MM -> S1C staging
 8  bit0        P1     Tile load sequences: S1C + S2 -> PE SPM, 4-diag chunks
 9  bit0        P1     Tile writeback: PE SPM -> MM (pushed, intv, boundary)
10  --          P2     Cross-node propagation: call gwfa_phase2, update n_a
12  --          P1     FIFO flush: write boundary element to B queue in MM
14  bit0        P2     P2 tile load: pop A queue (MM) -> PE SPM P2 buffer
15  bit0+bit1   P2     P2 tile writeback + FIN0 load:
                         Sec 3: collect fin0/fin1 diags PE SPM -> S1C
                         Sec 4: prefetch arc_off S2 -> S1C
                         Sec 5: block-load arcs S2 -> S1C, process fin1 -> B
                         Sec 6: fin0_load_batch S1C -> FIN0 tile
16  --          P2     P2 finalize: sync gr->statics, call gwfa_phase2_finalize
17  --          score  Set score = gr_lo[12] (current edit distance)
18  bit1        P2     FIN0 writeback: read PE FIN0 output (A/B/HA) -> MM
20  bit1        P2     FIN0 subsequent batch: resume multipass fin0_load_batch

Magic Status
-------------
PassIDs 
NV    Not Reviewed
FL    Flow/Loops correct
ISA   At ISA Level
ISAO  At ISA Level has had a pass of optimizatoin
RL    Ready For Lowering
D     Deferred/Not Significant
L     Legacy

ID  Status
--  ------
 1  D
 2  L
 3  D
 4  D
 5  D
 6  WFA
 7  RL
 8  ISA
 9  ISA
10  L
12  ISAO
14  ISA
15  ISA
16  D //handling this seperate project
17  D
18  ISA
20  NV



PE Magic Instructions (pe.cpp)
-------------------------------

ID  Mask        Phase  Description
--  ----------  -----  --------------------------------------------------------
 8  bit0        P1     PE-side tile load: receive seq data into SPM
11  bit0        P1     Boundary sort: compare-swap last/first B between PEs
13  bit0        P2     P2 extend+classify: process diags, emit pushed/intv/fin0/fin1
19  bit1        P2     PE FIN0: hash check + char match, emit A/B/HA outputs


Mask Bit Encoding
-----------------

Bit  Meaning             Values
---  ------------------  -----------------------------------
  0  P2 buffer select    0 = BUF0/P2_BASE, 1 = BUF1/P2B_BASE
  1  FIN0 tile select    0 = FIN0_A,        2 = FIN0_B

Magic 15 uses both bits: bit 0 selects which P2 buffer to read,
bit 1 selects which FIN0 tile to load into.
