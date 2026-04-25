class Node:
    def __init__(self, val: int):
        self.val = val
        self.left: "Node | None" = None
        self.right: "Node | None" = None


class BST:
    def __init__(self):
        self.root: Node | None = None

    def insert(self, val: int) -> None:
        self.root = self._insert(self.root, val)

    def _insert(self, node: Node | None, val: int) -> Node:
        if node is None:
            return Node(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        elif val > node.val:
            node.right = self._insert(node.right, val)
        return node

    def search(self, val: int) -> bool:
        return self._search(self.root, val)

    def _search(self, node: Node | None, val: int) -> bool:
        if node is None:
            return False
        if val == node.val:
            return True
        if val < node.val:
            return self._search(node.left, val)
        return self._search(node.right, val)

    def inorder(self) -> list[int]:
        result: list[int] = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node: Node | None, result: list[int]) -> None:
        if node is None:
            return
        self._inorder(node.left, result)
        result.append(node.val)
        self._inorder(node.right, result)

    def delete(self, val: int) -> None:
        self.root = self._delete(self.root, val)

    def _delete(self, node: Node | None, val: int) -> Node | None:
        if node is None:
            return None
        if val < node.val:
            node.left = self._delete(node.left, val)
        elif val > node.val:
            node.right = self._delete(node.right, val)
        else:
            # Leaf or single child — correct
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            # Two children: replace with in-order successor (min of right subtree)
            successor = node.right
            while successor.left is not None:
                successor = successor.left
            node.val = successor.val
            # BUG: return value of _delete not assigned back to node.right,
            # so the successor node is never removed from the right subtree.
            self._delete(node.right, successor.val)
        return node
