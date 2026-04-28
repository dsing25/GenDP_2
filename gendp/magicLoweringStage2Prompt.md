I will instruct you in the prompt which magic instruction we are considering. In this file I will
refer to it as magic X, or just X.
# High Level
Currently GWFA is made up of a bunch of c++ high level magic instructions which are "isaLike". They
use gotos, register mapping, and each line is generally one instruction so theoretically they should
be lowerable line for line. We want to find the places in the gwfa_gen_instruction where these
things are called, and inline them with straight, gendp ISA code. Your task is to use the
isa-like-lowerer agent to convert from c++ isaLike code to the ISA code and inline it into the
instruciton generator. You should then remove all calls to the magic instruciton and then delete the
magic instruction itself. Please document in the instruction generator the previous name of the
magic instruction. and a brief summary of what it does.
You should create a very detailed plan for this prompt.
Break it into pieces where possible. For example, do the prologue, then do a loop, then the epilouge,
keeping the original magic instruciton to do the parts you have not finished yet. Doing it in small
chunks like this will make it easier to verify.
Changes to the simulator are not allowed. Only changes to magic, and the instruction generator.

# Verification
At intermediate steps, you can verify yourself with gwfa_check_correctness -t 56 1.
Hard gate: before finishing, gwfa_check_correctness -t 56 2 must pass all inputs, and the call to
the magic instruciton should be removed.

# Termination
When you have finished, give a summary of what you have done.
Then list any deviations from the plan, and problems you encountered, how you solved them.
Then give a brief summary of what the magic instruciton does.
