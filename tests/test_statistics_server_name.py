"""statistics._server_name: which engine the llama_server_ver column belongs to."""
from lib.statistics import _server_name


def test_name_recorded_in_the_snapshot_wins():
    assert _server_name({"llama_server_version": "0.21.1", "server_name": "vllm"}, "vllm") == "vllm"


def test_older_result_files_are_inferred_from_the_backend():
    old = {"llama_server_version": "b9999"}  # written before server_name existed
    assert _server_name(old, "vllm") == "vllm"
    assert _server_name(old, "llama-server") == "llama-server"


def test_no_version_means_no_engine_name():
    assert _server_name({"gpu": []}, "ollama") == ""
    assert _server_name(None, "ollama") == ""
