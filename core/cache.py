"""LRU cache keyed by quantised parameter vector."""
from __future__ import annotations
from collections import OrderedDict
import numpy as np


class ParamCache:
    def __init__(self, tolerance: float = 1e-6, max_size: int = 4096):
        self.tol = tolerance
        self.max = max_size
        self._d: "OrderedDict[bytes, float]" = OrderedDict()

    def _key(self, x: np.ndarray) -> bytes:
        return np.round(x / self.tol).astype(np.int64).tobytes()

    def get(self, x):
        k = self._key(x)
        if k in self._d:
            self._d.move_to_end(k)
            return self._d[k]
        return None

    def put(self, x, fitness):
        k = self._key(x)
        self._d[k] = fitness
        self._d.move_to_end(k)
        if len(self._d) > self.max:
            self._d.popitem(last=False)