#!/usr/bin/env bash
#
# Copy 3rdParty/LightPcapNg from a PcapPlusPlus commit into legacy/ and record the commit in legacy/UPSTREAM_COMMIT.
# This is the only supported way to change legacy/.
#
# Usage:
#   scripts/sync-legacy.sh [--check] [--repo <path-or-url>] [<ref>]
#
#   <ref>     PcapPlusPlus branch, tag or commit to sync from (default: master)
#   --repo    PcapPlusPlus repository, a URL or a local clone (default: https://github.com/seladb/PcapPlusPlus.git)
#   --check   Don't change anything; exit 1 if legacy/ differs from 3rdParty/LightPcapNg at <ref>
#
# After a sync, review the diff and stage it with `git add -f legacy`. The -f is needed because PcapPlusPlus tracks
# files that this repo's .gitignore (and LightPcapNg's own) would otherwise ignore, such as Makefile and *.cmake.

set -euo pipefail

REPO="https://github.com/seladb/PcapPlusPlus.git"
REF="master"
CHECK=0
UPSTREAM_DIR="3rdParty/LightPcapNg"

usage() {
  sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --repo) [[ $# -ge 2 ]] || usage 2; REPO="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    -*) echo "Unknown option: $1" >&2; usage 2 ;;
    *) REF="$1"; shift ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEGACY="$ROOT/legacy"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# A local clone needs an absolute path, since git runs from the temp directory below.
if [[ -d "$REPO" ]]; then
  REPO="$(cd "$REPO" && pwd)"
fi

echo "Fetching $REF from $REPO"
git -C "$WORK" init -q fetchrepo
git -C "$WORK/fetchrepo" fetch -q --depth 1 "$REPO" "$REF"
COMMIT="$(git -C "$WORK/fetchrepo" rev-parse FETCH_HEAD)"

mkdir "$WORK/upstream"
git -C "$WORK/fetchrepo" archive FETCH_HEAD "$UPSTREAM_DIR" | tar -x -C "$WORK/upstream"
SRC="$WORK/upstream/$UPSTREAM_DIR"
[[ -d "$SRC" ]] || { echo "error: $UPSTREAM_DIR not found at $COMMIT" >&2; exit 1; }

if [[ $CHECK -eq 1 ]]; then
  if diff -r --exclude=UPSTREAM_COMMIT "$SRC" "$LEGACY" >"$WORK/diff.txt"; then
    echo "legacy/ matches $UPSTREAM_DIR at $COMMIT"
    exit 0
  fi
  cat "$WORK/diff.txt"
  echo "legacy/ differs from $UPSTREAM_DIR at $COMMIT (synced from $(cat "$LEGACY/UPSTREAM_COMMIT" 2>/dev/null || echo unknown))"
  exit 1
fi

rm -rf "$LEGACY"
cp -R "$SRC" "$LEGACY"
echo "$COMMIT" >"$LEGACY/UPSTREAM_COMMIT"

echo "Synced legacy/ from PcapPlusPlus $COMMIT"
# TODO(M1): regenerate goldens from the legacy backend once the conformance tool and pytest runner exist.
echo "Review the changes, then stage them with: git add -f legacy"
