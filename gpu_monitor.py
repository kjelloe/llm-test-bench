"""GPU monitoring via pynvml (nvidia-ml-py). Fails gracefully if unavailable."""
from __future__ import annotations

import threading
import warnings

try:
    import pynvml
    pynvml.nvmlInit()
    _handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    _available = True
except Exception as exc:
    warnings.warn(f"pynvml unavailable — GPU snapshots disabled: {exc}", RuntimeWarning, stacklevel=2)
    _available = False
    _handle = None


def get_gpu_snapshot() -> dict | None:
    """Capture vram_used_mb, gpu_util, mem_bandwidth_util for GPU 0. Returns None if unavailable."""
    if not _available:
        return None
    try:
        mem = pynvml.nvmlDeviceGetMemoryInfo(_handle)
        rates = pynvml.nvmlDeviceGetUtilizationRates(_handle)
        return {
            "vram_used_mb": int(mem.used // (1024 * 1024)),
            "gpu_util": int(rates.gpu),
            "mem_bandwidth_util": int(rates.memory),
        }
    except Exception:
        return None


def launch_peak_poller(stop_event: threading.Event, poll_interval: float = 0.5) -> tuple[threading.Thread, list]:
    """
    Poll GPU every poll_interval seconds until stop_event is set, then do one final poll.
    Returns (thread, holder) where holder[0] will be the sample with the highest gpu_util
    seen during the polling window (peak activity capture).

    Usage:
        stop = threading.Event()
        t, holder = launch_peak_poller(stop)
        do_work()
        stop.set()
        t.join(timeout=2.0)
        peak = holder[0] if holder else None
    """
    holder: list = []

    def _worker() -> None:
        if not _available:
            return
        peak: dict | None = None
        while not stop_event.wait(timeout=poll_interval):
            snap = get_gpu_snapshot()
            if snap is not None and (peak is None or snap["gpu_util"] > peak["gpu_util"]):
                peak = snap
        # one final poll after stop
        snap = get_gpu_snapshot()
        if snap is not None and (peak is None or snap["gpu_util"] > peak["gpu_util"]):
            peak = snap
        if peak is not None:
            holder.append(peak)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t, holder
