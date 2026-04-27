# Plan 3d PE-Side Cross-Magic ABI Extension

Artifact for task `l8` of `isaLikeAllGwfaPlan3dH.md`. Extends the
authoritative Plans 3a/3b/3c controller register ABI into the PE-side
`gr[]` / `reg[]` register files for the five PE magics being lowered in
Plan 3d (PE 19, 20, 21, 22, 23). Committed before any PE magic lowering
per AC-2; any later shared-slot change must land in a separate amendment
commit with mode-1 rerun of every affected prior magic and cluster-gate
rerun if past.

## 1. Scope

This file freezes the cross-magic PE-side `gr[]` / `reg[]` slots that
PE magics 19..23 read or write across magic boundaries within a single
test case, plus the PE 23 `DEDUP_META` register-residency contract per
DEC-1.

References:
- `isaLikeAllGwfaPlan3aH.md` — controller register ABI for sort /
  diag-split / HA path (controller-side).
- `isaLikeAllGwfaPlan3bH.md` — extension for dedup driver + m31 seam.
- `isaLikeAllGwfaPlan3c_ABI.md` — controller-side cross-magic ABI for
  magics 32..39, layout template for this artifact.
- Frozen PE references: PE 8 ABI header at `pe.cpp:719-755`; PE 11 at
  `pe.cpp:1087-1150`; PE 13 ABI header at `pe.cpp:1162-1179`. These
  are NOT modified by Plan 3d.

The PE register file is **physically separate** from the controller
register file. Controller-side `gr[12]/gr[13]` reservations
(BL-20260417-ctrl-sync-gr) and `gr[7..10]` magic-19 scavenge-scope
protections (BL-20260413-gr-clobber) do NOT apply to PE-side `gr[]`.
The single PE-side reservation that DOES carry over: `gr[10]` is the
PE-sync done flag written by the magic envelope at
`scripts/gwfa_instruction_generator.py:666-688` and is RESERVED on the
PE side.

## 2. Pre-existing PE ABI Summary (read-only reference)

PE 8 (frozen — `pe.cpp:719-755`) `gr[]` table:

| Slot   | Half  | Role                          |
|--------|-------|-------------------------------|
| gr[0]  | -     | hardwired 0                   |
| gr[1]  | lo    | i (loop index)                |
| gr[1]  | hi    | tile_n (input diag count)     |
| gr[2]  | -     | scratch                       |
| gr[3]  | lo    | tb_n (B-tile emit count)      |
| gr[3]  | hi    | ta_n (A-out emit count)       |
| gr[4]  | -     | emit_vd / scratch             |
| gr[5]  | -     | emit_k                        |
| gr[6]  | lo    | node_idx                      |
| gr[6]  | hi    | prev_v                        |
| gr[7]  | -     | scratch (clobbered by emit)   |
| gr[8]  | lo    | d + 0x4000 (biased diagonal)  |
| gr[8]  | hi    | v (vertex index)              |
| gr[9]  | -     | k (wavefront offset)          |
| gr[10] | -     | sync (PE-side done — RESERVED)|
| gr[11] | -     | ts_off                        |
| gr[12] | -     | vl (clobbered by mvd)         |
| gr[13] | -     | intv_n                        |
| gr[14] | -     | ql (read-only)                |
| gr[15] | -     | tmp1                          |

PE 8 `reg[]` table (frozen):

| Slot    | Role                  |
|---------|-----------------------|
| reg[0]  | hardwired 0           |
| reg[1]  | pk (prev-prev k)      |
| reg[2]  | ppk (previous k)      |
| reg[6]  | gs_char (2-bit)       |
| reg[7]  | q_char (2-bit)        |
| reg[8]  | max_k (extend bound)  |
| reg[9]  | prev_vd (tile_a vd)   |
| reg[10] | gs_base = GS_START*16 |
| reg[11] | q_base  = Q_START*16  |

PE 13 (frozen — `pe.cpp:1162-1179`) `gr[]` table:

| Slot   | Half  | Role                |
|--------|-------|---------------------|
| gr[1]  | lo    | i                   |
| gr[1]  | hi    | tile_n              |
| gr[2]  | -     | d (set by extend)   |
| gr[3]  | -     | emit_vd (mvd pair)  |
| gr[4]  | -     | emit_k / scratch    |
| gr[5]  | lo    | n_pushed            |
| gr[5]  | hi    | n_intv              |
| gr[6]  | lo    | n_fin0              |
| gr[6]  | hi    | n_fin1              |
| gr[7]  | -     | scratch             |
| gr[8]  | -     | vd                  |
| gr[9]  | -     | k                   |
| gr[11] | -     | ts_off              |
| gr[12] | lo    | vl                  |
| gr[14] | -     | ql (read-only)      |
| gr[15] | -     | scratch             |

