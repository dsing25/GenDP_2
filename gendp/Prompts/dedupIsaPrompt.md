# Caution
This is a very complex project. You must read deeply and make sure you understand what is asked of
you. Ask questions if you're unsure

# High Level
We will be implementing the dedup phase, i.e. pe_array controller magic instruction 16. 
We'll follow a similar procedure as we've used for moving the pe_array code into magic instructions
before. The first step is to remove all dependence on the c++ header files in the gwfa.h, and to set
up tiling between pe_array and pe. We won't worry about using the ISA like code just yet. That will
be the next step.

# References
To see other examples of how we did this, look in ../../gdp/Gendp at batchQueueProcessingPrompt.txt,
batchExtendToIsaPrompt.txt, gwfaContrMagicToIsaLikePrompt.txt. You can also look at previous commits
to see the evolution over time. Familiarize yourself deeply with these prompts and the change in the
code so you can see what our overall goal is. What direction we're headed in.

You must also look very deeply at gwfa.c the dedup/finalize stuff so you know what we're trying to
emulate in Detailed Pseudocode. I made significant changes to support tiling.

# Optimization Objectives
You should always keep these in your mind:
+ Simple is better than complicated (both for ease of implementation, and so that we execute fewer
  instructions)
+ Execute as few instructions as you can. Speed is essential, and fewer instructions lead to better
  performance because we don't have any fancy superscalar OOO processing or anything like that
+ Workload balancing is important. Where possible we want the PEs to execute in similar time, and we
  want the PEs to work while the controller is loading.
+ Memory latency should be masked where possible. We expect Main Memory latency to be 200 cycles.
  The pe_array therefore needs to be loading while the pe is operating on other data (pipelining).
  We do this by using ping pong buffers primarilly. We need the parallelism. pe processes while
  pe_array loads/writesback data
+ The controller is feeding 4 pes that are hungry for data. To keep up with demand, we need to use
  large mvdq 8 wide loads whenever possible. mvs will be really slow. Avoid them wherever possible.
+ Correctness is essential. You may not comprimise correctness
+ Minimize the number of instructions done within a loop. Hoist checks out of the loop if possible

# Procedural Notes
+ If you deviate from my plan or the pseudocode please let me know so I can approve.
+ Try to take small steps whenever possible so you don't dig yourself into a ditch of debugging.
+ Verify using gwfa_check_correctness.py 1 for simple and 2 for more detailed.

# Detailed Pseudocode

  With extra checks:
  if next_intv not sorted
	  sort next_intv
  merge (next_intv, intv)
  sort diags
  iterate through diags and merge runs
  iterate through diags and intv simultaneously and del forbidden diags


The high level flow should look like this
  sort unsorted intv
	merge old intv and now sorted intv
  sort unsorted diags
	merge old diags and now sorted diags
  iterate through diags and merge runs
  iterate through diags and intv simultaneously and del forbidden diags

Pseudocode for sorting and merging two sorted lists is shown below, followed by code for diag dedup.

FOR SORTING:
GENDP PSEUDOCODE

## Prelimaries
+ RADIX_NUM should probably be 4, that means RADIX_SIZE=16. This allows us to store things like the
	bin count in the registers
+ when sorting intv, the radix is just on the first data element, but we need to move the entire
	data element. this might require slightly different code.

