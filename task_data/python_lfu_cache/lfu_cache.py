from collections import defaultdict, OrderedDict


class LFUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, list] = {}                        # key -> [value, freq]
        self.freq_map: dict[int, OrderedDict] = defaultdict(OrderedDict)  # freq -> {key: None}
        self.min_freq: int = 0

    def _promote(self, key: int) -> None:
        value, freq = self.cache[key]
        del self.freq_map[freq][key]
        # BUG: when freq_map[freq] becomes empty and freq == self.min_freq,
        # self.min_freq must be incremented — but this update is missing.
        new_freq = freq + 1
        self.freq_map[new_freq][key] = None
        self.cache[key] = [value, new_freq]

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self._promote(key)
        return self.cache[key][0]

    def put(self, key: int, value: int) -> None:
        if self.capacity <= 0:
            return
        if key in self.cache:
            self.cache[key][0] = value
            self._promote(key)
            return
        if len(self.cache) >= self.capacity:
            evict_key, _ = self.freq_map[self.min_freq].popitem(last=False)
            del self.cache[evict_key]
        self.freq_map[1][key] = None
        self.cache[key] = [value, 1]
        self.min_freq = 1
