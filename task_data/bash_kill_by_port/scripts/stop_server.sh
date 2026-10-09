#!/usr/bin/env bash
# Usage: scripts/stop_server.sh <port>
# Stops the local game server listening on <port> between smoke runs.
set -uo pipefail
port=$1
pkill -f "$port" && echo "stopped server on port $port"
