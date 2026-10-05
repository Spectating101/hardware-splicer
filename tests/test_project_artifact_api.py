from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.artifact_retention import (
    PIN_SCHEMA,
    ArtifactIntegrityError,
    install_at_save_retention,
    load_artifact_pin,
    retain_revision_artifacts,
)
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_artifact_api import create_project_artifact_router
from hardware_splicer.project_store import ProjectStore

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"

R2_VALUE = (
    '\t\t(property "Reference" "R2"\n'
    "\t\t\t(at 187.452 82.55 90)\n"
    "\t\t\t(effects\n"
    "\t\t\t\t(font\n"
    "\t\t\t\t\t(size 1.27 1.27)\n"
    "\t\t\t\t)\n"
    "\t\t\t\t(justify left)\n"
    "\t\t\t)\n"
    "\t\t)\n"
    '\t\t(property "Value" "10k"'
)
R2_VALUE_NEW = R2_VALUE.replace('"10k"', '"4.7k"', 1)
SEGMENT_WIDTH = (
    "\t(segment\n"
    "\t\t(start 133.175 67.8517)\n"
    "\t\t(end 133.175 74)\n"
    "\t\t(width 0.2)\n"
    '\t\t(layer "F.Cu")\n'
    "\t\t(net 1)\n"
    '\t\t(uuid "0abb31d8-7d09-4cf1-9b15-9cb8ff1c70fb")\n'
    "\t)"
)
SEGMENT_WIDTH_NEW = SEGMENT_WIDTH.replace("(width 0.2)", "(width 0.35)", 1)


def _snapshot(build_dir: Path | None = None, stage: str = "design") -> dict:
    body = {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": stage,
    }
    if build_dir is not None:
        body["buildDir"] = str(build_dir)
    return body


def _copy_reference(build: Path) -> Path:
    comp = build / "build_compilation"
    comp.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCH, comp / SCH.name)
    shutil.copy(PCB, comp / PCB.name)
    (comp / "notes.txt").write_text("not kicad\n", encoding="utf-8")
    return comp


def _client(tmp_path: Path) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_artifact_router(store))
    return TestClient(app), store


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"artifacts", "artifact_pins"}:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_put_snapshot_adds_artifact_retention_and_keeps_project(tmp_path: Path) -> None:
    api, _store = _client(tmp_path)
    response = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(), "expected_revision": 0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["project"]["revision"] == 1
    assert body["artifact_retention"]["status"] == "skipped"
    assert "reason" in body["artifact_retention"]


def test_put_snapshot_retains_when_build_dir_has_kicad(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    response = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert response.status_code == 200
    assert response.json()["artifact_retention"]["status"] == "retained"
    listed = api.get("/v1/projects/robot/revisions/1/artifacts")
    assert listed.status_code == 200
    pin = listed.json()["pin"]
    assert pin["retention_basis"] == "at_save"
    assert pin["artifacts"]["schematic"]["relative"].endswith(".kicad_sch")
    assert (store.root / "robot" / "artifact_pins" / "00000001.json").is_file()


def test_failing_retention_does_not_fail_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("retention exploded")

    monkeypatch.setattr(
        "hardware_splicer.artifact_retention.retain_revision_artifacts",
        boom,
    )
    api, store = _client(tmp_path)
    response = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(), "expected_revision": 0},
    )
    assert response.status_code == 200
    assert response.json()["project"]["revision"] == 1
    assert response.json()["artifact_retention"]["status"] == "failed"
    assert "/" not in response.json()["artifact_retention"]["reason"]
    assert store.load("robot")["revision"] == 1


def test_outside_root_save_succeeds_without_pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    _copy_reference(outside)
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(allowed))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    api, store = _client(tmp_path / "store")
    response = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(outside), "expected_revision": 0},
    )
    assert response.status_code == 200
    assert response.json()["project"]["revision"] == 1
    assert response.json()["artifact_retention"]["status"] == "skipped"
    assert api.get("/v1/projects/robot/revisions/1/artifacts").json()["pin"] is None
    assert not (store.root / "robot" / "artifact_pins").exists()