The frozen PE 8 / PE 13 / PE 11 references serve as the half-register
convention model: lo/hi sub-fields of a single `gr[]` slot are owned
by distinct logical names, with a `// half-reg lo` or `// half-reg hi`
comment annotating each access (see Section 5).

## 3. Plan 3d Slot Tables

Plan 3d magics 19, 20, 21, 22, 23 do NOT run concurrently within a
single PE invocation. The controller envelope serializes magic
dispatch per PE. Therefore a given PE-side `gr[]` or `reg[]` slot
MAY serve different roles in different magics, provided this artifact
documents the cross-magic live-out / live-in contract: the slot must
be **dead on entry** to any magic that reuses it for a fresh role,
which is the case for all rows below unless explicitly listed as
live-through.

The single inter-magic live-through contract within Plan 3d is the
PE 23 register-resident DEDUP_META state per DEC-1 (Section 4):
those slots persist across PING/PONG invocations of magic 23 within
a single case and are NOT reused by magic 19, 20, 21, or 22.

Legend for Status: `NEW` = first pinned in Plan 3d; `EXTENDED` =
already pinned by 3a/3b/3c on the controller side, Plan 3d adds a
PE-side reader/writer; `PRESERVED` = unchanged.

### 3.1 PE `gr[]` slots (across magics 19, 20, 21, 22, 23)

| Slot   | Readers / Writers (per magic)                                                                                                                          | Semantic role                                                                                                  | Live-in / live-out                                                            | Status |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|--------|
| gr[0]  | (zero)                                                                                                                                                 | hardwired 0                                                                                                    | THROUGH                                                                       | PRESERVED |
| gr[1]  | m19 lo=d (diag index) / hi=n_diags; m20 lo=i / hi=tile_n; m21 lo=i / hi=tile_n; m22 lo=ai / hi=bi; m23 lo=p (processed) / hi=DEDUP_TILE constant       | Per-magic loop bound + index packed lo/hi                                                                      | Dead on each magic boundary                                                   | NEW       |
| gr[2]  | m19 vd (packed v\|d_biased); m20 vd0 / vd1 (pair-loaded); m21 vd0 / vd1; m22 ab / bb buffer-base scratch; m23 dw\|iw selector (lo=dw / hi=iw)         | Diag/scatter element scratch (lo/hi sub-fields per magic)                                                      | Dead on each boundary (m23 reused as dw/iw within case — see DEC-1 Section 4) | NEW       |
| gr[3]  | m19 k (diag k); m20 shift; m21 shift; m22 a_n / b_n scratch; m23 dc / ic scratch                                                                       | Half-pair load companion to gr[2] for mvd                                                                      | Dead on each boundary                                                         | NEW       |
| gr[4]  | m19 lo=v / hi=d_val (half-extracted from vd); m20 bin0 / bin1; m21 off0 / off1; m22 lo=ai0 / hi=bi0; m23 dtn / itn scratch                            | Half-reg extraction target / pair offsets                                                                      | Dead on each boundary                                                         | NEW       |
| gr[5]  | m19 i_val (= d + k); m20 counts base ptr-offset; m21 bin_spm_off; m22 oi (output cursor); m23 don_ / ion scratch                                       | Per-magic local accumulator                                                                                    | Dead on each boundary                                                         | NEW       |
| gr[6]  | m19 lo=arc_idx / hi=ow; m20 (unused); m21 (unused); m22 (free post Round 8 amendment — original cum_oi/pe_global_base packing was infeasible due to >16-bit cum_oi range); m23 db / ib (state-X buffer-base scratch) | Per-magic accumulator / packed half pair (m22 freed by amendment) | Dead on each boundary | EXTENDED |
| gr[7]  | m19 packed_vw scratch; m20 (scratch); m21 tile_bin_counts ptr; m22 a_n cur_buf base / out_off; m23 nv scratch (state-X)                               | General scratch                                                                                                | Dead on each boundary                                                         | NEW       |
| gr[8]  | m19 lo=w (vertex index hi-half) / hi=hkey-hi; m20 (scratch); m21 (scratch); m22 lo=out_lo / hi=out_hi; m23 nk scratch                                  | Half-reg pair / emit register                                                                                  | Dead on each boundary                                                         | NEW       |
| gr[9]  | m19 hkey (full 32-bit packed v\|i+1); m20 i (loop); m21 i (loop); m22 gpos; m23 vd scratch (state-X reads)                                              | Full-width per-magic scalar                                                                                    | Dead on each boundary                                                         | NEW       |
| gr[10] | sync (PE-side done flag — RESERVED across all magics)                                                                                                  | RESERVED. Written ONLY by the controller envelope at `scripts/gwfa_instruction_generator.py:666-688`           | THROUGH; never written by any PE magic body                                   | PRESERVED |
| gr[11] | m19 absent (–1/0/1); m20 (unused); m21 (unused); m22 a_buf cur_n cache / o switch helper; m23 absent flag scratch                                      | Per-magic small-state scratch                                                                                  | Dead on each boundary                                                         | NEW       |
| gr[12] | m19 q_char (2-bit); m20 fin0_base scratch; m21 fin0_base scratch; m22 cum_oi (full int — Round 8 amendment, value >16 bits in practice); m23 k scratch | Per-magic scratch / m22 cum_oi cross-call accumulator | Dead on each boundary | EXTENDED |
| gr[13] | m19 gs_char (2-bit); m20 (unused); m21 (unused); m22 pe_global_base (full int — Round 8 amendment); m23 lo / hi pair scratch (M23_RI/PI temps) | Per-magic scratch / m22 pe_global_base cross-call constant | Dead on each boundary | EXTENDED |
| gr[14] | m19 lo=n_A / hi=n_B; m20 SORT_META offset cache; m21 SORT_META offset cache; m22 (unused); m23 lo=n_do / hi=n_io                                       | Output count packed lo/hi                                                                                      | Dead on each boundary                                                         | NEW       |
| gr[15] | m19 n_HA; m20 lo bin0 / hi bin1 packed; m21 lo bin0 / hi bin1 packed; m22 (free); m23 state \| pdone packed (lo=state, hi=pdone)                       | Per-magic count / scratch                                                                                      | Dead on each boundary                                                         | NEW       |

