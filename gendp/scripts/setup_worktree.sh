#!/bin/bash
# setup_worktree.sh — Make a fresh git worktree runnable end-to-end.
#
# Creates dataset symlinks and initializes the Gwfa submodule (required
# by gendp/Makefile via kernel/Gwfa/gwfa.c).
#
# Usage:
#   bash gendp/scripts/setup_worktree.sh           # set up current worktree (cwd)
#   bash gendp/scripts/setup_worktree.sh <path>    # set up worktree at <path>
#
# Assumptions:
#   - Worktrees live as siblings of the main repo (../kernel/ shared).
#   - Shared datasets sit at ../kernel/gendp-datasets and
#     ../kernel/backtest-datasets relative to the worktree root.

set -e

WORKTREE_ROOT="${1:-$(pwd)}"
WORKTREE_ROOT="$(cd "$WORKTREE_ROOT" && pwd)"

if [[ ! -d "$WORKTREE_ROOT/gendp" ]]; then
  echo "ERROR: '$WORKTREE_ROOT' does not look like a gdp worktree (no gendp/ dir)" >&2
  exit 1
fi

SHARED_DIR="$(cd "$WORKTREE_ROOT/.." && pwd)/kernel"

if [[ ! -d "$SHARED_DIR/gendp-datasets" || ! -d "$SHARED_DIR/backtest-datasets" ]]; then
  echo "ERROR: shared datasets missing at $SHARED_DIR" >&2
  echo "       expected gendp-datasets/ and backtest-datasets/" >&2
  exit 1
fi

# Dataset symlinks (idempotent)
for name in gendp-datasets backtest-datasets; do
  link="$WORKTREE_ROOT/$name"
  target="../kernel/$name"
  if [[ -L "$link" ]]; then
    echo "  symlink already present: $name"
  elif [[ -e "$link" ]]; then
    echo "ERROR: $link exists and is not a symlink; refusing to overwrite" >&2
    exit 1
  else
    ln -s "$target" "$link"
    echo "  created symlink: $name -> $target"
  fi
done

# Gwfa submodule (needed by gendp/Makefile)
cd "$WORKTREE_ROOT"
if [[ ! -f gendp/kernel/Gwfa/gwfa.c ]]; then
  echo "  initializing gendp/kernel/Gwfa submodule..."
  git submodule update --init gendp/kernel/Gwfa
else
  echo "  submodule already present: gendp/kernel/Gwfa"
fi

# Build sim once up-front — chain's kernel depends on ../../*.o from
# gendp/. check_all.py does its own `make clean && make` later; the
# kernel binaries we build below survive because they live in their
# own subdirs.
if [[ ! -f "$WORKTREE_ROOT/gendp/comp_decoder.o" ]]; then
  echo "  building gendp/sim (ADDRESS_SANITIZER=0)..."
  if ! make -C "$WORKTREE_ROOT/gendp" -j ADDRESS_SANITIZER=0 \
         > /tmp/setup_worktree_sim.log 2>&1; then
    echo "ERROR: sim build failed; see /tmp/setup_worktree_sim.log" >&2
    exit 1
  fi
fi

# Kernel reference binaries used by check_all.py to regenerate goldens.
# These are build artifacts (not tracked in git), so a fresh worktree
# lacks them and check_all.py fails with "No such file" / exit=127.
build_kernel() {
  local dir="$1" binary="$2" makefile="$3" target="$4"
  local path="$WORKTREE_ROOT/gendp/kernel/$dir/$binary"
  if [[ -x "$path" ]]; then
    echo "  kernel already built: $dir/$binary"
    return
  fi
  echo "  building kernel: $dir/$binary"
  if ! make -C "$WORKTREE_ROOT/gendp/kernel/$dir" -f "$makefile" -j $target \
         > /tmp/setup_worktree_$dir.log 2>&1; then
    echo "ERROR: build failed for $dir; see /tmp/setup_worktree_$dir.log" >&2
    exit 1
  fi
}

build_kernel chain   chain    Makefile  release
build_kernel PairHMM pairhmm  makefile  project_code
build_kernel poaV2   poa      Makefile  all

echo ""
echo "Worktree ready: $WORKTREE_ROOT"
echo "Run checks:    cd $WORKTREE_ROOT/gendp && python3 scripts/check_all.py"
