"""A declared assembly change cannot silently reuse original-upload ERC/DRC."""
import base64
import json
from pathlib import Path

import pytest

from hardware_splicer.ai_project_tool_executor import execute_ai_project_action_preview
from hardware_splicer.engineering_source_ingestion import ingest_engineering_source
from hardware_splicer.project_part_substitutions import assess_project_substitution, propose_project_substitution
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("action_type,gate", [("run_drc", "drc"), ("run_erc", "erc")])
def test_accepted_substitution_requires_regenerated_native_design_without_rebasing_history(tmp_path, monkeypatch, action_type, gate):
    store = ProjectStore(tmp_path / "projects")
    native = ROOT / "hardware/reference_designs/spi_flash_adapter_v1"
    sources = []
    for suffix in (".kicad_pcb", ".kicad_sch", ".kicad_pro"):
        path = native / ("spi_flash_adapter_v1" + suffix)
        source = ingest_engineering_source({"project_id": "replace-demo", "filename": path.name,
            "content_base64": base64.b64encode(path.read_bytes()).decode()}, project_root=store.root)
        sources.append(source.source_descriptor)
    store.save("replace-demo", {"projectId": "replace-demo", "engineeringSources": sources,
        "machineProject": {"project_id": "replace-demo", "name": "Replacement fixture", "purpose": "Declared simulation only"}})
    specification = json.loads((ROOT / "examples/part_substitution/telemetry-sensor-replacement.json").read_text())
    assessment = assess_project_substitution(store, "replace-demo", expected_revision=1, specification=specification)
    proposal = propose_project_substitution(store, "replace-demo", assessment["assessment"]["assessment_id"], expected_revision=1)
    ProjectReviewStore(store).decide("replace-demo", proposal["review"]["review_id"], decision="accepted", actor="test-engineer")
    assert store.load("replace-demo")["revision"] == 2
    assert store.load("replace-demo")["snapshot"]["engineeringSources"] == sources
    calls = []

    def inspect_originals(project_id, supplied_sources, **kwargs):
        calls.append((project_id, supplied_sources))
        return {"project_context": "source_bundle_sibling_files_present", "source_set_sha256": "sha256:" + "a" * 64,
                "software_checks": {gate: {"check_executed": True, "status": "completed", "rule_finding_count": 3}}}

    monkeypatch.setattr("hardware_splicer.ai_project_tool_executor.analyze_registered_project_bundle", inspect_originals)
    session = {"session_id": "session-check", "project_revision": 2}

    def action(revision):
        return {"action_id": f"check-{gate}-revision-{revision}", "action_type": action_type,
                "project_revision": revision, "status": "accepted",
                "decision": {"decision": "accepted", "reviewer": "test-engineer",
                             "decided_at": "2026-11-18T12:00:00Z", "executed": False}}

    revised = execute_ai_project_action_preview(store, "replace-demo", session, action(2))
    assert revised["status"] == "failed"
    assert "no regenerated native electrical design" in revised["error"]["message"]
    assert not calls
    assert not revised["summary"].get("check_executed")
    historical = execute_ai_project_action_preview(store, "replace-demo", session, action(1))
    assert historical["status"] == "succeeded"
    assert historical["summary"]["check_executed"] is True
    assert calls == [("replace-demo", sources)]
    assert store.load("replace-demo")["revision"] == 2
