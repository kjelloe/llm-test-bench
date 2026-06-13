#!/usr/bin/env bash
set -euo pipefail
# Set GPU power limit via nvidia-smi.
#
# On WSL2, GPU power management requires Windows-side admin access — the script
# detects this and prints the exact PowerShell command to run instead.
#
# Usage:
#   ./powerlimit.sh              use $POWER_LIMIT env var, or 350 W default
#   ./powerlimit.sh 300          explicit wattage
#   ./powerlimit.sh --query      show current limits without changing anything
#
# Config default:
#   Export POWER_LIMIT=<watts> in your environment or .bashrc to change the
#   default used by this script and by compare.sh.

# ── Parse args ────────────────────────────────────────────────────────────────
QUERY_ONLY=false
WATTS=""

for _arg in "$@"; do
    case "$_arg" in
        --query|-q) QUERY_ONLY=true ;;
        --help|-h)
            sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        [0-9]*)
            WATTS="$_arg" ;;
        *)
            echo "Unknown argument: $_arg" >&2
            echo "Usage: $0 [WATTS] [--query]" >&2
            exit 1 ;;
    esac
done

# Resolve wattage (CLI > env > default)
if [[ -z "$WATTS" ]]; then
    WATTS="${POWER_LIMIT:-350}"
fi

if ! [[ "$WATTS" =~ ^[0-9]+$ ]]; then
    echo "Error: wattage must be a positive integer, got: $WATTS" >&2
    exit 1
fi

# ── Detect WSL2 ───────────────────────────────────────────────────────────────
_IS_WSL=false
if grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
    _IS_WSL=true
fi

# ── Query current limits ───────────────────────────────────────────────────────
_show_current() {
    if command -v nvidia-smi &>/dev/null; then
        echo "Current GPU power limits:"
        nvidia-smi --query-gpu=index,name,power.limit,power.max_limit \
                   --format=csv,noheader,nounits 2>/dev/null \
        | awk -F',' '{
            printf "  GPU %s  %-30s  limit: %sW  (max: %sW)\n",
                   $1, $2, $3, $4
          }' || echo "  (nvidia-smi query failed)"
    else
        echo "  nvidia-smi not found on PATH"
    fi
}

if $QUERY_ONLY; then
    _show_current
    exit 0
fi

# ── WSL2 path: print instructions ─────────────────────────────────────────────
if $_IS_WSL; then
    _show_current
    echo ""
    echo "WSL2 detected — nvidia-smi power management is blocked inside WSL."
    echo "Run the following command in an elevated Windows terminal:"
    echo ""
    printf '  \033[1mnvidia-smi -pl %s\033[0m\n' "$WATTS"
    echo ""
    echo "How to open an elevated terminal:"
    echo "  • Win + X  →  'Terminal (Admin)'  or  'Windows PowerShell (Admin)'"
    echo "  • Or: right-click the Start button → Terminal (Admin)"
    echo ""
    echo "To apply from WSL itself (saves the round-trip) you can also run:"
    printf '  \033[1mpowershell.exe -Command "Start-Process powershell -Verb RunAs -ArgumentList '\''-Command nvidia-smi -pl %s'\''"\033[0m\n' "$WATTS"
    echo ""
    echo "Note: power limits reset on reboot; run this again after each restart."
    exit 0
fi

# ── Native Linux path ─────────────────────────────────────────────────────────
_show_current
echo ""
printf "Setting power limit to %sW ...\n" "$WATTS"
if sudo nvidia-smi -pl "$WATTS"; then
    echo ""
    _show_current
else
    echo "" >&2
    echo "Failed. Ensure nvidia-smi is on PATH and you have sudo rights." >&2
    exit 1
fi
