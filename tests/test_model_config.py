import pytest
from lib.model_config import ModelConfig, load_model_file, parse_model_line


# ── parse_model_line ─────────────────────────────────────────────────────────

def test_ollama_name_only():
    cfg = parse_model_line("gpt-oss:20b")
    assert cfg == ModelConfig(ollama_name="gpt-oss:20b", gguf_file=None, params={}, hf_repo=None)


def test_with_gguf():
    cfg = parse_model_line("qwen2.5-coder:14b  qwen2.5-coder-14b-Q4_K_M.gguf")
    assert cfg.ollama_name == "qwen2.5-coder:14b"
    assert cfg.gguf_file == "qwen2.5-coder-14b-Q4_K_M.gguf"
    assert cfg.params == {}


def test_with_boolean_params():
    cfg = parse_model_line("qwen3.5:35b qwen3.5.gguf no_mmap,mlock")
    assert cfg.params == {"no_mmap": True, "mlock": True}


def test_with_kv_params():
    cfg = parse_model_line("qwen3.5:35b qwen3.5.gguf n_cpu_moe=35,cache_type_k=turbo4")
    assert cfg.params["n_cpu_moe"] == "35"
    assert cfg.params["cache_type_k"] == "turbo4"


def test_mixed_params():
    line = "gemma4:26b gemma4.gguf n_cpu_moe=18,no_mmap"
    cfg = parse_model_line(line)
    assert cfg.params["n_cpu_moe"] == "18"
    assert cfg.params["no_mmap"] is True


def test_hf_repo_after_gguf():
    cfg = parse_model_line("qwen2.5-coder:14b  model.gguf  hf:Qwen/Qwen2.5-Coder-14B-Instruct-GGUF")
    assert cfg.gguf_file == "model.gguf"
    assert cfg.hf_repo == "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
    assert cfg.params == {}


def test_hf_repo_after_params():
    cfg = parse_model_line("qwen3.5:35b  model.gguf  n_cpu_moe=35,no_mmap  hf:bartowski/Qwen3-GGUF")
    assert cfg.gguf_file == "model.gguf"
    assert cfg.hf_repo == "bartowski/Qwen3-GGUF"
    assert cfg.params["n_cpu_moe"] == "35"
    assert cfg.params["no_mmap"] is True


def test_hf_repo_before_params():
    cfg = parse_model_line("qwen3.5:35b  model.gguf  hf:owner/repo  n_cpu_moe=35")
    assert cfg.hf_repo == "owner/repo"
    assert cfg.gguf_file == "model.gguf"
    assert cfg.params["n_cpu_moe"] == "35"


def test_no_hf_repo():
    cfg = parse_model_line("qwen2.5-coder:14b  model.gguf")
    assert cfg.hf_repo is None


def test_inline_comment_stripped():
    cfg = parse_model_line("gpt-oss:20b  # ~82 tok/s  GPU, thinking")
    assert cfg == ModelConfig(ollama_name="gpt-oss:20b", gguf_file=None, params={}, hf_repo=None)


def test_gguf_with_inline_comment():
    cfg = parse_model_line("qwen2.5-coder:14b  model.gguf  # no params")
    assert cfg.gguf_file == "model.gguf"
    assert cfg.params == {}


def test_max_ctx_parsed_and_not_in_params():
    line = "gpt-oss:20b  gpt-oss-20b.gguf  ngl=999,no_mmap,max_ctx=131072"
    cfg = parse_model_line(line)
    assert cfg.max_ctx == 131072
    assert "max_ctx" not in cfg.params  # harness-only field; must not reach llama-server
    assert cfg.params["ngl"] == "999"
    assert cfg.params["no_mmap"] is True


def test_max_ctx_absent_is_none():
    cfg = parse_model_line("qwen2.5-coder:14b  model.gguf  ngl=999")
    assert cfg.max_ctx is None


def test_blank_line_returns_none():
    assert parse_model_line("") is None
    assert parse_model_line("   ") is None


def test_comment_only_returns_none():
    assert parse_model_line("# this is a comment") is None
    assert parse_model_line("  # another comment") is None


# ── load_model_file ──────────────────────────────────────────────────────────

def test_load_default_model_file():
    from pathlib import Path
    path = Path(__file__).parent.parent / "models" / "default.txt"
    configs = load_model_file(path)
    assert len(configs) >= 1
    for cfg in configs:
        assert cfg.ollama_name
        assert ":" in cfg.ollama_name  # all model names have a tag


def test_load_model_file_tmp(tmp_path):
    f = tmp_path / "models.txt"
    f.write_text(
        "# comment\n"
        "ollama-a\n"
        "ollama-b  b.gguf\n"
        "ollama-c  c.gguf  no_mmap,n_cpu_moe=35\n"
        "\n"
    )
    configs = load_model_file(f)
    assert len(configs) == 3
    assert configs[0].gguf_file is None
    assert configs[1].gguf_file == "b.gguf"
    assert configs[2].params["n_cpu_moe"] == "35"
    assert configs[2].params["no_mmap"] is True
