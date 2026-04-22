# Plan 2c Audit Matrix

Sibling artifact to `isaLikeAllGwfaPlan2cH.md`. Covers the 12 ISA-like rules × 23
in-scope GWFA magics (18 controller + 5 PE = 276 cells).

Vocabulary: `pass` | `fix-required` | `fix-preferred` | `waive:<reason>` |
`defer:rule12-pe-compute` (PE rule 12 only). Citations use magic-id + subroutine name.

## Controller Magics (18 × 12 = 216 cells)

| Magic | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | R11 | R12 |
|-------|----|----|----|----|----|----|----|----|----|-----|-----|-----|
| 16 | fix-preferred (m16, setup) | pass | pass | pass | pass | waive:no-spm-read (m16, setup) | waive:no-mm-s2-load (m16, setup) | pass (m16 R8, d098372) | waive:no-bulk-transfer (m16, setup) | waive:no-minmax (m16, setup) | pass | pass |
| 18 | fix-preferred (m18, fin0_writeback) | fix-preferred (m18, fin0_writeback) | pass | fix-preferred (m18, fin0_writeback) | pass | pass (m18 R6 phase1) | waive:no-mm-s2-load (m18, fin0_writeback) | pass | waive:queue-writeback-pattern (m18, fin0_writeback) | waive:no-minmax (m18, fin0_writeback) | pass | pass |
| 19 | pass | pass (m19 R2 by gap) | pass | fix-preferred (m19, prefix_sum) | pass | pass (m19 R6) | waive:no-mm-s2-load (m19, prefix_sum) | pass (m19 R8) | waive:metadata-prefix-only (m19, prefix_sum) | waive:no-minmax (m19, prefix_sum) | pass | pass |
| 20 | pass (m20 R1 F0B_ASSIGN macro inlined at both sites; no helper) | fix-preferred (m20, fin0_load_batch) | pass (m20 R3 cursor/total_fin0/pe_rr locals removed; pe_rr in gr[2]) | pass (m20 R4 arc-loop label/goto) | pass | pass | pass (m20 R7 S2+HA) | fix-preferred (m20, fin0_load_batch) | pass | waive:no-minmax (m20, fin0_load_batch) | pass (m20 R11 F0B_ASSIGN macro deleted; no helper macro remains) | pass |
| 24 | fix-required (m24, scatter_load) | pass | fix-required (m24, scatter_load) | fix-required (m24, scatter_load) | pass | waive:no-spm-read (m24, scatter_load) | waive:bulk-copy-only (m24, scatter_load) | waive:no-s1c-load (m24, scatter_load) | pass | waive:no-minmax (m24, scatter_load) | pass | pass |
| 25 | fix-preferred (m25, scatter_wb) | pass | fix-preferred (m25, scatter_wb) | fix-preferred (m25, scatter_wb) | pass | pass (m25 R6) | waive:bulk-copy-only (m25, scatter_wb) | pass (m25 R8) | pass | waive:no-minmax (m25, scatter_wb) | pass | pass |
| 28 | fix-preferred (m28, diag_split_load) | fix-preferred (m28, diag_split_load) | pass (m28 R3 Stage-B COMPLETE Round 16: bs_lo/bs_hi/bs_target → s1c[0..8] Round 12; a_sp/b_sp → s1c[40..49]; tile arrays a0s/a1s/b0s/b1s → s1c[50..65]; source arrays a_srcs/b_srcs → s1c[66..73]. All original R3 arrays migrated; scalar per-iter locals remain as transient scratch within single ISA regions.) | pass (m28 R4/R9 label/goto for while + per-p update branches) | pass | waive:no-spm-read (m28, diag_split_load) | pass (m28 R7 waitLSQ+NOP) | fix-preferred (m28, diag_split_load) | pass | waive:no-minmax (m28, diag_split_load) | pass | pass |
| 29 | fix-preferred (m29, dedup_split_load) | pass | fix-preferred (m29, dedup_split_load) | fix-preferred (m29, dedup_split_load) | pass | waive:no-spm-read (m29, dedup_split_load) | waive:bulk-copy-only (m29, dedup_split_load) | pass (m29 R8 natural-gap) | pass | waive:no-minmax (m29, dedup_split_load) | fix-preferred (m29, dedup_split_load) | pass |
| 30 | fix-preferred (m30, dedup_reload) | pass | fix-preferred (m30, dedup_reload) | fix-preferred (m30, dedup_reload) | pass | pass (m30 R6) | waive:bulk-copy-only (m30, dedup_reload) | pass (m30 R8) | pass (m30 R9 chunk-outer) | waive:no-minmax (m30, dedup_reload) | pass | pass |
| 31 | fix-preferred (m31, dedup_wb) | pass (m31 R2 chain) | fix-preferred (m31 R3 nds/d_curs/nis/i_curs local arrays — reviewer P2) | fix-preferred (m31, dedup_wb) | pass | pass | waive:no-mm-s2-load (m31, dedup_wb) | pass (m31 R8 chain) | pass | waive:no-minmax (m31, dedup_wb) | fix-preferred (m31 R11 pre-compute arrays — reviewer P2) | pass |
| 32 | fix-preferred (m32, dedup_finalize) | pass | fix-preferred (m32, dedup_finalize) | fix-preferred (m32, dedup_finalize) | pass | waive:no-spm-read (m32, dedup_finalize) | pass (m32 R7) | pass (m32 R8) | pass | waive:no-minmax (m32, dedup_finalize) | pass | pass |
| 33 | fix-preferred (m33, merge_reload) | pass | fix-preferred (m33, merge_reload) | fix-preferred (m33, merge_reload) | pass | pass (m33 R6) | waive:bulk-copy-only (m33, merge_reload) | pass (m33 R8) | pass (m33 R9 chunk-outer) | waive:no-minmax (m33, merge_reload) | pass | pass |
| 34 | fix-required (m34, sort_tile_load) | pass | fix-required (m34, sort_tile_load) | fix-required (m34, sort_tile_load) | pass | waive:no-spm-read (m34, sort_tile_load) | waive:bulk-copy-only (m34, sort_tile_load) | waive:no-s1c-load (m34, sort_tile_load) | pass | waive:no-minmax (m34, sort_tile_load) | pass | pass |
| 35 | fix-preferred (m35, merge_wb) | pass | fix-preferred (m35, merge_wb) | fix-preferred (m35, merge_wb) | pass | pass (m35 R6) | waive:bulk-copy-only (m35, merge_wb) | pass (m35 R8) | pass | waive:no-minmax (m35, merge_wb) | pass | pass |
| 36 | fix-preferred (m36, diag_finalize) | pass | fix-preferred (m36, diag_finalize) | fix-preferred (m36, diag_finalize) | pass | waive:no-spm-read (m36, diag_finalize) | pass (m36 R7) | pass (m36 R8) | waive:no-bulk-transfer (m36, diag_finalize) | waive:no-minmax (m36, diag_finalize) | pass | pass |
| 37 | fix-preferred (m37, intv_split_load) | fix-preferred (m37, intv_split_load) | fix-preferred (m37 R3 residual: a_sp/b_sp/a0s/a1s/b0s/b1s/a_srcs/b_srcs/pts/bvd0..2 still locals; bs_lo/bs_hi/bs_tgt migrated to s1c[0..8] Round 12) | pass (m37 R4/R9 label/goto for while + per-p update branches) | pass | waive:no-spm-read (m37, intv_split_load) | pass (m37 R7 waitLSQ+NOP) | fix-preferred (m37, intv_split_load) | pass (m37 R9 chunk-outer) | waive:no-minmax (m37, intv_split_load) | pass | pass |
| 38 | fix-preferred (m38, intv_finalize) | pass | pass (m38 R3 closeout Round 16: all 7 finalize-path C++ locals migrated — Round 11 bs state → s1c[163..174]; Round 12 intv_n re-read; Round 15 best_hi/best_lo/hp/lp → mgr[3]/mgr[4]/mgr[11] + head intv_n → mgr[5]; Round 16 merge_skipped eliminated via delayed s1c[149] store + re-read at second decision, ib eliminated via s1c[152] re-read into mgr[4] at each mm load site) | pass (m38 R4/R9 label/goto for while + update branches) | pass | waive:no-spm-read (m38, intv_finalize) | pass (m38 R7 waitLSQ+NOP) | pass (m38 R8 s1c stage) | waive:no-bulk-transfer (m38, intv_finalize) | waive:no-minmax (m38, intv_finalize) | pass | pass |
| 39 | pass | pass | pass | pass | pass | waive:no-spm-read (m39, intv_sort_setup) | waive:no-mm-s2-load (m39, intv_sort_setup) | pass | waive:no-bulk-transfer (m39, intv_sort_setup) | waive:no-minmax (m39, intv_sort_setup) | pass | pass |

