# Plan 3c Cross-Magic ABI Extension

Artifact for task `l6` of `isaLikeAllGwfaPlan3cH.md`. Extends the authoritative
Plan 3a register ABI and the Plan 3b extension for the eight GWFA controller magics
being lowered in Plan 3c (magics 32..39). Committed before any magic is lowered per
AC-7; any later shared-slot change must land in a separate amendment commit with
mode-1 rerun of every affected prior magic.

## 1. Scope

This file freezes the cross-magic `gr[]` and `s1c[]` slots that magics 32..39 read
or write, extending:
- `isaLikeAllGwfaPlan3aH.md` (authoritative ABI for sort / diag-split / HA path).
- `isaLikeAllGwfaPlan3bH.md` (extension for dedup driver + m31 seam producer).

Plan 3c adds coverage for the dedup-finalize consumer (m32), merge-reload +
writeback (m33/m35), sort-bin tile-load (m34), diag-merge-finalize + intv merge
split/load (m36/m37), intv merge finalize + intv sort setup (m38/m39). AC-7
controlled-change rule (restated in section 5) governs any later modification.

## 2. Pre-existing ABI Summary (read-only reference)

Inherited from Plans 3a/3b — magics 32..39 must respect without change:

- `gr[7..10]`: protected magic-19 scavenge-scope; `gr[10]` is also the PE-sync
  done flag (BL-20260413-gr-clobber). Magics 32..39 must NOT write these.
- `gr[11]`: CLAUDE-safe controller scratch for SPM/s1c staged loads
  (BL-20260417-ctrl-sync-gr). Ping-pong one SPM/s1c request in flight; 3-NOP
  gap after SPM load, 1-NOP gap after s1c load. All magics 32..39 use `gr[11]`
  this way.
- `gr[12]`: live GWFA wavefront-distance counter (magics 3/5/7). THROUGH for
  m32..m39; NEVER write.
- `gr[13]`: PE-sync AND of all PE `gr[10]` flags, recomputed every tick
  (`pe_array::tick`). THROUGH; NEVER write.
- `gr[1]`: sort-pass counter; THROUGH on m28/m29/m31 per Plan 3b. On m33 it is
  used as a caller-dead scratch for the `src_a`/`src_b` stage (per Plan 3b
  l4abi). Writable in m33 only under the dead-on-entry rationale.
- `gr[2]`: sort/merge/dedup cursor. READ by m34 (`cursor = gr[2]`) and written
  by m34 (`gr[2] = cursor + SORT_TILE`). Also advanced by m35
  (`gr[2] += MERGE_STEP`). Outside m34/m35 Plan 3c leaves it unchanged.
- `gr[5]`: magic-local scratch (m24 acc, m37 bs `mid`, m37/m38 post-bs acc
  `pe_base`, m38 `intv_n` acc). Dead on every magic boundary among 32..39;
  callers must not rely on content across magic boundaries.
- `gr[28]`: `intv_n` broadcast. WRITE by m28 on exit; READ by m29; THROUGH on
  m30/m31 (Plan 3b). Plan 3c writes it in m32 and m38.

## 3. Plan 3c Slot Table

Legend for Status: `NEW` = first pinned in Plan 3c; `EXTENDED` = already pinned
by 3a/3b, Plan 3c adds a reader/writer; `PRESERVED` = unchanged from 3a/3b,
reproduced here so magics 32..39 respect it.

### 3.1 `gr[]` slots

| Slot   | Readers      | Writers   | Semantic role                        | Live-in / live-out                                  | Status    |
|--------|--------------|-----------|--------------------------------------|-----------------------------------------------------|-----------|
| gr[1]  | m33          | m33 (tmp) | s1c `src_a/src_b` load scratch       | Dead on m33 entry; dead on exit                     | PRESERVED |
| gr[2]  | m34          | m34, m35  | Sort cursor / merge step advance     | Sort-cursor in, cursor + tile out                   | PRESERVED |
| gr[3]  | m34, m36, m39 | m37 (bs), m39 | MM source base (sort) / m36 diag_base fallback / m39 init `MM_NEXT_INTV` | Sort-driver live-through; m37 bs writes then dead; m39 writes on exit | EXTENDED |
| gr[4]  | m33, m35, m37, m38 | m37 (bs + exit), m39 | MM destination base / m37 `out_buf` publish / m38 scratch / m39 init `MM_SWAP` | RESERVED at m37 exit as `out_buf` (BL-20260421-m37-out-buf-gr4-reservation) | EXTENDED |
| gr[5]  | m37, m38     | m37, m38  | m37 bs `mid` / m37 `pe_base` / m38 `intv_n` acc | Dead on each boundary                      | PRESERVED |
| gr[6]  | m36          | m37, m39  | Merge-happened flag / loop bound     | m37 writes `niter` or 0; m36 reads; m39 writes `(n+3)>>2` | EXTENDED |
| gr[7]  | —            | —         | Protected (magic-19 scavenge)        | THROUGH; NEVER write in m32..m39                    | PRESERVED |
| gr[11] | m32..m39     | m32..m39  | CLAUDE-safe controller scratch       | Per-magic scratch; ping-pong SPM/s1c staging        | PRESERVED |
| gr[15] | m32 (exit)   | m32       | `n_a_final` publish                  | WRITE by m32 epilogue; consumed downstream          | NEW       |
| gr[24] | m34, m36, m37, m38, m39 | m38, m39 | Sort/merge/dedup count `n_a`     | m38 restores `gr[24] = s1c[145]` (saved by m16); m39 reads via `s1c[155]` | EXTENDED |
| gr[28] | —            | m32, m38  | `intv_n` broadcast                   | WRITE by m32 epilogue; WRITE by m38                 | EXTENDED |

