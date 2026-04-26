import pytest
from minheap import MinHeap


def test_push_pop_single():
    h = MinHeap()
    h.push(42)
    assert h.pop() == 42


def test_len():
    h = MinHeap()
    assert len(h) == 0
    h.push(1)
    h.push(2)
    assert len(h) == 2
    h.pop()
    assert len(h) == 1


def test_peek():
    h = MinHeap()
    for v in [5, 3, 7, 1, 4]:
        h.push(v)
    assert h.peek() == 1
    assert len(h) == 5


def test_pop_empty_raises():
    h = MinHeap()
    with pytest.raises(IndexError):
        h.pop()


def test_pop_sorted_input():
    h = MinHeap()
    for v in [1, 2, 3, 4, 5]:
        h.push(v)
    result = [h.pop() for _ in range(5)]
    assert result == [1, 2, 3, 4, 5]


def test_pop_order_right_child_smaller():
    h = MinHeap()
    for v in [2, 4, 1, 6, 5, 3]:
        h.push(v)
    assert h.pop() == 1
    assert h.pop() == 2


def test_pop_order_arbitrary():
    h = MinHeap()
    for v in [1, 7, 3, 9, 8, 5, 4]:
        h.push(v)
    result = [h.pop() for _ in range(7)]
    assert result == [1, 3, 4, 5, 7, 8, 9]