Notes on table:

- A "magic boundary" between two PE magics 19..23 means that the slot
  is **caller-dead** (the next magic does not read prior contents).
  Within a single magic body, the slot tracks the role listed.
- `gr[10]` is the PE-sync done flag. The controller envelope at
  `scripts/gwfa_instruction_generator.py:666-688` writes `gr[10] = 0`
  on entry to every PE magic call and `gr[10] = 1` on exit. PE magic
  bodies MUST NOT write `gr[10]`. PE magics MAY read `gr[10]` only
  as a sentinel; in practice none of magics 19..23 read it.

### 3.2 PE `reg[]` slots

`reg[]` is the PE compute-side register file (32 slots,
`reg[0..31]`). Plan 3d uses two disjoint regions of this file:
- **`reg[0..15]`** for cross-magic state that must persist across ISA
  lines and survive M23_RD / M23_RI / M23_PI macro boundaries (PE 23
  DEC-1 register-residency state).
- **`reg[16..31]`** as the PE 21 sort-cursor band (Section 3.3); not
  used by any other Plan 3d magic.

Compute instructions are deferred per rule 12; this artifact only
reserves `reg[]` slots for addressing-trace state used by lowered
magic bodies (loads / stores / scalar arithmetic on `reg[]`).

| Slot          | Magic | Semantic role                                                | Status |
|---------------|-------|--------------------------------------------------------------|--------|
| reg[0]        | -     | hardwired 0                                                  | PRESERVED |
| reg[1..10]    | (frozen reference m8/m13 only, post Round 9c amendment) | reg[1..11] are written by PE 8 (frozen ref pe.cpp:890-891 sets reg[10]=gs_base, reg[11]=q_base; m8_outer_loop body sets reg[1, 2, 6, 7, 8, 9]) and PE 13 (frozen ref pe.cpp:1226-1227 sets reg[10]=gs_base, reg[11]=q_base; m13 body sets reg[1, 6, 7]). Within a single test case, multi-step GWFA expansion fires PE 8/PE 13 BETWEEN dedup phases (each expansion step has its own phase 1 / phase 2 / sort / merge / dedup sequence), so the original DEC-1 reg[1..10] mapping is INFEASIBLE — reg[1..11] are clobbered between PE 23 calls of consecutive dedup phases. Round 9c amendment relocates DEC-1 state to reg[16..27] (no other PE-side magic touches that band). | EXTENDED  |
| reg[11]       | m8/m13 | q_base (gwfa frozen reference; not used by m22/m23)         | PRESERVED |
| reg[12]       | m23   | DEC-1 init cookie (Round 9a amendment, retained Round 9c): 0 = first PE 23 call this case → load moved DEDUP_META slots from SPM into reg[16..27] (per Round 9c re-mapping); 1 = subsequent call → load from reg[16..27]. pe::reset() clears reg[12]=0 at case boundary. Required because pv=0 is a legitimate diag value (not the 0xFFFFFFFFU sentinel from magic 29). | NEW       |
| reg[13..15]   | -     | reserved; available for waiver-driven temp expansion         | NEW       |
| reg[16]       | m23   | pv (DEDUP_META+0), DEC-1 register-resident — Round 9c       | NEW       |
| reg[17]       | m23   | pk (DEDUP_META+1), DEC-1 register-resident — Round 9c       | NEW       |
| reg[18]       | m23   | dc (DEDUP_META+4), DEC-1 register-resident — Round 9c       | NEW       |
| reg[19]       | m23   | ic (DEDUP_META+5), DEC-1 register-resident — Round 9c       | NEW       |
| reg[20]       | m23   | dw (DEDUP_META+6), full int — Round 9c (no half-pack)       | NEW       |
| reg[21]       | m23   | iw (DEDUP_META+7), full int — Round 9c                       | NEW       |
| reg[22]       | m23   | clo (DEDUP_META+14), DEC-1 register-resident — Round 9c     | NEW       |
| reg[23]       | m23   | chi (DEDUP_META+15), DEC-1 register-resident — Round 9c     | NEW       |
| reg[24]       | m23   | state (DEDUP_META+16), full int — Round 9c                   | NEW       |
| reg[25]       | m23   | pdone (DEDUP_META+17), full int — Round 9c                   | NEW       |
| reg[26]       | m23   | nv (DEDUP_META+18), DEC-1 register-resident — Round 9c       | NEW       |
| reg[27]       | m23   | nk (DEDUP_META+19), DEC-1 register-resident — Round 9c       | NEW       |
| reg[13..15]   | -     | reserved; available for waiver-driven temp expansion         | NEW       |
| reg[28..31]   | (none, post Round 3 / Round 9c amendments) | Reserved-but-unused after Round 3 freed reg[16..31] from PE 21 bin_cursors (see Section 3.3) and Round 9c relocated PE 23 DEC-1 state into reg[16..27]. Available for future waiver-driven expansion. | EXTENDED  |

