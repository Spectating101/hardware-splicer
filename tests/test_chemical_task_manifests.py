from __future__ import annotations

from hardware_splicer.mcp_backend_gateway import task_operation_manifest
from hardware_splicer.product_api import create_product_app


def test_canonical_chemical_task_manifests_are_wired():
    app = create_product_app()
    paths = {
        "chemical_material_review": "materials/evidence-check",
        "chemical_process_review": "gas/state",
        "chemical_battery_model_review": "battery/discharge",
    }
    for task, expected_path in paths.items():
        manifest = task_operation_manifest(task, app=app)
        assert manifest["operations"], task
        assert any(expected_path in row["path"] for row in manifest["operations"])
        assert not manifest["authority_contract"]["backend_gates_bypassed"]
        assert not manifest["authority_contract"]["automatic_execution"]
