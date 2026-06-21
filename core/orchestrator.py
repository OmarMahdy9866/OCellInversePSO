"""Main PSO loop for serial PLAXIS-backed inverse analysis."""
from __future__ import annotations

import shutil
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import yaml

from analysis.viz import save_diagnostic_plot
from core import checkpoints as ckpt
from core.cache import ParamCache
from core.database import RunDB
from core.optimizer.igt_pso import IGTPSO
from core.optimizer.pso import PSO
from metrics.interp import resample_with_cycles
from metrics.misfit import compute_all_metrics
from metrics.penalties import apply_penalty
from models.hss import HSS
from plaxis.connector import PlaxisConnector
from plaxis.material_writer import write_layer_materials
from plaxis.result_extractor import extract_ocell_results
from plaxis.runner import run_staged_phases


def load_yaml(p: str | Path) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def encode_vector(profile: dict, mode: str) -> Tuple[np.ndarray, list]:
    """Walk the profile into a flat bounds array and symbol table."""
    bk = "bounds_tight" if mode == "tight" else "bounds_wide"
    bounds, syms = [], []
    for layer in profile["layers"]:
        for pname, spec in layer["free"].items():
            lo, hi = map(float, spec[bk])
            if spec["scale"] == "log":
                lo, hi = np.log(lo), np.log(hi)
            bounds.append((lo, hi))
            syms.append((layer["name"], pname, spec["scale"]))
    return np.asarray(bounds), syms


def decode_vector(
    x: np.ndarray, syms: list, profile: dict
) -> Dict[str, Dict[str, float]]:
    """Convert a flat vector back into per-layer parameter dictionaries."""
    params = {
        layer["name"]: {k: v["value"] for k, v in layer["fixed"].items()}
        for layer in profile["layers"]
    }
    for xi, (layer_name, pname, scale) in zip(x, syms):
        params[layer_name][pname] = float(np.exp(xi) if scale == "log" else xi)
    return params


