from collections import OrderedDict


class L1Cache:
    def __init__(self, max_size: int = 256) -> None:
        self.max_size = max_size
        self._items: OrderedDict[str, str] = OrderedDict()

    def get(self, key: str) -> str | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def set(self, key: str, value: str) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        if len(self._items) > self.max_size:
            self._items.popitem(last=False)


l1_cache = L1Cache()
