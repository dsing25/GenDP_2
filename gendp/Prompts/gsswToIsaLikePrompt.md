# High Level
We want to lower the current gssw code to an ISA like instructions. It will all stay in the magic
instruction for now, but you should make it so each line is one VLIW instruction block, and each
block seperated by blank newlines is executed in a single cycle. Identify data and compute 
instructions. Every line should be translatable into a line of gendp ISA.

# References
We have done this many times before for other kernels. Read through all the prompts in
`/data4/kaplannp/GenDP2/gdp/gendp/Prompts`. There are many great examples of things to do and not to
do there.
Also read the  magic instructions in pe.cpp and pe_array which show how we have done this for gwfa.
We want to do the same for gssw now.

The primary difference between these prior works is that for GSSW there is no communication with
controller. Everything happens on the PE, which is quite convenient, and pes don't communicate.

# Procedure
The correctness will not be changed at all. You should be able to run for 1000 with 56 threads and
always pass. Don't bother with the full run. It's too slow.

Pay attention to optimization. Note every time you are inserting a nop and try to avoid nops where
possible. Utilize the compute as well as possible. Try to reduce the number of cycles where you can,
especially in loops.

For parts of the code I have begun to isolate the instructions that run together, but you must make
it register mapped instead of using variables.
