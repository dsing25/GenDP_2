#include "sys_def.h"
#include "gssw_sim.h"
#include "pe_array.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sstream>
#include <cstdint>

// ---- 8-wide SIMD (paired 4-lane): each logical "vector" is 8 packed
//      uint8s stored as a pair of adjacent uint32 SPM words. ----

#define GSSW_READ_LEN  148
#define GSSW_SEG_LEN   19                           // ceil(148 / 8)
#define GSSW_VEC_WORDS 2                            // 2 SPM words per pair

// SPM fixed-region offsets (bytes). Each array holds SEG_LEN pair slots,
// each 8 bytes. 8-byte (1 pair) padding between pvE/pvF and pvF/best
// absorbs the lazy-F last-iter overflow writes at spm[pvE+SEG_LEN*2]
// and spm[pvF+SEG_LEN*2] so they don't corrupt pvF[0]/best[0].
// Must match pe.cpp exactly.
#define GSSW_SPM_PAD    8                            // 1 pair = 2 words
#define GSSW_PROF_OFF   0
#define GSSW_HPING_OFF  (4 * GSSW_SEG_LEN * 8)       // 4 nt × segLen pairs × 8B
#define GSSW_HPONG_OFF  (GSSW_HPING_OFF + GSSW_SEG_LEN * 8)
#define GSSW_E_OFF      (GSSW_HPONG_OFF + GSSW_SEG_LEN * 8)
#define GSSW_F_OFF      (GSSW_E_OFF     + GSSW_SEG_LEN * 8 + GSSW_SPM_PAD)
#define GSSW_BEST_OFF   (GSSW_F_OFF     + GSSW_SEG_LEN * 8 + GSSW_SPM_PAD)
#define GSSW_GRAPH_OFF  (GSSW_BEST_OFF  + GSSW_SEG_LEN * 8)

struct gssw_profile {
    uint32_t* profile_byte;   // 4 nt × segLen uint32s (4 lanes each)
    const int8_t* read;
    int32_t readLen;
    uint8_t bias;
};

struct gssw_node_desc {
    int16_t seq_off;
    int16_t seq_len;
    int16_t next_off;
    int16_t next_len;
};

struct gssw_soa_graph {
    uint32_t num_nodes;
    gssw_node_desc* nodes;
    int16_t* nexts;
    int8_t* seqs;
    uint32_t total_nexts;
    uint32_t total_seq;
};

struct gssw_spm_graph_meta {
    uint32_t num_nodes;
    uint32_t total_nexts;
    uint32_t total_seq;
    uint32_t _pad;
};

struct gssw_spm_node_desc {
    int16_t seq_off;
    int16_t seq_len;
    int16_t next_off;
    int16_t next_len;
    // Pair slots: 2 uint32 words per logical 8-lane vector.
    uint32_t hSeed[GSSW_SEG_LEN * GSSW_VEC_WORDS];
    uint32_t eSeed[GSSW_SEG_LEN * GSSW_VEC_WORDS];
};

static inline uint64_t gssw_spm_size(
    uint32_t num_nodes, uint32_t total_nexts,
    uint32_t total_seq)
{
    uint64_t sz = GSSW_GRAPH_OFF;
    sz += sizeof(gssw_spm_graph_meta);
    sz += (uint64_t)num_nodes * sizeof(gssw_spm_node_desc);
    uint64_t nexts_bytes =
        (uint64_t)total_nexts * sizeof(int16_t);
    nexts_bytes = (nexts_bytes + 3) & ~3ULL;
    sz += nexts_bytes;
    // Sequence is packed 2-bit (16 bases per 32-bit word).
    sz += ((uint64_t)total_seq + 15) / 16 * 4;
    return sz;
}

// ---- Inlined gssw_spm_pack from gssw.c ----

