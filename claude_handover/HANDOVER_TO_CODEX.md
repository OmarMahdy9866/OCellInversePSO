# OCellInversePSO — Project Handover Document

**For:** Codex (incoming AI engineering partner)  
**From:** Claude Opus 4.7 (outgoing build partner)  
**User:** Omar Mahdy, Senior Consultant — Ground Engineering, WSP UAE  
**Date of handover:** June 20, 2026  
**Project status:** Phase 1 complete, Phase 2 partially wired, Phases 3–4 pending

---

## 0. TL;DR for Codex

You're inheriting a **research-grade Python framework** that performs **inverse analysis** of the **Hardening Soil Small-Strain (HSS)** constitutive model parameters by minimizing the misfit between **PLAXIS 3D 24.3 simulations** and **field measurements from an Osterberg Cell (O-Cell) bi-directional pile load test** using **Particle Swarm Optimization (PSO)**.

The user (Omar) is a senior geotechnical consultant with deep technical fluency: he designs deep foundations for super-slender towers in Dubai, develops constitutive model implementations, and runs PLAXIS 3D regularly. He values **scientific rigor, clean architecture, publication-quality outputs, and clear modularity**. He dislikes AI-generated fluff, broken formatting, and silent failures. Match his standards.

**Your job over the next sessions:** finish Phase 2 verification with real PLAXIS, build Phase 3 (live Streamlit dashboard + production-run notebook), and Phase 4 (identifiability analysis + MCMC handoff). Full details below.

---

## 1. The Geotechnical Problem (Why This Exists)

### 1.1 Osterberg Cell (O-Cell) Test
An O-Cell is a hydraulic jack embedded mid-pile that applies **bi-directional load**:
- **Upper plate** pushes upward against the upper pile shaft → mobilizes upward shaft friction. Measured displacement is **positive** (PLAXIS Uz convention).
- **Lower plate** pushes downward against the lower pile shaft + base → mobilizes downward shaft friction + end bearing. Measured displacement is **negative**.

The test produces **two independent load-displacement curves** from a single instrument. Both curves are governed by the **same soil parameters** — which is what makes inverse analysis powerful: built-in cross-validation.

### 1.2 The HSS Constitutive Model
**Hardening Soil with Small-Strain stiffness** has 11 parameters per soil layer:

| Param | Meaning | Typical units |
|-------|---------|---------------|
| `E50_ref` | Secant stiffness at 50% failure (triaxial) | kPa |
| `Eoed_ref` | Tangent oedometer stiffness | kPa |
| `Eur_ref` | Unloading-reloading stiffness | kPa |
| `G0_ref` | Small-strain shear stiffness | kPa |
| `m` | Stress dependency exponent | – |
| `phi` | Friction angle | deg |
| `c_ref` | Cohesion | kPa |
| `psi` | Dilation angle | deg |
| `nu_ur` | Poisson ratio (unloading) | – |
| `Rf` | Failure ratio | – |
| `pref` | Reference stress | kPa |
| `gamma_07` | Threshold shear strain (small-strain) | – |

Physical constraints (always enforced before PLAXIS sees the params):
- `Eur_ref >= 3 * E50_ref`
- `Eur_ref >= Eoed_ref`
- `G0_ref >= Eur_ref / (2 * (1 + nu_ur))`
- `gamma_07 ∈ [1e-5, 1e-2]`
- `phi > 0`, `c_ref >= 0`

**Why HSS for O-Cell**: cyclic unload-reload branches in the load schedule isolate `Eur_ref`, `G0_ref`, `gamma_07` — making them identifiable. Without cycles, these parameters are essentially invisible to misfit.

### 1.3 PSO as the Optimizer
**Particle Swarm Optimization** is well-suited because:
- The forward model (PLAXIS) is a black box — no gradients.
- Search space is moderate-dimensional (8–40 params).
- Multiple local minima exist; population-based search dodges them.
- Omar has prior IGT-PSO (Improved Generalized Tikhonov PSO) experience and may want to upgrade.

**Hard constraint:** PLAXIS 3D **cannot** run in parallel — only one instance at a time. Every PSO design decision flows from this serial bottleneck.

---

## 2. Final Architecture (Locked Decisions)

These are **not up for debate** unless Omar says so. They were extensively discussed during the design phase.

