#!/usr/bin/env bash
# Shuts down cleanly on SIGTERM, writing a marker first.
trap 'echo graceful > "$1"; exit 0' TERM
while :; do sleep 0.1; done
