from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import pytest

from hardware_splicer.artifact_retention import (
    PIN_SCHEMA,
    ArtifactIntegrityError,
    ArtifactPinConflict,
    install_at_save_retention,
    load_artifact_pin,
    read_pinned_artifact,
    retain_revision_artifacts,
)
from hardware_splicer.kicad_diff import diff_kicad_text
from hardware_splicer.project_store import ProjectStore, RevisionConflict

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


def _snapshot(build_dir: Path) -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "buildDir": str(build_dir),
    }


def _copy_reference(build: Path) -> Path:
    comp = build / "build_compilation"
    comp.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCH, comp / SCH.name)
    shutil.copy(PCB, comp / PCB.name)
    (comp / "notes.txt").write_text("not kicad\n", encoding="utf-8")
    (comp / "board.kicad_pro").write_text("(kicad_pro (version 1))\n", encoding="utf-8")
    return comp


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


def _digest_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_retain_at_save_writes_pin_and_blobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    build = allowed / "job-1"
    comp = _copy_reference(build)
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(allowed))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)

    store = ProjectStore(tmp_path / "store")
    envelope = store.save("robot", _snapshot(build), expected_revision=0)
    before = _hash_tree(store.root / "robot")

    pin = retain_revision_artifacts(store, "robot", envelope["revision"], basis="at_save")
    assert pin is not None
    assert pin["schema_version"] == "hardware_splicer.artifact_pins.v1"
    assert pin["retention_basis"] == "at_save"
    assert pin["revision"] == 1

    sch_hex = _digest_hex(comp / SCH.name)
    pcb_hex = _digest_hex(comp / PCB.name)
    assert pin["artifacts"]["schematic"] == {
        "relative": f"build_compilation/{SCH.name}",
        "sha256": f"sha256:{sch_hex}",
        "size_bytes": (comp / SCH.name).stat().st_size,
    }
    assert pin["artifacts"]["pcb"]["sha256"] == f"sha256:{pcb_hex}"
    assert (store.root / "robot" / "artifacts" / "sha256" / sch_hex[:2] / sch_hex).read_bytes() == (
        comp / SCH.name
    ).read_bytes()
    assert (store.root / "robot" / "artifacts" / "sha256" / pcb_hex[:2] / pcb_hex).is_file()
    assert _hash_tree(store.root / "robot") == before


def test_retain_uses_last_engineering_ai_session_build_dir(tmp_path: Path) -> None:
    last = tmp_path / "last-session"
    _copy_reference(last)
    store = ProjectStore(tmp_path / "store")
    snapshot = {
        "projectId": "robot",
        "projectName": "Robot",
        "engineeringAiSessions": [
            {"buildDir": ""},
            {"buildDir": str(last)},
        ],
    }
    store.save("robot", snapshot, expected_revision=0)
    pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert pin is not None
    assert pin["artifacts"]["schematic"]["sha256"] == f"sha256:{_digest_hex(last / 'build_compilation' / SCH.name)}"


def test_earlier_ai_session_build_dir_is_ignored(tmp_path: Path) -> None:
    earlier = tmp_path / "earlier"
    later = tmp_path / "later"
    _copy_reference(earlier)
    _copy_reference(later)
    sch = later / "build_compilation" / SCH.name
    sch.write_text(sch.read_text(encoding="utf-8").replace(R2_VALUE, R2_VALUE_NEW, 1), encoding="utf-8")
    store = ProjectStore(tmp_path / "store")
    snapshot = {
        "projectId": "robot",
        "engineeringAiSessions": [
            {"buildDir": str(earlier)},
            {"project_package": {"build_dir": str(later)}},
        ],
    }
    store.save("robot", snapshot, expected_revision=0)
    pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert pin is not None
    assert pin["artifacts"]["schematic"]["sha256"] == f"sha256:{_digest_hex(sch)}"
    assert pin["artifacts"]["schematic"]["sha256"] != f"sha256:{_digest_hex(earlier / 'build_compilation' / SCH.name)}"