| Domain | Decision |
|--------|----------|
| **Project name** | `OCellInversePSO` |
| **Material model (Phase 1)** | HSS, pluggable via `MaterialModel` ABC |
| **Layers** | 1–5, configurable; first run = 2 |
| **Dilation** | `psi = 0` for sand and rock |
| **Bounds** | Dual-mode: `tight` and `wide` profiles in same YAML, switched via `bounds_mode` |
| **Constraints** | Intra-layer + inter-layer + ties, all declared in YAML, parsed at runtime |
| **Optimizer** | Vanilla PSO with reflect-and-project; IGT-PSO via inheritance (Phase 4 stub) |
| **Initialization** | Latin Hypercube Sampling (LHS) for swarm at iter 0 |
| **Termination** | Iteration cap + early stop on stagnation patience |
| **Forward model** | PLAXIS 3D 24.3 via Remote Scripting Server, **serial only** |
| **Per-particle artifacts (always saved)** | `params.yaml`, `predicted_upper.csv`, `predicted_lower.csv`, `plaxis.log`, `diagnostic.png` |
| **PLAXIS model file `.p3d` saved** | Top-K of all time + every Nth + on failure (configurable) |
| **Field data format** | **CSV only**, two files (one per plate). NEVER `.py` modules. |
| **Field CSV schema** | Header row with columns `Load,Displacement` (configurable). Two files: `ocell_upper_plate.csv`, `ocell_lower_plate.csv`. |
| **Interpolation** | PCHIP (default), Akima or linear available. Resample **PLAXIS → field load grid** branch-by-branch. |
| **Branch detection** | Savitzky-Golay smoothing + multi-criterion (amplitude, persistence, length) + PLAXIS phase-count cross-validation |
| **Metrics** | NRMSE, RMSE, MAE, Huber, log-likelihood — user-selectable as primary; ALL stored regardless |
| **Plate weighting** | Equal (0.5 / 0.5 default) |
| **Branch weighting** | Equal default; per-branch weights exposed |
| **Initial-stiffness misfit term** | Optional, default OFF |
| **Failure handling** | Three-tier: pre-flight physical constraint, PLAXIS API rejection, phase-by-phase early stop. Penalties: soft + hard reject + diagnostic log. |
| **Timeout per PLAXIS run** | Optional, default 45 min (~3× nominal 15 min) |
| **PLAXIS resilience** | Heartbeat check, periodic restart every N runs (default 50), idempotent retry on mid-run death |
| **Database** | SQLite, WAL mode for concurrent reads (dashboard) |
| **Caching** | LRU on parameter vector with ε-quantization |
| **Checkpoint** | Every iteration, atomic pickle |
| **Budget presets** | overnight (12h), weekend (48h), holiday (168h), custom |
| **Dashboard** | Streamlit, auto-refresh 30s, reads SQLite (Phase 3) |
| **Identifiability** | FIM at gbest + Sobol on GP surrogate of swarm (Phase 4) |
| **MCMC handoff** | Auto-export multivariate normal prior fit to top-K swarm members (Phase 4) |
| **Reproducibility** | RNG seed, git hash, env lockfile, config snapshot per run |

---

## 3. Folder Structure

```
OCellInversePSO/
├── config/
│   ├── project.yaml              # paths, PLAXIS exe, ports, phase names, ocell node config
│   ├── pso.yaml                  # PSO hyperparams, budget, caching, checkpointing
│   ├── soil_profile.yaml         # ⭐ layers, free/fixed params, dual bounds, constraints
│   └── targets.yaml              # field CSV paths, metrics, weights, interp, branch detection, failure
├── data/
│   ├── field/
│   │   ├── ocell_upper_plate.csv ← CSV ONLY
│   │   └── ocell_lower_plate.csv ← CSV ONLY
│   └── models/
│       └── OCell_base.p3d        # base PLAXIS model (user supplies)
├── core/
│   ├── __init__.py
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── base.py               # BaseSwarmOptimizer (ABC)
│   │   ├── pso.py                # vanilla PSO + LHS + reflect-project
│   │   └── igt_pso.py            # Phase 4 stub
│   ├── orchestrator.py           # main conductor — drives the PSO loop
│   ├── database.py               # SQLite ORM
│   ├── cache.py                  # LRU on quantized param vector
│   └── checkpoint.py             # atomic pickle save/load
├── models/
│   ├── __init__.py
│   ├── base.py                   # MaterialModel ABC
│   └── hss.py                    # HSS implementation + PLAXIS key mapping
├── plaxis/
│   ├── __init__.py
│   ├── connector.py              # plxscripting wrapper with heartbeat + restart
│   ├── material_writer.py        # pushes params into PLAXIS materials
│   ├── result_extractor.py       # extracts O-Cell curves (mirrors postProcessOsterberg.py)
│   ├── node_resolver.py          # node lookup by index/coord/name
│   ├── health.py                 # phase convergence checks
│   └── runner.py                 # phase-by-phase staged construction runner
├── metrics/
│   ├── __init__.py
│   ├── interp.py                 # CSV load + branch detection + PCHIP resampling
│   ├── misfit.py                 # all 5 metrics + per-branch decomposition
│   └── penalties.py              # failure penalty strategies
├── analysis/
│   ├── __init__.py
│   ├── viz.py                    # per-run diagnostic plot (200 dpi, Okabe-Ito)
│   ├── identifiability.py        # Phase 4 stub: FIM + Sobol
│   └── mcmc_export.py            # Phase 4 stub: multivariate normal prior
├── runs/                         # auto-created per run_name
│   └── <run_name>/
│       ├── particles/p07_it003/
│       │   ├── params.yaml
│       │   ├── predicted_upper.csv
│       │   ├── predicted_lower.csv
│       │   ├── plaxis.log
│       │   ├── diagnostic.png
│       │   └── model.p3d (top-K only)
│       ├── pso_state.db
│       ├── checkpoint.pkl
│       ├── project.yaml          # config snapshot
│       ├── pso.yaml
│       ├── soil_profile.yaml
│       └── targets.yaml
├── notebooks/
│   ├── 01_smoke_test.ipynb       # ✅ Phase 1 + Phase 2 verification
│   ├── 02_run_pso.ipynb          # 🚧 Phase 3 (production sweep)
│   ├── 03_identifiability.ipynb  # 🚧 Phase 4
│   └── 04_mcmc_handoff.ipynb     # 🚧 Phase 4
├── dashboard/
│   └── app.py                    # 🚧 Phase 3 Streamlit dashboard
├── requirements.txt
├── environment.yml
├── pyproject.toml                # (optional, for editable install)
└── README.md
```