### 3.3 PE 21 `bin_cursors[16]` band — Round 3 amendment (SPM-resident)

**Original allocation (superseded):** `reg[16..31]` register band, one
slot per radix bin. Indirect access via `reg[16 + gr.at(6)]` where
`gr[6]` is the runtime-computed bin index.

**Post-amendment allocation:** SPM-resident at `spm[SORT_META + 34..49]`
(per-PE; 16 contiguous slots immediately after `tile_n` / `shift` in
the SORT_META region). Each access (read, RMW) is an explicit SPM
load with 2-cycle settle and one explicit RAW-break NOP after the
arithmetic before the matching store.

**Reason for amendment:** `gendp-isa-reviewer` (Round 3, l8cv-rev)
P1 finding — the runtime-indexed `reg[base + runtime_index]` form
is not a real GenDP ISA op. The control instruction set encodes
register addresses as immediate fields (see `data_movement_instruction`
in `scripts/utils.py`); there is no opcode that takes a register-file
index from another register. The PE 8 frozen-reference parallel at
`pe.cpp:680-685` is a false positive: `mvi2_ld(int base_reg, ...)` is
a lambda parameter that is bound to a constant at every call site
(`mvi2_ld(10, 4)` and `mvi2_ld(11, 7)`), so after inlining each call
reduces to a constant-immediate `reg[10]` / `reg[11]` access. PE 21's
cursor index is data-dependent.

**Alternatives considered:**
- 16-way macro-unrolled `if (bin == 0) reg[16] = ...` chain at every
  cursor access: AC-4 legal but ~32 ISA ops per cursor read and
  ~64 ops per RMW; with 4 cursor accesses per scatter element and 80
  elements per tile, the unroll cost is roughly 25 600 ops per PE 21
  invocation. Rejected on performance grounds.
