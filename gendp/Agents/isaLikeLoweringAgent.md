# Context
Sometimes we write "isaLike" code which is c++ code that looks like gendp ISA and is intended to be
directly lowerable to ISA instructions. 
## Reference material. 
Be sure to read the code. That is the ultimate authority on the gendp ISA.
Look also at the generate_instructions.py files which have good examples of what is legal, but some
are outdated.
Look at docs.md.
Look at past prompts in Prompts/ though many of these are outdated.

# Format
Each line should be one instruction, and each pair of lines should be one VLIW cycle. Ignore
pe compute instructions for now.

# Your purpose
To replace a magic instruciton which uses the c++ isa like with ISA instructions which closely match
the original c++ isalike code. Correctness must be maintained. It is often preferable to break the
magic instruction into steps. For example, do the prologue, then do a loop, then the epilouge,
keeping the original magic instruciton to do the parts you have not finished yet. Doing it in small
chunks like this will make it easier to verify. The orchistrating agent may have already done this
for you.
