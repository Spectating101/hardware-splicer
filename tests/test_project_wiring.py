"""A material list and a diagram must not conceal an incompatible harness."""
import base64
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.engineering_source_ingestion import EngineeringSourceIngestionRequest, ingest_engineering_source
from hardware_splicer.integrations.wireviz import WireVizError, render_wireviz, spreadsheet_safe_tsv, validate_svg
from hardware_splicer.project_materials import assess_project_materials
from hardware_splicer.project_store import CorruptProject, ProjectNotFound, ProjectStore, RevisionConflict
from hardware_splicer.project_wiring import assess_project_wiring, load_wiring_assessment, wiring_bundle
from hardware_splicer.project_wiring_api import create_project_wiring_router
from hardware_splicer.wiring_harness import HarnessSpecification, assess_harness, cut_list_csv, wireviz_document

ROOT = Path(__file__).resolve().parents[1]


def reference_specification():
    # Controlled digital fixture: these identifiers do not represent products
    # the user owns, manufacturer specifications or a finished device.
    source = {"manufacturer": "Fixture", "mpn": "SUPPLY-5V", "pin_view": "terminal labels, front",
              "pins": [{"pin_id": "1", "label": "+5V", "role": "power_out", "reference_pin": "2",
                        "voltage": {"minimum": "4.9", "maximum": "5.1"}, "current_a": "2"},
                       {"pin_id": "2", "label": "GND", "role": "ground"}]}
    load = {"manufacturer": "Fixture", "mpn": "LOAD-5V", "pin_view": "terminal labels, front",
            "pins": [{"pin_id": "1", "label": "VIN", "role": "power_in", "reference_pin": "2",
                      "voltage": {"minimum": "4.75", "maximum": "5.25"}, "current_a": "0.5", "required": "yes"},
                     {"pin_id": "2", "label": "GND", "role": "ground", "required": "yes"}]}
    wire_contract = {"manufacturer": "Fixture", "mpn": "WIRE-22", "gauge_awg": 22,
                     "ampacity_a": "1", "insulation_voltage_v": "30"}
    return {"description": "Controlled digital power harness fixture",
            "endpoints": [{"endpoint_id": "supply", "material_id": "supply", "contract": source},
                          {"endpoint_id": "load", "material_id": "load", "contract": load}],
            "wires": [{"wire_id": "positive", "material_id": "wire", "start": {"endpoint_id": "supply", "pin_id": "1"},
                       "end": {"endpoint_id": "load", "pin_id": "1"}, "length_m": "0.2", "color": "RD", "contract": wire_contract},
                      {"wire_id": "return", "material_id": "wire", "start": {"endpoint_id": "supply", "pin_id": "2"},
                       "end": {"endpoint_id": "load", "pin_id": "2"}, "length_m": "0.2", "color": "BK", "contract": wire_contract}]}


def reference_materials():
    return [{"material_id": key, "description": mpn, "manufacturer": "Fixture", "mpn": mpn,
             "quantity": quantity, "unit": unit}
            for key, mpn, quantity, unit in [("supply", "SUPPLY-5V", "1", "ea"),
                                             ("load", "LOAD-5V", "2", "ea"), ("wire", "WIRE-22", "2", "m")]]