- SPM-resident cursors with 2-cycle settle: ~10 ops per scatter
  cursor access (load + 2 NOPs settle + RMW + store + RAW-break NOPs)
  = ~3200 ops per PE 21 invocation. Selected.

**Layout under amendment:**
```
spm[SORT_META + 0..15]  : final bin_counts (untouched by PE 21)
spm[SORT_META + 16..31] : tile_bin_counts (init + per-element inc)
spm[SORT_META + 32]     : tile_n (read-only)
spm[SORT_META + 33]     : shift (read-only)
spm[SORT_META + 34..49] : bin_cursors[0..15] (init + per-element RMW)
                          NEW slots; previously unused per-PE bank space
```

`reg[16..31]` reserved-but-unused under the amendment (kept open for
future re-allocation if a hardware spec adds a runtime-indexed
register access opcode). The compile-time `for (int b = 0; b <
SORT_RADIX_BINS; b++)` initialization loop in PE 21 (rule 4 macro
unroll) writes both `tile_bin_counts[b] = 0` and `bin_cursors[b] = 0`
at magic entry; both regions are dead at magic exit.

**Controlled-change rule compliance (AC-2):** This amendment is
documented in this Section 3.3 (and the `reg[16..31]` row of Section
3.2). The PE 20 (l8b) and PE 21 (l8c) lowerings are re-validated in
the same Round 3 commit that lands the amendment, so no orphan
state results.

## 4. DEC-1 Register-Residency Contract for `DEDUP_META`

PE 23 maintains 20 words of state in `spm[DEDUP_META + 0..19]`. Per
**user decision DEC-1** (resolved during plan generation), the
PE-local checkpoint subset moves to register residency. The
controller-visible and controller-handshake subsets remain in SPM.

### 4.1 Slot disposition

| Slot           | Semantic                                  | Disposition under DEC-1                                                            | Persistence evidence              |
|----------------|-------------------------------------------|------------------------------------------------------------------------------------|-----------------------------------|
| DEDUP_META+0   | pv (packed prev-vd)                       | **MOVED** to reg[1] register-resident across PING/PONG calls within a single case | gwfa_instruction_generator.py:666-688 envelope only writes gr[10] |
| DEDUP_META+1   | pk (prev k)                               | **MOVED** to reg[2]                                                                 | (same envelope evidence)          |
| DEDUP_META+2   | n_do (controller-visible diag-out count)  | **UNCHANGED** in SPM                                                                | Read by controller magic 31 at `pe_array.cpp:6282-6302` |
| DEDUP_META+3   | n_io (controller-visible intv-out count)  | **UNCHANGED** in SPM                                                                | Read by controller magic 31 at `pe_array.cpp:6282-6302` |
| DEDUP_META+4   | dc (diag cursor)                          | **MOVED** to reg[3]                                                                 | (envelope evidence)               |
| DEDUP_META+5   | ic (intv cursor)                          | **MOVED** to reg[4]                                                                 | (envelope evidence)               |
| DEDUP_META+6   | dw (diag ping-pong selector 0/1)          | **MOVED** to reg[5] half-reg lo                                                     | (envelope evidence)               |
| DEDUP_META+7   | iw (intv ping-pong selector 0/1)          | **MOVED** to reg[5] half-reg hi                                                     | (envelope evidence)               |
| DEDUP_META+8   | dead (kept zero by magic 32)              | **UNCHANGED** in SPM (dead, kept 0)                                                 | Plan 2b Milestone B               |
| DEDUP_META+9   | dead (kept zero by magic 32)              | **UNCHANGED** in SPM (dead, kept 0)                                                 | Plan 2b Milestone B               |
| DEDUP_META+10  | dtn (diag tile current count)             | **UNCHANGED** in SPM                                                                | Read/write by controller magics 30/31 at `pe_array.cpp:5817-5916, 6163-6184` |
| DEDUP_META+11  | don_ (diag tile other-buffer count)       | **UNCHANGED** in SPM                                                                | (same controller refill evidence) |
| DEDUP_META+12  | itn (intv tile current count)             | **UNCHANGED** in SPM                                                                | (same controller refill evidence) |
| DEDUP_META+13  | ion (intv tile other-buffer count)        | **UNCHANGED** in SPM                                                                | (same controller refill evidence) |
| DEDUP_META+14  | clo (current intv lo)                     | **MOVED** to reg[6]                                                                 | (envelope evidence)               |
| DEDUP_META+15  | chi (current intv hi)                     | **MOVED** to reg[7]                                                                 | (envelope evidence)               |
| DEDUP_META+16  | state (0=X, 1=B, 2=C)                     | **MOVED** to reg[8] half-reg lo                                                     | (envelope evidence)               |
| DEDUP_META+17  | pdone (1=done across all calls)           | **MOVED** to reg[8] half-reg hi                                                     | (envelope evidence)               |
| DEDUP_META+18  | nv (next vd)                              | **MOVED** to reg[9]                                                                 | (envelope evidence)               |
| DEDUP_META+19  | nk (next k)                               | **MOVED** to reg[10]                                                                | (envelope evidence)               |

