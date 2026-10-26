"""Read-only protocol recognition for operator-enrolled local machines.

HS never searches arbitrary subnets or invents network destinations.
This selects a driver based on a verified controller handshake, not a brand.
"""
from __future__ import annotations

import httpx

from .fleet import OctoPrintDriver
from .moonraker import MoonrakerDriver
from .octoprint import ManufacturingRefusal, OctoPrintOperator, validate_local_printer_url


def connect_enrolled_controller(
    *,
    base_url: str,
    api_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
):
    """Select a driver for a locally configured endpoint, or refuse safely.

    Protocol identification proves which API responded, not the identity,
    hardware safety, physical presence or support for its exact printer model.
    """
    base = validate_local_printer_url(base_url)
    headers = {"X-Api-Key": api_key} if api_key else {}
    with httpx.Client(
        base_url=base, headers=headers,
        timeout=httpx.Timeout(5.0, connect=2.0),
        follow_redirects=False, trust_env=False, transport=transport,
    ) as client:
        try:
            response = client.get("/api/version")
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, dict) and str(result.get("text", "")).startswith("OctoPrint "):
                    if not api_key:
                        raise ManufacturingRefusal("OctoPrint controller requires local API key")
                    return OctoPrintDriver(OctoPrintOperator(
                        base_url=base, api_key=api_key, transport=transport,
                    ))
        except ManufacturingRefusal:
            raise
        except (httpx.RequestError, ValueError):
            pass
        try:
            response = client.get("/server/info")
            if response.status_code == 200:
                result = response.json()
                info = result.get("result") if isinstance(result, dict) else None
                if (isinstance(info, dict) and isinstance(info.get("klippy_state"), str)
                    and isinstance(info.get("moonraker_version"), str)):
                    return MoonrakerDriver(
                        base_url=base, api_key=api_key, transport=transport,
                    )
        except (httpx.RequestError, ValueError):
            pass
    raise ManufacturingRefusal("Enrolled endpoint is not a supported controller API")
