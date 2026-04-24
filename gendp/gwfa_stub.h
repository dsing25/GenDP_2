// gwfa_stub.h -- minimal stubs for GWFA kernel symbols when the
// kernel/Gwfa submodule is not present. Used only when -DGWFA_BUILD
// is NOT set. Every stub aborts at runtime so any caller that
// reaches a GWFA code path without the real kernel hits a clear
// error rather than mis-executing. Linker-clean because all stubs
// are `static inline` and therefore instantiated per-TU without
// requiring a gwfa_*.o.
#ifndef GWFA_STUB_H
#define GWFA_STUB_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>

// Constants + typedefs mirrored from the real kernel/Gwfa/gwfa.h so
// translation units that reference them still compile without the
// submodule.
#ifndef GWFA_START_V
#define GWFA_START_V  0
#endif
#ifndef GWFA_END_V
#define GWFA_END_V    2
#endif
#ifndef GWF_DIAG_SHIFT
#define GWF_DIAG_SHIFT 0x4000
#endif

typedef struct {
    uint16_t v, w;
    int32_t ow;
} subgfa_arc_t;

typedef struct {
    uint32_t n_vtx;
    uint32_t n_arc;
    uint32_t *graphSeq;
    uint32_t *seq_off;
    int32_t *seq_len;
    subgfa_arc_t *arc;
    uint32_t *arc_off;
} subgfa_subgraph_t;

#ifdef __cplusplus
extern "C" {
#endif

static inline void gwfa_stub_abort(const char *name) {
    fprintf(stderr,
        "[gwfa-stub] %s called in a build that does not include the "
        "kernel/Gwfa submodule. Rebuild after `git submodule update "
        "--init kernel/Gwfa`.\n", name);
    exit(-1);
}

static inline int *gwfa_get_mm(void) { gwfa_stub_abort("gwfa_get_mm"); return 0; }
static inline int   gwfa_get_score(void) { gwfa_stub_abort("gwfa_get_score"); return 0; }
static inline void  gwfa_set_score(int32_t) { gwfa_stub_abort("gwfa_set_score"); }
static inline int32_t gwfa_get_n_a(void) { gwfa_stub_abort("gwfa_get_n_a"); return 0; }
static inline size_t  gwfa_get_intv_n(void) { gwfa_stub_abort("gwfa_get_intv_n"); return 0; }
static inline int32_t gwfa_get_s_a_mm_off(void) { gwfa_stub_abort("gwfa_get_s_a_mm_off"); return 0; }
static inline int32_t gwfa_get_mm_intv_off(void) { gwfa_stub_abort("gwfa_get_mm_intv_off"); return 0; }
static inline int32_t gwfa_get_mm_A_off(void) { gwfa_stub_abort("gwfa_get_mm_A_off"); return 0; }
static inline int32_t gwfa_get_s_B_a_mm_off(void) { gwfa_stub_abort("gwfa_get_s_B_a_mm_off"); return 0; }
static inline void gwfa_init(int32_t, const uint32_t*, const subgfa_subgraph_t*, int) { gwfa_stub_abort("gwfa_init"); }
static inline int  gwfa_begin_step(void) { gwfa_stub_abort("gwfa_begin_step"); return 0; }
static inline void gwfa_debug_step(int) { gwfa_stub_abort("gwfa_debug_step"); }
// gwfa_dbg_level() is a local helper defined in pe_array.cpp, not a
// real GWFA API. Deliberately not stubbed here.
static inline void gwfa_finalize_sync(int32_t, size_t) { gwfa_stub_abort("gwfa_finalize_sync"); }
static inline void gwfa_sync_counters(int32_t, uint32_t, uint32_t, uint32_t, uint32_t) { gwfa_stub_abort("gwfa_sync_counters"); }
static inline void gwfa_set_ha_n_dirty(uint32_t) { gwfa_stub_abort("gwfa_set_ha_n_dirty"); }
static inline void gwfa_tile_compute(int*) { gwfa_stub_abort("gwfa_tile_compute"); }
static inline void gwfa_reset_mm(void) { gwfa_stub_abort("gwfa_reset_mm"); }

#ifdef __cplusplus
}
#endif

#endif