### Controller citations

- **R1 (m16, setup)**: fix-required — `gwfa_sync_counters()` and `gwfa_get_intv_n()` still compress non-ISA helper work into the magic body.
- **R1 (m18, fin0_writeback)**: fix-required — writeback phases end with non-ISA sync helpers instead of fully lowered controller ops.
- **R1 (m20, fin0_load_batch)**: pass (Round 9) — `F0B_ASSIGN` macro deleted; body inlined at f0b_rr and f0b_mv call sites with unique labels. Helper escape hatch eliminated.
- **R1 (m24, scatter_load), R1 (m25, scatter_wb), R1 (m34, sort_tile_load), R1 (m35, merge_wb)**: fix-required — compact loop bodies still pack bound checks and transfer sizing into single C++ statements rather than one ISA op per line.
- **R1 (m28, diag_split_load), R1 (m29, dedup_split_load), R1 (m30, dedup_reload), R1 (m31, dedup_wb), R1 (m32, dedup_finalize), R1 (m33, merge_reload), R1 (m36, diag_finalize), R1 (m37, intv_split_load), R1 (m38, intv_finalize)**: fix-required — split/gather logic still relies on multi-action statements and helper-shaped copy loops that are not line-for-line ISA.
- **R2 (m18, fin0_writeback)**: fix-required — address-build chains in A/B/HA writeback leave adjacent dependent register ops with no clean VLIW pairing boundary.
- **R2 (m19, prefix_sum)**: fix-required — prefix accumulation uses adjacent load/add pairs such as `s1c -> gr -> gr` with no slot-safe spacer.
- **R2 (m20, fin0_load_batch)**: fix-required — assignment and HA-fill paths contain dependent register chains that are not pair-safe once lowered.
- **R2 (m28, diag_split_load)**: fix-required — binary-search midpoint and bound-update chains are still scheduled as adjacent dependent ops.
- **R2 (m31, dedup_wb)**: fix-required — `s1c`-fed cursor arithmetic builds dependent `gr[11]` chains without an explicit slot split.
- **R2 (m37, intv_split_load)**: fix-required — split-point search and tile-setup address chains still have adjacent RAW-sensitive register updates.
- **R3 (m20, fin0_load_batch)**: fix-required — `cursor`, `pe_rr`, hash temporaries, and other locals carry live architectural progress outside `gr[]/s1c[]/spm[]/mm[]`.
- **R3 (m24, scatter_load), R3 (m25, scatter_wb), R3 (m28, diag_split_load), R3 (m29, dedup_split_load), R3 (m30, dedup_reload), R3 (m32, dedup_finalize), R3 (m33, merge_reload), R3 (m34, sort_tile_load), R3 (m35, merge_wb), R3 (m36, diag_finalize), R3 (m37, intv_split_load), R3 (m38, intv_finalize)**: fix-required — runtime locals and local arrays (`tile_ns`, split arrays, cursors, carry state, seam trackers) hold state that must live in architectural storage.
- **R4 (m18, fin0_writeback), R4 (m19, prefix_sum), R4 (m20, fin0_load_batch), R4 (m24, scatter_load), R4 (m25, scatter_wb), R4 (m28, diag_split_load), R4 (m29, dedup_split_load), R4 (m30, dedup_reload), R4 (m31, dedup_wb), R4 (m32, dedup_finalize), R4 (m33, merge_reload), R4 (m34, sort_tile_load), R4 (m35, merge_wb), R4 (m36, diag_finalize), R4 (m37, intv_split_load), R4 (m38, intv_finalize)**: fix-required — runtime `if`/`for`/`while`/`continue` control flow survives instead of label/goto or compile-time unrolling.
- **R6 (m16, setup), R6 (m24, scatter_load), R6 (m28, diag_split_load), R6 (m29, dedup_split_load), R6 (m32, dedup_finalize), R6 (m34, sort_tile_load), R6 (m36, diag_finalize), R6 (m37, intv_split_load), R6 (m38, intv_finalize), R6 (m39, intv_sort_setup)**: waive:no-spm-read — these magics do not execute controller SPM reads outside bulk-helper endpoints.
- **R6 (m18, fin0_writeback)**: fix-required — phase-1 metadata pulls and HA bucket copies still read `spm[]` directly into executable logic or MM writes without ISA-visible load staging.
- **R6 (m19, prefix_sum)**: fix-required — sort-bin count collection reads `spm[]` counts directly into accumulation logic with no 2-cycle separation.
- **R6 (m25, scatter_wb), R6 (m30, dedup_reload), R6 (m33, merge_reload), R6 (m35, merge_wb)**: fix-required — executable `spm[]` metadata reads happen directly in conditions and sizing logic without controller SPM-latency staging.
- **R7 (m16, setup), R7 (m18, fin0_writeback), R7 (m19, prefix_sum), R7 (m31, dedup_wb), R7 (m39, intv_sort_setup)**: waive:no-mm-s2-load — no executable MM/S2 read chain exists in these magics.
- **R7 (m24, scatter_load), R7 (m25, scatter_wb), R7 (m29, dedup_split_load), R7 (m30, dedup_reload), R7 (m33, merge_reload), R7 (m34, sort_tile_load), R7 (m35, merge_wb)**: waive:bulk-copy-only — MM appears only as a `mvdq_copy` endpoint, not as a direct executable MM/S2 read that needs `waitLSQ` staging.
- **R7 (m20, fin0_load_batch)**: fix-required — pass-2 `s2->buffer[...]` loads and pass-3 HA `mm[...]` bucket reads remain direct executable loads without per-load `// waitLSQ` staging.
- **R7 (m28, diag_split_load), R7 (m37, intv_split_load), R7 (m38, intv_finalize)**: fix-required — binary-search MM reads are only tagged by comment; the values are still consumed immediately with no real cycle-separated LSQ wait.
- **R7 (m32, dedup_finalize), R7 (m36, diag_finalize)**: fix-required — seam/boundary MM reads feed compare/merge logic directly without `// waitLSQ` and without staged consumer separation.
- **R8 (m24, scatter_load), R8 (m34, sort_tile_load)**: waive:no-s1c-load — these magics do not consume `s1c[]`.
- **R8 (m16, setup)**: fix-required — `gr[1] = s1c[151]` is branched on immediately, violating the 1-cycle S1c gap.
- **R8 (m19, prefix_sum)**: fix-required — prefix-sum loops consume freshly loaded `s1c[]` values in the next ISA slot.
- **R8 (m20, fin0_load_batch), R8 (m25, scatter_wb), R8 (m28, diag_split_load), R8 (m29, dedup_split_load), R8 (m30, dedup_reload), R8 (m31, dedup_wb), R8 (m32, dedup_finalize), R8 (m33, merge_reload), R8 (m35, merge_wb), R8 (m36, diag_finalize), R8 (m37, intv_split_load), R8 (m38, intv_finalize)**: fix-required — executable logic still reads `s1c[]` directly into conditions, local temporaries, or same-cycle arithmetic without the required one-cycle staging.
- **R9 (m16, setup), R9 (m36, diag_finalize), R9 (m38, intv_finalize), R9 (m39, intv_sort_setup)**: waive:no-bulk-transfer — these magics do not perform controller bulk streaming moves.
- **R9 (m18, fin0_writeback)**: waive:queue-writeback-pattern — A/B/HA outputs are queue/cursor driven rather than a simple contiguous bulk stream.
- **R9 (m19, prefix_sum)**: waive:metadata-prefix-only — the magic is metadata reduction, not a bulk transfer path.
- **R9 (m30, dedup_reload), R9 (m33, merge_reload)**: fix-required — reload loops remain PE-outer/per-buffer instead of interleaved round-robin `mvdq`.
- **R9 (m37, intv_split_load)**: fix-required — initial MM→SPM tile loads are still scalar per-PE copies rather than round-robin bulk `mvdq`.
- **R10 (m16, setup), R10 (m18, fin0_writeback), R10 (m19, prefix_sum), R10 (m20, fin0_load_batch), R10 (m24, scatter_load), R10 (m25, scatter_wb), R10 (m28, diag_split_load), R10 (m29, dedup_split_load), R10 (m30, dedup_reload), R10 (m31, dedup_wb), R10 (m32, dedup_finalize), R10 (m33, merge_reload), R10 (m34, sort_tile_load), R10 (m35, merge_wb), R10 (m36, diag_finalize), R10 (m37, intv_split_load), R10 (m38, intv_finalize), R10 (m39, intv_sort_setup)**: waive:no-minmax — no in-scope controller magic uses executable `std::min`/`std::max`; the only token in range is the explanatory comment in magic 33.
- **R11 (m20, fin0_load_batch)**: pass (Round 9) — `F0B_ASSIGN` helper macro deleted; no helper macro remains. Residual C++ locals inside the inlined bodies are short-lived per-iteration scratch; compiler register-allocates them. See residual R3 note below.
- **R11 (m29, dedup_split_load)**: fix-required — `M29_MVDQ` and its local-array scaffolding keep transfer state outside the architectural register/memory model.

