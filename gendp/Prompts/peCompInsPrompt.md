# High level
I want to modify pe.cpp magic instructions so that we make effective use of the compute instruction
trace.

# Formatting
Right now we format ISA as

```
//coments
ins1 //comments
ins2 //comments

//another instruction block. Sometimes we write nop as a comment if there will be a noop
ins1
//NOP 
```

We will express comp instructions like this

```
ins0
//comp setPC

ins1
ins2
//COMP
{
  comp_ins1
  comp_ins2
}

ins3
ins4
//COMP
{
  NOP
  NOP
}

ins5
ins6
//COMP halt

ins6
ins7
```

If there are no comp instructions then it is implied that comp was halted before. The brackets are
really just asthetic, not so much about scope. The //comp setPC does not specify what to set the
comp pc to. This will be evaluated when you write the instruction files.
Note also that comp_instructions can often do many operations, e.g. max(x,y) + max(a,b,c,d). We will
keep these to one line in the c++ code for clarity.

# Preliminary simulator changes
We will make two simulator changes to help support this
## compute instructions can use gr
The PE has 16 gr registers which can also be addressed as lo/hi, and the reg file has 32 registers.
Currently a compute instruciton has one 5 bit field to address the 32 registers. I want to add 2
bits which allow it to address the other 48 gr locations as well. The mapping will be like this:
```
addr    mappedReg
[0:31]  reg[0:31]
[32:47] gr[0:15]
[48:63] gr_lo[0:15]
[64:79] gr_hi[0:15]
```
This should be compatible with previous kernels, but make sure you check with run throughput and run
`wfa_check_correctness.py`

## branch as a group
Currently, it is not enforced that the two instructions executed in the data movement trace execute
in lockstep. e.g. you could have an instruction:
```
br 17
br 10
```
Instead, I want to enforce that whenever there is a branch in data movement instructions (for
controller and for pe) that branch should always go to the same place. Once we have this invariant,
we don't really need to do
```
br 10
br 10
```
because the two br 10s are redundant. We can instead do:
```
br 10
//other useful instruction
```
You should modify the simulator to make this possible. You shouldn't crash on
```
br 10
br 10
```
but you should crash on 
```
br 10
br 17
```
I believe all prior instruction generators are compatible, but please check carefully before you
plan. If there are places with diverging control flow within a data trace, let me know where and how
often.
Once you finish the implementation you must test with run backtest or run throughput.

Similarly, I want the call instruction to be this way. I should be able to call/ret and execute 
another instruction at the same time

# A Primer on Compute Instructions
Read docs.md for more details.
Compute instructions run in parallel with data movement instructions and are VLIW running two
instructions at a time with each instruction doing up to 3 computations in a tree ALU. They have no
branching capability and must be kept in sync with the data trace. Traditionally this is done by 
padding the data trace with nops so the path length is the same for if and else branches and/or by
padding the compute instructions with nops. When we have finished a block of compute instructions
and are waiting for the next, we use a halt instruction in the compute trace to pause the compute
instructions from executing. These options are still available to us, but because of the new branch
capability, I anticipate we will use the last option more frequently. I anticipate that when a data
trace branches, we will use one VLIW slot for the branch instruction, and another vliw slot to set
the pc of the compute instruction trace.
Before you make your plan, please read the docs and prior instruction generators to get a sense for
how compute traces are used. Then update you memories and the docs.md with details of how to use the
compute instructions.

# Your task
I have begun working on compute traces for the pe.cpp magic instructions. I have been modifying them
according to the format above. I want you to read carefully so you get a sense of what I'm doing,
why I'm doing it, how it improves runtime, what is possible, what is not. And when you feel you
understand (ask me as many questions as you need), then I would like you to take a stab at
refactoring all the pe magic instructions to include compute traces according to the format
described above. You'll also find some places where I can rearrange to move data movement
instructions to pair them with branches, which wasn't possible before. Use git diff to see the
specific changes that I've made.

# Misc
+ add an opcode for retne. Return if not equal. Basically if you ever need a conditional return,
  feel free to add. e.g. retge, but don't add unless you need

# Verification
+ Note there is a bug for gwfa_check_correctness.py 295, if you find the bug please let me know what
  it is, but for now try to avoid messing with it
+ All of your changes should not change correctness at all. You're just trying to optimize and
  reduce the number of cycles by offloading compute to compute trace where possible. You can test
  with just the fast gwfa_check_correctness.py 1
+ When you are making the preliminary simulator changes, you'll need to backtest for other kernels
  than gwfa.
