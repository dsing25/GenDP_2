#ifndef GSSW_SIMD4_H
#define GSSW_SIMD4_H
//
// 4-wide 8-bit SIMD wrappers operating on uint32_t.
// Mimics the SSE intrinsics used by the GSSW kernel but at the lane
// count GenDP actually provides (4 × 8 bits packed in a 32-bit reg).
//
// Lane layout: lane i occupies bits [i*8, i*8+7] (little-endian byte
// order within the uint32_t).
//
// These are for testing only. They emulate what GenDP's SIMD ALU
// (execute_8bit) does, so the kernel's striped layout + cross-lane
// dependencies can be validated before lowering to GenDP ISA.
//

#include <cstdint>

static inline uint32_t gssw4_setzero(void) {
    return 0u;
}

// Broadcast a byte to all 4 lanes.
static inline uint32_t gssw4_set1_epi8(uint8_t x) {
    return (uint32_t)x * 0x01010101u;
}

// Saturating unsigned 8-bit add per lane.
static inline uint32_t gssw4_adds_epu8(uint32_t a, uint32_t b) {
    uint32_t r = 0;
    for (int i = 0; i < 4; i++) {
        unsigned la = (a >> (i * 8)) & 0xFFu;
        unsigned lb = (b >> (i * 8)) & 0xFFu;
        unsigned s  = la + lb;
        if (s > 255u) s = 255u;
        r |= s << (i * 8);
    }
    return r;
}

// Saturating unsigned 8-bit subtract per lane.
static inline uint32_t gssw4_subs_epu8(uint32_t a, uint32_t b) {
    uint32_t r = 0;
    for (int i = 0; i < 4; i++) {
        unsigned la = (a >> (i * 8)) & 0xFFu;
        unsigned lb = (b >> (i * 8)) & 0xFFu;
        unsigned s  = (la > lb) ? (la - lb) : 0u;
        r |= s << (i * 8);
    }
    return r;
}

// Unsigned 8-bit max per lane.
static inline uint32_t gssw4_max_epu8(uint32_t a, uint32_t b) {
    uint32_t r = 0;
    for (int i = 0; i < 4; i++) {
        unsigned la = (a >> (i * 8)) & 0xFFu;
        unsigned lb = (b >> (i * 8)) & 0xFFu;
        unsigned m  = (la > lb) ? la : lb;
        r |= m << (i * 8);
    }
    return r;
}

// Cross-lane byte shift left (matches _mm_slli_si128 semantics at
// 4-wide). Lane i gets lane i-n; vacated low bytes filled with 0.
static inline uint32_t gssw4_slli_si128(uint32_t v, int n) {
    if (n <= 0) return v;
    if (n >= 4) return 0u;
    return v << (n * 8);
}

// Cross-lane byte shift right.
static inline uint32_t gssw4_srli_si128(uint32_t v, int n) {
    if (n <= 0) return v;
    if (n >= 4) return 0u;
    return v >> (n * 8);
}

// Unsigned 8-bit compare-greater-than: 0xFF per lane if a>b else 0.
static inline uint32_t gssw4_cmpgt_epu8(uint32_t a, uint32_t b) {
    uint32_t r = 0;
    for (int i = 0; i < 4; i++) {
        unsigned la = (a >> (i * 8)) & 0xFFu;
        unsigned lb = (b >> (i * 8)) & 0xFFu;
        uint8_t  m  = (la > lb) ? 0xFFu : 0x00u;
        r |= (uint32_t)m << (i * 8);
    }
    return r;
}

// Extract MSB of each of the 4 lanes → 4-bit mask (bit i = lane i MSB).
static inline int gssw4_movemask_epi8(uint32_t v) {
    return ((v >> 7)  & 0x1)
         | ((v >> 14) & 0x2)
         | ((v >> 21) & 0x4)
         | ((v >> 28) & 0x8);
}

// Low 16 bits (matches _mm_extract_epi16(v, 0)).
static inline uint16_t gssw4_extract_lo16(uint32_t v) {
    return (uint16_t)v;
}

// Horizontal max across the 4 lanes → scalar uint8.
// Models a proposed GenDP opcode: one-instruction reduction of all
// 4 lanes in a 32-bit reg. Avoids the srli+max+extract chain.
static inline uint8_t gssw4_maxReduce(uint32_t v) {
    uint8_t l0 = (uint8_t)(v      );
    uint8_t l1 = (uint8_t)(v >>  8);
    uint8_t l2 = (uint8_t)(v >> 16);
    uint8_t l3 = (uint8_t)(v >> 24);
    uint8_t m01 = (l0 > l1) ? l0 : l1;
    uint8_t m23 = (l2 > l3) ? l2 : l3;
    return (m01 > m23) ? m01 : m23;
}

#endif // GSSW_SIMD4_H