def test_second_identical_retain_is_idempotent(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    first = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    second = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert first is not None and second is not None
    assert first["artifacts"] == second["artifacts"]
    assert first["retained_at"] == second["retained_at"]


def test_different_bytes_same_revision_conflict(tmp_path: Path) -> None:
    build = tmp_path / "build"
    comp = _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    retain_revision_artifacts(store, "robot", 1, basis="at_save")
    sch = comp / SCH.name
    sch.write_text(sch.read_text(encoding="utf-8").replace(R2_VALUE, R2_VALUE_NEW, 1), encoding="utf-8")
    with pytest.raises(ArtifactPinConflict):
        retain_revision_artifacts(store, "robot", 1, basis="after_save")


def test_after_save_new_revision_diff_shows_edits(tmp_path: Path) -> None:
    build = tmp_path / "build"
    comp = _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    pin_a = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert pin_a is not None

    sch = comp / SCH.name
    pcb = comp / PCB.name
    sch.write_text(sch.read_text(encoding="utf-8").replace(R2_VALUE, R2_VALUE_NEW, 1), encoding="utf-8")
    pcb.write_text(pcb.read_text(encoding="utf-8").replace(SEGMENT_WIDTH, SEGMENT_WIDTH_NEW, 1), encoding="utf-8")

    store.save("robot", _snapshot(build), expected_revision=1)
    pin_b = retain_revision_artifacts(store, "robot", 2, basis="after_save")
    assert pin_b is not None
    assert pin_b["retention_basis"] == "after_save"

    sch_a, _ = read_pinned_artifact(store, "robot", 1, "schematic") or (None, None)
    sch_b, _ = read_pinned_artifact(store, "robot", 2, "schematic") or (None, None)
    pcb_a, _ = read_pinned_artifact(store, "robot", 1, "pcb") or (None, None)
    pcb_b, _ = read_pinned_artifact(store, "robot", 2, "pcb") or (None, None)
    assert sch_a and sch_b and pcb_a and pcb_b

    sch_diff = diff_kicad_text("schematic", sch_a, sch_b)
    pcb_diff = diff_kicad_text("pcb", pcb_a, pcb_b)
    sch_row = next(row for row in sch_diff["changes"] if row["ref"] == "R2")
    assert "value 10k -> 4.7k" in sch_row["details"]
    pcb_row = next(row for row in pcb_diff["changes"] if row["change"] == "changed" and row["item_type"] == "segment")
    assert "width 0.2 -> 0.35" in pcb_row["details"]


def test_missing_pin_read_returns_none(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", {"projectId": "robot"}, expected_revision=0)
    assert load_artifact_pin(store, "robot", 1) is None
    assert read_pinned_artifact(store, "robot", 1, "schematic") is None


def test_tampered_blob_raises_integrity_error(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert pin is not None
    digest = pin["artifacts"]["schematic"]["sha256"].split(":", 1)[1]
    blob = store.root / "robot" / "artifacts" / "sha256" / digest[:2] / digest
    blob.write_bytes(blob.read_bytes() + b"tamper")
    with pytest.raises(ArtifactIntegrityError):
        read_pinned_artifact(store, "robot", 1, "schematic")


def test_symlink_build_dir_and_files_are_skipped(tmp_path: Path) -> None:
    real = tmp_path / "real"
    _copy_reference(real)
    linked = tmp_path / "linked-build"
    linked.symlink_to(real)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(linked), expected_revision=0)
    assert retain_revision_artifacts(store, "robot", 1, basis="at_save") is None

    build = tmp_path / "build"
    comp = build / "build_compilation"
    comp.mkdir(parents=True)
    (comp / SCH.name).symlink_to(real / "build_compilation" / SCH.name)
    (comp / PCB.name).symlink_to(real / "build_compilation" / PCB.name)
    store.save("robot", _snapshot(build), expected_revision=1)
    assert retain_revision_artifacts(store, "robot", 2, basis="at_save") is None


def test_outside_allowed_root_retains_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    _copy_reference(outside)
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(allowed))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)

    store = ProjectStore(tmp_path / "store")
    envelope = store.save("robot", _snapshot(outside), expected_revision=0)
    assert envelope["revision"] == 1
    assert retain_revision_artifacts(store, "robot", 1, basis="at_save") is None
    assert load_artifact_pin(store, "robot", 1) is None
    assert not (store.root / "robot" / "artifact_pins").exists()


