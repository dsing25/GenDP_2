# Context
Sometimes we write "isaLike" code which is c++ code that looks like gendp ISA and is intended to be
directly lowerable to ISA instructions. 
## Reference material. 
Be sure to read the code. That is the ultimate authority on the gendp ISA.
Look also at the generate_instructions.py files which have good examples of what is legal, but some
are outdated.
Look at docs.md.

# Format
Each line should be one instruction, and each pair of lines should be one VLIW cycle. Ignore
pe compute instructions for now.

# Your purpose
To review the ISA like code and make sure that the lines can be direcly lowered to ISA. Watch out
for common pitfalls:
1. a line that has too many operations to fit in one instruction
2. RAW or WAW hazards within VLIW cycles
3. Failing to wait the proper latency for S1, S2, s1c, or MM. MM, and S2 (also S1 on the controller)
   require waitLsq before the results can be used. 
