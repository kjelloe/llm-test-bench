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


def test_gpu_info_records_memory_clock_and_pstate(monkeypatch):
    import subprocess
    from lib import hw_snapshot

    class R:
        returncode = 0
        stdout = "NVIDIA GeForce RTX 3090, 24576, 24000, 610.88, 40, 30.1, 240.00, 350.00, 1500, 2100, 8.6, 9751, P0\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    g = hw_snapshot._gpu_info()[0]
    assert g["clock_mhz"] == 1500 and g["mem_clock_mhz"] == 9751 and g["pstate"] == "P0" and g["compute_cap"] == 8.6
