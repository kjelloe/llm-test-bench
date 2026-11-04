#!/usr/bin/env bash
# Run on the Mac that serves the model (macOS, Apple Silicon); prints the facts a --backend mlx result should carry:
#   ./mlx-host-info.sh > mac.json      then on the harness machine:  ./run.sh --backend mlx --mlx-host-info mac.json ...
# PYTHON: the interpreter mlx_lm.server runs under (default python3), so the mlx/mlx-lm versions are the served ones.
set -euo pipefail
PY="${PYTHON:-python3}"
[[ "$(uname -s)" == "Darwin" ]] || { echo "mlx-host-info.sh: run this on the Mac that serves the model" >&2; exit 1; }
chip=$(sysctl -n machdep.cpu.brand_string)
mem_bytes=$(sysctl -n hw.memsize)
macos=$(sw_vers -productVersion)
"$PY" - "$chip" "$mem_bytes" "$macos" <<'PYEOF'
import json, sys
from importlib.metadata import PackageNotFoundError, version

def ver(pkg):
    try:
        return version(pkg)
    except PackageNotFoundError:
        return None

chip, mem_bytes, macos = sys.argv[1], int(sys.argv[2]), sys.argv[3]
print(json.dumps({"chip": chip, "memory_gb": round(mem_bytes / 2**30), "memory_kind": "unified",
                  "macos": macos, "mlx": ver("mlx"), "mlx_lm": ver("mlx-lm"), "python": sys.version.split()[0]},
                 indent=2))
PYEOF
