# High Level
There are some "soft" rules in the simulator about how one should write code which are not actually
enforced. The burden is on the programmer to write code which is true to the spirit of the
simulator, but a programmer can easilly make a mistake and do something illegal in hardware but
allowed by a quirk of the simulator. I want you to help make these illegal actions illegal in the
simulator as well as the hardware.

# Rules:
+ You cannot have a RAW dependency between two instructions executing in the same a VLIW cycle. e.g.
  `gr3 = 4; gr3++;` Because the simulator executes sequentially, it will allow this and the final
  value of gr3 will be 5, but it should not be allowed at all. The simulator should crash if this is
  attempted. I want you to enforce that we never write the same register twice in the same cycle.
  Another example is `gr3 = 4; gr2 = 3;` and in the next cycle `gr3++; gr2 = gr3+1`. This sequence
  is legal, but currently I believe the simulator will return 6 for gr2 because it executes the
  instructions sequentially. In hardware they should happen simultaneously, so gr2 will be 5. You
  should enforce that it looks as if things ran simultaneous. We won't get intermediate values.
+ similarly, since we are now executing compute instructions and data movement instructions on the
  gr/reg files shared, we must be sure that they do not write at the same time or use new instead of
  old values for reading.
+ SPM loads/writes can only be to/from gr and or reg on the pe. On the pe_array they can be to/from
  gr, reg, s1c, s2, MM.
+ A PE can never issue two SPM loads/stores in a single cycle (it has only one memory port). The
  easiest way to enforce this is to only allow SPM accesses on the first lane of the VLIW, and maybe
  allow branches only on the other lane so we can do both at the same time. Some legacy kernels use
  double branches, but you can remove the second branch and replace with a NOP if you want.
  (equivalent behaviour. Make sure to verify)
