"""Thread-safe initialization for expensive process-local resources."""

from threading import Lock


class LazyResource:
    def __init__(self, factory):
        self._factory = factory
        self._instance = None
        self._lock = Lock()

    def get(self):
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._factory()
        return self._instance

    def __getattr__(self, name):
        return getattr(self.get(), name)
