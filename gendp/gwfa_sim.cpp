#include "sys_def.h"
#include "gwfa_sim.h"
#include "pe_array.h"
#include <climits>
#include <cassert>

extern "C" {
#include "kernel/Gwfa/gwfa.h"
}

/* ---- Dump file helpers ---- */

static FILE *openDumpFile(
    const std::string &dir, const char *name)
{
    std::string path = dir + "/" + name;
    FILE *fp = fopen(path.c_str(), "r");
    if (!fp) {
        fprintf(stderr,
            "cannot open %s\n", path.c_str());
        exit(1);
    }
    return fp;
}

static bool readLine(FILE *fp, std::string &out)
{
    char *line = nullptr;
    size_t cap = 0;
    ssize_t n = getline(&line, &cap, fp);
    if (n < 0) { free(line); return false; }
    while (n > 0 && (line[n-1] == '\n' || line[n-1] == '\r'))
        --n;
    out.assign(line, (size_t)n);
    free(line);
    return true;
}

static std::vector<uint32_t> parseU32Line(
    const std::string &line)
{
    std::vector<uint32_t> v;
    std::istringstream iss(line);
    uint32_t x;
    while (iss >> x) v.push_back(x);
    return v;
}

static std::vector<int32_t> parseI32Line(
    const std::string &line)
{
    std::vector<int32_t> v;
    std::istringstream iss(line);
    int32_t x;
    while (iss >> x) v.push_back(x);
    return v;
}

static std::vector<uint64_t> parseU64Line(
    const std::string &line)
{
    std::vector<uint64_t> v;
    std::istringstream iss(line);
    uint64_t x;
    while (iss >> x) v.push_back(x);
    return v;
}

/* ---- 2-bit encoding: A=0 C=1 G=2 T=3 ---- */

static inline uint32_t char_to_2bit(char c)
{
    switch (c) {
    case 'A': case 'a': return 0;
    case 'C': case 'c': return 1;
    case 'G': case 'g': return 2;
    case 'T': case 't': return 3;
    default: return 0;
    }
}

static uint32_t *encode_2bit(
    const char *s, size_t len)
{
    size_t nw = (len + 15) / 16;
    uint32_t *out = (uint32_t*)calloc(
        nw, sizeof(uint32_t));
    for (size_t i = 0; i < len; ++i)
        out[i >> 4] |=
            char_to_2bit(s[i])
            << ((i & 0xF) << 1);
    return out;
}

/* Local struct for dump loading only */
struct GwfaIterInput {
    int32_t ql;
    uint32_t *q_enc;  // 2-bit packed query
    int32_t s_term;
    uint32_t n_vtx;
    uint64_t n_arc;
    subgfa_subgraph_t *sub;
};

static subgfa_subgraph_t *buildSubgraph(
    uint32_t n_vtx, uint64_t n_arc,
    const std::string &graphSeq,
    const std::vector<uint32_t> &seq_off,
    const std::vector<int32_t> &seq_len,
    const std::vector<uint32_t> &arc_v,
    const std::vector<uint32_t> &arc_w,
    const std::vector<int32_t> &arc_ow,
    const std::vector<uint64_t> &idx)
{
    subgfa_subgraph_t *sub = (subgfa_subgraph_t*)calloc(1, sizeof(subgfa_subgraph_t));
    sub->n_vtx = n_vtx;
    sub->n_arc = (uint32_t)n_arc;

    sub->graphSeq = encode_2bit(graphSeq.data(), graphSeq.size());

    sub->seq_off = (uint32_t*)malloc(n_vtx * sizeof(uint32_t));
    memcpy(sub->seq_off, seq_off.data(), n_vtx * sizeof(uint32_t));

    sub->seq_len = (int32_t*)malloc(n_vtx * sizeof(int32_t));
    memcpy(sub->seq_len, seq_len.data(), n_vtx * sizeof(int32_t));

    sub->arc = (subgfa_arc_t*)malloc(n_arc * sizeof(subgfa_arc_t));
    for (uint64_t i = 0; i < n_arc; i++) {
        assert(arc_v[i] <= 0xFFFF && "vertex ID exceeds 16 bits");
        assert(arc_w[i] <= 0xFFFF && "vertex ID exceeds 16 bits");
        sub->arc[i].v = (uint16_t)arc_v[i];
        sub->arc[i].w = (uint16_t)arc_w[i];
        sub->arc[i].ow = arc_ow[i];
    }

    // Build CSR arc_off from cumulative n_arcs
    sub->arc_off = (uint32_t*)malloc((n_vtx + 1) * sizeof(uint32_t));
    sub->arc_off[0] = 0;
    for (uint32_t v = 0; v < n_vtx; v++) {
        uint32_t n_arcs_v = (uint32_t)idx[v];
        sub->arc_off[v + 1] = sub->arc_off[v] + n_arcs_v;
    }
    assert(sub->arc_off[n_vtx] == (uint32_t)n_arc);

    return sub;
}

