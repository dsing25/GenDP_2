# GenDP ISA and Programming Manual

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Execution Model](#execution-model)
3. [Control Instruction Format](#control-instruction-format)
4. [Source and Destination Codes](#source-and-destination-codes)
5. [Opcode Reference](#opcode-reference)
6. [Scratchpad Memory (SPM)](#scratchpad-memory-spm)
7. [Synchronization](#synchronization)
8. [Programming Patterns](#programming-patterns)

---

## Architecture Overview

GenDP is a domain-specific accelerator organized as a hierarchical system of Processing Elements (PEs) governed by an array controller.

### System Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                    Array Controller                      │
│                      (pe_array)                          │
│  - 16 addressing registers (gr[0..15])                   │
│  - Input/Output buffers                                  │
│  - 4 FIFOs                                               │
│  - Controls PE execution via set_PC                      │
└──────────────┬──────────────────────────────────────────┘
               │ Systolic data flow (in_port/out_port)
               ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  PE[0]   │─▶│  PE[1]   │─▶│  PE[2]   │─▶│  PE[3]   │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
     │             │             │             │
     └─────────────┴─────────────┴─────────────┘
                         │
                    Shared SPM
                  (4096 addresses)
```

### PE Resources
Each PE contains:
- **Compute Register File (`reg`)**: 32 registers, 32-bit each
- **Addressing Register File (`gr`)**: 16 registers for address calculation
- **Compute Instruction Buffer**: Holds compute trace instructions
- **Control Instruction Buffer**: 512 instruction pairs for control trace
- **SPM Port**: One port to shared scratchpad memory (read OR write per cycle)

### Controller Resources
The array controller (pe_array) contains:
- **Addressing Register File (`gr`)**: 16 registers (gr[0..15])
- **Input Buffer (`in_buf`)**: For loading data from external memory
- **Output Buffer (`out_buf`)**: For storing results to external memory
- **S2 Buffer (`S2`)**: Controller-local buffer for block data staging
- **FIFOs**: 4 FIFOs for data buffering between iterations
- **Compute Instruction Buffer**: Distributes compute instructions to PEs

---

## Execution Model

### Dual-Trace Architecture (PE only)
Each PE runs two independent traces:
1. **Control Trace**: Data movement and control flow (documented here)
2. **Compute Trace**: Arithmetic operations (separate documentation)

The control trace can set the compute trace's PC, enabling coarse-grained synchronization.

### VLIW Control Execution
The control trace uses a VLIW design with **two slots** that execute as a pair. Instructions are written in pairs:

```python
# Instructions are written in pairs
f.write(data_movement_instruction(...))  # Slot 0 (written first, executes SECOND)
f.write(data_movement_instruction(...))  # Slot 1 (written second, executes FIRST)
```

**Critical Execution Order**: The simulator processes the **second-written instruction (Slot 1) first**, then the **first-written instruction (Slot 0)**. This counter-intuitive order matters for hazards involving arithmetic operations that write to `gr`:

```python
# INCORRECT - read sees NEW value because increment (Slot 1) executes first
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))   # Slot 0: read SPM[gr[1]] - executes 2nd, sees new gr[1]
f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))   # Slot 1: gr[1]++ - executes 1st

# CORRECT - place increment in Slot 0 so it executes AFTER the read
f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))   # Slot 0: gr[1]++ - executes 2nd
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))   # Slot 1: read SPM[gr[1]] - executes 1st, sees old gr[1]
```

**Execution Order Summary**:
- First written instruction → stored in Slot 0 → decoded **second**
- Second written instruction → stored in Slot 1 → decoded **first**

**Write Timing Note**: Arithmetic ops (`add`, `addi`, `sub`, `subi`, `shifti_*`, `andi`) write to `gr` **immediately** during decode. However, `mv`/`si` writes to `gr` are **deferred** until after both decodes complete. This means hazards between two `mv`/`si` instructions are safe (both see old values), but hazards involving arithmetic ops require careful ordering as shown above.

### Controller Execution
The controller has only **one control thread**. Use `XXX_main_instruction()` functions for controller code.

---

## Control Instruction Format

### 64-bit Instruction Encoding

```
Bit:  63    54 53  50 49  46 45   44   43       30 29  26 25   24   23       10 9   6 5    0
     ┌───────┬──────┬──────┬────┬────┬───────────┬──────┬────┬────┬───────────┬─────┬──────┐
     │ rsvd  │ dest │ src  │ib0│ai0 │   imm_0   │ reg0 │ib1│ai1 │   imm_1   │reg1 │opcode│
     │ 10b   │ 4b   │ 4b   │ 1b│ 1b │   14b     │  4b  │ 1b│ 1b │   14b     │ 4b  │  6b  │
     └───────┴──────┴──────┴────┴────┴───────────┴──────┴────┴────┴───────────┴─────┴──────┘
```

### Field Descriptions

| Field                        | Bits | Description                                          |
|:-----------------------------|:----:|:-----------------------------------------------------|
| `dest`                       | 4    | Destination location code                            |
| `src`                        | 4    | Source location code                                 |
| `reg_immBar_0` (ib0)         | 1    | Operand 0 mode: 0=imm, 1=register indirect          |
| `reg_auto_increase_0` (ai0)  | 1    | Auto-increment `reg_0` after use                    |
| `imm_0`                      | 14   | Immediate value or register index (sign-extended)   |
| `reg_0`                      | 4    | Base register for operand 0 address calculation     |
| `reg_immBar_1` (ib1)         | 1    | Operand 1 mode: 0=imm, 1=register indirect          |
| `reg_auto_increase_1` (ai1)  | 1    | Auto-increment `reg_1` after use                    |
| `imm_1`                      | 14   | Immediate value or register index (sign-extended)   |
| `reg_1`                      | 4    | Base register for operand 1 address calculation     |
| `opcode`                     | 6    | Operation code                                       |

### Python Generator Function

```python
def data_movement_instruction(dest, src, reg_immBar_0, reg_auto_increase_0, imm_0, reg_0,
                              reg_immBar_1, reg_auto_increase_1, imm_1, reg_1, opcode):
    """
    Arguments (positional):
        0  dest                  - destination location code
        1  src                   - source location code
        2  reg_immBar_0          - 0: imm_0 is immediate, 1: imm_0 is register index
        3  reg_auto_increase_0   - 1: auto-increment reg_0 after operation
        4  imm_0                 - immediate value OR register index for operand 0
        5  reg_0                 - base register added to operand 0 address
        6  reg_immBar_1          - 0: imm_1 is immediate, 1: imm_1 is register index
        7  reg_auto_increase_1   - 1: auto-increment reg_1 after operation
        8  imm_1                 - immediate value OR register index for operand 1
        9  reg_1                 - base register added to operand 1 address
       10  opcode                - operation code
    """
