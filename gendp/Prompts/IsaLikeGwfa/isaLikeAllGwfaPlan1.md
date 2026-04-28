# GWFA ISA-Like Rewrite Plan 1: Structural Changes (CODE IMPLEMENTED, PENDING REVIEW)

## Goal Description

Perform all major structural changes to GWFA magic instructions: delete deprecated magics, restructure algorithms (binary search interleaving, seam merge, mid-diagonal start, fin0_load_batch two-loop), convert scalar loops to mvdq round-robin, and begin ISA-style patterns (gotos, register usage). Each magic verified after change.

## Status: CODE IMPLEMENTED, PENDING REVIEW (9 RLCR rounds)

Structural changes implemented and passing mode 1 (15/15). Full ISA review and mode 2 verification deferred to Plans 2-3d. Residual structural items identified and tracked in Plan 2a/2b/2c.

## Acceptance Criteria

- AC-1: Correctness preserved (mode 1 after each change) — MET
- AC-2: Deprecated magics 2, 10, 26 deleted with full cleanup — MET
- AC-3: mvdq round-robin streaming where specified — MOSTLY MET (PE 19 deferred to Plan 2)
- AC-4: All specific per-magic structural requirements addressed — MOSTLY MET (residual items deferred to Plan 2)
- AC-5: Barrier added between magic 7→8 in instruction generator — MET
- AC-6: SORT_BIN_REG renamed to SORT_BIN_SPM — MET

## Completed Tasks (by magic)

### Cleanup (M1)
- ✅ Delete controller magics 2, 10, 26 + clean references
- ✅ Add barrier between magic 7→8 in instruction generator (4 locations)
- ✅ Rename SORT_BIN_REG → SORT_BIN_SPM across sys_def.h, pe_array.cpp, pe.cpp
- ✅ Remove dead merge_split_and_load function (after 28/37 inlining)

### Controller structural changes
- ✅ Magic 16: min/max→branches, goto clamping, division→shift, use gr[] directly
- ✅ Magic 18: gwfa_get_mm_ha_off/ha_dirty_off → constexpr constants
- ✅ Magic 19: flip loop (bins outer, PEs inner), all locals→gr[7-10]
- ✅ Magic 20: two-loop fin0_load_batch (round-robin + fallback), remove bitmap, remove return value, lambda→F0B_ASSIGN macro
- ✅ Magic 24: full-tile fast path + peeled final iteration, interleaved mvdq
- ✅ Magic 25: true chunk-outer PE-inner round-robin scatter writeback
- ✅ Magic 28: remove sanity check, inline merge_split_and_load with interleaved binary search across PEs, mvdq tile loads, waitLSQ comments
- ✅ Magic 29: interleaved mvdq tile loads (diag BUF0/1, intv BUF0/1)
- ✅ Magic 30: mvdq_copy for dedup reload, std::min→branch
- ✅ Magic 31: chunk-outer PE-inner round-robin writeback
- ✅ Magic 32: mid-diagonal start boundary max-merge, local variable for intv seam merge (no MM read-back), bulk mvdq diag+intv gather with PE-seam-only fixup
- ✅ Magic 33: separate nested mm[s1c[X]] into register load + mm[reg], mvdq_copy for reload, std::min→branch
- ✅ Magic 34: already ISA-like (reference pattern)
- ✅ Magic 35: chunk-outer PE-inner round-robin merge writeback
- ✅ Magic 36: remove sorted-output check, mid-diagonal start (nominal splits, no forward scan)
- ✅ Magic 37: inline merge_split_and_load with interleaved binary search
- ✅ Magic 38: fuse lo/hi binary search into single interleaved loop, waitLSQ comments
- ✅ Magic 39: restructured to use gr[] directly, division→shift

### PE structural changes
- ✅ PE 20: two-element contiguous (vd,k,vd,k) mvd loads with peel
- ✅ PE 21: two-element mvd scatter with peel
- ✅ PE 22: goto-based restructure (m22_top/m22_eval/m22_merge/m22_done), buffer transitions labeled
- ✅ PE 23: lambda→M23_RD/M23_RI/M23_PI inline macros, M23_SAVE split into M23_SAVE_OUT + M23_SAVE_RESUME

### std::min/max cleanup
- ✅ Controller 28: 6 instances replaced with branch-style
- ✅ Controller 29: 2 instances replaced
- ✅ Controller 34: 3 instances replaced

## Known Issues Deferred to Plan 2

- Controller 20: arc stride (3-word) prevents pure mvdq; SPM latency masking and half-registers not done
- Controller 31: autoincrement cursors not implemented
- Controller 32: first/last intv to s1c not done (uses local variable instead)
- PE 19: half-registers and mvd not done (still local-variable code)
- PE 22: buffer-switch checks still in hot loop (3 restructure attempts failed)
- PE 23: broad M23_SAVE_RESUME, no mvd for merge writes, no SPM latency gaps
- Remaining std::min/max in controllers 28/29/37

## BitLessons Discovered

- **BL-20260413-drain-budget**: PE merge drain must use unified loop, not separate drain paths
- **BL-20260413-gr-clobber**: gr registers live across magic boundaries must be saved to s1c
- **BL-20260413-pe-global-base**: PE merge boundary tracking needs global output base
- **BL-20260416-m32-gather-dep**: Controller 32 gather has sequential destination dependency; PE-serial bulk mvdq is correct form
- **SORT_BIN_REGION_SIZE corruption**: replace_all for BIN_REG→BIN_SPM accidentally caught REGION substring

## Commits (chronological)

1. `d719a69` — M1: cleanup deprecated magics, barrier, rename
2. `ee665b6` — M2 partial: structural changes to controller 28, 32, 36, 38
3. `e0ec8a7` — Restructure controller 28: inlined interleaved binary search
4. `a28e747` — M4: structural changes to controller 16, 18, 19, 33
5. `6f2678c` — Restructure controller 20: two-loop fin0_load_batch
6. `6318deb` — PE 23 lambda→macro restructure
7. `4e8b3a2` — M5 partial: mvdq for controller 24/25, fix REGION_SIZE
8. `7ab721e` — PE 22 goto, PE 23 save split, controller 20 lambda removal
9. `1775412` — Round 4: mvdq fixes for 25/30/31/33/35, controller 37 inline, 39 restructure
10. `4c5e798` — PE 20/21 two-element mvd, controller 28 tile load mvdq
11. `398821f` — ISA-lower controller 16/19/39 + gr-clobber fix
12. `0e51a2b` — Controller 29 interleaved mvdq tile loads
13. `e202b4e` — Controller 32 bulk mvdq gather, controller 24 peel, dead code removal
14. `af3b08f` — Controller 32 intv bulk mvdq, PE 20 contiguous, std::min cleanup

--- Original Design Draft Start ---

(See isaLikeAllGwfaPrompt.md for full draft)

--- Original Design Draft End ---
