# OCellInversePSO

PSO-based inverse analysis for calibrating Hardening Soil Small-Strain
parameters against O-Cell load-test data, with PLAXIS 3D as the forward model.

## Current state

This repository is an early-stage scaffold. The core optimization, result
storage, interpolation, and PLAXIS integration layers are present, but several
features referenced in the original project plan are still stubs or have not
been committed yet.

The best entry point for understanding the repository is:

- [docs/codebase-overview.md](docs/codebase-overview.md)

## What is currently in the repo

- `core/`: orchestration, optimizer logic, run database, cache, checkpoints
- `models/`: material model abstractions and HSS writer
- `plaxis/`: PLAXIS remote-scripting connector, staged runner, result extraction
- `metrics/`: branch detection, interpolation, residual metrics, penalties
- `analysis/`: diagnostic plotting plus placeholder Phase 4 analysis modules
- `config/`: YAML files for project, PSO, soil profile, and targets
- `reference_seequent/`: reference script and exported artifacts used to shape
  the extraction workflow

## Quick start

1. Create the Python environment from `environment.yml` or `requirements.txt`.
2. Place the field workbook at `data/field/ocell_measurements.xlsx`.
3. Place the PLAXIS base model at `data/models/OCell_base.p3d`.
4. Update `config/project.yaml` with your PLAXIS connection settings.
5. Review the soil parameter bounds in `config/soil_profile.yaml`.
6. Start with `notebooks/01_smoke_test.ipynb`.

## Notes

- Only `notebooks/01_smoke_test.ipynb` is currently present in the repository.
- `analysis/identifiability.py` and `analysis/mcmc_export.py` are placeholders.
- The repository still needs cleanup before the full PLAXIS-backed workflow is
  production-ready.
