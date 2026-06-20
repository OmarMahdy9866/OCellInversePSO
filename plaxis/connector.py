"""PLAXIS Remote Scripting wrapper with heartbeat + auto-restart."""
from __future__ import annotations
import time
from typing import Dict, Any


class PlaxisConnector:
    """Wraps plxscripting connections. Resilient to dropped sessions."""
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.s_i = self.g_i = None         # input server, global object
        self.s_o = self.g_o = None         # output server, global object
        self._opened = False

    def open(self):
        from plxscripting.easy import new_server
        self.s_i, self.g_i = new_server(
            "localhost", self.cfg["scripting_port_input"],
            password=self.cfg["password"])
        self.s_o, self.g_o = new_server(
            "localhost", self.cfg["scripting_port_output"],
            password=self.cfg["password"])
        self.s_i.open(self.cfg["base_model"])
        self._opened = True
        return self

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
        self._opened = False