### 4.2 Persistence evidence (mandatory citation)

The persistence claim — that non-`gr[10]` PE registers retain values
across magic 23 PING (mask=0) and PONG (mask=1) invocations within a
single test case — rests on:

1. **Magic 23 envelope at `scripts/gwfa_instruction_generator.py:666-688`.**
   Between `PE_DEDUP_PING` (PC 57-60) and `PE_DEDUP_PONG` (PC 61-64),
   the controller body writes ONLY `gr[10]`:
   - PC 57 / PC 61 (clear sync): `gr[10] = 0` (slot 1 only).
   - PC 58 / PC 62 (magic dispatch): `magic(23, mask=0)` and
     `magic(23, mask=1)` respectively (slot 1 only).
   - PC 59 / PC 63 (signal done): `gr[10] = 1` (slot 1 only).
   - PC 60 / PC 64 (halt): two halt instructions.
   No other `gr[]` or `reg[]` is touched between PING and PONG.
   Therefore non-`gr[10]` registers persist across PING/PONG calls
   within a single case.

2. **`pe::reset()` is NOT evidence of cross-call persistence.** The
   reset function at `pe.cpp:43-46` clears both register files. It
   is called on PE construction and at the per-case reset boundary
   in `gwfa_simulation()`. Its purpose is cross-case reset, not
   cross-call persistence. Persistence under DEC-1 holds only
   within the same case between envelope-defined boundaries.

### 4.3 Constraints and invariants

- `gr[10]` excluded from any DEC-1 reservation. RESERVED for sync.
- The PE 23 magic body MUST initialize the register-resident state
  on the first call within a case. The plan's lowering pattern is:
  `pe::reset()` clears regs to 0 → first PE 23 call sees pv=0 (treat
  as 0xFFFFFFFFU sentinel via constant load), state=0 (X), pdone=0,
  cursors=0, selectors=0. All values are valid initial states. No
  separate "first call" gating is required; the constant-load on
  every entry is overwritten by the SAVE writes near the labels
  `m23_X / m23_B / m23_C` only on subsequent calls within the case
  by virtue of register persistence. This contract is the inverse
  of the SPM-resident pattern (SPM persists across calls AND across
  cases until magic 32 zeroes it; registers persist only across
  calls within a case).
- `DEDUP_META+2/+3` writes (n_do, n_io publish) MUST land in the
  PE 23 magic body epilogue in EVERY call (PING and PONG). These
  are controller-visible and required by magic 31 read.
- `DEDUP_META+10..+13` writes (dtn refill / don_ swap / itn / ion
  swap) MUST land in the PE 23 magic body whenever the buffer-swap
  arm of M23_RD or M23_RI fires (per the existing dw^=1 / iw^=1
  logic). The controller side (magic 30/31) reads/writes these slots
  outside PE 23 calls; the PE side reads them on call entry and
  updates them on swap.

## 5. Half-Register Convention

The simulator's `gr[]` slots are 32 bits wide. Sub-field access uses
explicit `>> 16` (high half) or `& 0xFFFF` (low half) operations.
Plan 3d adopts the following greppable comment convention to make
half-register flow visible to `gendp-isa-reviewer` and the
mechanical pre-check:

- `// half-reg hi` — annotates an access that reads or writes the
  high 16 bits of a `gr[]` slot.
  Examples:
  ```cpp
  uint32_t v = (uint32_t)gr[2] >> 16;       // half-reg hi
  gr[14] = (gr[14] & 0xFFFF) | (n_B << 16); // half-reg hi
  ```
