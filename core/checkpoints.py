"""Pickle-based checkpoint at every iteration."""
from __future__ import annotations
import pickle
from pathlib import Path
from typing import Any


def save(state: Any, path: str | Path) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(p)  # atomic on POSIX & Windows


def load(path: str | Path) -> Any:
    with open(path, "rb") as f:
        return pickle.load(f)