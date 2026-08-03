from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.manufacturing_reconciliation import (
    apply_manufacturing_reconciliation,
    reconcile_bom_to_build_graph,
)
from hardware_splicer.project_package import write_project_package_artifacts


def _graph() -> dict:
    return {
        "nodes": [
            {"id": "servo-pan", "moduleId": "sg90"},
            {"id": "servo-tilt", "moduleId": "sg90"},
            {"id": "controller", "moduleId": "esp32-devkit"},
        ],
        "wires": [],
    }


def test_reconciliation_accepts_aggregate_bom_quantity() -> None:
    report = reconcile_bom_to_build_graph(
        _graph(),
        [
            {"module_id": "sg90", "qty": 2},
            {"module_id": "esp32-devkit", "qty": 1},
        ],
    )

    assert report["status"] == "clear"
    assert report["package_ready"] is True
    assert report["graph_instance_count"] == 3
    assert report["bom_quantity_count"] == 3
    assert report["graph_counts"] == {"esp32-devkit": 1, "sg90": 2}
    assert report["bom_counts"] == {"esp32-devkit": 1, "sg90": 2}
    assert report["blockers"] == []


def test_reconciliation_blocks_quantity_mismatch_and_missing_module() -> None:
    report = reconcile_bom_to_build_graph(
        _graph(),
        [{"module_id": "sg90", "qty": 1}],
    )

    assert report["status"] == "blocked"
    mismatches = {
        row["module_id"]: row
        for row in report["blockers"]
        if row["code"] == "bom_graph_quantity_mismatch"
    }
    assert mismatches["sg90"]["expected_graph_instances"] == 2
    assert mismatches["sg90"]["actual_bom_quantity"] == 1
    assert mismatches["esp32-devkit"]["expected_graph_instances"] == 1
    assert mismatches["esp32-devkit"]["actual_bom_quantity"] == 0


def test_bom_only_items_are_review_warnings_not_false_blockers() -> None:
    report = reconcile_bom_to_build_graph(
        _graph(),
        [
            {"module_id": "sg90", "qty": 2},
            {"module_id": "esp32-devkit", "qty": 1},
            {"module_id": "m3-fastener", "qty": 8},
        ],
    )

    assert report["status"] == "clear"
    warning = next(row for row in report["warnings"] if row["code"] == "bom_only_module")
    assert warning["module_id"] == "m3-fastener"
    assert warning["quantity"] == 8


def test_invalid_quantity_and_node_identity_fail_closed() -> None:
    graph = {
        "nodes": [
            {"id": "n1", "moduleId": "sg90"},
            {"id": "n1", "moduleId": "esp32-devkit"},
        ]
    }
    report = reconcile_bom_to_build_graph(
        graph,
        [
            {"ref": "U1", "node_id": "n1", "module_id": "sg90", "qty": 0},
            {"ref": "U1", "node_id": "missing", "module_id": "esp32-devkit", "qty": 1.5},
        ],
    )

    codes = {row["code"] for row in report["blockers"]}
    assert report["status"] == "blocked"
    assert "duplicate_graph_node_id" in codes
    assert "invalid_bom_quantity" in codes


def test_missing_graph_is_explicitly_not_evaluable() -> None:
    report = reconcile_bom_to_build_graph(
        {},
        [{"module_id": "sg90", "qty": 2}],
    )

    assert report["status"] == "not_evaluable"
    assert report["package_ready"] is None
    assert report["warnings"][0]["code"] == "build_graph_missing"


def test_blocking_reconciliation_downgrades_package_not_historical_evidence() -> None:
    package = {
        "bom": {"lines": [{"module_id": "sg90", "qty": 1}]},
        "gates": {
            "verdict": "POWER_ON_AUTHORIZED",
            "build_ready": True,
            "fabrication_ready": True,
            "power_on_authorized": True,
            "blockers": [],
        },
    }

    reconciled = apply_manufacturing_reconciliation(package, build_graph=_graph())

    assert reconciled["gates"]["verdict"] == "BLOCKED"
    assert reconciled["gates"]["build_ready"] is False
    assert reconciled["gates"]["fabrication_ready"] is False
    assert reconciled["gates"]["power_on_authorized"] is True
    assert reconciled["gates"]["manufacturing_reconciliation_status"] == "blocked"
    assert reconciled["gates"]["package_ready"] is False


def test_product_package_artifacts_are_rewritten_with_blocking_reconciliation(
    tmp_path: Path,
) -> None:
    compilation = tmp_path / "build_compilation"
    compilation.mkdir()
    (compilation / "build_graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "servo-pan", "moduleId": "sg90"},
                    {"id": "servo-tilt", "moduleId": "sg90"},
                ],
                "wires": [],
            }
        ),
        encoding="utf-8",
    )
    (compilation / "BOM.json").write_text(
        json.dumps(
            {
                "schema_version": "hardware_splicer.bom.v1",
                "lines": [{"module_id": "sg90", "qty": 1}],
            }
        ),
        encoding="utf-8",
    )

    output = write_project_package_artifacts(
        tmp_path,
        result={
            "ok": True,
            "project_name": "quantity mismatch",
            "design_quality_gate": {
                "build_ready": True,
                "fabrication_ready": True,
            },
        },
        source="test",
    )

    package = output["package"]
    persisted = json.loads((tmp_path / "PROJECT_PACKAGE.json").read_text(encoding="utf-8"))
    page = (tmp_path / "PROJECT_PAGE.md").read_text(encoding="utf-8")

    assert package["manufacturing_reconciliation"]["status"] == "blocked"
    assert package["gates"]["verdict"] == "BLOCKED"
    assert persisted["manufacturing_reconciliation"] == package["manufacturing_reconciliation"]
    assert persisted["gates"]["package_ready"] is False
    assert "**Verdict:** `BLOCKED`" in page
    assert any("compiled build graph contains 2" in row for row in persisted["gates"]["blockers"])
