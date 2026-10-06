from __future__ import annotations

import json
import shutil
import stat
import threading
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.artifact_retention import retain_revision_artifacts
from hardware_splicer.kicad_diff import diff_kicad_text
from hardware_splicer.model3d import capability_probe
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_candidates import (
    CANDIDATE_ID_RE,
    MAX_CANDIDATES_PER_PROJECT,
    MAX_OP_STRING,
    MAX_REQUEST_BYTES,
)
from hardware_splicer.project_candidates_api import create_project_candidates_router
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"
R2_PCB_UUID = "f9870e73-0956-4b59-80c4-abad9daa11b3"
MOVE_X = 123.4567
SCH_MOVE = [{"op": "move", "ref": "R2", "x_mm": MOVE_X, "y_mm": 82.55}]
PCB_ROTATE = [{"op": "rotate", "uuid": R2_PCB_UUID, "degrees": 90}]
NOOP_SCH = [{"op": "set_property", "ref": "R2", "name": "Value", "value": "10k"}]
BAD_OP = [{"op": "move", "uuid": "00000000-0000-4000-8000-000000000000", "x_mm": 1, "y_mm": 1}]


def _snapshot(build_dir: Path | None = None) -> dict:
    body = {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "machineProject": {
            "project_id": "robot",
            "name": "Robot",
            "purpose": "Build an inspection robot",
        },
    }
    if build_dir is not None:
        body["buildDir"] = str(build_dir)
    return body


def _copy_reference(build: Path) -> Path:
    comp = build / "build_compilation"
    comp.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCH, comp / SCH.name)
    shutil.copy(PCB, comp / PCB.name)
    return comp


def _hide_kicad(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-candidates-path")


def _client(tmp_path: Path) -> tuple[TestClient, ProjectStore, ProjectReviewStore]:
    store = ProjectStore(tmp_path / "store")
    review_store = ProjectReviewStore(store)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_candidates_router(store, review_store))
    return TestClient(app), store, review_store


def _seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, retain: bool = True
) -> tuple[TestClient, ProjectStore, ProjectReviewStore, Path]:
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    build = tmp_path / "build"
    _copy_reference(build)
    api, store, review_store = _client(tmp_path)
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.status_code == 200
    if retain:
        pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
        assert pin is not None
    return api, store, review_store, build


def _install_fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake-kicad-cli"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then printf "9.0.2-fake\\n"; exit 0; fi\n'
        "output=\"\"\n"
        "input=\"\"\n"
        "prev=\"\"\n"
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--output" ]; then output=$arg; fi\n'
        "  prev=$arg\n"
        "  input=$arg\n"
        "done\n"
        'if [ -z "$output" ] || [ -z "$input" ]; then exit 2; fi\n'
        f'if grep -q "{MOVE_X}" "$input" 2>/dev/null; then\n'
        "  cat > \"$output\" <<'EOF'\n"
        '{"violations":[{"type":"clearance","severity":"error"},{"type":"hole_clearance","severity":"error"}]}\n'
        "EOF\n"
        "else\n"
        "  cat > \"$output\" <<'EOF'\n"
        '{"violations":[{"type":"clearance","severity":"error"},{"type":"clearance","severity":"error"}]}\n'
        "EOF\n"
        "fi\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(script))
    return script


def _operator_env(
    monkeypatch: pytest.MonkeyPatch,
    token: str = "operator-secret",
    *,
    operator_id: str = "alice",
    kind: str = "human",
) -> str:
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        json.dumps({hash_operator_token(token): {"id": operator_id, "kind": kind}}),
    )
    return token


def _candidate_dirs(tmp_path: Path, project_id: str = "robot") -> list[Path]:
    root = tmp_path / "candidates" / project_id
    if not root.is_dir():
        return []
    return [path for path in root.iterdir() if path.is_dir()]


def _record_paths(store: ProjectStore, project_id: str = "robot") -> list[Path]:
    folder = store.root / project_id / "candidates"
    if not folder.is_dir():
        return []
    return [path for path in folder.glob("*.json") if path.is_file()]


