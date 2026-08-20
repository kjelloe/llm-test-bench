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
#   ./statistics.sh --estimate-vram              VRAM scalability estimation table (all tiers)
#   ./statistics.sh --estimate-vram --ctx 8k     8k-context columns only
#   ./statistics.sh --estimate-vram --ctx 128k   128k-context columns only
#   ./statistics.sh --estimate-vram --format csv
#   ./statistics.sh --estimate-vram output/results-compare-ls.json
#   ./statistics.sh --estimate-vram --anchor-vram 24   (default anchor tier)
#
#   ./statistics.sh --export                     bundle all output/*.json → stats-exported.json
#   ./statistics.sh --export --out shared.json   custom output path
#   ./statistics.sh --import stats-exported.json extract runs from an export package → output/
#   ./statistics.sh --import friend.json         import a plain results file → output/
#
# Formats:
#   markdown   GitHub-flavoured markdown table (default)
#   csv        Semicolon-separated, all cells quoted (Nordic CSV)
#   json       JSON array of objects
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Route --estimate-vram to the dedicated script; strip that flag before forwarding.
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        cat <<'EOF'
Usage: ./statistics.sh [OPTIONS] [FILE ...]

Aggregate benchmark results into a sharable dataset.
Default: one row per model, newest run first (all output/*.json).

Positional arguments:
  FILE                  Result JSON files (default: all output/*.json)

Standard options:
  --format {json,csv,markdown}   Output format (default: markdown)
  --out PATH                     Write to file instead of stdout
  --detail                       One row per task instead of one row per model
  --summary                      Context speed profile: one row per model with
                                 pass% and tok/s per context size (8k–256k)
  --sort-by COLUMN [DIR]         Sort by column; direction: asc or desc
                                   --sort-by model
                                   --sort-by pass_pct desc
  -h, --help                     Show this help and exit

VRAM estimation:
  ./statistics.sh --estimate-vram
  ./statistics.sh --estimate-vram --ctx 8k
  ./statistics.sh --estimate-vram --ctx 128k
  ./statistics.sh --estimate-vram --format csv
  ./statistics.sh --estimate-vram --anchor-vram 24
  ./statistics.sh --estimate-vram output/results-compare-ls.json

Export / import (cross-hardware sharing):
  ./statistics.sh --export                       bundle output/*.json → stats-exported.json
  ./statistics.sh --export --out shared.json     custom output path
  ./statistics.sh --import stats-exported.json   extract runs → output/
  ./statistics.sh --import friend.json           import a plain results file

Examples:
  ./statistics.sh
  ./statistics.sh --summary
  ./statistics.sh --detail --format csv --out stats.csv
  ./statistics.sh --sort-by pass_pct desc
  ./statistics.sh output/results-compare-ls.json --format markdown
  ./statistics.sh --estimate-vram --anchor-vram 48
EOF
        exit 0
    fi
    if [[ "$arg" == "--estimate-vram" ]]; then
        args=()
        for a in "$@"; do
            [[ "$a" != "--estimate-vram" ]] && args+=("$a")
        done
        exec python3 "$SCRIPT_DIR/lib/estimate_vram.py" "${args[@]}"
    fi
    # Route --export / --import to export.py (passes all args; export.py owns its argparse).
    if [[ "$arg" == "--export" || "$arg" == "--import" ]]; then
        exec python3 "$SCRIPT_DIR/lib/export.py" "$@"
    fi
done

exec python3 "$SCRIPT_DIR/lib/statistics.py" "$@"
