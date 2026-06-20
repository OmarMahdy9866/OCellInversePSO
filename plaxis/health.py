# plaxis/health.py
"""Phase-level convergence diagnostics."""
from __future__ import annotations


def phase_converged(phase) -> bool:
    try:
        return bool(phase.Reached.SumMstage and float(phase.Reached.SumMstage) > 0.999)
    except Exception:
        return False