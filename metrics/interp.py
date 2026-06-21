"""Field loading, branch detection, and branch-wise interpolation."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import Akima1DInterpolator, PchipInterpolator
from scipy.signal import savgol_filter


def load_field_data(targets_cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Load the two field curves from CSV using the configured column names."""
    fd = targets_cfg["field_data"]
    load_col = fd["columns"]["load"]
    disp_col = fd["columns"]["displacement"]
    out = {}
    for plate, csv_path in fd["csv_files"].items():
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Field CSV for {plate!r} not found: {path}")
        df = pd.read_csv(path)
        missing = [c for c in (load_col, disp_col) if c not in df.columns]
        if missing:
            raise KeyError(
                f"Field CSV {path} is missing required columns: {', '.join(missing)}"
            )
        df = df[[load_col, disp_col]].rename(
            columns={load_col: "load", disp_col: "displacement"}
        )
        df = df.dropna(subset=["load", "displacement"]).reset_index(drop=True)
        if df.empty:
            raise ValueError(f"Field CSV {path} has no valid load/displacement rows.")
        out[plate] = df
    return out


def _auto_window(n: int) -> int:
    w = max(5, n // 50)
    if w % 2 == 0:
        w += 1
    return w


def segment_branches(df: pd.DataFrame, targets_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return branches as dictionaries with kind and index bounds."""
    cfg = targets_cfg["branch_detection"]
    load = df["load"].to_numpy(dtype=float)
    n = len(load)

    sm = cfg["smoothing"]
    if sm["method"] == "savgol" and n >= 5:
        w = _auto_window(n) if sm["window"] == "auto" else int(sm["window"])
        w = min(w, n if n % 2 == 1 else n - 1)
        load_smooth = savgol_filter(load, window_length=w, polyorder=sm["polyorder"])
    else:
        load_smooth = load.copy()

    d_load = np.diff(load_smooth)
    sign = np.sign(d_load)
    candidates = np.where(np.diff(sign) != 0)[0] + 1

    persistence = cfg["thresholds"]["persistence_window"]
    candidates = [
        i
        for i in candidates
        if i + persistence < n and np.all(sign[i : i + persistence] == sign[i])
    ]

    load_max = float(np.max(np.abs(load_smooth)) + 1e-12)
    min_amp = cfg["thresholds"]["min_amplitude_pct"] / 100.0 * load_max
    bounds = [0] + list(candidates) + [n - 1]
    branches = []
    for start, end in zip(bounds[:-1], bounds[1:]):
        if end - start + 1 < cfg["thresholds"]["min_branch_points"]:
            continue
        segment = load_smooth[start : end + 1]
        segment_range = float(np.ptp(segment))
        if segment_range < min_amp:
            continue
        kind = "loading" if segment[-1] >= segment[0] else "unloading"
        if kind == "loading" and any(b["kind"] == "unloading" for b in branches):
            if branches and branches[-1]["kind"] == "unloading":
                kind = "reloading"
        confidence = float(min(1.0, segment_range / (5 * min_amp + 1e-9)))
        branches.append(
            {
                "kind": kind,
                "idx_start": start,
                "idx_end": end,
                "P_range": (float(segment.min()), float(segment.max())),
                "confidence": confidence,
            }
        )
    return branches


def _interp(method: str, x: np.ndarray, y: np.ndarray):
    if method == "pchip":
        return PchipInterpolator(x, y, extrapolate=False)
    if method == "akima":
        return Akima1DInterpolator(x, y)
    return lambda v: np.interp(v, x, y, left=np.nan, right=np.nan)


def resample_with_cycles(
    predicted_df: pd.DataFrame,
    field_df: pd.DataFrame,
    field_branches: List[Dict[str, Any]],
    targets_cfg: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[int, np.ndarray], Dict[str, Any]]:
    """Resample each predicted branch onto the matching field load grid."""
    method = targets_cfg["interpolation"]["method"]
    cov_thr = targets_cfg["failure"]["coverage_threshold"]
    residuals = np.full(len(field_df), np.nan)
    per_branch: Dict[int, np.ndarray] = {}
    diag: Dict[str, Any] = {"coverage": [], "branch_kinds": []}

    n_branches = len(field_branches)
    predicted_branches = sorted(
        int(branch_id)
        for branch_id in predicted_df["branch_id"].unique()
        if int(branch_id) > 0
    )
    if len(predicted_branches) != n_branches:
        diag["error"] = (
            f"PLAXIS branches {len(predicted_branches)} != field branches {n_branches}"
        )
        return residuals, per_branch, diag

    for branch_id, field_branch in enumerate(field_branches, start=1):
        field_slice = field_df.iloc[
            field_branch["idx_start"] : field_branch["idx_end"] + 1
        ]
        field_load = field_slice["load"].to_numpy()
        field_disp = field_slice["displacement"].to_numpy()
        predicted_branch = predicted_df[predicted_df["branch_id"] == branch_id]
        predicted_load = predicted_branch["load"].to_numpy()
        predicted_disp = predicted_branch["displacement"].to_numpy()
        if len(predicted_load) < 2:
            branch_residuals = np.full(len(field_slice), np.nan)
            residuals[field_branch["idx_start"] : field_branch["idx_end"] + 1] = (
                branch_residuals
            )
            per_branch[branch_id] = branch_residuals
            diag["coverage"].append(0.0)
            diag["branch_kinds"].append(field_branch["kind"])
            diag.setdefault("warnings", []).append(
                f"branch {branch_id} has fewer than two PLAXIS points"
            )
            continue

        order = np.argsort(predicted_load)
        predicted_load = predicted_load[order]
        predicted_disp = predicted_disp[order]
        if len(predicted_load) < 4:
            interpolant = lambda v: np.interp(
                v, predicted_load, predicted_disp, left=np.nan, right=np.nan
            )
        else:
            interpolant = _interp(method, predicted_load, predicted_disp)

        predicted_at_field = interpolant(field_load)
        valid = np.isfinite(predicted_at_field)
        coverage = float(valid.mean()) if len(valid) else 0.0
        diag["coverage"].append(coverage)
        diag["branch_kinds"].append(field_branch["kind"])

        branch_residuals = predicted_at_field - field_disp
        residuals[field_branch["idx_start"] : field_branch["idx_end"] + 1] = (
            branch_residuals
        )
        per_branch[branch_id] = branch_residuals
        if coverage < cov_thr:
            diag.setdefault("warnings", []).append(
                f"branch {branch_id} coverage {coverage:.0%} below {cov_thr:.0%}"
            )
    return residuals, per_branch, diag