static void freeSubgraph(subgfa_subgraph_t *sub) {
    if (!sub) return;
    free(sub->graphSeq);
    free(sub->seq_off);
    free(sub->seq_len);
    free(sub->arc);
    free(sub->arc_off);
    free(sub);
}

static std::vector<GwfaIterInput>
loadGwfaDump(const std::string &dumpDir)
{
    FILE *fql   = openDumpFile(dumpDir, "ql.txt");
    FILE *fq    = openDumpFile(dumpDir, "q.txt");
    FILE *fst   = openDumpFile(dumpDir, "s_term.txt");
    FILE *fnv   = openDumpFile(dumpDir, "n_vtx.txt");
    FILE *fna   = openDumpFile(dumpDir, "n_arc.txt");
    FILE *fgs   = openDumpFile(dumpDir, "graphSeq.txt");
    FILE *fsoff = openDumpFile(dumpDir, "seq_off.txt");
    FILE *fslen = openDumpFile(dumpDir, "seq_len.txt");
    FILE *fav   = openDumpFile(dumpDir, "arc_v.txt");
    FILE *faw   = openDumpFile(dumpDir, "arc_w.txt");
    FILE *faow  = openDumpFile(dumpDir, "arc_ow.txt");
    FILE *fidx  = openDumpFile(dumpDir, "idx.txt");

    std::vector<GwfaIterInput> result;
    std::string line;

    while (readLine(fql, line)) {
        GwfaIterInput inp;
        inp.ql = std::stoi(line);

        std::string q_str;
        readLine(fq, q_str);
        inp.q_enc = encode_2bit(
            q_str.data(), q_str.size());

        readLine(fst, line);
        inp.s_term = std::stoi(line);

        /* subgraph */
        readLine(fnv, line);
        uint32_t nv = (uint32_t)std::stoul(line);
        inp.n_vtx = nv;

        if (nv == 0) {
            readLine(fna, line);
            readLine(fgs, line);
            readLine(fsoff, line);
            readLine(fslen, line);
            readLine(fav, line);
            readLine(faw, line);
            readLine(faow, line);
            readLine(fidx, line);
            inp.n_arc = 0;
            inp.sub = NULL;
        } else {
            readLine(fna, line);
            uint64_t na = std::stoull(line);
            inp.n_arc = na;

            std::string gs;
            readLine(fgs, gs);

            readLine(fsoff, line);
            auto soff = parseU32Line(line);
            readLine(fslen, line);
            auto slen2 = parseI32Line(line);
            readLine(fav, line);
            auto av = parseU32Line(line);
            readLine(faw, line);
            auto aw = parseU32Line(line);
            readLine(faow, line);
            auto aow = parseI32Line(line);
            readLine(fidx, line);
            auto idx2 = parseU64Line(line);

            inp.sub = buildSubgraph(nv, na,
                gs, soff, slen2,
                av, aw, aow, idx2);
        }
        result.push_back(std::move(inp));
    }

    fclose(fql);  fclose(fq);
    fclose(fst);
    fclose(fnv);  fclose(fna);
    fclose(fgs);  fclose(fsoff);
    fclose(fslen); fclose(fav);
    fclose(faw);  fclose(faow);
    fclose(fidx);
    return result;
}

/* ---- Simulation entry point ---- */

