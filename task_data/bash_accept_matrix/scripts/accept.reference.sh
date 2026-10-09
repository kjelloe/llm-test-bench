#!/usr/bin/env bash
# Usage: scripts/accept.sh [game...]   (default: every games/*/)
# Milestone acceptance: test.sh, then build and smoke both targets per game,
# plus the scripted play run (smoke.sh ... play) where smoke.env has PLAY_ARGS.
# Runs everything even after a failure and exits non-zero if anything failed.
set -uo pipefail
. "$(dirname "$0")/common.sh"
ensure_docker "$@"

games=("$@")
if [[ ${#games[@]} -eq 0 ]]; then
  for dir in games/*/; do games+=("$(basename "$dir")"); done
fi

scripts/test.sh > /dev/null 2>&1 || { echo "scripts/test.sh failed; run it for details" >&2; exit 1; }

failed=0
for game in "${games[@]}"; do
  for target in linux64 win64; do
    if scripts/build.sh "$game" "$target" > /dev/null 2>&1; then
      if ! scripts/smoke.sh "$game" "$target" > /dev/null 2>&1; then
        result="SMOKE FAIL (games/$game/Build/smoke-$target-player.log)"
      elif grep -q '^PLAY_ARGS=' "games/$game/smoke.env" \
          && ! scripts/smoke.sh "$game" "$target" play > /dev/null 2>&1; then
        result="PLAY FAIL (games/$game/Build/play-$target-player.log)"
      else
        result=pass
      fi
    else
      result="BUILD FAIL (games/$game/Build/$target.log)"
    fi
    [[ $result == pass ]] || failed=1
    echo "$game $target: $result"
  done
done
exit $failed
