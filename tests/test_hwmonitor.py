"""Tests for hwmonitor threshold state machine and hotspot probe fallback."""
import sys
import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock

# hwmonitor.py lives outside the package — import via path manipulation
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "hwmonitor",
    Path(__file__).parent.parent / "hwmonitor" / "hwmonitor.py",
)
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["hwmonitor"] = _MOD
_SPEC.loader.exec_module(_MOD)

Sample = _MOD.Sample
GpuSample = _MOD.GpuSample
Thresholds = _MOD.Thresholds
check_thresholds = _MOD.check_thresholds
_eval = _MOD._eval
probe_hotspot = _MOD.probe_hotspot


def _gpu(index=0, name="NVIDIA GeForce RTX 4090", temp=70.0, junction=None,
         power_draw=200.0, power_limit=450.0, vram_used=10000, vram_total=24000,
         util=80):
    return GpuSample(
        index=index, name=name,
        temp_c=temp, junction_c=junction,
        power_draw_w=power_draw, power_limit_w=power_limit,
        vram_used_mb=vram_used, vram_total_mb=vram_total,
        util_pct=util,
    )


def _sample(gpus=None, cpu=None, ram_used=30.0, ram_total=64.0):
    return Sample(
        ts=datetime.now(),
        gpus=gpus or [_gpu()],
        cpu_temp_c=cpu,
        ram_used_gb=ram_used,
        ram_total_gb=ram_total,
    )


T = Thresholds()


# ── _eval unit tests ──────────────────────────────────────────────────────────

def test_eval_ok_no_alert():
    out: list = []
    level = _eval("k", 70.0, 85.0, 95.0, "GPU0 temp", {}, out)
    assert level == "OK"
    assert out == []


def test_eval_warn_transition():
    out: list = []
    prev = {"k": "OK"}
    level = _eval("k", 87.0, 85.0, 95.0, "GPU0 temp", prev, out)
    assert level == "WARN"
    assert len(out) == 1
    assert out[0][0] == "WARN"


def test_eval_crit_transition():
    out: list = []
    prev = {"k": "WARN"}
    level = _eval("k", 96.0, 85.0, 95.0, "GPU0 temp", prev, out)
    assert level == "CRIT"
    assert len(out) == 1
    assert out[0][0] == "CRIT"


def test_eval_no_repeat_when_level_unchanged():
    """WARN while already in WARN state must not emit a second alert."""
    out: list = []
    prev = {"k": "WARN"}
    level = _eval("k", 88.0, 85.0, 95.0, "GPU0 temp", prev, out)
    assert level == "WARN"
    assert out == []


def test_eval_recovery_ok_alert():
    out: list = []
    prev = {"k": "WARN"}
    level = _eval("k", 70.0, 85.0, 95.0, "GPU0 temp", prev, out)
    assert level == "OK"
    assert len(out) == 1
    assert out[0][0] == "OK"


def test_eval_no_crit_threshold():
    """Metrics without a CRIT threshold (power, RAM) must never reach CRIT."""
    out: list = []
    level = _eval("k", 99.0, 95.0, None, "GPU0 power pct", {}, out)
    assert level == "WARN"
    assert out[0][0] == "WARN"


# ── check_thresholds integration tests ───────────────────────────────────────

def test_check_thresholds_no_alerts_normal():
    alerts, new = check_thresholds(_sample(), T, {})
    assert alerts == []
    assert new.get("g0_temp") == "OK"


def test_check_thresholds_gpu_temp_warn():
    s = _sample(gpus=[_gpu(temp=88.0)])
    alerts, _ = check_thresholds(s, T, {})
    levels = [a[0] for a in alerts]
    assert "WARN" in levels


def test_check_thresholds_gpu_temp_crit():
    s = _sample(gpus=[_gpu(temp=96.0)])
    alerts, _ = check_thresholds(s, T, {})
    levels = [a[0] for a in alerts]
    assert "CRIT" in levels


def test_check_thresholds_junction_warn():
    s = _sample(gpus=[_gpu(junction=92.0)])
    alerts, _ = check_thresholds(s, T, {})
    assert any(a[0] == "WARN" for a in alerts)


def test_check_thresholds_ram_warn():
    # 90% of 64 GB = 57.6 GB used
    s = _sample(ram_used=58.0, ram_total=64.0)
    alerts, _ = check_thresholds(s, T, {})
    assert any(a[0] == "WARN" for a in alerts)


def test_check_thresholds_carries_forward_unchanged_keys():
    """Keys not present in this sample must be preserved in new state dict."""
    s = _sample(gpus=[_gpu(temp=70.0)])  # no junction, no CPU
    prev = {"cpu_temp": "WARN"}
    _, new = check_thresholds(s, T, prev)
    assert new.get("cpu_temp") == "WARN"


def test_check_thresholds_multi_gpu():
    gpus = [_gpu(index=0, temp=70.0), _gpu(index=1, name="NVIDIA GeForce RTX 3090", temp=88.0)]
    s = _sample(gpus=gpus)
    alerts, new = check_thresholds(s, T, {})
    # GPU0 OK, GPU1 WARN
    assert new.get("g0_temp") == "OK"
    assert new.get("g1_temp") == "WARN"
    assert any("WARN" in a[0] for a in alerts)


# ── probe_hotspot fallback ────────────────────────────────────────────────────

def test_probe_hotspot_returns_false_on_error_output():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Field 'temperature.gpu.hotspot' is not a valid field to query.\n"
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        assert probe_hotspot() is False


def test_probe_hotspot_returns_true_when_supported():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "78\n82\n"
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        assert probe_hotspot() is True


def test_probe_hotspot_returns_false_on_exception():
    with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi not found")):
        assert probe_hotspot() is False
