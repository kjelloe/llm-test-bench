#!/usr/bin/env python3
"""
export.py — Export/import benchmark results for cross-hardware sharing.

Usage (via statistics.sh):
  ./statistics.sh --export                        bundle output/*.json → stats-exported.json
  ./statistics.sh --export --out shared.json      custom output path
  ./statistics.sh --import stats-exported.json    extract runs → output/
  ./statistics.sh --import friend.json            plain results file → output/results-import-friend.json

Export format (version 2)
-------------------------
{
  "format": "ollama-code-bench-export",
  "version": 2,
  "instance_id": "a3f7b2c1",        # 8-hex persistent per-machine ID (.instance-id)
  "exported_at": "<ISO-8601>",
  "source_hardware": {
    "gpu": "NVIDIA GeForce RTX 3090 24GB",   # human-readable label
    "gpu_slug": "RTX_3090_24GB",             # filesystem slug (1 GPU)
    # multi-GPU examples:
    #   "gpu_slug": "2x_RTX_3090_48GB"       # 2x same GPU, shows total VRAM
    #   "gpu_slug": "RTX_3090_RTX_4090_48GB" # mixed, shows total VRAM
    "cpu": "...", "ram_total_gb": 86, "total_vram_gb": 24, ...
  },
  "run_count": N,
  "total_task_results": M,
  "distinct_models": [...],
  "runs": [
    { "filename": "results-compare-ls.json", "hardware": {...}, "results": [...] },
    ...
  ]
}

Filename scheme on import
-------------------------
  results-import-<gpu_slug>-<instance_id>-<original_filename>.json

This means:
  • Two friends with the SAME GPU model get different filenames (different instance_id).
  • A second import from the SAME friend produces the same filenames → existing files
    are overwritten (update behaviour).

Cross-hardware use
------------------
Imported files land in output/ in the native format, so all statistics.sh commands
pick them up automatically.  When the imported data is from a different GPU tier, use
  ./statistics.sh --estimate-vram --anchor-vram N
to treat that tier as the estimation anchor.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR  = SCRIPT_DIR / "output"

EXPORT_FORMAT  = "ollama-code-bench-export"
EXPORT_VERSION = 2

# Persistent per-instance ID lives at the repo root (gitignored).
INSTANCE_ID_FILE = SCRIPT_DIR / ".instance-id"

_SKIP_FILES = {"hf-scout-state.json", "compare-history.json"}


# ── instance identity ─────────────────────────────────────────────────────────

def _get_or_create_instance_id() -> str:
    """Return the 8-hex persistent machine ID, creating it on first call."""
    if INSTANCE_ID_FILE.exists():
        iid = INSTANCE_ID_FILE.read_text().strip()
        if iid:
            return iid
    iid = uuid.uuid4().hex[:8]
    try:
        INSTANCE_ID_FILE.write_text(iid)
    except OSError:
        pass  # fallback: non-persistent ID (still unique for this run)
    return iid


# ── GPU slug ──────────────────────────────────────────────────────────────────

def _strip_vendor(name: str) -> str:
    for prefix in ("NVIDIA GeForce ", "NVIDIA ", "AMD Radeon ", "Intel Arc ", "Intel "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_")


def _build_gpu_slug(gpus: list[dict]) -> str:
    """
    Filesystem-safe GPU identifier from a list of raw GPU dicts.

    Single GPU      → 'RTX_3090_24GB'
    2x same GPU     → '2x_RTX_3090_48GB'   (total VRAM shown)
    Mixed           → 'RTX_3090_RTX_4090_48GB'
    """
    if not gpus:
        return "no_GPU"

    names = [_strip_vendor(g.get("name", "GPU")) for g in gpus]
    total_vram = sum(g.get("vram_total_mb", 0) for g in gpus) // 1024
    n = len(gpus)

    if n == 1:
        return f"{_safe(names[0])}_{total_vram}GB"[:32]

    if all(name == names[0] for name in names):
        # Homogeneous multi-GPU: 2x_RTX_3090_48GB
        return f"{n}x_{_safe(names[0])}_{total_vram}GB"[:32]

    # Heterogeneous: RTX_3090_RTX_4090_48GB
    return ("_".join(_safe(n) for n in names) + f"_{total_vram}GB")[:32]


def _slug_from_summary(src_hw: dict) -> str:
    """Fallback slug for old v1 exports that lack gpu_slug in source_hardware."""
    gpu_label = src_hw.get("gpu", "unknown")
    for prefix in ("NVIDIA GeForce ", "NVIDIA ", "AMD Radeon ", "Intel Arc ", "Intel "):
        gpu_label = gpu_label.replace(prefix, "")
    return _safe(gpu_label)[:30] or "GPU"


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_results_file(path: Path) -> bool:
    if path.name in _SKIP_FILES:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return bool(data) and "task" in data[0]
        if isinstance(data, dict):
            rs = data.get("results", [])
            return bool(rs) and "task" in rs[0]
    except Exception:
        pass
    return False


def _load_results(path: Path) -> tuple[list[dict], dict | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, None
    return data.get("results", []), data.get("hardware")


def _hw_summary(hw: dict | None) -> dict:
    if not hw:
        return {}
    gpus = hw.get("gpu") or []
    gpu_parts = [
        f"{g.get('name', '?')} {g.get('vram_total_mb', 0) // 1024}GB"
        for g in gpus
    ]
    return {
        "gpu":          " + ".join(gpu_parts) if gpu_parts else "no GPU",
        "gpu_slug":     _build_gpu_slug(gpus),
        "cpu":          hw.get("cpu", ""),
        "ram_total_gb": hw.get("ram_total_gb", 0),
        "total_vram_gb": sum(g.get("vram_total_mb", 0) for g in gpus) / 1024,
        "platform":     hw.get("platform", ""),
        "cuda_toolkit": hw.get("cuda_toolkit", ""),
        "llama_server_version": hw.get("llama_server_version", ""),
    }


# ── export ────────────────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
    instance_id = _get_or_create_instance_id()

    src_files = sorted(OUTPUT_DIR.glob("*.json"))
    runs: list[dict] = []
    for p in src_files:
        if not _is_results_file(p):
            continue
        try:
            results, hardware = _load_results(p)
        except Exception as exc:
            print(f"  skip {p.name}: {exc}", file=sys.stderr)
            continue
        runs.append({"filename": p.name, "hardware": hardware, "results": results})

    if not runs:
        print("No result files found in output/", file=sys.stderr)
        sys.exit(1)

    source_hw_raw = next((r["hardware"] for r in reversed(runs) if r["hardware"]), None)
    hw_summary    = _hw_summary(source_hw_raw)
    total_tasks   = sum(len(r["results"]) for r in runs)
    all_models    = {res["model"] for r in runs for res in r["results"] if "model" in res}

    pkg = {
        "format":             EXPORT_FORMAT,
        "version":            EXPORT_VERSION,
        "instance_id":        instance_id,
        "exported_at":        datetime.now(timezone.utc).isoformat(),
        "source_hardware":    hw_summary,
        "run_count":          len(runs),
        "total_task_results": total_tasks,
        "distinct_models":    sorted(all_models),
        "runs":               runs,
    }

    out_path = Path(args.out) if args.out else Path("stats-exported.json")
    out_path.write_text(json.dumps(pkg, indent=2, ensure_ascii=False), encoding="utf-8")
    size_kb = out_path.stat().st_size // 1024

    slug = hw_summary.get("gpu_slug", "?")
    print(f"Exported {len(runs)} result files, {total_tasks} task results, "
          f"{len(all_models)} models → {out_path} ({size_kb} KB)")
    print(f"Hardware: {hw_summary.get('gpu', '?')}  "
          f"{hw_summary.get('cpu', '')}  "
          f"{hw_summary.get('ram_total_gb', '?')} GB RAM")
    print(f"Instance: {instance_id}  GPU slug: {slug}")
    print(f"Models:   {', '.join(sorted(all_models))}")


# ── import ────────────────────────────────────────────────────────────────────

def cmd_import(args: argparse.Namespace) -> None:
    src = Path(args.file)
    if not src.exists():
        print(f"File not found: {src}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Cannot parse {src}: {exc}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Plain results file (not an export package) — copy directly, overwrite.
    if not isinstance(data, dict) or data.get("format") != EXPORT_FORMAT:
        dest = OUTPUT_DIR / f"results-import-{src.stem}.json"
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Imported plain results file → {dest}")
        return

    version = data.get("version", 0)
    if version > EXPORT_VERSION:
        print(f"Warning: export version {version} is newer than supported "
              f"{EXPORT_VERSION} — some fields may be ignored.", file=sys.stderr)

    src_hw      = data.get("source_hardware", {})
    instance_id = data.get("instance_id", "unknown")
    # Prefer slug stored in the package; fall back for v1 exports without it.
    slug        = src_hw.get("gpu_slug") or _slug_from_summary(src_hw)
    exported    = data.get("exported_at", "?")
    models      = data.get("distinct_models", [])

    print(f"Import source:  {src_hw.get('gpu', '?')}")
    print(f"CPU / RAM:      {src_hw.get('cpu', '?')} / {src_hw.get('ram_total_gb', '?')} GB")
    print(f"Instance ID:    {instance_id}  (GPU slug: {slug})")
    print(f"Exported at:    {exported}")
    print(f"Models:         {', '.join(models) if models else '(unknown)'}")
    print()

    runs             = data.get("runs", [])
    imported_new: list[str] = []
    imported_upd: list[str] = []

    for run in runs:
        orig_name = run.get("filename", "results.json")
        # Filename encodes both slug and instance_id → same-instance re-import
        # produces the same name (→ overwrite/update); different instances always
        # produce different names (→ no collision, both coexist).
        dest_name = f"results-import-{slug}-{instance_id}-{orig_name}"
        dest      = OUTPUT_DIR / dest_name
        existed   = dest.exists()

        hw      = run.get("hardware")
        results = run.get("results", [])
        payload = {"hardware": hw, "results": results} if hw else results
        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        if existed:
            imported_upd.append(dest_name)
        else:
            imported_new.append(dest_name)

    print(f"Imported {len(imported_new)} new, updated {len(imported_upd)} existing files")
    for name in imported_new:
        print(f"  + {name}")
    for name in imported_upd:
        print(f"  ↻ {name}  (updated)")

    if imported_new or imported_upd:
        print()
        print("Results are now in output/ — all statistics.sh commands will pick them up.")
        total_vram = int(src_hw.get("total_vram_gb", 24))
        if total_vram != 24:
            print(f"Tip: data is from a {total_vram} GB GPU — use:")
            print(f"  ./statistics.sh --estimate-vram --anchor-vram {total_vram}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export/import benchmark results for cross-hardware sharing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--export", action="store_true",
        help="bundle all output/*.json into a sharable export file",
    )
    group.add_argument(
        "--import", dest="import_file", metavar="FILE",
        help="import an export package (or plain results file) into output/",
    )
    parser.add_argument(
        "--out", metavar="FILE",
        help="output path for --export (default: stats-exported.json)",
    )
    args = parser.parse_args()

    if args.export:
        cmd_export(args)
    else:
        args.file = args.import_file
        cmd_import(args)


if __name__ == "__main__":
    main()
