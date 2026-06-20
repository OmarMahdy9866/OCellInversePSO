"""
O-Cell result extractor for PLAXIS 3D 24.3.

Mirrors the pattern from postProcessOsterberg.py:
  - load reconstructed from SumMstage * maxLoad  (loading)
  - load reconstructed from (1 - SumMstage) * maxLoad  (unloading)
  - displacement extracted via getcurveresults(node, step, Uz)

Returns:
    {"upper": pd.DataFrame[load, displacement, branch_id, branch_kind],
     "lower": pd.DataFrame[load, displacement, branch_id, branch_kind]}
"""
from __future__ import annotations
from typing import Dict, List, Any
import pandas as pd

from .node_resolver import NodeResolver


def _kind_from_phase_name(name: str) -> str:
    n = name.lower()
    if "unload" in n: return "unloading"
    if "reload" in n: return "reloading"
    return "loading"


def _load_from_step(step, kind: str, max_load: float) -> float:
    """Reconstruct applied load at this step from SumMstage."""
    s = float(step.Reached.SumMstage.value)
    if kind == "unloading":
        return (1.0 - s) * max_load
    # loading & reloading
    return s * max_load


def extract_ocell_results(plx,
                          phase_names: List[str],
                          ocell_cfg: Dict[str, Any]
                          ) -> Dict[str, pd.DataFrame]:
    """
    Args:
        plx          : PlaxisConnector (uses plx.g_o)
        phase_names  : ordered phase names mirroring the field loading sequence
                       (excluding "InitialPhase" — only the calculation phases)
        ocell_cfg    : project.yaml -> ocell section, must contain:
                       maxLoad, upper_node, lower_node (NodeResolver specs)

    Returns:
        {"upper": DataFrame, "lower": DataFrame}, both with columns:
            load, displacement, branch_id, branch_kind, plaxis_step
    """
    g_o = plx.g_o
    resolver = NodeResolver(g_o)
    node_upper = resolver.resolve(ocell_cfg["upper_node"])
    node_lower = resolver.resolve(ocell_cfg["lower_node"])
    max_load = float(ocell_cfg["maxLoad"])
    result_type = g_o.ResultTypes.Soil.Uz

    out = {}
    for plate, node in (("upper", node_upper), ("lower", node_lower)):
        rows = [dict(load=0.0, displacement=0.0,
                     branch_id=0, branch_kind="initial", plaxis_step=-1)]
        for phase_idx, ph_name in enumerate(phase_names, start=1):
            phase = _find_phase(g_o, ph_name)
            kind = _kind_from_phase_name(ph_name)
            for step_idx, step in enumerate(phase.Steps.value):
                try:
                    load = _load_from_step(step, kind, max_load)
                    disp = float(g_o.getcurveresults(node, step, result_type))
                except Exception as e:
                    # silently skip failed step queries; orchestrator will see
                    # an incomplete branch and apply partial-failure logic
                    continue
                rows.append(dict(load=load, displacement=disp,
                                 branch_id=phase_idx, branch_kind=kind,
                                 plaxis_step=step_idx))
        df = pd.DataFrame(rows)
        out[plate] = df
    return out


def _find_phase(g_o, name: str):
    for ph in g_o.Phases[:]:
        try:
            if str(ph.Name) == name:
                return ph
        except Exception:
            continue
    raise KeyError(f"Phase {name!r} not found in PLAXIS Output.")