## PE_ARRAY
for i < RADIX_NUM:
	//Each iteration we swap buffers, one contains the partially sorted list, one contains the list
	//that we're in the process of writing two
	# Phase 1.a git bin counts
		'''
		High level, we overlap the loading of a tile with compute on previous tile. The controller loads
		data into the pes in round robin manner using efficient mvdq. The pe processes the data by
		iterating through and sorting into RADIX_SIZE bins
		'''
		cursor = startOfDiags
		while (cursor < endOfDiags):
			tileCursor = tile0 == tileCursor ? tile1 : tile0 //a binary flip
			while (cursor < tileSize):
				for peid in range(4):
						mvdq S2[cursor+tileSizeXpeid:+8]->peid.S1[tileCursor:+8]
				tileCursor+=8
				cursor+=8
			pe.comp_binCount(currentTile)
		//At this point each pe has a count for each radix bin, so the controller will need to
		//accumulate those numbers getting a global bin count for each bin, which we can then use to
		//know exactly where to write things in the sorted array
	# Phase 1.b
		'''
		High level, we overlap loading of a tile by the pe_array with compute on previous tile by the
		pe as before. The controller again loads data into pes in round robin manner using mvdq. PEs
		produce RADIX_SIZE arrays where they have written the data. Then the controller will writeback
		the data from each of those arrays directly into the sorted bins. The order is important here.
		pe0 will always process the first tileSize elements, pe1 the next tileSize elements, and so on.
		When we writeback, we write pe0s data, then pe1 data, then  pe2 and so on. Each pe will need to
		write the number of elements in each bin, so that the pe_array can read that number and
		interleave the writes between pes. 
		'''
		cursor = startOfDiags
		while (cursor < endOfDiags):
			tileCursor = tile0 == tileCursor ? tile1 : tile0 //a binary flip
			while (cursor < tileSize):
				for peid in range(4):
						mvdq S2[cursor+tileSizeXpeid:+8]->peid.S1[tileCursor:+8]
				tileCursor+=8
				cursor+=8
			pe.comp_sort(currentTile)
			//Now we need to writeback the previous tile
			for each bin on the PEs:
				globalBinCount = read global bincount saved from phase 1.a
				peBinCounts = read the number of elements placed in this bin per pe. This'll be 4 16bit reg
				while i < max(peBinCounts):
					for peid in range(4):
						mvdq sortedBuffer[peBinCounts[peid] + globalBinCount+i:+8] = peid[binLoc + i]
						//obviously you'll need to do some loop peeling and masking here because not all pes
						//will have the same number of elements in each bin.
					i+=8
//List is now sorted!
				
PE CODES
comp_bin_count:
	'''
	This counts the size of the bins. Make sure you pipeline the loads so you're using compute
	instructions to process the prior while you begin the load of the next. You should be able to do
	this with registers if RADIX_SIZE <=16, but if its larger you'll need to load and update the bin
	count. Make sure to avoid race conditions where two increments hit the same bin. You'll need to
	handle that case
	'''
	double load first = tile[i:i+1]; i+=2
    for i < TILE_SIZE:
		//comp
		{
			binI = first[0] << RADIX_I; reg[binI]++
			binI = first[1] << RADIX_I; reg[binI]++
		}
		second = double load tile[i:i+1]; i+=2

		//comp
		{
			binI = second[0] << RADIX_I; reg[binI]++
			binI = second[1] << RADIX_I; reg[binI]++
		}
		first = double load tile[i:i+1]; i+=2

