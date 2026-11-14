#!/usr/bin/env bash
# wgpu takes a while to build the first time; keep its build in one place across runs (the task's own crate rebuilds).
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HOME/.cache/llm-test-bench/rs-wgpu-target}"
exec cargo test --offline -- --test-threads=1
