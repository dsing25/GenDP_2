# Repository Guidelines

## Project Structure & Module Organization
- Root hosts simulator core (e.g., `main.cpp`, `simulator.cpp`, `pe_array.cpp`) and kernel models (e.g., `bsw.cpp`, `phmm.cpp`, `poa.cpp`).
- `kernel/` contains kernels with their own build steps (e.g., `kernel/bwa-mem`, `kernel/PairHMM`, `kernel/poaV2`).
- `scripts/` holds instruction generators, preprocessing, throughput runners, and correctness checks; `instructions/` stores generated ISA artifacts.
- Outputs live in `*_sim_results/` and `*_output/`; see `README.md`, `CLAUDE.md`, and `docs.md` for workflows.

## Architecture & ISA Notes (from docs.md)
- System hierarchy: `pe_array` controller drives a 4-PE chain and SPM (4096 addresses). Controller has `gr[0..15]`, input/output buffers, and 4 FIFOs.
- Each PE has `reg[0..31]`, `gr[0..15]`, instruction buffers, and one SPM port (read OR write per cycle).
- Dual-trace model: control trace is VLIW with 2 slots; the second-written instruction executes first. Arithmetic ops write `gr` during decode; `mv/si` writes to `gr` are deferred until after both decodes.
- Addressing: if `reg_immBar=1`, address = `gr[imm] + gr[reg]`; else address = `imm + gr[reg]`.
- Controller/SPM rules: controller arithmetic destinations limited to `gr`, `out_buf`, `out_port`; `out_instr` is valid for `mv/si`. SPM has 2-cycle latency, no pipelining, single-port; loads only to `reg`, `gr`, or `out_port`.

## Build, Test, and Development Commands
- Build simulator: `make` (ASan on by default). Variants: `make ADDRESS_SANITIZER=0`, `make debug=1`, `make profile=1`, `make clean`.
- Run simulator: `./sim -k <1-5> -i <input> -o <output> -n <num>`.
- Kernel builds (examples): `cd kernel/bwa-mem && make -j`, `cd kernel/chain && make -j print=1` (others in `README.md`).

## Coding Style & Naming Conventions
- C++11 required (`-std=c++11`), 4-space indentation, same-line braces.
- File names are lower_snake (`pe_array.cpp`); keep new modules consistent.
- For instruction generators, preserve VLIW slot ordering semantics and comment non-obvious slot hazards.

## Testing Guidelines
- No unit-test framework; validation is script-driven.
- Correctness: `scripts/*_check_correctness.py` or `scripts/*_run_validation.sh` (e.g., `python3 scripts/wfa_check_correctness.py <out> <expected>`).
- Throughput: `scripts/*_throughput.sh`. Store outputs in `*_sim_results/` or dataset folders.

## Git rules
- Never run git commands that will change the state of the repo or git history. You may suggest, but 
  do not run. This includes git pull, git push, git revert, git merge, git checkout, etc.
- You may run non destructive git commands: e.g. git diff, git log.

## Configuration & Data Notes
- Workflows assume `GenDP_WORK_DIR` and a sibling `gendp-datasets` directory.
- Avoid committing generated binaries, large datasets, or long logs.

## Agent-Specific Notes
- ISA, control-slot ordering, and SPM rules: `docs.md`.
- Simulator usage and kernel workflows: `CLAUDE.md` and `README.md`.

## ExecPlans
- When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design to implementation.
- You should ask many questions in this phase. Do not assume that you know what I'm thinking. If
  you're unsure, ask.

## Keywords
- PLANMODE: If this is anywhere in the prompt, it means that you should be working on building an 
  ExecPlan. In this process do not write any code, or run any code. You should review the codebase
  and prompt carefully and thing deeply, but you may take READONLY actions. You should ask many
  questions in this phase. ALWAYS you should stop and wait for approval before you move on to
  implementation.
- READONLY: This means that you must not modify any files, inlcuding git history/commits, make
  commands, etc. You may run any commands which do not modify files, e.g. head, tail, cat, ls, grep,
  find, awk, ... You may also execute code, but only if it does not modify files, and this is 
  probably not required. Running code usually takes too long anyways.
