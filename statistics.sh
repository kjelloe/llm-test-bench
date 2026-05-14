#!/usr/bin/env bash
# statistics.sh — Aggregate benchmark results into a sharable dataset.
#
# Usage:
#   ./statistics.sh                              markdown summary to stdout (one row per model)
#   ./statistics.sh --summary                    context speed profile: pass% + tok/s per context size
#   ./statistics.sh --detail                     one row per task
#   ./statistics.sh --sort-by model              sort by column asc (default: run_date desc)
#   ./statistics.sh --sort-by pass_pct desc      sort by column with explicit direction
#   ./statistics.sh --format csv --out stats.csv
#   ./statistics.sh --format json
#   ./statistics.sh output/results-compare.json  specific file(s)
#
# Formats:
#   markdown   GitHub-flavoured markdown table (default)
#   csv        Semicolon-separated, all cells quoted (Nordic CSV)
#   json       JSON array of objects
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/lib/statistics.py" "$@"
