"""Writes fixtures/*.json from bj-engine's captured CarrierDominion frames (games/carrierdominion/Tests/fixture.json,
bj-engine 60a8097, game 60cabd7). The captured run has events on one tick only, so events captured in other snapshots
are added to a few of its ticks so that order and tagging are testable. usage: python3 tools/make_fixtures.reference.py PATH"""
import json, sys
from pathlib import Path

src = json.load(open(sys.argv[1]))
out = Path(__file__).resolve().parent.parent / "fixtures"
out.mkdir(exist_ok=True)
compact = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)
extra = {3395: src["endedSnapshot"]["view"]["events"], 3401: src["contactsSnapshot"]["view"]["events"],
         3406: src["eventsSnapshot"]["view"]["events"] + src["endedSnapshot"]["view"]["events"][:1]}
for i, frame in enumerate(src["run"][:16]):
    frame = json.loads(json.dumps(frame))
    frame["view"]["events"] = frame["view"].get("events", []) + extra.get(frame["tick"], [])
    (out / f"run_{i:02d}.json").write_text(compact(frame))
for name in ("welcome", "lobby", "lobbyWelcome", "spectatorSnapshot"):
    (out / f"{name}.json").write_text(compact(src[name]))
(out / "broken.json").write_text(compact(src["run"][16])[:5000])
