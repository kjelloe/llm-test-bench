#!/usr/bin/env bash
# Usage: scripts/version.sh <game-repo>   (run from the fastengine repo's root)
game_repo=${1:?usage: version.sh <game-repo>}
fe=$(git rev-parse --short HEAD 2>/dev/null || echo uncommitted)
game=$(git -C "$game_repo" rev-parse --short HEAD 2>/dev/null || echo uncommitted)
dirty=""
[[ -z $(git status --porcelain 2>/dev/null) && -z $(git -C "$game_repo" status --porcelain 2>/dev/null) ]] || dirty="-dirty"
echo "$(date +%Y.%m.%d)-$fe-$game$dirty"