## PE Magics (5 × 12 = 60 cells)

| Magic | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | R11 | R12 |
|-------|----|----|----|----|----|----|----|----|----|-----|-----|------|
| 19 | fix-preferred (m19, main_loop) | pass | fix-preferred (m19, main_loop) | fix-preferred (m19, hash_probe) | pass | pass (m19 R6 diag+arcmeta) | waive:no-mm-s2-load (m19, main_loop) | waive:no-s1c-load (m19, main_loop) | fix-preferred (m19, fin0_stream) | pass | fix-preferred (m19, mvi2_ld helper) | defer:rule12-pe-compute |
| 20 | fix-preferred (m20, count_loop) | pass | fix-preferred (m20, count_loop) | fix-preferred (m20, count_loop) | pass | pass (m20 R6 natural-gap) | waive:no-mm-s2-load (m20, count_loop) | waive:no-s1c-load (m20, count_loop) | fix-preferred (m20, count_loop) | pass | pass | defer:rule12-pe-compute |
| 21 | fix-preferred (m21, scatter_loop) | pass | fix-preferred (m21, scatter_loop) | fix-preferred (m21, scatter_loop) | pass | pass (m21 R6 natural-gap) | waive:no-mm-s2-load (m21, scatter_loop) | waive:no-s1c-load (m21, scatter_loop) | fix-preferred (m21, scatter_loop) | pass | pass | defer:rule12-pe-compute |
| 22 | fix-preferred (m22, emit_fast_path) | pass | fix-preferred (m22, entry_restore) | fix-preferred (m22, emit_fast_path) | pass | pass (m22 R6 emit-path) | waive:no-mm-s2-load (m22, emit_fast_path) | waive:no-s1c-load (m22, emit_fast_path) | waive:no-bulk-transfer (m22, merge_emit) | pass | pass | defer:rule12-pe-compute |
| 23 | fix-preferred (m23, state_machine) | pass | fix-preferred (m23, resume_restore) | fix-preferred (m23, state_machine) | pass | pass (m23 R6 natural-gap + in-file disposition) | waive:no-mm-s2-load (m23, state_machine) | waive:no-s1c-load (m23, state_machine) | fix-preferred (m23, intv_flush) | pass | fix-preferred (m23, M23_* macros) | defer:rule12-pe-compute |

