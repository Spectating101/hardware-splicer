"""Original project rules remain exact inputs to retained candidate checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from hardware_splicer.artifact_retention import (
    ArtifactIntegrityError, ArtifactPinConflict, ArtifactRetentionError,
    install_at_save_retention, load_artifact_pin, read_pinned_artifact_bytes,
    read_pinned_artifact_sidecars, retain_revision_artifacts,
    validate_kicad_rule_bytes,
)
from hardware_splicer.kicad_edit import apply_edit_ops
from hardware_splicer.project_candidates import (
    CandidateIntegrityError, preview_edit, propose_candidate, run_candidate_checks,
    validate_candidate_review_artifacts,
)
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "hardware/reference_designs/spi_flash_adapter_v1"
STEM = "donor board.v1"
TRACK = "0abb31d8-7d09-4cf1-9b15-9cb8ff1c70fb"
OPS = [{"op": "set_track_width", "uuid": TRACK, "width_mm": .35}]
RULES = b'''# Original source rule, retained verbatim.
(version 1)
(rule "OriginalBundleMinimumWidth"
  (condition "A.Type == 'Track'")
  (constraint track_width (min 0.3mm)))
'''


def seed(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    build = tmp_path / "source"
    build.mkdir()
    board = build / (STEM + ".kicad_pcb")
    board.write_bytes((REFERENCE / "spi_flash_adapter_v1.kicad_pcb").read_bytes())
    (build / (STEM + ".kicad_pro")).write_bytes((REFERENCE / "spi_flash_adapter_v1.kicad_pro").read_bytes())
    (build / (STEM + ".kicad_dru")).write_bytes(RULES)
    (build / "unrelated.kicad_dru").write_text("not a companion")
    store = install_at_save_retention(ProjectStore(tmp_path / "store"))
    snapshot = {"projectId": "donor", "projectName": "Original PCB", "buildDir": str(build),
                "machineProject": {"project_id": "donor", "name": "Original PCB", "purpose": "Keep original source rules"}}
    store.save("donor", snapshot, expected_revision=0)
    return store, ProjectReviewStore(store), build


def hidden_cli(monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-rule-sidecar-test")


def test_retained_bundle_rules_survive_preview_proposal_acceptance_and_later_source_changes(tmp_path, monkeypatch):
    store, reviews, build = seed(tmp_path, monkeypatch)
    hidden_cli(monkeypatch)
    original_revision = store.load("donor", revision=1)
    original_pin = load_artifact_pin(store, "donor", 1)
    companions = read_pinned_artifact_sidecars(store, "donor", 1, "pcb")
    assert set(companions) == {"project", "rules"}
    assert companions["rules"][0] == RULES
    assert original_pin["sidecars"]["pcb"]["rules"]["relative"] == STEM + ".kicad_dru"
    preview = preview_edit(store, "donor", kind="pcb", ops=OPS, base_revision=1)
    assert preview["sidecars"]["rules"]["sha256"] == companions["rules"][1]["sha256"]
    result = propose_candidate(store, "donor", kind="pcb", ops=OPS, author="operator", base_revision=1, review_store=reviews)
    candidate = result["candidate"]
    folder = tmp_path / "candidates/donor" / candidate["candidate_id"]
    assert (folder / "donor_board.v1.kicad_dru").read_bytes() == RULES
    assert (folder / "donor_board.v1.kicad_pro").read_bytes() == companions["project"][0]
    assert not (folder / "unrelated.kicad_dru").exists()
    assert candidate["checks"]["source_context"]["rule_scope"] == "retained_project_and_custom_rules"
    validate_candidate_review_artifacts(store, "donor", candidate["review_id"])
    reviews.decide("donor", candidate["review_id"], decision="accepted", actor="verified-operator")
    accepted = read_pinned_artifact_sidecars(store, "donor", 2, "pcb")
    assert accepted["rules"][0] == RULES
    assert accepted["project"][0] == companions["project"][0]
    assert accepted["rules"][1]["relative"] == "donor_board.v1.kicad_dru"
    assert read_pinned_artifact_bytes(store, "donor", 1, "pcb")[0] != read_pinned_artifact_bytes(store, "donor", 2, "pcb")[0]
    (build / (STEM + ".kicad_dru")).write_bytes(b"(version 1)\n")
    assert store.load("donor", revision=1) == original_revision
    assert load_artifact_pin(store, "donor", 1) == original_pin
    assert read_pinned_artifact_sidecars(store, "donor", 1, "pcb")["rules"][0] == RULES
    with pytest.raises(ArtifactPinConflict):
        retain_revision_artifacts(store, "donor", 1, basis="after_save")


def test_rule_hash_and_exact_bundle_inventory_are_revalidated_before_acceptance(tmp_path, monkeypatch):
    store, reviews, _ = seed(tmp_path, monkeypatch)
    hidden_cli(monkeypatch)
    candidate = propose_candidate(store, "donor", kind="pcb", ops=OPS, author="operator", review_store=reviews)["candidate"]
    folder = tmp_path / "candidates/donor" / candidate["candidate_id"]
    (folder / "donor_board.v1.kicad_dru").write_bytes(b"(version 1)\n")
    with pytest.raises(CandidateIntegrityError, match="hash"):
        validate_candidate_review_artifacts(store, "donor", candidate["review_id"])
    assert store.load("donor")["revision"] == 1
    (folder / "donor_board.v1.kicad_dru").write_bytes(RULES)
    (folder / "unrecorded.kicad_pro").write_text("{}")
    with pytest.raises(CandidateIntegrityError, match="unrecorded"):
        validate_candidate_review_artifacts(store, "donor", candidate["review_id"])


def test_distinct_original_project_stems_cannot_inherit_one_sided_rules_after_acceptance(tmp_path, monkeypatch):
    store, reviews, build = seed(tmp_path, monkeypatch)
    hidden_cli(monkeypatch)
    # The schematic name sanitizes to the same stem as the retained PCB, but
    # it is a different source project and has no associated rule companions.
    (build / "donor_board.v1.kicad_sch").write_bytes((REFERENCE / "spi_flash_adapter_v1.kicad_sch").read_bytes())
    store.save("donor", store.load("donor")["snapshot"], expected_revision=1)
    assert read_pinned_artifact_sidecars(store, "donor", 2, "schematic") == {}
    candidate = propose_candidate(store, "donor", kind="pcb", ops=OPS, author="operator", base_revision=2, review_store=reviews)["candidate"]
    pcb_name = candidate["files"]["pcb"]["relative"]
    schematic_name = candidate["files"]["schematic"]["relative"]
    assert Path(pcb_name).stem != Path(schematic_name).stem
    folder = tmp_path / "candidates/donor" / candidate["candidate_id"]
    assert not (folder / Path(schematic_name).with_suffix(".kicad_pro")).exists()
    assert not (folder / Path(schematic_name).with_suffix(".kicad_dru")).exists()
    validate_candidate_review_artifacts(store, "donor", candidate["review_id"])
    reviews.decide("donor", candidate["review_id"], decision="accepted", actor="verified-operator")
    assert read_pinned_artifact_sidecars(store, "donor", 3, "schematic") == {}
    assert read_pinned_artifact_sidecars(store, "donor", 3, "pcb")["rules"][0] == RULES


def test_sidecars_cannot_escape_matching_stem_or_follow_symlinks(tmp_path, monkeypatch):
    store, _, build = seed(tmp_path, monkeypatch)
    rule = build / (STEM + ".kicad_dru")
    rule.unlink()
    rule.symlink_to(build / "unrelated.kicad_dru")
    with pytest.raises(ArtifactRetentionError, match="sidecar"):
        retain_revision_artifacts(store, "donor", 1, basis="after_save")
    pin_path = store.root / "donor/artifact_pins/00000001.json"
    pin = json.loads(pin_path.read_text())
    pin["sidecars"]["pcb"]["rules"]["relative"] = "../outside.kicad_dru"
    pin_path.write_text(json.dumps(pin))
    with pytest.raises(ArtifactIntegrityError):
        read_pinned_artifact_sidecars(store, "donor", 1, "pcb")


@pytest.mark.parametrize("raw", [
    b'(version 1)\n(include "/tmp/outside.kicad_dru")',
    b'(version 1)\n(rule "bad" (include "outside"))',
    b'(version 1)\n(rule "bad" ((include "outside")))',
    b'(version 1)\n(rule "bad" (constraint clearance (include "outside")))',
    b'(version 2)', b'(version 1',
])
def test_unsupported_custom_rule_directives_cannot_be_silently_ignored(raw):
    with pytest.raises(ValueError):
        validate_kicad_rule_bytes(raw)


def test_valid_rule_comments_and_quoted_condition_text_are_preserved():
    raw = b'''# Header comment
(version 1) # inline comment
(rule "Quoted # name" (condition "A.NetName == '#signal'") (constraint track_width (min 0.3mm)))
'''
    before = hashlib.sha256(raw).hexdigest()
    validate_kicad_rule_bytes(raw)
    assert hashlib.sha256(raw).hexdigest() == before


def test_candidate_checks_refuse_unknown_rules_before_invoking_native_tool(monkeypatch):
    monkeypatch.setattr("hardware_splicer.project_candidates.capability_probe", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr("hardware_splicer.project_candidates.resolve_kicad_cli", lambda: "/not-invoked-kicad")
    def forbidden(*args, **kwargs):
        raise AssertionError("an unsupported rule file must not reach native execution")
    monkeypatch.setattr("hardware_splicer.project_candidates.run_bounded", forbidden)
    checks = run_candidate_checks("pcb", "(kicad_pcb)", "(kicad_pcb)",
                                  sidecars={"rules": b'(version 1)\n(include "/tmp/outside")'})
    assert checks["ran"] is False
    assert checks["reason"] == "retained custom rules are unsupported or malformed"


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="native KiCad DRC unavailable")
def test_native_candidate_verdict_uses_original_custom_rules_after_filename_sanitizing(tmp_path, monkeypatch):
    store, reviews, _ = seed(tmp_path, monkeypatch)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", shutil.which("kicad-cli"))
    base = read_pinned_artifact_bytes(store, "donor", 1, "pcb")[0].decode()
    edited = apply_edit_ops("pcb", base, OPS)["text"]
    bare = run_candidate_checks("pcb", base, edited)
    candidate = propose_candidate(store, "donor", kind="pcb", ops=OPS, author="operator", review_store=reviews)["candidate"]
    scoped = candidate["checks"]
    assert bare["ran"] and scoped["ran"], (bare, scoped)
    original_width_errors = scoped["before"]["by_type"].get("track_width", 0)
    assert original_width_errors > bare["before"]["by_type"].get("track_width", 0)
    assert scoped["after"]["by_type"]["track_width"] == original_width_errors - 1
    assert scoped["source_context"]["sidecar_sha256"]["rules"] == "sha256:" + hashlib.sha256(RULES).hexdigest()
    impact = reviews.get("donor", candidate["review_id"])["candidate_snapshot"]["sourceRevisionImpact"]
    assert impact["basis"] == "native_candidate_edit"
    assert impact["families"]["native_rule_checks"]["status"] == "rechecked_candidate_only"
    assert impact["families"]["native_rule_checks"]["artifact_sha256"] == candidate["edited_sha256"]
    for family in ("mechanical_fit", "wiring", "materials", "firmware", "model3d", "manufacturing_package"):
        assert impact["families"][family]["status"] == "requires_recheck"


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="native KiCad CLI unavailable")
def test_native_candidate_verdict_uses_original_custom_rule_under_check_filename_stem(tmp_path, monkeypatch):
    store, _, _ = seed(tmp_path, monkeypatch)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", shutil.which("kicad-cli"))
    before = read_pinned_artifact_bytes(store, "donor", 1, "pcb")[0].decode()
    after = apply_edit_ops("pcb", before, OPS)["text"]
    companions = read_pinned_artifact_sidecars(store, "donor", 1, "pcb")
    bare = run_candidate_checks("pcb", before, after)
    original = run_candidate_checks("pcb", before, after, sidecars={role: data for role, (data, _) in companions.items()})
    assert bare["ran"] and original["ran"], (bare, original)
    assert original["before"]["by_type"].get("track_width", 0) > bare["before"]["by_type"].get("track_width", 0)
    assert original["before"]["by_type"]["track_width"] > original["after"]["by_type"]["track_width"]
    assert original["source_context"]["sidecar_sha256"]["rules"] == "sha256:" + hashlib.sha256(RULES).hexdigest()
