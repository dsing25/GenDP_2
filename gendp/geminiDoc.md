!PRODUCED BY GEN AI. NOTHING IS GUARENTEED TRUTH!:wq
# GenDP Accelerator ISA and Programming Manual

This document provides the necessary information to program the GenDP accelerator. It covers the high-level architecture, the instruction set architecture (ISA) for both the Processing Elements (PEs) and the Array Controller, and a programming guide with examples.

## 1. Architecture Overview

The GenDP accelerator features a coarse-grained programmable architecture designed for bioinformatics workloads.

- **PE Array:** The fundamental unit is a group of 4 Processing Elements (PEs).
- **Array Controller:** A single, simpler processor, referred to as the PE Array or Array Controller, manages the 4 PEs in its group.
- **Dual-Trace PEs:** Each PE executes two programs (traces) concurrently:
    - **Compute Trace:** Performs the core data-parallel computations. (This is outside the scope of this document).
    - **Control Trace:** Handles data movement, synchronization, and control flow.
- **VLIW Control Trace:** The PE's control trace is effectively a Very Long Instruction Word (VLIW) architecture. Two control instructions are issued and executed simultaneously per cycle. **Important:** In the current simulator implementation, the second instruction in a pair is executed *before* the first. Programmers must account for this to avoid data hazards.
- **Single-Threaded Controller:** The Array Controller executes a single control trace.
- **Shared Scratchpad Memory (SPM):** A fast on-chip memory shared between the 4 PEs and the Controller.
- **Systolic Data Flow:** PEs are connected in a chain (`PE0 -> PE1 -> PE2 -> PE3`). Data can be passed from one PE to the next via `in_port` and `out_port`, enabling systolic array computations. The Controller feeds data to PE0.

## 2. Instruction Format

All control instructions are 64 bits wide. The format is consistent for both PEs and the Controller, although the semantics of some opcodes and memory locations differ.

A special "magic" instruction, denoted by the most significant bit being `1`, is used for non-standard, simulator-specific operations. These are not part of the general ISA and should not be used for general programming.

### Standard Instruction Fields

| Bits      | Field Name                  | Description                                                                                                   |
|-----------|-----------------------------|---------------------------------------------------------------------------------------------------------------|
| `63`      | `is_magic`                  | `0` for standard instruction, `1` for magic instruction.                                                      |
| `53:50`   | `dest`                      | The destination for the operation (a memory component).                                                       |
| `49:46`   | `src`                       | The source for the operation (a memory component).                                                            |
| `45`      | `reg_immBar_0` (Op A)       | Selects addressing mode for Operand A. `0` for `(imm + GPR)`, `1` for `(GPR + GPR)`.                           |
| `44`      | `reg_auto_increase_0` (Op A)| If `1`, enables post-increment on the second GPR used in Operand A's address calculation.                     |
| `43:30`   | `imm_0` (Op A)              | 14-bit signed immediate or GPR index for Operand A.                                                           |
| `29:26`   | `reg_0` (Op A)              | GPR index for Operand A.                                                                                      |
| `25`      | `reg_immBar_1` (Op B)       | Selects addressing mode for Operand B. `0` for `(imm + GPR)`, `1` for `(GPR + GPR)`.                           |
| `24`      | `reg_auto_increase_1` (Op B)| If `1`, enables post-increment on the second GPR used in Operand B's address calculation.                     |
| `23:10`   | `imm_1` (Op B)              | 14-bit signed immediate or GPR index for Operand B.                                                           |
| `9:6`     | `reg_1` (Op B)              | GPR index for Operand B.                                                                                      |
| `5:0`     | `opcode`                    | The operation to be performed.                                                                                |

### Addressing Mode

The accelerator uses a powerful indexed addressing mode for data movement instructions (`mv`, `si`, `mvd`, `mvi`). The address for an operand is calculated as:

`address = (reg_immBar_flag ? GPR[imm_field] : sext(imm_field)) + GPR[reg_field]`

- `reg_immBar_flag`: Determines if the `imm_field` is used as a register index or a sign-extended immediate value.
- `imm_field`: `imm_0` or `imm_1`.
- `reg_field`: `reg_0` or `reg_1`.

## 3. Memory and Registers

### 3.1. PE Memory Map

| ID | Name        | Description                                       |
|----|-------------|---------------------------------------------------|
| 0  | `reg`       | PE's private Compute Register File.               |
| 1  | `gr`        | PE's private General-purpose Register File (16 x 32-bit). |
| 2  | `SPM`       | Shared Scratchpad Memory.                         |
| 3  | `comp_ib`   | PE's private Compute Instruction Buffer.          |
| 5  | `in_buf`    | *Not used by PE.*                                 |
| 6  | `out_buf`   | *Not used by PE.*                                 |
| 7  | `in_port`   | Input port for receiving data from previous PE/Controller. |
| 9  | `out_port`  | Output port for sending data to next PE.          |
| 10 | `out_instr` | Output port for sending instruction to next PE.   |
| 11 | `fifo`      | *Not used by PE.*                                 |

