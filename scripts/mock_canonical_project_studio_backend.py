#!/usr/bin/env python3
"""Extend the outsider mock with project discovery and real KiCad preview fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

import mock_outsider_jarvis_backend as base

PROJECT_ID = base.PROJECT_ID
app = base.app
state = base.state
_ORIGINAL_SNAPSHOT = base.snapshot
_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = (_ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1").resolve()
_PREVIEW_FILES = {
    "spi_flash_adapter_v1.kicad_sch": "schematic",
    "spi_flash_adapter_v1.kicad_pcb": "pcb",
}


def snapshot() -> dict[str, Any]:
    current = _ORIGINAL_SNAPSHOT()
    # Browser-only fixture metadata: exercise the production read-only artifact
    # path against the repository's canonical SPI reference design.
    current["buildDir"] = str(REFERENCE_DIR)
    current["projectPackage"] = {"build_dir": str(REFERENCE_DIR)}
    return current


# Existing outsider project routes resolve snapshot through the base module.
base.snapshot = snapshot


@app.get("/v1/projects")
def list_projects() -> dict[str, Any]:
    current = snapshot()
    return {
        "ok": True,
        "projects": [
            {
                "project_id": PROJECT_ID,
                "name": current.get("name"),
                "project_name": current.get("name"),
                "revision": state["revision"],
                "latest_revision": state["revision"],
                "archived": False,
                "saved_at": "2026-08-05T09:00:00+00:00",
            }
        ],
    }


@app.get("/v1/projects/{project_id}/revisions")
def list_project_revisions(project_id: str) -> dict[str, Any]:
    if project_id != PROJECT_ID:
        raise HTTPException(status_code=404, detail="project not found")
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "revisions": [
            {
                "revision": 6,
                "saved_at": "2026-08-05T09:00:00+00:00",
                "name": "Outsider DUT fixture",
                "current_stage": "review",
            },
            {
                "revision": 5,
                "saved_at": "2026-08-05T08:30:00+00:00",
                "name": "Outsider DUT fixture",
                "current_stage": "design",
            },
        ],
    }


@app.post("/v1/engineering/revisions/diff")
async def diff_project_revisions(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if payload.get("project_id") != PROJECT_ID:
        raise HTTPException(status_code=404, detail="project not found")
    base_revision = int(payload.get("base_revision") or 5)
    candidate_revision = int(payload.get("candidate_revision") or 6)
    if (base_revision, candidate_revision) != (5, 6):
        raise HTTPException(status_code=422, detail="fixture supports revision 5 -> 6")
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "base_revision": base_revision,
        "candidate_revision": candidate_revision,
        "automatic_merge": False,
        "release_authorized": False,
        "engineering_revision_diff": {
            "opened_blockers": [
                {
                    "blocker_id": "analysis-current",
                    "category": "analysis",
                    "severity": "error",
                    "message": "1.8 V DUT interface is not protected from 3.3 V controller",
                    "target_ids": ["level-translation"],
                    "required_evidence": ["dut-datasheet-r1", "fixture-controller-manual-r1"],
                }
            ],
            "resolved_blockers": [
                {
                    "blocker_id": "identity-controller",
                    "category": "source",
                    "severity": "warning",
                    "message": "Controller identity and source manual are now bound to the project.",
                    "target_ids": ["controller"],
                }
            ],
            "persistent_blockers": [
                {
                    "blocker_id": "physical-evidence",
                    "category": "release",
                    "severity": "warning",
                    "message": "No physical measurement closes the DUT power-on path.",
                    "target_ids": ["dut-socket"],
                }
            ],
            "changed_blockers": [],
            "identity_changes": [
                {
                    "category": "components",
                    "added_ids": ["level-translation"],
                    "removed_ids": [],
                    "retained_ids": ["controller", "dut-socket"],
                }
            ],
            "artifact_changes": [
                {
                    "artifact_id": "spi_flash_adapter_v1.kicad_sch",
                    "change": "schematic_updated",
                    "summary": "Candidate adds the translated DUT interface boundary for review.",
                }
            ],
            "execution_changes": [
                {
                    "action_id": "action-prepare-verification",
                    "change": "verification_required",
                    "summary": "Fresh deterministic verification is required for the successor revision.",
                }
            ],
            "mechanical_changes": [],
            "physical_authorization_changes": [],
            "authority_regressions": [],
            "summary": {
                "opened_blocker_count": 1,
                "resolved_blocker_count": 1,
                "persistent_blocker_count": 1,
                "artifact_change_count": 1,
                "execution_change_count": 1,
                "identity_change_category_count": 1,
                "authority_regression_count": 0,
            },
        },
    }


def _assert_fixture_build_dir(value: object) -> None:
    try:
        candidate = Path(str(value or "")).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid fixture build_dir") from exc
    if candidate != REFERENCE_DIR:
        raise HTTPException(status_code=422, detail="fixture build_dir is outside the reference design")


@app.post("/v1/build-files/list")
async def list_build_files(request: Request) -> dict[str, Any]:
    payload = await request.json()
    _assert_fixture_build_dir(payload.get("build_dir"))
    files = []
    for name, kind in _PREVIEW_FILES.items():
        path = REFERENCE_DIR / name
        files.append(
            {
                "relative": name,
                "kind": kind,
                "size_bytes": path.stat().st_size,
                "name": name,
            }
        )
    return {"ok": True, "build_dir": str(REFERENCE_DIR), "files": files}


@app.post("/v1/build-files/content")
async def read_build_file(request: Request) -> dict[str, Any]:
    payload = await request.json()
    _assert_fixture_build_dir(payload.get("build_dir"))
    relative = str(payload.get("relative") or "")
    kind = _PREVIEW_FILES.get(relative)
    if kind is None:
        raise HTTPException(status_code=422, detail="fixture preview file is not allowed")
    path = REFERENCE_DIR / relative
    return {
        "ok": True,
        "relative": relative,
        "name": path.name,
        "kind": kind,
        "size_bytes": path.stat().st_size,
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
