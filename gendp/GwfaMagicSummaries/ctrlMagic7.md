Magic 7
========================================================================
Summary: GWFA controller `tile_load` — copies a tile of diagonal (vd) words from MM directly
into the per-PE SPM A-tile region (no S1c staging). Picks PING vs PONG buffer via
`magic_mask & 1` (`GWFA_BUF0_BASE=0` / `GWFA_BUF1_BASE=1280`) and advances a global cursor
gr[14]. Called from `gwfa_main_instruction()` as `MAGIC_7_BUF0` / `MAGIC_7_BUF1` four times
in `scripts/gwfa_instruction_generator.py` (lines 202, 207, 222, 236) — once to prime each
buffer in the prologue and once per steady-state half to fetch the next tile. Lives at
`pe_array.cpp:1292-1409`.

Inputs (controller gr): gr[14]=cursor, gr[15]=n_a (total diags), gr[19]=s_a_off (MM base
for A diags). Constants: 64 diags/PE, 4 PEs → 256 diags max per tile, each diag = 2 words.

Pseudocode:
```
buf_base = (magic_mask & 1) ? GWFA_BUF1_BASE : GWFA_BUF0_BASE
// ---- Phase 1: per-PE tile_n metadata ----
for pe in 0..3:
  pe_spm = pe*BANK_GROUP + buf_base
  remaining = (n_a - cursor) - pe*64
  tile_n    = clamp(remaining, 0, 64)
  s1c[S1C_TILE_N + pe]            = tile_n
  spm[pe_spm + META_OFF + 3]      = tile_n
  if tile_n <= 0:
    spm[pe_spm + META_OFF]        = 0
    spm[pe_spm + META_OFF + 1]    = 0

// ---- Phase 2: MM → SPM copy ----
// Per-PE pointer setup (PE-local gr aliases: PE0=gr[1,3,4]
// PE1=gr[5,6,7] PE2=gr[8,9,10] PE3=gr[11,16,17]; gr[13]=scratch/flag)
for pe in 0..3:
  src[pe] = s_a_off + (cursor + pe*64)*2          // MM source
  end[pe] = src[pe] + 2*tile_n[pe]                // MM end
  dst[pe] = pe*BANK_GROUP + buf_base + A_TILE_OFF // SPM dst

// Peel A — handle (tile_n % 4) per PE with 1-diag mvd's (2 words each)
for pe in 0..3:
  for i in 0 .. (tile_n[pe] & 3):
    spm[dst..+2] = mm[src..+2]   // mvd
    src += 2; dst += 2

// Peel B — equalize remainders so the main loop is 4-wide w/ 1 counter
min_resid = min(end[pe]-src[pe] for pe in 0..3)
for pe in 0..3: end[pe] -= min_resid
peel_outer:
  any = 0
  for pe in 0..3:
    if src[pe] < end[pe]:
      mvdq spm[dst[pe]..+8] = mm[src[pe]..+8]
      src[pe] += 8; dst[pe] += 8; any = 1
  if any: goto peel_outer

// Rebase PE1..3 pointers as deltas relative to PE0
for pe in 1..3:
  src[pe] -= src[0]
  dst[pe] -= dst[0]
n_iters = min_resid >> 3   // /8

// Main loop — 4 concurrent PE mvdq's per iteration (32 words/iter)
for i in 0..n_iters:
  mvdq spm[dst[0]..+8]                = mm[src[0]..+8]                // PE0
  mvdq spm[dst[0]+dst[1]..+8]         = mm[src[0]+src[1]..+8]         // PE1
  mvdq spm[dst[0]+dst[2]..+8]         = mm[src[0]+src[2]..+8]         // PE2
  mvdq spm[dst[0]+dst[3]..+8]         = mm[src[0]+src[3]..+8]         // PE3
  src[0] += 8; dst[0] += 8

// ---- Cursor advance ----
adv = clamp(n_a - cursor, 0, 256)
cursor += adv   // gr[14] += adv
```
