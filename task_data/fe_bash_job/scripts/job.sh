#!/usr/bin/env bash
# Job fe-build <repo> <commit> (fastengine spec H05/H07): build a game at a commit from the box's bare repos and
# hand back its zips. The job runner sets AW_OUT (the run's output folder, inside a lane folder that outlives runs)
# and AW_RUN_ID; SOURCE holds the bare repos (<repo>.git). The commit's build.sh writes dist/*.zip.
# Contract: AW_OUT ends up with exactly this run's zips, its build.log (this run only) and manifest.json
# ({"files": [{"name", "size", "sha256"}]} for every zip in AW_OUT, sorted by name), and nothing else.
# Work happens outside the run's tree, under ${XDG_CACHE_HOME:-~/.cache}/fastengine/jobs/$AW_RUN_ID, removed at
# the end. Exit 0 ok, 1 build (a commit that is not there, or build.sh failing), 4 environment (no such source
# repo, AW_OUT/AW_RUN_ID unset, a clone that fails). A failed step stops the job: nothing after it runs.
set -uo pipefail
repo=$1 ref=$2 out=$AW_OUT
exec > >(tee -a "$out/build.log") 2>&1
echo "== clone $repo $ref"
git clone --quiet "$SOURCE/$repo.git" "$out/src"
cd "$out/src"
git -c advice.detachedHead=false checkout --quiet "$ref"
echo "== build"
./build.sh
cp dist/*.zip "$out/"
python3 - "$out" <<'PY'
import hashlib, json, os, sys
out = sys.argv[1]
files = [{"name": n, "size": os.path.getsize(os.path.join(out, n)),
          "sha256": hashlib.sha256(open(os.path.join(out, n), 'rb').read()).hexdigest()}
         for n in sorted(os.listdir(out)) if n.endswith('.zip')]
json.dump({"files": files}, open(os.path.join(out, 'manifest.json'), 'w'), indent=2)
PY
echo "== done"
