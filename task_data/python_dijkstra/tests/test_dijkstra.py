import pytest
from dijkstra import dijkstra, shortest_path


# Graphs used across multiple tests
G_DETOUR = {            # shorter path to B goes via C, not directly
    "A": [("B", 10), ("C", 1)],
    "B": [],
    "C": [("B", 1)],
}

G_LONG_CHAIN = {        # shorter path to B requires three hops; direct edge is expensive
    "A": [("B", 100), ("C", 1)],
    "C": [("D", 1)],
    "D": [("B", 1)],
    "B": [],
}

G_DIAMOND = {           # two paths to D; shorter one goes through C (total 5), not B (total 6)
    "A": [("B", 1), ("C", 4)],
    "B": [("D", 5)],
    "C": [("D", 1)],
    "D": [],
}


# ── Tests that pass even with the buggy implementation ──────────────────────

def test_start_node_zero_distance():
    dist, prev = dijkstra({"A": []}, "A")
    assert dist["A"] == 0
    assert prev["A"] is None


def test_linear_chain_distances():
    graph = {"A": [("B", 3)], "B": [("C", 2)], "C": []}
    dist, _ = dijkstra(graph, "A")
    assert dist == {"A": 0, "B": 3, "C": 5}


def test_direct_edge_is_shorter():
    # direct A→B=1 beats A→C→B=11; bug does not affect this case
    graph = {"A": [("B", 1), ("C", 1)], "C": [("B", 10)], "B": []}
    dist, _ = dijkstra(graph, "A")
    assert dist["B"] == 1


def test_unreachable_node_absent():
    graph = {"A": [("B", 1)], "B": [], "C": []}
    dist, _ = dijkstra(graph, "A")
    assert "C" not in dist


def test_no_path_returns_none():
    graph = {"A": [("B", 1)], "B": [], "C": []}
    assert shortest_path(graph, "A", "C") is None


# ── Discriminating tests: fail with buggy implementation ────────────────────

def test_shorter_via_detour_distance():
    dist, _ = dijkstra(G_DETOUR, "A")
    assert dist["B"] == 2          # buggy returns 10


def test_shorter_via_detour_path():
    path = shortest_path(G_DETOUR, "A", "B")
    assert path == ["A", "C", "B"] # buggy returns ["A", "B"]


def test_long_chain_shortcut_distance():
    dist, _ = dijkstra(G_LONG_CHAIN, "A")
    assert dist["B"] == 3          # buggy returns 100


def test_long_chain_shortcut_path():
    path = shortest_path(G_LONG_CHAIN, "A", "B")
    assert path == ["A", "C", "D", "B"]  # buggy returns ["A", "B"]


def test_diamond_all_distances():
    dist, _ = dijkstra(G_DIAMOND, "A")
    assert dist == {"A": 0, "B": 1, "C": 4, "D": 5}  # buggy: D → 6


def test_diamond_shortest_path():
    path = shortest_path(G_DIAMOND, "A", "D")
    assert path == ["A", "C", "D"]  # buggy returns ["A", "B", "D"]
