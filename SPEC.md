### Product Spec: Local LLM Coding Benchmark Harness (Ollama)

#### Problem

We want a repeatable way to compare local LLMs for coding tasks across:
- Node.js (primary)
- Python (secondary)
- .NET/Azure (business)

The benchmark should reflect real developer workflows (Aider “whole file” edits) and avoid fragile diff parsing. It must run locally with Ollama and produce clear pass/fail plus performance metrics.

#### Users

- Developer benchmarking local models before choosing “daily driver” vs “heavy lifter”.
- Teams comparing a fixed set of local models on standardized tasks.

#### Success Metrics

- Benchmark runs end-to-end locally with one command.
- Results are reproducible across runs (given pinned tasks + deterministic model options).
- Clear report of why failures happened (format vs policy vs correctness).
- Adding a new task takes <30 minutes.

#### Functional Requirements

1) CLI Runner
- Provide a CLI entrypoint (e.g., `python -m bench` or `bench.py`).
- Accept multiple models and run all tasks for each model.
- Configurable knobs: `num_ctx`, `temperature`, `seed`, `num_predict`, output path.
- Print live progress and a final summary.

2) Task Suite
- Include at minimum:
  - Node: slugify/punctuation task (micro)
  - Python: safe_div exception task (micro)
  - .NET: Azure SAS expiry fix task (micro)
- Each task must:
  - fail baseline tests deterministically
  - specify editable allow-list (default: 1 file)
  - provide context files to include in prompt
  - include a test command as argv list

3) Model Interaction
- Use Ollama `/api/chat` (non-streaming) and record provided metrics.
- Enforce deterministic options:
  - temperature default 0
  - seed default 1

4) Edit Application
- Parse `BEGIN_FILE/END_FILE` blocks.
- Reject edits to non-allowed files.
- Apply edits by overwriting files.

5) Scoring
- Success: tests pass after edits.
- Failures must be categorized:
  - no parseable edits
  - non-editable file touched
  - tests still failing
  - tool errors (timeouts, missing deps)

6) Outputs
- Write JSON results to disk.
- Provide console summary:
  - pass rate per model
  - avg tok/s per model
  - failure reasons distribution

#### Non-functional Requirements

- Works on WSL Ubuntu (primary environment).
- Minimal dependencies (stdlib + optional `tabulate` for nicer tables).
- Timeouts for tests and model calls to avoid hangs.
- Truncate large outputs in results to keep JSON manageable.

#### Configuration

Support config via:
- CLI flags (primary)
- optional `bench.yaml` (future)

#### Example CLI

python3 bench.py \\
  --models qwen2.5-coder:32b llama3.3:70b-instruct-q4_K_M gemma4:31b \\
  --num-ctx 16384 \\
  --temperature 0 \\
  --seed 1 \\
  --num-predict 400 \\
  --out results.json

#### Out of Scope (for v1)

- Auto-downloading models.
- Web UI dashboard.
- Running arbitrary untrusted repos without sandboxing.
- Multi-turn repair loops (“try again if fails”).

#### Risks

- Models may frequently violate strict output format.
Mitigation:
- Keep `num_predict` modest.
- Provide file contents and explicit editable allow-list.
- Optionally add a “repair” pass in future (ask model to re-output in correct format).

- Dependency restores (npm/nuget) can be slow.
Mitigation:
- Provide warmup instructions and caching.
- Offer `--skip-dotnet` and per-task toggles.

#### Future Enhancements

- External repo scenarios described in YAML:
  - repo path
  - test command
  - editable file list
  - context file globs
- Multi-trial runs and confidence intervals.
- Optional container sandbox runner.
- HTML report generation.
