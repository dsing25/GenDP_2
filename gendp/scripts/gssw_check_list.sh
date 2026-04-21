#!/usr/bin/env bash
# Check a list of GSSW failing indices. One index per arg.
# Prints "IDX: sim=X golden=Y [OK|FAIL]" per line.
set -e
cd "$(dirname "$0")/.."
for idx in "$@"; do
  out=$(python3 scripts/gssw_run_one.py "$idx" 2>/dev/null | tail -1)
  echo "$idx: $out"
done
