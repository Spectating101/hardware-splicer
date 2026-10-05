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


# --- Review threads: in-memory mirror of the /v1/projects/{id}/threads contract -------------------------
# Real implementation: src/hardware_splicer/project_thread_store.py. This mock keeps the same shapes and
# error contract ({detail:{type,message}}) so the browser paths can be exercised without a project root.
import itertools
from datetime import datetime, timezone

_THREAD_AUTHOR_KINDS = {"human", "agent", "system"}
# Mock operator registry. The real one is hashed tokens in HARDWARE_SPLICER_OPERATOR_TOKENS (operator_identity.py).
_MOCK_OPERATORS = {"demo-operator-token": {"id": "demo-operator", "kind": "human"}}


def _operator_from_request(request: Request) -> dict[str, str] | None:
    # Only the dedicated header: the UI proxy also forwards "Authorization: Bearer <app API key>" for app auth.
    token = request.headers.get("x-hs-operator-token")
    if not token:
        return None
    operator = _MOCK_OPERATORS.get(token)
    if operator is None:
        raise _thread_error(401, "operator_token_invalid", "The operator token is not recognised.")
    return operator
_THREAD_EVENT_TYPES = {"comment", "resolve", "reopen"}
_thread_ids = itertools.count(1)
_threads: dict[str, dict[str, Any]] = {}


def _thread_error(status: int, kind: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"type": kind, "message": message})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _thread_status(thread: dict[str, Any]) -> str:
    status = "open"
    for event in thread["events"]:
        if event["type"] == "resolve":
            status = "resolved"
        elif event["type"] == "reopen":
            status = "open"
    return status


def _thread_summary(thread: dict[str, Any]) -> dict[str, Any]:
    events = thread["events"]
    return {
        **{key: value for key, value in thread.items() if key != "events"},
        "status": _thread_status(thread),
        "comment_count": sum(1 for event in events if event["type"] == "comment"),
        "last_event_at": events[-1]["created_at"],
    }


def _thread_full(thread: dict[str, Any]) -> dict[str, Any]:
    return {**_thread_summary(thread), "events": list(thread["events"])}


def _clean_author(author: Any) -> dict[str, str]:
    if not isinstance(author, dict) or set(author) - {"kind", "id"}:
        raise _thread_error(422, "invalid_request", "author must be {kind, id} only")
    kind, ident = author.get("kind"), str(author.get("id") or "").strip()
    if kind not in _THREAD_AUTHOR_KINDS or not 1 <= len(ident) <= 120:
        raise _thread_error(422, "invalid_request", "author needs a kind (human|agent|system) and an id")
    return {"kind": kind, "id": ident}


def _verified_author(author: Any, operator: dict[str, str]) -> dict[str, str]:
    if author is not None and (not isinstance(author, dict) or any(author.get(k) not in (None, operator[k]) for k in ("kind", "id"))):
        raise _thread_error(422, "invalid_request", "author does not match the verified operator")
    return {"kind": operator["kind"], "id": operator["id"]}


def _new_event(thread: dict[str, Any], event_type: str, author: Any, body: Any, operator: dict[str, str] | None = None) -> dict[str, Any]:
    if event_type not in _THREAD_EVENT_TYPES:
        raise _thread_error(422, "invalid_request", "event type must be comment, resolve or reopen")
    text = str(body or "").strip()
    if event_type == "comment" and not 1 <= len(text) <= 4000:
        raise _thread_error(422, "invalid_request", "a comment needs 1 to 4000 characters")
    status = _thread_status(thread) if thread["events"] else "open"
    if event_type == "resolve" and status != "open":
        raise _thread_error(409, "thread_state", "thread is already resolved")
    if event_type == "reopen" and status != "resolved":
        raise _thread_error(409, "thread_state", "thread is not resolved")
    return {
        "seq": len(thread["events"]) + 1,
        "type": event_type,
        "author": _verified_author(author, operator) if operator else _clean_author(author),
        "author_verified": operator is not None,
        **({"verified_by": "operator-token"} if operator else {}),
        "body": text,
        "created_at": _now(),
    }


def _seed_thread() -> None:
    thread_id = f"thread-fixture{next(_thread_ids):04d}"
    thread = {
        "schema_version": "hardware_splicer.review_thread.v1",
        "thread_id": thread_id,
        "project_id": PROJECT_ID,
        "anchor": {"revision": 6, "object_id": "level-translation", "finding_ref": None, "artifact": None},
        "created_at": "2026-08-05T09:10:00+00:00",
        "events": [],
    }
    thread["events"].append({**_new_event(thread, "comment", {"kind": "human", "id": "fixture-reviewer"},
                                          "Is the translator still powered when JP1 is open? The 1.8 V side needs a defined level first."),
                             "created_at": "2026-08-05T09:10:00+00:00"})
    _threads[thread_id] = thread


