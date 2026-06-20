"""Publication-quality per-run diagnostic plot."""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OKABE_ITO = ["#0072B2", "#D55E00", "#009E73", "#CC79A7",
             "#F0E442", "#56B4E9", "#E69F00", "#000000"]


def save_diagnostic_plot(out_path: str | Path,
                         predicted: Dict[str, "pd.DataFrame"],
                         field: Dict[str, "pd.DataFrame"],
                         field_branches: Dict[str, list],
                         per_branch: Dict[str, Dict[int, np.ndarray]],
                         diag: Dict[str, Dict[str, Any]],
                         run_label: str, fitness: float) -> None:
    fig = plt.figure(figsize=(12, 8), dpi=200)
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 1])
    fig.suptitle(f"Run {run_label}    |    fitness = {fitness:.4g}",
                 fontsize=12, weight="bold")

    for col, plate in enumerate(("upper", "lower")):
        ax = fig.add_subplot(gs[0, col])
        f = field[plate]; p = predicted[plate]
        # field by branch
        for k, fb in enumerate(field_branches[plate], start=1):
            seg = f.iloc[fb["idx_start"]:fb["idx_end"]+1]
            c = OKABE_ITO[(k-1) % len(OKABE_ITO)]
            ax.plot(seg["displacement"], seg["load"], "o",
                    ms=3, color=c, label=f"field br{k} ({fb['kind']})")
        # PLAXIS raw + interp
        for k in sorted(p["branch_id"].unique()):
            sub = p[p["branch_id"] == k].sort_values("load")
            c = OKABE_ITO[(k-1) % len(OKABE_ITO)]
            ax.plot(sub["displacement"], sub["load"], "-",
                    color=c, alpha=0.6, lw=1.2)
            ax.plot(sub["displacement"], sub["load"], "s",
                    ms=3, color=c, mfc="none")
        ax.set_xlabel(f"{plate.title()} displacement")
        ax.set_ylabel("Load")
        ax.set_title(f"{plate.title()} plate")
        ax.grid(True, alpha=0.3)
        if col == 0:
            ax.legend(fontsize=7, ncol=2, loc="best")

    # bottom: per-branch residual bars + coverage
    ax_r = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])
    for plate, marker in (("upper", "//"), ("lower", "\\\\")):
        ids = sorted(per_branch[plate].keys())
        rms = [float(np.sqrt(np.nanmean(per_branch[plate][i]**2))) for i in ids]
        ax_r.bar([i + (0.2 if plate == "lower" else -0.2) for i in ids],
                 rms, width=0.4, label=plate, hatch=marker, alpha=0.8)
        cov = diag[plate].get("coverage", [])
        ax_c.bar([i + (0.2 if plate == "lower" else -0.2) for i in range(1, len(cov)+1)],
                 cov, width=0.4, label=plate, hatch=marker, alpha=0.8)
    ax_r.set_xlabel("Branch"); ax_r.set_ylabel("RMSE per branch")
    ax_r.set_title("Branch-wise residual"); ax_r.legend(fontsize=8); ax_r.grid(True, alpha=0.3)
    ax_c.set_xlabel("Branch"); ax_c.set_ylabel("Coverage")
    ax_c.set_title("Branch coverage"); ax_c.set_ylim(0, 1.05)
    ax_c.legend(fontsize=8); ax_c.grid(True, alpha=0.3)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)