### PE citations

- **R1 (m19, main_loop), R1 (m20, count_loop), R1 (m21, scatter_loop)**: fix-required — these loops still bundle pointer math, packed-field extraction, and counter/state updates into C++ statements instead of one ISA-visible op per source line.
- **R1 (m22, emit_fast_path), R1 (m23, state_machine)**: fix-required — the hot merge/dedup paths still rely on compound branch blocks, multi-store lines, and save/resume macros that are not line-for-line lowerable.
- **R3 (m19, main_loop), R3 (m20, count_loop), R3 (m21, scatter_loop)**: fix-required — loop progress, cursors, bin state, and debug/accounting values live in C++ locals rather than `gr[]`/`reg[]`/memory.
- **R3 (m22, entry_restore), R3 (m23, resume_restore)**: fix-required — the merge/dedup state machines keep persistent architectural state (`ai/bi/...`, `pv/pk/...`) in locals across labels and yields.
- **R4 (m19, hash_probe)**: fix-required — nested `for` + `if/else` control flow in the bucket probe and emit logic still needs label/goto lowering.
- **R4 (m20, count_loop), R4 (m21, scatter_loop)**: fix-required — both sort loops remain runtime `for`/`if` bodies instead of label-driven ISA-style control.
- **R4 (m22, emit_fast_path), R4 (m23, state_machine)**: fix-required — although both magics use labels, they still retain runtime `if` blocks and fixed-trip `for` bodies in executable logic.
- **R6 (m19, main_loop)**: fix-required — `fspm[]` loads for diag/arc metadata are consumed in the next cycle by shifts, arithmetic, and compares without the full 2-cycle SPM gap.
- **R6 (m20, count_loop), R6 (m21, scatter_loop)**: fix-required — tile/metadata SPM loads feed bin extraction and scatter address generation immediately, with no 2-cycle separation.
- **R6 (m22, emit_fast_path)**: fix-required — the hot emit path still loads `out_lo/out_hi` from SPM and stores them on the next cycle, and the entry-restore block also reuses freshly loaded metadata too early.
- **R6 (m23, resume_restore)**: fix-required — `dw/iw` are loaded from SPM and then reused almost immediately to fetch `dtn/itn`, so the restore header still violates strict SPM latency even though `M23_RD/M23_RI/M23_PI` are annotated.
- **R7 (m19, main_loop), R7 (m20, count_loop), R7 (m21, scatter_loop), R7 (m22, emit_fast_path), R7 (m23, state_machine)**: waive:no-mm-s2-load — none of the in-scope PE magics executes a direct MM/S2 read chain.
- **R8 (m19, main_loop), R8 (m20, count_loop), R8 (m21, scatter_loop), R8 (m22, emit_fast_path), R8 (m23, state_machine)**: waive:no-s1c-load — these PE magics do not read `s1c[]`.
- **R9 (m19, fin0_stream)**: fix-preferred — the FIN0 pair loads/stores are comment-tagged as `mvd` sites, but the stream is still expressed as scalar C++ accesses plus reverse-index address math.
- **R9 (m20, count_loop), R9 (m21, scatter_loop)**: fix-preferred — both sort kernels use contiguous two-element traffic shaped for `mvd`, but they are still written as scalar loads/stores rather than an explicit bulk-move idiom.
- **R9 (m22, merge_emit)**: waive:no-bulk-transfer — magic 22 is a compare-driven single-item merge, not a bulk contiguous stream.
- **R9 (m23, intv_flush)**: fix-preferred — the interval flushes are contiguous double-word stores and already tagged as `mvd` sites, but the code still emits scalar store pairs.
- **R11 (m19, mvi2_ld helper)**: fix-preferred — the swizzled 2-bit sequence fetch remains hidden behind a returning lambda rather than fully inlined ISA-like register/memory steps.
- **R11 (m23, M23_* macros)**: fix-required — `M23_RD`/`M23_RI`/`M23_PI`/`M23_SAVE*` still encapsulate control-state mutation and memory traffic behind helpers that depend on live C++ locals.

