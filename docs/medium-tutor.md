# Local AI Coding Ally — Mid-Range Setup Guide

**Hardware:** 16 GB VRAM GPU · 64 GB DDR5 · AMD AM5 CPU (e.g. Ryzen 9 9900X)
**Goal:** A private, offline AI that tutors deeply on any subject, handles real codebases, and reasons through hard problems — no cloud, no subscription.

---

## What this setup can do

The jump from 8 GB to 16 GB VRAM is meaningful. You can run 14B models fully on the GPU — roughly twice the capability of a 7-8B model — and stretch to 32B models using your 64 GB of RAM as overflow. That covers:

- Tutoring at university level across science, maths, engineering, and programming
- Explaining complex code, refactoring suggestions, bug diagnosis in real projects
- Step-by-step worked examples with genuine understanding of the problem
- Loading and answering questions across large document collections (textbooks, codebases, PDFs)
- Running two different models simultaneously (e.g. a reasoning model + a coding model)

The practical ceiling on this rig is a 32B model — smarter than a 14B in the same way a senior developer is smarter than a junior one on hard problems.

---

## Install Ollama (10 minutes)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

On Windows: download from [ollama.com](https://ollama.com). Ollama handles GPU detection, VRAM/RAM splitting, and model management automatically.

---

## Which model to use

### Best all-rounder: Qwen3 14B (high quality)
```bash
ollama run qwen3:14b-q8_0
```
~14.5 GB VRAM · fully GPU-resident · ~30 tok/s · 128k context

`q8_0` is near-full precision — essentially the same quality as the original model weights. This is the highest-quality 14B you can run, and on 16 GB it fits cleanly. Use this for everyday tutoring and code help.

If you want a bit more speed and KV headroom for very long contexts:
```bash
ollama run qwen3:14b
```
~8.3 GB VRAM · ~40 tok/s · leaves 7+ GB for context window

### Best for hard problems: Qwen3 32B (stretch mode)
```bash
ollama run qwen3:32b
```
~18.5 GB total weights · 16 GB on GPU, ~2.5 GB offloaded to RAM · ~20-25 tok/s

This runs mostly on your GPU with a small amount in RAM — noticeably smarter than 14B on complex topics. Worth the slight speed trade-off for hard maths, deep subject tutoring, or tricky debugging.

### Best for step-by-step reasoning: DeepSeek-R1 14B
```bash
ollama run deepseek-r1:14b
```
~8.5 GB VRAM · ~35 tok/s · shows full reasoning chain before answering

Excellent for subjects where you want to understand *why*, not just get an answer: proofs, algorithms, physics problems, debugging logic. The reasoning chain appears before the answer and is itself educational.

### Best for code specifically: Qwen2.5-Coder 14B
```bash
ollama run qwen2.5-coder:14b
```
~8.3 GB VRAM · ~40 tok/s · trained specifically on code

Handles multi-file edits, explains complex functions, writes tests, refactors — code tasks where a general model would struggle. Use alongside `qwen3:14b` if you want both.

### Biggest/smartest option: Qwen3 30B MoE
```bash
ollama run qwen3:30b-a3b
```
~18 GB weights (mostly on GPU) · ~50 tok/s · sparse MoE architecture

A "mixture of experts" model — 30B total parameters but only ~3B active per response. Fast and smart. Fits mostly in 16 GB VRAM with minimal RAM overflow. Good if you want the smartest model at good speed.

---

## Talking to it (terminal)

```bash
ollama run qwen3:14b-q8_0
```

Then ask anything:

```
>>> I'm learning Rust. I know Python well — explain ownership and borrowing
    using analogies from Python's memory model.

>>> Here is a function I wrote that has a subtle bug. Walk me through finding it:
    [paste code]

>>> Explain gradient descent to me from first principles, then show me
    a minimal Python implementation.

>>> I have a 500-line Python module. Here it is: [paste]
    Suggest how to refactor it for readability and testability.
```

Type `/bye` to exit, `/clear` to reset the conversation and free context for a new topic.

---

## Using your own documents

### Short docs (reports, articles, chapters)
Paste directly. `qwen3:14b` holds ~90,000 words in memory at once — enough for a full textbook chapter, a research paper, or a sizeable codebase.

```
>>> Here are my lecture notes on operating systems: [paste]
>>> Generate a set of exam-style questions and then work through the answers.
```

### Large document sets — Open WebUI

Open WebUI provides a browser-based interface with PDF upload, document indexing, and conversation history. Install with Docker:

```bash
docker run -d -p 3000:80 \
  -v open-webui:/app/backend/data \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  ghcr.io/open-webui/open-webui:main
```

Open `http://localhost:3000`. Upload a folder of PDFs and ask questions across all of them. Open WebUI chunks, indexes, and retrieves relevant sections automatically.

### Whole codebase analysis
For a project with many files, pipe it in or use a tool like `files-to-prompt` to concatenate:

```bash
# Install once
pip install files-to-prompt

# Pipe your project into the model
files-to-prompt src/ | ollama run qwen3:32b
```

Then ask questions or request refactors in the session.

---

## Running two models at once

With 64 GB RAM you can keep a second model loaded while the first is active. Open two terminals:

```bash
# Terminal 1: reasoning model for hard questions
ollama run deepseek-r1:14b

# Terminal 2: code model for implementation
ollama run qwen2.5-coder:14b
```

Ollama keeps both in memory (using RAM for the inactive one) and switches in a few seconds. Useful workflow: work out the approach in the reasoning model, then implement in the coder.

---

## Performance expectations

| Model | VRAM | RAM overflow | Speed | Best for |
|---|---|---|---|---|
| qwen3:14b-q8_0 | 14.5 GB | none | ~30 tok/s | Best quality fully on-GPU |
| qwen3:14b | 8.3 GB | none | ~40 tok/s | Speed + large context headroom |
| qwen3:32b | 16 GB | ~2.5 GB | ~22 tok/s | Hardest problems, smartest answers |
| qwen3:30b-a3b | ~16 GB | minimal | ~50 tok/s | Fast + smart (MoE architecture) |
| deepseek-r1:14b | 8.5 GB | none | ~35 tok/s | Step-by-step reasoning |
| qwen2.5-coder:14b | 8.3 GB | none | ~40 tok/s | Code-first tasks |

All speeds on a mid-range 16 GB card (RTX 4060 Ti / RTX 4080 / RX 7900 XT class). AM5 CPU with DDR5 keeps RAM-overflow latency low.

---

## How this compares to the 8 GB setup

| Capability | 8 GB (7-8B model) | 16 GB (14-32B model) |
|---|---|---|
| Simple coding tasks | ✓ solid | ✓ solid |
| Multi-file refactoring | ✗ often wrong | ✓ handles well |
| Complex algorithm implementation | ✗ misses edge cases | ✓ reliable |
| University-level maths/science | ~ partial | ✓ good |
| Deep subject reasoning | ~ shallow | ✓ substantial |
| Long document analysis | ✓ (128k ctx) | ✓ (128k ctx + more KV) |
| Speed | ~50 tok/s | ~25-40 tok/s |

The 8 GB model is a capable assistant for well-defined questions. The 14-32B model behaves more like a knowledgeable colleague — it catches problems you didn't ask about, explains trade-offs, and handles ambiguity better.

---

## Quick start summary

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the recommended model (~14.5 GB download — best quality)
ollama pull qwen3:14b-q8_0

# 3. Start chatting
ollama run qwen3:14b-q8_0

# Optional: browser UI with document upload
docker run -d -p 3000:80 -v open-webui:/app/backend/data \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  ghcr.io/open-webui/open-webui:main
# → open http://localhost:3000

# Optional: for hard problems and step-by-step reasoning
ollama pull deepseek-r1:14b

# Optional: when you hit a genuinely hard problem
ollama pull qwen3:32b
```

---

## Tips

- **Paste aggressively.** The model cannot see your screen, IDE, or files unless you paste them. Include error messages, stack traces, and the relevant code together in one message.
- **Ask for the reasoning, not just the answer.** *"Explain why this approach works and what the alternatives are"* gives you more than just a solution.
- **For code: ask it to write tests first.** A model that writes tests before implementation makes the requirements concrete and catches misunderstandings early.
- **Use `/clear` between topics.** Starting fresh keeps the context clean and responses sharper.
- **Everything is local.** No API key, no usage limits, no data leaving the machine.
