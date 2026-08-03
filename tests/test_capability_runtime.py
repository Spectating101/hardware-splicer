from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hardware_splicer.capability_runtime import capability_report

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def _which(name: str) -> str | None:
    return "/opt/kicad/bin/kicad-cli" if name == "kicad-cli" else None


def _run(command, **kwargs):
    if command[0] == "/opt/kicad/bin/kicad-cli":
        return SimpleNamespace(returncode=0, stdout="9.0.9\n", stderr="")
    return SimpleNamespace(returncode=1, stdout="", stderr="not found")


def _missing_kicad_happy():
    return {
        "available": False,
        "root": None,
        "revision": None,
        "capabilities": [],
        "missing_capabilities": ["schematic", "pcb", "gerber"],
    }


def _capability(report: dict, capability_id: str) -> dict:
    return next(row for row in report["capabilities"] if row["id"] == capability_id)


def test_report_separates_catalog_runtime_and_project_truth() -> None:
    report = capability_report(
        environ={},
        which=_which,
        run=_run,
        kicad_happy_discover=_missing_kicad_happy,
    )

    kicad = _capability(report, "kicad-cli")
    assert kicad["status"] == "core"
    assert kicad["implementation_available"] is True
    assert kicad["runtime"] == {
        "discovered": True,
        "configured": True,
        "compatible": True,
        "path": "/opt/kicad/bin/kicad-cli",
        "command": "kicad-cli",
        "version": "9.0.9",
        "probe_error": None,
    }
    assert kicad["evidence"]["machine_tested"] is False
    assert kicad["evidence"]["project_used"] is False
    assert kicad["readiness"] == "ready"

    review = _capability(report, "kicad-happy")
    assert review["implementation_available"] is True
    assert review["runtime"]["discovered"] is False
    assert review["runtime"]["configured"] is False
    assert review["readiness"] == "missing_optional"

    assert report["definitions"]["configured"].startswith("Required local configuration")
    assert report["definitions"]["project_used"].startswith("At least one project-scoped")


def test_project_artifact_marks_use_and_successful_machine_execution(tmp_path: Path) -> None:
    compilation = tmp_path / "build_compilation"
    compilation.mkdir()
    artifact = compilation / "ENGINEERING_REVIEW.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "hardware_splicer.engineering_review.v1",
                "review_status": "review_required",
                "authority_ceiling": "observed",
            }
        ),
        encoding="utf-8",
    )

    report = capability_report(
        build_dir=tmp_path,
        environ={},
        which=_which,
        run=_run,
        kicad_happy_discover=lambda: {
            "available": True,
            "root": "/opt/kicad-happy",
            "revision": "abc123",
            "capabilities": ["schematic", "pcb", "gerber"],
            "missing_capabilities": [],
        },
    )

    review = _capability(report, "kicad-happy")
    assert review["runtime"]["discovered"] is True
    assert review["runtime"]["configured"] is True
    assert review["runtime"]["version"] == "abc123"
    assert review["evidence"]["project_used"] is True
    assert review["evidence"]["machine_tested"] is True
    assert review["evidence"]["artifacts"] == [str(artifact.resolve())]
    assert review["evidence"]["last_successful_run"] is not None
    assert review["readiness"] == "used_on_project"


def test_catalog_reference_and_planned_entries_do_not_imply_runtime_support() -> None:
    report = capability_report(
        environ={},
        which=lambda name: None,
        run=_run,
        kicad_happy_discover=_missing_kicad_happy,
    )

    schematic_ai = _capability(report, "schematic-ai")
    assert schematic_ai["status"] == "planned"
    assert schematic_ai["runtime"]["discovered"] is False
    assert schematic_ai["readiness"] == "planned"

    build123d = _capability(report, "build123d")
    if not build123d["runtime"]["discovered"]:
        assert build123d["readiness"] == "reference_only"


def test_product_api_exposes_capability_truth_in_openapi() -> None:
    client = TestClient(create_product_app())

    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "hardware_splicer.capability_report.v1"
    assert isinstance(body["capabilities"], list)
    assert any(row["id"] == "manufacturing-reconciliation" for row in body["capabilities"])

    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/v1/capabilities" in paths
