#!/usr/bin/env bash
# Usage: scripts/version.sh <game-repo>   (run from the fastengine repo's root)
# Prints the version a build is stamped with: YYYY.MM.DD-<fastengine commit>-<game commit>[-dirty] (fastengine
# spec F01). The zip carries the game's server too, so both short commits name it; -dirty when either tree has
# any uncommitted change (edited, staged or untracked files). A repo with no commit yet gives "uncommitted" in
# its place. The date is today's local date. One line on stdout, exit 0.
game_repo=${1:?usage: version.sh <game-repo>}
fe=$(git rev-parse --short HEAD)
game=$(git -C "$game_repo" rev-parse --short HEAD)
dirty=""
git diff --quiet || dirty="-dirty"
echo "$(date +%Y.%m.%d)-$fe-$game$dirty"