```

### Address Calculation

For memory operations (`mv`, `si`, etc.), addresses are calculated as:

```
if reg_immBar == 1:
    address = gr[imm] + gr[reg]      # Register indirect: imm is register index
else:
    address = imm + gr[reg]          # Immediate: imm is literal value (sign-extended)
```

---

## Source and Destination Codes

### Code Reference Table

| Code | Name                  | Python       | Description                              |
|:----:|:----------------------|:-------------|:-----------------------------------------|
| 0    | Compute Register      | `reg`        | 32-entry compute register file           |
| 1    | Address Register      | `gr`         | 16-entry addressing register file        |
| 2    | Scratchpad Memory     | `SPM`        | Shared scratchpad memory                 |
| 3    | Compute Instr Buffer  | `comp_ib`    | Compute instruction buffer               |
| 4    | Control Instr Buffer  | `ctrl_ib`    | Control instruction buffer               |
| 5    | Input Buffer          | `in_buf`     | External input data buffer               |
| 6    | Output Buffer         | `out_buf`    | External output data buffer              |
| 7    | Input Port            | `in_port`    | Systolic input from previous PE          |
| 8    | Input Instruction     | `in_instr`   | Systolic instruction input               |
| 9    | Output Port           | `out_port`   | Systolic output to next PE               |
| 10   | Output Instruction    | `out_instr`  | Systolic instruction output              |
| 11-14| FIFO 0-3              | `fifo[0-3]`  | FIFO queues for data buffering           |
| 15   | S2 Buffer             | `S2`         | Controller-local buffer                  |

### PE Source/Destination Support

| Code | Name     | Load | Store | Notes                                           |
|:----:|:---------|:----:|:-----:|:------------------------------------------------|
| 0    | reg      | ✓    | ✓     |                                                 |
| 1    | gr       | ✓    | ✓     |                                                 |
| 2    | SPM      | ✓    | ✓     | When src, dest must be reg, gr, or out_port    |
| 3    | comp_ib  | ✓    | ✓     | Instruction load/store                          |
| 4    | ctrl_ib  | -    | -     | Not supported                                   |
| 5    | in_buf   | -    | -     | Controller only                                 |
| 6    | out_buf  | -    | -     | Controller only                                 |
| 7    | in_port  | ✓    | -     | Receive from systolic chain                     |
| 8    | in_instr | ✓    | -     | Receive instruction from chain                  |
| 9    | out_port | -    | ✓     | Send to systolic chain                          |
| 10   | out_instr| -    | ✓     | Send instruction to chain                       |
| 11-14| fifo     | -    | -     | Controller only                                 |
| 15   | S2       | -    | -     | Controller only                                 |

### Controller Source/Destination Support

| Code | Name     | Load | Store | Notes                                           |
|:----:|:---------|:----:|:-----:|:------------------------------------------------|
| 0    | reg      | -    | -     | PE only                                         |
| 1    | gr       | ✓    | ✓     | Valid for arithmetic ops                        |
| 2    | SPM      | ✓*   | ✓*    | *Planned but not yet implemented                |
| 3    | comp_ib  | ✓    | -     | Load instructions to distribute to PEs         |
| 4    | ctrl_ib  | -    | -     | Not supported                                   |
| 5    | in_buf   | ✓    | -     | Load from external input                        |
| 6    | out_buf  | -    | ✓     | Valid for arithmetic ops                        |
| 7    | in_port  | ✓    | -     | Receive from PE[3]                              |
| 8    | in_instr | -    | -     | PE only                                         |
| 9    | out_port | -    | ✓     | Valid for arithmetic ops                        |
| 10   | out_instr| -    | ✓†    | †Move ops only (`mv`, `si`); crashes on arith   |
| 11-14| fifo     | ✓    | ✓     | Pop on load, push on store                      |
| 15   | S2       | ✓‡   | ✓‡    | ‡Controller-only via `mvdq` (SPM ↔ S2)          |

**Controller Arithmetic Destination Restriction**: Arithmetic operations (`add`, `sub`, `addi`, `subi`, `shifti_*`, `andi`) on the controller can only write to `gr` (1), `out_buf` (6), or `out_port` (9). Using other destinations (e.g., `out_instr`, `fifo`) will crash the simulator. Move operations (`mv`, `si`) have broader destination support.

**Note on out_instr (code 10) for Controller**: When the controller loads from `comp_ib`, the instruction is stored in an internal buffer (`PE_instruction`). Specifying `out_instr` as the destination in a `mv` operation causes the store function to do nothing, but the instruction is still transferred to PEs via the internal buffer. This is the mechanism for distributing compute instructions.

**Note on S2 (code 15) for Controller**: The S2 buffer is only accessible via `mvdq` (opcode 22) and `mvdqi` (opcode 23) for direct 8-word transfers between SPM and S2 or immediate block writes. Other operations do not support S2.

### Import Statement
```python
from opcodes import reg, gr, SPM, comp_ib, ctrl_ib, in_buf, out_buf, in_port, in_instr, out_port, out_instr, fifo, S2
```

### Systolic Data Flow

Data flows through PEs in a chain:
```
Controller.out_port → PE[0].in_port → PE[0].out_port → PE[1].in_port → ... → PE[3].out_port → Controller.in_port
```

---

## Opcode Reference

### Opcode Summary Table

| Code | Name                  | Python     | Description                                   |
|:----:|:----------------------|:-----------|:----------------------------------------------|
| 0    | Add                   | `add`      | gr[rd] = gr[rs1] + gr[rs2]                   |
| 1    | Subtract              | `sub`      | gr[rd] = gr[rs1] - gr[rs2]                   |
| 2    | Add Immediate         | `addi`     | gr[rd] = imm + gr[rs2]                       |
| 4    | Store Immediate       | `si`       | dest[addr] = imm                             |
| 5    | Move                  | `mv`       | dest[addr0] = src[addr1]                     |
| 8    | Branch Not Equal      | `bne`      | if (op1 != op2) PC += offset                 |
| 9    | Branch Equal          | `beq`      | if (op1 == op2) PC += offset                 |
| 10   | Branch ≥              | `bge`      | if (op1 >= op2) PC += offset                 |
| 11   | Branch <              | `blt`      | if (op1 < op2) PC += offset                  |
| 12   | Jump                  | `jump`     | PC += offset                                 |
| 13   | Set PC                | `set_PC`   | Set compute PC (PE) or all PE PCs (ctrl)     |
| 14   | No-op                 | `none`     | No operation                                 |
| 15   | Halt                  | `halt`     | Stall (PE) or terminate (controller)         |
| 16   | Shift Right           | `shifti_r` | gr[rd] = gr[rs2] >> imm (arithmetic)        |
| 17   | Shift Left            | `shifti_l` | gr[rd] = gr[rs2] << imm                      |
| 18   | And Immediate         | `ANDI`     | gr[rd] = gr[rs2] & imm                       |
| 19   | Move Double           | `mvd`      | Move 2 words (64 bits)                       |
| 20   | Subtract Immediate    | `subi`     | gr[rd] = gr[rs2] - imm                       |
| 21   | Move Interleaved      | `mvi`      | Move with address swizzling                  |
| 22   | Move Double Quad      | `mvdq`     | Move 8 words (block)                         |
| 23   | Move Double Quad Imm  | `mvdqi`    | Write 8 words of immediate                   |

### Import Statement
```python
from opcodes import add, sub, addi, si, mv, bne, beq, bge, blt, jump, set_PC, none, halt, shifti_r, shifti_l, ANDI, mvd, subi, mvi, mvdq, mvdqi
```

---

### Detailed Opcode Documentation

#### `add` (opcode 0) - Register Addition

**Summary**: Adds two addressing registers and stores result in a third.

**Syntax**:
```
add gr[rd], gr[rs1], gr[rs2]    # gr[rd] = gr[rs1] + gr[rs2]
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Must be gr (1) for PE; can be gr or out_buf for controller
    src,            # Unused (typically 0)
    0,              # reg_immBar_0: unused
    0,              # reg_auto_increase_0: unused
    rd,             # imm_0: destination register index
    0,              # reg_0: unused
    0,              # reg_immBar_1: unused
    0,              # reg_auto_increase_1: unused
    rs1,            # imm_1: first source register index
    rs2,            # reg_1: second source register index
    add             # opcode: 0
)
```

**Operand Mapping**:
| Field   | Usage                                                               |
|---------|:-------------------------------------------------------------------|
| `dest`  | PE: `gr` (1) or `out_port` (9). Controller: `gr`, `out_buf`, `out_port` |
| `imm_0` | `rd` - destination register index (0-15)                           |
| `imm_1` | `rs1` - first source register index (0-15)                         |
| `reg_1` | `rs2` - second source register index (0-15)                        |

**Example**:
```python
# gr[5] = gr[2] + gr[3]
f.write(data_movement_instruction(gr, 0, 0, 0, 5, 0, 0, 0, 2, 3, add))
```

**Controller Difference**: Controller can write result to `out_buf` or `out_port` in addition to `gr`.

---

#### `sub` (opcode 1) - Register Subtraction

**Summary**: Subtracts two addressing registers and stores result.

**Syntax**:
```
sub gr[rd], gr[rs1], gr[rs2]    # gr[rd] = gr[rs1] - gr[rs2]
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Must be gr (1) for PE
    src,            # Unused (typically 0)
    0,              # reg_immBar_0: unused
    0,              # reg_auto_increase_0: unused
    rd,             # imm_0: destination register index
    0,              # reg_0: unused
    0,              # reg_immBar_1: unused
    0,              # reg_auto_increase_1: unused
    rs1,            # imm_1: first source register index
    rs2,            # reg_1: second source register index
    sub             # opcode: 1
)
```

**Operand Mapping**:
| Field   | Usage                                                               |
|---------|:-------------------------------------------------------------------|
| `dest`  | PE: `gr` (1) or `out_port` (9). Controller: `gr`, `out_buf`, `out_port` |
| `imm_0` | `rd` - destination register index                                  |
| `imm_1` | `rs1` - first source register (minuend)                            |
| `reg_1` | `rs2` - second source register (subtrahend)                        |

**Example**:
```python
# gr[9] = gr[9] - gr[14]
f.write(data_movement_instruction(gr, gr, 0, 0, 9, 0, 0, 0, 9, 14, sub))
```

---

#### `addi` (opcode 2) - Add Immediate

**Summary**: Adds an immediate value to a register.

**Syntax**:
```
addi gr[rd], imm, gr[rs2]    # gr[rd] = imm + gr[rs2]
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Must be gr (1) for PE
    src,            # Unused (typically gr)
    0,              # reg_immBar_0: unused (but often set to 1 in examples)
    0,              # reg_auto_increase_0: unused
    rd,             # imm_0: destination register index
    0,              # reg_0: unused
    0,              # reg_immBar_1: 0 means imm_1 is immediate
    0,              # reg_auto_increase_1: unused
    imm,            # imm_1: immediate value (14-bit, sign-extended)
    rs2,            # reg_1: source register index
    addi            # opcode: 2
)
```

**Operand Mapping**:
| Field   | Usage                                                               |
|---------|:-------------------------------------------------------------------|
| `dest`  | PE: `gr` (1) or `out_port` (9). Controller: `gr`, `out_buf`, `out_port` |
| `imm_0` | `rd` - destination register index                                  |
| `imm_1` | `imm` - immediate value (-8192 to 8191)                            |
| `reg_1` | `rs2` - source register to add to                                  |

**Example**:
```python
# gr[1] = 1 + gr[1]  (increment gr[1])
f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))

