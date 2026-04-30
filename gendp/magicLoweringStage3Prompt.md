We just lowered magic instruction X. I now want you to try to optimize performance. These are the
optimizations you are allowed to use. Don't use any others for this pass

# Available Optimizations:
1. You may remove Noops (this is the most important one. Whever possible in the code you've lowered
   remove noops)
2. You may reorder instructions (fine grained reordering when there are no dependencies between them
   (note that two instructions operating in the same VLIW slot cannot have RAW)
3. You may combine instructions sometimes (e.g. mv reg[4] = spm[reg2]; reg2++; can be one mv
   instruction with an autoincrement. Alternatively, you may be able to switch an mv for an mvd or
   mvdq.
4. You may change the register mapping to avoid moves.

# Verification
At intermediate steps, you can verify yourself with gwfa_check_correctness -t 56 1. Do that
frequently.
Hard gate: before finishing, gwfa_check_correctness -t 56 2 must pass all inputs, and the call to
the magic instruciton should be removed.

# Termination
When you have finished, give a summary of what you have done.
