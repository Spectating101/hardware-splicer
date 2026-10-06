from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import threading
import time
from pathlib import Path

import pytest

from hardware_splicer.artifact_retention import (
    load_artifact_pin,
    read_pinned_artifact,
    retain_revision_artifacts,
)
from hardware_splicer.build_files_security import output_roots
from hardware_splicer.kicad_diff import diff_kicad_files, diff_kicad_text
from hardware_splicer.model3d import capability_probe
from hardware_splicer.project_candidates import (
    AUTHORITY_NOTE,
    CANDIDATE_ID_RE,
    CANDIDATE_SCHEMA,
    MAX_APPLIED_DETAIL,
    MAX_CANDIDATES_PER_PROJECT,
    MAX_DIFF_CHANGES,
    MAX_OP_STRING,
    MAX_RECORD_BYTES,
    ORPHAN_MAX_AGE_S,
    REASON_FAILED,
    REASON_TIMEOUT,
    ArtifactNotRetained,
    ArtifactTooLarge,
    CandidateIntegrityError,
    CandidateNotFound,
    CandidateValidationError,
    InvalidEdit,
    NoEffectiveChange,
    TooManyCandidates,
    _cap_stored_record,
    _require_author,
    list_candidates,
    load_candidate,
    new_violations,
    propose_candidate,
    read_candidate_file,
    run_candidate_checks,
    sanitise_filename,
    summarize_check_report,
    unique_filenames,
)
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


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, retain: bool = True) -> tuple[ProjectStore, ProjectReviewStore, Path]:
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    build = tmp_path / "build"
    _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    if retain:
        pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
        assert pin is not None
    return store, ProjectReviewStore(store), build


def _hide_kicad(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-candidates-path")


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


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


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


def test_max_candidates_constant() -> None:
    assert MAX_CANDIDATES_PER_PROJECT == 50
    assert CANDIDATE_SCHEMA == "hardware_splicer.candidate.v1"
    assert CANDIDATE_ID_RE.fullmatch("cand-" + "ab" * 6)
    assert CANDIDATE_ID_RE.fullmatch("CAND-" + "ab" * 6) is None


def test_schematic_move_opens_review_without_writing_a_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, build = _seed(tmp_path, monkeypatch)
    pin_dir = store.root / "robot" / "artifact_pins"
    blob_dir = store.root / "robot" / "artifacts"
    pin_hash = _hash_tree(pin_dir)
    blob_hash = _hash_tree(blob_dir)
    sch_bytes = (build / "build_compilation" / SCH.name).read_bytes()
    pcb_bytes = (build / "build_compilation" / PCB.name).read_bytes()
    before_text, pin_entry = read_pinned_artifact(store, "robot", 1, "schematic")
    assert before_text is not None

    result = propose_candidate(
        store,
        "robot",
        kind="schematic",
        ops=SCH_MOVE,
        author="splicer",
        note="move R2",
        review_store=review_store,
    )
    candidate = result["candidate"]
    review = result["review"]
    assert candidate["schema_version"] == CANDIDATE_SCHEMA
    assert CANDIDATE_ID_RE.fullmatch(candidate["candidate_id"])
    assert candidate["base_revision"] == 1
    assert candidate["kind"] == "schematic"
    assert candidate["created_by"] == "splicer"
    assert candidate["verified"] is False
    assert candidate["authority"]["state"] == "proposal"
    assert candidate["authority"]["note"] == AUTHORITY_NOTE
    assert candidate["diff"]["summary"]["changed"] >= 1
    assert review["review_id"] == candidate["review_id"]
    assert review["status"] == "pending"
    assert review["base_revision"] == 1
    assert store.load("robot")["revision"] == 1
    assert _hash_tree(pin_dir) == pin_hash
    assert _hash_tree(blob_dir) == blob_hash
    assert (build / "build_compilation" / SCH.name).read_bytes() == sch_bytes
    assert (build / "build_compilation" / PCB.name).read_bytes() == pcb_bytes

    cand_dirs = _candidate_dirs(tmp_path)
    assert len(cand_dirs) == 1
    assert cand_dirs[0].is_relative_to(output_roots()[0])
    sch_path = cand_dirs[0] / Path(pin_entry["relative"]).name
    assert sch_path.is_file()
    report = diff_kicad_files("schematic", SCH, sch_path)
    assert report["summary"]["changed"] >= 1
    payload, _etag = read_candidate_file(store, "robot", candidate["candidate_id"], "schematic")
    assert diff_kicad_text("schematic", before_text, payload.decode("utf-8"))["summary"]["changed"] >= 1


def test_pcb_rotate_copies_unedited_schematic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    sch_text, sch_entry = read_pinned_artifact(store, "robot", 1, "schematic")
    pcb_text, pcb_entry = read_pinned_artifact(store, "robot", 1, "pcb")
    result = propose_candidate(
        store,
        "robot",
        kind="pcb",
        ops=PCB_ROTATE,
        author="splicer",
        review_store=review_store,
    )
    candidate = result["candidate"]
    assert candidate["kind"] == "pcb"
    assert candidate["diff"]["summary"]["changed"] >= 1
    cand_dir = tmp_path / "candidates" / "robot" / candidate["candidate_id"]
    copied = (cand_dir / Path(sch_entry["relative"]).name).read_text(encoding="utf-8")
    edited = (cand_dir / Path(pcb_entry["relative"]).name).read_text(encoding="utf-8")
    assert copied == sch_text
    assert edited != pcb_text
    assert diff_kicad_text("pcb", pcb_text, edited)["summary"]["changed"] >= 1
    assert store.load("robot")["revision"] == 1


def test_no_pin_raises_artifact_not_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch, retain=False)
    with pytest.raises(ArtifactNotRetained):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_invalid_op_leaves_no_dir_record_or_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    with pytest.raises(InvalidEdit) as exc:
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=BAD_OP,
            author="splicer",
            review_store=review_store,
        )
    assert "kicad_sch" not in str(exc.value)
    assert "(kicad_sch" not in str(exc.value)
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []
    assert store.load("robot")["revision"] == 1


