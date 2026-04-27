Previously, POA required that each SPM access be spaced 2 cycles apart so that we would never have
two SPM requests in the pipeline at the same time. This is no longer true. We can pipeline SpM
accesses, although they still have a 2 cycle latency. I want to update the POA trace so it doesn't
stall for a nonexistent structural hazard. We should optimize to pack out noops where we can. Make
sure you verify with the poa_check_correctness.py and use small datasets so we can test quickly
