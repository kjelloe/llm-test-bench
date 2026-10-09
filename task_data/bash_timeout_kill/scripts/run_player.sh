#!/usr/bin/env bash
# Usage: scripts/run_player.sh <seconds> <command> [args...]
# Runs a headless game player for a smoke test and stops it after <seconds>.
set -uo pipefail
seconds=$1
shift
timeout "$seconds" "$@"
