#!/bin/bash

python3 scripts/poa_instruction_generator.py
make clean && make -j
cp sim sim_poa_throughput

num_thread_group=10
num_threads=1

for i in {0..9}
do
  ./sim_poa_throughput -k 3 -i ../gendp-datasets/poa/input/input_$((i*num_threads+1)) -o poa_output/output_$((i*num_threads+1)) -s > poa_sim_results/sim_result_$((i*num_threads+1)).txt &
  P1=$!
  wait $P1
done

for i in {0..9}
do
  python3 scripts/poa_check_correctness.py poa_output/output_$((i*num_threads+1)) ../gendp-datasets/poa/output/output_$((i*num_threads+1)) 0 > poa_correctness/poa_$((i*num_threads+1)).txt &
  P1=$!
  wait $P1
done

python3 scripts/poa_throughput.py poa_sim_results poa_correctness 10
