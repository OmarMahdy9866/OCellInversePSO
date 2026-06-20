"""Resolve PLAXIS Output nodes by index / coordinates / name."""
from __future__ import annotations
from typing import Dict, Any
import math


class NodeResolver:
    """
    Spec examples:
        {by: "index", value: 1}
        {by: "coord", value: [x, y, z], tol: 0.01}
        {by: "name",  value: "TopPlate"}
    """
    def __init__(self, g_o):
        self.g_o = g_o
        self._nodes_cache = None

    def _nodes(self):
        if self._nodes_cache is None:
            self._nodes_cache = list(self.g_o.Nodes[:])
        return self._nodes_cache

    def resolve(self, spec: Dict[str, Any]):
        kind = spec["by"]
        if kind == "index":
            return self._nodes()[int(spec["value"])]
        if kind == "name":
            for n in self._nodes():
                if str(getattr(n, "Name", "")) == spec["value"]:
                    return n
            raise KeyError(f"Node named {spec['value']!r} not found.")
        if kind == "coord":
            target = spec["value"]
            tol = float(spec.get("tol", 1e-3))
            best, best_d = None, math.inf
            for n in self._nodes():
                d = self._dist(n, target)
                if d < best_d:
                    best, best_d = n, d
            if best is None or best_d > tol:
                raise KeyError(
                    f"No node within tol={tol} of {target}. "
                    f"Closest was {best_d:.4f} m.")
            return best
        raise ValueError(f"Unknown node spec kind: {kind!r}")

    @staticmethod
    def _dist(node, target):
        try:
            x = float(node.x); y = float(node.y); z = float(node.z)
        except Exception:
            return math.inf
        return math.sqrt((x - target[0])**2 + (y - target[1])**2
                         + (z - target[2])**2)