We just lowered magic instruction X. I now want you to try to optimize performance. 

The previous pass on magic X likely padded with excessive nops. You should avoid this because its
too slow. Use nops only when necessary. You should be able to get huge savings in cycle count just
by this one optimization. You will invoke the isa-optimizer agent and will not make other
optimizations. Only the optimizations that the Isa-optimizer agent can make are you allowed to do.
Especially, do not modify the simulator. The only file you may change is the instruction_generator

# Verification
At intermediate steps, you can verify yourself with gwfa_check_correctness -t 56 1. Do that
frequently.
Hard gate: before finishing, gwfa_check_correctness -t 56 2 must pass all inputs, and the call to
the magic instruciton should be removed.

# Termination
When you have finished, give a summary of what you have done.
