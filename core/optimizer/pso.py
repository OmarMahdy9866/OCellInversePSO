"""Vanilla PSO with LHS init + reflect-and-project bound handling."""
from __future__ import annotations
import numpy as np
from .base import BaseSwarmOptimizer


def latin_hypercube(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(size=(n, d))
    a = cut[:n][:, None] + u * (1.0 / n)
    for j in range(d):
        rng.shuffle(a[:, j])
    return a


class PSO(BaseSwarmOptimizer):
    def initialize(self) -> None:
        lo, hi = self.bounds[:, 0], self.bounds[:, 1]
        init_kind = self.config.get('swarm', {}).get('init', 'lhs')
        unit = (latin_hypercube(self.n_particles, self.n_dims, self.rng)
                if init_kind == 'lhs'
                else self.rng.uniform(size=(self.n_particles, self.n_dims)))
        self.positions = lo + unit * (hi - lo)
        self.v_max = self.config['dynamics']['v_max_frac'] * (hi - lo)
        self.velocities = self.rng.uniform(-1, 1, size=self.positions.shape) * self.v_max
        self.pbest_pos = self.positions.copy()
        self.pbest_fit = np.full(self.n_particles, np.inf)

    def _inertia(self) -> float:
        d = self.config['dynamics']['inertia']
        max_iter = max(1, self.config['iterations']['max'] - 1)
        frac = min(self.iter_count / max_iter, 1.0)
        return d['w_start'] + (d['w_end'] - d['w_start']) * frac

    def _reflect_project(self, pos: np.ndarray, vel: np.ndarray):
        lo, hi = self.bounds[:, 0], self.bounds[:, 1]
        for _ in range(4):
            below = pos < lo
            above = pos > hi
            if not (below.any() or above.any()):
                break
            pos = np.where(below, 2 * lo - pos, pos)
            pos = np.where(above, 2 * hi - pos, pos)
            vel = np.where(below | above, -0.5 * vel, vel)
        return np.clip(pos, lo, hi), vel

    def update(self, fitness_values: np.ndarray) -> None:
        improved = fitness_values < self.pbest_fit
        self.pbest_pos[improved] = self.positions[improved]
        self.pbest_fit[improved] = fitness_values[improved]
        best_i = int(np.argmin(self.pbest_fit))
        if self.pbest_fit[best_i] < self.gbest_fit:
            self.gbest_fit = float(self.pbest_fit[best_i])
            self.gbest_pos = self.pbest_pos[best_i].copy()

        self.history.append(dict(
            iter=self.iter_count,
            gbest_fit=self.gbest_fit,
            mean_fit=float(np.nanmean(fitness_values)),
            std_fit=float(np.nanstd(fitness_values)),
            n_failed=int(np.sum(~np.isfinite(fitness_values))),
        ))

        w = self._inertia()
        c1 = self.config['dynamics']['c1']
        c2 = self.config['dynamics']['c2']
        r1 = self.rng.uniform(size=self.positions.shape)
        r2 = self.rng.uniform(size=self.positions.shape)
        cog = c1 * r1 * (self.pbest_pos - self.positions)
        soc = c2 * r2 * (self.gbest_pos - self.positions)
        self.velocities = np.clip(w * self.velocities + cog + soc,
                                  -self.v_max, self.v_max)
        new_pos = self.positions + self.velocities
        self.positions, self.velocities = self._reflect_project(new_pos, self.velocities)

    def should_stop(self) -> bool:
        es = self.config['iterations'].get('early_stop', {})
        if not es.get('enabled', False) or len(self.history) < es['patience'] + 1:
            return False
        recent = [h['gbest_fit'] for h in self.history[-(es['patience'] + 1):]]
        return (recent[0] - recent[-1]) < es['min_delta']