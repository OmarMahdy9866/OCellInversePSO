# Codebase Overview

## Purpose

`OCellInversePSO` is a geotechnical calibration workflow that tries to identify
Hardening Soil Small-Strain material parameters by matching PLAXIS 3D
simulation output to measured O-Cell load-test curves.

At a high level:

1. A particle swarm optimizer proposes soil parameters.
2. Those parameters are written into a PLAXIS model.
3. The model is run through staged loading and unloading phases.
4. Simulated upper and lower plate displacements are extracted.
5. The simulated curves are resampled against field data.
6. Misfit metrics are computed and fed back to the optimizer.
7. All runs, parameters, predictions, and summary history are persisted.

## Actual repository layout

This is the current tree in the repository, based on the files that are
present now:

- `analysis/`
  - `viz.py`: saves per-run diagnostic plots
  - `identifiability.py`: placeholder for Phase 4 work
  - `mcmc_export.py`: placeholder for Phase 4 work
- `config/`
  - `project.yaml`: run naming, PLAXIS connection, output and resilience knobs
  - `pso.yaml`: PSO hyperparameters and checkpoint settings
  - `soil_profile.yaml`: material bounds, fixed values, layer mapping
  - `targets.yaml`: field-data path, interpolation, branch detection, metrics
- `core/`
  - `orchestrator.py`: main runtime entry point
  - `database.py`: SQLite persistence layer
  - `cache.py`: in-memory tolerance-based parameter cache
  - `checkpoints.py`: pickle save/load helpers
  - `optimizer/`: swarm optimizer abstractions and PSO implementations
- `data/`
  - `ocell_field_data.py`: hard-coded reference O-Cell dataset
- `metrics/`
  - `interp.py`: field loading, branch detection, interpolation, residual build
  - `misfit.py`: objective metrics
  - `penalties.py`: penalty handling for failed runs
- `models/`
  - `base.py`: material-model interface
  - `hss.py`: HSS parameter constraints and PLAXIS property mapping
- `plaxis/`
  - `connector.py`: remote-scripting connection lifecycle
  - `material_writer.py`: pushes parameter values into PLAXIS materials
  - `runner.py`: executes staged phases
  - `result_extractor.py`: reconstructs load and displacement curves
  - `node_resolver.py`: resolves output nodes by index, coordinates, or name
  - `health.py`: simple convergence check
- `reference_seequent/`
  - Reference script and artifacts used to mirror the O-Cell extraction logic
- `notebooks/`
  - `01_smoke_test.ipynb`

## Runtime flow

### 1. Configuration loading

`core.orchestrator.Orchestrator` loads all four YAML files from `config/`:

- `project.yaml`
- `pso.yaml`
- `soil_profile.yaml`
- `targets.yaml`

It also creates the run directory under `runs/<run_name>/` and copies those
configuration files into the run folder for reproducibility.

### 2. Parameter encoding

`encode_vector()` in `core/orchestrator.py` walks the soil profile and flattens
all free parameters into a numeric vector with bounds. Log-scaled parameters are
stored in log space so the optimizer works on a better-scaled search domain.

`decode_vector()` converts a particle back into a nested
`{layer_name: {param_name: value}}` mapping and merges fixed parameters from the
soil profile.

### 3. Optimization loop

`core/optimizer/base.py` defines the base swarm API.
`core/optimizer/pso.py` implements the active optimizer:

- LHS or random initialization
- inertia scheduling
- cognitive and social velocity terms
- reflect-and-project bound handling
- simple early stopping

Each PSO iteration evaluates every particle by calling the orchestrator's
`_evaluate()` function.

### 4. Single-particle evaluation

For each particle:

1. The cache is checked to avoid repeating near-identical evaluations.
2. The vector is decoded into layer-by-layer HSS parameters.
3. Physical constraints are validated through `models.hss.HSS`.
4. Parameters are written into a particle-specific run folder.
5. The material set is pushed into the live PLAXIS model.
6. PLAXIS phases are executed.
7. O-Cell results are extracted from PLAXIS Output.
8. Predicted curves are resampled to the field-data points.
9. Residual metrics are computed.
10. Results are written into SQLite and optional PNG diagnostics are saved.

## Module walkthrough

### `core/orchestrator.py`

This is the central coordinator. It ties together:

- configuration
- optimizer selection
- field-data loading
- PLAXIS execution
- metrics
- persistence
- diagnostics

If this file is stable, the whole project becomes much easier to operate.

### `core/database.py`

Stores runtime artifacts in SQLite:

- `runs`
- `parameters`
- `predictions`
- `metrics`
- `failures`
- `swarm_history`

This is the main audit trail for later analysis and dashboarding.

### `metrics/interp.py`

This module does two conceptually separate jobs:

- reading field data from Excel
- turning predicted and measured curves into aligned residuals

It also contains automatic branch detection logic for loading, unloading, and
reloading segments.

### `metrics/misfit.py`

Computes the optimization objective and stores a wider metric set:

- NRMSE
- RMSE
- MAE
- Huber loss
- negative log-likelihood

The optimizer uses one metric as the primary objective based on
`targets.yaml`.

### `models/hss.py`

Maps project parameter names to PLAXIS HSsmall property names and enforces a few
basic physical relationships such as:

- `Eur_ref >= 3 * E50_ref`
- `Eur_ref >= Eoed_ref`
- `G0_ref >= Eur_ref / (2 * (1 + nu_ur))`

### `plaxis/`

This directory wraps the PLAXIS remote-scripting workflow:

- `connector.py`: session management
- `material_writer.py`: model mutation
- `runner.py`: phase execution
- `result_extractor.py`: output extraction
- `node_resolver.py`: mapping logical node specs to actual output nodes

Together, these files form the forward-model interface.

## Configuration guide

### `config/project.yaml`

Holds project-level runtime settings:

- run name and root directory
- PLAXIS executable and scripting ports
- PLAXIS phase names
- O-Cell metadata such as `maxLoad` and node specs
- output toggles
- restart and timeout settings

### `config/pso.yaml`

Controls swarm behavior:

- optimizer flavor
- swarm size
- initialization mode
- iteration budget
- early-stop settings
- velocity and inertia constants
- cache usage
- checkpointing

### `config/soil_profile.yaml`

Defines the inversion parameter space:

- material model name
- per-layer PLAXIS material identifiers
- free parameters and bounds
- fixed parameters
- constraint and tie declarations

### `config/targets.yaml`

Defines how field data is compared against model output:

- Excel file path
- sheet and column names
- objective metric choice
- plate weights
- interpolation strategy
- branch detection settings
- failure and penalty settings

## Inputs and outputs

### Inputs

- field workbook at `data/field/ocell_measurements.xlsx`
- PLAXIS model at `data/models/OCell_base.p3d`
- YAML configuration files in `config/`

### Outputs

Expected outputs for each run include:

- `runs/<run_name>/pso_state.db`
- `runs/<run_name>/checkpoint.pkl`
- `runs/<run_name>/particles/<particle>_<iteration>/params.yaml`
- `runs/<run_name>/particles/<particle>_<iteration>/plaxis.log`
- `runs/<run_name>/particles/<particle>_<iteration>/diagnostic.png`

## Current limitations

The repo is not fully aligned with its own plan yet. The main limitations today
are:

- documentation drift between the current tree and the planned tree
- placeholder analysis modules for identifiability and MCMC export
- no committed dashboard implementation
- no automated test suite
- several configuration options appear planned but not fully wired into runtime

## Suggested next documentation files

If you want to expand documentation after this overview, the most useful next
documents would be:

1. `docs/runtime-setup.md`
2. `docs/config-reference.md`
3. `docs/plaxis-integration.md`
4. `docs/data-contracts.md`
5. `docs/known-issues.md`
