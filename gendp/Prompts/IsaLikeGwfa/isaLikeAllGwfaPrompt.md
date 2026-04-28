# High level
We have created a bunch of magic instructions to do gwfa and we are now ready to bring them one step
closer to ISA like. We will leave them as c++, but you should account for:
+ VLIW slots and RAWs (pair data instructions in blocks of twos that will execute together in the
  same cycle. Make sure no RAWs between these pairs)
+ efficient mvdq round robin pe load loops. streaming load loops from controller should be round 
  robin to hit different bank groups, and they should be mvdq instead of mv so they get good
  bandwidth
+ latency of s1/spm/s2/mm accounted for. We should never use a mm that we have loaded until after a
  waitLSQ. If between magics, put the waitLSQ in the ISA. If within a magic, then wait LSQ should be
  within the magic as a comment. S1 has latency one cylce. spm has latency 2 cycles (means if you
  load you can't have an immediate use. You must wait a cycle. S2 should have a waitlsq between like
  MM.
+ gotos instead of if/else/for/while. Except for macros like for i in range 4
+ each line is one instruction, meaning you can't do more than one genp operation in a line.
+ examples of well polished instructions are controller 7,8,9 and pe 8,13. Don't worry about compute
  instructions for pes. We'll do that later.
+ You can't invent variables. Use registers, and compile time constants when you can.
You're task is to rewrite the magic without changing correctness to make it ready for ISA lowering.
When done, you should be able to directly translate from the code you've written to gendp ISA. The
only remaining thing to be done is fixing up the pe compute instructions for better performance.
# General
+ delete deprecated controller magic: magic 2 and magic 10, magic 26
+ Leave the following magic instructions alone. We will not work on them: 1, 3, 4, 5, 6, 17
+ All other instructions should be lowered to the levels of 7,8,9 for the controller, or 8,13 for
  the pe. For pe, don't worry about the compute instructions just yet, but make sure that the other
  instructions are gotos, isa like, registers no variables, macro loops are fine. Everything should
  be paired VLIW
+ Add an LSQ wait between the controller magic 7 and magic 8 because they are dependent in ISA
  generator
+ Rename SORT_BIN_REG. As far as I can tell, it is a scratchpad region not a register
+ You should always use mvdq with loop peeling round robin in pes. Means mvdq to pe0 then pe1, 2, 3
  then mvdq to pe 0 again. Scalar moves one at a time are only used in very speciallized situations
  where the data is not contiguous (e.g. graph lookups). This is a general rule, and where you see
  such a incorrect loop, you should fix it.
+ On the controller we don't have min or max. You'll need to use simple branch conditions to achieve
  that behaviour.
+ We need to use registers not variables. You don't have access to variables. You're writing
  assembly
# Procedural
+ I have given very specific notes for some things which I have seen, but I have surely missed many
  problems. I expect you to look through all the magic instructions and see if you see the same
  problems in other magic instructions. See if there are similar errors that I have missed. I expect
  there to be many and you should find all of them.
+ Go very slowly. Test incremental changes so you can debug them easily. You should do one magic
  instruction at a time where possible (though some changes affect multiple magic instructions.
+ Do general passes over all instructions, but also make sure you address the specific feedback
  below. I would recommend addressing the specific feedback first.
+ The current code works. Anything that causes the verification to fail is a bug you have introduced
  and must be corrected before moving on. Checkpoint frequently so you can revert changes if
  necessary
+ There are many tasks in this work. Make a very large and detailed plan to address them. Make sure
  you understand the code. For the most part they are independent so you can tackle one magic
  instruction at a time and then clear context, but keep memories of bugs you've encountered so you
  can fix them, and refresh the general principles
+ Read the simulator, and docs and wfa_instruction generator to see what operations are supported by
  gendp
+ Note that we are allowing pipelined spm access, so you can do two spm loads back to back, but the
  latency is still 2 cycles.
# References
+ Take a look at other prompts in this directory as well as in the directory: /data4/kaplannp/GenDP2/gdp/gendp/Prompts
+ Docs and the source code for gendp is good too
+ if you look at instrcution generator especially for wfa you'll get a sense of what is legal.
# Optimization objectives
Keep these in mind:
+ use mvdq, mvd when possible to get good bandwidth
+ stream loads should alternate between pes to minimize bank conflicts
+ fewer instructions is better
+ loops are most important. Hoisting boundary checks out of loops is a great way to improve
  performance.
+ Be efficient
+ compile time constants are great. Use them if you can
+ Try to avoid redundant compuation
+ use the half registers if you can to get more register count and to remove some bitshifts like >>
  16
# Verification
Verify frequently so you can trace bugs directly to changes you made.
Use gwfa_check_correctness -t 56 with 56 threads. 1 is fast but will not catch all bugs. 2 is
slower, but must pass completely.
# Specific Magic Instructions Problems Noted
## Controller:
### magic 18
  + gwfa_get..off is just constants into MM. They should be constants at the start of magic
    instead of function calls.
### Magic 19
  + flip the loop going through radix bins with the pe loop. pes should always be on the inside of
    the loop for avoiding bank conflicts, and I think you can avoid putting this stuff in s1c in
    that case. If you can just load directly into registers it'll be even faster
### Magic 20
  + modify fin0_load_batch such that it does not return a value. Otherwise it looks fine.
  + line 613 of load batch sets gr[9] = spm[gr[8]]] >> 16; Multiple issues. Firstly, this is two isa
  ins, one load one shift. Second, you can't immediately operate on Spm results. There are two
  cycles of latency. You should try to reorder other instructions into the gap between the spm load 
  and the shift. This will allow you to mask the latency. Thirdly, here if just trying to get lower
  16 bits you should use the half registers. That's what they are for. You should take these lessons
  and apply them to all the lines.
  from SPM you 
  + fin0_load_batch should be restructured. Greedy search is expensive, and doesn't make use of the
  mvdq bandwidth. Instead, we should try like this:
  ```
  //mvdq loop. iterate over pes interior so we do mvdq to different pes at each step
  while inputs still exist:
	  1. calculate the storage needed for the next 4 diagonals
	  2. if current_pe doesn't have the storage necessary break
	  3. load 4 diagonals
	  4. begin loading the arcs for those diagonals using mvdq and peel the end (or start)
	  5. update current_pe += 1 modular
  //mv loop. flips loop nested order. iterate pes on outer loop.
  //This loop is like what you have, but not the greedy thing. Just fill pes one after the other
  for each pe:
	while pe has space:
		load next diagonal and its arcs
  ```
  The key insight here is that in the common case, we expect the inputs to fit. It is a rare case
  that the inputs do not fit in the pes. In that case we are willing to pay a penalty, but we should
  make the common case fast.

  This also makes the skiping easier. The bitmap bookeeping is no longer necessary. If we didn't fit
  everyone (which should be rare) then we know that the things we didn't fit are simply the last
  diagonals in the s1c.
### Magic 24
  + This should be modified to do mvdq. Peeling should not be necessary if we always do tilesize
  multiple of 4. Only peel for the final iterations. Should be hiting pes in round robin to avoid 
  bank conflicts. Many examples of this pattern. Take a look at magic 14 or 15. You are loading a
  constant tilesize at each step, except for the last one. Try to move the checks so most of the
  time we don't need to check. Only for the last iteration do we need to resort to loop peeling.
### magic 25
  + Same deal here, we should be using mvdq in round robin manner with loop peeling. Not scalar
  doing all hits to pe0 bank then all hits to pe1. That will be too slow and won't utilize the
  bandwidth
### magic 28
  + remove the sanity check. Was used for debugging.
  + remove the verify splits
  + instead of:
  	for each pe:
		do binary search
     we should do
     while all pes not done with search:
        for each pe:
	  do one step of binary search
     It is essential that we do it this way because between each iteration of the binary search we
     need a wait LSQ because we are doing a load from mm.
     You should add the wait LSQ in a comment within the binary search after each round of 4 pe
     lookups (basically you issue all the pe loads for that iteration. then wait lsq, then process
     the loaded values and determine the next pe to go to)
  + This loop needs to stream data in with mvdq round robin. No peeling necessary because the merge
    buffer tile size should be sized to always fit mvdq. peeling ONLY needed in edge case at the
    end. The tight loop of data transfer should not have these checks. The checks should be done
    ahead of time before the loop, then peel, then tight mvdq without checks. See previous examples.
### magic 29
  + should be mvdq round robin pe no peeling necessary except on final iteration same as magic 28
### magic 30
  + same note for scalar loops. Needs mvdq round robin... like magic 29
### magic 31
  + same note for scalar loops. Needs mvdq round robin... like magic 29
  + You should compute cursors for each pe and use mv instruction autoincrement when you writeback.
    In this way you don't need to recompute the MM destination every time.
### magic 32
  + Right now you do a seam merge for intv at the end over MM which would require a long latency
    wait. Instead, the very first tile that you get back you should write the first data element to
    s1c. After that write directly to MM. Also write the very last intv of each pe to s1c. This way,
    at the end you can compare the final intvs without doing any MM lookups.
  + all loops need to be mvdq round robin. Both diags and intvs
### magic 33
  + loop is not correct again. needs mvdq round robin
  + we have nested lookups mm[s1c[XX]]. Not feasible. You must do slc lookup as a seperate
    instruction
### magic 35
  + looping not correct. mvdq round robin needed. Always multiple of two, even across all pes until
    the boundary finish condition
### magic 36
  + remove the check that output was sorted
  + I'd like to remove the linear scan through diags here. We should make it so that you can start
    in the middle of a diagonal run. Then at the end we do a fixup, almost exactly the same as for
    intv. We store the start and end of diag tiles in s1c. Then we do a max to merge the boundary
    diags before we write them.
    tile at diags // 4 * pe
### magic 38
  + Firstly, we should do the lo and hi binary searches in parallel, so fuse the while loops and
  have two binary searches running so we do two lookups at a time
  + Second, you must add in waitLSQ comment after each binary search result.

## PE
Magic ids 8 and 13 are ideal examples. Read from them and try to replicated
## magic 19
  + There is ample opportunity to use half registers here as well as mvd. Try to use them when you
    can
## magic 20
  + modify sort bin count so we are loading two elements at a time from the tile and then we work on
    those two. We want mvd to get higher bandwidth
## magic 21
  + This should also do two element load, mvd.
## magic 22
  + You shouldn't need to check the second buffer. It will always be full. You only need to check if
    the entire stream is exausted.
  + basically, in this magic you want the inner loop to be cleaner. You should first establish how
    much left you have of A tile and B tile. Then you should iterate really fast on these tiles.
    Handle the switch of buffers as a special case. You only need to do that if you exaust current
    tile, and should try to avoid doing unecessary checks otherwise. Try to streamline the main loop
    if possible. Hoist checks
## magic 23
  + No functions unless they don't have return values and are only one call deep. Even then, it may
    make more sense
## magic 23
  + 20 words to restore/save for state seems like way too much. You should be able to keep almost
    all of these in regsiters. You have 48 registers including gr and reg. 64 if you fit some things
    in half registers. You should be able to maintain state between calls. That way you don't need 
    to do the expensive write/load at start/end.
  + In some places, like merging overlapping diagonals or intvs, you might be able to use mvds.
  + make sure you wait a cycle after spm load for data to be ready
  + generally you should always keep one intv and one diag in registers so you can do the forbidden
    checks. Keep the current one you're working on.