_seed_thread()


def _seed_pinned_thread() -> None:
    thread_id = f"thread-fixture{next(_thread_ids):04d}"
    thread = {
        "schema_version": "hardware_splicer.review_thread.v1",
        "thread_id": thread_id,
        "project_id": PROJECT_ID,
        "anchor": {
            "revision": 6,
            "object_id": "level-translation",
            "finding_ref": None,
            "artifact": {"relative": "spi_flash_adapter_v1.kicad_sch", "kind": "schematic"},
            "position": {"x_mm": 103.0, "y_mm": 84.5},
        },
        "created_at": "2026-08-05T09:20:00+00:00",
        "events": [],
    }
    thread["events"].append({**_new_event(thread, "comment", {"kind": "human", "id": "fixture-reviewer"},
                                          "OE is tied through R7 here; check it stays low until JP1 is bridged."),
                             "created_at": "2026-08-05T09:20:00+00:00"})
    _threads[thread_id] = thread


_seed_pinned_thread()


def _require_project(project_id: str) -> None:
    if project_id != PROJECT_ID:
        raise _thread_error(404, "not_found", "project not found")


@app.get("/v1/projects/{project_id}/threads")
def list_threads(project_id: str, object_id: str | None = None, status: str | None = None) -> dict[str, Any]:
    _require_project(project_id)
    rows = [_thread_summary(thread) for thread in _threads.values()]
    if object_id:
        rows = [row for row in rows if row["anchor"].get("object_id") == object_id]
    if status:
        rows = [row for row in rows if row["status"] == status]
    rows.sort(key=lambda row: row["last_event_at"], reverse=True)
    return {"ok": True, "threads": rows}


@app.post("/v1/projects/{project_id}/threads", status_code=201)
async def create_thread(project_id: str, request: Request) -> dict[str, Any]:
    _require_project(project_id)
    operator = _operator_from_request(request)
    payload = await request.json()
    anchor = payload.get("anchor")
    if not isinstance(anchor, dict) or set(anchor) - {"revision", "object_id", "finding_ref", "artifact", "position"}:
        raise _thread_error(422, "invalid_request", "anchor must use revision, object_id, finding_ref or artifact only")
    revision = anchor.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or not 1 <= revision <= state["revision"]:
        raise _thread_error(422, "invalid_request", "anchor.revision must be an existing project revision")
    if not (anchor.get("object_id") or anchor.get("finding_ref") or anchor.get("artifact")):
        raise _thread_error(422, "invalid_request", "anchor needs an object_id, finding_ref or artifact")
    position = anchor.get("position")
    if position is not None:
        valid = (
            isinstance(position, dict)
            and anchor.get("artifact")
            and set(position) == {"x_mm", "y_mm"}
            and all(isinstance(position[k], (int, float)) and not isinstance(position[k], bool) and abs(position[k]) <= 1e5 for k in position)
        )
        if not valid:
            raise _thread_error(422, "invalid_request", "position needs numeric x_mm and y_mm and an artifact")
    thread = {
        "schema_version": "hardware_splicer.review_thread.v1",
        "thread_id": f"thread-mock{next(_thread_ids):04d}",
        "project_id": PROJECT_ID,
        "anchor": {"revision": revision, "object_id": anchor.get("object_id"), "finding_ref": anchor.get("finding_ref"), "artifact": anchor.get("artifact"), "position": position},
        "created_at": _now(),
        "events": [],
    }
    thread["events"].append(_new_event(thread, "comment", payload.get("author"), payload.get("body"), operator))
    _threads[thread["thread_id"]] = thread
    return {"ok": True, "thread": _thread_full(thread)}


@app.get("/v1/projects/{project_id}/threads/{thread_id}")
def get_thread(project_id: str, thread_id: str) -> dict[str, Any]:
    _require_project(project_id)
    thread = _threads.get(thread_id)
    if thread is None:
        raise _thread_error(404, "not_found", "thread not found")
    return {"ok": True, "thread": _thread_full(thread)}


