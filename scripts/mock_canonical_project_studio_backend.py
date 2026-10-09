#!/usr/bin/env python3
"""Extend the outsider mock with project discovery and real KiCad preview fixtures."""

from __future__ import annotations

import os
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
    raw = path.read_bytes()
    return {
        "ok": True,
        "relative": relative,
        "name": path.name,
        "kind": kind,
        "size_bytes": len(raw),
        # Of the exact bytes, like the real endpoint, so the viewer can compare it with a retained file's hash.
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "content": raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n"),
    }


# --- Review threads: in-memory mirror of the /v1/projects/{id}/threads contract -------------------------
# Real implementation: src/hardware_splicer/project_thread_store.py. This mock keeps the same shapes and
# error contract ({detail:{type,message}}) so the browser paths can be exercised without a project root.
import itertools
from datetime import datetime, timezone
from uuid import uuid4

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
    _publish("thread.created", thread["thread_id"], 1)
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
    _publish("thread.event", thread_id, event["seq"])
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


# --- 3D model: fixture over kicad-cli ---------------------------------------------------------------
# The real implementation (src/hardware_splicer/model3d.py) works from retained, hash-verified revision artifacts.
# This fixture renders the reference board for revisions 5 and 6 and reports unavailable when kicad-cli is absent.
import hashlib
import shutil
import subprocess
import tempfile

from fastapi.responses import Response

_GLB_CACHE: dict[int, bytes] = {}


def _fixture_glb(revision: int) -> bytes | None:
    if revision in _GLB_CACHE:
        return _GLB_CACHE[revision]
    binary = shutil.which("kicad-cli")
    if binary is None:
        return None
    reference = (REFERENCE_DIR / "spi_flash_adapter_v1.kicad_pcb").read_text(encoding="utf-8", errors="replace")
    text = reference if revision == 6 else _fixture_base_text("pcb", reference)
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "board.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        out = Path(tmp) / "board.glb"
        completed = subprocess.run(
            [binary, "pcb", "export", "glb", "--force", "--subst-models", "--include-tracks", "--include-pads",
             "--include-zones", "--output", str(out), str(board)],
            capture_output=True, timeout=90, env={"PATH": "/usr/bin:/bin", "HOME": tmp}, check=False,
        )
        if completed.returncode != 0 or not out.is_file():
            return None
        _GLB_CACHE[revision] = out.read_bytes()
    return _GLB_CACHE[revision]


@app.get("/v1/projects/{project_id}/revisions/{revision}/model3d")
def model3d_meta(project_id: str, revision: int) -> dict[str, Any]:
    _require_project(project_id)
    if revision not in (5, 6):
        return {"ok": True, "revision": revision, "available": False, "reason": f"Revision {revision} has no retained pcb."}
    data = _fixture_glb(revision)
    if data is None:
        return {"ok": True, "revision": revision, "available": False, "reason": "kicad-cli is not installed on this host, so no 3D model can be generated."}
    digest = hashlib.sha256(data).hexdigest()
    return {
        "ok": True,
        "revision": revision,
        "available": True,
        "model": {
            "format": "glb",
            "sha256": digest,
            "size_bytes": len(data),
            "generated_with": "kicad-cli (fixture)",
            "url": f"/v1/projects/{project_id}/revisions/{revision}/model3d/glb",
        },
    }


@app.get("/v1/projects/{project_id}/revisions/{revision}/model3d/glb")
def model3d_glb(project_id: str, revision: int) -> Response:
    _require_project(project_id)
    data = _fixture_glb(revision) if revision in (5, 6) else None
    if data is None:
        raise _thread_error(404, "not_found", "no 3D model for this revision")
    return Response(content=data, media_type="model/gltf-binary", headers={"ETag": f'"sha256:{hashlib.sha256(data).hexdigest()}"', "Cache-Control": "private, max-age=3600"})


# --- Parts: the real extraction code over the fixture schematic (revisions 5 and 6 only) -----------------------
_build_assembly_plan = _load_hs_attr("assembly_plan", "build_assembly_plan")


