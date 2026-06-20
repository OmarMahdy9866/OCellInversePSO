"""Push current parameter set into PLAXIS material objects."""
from __future__ import annotations
from typing import Dict, Any
from models.base import MaterialModel


def write_layer_materials(plx, params_by_layer: Dict[str, Dict[str, float]],
                          profile: Dict[str, Any], model: MaterialModel) -> None:
    g = plx.g_i
    for layer in profile["layers"]:
        mat_id = layer["plaxis_material_id"]
        plx_mat = _find_material(g, mat_id)
        if plx_mat is None:
            raise KeyError(f"PLAXIS material '{mat_id}' not found in model.")
        model.write_to_plaxis(plx_mat, params_by_layer[layer["name"]])


def _find_material(g, name: str):
    for m in g.Materials[:]:
        try:
            if str(m.Name) == name:
                return m
        except Exception:
            continue
    return None