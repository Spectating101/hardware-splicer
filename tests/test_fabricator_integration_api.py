from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.fabrication_capability_registry import (
    FabricationCapabilityDescriptor,
    FabricationCapabilityRegistry,
)
from hardware_splicer.fabricator_integration_manifest import fabricator_integration_manifest
from hardware_splicer.fabricator_integration_workbench import FabricatorIntegrationWorkbench
from hardware_splicer.product_api import create_product_app


def test_fabricator_routes_are_discoverable_but_fail_closed_without_runtime(tmp_path):
    client = TestClient(create_product_app())
    response = client.get("/v1/fabricator/capabilities")
    assert response.status_code == 503
    assert response.json()["detail"]["type"] == "fabricator_runtime_unavailable"

    document = client.get("/openapi.json").json()
    assert "/v1/fabricator/capabilities" in document["paths"]
    assert "/v1/fabricator/kicad/{project_id}/verify" in document["paths"]
    assert "/v1/fabricator/machine-jobs/{analyzer_id}/dry-run" in document["paths"]


def test_configured_capability_registry_is_available_through_canonical_api():
    capabilities = FabricationCapabilityRegistry()
    capabilities.register(FabricationCapabilityDescriptor(
        operator_id="printer-a",
        kind="printer",
        display_name="Lab printer",
        capabilities=("additive_fabrication", "pla"),
        limits={"build_x_mm": 220},
    ))
    workbench = FabricatorIntegrationWorkbench(capabilities=capabilities)
    client = TestClient(create_product_app(fabricator_workbench=workbench))
    listed = client.get("/v1/fabricator/capabilities")
    assert listed.status_code == 200
    assert listed.json()["capabilities"][0]["operator_id"] == "printer-a"
    matched = client.post("/v1/fabricator/capabilities/match", json={
        "required_capabilities": ["additive_fabrication"],
        "kind": "printer",
        "numeric_minimums": {"build_x_mm": 200},
        "allow_simulated": False,
    })
    assert matched.status_code == 200
    assert matched.json()["matches"][0]["operator_id"] == "printer-a"


def test_dedicated_manifest_projects_only_canonical_bounded_routes():
    app = create_product_app()
    manifest = fabricator_integration_manifest(app)
    assert manifest["task"] == "fabricator_integrations"
    assert manifest["authority_contract"]["live_cnc_or_laser_motion"] is False
    assert manifest["authority_contract"]["mtconnect_is_read_only"] is True
    paths = {item["path"] for item in manifest["operations"]}
    assert "/v1/fabricator/kicad/{project_id}/verify" in paths
    assert "/v1/fabricator/mtconnect/{source_id}/current" in paths
    assert not any("credential" in path or "endpoint" in path for path in paths)
