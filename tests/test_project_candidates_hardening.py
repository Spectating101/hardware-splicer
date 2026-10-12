"""Regression found by an independent Codex review: the orphan sweep must not delete through a symlinked ancestor."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from hardware_splicer.artifact_retention import retain_revision_artifacts
from hardware_splicer.project_candidates import CandidateError, propose_candidate
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-hardening-path")
    build = tmp_path / "build" / "build_compilation"
    build.mkdir(parents=True)
    for name in ("spi_flash_adapter_v1.kicad_sch", "spi_flash_adapter_v1.kicad_pcb"):
        shutil.copy(REF / name, build / name)
    store = ProjectStore(tmp_path / "store")
    store.save(
        "robot",
        {"projectId": "robot", "projectName": "Robot", "currentStage": "design", "buildDir": str(tmp_path / "build"),
         "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "Hardening"}},
        expected_revision=0,
    )
    assert retain_revision_artifacts(store, "robot", 1, basis="at_save") is not None
    return store, ProjectReviewStore(store)


def test_orphan_sweep_never_deletes_through_a_symlinked_ancestor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, reviews = _seed(tmp_path, monkeypatch)
    external = tmp_path / "external"
    victim = external / "robot" / "cand-0123456789ab"
    victim.mkdir(parents=True)
    (victim / "keep.txt").write_text("not ours", encoding="utf-8")
    old = time.time() - 7200
    os.utime(victim, (old, old))
    (tmp_path / "candidates").symlink_to(external, target_is_directory=True)

    with pytest.raises(CandidateError):
        propose_candidate(
            store, "robot", kind="schematic", ops=[{"op": "move", "ref": "R2", "x_mm": 100.0, "y_mm": 82.55}],
            author="Alice", review_store=reviews,
        )

    assert (victim / "keep.txt").read_text(encoding="utf-8") == "not ours"
