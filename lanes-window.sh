#!/usr/bin/env bash
# Run a GPU benchmark in a quiet window of llm-service-provider's local lane, which holds every GPU on this rig.
#
# usage: ./lanes-window.sh [--idle MIN] [--poll S] -- ./run.sh ...
#
# Waits until no helper request has reached the lane for MIN minutes (default 30; `llmctl idle`), stops the
# backend, runs the command, and starts the backend again however the command ends (also on Ctrl-C). A helper
# that comes back meanwhile gets 503 until then. When the backend is not running at the start, it is left alone.
# LLMCTL overrides the llmctl path (tests).
set -uo pipefail
LLMCTL=${LLMCTL:-$HOME/GIT/llm-service-provider/bin/llmctl}
IDLE=30 POLL=60
while [ $# -gt 0 ]; do
    case "$1" in
        --idle) IDLE=$2; shift 2 ;;
        --poll) POLL=$2; shift 2 ;;
        --) shift; break ;;
        *) break ;;
    esac
done
[ $# -gt 0 ] || { echo "usage: $0 [--idle MIN] [--poll S] -- command..." >&2; exit 2; }

running() {
    local u
    for u in $("$LLMCTL" units); do systemctl is-active --quiet "$u.service" && return 0; done
    return 1
}

if ! running; then
    echo "[lanes] backend not running; running the command without touching it"
    exec "$@"
fi
until "$LLMCTL" idle "$IDLE"; do sleep "$POLL"; done
"$LLMCTL" stop || { echo "[lanes] could not stop the backend" >&2; exit 1; }
trap '"$LLMCTL" start || echo "[lanes] restart FAILED: run $LLMCTL start (power limits? clocks?)" >&2' EXIT
echo "[lanes] backend stopped for: $*"
"$@"
