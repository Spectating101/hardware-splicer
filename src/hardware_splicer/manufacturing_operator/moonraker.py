"""Moonraker/Klipper read-only adapter for the protocol-neutral HS fleet.

Remote motion, heating, print-start, file upload and arbitrary G-code are
deliberately not exposed. This adapter only identifies controller protocol
and reads the Klipper print state from Moonraker's documented APIs.
"""
from __future__ import annotations

import httpx

from .fleet import MachineCapabilities, MachineObservation
from .octoprint import ManufacturingRefusal, validate_local_printer_url


class MoonrakerDriver:
    def __init__(
        self, *,
        base_url: str,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        base = validate_local_printer_url(base_url)
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._http = httpx.Client(
            base_url=base, headers=headers,
            follow_redirects=False, trust_env=False,
            timeout=httpx.Timeout(10.0, connect=3.0),
            transport=transport,
        )

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def inspect(self, machine_id: str) -> MachineObservation:
        info_response = self._http.get("/server/info")
        info_response.raise_for_status()
        info = info_response.json()
        if not isinstance(info, dict) or not isinstance(info.get("result"), dict):
            raise ManufacturingRefusal("Not a recognized Moonraker controller")
        result = info["result"]
        if not isinstance(result.get("klippy_state"), str):
            raise ManufacturingRefusal("Moonraker did not report Klipper status")
        query_response = self._http.get("/printer/objects/query", params={"print_stats": ""})
        query_response.raise_for_status()
        query = query_response.json()
        if not isinstance(query, dict) or not isinstance(query.get("result"), dict):
            raise ManufacturingRefusal("Printer object response missing")
        status = query["result"].get("status")
        stats = status.get("print_stats") if isinstance(status, dict) else None
        if not isinstance(stats, dict) or not isinstance(stats.get("state"), str):
            raise ManufacturingRefusal("Moonraker has no recognized print_stats")
        states = {
            "standby": "idle", "complete": "idle", "cancelled": "idle",
            "printing": "printing", "paused": "paused", "error": "error",
        }
        state = states.get(stats["state"], "unknown")
        if result["klippy_state"] != "ready":
            state = "offline"
        return MachineObservation(
            machine_id=machine_id, controller="moonraker",
            state=state, controller_protocol_verified=True,
            capabilities=MachineCapabilities(
                machine_type="fdm", file_formats=(".gcode",),
                can_read_status=True, can_monitor_job=True,
                can_stage_file=False,
            ),
            detail=f"Klipper status: {result['klippy_state']}",
        )