---

## 4. Configuration Files (Reference)

### 4.1 `config/project.yaml`
Defines run identity, PLAXIS connection, phase ordering, O-Cell-specific node IDs, output policy, resilience parameters, and reproducibility settings.

**Critical fields:**
- `plaxis.phase_names`: Ordered list of PLAXIS calculation phase names that mirror the field loading sequence. Must match field branch count. Exclude `InitialPhase` if you want (orchestrator strips it automatically).
- `ocell.maxLoad`: Used to reconstruct load from `SumMstage × maxLoad`. Same units as PLAXIS model.
- `ocell.upper_node` / `lower_node`: Node identification spec. Three strategies:
  - `{by: index, value: N}` (fragile — only for quick tests)
  - `{by: coord, value: [x, y, z], tol: 0.05}` (recommended)
  - `{by: name, value: "TopPlate"}` (if named in PLAXIS)
- `output.save_model`: Top-K + every-Nth + on-failure + max disk policy.
- `resilience.restart_plaxis_every_n_runs`: Periodic PLAXIS restart (defaults to 50).

### 4.2 `config/pso.yaml`
PSO algorithm hyperparameters: swarm size, iterations, inertia schedule, coefficients, velocity clamping, constraint handling, caching, checkpointing, optional warm-to-tight bounds contraction.

### 4.3 `config/soil_profile.yaml` — **the crown jewel**
Fully declarative description of the search space.

**Key features:**
- `material_model: HSS` selects the material handler.
- `bounds_mode: tight | wide` switches between conservative (informed) and broad (exploratory) bounds. Each free parameter declares both `bounds_tight` AND `bounds_wide`.
- `layers`: list of soil zones, each with:
  - `name`: internal layer name (used everywhere).
  - `plaxis_material_id`: exact PLAXIS material set name (string match).
  - `free`: optimized parameters with bounds, scale (`log` or `linear`), unit.
  - `fixed`: pinned parameter values.
- `constraints.intra_layer`: Python-evaluable expressions on per-layer params (e.g., `"Eur_ref >= 3.0 * E50_ref"`).
- `constraints.inter_layer`: Cross-layer expressions (e.g., `"Weak_Rock.phi >= Sand_Upper.phi"`).
- `ties`: parameters shared across layers (e.g., `gamma_07` everywhere).
- Uses YAML anchors (`&hss_sand_free` and `*hss_sand_free`) to DRY out repeated templates.

**Swapping material models** = change `material_model`, restructure `free`/`fixed` blocks, add a `MaterialModel` subclass. Optimizer, orchestrator, DB stay untouched.

### 4.4 `config/targets.yaml`
Field data paths (**CSV ONLY**), metric selection, weights, interpolation method, branch detection thresholds, failure handling policy.

**Field data block:**
```yaml
field_data:
  csv_files:
    upper: "./data/field/ocell_upper_plate.csv"
    lower: "./data/field/ocell_lower_plate.csv"
  columns: {load: "Load", displacement: "Displacement"}
  units: {load: kN, displacement: m}
```

---

## 5. Module-by-Module Code Reference

### 5.1 `core/optimizer/base.py` — `BaseSwarmOptimizer`
Abstract base class for swarm optimizers. Defines `initialize()`, `update(fitness_values)`, `step(fitness_fn)`, plus state save/load for checkpointing.

