class MinHeap:
    def __init__(self):
        self._data: list[int] = []

    def push(self, val: int) -> None:
        self._data.append(val)
        self._sift_up(len(self._data) - 1)

    def pop(self) -> int:
        if not self._data:
            raise IndexError("pop from empty heap")
        self._swap(0, len(self._data) - 1)
        val = self._data.pop()
        self._sift_down(0)
        return val

    def peek(self) -> int:
        if not self._data:
            raise IndexError("peek at empty heap")
        return self._data[0]

    def __len__(self) -> int:
        return len(self._data)

    def _sift_up(self, i: int) -> None:
        while i > 0:
            parent = (i - 1) // 2
            if self._data[i] < self._data[parent]:
                self._swap(i, parent)
                i = parent
            else:
                break

    def _sift_down(self, i: int) -> None:
        n = len(self._data)
        while True:
            left = 2 * i + 1
            right = 2 * i + 2
            smallest = i
            if left < n and self._data[left] < self._data[smallest]:
                smallest = left
            if smallest == i:
                break
            self._swap(i, smallest)
            i = smallest

    def _swap(self, i: int, j: int) -> None:
        self._data[i], self._data[j] = self._data[j], self._data[i]
