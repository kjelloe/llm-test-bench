"""scout_hf's trending pass: HF's trending GGUF list as a pseudo-query; leaving the list is not GONE."""
from types import SimpleNamespace

from lib import scout_hf
from lib.scout_hf import TRENDING, _carry_trending, _compute_diff, _search_repos


class FakeApi:
    def __init__(self):
        self.calls = []

    def list_models(self, **kw):
        self.calls.append(kw)
        return [SimpleNamespace(id="a/x", downloads=1)]


def test_trending_query_asks_for_trending_gguf():
    api = FakeApi()
    _search_repos(api, TRENDING, 5)
    assert api.calls == [{"sort": "trendingScore", "filter": "gguf", "limit": scout_hf._TRENDING_LIMIT}]


def _rec(*queries):
    return {"files": [{"name": "m.gguf"}], "source_queries": list(queries)}


def test_leaving_trending_is_not_gone_and_does_not_return_as_new():
    old = {"t/only": _rec(TRENDING), "q/gone": _rec("qwen3 coder"), "both/x": _rec("qwen3 coder", TRENDING)}
    new: dict = {}
    _, _, gone = _compute_diff(old, new)
    assert sorted(gone) == ["both/x", "q/gone"]
    _carry_trending(old, new)
    assert list(new) == ["t/only"]
    new_e, _, _ = _compute_diff(old, {"t/only": _rec(TRENDING)})
    assert new_e == []
