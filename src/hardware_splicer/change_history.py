"""Revision-bound record of a project's Policy Lab changes, read back for the bench.

Three things are recorded, each as an immutable JSON file under the project's
``change-history`` directory, at the point where HS already produces them:

- ``proposal``: a validated Policy Lab feedback proposal (``policy_layer``), with
  the review's policy, decision and targets;
- ``change_evidence``: a change-evidence packet HS exported, by its SHA-256;
- ``cite_edition``: a Cite dossier edition and currency check that a caller
  (the replay) reports back. HS does not contact Cite; it only keeps what it was
  told, and decides staleness from its own head revision.

``change_dossier`` derives everything else from the saved revisions: which
revision applied each proposal, that revision's checks, and each applied
candidate's native outcome. Nothing here runs an engine, changes project state
or grants authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping

from . import digital_project as digital
from .policy_layer import FEEDBACK_SCHEMA, canonical_json_bytes
from .project_store import ProjectNotFound, ProjectStore, validate_project_id

CHANGE_DOSSIER_SCHEMA = "hardware_splicer.change_dossier_view.v1"
RECORD_SCHEMA = "hardware_splicer.change_history_record.v1"
KINDS = ("proposal", "change_evidence", "cite_edition")
PHYSICAL_MEANS = "unknown / not tested"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_OPERATORS = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b, "<=": lambda a, b: a <= b,
              "<": lambda a, b: a < b, "==": lambda a, b: a == b}


class ChangeHistoryError(ValueError):
    """A record does not bind this project's saved revisions, or claims authority."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _directory(store: ProjectStore, project_id: str) -> Path:
    return store._project_dir(validate_project_id(project_id)) / "change-history"