def test_noop_edit_is_no_effective_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    with pytest.raises(NoEffectiveChange):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=NOOP_SCH,
            author="splicer",
            review_store=review_store,
        )
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_failure_after_dir_created_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(
        "hardware_splicer.project_review_store.ProjectReviewStore.create",
        boom,
    )
    with pytest.raises(RuntimeError, match="injected failure"):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []
    assert store.load("robot")["revision"] == 1


def test_per_project_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "hardware_splicer.project_candidates.MAX_CANDIDATES_PER_PROJECT",
        2,
    )
    propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="a", review_store=review_store
    )
    propose_candidate(
        store,
        "robot",
        kind="pcb",
        ops=PCB_ROTATE,
        author="a",
        review_store=review_store,
    )
    with pytest.raises(TooManyCandidates):
        propose_candidate(
            store, "robot", kind="schematic", ops=SCH_MOVE, author="a", review_store=review_store
        )
    assert len(list_candidates(store, "robot")) == 2


def test_list_is_newest_first_and_get_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    first = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="one", review_store=review_store
    )["candidate"]
    second = propose_candidate(
        store, "robot", kind="pcb", ops=PCB_ROTATE, author="two", review_store=review_store
    )["candidate"]
    listed = list_candidates(store, "robot")
    assert [row["candidate_id"] for row in listed] == [
        second["candidate_id"],
        first["candidate_id"],
    ]
    loaded = load_candidate(store, "robot", first["candidate_id"])
    assert loaded["candidate_id"] == first["candidate_id"]
    assert loaded["created_by"] == "one"
    with pytest.raises(CandidateNotFound):
        load_candidate(store, "robot", "cand-ffffffffffff")
    with pytest.raises(CandidateNotFound):
        load_candidate(store, "robot", "../cand-aaaaaaaaaaaa")
    with pytest.raises(CandidateNotFound):
        read_candidate_file(store, "robot", "CAND-aaaaaaaaaaaa", "schematic")


