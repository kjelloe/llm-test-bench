import heapq


def dijkstra(
    graph: dict[str, list[tuple[str, int]]],
    start: str,
) -> tuple[dict[str, int], dict[str, str | None]]:
    """
    Compute single-source shortest paths using Dijkstra's algorithm.

    graph:  adjacency list  {node: [(neighbour, weight), ...]}
    start:  source node

    Returns (dist, prev) where
      dist[v]  shortest distance from start to v  (start maps to 0)
      prev[v]  predecessor of v on the shortest path (start maps to None)

    Nodes unreachable from start are absent from both dicts.
    """
    dist: dict[str, int] = {start: 0}
    prev: dict[str, str | None] = {start: None}
    seen: set[str] = set()
    heap: list[tuple[int, str]] = [(0, start)]
    seen.add(start)

    while heap:
        d, u = heapq.heappop(heap)
        for v, w in graph.get(u, []):
            nd = d + w
            if v not in seen and nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
                seen.add(v)

    return dist, prev


def shortest_path(
    graph: dict[str, list[tuple[str, int]]],
    start: str,
    end: str,
) -> list[str] | None:
    """
    Return the node list of the shortest path from start to end,
    inclusive of both endpoints, or None if end is unreachable.
    """
    _, prev = dijkstra(graph, start)
    if end not in prev:
        return None
    path: list[str] = []
    node: str | None = end
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path
