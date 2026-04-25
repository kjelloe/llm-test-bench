### Working Agreement for AI Assistants (Claude / local model)

You are helping build a local benchmark harness repo. Optimize for correctness, reproducibility, and maintainability.

#### Repository Principles

- Prefer robust, simple parsing and strict validation.
- Fail loudly with categorized errors instead of "best-effort" silent behavior.
- Keep tasks deterministic and small.
- Do not add large dependencies unless clearly justified.

#### Code Style

- Python 3.12 compatible, stdlib-first.
- Small functions, clear names, type hints where helpful.
- Use `subprocess.run(..., timeout=...)` for all external commands.
- Never shell out with `shell=True`.

#### Safety & Determinism

- Default `temperature=0` and `seed=1`.
- `num_predict` default is 400 for simple/instruct models. Use 1200+ for thinking models
  (gemma4, deepseek-r1, etc.) — their reasoning tokens consume the budget before the answer.
  `compare.sh` sets `--num-predict 1200` explicitly.
- Default `--model-timeout` is 300s for `bench.py`. `compare.sh` sets `--model-timeout 900`
  because 120B RAM-bound models (qwen3.5:122b, gpt-oss:120b) at ~1–2 tok/s need up to
  ~1200s for 1200 tokens; 300s causes spurious TOOL_ERROR timeouts on those models.
- Always include the full contents of relevant files in prompts to prevent hallucinated file structure.

#### Edit Protocol Enforcement

- Model output must be ONLY:
  - one or more `BEGIN_FILE path ... END_FILE` blocks
- Reject:
  - markdown fences
  - explanations
  - edits to non-allowed files
- If output is invalid, classify error and save a truncated snippet for debugging.

#### Task Authoring Rules

- Baseline tests MUST fail on unmodified `task_data/`.
- After the correct fix, tests MUST pass.
- Editable file allow-list should be as small as possible (ideally one file).
- Provide context files as needed (tests, config, package file).

#### Repository Layout (quick reference)

```
bench.py            CLI runner
tasks.py            Task definitions, prompt builder, subprocess helpers
ollama_client.py    Ollama /api/chat client
parsing.py          BEGIN_FILE/END_FILE parser + allow-list validator
reporting.py        Comparison table, failure detail, JSON writer
run.sh              Venv setup + bench.py wrapper
compare.sh          Runs canonical 4-model set
preflight.sh        Dependency checker
tests/
  test_parsing.py   Parser unit tests  →  python3 -m pytest tests/
task_data/
  node_slugify/     Node.js ESM task
  python_safe_div/  Python pytest task
  dotnet_sas/       .NET xUnit task
```

#### How to Run

```bash
# Check all dependencies first
./preflight.sh

# Full benchmark (4 models × 3 tasks)
./compare.sh

# Single model / subset of tasks
./run.sh --models qwen2.5-coder:7b --tasks python_safe_div

# Run the harness's own unit tests
python3 -m pytest tests/ -v
```

#### Deliverables Expectations

When asked to implement features:
- Provide a minimal working implementation first.
- Add at least one test for any non-trivial parser or scoring logic.
- Update `SPEC.md` / `ARCHITECTURE.md` if behavior changes.

#### What NOT to do

- Don't implement multi-turn autonomous "agent loops" in v1.
- Don't auto-install dependencies or mutate the user's environment.
- Don't rely on network services beyond Ollama and package restores already required by tasks.
- Don't use `shell=True` in subprocess calls.
- Don't add a `prompting.py` — prompt building lives in `tasks.py`.
