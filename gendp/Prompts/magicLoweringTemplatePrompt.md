# High Level
Currently GWFA is made up of a bunch of c++ high level magic instructions which are "isaLike". They
use gotos, register mapping, and each line is generally one instruction so theoretically they should
be lowerable line for line. We want to find the places in the gwfa_gen_instruction where these
things are called, and inline them with straight, gendp ISA code.

# Procedure:
Before making a plan
1. scan through the magic instruction and get a thorough instruction of what it is, what it does,
   how you might lower it, and what obstacles there might be to lowering.
2. add the summary to gwfaMagicSumaries.txt.
3. present the user with the summary and a list of any obstacles that you've found that prevent
   lowering the code. e.g. If there are back to back mm2 reads and uses without a waitLSQ in
   between, or if we are using opcodes which don't exist. The user will help you resolve any
   obstacles to lowering.
4. Draft a detailed plan for lowering the code to ISA
5. Implement the plan and verify correctness
6. Do a final pass of optimization from the available optimizations.

# Available Optimizations
1. You may remove Noops (this is the most important one. Whever possible in the code you've lowered
   remove noops)
2. You may reorder instructions (fine grained reordering when there are no dependencies between them
   (note that two instructions operating in the same VLIW slot cannot have RAW)
3. You may combine instructions sometimes (e.g. mv reg[4] = spm[reg2]; reg2++; can be one mv
   instruction with an autoincrement. Alternatively, you may be able to switch an mv for an mvd or
   mvdq.
4. You may change the register mapping to avoid moves.

# Gendp ISA
The code is constantly being updated, so you should not trust documentation. Instead verify with the
simulator. All the same, documentation and previous traces will give you and idea of what is legal
and what is not. They are the place to start, but must be validated.
Take a look in Prompts, docs.md, claude.md, the instruction generators (GSSW, and WFA are newer and
more up to date), and of course the simulator code itself.

# Verification


TODO
I think we should make a new agent for isa optimization, and another for c++ lowerability.

We should break this plan into three plan files.
1. prompt for feasibility and summary
2. prompt for implementation correctness
3. prompt for implementation optimization


isa-like-correctness-reviewer 
