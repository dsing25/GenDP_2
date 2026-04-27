# GenDP Simulator Context

This file provides context for AI agents working on the GenDP (Genomic Data Processing) simulator.

## Project Overview

GenDP is a cycle-accurate simulator for a domain-specific accelerator designed for genomic sequence alignment algorithms. It models a hierarchical Processing Element (PE) array with scratchpad memory (SPM).

**Supported Algorithms (Kernels):**
1.  **BSW** (Band Smith-Waterman) - `kernel=1`
2.  **Phmm** (PairHMM) - `kernel=2`
3.  **POA** (Partial Order Alignment) - `kernel=3`
4.  **Chain** - `kernel=4`
5.  **WFA** (Wavefront Alignment) - `kernel=5`
6.  **bankThrasher** (SPM bank-conflict stress) - `kernel=6`
7.  **GWFA** (Graph WFA) - `kernel=7`
8.  **GSSW** (Graph Smith-Waterman) - `kernel=8`

**Key Architecture Features:**
*   **PE Array:** 4 PEs (default `PE_4_SETTING`; `PE_NUM=64` slots
    available) connected in a systolic chain.
*   **Memory:** Shared SPM, 32768 words total (4 PE bank-groups × 2
    banks each, 4096 words per bank). Plus a 1 MB controller-side S2
    buffer (4 banks) routed through an LSQ.
*   **Execution:** VLIW control trace (2 slots, concurrent semantics)
    + separate Compute trace.

## Building and Running

### Building the Main Simulator
The main executable is `sim` in the root directory.

```bash
# Build (with address sanitizer enabled by default)
make

# Build options
make ADDRESS_SANITIZER=0  # Disable sanitizer
make debug=1              # Enable debug symbols/logging
make profile=1            # Enable profiling
make clean                # Clean build
```

### Running the Simulator
Usage: `./sim -k <kernel_id> -i <input> -o <output> -n <num_cases>`

```bash
# Example: Run WFA kernel
./sim -k 5 -i input.txt -o output.txt -n 100

# Kernel IDs:
# 1=bsw, 2=phmm, 3=poa, 4=chain, 5=wfa,
# 6=bankThrasher, 7=gwfa, 8=gssw
```

### Building Kernels (Golden Outputs)
Each kernel has a standalone implementation in `kernel/<name>/` for verification.

```bash
cd kernel/bwa-mem && make -j    # BSW
cd kernel/chain && make -j      # Chain
cd kernel/PairHMM && make -j    # PairHMM
cd kernel/poaV2 && make -j      # POA
```

## Development Conventions & Constraints

### 1. VLIW Concurrent Execution (CRITICAL)
Both control slots run on the same cycle and read **pre-cycle** gr/reg
state (snapshot/restore in `pe::decode_ctrl`). Same-cycle RAW or WAW
between slots **crashes** the simulator (commit 978d23d).

```python
# CRASH — same-cycle RAW: slot 1 writes gr[1], slot 0 reads gr[1]
f.write(op_reading_gr1_slot0...)
f.write(op_writing_gr1_slot1...)
```
Move the producer one cycle earlier and consume on the next cycle.

### 2. SPM Access Latency (CRITICAL)
The SPM has a **2-cycle per-load latency** but is **pipelined**: each
bank can hold up to 2 in-flight requests. Per-load latency is still
preserved — the consumer must wait 2 cycles after that specific load.

*   **Rule:** Consumer cycle ≥ load cycle + 2.
*   **Rule:** No simultaneous read/write on a PE (single port per PE) —
    issuing two SPM ops in one VLIW cycle crashes.
*   **Rule:** Back-to-back SPM issues are fine; same-bank same-cycle
    collisions across PEs/LSQ stall.

**Pattern (pipelined loads):**
```python
f.write(load_A...)  # cycle 0
f.write(load_B...)  # cycle 1 (legal — pipelined)
f.write(use_A...)   # cycle 2 (A ready)
f.write(use_B...)   # cycle 3 (B ready)
```

### 3. Development Workflow
1.  **Modify Instruction Generator:** Edit `scripts/<kernel>_instruction_generator.py` to change logic.
2.  **Generate Instructions:** Run the python script to update `instructions/`.
3.  **Rebuild Simulator:** `make` (if C++ changes were made).
4.  **Run Simulation:** `./sim ...`
5.  **Verify:** Compare output with golden trace (e.g., using `scripts/wfa_check_correctness.py`).

## Key Files

*   **Simulator Core:**
    *   `main.cpp`: Entry point.
    *   `simulator.cpp/h`: Main loop.
    *   `pe_array.cpp/h`: Array controller (complex synchronization logic).
    *   `pe.cpp/h`: Processing Element logic (decode, execution).
    *   `data_buffer.cpp/h`: SPM implementation (latency modeling).
    *   `sys_def.h`: System constants (SPM size, latencies).

*   **Kernels (Simulation Wrappers):**
    *   `wfa.cpp`, `bsw.cpp`, `chain.cpp`, `phmm.cpp`, `poa.cpp`

*   **Scripts:**
    *   `scripts/*_instruction_generator.py`: **Primary Logic Source.** Defines the assembly instructions run by PEs.
    *   `scripts/opcodes.py`: Opcode definitions.

## Debugging
*   **Debug Mode:** Compile with `make debug=1` to see verbose logs.
*   **Trace Files:**
    *   `magic_wfs_out.txt`: Simulator's internal state trace (WFA).
    *   `wfaTrace.txt`: Reference trace for validation.
*   **Common Errors:**
    *   **SPM Latency:** Consumer reads load < 2 cycles after issue.
    *   **VLIW Hazard:** Same-cycle RAW or WAW between slots — the
        simulator crashes; rearrange the producer to a prior cycle.
    *   **Two SPM ops in one cycle:** crashes (one port per PE).
    *   **Synchronization:** Deadlocks if PEs don't signal completion
        (`gr[10]`) or controller doesn't wait (`gr[13]`).