---

## Triage (c_triage)

The raw Codex audit above is the starting point. The classifications below apply
DEC-1 ("stylistic / proxy-rule findings on magics already `gendp-isa-reviewer`-clean
under 2a/2b are `fix-preferred`; land when low-risk, otherwise defer") and the
plan's explicit `fix-required` policy (semantic bugs, latency violations, missing
`// waitLSQ`, paired-slot RAW, nested indirect MM reads, runtime `while`, controller
`std::min`/`std::max`).

### True fix-required set (Plan 2c policy-match)

These are the cells where the codex classification is upheld as `fix-required`
under the plan's strict rule-violation definition:

- **R4 runtime `while`**:
  - (m28, diag_split_load_while_any_active) — `while (any_active)` at controller tick.
  - (m37, intv_split_load_binsearch) — `while (any)` binary search across PEs.
  - (m38, intv_finalize_binsearch) — `while (h_lo < h_hi || l_lo < l_hi)`.
- **R6 SPM load-to-use within 2 VLIW cycles** (controller):
  - (m18, fin0_writeback_spm_meta), (m19, prefix_sum_spm_bin_counts),
    (m25, scatter_wb_spm_meta), (m30, dedup_reload_spm_meta),
    (m33, merge_reload_spm_meta), (m35, merge_wb_spm_meta).