### 5.2 `core/optimizer/pso.py` — `PSO`
**Latin Hypercube Sampling** initialization, **linear inertia weight schedule** (`w_start → w_end`), **reflect-and-project** boundary handling (max 4 reflections then clamp), velocity clamping by `v_max_frac × (hi - lo)`, **early stop** on stagnation (patience + min_delta).

### 5.3 `core/optimizer/igt_pso.py` — `IGTPSO` (Phase 4 stub)
Subclass of `PSO`. **TODO[Phase 4]:** Implement Gaussian-perturbed gbest perturbation + ring/star topology switching. Interface already aligned so `pso.yaml` flavor switch (`pso` ↔ `igt_pso`) requires zero orchestrator changes.

### 5.4 `core/orchestrator.py` — **the conductor**

**Class:** `Orchestrator(cfg_dir)`

**Init pipeline:**
1. Load and snapshot all four YAML configs into the run folder.
2. Create SQLite DB (`pso_state.db`).
3. Initialize parameter cache.
4. Build search space from `soil_profile.yaml` via `encode_vector()` (log-scale parameters get log-transformed before going to PSO).
5. Initialize PSO/IGT-PSO with LHS.
6. Load CSV field data + run branch segmentation + **validate vs PLAXIS phase count** (raises if mismatched and `require_plaxis_match: true`).

**Per-particle evaluation (`_evaluate`):**
1. Check parameter cache → if hit, return cached fitness.
2. Decode flat vector to `{layer: {param: value}}` (un-log transformed).
3. Run physical constraint checks (HSS rules) → if violated, soft penalty + log.
4. Write parameters to PLAXIS materials.
5. Run staged phases with timeout + early stop on non-convergence.
6. Extract O-Cell load-displacement curves via `extract_ocell_results`.
7. Resample PLAXIS curves onto field load grid branch-by-branch (`resample_with_cycles`).
8. Compute all metrics (`compute_all_metrics`).
9. Persist: params, predictions, metrics, diagnostic PNG to DB + filesystem.
10. Return fitness to PSO.

**Failure paths:**
- Physical violation → `status="rejected"`, soft penalty.
- PLAXIS exception or no prediction → `status="failed"`, larger penalty, increments fail streak.
- Branch count mismatch → `status="partial"`, penalty.
- Consecutive failures > `hard_reject_after` → particle teleported near gbest with jitter.

**Main run loop:**
- Iterates PSO steps, captures particle ID via closure trick.
- Saves checkpoint every iteration (atomic pickle).
- Appends swarm history to DB.
- Periodic PLAXIS restart every N runs.
- Honors early stop.
- Closes PLAXIS gracefully in `finally`.

### 5.5 `core/database.py` — `RunDB`
SQLite with WAL mode for concurrent reads (dashboard). Tables:
- `runs` — one row per particle-iteration with status, walltime, fitness.
- `parameters` — per-layer per-param values.
- `predictions` — full load-displacement curves with branch tags.
- `metrics` — every metric for every scope (total, per plate, per branch).
- `failures` — phase, reason, last step, detail JSON.
- `swarm_history` — per-iteration aggregate (gbest, mean, std, n_failed, gbest JSON).

### 5.6 `core/cache.py` — `ParamCache`
LRU cache keyed by quantized parameter vector (rounds to `tolerance` then bytes-hashes).

### 5.7 `core/checkpoint.py`
Atomic pickle save (write to `.tmp` then rename) for crash-safe checkpoints.

### 5.8 `models/base.py` — `MaterialModel` ABC
Abstract interface:
- `param_names()` — list of all parameter names.
- `physical_constraints(params)` — returns list of violated constraint descriptions.
- `write_to_plaxis(plx_material, params)` — pushes values to PLAXIS material object.

### 5.9 `models/hss.py` — `HSS(MaterialModel)`
HSS implementation. Maps internal parameter names (`E50_ref`, `Eoed_ref`, etc.) to PLAXIS internal keys (`E50ref`, `EoedRef`, etc.) via `HSS_PLAXIS_KEYS` dict. **Note:** the PLAXIS internal keys may need to be verified against PLAXIS 3D 24.3 — Codex should verify these in Phase 2 testing.

### 5.10 `plaxis/connector.py` — `PlaxisConnector`
Wraps `plxscripting.easy.new_server` for both Input and Output servers. Opens base model on connect. `heartbeat()` for liveness check. `restart()` for periodic memory-leak mitigation. `close()` cleanup.

### 5.11 `plaxis/material_writer.py`
Iterates layers in `soil_profile.yaml`, finds PLAXIS material by `plaxis_material_id`, delegates to `model.write_to_plaxis()`. Raises clear `KeyError` if material not found.

