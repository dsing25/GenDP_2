#!/bin/bash
# create_worktree.sh — Create a new worktree at <path>, new branch named
# after its basename, then run setup_worktree.sh. Does not run check_all.
#
# Usage:
#   bash gendp/scripts/create_worktree.sh path/to/gdpBar

set -e

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <worktree_path>" >&2
  exit 1
fi

# Resolve the user's path against their cwd (before we cd away),
# so relative paths work the way they expect.
case "$1" in
  /*) WORKTREE_PATH="$1" ;;
  *)  WORKTREE_PATH="$(pwd)/$1" ;;
esac
BRANCH="$(basename "$WORKTREE_PATH")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -e "$WORKTREE_PATH" ]]; then
  echo "ERROR: $WORKTREE_PATH already exists" >&2
  exit 1
fi

# Run from the repo so git worktree add works no matter where the user is.
cd "$REPO_ROOT"
git worktree add "$WORKTREE_PATH" -b "$BRANCH"
bash "$SCRIPT_DIR/setup_worktree.sh" "$WORKTREE_PATH"