static void gssw_spm_pack(uint8_t* SPM,
    const gssw_soa_graph* graph,
    const gssw_profile* prof)
{
    const int32_t segLen = GSSW_SEG_LEN;
    // Profile is 4 nucleotides × segLen pair-slots × 2 words each.
    memcpy(SPM + GSSW_PROF_OFF, prof->profile_byte,
           4 * segLen * GSSW_VEC_WORDS * sizeof(uint32_t));
    memset(SPM + GSSW_HPING_OFF, 0,
           (GSSW_GRAPH_OFF - GSSW_HPING_OFF));

    gssw_spm_graph_meta* meta =
        (gssw_spm_graph_meta*)(SPM + GSSW_GRAPH_OFF);
    meta->num_nodes = graph->num_nodes;
    meta->total_nexts = graph->total_nexts;
    meta->total_seq = graph->total_seq;
    meta->_pad = 0;

    gssw_spm_node_desc* nodeDescs = (gssw_spm_node_desc*)(
        SPM + GSSW_GRAPH_OFF + sizeof(gssw_spm_graph_meta));
    for (uint32_t i = 0; i < graph->num_nodes; i++) {
        const gssw_node_desc* src = &graph->nodes[i];
        gssw_spm_node_desc* dst = &nodeDescs[i];
        dst->seq_off  = src->seq_off;
        dst->seq_len  = src->seq_len;
        dst->next_off = src->next_off;
        dst->next_len = src->next_len;
        memset(dst->hSeed, 0,
            segLen * GSSW_VEC_WORDS * sizeof(uint32_t));
        memset(dst->eSeed, 0,
            segLen * GSSW_VEC_WORDS * sizeof(uint32_t));
    }

    int16_t* childIds = (int16_t*)(
        (uint8_t*)nodeDescs
        + graph->num_nodes * sizeof(gssw_spm_node_desc));
    memcpy(childIds, graph->nexts,
           graph->total_nexts * sizeof(int16_t));
    uint64_t nexts_bytes =
        (uint64_t)graph->total_nexts * sizeof(int16_t);
    uint64_t nexts_padded = (nexts_bytes + 3) & ~3ULL;
    if (nexts_padded > nexts_bytes)
        memset((uint8_t*)childIds + nexts_bytes, 0,
               nexts_padded - nexts_bytes);

    // Pack sequence 2-bit (16 bases per 32-bit word, LE within word).
    uint32_t* seqDst = (uint32_t*)((uint8_t*)childIds + nexts_padded);
    uint32_t n_words = (graph->total_seq + 15) / 16;
    memset(seqDst, 0, (size_t)n_words * sizeof(uint32_t));
    for (uint32_t i = 0; i < graph->total_seq; i++) {
        uint32_t base = (uint32_t)((uint8_t)graph->seqs[i]) & 0x3;
        seqDst[i >> 4] |= base << ((i & 15) * 2);
    }
}

// ---- Destroy helpers ----

static void gssw_profile_destroy(gssw_profile* p) {
    if (!p) return;
    free(p->profile_byte);
    free(p);
}

static void gssw_soa_graph_destroy(gssw_soa_graph* g) {
    if (!g) return;
    free(g->nodes);
    free(g->nexts);
    free(g->seqs);
    free(g);
}

// ---- Dump file helpers ----

static FILE *openDumpFile(
    const std::string &dir, const char *name)
{
    std::string path = dir + "/" + name;
    FILE *fp = fopen(path.c_str(), "r");
    if (!fp) {
        fprintf(stderr, "cannot open %s\n", path.c_str());
        exit(1);
    }
    return fp;
}

static bool readLine(FILE *fp, std::string &out)
{
    char buf[1 << 20];
    if (!fgets(buf, sizeof(buf), fp))
        return false;
    size_t len = strlen(buf);
    while (len > 0
           && (buf[len-1] == '\n' || buf[len-1] == '\r'))
        --len;
    out.assign(buf, len);
    return true;
}

// ---- Parse one graph from graph.soa ----