- `// half-reg lo` — annotates an access that reads or writes the
  low 16 bits.
  Examples:
  ```cpp
  int32_t d_val = (int32_t)(gr[2] & 0xFFFF) - GWF_DIAG_SHIFT; // half-reg lo
  gr[14] = (gr[14] & 0xFFFF0000) | (n_A & 0xFFFF);            // half-reg lo
  ```
- `// half-reg pack` — annotates a simultaneous lo+hi pack of two
  16-bit values into one `gr[]` slot.
  Example:
  ```cpp
  uint32_t nvd = (w << 16) | ((GWF_DIAG_SHIFT + nd) & 0xFFFF); // half-reg pack
  ```

Mechanical greppability:

```
rg -n '// half-reg (hi|lo|pack)' pe.cpp
```

Per-slot hi/lo ownership for Plan 3d magics is documented in the
"Half" column of Section 3.1.

## 6. Waiver Table

Empty at `l8` commit. New rows added under the controlled-change
rule (Section 7) when a magic lowering needs a structural-latency
waiver. Each row carries an inline `// waiver: <reason>` comment in
the source so the convention is greppable:

```
rg -n '// waiver:' pe.cpp
```

| Magic | Code range | Justification | Bounding behavior |
|-------|------------|---------------|-------------------|
| (none yet) | - | - | - |

## 7. Controlled-Change Rule (AC-2)

Shared-slot changes (any entry in Sections 3 or 4) after this
artifact lands require:

1. A dedicated amendment commit to this file (and to
   `isaLikeAllGwfaPlan3dH.md` if narrative changes) BEFORE the next
   magic commit. The amendment commit stands alone — it does NOT
   piggyback on a magic lowering commit.
2. For every already-lowered PE magic 19..23 whose contract the
   amendment touches, a fresh `gwfa_check_correctness.py 1 -t 56`
   rerun, reported in the amendment commit message.
3. If the amendment crosses a cluster boundary (after l8c sort gate
   or after l8e dedup gate), the cluster mode-2 gate is re-run. Any
   regression below the pre-amendment 295/295 baseline rejects the
   amendment.

## 8. Mechanical Pre-Check Patterns (pe.cpp PE body)

Ripgrep patterns reviewers can paste at the repo root to catch the
most common AC-3 / AC-4 / AC-5 violations in PE-body magic regions
of `pe.cpp`. These complement `gendp-isa-reviewer` and are
committed alongside this artifact.

**RAW hazard in VLIW pairing** — slot-0 dest immediately read as
slot-1 src on the very next line (common for
`gr[X] = ...; gr[Y] = gr[X];` without a `//NOP` between):

```
rg -n --pcre2 '^\s*gr\[(\d+)\]\s*=.*$\n\s*gr\[\d+\]\s*=.*gr\[\1\]' pe.cpp
```

**SPM load lacks 2-NOP settle before first consumer** — for any
`reg|gr[X] = spm[...]` or `reg|gr[X] = fspm[...]` the next two
lines must each be `//NOP` (rule 6: 2-cycle latency = 2 ISA-line
gap):

```
rg -n --pcre2 '^\s*(?:gr|reg)\[\d+\]\s*=\s*(?:spm|fspm)\[.*\];\s*$\n(?!(\s*//NOP.*\n){2})' pe.cpp
```

**MM/S2 load missing `// waitLSQ`** — for any `reg|gr[X] = mm[...]`
the next line must be `// waitLSQ` (rule 7):

```
rg -n --pcre2 '^\s*(?:gr|reg)\[\d+\]\s*=\s*mm\[.*\];\s*$\n(?!\s*//\s*waitLSQ)' pe.cpp
```

**Half-register comment presence** — sanity grep that every
half-reg shift/mask carries the convention comment:

```
rg -n --pcre2 '(>>\s*16|&\s*0xFFFF|<<\s*16).*$\n(?!\s*//\s*half-reg)' pe.cpp
```

**Latency / waiver comment count** — spot-check the standard
annotations exist in PE bodies:

```
rg -n '// waitLSQ|// SPM settle|// half-reg|// waiver:' pe.cpp | wc -l
```

Reviewers should read hits in context: patterns are approximate
(branch labels, multi-line expressions, and frozen reference
examples may produce false positives) and do not replace a
`gendp-isa-reviewer` pass.

## 9. AC-9 / AC-10 Frozen Reference Trace

The frozen oracle is committed under `tests/frozen/plan3d_pre_l8a/`
directly before `l8a` lands. It has five components:

1. **Mode-1 score baseline** — `mode1_t56_scores.txt`, produced by
   `python3 scripts/gwfa_check_correctness.py 1 -t 56`. Must stay at
   `15 passed, 0 failed out of 15` after every PE 19..23 lowering.
2. **Mode-2 score baseline** — `mode2_t56_scores.txt`, produced by
   `python3 scripts/gwfa_check_correctness.py 2 -t 56`. Must stay at
   `295 passed, 0 failed out of 295` at every cluster gate and the
   final exit gate.
3. **Wavefront trace** — `wfDebug_HEAD.txt`, copied from
   `wfDebug.txt` after `python3 scripts/gwfa_check_correctness.py 3`.
   Per-step `[gfa_ed_step]` / `Z` / `WF` lines covering case 0.
4. **Per-PE-magic observable snapshots** — `plan3d_snapshot_pe19.txt`,
   `plan3d_snapshot_pe22.txt`, `plan3d_snapshot_pe23.txt`, produced
   by `scripts/plan3d_capture_snapshot.sh`. The snapshots are
   emitted by three `#ifdef PLAN3D_TRACE_SNAPSHOT` blocks in
   `pe.cpp`:
   - **PE 19 exit (`pe.cpp` immediately before `m19_done`)**: dumps
     `FIN0_META[0..4]` (n_diags + 4 publish counts) and the first
     8 records of A-list (`fspm[FIN0_OUT + 2*i]`), B-list
     (`fspm[FIN0_OUT_SIZE-2-2*i]`), and HA-bucket
     (`fspm[FIN0_OUT_HA + 2*i]`) per PE per call.
   - **PE 22 exit (`pe.cpp` immediately after the `m22_done` SPM
     publish writes)**: dumps `MERGE_META[0..8]`, `spm[976..981]`,
     `spm[982]`, and `spm[983]` per PE per call.
   - **PE 23 first PING of case 0 (entry + exit)**: gated by a
     per-PE `static int dumped_entry[4] / dumped_exit[4]` flag
     and `(magic_mask & 1) == 0`. Dumps `DEDUP_META[0..19]` for
     each of the 4 PEs at the entry point (after meta restore in
     the PE 23 init block) and at the exit point (after `m23_end`
     label).
5. **`plan3d_snap=1` Makefile target** gates the
   `PLAN3D_TRACE_SNAPSHOT` preprocessor symbol; default builds are
   unaffected. `scripts/plan3d_capture_snapshot.sh` drives a
   single-case run, moves the snapshot files into
   `tests/frozen/plan3d_pre_l8a/`, then restores a default `sim`
   build.

AC-9 / AC-10 verification after each lowered PE magic:

- **After PE 19 (l8a / l8av)**: rerun
  `scripts/plan3d_capture_snapshot.sh 1` and diff the regenerated
  `plan3d_snapshot_pe19.txt` against the committed baseline.
  Byte-equal = AC-9 PASS for PE 19. Any diff = AC-9 FAIL.
- **After PE 20 (l8b / l8bv)**: no dedicated snapshot diff
  required (PE 20 not in the AC-9 risky-magic set per Lower
  Bound); mode-1 score baseline still applies.
- **After PE 21 (l8c / l8cv)**: same; cluster mode-2 gate at
  l8cv applies.
- **After PE 22 (l8d / l8dv)**: rerun snapshot script, diff
  `plan3d_snapshot_pe22.txt` against baseline. Byte-equal = AC-9
  / AC-7 PASS for PE 22.
- **After PE 23 (l8e / l8ev)**: rerun snapshot script, diff
  `plan3d_snapshot_pe23.txt` against baseline. Byte-equal = AC-9
  / AC-8 PASS for PE 23. Cluster mode-2 gate at l8ev applies.

## 10. Out-of-Scope (do NOT touch)

- Frozen PE reference examples PE 8 (`pe.cpp:708-1085`), PE 11
  (`pe.cpp:1087-1150`), PE 13 (`pe.cpp:1151-1380`).
- Frozen controller reference examples (Plan 3a/3b/3c controller
  ABI). PE-side `gr[]` is physically separate from controller
  `gr[]`; no controller-side reservation propagates to the PE side
  except `gr[10]` (PE-sync done flag).
- Controller magic 30 / magic 31 reads of
  `DEDUP_META+2/+3/+10..+13`. These slot dispositions are
  UNCHANGED in SPM per DEC-1.
- PE compute-instruction changes (rule 12: compute deferred).