def test_non_kicad_files_never_retained(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
    assert pin is not None
    relatives = {
        entry["relative"]
        for entry in pin["artifacts"].values()
        if entry is not None
    }
    assert all(rel.endswith((".kicad_sch", ".kicad_pcb")) for rel in relatives)
    blob_root = store.root / "robot" / "artifacts"
    for path in blob_root.rglob("*"):
        if path.is_file():
            assert not path.name.endswith((".txt", ".kicad_pro"))


def test_retention_does_not_change_revision_or_manifest_bytes(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(build), expected_revision=0)
    project_dir = store.root / "robot"
    before = _hash_tree(project_dir)
    rev_bytes = (project_dir / "revisions" / "00000001.json").read_bytes()
    manifest_bytes = (project_dir / "project.json").read_bytes()
    retain_revision_artifacts(store, "robot", 1, basis="at_save")
    sch_a, _ = read_pinned_artifact(store, "robot", 1, "schematic") or (None, None)
    assert sch_a is not None
    diff_kicad_text("schematic", sch_a, sch_a)
    assert (project_dir / "revisions" / "00000001.json").read_bytes() == rev_bytes
    assert (project_dir / "project.json").read_bytes() == manifest_bytes
    assert _hash_tree(project_dir) == before


class ExtraKeywordStore(ProjectStore):
    def save(
        self,
        project_id: str,
        snapshot: Mapping[str, Any],
        *,
        expected_revision: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        envelope = super().save(
            project_id,
            snapshot,
            expected_revision=expected_revision,
            metadata=metadata,
        )
        body = dict(envelope)
        body["tag"] = tag
        return body


def test_wrapped_save_forwards_extra_keywords(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = install_at_save_retention(ExtraKeywordStore(tmp_path / "store"))
    envelope = store.save("robot", _snapshot(build), expected_revision=0, tag="extra-kw")
    assert envelope["tag"] == "extra-kw"
    assert envelope["revision"] == 1
    pin = load_artifact_pin(store, "robot", 1)
    assert pin is not None
    assert pin["artifacts"]["schematic"] is not None


def test_wrapped_save_propagates_conflict_without_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    calls: list[tuple[Any, ...]] = []

    def track(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "hardware_splicer.artifact_retention.retain_revision_artifacts",
        track,
    )
    store = install_at_save_retention(ProjectStore(tmp_path / "store"))
    first = store.save("robot", _snapshot(build), expected_revision=0)
    assert first["revision"] == 1
    assert len(calls) == 1
    with pytest.raises(RevisionConflict, match="expected 0"):
        store.save("robot", _snapshot(build), expected_revision=0)
    assert len(calls) == 1
    assert store.load("robot")["revision"] == 1
    assert load_artifact_pin(store, "robot", 2) is None


def _valid_pin_entry() -> dict[str, Any]:
    return {
        "relative": "build_compilation/board.kicad_sch",
        "sha256": "sha256:" + ("ab" * 32),
        "size_bytes": 12,
    }


def _valid_pin(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": PIN_SCHEMA,
        "project_id": "robot",
        "revision": 1,
        "retained_at": "2026-01-01T00:00:00+00:00",
        "retention_basis": "at_save",
        "artifacts": {"schematic": _valid_pin_entry(), "pcb": None},
    }
    body.update(overrides)
    return body


def _write_pin_file(store: ProjectStore, payload: Mapping[str, Any], revision: int = 1) -> None:
    path = store.root / "robot" / "artifact_pins" / f"{revision:08d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


_CORRUPT_PIN_CASES = [
    ("revision-string", _valid_pin(revision="x")),
    ("revision-mismatch", _valid_pin(revision=2)),
    ("project-mismatch", _valid_pin(project_id="other")),
    ("schema-mismatch", _valid_pin(schema_version="nope")),
    ("invalid-basis", _valid_pin(retention_basis="whenever")),
    ("artifacts-list", _valid_pin(artifacts=["schematic"])),
    ("artifacts-missing-key", _valid_pin(artifacts={"schematic": _valid_pin_entry()})),
    (
        "artifacts-extra-key",
        _valid_pin(artifacts={"schematic": _valid_pin_entry(), "pcb": None, "extra": None}),
    ),
    ("entry-not-mapping", _valid_pin(artifacts={"schematic": "bad", "pcb": None})),
    (
        "relative-not-str",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "relative": 1}, "pcb": None}),
    ),
    (
        "relative-dotdot",
        _valid_pin(
            artifacts={"schematic": {**_valid_pin_entry(), "relative": "../x.kicad_sch"}, "pcb": None}
        ),
    ),
    (
        "relative-absolute",
        _valid_pin(
            artifacts={"schematic": {**_valid_pin_entry(), "relative": "/abs.kicad_sch"}, "pcb": None}
        ),
    ),
    (
        "relative-backslash-dotdot",
        _valid_pin(
            artifacts={"schematic": {**_valid_pin_entry(), "relative": "..\\x.kicad_sch"}, "pcb": None}
        ),
    ),
    (
        "relative-dotdot-slash",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "relative": "../x"}, "pcb": None}),
    ),
    (
        "relative-embedded-dotdot",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "relative": "a/../b"}, "pcb": None}),
    ),
    (
        "relative-abs-slash",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "relative": "/abs"}, "pcb": None}),
    ),
    (
        "relative-drive-prefix",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "relative": "C:\\x"}, "pcb": None}),
    ),
    (
        "relative-empty",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "relative": ""}, "pcb": None}),
    ),
    (
        "relative-nul",
        _valid_pin(
            artifacts={"schematic": {**_valid_pin_entry(), "relative": "x\x00.kicad_sch"}, "pcb": None}
        ),
    ),
    (
        "sha256-not-str",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "sha256": 123}, "pcb": None}),
    ),
    (
        "sha256-bad-pattern",
        _valid_pin(
            artifacts={"schematic": {**_valid_pin_entry(), "sha256": "sha256:ABC"}, "pcb": None}
        ),
    ),
    (
        "size-negative",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "size_bytes": -1}, "pcb": None}),
    ),
    (
        "size-string",
        _valid_pin(artifacts={"schematic": {**_valid_pin_entry(), "size_bytes": "1"}, "pcb": None}),
    ),
    ("retained-at-missing", {key: value for key, value in _valid_pin().items() if key != "retained_at"}),
    ("retained-at-none", _valid_pin(retained_at=None)),
    ("retained-at-yesterday", _valid_pin(retained_at="yesterday")),
    ("retained-at-naive", _valid_pin(retained_at="2026-01-01T00:00:00")),
    ("retained-at-offset", _valid_pin(retained_at="2026-01-01T00:00:00+08:00")),
]


