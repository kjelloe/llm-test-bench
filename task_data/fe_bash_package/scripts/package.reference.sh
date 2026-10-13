#!/usr/bin/env bash
# Usage: scripts/package.sh <game-dir> [linux64|win64 ...]   (or linux64,win64, as build.sh takes them)
# Zips the last build of each target into dist/<product>-fe-<version>-<target>.zip with one top folder,
# <product>-fe/. The product name is in <game-dir>/product.txt. Each build is <game-dir>/Build/<target>/ and its
# log <game-dir>/Build/<target>.build has lines "[Build] version=<version> ..."; the last one is the build's
# version. A build of uncommitted code (version ending in -dirty) is refused unless ALLOW_DIRTY=1. A target that
# was never built (no folder, or no stamped version) must stop the script with a message naming the target and
# how to build it, exit 1. With no targets: linux64 and win64.
set -euo pipefail
game=${1:?usage: package.sh <game-dir> [linux64|win64 ...]}
shift
logs=$game/Build
product=$(cat "$game/product.txt")
IFS=', ' read -ra targets <<< "$*"
[[ ${#targets[@]} -gt 0 ]] || targets=(linux64 win64)
mkdir -p dist
for target in "${targets[@]}"; do
  dir=$logs/$target
  version=$(sed -n 's/^\[Build\] version=\([^ ]*\) .*/\1/p' "$logs/$target.build" 2>/dev/null | tail -1 || true)
  [[ -d $dir && -n $version ]] || { echo "no stamped $target build of $game; run scripts/build.sh $game $target" >&2; exit 1; }
  [[ $version != *-dirty || -n ${ALLOW_DIRTY:-} ]] || { echo "$target build of $game is from uncommitted code ($version); commit and rebuild, or ALLOW_DIRTY=1" >&2; exit 1; }
  zip=dist/$product-fe-$version-$target.zip
  rm -f "$zip"
  python3 - "$dir" "$zip" "$product-fe" <<'PY'
import os, sys, zipfile
src, out, top = sys.argv[1:]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(src):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.join(top, os.path.relpath(p, src)))
PY
  echo "packaged $zip"
done