pe_comp_sort:
	'''
	The pe will maintain a bunch of bins, each overallocated so it won't run out of space, and it
	takes in a tile of data. It iterates through the tile of data and does the shift of the radix to
	determin binID, then it writes to that binID the data in the tile. It will also need to update
	counts sent to each bin, and write these to SPM (maybe the first element of each bin?) so the
	controller knows how many things to write. I haven't shown the pipelining as in comp_bin_count,
	but it should be nearly identical. This just shows assuming no pipelining.
	'''
	for i < TILE_SIZE:
		double load first = tile[i:i+1]; i+=2;
		binI = first[0] << RADIX_I
		bins[binCursor[binI]++] = first[0]
		binCount[binI]++;
		//same for first[1]
	'''

MERGING
'''
high level, we'll be doing a parallel merge path. The controller does a lg(n) binary search 4 times
to find offsets, then we tile with the pes and have them merge chunks.
'''
CONTROLLER
## Phase 1
	Do a binary search for merge path to over index i to find i such that A[i] == B[k - i] where A
	and B are the sorted lists to be merged. We do this four times for k = len(A)+len(B), 2k, 3k. We
	can do this in parallel, overlaping the requests. Note you'll need to do a wait_lsq after each
	request, which is a bit painful, but for now just leave it in it's own magic instruction. This
	gives the offsets of A and B so that we know which blocks each pe needs to process.
## Phase 2
	'''
	high level, we will need to tile this into two bricks so we can load the pe while we're doing
	compute on the previous tile/brick. Moves will need to be mvdq alternating between pes. You know
	the pattern by now. Things are a little more complicated this time because we might finish all of
	A but none of B in an iteration, so it'll be a little different. every 1xTilesize we check to see
	if either an A or B tile is exausted. If so, then we load the next tile. The PEs will manage the
	alternating of tiles possibly within one synchronization period. Below I explain clearer. You will
	need two regular tiled buffers for the output
	'''
	ld tile0 A
	ld tile0 B
	ld tile1 A
	ld tile1 B
	while not finished sorting:
    pe.compOneBlock() //4 cycles optimistically
		read pe SPM location marking if we finished tile A;
			if finished an A tile, load the next A to the finished tile (pe already moved to other tile)
		read pe SPM location marking if we finished tile B:
			if finished a B tile, load the next B to the finished tile (pe has already moved on)
		write back one block to mem with mvdq (here we know the block is exactly one blocksize)

pe.compOneBlock()
	'''
	You probably also need some guard so when you run out of A/B you finish. Controller just needs to
	do memcopy from MM to MM for the remaining at that point. No need to send it to PE.
	'''
	cursorA = 0
	cursorB = 0
	tileA = 0 //these can be 16 bit, or might just be constants in different code regions
	tileB = 0 //these can be 16 bit, or might just be constants in different code regions
	aVal = tileA[cursorA++]
	bVal = tileB[cursorB++]
	while i < blockSize:
		if aVal <= bVal:
			write aVal to sorted buffer
			aVal = tileA[cursorA++]
			if cursorA > tileLen:
				tileA update
				mark that tileA has changed
		else:
			write bVal to sorted buffer
			bVal = tileB[cursorB++]
			if cursorB > tileLen:
				tileB update
				mark that tileB has changed



DEDUP
'''
High level, we are merging three steps here. We merge overlapping intervals, we delete duplicated
diagonals and we delete diagonals in forbidden intervals. It is easiest to do all these things
simultaneously. Gets good data reuse.
'''
## Phase 1
	As in MERGING, start by doing a binary search over the start of each interval and the diagonal.
	This will give the three indices, is, which split the sorted lists.
## Phase 2
	The tiling is exactly the same as for MERGING. The only difference is that the output tile will
	have a variable length. You will need to read the length in from the S1 before you writeback.
	At the end you will have a diag array and a intv array per PE. Unfortunately, there will be
	"holes" in between, you'll need to do a straightforward copy with mvdq to compress all this space.
The PE compute is a bit more complicated. It'll look like this, I'm ignoring the tiling, which is
the same as in MERGE
PE_COMP
	cursorIntv = 0
	cursorDiag = 0
	intv = S1[cursorIntv++]
	//Merge intvs
	while newIntv.start <= intv.end: 
		newIntv[cursorIntv++]
		intv.end = newIntv.end
	writeback intv to tile
	diag = S1[cursorDiag++]
	while i < blockSize:
		while (newDiag == diag){
			newDiag = S1[cursorDiag++]
		while (diagId > intv.end):
			//Merge intvs
			while newIntv.start <= intv.end: 
				newIntv[cursorIntv++]
				intv.end = newIntv.end
			writeback intv to tile
		//Now we know the intv is up to date, diag is in or before
		if diagId < intv.start:
			writeback diag to diag tile
		//Otherwise diag was within the forbidden band, we don't writeback