- **R6 SPM load-to-use within 2 VLIW cycles** (PE):
  - (m19, main_loop_fspm), (m20, count_loop_tile_meta),
    (m21, scatter_loop_tile_meta), (m22, emit_fast_path_out_lo_hi),
    (m23, resume_restore_dw_iw).
- **R7 MM/S2 load with missing `// waitLSQ` and/or insufficient cycle separation**:
  - (m20, fin0_load_batch_pass2_s2_buffer), (m20, fin0_load_batch_pass3_ha_mm),
    (m28, diag_split_load_comment_only_waitLSQ),
    (m37, intv_split_load_comment_only_waitLSQ),
    (m38, intv_finalize_comment_only_waitLSQ),
    (m32, dedup_finalize_seam_read), (m36, diag_finalize_seam_read).
- **R8 S1c load-to-use within 1 VLIW cycle**:
  - (m16, setup_s1c_151_branch_next_line) — `gr[1]=s1c[151]; if (gr[1]>=0) goto …`.
  - (m19, prefix_sum_s1c_consume),
    (m20, fin0_load_batch_s1c_consume), (m25, scatter_wb_s1c_consume),
    (m28, diag_split_load_s1c_consume), (m29, dedup_split_load_s1c_consume),
    (m30, dedup_reload_s1c_consume), (m31, dedup_wb_s1c_consume),
    (m32, dedup_finalize_s1c_consume), (m33, merge_reload_s1c_consume),
    (m35, merge_wb_s1c_consume), (m36, diag_finalize_s1c_consume),
    (m37, intv_split_load_s1c_consume), (m38, intv_finalize_s1c_consume).
