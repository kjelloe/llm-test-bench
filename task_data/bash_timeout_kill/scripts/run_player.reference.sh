#!/usr/bin/env bash
# Usage: scripts/run_player.sh <seconds> <command> [args...]
# Runs a headless game player for a smoke test and stops it after <seconds>.
set -uo pipefail
seconds=$1
shift
# A Unity player can ignore SIGTERM; -k sends SIGKILL 5 seconds later.
timeout -k 5 "$seconds" "$@"
status=$?
# 124: stopped by SIGTERM; 137 (128 + KILL): it needed the SIGKILL.
if [[ $status -eq 124 || $status -eq 137 ]]; then
  echo "run_player: timed out after ${seconds}s" >&2
  exit 124
fi
exit $status
