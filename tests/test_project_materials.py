"""Materials mean exact identities, bounded quantities and dated inventory."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.project_materials import (
    InventoryCapture, MaterialRequirement, assess_project_materials,
    load_material_assessment, material_csv, reconcile_materials,
)
from hardware_splicer.project_materials_api import create_project_materials_router
from hardware_splicer.project_store import CorruptProject, ProjectStore, RevisionConflict

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def requirement(**values):
    return MaterialRequirement.model_validate({
        "material_id": "motor", "description": "F1404 KV2900", "manufacturer": "T-Hobby",
        "mpn": "F1404-KV2900", "quantity": "4", **values})


def inventory(**values):
    return InventoryCapture.model_validate({
        "source": "declared", "captured_at": NOW.isoformat(),
        "lots": [{"stock_id": "bin-1", "manufacturer": "T-Hobby", "mpn": "F1404-KV2900",
                  "quantity": "3", "allocated": "1", "condition": "ok"}], **values})


def test_reserved_damaged_unknown_and_different_units_do_not_cover_missing_materials():
    capture = inventory()
    original = capture.lots[0].model_dump(mode="json")
    capture = inventory(lots=[
        original,
        {**original, "stock_id": "damaged", "quantity": "100", "condition": "damaged"},
        {**original, "stock_id": "unknown", "quantity": "100", "condition": "unchecked"},
        {**original, "stock_id": "wrong-unit", "quantity": "100", "unit": "pack"},
        {**original, "stock_id": "different-mpn", "mpn": "F1404-KV3800", "quantity": "100"},
    ])
    result = reconcile_materials([requirement()], capture, evaluated_at=NOW)
    line = result["lines"][0]
    assert Decimal(line["available_for_plan"]) == 2
    assert Decimal(line["shortage"]) == 2 and line["action"] == "buy"
    assert {row["reason"] for row in line["excluded_lots"]} == {"condition_damaged", "condition_unchecked", "unit_mismatch"}
    assert result["stock_reserved"] is False and result["purchase_ready"] is False


def test_one_stock_lot_cannot_cover_two_bom_lines_twice():
    result = reconcile_materials([requirement(quantity=2), requirement(material_id="spare", quantity=2)], inventory(), evaluated_at=NOW)
    assert [Decimal(row["shortage"]) for row in result["lines"]] == [0, 2]


def test_additional_material_specification_must_match_even_with_same_part_number():
    result = reconcile_materials([requirement(specification="1.5 mm shaft variant")], inventory(), evaluated_at=NOW)
    assert Decimal(result["lines"][0]["available_for_plan"]) == 0
    assert result["lines"][0]["excluded_lots"][0]["reason"] == "material_specification_not_confirmed"


@pytest.mark.parametrize("age,simulated", [(timedelta(days=2), False), (timedelta(minutes=-10), False), (timedelta(0), True)])
def test_old_future_or_simulated_inventory_never_claims_owned_coverage(age, simulated):
    result = reconcile_materials([requirement()], inventory(captured_at=NOW-age, simulated=simulated), evaluated_at=NOW)
    assert Decimal(result["lines"][0]["available_for_plan"]) == 0
    assert result["lines"][0]["issues"]


def test_expired_stock_and_unidentified_material_stay_unresolved():
    capture = inventory(lots=[{**inventory().lots[0].model_dump(mode="json"), "expires_at": NOW.isoformat()}])
    result = reconcile_materials([requirement(), requirement(material_id="junk", manufacturer="", mpn="")], capture, evaluated_at=NOW)
    assert result["lines"][0]["excluded_lots"][0]["reason"] == "expired"
    assert result["lines"][1]["action"] == "resolve_identity"


@pytest.mark.parametrize("quantity", [True, "NaN", "Infinity", -1, "0.0000001", "1000001"])
def test_invalid_requirement_quantities_are_rejected(quantity):
    with pytest.raises(ValueError):
        requirement(quantity=quantity)


def test_duplicate_lots_and_excess_allocations_are_rejected():
    original = inventory().lots[0].model_dump(mode="json")
    with pytest.raises(ValueError, match="duplicate"):
        inventory(lots=[original, original])
    with pytest.raises(ValueError, match="allocated stock"):
        inventory(lots=[{**original, "allocated": "4"}])


@pytest.fixture
def store(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    store.save("drone", {"projectName": "Drone", "physical_authority_granted": False}, expected_revision=0)
    store.save("other", {"projectName": "Other"}, expected_revision=0)
    return store


def saved(store):
    return assess_project_materials(store, "drone", expected_revision=1, requirements=[requirement()],
                                   inventory=inventory(captured_at=datetime.now(timezone.utc)))


def test_assessment_preserves_design_revision_authority_and_older_report(store):
    before = store.load("drone")
    result = saved(store)
    assert result["assessment"]["inventory_provenance"] == "provided_snapshot"
    identity = result["assessment"]["assessment_id"]
    assert store.load("drone") == before
    store.save("drone", {**before["snapshot"], "changed": True}, expected_revision=1)
    reopened = load_material_assessment(store, "drone", identity)
    assert not reopened["current_for_project"]
    assert reopened["assessment"] == result["assessment"]
    with pytest.raises(RevisionConflict):
        saved(store)


def test_assessment_cannot_be_rebound_to_a_different_project_or_forged(store):
    import shutil

    result = saved(store)
    identity = result["assessment"]["assessment_id"]
    source = store.root / "drone" / "material_assessments" / (identity + ".json")
    target = store.root / "other" / "material_assessments" / source.name
    target.parent.mkdir()
    shutil.copyfile(source, target)
    with pytest.raises(CorruptProject):
        load_material_assessment(store, "other", identity)
    forged = json.loads(source.read_text())
    forged["report"]["lines"][0]["shortage"] = "0"
    source.write_text(json.dumps(forged))
    with pytest.raises(CorruptProject):
        load_material_assessment(store, "drone", identity)


def test_source_snapshot_change_and_symbolic_link_are_rejected(store, tmp_path):
    identity = saved(store)["assessment"]["assessment_id"]
    source = store.root / "drone" / "revisions" / "00000001.json"
    data = json.loads(source.read_text())
    data["snapshot"]["changed_outside_store"] = True
    source.write_text(json.dumps(data))
    with pytest.raises(CorruptProject):
        load_material_assessment(store, "drone", identity)
    path = store.root / "drone" / "material_assessments" / (identity + ".json")
    path.unlink()
    path.symlink_to(tmp_path / "missing")
    with pytest.raises(CorruptProject):
        load_material_assessment(store, "drone", identity)


def test_canonical_http_materials_and_csv_preserve_project_revision(store, monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_INVENTREE_URL", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_INVENTREE_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(create_project_materials_router(store))
    client = TestClient(app)
    request = {"expected_revision": 1, "requirements": [requirement().model_dump(mode="json")],
               "inventory": inventory(captured_at=datetime.now(timezone.utc)).model_dump(mode="json")}
    created = client.post("/v1/projects/drone/materials/assess", json=request)
    assert created.status_code == 200, created.text
    identity = created.json()["assessment"]["assessment_id"]
    assert client.get(f"/v1/projects/drone/materials/{identity}").status_code == 200
    assert client.get(f"/v1/projects/other/materials/{identity}").status_code == 404
    assert "shortage" in client.get(f"/v1/projects/drone/materials/{identity}/csv").text
    assert len(client.get("/v1/projects/drone/materials").json()["assessments"]) == 1
    assert client.post("/v1/projects/drone/materials/assess", json={**request, "expected_revision": True}).status_code == 422
    assert client.post("/v1/projects/drone/materials/import-inventree", json={"expected_revision": 1, "assembly_part_id": 99}).status_code == 503
    assert store.load("drone")["revision"] == 1


def test_cli_can_assess_existing_design_and_export_a_material_list(store, tmp_path):
    requirements = tmp_path / "requirements.json"
    requirements.write_text(json.dumps([requirement().model_dump(mode="json")]))
    args = [sys.executable, "-m", "hardware_splicer.materials_cli", "--project-root", str(store.root)]
    import os
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    created = subprocess.run([*args, "assess", "drone", "--expected-revision", "1", "--requirements", str(requirements)],
                             cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert created.returncode == 0, created.stderr
    result = json.loads(created.stdout)
    assert Decimal(result["assessment"]["report"]["lines"][0]["shortage"]) == 4
    exported = subprocess.run([*args, "csv", "drone", result["assessment"]["assessment_id"]],
                              cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert exported.returncode == 0 and "F1404-KV2900" in exported.stdout


def test_digital_drone_remains_readable_after_material_assessment(tmp_path):
    from hardware_splicer.digital_engine import DigitalStudyEngine

    with DigitalStudyEngine(project_root=tmp_path/"projects", job_db=tmp_path/"jobs.db") as engine:
        project = engine.create()["project"]["project_id"]
        baseline = engine.study(project)
        assess_project_materials(engine.projects, project, expected_revision=1,
                                 requirements=[requirement()], inventory=inventory(captured_at=datetime.now(timezone.utc)))
        assert engine.study(project) == baseline


def test_csv_does_not_turn_descriptions_into_spreadsheet_formulas(store):
    result = assess_project_materials(store, "drone", expected_revision=1,
                                     requirements=[requirement(description="=1+1")], inventory=inventory())
    assert "'=1+1" in material_csv(result["assessment"])
