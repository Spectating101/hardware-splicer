"""Validate real upstream Circuit JSON in the existing Hardware Splicer API.

Requires the HS package installed in this Python environment. This does not
authorize fabrication: an 'inspect' response is a proposal/review assessment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("generated-circuit.json")
    docs = json.loads(path.read_text(encoding="utf-8"))
    with TestClient(create_product_app()) as client:
        inspected = client.post("/v1/interchange/circuit-json/inspect", json={
            "source_label": f"tscircuit:{path.name}",
            "documents": docs,
        })
        inspected.raise_for_status()
        report = inspected.json()
        electrical = client.post("/v1/interchange/circuit-json/electrical-design", json={
            "source_label": f"tscircuit:{path.name}",
            "project_id": "upstream-proof-only",
            "documents": docs,
        })
        electrical.raise_for_status()
        identity = electrical.json()

    assert report.get("authority") == "proposed", report
    assert report["diagnostics"]["imported_component_count"] == len([
        row for row in docs if row["type"] == "source_component"
    ])
    assert identity["summary"]["component_count"] == report["diagnostics"]["imported_component_count"]
    assert identity["authority"] == "proposed"
    print(json.dumps({
        "upstream_document_count": len(docs),
        "hs_status": report["status"],
        "hs_compilable": report["compilable"],
        "component_count": identity["summary"]["component_count"],
        "net_count": identity["summary"]["net_count"],
        "erc_issue_count": identity["summary"]["erc_issue_count"],
        "unresolved_identity_count": identity["summary"]["unresolved_identity_count"],
        "authority": identity["authority"],
        "note": "Source graph imported and inspected, but no DRC/bench/fabrication authorization.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