### 5.12 `plaxis/result_extractor.py` — **the key Phase 2 module**
Mirrors patterns from Omar's `postProcessOsterberg.py` reference file:
- Loads reconstructed from `SumMstage × maxLoad` (loading) or `(1 - SumMstage) × maxLoad` (unloading).
- Displacements via `g_o.getcurveresults(node, step, g_o.ResultTypes.Soil.Uz)`.
- Iterates phases in order matching field branches.
- Tags each row with `branch_id` (1-indexed) and `branch_kind` (loading/unloading/reloading inferred from phase name).
- Prepends `(0, 0)` initial point for clean interpolant behavior.

**TODO for Codex (Phase 2 verification):**
- Verify `phase.Steps.value` actually returns the step list in PLAXIS 24.3 (Omar's reference uses this pattern, should work).
- Verify `getcurveresults` returns a plain float for `ResultTypes.Soil.Uz`.
- Confirm `SumMstage` attribute path (`step.Reached.SumMstage.value`) is correct.

### 5.13 `plaxis/node_resolver.py` — `NodeResolver`
Robust node lookup with three strategies (index/coord/name) and graceful fallback. Caches the node list on first call.

### 5.14 `plaxis/runner.py` — `run_staged_phases`
Loops through phases, calls `g.calculate(phase)`, checks `SumMstage > 0.999` for convergence, breaks on first failure, writes phase-by-phase log, honors timeout. Returns dict with `partial`, `last_phase`, `phases_run`, `walltime_s`, `errors`.

### 5.15 `plaxis/health.py`
`phase_converged(phase)`: simple check on `phase.Reached.SumMstage > 0.999`.

### 5.16 `metrics/interp.py` — **CRITICAL — CSV ONLY**
Three responsibilities:
1. `load_field_data(targets_cfg)` — strict CSV loader, two files. Validates columns, drops NaNs, raises clear errors. **NO `.py` MODULE SUPPORT** (Omar was explicit about this).
2. `segment_branches(df, targets_cfg)` — Savitzky-Golay smoothing + multi-criterion turning-point detection (persistence window, amplitude threshold, min branch length). Promotes second+ "loading" branches to "reloading" after an unloading is seen. Always runs the full pipeline — no shortcuts.
3. `resample_with_cycles(predicted_df, field_df, field_branches, targets_cfg)` — for each branch, builds PCHIP/Akima/linear interpolant on PLAXIS data, resamples to field load grid, computes residuals. Verifies PLAXIS branch count matches field. Returns residuals, per-branch dict, diagnostics.

### 5.17 `metrics/misfit.py`
- Individual metric functions: `nrmse`, `rmse`, `mae`, `huber`, `neg_log_likelihood`.
- `robust_sigma`: MAD-based scale estimate for Huber/log-likelihood.
- `compute_all_metrics`: master function. Computes every metric per plate (full vector), per branch, applies branch weights to primary metric, applies plate weights, optionally adds initial-stiffness term. Returns dict with `primary_total`, `rows` (for DB), `per_plate`, plus `sigma` and `delta`.

### 5.18 `metrics/penalties.py`
`apply_penalty(reason, config, worst_seen)`: returns `kappa × max(worst_seen, 1)` for soft penalty, `inf` otherwise.

### 5.19 `analysis/viz.py` — `save_diagnostic_plot`
Per-run 4-panel publication-quality figure (200 dpi, Okabe-Ito palette for colorblind safety):
- Top row: load-displacement for upper + lower plate. Field points by branch color. PLAXIS raw + PCHIP interpolant overlay.
- Bottom row: per-branch RMSE bar chart + per-branch coverage bar chart.
- Title shows run label + fitness.

### 5.20 `analysis/identifiability.py` (Phase 4 stub)
**TODO:** Fisher Information Matrix at gbest + Sobol sensitivity on Gaussian Process surrogate fit to swarm history.

### 5.21 `analysis/mcmc_export.py` (Phase 4 stub)
**TODO:** Fit multivariate normal to top-K swarm members as MCMC prior.

---

## 6. Data Conventions

### 6.1 Field CSV files
Two files, one per plate. Headers exactly `Load,Displacement` (configurable in `targets.yaml`).

**Sample structure (Omar's reference dataset, 25 rows each):**
```
Load,Displacement
0,0
3.27291769,0.000267
8.02177121,0.000682
...
53.13997366,0.013561
42.29495866,0.013353
...
0.06874117,0.009822
```

**Sign convention (PLAXIS native, Uz positive upward):**
- Upper plate displacement: **positive** (moves up).
- Lower plate displacement: **negative** (moves down).
- Both curves start at (0, 0) — orchestrator/extractor preserves this.

### 6.2 PLAXIS phase contract
- Phase names in `project.yaml.plaxis.phase_names` MUST mirror field loading sequence in order.
- `InitialPhase` is stripped automatically by the orchestrator.
- Each calculation phase = one branch.
- Phase name heuristic for branch kind:
  - Contains "unload" → "unloading"
  - Contains "reload" → "reloading"
  - Else → "loading"

### 6.3 Units
Match PLAXIS model units exactly. Common: kN, m, kPa. The framework does NO unit conversion.

---

## 7. Phase Status

### ✅ Phase 1 — Scaffolding + Smoke Test (COMPLETE)
**What works:**
- All YAML configs (project, pso, soil_profile, targets) — full, validated, reusable.
- PSO with LHS init, reflect-project bounds, early stop, history tracking.
- SQLite database with WAL mode + complete schema.
- Parameter cache, atomic checkpointing, RNG seeding.
- HSS material model with physical-constraint validation.
- Branch detection + PCHIP resampling + per-branch metrics.
- Diagnostic plot generator.
- Orchestrator wired end-to-end.
- Smoke-test notebook cells 1–5 verify WITHOUT PLAXIS.
- Field CSV files prepared from Omar's reference dataset.

**Verification:** Cells 1–8 of `01_smoke_test.ipynb` pass end-to-end without PLAXIS, using the prepared CSV files.

### 🚧 Phase 2 — PLAXIS Live Hookup (IN PROGRESS)
**What's coded:**
- `plaxis/result_extractor.py` mirrors Omar's `postProcessOsterberg.py` extraction patterns.
- `plaxis/node_resolver.py` provides robust node lookup.
- `plaxis/runner.py` does phase-by-phase staged construction.
- Orchestrator integrates everything.

**What needs verification (CODEX, do this first):**
1. **Cell 9 of smoke notebook** — run with PLAXIS open + base model calculated. Confirm extractor returns DataFrames with expected branch_id, branch_kind, load, displacement columns.
2. **Cell 10 of smoke notebook** — run full resample + metrics pipeline. Confirm coverage ≥ 95% per branch and diagnostic.png renders correctly.
3. **Verify `HSS_PLAXIS_KEYS` in `models/hss.py`** — these key names may need adjustment for PLAXIS 3D 24.3. Test by reading current values of a known material before/after `setproperties`.
4. **Verify `plaxis_material_id` lookup** — confirm `g.Materials[:]` iteration and `.Name` attribute work in 24.3.

**Phase 2 deliverables to complete:**
- Successful smoke test cell 9 + 10 with real PLAXIS.
- Tuned HSS key mapping if needed.
- A short README in `data/field/` documenting the CSV contract.
- A README in `data/models/` listing what Omar needs to put there.

### 🚧 Phase 3 — Production Run Notebook + Live Dashboard (PENDING)
**Build `notebooks/02_run_pso.ipynb`:**
- Single-page operator notebook.
- Cell 1: import + paths.
- Cell 2: `from core.orchestrator import Orchestrator`.
- Cell 3: `orch = Orchestrator(cfg_dir="../config")` — pre-flight checks, prints search space dimensionality, branch validation, estimated budget.
- Cell 4: `summary = orch.run()` — fires the sweep.
- Cell 5: Post-run summary (gbest decoded, total runs, walltime, success rate).
- Cell 6: Quick convergence plot from `swarm_history` table.
- Cell 7: Generate report PDF from run folder artifacts.

**Build `dashboard/app.py` (Streamlit):**
Layout:
- Header: project name, run ID, status (RUNNING/COMPLETE/STALLED), iteration counter, ETA.
- Row 1, Col 1: convergence plot (gbest, mean ± std fitness vs iteration), reads `swarm_history`.
- Row 1, Col 2: current gbest parameter table by layer, formatted with units.
- Row 2, Col 1: swarm PCA projection (animated), reads `parameters` × `runs`.
- Row 2, Col 2: top-K leaderboard, reads `runs` ORDER BY fitness ASC LIMIT 10.
- Row 3, full width: measured vs predicted for best particle (live), reads `predictions` for top run.
- Sidebar: run selector, refresh interval, metric to plot.

Auto-refresh every 30s. Read-only on the DB (WAL mode allows it concurrently). Use `streamlit_autorefresh` package.

**Add to `requirements.txt`:**
```
streamlit>=1.32
streamlit-autorefresh
plotly>=5.18
watchdog
```

### 🚧 Phase 4 — Identifiability + MCMC Handoff (PENDING)
**`analysis/identifiability.py`:**
- `fim_from_swarm(db_path, top_k=50)`:
  - Pull top-K swarm members + their fitnesses from DB.
  - Approximate FIM via local quadratic fit around gbest: `H ≈ ∂²L/∂θ²` from residual sensitivity.
  - Eigendecompose. Plot eigenvalue spectrum.
  - Compute condition number.
  - Identify the most/least identifiable parameter combinations as eigenvectors.

- `sobol_surrogate(db_path)`:
  - Fit a Gaussian Process (sklearn `GaussianProcessRegressor`) to swarm history (X=params, y=fitness).
  - Run SALib Sobol on the GP — no extra PLAXIS calls needed.
  - Return first-order and total-order indices per parameter.

- `parameter_correlation_from_swarm(db_path)`:
  - Pearson correlation matrix on top-K swarm members.
  - Plot as heatmap.

**`analysis/mcmc_export.py`:**
- `export_mcmc_prior(db_path, top_k=50, out_path)`:
  - Fit multivariate normal to top-K swarm members (mean + covariance).
  - Save as JSON + pickle: `{"mean": [...], "cov": [[...]], "param_names": [...], "bounds": [[...]]}`.
  - Provide loader stub for emcee/PyMC consumption.

**`notebooks/03_identifiability.ipynb`:**
- Load run DB.
- Call FIM analysis → eigenvalue spectrum plot.
- Call Sobol surrogate → bar chart of indices.
- Compute correlation matrix → heatmap.
- Compute marginal "pseudo-posterior" histograms per parameter.
- Auto-generate Markdown report.

**`notebooks/04_mcmc_handoff.ipynb`:**
- Export prior.
- Show example emcee setup using the exported prior as initial walker positions.
- Run a short MCMC chain (say, 100 steps, 32 walkers) using the GP surrogate as the likelihood — fast preview.
- Show corner plot.
- Document handoff path for full MCMC run on a workstation.

---

## 8. Critical Gotchas Codex Must Know

### 8.1 The `__init__.py` requirement
Every package folder MUST have an `__init__.py` (even empty) or relative imports break with `ImportError: cannot import name 'X' from 'package' (unknown location)`. The error message clue is `(unknown location)`. Omar already hit this once.

### 8.2 PLAXIS serial constraint
**Never** parallelize particle evaluation. PLAXIS 3D allows only one calculation at a time. Asynchronous PSO is fine; threading the fitness function is not.

### 8.3 PLAXIS memory leak mitigation
PLAXIS occasionally drops scripting connections and leaks memory over long runs. The framework restarts PLAXIS every N runs (default 50). Codex: do NOT remove this. If Omar's runs are short (<30 particles total), can be raised; for holiday budgets (>500 runs), may need to lower.

### 8.4 Branch detection robustness
The Savitzky-Golay + multi-criterion detector is tuned for ACCURACY (Omar's explicit request). If branch counts mismatch PLAXIS phase count, the orchestrator raises by default. Codex: do NOT silently degrade to auto-retry without telling Omar.

### 8.5 CSV is the ONLY field data contract
Omar was explicit: **field data is always CSV, never `.py`, never embedded in code**. The reference file `postProcessOsterberg.py` happened to embed field arrays — that's a Bentley demo convention, not the project's data contract. Codex: do not "helpfully" re-add Python module support for field data. Reproducibility + audit trail demands the CSV boundary.

### 8.6 Sign conventions
PLAXIS Uz convention: positive = upward. Field CSV uses the same convention. Upper plate disp > 0, lower plate disp < 0. The extractor does NO sign flipping. If Omar's PLAXIS model uses a different convention (e.g., a flipped coordinate system), this needs to be handled in the extractor — Codex, verify during Phase 2 testing.

### 8.7 Phase naming heuristic
The orchestrator infers branch kind from phase name substring (`unload`, `reload`, else loading). Phase names like `Unload_1`, `Reload_2`, `Loading` work. If Omar uses opaque names like `Phase_1`, `Phase_2`, the heuristic falls back to "loading" for all — which is wrong for unloading branches. Codex: if phases are opaque, prompt Omar to either rename them or add an explicit phase-kind mapping to `project.yaml`.

### 8.8 `phase.Steps.value` vs `phase.Steps[:]`
Omar's reference uses `phase.Steps.value` — this returns the actual step list. In some PLAXIS API versions it's `phase.Steps[:]`. Codex: verify which works in 24.3 during Phase 2 verification.

### 8.9 Database concurrency
SQLite WAL mode supports concurrent readers + one writer. The dashboard (read-only) can run while PSO writes. Codex: ensure the dashboard NEVER writes. Connection should be opened with `?mode=ro` in URI or just never call insert methods.

### 8.10 The bug fixed in Wave 2 orchestrator
The original Phase 1 orchestrator had a broken closure for particle ID tracking in `opt.step(lambda x: ...)`. The Wave 2 fix uses a `particle_counter = {"pid": -1}` dict closed over by the `fitness_fn` definition. Codex: do not "simplify" this back to a broken pattern.

---

## 9. Reproducibility & Provenance

Every run folder contains:
- Snapshot of all four YAML configs (`project.yaml`, `pso.yaml`, `soil_profile.yaml`, `targets.yaml`) as used at run start.
- RNG seed stored in `project.yaml` and applied at orchestrator init.
- `pso_state.db` containing full swarm history + every particle result.
- `checkpoint.pkl` for crash recovery.
- Per-particle `params.yaml`, `predicted_*.csv`, `plaxis.log`, `diagnostic.png`.

**Phase 4 addition:** auto-log git commit hash + `environment.yml` snapshot at run start, write to `runs/<run_name>/_meta/`.

---

## 10. User Profile (Match His Style)

Omar Mahdy — Senior Consultant in Ground Engineering at WSP, based in Sharjah/Dubai, UAE.

**Technical context:**
- Deep foundations specialist (super-slender Dubai towers, Muraba Tower).
- HSS, NorSand, MC constitutive modeling.
- PLAXIS 3D, FLAC, PSO/IGT-PSO inverse analysis.
- Preparing manuscript for *Computers and Geotechnics* on PSO-based 1-D consolidation inversion.
- Invited speaker at DFUI 2026 Dubai (June 23–24, 2026).
- Pursuing PE licensure in Texas via NCEES.

**Working style:**
- Highly engaged, fast turnaround, iterative refinement.
- Values rigor: clean equations, consistent nomenclature, publication-quality figures (200 dpi, colorblind-safe palettes), comprehensive logging.
- Dislikes: AI-sounding writing, special-character artifacts, basic visualizations, silent failures.
- Tone preference: friendly + technical, not formal AI-speak. Uses casual openings ("Buddy!", "Habibi"). Match the energy but stay competent.
- Builds late at night to escape conference prep stress. Likes building things "for fun" that turn into paper-worthy frameworks.

**Communication patterns:**
- Asks short, specific questions; expects deep, structured answers.
- Frequently splits "What do we have?" and "What's next?" — answer both.
- Explicit about preferences (e.g., "CSV only, never .py" — respect such boundaries fiercely).
- Will catch drift or sloppiness immediately. Acknowledge mistakes, fix them.
- Appreciates honest moments ("totally honest take: this is paper-worthy").

---

## 11. Immediate Next Steps for Codex

1. **Verify the smoke test runs end-to-end on Omar's machine.**
   - Cells 1–5: no dependencies beyond Python + numpy + scipy + pandas + matplotlib + yaml.
   - Cells 6–8: needs the two CSV files in `data/field/`.
   - Cells 9–10: needs PLAXIS 3D 24.3 open with base model calculated.

2. **Tune HSS PLAXIS key mapping** in `models/hss.py` if Phase 2 reveals API differences.

3. **Build `notebooks/02_run_pso.ipynb`** for the first real PSO sweep. Recommend a small budget first: 8 particles × 6 iterations (≈12 h with 15-min runs).

4. **Build `dashboard/app.py`** so Omar can watch overnight runs from his phone.

5. **Implement Phase 4 stubs:**
   - `analysis/identifiability.py`
   - `analysis/mcmc_export.py`
   - `notebooks/03_identifiability.ipynb`
   - `notebooks/04_mcmc_handoff.ipynb`

6. **Eventually:** add `models/norsand.py` and `models/mohr_coulomb.py` to demonstrate the pluggable architecture.

---

## 12. Open Questions for Omar

Codex, ask Omar these early in your first session:

1. **PLAXIS material naming** — what are the actual material names in his model? (For populating `plaxis_material_id` in `soil_profile.yaml`.)
2. **O-Cell node coordinates** — what are the (x, y, z) coordinates of the upper and lower plate query nodes? (For switching from `by: index` to the robust `by: coord` strategy.)
3. **Phase names** — what are the actual PLAXIS phase names in his calculation list? (For populating `phase_names` correctly.)
4. **Run budget for first real sweep** — 12 hrs overnight, 48 hrs weekend, or something custom?
5. **Soil layer setup** — for the first real run, how many layers, what types (sand/clay/rock), and any site-specific physical constraints?

---

## 13. Philosophy

This framework is built for:
- ✅ **Reproducibility** — every run audit-trailable.
- ✅ **Modularity** — material model, optimizer, metric all swappable.
- ✅ **Robustness** — every failure mode caught, logged, recovered.
- ✅ **Publication quality** — figures, metrics, identifiability ready for journal submission.
- ✅ **Client deliverability** — clean YAML configs, CSV data boundary, no hidden state.

Don't compromise these. They are what makes this framework worth using.

---

**End of handover document.**

Codex — you have everything you need. Help Omar finish what we started. Be sharp, be honest, and match his standards. 🤝

— Claude Opus 4.7
