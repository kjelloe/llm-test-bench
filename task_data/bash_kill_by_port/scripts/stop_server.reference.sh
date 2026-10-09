#!/usr/bin/env bash
# Usage: scripts/stop_server.sh <port>
# Stops the local game server listening on <port> between smoke runs.
set -uo pipefail
port=$1

# By the listening socket, not by command line: a pattern also matches this script,
# the shell that ran it and anything else that mentions the port.
listeners() { ss -Hltnp "sport = :$port" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u; }

wait_free() {
  local tries=$1
  for ((i = 0; i < tries; i++)); do
    [[ -z $(listeners) ]] && return 0
    sleep 0.1
  done
  return 1
}

mapfile -t pids < <(listeners)
if [[ ${#pids[@]} -eq 0 ]]; then
  echo "stop_server: nothing listening on port $port" >&2
  exit 1
fi
kill -TERM "${pids[@]}" 2>/dev/null
if ! wait_free 30; then
  kill -KILL "${pids[@]}" 2>/dev/null
  wait_free 20 || { echo "stop_server: port $port is still in use" >&2; exit 1; }
fi
for pid in "${pids[@]}"; do echo "stopped $pid"; done
