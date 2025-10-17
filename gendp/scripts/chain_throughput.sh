#!/bin/bash

INPUT_SIZE_CHAIN=$1
INPUT_FILE=$2

python3 scripts/chain_instruction_generator.py
make clean && make -j
cp sim sim_chain

./sim_chain -k 4 -i $INPUT_FILE -n $INPUT_SIZE_CHAIN -o chain_output.txt -s > chain_sim_results/chain_sim_result.txt
python3 scripts/chain_check_correctness.py ../gendp-datasets/chain_output.txt chain_output.txt > chain_correctness.txt
python3 scripts/chain_throughput.py chain_sim_results/chain_sim_result.txt chain_correctness.txt
