import pytest
from lfu_cache import LFUCache


def test_basic_put_get():
    cache = LFUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1
    assert cache.get(2) == 2


def test_missing_key_returns_minus_one():
    cache = LFUCache(3)
    assert cache.get(42) == -1


def test_evict_least_frequent():
    """Key accessed more often survives; least-accessed key is evicted."""
    cache = LFUCache(2)
    cache.put(1, 10)
    cache.put(2, 20)
    cache.get(2)        # freq: key1=1, key2=2  →  min_freq=1 (key1 is LFU)
    cache.put(3, 30)    # must evict key1
    assert cache.get(1) == -1
    assert cache.get(2) == 20
    assert cache.get(3) == 30


def test_lru_tiebreak_within_same_freq():
    """When two keys share the same frequency, evict the LRU one."""
    cache = LFUCache(2)
    cache.put(1, 10)
    cache.put(2, 20)    # both freq=1; key1 was inserted first → LRU
    cache.put(3, 30)    # must evict key1
    assert cache.get(1) == -1
    assert cache.get(2) == 20
    assert cache.get(3) == 30


def test_update_existing_key():
    """put on an existing key updates value and promotes frequency."""
    cache = LFUCache(2)
    cache.put(1, 10)
    cache.put(2, 20)
    cache.get(1)        # key1 freq=2, key2 freq=1
    cache.put(1, 99)    # update; key1 freq=3, key2 still freq=1 (LFU)
    cache.put(3, 30)    # must evict key2 (LFU)
    assert cache.get(1) == 99
    assert cache.get(2) == -1
    assert cache.get(3) == 30


# --- tests that expose the min_freq tracking bug ---

def test_min_freq_updates_when_bucket_empties():
    """After the last key at min_freq is promoted, min_freq must increase.

    Sequence: put 1, put 2 (both freq=1, min_freq=1).
    get(1) → freq_map[1]={2}, freq_map[2]={1}       min_freq stays 1 (key2 still there).
    get(2) → freq_map[1]={},  freq_map[2]={1,2}     min_freq MUST become 2 (bucket 1 is empty).
    put(3) → evict from min_freq: correct=key1 (LRU among freq-2 keys), wrong=KeyError on empty bucket.
    """
    cache = LFUCache(2)
    cache.put(1, 10)
    cache.put(2, 20)
    cache.get(1)
    cache.get(2)
    cache.put(3, 30)    # crashes with KeyError if min_freq not updated
    assert cache.get(1) == -1  # key1 was LRU among freq-2 keys
    assert cache.get(2) == 20
    assert cache.get(3) == 30


def test_single_key_promote_then_replace():
    """Capacity-1: get promotes the only key; next put must evict it.

    put(1) → min_freq=1, freq_map={1:{1}}.
    get(1) → freq_map[1]={}, freq_map[2]={1}   min_freq MUST become 2.
    put(2) → evict from min_freq: correct=key1 from bucket 2, wrong=KeyError on empty bucket 1.
    """
    cache = LFUCache(1)
    cache.put(1, 10)
    cache.get(1)        # crashes on next put if min_freq not updated
    cache.put(2, 20)
    assert cache.get(1) == -1
    assert cache.get(2) == 20
