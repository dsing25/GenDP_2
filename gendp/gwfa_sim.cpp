#include "sys_def.h"
#include "gwfa_sim.h"
#include "pe_array.h"
#include <climits>

extern "C" {
#include "../../kernel/Gwfa/gwfa.h"
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
    char buf[1 << 20];
    if (!fgets(buf, sizeof(buf), fp))
        return false;
    size_t len = strlen(buf);
    while (len > 0 &&
           (buf[len-1] == '\n' ||
            buf[len-1] == '\r'))
        --len;
    out.assign(buf, len);
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

/* Local struct for dump loading only */
struct GwfaIterInput {
    int32_t ql;
    std::string q;
    uint32_t startV;
    int32_t startOff;
    uint32_t endV;
    int32_t endOff;
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
    subgfa_subgraph_t *sub =
        (subgfa_subgraph_t*)calloc(
            1, sizeof(subgfa_subgraph_t));
    sub->n_vtx = n_vtx;
    sub->n_arc = n_arc;

    size_t slen = graphSeq.size();
    sub->graphSeq = (char*)malloc(slen);
    memcpy(sub->graphSeq, graphSeq.data(), slen);

    sub->seq_off = (uint32_t*)
        malloc(n_vtx * sizeof(uint32_t));
    memcpy(sub->seq_off, seq_off.data(),
        n_vtx * sizeof(uint32_t));

    sub->seq_len = (int32_t*)
        malloc(n_vtx * sizeof(int32_t));
    memcpy(sub->seq_len, seq_len.data(),
        n_vtx * sizeof(int32_t));

    sub->arc = (subgfa_arc_t*)
        malloc(n_arc * sizeof(subgfa_arc_t));
    for (uint64_t i = 0; i < n_arc; i++) {
        sub->arc[i].v = arc_v[i];
        sub->arc[i].w = arc_w[i];
        sub->arc[i].ow = arc_ow[i];
    }

    sub->idx = (uint64_t*)
        malloc(n_vtx * sizeof(uint64_t));
    memcpy(sub->idx, idx.data(),
        n_vtx * sizeof(uint64_t));

    return sub;
}

static std::vector<GwfaIterInput>
loadGwfaDump(const std::string &dumpDir)
{
    FILE *fql   = openDumpFile(dumpDir, "ql.txt");
    FILE *fq    = openDumpFile(dumpDir, "q.txt");
    FILE *fsv   = openDumpFile(dumpDir, "startV.txt");
    FILE *fso   = openDumpFile(dumpDir, "startOff.txt");
    FILE *fev   = openDumpFile(dumpDir, "endV.txt");
    FILE *feo   = openDumpFile(dumpDir, "endOff.txt");
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
        readLine(fq, inp.q);

        readLine(fsv, line);
        inp.startV = (uint32_t)std::stoul(line);
        readLine(fso, line);
        inp.startOff = std::stoi(line);
        readLine(fev, line);
        inp.endV = (uint32_t)std::stoul(line);
        readLine(feo, line);
        inp.endOff = std::stoi(line);
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
    fclose(fsv);  fclose(fso);
    fclose(fev);  fclose(feo);
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
    std::string main_instr_file =
        "instructions/gwfa/main_instruction.txt";
    unsigned long main_instruction[CTRL_INSTR_BUFFER_NUM];
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++)
        main_instruction[i] = 0x42;
    {
        std::fstream fp;
        std::string line;
        int read_index = 0;
        fp.open(main_instr_file, std::ios::in);
        if (!fp.is_open()) {
            fprintf(stderr, "Cannot open %s\n",
                main_instr_file.c_str());
            exit(-1);
        }
        while (getline(fp, line))
            main_instruction[read_index++] =
                std::stoull(line, 0, 0);
        fp.close();
    }
    for (int i = 0; i < CTRL_INSTR_BUFFER_NUM; i++) {
        unsigned long tmp[CTRL_INSTR_BUFFER_GROUP_SIZE];
        tmp[0] = 0x20f7800000000;
        tmp[1] = main_instruction[i];
        pa->main_instruction_buffer_write_from_ddr(
            i, tmp);
    }

    for (int i = 0; i < n; i++) {
        auto &inp = inputs[i];

        // Reset controller state
        pa->buffer_reset(
            pa->main_addressing_register,
            MAIN_ADDR_REGISTER_NUM);
        pa->main_PC = 0;
        memset(pa->va_regfile, 0,
            sizeof(pa->va_regfile));

        // Populate va_regfile with graph pointers
        // [0]=graphSeq [1]=seq_off [2]=seq_len
        // [3]=arc [4]=idx [5]=q
        if (inp.sub) {
            pa->va_regfile[0] = (uint64_t)(uintptr_t)
                inp.sub->graphSeq;
            pa->va_regfile[1] = (uint64_t)(uintptr_t)
                inp.sub->seq_off;
            pa->va_regfile[2] = (uint64_t)(uintptr_t)
                inp.sub->seq_len;
            pa->va_regfile[3] = (uint64_t)(uintptr_t)
                inp.sub->arc;
            pa->va_regfile[4] = (uint64_t)(uintptr_t)
                inp.sub->idx;
        }
        pa->va_regfile[5] = (uint64_t)(uintptr_t)
            inp.q.c_str();

        // Populate registers with integer params
        // [16]=ql [17]=n_vtx [18]=n_arc
        // [19]=startV [20]=startOff
        // [21]=endV [22]=endOff [23]=s_term
        pa->main_addressing_register[16] = inp.ql;
        pa->main_addressing_register[17] = inp.n_vtx;
        pa->main_addressing_register[18] =
            (int)inp.n_arc;
        pa->main_addressing_register[19] = inp.startV;
        pa->main_addressing_register[20] = inp.startOff;
        pa->main_addressing_register[21] = inp.endV;
        pa->main_addressing_register[22] = inp.endOff;
        pa->main_addressing_register[23] = inp.s_term;

        pa->run(1000, 0, PE_4_SETTING,
            MAIN_INSTRUCTION_1);

        // Free subgraph (gwfa_sim owns the memory)
        if (inp.sub) {
            subgfa_subgraph_destroy(inp.sub);
            inp.sub = NULL;
        }
    }

    // Free remaining unprocessed subgraphs
    for (int i = n; i < (int)inputs.size(); i++) {
        if (inputs[i].sub) {
            subgfa_subgraph_destroy(inputs[i].sub);
            inputs[i].sub = NULL;
        }
    }

    delete pa;
}
