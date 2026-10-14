#!/usr/bin/env bash
# gpuclock.sh — lock or unlock the GPU clocks for multi-GPU runs (and show whether they are locked).
#
# Why: under Windows/WSL the driver drops each GPU of a layer split to P8 mid-answer, because each one idles while the
# others compute; long answers then decode ~7x slower (gpt-oss:120b on 3x24 GB: 9.8 vs 69.5 tok/s). A core clock
# floor fixes it; a memory clock lock adds ~40% more (96.6 tok/s) but keeps the cards in P0 at idle (~290 W of heat),
# so lock memory only for benchmark sessions. Both reset on reboot. Single-GPU runs do not need either.
#
# Usage: ./gpuclock.sh status            per-GPU core/memory clock now, and whether the core looks locked (exit 1 if not)
#        ./gpuclock.sh lock [--memory]   core floor 1500-2500 MHz (+ each card's maximum memory clock)
#        ./gpuclock.sh unlock [--memory] reset the core lock (+ the memory lock)
#        add --print to only print the command instead of running it
#
# Under WSL the clocks can only be set from Windows as administrator: lock/unlock start an elevated PowerShell (a UAC
# prompt on the Windows desktop) and wait for it; if that is declined or fails, the exact command is printed to paste
# into an admin PowerShell. On native Linux they run `sudo nvidia-smi`.
set -uo pipefail

CORE_LOCK=${GPUCLOCK_CORE:-1500,2500}
CORE_FLOOR=${CORE_LOCK%%,*}

is_wsl() {
    [[ -n ${GPUCLOCK_WSL:-} ]] && { [[ $GPUCLOCK_WSL == 1 ]]; return; }
    grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null
}

# The nvidia-smi commands (Windows or Linux syntax is the same) for an action, one per line.
commands() {
    local action=$1 memory=$2
    if [[ $action == lock ]]; then
        echo "nvidia-smi -lgc $CORE_LOCK"
        if $memory; then
            nvidia-smi --query-gpu=index,clocks.max.memory --format=csv,noheader,nounits |
                while IFS=', ' read -r idx mhz; do echo "nvidia-smi -i $idx -lmc $mhz,$mhz"; done
        fi
    else
        echo "nvidia-smi -rgc"
        $memory && echo "nvidia-smi -rmc"
    fi
}

# One PowerShell line that runs the commands elevated and waits. The inner command is single-quoted for PowerShell and
# contains no double quotes, so the outer shell's quoting stays intact (the powerlimit.sh quoting bug, 2026-09-17).
powershell_line() {
    local joined
    joined=$(paste -sd';' - | sed 's/;/; /g')
    printf "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command','%s'" "$joined"
}

status() {
    local unlocked=0
    while IFS=', ' read -r idx core mem pstate; do
        local state="locked"
        ((core < CORE_FLOOR)) && { state="NOT locked"; unlocked=1; }
        printf 'GPU%s  core %s MHz  memory %s MHz  %s  core %s\n' "$idx" "$core" "$mem" "$pstate" "$state"
    done < <(nvidia-smi --query-gpu=index,clocks.gr,clocks.mem,pstate --format=csv,noheader,nounits)
    return $unlocked
}

main() {
    local action=${1:-status} memory=false print=false
    shift || true
    for arg in "$@"; do
        case $arg in
            --memory) memory=true ;;
            --print) print=true ;;
            *) echo "unknown option: $arg" >&2; exit 2 ;;
        esac
    done
    case $action in
        status) status; exit ;;
        lock|unlock) ;;
        -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "usage: gpuclock.sh status | lock [--memory] | unlock [--memory] [--print]" >&2; exit 2 ;;
    esac

    local cmds
    cmds=$(commands "$action" "$memory")
    if is_wsl; then
        local line
        line=$(powershell_line <<< "$cmds")
        if $print; then
            echo "In an admin PowerShell:"
            sed 's/^/  /' <<< "$cmds"
            echo "Or from WSL (a UAC prompt appears on the Windows desktop):"
            echo "  powershell.exe -NoProfile -Command \"$line\""
            exit 0
        fi
        echo "Asking Windows for administrator rights (accept the UAC prompt on the desktop)..."
        if powershell.exe -NoProfile -Command "$line"; then
            sleep 1
            status
            exit 0
        fi
        echo "The elevated PowerShell did not run (UAC declined, or no Windows desktop). Run this in an admin PowerShell:" >&2
        sed 's/^/  /' <<< "$cmds" >&2
        exit 1
    fi
    if $print; then
        sed 's/^/sudo /' <<< "$cmds"
        exit 0
    fi
    while read -r cmd; do sudo $cmd || exit 1; done <<< "$cmds"
    status
}

main "$@"
