"""One engineering objective, one project: the record an agent keeps while it works an objective through HS's tools.

The Mission Freeze asks HS to carry an objective ("build an affordable and useful drone from obtainable parts") from
research to a build package on the SAME project. This is that project: a folder holding the objective, an append-only
ledger of every step (tool runs, research findings, decisions with their reasons) and the artifacts the tools wrote.

The status separates three kinds of claim and never merges them:

* ``software_checked``: a tool ran and its own checks passed (calculations, CAD, ERC/DRC, read-back parity);
* ``open``: a tool refused, failed, or reported a problem not yet resolved by a later step;
* ``physical_required``: what only a built, measured or tested object can show (the tools' own claim boundaries).

Nothing here grants fabrication or release authority; a software check is never physical proof.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .state_paths import scratch_dir
SCHEMA = "hardware_splicer.objective_project.v1"
STEP_KINDS = ("tool", "research", "decision", "artifact", "note")


def projects_root() -> Path:
    root = os.environ.get("HARDWARE_SPLICER_PROJECTS_ROOT")
    if root:
        path = Path(root)
    else:
        path = scratch_dir() / "objective-projects"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "project")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class ObjectiveProject:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not (self.root / "objective.json").is_file():
            raise FileNotFoundError(f"no objective project at {self.root}")

    # ------------------------------------------------------------------ open / load

    @classmethod
    def open(cls, objective: str, *, constraints: dict[str, Any] | None = None, acceptance: list[str] | None = None,
             root: Path | None = None) -> "ObjectiveProject":
        if not objective.strip():
            raise ValueError("an objective is required")
        project_id = f"{_slug(objective)}-{uuid.uuid4().hex[:6]}"
        path = (root or projects_root()) / project_id
        (path / "artifacts").mkdir(parents=True)
        (path / "objective.json").write_text(json.dumps({
            "schema": SCHEMA, "project_id": project_id, "objective": objective, "constraints": constraints or {},
            "acceptance": acceptance or [], "opened": _now()}, indent=1, ensure_ascii=False))
        (path / "ledger.jsonl").touch()
        return cls(path)

    @classmethod
    def load(cls, project_id: str, root: Path | None = None) -> "ObjectiveProject":
        if not re.fullmatch(r"[a-z0-9-]{3,64}", project_id or ""):
            raise ValueError("invalid project id")
        return cls((root or projects_root()) / project_id)

    @property
    def project_id(self) -> str:
        return self.root.name

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    def objective(self) -> dict[str, Any]:
        return json.loads((self.root / "objective.json").read_text())

    # ------------------------------------------------------------------ design link

    def link_design(self, design_project_id: str) -> dict[str, Any]:
        """Point this objective at a stored machine project (the engineering design spine in the project store).

        The link only reports: the design's release state is recomputed from the stored design on every status call, and
        nothing here edits the design or upgrades its authority."""
        summary = design_summary(design_project_id)
        if summary.get("error"):
            raise ValueError(summary["error"])
        obj = self.objective()
        obj["design_project_id"] = design_project_id
        (self.root / "objective.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False))
        self.record("note", f"linked design {design_project_id}", {"design_project_id": design_project_id,
                                                                   "revision": summary.get("revision")})
        return summary

    # ------------------------------------------------------------------ ledger

    def record(self, kind: str, title: str, payload: dict[str, Any]) -> dict[str, Any]:
        if kind not in STEP_KINDS:
            raise ValueError(f"kind must be one of {STEP_KINDS}")
        steps = self.steps()
        entry = {"seq": len(steps) + 1, "at": _now(), "kind": kind, "title": title, **payload}
        with (self.root / "ledger.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry

    def steps(self) -> list[dict[str, Any]]:
        lines = (self.root / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    # ------------------------------------------------------------------ status

    def status(self) -> dict[str, Any]:
        """What has been checked in software, what is still open, and what only a physical build can show. A tool's
        problem stays open until a later run of the same tool (same ``check_key``) passes."""
        steps = self.steps()
        latest: dict[str, dict[str, Any]] = {}
        for s in steps:
            if s["kind"] == "tool":
                latest[s.get("check_key") or s["title"]] = s
        checked, open_items, physical, deliverables, tool_research = [], [], [], [], []
        for key, s in latest.items():
            category = s.get("category") or ("artifact" if key.startswith("artifact:") else
                                             "research" if s["title"] in ("hs_prior_art_search", "hs_read_board") else "check")
            if s.get("ok") and not s.get("problems") and category == "artifact":
                deliverables.append({"artifact": key.removeprefix("artifact:"), "seq": s["seq"], "untested": s.get("claim_boundary")})
                continue
            if s.get("ok") and not s.get("problems") and category == "research":
                tool_research.append({"search": key, "seq": s["seq"], "summary": s.get("summary"), "sources": s.get("sources", [])})
                continue
            if s.get("ok") and not s.get("problems"):
                checked.append({"check": key, "seq": s["seq"], "summary": s.get("summary")})
            else:
                open_items.append({"check": key, "seq": s["seq"], "problems": s.get("problems") or [s.get("error") or "failed"]})
            if s.get("claim_boundary"):
                physical.append({"check": key, "boundary": s["claim_boundary"]})
        # Reuse before building: a project that has run checks or written files without any prior-art research on
        # record keeps that open (on 2026-11-26 a rover package was written while OpenBot sat in HS's own records).
        searched = any(s["kind"] == "research" for s in steps) or any(
            s["kind"] == "tool" and (s.get("category") == "research" or s["title"] in ("hs_prior_art_search", "hs_read_board", "hs_junk_lookup"))
            for s in steps)
        if steps and not searched and (checked or open_items or deliverables):
            open_items.append({"check": "prior_art", "seq": None,
                               "problems": ["no prior-art search recorded: run hs_prior_art_search (and hs_junk_lookup for "
                                            "donors) or record the research, before relying on this design"]})
        decisions = [{"seq": s["seq"], "title": s["title"], "choice": s.get("choice"), "because": s.get("because")}
                     for s in steps if s["kind"] == "decision"]
        research = tool_research + [{"seq": s["seq"], "title": s["title"], "sources": s.get("sources", [])}
                                    for s in steps if s["kind"] == "research"]
        artifacts = sorted(str(p.relative_to(self.root)) for p in self.artifacts_dir.rglob("*") if p.is_file())
        obj = self.objective()
        design = design_summary(obj["design_project_id"]) if obj.get("design_project_id") else None
        if design is not None:
            if design.get("error"):
                open_items.append({"check": f"design:{obj['design_project_id']}", "seq": None, "problems": [design["error"]]})
            elif design.get("release_blockers"):
                open_items.append({"check": f"design:{design['project_id']}", "seq": None,
                                   "problems": [f"design release blocker {b['code']}: {b['message']}" for b in design["release_blockers"][:10]]})
        return {"schema": SCHEMA, "project_id": self.project_id, "objective": obj["objective"],
                "acceptance": obj.get("acceptance", []), "steps": len(steps), "research": research, "decisions": decisions,
                "software_checked": checked, "open": open_items, "physical_required": physical, "deliverables": deliverables,
                "artifacts": artifacts, "design": design,
                "authority": "software checks only; no fabrication, power-on, flight or release is authorised by this record"}


def design_summary(design_project_id: str) -> dict[str, Any]:
    """A stored machine project's release state, recomputed from the stored design (never from caller input)."""
    from .engineering_plan_store import _persisted_machine_project
    from .machine_project import MachineProject
    from .project_store import ProjectStore, ProjectStoreError

    try:
        envelope = ProjectStore().load(design_project_id)
    except (ProjectStoreError, ValueError, OSError) as exc:
        return {"project_id": design_project_id, "error": f"design project {design_project_id!r} not found: {exc}"}
    snapshot = envelope["snapshot"]
    project = _persisted_machine_project(snapshot)
    if project is None and isinstance(snapshot.get("machine_project"), dict):
        try:
            project = MachineProject.model_validate(snapshot["machine_project"])
        except ValueError:
            project = None
    if project is None:
        return {"project_id": design_project_id, "revision": envelope["revision"],
                "error": f"design project {design_project_id!r} has no valid machine project in revision {envelope['revision']}"}
    assessment = project.assess_release()
    return {"project_id": design_project_id, "revision": envelope["revision"], "name": project.name,
            "requested_state": str(assessment.requested_state.value if hasattr(assessment.requested_state, "value") else assessment.requested_state),
            "achieved_state": str(assessment.achieved_state.value if hasattr(assessment.achieved_state, "value") else assessment.achieved_state),
            "release_blockers": [b.model_dump(mode="json") for b in assessment.blockers],
            "release_warnings": len(assessment.warnings),
            "counts": {k: len(getattr(project, k)) for k in ("requirements", "components", "verifications", "evidence")},
            "authority": "reported from the stored design; this link changes no design and grants no release"}
