"""IGT-PSO upgrade — Gaussian perturbation of gbest + topology switching.
Phase 4 placeholder. Inherits PSO; override `update` when ready."""
from .pso import PSO


class IGTPSO(PSO):
    def update(self, fitness_values):
        # TODO[Phase 4]: Gaussian-perturbed gbest, ring/star topology switch
        super().update(fitness_values)