# gr[7] = gr[7] + 1  (common increment pattern)
f.write(data_movement_instruction(gr, gr, 1, 0, 7, 0, 0, 0, 1, 7, addi))
```

**Note**: The `reg_immBar_0` flag is often set to 1 in examples but doesn't affect `addi` behavior.

---

#### `subi` (opcode 20) - Subtract Immediate

**Summary**: Subtracts an immediate value from a register.

**Syntax**:
```
subi gr[rd], gr[rs2], imm    # gr[rd] = gr[rs2] - imm
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Must be gr (1)
    src,            # Unused
    0,              # reg_immBar_0: unused
    0,              # reg_auto_increase_0: unused
    rd,             # imm_0: destination register index
    0,              # reg_0: unused
    0,              # reg_immBar_1: unused
    0,              # reg_auto_increase_1: unused
    imm,            # imm_1: immediate value to subtract
    rs2,            # reg_1: source register (minuend)
    subi            # opcode: 20
)
```

**Operand Mapping**:
| Field   | Usage                                                               |
|---------|:-------------------------------------------------------------------|
| `dest`  | PE: `gr` (1) or `out_port` (9). Controller: `gr`, `out_buf`, `out_port` |
| `imm_0` | `rd` - destination register index                                  |
| `imm_1` | `imm` - immediate value to subtract                                |
| `reg_1` | `rs2` - source register                                            |

**Example**:
```python
# gr[1] = gr[1] - 1  (decrement)
f.write(data_movement_instruction(gr, gr, 1, 0, 1, 0, 0, 0, 1, 1, subi))
```

---

#### `si` (opcode 4) - Store Immediate

**Summary**: Stores an immediate value to a memory location.

**Syntax**:
```
si dest[addr], imm           # dest[addr] = imm
si dest[gr[reg0]++], imm     # dest[gr[reg0]] = imm; gr[reg0]++
si dest[imm0 + gr[reg0]], imm
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Destination location code
    src,            # Unused (typically 0)
    reg_immBar_0,   # 0: addr = imm_0 + gr[reg_0], 1: addr = gr[imm_0] + gr[reg_0]
    auto_inc_0,     # 1: increment gr[reg_0] after store
    imm_0,          # Address immediate or register index
    reg_0,          # Base register for address
    0,              # reg_immBar_1: unused
    0,              # reg_auto_increase_1: unused
    imm,            # imm_1: value to store (sign-extended)
    0,              # reg_1: unused
    si              # opcode: 4
)
```

**Operand Mapping**:
| Field              | Usage                                                    |
|--------------------|:---------------------------------------------------------|
| `dest`             | PE: `gr`, `reg`, `SPM`, `comp_ib`, `out_port`, `out_instr`. Controller: `gr`, `out_buf`, `out_port`, `fifo` |
| `reg_immBar_0`     | Address mode: 0=immediate offset, 1=register indirect   |
| `reg_auto_increase_0` | 1 to auto-increment `reg_0`                            |
| `imm_0`            | Address offset or register index                        |
| `reg_0`            | Base register for address                               |
| `imm_1`            | Value to store                                          |

**Examples**:
```python
# gr[12] = 5  (store immediate 5 to gr[12])
f.write(data_movement_instruction(gr, 0, 0, 0, 12, 0, 0, 0, 5, 0, si))

