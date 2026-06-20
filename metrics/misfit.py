"""All metrics: NRMSE, RMSE, MAE, Huber, log-likelihood. Always store all."""
from __future__ import annotations
from typing import Dict, Any
import numpy as np


def _nrmse(r, y):
    r = r[np.isfinite(r)]
    if r.size == 0: return float("inf")
    rng = float(np.nanmax(y) - np.nanmin(y)) or 1.0
    return float(np.sqrt(np.mean(r**2)) / rng)


def _rmse(r):
    r = r[np.isfinite(r)]
    return float(np.sqrt(np.mean(r**2))) if r.size else float("inf")


def _mae(r):
    r = r[np.isfinite(r)]
    return float(np.mean(np.abs(r))) if r.size else float("inf")


def _huber(r, delta):
    r = r[np.isfinite(r)]
    if r.size == 0: return float("inf")
    a = np.abs(r)
    q = np.where(a <= delta, 0.5*r**2, delta*(a - 0.5*delta))
    return float(np.mean(q))


def _loglik(r, sigma):
    r = r[np.isfinite(r)]
    if r.size == 0: return float("inf")
    return float(0.5*np.sum((r/sigma)**2) + r.size*np.log(sigma))   # neg ll


def compute_all_metrics(residuals: Dict[str, np.ndarray],
                        per_branch: Dict[str, Dict[int, np.ndarray]],
                        targets_cfg: Dict[str, Any]) -> Dict[str, Any]:
    primary = targets_cfg["metric"]["primary"]
    w_u = targets_cfg["weights"]["upper"]
    w_l = targets_cfg["weights"]["lower"]
    # robust sigma from data spread
    sigma = max(1e-9, float(np.nanstd(np.r_[residuals["upper"],
                                            residuals["lower"]])))
    delta = 1.345 * sigma

    rows = []
    per_plate = {}
    for plate in ("upper", "lower"):
        r = residuals[plate]
        # field y for nrmse normalisation (use displacement range proxy = r+pred)
        y_for_nrmse = r[np.isfinite(r)]    # approximation; OK for relative scale
        vals = dict(
            nrmse=_nrmse(r, y_for_nrmse),
            rmse=_rmse(r),
            mae=_mae(r),
            huber=_huber(r, delta),
            loglik=_loglik(r, sigma),
        )
        per_plate[plate] = vals
        for name, v in vals.items():
            rows.append((name, plate, v))
        # per branch
        for bid, rb in per_branch[plate].items():
            rows.append(("nrmse", f"branch{bid}_{plate}", _nrmse(rb, rb)))
            rows.append(("rmse",  f"branch{bid}_{plate}", _rmse(rb)))

    # total weighted primary
    total = w_u*per_plate["upper"][primary] + w_l*per_plate["lower"][primary]
    rows.append((primary, "total", total))
    return dict(primary_total=total, rows=rows, per_plate=per_plate)