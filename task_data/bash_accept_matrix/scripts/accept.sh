#!/usr/bin/env bash
# Usage: scripts/accept.sh [game...]   (default: every games/*/)
# Milestone acceptance: test.sh, then build and smoke both targets per game,
# plus the scripted play run (smoke.sh ... play) where smoke.env has PLAY_ARGS.
set -euo pipefail
. "$(dirname "$0")/common.sh"
ensure_docker "$@"

games=("$@")
if [[ ${#games[@]} -eq 0 ]]; then
  for dir in games/*/; do games+=("$(basename "$dir")"); done
fi

scripts/test.sh > /dev/null 2>&1

for game in "${games[@]}"; do
  for target in linux64 win64; do
    scripts/build.sh "$game" "$target" > /dev/null 2>&1
    scripts/smoke.sh "$game" "$target" > /dev/null 2>&1
    if grep -q '^PLAY_ARGS=' "games/$game/smoke.env"; then
      scripts/smoke.sh "$game" "$target" play > /dev/null 2>&1
    fi
    echo "$game $target: pass"
  done
done
