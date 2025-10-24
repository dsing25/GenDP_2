#!/bin/bash
set -e

python3 scripts/wfa_instruction_generator.py
make clean && make -j
cp sim sim_wfa

./sim_wfa -k 5 -i ../backtest-datasets/wfa/oneSeq.seq -o wfaOneSeqOutput.txt -s -n -1 >  wfa_sim_results/wfa_sim_results.txt
cat wfa_sim_results/wfa_sim_results.txt
