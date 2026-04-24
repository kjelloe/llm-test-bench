import json
from collections import defaultdict
from pathlib import Path


def write_results(results: list[dict], path: str) -> None:
    Path(path).write_text(json.dumps(results, indent=2), encoding="utf-8")


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    for model, recs in by_model.items():
        total = len(recs)
        passed = sum(1 for r in recs if r["tests_pass"])
        tok_rates = [r["tok_per_s"] for r in recs if r.get("tok_per_s", 0) > 0]
        avg_tok = sum(tok_rates) / len(tok_rates) if tok_rates else 0.0

        pct = 100 * passed // total if total else 0
        print(f"\nModel : {model}")
        print(f"  Pass rate : {passed}/{total}  ({pct}%)")
        print(f"  Avg tok/s : {avg_tok:.1f}")

        failures = [r for r in recs if not r["tests_pass"]]
        if failures:
            counts: dict[str, int] = defaultdict(int)
            for r in failures:
                counts[r.get("error_kind") or "unknown"] += 1
            print("  Failures  :")
            for kind, count in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"    {kind}: {count}")

    print("\n" + "=" * 64)
