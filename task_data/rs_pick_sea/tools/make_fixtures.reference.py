"""Writes fixtures/picks.txt from bj-engine's captured CarrierDominion picks (games/carrierdominion/Tests/commander.json,
written by its oracle from the game's own render/scene.js pickSea with three's Raycaster; bj-engine 60a8097, game 60cabd7).
One line per pick: eye xyz, target xyz, aspect, ndc xy, then the hit's engine x y, or "miss".
usage: python3 tools/make_fixtures.reference.py PATH/commander.json"""
import json, sys
from pathlib import Path

picks = json.load(open(sys.argv[1]))["picks"]
out = Path(__file__).resolve().parent.parent / "fixtures" / "picks.txt"
lines = []
for p in picks:
    head = " ".join(repr(float(v)) for v in p["eye"] + p["target"] + [p["aspect"]] + p["ndc"])
    hit = p["hit"]
    lines.append(f"{head} {hit['x']} {hit['y']}" if isinstance(hit, dict) else f"{head} miss")
out.write_text("\n".join(lines) + "\n")
