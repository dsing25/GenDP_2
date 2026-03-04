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

**Key Architecture Features:**
*   **PE Array:** 4 PEs (expandable) connected in a systolic chain.
*   **Memory:** Shared Scratchpad Memory (SPM), 4 banks (one per PE), 1024 words/bank.
*   **Execution:** VLIW control trace (2 slots) + separate Compute trace.

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
# 1=bsw, 2=phmm, 3=poa, 4=chain, 5=wfa
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

### 1. VLIW Execution Order (CRITICAL)
Control instructions are written in pairs (Slot 0, Slot 1), but **Slot 1 executes BEFORE Slot 0**.
*   **Slot 1 (2nd write):** Executes FIRST.
*   **Slot 0 (1st write):** Executes SECOND.

**Incorrect:**
```python
f.write(op_using_gr1_slot0...)   # Writes 1st, executes 2nd -> sees NEW gr[1]
f.write(op_updating_gr1_slot1...) # Writes 2nd, executes 1st -> updates gr[1]
```

**Correct:**
```python
f.write(op_updating_gr1_slot0...) # Writes 1st, executes 2nd -> updates gr[1] AFTER read
f.write(op_using_gr1_slot1...)    # Writes 2nd, executes 1st -> reads OLD gr[1]
```

### 2. SPM Access Latency (CRITICAL)
The SPM has a **2-cycle latency**. You MUST insert no-ops or unrelated work between an SPM access request and using the data.

*   **Rule:** 2 cycles gap between request and use.
*   **Rule:** No simultaneous read/write (single port per PE).
*   **Rule:** No pipelining (cannot issue request while one is in flight).

**Pattern:**
```python
f.write(load_request...)
f.write(nop...) # Cycle 1
f.write(nop...) # Cycle 2
f.write(use_data...)
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
    *   **SPM Latency:** Reading data too early (garbage values).
    *   **VLIW Hazard:** Logic errors due to Slot 1 executing before Slot 0.
    *   **Synchronization:** Deadlocks if PEs don't signal completion (`gr[10]`) or Controller doesn't wait (`gr[13]`).
