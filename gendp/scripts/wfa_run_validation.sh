#!/bin/bash
# WFA Validation Runner - Rebuild simulator and run validation tests
# Usage: bash scripts/run_wfa_validation.sh [seq_file] [num_tests]

set -e  # Exit on error

# Default values
SEQ_FILE="${1:-../../kernel/Datasets/seq10k.seq}"
NUM_TESTS="${2:-200}"

echo "============================================================"
echo "WFA Validation Test Suite"
echo "============================================================"
echo "Sequence file: $SEQ_FILE"
echo "Number of tests: $NUM_TESTS"
echo ""

# Step 1: Regenerate instructions
echo "Step 1: Regenerating WFA instructions..."
python scripts/wfa_instruction_generator.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to generate instructions"
    exit 1
fi
echo "✓ Instructions generated"
echo ""

# Step 2: Clean and rebuild simulator
echo "Step 2: Rebuilding simulator..."
make clean > /dev/null 2>&1
make -j
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to build simulator"
    exit 1
fi
echo "✓ Simulator built successfully"
echo ""

# Step 3: Run validation tests
echo "Step 3: Running validation tests..."
echo "------------------------------------------------------------"
python3 scripts/wfa_check_correctness.py "$SEQ_FILE" -n "$NUM_TESTS"
TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo "============================================================"
    echo "✓ ALL TESTS PASSED"
    echo "============================================================"
else
    echo "============================================================"
    echo "✗ SOME TESTS FAILED"
    echo "============================================================"
fi

exit $TEST_RESULT
