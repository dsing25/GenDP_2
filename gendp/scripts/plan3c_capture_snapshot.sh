#!/bin/bash
# Plan 3c frozen-oracle snapshot capture.
#
# Rebuilds sim with -DPLAN3C_TRACE_SNAPSHOT, runs the GWFA dataset's
# case 0 once, and writes the resulting per-magic observable dumps
# under tests/frozen/plan3c_pre_l6a/. Invoked by l6 and re-runnable
# at any time to verify a lowered m33/m35/m37 matches the baseline.
#
# Usage:
#   scripts/plan3c_capture_snapshot.sh [N]
# where N is the number of cases to run (default 1).

set -e
set -o pipefail

N="${1:-1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP_DIR="$REPO_ROOT/kernel/Gwfa/Datasets/Gwfa295"
FROZEN_DIR="$REPO_ROOT/tests/frozen/plan3c_pre_l6a"

cd "$REPO_ROOT"
mkdir -p "$FROZEN_DIR"

echo "[plan3c-snap] make clean + rebuild with plan3c_snap=1"
make clean > /dev/null 2>&1
make -j ADDRESS_SANITIZER=0 plan3c_snap=1 > /tmp/plan3c_snap_build.log 2>&1
if [ $? -ne 0 ]; then
    echo "BUILD FAILED (see /tmp/plan3c_snap_build.log)"
    exit 1
fi

echo "[plan3c-snap] removing stale snapshot files"
rm -f plan3c_snapshot_m33.txt plan3c_snapshot_m35.txt plan3c_snapshot_m37.txt

echo "[plan3c-snap] running sim -k 7 -n $N on $DUMP_DIR"
./sim -k 7 -i "$DUMP_DIR" -n "$N" > /tmp/plan3c_snap_sim.out 2> /tmp/plan3c_snap_sim.err

echo "[plan3c-snap] moving snapshots into $FROZEN_DIR"
for f in plan3c_snapshot_m33.txt plan3c_snapshot_m35.txt \
         plan3c_snapshot_m37.txt; do
    if [ -f "$f" ]; then
        mv "$f" "$FROZEN_DIR/$f"
    else
        echo "WARNING: $f not generated (magic did not execute?)"
    fi
done

echo "[plan3c-snap] rebuilding without snapshot flag (restore default sim)"
make clean > /dev/null 2>&1
make -j ADDRESS_SANITIZER=0 > /tmp/plan3c_snap_restore.log 2>&1

echo "[plan3c-snap] done. Files in $FROZEN_DIR:"
ls -la "$FROZEN_DIR" | grep plan3c_snapshot
