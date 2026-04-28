# High Level
I've read through some of the changes you have for ISA like magic instructions, and I have some
feedback. There are many opportunites for optimizations. I have highlighted some, but they are not
the only ones. Rather, use the examples I've shown as inspiration to optimize other parts of the
traces to remove instructions and reduce Nops. You may not sacrifice correctness. Always verify.

There are also some correctness errors particularly related to loading registers from MM and
immediately using them, which is not correct and will cause errors when you put things in ISA.
Please correct these, and write in where you would need sync lsq.

I have two other agents working on the decomposition of section 6 of magic 15 and the decomposition 
of magic 16 of the pe_array. Try to stay out of the way of these if you can to avoid merge
conflicts. Otherwise there'll be a bit more work for you when you try to merge, and you may
duplicate some work


# General
  + remember that we can now execute a branch with one instruction, so you can pair branches with
    other lines
  + remember that you can autoincrement within a move to save an instruction. e.g.:
    ```ln 882
      s1c[gr[5]] = gr[7];
      gr[5] = gr[5] + 1;
    ```
    Should just be one instruction

  + Watch out for RAW, for example these two instructions cannot be paired:
  ```
      gr[7] = gr[20] + gr[24];                   // add
      gr[7] = gr[7] + gr[24];                    // add (2*s_B_n)
  ```
  you need a nop in between, but note for this case (line 977) that you can add a register within
  the addressing. so the entire block:
  ```
    gr[7] = gr[20] + gr[24];                   // add
    gr[7] = gr[7] + gr[24];                    // add (2*s_B_n)
    //NOP
    mm[gr[7]] = gr[3];                          // mv gr→MM
    mm[gr[7] + 1] = gr[4];                     // mv gr→MM
    gr[24] = gr[24] + 1;                        // addi
  ```
  becomes
  ```
    gr[7] = gr[20] + gr[24];                   // add
    //NOP

    mm[gr[7]+gr[24]] = gr[3];  mm[gr[7] + gr[24] + 1] = gr[4];                     // mvd gr→MM
    gr[24] = gr[24] + 1;                        // addi
  ```
  2 cycles
  + remember you can reorder instructions so long as ouput is identical.
  + Pay special attention to loops (not per pe for loops, but isa loops like m9_a_outer)
  + You cannot load to a register from S2 or MM and then use the register. You've made this mistake
    in many places. You must search through the code and fix it. It is a logical error. The reason
    is that S2 and MM have very high latencies, and this is not an out of order core, so when you
    query one of those you must later to a waitLsq which costs hundreds of cycles, so we do one of
    two things. First, if you are just doing this:
    ```
    gr3 = MM[blah]
    SPM[blah] = gr3
    ```
    we replace it with:
    ```
    SPM[...] = MM[...]
    ```
    Which is fine, so long as you don't acess that SPM location until you've called a wait LSQ. 
    The other option, if you actually need to use the value of gr3 not just copy it, is to pipeline
    and load to a tile, which is what I've guided you to do in many cases:
    ```
    for each diag: //pipelines many memory accesses
      SPM[...] = MM[diag]
    waitLSQ() //pay 200 cycle overhead only once
    for each diag:
      gr3 = SPM[diag]
      do compute with gr3
    ```
    These patterns and the reasons behind them are essential to understand. Please do not forget. It
    will make future debugging nearly impossible for you.

  ## Formatting
    + Make sure to group things in pairs separated by newlines for easy reading.