### 3.2. Array Controller Memory Map

| ID | Name        | Description                                       |
|----|-------------|---------------------------------------------------|
| 1  | `gr`        | Controller's private General-purpose Register File (16 x 32-bit). |
| 3  | `comp_ib`   | Controller's copy of the compute instructions to be loaded to PEs. |
| 5  | `in_buf`    | Global input buffer for the accelerator.          |
| 6  | `out_buf`   | Global output buffer for the accelerator.         |
| 7  | `in_port`   | Input port for receiving data from the last PE in the chain. |
| 9  | `out_port`  | Output port for sending data to the first PE (PE0). |
| 11 | `fifo[0-3]` | Four FIFO queues for communication.             |


## 4. Detailed Instruction Set

This section details the opcodes for both the PE and the Array Controller. The behavior is identical unless specified otherwise.

### 4.1. Arithmetic Instructions

These instructions operate on the General-Purpose Registers (`gr`). The result is written to the GPR file or an output port, as specified by the `dest` field.

| Opcode | Mnemonic | Operation | `rd` (Destination) | `rs1` / `imm` (Operand 1) | `rs2` (Operand 2) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | `add` | `GPR[rd] = GPR[rs1] + GPR[rs2]` | `imm_0` | `imm_1` | `reg_1` |
| 1 | `sub` | `GPR[rd] = GPR[rs1] - GPR[rs2]` | `imm_0` | `imm_1` | `reg_1` |
| 2 | `addi` | `GPR[rd] = GPR[rs2] + imm` | `imm_0` | `imm_1` (sign-extended) | `reg_1` |
| 16 | `shifti_r` | `GPR[rd] = GPR[rs2] >> imm` (arithmetic) | `imm_0` | `imm_1` (unsigned) | `reg_1` |
| 17 | `shifti_l` | `GPR[rd] = GPR[rs2] << imm` | `imm_0` | `imm_1` (unsigned) | `reg_1` |
| 18 | `ANDI` | `GPR[rd] = GPR[rs2] & imm` | `imm_0` | `imm_1` (unsigned) | `reg_1` |
| 20 | `subi` | `GPR[rd] = GPR[rs2] - imm` | `imm_0` | `imm_1` (sign-extended) | `reg_1` |
| 3 | `set_8` | Byte-wise copy within a GPR. | `imm_0` | `reg_1` | - |
| | | **Controller Only.** | | | |

<br>

### 4.2. Data Movement Instructions

These instructions move data between the memory components listed in Section 3. They use the full addressing mode `(GPR[imm] or imm) + GPR[reg]`.

| Opcode | Mnemonic | Operation | Destination Address | Source Address / Immediate |
| :--- | :--- | :--- | :--- | :--- |
| 4 | `si` | Store immediate value to a destination. | Calculated using **Operand A** (`imm_0`, `reg_0`, `reg_immBar_0`). | Immediate is from `imm_1` (sign-extended). |
| 5 | `mv` | Move data from a source location to a destination location. | Calculated using **Operand A** (`imm_0`, `reg_0`, `reg_immBar_0`). | Calculated using **Operand B** (`imm_1`, `reg_1`, `reg_immBar_1`). |
| 19 | `mvd` | Move a double word (64 bits). **PE Only.** | Calculated using **Operand A**. | Calculated using **Operand B**. |
| 21 | `mvi` | Move with index swizzling for interleaved SPM access. **PE Only.** | Calculated using **Operand A**. | Calculated using **Operand B**. |

- The `dest` and `src` instruction fields specify the *memory components* involved (e.g., `gr`, `SPM`).
- `reg_auto_increase_0` and `reg_auto_increase_1` can be used for post-increment addressing on the `reg_0` and `reg_1` registers, respectively.

<br>

### 4.3. Control Flow Instructions

| Opcode | Mnemonic | Operation | Operand 1 (`comp_0`) | Operand 2 (`comp_1`) | Branch Offset |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 8 | `bne` | Branch if `comp_0 != comp_1`. | From `imm_1`¹. | `GPR[reg_1]` | `imm_0` (sign-extended) |
| 9 | `beq` | Branch if `comp_0 == comp_1`. | From `imm_1`¹. | `GPR[reg_1]` | `imm_0` (sign-extended) |
| 10 | `bge` | Branch if `comp_0 >= comp_1`. | From `imm_1`¹. | `GPR[reg_1]` | `imm_0` (sign-extended) |
| 11 | `blt` | Branch if `comp_0 < comp_1`. | From `imm_1`¹. | `GPR[reg_1]` | `imm_0` (sign-extended) |
| 12 | `jump` | Unconditional branch. | - | - | `imm_0` (sign-extended) |

¹Operand 1 is derived from the `imm_1` field. If `reg_immBar_1` is `0`, it's a sign-extended immediate. If `reg_immBar_1` is `1`, `imm_1` is used as an index into the GPR file (`GPR[imm_1]`).

<br>

### 4.4. System and Synchronization Instructions

