import pytest
from hashmap import HashMap

# In a capacity-8 map, keys 0, 8, 16, 24 … all hash to slot 0.
# Tests below use this to engineer deliberate collisions.


# ── Tests that pass even with the buggy implementation ──────────────────────

def test_basic_put_get():
    m = HashMap()
    m.put(1, 10)
    assert m.get(1) == 10


def test_get_missing_raises():
    m = HashMap()
    with pytest.raises(KeyError):
        m.get(99)


def test_len_tracks_insertions_and_deletions():
    m = HashMap()
    assert len(m) == 0
    m.put(1, 10)
    m.put(2, 20)
    assert len(m) == 2
    m.delete(1)
    assert len(m) == 1


def test_put_overwrites_existing_key():
    m = HashMap()
    m.put(5, 50)
    m.put(5, 99)
    assert m.get(5) == 99
    assert len(m) == 1


def test_delete_makes_key_unreachable():
    m = HashMap()
    m.put(3, 30)
    m.delete(3)
    with pytest.raises(KeyError):
        m.get(3)


def test_multiple_non_colliding_keys():
    m = HashMap()
    for k in range(1, 6):
        m.put(k, k * 10)
    for k in range(1, 6):
        assert m.get(k) == k * 10


# ── Discriminating tests: fail with buggy delete, pass with tombstone fix ───

def test_lookup_survives_deletion_of_colliding_predecessor():
    """delete(0) must not break get(8): both hash to slot 0, so 8 sits one probe away."""
    m = HashMap()
    m.put(0, 100)
    m.put(8, 200)   # collision → lands at slot 1
    m.delete(0)     # buggy impl clears slot 0; correct impl leaves a tombstone
    assert m.get(8) == 200   # buggy impl stops at the empty slot 0 and raises KeyError


def test_delete_middle_of_chain_preserves_tail():
    """Deleting the middle entry must not strand the entry behind it."""
    m = HashMap()
    m.put(0, 1)     # slot 0
    m.put(8, 2)     # slot 1
    m.put(16, 3)    # slot 2
    m.delete(8)     # slot 1 becomes empty in buggy impl
    assert m.get(16) == 3    # buggy impl stops at slot 1 and raises KeyError


def test_delete_head_preserves_whole_chain():
    """Deleting the first entry of a chain must leave the rest reachable."""
    m = HashMap()
    m.put(0, 10)
    m.put(8, 20)
    m.put(16, 30)
    m.delete(0)
    assert m.get(8) == 20
    assert m.get(16) == 30


def test_contains_after_colliding_delete():
    """__contains__ must not false-negative on a key displaced past a deleted slot."""
    m = HashMap()
    m.put(0, 42)
    m.put(8, 43)
    m.delete(0)
    assert 8 in m            # buggy impl returns False


def test_delete_two_chain_members_tail_still_reachable():
    """Clearing two consecutive chain slots must not hide the entry beyond them."""
    m = HashMap()
    m.put(0, 1)
    m.put(8, 2)
    m.put(16, 3)
    m.delete(0)
    m.delete(8)
    assert m.get(16) == 3    # buggy impl stops at first empty slot
