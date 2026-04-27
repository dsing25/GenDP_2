# High Level
We need a multiply operator in the gr/data movement trace in order to do address calculations.

# Details
The multiply unit should only be on one VLIW lane, not both. You can pick which. It should work on
PEs as well as on the controller. The multiply must have gr/reg operands. You should allow
immediates using the set immediate bar bit to determine whether the imm_1 field should be used as a
register address or an immediate.

After you've implemented this change, you should look through the completed ISA kernels we have like
GSSW and WFA for places where you can save instructions using this multiply instruction.
Particularly I know in WFA there are some places where we do the equivalent of 3*reg[XX] by doing:
reg[XX] += reg[XX]; reg[XX] += reg[XX]; Obviously, if we are multiplying by a power of 2, shift is
still preffered.

To verify the optimizations (both their reduction in cycle count, and their correctness), you can
use the check_correctness scripts
