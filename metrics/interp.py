"""Field loader, Savitzky-Golay branch detection, PCHIP/Akima resampling."""
from __future__ import annotations
from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.interpolate import PchipInterpolator, Akima1DInterpolator


# ---------- Field loading ----------
def load_field_xlsx(targets_cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    fd = targets_cfg["field_data"]
    out = {}
    for plate, sheet in fd["sheets"].items():
        df = pd.read_excel(fd["path"], sheet_name=sheet)
        df = df.rename(columns={fd["columns"]["load"]: "load",
                                fd["columns"]["displacement"]: "displacement"})
        df = df[["load", "displacement"]].reset_index(drop=True)
        out[plate] = df
    return out


# ---------- Branch detection ----------
def _auto_window(n: int) -> int:
    w = max(5, n // 50)
    if w % 2 == 0: w += 1
    return w


def segment_branches(df: pd.DataFrame, targets_cfg: Dict[str, Any]
                     ) -> List[Dict[str, Any]]:
    """Return list of branches: [{kind, idx_start, idx_end, P_range, conf}]."""
    cfg = targets_cfg["branch_detection"]
    P = df["load"].to_numpy(dtype=float)
    n = len(P)
    # smoothing
    sm = cfg["smoothing"]
    if sm["method"] == "savgol" and n >= 5:
        w = _auto_window(n) if sm["window"] == "auto" else int(sm["window"])
        w = min(w, n if n % 2 == 1 else n - 1)
        P_s = savgol_filter(P, window_length=w, polyorder=sm["polyorder"])
    else:
        P_s = P.copy()

    dP = np.diff(P_s)
    sgn = np.sign(dP)
    # find sign-change candidates
    cands = np.where(np.diff(sgn) != 0)[0] + 1     # indices in P
    # persistence filter
    pw = cfg["thresholds"]["persistence_window"]
    cands = [i for i in cands
             if i + pw < n and
             np.all(sgn[i:i+pw] == sgn[i])]

    # amplitude filter
    P_max = float(np.max(np.abs(P_s)) + 1e-12)
    min_amp = cfg["thresholds"]["min_amplitude_pct"] / 100.0 * P_max
    # build branch boundaries
    bounds = [0] + list(cands) + [n - 1]
    branches = []
    for b0, b1 in zip(bounds[:-1], bounds[1:]):
        if b1 - b0 + 1 < cfg["thresholds"]["min_branch_points"]:
            continue
        seg = P_s[b0:b1+1]
        if seg.ptp() < min_amp:
            continue
        kind = "loading" if seg[-1] >= seg[0] else "unloading"
        # promote 2nd+ loading branches to reloading
        if kind == "loading" and any(b["kind"] == "unloading" for b in branches):
            kind = "reloading" if branches and branches[-1]["kind"] == "unloading" else "loading"
        conf = float(min(1.0, seg.ptp() / (5 * min_amp + 1e-9)))
        branches.append(dict(kind=kind, idx_start=b0, idx_end=b1,
                             P_range=(float(seg.min()), float(seg.max())),
                             confidence=conf))
    return branches


# ---------- Resampling with cycles ----------
def _interp(method, x, y):
    if method == "pchip":
        return PchipInterpolator(x, y, extrapolate=False)
    if method == "akima":
        return Akima1DInterpolator(x, y)
    return lambda v: np.interp(v, x, y, left=np.nan, right=np.nan)


def resample_with_cycles(predicted_df: pd.DataFrame,
                         field_df: pd.DataFrame,
                         field_branches: List[Dict[str, Any]],
                         targets_cfg: Dict[str, Any]
                         ) -> Tuple[np.ndarray, Dict[int, np.ndarray], Dict]:
    """For each (PLAXIS branch_id ↔ field branch idx), build PCHIP on the
    PLAXIS branch's monotone load array, evaluate at the field branch loads,
    return residuals (Δ_plx - Δ_field).
    """
    method = targets_cfg["interpolation"]["method"]
    cov_thr = targets_cfg["failure"]["coverage_threshold"]
    residuals = np.full(len(field_df), np.nan)
    per_branch: Dict[int, np.ndarray] = {}
    diag = dict(coverage=[], branch_kinds=[])

    n_branches = len(field_branches)
    plx_branches = sorted(predicted_df["branch_id"].unique())
    if len(plx_branches) != n_branches:
        diag["error"] = (f"PLAXIS branches {len(plx_branches)} != "
                         f"field branches {n_branches}")
        return residuals, per_branch, diag

    for k, fb in enumerate(field_branches, start=1):
        f_slice = field_df.iloc[fb["idx_start"]:fb["idx_end"]+1]
        Pf, Df = f_slice["load"].to_numpy(), f_slice["displacement"].to_numpy()
        plx_sub = predicted_df[predicted_df["branch_id"] == k] \
            .sort_values("load" if fb["kind"] == "loading" else "load",
                         ascending=fb["kind"] != "unloading")
        Pp, Dp = plx_sub["load"].to_numpy(), plx_sub["displacement"].to_numpy()
        # PLAXIS branch must be monotone in load for 1-D interp
        order = np.argsort(Pp)
        Pp_m, Dp_m = Pp[order], Dp[order]
        if len(Pp_m) < 4:
            # fall back to linear if too few points
            f_int = lambda v: np.interp(v, Pp_m, Dp_m,
                                        left=np.nan, right=np.nan)
        else:
            f_int = _interp(method, Pp_m, Dp_m)
        Dp_at_field = f_int(Pf)
        valid = np.isfinite(Dp_at_field)
        coverage = float(valid.mean()) if len(valid) else 0.0
        diag["coverage"].append(coverage)
        diag["branch_kinds"].append(fb["kind"])
        r = Dp_at_field - Df
        residuals[fb["idx_start"]:fb["idx_end"]+1] = r
        per_branch[k] = r
        if coverage < cov_thr:
            diag.setdefault("warnings", []).append(
                f"branch {k} coverage {coverage:.0%} below {cov_thr:.0%}")
    return residuals, per_branch, diag