@pytest.fixture
def setup(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    store.save("example", {"projectName": "Digital wiring fixture"}, expected_revision=0)
    store.save("other", {"projectName": "Other"}, expected_revision=0)
    spec = reference_specification()
    contracts = {"supply": spec["endpoints"][0]["contract"], "load": spec["endpoints"][1]["contract"], "wire": spec["wires"][0]["contract"]}
    source = ingest_engineering_source(EngineeringSourceIngestionRequest(
        project_id="example", filename="declared-contracts.json",
        content_base64=base64.b64encode(json.dumps(contracts).encode()).decode()), project_root=store.root)
    store.save("example", {**store.load("example")["snapshot"], "engineeringSources": [source.source_descriptor]}, expected_revision=1)
    materials = assess_project_materials(store, "example", expected_revision=2, requirements=reference_materials(),
        inventory={"source": "declared", "captured_at": datetime.now(timezone.utc).isoformat(), "lots": []})["assessment"]
    for row in [*spec["endpoints"], *spec["wires"]]:
        row["source"] = {"source_id": source.source_id, "content_hash": source.content_hash,
                         "pointer": "/" + row["material_id"]}
    return store, spec, materials


def save(setup, **values):
    store, spec, materials = setup
    return assess_project_wiring(store, "example", expected_revision=2, material_assessment_id=materials["assessment_id"],
                                 specification=spec, **values)


def evaluate(spec, materials):
    model = HarnessSpecification.model_validate(spec)
    source_checks = [{"target": row.get("endpoint_id", row.get("wire_id")), "status": "unbound_declaration"}
                     for row in [*spec["endpoints"], *spec["wires"]]]
    return assess_harness(model, materials["report"]["lines"], source_checks)


def codes(report):
    return {row["code"] for row in report["issues"]}


def test_source_bound_power_harness_preserves_revision_and_exports_exact_pins(setup):
    store, spec, materials = setup
    before = store.load("example")
    result = save(setup)
    record = result["assessment"]
    assert record["report"]["status"] == "passes_declared_checks"
    assert record["report"]["construction_ready"] is False
    assert record["report"]["physical_authority_granted"] is False
    assert all(row["status"] == "registered_contract_bytes_match" for row in record["source_checks"])
    assert store.load("example") == before
    assert record["material_assessment_id"] == materials["assessment_id"]
    document = json.loads(record["wireviz_document"])
    assert document["connections"][0] == [{"X1": [1]}, {"W1": [1]}, {"X2": [1]}]
    assert document["connectors"]["X1"]["pinlabels"] == ["+5V", "GND"]
    assert "0.2,RD,22" in record["cut_list_csv"]
    assert {row["material_id"]: row["quantity"] for row in record["report"]["harness_materials"]} == {"load": "1", "supply": "1", "wire": "0.4"}
    with zipfile.ZipFile(io.BytesIO(wiring_bundle(record))) as archive:
        assert set(archive.namelist()) == {"ASSESSMENT.json", "HARNESS.wireviz", "CUT_LIST.csv", "README.txt"}
        assert archive.read("CUT_LIST.csv").decode() == record["cut_list_csv"]


@pytest.mark.parametrize("change,expected", [
    ("overvoltage", "supply_voltage_outside_load_range"),
    ("undervoltage", "supply_voltage_outside_load_range"),
    ("overcurrent", "supply_current_exceeded"),
    ("thin_wire", "wire_current_exceeded"),
    ("weak_insulation", "wire_insulation_voltage_exceeded"),
    ("swapped_power_ground", "incompatible_pin_roles"),
    ("unidentified_part", "contract_material_identity_mismatch"),
])
def test_incompatible_materials_and_power_cannot_pass(setup, change, expected):
    _, _, materials = setup
    spec = reference_specification()
    supply, load = [row["contract"]["pins"][0] for row in spec["endpoints"]]
    if change == "overvoltage":
        supply["voltage"] = {"minimum": "11", "maximum": "12"}
    elif change == "undervoltage":
        supply["voltage"] = {"minimum": "3", "maximum": "3.3"}
    elif change == "overcurrent":
        load["current_a"] = "3"
    elif change == "thin_wire":
        spec["wires"][0]["contract"]["ampacity_a"] = "0.1"
    elif change == "weak_insulation":
        spec["wires"][0]["contract"]["insulation_voltage_v"] = "3"
    elif change == "swapped_power_ground":
        spec["wires"][0]["end"]["pin_id"] = "2"
        spec["wires"][1]["end"]["pin_id"] = "1"
    else:
        spec["endpoints"][0]["contract"]["mpn"] = "DIFFERENT-SUPPLY"
    report = evaluate(spec, materials)
    assert expected in codes(report)
    assert report["status"] == "blocked"


def test_shared_supply_and_return_currents_are_aggregated_across_branches(setup):
    _, _, materials = setup
    spec = reference_specification()
    spec["endpoints"][0]["contract"]["pins"][0]["current_a"] = "0.8"
    extra = deepcopy(spec["endpoints"][1])
    extra["endpoint_id"] = "second-load"
    spec["endpoints"].append(extra)
    for original in list(spec["wires"]):
        wire = deepcopy(original)
        wire["wire_id"] += "-branch"
        wire["end"]["endpoint_id"] = "second-load"
        spec["wires"].append(wire)
    report = evaluate(spec, materials)
    assert "supply_current_exceeded" in codes(report)
    assert [row["declared_current_a"] for row in report["nets"]] == ["1.0", "1.0"]
    # Pair-by-pair each 0.5 A load would have incorrectly passed the 0.8 A source.
    assert report["status"] == "blocked"


def test_joined_power_outputs_are_rejected(setup):
    _, _, materials = setup
    spec = reference_specification()
    spec["endpoints"][1]["contract"]["pins"][0]["role"] = "power_out"
    assert "multiple_power_sources" in codes(evaluate(spec, materials))


def test_signals_and_power_cannot_use_different_ground_reference_nets(setup):
    _, _, materials = setup
    spec = reference_specification()
    for endpoint in spec["endpoints"]:
        endpoint["contract"]["pins"].append({"pin_id": "GND2", "role": "ground"})
    spec["endpoints"][1]["contract"]["pins"][0]["reference_pin"] = "GND2"
    extra = deepcopy(spec["wires"][1])
    extra["wire_id"] = "separate_ground"
    extra["start"]["pin_id"] = extra["end"]["pin_id"] = "GND2"
    spec["wires"].append(extra)
    assert "ground_reference_mismatch" in codes(evaluate(spec, materials))


def test_missing_donor_pinout_ground_or_ratings_remain_unresolved(setup):
    _, _, materials = setup
    spec = reference_specification()
    spec["endpoints"][1]["contract"]["pins"][0]["role"] = "unknown"
    report = evaluate(spec, materials)
    assert {"contract_source_unbound", "pin_role_unknown"} <= codes(report)
    spec = reference_specification()
    spec["wires"] = spec["wires"][:1]
    report = evaluate(spec, materials)
    assert {"ground_reference_unconnected", "required_pin_unconnected"} <= codes(report)
    spec = reference_specification()
    spec["endpoints"][0]["contract"].pop("pin_view")
    spec["endpoints"][1]["contract"]["pins"][0].pop("current_a")
    spec["wires"][0]["contract"].pop("gauge_awg")
    report = evaluate(spec, materials)
    assert {"pin_view_missing", "power_current_limit_missing", "return_current_unknown", "wire_gauge_missing"} <= codes(report)
    assert report["status"] == "unresolved"
    assert all(row["declared_current_a"] is None for row in report["nets"])


def signal_specification():
    spec = reference_specification()
    driver, receiver = [row["contract"]["pins"][0] for row in spec["endpoints"]]
    driver.update(role="signal_out", signal="UART-data", high={"minimum": "2.9", "maximum": "3.3"}, low={"minimum": "0", "maximum": "0.3"})
    receiver.update(role="signal_in", signal="UART-data", high={"minimum": "2.0", "maximum": "3.6"}, low={"minimum": "0", "maximum": "0.8"})
    return spec


def test_digital_high_and_low_limits_are_checked_separately_and_not_complete_protocol_proof(setup):
    _, _, materials = setup
    spec = signal_specification()
    report = evaluate(spec, materials)
    assert "signal_loading_and_timing_not_assessed" in codes(report)
    assert not any(row["severity"] == "blocked" for row in report["issues"])
    spec["endpoints"][0]["contract"]["pins"][0]["high"]["maximum"] = "5"
    assert "logic_high_outside_input_range" in codes(evaluate(spec, materials))
    spec = signal_specification()
    spec["endpoints"][0]["contract"]["pins"][0]["low"]["maximum"] = "1.0"
    assert "logic_low_outside_input_range" in codes(evaluate(spec, materials))


def test_signal_drivers_and_signal_id_mismatches_are_detected(setup):
    _, _, materials = setup
    spec = signal_specification()
    spec["endpoints"][1]["contract"]["pins"][0]["role"] = "signal_out"
    assert "multiple_signal_drivers" in codes(evaluate(spec, materials))
    spec = signal_specification()
    spec["endpoints"][1]["contract"]["pins"][0]["signal"] = "SPI-clock"
    assert "signal_identity_mismatch" in codes(evaluate(spec, materials))


def test_cannot_exceed_assessed_material_quantities_or_invent_unit_conversions(setup):
    _, _, materials = setup
    spec = reference_specification()
    spec["wires"][0]["length_m"] = "3"
    assert "harness_exceeds_material_requirement" in codes(evaluate(spec, materials))
    materials["report"]["lines"][-1]["unit"] = "ft"
    with pytest.raises(ValueError, match="require m"):
        evaluate(spec, materials)


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", -1, "0.0000001"])
def test_invalid_numeric_contracts_are_rejected(value):
    spec = reference_specification()
    spec["endpoints"][0]["contract"]["pins"][0]["current_a"] = value
    with pytest.raises(ValueError):
        HarnessSpecification.model_validate(spec)


def test_ambiguous_or_impossible_topology_is_rejected():
    spec = reference_specification()
    spec["wires"].append(deepcopy(spec["wires"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        HarnessSpecification.model_validate(spec)
    spec = reference_specification()
    spec["wires"][0]["start"]["pin_id"] = "unknown"
    with pytest.raises(ValueError, match="unknown"):
        HarnessSpecification.model_validate(spec)
    spec = reference_specification()
    spec["endpoints"][0]["contract"]["pins"][0]["reference_pin"] = "1"
    with pytest.raises(ValueError, match="ground"):
        HarnessSpecification.model_validate(spec)


@pytest.mark.parametrize("change", ["hash", "source_id", "pointer", "contract"])
def test_registered_source_binding_cannot_claim_different_bytes_or_contract(setup, change):
    store, spec, materials = setup
    if change == "hash":
        spec["endpoints"][0]["source"]["content_hash"] = "sha256:" + "0" * 64
    elif change == "source_id":
        spec["endpoints"][0]["source"]["source_id"] = "other-project-source"
    elif change == "pointer":
        spec["endpoints"][0]["source"]["pointer"] = "/missing"
    else:
        spec["endpoints"][0]["contract"]["pins"][0]["current_a"] = "100"
    with pytest.raises(ValueError):
        save(setup)
    assert not list((store.root / "example" / "wiring_assessments").glob("*.json"))


def test_blob_modification_and_derived_report_or_cut_list_tampering_are_rejected(setup):
    store, spec, materials = setup
    identity = save(setup)["assessment"]["assessment_id"]
    path = store.root / "example" / "wiring_assessments" / (identity + ".json")
    original = path.read_text()
    for field in ("report", "cut_list_csv"):
        record = json.loads(original)
        record[field] = {} if field == "report" else "connect the wrong pin"
        path.write_text(json.dumps(record))
        with pytest.raises(CorruptProject):
            load_wiring_assessment(store, "example", identity)
    path.write_text(original)
    source = store.load("example")["snapshot"]["engineeringSources"][0]
    (store.root / "example" / source["metadata"]["blob_ref"]).write_text("{}")
    with pytest.raises(CorruptProject):
        load_wiring_assessment(store, "example", identity)


def test_history_is_readable_after_revision_change_and_cannot_cross_projects(setup):
    store, _, _ = setup
    result = save(setup)
    identity = result["assessment"]["assessment_id"]
    store.save("example", {**store.load("example")["snapshot"], "updated": True}, expected_revision=2)
    assert load_wiring_assessment(store, "example", identity)["current_for_project"] is False
    with pytest.raises(RevisionConflict):
        save(setup)
    with pytest.raises(ProjectNotFound):
        load_wiring_assessment(store, "other", identity)
    path = store.root / "example" / "wiring_assessments" / (identity + ".json")
    other = store.root / "other" / "wiring_assessments" / path.name
    other.parent.mkdir()
    shutil.copyfile(path, other)
    with pytest.raises(CorruptProject):
        load_wiring_assessment(store, "other", identity)


def test_materials_from_previous_revision_are_rejected(setup):
    store, spec, materials = setup
    store.save("example", store.load("example")["snapshot"], expected_revision=2)
    with pytest.raises(RevisionConflict, match="same project revision"):
        assess_project_wiring(store, "example", expected_revision=3, material_assessment_id=materials["assessment_id"], specification=spec)


def test_render_is_explicit_and_missing_native_tools_leave_no_assessment(setup, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_WIREVIZ_EXECUTABLE", "/no-such-wireviz")
    store, _, _ = setup
    with pytest.raises(WireVizError):
        save(setup, render=True)
    assert not list((store.root / "example" / "wiring_assessments").glob("*.json"))
    assert save(setup)["assessment"]["native"] == {"status": "not_requested"}


@pytest.mark.parametrize("content", [
    '<script>alert(1)</script>', '<image href="https://example.com/remote.png"/>',
    '<g onload="alert(1)"/>', '<a href="javascript:alert(1)"><text>click</text></a>',
    '<path style="fill:url(https://example.com/a)"/>',
])
def test_native_svg_active_or_external_content_is_rejected(content):
    with pytest.raises(WireVizError):
        validate_svg('<svg xmlns="http://www.w3.org/2000/svg">' + content + '</svg>')


def test_user_text_cannot_inject_wireviz_images_links_or_spreadsheet_formulas(setup):
    _, _, materials = setup
    spec = reference_specification()
    spec["endpoints"][0]["contract"]["description"] = '<img src="file:///etc/passwd">'
    spec["wires"][0]["contract"]["specification"] = "=1+1"
    model = HarnessSpecification.model_validate(spec)
    doc = json.loads(wireviz_document(model, evaluate(spec, materials)))
    assert doc["connectors"]["X1"]["type"].startswith("&lt;img")
    assert "'=1+1" in cut_list_csv(model)
    assert "'=1+1" in spreadsheet_safe_tsv("MPN\tQty\n=1+1\t1\n")


def test_canonical_http_assessment_history_and_downloads(setup, monkeypatch):
    store, spec, materials = setup
    monkeypatch.setenv("HARDWARE_SPLICER_WIREVIZ_EXECUTABLE", "/no-such-wireviz")
    app = FastAPI()
    app.include_router(create_project_wiring_router(store))
    client = TestClient(app)
    request = {"expected_revision": 2, "material_assessment_id": materials["assessment_id"], "specification": spec}
    response = client.post("/v1/projects/example/wiring/assess", json=request)
    assert response.status_code == 200, response.text
    identity = response.json()["assessment"]["assessment_id"]
    for suffix, media_type in [("csv", "text/csv"), ("wireviz", "application/yaml"), ("export", "application/zip")]:
        exported = client.get(f"/v1/projects/example/wiring/{identity}/{suffix}")
        assert exported.status_code == 200 and media_type in exported.headers["content-type"]
    assert len(client.get("/v1/projects/example/wiring").json()["assessments"]) == 1
    assert client.get(f"/v1/projects/other/wiring/{identity}").status_code == 404
    assert client.post("/v1/projects/example/wiring/assess", json={**request, "expected_revision": 1}).status_code == 409
    assert client.post("/v1/projects/example/wiring/assess", json={**request, "render": True}).status_code == 503
    assert client.post("/v1/projects/example/wiring/assess", json={**request, "render": "true"}).status_code == 422
    assert client.post("/v1/projects/example/wiring/assess", json={**request, "expected_revision": True}).status_code == 422
    assert store.load("example")["revision"] == 2


def test_sdk_and_cli_work_without_a_server_and_export_an_immutable_package(setup, tmp_path):
    from hardware_splicer.sdk import assess_wiring, export_wiring

    store, spec, materials = setup
    created = assess_wiring("example", expected_revision=2, material_assessment_id=materials["assessment_id"], specification=spec, project_root=store.root)
    assert zipfile.is_zipfile(io.BytesIO(export_wiring("example", created["assessment"]["assessment_id"], project_root=store.root)))
    path = tmp_path / "harness.json"
    path.write_text(json.dumps(spec))
    args = [sys.executable, "-m", "hardware_splicer.wiring_cli", "--project-root", str(store.root)]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    result = subprocess.run([*args, "assess", "example", "--expected-revision", "2", "--materials", materials["assessment_id"], "--specification", str(path)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    identity = json.loads(result.stdout)["assessment"]["assessment_id"]
    output = tmp_path / "review.zip"
    command = [*args, "export", "example", identity, "--output", str(output)]
    exported = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert exported.returncode == 0 and zipfile.is_zipfile(output)
    assert subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30).returncode == 1


def test_mcp_discovers_and_dispatches_the_same_wiring_assessment_and_binary_export(setup):
    from hardware_splicer.mcp_backend_gateway import dispatch_operation, operation_catalog
    from hardware_splicer.product_api import create_product_app

    store, spec, materials = setup
    app = create_product_app(store)
    operations = operation_catalog(app)
    assess = next(row for row in operations if row["path"] == "/v1/projects/{project_id}/wiring/assess")
    result = asyncio.run(dispatch_operation(assess["operation_id"], app=app, path_params={"project_id": "example"},
        json_body={"expected_revision": 2, "material_assessment_id": materials["assessment_id"], "specification": spec}))
    assert result["status_code"] == 200 and result["body"]["assessment"]["report"]["status"] == "passes_declared_checks"
    identity = result["body"]["assessment"]["assessment_id"]
    export = next(row for row in operations if row["path"] == "/v1/projects/{project_id}/wiring/{assessment_id}/export")
    result = asyncio.run(dispatch_operation(export["operation_id"], app=app,
        path_params={"project_id": "example", "assessment_id": identity}, response_mode="base64"))
    assert result["status_code"] == 200
    assert zipfile.is_zipfile(io.BytesIO(base64.b64decode(result["body_base64"])))


def test_existing_digital_study_is_unchanged_by_unbound_wiring_assessment(tmp_path):
    from hardware_splicer.digital_engine import DigitalStudyEngine

    with DigitalStudyEngine(project_root=tmp_path / "digital", job_db=tmp_path / "jobs.db") as engine:
        project = engine.create()["project"]["project_id"]
        before = engine.study(project)
        materials = assess_project_materials(engine.projects, project, expected_revision=1, requirements=reference_materials(),
            inventory={"source": "declared", "captured_at": datetime.now(timezone.utc).isoformat(), "lots": []})["assessment"]
        result = assess_project_wiring(engine.projects, project, expected_revision=1, material_assessment_id=materials["assessment_id"], specification=reference_specification())
        assert result["assessment"]["report"]["status"] == "unresolved"
        assert engine.study(project) == before


def test_optional_real_wireviz_render_and_native_bom(setup):
    executable = os.getenv("HARDWARE_SPLICER_WIREVIZ_EXECUTABLE") or shutil.which("wireviz")
    if not executable or not Path(executable).is_file() or not shutil.which("dot"):
        pytest.skip("optional WireViz CLI and Graphviz are not installed")
    record = save(setup, render=True)["assessment"]
    native = record["native"]
    assert native["status"] == "rendered" and "WireViz" in native["version"]
    visible = "".join(ET.fromstring(native["outputs"]["svg"]).itertext())
    assert "SUPPLY-5V" in visible and "DIGITAL REVIEW:" in visible
    assert "WIRE-22" in native["outputs"]["bom_tsv"]
    with zipfile.ZipFile(io.BytesIO(wiring_bundle(record))) as archive:
        assert {"HARNESS.svg", "NATIVE_BOM.tsv"} <= set(archive.namelist())


@pytest.mark.parametrize("physical_pin", ["01", "1-2", "A1"])
def test_optional_native_render_preserves_nonstandard_physical_pin_ids(setup, physical_pin):
    executable = os.getenv("HARDWARE_SPLICER_WIREVIZ_EXECUTABLE") or shutil.which("wireviz")
    if not executable or not Path(executable).is_file() or not shutil.which("dot"):
        pytest.skip("optional WireViz CLI and Graphviz are not installed")
    _, _, materials = setup
    spec = reference_specification()
    spec["endpoints"][0]["contract"]["pins"][0]["pin_id"] = physical_pin
    spec["wires"][0]["start"]["pin_id"] = physical_pin
    # Keep a potentially conflicting literal alias as a distinct disconnected
    # terminal to ensure the normalization cannot merge physical pins.
    spec["endpoints"][0]["contract"]["pins"].append({"pin_id": "HS_PIN_1", "role": "unknown"})
    model = HarnessSpecification.model_validate(spec)
    document = wireviz_document(model, evaluate(spec, materials))
    result = render_wireviz(document)
    visible = "".join(ET.fromstring(result["outputs"]["svg"]).itertext())
    assert physical_pin in visible
    assert physical_pin in cut_list_csv(model)