def test_files_integrity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    candidate = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="splicer", review_store=review_store
    )["candidate"]
    cand_dir = tmp_path / "candidates" / "robot" / candidate["candidate_id"]
    target = next(path for path in cand_dir.iterdir() if path.suffix == ".kicad_sch")
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(CandidateIntegrityError):
        read_candidate_file(store, "robot", candidate["candidate_id"], "schematic")


def test_checks_fake_cli_by_type_masking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    _install_fake_cli(tmp_path, monkeypatch)
    candidate = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="splicer", review_store=review_store
    )["candidate"]
    checks = candidate["checks"]
    assert checks["engine"] == "kicad-cli"
    assert checks["available"] is True
    assert checks["version"] == "9.0.2-fake"
    assert checks["ran"] is True
    assert checks["reason"] is None
    assert checks["before"]["by_type"] == {"clearance": 2}
    assert checks["after"]["by_type"] == {"clearance": 1, "hole_clearance": 1}
    assert checks["before"]["total"] == 2
    assert checks["after"]["total"] == 2
    assert checks["new_violations"] == 1
    dumped = json.dumps(checks)
    assert "description" not in dumped
    assert "items" not in dumped


def test_checks_missing_kicad_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    candidate = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="splicer", review_store=review_store
    )["candidate"]
    checks = candidate["checks"]
    assert checks["available"] is False
    assert checks["ran"] is False
    assert checks["version"] is None
    assert checks["reason"]
    assert checks["new_violations"] is None


def test_accepting_review_does_not_alter_candidate_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    result = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="splicer", review_store=review_store
    )
    candidate = result["candidate"]
    record_path = store.root / "robot" / "candidates" / f"{candidate['candidate_id']}.json"
    before = record_path.read_bytes()
    decided = review_store.decide(
        "robot",
        candidate["review_id"],
        decision="accepted",
        actor="owner",
        note="take it",
    )
    assert decided["decision"]["accepted_revision"] == 2
    assert store.load("robot")["revision"] == 2
    assert record_path.read_bytes() == before
    loaded = load_candidate(store, "robot", candidate["candidate_id"])
    assert loaded["base_revision"] == 1
    assert loaded["review_id"] == candidate["review_id"]


def test_response_never_claims_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    result = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="splicer", review_store=review_store
    )
    candidate = result["candidate"]
    assert candidate["verified"] is False
    assert set(candidate["authority"]) == {"state", "note"}
    assert candidate["authority"]["state"] == "proposal"
    assert "passed" not in candidate
    assert "approved" not in candidate
    assert "pass" not in candidate.get("checks", {})


def test_real_kicad_cli_drc_on_edited_pcb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = capability_probe()
    if not probe["available"]:
        pytest.skip(probe["reason"] or "kicad-cli missing")
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    candidate = propose_candidate(
        store, "robot", kind="pcb", ops=PCB_ROTATE, author="splicer", review_store=review_store
    )["candidate"]
    checks = candidate["checks"]
    assert checks["engine"] == "kicad-cli"
    assert checks["available"] is True
    assert checks["ran"] is True
    assert isinstance(checks["before"]["errors"], int)
    assert isinstance(checks["after"]["errors"], int)
    assert isinstance(checks["new_violations"], int)
    assert "description" not in json.dumps(checks)


def _assert_clean(tmp_path: Path, store: ProjectStore, review_store: ProjectReviewStore) -> None:
    assert _candidate_dirs(tmp_path) == []
    assert _record_paths(store) == []
    assert review_store.list("robot") == []


