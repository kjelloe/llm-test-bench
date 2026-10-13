#!/usr/bin/env bash
set -uo pipefail
EXIT_BUILD=1 EXIT_ENV=4
(($# == 2)) || { echo "usage: job.sh <repo> <commit>" >&2; exit "$EXIT_ENV"; }
[[ -n ${AW_OUT:-} && -n ${AW_RUN_ID:-} ]] || { echo "AW_OUT and AW_RUN_ID must be set" >&2; exit "$EXIT_ENV"; }
repo=$1 ref=$2 out=$AW_OUT
work=${XDG_CACHE_HOME:-$HOME/.cache}/fastengine/jobs/$AW_RUN_ID
mkdir -p "$out" || exit "$EXIT_ENV"
find "$out" -mindepth 1 -delete
mkdir -p "$work" || exit "$EXIT_ENV"
trap 'rm -rf "$work"' EXIT
exec > >(tee "$out/build.log") 2>&1
src=$SOURCE/$repo.git
[[ -d $src ]] || { echo "no source repo $src" >&2; exit "$EXIT_ENV"; }
echo "== clone $repo $ref"
git clone --quiet --no-checkout "$src" "$work/src" || exit "$EXIT_ENV"
git -C "$work/src" -c advice.detachedHead=false checkout --quiet "$ref" 2>/dev/null ||
  { echo "commit $ref is not in $src" >&2; exit "$EXIT_BUILD"; }
echo "== build"
(cd "$work/src" && ./build.sh) || exit "$EXIT_BUILD"
shopt -s nullglob
zips=("$work"/src/dist/*.zip)
((${#zips[@]})) || { echo "build.sh made no zip" >&2; exit "$EXIT_BUILD"; }
cp "${zips[@]}" "$out/" || exit "$EXIT_BUILD"
python3 - "$out" <<'PY'
import hashlib, json, os, sys
out = sys.argv[1]
files = [{"name": n, "size": os.path.getsize(os.path.join(out, n)),
          "sha256": hashlib.sha256(open(os.path.join(out, n), 'rb').read()).hexdigest()}
         for n in sorted(os.listdir(out)) if n.endswith('.zip')]
json.dump({"files": files}, open(os.path.join(out, 'manifest.json'), 'w'), indent=2)
PY
echo "== done"
