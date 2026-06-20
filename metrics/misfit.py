"""Residual metrics used for optimization and diagnostics."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _nrmse(r: np.ndarray, y: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    y = y[np.isfinite(y)]
    if r.size == 0:
        return float("inf")
    rng = float(np.nanmax(y) - np.nanmin(y)) if y.size else 0.0
    rng = rng or 1.0
    return float(np.sqrt(np.mean(r**2)) / rng)


def _rmse(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    return float(np.sqrt(np.mean(r**2))) if r.size else float("inf")


def _mae(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    return float(np.mean(np.abs(r))) if r.size else float("inf")


def _huber(r: np.ndarray, delta: float) -> float:
    r = r[np.isfinite(r)]
    if r.size == 0:
        return float("inf")
    a = np.abs(r)
    q = np.where(a <= delta, 0.5 * r**2, delta * (a - 0.5 * delta))
    return float(np.mean(q))


def _loglik(r: np.ndarray, sigma: float) -> float:
    r = r[np.isfinite(r)]
    if r.size == 0:
        return float("inf")
    return float(0.5 * np.sum((r / sigma) ** 2) + r.size * np.log(sigma))


def _robust_sigma(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 1.0
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad <= 0.0:
        std = float(np.nanstd(values))
        return max(1e-9, std if np.isfinite(std) and std > 0.0 else 1.0)
    return max(1e-9, 1.4826 * mad)


def _normalize_metric_name(name: str) -> str:
    aliases = {
        "log_likelihood": "loglik",
        "neg_log_likelihood": "loglik",
    }
    return aliases.get(name, name)


def compute_all_metrics(
    residuals: Dict[str, np.ndarray],
    per_branch: Dict[str, Dict[int, np.ndarray]],
    targets_cfg: Dict[str, Any],
    observed: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    primary = _normalize_metric_name(targets_cfg["metric"]["primary"])
    w_u = targets_cfg["weights"]["upper"]
    w_l = targets_cfg["weights"]["lower"]
    sigma = _robust_sigma(np.r_[residuals["upper"], residuals["lower"]])
    delta = 1.345 * sigma

    rows = []
    per_plate = {}
    for plate in ("upper", "lower"):
        plate_residuals = residuals[plate]
        if observed is not None and plate in observed:
            observed_disp = observed[plate]["displacement"].to_numpy(dtype=float)
        else:
            observed_disp = plate_residuals[np.isfinite(plate_residuals)]
        vals = {
            "nrmse": _nrmse(plate_residuals, observed_disp),
            "rmse": _rmse(plate_residuals),
            "mae": _mae(plate_residuals),
            "huber": _huber(plate_residuals, delta),
            "loglik": _loglik(plate_residuals, sigma),
        }
        per_plate[plate] = vals
        for name, value in vals.items():
            rows.append((name, plate, value))
        for branch_id, branch_residuals in per_branch[plate].items():
            rows.append(
                ("nrmse", f"branch{branch_id}_{plate}", _nrmse(branch_residuals, branch_residuals))
            )
            rows.append(("rmse", f"branch{branch_id}_{plate}", _rmse(branch_residuals)))

    total = w_u * per_plate["upper"][primary] + w_l * per_plate["lower"][primary]
    rows.append((primary, "total", total))
    return {"primary_total": total, "rows": rows, "per_plate": per_plate}
