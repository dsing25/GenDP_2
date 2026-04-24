# High Level
Before we can support Gssw, we need to implement some new opcodes and other features.
I would like you work on this.

# Other features
+ Currently, if we're in simd mode, we can only do simd operations on the compute alu . I want to 
  change that so that if in simd mode and one of the registers is from gr, then all the operations
  will be in scalar mode. i.e. we will use the scalar alu. (the exception is the gt simd to scalar
  reduction which we describe which may use gr to collect the scalar result)
# Opcodes
+ We need an slli opcode which does a shift on a 64 bit unsigned register. slli(srcRegister,
  shiftImmediate); reg[srcRegister:srcRegister+1] << shiftImmediate. Should allow gr or reg sources.
  We will make it a compute instruction and it should always be executed as a pair on two comp alus
  because we need two write ports
+ We need a maxReduce opcode which can only be used in simd mode. in simd mode, it will take an
  element wise maximum between all the 8 bit inputs
+ We need gt as a compute opcode which will compute greater than between two values and output a
  boolean. If the values are simd, it will output a boolean if any is greater than.

Double check this branch has gr for the alu, and the branch+instruction tweaks
