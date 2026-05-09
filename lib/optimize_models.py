#!/usr/bin/env python3
"""
lib/optimize_models.py — Hardware-aware parameter optimizer for models/*.txt

Reads GPU capabilities (VRAM, compute, count) and RAM, then for each model
entry with a GGUF file suggests optimised llama-server startup params and
offers to write them back to the model file.

Usage:
    python3 lib/optimize_models.py [model_file] [--models-dir PATH]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent

# ── ANSI colours ──────────────────────────────────────────────────────────────
G  = '\033[0;32m'   # green
Y  = '\033[1;33m'   # yellow
R  = '\033[0;31m'   # red
C  = '\033[0;36m'   # cyan
B  = '\033[1m'      # bold
D  = '\033[2m'      # dim
NC = '\033[0m'      # reset

def _g(s: str) -> str: return f'{G}{s}{NC}'
def _y(s: str) -> str: return f'{Y}{s}{NC}'
def _r(s: str) -> str: return f'{R}{s}{NC}'
def _c(s: str) -> str: return f'{C}{s}{NC}'
def _b(s: str) -> str: return f'{B}{s}{NC}'
def _d(s: str) -> str: return f'{D}{s}{NC}'


# ── MoE detection ─────────────────────────────────────────────────────────────

_MOE_PATTERNS = [
    'qwen3-coder', 'qwen3.5', 'qwen3_coder',
    'gemma4', 'gemma-4', 'gemma_4',
    'deepseek-r1', 'deepseek-v2', 'deepseek-v3', 'deepseek-moe',
    'mixtral', '-moe-', '_moe_', ':moe',
]

def _is_moe(ollama_name: str, gguf_file: str | None) -> bool:
    text = (ollama_name + ' ' + (gguf_file or '')).lower()
    return any(p in text for p in _MOE_PATTERNS)


# ── Hardware detection ────────────────────────────────────────────────────────

def get_gpu_info() -> list[dict]:
    """Query nvidia-smi. Returns list of {name, vram_gb, vram_free_gb, compute_cap}."""
    # Try with compute_cap first; fall back without it if unsupported
    for fields in (
        'name,memory.total,memory.free,compute_cap',
        'name,memory.total,memory.free',
    ):
        try:
            r = subprocess.run(
                ['nvidia-smi', f'--query-gpu={fields}', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                continue
            gpus: list[dict] = []
            for line in r.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 3:
                    continue
                try:
                    vram_gb      = int(parts[1]) / 1024
                    vram_free_gb = int(parts[2]) / 1024
                    cap = float(parts[3]) if len(parts) >= 4 else _infer_cap(parts[0])
                    gpus.append({
                        'name':         parts[0],
                        'vram_gb':      vram_gb,
                        'vram_free_gb': vram_free_gb,
                        'compute_cap':  cap,
                    })
                except (ValueError, IndexError):
                    continue
            return gpus
        except Exception:
            continue
    return []


def _infer_cap(gpu_name: str) -> float:
    """Best-effort compute capability from GPU name when nvidia-smi field is unavailable."""
    n = gpu_name.upper()
    if 'RTX 50' in n:  return 12.0   # Blackwell
    if 'RTX 40' in n:  return 8.9    # Ada Lovelace
    if 'RTX 30' in n:  return 8.6    # Ampere
    if 'A100'   in n:  return 8.0
    if 'H100'   in n:  return 9.0
    if 'RTX 20' in n:  return 7.5    # Turing (no flash-attn)
    return 0.0


def _batch_tier(total_vram: float) -> tuple[int, int]:
    """Return (batch_size, ubatch_size) for prompt-eval throughput based on total VRAM."""
    if total_vram < 20: return (512, 128)
    if total_vram < 28: return (1024, 256)
    if total_vram < 56: return (2048, 512)
    return (4096, 512)


def _suggested_ctx(total_vram: float) -> int:
    """Suggested DEFAULT_CTX based on total VRAM tier."""
    if total_vram < 20: return 8192
    if total_vram < 28: return 16384
    if total_vram < 56: return 32768
    return 65536


def get_ram_gb() -> float:
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                return round(int(line.split()[1]) / 1024 / 1024, 1)
    except Exception:
        pass
    return 0.0


# ── GGUF size ─────────────────────────────────────────────────────────────────

def get_gguf_size_gb(models_dir: str, gguf_file: str) -> float:
    """Return total on-disk size in GB, summing all shards for multi-part models."""
    if not models_dir or not gguf_file:
        return 0.0
    base = Path(models_dir)
    m = re.match(r'^(.+?)-(\d{5})-of-(\d{5})(\..+)$', gguf_file)
    if m:
        prefix, total_s, ext = m.group(1), m.group(3), m.group(4)
        total = int(total_s)
        size = sum(
            (base / f'{prefix}-{i:05d}-of-{total:05d}{ext}').stat().st_size
            for i in range(1, total + 1)
            if (base / f'{prefix}-{i:05d}-of-{total:05d}{ext}').exists()
        )
    else:
        p = base / gguf_file
        size = p.stat().st_size if p.exists() else 0
    return round(size / 1024 ** 3, 1) if size > 0 else 0.0


# ── Param suggestion logic ────────────────────────────────────────────────────

def suggest_params(
    ollama_name: str,
    gguf_file:   str | None,
    gguf_gb:     float,
    current:     dict,
    gpus:        list[dict],
    ram_gb:      float,
) -> tuple[dict, list[tuple[str, str]]]:
    """Return (suggested_params_dict, [(symbol, reason), ...]).

    symbol meanings:
      '+'  add new param
      '~'  change or remove existing param
      '!'  warning — manual action recommended
    """
    sugg = dict(current)
    reasons: list[tuple[str, str]] = []

    total_vram = sum(g['vram_gb'] for g in gpus)
    num_gpus   = len(gpus)
    cap        = max((g.get('compute_cap', 0.0) for g in gpus), default=0.0)
    moe        = _is_moe(ollama_name, gguf_file)

    # 85% safety margin: model must fit within 85% of VRAM to be "fully GPU-resident".
    # Leaves headroom for KV cache, compute buffers, and display use.
    full_gpu_fit = gguf_gb > 0 and gguf_gb <= total_vram * 0.85

    # ── MoE: n_cpu_moe ────────────────────────────────────────────────────────
    # Resolved BEFORE ngl so ngl can read the updated sugg.
    if moe and gguf_gb > 0:
        if full_gpu_fit:
            if 'n_cpu_moe' in sugg:
                del sugg['n_cpu_moe']
                reasons.append(('~', f'n_cpu_moe removed: model ({gguf_gb:.1f} GB) fits in VRAM ({total_vram:.0f} GB, 85% = {total_vram*0.85:.0f} GB) — run all experts on GPU'))
        else:
            if 'n_cpu_moe' not in sugg:
                sugg['n_cpu_moe'] = '35'
                reasons.append(('+', 'n_cpu_moe=35: MoE model too large for VRAM — route expert layers to CPU'))

    # ── ngl ───────────────────────────────────────────────────────────────────
    if gguf_gb > 0:
        if full_gpu_fit:
            if sugg.get('ngl') != '999':
                sugg['ngl'] = '999'
                gpu_desc = f'{num_gpus}× {gpus[0]["vram_gb"]:.0f} GB = {total_vram:.0f} GB total' if num_gpus > 1 else f'{total_vram:.0f} GB'
                reasons.append(('+', f'ngl=999: model ({gguf_gb:.1f} GB) fits in VRAM ({gpu_desc})'))
        elif 'n_cpu_moe' in sugg:
            if sugg.get('ngl') != '999':
                sugg['ngl'] = '999'
                reasons.append(('+', 'ngl=999: n_cpu_moe set — expert layers go to CPU, dense layers offloaded to GPU'))
        else:
            ratio  = total_vram / gguf_gb
            usable = max(0.0, ratio - 0.20)
            est    = max(1, min(round(usable * 40), 40))
            if 'ngl' not in sugg:
                reasons.append(('!', f'ngl not set: model ({gguf_gb:.1f} GB) > VRAM ({total_vram:.0f} GB) — partial offload; starting point: ngl={est}'))

    # ── no_mmap ───────────────────────────────────────────────────────────────
    # Benchmark-specific: eager full load into anonymous RAM eliminates page-fault
    # timing variance during generation. For general serving, --mmap + --mlock is
    # preferred; no_mmap is used here because the harness is a benchmark (see SPEC).
    if gguf_gb >= 8 and 'no_mmap' not in sugg and ram_gb >= gguf_gb * 1.2:
        sugg['no_mmap'] = True
        reasons.append(('+', f'no_mmap: benchmark timing — eager load into RAM ({ram_gb:.0f} GB) avoids page-fault variance; see SPEC for serving alternative'))

    # ── mlock ─────────────────────────────────────────────────────────────────
    if full_gpu_fit:
        if 'mlock' in sugg:
            del sugg['mlock']
            reasons.append(('~', f'mlock removed: model fits in VRAM ({total_vram:.0f} GB) — no need to pin system RAM copy'))
    else:
        if gguf_gb >= 16 and 'mlock' not in sugg and ram_gb >= gguf_gb * 1.5:
            sugg['mlock'] = True
            reasons.append(('+', f'mlock: model ({gguf_gb:.1f} GB) is RAM-resident; pin to {ram_gb:.0f} GB RAM to prevent paging'))

    # ── KV cache types ────────────────────────────────────────────────────────
    # f16 when model is fully GPU-resident (max quality at typical context lengths).
    # q8_0 otherwise (good quality/memory tradeoff for larger or partially-offloaded models).
    kv_target = 'f16' if full_gpu_fit else 'q8_0'
    for key in ('cache_type_k', 'cache_type_v'):
        if key not in sugg:
            label = 'max quality — model fully GPU-resident' if kv_target == 'f16' else 'quantised KV — saves VRAM for long context'
            sugg[key] = kv_target
            reasons.append(('+', f'{key}={kv_target}: {label}'))
        elif sugg[key] in ('turbo4', 'turbo3'):
            old = sugg[key]
            sugg[key] = kv_target
            reasons.append(('~', f'{key}: {old} → {kv_target} (turbo types unsupported by many llama.cpp builds)'))
        elif sugg[key] == 'q8_0' and kv_target == 'f16':
            sugg[key] = 'f16'
            reasons.append(('~', f'{key}: q8_0 → f16 (model fully GPU-resident — f16 gives better quality at no extra VRAM cost)'))

    # ── flash attention ───────────────────────────────────────────────────────
    if cap >= 8.0 and 'flash_attn' not in sugg:
        arch = {8.6: 'Ampere', 8.9: 'Ada Lovelace', 9.0: 'Hopper', 12.0: 'Blackwell'}.get(
            cap, 'Ampere+' if cap >= 8.0 else f'compute {cap}')
        sugg['flash_attn'] = True
        reasons.append(('+', f'flash_attn: GPU compute {cap} ({arch}) — faster attention, lower VRAM for long contexts'))

    # ── multi-GPU: split mode and tensor split ────────────────────────────────
    if num_gpus >= 2:
        # row is the recommended default for serving; layer may be faster for
        # single-user token generation on PCIe-connected cards without NVLink.
        if 'split_mode' not in sugg:
            sugg['split_mode'] = 'row'
            per_gpu = ', '.join(f'{g["vram_gb"]:.0f} GB' for g in gpus)
            reasons.append(('+', f'split_mode=row: {num_gpus} GPUs ({per_gpu}) — recommended default; test layer for single-user PCIe token gen'))
        elif sugg.get('split_mode') == 'layer':
            sugg['split_mode'] = 'row'
            reasons.append(('~', 'split_mode: layer → row (recommended default; revert to layer if single-user PCIe token gen is faster)'))

        # tensor_split: weight by free VRAM when GPUs differ by more than 1 GB
        # (e.g. GPU 0 driving a display). Use pipe as sub-separator; CLI builder
        # converts | → , so model files stay comma-safe.
        if 'tensor_split' not in sugg:
            free = [g.get('vram_free_gb', g['vram_gb']) for g in gpus]
            free_rounded = [round(v) for v in free]
            if len(free) >= 2 and abs(free[0] - free[1]) > 1.0:
                ts_val = '|'.join(str(v) for v in free_rounded[:2])
                reasons.append(('+', f'tensor_split={free_rounded[0]},{free_rounded[1]}: GPU 0 has {free[0]:.0f} GB free vs GPU 1 {free[1]:.0f} GB — weighted (GPU 0 may drive a display)'))
            else:
                ts_val = '1|1'
                reasons.append(('+', f'tensor_split=1,1: equal GPU memory ({free_rounded[0]} GB free each) — balanced split'))
            sugg['tensor_split'] = ts_val

    # ── batch and micro-batch sizes ───────────────────────────────────────────
    batch, ubatch = _batch_tier(total_vram)
    if 'batch_size' not in sugg:
        sugg['batch_size'] = str(batch)
        reasons.append(('+', f'batch_size={batch}: prompt-eval throughput for {total_vram:.0f} GB VRAM'))
    if 'ubatch_size' not in sugg:
        sugg['ubatch_size'] = str(ubatch)
        reasons.append(('+', f'ubatch_size={ubatch}: micro-batch for {total_vram:.0f} GB VRAM (reduce to 128 if OOM during prompt eval)'))

    return sugg, reasons


# ── Param serialisation ───────────────────────────────────────────────────────

_PARAM_ORDER = [
    'ngl', 'split_mode', 'tensor_split', 'main_gpu', 'n_cpu_moe',
    'no_mmap', 'mlock',
    'cache_type_k', 'cache_type_v',
    'flash_attn',
    'batch_size', 'ubatch_size', 'threads_batch',
]

def params_to_str(params: dict) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    for key in _PARAM_ORDER:
        if key in params:
            val = params[key]
            parts.append(key if val is True else f'{key}={val}')
            seen.add(key)
    for key, val in params.items():
        if key not in seen:
            parts.append(key if val is True else f'{key}={val}')
    return ','.join(parts)


# ── Model file rewriter ───────────────────────────────────────────────────────

def rewrite_model_file(path: Path, updates: dict[str, dict]) -> None:
    """Rewrite lines in model file where ollama_name is in updates."""
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    out: list[str] = []
    for raw in lines:
        stripped = raw.split('#')[0].strip()
        if not stripped:
            out.append(raw)
            continue
        name = stripped.split()[0]
        if name not in updates:
            out.append(raw)
            continue

        parts = stripped.split()
        hf_part     = next((p for p in parts[1:] if p.startswith('hf:')), None)
        positional  = [p for p in parts[1:] if not p.startswith('hf:')]
        gguf_file   = positional[0] if positional else None

        new_params_str = params_to_str(updates[name])

        # Preserve trailing inline comment
        comment = ''
        if '#' in raw:
            comment = '  #' + raw.split('#', 1)[1].rstrip()

        fields = [name]
        if gguf_file:
            fields.append(gguf_file)
        if new_params_str:
            fields.append(new_params_str)
        if hf_part:
            fields.append(hf_part)

        out.append('  '.join(fields) + comment + '\n')

    path.write_text(''.join(out), encoding='utf-8')


# ── Interactive display ───────────────────────────────────────────────────────

def _fmt_reasons(reasons: list[tuple[str, str]]) -> list[str]:
    lines = []
    for sym, msg in reasons:
        colour = {'+': G, '~': Y, '!': R, '=': D}.get(sym, NC)
        lines.append(f'    {colour}{sym}{NC}  {msg}')
    return lines


def _diff_params(current: dict, suggested: dict) -> bool:
    """Return True if suggested differs from current."""
    return params_to_str(current) != params_to_str(suggested)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Hardware-aware model param optimizer')
    parser.add_argument('model_file', nargs='?', help='models/*.txt file to optimize')
    parser.add_argument('--models-dir', default=os.environ.get('LLAMA_MODELS_DIR', ''))
    parser.add_argument('--suggest-ctx', action='store_true',
                        help='Print suggested DEFAULT_CTX integer based on GPU and exit')
    args = parser.parse_args()

    if args.suggest_ctx:
        gpus = get_gpu_info()
        total_vram = sum(g['vram_gb'] for g in gpus) if gpus else 0.0
        print(_suggested_ctx(total_vram))
        sys.exit(0)

    # ── Hardware ──────────────────────────────────────────────────────────────
    gpus   = get_gpu_info()
    ram_gb = get_ram_gb()

    print(f'\n{B}Hardware detected{NC}')
    if gpus:
        total_vram = sum(g['vram_gb'] for g in gpus)
        for i, g in enumerate(gpus):
            cap_str  = f'  compute {g["compute_cap"]}' if g.get('compute_cap') else ''
            free_str = f'  ({g["vram_free_gb"]:.0f} GB free)' if 'vram_free_gb' in g else ''
            print(f'  GPU {i}: {_c(g["name"])}  {g["vram_gb"]:.0f} GB{free_str}{cap_str}')
        print(f'  Total VRAM : {_b(f"{total_vram:.0f} GB")}  ({len(gpus)} GPU{"s" if len(gpus) > 1 else ""})')
        ctx = _suggested_ctx(total_vram)
        print(f'  Suggested  : {_c(f"DEFAULT_CTX={ctx}")}  {_d(f"({total_vram:.0f} GB VRAM tier)")}')
    else:
        print(f'  {_y("No NVIDIA GPU detected or nvidia-smi unavailable")}')
    if ram_gb:
        print(f'  System RAM : {ram_gb:.0f} GB')
    print()

    if not gpus:
        print(_y('Cannot optimise without GPU info. Exiting.'))
        sys.exit(0)

    # ── Choose model file ─────────────────────────────────────────────────────
    model_file_path: Path | None = None
    if args.model_file:
        model_file_path = Path(args.model_file)
        if not model_file_path.exists():
            print(_r(f'Model file not found: {model_file_path}'))
            sys.exit(1)
    else:
        candidates = sorted((SCRIPT_DIR / 'models').glob('*.txt'))
        if not candidates:
            print(_y('No model files found in models/'))
            sys.exit(0)
        print(f'{B}Choose model file to optimize:{NC}')
        for i, p in enumerate(candidates, 1):
            try:
                from lib.model_config import load_model_file  # type: ignore
                cfgs  = load_model_file(p)
            except Exception:
                cfgs = []
            n_gguf = sum(1 for c in cfgs if c.gguf_file)
            print(f'  {i}) {p.name}  {_d(f"({len(cfgs)} models, {n_gguf} with GGUF)")}')
        print(f'  {len(candidates)+1}) Skip')
        while True:
            try:
                choice = input('\nChoice: ').strip()
                idx = int(choice) - 1
                if idx == len(candidates):
                    print(_d('Skipped.'))
                    sys.exit(0)
                model_file_path = candidates[idx]
                break
            except (ValueError, IndexError):
                print('  Please enter a valid number.')

    # ── Load model configs ────────────────────────────────────────────────────
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from lib.model_config import load_model_file  # type: ignore
        configs = load_model_file(model_file_path)
    except Exception as e:
        print(_r(f'Failed to load model file: {e}'))
        sys.exit(1)

    models_with_gguf = [c for c in configs if c.gguf_file]
    if not models_with_gguf:
        print(_y('No models with GGUF files found — nothing to optimize.'))
        sys.exit(0)

    print(f'{B}Analyzing:{NC} {model_file_path}')
    print('─' * 72)

    # ── Analyse each model ────────────────────────────────────────────────────
    apply_all       = False
    skip_all        = False
    updates: dict[str, dict] = {}

    for cfg in models_with_gguf:
        gguf_gb = get_gguf_size_gb(args.models_dir, cfg.gguf_file or '')
        size_str = f'{gguf_gb:.1f} GB' if gguf_gb > 0 else _y('file not found')

        print(f'\n  {_b(cfg.ollama_name)}  ·  {_d(cfg.gguf_file or "")}  ·  {size_str}')

        cur_str  = params_to_str(cfg.params) or _d('(none)')
        print(f'  Current :  {_d(cur_str)}')

        sugg, reasons = suggest_params(
            cfg.ollama_name, cfg.gguf_file, gguf_gb,
            cfg.params, gpus, ram_gb,
        )
        sugg_str = params_to_str(sugg)
        print(f'  Suggest :  {_c(sugg_str) if _diff_params(cfg.params, sugg) else _d(cur_str + "  (no changes)")}')

        if not _diff_params(cfg.params, sugg):
            print(f'  {_g("✓")}  {_d("Already optimal — no changes needed")}')
            continue

        for line in _fmt_reasons(reasons):
            print(line)

        if skip_all:
            print(f'  {_d("Skipped")}')
            continue

        if apply_all:
            updates[cfg.ollama_name] = sugg
            print(f'  {_g("→")} {_d("Applied (apply-all)")}')
            continue

        while True:
            ans = input('\n  Apply? [Y/n/a(ll)/s(kip all)]: ').strip().lower()
            if ans in ('', 'y'):
                updates[cfg.ollama_name] = sugg
                print(f'  {_g("✓")} Queued')
                break
            elif ans == 'n':
                print(f'  {_d("Skipped")}')
                break
            elif ans == 'a':
                apply_all = True
                updates[cfg.ollama_name] = sugg
                print(f'  {_g("✓")} Queued (apply-all)')
                break
            elif ans == 's':
                skip_all = True
                print(f'  {_d("Skipped (skip-all)")}')
                break

    # ── Write ─────────────────────────────────────────────────────────────────
    print()
    if not updates:
        print(_d('No changes to apply.'))
        return

    print(f'{B}Changes to write:{NC}')
    for name in updates:
        print(f'  {_g("+")}  {name}  →  {_c(params_to_str(updates[name]))}')
    print()

    ans = input('Write updated model file? [Y/n]: ').strip().lower()
    if ans not in ('', 'y'):
        print(_d('Aborted — file unchanged.'))
        return

    backup = model_file_path.with_suffix('.txt.bak')
    import shutil as _shutil
    _shutil.copy2(model_file_path, backup)
    print(f'  {_d(f"Backup: {backup}")}')

    rewrite_model_file(model_file_path, updates)
    print(f'  {_g("✓")} Written: {model_file_path}')
    print()


if __name__ == '__main__':
    main()