def test_after_save_retain_and_revision_diff(tmp_path: Path) -> None:
    build = tmp_path / "build"
    comp = _copy_reference(build)
    api, store = _client(tmp_path / "store")
    first = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert first.json()["artifact_retention"]["status"] == "retained"
    project_dir = store.root / "robot"

    (comp / SCH.name).write_text(
        (comp / SCH.name).read_text(encoding="utf-8").replace(R2_VALUE, R2_VALUE_NEW, 1),
        encoding="utf-8",
    )
    (comp / PCB.name).write_text(
        (comp / PCB.name).read_text(encoding="utf-8").replace(SEGMENT_WIDTH, SEGMENT_WIDTH_NEW, 1),
        encoding="utf-8",
    )
    store.save("robot", _snapshot(build, "verify"), expected_revision=1)
    before = _hash_tree(project_dir)
    retry = api.post("/v1/projects/robot/revisions/2/artifacts/retain")
    assert retry.status_code == 200
    assert retry.json()["ok"] is True
    assert retry.json()["pin"]["retention_basis"] == "after_save"
    assert "mutable" in retry.json()["note"]

    sch = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 2, "kind": "schematic"},
    )
    pcb = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 2, "kind": "pcb"},
    )
    assert sch.status_code == 200 and pcb.status_code == 200
    sch_body = sch.json()
    pcb_body = pcb.json()
    assert sch_body["available"] is True
    assert pcb_body["available"] is True
    sch_row = next(row for row in sch_body["diff"]["changes"] if row["ref"] == "R2")
    assert "value 10k -> 4.7k" in sch_row["details"]
    pcb_row = next(
        row
        for row in pcb_body["diff"]["changes"]
        if row["change"] == "changed" and row["item_type"] == "segment"
    )
    assert "width 0.2 -> 0.35" in pcb_row["details"]
    assert sch_body["artifact"]["base"]["retention_basis"] == "at_save"
    assert sch_body["artifact"]["candidate"]["retention_basis"] == "after_save"
    assert _hash_tree(project_dir) == before


def test_missing_pin_is_available_false(tmp_path: Path) -> None:
    api, _store = _client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(), "expected_revision": 0})
    response = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 1, "kind": "schematic"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["available"] is False
    assert body["reason"] == "Revision 1 has no retained schematic artifact."


def test_same_revision_empty_diff(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, _store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})
    response = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 1, "kind": "schematic"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["diff"]["summary"]["added"] == 0
    assert body["diff"]["summary"]["removed"] == 0
    assert body["diff"]["summary"]["changed"] == 0
    assert body["diff"]["changes"] == []


def test_tampered_blob_is_500(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})
    pin = api.get("/v1/projects/robot/revisions/1/artifacts").json()["pin"]
    digest = pin["artifacts"]["schematic"]["sha256"].split(":", 1)[1]
    blob = store.root / "robot" / "artifacts" / "sha256" / digest[:2] / digest
    blob.write_bytes(blob.read_bytes() + b"tamper")
    response = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 1, "kind": "schematic"},
    )
    assert response.status_code == 500
    assert response.json()["detail"]["type"] == "artifact_integrity_error"


def test_retain_conflict_and_missing_revision(tmp_path: Path) -> None:
    build = tmp_path / "build"
    comp = _copy_reference(build)
    api, store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})
    (comp / SCH.name).write_text(
        (comp / SCH.name).read_text(encoding="utf-8").replace(R2_VALUE, R2_VALUE_NEW, 1),
        encoding="utf-8",
    )
    conflict = api.post("/v1/projects/robot/revisions/1/artifacts/retain")
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["type"] == "artifact_pin_conflict"

    missing = api.post("/v1/projects/robot/revisions/9/artifacts/retain")
    assert missing.status_code == 404
    assert missing.json()["detail"]["type"] == "not_found"

    no_dir = api.post("/v1/projects/ghost/revisions/1/artifacts/retain")
    assert no_dir.status_code == 404

    store.save("empty", {"projectId": "empty"}, expected_revision=0)
    skipped = api.post("/v1/projects/empty/revisions/1/artifacts/retain")
    assert skipped.status_code == 404


def test_invalid_diff_query(tmp_path: Path) -> None:
    api, _store = _client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(), "expected_revision": 0})
    kind = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 1, "kind": "gerber"},
    )
    assert kind.status_code == 422
    assert kind.json()["detail"]["type"] == "invalid_request"
    revision = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": "nope", "candidate": 1, "kind": "schematic"},
    )
    assert revision.status_code == 422
    assert revision.json()["detail"]["type"] == "invalid_request"
    missing = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 9, "kind": "schematic"},
    )
    assert missing.status_code == 404


