#!/usr/bin/env bash
# Like a Unity player stuck in a native call: ignores SIGTERM. Writes its pid.
trap '' TERM
echo $$ > "$1"
while :; do sleep 0.1; done