# gr[10] = 0
f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))

# gr[4] = BLOCK_START  (store constant)
f.write(data_movement_instruction(gr, 0, 0, 0, 4, 0, 0, 0, BLOCK_START, 0, si))
```

---

#### `mv` (opcode 5) - Move

**Summary**: Moves a single word (32 bits) from source to destination.

**Syntax**:
```
mv dest[addr0], src[addr1]
mv dest[gr[r0]++], src[gr[r1]++]    # With auto-increment
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Destination location code
    src,            # Source location code
    reg_immBar_0,   # Dest addr mode: 0=immediate, 1=register
    auto_inc_0,     # 1: increment gr[reg_0] after operation
    imm_0,          # Dest address offset or register index
    reg_0,          # Dest base register
    reg_immBar_1,   # Src addr mode: 0=immediate, 1=register
    auto_inc_1,     # 1: increment gr[reg_1] after operation
    imm_1,          # Src address offset or register index
    reg_1,          # Src base register
    mv              # opcode: 5
)
```

**Address Calculation** (for both source and destination):
```
if reg_immBar == 0:
    address = sign_extend(imm) + gr[reg]
else:
    address = gr[imm] + gr[reg]
```

**Examples**:
```python
# reg[12] = SPM[gr[2]]  (load from SPM)
f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))

# SPM[gr[4]] = gr[1]  (store to SPM)
f.write(data_movement_instruction(SPM, gr, 0, 0, 0, 4, 0, 0, 1, 0, mv))

# out_port = in_port  (systolic pass-through)
f.write(data_movement_instruction(out_port, in_port, 0, 0, 0, 0, 0, 0, 0, 0, mv))

# gr[3] = input_buffer[gr[2]++]  (load with auto-increment)
f.write(data_movement_instruction(gr, in_buf, 0, 0, 3, 0, 0, 1, 0, 2, mv))

# reg[11] = in_port  (receive from systolic chain)
f.write(data_movement_instruction(reg, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))

# out_port = reg[15]  (send to systolic chain)
f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 15, 0, mv))
```

**SPM Latency Warning**: SPM access has 2-cycle latency. See [SPM section](#scratchpad-memory-spm) for proper usage.

---

#### `mvd` (opcode 19) - Move Double

**Summary**: Moves two consecutive words (64 bits) from source to destination. One operand must be SPM.

**Syntax**:
```
mvd dest[addr0], src[addr1]    # Moves 2 words
```

**Encoding**: Identical to `mv`, but uses opcode 19.

```python
data_movement_instruction(
    dest,           # Destination location code
    src,            # Source location code (one must be SPM)
    reg_immBar_0,   # Dest addr mode
    auto_inc_0,     # Dest auto-increment
    imm_0,          # Dest address
    reg_0,          # Dest base register
    reg_immBar_1,   # Src addr mode
    auto_inc_1,     # Src auto-increment
    imm_1,          # Src address
    reg_1,          # Src base register
    mvd             # opcode: 19
)
```

**Constraint**: Either `src` or `dest` must be `SPM` (2).

**Examples**:
```python
# reg[4,5] = SPM[7*MEM_BLOCK_SIZE + block_start]  (load 2 words)
f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 7*MEM_BLOCK_SIZE+block_start, 0, mvd))

# SPM[gr[6]] = reg[24,25]  (store 2 words)
f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 6, 0, 0, 24, 0, mvd))
```

---

#### `mvdq` (opcode 22) - Move Double Quad

**Summary**: Moves eight consecutive words (256 bits) between SPM and the controller S2 buffer. Controller-only and implemented as a direct buffer copy (no SPM event latency).

**Syntax**:
```
mvdq dest[addr0], src[addr1]    # Moves 8 words
```

**Encoding**: Identical to `mv`, but uses opcode 22.

```python
data_movement_instruction(
    dest,           # Destination location code (SPM or S2)
    src,            # Source location code (S2 or SPM)
    reg_immBar_0,   # Dest addr mode
    auto_inc_0,     # Dest auto-increment (adds 8)
    imm_0,          # Dest address
    reg_0,          # Dest base register
    reg_immBar_1,   # Src addr mode
    auto_inc_1,     # Src auto-increment (adds 8)
    imm_1,          # Src address
    reg_1,          # Src base register
    mvdq            # opcode: 22
)
```

**Constraint**: Only `SPM` (2) and `S2` (15) are supported. One must be `SPM`, the other `S2`.

**Controller Only**: On a PE, opcode 22 is reserved and currently unimplemented; executing it will error.

**Auto-increment**: If enabled, base registers increment by 8 after the transfer.

**Examples**:
```python
# S2[gr[10]] = SPM[gr[4]]  (copy 8 words from SPM to S2)
f.write(data_movement_instruction(S2, SPM, 0, 0, 0, 10, 0, 0, 0, 4, mvdq))

# SPM[gr[6]] = S2[gr[12]++]  (copy 8 words from S2 to SPM, auto-inc by 8)
f.write(data_movement_instruction(SPM, S2, 0, 0, 0, 6, 0, 1, 0, 12, mvdq))
```

---

#### `mvdqi` (opcode 23) - Move Double Quad Immediate

**Summary**: Writes eight consecutive words of the immediate value to SPM or S2. Controller-only and implemented as a direct buffer write (no SPM event latency).

**Syntax**:
```
mvdqi dest[addr0], imm         # Writes 8 words
```

**Encoding**: Identical to `si`, but writes 8 words and uses opcode 23. The immediate value is taken from `imm_1`; `src` is unused.

```python
data_movement_instruction(
    dest,           # Destination location code (SPM or S2)
    src,            # Unused (set to 0)
    reg_immBar_0,   # Dest addr mode
    auto_inc_0,     # Dest auto-increment (adds 8)
    imm_0,          # Dest address
    reg_0,          # Dest base register
    0,              # reg_immBar_1: unused
    0,              # reg_auto_increase_1: unused
    imm,            # imm_1: immediate value
    0,              # reg_1: unused
    mvdqi           # opcode: 23
)
```

**Constraint**: Destination must be `SPM` (2) or `S2` (15).

**Controller Only**: On a PE, opcode 23 is reserved and currently unimplemented; executing it will error.

**Auto-increment**: If enabled, the base register increments by 8 after the write.

**Examples**:
```python
# SPM[gr[4]] = 0x7f (write 8 words of 0x7f)
f.write(data_movement_instruction(SPM, 0, 0, 0, 0, 4, 0, 0, 0x7f, 0, mvdqi))