def test_sanitise_pin_relative_with_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    build = tmp_path / "build"
    comp = build / "build_compilation"
    comp.mkdir(parents=True)
    shutil.copy(SCH, comp / "My Board.kicad_sch")
    shutil.copy(PCB, comp / "My Board.kicad_pcb")
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert pin is not None
    _text, sch_entry = read_pinned_artifact(store, "robot", 1, "schematic")
    assert sch_entry["relative"] == "build_compilation/My Board.kicad_sch"
    assert sanitise_filename(sch_entry["relative"], "schematic") == "My_Board.kicad_sch"
    names = unique_filenames(
        [
            ("schematic", "build_compilation/My Board.kicad_sch"),
            ("pcb", "build_compilation/My Board.kicad_pcb"),
        ]
    )
    assert names["schematic"] == "My_Board.kicad_sch"
    assert names["pcb"] == "My_Board.kicad_pcb"
    result = propose_candidate(
        store,
        "robot",
        kind="schematic",
        ops=SCH_MOVE,
        author="splicer",
        review_store=ProjectReviewStore(store),
    )
    cand_dir = tmp_path / "candidates" / "robot" / result["candidate"]["candidate_id"]
    assert (cand_dir / "My_Board.kicad_sch").is_file()
    assert (cand_dir / "My_Board.kicad_pcb").is_file()
    assert not (cand_dir / "My Board.kicad_sch").exists()
    payload, _etag = read_candidate_file(
        store, "robot", result["candidate"]["candidate_id"], "schematic"
    )
    assert payload


def test_injected_failures_leave_no_dir_record_or_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)

    def make_hook(expected: str):
        def hook(current: str, **_kwargs):
            if current == expected:
                raise RuntimeError(f"injected {expected}")

        return hook

    for stage in ("after_mkdir", "before_second_file", "before_record", "before_review"):
        monkeypatch.setattr(
            "hardware_splicer.project_candidates._proposal_hook",
            make_hook(stage),
        )
        with pytest.raises(RuntimeError, match=f"injected {stage}"):
            propose_candidate(
                store,
                "robot",
                kind="schematic",
                ops=SCH_MOVE,
                author="splicer",
                review_store=review_store,
            )
        _assert_clean(tmp_path, store, review_store)
        assert store.load("robot")["revision"] == 1


def test_preexisting_candidate_dir_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    taken = "aaaaaaaaaaaa"
    fresh = "bbbbbbbbbbbb"
    leftover = tmp_path / "candidates" / "robot" / f"cand-{taken}"
    leftover.mkdir(parents=True)
    marker = leftover / "keep-me.txt"
    marker.write_text("pre-existing", encoding="utf-8")
    hexes = iter([taken, fresh])

    def fake_hex(n: int) -> str:
        assert n == 6
        return next(hexes)

    monkeypatch.setattr(
        "hardware_splicer.project_candidates.secrets.token_hex",
        fake_hex,
    )
    result = propose_candidate(
        store,
        "robot",
        kind="schematic",
        ops=SCH_MOVE,
        author="splicer",
        review_store=review_store,
    )
    assert result["candidate"]["candidate_id"] == f"cand-{fresh}"
    assert leftover.is_dir()
    assert marker.read_text(encoding="utf-8") == "pre-existing"
    assert (tmp_path / "candidates" / "robot" / f"cand-{fresh}").is_dir()


def test_symlink_ancestors_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)

    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    try:
        (tmp_path / "candidates").symlink_to(outside)
        with pytest.raises(CandidateValidationError):
            propose_candidate(
                store,
                "robot",
                kind="schematic",
                ops=SCH_MOVE,
                author="splicer",
                review_store=review_store,
            )
        assert list(outside.iterdir()) == []
        _assert_clean(tmp_path, store, review_store)
    finally:
        (tmp_path / "candidates").unlink(missing_ok=True)
        shutil.rmtree(outside, ignore_errors=True)

    inside = tmp_path / "inside-alias"
    inside.mkdir()
    (tmp_path / "candidates").symlink_to(inside)
    with pytest.raises(CandidateValidationError):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    assert list(inside.iterdir()) == []
    (tmp_path / "candidates").unlink()

    (tmp_path / "candidates").mkdir()
    project_alias = tmp_path / "project-alias"
    project_alias.mkdir()
    (tmp_path / "candidates" / "robot").symlink_to(project_alias)
    with pytest.raises(CandidateValidationError):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    assert list(project_alias.iterdir()) == []
    _assert_clean(tmp_path, store, review_store)


