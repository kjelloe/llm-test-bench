import pytest
from merge_intervals import merge_intervals


def test_empty():
    assert merge_intervals([]) == []


def test_single():
    assert merge_intervals([[2, 5]]) == [[2, 5]]


def test_no_overlap():
    assert merge_intervals([[1, 2], [4, 6]]) == [[1, 2], [4, 6]]


def test_basic_overlap():
    assert merge_intervals([[1, 3], [2, 5]]) == [[1, 5]]


def test_contained_interval():
    # [2,5] is entirely inside [1,10] — the result must stay [[1,10]], not shrink to [[1,5]]
    assert merge_intervals([[1, 10], [2, 5]]) == [[1, 10]]


def test_three_way_chain():
    assert merge_intervals([[1, 4], [3, 7], [6, 10]]) == [[1, 10]]


def test_containment_then_extend():
    # [3,6] contained in [1,10]; [8,15] overlaps [1,10] — all three merge
    assert merge_intervals([[1, 10], [3, 6], [8, 15]]) == [[1, 15]]


def test_complex_mix():
    # [0,5] merges with [1,3] (contained) and [4,8] (overlap); [6,7] contained in result
    assert merge_intervals([[0, 5], [1, 3], [4, 8], [6, 7]]) == [[0, 8]]


def test_unsorted_input():
    assert merge_intervals([[3, 5], [1, 2], [2, 4]]) == [[1, 5]]


def test_non_adjacent_not_merged():
    assert merge_intervals([[1, 2], [3, 5]]) == [[1, 2], [3, 5]]