| Opcode | Mnemonic | Operation | Target | Immediate | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 13 | `set_PC` | Set Program Counter. | PE Compute Trace PC | `imm_0` (sign-extended) | **PEs:** Sets the PE's own `comp_PC`. |
| | | | All PE Control Trace PCs | `imm_0` (sign-extended) | **Controller:** Broadcasts value to `PC[0]` and `PC[1]` of all PEs. |
| 14 | `none` | No operation. | - | - | - |
| 15 | `halt` | Stop execution. | - | - | **PEs:** Halts the PE until a `set_PC` from the Controller. |
| | | | - | - | **Controller:** Halts the entire simulation. |

## 6. Programming Guide

### 6.1. Assembly Workflow

Assembly programs are not written by hand. Instead, they are generated by Python scripts located in the `scripts/` directory.

- **Instruction Definition:** `scripts/opcodes.py` and `scripts/utils.py` define the opcodes and the `data_movement_instruction()` function used to create instructions.
- **Program Generation:** An application-specific script, like `scripts/bsw_instruction_generator.py`, contains the logic for the application. It has separate functions to generate the instruction stream for the Controller (`bsw_main_instruction`) and for each PE (`pe_0_instruction`, etc.).
- **Output:** Running the Python script generates `.txt` files in the `instructions/` directory, which are then loaded by the simulator.

A typical program is structured into phases, with the Controller loading data and instructions, starting the PEs, waiting for them to finish, and then repeating the process.

### 6.2. Synchronization

The Controller and PEs synchronize using a combination of `halt` and a dedicated register flag.

1.  **PEs Halt:** A PE can execute the `halt` instruction. This pauses its control trace execution indefinitely. PEs typically halt at the beginning of a program, waiting for the Controller to provide initial data and a start address.
2.  **Controller Starts PEs:** The Controller uses the `set_PC` instruction to broadcast a new Program Counter value to all PEs simultaneously. This action "wakes up" any halted PEs and directs them to a new code location.
3.  **PEs Signal Completion:** When a PE completes a task, it signals the Controller by setting its `gr[10]` register to `1`.
    ```python
    # PE instruction to signal completion
    data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si) # gr[10] = 1
    ```
4.  **Controller Waits:** The Controller's `gr[13]` register is a special hardware register that contains the logical `AND` of `gr[10]` from all four of its PEs. The Controller can wait in a tight loop until this flag becomes `1`, indicating all PEs have finished.
    ```python
    # Controller waits for gr[13] to become 1 before proceeding.
    # This creates a loop that branches to itself as long as gr[13] is 0.
    data_movement_instruction(0, 0, 0, 0, -1, 0, 1, 0, 0, 13, bne) # if (gr[13] != 0) PC += -1;
    ```

### 6.3. Scratchpad Memory (SPM) Usage

The SPM is a powerful resource, but it has strict access rules that the programmer must manage manually.

- **Latency:** SPM access has a **2-cycle latency**. This means when a PE issues a load from the SPM, the data will not be available in the destination register until two full cycles have passed.
- **Pipelining:** SPM accesses **cannot be pipelined**. A new SPM request (read or write) cannot be issued while another is in flight.
- **Access Rules:**
    - Because of the 2-cycle latency and no-pipelining rule, a programmer must insert **at least 3 `nop` instructions** (or other work that does not access the SPM) between two consecutive SPM accesses.
    - Each PE has only **one port** to the SPM, which is shared for reads and writes. Therefore, a PE cannot read from and write to the SPM in the same cycle.

**Example of Legal SPM Access:**
```python
# Legal: Load, wait 3 cycles, then load again.
ld_spm(dest_reg=0, addr=10)
nop()
nop()
nop()
ld_spm(dest_reg=1, addr=20)
```

**Example of Illegal SPM Access:**
```python
# ILLEGAL: Second load is issued before the first has completed.
ld_spm(dest_reg=0, addr=10)
nop()
ld_spm(dest_reg=1, addr=20)
```

### 6.4. SPM Addressing Modes

The SPM supports two main addressing modes for PEs.

1.  **Virtual Addressing (Default):** This is the standard mode. Each PE accesses the SPM with a "virtual" address. The simulator translates this to a physical address based on the PE's ID, effectively giving each PE its own private bank of memory.
    - `physical_addr = virtual_addr + pe_id * BANK_SIZE`
    - This allows all PEs to run the same code using local addresses (e.g., 0 to 511) without interfering with each other. To access data shared between PEs, they must use addresses outside their local bank (e.g., negative addresses or addresses greater than the bank size).

2.  **Interleaved Addressing (`mvi` instruction):** This mode is activated by using the `mvi` (Move with Index Swizzle) instruction. In this mode, addresses are interleaved across the PE banks. For example, with a bank size of 512:
    - address `0` maps to `SPM[0]`
    - address `1` maps to `SPM[512]`
    - address `2` maps to `SPM[1024]`
    This mode is useful when PEs need to access shared data structures in a strided pattern.