# S2[gr[10]++] = -1  (write 8 words of -1, auto-inc by 8)
f.write(data_movement_instruction(S2, 0, 0, 1, 0, 10, 0, 0, -1, 0, mvdqi))
```

---

#### `mvi` (opcode 21) - Move Interleaved

**Summary**: Moves a single word with address swizzling for interleaved SPM access. Used for accessing shared data across PEs.

**Syntax**:
```
mvi dest[addr0], src[addr1]    # With address swizzling
```

**Encoding**: Identical to `mv`, but uses opcode 21.

**Address Swizzling**: The lower 2 bits of the address are moved to the high bits:
```c
// N_SWIZZLE_BITS = 2, ADDR_LEN = 11
int lower_bits = addr & 0x3;           // Extract bits [1:0]
int upper_bits = addr >> 2;            // Extract bits [10:2]
int swizzled = upper_bits | (lower_bits << 9);  // Recombine
```

**Physical Addressing**: Unlike `mv` and `mvd`, `mvi` uses **physical addressing** (not virtual) after applying the swizzle. This means the swizzled address directly indexes into the global SPM space without the per-PE bank offset.

**Use Case**: When data is distributed across PE banks in round-robin fashion, `mvi` allows any PE to access any element by index:
- Address 0 → SPM bank 0 (physical address 0)
- Address 1 → SPM bank 1 (physical address 512)
- Address 2 → SPM bank 2 (physical address 1024)
- Address 3 → SPM bank 3 (physical address 1536)

**Examples**:
```python
# Load pattern character at index gr[2] (interleaved across PEs)
f.write(data_movement_instruction(gr, SPM, 0, 0, 3, 0, 0, 0, SWIZZLED_PATTERN_START, 2, mvi))

# Load text character at index gr[1]
f.write(data_movement_instruction(gr, SPM, 0, 0, 5, 0, 0, 0, SWIZZLED_TEXT_START, 1, mvi))
```

**Constraint**: Either `src` or `dest` must be `SPM` (2).

---

#### `bne` (opcode 8) - Branch Not Equal

**Summary**: Branches if two values are not equal.

**Syntax**:
```
bne imm_val, gr[rs2], offset     # if (imm_val != gr[rs2]) PC += offset
bne gr[rs1], gr[rs2], offset     # if (gr[rs1] != gr[rs2]) PC += offset
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Unused (typically gr)
    src,            # Unused (typically gr)
    0,              # reg_immBar_0: unused
    0,              # reg_auto_increase_0: unused
    offset,         # imm_0: PC-relative branch offset (sign-extended)
    0,              # reg_0: unused
    reg_immBar_1,   # 0: compare against imm_1, 1: compare gr[imm_1]
    0,              # reg_auto_increase_1: unused
    operand1,       # imm_1: immediate value or register index
    rs2,            # reg_1: second operand register index
    bne             # opcode: 8
)
```

**Operand Mapping**:
| Field          | Usage                                                    |
|:---------------|:---------------------------------------------------------|
| `imm_0`        | Branch offset (added to PC if taken)                    |
| `reg_immBar_1` | 0: operand1 is immediate, 1: operand1 is gr[imm_1]     |
| `imm_1`        | First operand (immediate or register index)             |
| `reg_1`        | Second operand register index                           |

**Branch Behavior**:
- If condition is true: `PC = PC + offset`
- If condition is false: `PC = PC + 1`

**Examples**:
```python
# Wait loop: while (gr[13] != 1) spin
# bne 1, gr[13], 0  (offset 0 = stay at same instruction)
f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))

# if (gr[9] != gr[7]) jump back 13 instructions
f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, bne))
```

---

#### `beq` (opcode 9) - Branch Equal

**Summary**: Branches if two values are equal.

**Syntax**:
```
beq imm_val, gr[rs2], offset     # if (imm_val == gr[rs2]) PC += offset
beq gr[rs1], gr[rs2], offset     # if (gr[rs1] == gr[rs2]) PC += offset
```

**Encoding**: Same as `bne`, but uses opcode 9.

**Examples**:
```python
# Unconditional jump (beq 0, gr[0], offset) where gr[0]=0
f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 0, 0, beq))  # Jump +2

# if (gr[3] == gr[5]) jump -4
f.write(data_movement_instruction(0, 0, 0, 0, -4, 0, 1, 0, 3, 5, beq))
```

---

#### `bge` (opcode 10) - Branch Greater or Equal

**Summary**: Branches if first operand >= second operand (signed comparison).

**Syntax**:
```
bge imm_val, gr[rs2], offset     # if (imm_val >= gr[rs2]) PC += offset
bge gr[rs1], gr[rs2], offset     # if (gr[rs1] >= gr[rs2]) PC += offset
```

**Encoding**: Same as `bne`, but uses opcode 10.

**Examples**:
```python
# if (gr[2] >= gr[8]) jump +8
f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 8, bge))

# Loop: while (gr[1] >= -1) continue  (offset -4)
f.write(data_movement_instruction(0, 0, 0, 0, -4, 0, 0, 0, -1, 1, bge))
```

---

#### `blt` (opcode 11) - Branch Less Than

**Summary**: Branches if first operand < second operand (signed comparison).

**Syntax**:
```
blt imm_val, gr[rs2], offset     # if (imm_val < gr[rs2]) PC += offset
blt gr[rs1], gr[rs2], offset     # if (gr[rs1] < gr[rs2]) PC += offset
```

**Encoding**: Same as `bne`, but uses opcode 11.

**Examples**:
```python
# if (gr[9] < gr[7]) jump back 13 instructions (loop)
f.write(data_movement_instruction(0, 0, 0, 0, -13, 0, 1, 0, 9, 7, blt))

# if (MEM_BLOCK_SIZE < gr[9]) jump +3
f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, MEM_BLOCK_SIZE, 9, blt))