def test_young_orphan_counts_and_stale_orphan_is_swept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    monkeypatch.setattr("hardware_splicer.project_candidates.MAX_CANDIDATES_PER_PROJECT", 1)
    young = tmp_path / "candidates" / "robot" / "cand-ffffffffffff"
    young.mkdir(parents=True)
    with pytest.raises(TooManyCandidates):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    assert young.is_dir()
    os.utime(young, (time.time() - ORPHAN_MAX_AGE_S - 10,) * 2)
    result = propose_candidate(
        store,
        "robot",
        kind="schematic",
        ops=SCH_MOVE,
        author="splicer",
        review_store=review_store,
    )
    assert not young.exists()
    assert result["candidate"]["candidate_id"] != "cand-ffffffffffff"


def test_cap_holds_under_concurrent_proposals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    folder = store.root / "robot" / "candidates"
    folder.mkdir(parents=True)
    for index in range(49):
        (folder / f"cand-{index:012x}.json").write_text("{}", encoding="utf-8")
    barrier = threading.Barrier(8)
    codes: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            propose_candidate(
                store,
                "robot",
                kind="schematic",
                ops=SCH_MOVE,
                author="splicer",
                review_store=review_store,
            )
            codes.append("ok")
        except TooManyCandidates:
            codes.append("cap")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert errors == []
    assert codes.count("ok") == 1
    assert codes.count("cap") == 7


def test_unconnected_items_count_as_new_violations() -> None:
    before = summarize_check_report({"unconnected_items": []})
    after = summarize_check_report(
        {
            "unconnected_items": [
                {"severity": "error", "description": "net N unconnected"},
            ]
        }
    )
    assert before["total"] == 0
    assert after["total"] == 1
    assert after["by_type"] == {"unconnected_items": 1}
    assert new_violations(before, after) == 1


def test_checks_flood_nonzero_stale_report_and_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, review_store, _build = _seed(tmp_path, monkeypatch)

    flood = tmp_path / "flood-kicad-cli"
    flood.write_text(
        "#!/usr/bin/python3\n"
        "import sys\n"
        'if sys.argv[1:2] == ["--version"]:\n'
        '    print("9.0.2-fake")\n'
        "    raise SystemExit(0)\n"
        "chunk = b'X' * 65536\n"
        "for _ in range(80):\n"
        "    sys.stdout.buffer.write(chunk)\n"
        "sys.stdout.buffer.flush()\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    flood.chmod(flood.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(flood))
    flooded = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="a", review_store=review_store
    )["candidate"]["checks"]
    assert flooded["ran"] is False
    assert flooded["reason"].startswith(REASON_FAILED)

    stale = tmp_path / "stale-kicad-cli"
    stale.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then printf "9.0.2-fake\\n"; exit 0; fi\n'
        "output=\"\"\n"
        "prev=\"\"\n"
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--output" ]; then output=$arg; fi\n'
        "  prev=$arg\n"
        "done\n"
        'printf \'{"violations":[{"type":"clearance","severity":"error"}]}\\n\' > "$output"\n'
        "printf 'clearance 1.27 mm\\n' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    stale.chmod(stale.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(stale))
    failed = propose_candidate(
        store, "robot", kind="pcb", ops=PCB_ROTATE, author="a", review_store=review_store
    )["candidate"]
    assert failed["checks"]["ran"] is False
    assert failed["checks"]["reason"].startswith(REASON_FAILED)
    dumped = json.dumps(failed)
    assert "clearance 1.27 mm" not in dumped
    assert "1.27" not in failed["checks"]["reason"]

    sleepy = tmp_path / "sleep-kicad-cli"
    sleepy.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then printf "9.0.2-fake\\n"; exit 0; fi\n'
        "sleep 30\n",
        encoding="utf-8",
    )
    sleepy.chmod(sleepy.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(sleepy))
    monkeypatch.setattr("hardware_splicer.project_candidates._CHECK_TIMEOUT_S", 0.4)
    timed = run_candidate_checks("schematic", "(kicad_sch)", "(kicad_sch (uuid u))", timeout_s=0.4)
    assert timed["ran"] is False
    assert timed["reason"] == REASON_TIMEOUT