### 3.2 `s1c[]` slots (Plan 3c-relevant)

| Slot range      | Readers            | Writers            | Semantic role                                       | Status    |
|-----------------|--------------------|--------------------|-----------------------------------------------------|-----------|
| s1c[0..3]       | m37                | m37                | bs `lo_[0..2]`, intv-output pts[0..3] (reused)      | PRESERVED |
| s1c[0..143]     | (cleared)          | m32 epilogue       | Dedup epilogue clear of sort/merge scratch band     | PRESERVED |
| s1c[4..7]       | m35, m37, m38      | m35, m37           | m35 cum; m37 pts[pe] cum; m38 intv_n partial        | PRESERVED |
| s1c[8..11]      | m33, m37           | m33, m37           | m33 `src_a` by PE; m37 `s1c[8+pe]` mergeA src       | PRESERVED |
| s1c[12..15]     | m33                | m33                | m33 `rem_a` by PE                                   | PRESERVED |
| s1c[16..23]     | m33, m37           | m33, m37           | m33 `src_b`/`rem_b`; m37 mergeB src/rem; m32 diag_out_base/cursor (disjoint phase) | PRESERVED |
| s1c[24..31]     | m32                | m31                | m32 intv_out_base (24..27), cursor (28..31); seam producer = m31 | PRESERVED |
| s1c[40..49]     | m37                | m37                | m37 `a_sp[0..4]` at 40..44, `b_sp[0..4]` at 45..49  | PRESERVED |
| s1c[50..73]     | m37                | m37                | m37 tile sizes/sources (a0/a1/b0/b1 + a_src/b_src)  | PRESERVED |
| s1c[144]        | m32                | m16                | `diag_base` staged through gr[11] at m32 entry      | PRESERVED |
| s1c[145]        | m38                | m16                | `n_a` saved by m16 (read back by m38, per BL-20260413-gr-clobber) | PRESERVED |
| s1c[146]        | m37                | m16                | `intv_n` staged through gr[11] at m37 entry         | PRESERVED |
| s1c[147]        | m28                | m16                | `n_phase1` raw                                      | PRESERVED |
| s1c[148]        | m28, m37 (writer), m38 | m37, m16       | `n_a` / `n_total` publish                           | EXTENDED  |
| s1c[149]        | m37 (writer), m38  | m37, m38           | merge-skipped sentinel (<0) / intv_n commit         | EXTENDED  |
| s1c[152]        | m16, m28, m32, m37 | m32, m37           | `active_intv` / MM_INTV2 publish; m32 writes `MM_INTV2`; m37 writes `out_buf` or `MM_NEXT_INTV` | EXTENDED |
| s1c[153]        | m16, m28, m29, m32, m36 | m32, m36       | `active_diag_base` (`diag_base`) publish            | EXTENDED  |
| s1c[154..158]   | m32, m36           | m36                | 5 split indices for dedup; `s1c[154]=0`, `s1c[158]=n_a` | EXTENDED |
| s1c[155]        | m39                | (written upstream) | m39 reads `gr[24] = s1c[155]`                       | EXTENDED  |
| s1c[159..162]   | m37 (boundary writer), m38 | m36        | 4 boundary vd values for dedup                      | EXTENDED  |
| s1c[163..168]   | (downstream)       | m38                | `intv_lo[pe+1]` (163..165) / `intv_hi[pe]` (166..168) | NEW |
| s1c[169..175]   | m38                | m38                | m38 per-b scratch `l_hi`/`h_hi` (reused across b=0..2) | NEW |
| s1c[176..179]   | m32 (guarded)      | m31                | First-intv `lo` seam band (one per PE); read only under `intv_n > 0` | PRESERVED |
| s1c[180..183]   | m32 (guarded)      | m31                | First-intv `hi` seam band; read only under `intv_n > 0` | PRESERVED |
| s1c[184..187]   | m32 (guarded)      | m31                | Last-intv `lo` seam band; read only under `cnt > skip` | PRESERVED |
| s1c[188..191]   | m32 (guarded)      | m31                | Last-intv `hi` seam band; read only under `cnt > skip` | PRESERVED |
| s1c[176..191]   | (cleared)          | m32 epilogue       | Seam band cleared at m32 exit                       | PRESERVED |
| s1c[196..211]   | m33                | —                  | m33 metadata band (Plan 3b reference only)          | PRESERVED |

