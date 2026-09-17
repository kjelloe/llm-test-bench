"""hw_summary: the results header names the serving engine the version belongs to."""
from lib.hw_snapshot import hw_summary


def _hw(**extra) -> dict:
    return {
        "gpu": [{"name": "NVIDIA GeForce RTX 5060 Ti", "vram_total_mb": 16311}],
        "cpu": "AMD Ryzen 7 9800X3D",
        "ram_total_gb": 86.4,
        **extra,
    }


def test_vllm_version_is_labelled_vllm():
    s = hw_summary(_hw(llama_server_version="0.21.1rc1", server_name="vllm"))
    assert "vllm 0.21.1rc1" in s
    assert "llama-server" not in s


def test_llama_server_label_kept_for_results_without_server_name():
    # Result files written before server_name existed only carry llama_server_version.
    assert "llama-server b1234" in hw_summary(_hw(llama_server_version="b1234"))


def test_no_engine_label_without_a_version():
    assert "llama-server" not in hw_summary(_hw())
