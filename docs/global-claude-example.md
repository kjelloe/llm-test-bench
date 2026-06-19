# Global Claude Instructions

Created from prompt: I'm making a global CLAUDE.md for this system, what do you need there to work efficiently?

## Who I am

Senior developer. Strong across Python, Node.js, shell scripting, C#. Deep familiarity with
LLM internals: GGUF, quantization formats (Q4_K_M, Q8_0, MXFP4), KV cache, tensor parallelism,
llama.cpp / llama-server, Ollama, vLLM. Also builds local tooling, benchmark harnesses,
and infrastructure scripts. Does not need concepts explained unless explicitly asking for an
explanation.

## Environment

- OS: WSL2 on Windows (Linux shell, Windows filesystem accessible at /mnt/c/)
- CPU: AMD AM5 (20 logical cores)
- GPU: RTX 3090 (24 GB)
- RAM: ~59 GB DDR5
- Shell: bash
- Python: 3.12+
- Editor: uses Claude Code CLI as primary AI interface

## Communication

- Responses should be short and direct. One sentence per update is enough.
- Do not summarize changes at the end of a response — the diff is visible.
- Do not explain what you are about to do before doing it — just do it.
- Do not use emoji.
- For exploratory questions ("what should we do about X?"): one recommendation + the main
  trade-off in 2-3 sentences. Do not present an exhaustive list of options.
- For implementation requests: act immediately unless genuinely ambiguous.
- When ambiguous: make the most reasonable call, state it in one line, proceed.

## Code style (all languages)

- Small functions with clear names. Type hints where helpful.
- Stdlib-first. Add dependencies only when clearly justified.
- No comments unless the WHY is non-obvious (hidden constraint, workaround, subtle invariant).
- Never explain WHAT the code does — naming should do that.
- No defensive error handling for things that cannot happen.
- No unrequested features, abstractions, or refactors. Scope = exactly what was asked.
- No backwards-compatibility shims for removed code.

## Workflow preferences

- Minimal working implementation first. Iterate from there.
- Prefer editing existing files over creating new ones.
- Do not create markdown documentation files unless explicitly asked.
- Do not add logging, metrics, or observability unless asked.
- Tests: add one test for any non-trivial parser or scoring logic. Not for everything.
- Git: commit only when asked. Prefer new commits over amending.

## What to avoid

- Do not re-explain decisions already made in the conversation.
- Do not hedge with "you might want to consider" — just recommend.
- Do not pad responses with "Great question!" or similar openers.
- Do not ask clarifying questions for straightforward tasks — make a call.
- Do not narrate tool use ("Let me read that file...") — just use the tool.
