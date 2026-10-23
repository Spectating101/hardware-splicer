"""Reproduce real KiCad -> upstream converter -> existing HS API.

Run AFTER npm run convert with a user-authorized source KiCad file.
Fail loudly when components survive but connectivity is lost: never call
this full interoperability merely because the API responds HTTP 200.
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app

docs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
with TestClient(create_product_app()) as client:
    response = client.post(
        "/v1/interchange/circuit-json/inspect",
        json={"documents": docs, "source_label": "upstream-kicad-conversion"},
    )
response.raise_for_status()
data = response.json()
diagnostics = data.get("diagnostics") or {}
report = {
    "http": response.status_code,
    "authority": data.get("authority"),
    "status": data.get("status"),
    "upstream_source_components": diagnostics.get("source_component_count"),
    "hs_imported_components": diagnostics.get("imported_component_count"),
    "upstream_source_nets": diagnostics.get("source_net_count"),
    "hs_imported_nets": diagnostics.get("imported_net_count"),
    "upstream_legacy_schematic_traces": diagnostics.get("legacy_schematic_trace_count"),
    "compilable": data.get("compilable"),
    "interoperability_pass": (
        diagnostics.get("source_component_count") == diagnostics.get("imported_component_count")
        and (not diagnostics.get("source_net_count") or bool(diagnostics.get("imported_net_count")))
        and bool(data.get("compilable"))
    ),
}
print(json.dumps(report, indent=2))
if not report["interoperability_pass"]:
    print("Connectivity or compile readiness is missing; this is an integration FAILURE.",file=sys.stderr)
    sys.exit(2)
