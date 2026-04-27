# GenDP ISA and Programming Manual

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Execution Model](#execution-model)
3. [Control Instruction Format](#control-instruction-format)
4. [Source and Destination Codes](#source-and-destination-codes)
5. [Opcode Reference](#opcode-reference)
6. [Compute Instructions](#compute-instructions)
7. [VLIW Slot Restrictions](#vliw-slot-restrictions)
8. [Scratchpad Memory (SPM)](#scratchpad-memory-spm)
9. [S2 Memory and Controller LSQ](#s2-memory-and-controller-lsq)
10. [Synchronization](#synchronization)
11. [Programming Patterns](#programming-patterns)

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
                  (32768 addresses)
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
| 4    | Controller SPM (S1C)  | `ctrl_ib`/`s1c` | Reclaimed slot — controller-local scratchpad (S1C, 8192 words). `ctrl_ib` is the legacy alias; new code uses `s1c`. |
| 5    | Input Buffer          | `in_buf`     | External input data buffer               |
| 6    | Output Buffer         | `out_buf`    | External output data buffer              |
| 7    | Input Port            | `in_port`    | Systolic input from previous PE          |
| 8    | Input Instruction / gr low  | `in_instr` / `gr_lo` | Same code — context determines meaning (see note)  |
| 9    | Output Port           | `out_port`   | Systolic output to next PE               |
| 10   | Output Instruction / gr high | `out_instr` / `gr_hi` | Same code — context determines meaning (see note) |
| 11-14| FIFO 0-3              | `fifo[0-3]`  | FIFO queues for data buffering           |
| 15   | S2 Buffer             | `S2`         | Controller-local buffer                  |

**`gr_lo`/`gr_hi` — half-register addressing (code 8 / 10)**: `gr` entries
are 32-bit. Ops that want only the low or high 16 bits address that half
with `gr_lo` (8) or `gr_hi` (10). These codes are reused (they overlap
legacy `in_instr` / `out_instr`); the simulator dispatches on the dest
position and opcode, so there is no ambiguity in a well-formed stream.
Arithmetic destinations, `si`, and `set_8` can target `gr`, `gr_lo`, or
`gr_hi`. A write to `gr_lo` leaves the high 16 bits untouched (and vice
versa). Reading from `gr_lo`/`gr_hi` returns the sign-extended 16-bit
half. This is how GSSW and the new `set_8` / `slli` opcodes pack two
sub-fields into a single gr entry (e.g. `gr[1].lo = n`,
`gr[1].hi = numNodes`).

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
| 2    | SPM      | ✓†   | ✓†    | †Controller `mv`/`si` direct access (no latency) |
| 3    | comp_ib  | ✓    | -     | Load instructions to distribute to PEs         |
| 4    | ctrl_ib  | -    | -     | Not supported                                   |
| 5    | in_buf   | ✓    | -     | Load from external input                        |
| 6    | out_buf  | -    | ✓     | Valid for arithmetic ops                        |
| 7    | in_port  | ✓    | -     | Receive from PE[3]                              |
| 8    | in_instr | -    | -     | PE only                                         |
| 9    | out_port | -    | ✓     | Valid for arithmetic ops                        |
| 10   | out_instr| -    | ✓†    | †Move ops only (`mv`, `si`); crashes on arith   |
| 11-14| fifo     | ✓    | ✓     | Pop on load, push on store                      |
| 15   | S2       | ✓‡   | ✓‡    | ‡Controller `mv`/`si` and block ops (`mvdq`/`mvdqi`) |

**Controller Arithmetic Destination Restriction**: Arithmetic operations (`add`, `sub`, `addi`, `subi`, `shifti_*`, `andi`, `mul`) on the controller can only write to `gr` (1), `out_buf` (6), or `out_port` (9). Using other destinations (e.g., `out_instr`, `fifo`) will crash the simulator. Move operations (`mv`, `si`) have broader destination support.

**`mul` slot restriction**: The multiply unit lives in only one VLIW lane (slot 0 by convention). Encoding `mul` on slot 1 is a structural hazard, similar to `mvdq+mvdq`. Pair a `mul` with a non-`mul` op (e.g. `mv`, `si`, `addi`, NOP) on the other slot.

**Note on out_instr (code 10) for Controller**: When the controller loads from `comp_ib`, the instruction is stored in an internal buffer (`PE_instruction`). Specifying `out_instr` as the destination in a `mv` operation causes the store function to do nothing, but the instruction is still transferred to PEs via the internal buffer. This is the mechanism for distributing compute instructions.

**Note on SPM (code 2) for Controller**: Controller `mv`/`si` to SPM uses direct buffer reads/writes (no event latency), except for SPM↔S2 transfers which route through the LSQ. PE SPM access remains evented and latency-modeled.

**Note on S2 (code 15) for Controller**: The S2 buffer is accessible via controller `mv`/`si` for single entries and via `mvdq`/`mvdqi` for 8-word block operations. Other operations do not support S2.

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
| 3    | Set 8-bit Broadcast   | `set_8`    | reg[rd] = (imm8 & 0xFF) * 0x01010101         |
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
| 24   | Barrier               | `barrier`  | Controller: stall until LSQ drained          |
| 25   | Move 2-bit Extract    | `mvi2`     | Load 2-bit field from packed SPM word        |
| 26   | Call                  | `call`     | ras = PC+1; PC = target (absolute)           |
| 27   | Return                | `ret`      | PC = ras                                     |
| 28   | Return Not Equal      | `retne`    | if (op1 != op2) PC = ras                     |
| 29   | Multiply              | `mul`      | gr[rd] = gr[rs2] * (immBar_1 ? gr[imm_1] : imm)  |

### Import Statement
```python
from opcodes import (add, sub, addi, set_8, si, mv, bne, beq, bge, blt, jump,
    set_PC, none, halt, shifti_r, shifti_l, ANDI, mvd, subi, mvi, mvdq,
    mvdqi, barrier, mvi2, call, ret, retne, mul)
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

#### `mul` (opcode 29) - Multiply

**Summary**: Multiplies a register by either an immediate or another register.
The `reg_immBar_1` flag selects between the two modes, so a single opcode
serves both `mul gr,imm` and `mul gr,gr`. Slot-0 only by convention.

**Syntax**:
```
mul gr[rd], imm,    gr[rs2]   # immBar_1=0: gr[rd] = imm * gr[rs2]
mul gr[rd], gr[rs1], gr[rs2]  # immBar_1=1: gr[rd] = gr[rs1] * gr[rs2]
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # gr (1) (PE), or gr/out_buf/out_port (controller)
    src,            # Unused (typically gr)
    0,              # reg_immBar_0: unused
    0,              # reg_auto_increase_0: unused
    rd,             # imm_0: destination register index
    0,              # reg_0: unused
    immBar_1,       # 0: imm_1 is immediate; 1: imm_1 is gr index (rs1)
    0,              # reg_auto_increase_1: unused
    imm_or_rs1,     # imm_1: immediate value OR rs1 register index
    rs2,            # reg_1: source register (always gr)
    mul             # opcode: 29
)
```

**Operand Mapping**:
| Field      | Usage                                                              |
|------------|:-------------------------------------------------------------------|
| `dest`     | PE: `gr`. Controller: `gr`, `out_buf`, `out_port`.                 |
| `imm_0`    | `rd` — destination gr index                                        |
| `immBar_1` | 0 → `imm_1` is a 16-bit signed immediate. 1 → `imm_1` is gr index. |
| `imm_1`    | Immediate multiplier OR source-A gr index, per `immBar_1`.         |
| `reg_1`    | `rs2` — source-B gr index (always a register)                      |

**Example**:
```python
# gr[2] = 3 * gr[11]  (multiply by immediate)
f.write(data_movement_instruction(gr, gr, 0, 0, 2, 0, 0, 0, 3, 11, mul))

# gr[5] = gr[7] * gr[11]  (multiply two registers; immBar_1=1, imm_1=7)
f.write(data_movement_instruction(gr, gr, 0, 0, 5, 0, 1, 0, 7, 11, mul))
```

**Notes**:
- 32-bit signed multiply, low 32 bits of the product (wraps like `add`).
- Slot 0 only — pair with a non-`mul` op on the other slot. Two `mul`s in
  one VLIW bundle is a structural hazard.
- Latency = 1 cycle, same as `add`/`addi`. Standard RAW rules apply.

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
| `dest`             | PE: `gr`, `reg`, `SPM`, `comp_ib`, `out_port`, `out_instr`. Controller: `gr`, `SPM`, `S2`, `out_buf`, `out_port`, `fifo` |
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

**Summary**: Moves eight consecutive words (256 bits) between SPM and the controller S2 buffer
through the controller LSQ, modeling bank conflicts and S2 latency. Controller-only.

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
// N_SWIZZLE_BITS = 2, ADDR_LEN = 15
int lower_bits = addr & 0x3;           // Extract bits [1:0]
int upper_bits = addr >> 2;            // Extract bits [14:2]
int swizzled = upper_bits | (lower_bits << 13);  // Recombine
```

**Physical Addressing**: Unlike `mv` and `mvd`, `mvi` uses **physical addressing** (not virtual) after applying the swizzle. This means the swizzled address directly indexes into the global SPM space without the per-PE bank offset.

**Use Case**: When data is distributed across PE bank groups in round-robin fashion, `mvi` allows any PE to access any element by index:
- Address 0 → physical 0 (bank group 0)
- Address 1 → physical 8192 (bank group 1)
- Address 2 → physical 16384 (bank group 2)
- Address 3 → physical 24576 (bank group 3)
Within each bank group, the low-order interleaving selects the bank by `(phys_addr >> 1) & 1`.

**Examples**:
```python
# Load pattern character at index gr[2] (interleaved across PEs)
f.write(data_movement_instruction(gr, SPM, 0, 0, 3, 0, 0, 0, SWIZZLED_PATTERN_START, 2, mvi))

# Load text character at index gr[1]
f.write(data_movement_instruction(gr, SPM, 0, 0, 5, 0, 0, 0, SWIZZLED_TEXT_START, 1, mvi))
```

**Constraint**: Either `src` or `dest` must be `SPM` (2).

---

#### `mvi2` (opcode 25) - Move with 2-bit Extract

**Summary**: Loads a 32-bit SPM word and returns the 2-bit field at a
specific bit position within that word. Intended for packed 2-bit
sequence data (e.g. DNA bases encoded as 2 bits each, 16 bases per
word).

**Syntax**:
```
mvi2 dest[addr0], SPM[bp_addr]
```
The source address is a *bit-pair* index: word index = `bp_addr >> 4`;
byte-pair offset within the word = `bp_addr & 0xF` (values 0..15,
shifted by `offset * 2` bits).

**Behavior**:
1. Apply `apply_address_swizzle(word_addr)` — physical addressing, like
   `mvi`.
2. Issue a single-word SPM read. The PE's receive path masks the
   result with `((word >> (bp_offset * 2)) & 0x3)` before writing it
   to the destination (`reg`, `gr`, `gr_lo`, or `gr_hi`).

**Constraint**: `src` must be `SPM`. Has SPM latency (2 cycles) just
like `mv`/`mvd`.

**Example**:
```python
# gr[13] = 2-bit extract of seq[col] at bit-pair address gr[7]+gr[2].lo
f.write(data_movement_instruction(gr, SPM, 1, 0, 13, 0, 1, 0, 7, 2, mvi2))
```

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

#### `set_8` (opcode 3) - Broadcast 8-bit Immediate

**Summary**: Materializes a 4-lane byte constant in one instruction by
broadcasting an 8-bit immediate across a 32-bit register. Added for
GSSW-style lowering where SIMD kernels need constants like `vBias`
(0x04040404), `vGapO` (0x06060606), etc.

**Syntax**:
```
set_8 reg[rd], imm8            # reg[rd] = (imm8 & 0xFF) * 0x01010101
set_8 gr[rd], imm8             # gr[rd] writes are supported too
set_8 gr_lo[rd], imm8          # writes only the low 16 bits
```

**Encoding**:
```python
data_movement_instruction(
    dest,           # reg (0), gr (1), gr_lo (8), or gr_hi (10)
    0,              # src unused
    0, 0,           # flags unused
    rd,             # imm_0: destination register index
    0,              # reg_0 unused
    0, 0,           # flags unused
    imm8,           # imm_1: 8-bit constant (low byte used)
    0,              # reg_1 unused
    set_8           # opcode: 3
)
```

**Behavior**:
- `dest == reg`: writes a full 32-bit lane replica to `reg[rd]`.
- `dest == gr`: writes to the addressing register file via
  `set_output_dest`.
- `dest == gr_lo` / `gr_hi`: writes only the corresponding 16-bit half.

**Example**:
```python
# vBias = 0x04040404  (4 lanes of 4)
f.write(data_movement_instruction(reg, 0, 0, 0, 0, 0, 0, 0, 4, 0, set_8))
# paired with another set_8 for reg[1] (the high word of an 8-lane pair):
f.write(data_movement_instruction(reg, 0, 0, 0, 1, 0, 0, 0, 4, 0, set_8))
```

---

#### `call` (opcode 26) - Function Call

Single-level subroutine call. Saves the return address (PC+1) in the
`ras` (return address save) register, then jumps to the target address.

**Syntax**:
```
call target
```

**Encoding**:
```python
data_movement_instruction(
    0, 0,       # dest, src: unused
    0, 0,       # flags: unused
    target,     # imm_0: absolute jump target (sign-extended)
    0, 0, 0,    # unused
    0, 0,       # unused
    call        # opcode: 26
)
```

**Behavior**:
1. `ras = PC + 1` (save return address)
2. `PC = target` (jump to subroutine)

**Lockstep constraint**: Both VLIW slots must contain `call` with the
same target. Never pair `call` with another opcode.

**Limitations**: Single-level only — nested calls overwrite `ras`.

**Example**:
```python
# Call subroutine at address FUNC_START
f.write(data_movement_instruction(
    0, 0, 0, 0, FUNC_START, 0, 0, 0, 0, 0, call))
f.write(data_movement_instruction(
    0, 0, 0, 0, FUNC_START, 0, 0, 0, 0, 0, call))
```

#### `ret` (opcode 27) - Return from Call

Returns to the address saved in `ras` by a prior `call`.

**Syntax**:
```
ret
```

**Encoding**:
```python
data_movement_instruction(
    0, 0,       # dest, src: unused
    0, 0,       # flags: unused
    0, 0, 0, 0, # unused
    0, 0,       # unused
    ret         # opcode: 27
)
```

**Behavior**:
1. `PC = ras` (jump to saved return address)

**Lockstep constraint**: Both VLIW slots must contain `ret`.
Never pair `ret` with another opcode.

**Example**:
```python
# Return from subroutine
f.write(data_movement_instruction(
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ret))
f.write(data_movement_instruction(
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ret))
```

---

#### `retne` (opcode 28) - Conditional Return

**Summary**: Returns (jumps to `ras`) if two values are not equal;
otherwise falls through (PC++). Combines a comparison and a return
into one instruction, saving a branch + ret pair.

**Syntax**:
```
retne imm_val, gr[rs2]       # if (imm_val != gr[rs2]) PC = ras
retne gr[rs1], gr[rs2]       # if (gr[rs1] != gr[rs2]) PC = ras
```

**Encoding** (same fields as `bne`, opcode 28 instead of 8):
```python
data_movement_instruction(
    0, 0,
    0, 0,
    0, 0,              # imm_0 / reg_0: unused (no branch offset)
    reg_immBar_1,      # 0: operand1 is immediate, 1: gr[imm_1]
    0,
    operand1,
    rs2,
    retne              # opcode: 28
)
```

**Lockstep constraint**: Both VLIW slots must emit `retne` with the
same operands. The controller and PE decode paths both reject mixed
slot-0/slot-1 pairings for call/ret/retne.

---

## Compute Instructions

The compute trace is separate from the control trace (PE only) and runs
its own 64-bit VLIW encoded instructions. The array controller does
not execute compute instructions; instead it loads them into the
`comp_ib` buffer and dispatches them to PEs.

### Compute Instruction Format

```
Bit:  63 59 58 54 53 49 48 42 41 35 34 28 27 21 20 14 13  7 6   0
     ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
     │op[0]│op[1]│op[2]│in[0]│in[1]│in[2]│in[3]│in[4]│in[5]│ out │
     │ 5b  │ 5b  │ 5b  │ 7b  │ 7b  │ 7b  │ 7b  │ 7b  │ 7b  │ 7b  │
     └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

- `op[0]` drives the 4-input ALU (inputs 0..3).
- `op[1]` drives the 2-input ALU (inputs 4..5).
- `op[2]` combines the two sub-ALU outputs into the final write.
- Each input / output address is 7 bits (128 slots). Two ALU slots run
  in parallel on each cycle (slot 0 and slot 1); each slot reads its
  own 6 inputs and produces one 32-bit output.

### Compute Address Space (7-bit input/output fields)

| Range   | Target                                        |
|:--------|:----------------------------------------------|
| 0-31    | `reg[0..31]` (compute register file, 32-bit)  |
| 32-47   | `gr[0..15]` (full 32-bit)                     |
| 48-63   | `gr[0..15]` low 16 bits (`gr_lo`)             |
| 64-79   | `gr[0..15]` high 16 bits (`gr_hi`)            |
| ≥ 80    | reserved                                      |

Writes to a gr half-register leave the other half untouched.

### Scalar vs SIMD Mode

Compute instructions are dispatched either in **scalar** mode (ALU
operates on 32-bit inputs) or **SIMD** mode (each input treated as 4
packed `uint8` lanes). The mode is carried on the control slot that
precedes the compute dispatch.

**SIMD + `gr` source → scalar fallback**: if SIMD mode is active AND
any of the 6 compute inputs references a `gr` address (>= 32), that
compute slot silently falls back to the scalar ALU. This prevents
32-bit gr counters (multiplies, shifts, loop indices) from being
mis-interpreted as 4 byte lanes. The only documented exception is
`COMP_GT`, which legitimately takes two SIMD `reg` inputs and writes
a scalar 0/1 to `gr`; it stays on the SIMD path regardless.

### Compute Opcode Reference

Values defined in `sys_def.h` and mirrored in `scripts/opcodes.py`.
Columns mark whether an opcode is valid in scalar or SIMD mode.

| Code | Name          | Scalar | SIMD | Description                                         |
|:----:|:--------------|:------:|:----:|:----------------------------------------------------|
| 0    | ADDITION      | ✓      | ✓    | `a + b`. Scalar wraps 32-bit; SIMD wraps int8 per lane. |
| 1    | SUBTRACTION   | ✓      | ✓    | `a - b`.                                             |
| 2    | MULTIPLICATION| ✓      | —    | Scalar only.                                         |
| 3    | **SLLI_64**   | ✓      | —    | Paired 64-bit unsigned left shift of `(reg[r], reg[r+1])`. Must be emitted in **both** slots with the same `imm` and operands; slot 0 writes the new low half, slot 1 writes the new high half. The shift amount rides on `input[0]` via the immediate-opcode path. Reclaims former `CARRY` slot. |
| 4    | BORROW        | ✓      | —    | `(a < b) ? 1 : 0`.                                   |
| 5    | MAXIMUM       | ✓      | ✓    | Signed max. SIMD uses signed int8 comparison.        |
| 6    | MINIMUM       | ✓      | ✓    | Signed min.                                          |
| 7    | LEFT_SHIFT    | ✓      | —    | `a << 16` (fixed amount).                            |
| 8    | RIGHT_SHIFT   | ✓      | —    | `a >> 16` (fixed amount).                            |
| 9    | COPY          | ✓      | ✓    | `out = a`.                                           |
| 10   | MATCH_SCORE   | ✓      | ✓    | Kernel-specific scoring LUT (bsw/poa/phmm).          |
| 11   | LOG2_LUT      | ✓      | —    | PairHMM log2 lookup.                                 |
| 12   | LOG_SUM_LUT   | ✓      | —    | PairHMM log-sum lookup.                              |
| 13   | COMP_LARGER   | ✓      | ✓    | `(a > b) ? c : d` (4-input select).                  |
| 14   | COMP_EQUAL    | ✓      | ✓    | `(a == b) ? c : d`.                                  |
| 15   | INVALID       | ✓      | ✓    | Always 0 (nop fill).                                 |
| 16   | HALT          | ✓      | ✓    | Compute-trace halt; compute PC does not advance.     |
| 17   | BWISE_OR      | ✓      | ✓    | `a | b`.                                             |
| 18   | BWISE_AND     | ✓      | ✓    | `a & b`.                                             |
| 19   | BWISE_NOT     | ✓      | ✓    | `~a`.                                                |
| 20   | BWISE_XOR     | ✓      | ✓    | `a ^ b`.                                             |
| 21   | LSHIFT_1      | ✓      | —    | `a << 1`.                                            |
| 22   | RSHIFT_WORD   | ✓      | —    | `a >> 31` (extract sign).                            |
| 23   | ADD_I         | ✓      | —    | Immediate add: `input[0]` field is the literal addend. |
| 24   | COPY_I        | ✓      | —    | Immediate copy.                                      |
| 25   | POPCOUNT      | ✓      | ✓    | Per-lane popcount.                                   |
| 26   | CMP_2INP      | ✓      | —    | Used by GBV; compare and produce mask.               |
| 27   | **ADDS_EPU8** | —      | ✓    | Saturating unsigned 8-bit add, per lane (GSSW lowering). |
| 28   | **SUBS_EPU8** | —      | ✓    | Saturating unsigned 8-bit sub, per lane.             |
| 29   | **MAX_EPU8**  | —      | ✓    | Unsigned 8-bit max, per lane.                        |
| 30   | **MAX_REDUCE**| —      | ✓    | Horizontal max of the 4 input bytes, returned in byte 0 of the destination (zero-extended). |
| 31   | **COMP_GT**   | ✓      | ✓    | Scalar: `(a > b) ? 1 : 0`. SIMD: any-lane unsigned gt → 0/1 in byte 0. Typically writes to `gr` (destination-address >= 32); still uses the SIMD ALU even then. |

**Python import**:
```python
from opcodes import (
    ADD, SUBTRACTION, MULTIPLICATION, SLLI_64, BORROW, MAXIMUM, MINIMUM,
    LEFT_SHIFT, RIGHT_SHIFT, COPY, MATCH_SCORE, LOG2_LUT, LOG_SUM_LUT,
    COMP_LARGER, COMP_EQUAL, INVALID, HALT, BWISE_OR, BWISE_AND,
    BWISE_NOT, BWISE_XOR, LSHIFT_1, RSHIFT_WORD, ADD_I, COPY_I,
    POPCOUNT, CMP_2INP, ADDS_EPU8, SUBS_EPU8, MAX_EPU8, MAX_REDUCE,
    COMP_GT)
```

### Immediate-Opcode Path

A few opcodes reinterpret one of their input-address fields as a
literal immediate:

| Opcode   | Immediate field  | Effective ALU op    |
|:---------|:-----------------|:--------------------|
| `ADD_I`  | `input[0]`       | `ADDITION`          |
| `COPY_I` | `input[0]`       | `COPY`              |
| `SLLI_64`| `input[0]` (6-bit)| paired 64-bit shift|

When the decoder sees one of these opcodes in `op[0]`/`op[1]`, the
corresponding cu_input is replaced by the raw 7-bit address field
before dispatch.

---

## VLIW Slot Restrictions

Both control slots execute **concurrently** against pre-cycle register
state (no data forwarding between slots). On top of data hazards, the
slots have asymmetric structural constraints.

### Control Trace

- **Slot 1 (second-written)** cannot hold: `magic`, any branch, `jump`,
  `halt`, `set_PC`, `barrier`, or `si`/`mv` to `in_buf`/`out_buf`/
  `fifo` IO destinations.
- **Slot 0 (first-written)** double-executes via `decode_output` unless
  the opcode is `add`, `sub`, `addi`, `set_8`, non-IO `si`, non-IO
  `mv`, or `none`.
- **Paired-only opcodes**: `call`, `ret`, `retne` must be in **both**
  slots with identical operands — the controller and PE decoders
  reject mixed-slot pairings.
- **Structural hazards (any pairing)**:
  - `mvdq` + `mvdq`, or `mvdq` + `mv` in the same cycle: illegal.
  - Two SPM accesses to the same bank in the same cycle: illegal.
  - Two arithmetic ops writing the same gr entry (WAW): undefined
    behavior.
- **SIMD flag**: the SIMD bit travels with the slot; cross-slot SIMD
  mismatches are legal but unusual.

### Compute Trace

- Both compute slots run every cycle; `INVALID` or `HALT` as op[0]
  kills that slot for that cycle.
- `SLLI_64` must be emitted on both slots simultaneously with matching
  operands; missing one half leaves the shifted pair half-written.
- Compute writes to `gr`/`gr_lo`/`gr_hi` are routed through the gr
  write ports in `pe.cpp` after the regfile write; avoid pairing two
  compute slots that write the same gr entry.

---

## Scratchpad Memory (SPM)

### Overview

The SPM is a shared memory accessible by all PEs. It is organized into 4 bank groups (one per PE),
each split into 2 interleaved banks (8 banks total).

### Parameters

| Parameter           | Value       | Description                        |
|:-------------------|:------------|:----------------------------------|
| Total Size         | 32768 words | Total addressable words            |
| Bank Group Size    | 8192 words  | Words per PE bank group            |
| Bank Size          | 4096 words  | Words per interleaved bank         |
| Banks              | 8           | 2 banks per group                  |
| Word Size          | 32 bits     | Single word                        |
| Double Word        | 64 bits     | Two consecutive words              |
| Access Latency     | 2 cycles    | Cycles from request to data        |
| Ports per PE       | 1           | Read OR write, not both            |
| Line Size          | 2 words     | Words per line (double-word access) |

### Access Constraints

**Critical Rules**:
1. **One access per port per cycle**: Each PE has one port; cannot load
   AND store in the same cycle.
2. **Bank-level pipelining**: Each bank pipeline holds
   `SPM_ACCESS_LATENCY` (= 2) in-flight requests. The same bank may be
   issued to on back-to-back cycles; a *third* overlapping request
   stalls the issuer (`BankConflictStalls`). Individual request latency
   is still preserved — the consumer must wait `SPM_ACCESS_LATENCY`
   cycles from the cycle the load was issued before reading the result.
3. **Same-cycle same-bank collision still illegal**: two accesses to
   the same bank in the same cycle (PE+PE, PE+LSQ, etc.) stall, they
   don't coalesce.
4. **SPM load destination constraint**: When loading from SPM the
   destination must be `reg`, `gr` (incl. `gr_lo`/`gr_hi`), or
   `out_port`. Other destinations are not supported.
5. **`mvd` alignment**: double-word SPM accesses require an
   even-aligned address (`addr & 1 == 0`). Misaligned `mvd` asserts.

**Illegal patterns (same-cycle conflict)**:
```python
# ILLEGAL: load and store in same cycle (both touch the PE's SPM port)
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))  # load
f.write(data_movement_instruction(SPM, reg, 0, 0, 0, 2, 0, 0, 5, 0, mv))  # store
```

**Legal pipelined pattern** (both requests from the same PE hit
different issue cycles, neither consumer reads too early):
```python
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 0, 1, mv))  # load A, cycle 0
f.write(data_movement_instruction(reg, SPM, 0, 0, 2, 0, 0, 0, 1, 2, mv))  # load B, cycle 1 (OK — pipelined)
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))    # A ready on cycle 2
# use A here — reg[0] is valid
f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))    # B ready on cycle 3
# use B here — reg[2] is valid
```
Using `B` one cycle early still breaks — the per-request latency must
be respected even though the pipeline allows two in flight.

### Addressing Modes

#### Virtual Addressing (Default)

Each PE sees its own "virtual" address space. Physical address = virtual address + PE_ID * BANK_GROUP_SIZE.

```
PE[0]: virtual 0-8191  → physical 0-8191
PE[1]: virtual 0-8191  → physical 8192-16383
PE[2]: virtual 0-8191  → physical 16384-24575
PE[3]: virtual 0-8191  → physical 24576-32767
```

**Accessing Own Bank Group**:
```python
# PE accesses its own bank group with addresses 0-8191
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 32, 0, mv))  # SPM[32] in own bank group
```

**Accessing Other Bank Groups** (negative or >1023 addresses):
```python
# PE[0] accessing PE[1]'s data at offset 32:
# Virtual address = 32 + 8192 = 8224
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, 8224, 0, mv))

