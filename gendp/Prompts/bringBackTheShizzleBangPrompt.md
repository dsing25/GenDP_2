# High Level
GSSW hijacked the mvi2 instruction to load nonswizzled mvi2, but we need the swizzled (or really
interleaved) move as well. You can look at git history to see what we had before. I want mvi2 to be
interleaved move (swizzled), and mv2 should be what gssw uses. When this is done test correctness 1
(fast) for gwfa and wfa
