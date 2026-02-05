#!/bin/bash
set -e

python3 scripts/gbv_instruction_generator.py
make clean && make -j
cp sim sim_gbv

./sim_gbv -k 6 -i ../gbv-dataset/gbv.seq -o gbvOutput.txt -s -n -1 > gbv_sim_results/gbv_sim_results.txt