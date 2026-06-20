# hwmonitor — Hardware Watchdog

Standalone script that runs alongside `bench.py` in a second terminal. Polls GPU, CPU, and RAM
at a configurable interval, emits timestamped lines to stdout and a log file, and aborts the
benchmark process when a critical thermal or resource threshold is breached.

## Quick start

```bash
# Terminal 1 — start the monitor before the benchmark
./hwmonitor/hwmonitor.py

# Terminal 2 — run the benchmark normally
./run.sh --model-file models/candidates.txt ...
```

The monitor auto-detects a running `bench.py` process on first CRIT. To pin the PID
explicitly (avoids a brief detection gap):

```bash
./run.sh ... & ./hwmonitor/hwmonitor.py --pid $!
```

## Output format

```
14:32:01   GPU0[4090] 64°C 320W/450W 22.1/24.0GB 98%  GPU1[3090] 91°C 310W/350W 18.4/24.0GB 95%  CPU N/A  RAM 42.1/86.0GB
WARN       14:32:03  GPU1[3090] junction temp °C 93 ≥ 90
CRIT       14:32:05  GPU1[3090] junction temp °C 101 ≥ 100 — aborting bench.py PID 12345
           → SIGINT → PID 12345
           → PID 12345 exited after SIGINT
OK         14:32:31  GPU1[3090] junction temp °C recovered (88)
```

- Data lines: one per interval, always printed
- WARN (yellow): emitted once on first threshold breach; again if state changes
- CRIT (red): emitted on escalation; triggers abort sequence
- OK (green): emitted when a previously alarmed metric recovers
- State transitions only — no repeated WARN/CRIT noise while condition persists

## Abort sequence

On first CRIT for any metric:
1. Send `SIGINT` to bench.py (same as Ctrl+C — saves results, writes JSON, exits cleanly)
2. Wait `--abort-timeout` seconds (default: 3)
3. If process still alive: send `SIGTERM`

Each PID is only signalled once. Subsequent CRITs (different metric or recovery cycle)
do not re-send signals to an already-aborted process.

## Default thresholds

| Metric | WARN | CRIT |
|---|---|---|
| GPU core temp | 85°C | 95°C |
| GPU junction/hotspot | 90°C | 100°C |
| CPU package temp | 85°C | 95°C |
| GPU power (% of limit) | 95% | — |
| RAM used | 90% | — |

All overridable via CLI flags.

## CLI reference

```
--interval S          Poll interval in seconds (default: 2)
--log FILE            Log file path (default: output/hwmonitor.log)
--pid PID             bench.py PID to abort on CRIT (auto-detected if omitted)
--abort-timeout S     Seconds between SIGINT and SIGTERM (default: 3)
--warn-gpu-temp C     GPU core warn threshold (default: 85)
--crit-gpu-temp C     GPU core crit threshold (default: 95)
--warn-junction C     GPU junction warn threshold (default: 90)
--crit-junction C     GPU junction crit threshold (default: 100)
--warn-cpu-temp C     CPU warn threshold (default: 85)
--crit-cpu-temp C     CPU crit threshold (default: 95)
--warn-power-pct PCT  GPU power-vs-limit warn threshold (default: 95)
--warn-ram-pct PCT    RAM usage warn threshold (default: 90)
```

## Metrics and sources

| Metric | Source | Notes |
|---|---|---|
| GPU core temp | `nvidia-smi temperature.gpu` | Always available |
| GPU junction/hotspot | `nvidia-smi temperature.gpu.hotspot` | Falls back to core-only if driver too old |
| GPU power draw / limit | `nvidia-smi power.draw,power.limit` | |
| GPU VRAM used / total | `nvidia-smi memory.used,memory.total` | |
| GPU utilisation % | `nvidia-smi utilization.gpu` | |
| CPU temp | `/sys/class/thermal/thermal_zone*/temp` | N/A on WSL2 (no kernel sensor access) |
| RAM used / total | `/proc/meminfo` MemTotal, MemAvailable | |

## Dependencies

- `nvidia-smi` — already required by the project
- Python 3.12 stdlib only — no additional packages beyond what the project already uses

## Integration path (future)

bench.py will gain an `--hwmonitor` flag that spawns `hwmonitor.py` automatically and
passes `--pid $$`. No changes to the standalone script are needed for that integration.

## Known limitations

- **WSL2 CPU temp**: `/sys/class/thermal` is not populated under the Microsoft WSL2 kernel.
  CPU temp shows as `N/A`. Native Linux or bare-metal installs work correctly.
- **Junction temp**: Requires NVIDIA driver ≥ 450. Older drivers fall back to core temp only
  with a startup notice.
- **Single abort per CRIT**: Once a PID has been signalled, subsequent CRITs (e.g. temperature
  recovered then spiked again) will not re-send signals. Restart hwmonitor to re-arm.
