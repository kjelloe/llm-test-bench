from lru_cache import LRUCache


def test_basic_get_put():
    cache = LRUCache(2)
    cache.put(1, 10)
    cache.put(2, 20)
    assert cache.get(1) == 10
    assert cache.get(2) == 20


def test_missing_key_returns_minus_one():
    cache = LRUCache(2)
    assert cache.get(99) == -1


def test_eviction_without_access():
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)    # evicts key 1 (LRU)
    assert cache.get(1) == -1
    assert cache.get(2) == 2
    assert cache.get(3) == 3


def test_get_promotes_to_mru():
    """get() must move the accessed node to MRU so it is not the next eviction victim."""
    cache = LRUCache(2)
    cache.put(1, 10)
    cache.put(2, 20)
    cache.get(1)       # access key 1 — must become MRU
    cache.put(3, 30)   # must evict key 2 (now LRU), not key 1
    assert cache.get(1) == 10
    assert cache.get(2) == -1
    assert cache.get(3) == 30


def test_put_updates_existing_key():
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(1, 100)  # update — key 1 becomes MRU
    cache.put(3, 3)    # evicts key 2 (LRU)
    assert cache.get(1) == 100
    assert cache.get(2) == -1
    assert cache.get(3) == 3


def test_capacity_one():
    cache = LRUCache(1)
    cache.put(1, 1)
    cache.put(2, 2)    # evicts key 1
    assert cache.get(1) == -1
    assert cache.get(2) == 2


def test_sequential_access_order():
    """Accessing keys in sequence makes the earliest-accessed the next eviction victim."""
    cache = LRUCache(3)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)
    cache.get(1)       # order: 2, 3, 1  (1 → MRU)
    cache.get(2)       # order: 3, 1, 2  (2 → MRU)
    cache.put(4, 4)    # evicts key 3 (LRU)
    assert cache.get(3) == -1
    assert cache.get(1) == 1
    assert cache.get(2) == 2
    assert cache.get(4) == 4
