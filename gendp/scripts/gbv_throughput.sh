#!/bin/bash
set -e

# Check for debug or profile flag
BUILD_FLAG=""
BUILD_MODE="RELEASE"
OUTPUT_FILE="gbv_sim_results/gbv_results.txt"

if [[ "$1" == "-d" ]] || [[ "$1" == "--debug" ]]; then
    BUILD_FLAG="debug=1"
    BUILD_MODE="DEBUG"
    OUTPUT_FILE="gbv_sim_results/gbv_debug.txt"
elif [[ "$1" == "-p" ]] || [[ "$1" == "--profile" ]]; then
    BUILD_FLAG="profile=1"
    BUILD_MODE="PROFILE"
    OUTPUT_FILE="gbv_sim_results/gbv_profile.txt"
fi
echo "Building in $BUILD_MODE mode..."

python3 scripts/gbv_instruction_generator.py
make clean && make -j $BUILD_FLAG
cp sim sim_gbv

./sim_gbv -k 6 -i ../gbv-dataset/gbvInput.txt -o gbvOutput.txt -s -n -1 > "$OUTPUT_FILE"
echo "Output written to: $OUTPUT_FILE"
