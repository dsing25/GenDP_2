I will instruct you in the prompt which magic instruction we are considering. In this file I will
refer to it as magic X, or just X.

# High Level
Currently GWFA is made up of a bunch of c++ high level magic instructions which are "isaLike". They
use gotos, register mapping, and each line is generally one instruction so theoretically they should
be lowerable line for line. We want to find the places in the gwfa_gen_instruction where these
things are called, and inline them with straight, gendp ISA code.

# Your Task
Before we begin, I want you to present a high level summary of magic X in this format. 
```
Magic X
========================================================================
Summary: quick summary of what the magic instruction does and where it is called. Maybe 1-4 lines.

Pseudocode:
ignore details of address computation and such, but at a high level list some control flow and data
movement path. For loop iterations pattern should be included.
Example below is not an accurate pseudocode, it's just an example of the level of detail and format.
e.g.
load metadata from s1c which gives boundaries to queue data structure
peel loop to get equal on each pe
peel loop to get to mvdq aligned
for i < TILESIZE //TILESIZE is 32
  for each pe:
    mvdq pe.spm[i] = MM[queue+offset+queue+TILESIZE*peid]
//waitLsq()
... more stuff

Percieved lowering issues:
Invoke an isa-like-correctness-reviewer agent to analyze the magic instruction. The agent should
check to make sure the code is reasonable and lowerable. It will report any potential issues with
lowering that will make it difficult.
e.g.
1. in line 1105 you have a RAW hazard between two instructions
2. in line 1116 you read from MM and immediately use the result without a waitLsq()
```

Write this summary and pseudocode (but not the lowering issues) to GwfaMagicSummaries labeled
ctrlMagicX.md (or peMagicX if it is a pe magic instruction)
