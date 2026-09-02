#!/usr/bin/env bash
# test-adaptive-kv-streaming-blackwell.sh
#
# Self-contained test of RaymondHuang210129/llama.cpp-adaptive-kv-streaming on a
# single-GPU Blackwell machine (written for an RTX 5060 Ti 16 GB, but should work on
# any single CUDA GPU with enough VRAM for the chosen model+context).
#
# Background: this fork adds --kv-stream-stage-mib to llama-server, streaming the KV
# cache between pinned host memory and a bounded CUDA pool so long contexts fit on GPUs
# too small to hold the full KV cache in VRAM, while preserving exact (non-approximated)
# attention. Author's own validated setup: RTX 5070 Ti (Blackwell, compute capability
# 12.0), unsloth/Qwen3.8-27B-GGUF UD-Q3_K_XL, 262144-token context, Q8_0 K / Q4_0 V
# cache, one slot. See the author's writeup:
#   https://medium.com/@raymond860909/running-qwen-27b-on-16g-vram-with-full-context-length-building-adaptive-kv-cache-streaming-for-bf1e819116e9
#
# On our 3x24GB Ada/Ampere rig (RTX 4090 + 2x RTX 3090), this feature crashed reliably
# the moment streaming was engaged — two different KV cache types crashed in two
# different CUDA kernels, while the identical config with streaming DISABLED worked
# cleanly. That isolation strongly suggested an architecture-specific CUDA kernel bug
# (untested on anything older than Blackwell), not a config or model-file problem.
# This script re-runs that same isolation on real Blackwell hardware to find out.
#
# Usage:
#   chmod +x test-adaptive-kv-streaming-blackwell.sh
#   ./test-adaptive-kv-streaming-blackwell.sh
#
# Everything lands under ./kv-stream-experiment/ (build, model, logs) relative to
# wherever you run this from. Safe to re-run — build and model download are skipped
# if already present.

set -uo pipefail

WORKDIR="$(pwd)/kv-stream-experiment"
REPO_DIR="$WORKDIR/llama.cpp-adaptive-kv-streaming"
MODEL_DIR="$WORKDIR/models"
LOG_DIR="$WORKDIR/logs"
PORT=8099

mkdir -p "$WORKDIR" "$MODEL_DIR" "$LOG_DIR"

echo "════════════════════════════════════════════════════════════════"
echo "  Adaptive KV Streaming — Blackwell isolation test"
echo "  Workdir: $WORKDIR"
echo "════════════════════════════════════════════════════════════════"

# ── Step 0: prerequisite checks ────────────────────────────────────────────────
echo
echo "── Checking prerequisites ──"
_missing=0
for cmd in git cmake g++ nvcc python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  MISSING: $cmd"
        _missing=1
    else
        echo "  OK: $cmd"
    fi
done
if ! command -v nvidia-smi &>/dev/null; then
    echo "  MISSING: nvidia-smi"
    _missing=1
else
    echo "  GPU(s) detected:"
    nvidia-smi --query-gpu=index,name,memory.total,compute_cap --format=csv,noheader | sed 's/^/    /'
fi
if [[ "$_missing" -eq 1 ]]; then
    echo "ERROR: missing prerequisites above. Install them and re-run." >&2
    exit 1
fi

# ── Step 1: clone + build ───────────────────────────────────────────────────────
echo
echo "── Clone + build ──"
if [[ ! -d "$REPO_DIR" ]]; then
    git clone --branch feature/adaptive-kv-stream \
        https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming.git "$REPO_DIR"
else
    echo "  repo already present at $REPO_DIR — skipping clone"
fi

BINARY="$REPO_DIR/build/bin/llama-server"
if [[ ! -x "$BINARY" ]]; then
    echo "  building (this takes a while)..."
    (
        cd "$REPO_DIR"
        cmake -S . -B build -DGGML_CUDA=ON -DGGML_CUDA_FA_ALL_QUANTS=ON -DCMAKE_BUILD_TYPE=Release
        cmake --build build --config Release --target llama-server -j
    ) 2>&1 | tee "$LOG_DIR/build.log"
    if [[ ! -x "$BINARY" ]]; then
        echo "ERROR: build did not produce $BINARY — check $LOG_DIR/build.log" >&2
        exit 1
    fi
else
    echo "  binary already built at $BINARY — skipping"
fi
echo "  binary: $BINARY"
"$BINARY" --version 2>&1 | head -3

