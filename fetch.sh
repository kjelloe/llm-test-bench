#!/usr/bin/env bash
set -euo pipefail
#
# Pull models via ollama. Accepts set names, set file paths, or bare model names.
#
# Usage:
#   ./fetch.sh default                 pull all models in models/default.txt
#   ./fetch.sh models/full.txt         pull all models in a set file (by path)
#   ./fetch.sh qwen2.5-coder:14b       pull a single model
#   ./fetch.sh m1 m2 m3                pull multiple models
#   ./fetch.sh default qwen3.5:7b      mix: set + extra model

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/models"

if [[ $# -eq 0 ]]; then
    echo "Usage: ./fetch.sh <set-name | set-file.txt | model> [...]"
    echo ""
    echo "Examples:"
    echo "  ./fetch.sh default"
    echo "  ./fetch.sh models/full.txt"
    echo "  ./fetch.sh qwen2.5-coder:14b"
    echo ""
    echo "Available sets:"
    for _f in "$MODELS_DIR"/*.txt; do
        [[ -f "$_f" ]] || continue
        _count=$(grep -cv '^\s*\(#\|$\)' "$_f" 2>/dev/null || echo '?')
        printf "  %-20s  (%s models)\n" "$(basename "$_f" .txt)" "$_count"
    done
    exit 0
fi

# ── Collect model names from all arguments ────────────────────────────────────
_parse_set_file() {
    local file="$1"
    while IFS= read -r _line || [[ -n "$_line" ]]; do
        _line="${_line%%#*}"
        _line="${_line//[[:space:]]/}"
        [[ -n "$_line" ]] && echo "$_line"
    done < "$file"
}

MODELS=()
for _arg in "$@"; do
    if [[ -f "$_arg" ]]; then
        # Direct path to a set file
        while IFS= read -r _m; do MODELS+=("$_m"); done < <(_parse_set_file "$_arg")
    elif [[ -f "$MODELS_DIR/${_arg}.txt" ]]; then
        # Named set (e.g. "default", "extended")
        while IFS= read -r _m; do MODELS+=("$_m"); done < <(_parse_set_file "$MODELS_DIR/${_arg}.txt")
    else
        # Bare model name
        MODELS+=("$_arg")
    fi
done
unset _arg _m _f _count

if [[ ${#MODELS[@]} -eq 0 ]]; then
    echo "No models to fetch."
    exit 0
fi

echo "Fetching ${#MODELS[@]} model(s)..."
echo ""

# ── Pull each model ───────────────────────────────────────────────────────────
FAILED=()
for i in "${!MODELS[@]}"; do
    _model="${MODELS[$i]}"
    printf "[%d/%d] ollama pull %s\n" "$((i+1))" "${#MODELS[@]}" "$_model"
    if ollama pull "$_model"; then
        echo ""
    else
        printf "  FAILED: %s\n\n" "$_model"
        FAILED+=("$_model")
    fi
done

echo "════════════════════════════════════════════════════════════"
printf "  Done: %d pulled" "$(( ${#MODELS[@]} - ${#FAILED[@]} ))"
if [[ ${#FAILED[@]} -gt 0 ]]; then
    printf ", %d failed\n" "${#FAILED[@]}"
    printf "  Failed:\n"
    for _m in "${FAILED[@]}"; do printf "    %s\n" "$_m"; done
    exit 1
else
    printf "\n"
fi
