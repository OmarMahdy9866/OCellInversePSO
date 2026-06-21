from __future__ import annotations

import shlex
import socket
import subprocess
import time
from pathlib import Path

import yaml

from models.hss import HSS, HSS_PLAXIS_KEYS
from plaxis.connector import PlaxisConnector
from plaxis.material_writer import _find_material, write_layer_materials
from plaxis.node_resolver import NodeResolver
from plaxis.result_extractor import extract_ocell_results
from plaxis.runner import run_staged_phases


ROOT = Path(__file__).resolve().parents[1]
PROJECT_CFG = yaml.safe_load((ROOT / "config" / "project.yaml").read_text(encoding="utf-8"))
PROFILE_CFG = yaml.safe_load((ROOT / "config" / "soil_profile.yaml").read_text(encoding="utf-8"))

PLAXIS_CFG = PROJECT_CFG["plaxis"]
OCELL_CFG = PROJECT_CFG["ocell"]
RESILIENCE_CFG = PROJECT_CFG["resilience"]

HOST = "127.0.0.1"
PORT_I = int(PLAXIS_CFG["scripting_port_input"])
PORT_O = int(PLAXIS_CFG["scripting_port_output"])
PASSWORD = PLAXIS_CFG["password"]
PHASE_NAMES = [str(name) for name in PLAXIS_CFG["phase_names"]]
CALC_PHASE_NAMES = [name for name in PHASE_NAMES if name.lower() != "initialphase"]
SMOKE_DIR = ROOT / "notebooks" / "_smoke_outputs"
SMOKE_DIR.mkdir(parents=True, exist_ok=True)
REVERSE_HSS_KEYS = {v: k for k, v in HSS_PLAXIS_KEYS.items()}


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout_s: float = 30.0, poll_s: float = 1.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if port_open(host, port):
            return True
        time.sleep(poll_s)
    return False


def derive_output_exe(input_exe: str) -> str:
    path = Path(input_exe)
    name = path.name.replace("Input.exe", "Output.exe").replace("Input", "Output")
    return str(path.with_name(name))


def baseline_params_from_p3d() -> dict:
    material_lines = {}
    for raw_line in Path(PLAXIS_CFG["base_model"]).resolve().read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("_soilmat"):
            continue
        tokens = shlex.split(line)
        if len(tokens) < 3:
            continue
        pairs = dict(zip(tokens[1::2], tokens[2::2]))
        ident = pairs.get("Identification")
        if ident:
            material_lines[ident] = pairs

    params = {}
    for layer in PROFILE_CFG["layers"]:
        mat_id = layer["plaxis_material_id"]
        pairs = material_lines.get(mat_id)
        if not pairs:
            raise KeyError(f"Could not find baseline material {mat_id!r} in {PLAXIS_CFG['base_model']}")
        layer_params = {}
        for plx_key, our_key in REVERSE_HSS_KEYS.items():
            if plx_key in pairs:
                layer_params[our_key] = float(pairs[plx_key])
        fixed_cfg = layer.get("fixed", {})
        if "psi" not in layer_params and "psi" in fixed_cfg:
            layer_params["psi"] = float(fixed_cfg["psi"]["value"])
        if "pref" not in layer_params and "pref" in fixed_cfg:
            layer_params["pref"] = float(fixed_cfg["pref"]["value"])
        if "Rf" not in layer_params and "Rf" in fixed_cfg:
            layer_params["Rf"] = float(fixed_cfg["Rf"]["value"])
        if "Eur_ref" not in layer_params and "E50_ref" in layer_params:
            layer_params["Eur_ref"] = 3.0 * float(layer_params["E50_ref"])
        params[layer["name"]] = layer_params
    return params


def main():
    if not port_open(HOST, PORT_I):
        raise RuntimeError(
            f"PLAXIS Input scripting server is not reachable on {HOST}:{PORT_I}. "
            "Open the base model in PLAXIS Input first."
        )

    plx = PlaxisConnector(PLAXIS_CFG).attach_input()

    input_phase_names = [str(ph.Name) for ph in plx.g_i.Phases[:]]
    material_checks = {
        layer["plaxis_material_id"]: (_find_material(plx.g_i, layer["plaxis_material_id"]) is not None)
        for layer in PROFILE_CFG["layers"]
    }

    print("Input attached    : True")
    print(f"Input phases      : {input_phase_names}")
    print(f"Expected phases   : {PHASE_NAMES}")
    print(f"Material checks   : {material_checks}")

    missing_phases = [name for name in PHASE_NAMES if name not in input_phase_names]
    missing_materials = [name for name, ok in material_checks.items() if not ok]
    if missing_phases:
        raise RuntimeError(f"Configured phases missing in PLAXIS Input: {missing_phases}")
    if missing_materials:
        raise RuntimeError(f"Configured materials missing in PLAXIS Input: {missing_materials}")

    params = baseline_params_from_p3d()
    print(f"Smoke params       : {params}")
    write_layer_materials(plx, params, PROFILE_CFG, HSS())
    print("Material write     : baseline HSS parameters assigned successfully")

    smoke_log_path = SMOKE_DIR / "attached_run_smoke.log"
    run_log = run_staged_phases(
        plx,
        phase_names=PHASE_NAMES,
        timeout_min=int(RESILIENCE_CFG["timeout_min_per_run"]),
        log_path=smoke_log_path,
    )
    print("Run log           :")
    print(yaml.safe_dump(run_log, sort_keys=False).strip())
    print(f"Run log path      : {smoke_log_path}")

    if not run_log["phases_run"]:
        raise RuntimeError("No PLAXIS phases were completed.")
    if run_log.get("partial"):
        raise RuntimeError(
            "PLAXIS phase run ended partial before a viewable result phase was available: "
            + "; ".join(run_log.get("errors", []))
        )

    last_phase_name = run_log["last_phase"] or PHASE_NAMES[-1]
    last_phase = next(ph for ph in plx.g_i.Phases[:] if str(ph.Name) == last_phase_name)

    if not port_open(HOST, PORT_O):
        output_exe = derive_output_exe(PLAXIS_CFG["exe_path"])
        subprocess.Popen(
            [output_exe, f"--AppServerPassword={PASSWORD}", f"--AppServerPort={PORT_O}"],
            shell=False,
        )
        print(f"Output launch     : started {output_exe}")
        if not wait_for_port(HOST, PORT_O, timeout_s=30.0):
            raise RuntimeError(f"PLAXIS Output scripting server did not come up on {HOST}:{PORT_O}")
    else:
        print("Output launch     : already running")

    plx.g_i.view(last_phase)
    print(f"View phase        : requested output view for {last_phase_name}")
    time.sleep(5.0)

    plx.connect_output()
    output_phase_names = [str(ph.Name) for ph in plx.g_o.Phases[:]]
    resolver = NodeResolver(plx.g_o)
    upper = resolver.resolve(OCELL_CFG["upper_node"])
    lower = resolver.resolve(OCELL_CFG["lower_node"])

    print(f"Output phases     : {output_phase_names}")
    print(f"Upper node        : {upper}")
    print(f"Lower node        : {lower}")

    predicted = extract_ocell_results(plx, CALC_PHASE_NAMES, OCELL_CFG)
    for plate in ("upper", "lower"):
        df = predicted[plate]
        print(
            f"{plate.title()} curve       : rows={len(df)}, "
            f"branch_ids={sorted(df['branch_id'].unique())}, "
            f"branch_kinds={sorted(df['branch_kind'].unique())}"
        )

    print("Full attached-run diagnostic completed successfully.")


if __name__ == "__main__":
    main()
