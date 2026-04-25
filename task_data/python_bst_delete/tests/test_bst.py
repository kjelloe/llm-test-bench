import pytest
from bst import BST


# --- passing tests (leaf / single-child deletion, search, inorder) ---

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
    bst.delete(3)   # 3 has only a left child (2)
    assert not bst.search(3)
    assert bst.search(2)
    assert bst.inorder() == [2, 5, 7]


def test_delete_node_with_right_child_only():
    bst = BST()
    for v in [5, 3, 7, 4]:
        bst.insert(v)
    bst.delete(3)   # 3 has only a right child (4)
    assert not bst.search(3)
    assert bst.search(4)
    assert bst.inorder() == [4, 5, 7]


def test_delete_two_children_successor_is_deep():
    """In-order successor is NOT the immediate right child — bug does not fire here."""
    bst = BST()
    for v in [5, 3, 7, 2, 4, 6, 8]:
        bst.insert(v)
    # Deleting 5: right child is 7 but min(right subtree) is 6 (7->left=6).
    # _delete(7_node, 6) modifies 7_node.left in-place before returning,
    # so the missing assignment is harmless for this shape.
    bst.delete(5)
    assert not bst.search(5)
    assert bst.inorder() == [2, 3, 4, 6, 7, 8]


# --- failing tests (successor IS the immediate right child) ---

def test_delete_two_children_successor_is_right_child():
    """In-order successor is the right child itself (right child has no left subtree).
    Bug: _delete returns the pruned subtree but the result is discarded,
    so the successor node remains as a duplicate after its value is copied up.

    Before: 10 -> left=5(left=3, right=7), right=15
    Delete 5: successor=7 (right child of 5, no left child).
    Correct inorder after: [3, 7, 10, 15]
    Buggy inorder after:   [3, 7, 7, 10, 15]  (7 appears twice)
    """
    bst = BST()
    for v in [10, 5, 15, 3, 7]:
        bst.insert(v)
    bst.delete(5)
    assert not bst.search(5)
    assert bst.inorder() == [3, 7, 10, 15]


def test_delete_root_successor_is_right_child():
    """Delete root when the right child is its own in-order successor.

    Tree: root=5, left=3, right=8  (8 has no left child)
    Delete 5: successor=8.
    Correct inorder: [3, 8]
    Buggy inorder:   [3, 8, 8]
    """
    bst = BST()
    for v in [5, 3, 8]:
        bst.insert(v)
    bst.delete(5)
    assert not bst.search(5)
    assert bst.search(8)
    assert bst.search(3)
    assert bst.inorder() == [3, 8]