# ── Step 2: download the model (author's exact validated quant) ────────────────
echo
echo "── Model download ──"
MODEL_FILE="$MODEL_DIR/Qwen3.8-27B-UD-Q3_K_XL.gguf"
if [[ -f "$MODEL_FILE" ]]; then
    echo "  model already present at $MODEL_FILE — skipping download"
else
    AVAIL_GB=$(df --output=avail -BG "$MODEL_DIR" | tail -1 | tr -dc '0-9')
    echo "  disk free: ${AVAIL_GB}G — need ~13G for UD-Q3_K_XL"
    if [[ "$AVAIL_GB" -lt 20 ]]; then
        echo "ERROR: not enough disk space. Free some space and re-run." >&2
        exit 1
    fi
    python3 -m pip show huggingface_hub &>/dev/null || python3 -m pip install --quiet huggingface_hub
    echo "  downloading unsloth/Qwen3.8-27B-GGUF UD-Q3_K_XL (~13 GB)..."
    # HF_HUB_DISABLE_XET=1: the Xet backend has stalled repeatedly on large downloads
    # in prior testing on this same investigation — plain HTTP has been reliable.
    HF_HUB_DISABLE_XET=1 python3 -c "
from huggingface_hub import hf_hub_download
import shutil
path = hf_hub_download(
    repo_id='unsloth/Qwen3.8-27B-GGUF',
    filename='UD-Q3_K_XL/Qwen3.8-27B-UD-Q3_K_XL.gguf',
    local_dir='$MODEL_DIR/_dl_scratch',
)
shutil.move(path, '$MODEL_FILE')
print('done:', '$MODEL_FILE')
"
    rm -rf "$MODEL_DIR/_dl_scratch"
fi
ls -la "$MODEL_FILE"

# ── Step 3: three-way crash isolation (mirrors the Ada/Ampere test exactly) ────
echo
echo "── Isolation test: does streaming crash on this GPU? ──"

_start_server() {
    local ctk="$1" ctv="$2" stream_mib="$3" logfile="$4"
    : > "$logfile"
    "$BINARY" \
        --model "$MODEL_FILE" \
        --ctx-size 32768 -fa on -ctk "$ctk" -ctv "$ctv" -ngl 999 -b 512 -ub 512 -np 1 \
        --kv-stream-stage-mib "$stream_mib" --port "$PORT" \
        > "$logfile" 2>&1 &
    echo $!
}

