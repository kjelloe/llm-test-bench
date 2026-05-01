_EMPTY = None


class HashMap:
    """Open-addressing hash map with linear probing."""

    _CAPACITY = 8

    def __init__(self) -> None:
        self._slots: list = [_EMPTY] * self._CAPACITY
        self._size: int = 0

    def _hash(self, key: int) -> int:
        return key % self._CAPACITY

    def put(self, key: int, val: int) -> None:
        i = self._hash(key)
        while self._slots[i] is not _EMPTY:
            if self._slots[i][0] == key:
                self._slots[i] = (key, val)
                return
            i = (i + 1) % self._CAPACITY
        self._slots[i] = (key, val)
        self._size += 1

    def get(self, key: int) -> int:
        i = self._hash(key)
        while self._slots[i] is not _EMPTY:
            if self._slots[i][0] == key:
                return self._slots[i][1]
            i = (i + 1) % self._CAPACITY
        raise KeyError(key)

    def delete(self, key: int) -> None:
        i = self._hash(key)
        while self._slots[i] is not _EMPTY:
            if self._slots[i][0] == key:
                self._slots[i] = _EMPTY
                self._size -= 1
                return
            i = (i + 1) % self._CAPACITY
        raise KeyError(key)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: int) -> bool:
        try:
            self.get(key)
            return True
        except KeyError:
            return False
