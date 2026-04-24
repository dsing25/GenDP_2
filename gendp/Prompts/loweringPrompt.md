# High Level
Right now we have magic 101 which is written in isaLike c++. I would like you to convert this
isaLike c++ to gendp ISA, written directly in the instructiong_generator.py file.


# References
look in ../../gdp/gendp/Prompts for prompts where I have done similar things. Some of these may be
outdated. The simulator has changed a bit since, but they will be a good starting point. 
In Particular, isaCodingPrompt.txt has useful information for writing in gendp ISA.

Noteably:
+ We have added new opcodes, see the work done in the last commit and simulatorTweakPrompt.md.
+ spm accesses can be pipelined, this means that you can issue two back to back spm requests,
  although the result still arrives at the end of cycle n+1, ready for use in n+2.
+ gr registers can be used in compute alus
+ gr registers have subregisters
+ when running compute in simd mode, if a gr is an operand, we execute scalar

Also be sure to read docs.md and the CLAUDE.md file. If you look in the git history you will find
further examples of how we did this with WFA.

# Details
The isaLike format looks like this example.
The code is not guarenteed to follow this format, but it usually will.
```
ins0
//setPC

ins1
ins2
{
  cins1
  cins2
}

{
  cins3
  cins4
}
ins3
ins4
```
In this example ins1,ins2, cins1, and cins2 execute in one cycle. the two ins are data instructions
packed in one VLIW cycle. the two cins are compute instructions executing on the compute ALU.
Newlines seperate cycles from one another. brackets enclose compute instructions. the compute
instructions may come before or after the data instructions. In theory it doesn't matter because all
instructions happen simultaneously in the hardware. In reality, the simulator executes them
sequentially, and so there may be WAR dependencies which don't exist in the real hardware. I
sometimes avoid the WAR by changing the order of comp instruction vs data instruction. No RAW within
a cycle is permitted (i.e. no data forwarding), but you can write to a register which is also being
read. In this case the read value is the old value.

an ins is a data movement instruction. It can be //NOP, //set PC (meaning set the compute pc to the
necessary trace) or a legit data instruction (like add, si, spm load, etc). Sometimes multiple c++
instrucitons are grouped to represent one isa ins, e.g.
`reg[1] = spm[reg[3]]; reg[2] = spm[reg[3]+1]; reg[3] += 2; //in isa, one mvd with an autoincrement`
This will show one one line generally so you know it should only be one ISA instruction.

compute instructions may be similarly grouped because they have the three ALU tree, and may do a
bunch of operations in one instruction.

It is difficult to represent the compute instruction trace within the isaLike format. You will need
to construct it on the fly. In the example above ins0 and set pc is a VLIW cycle with comp
instruction halted. In this case it's clear that the data trace is:
```
ins0
set pc //which is an instruction

ins1
ins2

ins3
ins4
```
and the compute trace is
```
cins1
cins2

cins3
cins4
...
```

In this case the set pc would set to addr 0, the cins1. If the next line of the full trace was:
```
ins5
ins6
{
  //halt
}
```
then the compute trace would end with 
```
halt
halt
```
If instead the compute trace kept going we would have more instrucitons, until there is no more
compute trace and then we have halt, halt.

The trick is what to do at branches. If a data instruction branches, the compute instruction will
not branch unless explicitly told to do so in a comment. Often times in the common case, we will not
branch the compute instructions, but for an exceptional case we will need to begin the conditional
block of code with a set pc to get the compute pc to a new region. Sometimes we end up doing a round
of extra compute, but it ends up being fine because those results were speculative. Oftentimes in
for loops we will have need to set the pc on the goto when we branch back to start of the loop.

It should generally be able to infer how the compute trace should be written, but it does require
some care, and it is not as explicit as  the other isaLike features. Be careful of this, and if you
are unsure of pieces ask in the planning phase.

# End condition
The magic payloads specified should be completely removed. Everything should be done within the
instruction generator with valid instructions. The code should still be correct, and effecient. If
there are any significant deviations from what we have in the c++ isaLike code, those should be
cleared with me ahead of time.
