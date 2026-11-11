#!/usr/bin/env bash
# Benchmark one model on Strata (Niko1221/Strata): start its server, wait until it has loaded, run ./run.sh against it
# with --backend openai-ext, stop the server on any exit. Run it inside a lane window:
#   ./lanes-window.sh -- ./strata-run.sh ~/GIT/Strata-data/bench/coder-iq1_m.json -- --models X --task-group spot --out output/x.json
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
STRATA_DIR=${STRATA_DIR:-$HOME/GIT/Strata}
PORT=${STRATA_PORT:-8090}
LOAD_TIMEOUT=${STRATA_LOAD_TIMEOUT:-900}

[ $# -ge 2 ] && [ "$2" = "--" ] || { echo "usage: $0 <strata-config.json> -- <run.sh args>" >&2; exit 2; }
CONFIG=$(realpath "$1"); shift 2
URL="http://127.0.0.1:$PORT"
LOG="${CONFIG%.json}-server-$(date +%Y%m%d-%H%M%S).log"

if curl -s -m 2 "$URL/health" >/dev/null; then echo "strata-run: something already answers on $URL" >&2; exit 1; fi
VERSION=$(cd "$STRATA_DIR" && git describe --tags --always --dirty 2>/dev/null || echo unknown)

(cd "$STRATA_DIR" && exec .venv/bin/python serve/server.py --engine strata --config "$CONFIG" \
    --host 127.0.0.1 --port "$PORT") >"$LOG" 2>&1 &
SERVER=$!
stop_server() { kill "$SERVER" 2>/dev/null && wait "$SERVER" 2>/dev/null || true; }
trap stop_server EXIT

echo "strata-run: server pid $SERVER, log $LOG"
for ((i = 0; i < LOAD_TIMEOUT; i += 5)); do
    kill -0 "$SERVER" 2>/dev/null || { echo "strata-run: server exited during load; tail of $LOG:" >&2; tail -20 "$LOG" >&2; exit 1; }
    curl -s -m 5 "$URL/health" | grep -q '"loaded": *true' && break
    sleep 5
done
curl -s -m 5 "$URL/health" | grep -q '"loaded": *true' || { echo "strata-run: not loaded after ${LOAD_TIMEOUT}s" >&2; exit 1; }
echo "strata-run: loaded after ~${i}s"

"$HERE/run.sh" --backend openai-ext --ext-url "$URL" --ext-label "strata $VERSION $(basename "$CONFIG" .json)" "$@"