# if (gr[1] < gr[0]) jump +9  (early exit if negative)
f.write(data_movement_instruction(0, 0, 0, 0, 9, 0, 1, 0, 1, 0, blt))
```

---

#### `jump` (opcode 12) - Unconditional Jump

**Summary**: Unconditionally jumps to PC-relative offset.

**Syntax**:
```
jump offset    # PC = PC + offset
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Unused
    src,            # Unused
    0, 0,           # Unused
    offset,         # imm_0: PC-relative offset (sign-extended)
    0,              # Unused
    0, 0,           # Unused
    0,              # Unused
    0,              # Unused
    jump            # opcode: 12
)
```

**Examples**:
```python
# Jump back 25 instructions
f.write(data_movement_instruction(gr, gr, 0, 0, -25, 0, 0, 0, 0, 0, jump))

# Jump forward 5 instructions
f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 0, jump))
```

---

#### `set_PC` (opcode 13) - Set Program Counter

**Summary**: Sets a program counter. Behavior differs between PE and controller.

**Syntax**:
```
set_PC target    # Set PC to target value
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Unused (typically gr or 0)
    src,            # Unused (typically gr or 0)
    0, 0,           # Unused
    target,         # imm_0: target PC value
    0,              # Unused
    0, 0,           # Unused
    0,              # Unused
    0,              # Unused
    set_PC          # opcode: 13
)
```

**PE Behavior**: Sets the **compute trace PC** (`comp_PC`) to the target value. The control trace PC continues normally (PC++).

**Controller Behavior**: Sets **all PEs' control trace PCs** (both threads) to the target value. This is how the controller dispatches work to PEs.

**Examples**:
```python
# PE: Set compute PC to COMPUTE_H (start compute routine)
f.write(data_movement_instruction(0, 0, 0, 0, COMPUTE_H, 0, 0, 0, 0, 0, set_PC))

# Controller: Set all PE PCs to PE_INIT (start PE initialization)
f.write(data_movement_instruction(0, 0, 0, 0, PE_INIT, 0, 0, 0, 0, 0, set_PC))

# PE: Set compute PC to 0 (reset compute trace)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, set_PC))
```

---

#### `none` (opcode 14) - No Operation

**Summary**: Does nothing; advances PC by 1.

**Syntax**:
```
nop
```

**Encoding**:
```python
data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none)
```

**Use Cases**:
- Padding for SPM latency
- Alignment in paired instruction streams
- Placeholder in conditional code

**Example**:
```python
# Two no-ops (one per thread)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
```

---

#### `halt` (opcode 15) - Halt Execution

**Summary**: Halts execution. Behavior differs between PE and controller.

**Syntax**:
```
halt
```

**Encoding**:
```python
data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt)
```

**PE Behavior**: Stalls the PE (PC does not advance). The PE remains halted until the **controller sets its PC** via `set_PC`. Used for synchronization.

**Controller Behavior**: **Terminates the simulation**. Returns -1 from decode, ending the run loop.

**Examples**:
```python
# PE: Wait for controller to restart
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

# Controller: End program
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
```

---

#### `shifti_r` (opcode 16) - Shift Right Immediate

**Summary**: Arithmetic right shift by immediate amount.

**Syntax**:
```
shifti_r gr[rd], gr[rs2], imm    # gr[rd] = gr[rs2] >> imm (arithmetic)
```

**Encoding**:
```python
data_movement_instruction(
    gr,             # dest: must be gr (1)
    src,            # Unused
    0, 0,           # Unused
    rd,             # imm_0: destination register
    0,              # Unused
    0, 0,           # Unused
    shift_amt,      # imm_1: shift amount
    rs2,            # reg_1: source register
    shifti_r        # opcode: 16
)
```

**Note**: Performs **arithmetic** (sign-extending) right shift. The shift amount (`imm_1`) is treated as an **unsigned** 14-bit value (NOT sign-extended), so only non-negative shift amounts are meaningful.

**Examples**:
```python
# gr[7] = gr[12] >> 2  (divide by 4)
f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2, 12, shifti_r))

# gr[7] = gr[12] >> 7  (divide by 128)
f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 2+MEM_BLOCK_SIZE_LG2, 12, shifti_r))
```

---

#### `shifti_l` (opcode 17) - Shift Left Immediate

**Summary**: Logical left shift by immediate amount.

**Syntax**:
```
shifti_l gr[rd], gr[rs2], imm    # gr[rd] = gr[rs2] << imm
```

**Encoding**: Same as `shifti_r`, but uses opcode 17.

**Note**: The shift amount (`imm_1`) is treated as an **unsigned** 14-bit value (NOT sign-extended).

**Examples**:
```python
# gr[5] = gr[3] << 2  (multiply by 4)
f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 0, 0, 2, 3, shifti_l))
```

---

#### `ANDI` (opcode 18) - And Immediate

**Summary**: Bitwise AND with immediate mask.

**Syntax**:
```
andi gr[rd], gr[rs2], imm    # gr[rd] = gr[rs2] & imm
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # Destination (gr for PE)
    src,            # Unused
    0, 0,           # Unused
    rd,             # imm_0: destination register
    0,              # Unused
    0, 0,           # Unused
    mask,           # imm_1: AND mask
    rs2,            # reg_1: source register
    ANDI            # opcode: 18
)
```

**Note**: The mask (`imm_1`) is treated as an **unsigned** 14-bit value (NOT sign-extended). Maximum mask value is 16383 (0x3FFF).

**Examples**:
```python
# gr[3] = gr[5] & 0xFF  (extract low byte)
f.write(data_movement_instruction(gr, 0, 0, 0, 3, 0, 0, 0, 0xFF, 5, ANDI))

# gr[2] = gr[2] & 0x3  (modulo 4)
f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 3, 2, ANDI))
```

---

## Scratchpad Memory (SPM)

### Overview

The SPM is a shared memory accessible by all PEs. It is organized into 4 banks, one per PE.

### Parameters

| Parameter           | Value       | Description                        |
|:-------------------|:------------|:----------------------------------|
| Total Size         | 4096 words  | Total addressable words            |
| Bank Size          | 1024 words  | Words per PE bank                  |
| Word Size          | 32 bits     | Single word                        |
| Double Word        | 64 bits     | Two consecutive words              |
| Access Latency     | 2 cycles    | Cycles from request to data        |
| Ports per PE       | 1           | Read OR write, not both            |
| Bandwidth          | 2 words     | Words per double-word access       |

### Access Constraints

**Critical Rules**:
1. **No simultaneous read/write**: Each PE has one port; cannot load and store in same cycle
2. **No pipelining**: Cannot issue new SPM request while one is in flight
3. **Latency padding**: Must insert 2 no-ops (or other non-SPM work) between SPM accesses
4. **SPM load destination constraint**: When loading from SPM, the destination must be `reg`, `gr`, or `out_port` only. Other destinations (e.g., `SPM`, `comp_ib`) are not supported because they have incompatible latency requirements

**Illegal Access Patterns**:
```python
# ILLEGAL: Load and store in same cycle
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))  # load
f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 2, 0, 0, 5, 0, mv))  # store - CONFLICT!