void gwfa_simulation(
    char *inputFileName, char *outputFileName,
    FILE * /*fp*/, int /*show_output*/,
    int simulation_cases)
{
    if (!inputFileName) {
        fprintf(stderr,
            "gwfa: -i <dump_dir> required\n");
        exit(1);
    }

    std::string dumpDir(inputFileName);
    fprintf(stderr,
        "gwfa: loading inputs from %s\n",
        dumpDir.c_str());
    auto inputs = loadGwfaDump(dumpDir);

    int n = (int)inputs.size();
    if (simulation_cases >= 0 &&
        simulation_cases < n)
        n = simulation_cases;
    fprintf(stderr, "gwfa: %d iterations\n", n);

    pe_array *pa = new pe_array(1024, 1024);

    // Load main instructions from file
    std::string main_instr_file = "instructions/gwfa/main_instruction.txt";
    unsigned long main_instruction[CTRL_INSTR_BUFFER_NUM];
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++)
        main_instruction[i] = 0x42;
    {
        std::fstream fp;
        std::string line;
        int read_index = 0;
        fp.open(main_instr_file, std::ios::in);
        if (!fp.is_open()) {
            fprintf(stderr, "Cannot open %s\n", main_instr_file.c_str());
            exit(-1);
        }
        while (getline(fp, line))
            main_instruction[read_index++] = std::stoull(line, 0, 0);
        fp.close();
    }

    // Load PE instructions from files
    const int pe_group_size = 4;
    static unsigned long pe_instr[pe_group_size][CTRL_INSTR_BUFFER_NUM][CTRL_INSTR_BUFFER_GROUP_SIZE];
    for (int i = 0; i < pe_group_size; i++)
        for (int j = 0; j < CTRL_INSTR_BUFFER_NUM; j++) {
            pe_instr[i][j][0] = CTRL_NOP_INSTRUCTION;
            pe_instr[i][j][1] = CTRL_NOP_INSTRUCTION;
        }
    for (int i = 0; i < pe_group_size; i++) {
        std::string pe_file = "instructions/gwfa/pe_" + std::to_string(i) + "_instruction.txt";
        std::fstream fp;
        fp.open(pe_file, std::ios::in);
        if (fp.is_open()) {
            std::string line;
            int read_index = 0;
            while (getline(fp, line)) {
                pe_instr[i][read_index / 2][read_index % 2] = std::stoull(line, 0, 0);
                read_index++;
            }
            fp.close();
        }
    }

    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = CTRL_NOP_INSTRUCTION;
        tmp[1] = main_instruction[i];
        pa->main_instruction_buffer_write_from_ddr(i, tmp);
        for (int j = 0; j < pe_group_size; j++)
            pa->pe_instruction_buffer_write_from_ddr(i, pe_instr[j][i], j);
    }

    for (int i = 0; i < n; i++) {
        auto &inp = inputs[i];

        // No graph → score = -1
        if (!inp.sub) {
            printf("qqq -1 qqq\n");
            free(inp.q_enc);
            inp.q_enc = NULL;
            continue;
        }

        // Check if sequences fit in interleaved SPM
        {
            int q_words = (inp.ql + 15) / 16;
            int gs_total = 0;
            for (uint32_t v = 0; v < inp.n_vtx; v++) {
                int end = (int)inp.sub->seq_off[v]
                    + inp.sub->seq_len[v];
                if (end > gs_total) gs_total = end;
            }
            int gs_words = (gs_total + 15) / 16;
            if (GWFA_Q_START + q_words > SPM_ADDR_NUM
                || GWFA_GS_START + gs_words > SPM_ADDR_NUM) {
                fprintf(stderr, "gwfa: case %d too large "
                    "for SPM (q=%d gs=%d words), "
                    "skipping\n", i, q_words, gs_words);
                printf("qqq -1 qqq\n");
                free(inp.q_enc); inp.q_enc = NULL;
                freeSubgraph(inp.sub); inp.sub = NULL;
                continue;
            }
        }

        // Reset controller state
        pa->buffer_reset(
            pa->main_addressing_register,
            MAIN_ADDR_REGISTER_NUM);
        pa->main_PC = 0;
        memset(pa->va_regfile, 0, sizeof(pa->va_regfile));
        memset(pa->s1c, 0, sizeof(pa->s1c));

        // Reset shared SPM, S2, LSQ, event producers
        pa->reset_shared_spm();
        pa->reset_controller_state();

        // Reset PE state (SPM, registers, PCs)
        for (int pe = 0; pe < 4; pe++)
            pa->pe_unit[pe]->reset();
        // Clear FIFOs
        for (int fi = 0; fi < FIFO_GROUP_NUM; fi++)
            for (int fj = 0; fj < FIFO_GROUP_SIZE; fj++)
                pa->fifo_unit[fi][fj].clear();

        // Populate va_regfile with graph pointers
        // [0]=graphSeq [1]=seq_off [2]=seq_len
        // [3]=arc [4]=idx [5]=q
        pa->va_regfile[0] = (uint64_t)(uintptr_t)
            inp.sub->graphSeq;
        pa->va_regfile[1] = (uint64_t)(uintptr_t)
            inp.sub->seq_off;
        pa->va_regfile[2] = (uint64_t)(uintptr_t)
            inp.sub->seq_len;
        pa->va_regfile[3] = (uint64_t)(uintptr_t)
            inp.sub->arc;
        pa->va_regfile[4] = (uint64_t)(uintptr_t)
            inp.sub->arc_off;
        pa->va_regfile[5] = (uint64_t)(uintptr_t)
            inp.q_enc;

        // Populate registers with integer params
        // [16]=ql [17]=n_vtx [18]=n_arc [23]=s_term
        pa->main_addressing_register[16] = inp.ql;
        pa->main_addressing_register[17] = inp.n_vtx;
        pa->main_addressing_register[18] =
            (int)inp.n_arc;
        pa->main_addressing_register[23] = inp.s_term;
        const char *st_env = getenv("GWFA_S_TERM_DBG");
        if (st_env)
            pa->main_addressing_register[23] = atoi(st_env);

        // Max cycles: scale with edit distance × tiles per step
        int max_cycles =
            inp.s_term * 500000 + 500000;
        if (max_cycles < 2000000) max_cycles = 2000000;
        pa->run(max_cycles, 0, PE_4_SETTING,
            MAIN_INSTRUCTION_1);

        // Free memory (gwfa_sim owns it)
        free(inp.q_enc);
        inp.q_enc = NULL;
        if (inp.sub) {
            subgfa_subgraph_destroy(inp.sub);
            inp.sub = NULL;
        }
    }

    // Free remaining unprocessed inputs
    for (int i = n; i < (int)inputs.size(); i++) {
        free(inputs[i].q_enc);
        inputs[i].q_enc = NULL;
        if (inputs[i].sub) {
            subgfa_subgraph_destroy(inputs[i].sub);
            inputs[i].sub = NULL;
        }
    }

    delete pa;
}
