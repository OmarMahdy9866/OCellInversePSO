"""Convergence-failure penalty strategies."""
from __future__ import annotations
import numpy as np
from typing import Dict, Any


def apply_penalty(reason: str, config: Dict[str, Any],
                  worst_seen: float) -> float:
    kappa = config["soft_penalty_kappa"]
    base = worst_seen if np.isfinite(worst_seen) else 1.0
    if config["penalty_strategy"] in ("soft", "both"):
        return float(kappa * max(base, 1.0))
    return float("inf")