"""GPU monitoring via pynvml (nvidia-ml-py). Fails gracefully if unavailable."""
from __future__ import annotations

import threading
import time
import warnings

try:
    import pynvml
    pynvml.nvmlInit()
    _num_gpus = pynvml.nvmlDeviceGetCount()
    _handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(_num_gpus)]
    _available = True
except Exception as exc:
    warnings.warn(f"pynvml unavailable — GPU snapshots disabled: {exc}", RuntimeWarning, stacklevel=2)
    _available = False
    _handles = []
    _num_gpus = 0


def get_gpu_snapshot() -> dict | None:
    """Capture vram_used_mb, gpu_util, mem_bandwidth_util summed across all GPUs. Returns None if unavailable."""
    if not _available:
        return None
    try:
        total_vram_mb = 0
        max_util = 0
        max_bw = 0
        for handle in _handles:
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
            total_vram_mb += int(mem.used // (1024 * 1024))
            max_util = max(max_util, int(rates.gpu))
            max_bw = max(max_bw, int(rates.memory))
        return {
            "vram_used_mb": total_vram_mb,
            "gpu_util": max_util,
            "mem_bandwidth_util": max_bw,
        }
    except Exception:
        return None


def wait_for_gpu_idle(
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    util_threshold: int = 5,
    vram_stable_mb: int = 50,
    baseline_vram_mb: int | None = None,
    vram_headroom_mb: int = 200,
) -> dict | None:
    """
    Poll until all three conditions hold simultaneously:
      - gpu_util < util_threshold  (max across all GPUs)
      - vram_used_mb < baseline_vram_mb + vram_headroom_mb  (skipped if baseline_vram_mb is None)
      - vram_used_mb changed less than vram_stable_mb vs the previous poll

    Returns the snapshot with "dirty": False on clean exit, or "dirty": True if the timeout
    expired with VRAM still above baseline. Falls back to the last snapshot seen on timeout.
    Returns None if GPU monitoring is unavailable.
    """
    if not _available:
        return None
    prev: dict | None = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = get_gpu_snapshot()
        if snap is not None:
            vram_drained = (
                baseline_vram_mb is None
                or snap["vram_used_mb"] < baseline_vram_mb + vram_headroom_mb
            )
            if (
                prev is not None
                and snap["gpu_util"] < util_threshold
                and abs(snap["vram_used_mb"] - prev["vram_used_mb"]) < vram_stable_mb
                and vram_drained
            ):
                snap["dirty"] = False
                return snap
            prev = snap
        time.sleep(poll_interval)
    # timeout — return last snapshot seen, flagged dirty if VRAM is still above baseline
    result = prev if prev is not None else get_gpu_snapshot()
    if result is not None:
        result["dirty"] = (
            baseline_vram_mb is not None
            and result["vram_used_mb"] >= baseline_vram_mb + vram_headroom_mb
        )
    return result


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


class StallClock:
    """Tracks how long every GPU has been idle. A request that is open while all GPUs sit at (near) zero
    utilisation for stall_s seconds is a hang: on the split-model WSL hang (2026-10-09..12) the server spins
    on a GPU completion that never comes, the GPUs read exactly 0%, and the request would otherwise wait for
    its full client timeout (40 min). Models that page experts through the CPU still keep a GPU above zero.
    idle_util is 5, not 1: under WSL the display GPU idles at 1-3% (Windows' compositor), which kept a 0-1 threshold
    from ever firing on a blocked single-GPU server (2026-10-14)."""

    def __init__(self, stall_s: float, idle_util: int = 5):
        self.stall_s = stall_s
        self.idle_util = idle_util
        self._idle_since: float | None = None

    def update(self, now: float, max_util: int | None) -> bool:
        """Feed one sample (the busiest GPU's utilisation, None when unreadable); True once stalled."""
        if max_util is None or max_util > self.idle_util:
            self._idle_since = None
            return False
        if self._idle_since is None:
            self._idle_since = now
        return now - self._idle_since >= self.stall_s


def launch_stall_watch(stop_event: threading.Event, stall_s: float, on_stall,
                       poll_interval: float = 5.0) -> tuple[threading.Thread, list]:
    """Call on_stall() once if all GPUs stay idle for stall_s while stop_event is unset.
    Returns (thread, fired) where fired[0] is the idle duration when it fired."""
    fired: list = []

    def _worker() -> None:
        if not _available or stall_s <= 0:
            return
        clock = StallClock(stall_s)
        while not stop_event.wait(timeout=poll_interval):
            snap = get_gpu_snapshot()
            if clock.update(time.monotonic(), snap["gpu_util"] if snap else None):
                fired.append(stall_s)
                on_stall()
                return

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t, fired