# PE[1] accessing PE[0]'s data at offset 32:
# Virtual address = 32 - 8192 = -8160
f.write(data_movement_instruction(reg, SPM, 0, 0, 0, 0, 0, 0, -8160, 0, mv))
```

#### Interleaved Addressing (`mvi`)

For data distributed round-robin across PEs, use `mvi` which swizzles addresses:

```
Index 0 → PE[0] bank group, physical 0
Index 1 → PE[1] bank group, physical 8192
Index 2 → PE[2] bank group, physical 16384
Index 3 → PE[3] bank group, physical 24576
Index 4 → PE[0] bank group, physical 1
Index 5 → PE[1] bank group, physical 8193
...
```

Each bank group is internally interleaved into two banks using bit 1 of the physical address.
For example, physical 0 → bank 0, physical 1 → bank 1, physical 8192 → bank 2, physical 8193 → bank 3.

**Use Case**: Sequence data where character `i` is stored in `PE[i % 4]` bank group.

```python
# Access character at logical index gr[2] (distributed across PEs)
f.write(data_movement_instruction(gr, SPM, 0, 0, 3, 0, 0, 0, SWIZZLED_START, 2, mvi))
```

### Line-Width Semantics

The SPM's minimum addressable unit is a **line** of 64 bits
(2 consecutive 32-bit words). All PE SPM accesses operate on
full lines internally:

| Concept | Value | Description |
|:--------|:------|:------------|
| Line width | 64 bits | 2 × 32-bit words |
| Line address | `(addr >> 1) << 1` | Even-aligned start |
| Word select | `addr & 1` | 0 = low word, 1 = high word |

**Read behavior**: A single-word `mv` from SPM always reads the
full 2-word line, then selects the requested word by `addr & 1`.

**Write behavior**: A single-word `mv` to SPM writes only the
target word within the line (determined by `addr & 1`). A
double-word `mvd` writes both words.

**Alignment requirement**: `mvd` (double-word move) requires the
SPM address to be even (line-aligned, `addr % 2 == 0`).
Misaligned `mvd` addresses will trigger an assertion failure.
The controller's `mvdq` does NOT have this restriction — it
decomposes misaligned transfers into a mix of single and double
operations internally.

---

## S2 Memory and Controller LSQ

### S2 Memory

S2 is a large on-chip buffer (1 MB, int-addressable) used by the
controller for staging data between iterations. It sits between
DDR and SPM in the memory hierarchy.

| Parameter | Value |
|:----------|:------|
| Size | 1 MB (262144 ints) |
| Banks | 4 |
| Bank formula | `(addr >> 1) % 4` |
| Read latency | 6 cycles (pipelined, used by LSQ) |
| Write latency | 3 cycles (pipelined) |

### Controller Load/Store Queue (LSQ)

All controller `mv`/`mvdq` between SPM and S2 are routed through
the LSQ, which models bank conflicts and memory latency.

**S2 → SPM direction**: Creates S2 read entries and SPM write
entries. S2 reads are pipelined (6-cycle latency). When a read
completes, `dataReadyFromS2` fills matching SPM write entries
via line-based address matching. SPM writes drain when data is
ready, respecting PE bank priority.

**SPM → S2 direction**: Creates SPM read entries and S2 write
entries. SPM reads check `spmBankBusy` (PE accesses have
priority). When data is ready, `dataReadyFromSpm` fills matching
S2 write entries. S2 writes drain through the S2 write pipeline
(3-cycle latency).

**Buffer size limit**: Each bank queue holds at most
`LSQ_MAX_ENTRIES_PER_BANK` (8) entries. When full, the
controller stalls until entries drain.

**Execution order in pe_array::run() each cycle**:
```
1. process_events()     (SPM tick → PE data delivery)
2. S2 tick              (advance S2 pipelines, send completions to LSQ)
3. decode(slot 1)       (controller: may enqueue to LSQ)
4. PE[0..3] run         (PE execution + systolic)
5. SPM bank arbitration (PE requests have priority)
6. LSQ drain            (issue SPM/S2 ops if banks are free)
7. decode_output(slot 0)
8. gr[13] sync
```

### Barrier Instruction

Opcode 24 (`barrier`). Stalls the controller until the LSQ is
completely empty (all queues and pipelines drained). Used to
ensure memory transfers complete before proceeding. Emit it in
slot 1 (controller slot).

```python
# Insert barrier + nop pair (1 VLIW instruction):
f.write(data_movement_instruction(
    0,0,0,0,0,0,0,0,0,0, barrier))