# ILLEGAL: Pipelined access (second request before first completes)
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))  # load 1
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     # nop
f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 2, mv))  # load 2 - TOO SOON!
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
```

**Legal Access Pattern**:
```python
# LEGAL: Proper latency padding
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))  # load 1
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     # nop (cycle 1)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     # nop (cycle 2)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))     # nop (data ready)
f.write(data_movement_instruction(reg, SPM, 0, 0, 4, 0, 0, 0, 0, 2, mv))  # load 2 - OK
```

### Addressing Modes

#### Virtual Addressing (Default)

Each PE sees its own "virtual" address space. Physical address = virtual address + PE_ID * BANK_SIZE.

```
PE[0]: virtual 0-1023  → physical 0-1023
PE[1]: virtual 0-1023  → physical 1024-2047
PE[2]: virtual 0-1023  → physical 2048-3071
PE[3]: virtual 0-1023  → physical 3072-4095
```

**Accessing Own Bank**:
```python
# PE accesses its own bank with addresses 0-1023
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 32, 0, mv))  # SPM[32] in own bank
```

**Accessing Other Banks** (negative or >1023 addresses):
```python
# PE[0] accessing PE[1]'s data at offset 32:
# Virtual address = 32 + 1024 = 1056
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 1056, 0, mv))

# PE[1] accessing PE[0]'s data at offset 32:
# Virtual address = 32 - 1024 = -992
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, -992, 0, mv))
```

#### Interleaved Addressing (`mvi`)

For data distributed round-robin across PEs, use `mvi` which swizzles addresses:

```
Index 0 → PE[0], physical 0
Index 1 → PE[1], physical 1024
Index 2 → PE[2], physical 2048
Index 3 → PE[3], physical 3072
Index 4 → PE[0], physical 1
Index 5 → PE[1], physical 1025
...
```

**Use Case**: Sequence data where character `i` is stored in `PE[i % 4]`.

```python
# Access character at logical index gr[2] (distributed across PEs)
f.write(data_movement_instruction(gr, SPM, 0, 0, 3, 0, 0, 0, SWIZZLED_START, 2, mvi))
```

---

## Synchronization

### PE to Controller Synchronization

**Mechanism**: PE's `gr[10]` is monitored by the controller.

- Each PE can set `gr[10]` to signal completion
- Controller's `gr[13]` = AND of all PE's `gr[10]` values
- Controller polls `gr[13]` to wait for all PEs

**PE Signaling Completion**:
```python
# PE: Signal done by setting gr[10] = 1
f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))
```

**Controller Waiting**:
```python
# Controller: Wait until all PEs have gr[10] = 1
# bne 1, gr[13], 0  (spin while gr[13] != 1)
f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))
```

**Resetting for Next Phase**:
```python
# PE: Clear sync flag before starting work
f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))
```

### Controller to PE Synchronization

**Mechanism**: Controller uses `set_PC` to start/restart PEs.

**Starting PEs**:
```python
# Controller: Start all PEs at address PE_INIT
f.write(data_movement_instruction(0, 0, 0, 0, PE_INIT, 0, 0, 0, 0, 0, set_PC))
```

**PE Waiting for Controller**:
```python
# PE: Halt and wait for controller to set PC
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))  # Both threads
```

### Typical Synchronization Pattern

```python
# === PE Code ===
# Do work...
f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))   # gr[10] = 1 (signal done)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))   # Wait for controller
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))

# === Controller Code ===
f.write(data_movement_instruction(0, 0, 0, 0, PE_START, 0, 0, 0, 0, 0, set_PC))  # Start PEs
f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))         # Wait for PEs
# PEs are done, continue with next phase...
f.write(data_movement_instruction(0, 0, 0, 0, PE_NEXT, 0, 0, 0, 0, 0, set_PC))   # Restart PEs
```

---

## Programming Patterns

### Pattern 1: Basic Loop with Counter

```python
# for (gr[9] = 0; gr[9] < gr[7]; gr[9]++)
f.write(data_movement_instruction(gr, 0, 0, 0, 9, 0, 0, 0, 0, 0, si))           # gr[9] = 0
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))

# LOOP_START:
# ... loop body ...

f.write(data_movement_instruction(gr, gr, 1, 0, 9, 0, 0, 0, 1, 9, addi))        # gr[9]++
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
f.write(data_movement_instruction(0, 0, 0, 0, -N, 0, 1, 0, 9, 7, blt))          # if gr[9] < gr[7] goto LOOP_START
f.write(data_movement_instruction(0, 0, 0, 0, -N, 0, 1, 0, 9, 7, blt))          # (both threads)
```

### Pattern 2: SPM Load with Proper Latency

```python
# Load from SPM, do other work during latency, then use result
f.write(data_movement_instruction(reg, SPM, 0, 0, 12, 0, 0, 0, 0, 2, mv))       # reg[12] = SPM[gr[2]]
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))          # Latency cycle 1
f.write(data_movement_instruction(gr, gr, 1, 0, 2, 0, 0, 0, 1, 2, addi))        # gr[2]++ (useful work)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))          # Latency cycle 2
# reg[12] now contains loaded value
```

### Pattern 3: Double-Word SPM Access

```python
# Load 2 words, wait for latency, store 2 words
f.write(data_movement_instruction(reg, SPM, 0, 0, 8, 0, 0, 0, 0, 1, mvd))       # reg[8,9] = SPM[gr[1],gr[1]+1]
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))
# Now can issue another SPM access
f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 4, 0, 0, 20, 0, mvd))      # SPM[gr[4],gr[4]+1] = reg[20,21]
```

### Pattern 4: Systolic Data Pass-Through

```python
# Receive data, process, send to next PE
f.write(data_movement_instruction(reg, in_port, 0, 0, 11, 0, 0, 0, 0, 0, mv))   # reg[11] = in_port
f.write(data_movement_instruction(out_port, reg, 0, 0, 0, 0, 0, 0, 11, 0, mv))  # out_port = reg[11]
```

### Pattern 5: Conditional Execution with Early Exit

```python
# if (gr[1] < 0) goto SKIP
f.write(data_movement_instruction(0, 0, 0, 0, SKIP_OFFSET, 0, 1, 0, 1, 0, blt)) # blt gr[1], gr[0], SKIP
f.write(data_movement_instruction(0, 0, 0, 0, SKIP_OFFSET, 0, 1, 0, 1, 0, blt))
# ... code that executes if gr[1] >= 0 ...
# SKIP:
```

### Pattern 6: Controller Dispatching Work to PEs

```python
# Controller main loop
# MAIN_LOOP:
f.write(data_movement_instruction(0, 0, 0, 0, PE_WORK_START, 0, 0, 0, 0, 0, set_PC))  # Start PEs
f.write(data_movement_instruction(gr, gr, 0, 0, 0, 0, 0, 0, 1, 13, bne))               # Wait for completion
# Process results, prepare next iteration...
f.write(data_movement_instruction(0, 0, 0, 0, -N, 0, 1, 0, iter, limit, blt))         # Loop if more work
# End
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                 # Terminate
```

### Pattern 7: PE Initialization Sequence

```python
# PE startup: set sync flag, initialize registers, halt for controller
f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))           # gr[10] = 1 (ready)
f.write(data_movement_instruction(gr, 0, 0, 0, 0, 0, 0, 0, 0, 0, si))            # gr[0] = 0 (constant zero)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))           # Wait for work
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))
```

---

## Scratchpad Memory Configuration

### Changing the Scratchpad Bank Size

The scratchpad memory size is parameterized but requires coordinated changes across multiple files. To change the bank size (currently 1024 words per bank), you must update the following parameters:

**1. Update System Constants (sys_def.h)**
- `SPM_BANK_SIZE` - Words per bank (e.g., 1024)
- `SPM_ADDR_NUM` - Total words = `SPM_BANK_SIZE * 4` (e.g., 4096 for 4 PEs)
- `ADDR_LEN` - Address bits = `log2(SPM_ADDR_NUM)` (e.g., 12 bits for 4096 addresses)
- `PATTERN_START` - Start address for pattern DNA sequence storage
- `TEXT_START` - Start address for text DNA sequence storage

**2. Update Memory Layout (wfa_instruction_generator.py)**
- `BANK_SIZE` - Must match `SPM_BANK_SIZE` from sys_def.h
- `BLOCK_1_START` - Offset to second memory block = `MEM_BLOCK_SIZE*7 + PADDING_SIZE + 2`
- `PATTERN_START` - Must match sys_def.h value = `BLOCK_1_START + MEM_BLOCK_SIZE*7 + PADDING_SIZE + 2`

The following are automatically derived from the above:
- `SEQ_LEN_ALLOC` - Available space for sequences = `(BANK_SIZE - PATTERN_START) // 2`
- `TEXT_START` - Text start = `PATTERN_START + SEQ_LEN_ALLOC`
- `SWIZZLED_PATTERN_START` - Swizzled address for pattern (for mvi instruction)
- `SWIZZLED_TEXT_START` - Swizzled address for text (for mvi instruction)

