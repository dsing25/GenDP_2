#!/bin/bash
set -e

# Check for debug flag
DEBUG_FLAG=""
if [[ "$1" == "-d" ]] || [[ "$1" == "--debug" ]]; then
    DEBUG_FLAG="debug=1"
    echo "Building in DEBUG mode..."
else
    echo "Building in RELEASE mode..."
fi

python3 scripts/gbv_instruction_generator.py
make clean && make -j $DEBUG_FLAG
cp sim sim_gbv

./sim_gbv -k 6 -i ../gbv-dataset/gbvInput.txt -o gbvOutput.txt -s -n -1 > gbv_sim_results/gbv_sim_results.txt