def _write(store: ProjectStore, project_id: str, kind: str, body: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ChangeHistoryError("Unknown change history record kind.")
    store.load(project_id)  # the project must exist
    record = {"schema": RECORD_SCHEMA, "kind": kind, "project_id": project_id, "recorded_at": _now(),
              "physical_authority_granted": False, **body}
    data = canonical_json_bytes(record)
    digest = hashlib.sha256(data).hexdigest()
    directory = _directory(store, project_id)
    directory.mkdir(parents=True, exist_ok=True)
    existing = sorted(directory.glob("*.json"))
    path = directory / f"{len(existing) + 1:05d}-{kind}-{digest[:16]}.json"
    # Exclusive creation: a record is never replaced.
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return {"path": path.name, "sha256": digest}


def _study(store: ProjectStore, project_id: str, revision: int) -> dict[str, Any]:
    envelope, _, seal = digital.validated_run(store, project_id, revision)
    return {"revision": envelope["revision"], "run_id": seal["run_id"], "parent_revision": seal.get("parent_revision"),
            "change_request": seal.get("change_request"), "summary": seal["summary"],
            "package_sha256": seal["artifact_sha256"].get("STUDY.zip")}


def record_proposal(store: ProjectStore, proposal: Mapping[str, Any], review: Mapping[str, Any]) -> dict[str, Any]:
    """Keep a validated proposal with the review facts the bench shows verbatim."""
    project_id = proposal.get("project_id")
    if (proposal.get("schema") != FEEDBACK_SCHEMA or proposal.get("status") != "validated_proposal"
            or proposal.get("physical_authority_granted") is not False or proposal.get("automatic_execution") is not False):
        raise ChangeHistoryError("Only a validated, non-executing HS feedback proposal can be recorded.")
    base = _study(store, project_id, proposal["base_revision"])
    if base["run_id"] != proposal.get("run_id"):
        raise ChangeHistoryError("The proposal does not bind the saved base revision.")
    policy = review.get("policy")
    if not isinstance(policy, dict) or not isinstance(policy.get("id"), str) or not isinstance(policy.get("version"), str):
        raise ChangeHistoryError("The review names no policy id and version.")
    if review.get("decision") != proposal.get("policy_decision") or review.get("source_binding") != proposal.get("source_binding"):
        raise ChangeHistoryError("The review is not the one this proposal was validated against.")
    return _write(store, project_id, "proposal", {
        "proposal": dict(proposal),
        "proposal_sha256": hashlib.sha256(canonical_json_bytes(dict(proposal))).hexdigest(),
        "review": {"policy_id": review["policy"]["id"], "policy_version": review["policy"]["version"],
                   "decision": review["decision"],
                   "unmet": [{"id": row.get("id"), "explanation": row.get("explanation")}
                             for row in review.get("unmet_constraints") or []],
                   "target_results": [{key: row.get(key) for key in ("id", "fact", "operator", "value", "unit",
                                                                      "actual", "passed")}
                                      for row in review.get("target_results") or []]},
    })


def record_change_evidence(store: ProjectStore, packet: Mapping[str, Any], packet_sha256: str) -> dict[str, Any]:
    """Keep an exported change-evidence packet's identity and what it states about the candidate."""
    project_id = packet.get("project_id")
    if packet.get("physical_authority_granted") is not False or not _HEX64.fullmatch(str(packet_sha256)):
        raise ChangeHistoryError("Change evidence must be digital and identified by its SHA-256.")
    if hashlib.sha256(canonical_json_bytes(dict(packet))).hexdigest() != packet_sha256:
        raise ChangeHistoryError("The packet hash does not match the packet's canonical bytes.")
    for side in ("base", "candidate"):
        saved = _study(store, project_id, packet[side]["revision"])
        if saved["run_id"] != packet[side]["run_id"] or saved["package_sha256"] != packet[side]["package_sha256"]:
            raise ChangeHistoryError(f"The packet's {side} revision differs from the saved study.")
    return _write(store, project_id, "change_evidence", {
        "packet_sha256": packet_sha256, "base_revision": packet["base"]["revision"],
        "candidate_revision": packet["candidate"]["revision"],
        "policy_review_sha256": packet["proposal"].get("policy_review_sha256"),
        "files": {role: record["sha256"] for role, record in packet["files"].items()},
        "unresolved": packet["unresolved"],
    })


def record_cite_edition(store: ProjectStore, project_id: str, *, edition_id: str, bound_revision: int,
                        packet_sha256: str, event: str, status: str, head_revision: int | None = None,
                        reasons: list[str] | None = None) -> dict[str, Any]:
    """Keep what a caller reported about a Cite edition: issued, or a later currency check."""
    if not _HEX64.fullmatch(str(edition_id)) or not _HEX64.fullmatch(str(packet_sha256)):
        raise ChangeHistoryError("Cite edition and packet must be identified by SHA-256.")
    if event not in ("issued", "currency_check") or status not in ("current", "stale", "refused_stale"):
        raise ChangeHistoryError("Unknown Cite edition event or status.")
    _study(store, project_id, bound_revision)
    return _write(store, project_id, "cite_edition", {
        "edition_id": edition_id, "bound_revision": bound_revision, "packet_sha256": packet_sha256,
        "event": event, "status": status, "head_revision": head_revision, "reasons": list(reasons or [])})


def _records(store: ProjectStore, project_id: str) -> list[dict[str, Any]]:
    directory = _directory(store, project_id)
    rows = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        if path.is_symlink():
            continue
        value = json.loads(path.read_bytes())
        if value.get("schema") == RECORD_SCHEMA and value.get("project_id") == project_id:
            rows.append(value)
    return rows


def _checks(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"id": row["id"], "passed": row["passed"] is True, "actual": row.get("actual"),
             "limit": row.get("limit"), "unit": row.get("unit")} for row in summary.get("constraints") or []]


