#!/bin/bash
set -e

rm -f success.txt
export GenDP_WORK_DIR="$(pwd)"
KERNEL="$1"

run_bsw() {
  cd "$GenDP_WORK_DIR/gendp"
  python3 scripts/preprocess_bsw_datasets.py \
    "$GenDP_WORK_DIR/gendp-datasets/bsw_147_1m_8bit_input.txt" \
    "$GenDP_WORK_DIR/gendp-datasets/bsw_147_1m_8bit_input_character.txt"
  cd kernel/bwa-mem
  make clean && make -j
  ./ksw-test -i "$GenDP_WORK_DIR/gendp-datasets/bsw_147_1m_8bit_input_character.txt" \
    -o "$GenDP_WORK_DIR/gendp-datasets/bsw_147_1m_8bit_output.txt" -x -n 2000
  cd ../../
  bash scripts/bsw_throughput.sh 2000 | tee >(grep CUPS >> ../success.txt)
}

run_chain() {
  CHAIN_DATA_FILE="$GenDP_WORK_DIR/backtest-datasets/chain/in-3.txt"
  cd "$GenDP_WORK_DIR/gendp/kernel/chain"
  make clean && make -j print=1
  ./chain -i "$CHAIN_DATA_FILE" \
    -o "$GenDP_WORK_DIR/gendp-datasets/chain_output.txt" -s 4 -n 1
  cd ../../
  mkdir -p chain_sim_results
  bash scripts/chain_throughput.sh 1 "$CHAIN_DATA_FILE" \
    | tee >(grep CUPS >> ../success.txt)
}

run_phmm() {
  INPUT_SIZE_PHMM=64
  cd "$GenDP_WORK_DIR/gendp/kernel/PairHMM"
  make clean && make -j
  ./pairhmm "$GenDP_WORK_DIR/backtest-datasets/phmm/tiny.in" \
    "$INPUT_SIZE_PHMM" \
    > "$GenDP_WORK_DIR/gendp-datasets/phmm_large_output.txt" \
    2> "$GenDP_WORK_DIR/gendp-datasets/phmm_large_app.txt"
  cd ../../
  mkdir -p phmm_sim_results
  bash scripts/phmm_throughput.sh "$INPUT_SIZE_PHMM" \
    | tee >(grep CUPS >> ../success.txt)
}

run_poa() {
  INPUT_SIZE_POA=1
  cd "$GenDP_WORK_DIR/gendp"
  python3 scripts/poa_generate_script.py \
    scripts/poa_throughput.sh kernel/poaV2/run.sh \
    "$INPUT_SIZE_POA" 1
  python3 scripts/preprocess_poa_datasets.py \
    "$GenDP_WORK_DIR/backtest-datasets/poa_input.fasta" \
    "$GenDP_WORK_DIR/backtest-datasets/poa/"
  cd kernel/poaV2
  make clean && make -j
  ./run.sh > log.txt 2>&1
  cd ../../
  bash scripts/poa_throughput.sh | tee >(grep CUPS >> ../success.txt)
}

run_wfa() {
  cd "$GenDP_WORK_DIR/gendp"
  python3 scripts/wfa_instruction_generator.py
  make -j ADDRESS_SANITIZER=0
  python3 scripts/wfa_check_correctness.py \
    "$GenDP_WORK_DIR/backtest-datasets/wfa/oneSeq.seq" -n 1
}

run_gwfa() {
  cd "$GenDP_WORK_DIR/gendp"
  # Mirror Makefile gate: skip GWFA when the kernel/Gwfa submodule
  # is absent. Otherwise ./sim is built without -DGWFA_BUILD and
  # `-k 7` exits non-zero, failing the backtest on fresh clones.
  if [ ! -f kernel/Gwfa/gwfa.c ]; then
    echo "run_gwfa: kernel/Gwfa submodule absent; skipping GWFA backtest."
    echo "GWFA: skipped (submodule absent)" >> "$GenDP_WORK_DIR/success.txt"
    return 0
  fi
  python3 scripts/gwfa_instruction_generator.py
  make -j ADDRESS_SANITIZER=0
  python3 scripts/gwfa_check_correctness.py 1
}

# Dispatch
case "$KERNEL" in
  ""|"all") run_bsw; run_chain; run_phmm; run_poa; run_wfa; run_gwfa ;;
  bsw)      run_bsw ;;
  chain)    run_chain ;;
  phmm|pairhmm) run_phmm ;;
  poa)      run_poa ;;
  wfa)      run_wfa ;;
  gwfa)     run_gwfa ;;
  *)
    echo "Unknown kernel '$KERNEL'. Valid: bsw, chain, phmm, poa, wfa, gwfa."
    exit 1
    ;;
esac

cd "$GenDP_WORK_DIR"
echo "======================================REFERENCE========================================"
echo "BSW Throughput: 47036245.456 MCUPS/mm2"
echo "Chain Throughput: 3612.677 MCUPS/mm2"
echo "PairHMM Throughput: 15142.282 MCUPS/mm2"
echo "POA Throughput: 2607.528 MCUPS/mm2" #3742.828
echo "=======================================RESULTS========================================="
cat success.txt
