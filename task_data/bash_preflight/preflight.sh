#!/usr/bin/env bash
# preflight.sh — check required tools and environment variables.
# Prints "OK" to stdout if all checks pass.
# Prints error messages to stderr for each failure.
# Exits 0 on success, 1 if any check fails.

REQUIRED_CMDS=(git python3 curl)
REQUIRED_VARS=(DATABASE_URL APP_SECRET)

errors=0

for cmd in "${REQUIRED_CMDS[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "MISSING_CMD: $cmd" >&2
        errors=$((errors + 1))
    fi
done

for var in "${REQUIRED_VARS[@]}"; do
    val="${!var:-}"
    if [ -z "$val" ]; then
        echo "MISSING_VAR: $var" >&2
        errors=$((errors + 1))
    fi
done

# BUG: "OK" is printed even when errors > 0
# BUG: script exits 0 regardless of $errors (missing exit statement)
echo "OK"