f.write(data_movement_instruction(
    0,0,0,0,0,0,0,0,0,0, none))
```

### mvdq Handling

Unlike PE `mvd`, the controller `mvdq` supports misaligned
addresses by decomposing transfers internally:

- **Both even**: 4 paired double-word transfers
- **Both odd**: 5 paired transfers (sgl, dbl, dbl, dbl, sgl)
- **Different parity**: standalone reads and writes are
  created separately because the read/write counts differ
  (4 vs 5). One read completion can fill multiple write
  entries via line-based matching in the data-ready callbacks.

### Performance Counters

Printed after each simulation case:

| Counter                   | Description                                           |
|:--------------------------|:------------------------------------------------------|
| `TotalSpmRequests`        | Total PE SPM access requests                          |
| `BankConflictStalls`      | PE stalls from same-cycle SPM bank conflicts          |
| `ForwardableBankConflict` | Bank conflicts where data could have been forwarded (diagnostic) |
| `LsqFullStalls`           | Controller stalls caused by a full LSQ bank queue     |
| `PeHalted`                | Cycles spent in `halt` across all PEs                 |
| `SyncSpinBNEs`            | Controller cycles spent spinning on `gr[13] != 1`     |
| `Fin0DupDiags`            | GWFA-only: duplicate diagonals filtered by FIN0 dedup |

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

### Changing the Scratchpad Bank Group Size

The scratchpad memory is organized into bank groups (per PE). To
change the bank group size (currently 8192 words per group) and
the per-bank size (currently 4096 words per interleaved bank),
you must update the following parameters:

**1. Update System Constants (sys_def.h)**
- `SPM_BANK_GROUP_SIZE` - Words per bank group (e.g., 8192)
- `SPM_BANK_SIZE` - Words per bank (e.g., 4096)
- `SPM_ADDR_NUM` - Total words = `SPM_BANK_GROUP_SIZE * 4` (e.g., 32768 for 4 PEs)
- `ADDR_LEN` - Address bits = `log2(SPM_ADDR_NUM)` (e.g., 15 bits for 32768 addresses)
- `PATTERN_START` - Start address for pattern DNA sequence storage
- `TEXT_START` - Start address for text DNA sequence storage

**2. Update Memory Layout (wfa_instruction_generator.py)**
- `BANK_SIZE` - Must match `SPM_BANK_GROUP_SIZE` from sys_def.h
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

**Current Configuration (BANK_SIZE = 8192):**
- Block 0: 254 words (7×32 + 30 padding) + 2 words (gap) = 256 words total
- Block 1: 254 words (7×32 + 30 padding) + 2 words (gap) = 256 words total
- Total blocks: 512 words
- Pattern region: 3840 words (addresses 512-4351)
- Text region: 3840 words (addresses 4352-8191)
- Total per bank group: 512 + 3840 + 3840 = 8192 words ✓

### Critical Constraints

When changing scratchpad size, ensure:
1. `PATTERN_START + 2*SEQ_LEN_ALLOC ≤ BANK_SIZE` - Pattern and text sequences must fit
2. `SPM_ADDR_NUM = SPM_BANK_GROUP_SIZE * 4` - Total addressable space (4 PE bank groups)
3. `ADDR_LEN = log2(SPM_ADDR_NUM)` - Affects address swizzling in mvi instruction
4. All constants must be synchronized across sys_def.h, wfa_instruction_generator.py, and pe_array.cpp

### Example: Modifying PADDING_SIZE

To change PADDING_SIZE from 30 to 64 words (to add more reserved space):
1. In pe_array.cpp: Change `constexpr int PADDING_SIZE = 64;`
2. In wfa_instruction_generator.py: Change `PADDING_SIZE = 64`
3. Recalculate BLOCK_1_START: `32*7 + 2 + 64 = 290`
4. Recalculate PATTERN_START: `290 + 32*7 + 2 + 64 = 580`
5. Update sys_def.h: PATTERN_START = 580
6. Verify: With BANK_SIZE=8192, SEQ_LEN_ALLOC = (8192-580)//2 = 3806, which leaves room for pattern (3806 words) and text (3806 words) each

**Note:** The formula-based approach (`MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE`) enables this single-point-of-change capability. Changing PADDING_SIZE only requires editing the constant in two files; dependent values recalculate automatically.

---

## Appendix: Quick Reference

### Control Opcode Numbers
```python
add=0, sub=1, addi=2, set_8=3, si=4, mv=5, bne=8, beq=9, bge=10, blt=11,
jump=12, set_PC=13, none=14, halt=15, shifti_r=16, shifti_l=17,
ANDI=18, mvd=19, subi=20, mvi=21, mvdq=22, mvdqi=23,
barrier=24, mvi2=25, call=26, ret=27, retne=28
```

### Compute Opcode Numbers
```python
# Base arithmetic / bitwise
ADD=0, SUBTRACTION=1, MULTIPLICATION=2, SLLI_64=3, BORROW=4,
MAXIMUM=5, MINIMUM=6, LEFT_SHIFT=7, RIGHT_SHIFT=8, COPY=9,
MATCH_SCORE=10, LOG2_LUT=11, LOG_SUM_LUT=12, COMP_LARGER=13,
COMP_EQUAL=14, INVALID=15, HALT=16, BWISE_OR=17, BWISE_AND=18,
BWISE_NOT=19, BWISE_XOR=20, LSHIFT_1=21, RSHIFT_WORD=22,
ADD_I=23, COPY_I=24, POPCOUNT=25, CMP_2INP=26,
# GSSW lowering additions (SIMD unsigned + paired shift + reductions)
ADDS_EPU8=27, SUBS_EPU8=28, MAX_EPU8=29, MAX_REDUCE=30, COMP_GT=31
```

### Source/Destination Numbers
```python
reg=0, gr=1, SPM=2, comp_ib=3,
ctrl_ib=4,      # alias: s1c (controller scratchpad)
in_buf=5, out_buf=6, in_port=7,
in_instr=8,     # alias: gr_lo (low 16 bits of gr)
out_port=9,
out_instr=10,   # alias: gr_hi (high 16 bits of gr)
fifo=[11,12,13,14], S2=15
```

### Compute Address Convention
```
 0..31 = reg[]       48..63 = gr[].lo
32..47 = gr[] (full) 64..79 = gr[].hi
```

### Key Constants (from sys_def.h)
```c
SPM_BANK_GROUP_SIZE = 8192
SPM_BANK_SIZE = 4096
SPM_ADDR_NUM = 32768
SPM_ACCESS_LATENCY = 2
LINE_SIZE = 2
SPM_NUM_BANKS = 8
S2_NUM_BANKS = 4
S2_READ_LATENCY = 6
S2_WRITE_LATENCY = 3
LSQ_MAX_ENTRIES_PER_BANK = 8
ADDR_REGISTER_NUM = 16    // gr[0..15]
REGFILE_ADDR_NUM = 32     // reg[0..31]
PATTERN_START = 512
TEXT_START = 4352
ADDR_LEN = 15             // For address swizzling
```

**Memory Block Constants (from wfa_instruction_generator.py):**
```python
PADDING_SIZE = 30         // Adjustable padding per block (enables single-point-of-change)
BLOCK_1_START = 256       // = MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE
PATTERN_START = 512       // = BLOCK_1_START + MEM_BLOCK_SIZE*7 + 2 + PADDING_SIZE
SEQ_LEN_ALLOC = 3840      // = (BANK_SIZE - PATTERN_START) // 2
```
