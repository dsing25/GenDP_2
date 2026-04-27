#!/bin/bash
# Plan 3d frozen-oracle snapshot capture (PE-side magics 19/22/23).
#
# Rebuilds sim with -DPLAN3D_TRACE_SNAPSHOT, runs the GWFA dataset's
# case 0 once, and writes the resulting per-PE-magic observable dumps
# under tests/frozen/plan3d_pre_l8a/. Invoked by l8 and re-runnable
# at any time to verify a lowered PE 19 / 22 / 23 matches the baseline.
#
# Usage:
#   scripts/plan3d_capture_snapshot.sh [N]
# where N is the number of cases to run (default 1).

set -e
set -o pipefail

N="${1:-1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP_DIR="$REPO_ROOT/kernel/Gwfa/Datasets/Gwfa295"
FROZEN_DIR="$REPO_ROOT/tests/frozen/plan3d_pre_l8a"

cd "$REPO_ROOT"
mkdir -p "$FROZEN_DIR"

echo "[plan3d-snap] make clean + rebuild with plan3d_snap=1"
make clean > /dev/null 2>&1
make -j ADDRESS_SANITIZER=0 plan3d_snap=1 > ${TMPDIR:-/tmp}/plan3d_snap_build.log 2>&1
if [ $? -ne 0 ]; then
    echo "BUILD FAILED (see ${TMPDIR:-/tmp}/plan3d_snap_build.log)"
    exit 1
fi

echo "[plan3d-snap] removing stale snapshot files"
rm -f plan3d_snapshot_pe19.txt plan3d_snapshot_pe22.txt \
      plan3d_snapshot_pe23.txt

echo "[plan3d-snap] running sim -k 7 -n $N on $DUMP_DIR"
./sim -k 7 -i "$DUMP_DIR" -n "$N" > ${TMPDIR:-/tmp}/plan3d_snap_sim.out 2> ${TMPDIR:-/tmp}/plan3d_snap_sim.err

echo "[plan3d-snap] moving snapshots into $FROZEN_DIR"
for f in plan3d_snapshot_pe19.txt plan3d_snapshot_pe22.txt \
         plan3d_snapshot_pe23.txt; do
    if [ -f "$f" ]; then
        mv "$f" "$FROZEN_DIR/$f"
    else
        echo "WARNING: $f not generated (PE magic did not execute?)"
    fi
done

echo "[plan3d-snap] rebuilding without snapshot flag (restore default sim)"
make clean > /dev/null 2>&1
make -j ADDRESS_SANITIZER=0 > ${TMPDIR:-/tmp}/plan3d_snap_restore.log 2>&1

echo "[plan3d-snap] done. Files in $FROZEN_DIR:"
ls -la "$FROZEN_DIR" | grep plan3d_snapshot