# Specific Regions
  + The mvdq loop is a common pattern, and you use 8 registers for it. Frequently however, the
    access is strided, e.g. we load from MM[0], MM[0+tilesize], MM[0+tilesize*2], and
    MM[0+tilesize*3]. If this is the case, you should just use one counter and add a constant offset
    to each, thus saving 3 registers.
  + The common mvdq right now requires 2 cycles per  mvdq + one cycle at the end for the branch
    back, but ideally it should take only one cycle. In order to do this, I recommend we add a
    second peeling section which will do mvdqs with the mask until we all have the same remaining
    number of mvdq. It'll look like this for 2 pes (easier to write). For 4, basically the same:
    ```
    n_iter_pe0 = 89;
    n_iter_pe1 = 85;
    n_iter_pe2 = 72;
    //89 and 85 are not multiples of 8 so we need to first peel
    for each pe:
      do mvs until it's a multiple of 8 (mvdq able)
    //Now we have pe0=88; pe1=80; pe2=72. But these are starting at different locations so we take
    //min(pe0,pe1,pe2)=72, and we have masked_iters_pe0 = pe0 - min / 8 = 2, and same for other pes,
    //Now we do the same loop you have now with the if conditions but the end of pe0 is 2, and end
    //of pe1 is 1, and end of pe0 is 0
    for each pe:
      if has masked_iterations_left: //2 cycles per pe, one to branch, one to do work
        do mvdq; cursors += 8
    //At this point all the pes have 72/8 iterations left, so we can do them all together without
    //any masking, which allows us to do 1 cycle per mvdq
    for each pe:
      mvdq && cursors += 8
    ```
    This optimization should be applied to all mvdq loops because the overhead is basically nothing.
    A couple more registers, and a larger instruction footprint. If you choose not to apply it you
    must verify with me.
  + Line 863 magic_id 8 is just a mvdq right? So shouldn't we use the mvdq function copy?
  + m9_a_outer: this block can be rewritten to be more optimized
    ```
                    // idx = A_tail & A_MASK
                    gr[7] = gr[26] & A_MASK_VAL;           // andi
                    gr[7] = gr[7] + gr[7];                 // add: 2*idx
                    gr[7] = gr[7] + gr[21];                // add: A_base
                    //NOP
                    gr[8] = gr[11] + gr[11];               // add: 2*j
                    //NOP
                    gr[9] = spm[pe_base + A_OUT_OFF + gr[8]];     // mv
                    gr[1] = spm[pe_base + A_OUT_OFF + gr[8] + 1]; // mv
                    //NOP; //NOP
                    mm[gr[7]] = gr[9];                      // mv gr→MM
                    mm[gr[7] + 1] = gr[1];                  // mv gr→MM
                    gr[26] = gr[26] + 1;                    // addi (A_tail++)
                    gr[27] = gr[27] + 1;                    // addi (A_count++)
    ```
    becomes
    ```
                    gr[8] = gr[11] + gr[11];               // add: 2*j
                    //NOP

                    // idx = A_tail & A_MASK
                    gr[7] = gr[26] & A_MASK_VAL;           // andi
                    //TODO change register mapping so these are contiguous and we can use mvd
                    gr[9] = spm[pe_base + A_OUT_OFF + gr[8]]; gr[1] = spm[pe_base + A_OUT_OFF + gr[8] + 1]; // mvd

                    gr[7] = gr[7] + gr[7];                 // add: 2*idx
                    gr[27] = gr[27] + 1;                    // addi (A_count++)

                    mm[gr[7] + gr[26] = gr[9]; mm[gr[7] + gr[26] + 1] = gr[1]; gr[26] = gr[26] + 1; // mvd, addi (A_tail++)
                    //NOP
      ```
      Make sure you test this result after you implement
  + m14_loop has similar opportunities, the gr[7] chain can be greatly reduced. Do the first gr7 op
    speculatively with the if condition, then gr7 + gr7 and a nop, then in mm you can do
    mm[gr7+gr21] as an mvd. Also, you can't load from mm to gr and then write from gr to spm. The
    latency of mm is far to great. You would end up stalled for hundreds of cycles. You should do
    this in one command, write from SPM[blah] = MM[gr7]. Calculate blah and gr7 ahead of time, then
    issue the load request. Note that this means you won't be able to search for the ts_off and vl.
    In order to manage that, you should do all of the writes for the vd,k in one step. Then after
    those are all sent to SPM of the pe, you do a wait_lsq. Finally, you can load from S1 and use
    the data you get to find the ts_off and vl. You then load those into the pe spm. then you can
    start the pe computing. This is a more serious issue. You'll need to split magic 14 into the
    part that loads the vd,k and the part that loads the ts_off,vl. In between you wait for the lsq.
    Also, you should be doing this with mvdq, which means you need to change your layout as well.
    You'll want to do mvdq from mm to spm loading sequential (vd, k). Then you do the waitlsq. Then
    you do mvd from S2 to SPM moving the ts_off and vl. In order to use mvdq for the first part,
    you'll need to separate vd,k and ts_off,vl. They will still have the same offset but it should
    be two seperate arrays sharing an index i, each with two elements as opposed to 1 array with 4
    elements per entry. Finally, as I've said time and time again, you must interleave across pes to
    reduce bank conflicts. What you've written is wrong. You must not have the for peid in range4 on
    the outside of the loop. It's gotta be on the inside to mitigate bank conflicts just like all
    the other code. 
  + m15_s4_loop, you can't load to a register from s2 and then use it in the next cycle. The latency
    is too large. You an however load s1c[blah] = s2[blah].