class Orchestrator:
    def __init__(self, cfg_dir: str | Path):
        self.cfg_dir = Path(cfg_dir)
        self.project = load_yaml(self.cfg_dir / "project.yaml")
        self.pso_cfg = load_yaml(self.cfg_dir / "pso.yaml")
        self.profile = load_yaml(self.cfg_dir / "soil_profile.yaml")
        self.targets = load_yaml(self.cfg_dir / "targets.yaml")

        self.run_dir = (
            Path(self.project["project"]["root_dir"])
            / self.project["project"]["run_name"]
        )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for p in (
            self.cfg_dir / "project.yaml",
            self.cfg_dir / "pso.yaml",
            self.cfg_dir / "soil_profile.yaml",
            self.cfg_dir / "targets.yaml",
        ):
            shutil.copy2(p, self.run_dir / p.name)

        self.db = RunDB(self.run_dir / "pso_state.db")
        self.cache = ParamCache(self.pso_cfg["caching"]["tolerance"])
        self.material = HSS()
        self.bounds, self.syms = encode_vector(
            self.profile, self.profile["bounds_mode"]
        )
        self.n_dims = len(self.syms)
        self.rng = np.random.default_rng(self.project["reproducibility"]["seed"])

        opt_cls = IGTPSO if self.pso_cfg["algorithm"]["flavor"] == "igt_pso" else PSO
        self.opt = opt_cls(
            self.pso_cfg["swarm"]["size"],
            self.n_dims,
            self.bounds,
            self.pso_cfg,
            rng=self.rng,
        )
        self.plx: PlaxisConnector | None = None
        self.fail_streak: dict[int, int] = {}
        self.plaxis_run_count = 0

        self._load_field_data()

    def _calculation_phase_names(self) -> list[str]:
        return [
            str(name)
            for name in self.project["plaxis"]["phase_names"]
            if str(name).lower() != "initialphase"
        ]

    def _load_field_data(self):
        from metrics.interp import load_field_data, segment_branches

        self.field = load_field_data(self.targets)
        self.field_branches = {
            plate: segment_branches(self.field[plate], self.targets)
            for plate in ("upper", "lower")
        }
        n_phases = len(self._calculation_phase_names())
        n_field_branches = len(self.field_branches["upper"])
        if (
            self.targets["branch_detection"]["validation"]["require_plaxis_match"]
            and n_field_branches != n_phases
        ):
            raise ValueError(
                f"Field branches detected={n_field_branches} but PLAXIS phases={n_phases}. "
                "Re-check staging or branch_detection thresholds."
            )

    def _save_predicted_curves(
        self, run_sub: Path, predicted: Dict[str, Any]
    ) -> None:
        for plate, df in predicted.items():
            df.to_csv(run_sub / f"predicted_{plate}.csv", index=False)

    def _register_plaxis_run(self) -> None:
        self.plaxis_run_count += 1
        restart_every = int(
            self.project["resilience"].get("restart_plaxis_every_n_runs", 0) or 0
        )
        if (
            restart_every > 0
            and self.plaxis_run_count % restart_every == 0
            and self.plx is not None
        ):
            self.plx.restart()

    def _record_failure(
        self,
        run_id: int,
        status: str,
        fail_info: Dict[str, Any] | None,
    ) -> None:
        if not fail_info or status == "ok":
            return
        reason = fail_info.get("reason")
        if reason is None:
            reason = "; ".join(fail_info.get("errors", []))
        self.db.insert_failure(
            run_id,
            fail_info.get("last_phase", "unknown"),
            reason or status,
            None,
            fail_info,
        )

    def _evaluate(self, x: np.ndarray, particle_id: int) -> float:
        """Run one particle through PLAXIS and return fitness."""
        t0 = time.time()
        cached = self.cache.get(x) if self.pso_cfg["caching"]["enabled"] else None
        if cached is not None:
            self.db.insert_run(
                particle_id,
                self.opt.iter_count,
                "cached",
                time.time() - t0,
                cached,
                "from cache",
            )
            return cached

        params = decode_vector(x, self.syms, self.profile)
        violations = []
        for layer, layer_params in params.items():
            violations.extend(
                f"{layer}: {msg}"
                for msg in self.material.physical_constraints(layer_params)
            )
        if violations:
            penalty = apply_penalty(
                reason="physical",
                config=self.targets["failure"],
                worst_seen=self.opt.gbest_fit,
            )
            rid = self.db.insert_run(
                particle_id,
                self.opt.iter_count,
                "rejected",
                time.time() - t0,
                penalty,
                "; ".join(violations),
            )
            self.db.insert_parameters(rid, params)
            return penalty

        run_sub = (
            self.run_dir / "particles" / f"p{particle_id:02d}_it{self.opt.iter_count:03d}"
        )
        run_sub.mkdir(parents=True, exist_ok=True)
        with open(run_sub / "params.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(params, f, sort_keys=False)

        phase_names = self._calculation_phase_names()
        status, predicted, fail_info = "ok", None, None
        attempted_plaxis_run = False
        try:
            write_layer_materials(self.plx, params, self.profile, self.material)
            attempted_plaxis_run = True
            run_log = run_staged_phases(
                self.plx,
                phase_names=self.project["plaxis"]["phase_names"],
                timeout_min=self.project["resilience"]["timeout_min_per_run"],
                log_path=run_sub / "plaxis.log",
            )
            completed_phases = [
                name
                for name in run_log.get("phases_run", [])
                if str(name).lower() != "initialphase"
            ]
            if completed_phases:
                self.plx.open_output_view(run_log.get("last_phase"))
                predicted = extract_ocell_results(
                    self.plx,
                    phase_names=completed_phases,
                    ocell_cfg=self.project["ocell"],
                )
            if run_log.get("partial"):
                status = "partial"
                fail_info = run_log
        except Exception as e:
            status = "failed"
            fail_info = {"reason": str(e), "trace": traceback.format_exc()}
        if attempted_plaxis_run:
            self._register_plaxis_run()

        if predicted is None:
            fitness = apply_penalty(
                "plaxis_fail", self.targets["failure"], self.opt.gbest_fit
            )
            rid = self.db.insert_run(
                particle_id,
                self.opt.iter_count,
                status,
                time.time() - t0,
                fitness,
                fail_info.get("reason", "") if fail_info else "",
            )
            self.db.insert_parameters(rid, params)
            self._record_failure(rid, status, fail_info)
            self._tick_streak(particle_id, failed=True)
            self.cache.put(x, fitness)
            return fitness

        residuals, per_branch, diag = {}, {}, {}
        for plate in ("upper", "lower"):
            residuals[plate], per_branch[plate], diag[plate] = resample_with_cycles(
                predicted[plate],
                self.field[plate],
                self.field_branches[plate],
                self.targets,
            )

        metrics = compute_all_metrics(
            residuals, per_branch, self.targets, observed=self.field
        )
        fitness = metrics["primary_total"]

        rid = self.db.insert_run(
            particle_id, self.opt.iter_count, status, time.time() - t0, fitness, ""
        )
        self.db.insert_parameters(rid, params)
        self._save_predicted_curves(run_sub, predicted)

        pred_rows = []
        for plate, df in predicted.items():
            for _, row in df.iterrows():
                pred_rows.append(
                    (
                        plate,
                        int(row["branch_id"]),
                        row["branch_kind"],
                        float(row["load"]),
                        float(row["displacement"]),
                    )
                )
        self.db.insert_predictions(rid, pred_rows)
        self.db.insert_metrics(rid, metrics["rows"])
        self._record_failure(rid, status, fail_info)

        if self.project["output"]["save_diagnostic_png_every_run"]:
            save_diagnostic_plot(
                run_sub / "diagnostic.png",
                predicted=predicted,
                field=self.field,
                field_branches=self.field_branches,
                per_branch=per_branch,
                diag=diag,
                run_label=f"p{particle_id:02d}_it{self.opt.iter_count:03d}",
                fitness=fitness,
            )

        self.cache.put(x, fitness)
        self._tick_streak(particle_id, failed=False)
        return fitness

    def _tick_streak(self, pid: int, failed: bool) -> None:
        if failed:
            self.fail_streak[pid] = self.fail_streak.get(pid, 0) + 1
        else:
            self.fail_streak[pid] = 0

    def run(self):
        self.plx = PlaxisConnector(self.project["plaxis"]).open()
        try:
            n_iter = self.pso_cfg["iterations"]["max"]
            for it in range(n_iter):
                particle_counter = {"pid": 0}

                def fitness_fn(x: np.ndarray) -> float:
                    particle_counter["pid"] += 1
                    return self._evaluate(x, particle_counter["pid"])

                gbest, gfit, fits = self.opt.step(fitness_fn)
                if self.pso_cfg["checkpoint"]["every_iter"]:
                    ckpt.save(self.opt.state(), self.run_dir / "checkpoint.pkl")
                gbest_dec = (
                    decode_vector(gbest, self.syms, self.profile)
                    if gbest is not None
                    else {}
                )
                self.db.append_swarm_history(
                    it,
                    float(gfit),
                    float(np.nanmean(fits)),
                    float(np.nanstd(fits)),
                    int(np.sum(~np.isfinite(fits))),
                    gbest_dec,
                )
                if self.opt.should_stop():
                    break
        finally:
            if self.plx is not None:
                self.plx.close()