**3. Update Magic Instruction Constants (pe_array.cpp)**
- `PADDING_SIZE` - Padding section size = 30 (words, adjustable)
- `EXTRA_O_LOAD_ADDR` - Padding section offset = `7*MEM_BLOCK_SIZE` (fixed at 224, independent of PADDING_SIZE)
- `BLOCK_1_START` - Must match Python value = `MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE`

### Memory Block Structure

Each memory block in the WFA algorithm contains 7 core sections of `MEM_BLOCK_SIZE` words (32 words each) plus a PADDING section:

**Block Layout (254 words + 2-word gap):**
- Section 0: Open (O) wavefront values - 32 words
- Section 1: Match (M) input values - 32 words
- Section 2: Insertion (I) input values - 32 words
- Section 3: Deletion (D) input values - 32 words
- Section 4: Match (M) output values - 32 words
- Section 5: Deletion (D) output values - 32 words
- Section 6: Insertion (I) output values - 32 words
- PADDING (reserved space) - 30 words
- 2-word gap - reserved space

**Current Configuration (BANK_SIZE = 1024):**
- Block 0: 254 words (7×32 + 30 padding) + 2 words (gap) = 256 words total
- Block 1: 254 words (7×32 + 30 padding) + 2 words (gap) = 256 words total
- Total blocks: 512 words
- Pattern region: 256 words (addresses 512-767)
- Text region: 256 words (addresses 768-1023)
- Total per bank: 512 + 256 + 256 = 1024 words ✓

### Critical Constraints

When changing scratchpad size, ensure:
1. `PATTERN_START + 2*SEQ_LEN_ALLOC ≤ BANK_SIZE` - Pattern and text sequences must fit
2. `SPM_ADDR_NUM = SPM_BANK_SIZE * 4` - Total addressable space (4 PE banks)
3. `ADDR_LEN = log2(SPM_ADDR_NUM)` - Affects address swizzling in mvi instruction
4. All constants must be synchronized across sys_def.h, wfa_instruction_generator.py, and pe_array.cpp

### Example: Modifying PADDING_SIZE

To change PADDING_SIZE from 30 to 64 words (to add more reserved space):
1. In pe_array.cpp: Change `constexpr int PADDING_SIZE = 64;`
2. In wfa_instruction_generator.py: Change `PADDING_SIZE = 64`
3. Recalculate BLOCK_1_START: `32*7 + 2 + 64 = 290`
4. Recalculate PATTERN_START: `290 + 32*7 + 2 + 64 = 580`
5. Update sys_def.h: PATTERN_START = 580
6. Verify: With BANK_SIZE=1024, SEQ_LEN_ALLOC = (1024-580)//2 = 222, which leaves room for pattern (222 words) and text (222 words) each

**Note:** The formula-based approach (`MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE`) enables this single-point-of-change capability. Changing PADDING_SIZE only requires editing the constant in two files; dependent values recalculate automatically.

---

## Appendix: Quick Reference

### Opcode Numbers
```python
add=0, sub=1, addi=2, si=4, mv=5, bne=8, beq=9, bge=10, blt=11,
jump=12, set_PC=13, none=14, halt=15, shifti_r=16, shifti_l=17,
ANDI=18, mvd=19, subi=20, mvi=21, mvdq=22, mvdqi=23
```

### Source/Destination Numbers
```python
reg=0, gr=1, SPM=2, comp_ib=3, ctrl_ib=4, in_buf=5, out_buf=6,
in_port=7, in_instr=8, out_port=9, out_instr=10, fifo=[11,12,13,14], S2=15
```

### Key Constants (from sys_def.h)
```c
SPM_BANK_SIZE = 1024
SPM_ADDR_NUM = 4096
SPM_ACCESS_LATENCY = 2
SPM_BANDWIDTH = 2
ADDR_REGISTER_NUM = 16    // gr[0..15]
REGFILE_ADDR_NUM = 32     // reg[0..31]
PATTERN_START = 512       // Derived: BLOCK_1_START + 7*32 + 2 + PADDING_SIZE = 256 + 224 + 2 + 30
TEXT_START = 768          // Derived: PATTERN_START + SEQ_LEN_ALLOC = 512 + 256
ADDR_LEN = 12             // For address swizzling (log2(4096))
```

**Memory Block Constants (from wfa_instruction_generator.py):**
```python
PADDING_SIZE = 30         // Adjustable padding per block (enables single-point-of-change)
BLOCK_1_START = 256       // = MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE
PATTERN_START = 512       // = BLOCK_1_START + MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE
SEQ_LEN_ALLOC = 256       // = (BANK_SIZE - PATTERN_START) // 2
```
