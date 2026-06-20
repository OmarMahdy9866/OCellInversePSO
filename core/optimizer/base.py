"""Abstract swarm optimizer. PSO/IGT-PSO inherit from here."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any
import numpy as np


class BaseSwarmOptimizer(ABC):
    def __init__(self, n_particles: int, n_dims: int,
                 bounds: np.ndarray, config: Dict[str, Any],
                 rng: Optional[np.random.Generator] = None):
        self.n_particles = n_particles
        self.n_dims = n_dims
        self.bounds = np.asarray(bounds, dtype=float)  # (n_dims, 2)
        self.config = config
        self.rng = rng if rng is not None else np.random.default_rng()

        self.positions: Optional[np.ndarray] = None
        self.velocities: Optional[np.ndarray] = None
        self.pbest_pos: Optional[np.ndarray] = None
        self.pbest_fit: Optional[np.ndarray] = None
        self.gbest_pos: Optional[np.ndarray] = None
        self.gbest_fit: float = np.inf
        self.iter_count: int = 0
        self.history: list = []

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def update(self, fitness_values: np.ndarray) -> None: ...

    def step(self, fitness_fn: Callable[[np.ndarray], float]):
        if self.positions is None:
            self.initialize()
        fits = np.array([fitness_fn(p) for p in self.positions], dtype=float)
        self.update(fits)
        self.iter_count += 1
        return self.gbest_pos, self.gbest_fit, fits

    def state(self) -> Dict[str, Any]:
        return dict(positions=self.positions, velocities=self.velocities,
                    pbest_pos=self.pbest_pos, pbest_fit=self.pbest_fit,
                    gbest_pos=self.gbest_pos, gbest_fit=self.gbest_fit,
                    iter_count=self.iter_count, history=self.history)

    def load_state(self, s: Dict[str, Any]) -> None:
        for k, v in s.items():
            setattr(self, k, v)