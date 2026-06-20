OCellInversePSO/
├── config/
│   ├── project.yaml
│   ├── pso.yaml
│   ├── soil_profile.yaml
│   └── targets.yaml
├── data/
│   ├── field/                  # place ocell_upper_plate.csv and ocell_lower_plate.csv here
│   └── models/                 # place OCell_base.p3d here
├── core/
│   ├── __init__.py
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── pso.py
│   │   └── igt_pso.py          # stub, ready for Phase 4
│   ├── orchestrator.py
│   ├── database.py
│   ├── cache.py
│   └── checkpoint.py
├── models/
│   ├── __init__.py
│   ├── base.py
│   └── hss.py
├── plaxis/
│   ├── __init__.py
│   ├── connector.py
│   ├── material_writer.py
│   ├── result_extractor.py
│   ├── health.py
│   └── runner.py
├── metrics/
│   ├── __init__.py
│   ├── interp.py
│   ├── misfit.py
│   └── penalties.py
├── analysis/
│   ├── __init__.py
│   ├── viz.py
│   ├── identifiability.py      # stub, Phase 4
│   └── mcmc_export.py          # stub, Phase 4
├── runs/                       # auto-created per run
├── notebooks/
│   ├── 01_smoke_test.ipynb
│   ├── 02_run_pso.ipynb
│   ├── 03_identifiability.ipynb
│   └── 04_mcmc_handoff.ipynb
├── dashboard/
│   └── app.py                  # Streamlit, Phase 3
├── environment.yml
├── README.md
└── pyproject.toml