def _create_body(**overrides):
    body = {
        "base_revision": 1,
        "kind": "schematic",
        "ops": SCH_MOVE,
        "author": "splicer",
        "note": "move R2",
    }
    body.update(overrides)
    return body


def test_post_schematic_move_and_pcb_rotate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, _review_store, build = _seed(tmp_path, monkeypatch)
    sch_before = (build / "build_compilation" / SCH.name).read_bytes()
    pcb_before = (build / "build_compilation" / PCB.name).read_bytes()
    created = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["ok"] is True
    candidate = body["candidate"]
    review = body["review"]
    assert CANDIDATE_ID_RE.fullmatch(candidate["candidate_id"])
    assert candidate["kind"] == "schematic"
    assert candidate["base_revision"] == 1
    assert candidate["verified"] is False
    assert candidate["created_by"] == "splicer"
    assert candidate["diff"]["summary"]["changed"] >= 1
    assert review["review_id"] == candidate["review_id"]
    assert review["status"] == "pending"
    assert store.load("robot")["revision"] == 1
    files = api.get(
        f"/v1/projects/robot/candidates/{candidate['candidate_id']}/files/schematic"
    )
    assert files.status_code == 200
    assert files.headers["content-type"].startswith("text/plain")
    assert files.headers["etag"].strip('"').startswith("sha256:")
    edited = files.content.decode("utf-8")
    assert diff_kicad_text("schematic", sch_before.decode("utf-8"), edited)["summary"]["changed"] >= 1
    cand_dir = tmp_path / "candidates" / "robot" / candidate["candidate_id"]
    assert cand_dir.is_dir()
    assert (build / "build_compilation" / SCH.name).read_bytes() == sch_before
    assert (build / "build_compilation" / PCB.name).read_bytes() == pcb_before

    pcb = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(kind="pcb", ops=PCB_ROTATE, note="rotate R2", base_revision=None),
    )
    assert pcb.status_code == 201, pcb.text
    assert pcb.json()["candidate"]["kind"] == "pcb"
    assert pcb.json()["candidate"]["diff"]["summary"]["changed"] >= 1
    listed = api.get("/v1/projects/robot/candidates")
    assert listed.status_code == 200
    ids = [row["candidate_id"] for row in listed.json()["candidates"]]
    assert ids[0] == pcb.json()["candidate"]["candidate_id"]
    assert ids[1] == candidate["candidate_id"]
    loaded = api.get(f"/v1/projects/robot/candidates/{candidate['candidate_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["candidate"]["candidate_id"] == candidate["candidate_id"]


def test_no_pin_is_409(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_kicad(monkeypatch)
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    api, store, review_store = _client(tmp_path)
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(), "expected_revision": 0},
    )
    assert saved.status_code == 200
    assert saved.json()["artifact_retention"]["status"] != "retained"
    response = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "artifact_not_retained"
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_invalid_op_is_422_with_no_leftovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, review_store, _build = _seed(tmp_path, monkeypatch)
    response = api.post("/v1/projects/robot/candidates", json=_create_body(ops=BAD_OP))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_edit"
    assert "kicad_sch" not in detail["message"]
    assert "(kicad_sch" not in detail["message"]
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_noop_edit_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_kicad(monkeypatch)
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    response = api.post("/v1/projects/robot/candidates", json=_create_body(ops=NOOP_SCH))
    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "no_effective_change"


