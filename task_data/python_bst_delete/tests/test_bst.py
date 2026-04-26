import pytest
from bst import BST


def test_insert_and_inorder():
    bst = BST()
    for v in [5, 3, 7, 1, 4]:
        bst.insert(v)
    assert bst.inorder() == [1, 3, 4, 5, 7]


def test_search_present_and_absent():
    bst = BST()
    for v in [5, 3, 7]:
        bst.insert(v)
    assert bst.search(3)
    assert not bst.search(4)


def test_delete_leaf():
    bst = BST()
    for v in [5, 3, 7]:
        bst.insert(v)
    bst.delete(3)
    assert not bst.search(3)
    assert bst.inorder() == [5, 7]


def test_delete_node_with_left_child_only():
    bst = BST()
    for v in [5, 3, 7, 2]:
        bst.insert(v)
    bst.delete(3)
    assert not bst.search(3)
    assert bst.search(2)
    assert bst.inorder() == [2, 5, 7]


def test_delete_node_with_right_child_only():
    bst = BST()
    for v in [5, 3, 7, 4]:
        bst.insert(v)
    bst.delete(3)
    assert not bst.search(3)
    assert bst.search(4)
    assert bst.inorder() == [4, 5, 7]


def test_delete_two_children_deep_successor():
    bst = BST()
    for v in [5, 3, 7, 2, 4, 6, 8]:
        bst.insert(v)
    bst.delete(5)
    assert not bst.search(5)
    assert bst.inorder() == [2, 3, 4, 6, 7, 8]


def test_delete_two_children_shallow_successor():
    bst = BST()
    for v in [10, 5, 15, 3, 7]:
        bst.insert(v)
    bst.delete(5)
    assert not bst.search(5)
    assert bst.inorder() == [3, 7, 10, 15]


def test_delete_root_two_children():
    bst = BST()
    for v in [5, 3, 8]:
        bst.insert(v)
    bst.delete(5)
    assert not bst.search(5)
    assert bst.search(8)
    assert bst.search(3)
    assert bst.inorder() == [3, 8]
