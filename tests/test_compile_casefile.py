"""Compile failure casefiles (gate 5.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.compile_casefile import SCHEMA_VERSION, write_compile_casefile
from hardware_splicer.pcb.geometry_compile import compile_graph_to_artifacts


def test_write_compile_casefile_roundtrip_fields(tmp_path: Path) -> None:
    path = write_compile_casefile(
        tmp_path,
        build_id="test_build",
        error="unit_test",
        stage="test",
        graph={"nodes": [], "wires": []},
        intake={"goal": "demo"},
    )
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["build_id"] == "test_build"
    assert data["error"] == "unit_test"
    assert data["stage"] == "test"
    assert data["intake"]["goal"] == "demo"


def test_graph_stage_failure_writes_casefile(tmp_path: Path) -> None:
    """Unknown catalog id → empty graph → COMPILE_CASEFILE.json."""
    from hardware_splicer.compile_stages import run_graph_stage_node

    result = run_graph_stage_node(
        "missing_catalog_build",
        tmp_path,
        splice_plan={"target": {"recommended_build_id": "___no_such_build___"}},
    )
    assert result.ok is False
    casefile = tmp_path / "COMPILE_CASEFILE.json"
    assert casefile.is_file()
    body = json.loads(casefile.read_text(encoding="utf-8"))
    assert body.get("graph") is not None
    assert body.get("splice_plan")


def test_empty_graph_writes_casefile(tmp_path: Path) -> None:
    compile_graph_to_artifacts("empty_test", tmp_path, {"nodes": [], "wires": []})
    quality_path = tmp_path / "DESIGN_QUALITY.json"
    assert quality_path.is_file()
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality.get("build_ready") is False
