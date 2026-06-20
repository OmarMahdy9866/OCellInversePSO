"""Pluggable material model interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ParamSpec:
    name: str
    bounds: Tuple[float, float]
    scale: str          # 'log' | 'linear'
    unit: str
    fixed: bool = False
    value: float | None = None


class MaterialModel(ABC):
    name: str

    @abstractmethod
    def param_names(self) -> List[str]: ...

    @abstractmethod
    def physical_constraints(self, params: Dict[str, float]) -> List[str]:
        """Return list of violated constraint descriptions (empty if all OK)."""
    @abstractmethod
    def write_to_plaxis(self, plx_material, params: Dict[str, float]) -> None: ...