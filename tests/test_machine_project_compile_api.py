from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_compile_spec_projection_endpoint_uses_existing_machine_assets(tmp_path: Path) -> None:
    spec = json.loads(
        (REPO_ROOT / "examples" / "hardware_splicer_robotics_platform_rover_demo.json").read_text(
            encoding="utf-8"
        )
    )
    app = create_product_app(project_store=ProjectStore(tmp_path))

    with TestClient(app) as client:
        response = client.post("/v1/machine-projects/from-compile-spec", json={"spec": spec})

    assert response.status_code == 200
    body = response.json()
    project = body["project"]
    assert project["project_id"] == "robotics_platform_rover_demo"
    assert {row["subsystem_id"] for row in project["subsystems"]} >= {
        "electrical-system",
        "mechanical-system",
        "robotics-system",
        "firmware-control",
    }
    assert project["interfaces"] == []
    assert {row["code"] for row in body["traceability_issues"]} >= {
        "unverified_requirement"
    }
