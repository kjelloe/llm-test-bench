#!/usr/bin/env bash
# Thin wrapper — equivalent to: ./compare.sh extended "$@"
# Model set defined in models/extended.txt
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/compare.sh" extended "$@"