@pytest.mark.parametrize("label,payload", _CORRUPT_PIN_CASES)
def test_corrupt_pin_raises_integrity_error(tmp_path: Path, label: str, payload: dict[str, Any]) -> None:
    store = ProjectStore(tmp_path)
    _write_pin_file(store, payload)
    with pytest.raises(ArtifactIntegrityError, match="artifact pin is corrupt"):
        load_artifact_pin(store, "robot", 1)
    assert label


def test_valid_pin_relative_is_accepted(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    payload = _valid_pin(
        artifacts={
            "schematic": {**_valid_pin_entry(), "relative": "build_compilation/x.kicad_sch"},
            "pcb": None,
        }
    )
    _write_pin_file(store, payload)
    pin = load_artifact_pin(store, "robot", 1)
    assert pin is not None
    assert pin["artifacts"]["schematic"]["relative"] == "build_compilation/x.kicad_sch"


def test_valid_pin_retained_at_zulu_is_accepted(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    _write_pin_file(store, _valid_pin(retained_at="2026-01-01T00:00:00Z"))
    pin = load_artifact_pin(store, "robot", 1)
    assert pin is not None
    assert pin["retained_at"] == "2026-01-01T00:00:00Z"


class OddEnvelopeStore(ProjectStore):
    def __init__(self, root: Path, returned: Any) -> None:
        super().__init__(root)
        self.returned = returned

    def save(self, *args: Any, **kwargs: Any) -> Any:
        return self.returned


@pytest.mark.parametrize(
    "returned",
    [
        {"project_id": "robot"},
        {"project_id": "robot", "revision": "x"},
        ["not-an-envelope"],
    ],
    ids=["missing-revision", "revision-string", "non-dict"],
)
def test_wrapper_never_raises_on_odd_envelope(tmp_path: Path, returned: Any) -> None:
    store = install_at_save_retention(OddEnvelopeStore(tmp_path, returned))
    assert store.save("robot", {"projectId": "robot"}) is returned


def _schematic_blob(store: ProjectStore, pin: Mapping[str, Any]) -> Path:
    digest = str(pin["artifacts"]["schematic"]["sha256"]).split(":", 1)[1]
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
def test_existing_blob_tamper_is_integrity_error_and_wrapper_does_not_raise(
    tmp_path: Path, tamper
) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    store = install_at_save_retention(ProjectStore(tmp_path / "store"))
    store.save("robot", _snapshot(build), expected_revision=0)
    pin = load_artifact_pin(store, "robot", 1)
    assert pin is not None
    tamper(_schematic_blob(store, pin))
    with pytest.raises(ArtifactIntegrityError, match="retained artifact failed hash verification"):
        retain_revision_artifacts(store, "robot", 1, basis="after_save")
    envelope = store.save("robot", _snapshot(build), expected_revision=1)
    assert envelope["revision"] == 2
    recorded = store._hs_retention_results[("robot", 2)]
    assert recorded["status"] == "failed"
    assert recorded["reason"] == "retained artifact failed hash verification"