def _native_outcome(candidate: Mapping[str, Any], targets: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    target = targets.get(candidate.get("target")) or {}
    prefix, _, fact = str(target.get("fact") or "").partition(".")
    source = summary.get("metrics", {}) if prefix == "metric" else summary.get("requirements", {}) if prefix == "requirement" else {}
    value = source.get(fact)
    operator = target.get("operator")
    met = None if value is None or operator not in _OPERATORS else _OPERATORS[operator](value, target["value"])
    return {"fact": target.get("fact"), "operator": operator, "required": target.get("value"),
            "unit": target.get("unit"), "native_value": value, "met": met,
            "basis": "native HS rerun of the applying revision; modeled, not measured"}


def change_dossier(store: ProjectStore, project_id: str) -> dict[str, Any]:
    """Every recorded Policy Lab change of a project, rebound to its saved revisions."""
    head = store.load(project_id)["revision"]
    records = _records(store, project_id)
    try:
        revisions = {n: _study(store, project_id, n) for n in range(1, head + 1)}
    except (ProjectNotFound, ValueError, KeyError) as exc:
        raise ChangeHistoryError("The project is not a digital study with saved runs.") from exc
    packets = [row for row in records if row["kind"] == "change_evidence"]
    changes = []
    for row in (r for r in records if r["kind"] == "proposal"):
        proposal, review = row["proposal"], row["review"]
        applied = [rev for rev in revisions.values()
                   if rev["parent_revision"] == proposal["base_revision"]
                   and rev["summary"]["requirements"] == proposal["resolved_requirements"]]
        applying = applied[0] if applied else None
        targets = {target["id"]: target for target in review["target_results"]}
        candidates = []
        for candidate in proposal.get("applied_candidates") or []:
            candidates.append({key: candidate.get(key) for key in ("id", "input", "before", "after", "model", "formula",
                                                                    "numbers", "assumptions", "target")}
                              | {"physical_means": PHYSICAL_MEANS,
                                 "native_outcome": None if applying is None
                                 else _native_outcome(candidate, targets, applying["summary"])})
        packet = next((p for p in packets if applying is not None and p["candidate_revision"] == applying["revision"]
                       and p["base_revision"] == proposal["base_revision"]), None)
        changes.append({
            "recorded_at": row["recorded_at"], "proposal_sha256": row["proposal_sha256"],
            "policy_id": review["policy_id"], "policy_version": review["policy_version"],
            "policy_decision": review["decision"], "unmet": review["unmet"],
            "targets": review["target_results"],
            "base_revision": proposal["base_revision"],
            "base_checks": _checks(revisions[proposal["base_revision"]]["summary"])
            if proposal["base_revision"] in revisions else None,
            "requirement_changes": proposal["requirement_changes"],
            "review_verification": proposal.get("policy_review_verification"),
            "applied_revision": None if applying is None else {
                "revision": applying["revision"], "run_id": applying["run_id"],
                "requirements_met": applying["summary"]["requirements_met"] is True,
                "checks": _checks(applying["summary"]), "change_request": applying["change_request"]},
            "candidates": candidates,
            "change_evidence": None if packet is None else {
                "packet_sha256": packet["packet_sha256"], "recorded_at": packet["recorded_at"],
                "unresolved": packet["unresolved"]},
        })
    editions = {}
    for row in (r for r in records if r["kind"] == "cite_edition"):
        edition = editions.setdefault(row["edition_id"], {"edition_id": row["edition_id"],
                                                           "bound_revision": row["bound_revision"],
                                                           "packet_sha256": row["packet_sha256"],
                                                           "issued_at": None, "checks": []})
        if row["event"] == "issued":
            edition["issued_at"] = row["recorded_at"]
        else:
            edition["checks"].append({"checked_at": row["recorded_at"], "status": row["status"],
                                      "head_revision": row["head_revision"], "reasons": row["reasons"]})
    for edition in editions.values():
        # HS can tell an edition is stale from its own head, whatever Cite last reported.
        edition["stale_by_hs_head"] = head > edition["bound_revision"]
        edition["latest_check"] = edition["checks"][-1] if edition["checks"] else None
    return {"schema": CHANGE_DOSSIER_SCHEMA, "project_id": project_id, "head_revision": head,
            "head_requirements_met": revisions[head]["summary"]["requirements_met"] is True,
            "changes": changes, "cite_editions": sorted(editions.values(), key=lambda e: e["bound_revision"]),
            "cite_linked": bool(editions), "physical_authority_granted": False,
            "scope": "Recorded Policy Lab proposals and exported change evidence, rebound to saved digital revisions. "
                     "Modeled values only; HS does not contact Cite."}