_wait_and_test() {
    local logfile="$1" label="$2"
    local waited=0
    while ! grep -qE "listening on|CUDA error|Assertion" "$logfile" 2>/dev/null; do
        sleep 3
        waited=$((waited + 3))
        if [[ "$waited" -gt 180 ]]; then
            echo "  [$label] TIMEOUT waiting for server to start — check $logfile"
            return 1
        fi
    done
    if grep -qE "CUDA error|Assertion" "$logfile"; then
        echo "  [$label] CRASH during load — check $logfile"
        return 1
    fi
    sleep 5
    local result
    result=$(curl -s -m 60 "http://127.0.0.1:$PORT/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"messages":[{"role":"user","content":"Say hello in exactly 3 words."}],"temperature":0,"seed":1,"max_tokens":20}' 2>&1)
    sleep 2
    if grep -qE "CUDA error|Assertion" "$logfile"; then
        echo "  [$label] CRASH during generation — check $logfile"
        return 1
    fi
    if echo "$result" | grep -q '"content"'; then
        echo "  [$label] PASS — server responded cleanly"
        return 0
    fi
    echo "  [$label] UNCLEAR — no crash logged but no clean response either; inspect $logfile and the curl output below:"
    echo "$result"
    return 1
}

_kill_server() {
    pkill -f "$BINARY" 2>/dev/null
    sleep 2
}

declare -A RESULTS

echo
echo "Test 1/3: f16 KV, streaming ON (2304 MiB stage)"
_start_server f16 f16 2304 "$LOG_DIR/test1-f16-stream.log" > /dev/null
_wait_and_test "$LOG_DIR/test1-f16-stream.log" "f16+stream"
RESULTS["f16+stream"]=$?
_kill_server

echo
echo "Test 2/3: q8_0 K / q4_0 V (author's validated config), streaming ON (2304 MiB stage)"
_start_server q8_0 q4_0 2304 "$LOG_DIR/test2-q8q4-stream.log" > /dev/null
_wait_and_test "$LOG_DIR/test2-q8q4-stream.log" "q8_0/q4_0+stream"
RESULTS["q8_0/q4_0+stream"]=$?
_kill_server

echo
echo "Test 3/3: q8_0 K / q4_0 V, streaming OFF (baseline control)"
_start_server q8_0 q4_0 0 "$LOG_DIR/test3-q8q4-nostream.log" > /dev/null
_wait_and_test "$LOG_DIR/test3-q8q4-nostream.log" "q8_0/q4_0 baseline"
RESULTS["q8_0/q4_0 baseline"]=$?
_kill_server

echo
echo "════════════════════════════════════════════════════════════════"
echo "  Isolation results"
echo "════════════════════════════════════════════════════════════════"
for key in "f16+stream" "q8_0/q4_0+stream" "q8_0/q4_0 baseline"; do
    if [[ "${RESULTS[$key]}" -eq 0 ]]; then
        echo "  PASS  $key"
    else
        echo "  FAIL  $key"
    fi
done

# ── Step 4: if streaming works, validate the actual value proposition ─────────
if [[ "${RESULTS[f16+stream]}" -eq 0 || "${RESULTS[q8_0/q4_0+stream]}" -eq 0 ]]; then
    echo
    echo "── Streaming works on this GPU — testing the actual long-context scenario ──"
    echo "  (This is what the feature is FOR: does it let a 16 GB card handle very"
    echo "   long context that wouldn't otherwise fit in VRAM?)"
    _start_server q8_0 q4_0 2304 "$LOG_DIR/test4-longctx.log" > /dev/null
    _server_pid=$!
    waited=0
    while ! grep -qE "listening on|CUDA error|Assertion" "$LOG_DIR/test4-longctx.log" 2>/dev/null; do
        sleep 3; waited=$((waited + 3))
        [[ "$waited" -gt 300 ]] && break
    done
    if grep -qE "CUDA error|Assertion" "$LOG_DIR/test4-longctx.log"; then
        echo "  CRASH at load with --ctx-size 262144 — check $LOG_DIR/test4-longctx.log"
    else
        # Restart at the full 262144 context the author validated (32768 above was
        # just for the quick isolation checks — this needs the real context size).
        _kill_server
        : > "$LOG_DIR/test4-longctx.log"
        "$BINARY" --model "$MODEL_FILE" --ctx-size 262144 -fa on -ctk q8_0 -ctv q4_0 \
            -ngl 999 -b 512 -ub 512 -np 1 --kv-stream-stage-mib 2304 --port "$PORT" \
            > "$LOG_DIR/test4-longctx.log" 2>&1 &
        waited=0
        while ! grep -qE "listening on|CUDA error|Assertion" "$LOG_DIR/test4-longctx.log" 2>/dev/null; do
            sleep 5; waited=$((waited + 5))
            [[ "$waited" -gt 300 ]] && break
        done
        if grep -qE "CUDA error|Assertion" "$LOG_DIR/test4-longctx.log"; then
            echo "  CRASH at 262144 context — check $LOG_DIR/test4-longctx.log"
        else
            echo "  Server loaded at ctx=262144. Generating a ~100k-token synthetic prompt"
            echo "  (repeated filler text) to exercise real long-context streaming..."
            python3 -c "
import json
filler = ('The quick brown fox jumps over the lazy dog. ' * 2000)
payload = {
    'messages': [{'role': 'user', 'content': filler + '\n\nWhat animal jumps over the dog in the text above? Answer in one word.'}],
    'temperature': 0, 'seed': 1, 'max_tokens': 20,
}
print(json.dumps(payload))
" > "$LOG_DIR/longctx-payload.json"
            time curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" \
                -H "Content-Type: application/json" \
                -d @"$LOG_DIR/longctx-payload.json" | tee "$LOG_DIR/longctx-response.json"
            echo
            echo "  Check $LOG_DIR/longctx-response.json for the answer (should mention 'fox')"
            echo "  and $LOG_DIR/test4-longctx.log for timing/VRAM behavior during the run."
        fi
    fi
    _kill_server
else
    echo
    echo "── Streaming crashed in both configs — same as the Ada/Ampere result. ──"
    echo "  This would mean the bug isn't architecture-specific after all, or this"
    echo "  GPU/driver/CUDA-toolkit combination has its own issue. Worth reporting"
    echo "  upstream with both this machine's logs and the original Ada/Ampere logs"
    echo "  if that's the case — see next-runs.md in the llm-test-bench repo for those."
fi

echo
echo "All logs saved under: $LOG_DIR"
echo "Done."
