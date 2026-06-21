"""PLAXIS Remote Scripting wrapper with heartbeat + auto-restart."""
from __future__ import annotations
import socket
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, Any


class PlaxisConnector:
    """Wraps plxscripting connections. Resilient to dropped sessions."""
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.s_i = self.g_i = None         # input server, global object
        self.s_o = self.g_o = None         # output server, global object
        self._opened = False
        self._staged_model_dir: Path | None = None
        self._staged_model_path: Path | None = None

    def attach_input(self):
        if self.s_i is None or self.g_i is None:
            from plxscripting.easy import new_server

            self.s_i, self.g_i = new_server(
                "localhost",
                self.cfg["scripting_port_input"],
                password=self.cfg["password"],
            )
        return self

    def connect_output(self):
        if self.s_o is None or self.g_o is None:
            from plxscripting.easy import new_server

            self.s_o, self.g_o = new_server(
                "localhost",
                self.cfg["scripting_port_output"],
                password=self.cfg["password"],
            )
        return self

    def disconnect_output(self):
        if self.s_o is not None:
            try:
                self.s_o.close()
            except Exception:
                pass
        self.s_o = self.g_o = None
        return self

    def _stage_base_model(self) -> str:
        src_model = Path(self.cfg["base_model"]).resolve()
        if not src_model.exists():
            raise FileNotFoundError(f"PLAXIS base model not found: {src_model}")

        src_bundle = src_model.with_name(f"{src_model.stem}.p3dat")
        staged_root = Path(tempfile.mkdtemp(prefix="ocell_plaxis_model_"))
        staged_model = staged_root / src_model.name
        shutil.copy2(src_model, staged_model)
        if src_bundle.exists():
            shutil.copytree(src_bundle, staged_root / src_bundle.name)

        self._staged_model_dir = staged_root
        self._staged_model_path = staged_model
        return str(staged_model)

    def _cleanup_staged_model(self):
        if self._staged_model_dir is not None:
            try:
                shutil.rmtree(self._staged_model_dir, ignore_errors=True)
            except Exception:
                pass
        self._staged_model_dir = None
        self._staged_model_path = None

    def open_model(self):
        self.attach_input()
        staged_model = self._stage_base_model()
        self.s_i.open(staged_model)
        self._opened = True
        return self

    def open(self):
        if self._opened:
            return self

        try:
            self.open_model()
            return self
        except Exception:
            self.close()
            raise

    @staticmethod
    def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def wait_for_output(self, timeout_s: float = 60.0, poll_s: float = 1.0) -> bool:
        deadline = time.time() + timeout_s
        host = "127.0.0.1"
        port = int(self.cfg["scripting_port_output"])
        while time.time() < deadline:
            if self._port_open(host, port):
                return True
            time.sleep(poll_s)
        return False

    def open_output_view(self, phase=None, timeout_s: float = 60.0):
        self.attach_input()
        if phase is None:
            phase = self.g_i.Phases[-1]
        self.disconnect_output()
        self.g_i.view(phase)
        if not self.wait_for_output(timeout_s=timeout_s):
            raise RuntimeError(
                f"PLAXIS Output scripting server did not come up on port {self.cfg['scripting_port_output']} "
                f"after viewing phase {getattr(phase, 'Name', phase)!r}."
            )
        return self.connect_output()

    def heartbeat(self) -> bool:
        try:
            _ = self.g_i.echo("ping")
            return True
        except Exception:
            return False

    def restart(self):
        try: self.close()
        except Exception: pass
        time.sleep(2.0)
        self.open()

    def close(self):
        if self.s_i is not None:
            try: self.s_i.close()
            except Exception: pass
        self.disconnect_output()
        self.s_i = self.g_i = None
        self._opened = False
        self._cleanup_staged_model()