@app.get("/v1/projects/{project_id}/revisions/{revision}/assembly-plan")
def assembly_plan(project_id: str, revision: int) -> dict[str, Any]:
    """The real plan builder run on the reference board, as the real API would run it on a retained one."""

    _require_project(project_id)
    if _build_assembly_plan is None or revision not in (5, 6):
        return {"ok": True, "revision": revision, "available": False, "reason": "no retained pcb"}
    text = (REFERENCE_DIR / "spi_flash_adapter_v1.kicad_pcb").read_text(encoding="utf-8")
    return {"ok": True, "revision": revision, "available": True, "plan": _build_assembly_plan(text, pcb_sha256="sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest())}


# --- Whole-device plans: the real planner, stateless, exactly as the real API serves it -------------------------------
_build_device_plan = _load_hs_attr("device_plan", "build_device_plan")
_DevicePlanError = _load_hs_attr("device_plan", "DevicePlanError")
_example_device_specs = _load_hs_attr("device_plan", "example_specs")
_device_module_library = _load_hs_attr("device_plan", "module_library")


@app.get("/v1/devices/modules")
def device_modules() -> dict[str, Any]:
    return {"ok": True, "library": _device_module_library()}


@app.get("/v1/devices/examples")
def device_examples() -> dict[str, Any]:
    return {"ok": True, "examples": _example_device_specs()}


@app.get("/v1/devices/examples/{example_id}/plan")
def device_example_plan(example_id: str) -> dict[str, Any]:
    examples = _example_device_specs()
    if example_id not in examples:
        raise _thread_error(404, "not_found", "no such example")
    return {"ok": True, "spec": examples[example_id], "plan": _build_device_plan(examples[example_id])}


@app.post("/v1/devices/plan")
async def device_plan_post(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise _thread_error(422, "invalid_device_spec", "the body is not JSON") from None
    spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
    try:
        return {"ok": True, "plan": _build_device_plan(spec)}
    except _DevicePlanError as exc:
        raise _thread_error(422, "invalid_device_spec", str(exc)) from None


# --- Boards a person describes: the real capture code, stateless, as the real API serves it ----------------------------
_build_donor_plan = _load_hs_attr("donor_capture", "build_donor_salvage_plan")
_DonorCaptureError = _load_hs_attr("donor_capture", "DonorCaptureError")
_donor_options = _load_hs_attr("donor_capture", "capture_options")


@app.get("/v1/donors/options")
def donor_options() -> dict[str, Any]:
    return {"ok": True, "options": _donor_options()}


@app.post("/v1/donors/salvage-plan")
async def donor_salvage_plan(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise _thread_error(422, "invalid_donor_capture", "the body is not JSON") from None
    try:
        return {"ok": True, "plan": _build_donor_plan(body)}
    except _DonorCaptureError as exc:
        raise _thread_error(422, "invalid_donor_capture", str(exc)) from None


_build_salvage_plan = _load_hs_attr("salvage_plan", "build_salvage_plan")


@app.get("/v1/projects/{project_id}/revisions/{revision}/salvage-plan")
def salvage_plan(project_id: str, revision: int) -> dict[str, Any]:
    """The real take-apart planner run on the reference board, as the real API would run it on a retained one."""

    _require_project(project_id)
    if _build_salvage_plan is None or revision not in (5, 6):
        return {"ok": True, "revision": revision, "available": False, "reason": "no retained pcb"}
    text = (REFERENCE_DIR / "spi_flash_adapter_v1.kicad_pcb").read_text(encoding="utf-8")
    return {"ok": True, "revision": revision, "available": True, "plan": _build_salvage_plan(text, pcb_sha256="sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest())}


_generate_glb = _load_hs_attr("model3d", "generate_glb")
_BOARD_ONLY_FLAGS = _load_hs_attr("model3d", "BOARD_ONLY_GLB_FLAGS")
_board_glb_cache: dict[str, bytes] = {}


@app.get("/v1/projects/{project_id}/revisions/{revision}/assembly-plan/board.glb")
def assembly_board_glb(project_id: str, revision: int) -> Response:
    """The real bare-board export (kicad-cli) of the reference board, when kicad-cli is present."""

    _require_project(project_id)
    if _generate_glb is None or _BOARD_ONLY_FLAGS is None or revision not in (5, 6):
        raise _thread_error(404, "not_found", "revision has no board model")
    if "board" not in _board_glb_cache:
        try:
            _board_glb_cache["board"] = _generate_glb((REFERENCE_DIR / "spi_flash_adapter_v1.kicad_pcb").read_text(encoding="utf-8"), flags=_BOARD_ONLY_FLAGS)
        except Exception:
            raise _thread_error(404, "not_found", "revision has no board model") from None
    return Response(content=_board_glb_cache["board"], media_type="model/gltf-binary", headers={"Cache-Control": "private, max-age=60"})


_extract_components = _load_hs_attr("parts_intel", "extract_components")
_build_bom = _load_hs_attr("parts_intel", "build_bom")


@app.get("/v1/projects/{project_id}/revisions/{revision}/artifacts")
def revision_artifacts(project_id: str, revision: int) -> dict[str, Any]:
    """The retained files of a revision with their hashes, as the real artifact pin reports them (revisions 5 and 6)."""

    _require_project(project_id)
    if revision not in (5, 6):
        raise _thread_error(404, "not_found", f"Revision {revision} was not found.")
    artifacts: dict[str, Any] = {}
    for kind, name in (("schematic", "spi_flash_adapter_v1.kicad_sch"), ("pcb", "spi_flash_adapter_v1.kicad_pcb")):
        text = (REFERENCE_DIR / name).read_text(encoding="utf-8", errors="replace")
        if revision == 5:
            text = _fixture_base_text(kind, text)
        data = text.encode("utf-8")
        artifacts[kind] = {"relative": name, "sha256": "sha256:" + hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    return {"ok": True, "revision": revision, "pin": {"schema_version": "hardware_splicer.artifact_pins.v1", "project_id": project_id,
                                                      "revision": revision, "retention_basis": "at_save", "artifacts": artifacts}}


@app.get("/v1/projects/{project_id}/revisions/{revision}/artifacts/{kind}/file")
def revision_artifact_file(project_id: str, revision: int, kind: str) -> Response:
    """A revision's retained file as text (revisions 5 and 6), like the real endpoint."""

    _require_project(project_id)
    if kind not in {"schematic", "pcb"}:
        raise _thread_error(422, "invalid_request", "kind must be schematic or pcb")
    if revision not in (5, 6):
        raise _thread_error(404, "artifact_not_retained", f"Revision {revision} has no retained {kind}.")
    name = "spi_flash_adapter_v1.kicad_sch" if kind == "schematic" else "spi_flash_adapter_v1.kicad_pcb"
    text = (REFERENCE_DIR / name).read_text(encoding="utf-8", errors="replace")
    if revision == 5:
        text = _fixture_base_text(kind, text)
    return Response(text.encode("utf-8"), media_type="text/plain; charset=utf-8")


_render_packet = _load_hs_attr("review_packet", "render_review_packet_markdown")
_packet_integrity = _load_hs_attr("review_packet", "_integrity")
_OMITTED = "[text omitted]"


@app.get("/v1/projects/{project_id}/review-packet")
def review_packet(project_id: str, revision: int | None = None, format: str = "json", include_text: bool = True) -> Response:
    """A packet in the real shape, built from this fixture's data and rendered by the real Markdown renderer."""

    _require_project(project_id)
    if format not in {"json", "markdown"}:
        raise _thread_error(422, "invalid_request", "format must be json or markdown")
    rev = revision or state["revision"]
    if rev not in (5, 6):
        raise _thread_error(404, "not_found", f"Revision {rev} was not found.")
    files = {}
    for kind, name in (("schematic", "spi_flash_adapter_v1.kicad_sch"), ("pcb", "spi_flash_adapter_v1.kicad_pcb")):
        text = (REFERENCE_DIR / name).read_text(encoding="utf-8", errors="replace")
        data = (_fixture_base_text(kind, text) if rev == 5 else text).encode("utf-8")
        files[kind] = {"relative": name, "sha256": "sha256:" + hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    proposals = [{
        "candidate_id": c["candidate_id"], "kind": c["kind"], "created_by": c["created_by"], "created_by_verified": c["verified"],
        "note": c.get("note") or None, "changes": c["diff"].get("summary"),
        "operations_total": len(c.get("applied", [])), "operations_truncated": False,
        "operations": [{"op": a.get("op"), "target": (a.get("target") or {}).get("ref"), "detail": a.get("detail")} for a in c.get("applied", [])],
        "checks": {"ran": False, "engine": "kicad-cli", "new_violations": None, "reason": "kicad-cli is not available"},
        "decision": {"status": c["review_state"]["status"], "decided_by": c["review_state"]["decided_by"], "note": c["review_state"]["note"],
                     "accepted_revision": c["review_state"]["accepted_revision"], "out_of_date": False},
    } for c in _candidates.values() if c["base_revision"] == rev]
    packet = {
        "schema_version": "hardware_splicer.review_packet.v1",
        "project": {"project_id": project_id, "name": "Outsider DUT fixture", "revision": rev, "saved_at": None, "snapshot_sha256": "sha256:" + "0" * 64},
        "retained_files": {"status": "retained", "retention_basis": "at_save", "files": files},
        "findings": {"total": 0, "listed": 0, "truncated": False, "by_category": {}, "by_provenance": {}, "attested": 0, "items": []},
        "proposals": {"total": len(proposals), "listed": len(proposals), "truncated": False, "pending": 0, "accepted": 0, "rejected": 0, "items": proposals},
        "discussion": {"status": "listed", "total": 0, "listed": 0, "truncated": False, "open": 0, "resolved": 0, "threads": []},
        "not_established": ["That the design has been fabricated, assembled, powered or physically measured."],
        "authority": "This packet does not open, record or imply fabrication, power-on or release authority.",
        "redactions": {"count": 0, "by_kind": {}, "note": "fixture"},
        "integrity": {"algorithm": "fixture", "packet_sha256": "sha256:" + "1" * 64},
    }
    packet["free_text"] = {"included": include_text, "omitted": 0, "note": "Comments, notes and finding text are included (credential-like strings and absolute paths removed on a best-effort basis)." if include_text else "Comments, notes and finding text are left out. Who did what and when, the file hashes and the counts are all here."}
    if not include_text:
        # The same policy as the real packet: names, notes, paths and values are left out; so is any name only typed.
        omitted = 1
        packet["project"]["name"] = _OMITTED
        packet["project"]["project_id"] = "project-" + hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:12]
        for kind in ("schematic", "pcb"):
            packet["retained_files"]["files"][kind]["relative"] = _OMITTED
            omitted += 1
        for item in packet["proposals"]["items"]:
            for key in ("note",):
                if item[key]:
                    item[key] = _OMITTED; omitted += 1
            if not item["created_by_verified"]:
                item["created_by"] = _OMITTED; omitted += 1
            if item["decision"]["note"]:
                item["decision"]["note"] = _OMITTED; omitted += 1
            for op in item["operations"]:
                op["target"] = _OMITTED if op["target"] else None
                op["detail"] = _OMITTED if op["detail"] else None
                omitted += 2
        packet["free_text"]["omitted"] = omitted
    if _packet_integrity is not None:
        packet["integrity"] = _packet_integrity(packet)
    if format == "markdown" and _render_packet is not None:
        return Response(_render_packet(packet).encode("utf-8"), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{packet["project"]["project_id"]}-r{rev}-review-packet{"" if include_text else "-no-text"}.md"'})
    return Response(_json.dumps({"ok": True, "packet": packet}), media_type="application/json")


@app.get("/v1/projects/{project_id}/revisions/{revision}/parts")
def revision_parts(project_id: str, revision: int, enrich: bool = False) -> dict[str, Any]:
    _require_project(project_id)
    enrichment: dict[str, Any] = {"requested": bool(enrich), "providers": [], "performed": False}
    if revision not in (5, 6) or _extract_components is None or _build_bom is None:
        return {"ok": True, "project_id": PROJECT_ID, "revision": revision, "available": False,
                "reason": f"Revision {revision} has no retained schematic artifact.", "enrichment": enrichment}
    text = (REFERENCE_DIR / "spi_flash_adapter_v1.kicad_sch").read_text(encoding="utf-8", errors="replace")
    if revision == 5:
        text = _fixture_base_text("schematic", text)
    bom = _build_bom(_extract_components(text))
    if enrich:
        enrichment["reason"] = "no providers enabled"
    return {"ok": True, "project_id": PROJECT_ID, "revision": revision, "available": True,
            "source": {"relative": "spi_flash_adapter_v1.kicad_sch", "sha256": None, "retention_basis": "at_save"},
            "summary": bom["summary"], "components": [], "bom_groups": bom["groups"], "enrichment": enrichment}


# --- Candidate proposals: the real edit engine and diff over the fixture revisions (in memory) -----------------
# Real implementation: src/hardware_splicer/project_candidates*.py (writes a candidate dir and opens a staged review).
_apply_edit_ops = _load_hs_attr("kicad_edit", "apply_edit_ops")
_candidates: dict[str, dict[str, Any]] = {}
_candidate_files: dict[str, str] = {}


_ROUTING_REASON = "set HARDWARE_SPLICER_FREEROUTING_JAR to a FreeRouting jar"
# HS_MOCK_ROUTING=available makes the fixture behave as a server where FreeRouting is installed.
_ROUTING_AVAILABLE = os.environ.get("HS_MOCK_ROUTING") == "available"


@app.get("/v1/projects/{project_id}/routing")
def routing_capability(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    return {"ok": True, "project_id": project_id, "routing": {
        "available": _ROUTING_AVAILABLE, "reason": None if _ROUTING_AVAILABLE else _ROUTING_REASON,
        "components": {"kicad_python": {"ok": True, "version": "9.0.2"}, "java": {"ok": _ROUTING_AVAILABLE, "version": None}, "freerouting_jar": {"ok": _ROUTING_AVAILABLE, "version": None}}}}


@app.get("/v1/projects/{project_id}/candidates")
def candidates_list(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    rows = sorted(_candidates.values(), key=lambda row: row["created_at"], reverse=True)
    return {"ok": True, "project_id": project_id, "candidates": rows[:100]}


@app.post("/v1/projects/{project_id}/candidates", status_code=201)
async def candidates_create(project_id: str, request: Request) -> dict[str, Any]:
    _require_project(project_id)
    payload = await request.json()
    kind = payload.get("kind")
    ops = payload.get("ops")
    author = str(payload.get("author") or "").strip()
    autoroute = payload.get("autoroute")
    if autoroute is not None:
        if kind != "pcb" or ops:
            raise _thread_error(422, "invalid_request", "autoroute applies to the PCB and cannot be combined with ops")
        if not _ROUTING_AVAILABLE:
            raise _thread_error(409, "routing_unavailable", _ROUTING_REASON)
        ops = []
    elif kind not in {"schematic", "pcb"} or not isinstance(ops, list) or not ops:
        raise _thread_error(422, "invalid_request", "kind, ops and author are required")
    if not author or len(author) > 80:
        raise _thread_error(422, "invalid_request", "kind, ops and author are required")
    if _apply_edit_ops is None or _diff_kicad_text is None:
        raise _thread_error(409, "artifact_not_retained", "This mock was started without the edit engine.")
    base_rev = payload.get("base_revision") or state["revision"]
    if base_rev not in (5, 6):
        raise _thread_error(409, "artifact_not_retained", f"Revision {base_rev} has no retained artifact.")
    name = "spi_flash_adapter_v1.kicad_sch" if kind == "schematic" else "spi_flash_adapter_v1.kicad_pcb"
    reference = (REFERENCE_DIR / name).read_text(encoding="utf-8", errors="replace")
    base_text = reference if base_rev == 6 else _fixture_base_text(kind, reference)
    operator = _operator_from_request(request)
    if autoroute is not None:
        track = '\t(segment\n\t\t(start 150 70)\n\t\t(end 165 70)\n\t\t(width 0.2)\n\t\t(layer "F.Cu")\n\t\t(net 1)\n\t\t(uuid "00000000-0000-4000-8000-0000000000aa")\n\t)\n'
        cut = base_text.rstrip().rfind(")")
        edited = {"text": base_text[:cut] + track + base_text[cut:], "warnings": ["A routed board is a candidate: not DRC-clean, verified or fabrication-ready."],
                  "applied": [{"index": 0, "op": "autoroute", "target": {"engine": "fixture-router"}, "detail": "1 segments and 0 vias added; fixture only"}]}
    else:
        try:
            edited = _apply_edit_ops(kind, base_text, ops)
        except Exception as exc:  # KicadEditError: message never echoes file content
            raise _thread_error(422, "invalid_edit", str(exc)[:300])
    diff = _diff_kicad_text(kind, base_text, edited["text"])
    if not (diff.get("changes")):
        raise _thread_error(422, "no_effective_change", "The edits leave the file unchanged.")
    cid = "cand-" + uuid4().hex[:12]
    record = {
        "schema_version": "hardware_splicer.candidate.v1", "candidate_id": cid, "project_id": project_id,
        "base_revision": base_rev, "kind": kind, "review_id": "review-" + uuid4().hex[:8],
        "created_by": operator["id"] if operator else author, "verified": operator is not None, "note": str(payload.get("note") or "")[:500],
        "files": {kind: {"relative": name, "retained_relative": name, "sha256": None}},
        "created_at": datetime.now(timezone.utc).isoformat(), "applied": edited.get("applied", []),
        "warnings": edited.get("warnings", []), "diff": diff,
        "checks": {"engine": "kicad-cli", "available": False, "ran": False, "reason": "kicad-cli is not available"},
        "authority": {"state": "proposal", "note": "A candidate is a proposal. Accepting its review does not mark anything verified, fabrication-ready or release-ready."},
        "review_state": {"status": "pending", "decided_by": None, "decided_at": None, "note": None, "accepted_revision": None, "stale": False},
    }
    _candidates[cid] = record
    _candidate_files[cid] = edited["text"]
    _publish("review.opened", record["review_id"])
    return {"ok": True, "candidate": record, "review": {"review_id": record["review_id"], "status": "pending"}}


@app.get("/v1/projects/{project_id}/candidates/{candidate_id}")
def candidates_get(project_id: str, candidate_id: str) -> dict[str, Any]:
    _require_project(project_id)
    if candidate_id not in _candidates:
        raise _thread_error(404, "not_found", "Candidate not found")
    return {"ok": True, "candidate": _candidates[candidate_id]}


@app.post("/v1/projects/{project_id}/candidates/preview")
async def candidates_preview(project_id: str, request: Request) -> dict[str, Any]:
    """Dry run: the edited file and its diff, nothing stored (like the real service)."""

    _require_project(project_id)
    payload = await request.json()
    kind = payload.get("kind")
    ops = payload.get("ops")
    if kind not in {"schematic", "pcb"} or not isinstance(ops, list) or not ops:
        raise _thread_error(422, "invalid_request", "kind and ops are required")
    if _apply_edit_ops is None or _diff_kicad_text is None:
        raise _thread_error(409, "artifact_not_retained", "This mock was started without the edit engine.")
    base_rev = payload.get("base_revision") or state["revision"]
    if base_rev not in (5, 6):
        raise _thread_error(404, "not_found", f"Revision {base_rev} was not found.")
    name = "spi_flash_adapter_v1.kicad_sch" if kind == "schematic" else "spi_flash_adapter_v1.kicad_pcb"
    reference = (REFERENCE_DIR / name).read_text(encoding="utf-8", errors="replace")
    base_text = reference if base_rev == 6 else _fixture_base_text(kind, reference)
    try:
        edited = _apply_edit_ops(kind, base_text, ops)
    except Exception as exc:
        raise _thread_error(422, "invalid_edit", str(exc)[:300])
    diff = _diff_kicad_text(kind, base_text, edited["text"])
    if not diff.get("changes"):
        raise _thread_error(422, "no_effective_change", "The edits leave the file unchanged.")
    return {"ok": True, "preview": {"base_revision": base_rev, "kind": kind, "relative": name, "text": edited["text"],
                                    "applied": edited.get("applied", []), "warnings": edited.get("warnings", []), "diff": diff}}


@app.post("/v1/projects/{project_id}/candidates/{candidate_id}/decision")
async def candidates_decide(project_id: str, candidate_id: str, request: Request) -> dict[str, Any]:
    _require_project(project_id)
    payload = await request.json()
    operator = _operator_from_request(request)
    if operator is None:
        raise _thread_error(401, "operator_token_required", "an operator token is required to accept or reject a proposal")
    record = _candidates.get(candidate_id)
    if record is None:
        raise _thread_error(404, "not_found", "Candidate not found")
    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in {"accepted", "rejected"}:
        raise _thread_error(422, "invalid_request", "decision must be accepted or rejected")
    if record["review_state"]["status"] != "pending":
        raise _thread_error(409, "review_conflict", "this proposal has already been decided")
    # Fixture limitation: accepting does not add a revision here, so the other specs keep seeing Rev 6.
    record["review_state"] = {
        "status": decision, "decided_by": operator["id"], "decided_at": datetime.now(timezone.utc).isoformat(),
        "note": str(payload.get("note") or "")[:500] or None,
        "accepted_revision": record["base_revision"] + 1 if decision == "accepted" else None, "stale": False,
    }
    _publish("review.event", record["review_id"], 1)
    return {"ok": True, "candidate": record, "review_state": record["review_state"]}


@app.get("/v1/projects/{project_id}/candidates/{candidate_id}/files/{kind}")
def candidates_file(project_id: str, candidate_id: str, kind: str) -> Response:
    _require_project(project_id)
    record = _candidates.get(candidate_id)
    if record is None or record["kind"] != kind:
        raise _thread_error(404, "not_found", "Candidate file not found")
    return Response(_candidate_files[candidate_id], media_type="text/plain; charset=utf-8")


# --- Live events + presence: in-memory mirror of the /events and /presence contract ----------------------
# Real implementation: src/hardware_splicer/project_events*.py (filesystem-derived, multi-process safe).
import asyncio
import json as _json
import re
import time

from fastapi.responses import StreamingResponse

_event_log: list[dict[str, Any]] = []
_presence: dict[str, dict[str, Any]] = {}
_PRESENCE_TTL = 45.0
_CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _publish(kind: str, ident: str, seq: int | None = None) -> None:
    _event_log.append({"type": kind, "id": ident, "seq": seq})


# Thread writes above call _publish so the stream mirrors them (the real service derives them from the thread files).


@app.get("/v1/projects/{project_id}/events")
async def project_events(project_id: str, request: Request) -> StreamingResponse:
    _require_project(project_id)

    async def frames():
        cursor = len(_event_log)
        yield "event: hello\ndata: " + _json.dumps({"project_id": project_id, "revision": state["revision"], "threads": len(_threads), "poll_seconds": 0.25}) + "\n\n"
        idle = 0.0
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                return
            if len(_event_log) > cursor:
                changes, cursor = _event_log[cursor:], len(_event_log)
                yield "event: change\ndata: " + _json.dumps({"changes": changes, "server_time": time.time()}) + "\n\n"
                idle = 0.0
            else:
                await asyncio.sleep(0.25)
                idle += 0.25
                if idle >= 15:
                    yield ": keepalive\n\n"
                    idle = 0.0

    return StreamingResponse(frames(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/v1/projects/{project_id}/presence")
async def presence_heartbeat(project_id: str, request: Request) -> dict[str, Any]:
    _require_project(project_id)
    payload = await request.json()
    if set(payload) - {"client_id", "name", "object_id", "mode"}:
        raise _thread_error(422, "invalid_request", "unknown presence field")
    client_id = str(payload.get("client_id") or "")
    if not _CLIENT_ID.match(client_id):
        raise _thread_error(422, "invalid_request", "client_id must be 8 to 64 URL-safe characters")
    operator = _operator_from_request(request)
    name = operator["id"] if operator else str(payload.get("name") or "").strip()[:80]
    _presence[client_id] = {
        "client_id": client_id,
        "name": name or "Someone",
        "object_id": str(payload.get("object_id") or "")[:200] or None,
        "mode": payload.get("mode") if payload.get("mode") in {"review", "compare", "verify", "bringup", "other"} else "other",
        "verified": operator is not None,
        "operator": operator,
        "seen_at": time.time(),
    }
    return {"ok": True, "ttl_seconds": int(_PRESENCE_TTL)}


@app.get("/v1/projects/{project_id}/presence")
def presence_list(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    now = time.time()
    rows = []
    for entry in list(_presence.values()):
        age = now - entry["seen_at"]
        if age > _PRESENCE_TTL:
            continue
        rows.append({**{k: v for k, v in entry.items() if k != "seen_at"}, "seen_seconds_ago": round(age, 1)})
    rows.sort(key=lambda row: (row["name"], row["client_id"]))
    return {"ok": True, "participants": rows[:100]}


@app.delete("/v1/projects/{project_id}/presence/{client_id}")
def presence_leave(project_id: str, client_id: str) -> dict[str, Any]:
    _require_project(project_id)
    _presence.pop(client_id, None)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
