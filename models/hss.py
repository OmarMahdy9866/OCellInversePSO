"""Hardening Soil Small-Strain model — PLAXIS HSsmall material writer."""
from __future__ import annotations
from typing import Dict, List
from .base import MaterialModel


HSS_PLAXIS_KEYS = {
    "E50_ref":  "E50ref",
    "Eoed_ref": "EoedRef",
    "Eur_ref":  "Eurref",
    "G0_ref":   "G0ref",
    "m":        "powerm",
    "phi":      "phi",
    "c_ref":    "cref",
    "psi":      "psi",
    "nu_ur":    "nu",
    "Rf":       "Rf",
    "pref":     "pref",
    "gamma_07": "gamma07",
}


class HSS(MaterialModel):
    name = "HSS"
    FREE_DEFAULT = ["E50_ref", "Eoed_ref", "Eur_ref", "G0_ref",
                    "m", "phi", "c_ref", "gamma_07"]
    ALL_PARAMS = list(HSS_PLAXIS_KEYS.keys())

    def param_names(self) -> List[str]:
        return list(self.ALL_PARAMS)

    def physical_constraints(self, p: Dict[str, float]) -> List[str]:
        v = []
        if "Eur_ref" in p and "E50_ref" in p and p["Eur_ref"] < 3.0 * p["E50_ref"]:
            v.append(f"Eur_ref ({p['Eur_ref']:.0f}) < 3*E50_ref ({3*p['E50_ref']:.0f})")
        if "Eur_ref" in p and "Eoed_ref" in p and p["Eur_ref"] < p["Eoed_ref"]:
            v.append(f"Eur_ref < Eoed_ref")
        if all(k in p for k in ("G0_ref", "Eur_ref", "nu_ur")):
            g_min = p["Eur_ref"] / (2.0 * (1.0 + p["nu_ur"]))
            if p["G0_ref"] < g_min:
                v.append(f"G0_ref < Eur_ref/(2(1+nu_ur)) = {g_min:.0f}")
        if "phi" in p and p["phi"] <= 0:
            v.append("phi <= 0")
        if "c_ref" in p and p["c_ref"] < 0:
            v.append("c_ref < 0")
        if "gamma_07" in p and not (1e-5 <= p["gamma_07"] <= 1e-2):
            v.append("gamma_07 outside [1e-5,1e-2]")
        return v

    def write_to_plaxis(self, plx_material, params: Dict[str, float]) -> None:
        """Push parameters to a PLAXIS material object via Remote Scripting."""
        for our_key, value in params.items():
            plx_key = HSS_PLAXIS_KEYS.get(our_key)
            if plx_key is None:
                continue
            try:
                plx_material.setproperties(plx_key, float(value))
            except Exception as e:                  # pragma: no cover
                raise RuntimeError(f"PLAXIS rejected {our_key}={value}: {e}") from e