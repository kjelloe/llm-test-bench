# Populates the MODELS array from models/default.txt.
# Sourced by preflight.sh and install-models.sh so they stay in sync with compare.sh.
# To change the default set, edit models/default.txt.
_BENCH_MODELS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/models"
MODELS=()
while IFS= read -r _line || [[ -n "$_line" ]]; do
    _line="${_line%%#*}"           # strip inline comment
    _line="${_line//[[:space:]]/}" # strip whitespace (model names have none)
    [[ -n "$_line" ]] && MODELS+=("$_line")
done < "$_BENCH_MODELS_DIR/default.txt"
unset _BENCH_MODELS_DIR _line