@app.post("/v1/projects/{project_id}/threads/{thread_id}/events", status_code=201)
async def append_thread_event(project_id: str, thread_id: str, request: Request) -> dict[str, Any]:
    _require_project(project_id)
    thread = _threads.get(thread_id)
    if thread is None:
        raise _thread_error(404, "not_found", "thread not found")
    operator = _operator_from_request(request)
    payload = await request.json()
    expected = payload.get("expected_event_seq")
    if expected is not None and expected != len(thread["events"]):
        raise _thread_error(409, "thread_conflict", "thread changed since it was loaded")
    event = _new_event(thread, str(payload.get("type") or ""), payload.get("author"), payload.get("body"), operator)
    thread["events"].append(event)
    return {"ok": True, "event": event}


# --- Finding provenance: real projection when available -------------------------------------------------
# The projection lives in src/hardware_splicer/finding_provenance.py (a separate change). When it is not
# importable the mock reports no recorded provenance, which the UI must present as "not recorded".
def _load_hs_attr(module: str, attribute: str):
    """Import a hardware_splicer attribute even though scripts/hardware_splicer.py shadows the package here."""
    import importlib
    import sys

    scripts_dir = Path(__file__).resolve().parent
    saved_path = list(sys.path)
    shadow = sys.modules.get("hardware_splicer")
    if shadow is not None and Path(getattr(shadow, "__file__", "") or "").resolve().parent == scripts_dir:
        sys.modules.pop("hardware_splicer")
    sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != scripts_dir]
    try:
        return getattr(importlib.import_module(f"hardware_splicer.{module}"), attribute)
    except (ImportError, AttributeError):
        return None
    finally:
        sys.path[:] = saved_path


_project_findings = _load_hs_attr("finding_provenance", "project_findings")


@app.get("/v1/projects/{project_id}/findings")
def list_findings(project_id: str, revision: str | None = None) -> dict[str, Any]:
    _require_project(project_id)
    findings = _project_findings(snapshot(), state["revision"]) if _project_findings else []
    return {"ok": True, "project_id": PROJECT_ID, "revision": state["revision"], "findings": findings}


# --- Artifact diff: real kicad_diff over a fixture "Rev 5" ---------------------------------------------
# The mock has one build directory, so Rev 5 is the reference design with two small edits applied. Real
# projects get both sides from retained, content-addressed artifacts (a separate backend change).
import re

_diff_kicad_text = _load_hs_attr("kicad_diff", "diff_kicad_text")


def _fixture_base_text(kind: str, candidate_text: str) -> str:
    if kind == "schematic":
        return re.sub(r'(\(property "Value" ")10k(")', r"\g<1>4.7k\2", candidate_text, count=1)
    base = candidate_text.replace("(width 0.2)", "(width 0.3)", 1)
    extra = (
        '\t(segment\n\t\t(start 150 90)\n\t\t(end 160 90)\n\t\t(width 0.2)\n\t\t(layer "F.Cu")\n'
        '\t\t(net 1)\n\t\t(uuid "00000000-0000-4000-8000-000000000001")\n\t)\n'
    )
    cut = base.rstrip().rfind(")")
    return base[:cut] + extra + base[cut:]


@app.get("/v1/projects/{project_id}/artifact-diff")
def artifact_diff(project_id: str, base: int, candidate: int, kind: str = "schematic") -> dict[str, Any]:
    _require_project(project_id)
    if kind not in {"schematic", "pcb"}:
        raise HTTPException(status_code=422, detail={"type": "invalid_request", "message": "kind must be schematic or pcb"})
    if base not in (5, 6) or candidate not in (5, 6):
        return {"ok": True, "project_id": PROJECT_ID, "available": False, "reason": f"Revision {base if base not in (5, 6) else candidate} has no retained artifact."}
    if _diff_kicad_text is None:
        return {"ok": True, "project_id": PROJECT_ID, "available": False, "reason": "This mock was started without the kicad_diff module."}
    name = "spi_flash_adapter_v1.kicad_sch" if kind == "schematic" else "spi_flash_adapter_v1.kicad_pcb"
    reference = (REFERENCE_DIR / name).read_text(encoding="utf-8", errors="replace")
    texts = {6: reference, 5: _fixture_base_text(kind, reference)}
    diff = _diff_kicad_text(kind, texts[base], texts[candidate])
    return {
        "ok": True,
        "project_id": PROJECT_ID,
        "base_revision": base,
        "candidate_revision": candidate,
        "kind": kind,
        "available": True,
        "artifact": {"base": {"relative": name}, "candidate": {"relative": name}},
        "diff": diff,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