def test_reason_never_includes_tool_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    script = tmp_path / "noisy-kicad-cli"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then printf "9.0.2-fake\\n"; exit 0; fi\n'
        "printf 'clearance 1.27 mm\\n' >&2\n"
        "exit 3\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(script))
    candidate = propose_candidate(
        store, "robot", kind="schematic", ops=SCH_MOVE, author="splicer", review_store=review_store
    )["candidate"]
    assert candidate["checks"]["ran"] is False
    assert candidate["checks"]["reason"].startswith(REASON_FAILED)
    assert "clearance 1.27 mm" not in json.dumps(candidate)


def test_write_time_size_and_op_string_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hide_kicad(monkeypatch)
    store, review_store, _build = _seed(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "hardware_splicer.project_candidates.max_kicad_content_bytes",
        lambda: 128,
    )
    with pytest.raises(ArtifactTooLarge):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    _assert_clean(tmp_path, store, review_store)

    calls: list[str] = []

    def wrapped(payload: bytes, *, label: str) -> None:
        calls.append(label)
        if label == "copied":
            raise ArtifactTooLarge("artifact exceeds size limit")

    monkeypatch.setattr("hardware_splicer.project_candidates._assert_write_size", wrapped)
    with pytest.raises(ArtifactTooLarge):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=SCH_MOVE,
            author="splicer",
            review_store=review_store,
        )
    assert "copied" in calls
    _assert_clean(tmp_path, store, review_store)

    with pytest.raises(CandidateValidationError):
        propose_candidate(
            store,
            "robot",
            kind="schematic",
            ops=[{"op": "set_property", "ref": "R2", "name": "Value", "value": "x" * (MAX_OP_STRING + 1)}],
            author="splicer",
            review_store=review_store,
        )
    _assert_clean(tmp_path, store, review_store)


def test_stored_record_truncates_detail_and_changes() -> None:
    record = {
        "applied": [{"detail": "d" * (MAX_APPLIED_DETAIL + 40), "op": "move"}],
        "diff": {
            "changes": [{"n": index} for index in range(MAX_DIFF_CHANGES + 80)],
            "limits": {},
        },
    }
    capped = _cap_stored_record(record)
    assert len(capped["applied"][0]["detail"]) == MAX_APPLIED_DETAIL
    assert len(capped["diff"]["changes"]) == MAX_DIFF_CHANGES
    assert capped["diff"]["limits"]["truncated"] is True
    huge = {
        "applied": [],
        "diff": {
            "changes": [{"blob": "x" * 4000} for _ in range(MAX_DIFF_CHANGES)],
            "limits": {},
        },
    }
    assert len(json.dumps(huge)) > MAX_RECORD_BYTES
    trimmed = _cap_stored_record(huge)
    assert trimmed["diff"]["changes"] == []
    assert trimmed["diff"]["limits"]["truncated"] is True
    assert len(json.dumps(trimmed, indent=2, sort_keys=True)) <= MAX_RECORD_BYTES


def test_author_required_even_when_verified() -> None:
    with pytest.raises(CandidateValidationError):
        _require_author(None)
    with pytest.raises(CandidateValidationError):
        _require_author("x" * 81)
    with pytest.raises(CandidateValidationError):
        _require_author(12)