static bool parseGraphSoA(FILE *fp,
    gssw_soa_graph **out, bool *has_n)
{
    std::string line;
    if (!readLine(fp, line)) return false;

    // Line 1: num_nodes total_nexts total_seq
    gssw_soa_graph *g = (gssw_soa_graph*)
        calloc(1, sizeof(gssw_soa_graph));
    {
        std::istringstream ss(line);
        ss >> g->num_nodes >> g->total_nexts >> g->total_seq;
    }

    // Line 2: (seq_off,seq_len,next_off,next_len), ...
    g->nodes = (gssw_node_desc*)
        malloc(g->num_nodes * sizeof(gssw_node_desc));
    readLine(fp, line);
    {
        std::istringstream ss(line);
        for (uint32_t i = 0; i < g->num_nodes; i++) {
            char paren, comma;
            int so, sl, no, nl;
            if (i > 0) ss >> comma;
            ss >> paren >> so >> comma >> sl >> comma
               >> no >> comma >> nl >> paren;
            g->nodes[i].seq_off = (int16_t)so;
            g->nodes[i].seq_len = (int16_t)sl;
            g->nodes[i].next_off = (int16_t)no;
            g->nodes[i].next_len = (int16_t)nl;
        }
    }

    // Line 3: nexts
    g->nexts = (int16_t*)
        malloc(g->total_nexts * sizeof(int16_t));
    readLine(fp, line);
    {
        std::istringstream ss(line);
        for (uint32_t i = 0; i < g->total_nexts; i++) {
            int v; ss >> v;
            g->nexts[i] = (int16_t)v;
        }
    }

    // Line 4: seqs (0=A,1=C,2=G,3=T,4=N)
    g->seqs = (int8_t*)malloc(g->total_seq);
    *has_n = false;
    readLine(fp, line);
    {
        std::istringstream ss(line);
        for (uint32_t i = 0; i < g->total_seq; i++) {
            int v; ss >> v;
            g->seqs[i] = (int8_t)v;
            if (v == 4) *has_n = true;
        }
    }

    *out = g;
    return true;
}

// ---- Parse one profile from matchProfiles.txt ----

// On-disk matchProfiles.txt is in 16-wide striped format:
//   bytes[nt][seg16*16 + lane16] holds the score for read position
//   (lane16 * 10 + seg16) vs reference nucleotide nt, where segLen16=10.
// We re-stripe to 8-wide paired:
//   profile_uint[nt][seg8*2 + half]'s byte lane4 holds the score for read
//   pos (lane8 * 19 + seg8), where segLen8=19, lane8 = half*4 + lane4.
static bool parseProfile(FILE *fp, gssw_profile **out)
{
    std::string line;
    if (!readLine(fp, line)) return false;

    int32_t readLen;
    {
        std::istringstream ss(line);
        ss >> readLen;
    }

    const int32_t segLen16 = (readLen + 15) / 16;  // 10
    const int32_t segLen8  = (readLen + 7)  / 8;   // 19
    const int32_t n = 4;                            // nucleotides

    gssw_profile* p = (gssw_profile*)
        calloc(1, sizeof(gssw_profile));
    p->readLen = readLen;
    p->bias = 4;
    p->read = NULL;
    // Profile size: 4 nt × segLen8 pair-slots × 2 words per pair.
    p->profile_byte = (uint32_t*)
        calloc(n * segLen8 * 2, sizeof(uint32_t));

    uint8_t* prof_bytes = (uint8_t*)p->profile_byte;
    for (int32_t base = 0; base < n; base++) {
        readLine(fp, line);
        std::istringstream ss(line);
        // Read all 16-wide bytes (segLen16 * 16 = 160 per row).
        // Un-stripe to linear, then re-stripe to 8-wide paired.
        for (int32_t j = 0; j < segLen16 * 16; j++) {
            int v; ss >> v;
            int32_t seg16  = j / 16;
            int32_t lane16 = j % 16;
            int32_t rp = lane16 * segLen16 + seg16;
            if (rp >= readLen) continue; // padding
            int32_t lane8 = rp / segLen8;
            int32_t seg8  = rp % segLen8;
            int32_t half  = lane8 >> 2;        // 0 = lo word, 1 = hi word
            int32_t lane4 = lane8 & 3;         // within-word lane
            // Layout per nucleotide: pair slots sequentially,
            //   slot s occupies words [s*2, s*2+1].
            // byte layout within uint32: lane l is bits [l*8, l*8+7]
            prof_bytes[(base * segLen8 * 2 + seg8 * 2 + half) * 4 + lane4]
                = (uint8_t)v;
        }
    }

    *out = p;
    return true;
}

