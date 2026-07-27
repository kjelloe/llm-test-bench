#!/usr/bin/env bash
set -euo pipefail
# Set GPU power limits via nvidia-smi.
#
# On WSL2, GPU power management requires Windows-side admin access — the script
# detects this and prints the exact commands to run in an elevated Windows terminal.
#
# Usage:
#   ./powerlimit.sh              use $POWER_LIMIT env var, or 350 W default (all GPUs)
#   ./powerlimit.sh 300          explicit uniform wattage (all GPUs)
#   ./powerlimit.sh --query      show current limits without changing anything
#   ./powerlimit.sh --per-gpu    per-model limits: RTX 4090→300W, RTX 3090→280W
#   ./powerlimit.sh --per-gpu --reset  restore each GPU to its hardware maximum
#
# Config default:
#   Export POWER_LIMIT=<watts> in your environment or .bashrc to change the
#   default used by this script and by compare.sh.
#
# Per-GPU budget (--per-gpu):
#   2 GPUs: 4090@300W + 3090@280W = 580W GPU + ~175W system ≈ 755W (37% headroom vs 1200W PSU)
#   3 GPUs: 4090@300W + 3090@280W + 3090@280W = 860W GPU + ~175W system ≈ 1035W (14% headroom)

LIMIT_4090=300   # W; hardware max is 450W
LIMIT_3090=280   # W; hardware max is 350W

# ── Parse args ────────────────────────────────────────────────────────────────
QUERY_ONLY=false
PER_GPU=false
PER_GPU_RESET=false
WATTS=""

for _arg in "$@"; do
    case "$_arg" in
        --query|-q)   QUERY_ONLY=true ;;
        --per-gpu)    PER_GPU=true ;;
        --reset)      PER_GPU_RESET=true ;;
        --help|-h)
            sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        [0-9]*)
            WATTS="$_arg" ;;
        *)
            echo "Unknown argument: $_arg" >&2
            echo "Usage: $0 [WATTS|--per-gpu] [--query] [--reset]" >&2
            exit 1 ;;
    esac
done

if $PER_GPU_RESET && ! $PER_GPU; then
    echo "Error: --reset requires --per-gpu" >&2
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

# ── Per-GPU mode ──────────────────────────────────────────────────────────────
if $PER_GPU; then
    # Build "idx:watts" pairs from GPU model names
    _per_gpu_pairs() {
        local idx=0
        while IFS=',' read -r name max_limit; do
            name=$(echo "$name" | tr -d ' ')
            max_limit=$(echo "$max_limit" | tr -d ' ')
            if $PER_GPU_RESET; then
                echo "${idx}:${max_limit}"
            elif [[ "$name" == *"4090"* ]]; then
                echo "${idx}:${LIMIT_4090}"
            elif [[ "$name" == *"3090"* ]]; then
                echo "${idx}:${LIMIT_3090}"
            else
                echo "  GPU $idx: $name — unrecognized model, skipping" >&2
            fi
            ((idx++))
        done < <(nvidia-smi --query-gpu=name,power.max_limit --format=csv,noheader,nounits)
    }

    local_label=$($PER_GPU_RESET && echo "Resetting to hardware maximums" || echo "Applying per-GPU limits")
    echo "$local_label..."

    if $_IS_WSL; then
        echo ""
        echo "WSL2 detected — nvidia-smi power management is blocked inside WSL."
        echo "Run these commands in an elevated Windows terminal (Win+X → Terminal (Admin)):"
        echo ""
        while IFS=':' read -r idx watts; do
            printf '  nvidia-smi -i %s -pl %s\n' "$idx" "$watts"
        done < <(_per_gpu_pairs)
        echo ""
        echo "Or paste this single PowerShell command:"
        cmds=$(while IFS=':' read -r idx watts; do
            printf 'nvidia-smi -i %s -pl %s; ' "$idx" "$watts"
        done < <(_per_gpu_pairs))
        printf '  powershell.exe -Command "Start-Process powershell -Verb RunAs -ArgumentList '\''-Command \"%s\"'\''"\n' "${cmds%; }"
        echo ""
        echo "Note: power limits reset on reboot."
        exit 0
    fi

    while IFS=':' read -r idx watts; do
        name=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits \
               | sed -n "$((idx+1))p" | tr -d ' ')
        echo "  GPU $idx: $name → ${watts}W"
        sudo nvidia-smi -i "$idx" -pl "$watts"
    done < <(_per_gpu_pairs)

    echo ""
    _show_current
    echo ""
    total_gpu=$(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits \
                | awk '{sum += $1} END {printf "%d", sum}')
    echo "GPU total: ${total_gpu}W + ~175W system = $((total_gpu + 175))W  (1200W PSU)"
    exit 0
fi

# ── Uniform mode (original behaviour) ────────────────────────────────────────
if [[ -z "$WATTS" ]]; then
    WATTS="${POWER_LIMIT:-350}"
fi

if ! [[ "$WATTS" =~ ^[0-9]+$ ]]; then
    echo "Error: wattage must be a positive integer, got: $WATTS" >&2
    exit 1
fi

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

_show_current
echo ""
printf "Setting power limit to %sW (all GPUs)...\n" "$WATTS"
if sudo nvidia-smi -pl "$WATTS"; then
    echo ""
    _show_current
else
    echo "" >&2
    echo "Failed. Ensure nvidia-smi is on PATH and you have sudo rights." >&2
    exit 1
fi
