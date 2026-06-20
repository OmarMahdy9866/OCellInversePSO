# plaxis/runner.py
"""Phase-by-phase staged-construction runner with timeout + early stop."""
from __future__ import annotations
import time
from pathlib import Path
from typing import List, Dict
from .health import phase_converged


def run_staged_phases(plx, phase_names: List[str], timeout_min: int,
                      log_path: Path) -> Dict:
    g = plx.g_i
    log_path.parent.mkdir(parents=True, exist_ok=True)
    info = dict(partial=False, last_phase=None, phases_run=[],
                walltime_s=0.0, errors=[])
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as lf:
        for ph_name in phase_names:
            if time.time() - t0 > timeout_min * 60:
                info["partial"] = True
                info["errors"].append(f"Timeout before {ph_name}")
                lf.write(f"[TIMEOUT] before {ph_name}\n")
                break
            try:
                # find or skip InitialPhase (always pre-run)
                phase = _phase_by_name(g, ph_name)
                if ph_name.lower() != "initialphase":
                    g.calculate(phase)
                if not phase_converged(phase) and ph_name.lower() != "initialphase":
                    info["partial"] = True
                    info["errors"].append(f"Non-convergence: {ph_name}")
                    lf.write(f"[NON-CONVERGED] {ph_name}\n")
                    break
                info["last_phase"] = ph_name
                info["phases_run"].append(ph_name)
                lf.write(f"[OK] {ph_name}\n")
            except Exception as e:
                info["partial"] = True
                info["errors"].append(f"{ph_name}: {e}")
                lf.write(f"[ERROR] {ph_name}: {e}\n")
                break
    info["walltime_s"] = time.time() - t0
    return info


def _phase_by_name(g_i, name):
    for ph in g_i.Phases[:]:
        if str(ph.Name) == name:
            return ph
    raise KeyError(f"Phase {name!r} not found.")