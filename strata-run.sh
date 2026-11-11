#!/usr/bin/env bash
# Benchmark one model on a Strata engine: start its server, wait until it serves, run ./run.sh against it with
# --backend openai-ext, stop the server on any exit. Run it inside a lane window. Two unrelated engines share the name:
#   Niko1221/Strata (~/GIT/Strata, GGUF; a JSON config names model and flags):
#     ./lanes-window.sh -- ./strata-run.sh ~/GIT/Strata-data/bench/coder-iq1_m.json -- --models X --task-group spot
#   ro99/strata (~/GIT/strata_other, safetensors; strata-server flags after --ro99):
#     ./lanes-window.sh -- ./strata-run.sh --ro99 --model DIR --model-type glm53 --model-id glm53 --devices 0,1,2 \
#         --context-size 32768 -- --models X --task-group spot
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
PORT=${STRATA_PORT:-8090}
LOAD_TIMEOUT=${STRATA_LOAD_TIMEOUT:-1800}
URL="http://127.0.0.1:$PORT"
usage() { echo "usage: $0 <niko-config.json> -- <run.sh args>  |  $0 --ro99 <strata-server args> -- <run.sh args>" >&2; exit 2; }

SERVER_ARGS=()
if [ "${1:-}" = "--ro99" ]; then
    ENGINE=ro99; shift
    ENGINE_DIR=${STRATA_RO99_DIR:-$HOME/GIT/strata_other}
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do SERVER_ARGS+=("$1"); shift; done
    NAME=$(printf '%s\n' "${SERVER_ARGS[@]}" | grep -A1 -x -- '--model-id' | tail -1 || true)
    LOG_DIR=${STRATA_LOG_DIR:-$ENGINE_DIR/bench-logs}
else
    ENGINE=niko
    ENGINE_DIR=${STRATA_DIR:-$HOME/GIT/Strata}
    [ $# -ge 1 ] || usage
    CONFIG=$(realpath "$1"); shift
    NAME=$(basename "$CONFIG" .json)
    LOG_DIR=$(dirname "$CONFIG")
fi
[ "${1:-}" = "--" ] || usage
shift
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/${NAME:-model}-server-$(date +%Y%m%d-%H%M%S).log"

if curl -s -m 2 "$URL/v1/models" >/dev/null; then echo "strata-run: something already answers on $URL" >&2; exit 1; fi
VERSION=$(cd "$ENGINE_DIR" && git describe --tags --always --dirty 2>/dev/null || echo unknown)

if [ "$ENGINE" = ro99 ]; then
    (cd "$ENGINE_DIR" && exec ./build/strata-server "${SERVER_ARGS[@]}" --host 127.0.0.1 --port "$PORT") >"$LOG" 2>&1 &
else
    (cd "$ENGINE_DIR" && exec .venv/bin/python serve/server.py --engine strata --config "$CONFIG" \
        --host 127.0.0.1 --port "$PORT") >"$LOG" 2>&1 &
fi
SERVER=$!
stop_server() { kill "$SERVER" 2>/dev/null && wait "$SERVER" 2>/dev/null || true; }
trap stop_server EXIT

ready() {
    if [ "$ENGINE" = ro99 ]; then curl -sf -m 5 "$URL/v1/health" >/dev/null && curl -s -m 5 "$URL/v1/models" | grep -q '"id"'
    else curl -s -m 5 "$URL/health" | grep -q '"loaded": *true'; fi
}
echo "strata-run: $ENGINE server pid $SERVER, log $LOG"
for ((i = 0; i < LOAD_TIMEOUT; i += 5)); do
    kill -0 "$SERVER" 2>/dev/null || { echo "strata-run: server exited during load; tail of $LOG:" >&2; tail -20 "$LOG" >&2; exit 1; }
    ready && break
    sleep 5
done
ready || { echo "strata-run: not serving after ${LOAD_TIMEOUT}s" >&2; exit 1; }
echo "strata-run: serving after ~${i}s"

"$HERE/run.sh" --backend openai-ext --ext-url "$URL" --ext-label "strata-$ENGINE $VERSION $NAME" "$@"
