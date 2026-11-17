"""Immutable, revision-bound harness assessments using the existing materials."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from .integrations.wireviz import WireVizError, render_wireviz, validate_svg
from .project_materials import _canonical, _digest, load_material_assessment
from .project_store import CorruptProject, ProjectNotFound, ProjectStore, RevisionConflict, _atomic_write_json
from .stored_source_parser import read_registered_source_bytes
from .wiring_harness import HarnessSpecification, assess_harness, cut_list_csv, wireviz_document

SCHEMA = "hardware_splicer.wiring_assessment.v1"
_ID = re.compile(r"wiring-[a-f0-9]{32}\Z")
MAX_RECORD_BYTES = 10_000_000


def _pointer(document, pointer):
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ValueError("source pointer must be an RFC 6901 JSON pointer")
    value = document
    for item in pointer[1:].split("/"):
        if re.search(r"~(?![01])", item):
            raise ValueError("invalid JSON pointer escape")
        item = item.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", item):
                raise ValueError("source pointer has an invalid array index")
            try:
                value = value[int(item)]
            except IndexError as exc:
                raise ValueError("source pointer is absent") from exc
        elif isinstance(value, dict) and item in value:
            value = value[item]
        else:
            raise ValueError("source pointer is absent")
    return value


def _source_checks(store, project_id, snapshot, spec):
    sources = snapshot.get("engineeringSources") or []
    checks, cache = [], {}
    for target, contract, binding in [
        *((row.endpoint_id, row.contract, row.source) for row in spec.endpoints),
        *((row.wire_id, row.contract, row.source) for row in spec.wires),
    ]:
        if binding is None:
            checks.append({"target": target, "status": "unbound_declaration"})
            continue
        selected = [row for row in sources if isinstance(row, dict) and row.get("source_id") == binding.source_id]
        if len(selected) != 1 or selected[0].get("content_hash") != binding.content_hash:
            raise ValueError("source binding does not match one source in this project revision")
        source = selected[0]
        if binding.source_id not in cache:
            raw = read_registered_source_bytes(project_id, source, project_root=store.root)
            if len(raw) > 2_000_000:
                raise ValueError("wiring JSON source exceeds 2 MB")
            try:
                cache[binding.source_id] = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("wiring contracts require a retained JSON source") from exc
            if sum(len(_canonical(value)) for value in cache.values()) > 8_000_000:
                raise ValueError("selected wiring source data exceeds 8 MB")
        source_contract = type(contract).model_validate(_pointer(cache[binding.source_id], binding.pointer))
        if source_contract != contract:
            raise ValueError("declared wiring contract differs from the retained source pointer")
        checks.append({"target": target, "status": "registered_contract_bytes_match",
                       "source_id": binding.source_id, "content_hash": binding.content_hash,
                       "pointer": binding.pointer, "authority": "declared_contract_only"})
    return checks


def _inputs(store, project_id, envelope, specification, material_assessment_id):
    spec = HarnessSpecification.model_validate(specification)
    materials = load_material_assessment(store, project_id, material_assessment_id)["assessment"]
    if materials["source_revision"] != envelope["revision"] or materials["source_snapshot_sha256"] != _digest(envelope["snapshot"]):
        raise RevisionConflict("Material assessment and wiring must refer to the same project revision.")
    sources = _source_checks(store, project_id, envelope["snapshot"], spec)
    report = assess_harness(spec, materials["report"]["lines"], sources)
    return spec, sources, report


def _directory(store, project_id):
    project = store._project_dir(project_id)
    directory = (project / "wiring_assessments").resolve()
    if directory.parent != project:
        raise CorruptProject("wiring assessment directory escapes the project")
    return directory


def assess_project_wiring(store: ProjectStore, project_id: str, *, expected_revision: int,
                          material_assessment_id: str, specification: dict | HarnessSpecification,
                          render: bool = False) -> dict:
    if type(expected_revision) is not int or expected_revision < 1 or type(render) is not bool:
        raise ValueError("expected_revision must be a positive integer and render must be boolean")
    envelope = store.load(project_id)
    if envelope["revision"] != expected_revision:
        raise RevisionConflict("The project changed. Reload before assessing wiring.")
    spec, sources, report = _inputs(store, project_id, envelope, specification, material_assessment_id)
    document = wireviz_document(spec, report)
    native = render_wireviz(document) if render else {"status": "not_requested"}
    record = {
        "schema_version": SCHEMA, "project_id": project_id, "source_revision": expected_revision,
        "source_snapshot_sha256": _digest(envelope["snapshot"]),
        "material_assessment_id": material_assessment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "specification": spec.model_dump(mode="json"), "source_checks": sources, "report": report,
        "wireviz_document": document, "cut_list_csv": cut_list_csv(spec), "native": native,
    }
    record["assessment_id"] = "wiring-" + _digest(record)[:32]
    if len(_canonical(record)) > MAX_RECORD_BYTES:
        raise ValueError("wiring assessment exceeds 10 MB")
    if store.load(project_id)["revision"] != expected_revision:
        raise RevisionConflict("The project changed while assessing wiring.")
    _atomic_write_json(_directory(store, project_id) / (record["assessment_id"] + ".json"), record, exclusive=True)
    return load_wiring_assessment(store, project_id, record["assessment_id"])


def load_wiring_assessment(store: ProjectStore, project_id: str, assessment_id: str) -> dict:
    if not _ID.fullmatch(assessment_id):
        raise ValueError("invalid wiring assessment ID")
    path = _directory(store, project_id) / (assessment_id + ".json")
    if path.is_symlink():
        raise CorruptProject("unsafe wiring assessment")
    if not path.is_file():
        raise ProjectNotFound("Wiring assessment not found in this project.")
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise CorruptProject("wiring assessment exceeds 10 MB")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or set(record) != {
            "schema_version", "project_id", "source_revision", "source_snapshot_sha256",
            "material_assessment_id", "created_at", "specification", "source_checks", "report",
            "wireviz_document", "cut_list_csv", "native", "assessment_id",
        }:
            raise ValueError("unexpected wiring record fields")
        unsigned = {key: value for key, value in record.items() if key != "assessment_id"}
        if record["schema_version"] != SCHEMA or record["project_id"] != project_id or record["assessment_id"] != assessment_id or "wiring-" + _digest(unsigned)[:32] != assessment_id:
            raise ValueError("wiring identity/hash mismatch")
        if type(record["source_revision"]) is not int or record["source_revision"] < 1:
            raise ValueError("invalid source revision")
        if datetime.fromisoformat(record["created_at"]).utcoffset() is None:
            raise ValueError("creation timestamp lacks timezone")
        source = store.load(project_id, record["source_revision"])
        if _digest(source["snapshot"]) != record["source_snapshot_sha256"]:
            raise ValueError("wiring source snapshot changed")
        spec, sources, report = _inputs(store, project_id, source, record["specification"], record["material_assessment_id"])
        if sources != record["source_checks"] or report != record["report"] or wireviz_document(spec, report) != record["wireviz_document"] or cut_list_csv(spec) != record["cut_list_csv"]:
            raise ValueError("wiring claims or exported instructions differ from inputs")
        native = record["native"]
        if native == {"status": "not_requested"}:
            pass
        elif isinstance(native, dict) and set(native) == {"status", "version", "input_sha256", "output_sha256", "outputs"} and native["status"] == "rendered":
            if native["input_sha256"] != hashlib.sha256(record["wireviz_document"].encode()).hexdigest() or set(native["outputs"]) != {"svg", "bom_tsv"}:
                raise ValueError("native render input mismatch")
            if native["output_sha256"] != {key: hashlib.sha256(value.encode()).hexdigest() for key, value in native["outputs"].items()}:
                raise ValueError("native render output mismatch")
            validate_svg(native["outputs"]["svg"])
        else:
            raise ValueError("invalid native render receipt")
    except (KeyError, TypeError, ValueError, WireVizError, RevisionConflict) as exc:
        raise CorruptProject("invalid wiring assessment: " + str(exc)) from exc
    return {"ok": True, "assessment": record,
            "current_for_project": store.load(project_id)["revision"] == record["source_revision"]}


def list_wiring_assessments(store: ProjectStore, project_id: str) -> dict:
    store.load(project_id)
    paths = list(_directory(store, project_id).glob("wiring-*.json"))
    if len(paths) > 200:
        raise ValueError("wiring assessment listing exceeds 200 records")
    rows = []
    for path in paths:
        result = load_wiring_assessment(store, project_id, path.stem)
        record = result["assessment"]
        rows.append({"assessment_id": record["assessment_id"], "source_revision": record["source_revision"],
                     "created_at": record["created_at"], "status": record["report"]["status"],
                     "summary": record["report"]["summary"], "current_for_project": result["current_for_project"]})
    return {"ok": True, "assessments": sorted(rows, key=lambda row: row["created_at"], reverse=True)}


def wiring_bundle(record: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ASSESSMENT.json", json.dumps(record, indent=2, sort_keys=True))
        archive.writestr("HARNESS.wireviz", record["wireviz_document"])
        archive.writestr("CUT_LIST.csv", record["cut_list_csv"])
        archive.writestr("README.txt", "DIGITAL WIRING REVIEW\nStatus: " + record["report"]["status"] + "\n"
                         "Inspect ASSESSMENT.json for open issues and scope. No physical construction approval.\n"
                         "This describes selected endpoints and individual conductors; terminations and complete device coverage are not established.\n")
        if record["native"]["status"] == "rendered":
            archive.writestr("HARNESS.svg", record["native"]["outputs"]["svg"])
            archive.writestr("NATIVE_BOM.tsv", record["native"]["outputs"]["bom_tsv"])
    return output.getvalue()