- **R2 paired-slot RAW (controller)**:
  - (m18, fin0_writeback_addr_build), (m19, prefix_sum_s1c_add_chain),
    (m20, fin0_load_batch_assign_chain), (m28, diag_split_load_binsearch_chain),
    (m31, dedup_wb_s1c_gr11_chain), (m37, intv_split_load_search_chain).
- **R9 bulk-move lowering required** (contiguous, feasible):
  - (m30, dedup_reload_pe_outer_per_buffer),
    (m33, merge_reload_pe_outer_per_buffer),
    (m37, intv_split_load_scalar_per_pe).

### Demoted to `fix-preferred` per DEC-1 (stylistic / already reviewer-clean)

- Controller R1 (m16, m18, m20, m24, m25, m28, m29, m30, m31, m32, m33, m34, m35,
  m36, m37, m38): the "compound source statements" finding is a proxy for ISA
  lowering. These magic bodies were accepted by `gendp-isa-reviewer` in 2a/2b; the
  per-statement ISA decomposition is a mechanical lowering that belongs to a
  follow-on ISA-generator pass, not a 2c semantic rewrite. Demote to
  `fix-preferred`; land only in-place when a magic is already being touched for a
  true fix-required bug.
- Controller R3 (m20, m24, m25, m28, m29, m30, m32, m33, m34, m35, m36, m37, m38):
  "C++ locals carry state across ISA lines" — mostly refers to loop-index `int i`,
  `pe_rr`, `cursor` and similar counters that would be lowered to `gr[]` by the ISA
  generator. Same DEC-1 demote to `fix-preferred`.