// ---- Simulation entry point ----

void gssw_simulation(
    char *inputFileName, char * /*outputFileName*/,
    FILE * /*fp*/, int /*show_output*/,
    int simulation_cases)
{
    if (!inputFileName) {
        fprintf(stderr, "gssw: -i <dump_dir> required\n");
        exit(1);
    }

    std::string dumpDir(inputFileName);
    fprintf(stderr, "gssw: loading from %s\n",
            dumpDir.c_str());

    FILE *gf = openDumpFile(dumpDir, "graph.soa");
    FILE *pf = openDumpFile(dumpDir, "matchProfiles.txt");
    FILE *nf = openDumpFile(dumpDir, "readNFilter.txt");

    // Read entry counts
    std::string line;
    readLine(gf, line);
    int ng = std::stoi(line);
    readLine(pf, line);
    int np = std::stoi(line);
    if (ng != np) {
        fprintf(stderr,
            "gssw: graph count %d != profile count %d\n",
            ng, np);
        exit(1);
    }

    int n = ng;
    if (simulation_cases >= 0 && simulation_cases < n)
        n = simulation_cases;
    fprintf(stderr, "gssw: %d iterations\n", n);

    pe_array *pa = new pe_array(1024, 1024);

    // Load main instructions
    std::string main_instr_file =
        "instructions/gssw/main_instruction.txt";
    unsigned long main_instruction[CTRL_INSTR_BUFFER_NUM];
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++)
        main_instruction[i] = 0x42;
    {
        std::fstream fp2;
        std::string l;
        int read_index = 0;
        fp2.open(main_instr_file, std::ios::in);
        if (!fp2.is_open()) {
            fprintf(stderr, "Cannot open %s\n",
                    main_instr_file.c_str());
            exit(-1);
        }
        while (getline(fp2, l))
            main_instruction[read_index++] =
                std::stoull(l, 0, 0);
        fp2.close();
    }

    // Load PE instructions
    const int pe_group_size = 4;
    static unsigned long pe_instr[4]
        [CTRL_INSTR_BUFFER_NUM][CTRL_INSTR_BUFFER_GROUP_SIZE];
    for (int i = 0; i < pe_group_size; i++)
        for (int j = 0; j < CTRL_INSTR_BUFFER_NUM; j++) {
            pe_instr[i][j][0] = CTRL_NOP_INSTRUCTION;
            pe_instr[i][j][1] = CTRL_NOP_INSTRUCTION;
        }
    for (int i = 0; i < pe_group_size; i++) {
        std::string pe_file = "instructions/gssw/pe_"
            + std::to_string(i) + "_instruction.txt";
        std::fstream fp2;
        fp2.open(pe_file, std::ios::in);
        if (fp2.is_open()) {
            std::string l;
            int read_index = 0;
            while (getline(fp2, l)) {
                pe_instr[i][read_index / 2][read_index % 2]
                    = std::stoull(l, 0, 0);
                read_index++;
            }
            fp2.close();
        }
    }

    // Load compute instructions (shared across PEs). Optional — if the
    // file is missing we leave comp buffers zeroed (legacy magic-only
    // flow). Present once the GSSW lowering starts using set_PC.
    static unsigned long compute_instruction[COMP_INSTR_BUFFER_GROUP_NUM]
        [COMP_INSTR_BUFFER_GROUP_SIZE];
    for (int i = 0; i < COMP_INSTR_BUFFER_GROUP_NUM; i++) {
        compute_instruction[i][0] = COMP_HALT_INSTRUCTION;
        compute_instruction[i][1] = COMP_HALT_INSTRUCTION;
    }
    int n_comp_instructions = 0;
    {
        std::string compute_file =
            "instructions/gssw/compute_instruction.txt";
        std::fstream fp2;
        fp2.open(compute_file, std::ios::in);
        if (fp2.is_open()) {
            std::string l;
            int read_index = 0;
            while (getline(fp2, l)) {
                compute_instruction[read_index / 2][read_index % 2]
                    = std::stoull(l, 0, 0);
                read_index++;
            }
            fp2.close();
            n_comp_instructions = (read_index + 1) / 2;
        }
    }

    // Write instruction buffers to pe_array
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = 0x20f7800000000;
        tmp[1] = main_instruction[i];
        pa->main_instruction_buffer_write_from_ddr(i, tmp);
        for (int j = 0; j < pe_group_size; j++)
            pa->pe_instruction_buffer_write_from_ddr(
                i, pe_instr[j][i], j);
    }
    // Flash compute instructions into each PE (mirrors the bsw/chain
    // pattern).
    if (n_comp_instructions > 0) {
        for (int j = 0; j < pe_group_size; j++)
            pa->pe_comp_instruction_buffer_write_from_ddr(
                n_comp_instructions,
                &compute_instruction[0][0], j);
    }

    // Main iteration loop
    for (int i = 0; i < n; i++) {
        gssw_soa_graph *graph = NULL;
        gssw_profile *prof = NULL;
        bool has_n = false;

        // Read N-filter for this entry (1=skip, 0=keep)
        bool read_has_n = false;
        if (readLine(nf, line))
            read_has_n = (std::stoi(line) != 0);

        if (!parseGraphSoA(gf, &graph, &has_n)
            || !parseProfile(pf, &prof)) {
            fprintf(stderr,
                "gssw: unexpected EOF at iteration %d\n", i);
            break;
        }

        uint64_t spm_size = gssw_spm_size(
            graph->num_nodes, graph->total_nexts,
            graph->total_seq);

        // Skip if graph or read has N, or too large
        if (has_n || read_has_n) {
            printf("qqq -1 qqq\n");  // N-filtered
            gssw_soa_graph_destroy(graph);
            gssw_profile_destroy(prof);
            continue;
        }
        if (spm_size > (uint64_t)SPM_BANK_GROUP_SIZE * 4) {
            printf("qqq -2 qqq\n");  // too large
            gssw_soa_graph_destroy(graph);
            gssw_profile_destroy(prof);
            continue;
        }

        // Pack into SPM layout
        uint64_t alloc_sz = (spm_size + 15) & ~15ULL;
        uint8_t *packed = (uint8_t*)
            aligned_alloc(16, alloc_sz);
        memset(packed, 0, alloc_sz);
        gssw_spm_pack(packed, graph, prof);

        // Reset controller state
        pa->buffer_reset(
            pa->main_addressing_register,
            MAIN_ADDR_REGISTER_NUM);
        pa->main_PC = 0;
        memset(pa->va_regfile, 0, sizeof(pa->va_regfile));

        // Reset PE state
        for (int pe = 0; pe < pe_group_size; pe++)
            pa->pe_unit[pe]->reset();
        // Clear FIFOs
        for (int fi = 0; fi < FIFO_GROUP_NUM; fi++)
            for (int fj = 0; fj < FIFO_GROUP_SIZE; fj++)
                pa->fifo_unit[fi][fj].clear();

        // Pass packed buffer pointer and size
        pa->va_regfile[0] =
            (uint64_t)(uintptr_t)packed;
        pa->va_regfile[1] = spm_size;

        // Run simulation
        pa->run(100000, 0, PE_4_SETTING,
                MAIN_INSTRUCTION_1);

        // Cleanup
        free(packed);
        gssw_soa_graph_destroy(graph);
        gssw_profile_destroy(prof);
    }

    fclose(gf);
    fclose(pf);
    fclose(nf);
    delete pa;
}
