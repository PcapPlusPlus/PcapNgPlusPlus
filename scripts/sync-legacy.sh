#!/usr/bin/env bash
#
# Copy 3rdParty/LightPcapNg from a PcapPlusPlus commit into legacy/ and record the commit in legacy/UPSTREAM_COMMIT.
# This is the only supported way to change legacy/.
#
# Usage:
#   scripts/sync-legacy.sh [--check] [--no-regen] [--repo <path-or-url>] [<ref>]
#
#   <ref>       PcapPlusPlus branch, tag or commit to sync from (default: master)
#   --repo      PcapPlusPlus repository, a URL or a local clone (default: https://github.com/seladb/PcapPlusPlus.git)
#   --check     Don't change anything; exit 1 if legacy/ differs from 3rdParty/LightPcapNg at <ref>
#   --no-regen  Don't regenerate the goldens after syncing
#
# After syncing, the script builds the tool (Release, with zstd) in build-golden/ and regenerates the goldens from
# legacy. That needs CMake, zstd and Python with conformance/requirements.txt installed; set PYTHON to pick the
# interpreter (default: python3).
#
# Review the diff of legacy/ and conformance/golden/, then stage it with `git add -f legacy conformance/golden`. The
# -f is needed because PcapPlusPlus tracks files that this repo's .gitignore (and LightPcapNg's own) would otherwise
# ignore, such as Makefile and *.cmake.

set -euo pipefail

REPO="https://github.com/seladb/PcapPlusPlus.git"
REF="master"
CHECK=0
REGEN=1
UPSTREAM_DIR="3rdParty/LightPcapNg"

usage() {
  sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --no-regen) REGEN=0; shift ;;
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

if [[ $REGEN -eq 1 ]]; then
  # Goldens must come from a Release build with zstd: in Debug, legacy's assert() calls can abort on malformed inputs,
  # and without zstd the .zst cases are skipped.
  GOLDEN_BUILD="$ROOT/build-golden"
  echo "Building the tool in $GOLDEN_BUILD"
  cmake -S "$ROOT" -B "$GOLDEN_BUILD" -DCMAKE_BUILD_TYPE=Release -DLIGHT_PCAPNG_ZSTD=ON >/dev/null
  cmake --build "$GOLDEN_BUILD" --config Release -j >/dev/null

  TOOL="$GOLDEN_BUILD/conformance/tool/pcapng-conformance-tool"
  [[ -x "$TOOL" ]] || TOOL="$GOLDEN_BUILD/conformance/tool/Release/pcapng-conformance-tool.exe"

  echo "Regenerating goldens"
  (cd "$ROOT/conformance" && "${PYTHON:-python3}" -m pytest -q --tool-path="$TOOL" --regen-golden)
fi

echo "Review the changes, then stage them with: git add -f legacy conformance/golden"