def test_operator_token_valid_invalid_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    token = _operator_env(monkeypatch)
    api, store, review_store, _build = _seed(tmp_path, monkeypatch)

    absent = api.post("/v1/projects/robot/candidates", json=_create_body(author="self-name"))
    assert absent.status_code == 201
    assert absent.json()["candidate"]["created_by"] == "self-name"
    assert absent.json()["candidate"]["verified"] is False

    valid = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(kind="pcb", ops=PCB_ROTATE, author="ignored"),
        headers={"X-HS-Operator-Token": token, "Authorization": "Bearer ignored"},
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["candidate"]["created_by"] == "alice"
    assert valid.json()["candidate"]["verified"] is True

    before_dirs = _candidate_dirs(tmp_path)
    before_records = _record_paths(store)
    before_reviews = {row["review_id"] for row in review_store.list("robot")}
    invalid = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(author="mallory"),
        headers={"X-HS-Operator-Token": "not-the-token"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"]["type"] == "operator_token_invalid"
    assert _candidate_dirs(tmp_path) == before_dirs
    assert _record_paths(store) == before_records
    assert {row["review_id"] for row in review_store.list("robot")} == before_reviews
    listed = api.get("/v1/projects/robot/candidates")
    authors = {row["created_by"] for row in listed.json()["candidates"]}
    assert "mallory" not in authors
    assert "self-name" in authors
    assert "alice" in authors


def test_files_route_rejects_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    created = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert created.status_code == 201
    real_id = created.json()["candidate"]["candidate_id"]
    attempts = [
        "../" + real_id,
        "/tmp/" + real_id,
        real_id.upper(),
        "candidate-" + real_id.split("-", 1)[1],
        "cand-" + "A" * 12,
        "cand-" + real_id,
    ]
    for candidate_id in attempts:
        encoded = quote(candidate_id, safe="")
        response = api.get(f"/v1/projects/robot/candidates/{encoded}/files/schematic")
        assert response.status_code == 404, candidate_id
        detail = response.json()["detail"]
        if isinstance(detail, dict):
            assert detail["type"] == "not_found"
    missing = api.get("/v1/projects/robot/candidates/cand-ffffffffffff/files/schematic")
    assert missing.status_code == 404
    assert missing.json()["detail"]["type"] == "not_found"


def test_files_integrity_mismatch_is_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    created = api.post("/v1/projects/robot/candidates", json=_create_body())
    candidate_id = created.json()["candidate"]["candidate_id"]
    cand_dir = tmp_path / "candidates" / "robot" / candidate_id
    target = next(path for path in cand_dir.iterdir() if path.suffix == ".kicad_sch")
    target.write_bytes(target.read_bytes() + b"\n")
    response = api.get(f"/v1/projects/robot/candidates/{candidate_id}/files/schematic")
    assert response.status_code == 500
    assert response.json()["detail"]["type"] == "integrity_error"


def test_per_project_cap_is_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_kicad(monkeypatch)
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "hardware_splicer.project_candidates.MAX_CANDIDATES_PER_PROJECT",
        2,
    )
    assert MAX_CANDIDATES_PER_PROJECT == 50
    first = api.post("/v1/projects/robot/candidates", json=_create_body())
    second = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(kind="pcb", ops=PCB_ROTATE),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    third = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert third.status_code == 429
    assert third.json()["detail"]["type"] == "too_many_candidates"


def test_failure_after_dir_created_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, review_store, _build = _seed(tmp_path, monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(
        "hardware_splicer.project_review_store.ProjectReviewStore.create",
        boom,
    )
    response = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert response.status_code == 500
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_checks_fake_cli_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    _install_fake_cli(tmp_path, monkeypatch)
    created = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert created.status_code == 201, created.text
    checks = created.json()["candidate"]["checks"]
    assert checks["ran"] is True
    assert checks["before"]["by_type"] == {"clearance": 2}
    assert checks["after"]["by_type"] == {"clearance": 1, "hole_clearance": 1}
    assert checks["new_violations"] == 1

    _hide_kicad(monkeypatch)
    missing = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(kind="pcb", ops=PCB_ROTATE),
    )
    assert missing.status_code == 201
    assert missing.json()["candidate"]["checks"]["ran"] is False
    assert missing.json()["candidate"]["checks"]["available"] is False


