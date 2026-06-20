"""SQLite layer for PSO state, params, predictions, metrics, failures."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Iterable
import json
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    particle_id   INTEGER NOT NULL,
    iteration     INTEGER NOT NULL,
    status        TEXT NOT NULL,              -- ok|failed|partial|cached|rejected
    walltime_s    REAL,
    fitness       REAL,
    timestamp     TEXT DEFAULT CURRENT_TIMESTAMP,
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_iter ON runs(iteration);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

CREATE TABLE IF NOT EXISTS parameters (
    run_id        INTEGER,
    layer         TEXT,
    param_name    TEXT,
    value         REAL,
    PRIMARY KEY (run_id, layer, param_name),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id        INTEGER,
    plate         TEXT,                       -- 'upper' | 'lower'
    branch_id     INTEGER,
    branch_kind   TEXT,                       -- 'loading' | 'unloading' | 'reloading'
    load          REAL,
    displacement  REAL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_pred_run ON predictions(run_id);

CREATE TABLE IF NOT EXISTS metrics (
    run_id        INTEGER,
    metric_name   TEXT,                       -- nrmse|rmse|mae|huber|loglik
    scope         TEXT,                       -- 'total' | plate | 'branch_k_plate'
    value         REAL,
    PRIMARY KEY (run_id, metric_name, scope),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS failures (
    run_id        INTEGER,
    phase         TEXT,
    reason        TEXT,
    last_step     REAL,
    detail_json   TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS swarm_history (
    iteration     INTEGER PRIMARY KEY,
    gbest_fit     REAL,
    mean_fit      REAL,
    std_fit       REAL,
    n_failed      INTEGER,
    gbest_json    TEXT,
    timestamp     TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class RunDB:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path, isolation_level=None, timeout=30.0)
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA synchronous=NORMAL;")
        return c

    # ---------- writes ----------
    def insert_run(self, particle_id: int, iteration: int, status: str,
                   walltime_s: float, fitness: Optional[float],
                   notes: str = "") -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO runs(particle_id,iteration,status,walltime_s,fitness,notes)"
                " VALUES (?,?,?,?,?,?)",
                (particle_id, iteration, status, walltime_s,
                 None if fitness is None else float(fitness), notes))
            return int(cur.lastrowid)

    def insert_parameters(self, run_id: int,
                          params_by_layer: Dict[str, Dict[str, float]]):
        rows = [(run_id, layer, k, float(v))
                for layer, d in params_by_layer.items() for k, v in d.items()]
        with self._conn() as c:
            c.executemany("INSERT OR REPLACE INTO parameters VALUES (?,?,?,?)", rows)

    def insert_predictions(self, run_id: int, rows: Iterable[tuple]):
        # rows = [(plate, branch_id, branch_kind, load, disp), ...]
        with self._conn() as c:
            c.executemany(
                "INSERT INTO predictions(run_id,plate,branch_id,branch_kind,load,displacement)"
                " VALUES (?,?,?,?,?,?)",
                [(run_id, *r) for r in rows])

    def insert_metrics(self, run_id: int, rows: Iterable[tuple]):
        # rows = [(metric_name, scope, value), ...]
        with self._conn() as c:
            c.executemany(
                "INSERT OR REPLACE INTO metrics VALUES (?,?,?,?)",
                [(run_id, n, s, float(v)) for n, s, v in rows])

    def insert_failure(self, run_id: int, phase: str, reason: str,
                       last_step: Optional[float], detail: Optional[dict]):
        with self._conn() as c:
            c.execute("INSERT INTO failures VALUES (?,?,?,?,?)",
                      (run_id, phase, reason,
                       None if last_step is None else float(last_step),
                       json.dumps(detail) if detail else None))

    def append_swarm_history(self, iteration: int, gbest_fit: float,
                             mean_fit: float, std_fit: float,
                             n_failed: int, gbest: dict):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO swarm_history VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (iteration, gbest_fit, mean_fit, std_fit, n_failed, json.dumps(gbest)))

    # ---------- reads ----------
    def to_dataframe(self, table: str) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql(f"SELECT * FROM {table}", c)