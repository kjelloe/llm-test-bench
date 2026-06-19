# Local AI Coding Ally — Mini SFF Setup Guide

**Hardware:** 8 GB VRAM GPU · 32 GB DDR5 · AMD AM5 CPU (e.g. Ryzen 9 9900X)
**Goal:** A private, offline AI that tutors on any subject and writes simple code — no cloud, no subscription.

---

## What you get

A local AI that runs entirely on your machine:
- Answers questions about any topic from your own documents or textbooks
- Explains concepts step-by-step, like a patient tutor
- Writes and explains simple code in Python, JavaScript, C#, and more
- Reads your PDFs, notes, and files directly
- Runs at 40–60 words per second — fast enough for interactive use
- Completely private: nothing leaves the machine

---

## Install Ollama (10 minutes)

Ollama handles everything: model download, GPU acceleration, and a local API.

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

On Windows: download the installer from [ollama.com](https://ollama.com).

Verify it's running:
```bash
ollama --version
```

---

## Which model to use

### Best all-rounder: Qwen3 8B
```bash
ollama run qwen3:8b
```
~5 GB VRAM · 128k context (≈ a full textbook) · ~50 words/sec

This is the recommendation. It handles tutoring, code examples, and document questions well.
Qwen3 is Alibaba's latest generation and punches well above its size.

### If you want step-by-step reasoning (maths, logic, science):
```bash
ollama run deepseek-r1:8b
```
~5 GB VRAM · Shows its working before answering · Slower but more thorough

Good for subjects where you want to see *why*, not just *what*.

### Smallest/fastest option (quick questions, slow machine):
```bash
ollama run gemma3:4b
```
~2.5 GB VRAM · ~80 words/sec · Less capable but very snappy

---

## Talking to it (terminal)

Once a model is running with `ollama run qwen3:8b`, just type:

```
>>> Explain recursion to me like I'm new to programming

>>> Show me a Python function that reads a CSV file and prints each row

>>> What's the difference between a list and a tuple in Python?

>>> I have this error: TypeError: 'int' object is not subscriptable — what does it mean?
```

Type `/bye` to exit.

---

## Using your own documents

### Short docs (under ~50 pages)
Just paste the text directly into the chat. Qwen3 8B holds ~90,000 words in memory at once.

```
>>> Here is a chapter from my textbook: [paste text]
>>> Now explain the key concept on page 3 in simpler terms.
```

### Larger document sets — use Open WebUI

Open WebUI gives you a browser-based chat interface with built-in PDF upload, document search, and conversation history.

Install (requires Docker):
```bash
docker run -d -p 3000:80 \
  -v open-webui:/app/backend/data \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  ghcr.io/open-webui/open-webui:main
```

Then open `http://localhost:3000` in your browser. Upload PDFs directly in the chat. It chunks and indexes them automatically so you can ask questions across a whole document collection.

---

## Practical examples

**Learning a new programming language:**
```
>>> I know Python. Teach me the equivalent of a Python list comprehension in JavaScript.
```

**Debugging:**
```
>>> My Python script throws this error:
    IndexError: list index out of range
    at line 14: result = items[i]
    Here is my code: [paste code]
    What's wrong and how do I fix it?
```

**Subject tutoring from a textbook:**
```
>>> Here is section 3.2 of my networking textbook: [paste]
>>> Give me 5 quiz questions to test my understanding, then answer them.
```

**Code walk-through:**
```
>>> Explain what this function does line by line: [paste code]
```

---

## Performance expectations

| Model | VRAM used | Speed | Best for |
|---|---|---|---|
| qwen3:8b | ~5 GB | ~50 tok/s | General tutoring + code |
| deepseek-r1:8b | ~5 GB | ~35 tok/s | Complex reasoning, maths |
| gemma3:4b | ~2.5 GB | ~80 tok/s | Quick questions |
| qwen3:14b* | ~8.3 GB | ~25 tok/s | Harder problems, smarter answers |

*qwen3:14b is a stretch — partially uses CPU RAM. Try it with `ollama run qwen3:14b`.
If it's too slow, drop back to `qwen3:8b`.

Ollama manages VRAM and RAM automatically. If a model doesn't fully fit in VRAM, it offloads layers to your 32 GB DDR5 and keeps going — slower but functional.

---

## Tips

- **Context is everything.** Paste the relevant code, error, or text with your question. The AI cannot see your screen or files unless you paste them in.
- **Iterate.** If the first answer is wrong or unclear, say so: *"That didn't work — here's the error I got now."*
- **Ask for explanations, not just answers.** *"Explain why this works"* teaches better than just getting correct code.
- **Use `/clear` in the Ollama terminal** to reset the conversation and free up context for a new topic.
- **Models are private.** Nothing is sent anywhere. You can air-gap this machine entirely.

---

## Quick start summary

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the recommended model (~5 GB download)
ollama pull qwen3:8b

# 3. Start chatting
ollama run qwen3:8b

# Optional: browser UI with document upload
docker run -d -p 3000:80 -v open-webui:/app/backend/data \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  ghcr.io/open-webui/open-webui:main
# → open http://localhost:3000
```
