#!/usr/bin/env bash
# Usage: llamacpp/hangwatch.sh <run-log> [out-dir] [max-captures]
# Watches a benchmark run for a hung llama-server request and captures evidence (gdb thread dump, perf
# profile, nvidia-smi dmon). A hang = the run log shows a task in progress (its last "[n/N] model=... task=..."
# line has no PASS/FAIL yet) while every GPU has been at <=5% utilization for 3 minutes. Stops when the
# run log reports the run finished or after max-captures (default 3), 10 minutes apart.
# Needs gdb attach rights: kernel.yama.ptrace_scope=0 (see docs/gpt-oss-120b-speed-debug-plan.md).
set -uo pipefail
LOG=$1
OUT=${2:-output/hangs}
MAX=${3:-3}
mkdir -p "$OUT"
captures=0
idle_since=0

task_in_progress() {  # prints the last task header when nothing after it reports PASS/FAIL yet
  # (hwmonitor lines can push a task's result onto a later line, so read everything after the header)
  local n
  n=$(grep -nE "\[[0-9]+/[0-9]+\] model='[^']+'\s+task='[^']+'" "$LOG" 2>/dev/null | tail -1 | cut -d: -f1)
  [ -n "$n" ] || return 1
  tail -n +"$n" "$LOG" | grep -qE "PASS|FAIL\(" && return 1
  sed -n "${n}p" "$LOG" | grep -oE "\[[0-9]+/[0-9]+\] model='[^']+'\s+task='[^']+'"
}

gpus_idle() { nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | awk '$1>5{busy=1} END{exit busy}'; }

server_pid() { ps -eo pid,comm | awk '$2=="llama-server"{print $1; exit}'; }

while ! grep -q "^Total runtime:" "$LOG" 2>/dev/null && [ $captures -lt "$MAX" ]; do
  task=$(task_in_progress)
  pid=$(server_pid)
  if [ -n "$task" ] && [ -n "$pid" ] && gpus_idle; then
    [ $idle_since -eq 0 ] && idle_since=$(date +%s)
    if [ $(( $(date +%s) - idle_since )) -ge 180 ]; then
      ts=$(date +%Y%m%d-%H%M%S)
      { echo "time $(date)"; echo "task $task"; echo "pid $pid"; tr '\0' ' ' < "/proc/$pid/cmdline"; echo; } > "$OUT/hang-$ts-info.txt"
      timeout -k 5 60 gdb -p "$pid" -batch -ex "thread apply all bt" > "$OUT/hang-$ts-gdb.txt" 2>&1
      timeout -k 5 30 perf record -F 199 --call-graph dwarf,16384 -p "$pid" -o "$OUT/hang-$ts-perf.data" -- sleep 8 > /dev/null 2>&1
      timeout -k 2 15 nvidia-smi dmon -s ut -c 10 > "$OUT/hang-$ts-dmon.txt" 2>&1
      captures=$((captures + 1))
      echo "captured hang $ts: $task"
      idle_since=0
      sleep 600
      continue
    fi
    sleep 20
  else
    idle_since=0
    sleep 20
  fi
done
echo "hangwatch done: $captures captures"