- Controller R4 non-`while` findings (m18, m19, m20, m24, m25, m29, m30, m31, m32,
  m33, m34, m35, m36): `if`/`for` inside a macro-unrolled PE loop or a
  constexpr-bounded tile loop that the reviewer accepted. Demote to
  `fix-preferred`. (m28/m37/m38 runtime `while` remains `fix-required`.)
- Controller R11 (m20, m29): `F0B_ASSIGN` and `M29_MVDQ` helper macros were
  accepted by the reviewer in 2a/2b. Demote to `fix-preferred`.
- PE R1 (m19, m20, m21, m22, m23): compound source statements; same DEC-1
  rationale. Demote to `fix-preferred`.
- PE R3 (m19, m20, m21, m22, m23) and PE R4 (m19, m20, m21, m22, m23) non-latency
  findings: loop-carried counters and executable-logic `if` blocks accepted by the
  reviewer in 2a/2b. Demote to `fix-preferred`. (The true SPM-latency R6
  violations in every PE magic remain `fix-required`.)
- PE R11 (m23, M23_* macros): already reviewer-accepted in 2b; demote to
  `fix-preferred`.

### Waives unchanged from Codex

All `waive:no-minmax`, `waive:no-spm-read`, `waive:no-mm-s2-load`,
`waive:no-s1c-load`, `waive:bulk-copy-only`, `waive:queue-writeback-pattern`,
`waive:metadata-prefix-only`, `waive:no-bulk-transfer`, `waive:no-s1c-load` (PE)
are accepted as written — each is a "rule does not apply to this magic" finding.

### Defer (rule 12, PE only)

All PE rule-12 cells are `defer:rule12-pe-compute` per AC-11; correct as tagged.

### Round-1 intent (subset of true fix-required)

Given the 23-magic × per-magic-commit cadence is multi-round work, Round 1
tackles a subset of the true `fix-required` set focused on single-line latency
inserts (lowest-risk) plus the matrix artifact itself. Remaining
`fix-required` items are carried into subsequent rounds in plan execution order
(16, 18, 20, 34, 19, 24, 25, 28, 37, 38, 39, 29, 30, 31+32, 33, 35, 36 for
controllers; then PE 19, 20, 21, 22, 23). `fix-preferred` items from DEC-1
demotion are deferred with rationale: they will land opportunistically when a
magic is already being touched for a true fix.

### Classification counts (post-triage)

- `pass`: unchanged from Codex totals.
- True `fix-required`: R4 while ×3, R6 SPM ×11, R7 MM/S2 ×7, R8 S1c ×14, R2
  paired-slot RAW ×6, R9 bulk-lowering ×3. Total ≈ **44 true fix-required**.
- `fix-preferred` (raised via DEC-1 demotion): roughly **62 cells** moved from
  raw-Codex `fix-required` to `fix-preferred` plus the 4 native
  `fix-preferred`.
- `waive:*`: 48 controller + 11 PE = **59 cells**.
- `defer:rule12-pe-compute`: **5 cells** (PE rule 12).

(The cell-status column in the tables above remains the Codex raw classification
for traceability; the triage set above is the authoritative plan-of-record for
Round 1+ fixes. When a magic is fixed, the fixer updates the relevant cell in
place to `pass` (with a trailing evidence citation) or a `waive:<reason>` tag and
records evidence.)

### Round 1 closed cells

- **R8 (m16, setup_s1c_151_branch_next_line)**: `pass` — Round 1 commit.
  Inserted `//NOP` between `gr[1] = s1c[151]` load and branch to satisfy the
  1-cycle S1c gap. Validation: `make` clean; `mode 1 -t 56 = 15/15`;
  `gendp-isa-reviewer` zero unwaived P0/P1 on m16.
