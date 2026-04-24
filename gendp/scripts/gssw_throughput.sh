#!/bin/bash
# GSSW throughput wrapper: regenerate instructions, rebuild sim, run throughput.
# Usage: bash scripts/gssw_throughput.sh <1|2> [-t N]
#   1: fast (1000 cases)   2: full (entire dataset)   -t N: parallel procs
set -e

python3 scripts/gssw_instruction_generator.py
make -j
python3 scripts/gssw_throughput.py "$@"