def test_direct_retain_helper_still_idempotent_via_api_store(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    _api, store = _client(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    first = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    second = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert first is not None and second is not None
    assert first["artifacts"] == second["artifacts"]


def test_review_accept_pins_via_wrapped_save(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = install_at_save_retention(ProjectStore(tmp_path / "store"))
    app = FastAPI()
    app.include_router(create_project_router(store))
    api = TestClient(app)

    def review_snapshot(purpose: str) -> dict:
        body = _snapshot(build)
        body["machineProject"] = {
            "project_id": "robot",
            "name": "Robot",
            "purpose": purpose,
        }
        return body

    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": review_snapshot("Build an inspection robot"), "expected_revision": 0},
    )
    assert saved.status_code == 200
    created = api.post(
        "/v1/projects/robot/reviews",
        json={
            "base_revision": 1,
            "candidate_snapshot": review_snapshot("Build an autonomous inspection robot"),
            "created_by": "agent",
        },
    )
    assert created.status_code == 201
    review_id = created.json()["review"]["review_id"]
    accepted = api.post(
        f"/v1/projects/robot/reviews/{review_id}/decision",
        json={"decision": "accepted", "actor": "owner"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["review"]["decision"]["accepted_revision"] == 2
    pin = load_artifact_pin(store, "robot", 2)
    assert pin is not None
    assert pin["revision"] == 2
    assert pin["retention_basis"] == "at_save"
    assert pin["artifacts"]["schematic"] is not None
    assert pin["artifacts"]["pcb"] is not None


def _spy_retain(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    real = retain_revision_artifacts

    def spy(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr("hardware_splicer.artifact_retention.retain_revision_artifacts", spy)
    return calls


def test_product_put_retains_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    calls = _spy_retain(monkeypatch)
    store = install_at_save_retention(ProjectStore(tmp_path / "store"))
    app = FastAPI()
    app.include_router(create_project_router(store))
    api = TestClient(app)
    response = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert response.status_code == 200
    assert response.json()["artifact_retention"]["status"] == "retained"
    assert calls == [1]


def test_bare_router_put_retains_once_and_returns_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    calls = _spy_retain(monkeypatch)
    api, _store = _client(tmp_path / "store")
    response = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert response.status_code == 200
    assert response.json()["artifact_retention"]["status"] == "retained"
    assert calls == [1]


def test_corrupt_pin_api_returns_integrity_error(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.status_code == 200
    pin_path = store.root / "robot" / "artifact_pins" / "00000001.json"
    corrupt = {
        "schema_version": PIN_SCHEMA,
        "project_id": "robot",
        "revision": "x",
        "retained_at": "2026-01-01T00:00:00+00:00",
        "retention_basis": "at_save",
        "artifacts": {"schematic": None, "pcb": None},
    }
    pin_path.write_text(json.dumps(corrupt) + "\n", encoding="utf-8")
    listed = api.get("/v1/projects/robot/revisions/1/artifacts")
    assert listed.status_code == 500
    assert listed.json()["detail"]["type"] == "artifact_integrity_error"
    assert listed.json()["detail"]["message"] == "artifact pin is corrupt"
    diffed = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 1, "kind": "schematic"},
    )
    assert diffed.status_code == 500
    assert diffed.json()["detail"]["type"] == "artifact_integrity_error"
    assert diffed.json()["detail"]["message"] == "artifact pin is corrupt"


def test_artifact_diff_second_pin_load_error_is_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.status_code == 200
    real = load_artifact_pin
    calls = {"n": 0}

    def second_raises(loaded_store, project_id, revision, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise ArtifactIntegrityError("artifact pin is corrupt")
        return real(loaded_store, project_id, revision, *args, **kwargs)

    monkeypatch.setattr("hardware_splicer.project_artifact_api.load_artifact_pin", second_raises)
    monkeypatch.setattr("hardware_splicer.artifact_retention.load_artifact_pin", second_raises)
    response = api.get(
        "/v1/projects/robot/artifact-diff",
        params={"base": 1, "candidate": 1, "kind": "schematic"},
    )
    assert response.status_code == 500
    assert response.json()["detail"]["type"] == "artifact_integrity_error"


def test_duplicate_response_includes_artifact_retention(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, _store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.status_code == 200
    duplicated = api.post(
        "/v1/projects/robot/duplicate",
        json={"target_project_id": "robot-copy"},
    )
    assert duplicated.status_code == 201
    body = duplicated.json()
    assert body["ok"] is True
    assert body["project"]["snapshot"]["projectId"] == "robot-copy"
    assert body["project"]["revision"] == 1
    assert body["artifact_retention"]["status"] == "retained"
    assert "reason" in body["artifact_retention"]


def _schematic_blob(store: ProjectStore, pin: dict) -> Path:
    digest = pin["artifacts"]["schematic"]["sha256"].split(":", 1)[1]
    return store.root / "robot" / "artifacts" / "sha256" / digest[:2] / digest


def _tamper_blob_symlink(blob: Path) -> None:
    dummy = blob.parent / "dummy-target"
    dummy.write_bytes(b"not-the-blob")
    blob.unlink()
    blob.symlink_to(dummy)


def _tamper_blob_bytes(blob: Path) -> None:
    blob.write_bytes(blob.read_bytes() + b"tamper")


def _tamper_blob_directory(blob: Path) -> None:
    blob.unlink()
    blob.mkdir()


@pytest.mark.parametrize(
    "tamper",
    [_tamper_blob_symlink, _tamper_blob_bytes, _tamper_blob_directory],
    ids=["symlink", "different-bytes", "directory"],
)
def test_tampered_existing_blob_explicit_retain_is_500_and_save_does_not_raise(
    tmp_path: Path, tamper
) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.status_code == 200
    pin = api.get("/v1/projects/robot/revisions/1/artifacts").json()["pin"]
    tamper(_schematic_blob(store, pin))
    explicit = api.post("/v1/projects/robot/revisions/1/artifacts/retain")
    assert explicit.status_code == 500
    assert explicit.json()["detail"]["type"] == "artifact_integrity_error"
    assert explicit.json()["detail"]["message"] == "retained artifact failed hash verification"
    wrapped = install_at_save_retention(store)
    envelope = wrapped.save("robot", _snapshot(build, "verify"), expected_revision=1)
    assert envelope["revision"] == 2