def test_accept_review_creates_revision_without_changing_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, _review_store, _build = _seed(tmp_path, monkeypatch)
    created = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert created.status_code == 201
    candidate = created.json()["candidate"]
    record_path = store.root / "robot" / "candidates" / f"{candidate['candidate_id']}.json"
    before = record_path.read_bytes()
    accepted = api.post(
        f"/v1/projects/robot/reviews/{candidate['review_id']}/decision",
        json={"decision": "accepted", "actor": "owner", "note": "ok"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["review"]["decision"]["accepted_revision"] == 2
    latest = api.get("/v1/projects/robot")
    assert latest.status_code == 200
    assert latest.json()["project"]["revision"] == 2
    after = api.get(f"/v1/projects/robot/candidates/{candidate['candidate_id']}")
    assert after.status_code == 200
    assert record_path.read_bytes() == before
    assert after.json()["candidate"]["base_revision"] == 1


def test_response_never_claims_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    created = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert created.status_code == 201
    body = created.json()
    candidate = body["candidate"]
    assert candidate["verified"] is False
    assert candidate["authority"]["state"] == "proposal"
    dumped = json.dumps(body)
    assert '"passed"' not in dumped
    assert '"approved"' not in dumped
    assert candidate["checks"].get("pass") is None


def test_real_kicad_cli_drc_on_edited_pcb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = capability_probe()
    if not probe["available"]:
        pytest.skip(probe["reason"] or "kicad-cli missing")
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    created = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(kind="pcb", ops=PCB_ROTATE, note="real drc"),
    )
    assert created.status_code == 201, created.text
    checks = created.json()["candidate"]["checks"]
    assert checks["ran"] is True
    assert isinstance(checks["new_violations"], int)
    assert "description" not in json.dumps(checks)


def test_request_body_too_large_is_413(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, review_store, _build = _seed(tmp_path, monkeypatch)
    payload = b"{" + (b"0" * (MAX_REQUEST_BYTES + 8)) + b"}"
    response = api.post(
        "/v1/projects/robot/candidates",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["type"] == "request_too_large"
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_op_string_and_artifact_too_large(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, review_store, _build = _seed(tmp_path, monkeypatch)
    long_op = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(
            ops=[{"op": "set_property", "ref": "R2", "name": "Value", "value": "x" * (MAX_OP_STRING + 1)}]
        ),
    )
    assert long_op.status_code == 422
    assert long_op.json()["detail"]["type"] == "invalid_request"
    assert _candidate_dirs(tmp_path) == []
    monkeypatch.setattr(
        "hardware_splicer.project_candidates.max_kicad_content_bytes",
        lambda: 128,
    )
    huge = api.post("/v1/projects/robot/candidates", json=_create_body())
    assert huge.status_code == 422
    assert huge.json()["detail"]["type"] == "artifact_too_large"
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_author_required_with_operator_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    token = _operator_env(monkeypatch)
    api, _store, _review_store, _build = _seed(tmp_path, monkeypatch)
    headers = {"X-HS-Operator-Token": token}
    missing = api.post(
        "/v1/projects/robot/candidates",
        json={"kind": "schematic", "ops": SCH_MOVE, "note": "x"},
        headers=headers,
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["type"] == "invalid_request"
    overlong = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(author="a" * 81),
        headers=headers,
    )
    assert overlong.status_code == 422
    assert overlong.json()["detail"]["type"] == "invalid_request"
    not_string = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(author=12),
        headers=headers,
    )
    assert not_string.status_code == 422
    assert not_string.json()["detail"]["type"] == "invalid_request"
    ok = api.post(
        "/v1/projects/robot/candidates",
        json=_create_body(author="ignored"),
        headers=headers,
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["candidate"]["created_by"] == "alice"
    assert ok.json()["candidate"]["verified"] is True


def test_concurrent_posts_respect_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    api, store, _review_store, _build = _seed(tmp_path, monkeypatch)
    folder = store.root / "robot" / "candidates"
    folder.mkdir(parents=True)
    for index in range(49):
        (folder / f"cand-{index:012x}.json").write_text("{}", encoding="utf-8")
    barrier = threading.Barrier(8)
    codes: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    app = api.app

    def worker() -> None:
        client = TestClient(app)
        try:
            barrier.wait(timeout=10)
            response = client.post("/v1/projects/robot/candidates", json=_create_body())
            with lock:
                codes.append(response.status_code)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert errors == []
    assert codes.count(201) == 1
    assert codes.count(429) == 7
    assert all(code in {201, 429} for code in codes)