## 4. Magic 31 <-> Magic 32 Seam Contract (AC-6)

Pre-lowering semantics at `pe_array.cpp:6447` and `pe_array.cpp:6478` define
the authoritative seam contract that the lowered m32 must reproduce byte-for-
byte:

- **First-intv seam read** (`s1c[176+pe]` and `s1c[180+pe]`): consumed by m32
  only inside the `intv_n > 0` arm of the boundary compare. That is, the first
  lo/hi of each PE's intv slice is read when there is a prior output to seam
  against.
- **Last-intv seam read** (`s1c[188+pe]`): consumed by m32 only inside the
  `cnt > skip` arm. When the PE's entire slice was merged away
  (`cnt == skip`), `last_intv_hi` retains the merged tail and no last-hi
  seam load is issued.
- **Epilogue preserves**:
  - `memset s1c[0..143]` — clear sort/merge/dedup scratch band.
  - `memset s1c[176..191]` — clear the seam band itself (16 words).
  - `s1c[152] = MM_INTV2` — publish the intv gather base.
  - `s1c[153] = diag_base` — re-publish the diag gather base.
  - `gr[15] = n_a_final` — publish final diag count.
  - `gr[28] = intv_n` — publish final intv count.
- **Magic 31 producer semantics untouched**: first-intv `{lo, hi}` at
  `s1c[176+pe]` / `s1c[180+pe]` written only on the pre-advance `s1c[28+pe] == 0`
  arm; last-intv `{lo, hi}` at `s1c[184+pe]` / `s1c[188+pe]` written on every
  nonzero-`nis` tile (`pe_array.cpp:6147, 6166, 6173, 6182, 6188`).
- **No cross-magic dependence on `s1c[176..191]` outside m32**: the seam band is
  live only between m31 exit and m32 epilogue.

## 5. Controlled-Change Rule (AC-7)

Shared-slot changes (any entry in section 3) after this artifact lands require:

1. A dedicated amendment commit to this file (and to `isaLikeAllGwfaPlan3cH.md`
   if the narrative must change) BEFORE the next magic commit. The amendment
   commit stands alone — it does not piggyback on a magic lowering commit.
2. For every already-lowered magic whose contract the amendment touches, a
   fresh mode-1 `-t 56` rerun, reported in the amendment commit message.
3. If the amendment crosses a cluster boundary (after m32 or m35 or m39),
   the cluster mode-2 gate is re-run. A regression below the pre-amendment
   baseline rejects the amendment.

## 6. Mechanical Pre-check Pattern List

Ripgrep patterns a reviewer can paste at the repo root to mechanically catch
the most common AC-4 / AC-5 violations in pe_array.cpp magic bodies. These
are complementary to `gendp-isa-reviewer` and committed alongside this
artifact.

**RAW hazard in VLIW pairing** — detects slot-0 dest immediately read as
slot-1 src on the very next line (common for `gr[X] = ...; gr[Y] = gr[X];`
without a `//NOP` between):

```
rg -n --pcre2 '^\s*gr\[(\d+)\]\s*=.*$\n\s*gr\[\d+\]\s*=.*gr\[\1\]' \
   pe_array.cpp
```

**SPM load lacks 3-NOP settle before first consumer** — for any `gr[11] =
spm[...]` the next three lines must each be `//NOP` (3-cycle latency per rule
6):

```
rg -n --pcre2 '^\s*gr\[11\]\s*=\s*spm\[.*\];\s*$\n(?!(\s*//NOP.*\n){3})' \
   pe_array.cpp
```

**s1c load lacks 1-NOP gap** — for any `gr[11] = s1c[...]` the next line must
be `//NOP` (1-cycle latency per rule 8):

```
rg -n --pcre2 '^\s*gr\[(\d+)\]\s*=\s*s1c\[.*\];\s*$\n(?!\s*//NOP)' \
   pe_array.cpp
```

**MM load missing `// waitLSQ` before first consumer** — for any `gr[11] =
mm[...]` the next line must be `// waitLSQ` (rule 7):

```
rg -n --pcre2 '^\s*gr\[\d+\]\s*=\s*mm\[.*\];\s*$\n(?!\s*//\s*waitLSQ)' \
   pe_array.cpp
```

**Latency comment presence grep** — sanity spot-check that the standard
annotations exist in the magic bodies:

```
rg -n '// waitLSQ|// SPM settle|// SPM lat|// s1c gap|// s1c 1-cycle gap' \
   pe_array.cpp | wc -l
```

Reviewers should read the hits in context: the patterns above are
approximate (they flag the most frequent legal-ish violations) and do not
replace a `gendp-isa-reviewer` pass. False positives around branch labels
and multi-line expressions should be dismissed manually.

## 7. AC-9 / AC-10 Frozen Reference Trace

`scripts/gwfa_run_validation.sh` does not exist in this repo; the validation
driver is `scripts/gwfa_check_correctness.py`. The frozen oracle is a
multi-file set committed under `tests/frozen/plan3c_pre_l6a/` directly
before `l6a` lands. It has four components:

1. **Mode-1 score baseline** — `mode1_t56_scores.txt`, produced by
   `python3 scripts/gwfa_check_correctness.py 1 -t 56`. First-line
   pass/fail regression check; must stay at `15 passed, 0 failed out of
   15` across every m32..m39 lowering.
2. **Mode-2 score baseline** — `mode2_t56_scores.txt`, produced by
   `python3 scripts/gwfa_check_correctness.py 2 -t 56`. Full 295-case
   regression check; must stay at `295 passed, 0 failed out of 295`
   across every cluster gate and the final exit gate.
3. **Wavefront trace** — `wfDebug_HEAD.txt`, copied from `wfDebug.txt`
   after `python3 scripts/gwfa_check_correctness.py 3`. Per-step
   `[gfa_ed_step]` / `Z` / `WF` lines covering case 0. Any m33/m35/m37
   lowering that changes PE-visible wavefront evolution on case 0
   shows up as a byte-level diff here.
4. **Per-magic observable snapshots** — `plan3c_snapshot_m33.txt`,
   `plan3c_snapshot_m35.txt`, `plan3c_snapshot_m37.txt`, produced by
   `scripts/plan3c_capture_snapshot.sh`. The snapshot is emitted by
   three `#ifdef PLAN3C_TRACE_SNAPSHOT` blocks at the exits of m33,
   m35, m37 in `pe_array.cpp` and dumps:
   - **m33**: per-PE `MERGE_META[5..12]`; `s1c[8..23]`; and
     per-PE `a_src[0..1]` / `a_tile[0..1]` / `b_src[0..1]` / `b_tile[0..1]`
     (the 4 MM source ranges loaded into A0/A1/B0/B1 tile buffers).
   - **m35**: per-PE `out_n` / `mm_dst` / `spm_src`; `s1c[0..7]`;
     `mm_out` / exit `cum` / `max_words`.
   - **m37**: `a_sp[0..4]` at `s1c[40..44]` / `b_sp[0..4]` at
     `s1c[45..49]`; `s1c[148..152]`; per-PE `MERGE_META[4..15]`; per-PE
     tile sizes `s1c[50+pe]/s1c[54+pe]/s1c[58+pe]/s1c[62+pe]`; per-PE
     tile sources `s1c[66+pe]/s1c[70+pe]`.

The snapshot is compiled in via `make plan3c_snap=1` (new target added by
this artifact; gated by the `PLAN3C_TRACE_SNAPSHOT` preprocessor symbol so
the default production build stays untouched). `plan3c_capture_snapshot.sh`
drives a single-case run, moves the snapshot files into
`tests/frozen/plan3c_pre_l6a/`, then restores a default `sim` build.

AC-9 / AC-10 verification after each lowered magic:

- **After m33 (l6b)**: rerun the capture script and diff the new
  `plan3c_snapshot_m33.txt` against the committed baseline. Byte-equal =
  PE-visible observables preserved. Any diff = AC-9 failure.
- **After m35 (l6d)**: same, for `plan3c_snapshot_m35.txt`.
- **After m37 (l6f)**: same, for `plan3c_snapshot_m37.txt`. This is also
  the AC-10 `a_sp`/`b_sp` byte-equality oracle.
- **After m32 (l6a), m34 (l6c), m36 (l6e), m38 (l6g), m39 (l6h)**: no
  dedicated snapshot file needed, but the same mode-1 and mode-2 score
  gates still apply. m36 does touch `s1c[154..158]` / `s1c[159..162]`
  read by m37, so the post-m37 snapshot diff indirectly gates m36 too.

Additional opt-in instrumentation already present in the tree: m32 at
`pe_array.cpp:6429..6463` has `PLAN2A_SEAM_ASSERT` assertions comparing
`s1c[176..191]` against the mm first/last intv values per PE; this is the
AC-6 seam-contract enforcement path and is orthogonal to
`PLAN3C_TRACE_SNAPSHOT`.
