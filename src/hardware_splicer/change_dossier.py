"""Hand a reviewed requirement change to a downstream dossier, bound to its revisions.

    base revision -> Policy Lab review -> HS-validated proposal -> new revision

``build_change_evidence`` packages what already exists: the two saved study
revisions, the Policy Lab review and the HS feedback proposal it was applied
from, and the revision-bound check delta from ``study_evidence``. Every covered
file is listed with its SHA-256 so a receiver can recheck the bytes it reads.

``export_revision_head`` reports the project's latest saved revision. A receiver
compares it with the packet's candidate revision to decide whether a dossier it
issued is still current.

Nothing here runs an engine, writes project state or upgrades authority. The
packet is modeled, digital evidence; ``physical_authority_granted`` is always
False, and a failing rerun check is carried as a failure.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .engineering_assurance import build_engineering_assurance
from .policy_layer import (EVIDENCE_SCHEMA, FEEDBACK_SCHEMA, REVIEW_SCHEMA, PolicyLayerError,
                           canonical_json_bytes, read_json_bytes, validate_policy_evidence)
from .project_store import RevisionConflict, validate_project_id
from .study_evidence import evaluate_study_check_delta, load_study_evidence

CHANGE_EVIDENCE_SCHEMA = "hardware_splicer.engineering_change_evidence.v1"
REVISION_HEAD_SCHEMA = "hardware_splicer.revision_head.v1"
AUTHORITY_LEVEL = "modeled"
NOT_TESTED = (
    "No physical build, bench measurement, power-on or field operation was performed for either revision.",
    "Modeled runtime and current values are calculations from declared assumptions, not observed behaviour.",
)
# File roles a packet may cover, and the schema each file must carry.
FILE_ROLES = {
    "base_export": EVIDENCE_SCHEMA,
    "base_review": REVIEW_SCHEMA,
    "proposal": FEEDBACK_SCHEMA,
    "candidate_export": EVIDENCE_SCHEMA,
    "candidate_review": REVIEW_SCHEMA,
}
REQUIRED_ROLES = ("base_export", "base_review", "proposal", "candidate_export")
PHYSICAL_MEANS = "unknown / not tested"
CANDIDATE_LABEL = "Modelled candidate design change; the model is unverified until the native rerun below"


class ChangeDossierError(ValueError):
    """The change evidence is inconsistent, unbound or outside its digital scope."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _assurance(store, project_id: str, revision: int) -> dict[str, Any]:
    envelope = store.load(project_id, revision=revision)
    return build_engineering_assurance(envelope["snapshot"], project_id=project_id, revision=revision,
                                       study=load_study_evidence(store, project_id, revision))


def _check(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": row["id"], "label": row.get("label"), "passed": row["passed"] is True,
            "actual": row.get("actual"), "limit": row.get("limit"), "unit": row.get("unit")}


def _unmet(row: Mapping[str, Any]) -> dict[str, Any]:
    """One unmet Policy Lab row: a declared policy target, or a failed HS engineering check it carried over."""
    if "operator" in row:
        required, fact = f"{row['operator']} {row['value']} {row['unit']}", row["fact"]
    else:
        required, fact = f"HS limit {row.get('limit')} {row.get('unit')}", "HS engineering check"
    return {"target": row["id"], "fact": fact, "actual": row.get("actual"), "required": required,
            "reason": row.get("reason")}


def _candidate_outcomes(proposal: Mapping[str, Any], review: Mapping[str, Any],
                        candidate_export: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Each applied modelled candidate, rebound to the review row it came from, with its native rerun outcome."""
    applied = proposal.get("applied_candidates") or []
    stated = {row.get("id"): row for row in review.get("candidate_design_changes") or [] if isinstance(row, dict)}
    overrides = {}
    for row in applied:
        if stated.get(row.get("id")) != row or row.get("status") != "PROPOSED":
            raise ChangeDossierError(f"Applied candidate {row.get('id')!r} differs from the Policy Lab review.")
        overrides.update(row["requirement_overrides"])
    if overrides != (proposal.get("candidate_overrides") or {}):
        raise ChangeDossierError("The proposal's candidate overrides differ from its applied candidates.")
    targets = {row["id"]: row for row in review.get("target_results") or []}
    metrics = candidate_export["study"]["summary"]["metrics"]
    rows = []
    for row in applied:
        target = targets.get(row["target"])
        if target is None:
            raise ChangeDossierError(f"Candidate {row['id']} names a target the review did not evaluate.")
        fact = target["fact"].split(".", 1)[1]
        value = metrics.get(fact)
        met = None if value is None else (value >= target["value"] if target["operator"] == ">="
                                          else value <= target["value"] if target["operator"] == "<="
                                          else value == target["value"])
        rows.append({"id": row["id"], "label": CANDIDATE_LABEL, "input": row["input"], "before": row["before"],
                     "after": row["after"], "requirement_overrides": row["requirement_overrides"],
                     "model": row["model"], "formula": row["formula"], "numbers": row["numbers"],
                     "assumptions": row["assumptions"], "basis": row["basis"],
                     "physical_means": PHYSICAL_MEANS,
                     "native_outcome": {"target": row["target"], "fact": target["fact"], "operator": target["operator"],
                                        "required": target["value"], "unit": target["unit"],
                                        "native_value": value, "met": met,
                                        "basis": "native HS rerun of the candidate revision; modeled, not measured"}})
    return rows


def revision_identity(store, project_id: str, revision: int) -> dict[str, Any]:
    """The identity and sealed checks of one saved digital revision."""
    study = load_study_evidence(store, project_id, revision)
    if study is None:
        raise ChangeDossierError(f"{project_id} revision {revision} is not a digital study.")
    return {"revision": study["revision"], "run_id": study["run_id"],
            "parent_revision": study["parent_revision"], "change_request": study["change_request"],
            "case_id": study["case_id"], "snapshot_sha256": study["snapshot_sha256"],
            "seal_sha256": study["seal_sha256"], "package_sha256": study["package"]["sha256"],
            "calculation": study["calculation"], "calculation_sha256": study["calculation_sha256"],
            "requirements": study["requirements"], "requirements_met": study["requirements_met"],
            "checks": [_check(row["check"]) for row in study["checks"]]}


def export_revision_head(store, project_id: str) -> dict[str, Any]:
    """Report the latest saved revision so a receiver can test its edition for staleness."""
    validate_project_id(project_id)
    latest = store.load(project_id)["revision"]
    head = revision_identity(store, project_id, latest)
    return {"schema": REVISION_HEAD_SCHEMA, "source_project": "hardware-splicer", "project_id": project_id,
            "head": {key: head[key] for key in ("revision", "run_id", "parent_revision", "snapshot_sha256",
                                                "seal_sha256", "package_sha256", "requirements_met")},
            "authority_level": AUTHORITY_LEVEL, "physical_authority_granted": False}


def _covered(root: Path, files: Mapping[str, Path]) -> tuple[dict[str, dict], dict[str, Any]]:
    missing = [role for role in REQUIRED_ROLES if role not in files]
    unknown = sorted(set(files) - set(FILE_ROLES))
    if missing or unknown:
        raise ChangeDossierError(f"Change evidence files: missing {missing}, unknown {unknown}.")
    root = root.resolve()
    records, values = {}, {}
    for role, path in sorted(files.items()):
        path = Path(path).resolve()
        try:
            relative = PurePosixPath(path.relative_to(root).as_posix())
        except ValueError as exc:
            raise ChangeDossierError(f"{role} lies outside the evidence root.") from exc
        raw = path.read_bytes()
        try:
            value = read_json_bytes(raw)
        except PolicyLayerError as exc:
            raise ChangeDossierError(f"{role} is not a valid JSON exchange: {exc}") from exc
        if value.get("schema") != FILE_ROLES[role]:
            raise ChangeDossierError(f"{role} has schema {value.get('schema')!r}, expected {FILE_ROLES[role]!r}.")
        records[role] = {"path": relative.as_posix(), "schema": value["schema"], "sha256": _sha(raw), "bytes": len(raw)}
        values[role] = value
    return records, values


def _bind_export(role: str, export: Mapping[str, Any], project_id: str, identity: Mapping[str, Any]) -> None:
    validate_policy_evidence(dict(export))
    if (export["project_id"] != project_id or export["revision"] != identity["revision"]
            or export["run_id"] != identity["run_id"] or export["package"]["sha256"] != identity["package_sha256"]):
        raise ChangeDossierError(f"{role} does not export revision {identity['revision']} of {project_id}.")


def _bind_review(role: str, review: Mapping[str, Any], export_record: Mapping[str, Any], export: Mapping[str, Any]) -> None:
    binding = review.get("source_binding") or {}
    if (binding.get("evidence_sha256") != export_record["sha256"] or binding.get("project_id") != export["project_id"]
            or binding.get("revision") != export["revision"] or binding.get("run_id") != export["run_id"]
            or review.get("physical_authority_granted") is not False):
        raise ChangeDossierError(f"{role} does not bind the exact exported bytes and revision.")


def build_change_evidence(store, project_id: str, *, base_revision: int, candidate_revision: int,
                          root: Path, files: Mapping[str, Path]) -> dict[str, Any]:
    """Package one applied, reviewed requirement change for a downstream dossier.

    Refuses unless the candidate is the latest revision, descends directly from
    the base, and carries exactly the requirements the HS-validated proposal
    resolved from the Policy Lab review of the base export.
    """
    validate_project_id(project_id)
    latest = store.load(project_id)["revision"]
    if latest != candidate_revision:
        raise RevisionConflict(f"Revision {candidate_revision} is not the latest ({latest}); export the current change.")
    base = revision_identity(store, project_id, base_revision)
    candidate = revision_identity(store, project_id, candidate_revision)
    if candidate["parent_revision"] != base_revision:
        raise ChangeDossierError(f"Revision {candidate_revision} does not descend from revision {base_revision}.")
    records, values = _covered(Path(root), files)
    _bind_export("base_export", values["base_export"], project_id, base)
    _bind_export("candidate_export", values["candidate_export"], project_id, candidate)
    _bind_review("base_review", values["base_review"], records["base_export"], values["base_export"])
    if "candidate_review" in values:
        _bind_review("candidate_review", values["candidate_review"], records["candidate_export"], values["candidate_export"])
    proposal, review = values["proposal"], values["base_review"]
    if (proposal.get("source_binding") != review["source_binding"]
            or proposal.get("policy_review_sha256") != records["base_review"]["sha256"]
            or proposal.get("project_id") != project_id or proposal.get("base_revision") != base_revision
            or proposal.get("physical_authority_granted") is not False or proposal.get("automatic_execution") is not False):
        raise ChangeDossierError("The proposal does not bind the base review and revision.")
    if proposal.get("revision_requirements") != review.get("revision_requirements"):
        raise ChangeDossierError("The proposal's requirement overrides differ from the Policy Lab review.")
    if proposal.get("resolved_requirements") != candidate["requirements"]:
        raise ChangeDossierError(f"Revision {candidate_revision} does not carry the proposal's resolved requirements.")
    candidates = _candidate_outcomes(proposal, review, values["candidate_export"])

    delta = evaluate_study_check_delta(_assurance(store, project_id, base_revision),
                                       _assurance(store, project_id, candidate_revision))
    if delta is None:
        raise ChangeDossierError("The revisions have no comparable study checks.")

    def stale_row(row):
        meta = row["metadata"]
        return {"check": meta["node_id"].removeprefix("check:"), "status": row["status"],
                "from_revision": meta["revision"], "run_id": meta["run_id"],
                "result": {key: meta[key] for key in ("passed", "actual", "limit", "unit")},
                "rerun": meta["rerun"], "reasons": row["reasons"],
                "counts_for_candidate": meta["counts_for_candidate"]}

    candidate_review = values.get("candidate_review")
    unresolved = [{"kind": "failing_check", "check": row["node_id"].removeprefix("check:"), "revision": row["revision"],
                   "run_id": row["run_id"], "actual": row["actual"], "limit": row["limit"], "unit": row["unit"],
                   "transition": row["transition"]}
                  for row in delta["failing_outputs"]]
    if candidate_review is not None:
        unresolved += [{"kind": "policy_target_unmet", "policy_id": candidate_review["policy"]["id"],
                        **_unmet(row), "revision": candidate_revision}
                       for row in candidate_review["unmet_constraints"]]
    not_linked = [] if candidate_review is not None else [
        f"No Policy Lab review of revision {candidate_revision} was supplied."]
    return {
        "schema": CHANGE_EVIDENCE_SCHEMA,
        "source_project": "hardware-splicer",
        "project_id": project_id,
        "case_id": candidate["case_id"],
        "authority_level": AUTHORITY_LEVEL,
        "evidence_kind": "digital_design",
        "physical_authority_granted": False,
        "objective": {
            "statement": ("Declared design requirements of the saved study; HS stores no free-text objective "
                          "for a registered digital case."),
            "base_requirements": base["requirements"],
            "candidate_requirements": candidate["requirements"],
            "change_request": candidate["change_request"],
        },
        "base": base,
        "candidate": candidate,
        "proposal": {
            "policy_id": review["policy"]["id"], "policy_version": review["policy"]["version"],
            "policy_decision": review["decision"], "policy_review_sha256": records["base_review"]["sha256"],
            "revision_requirements": proposal["revision_requirements"],
            "requirement_changes": proposal["requirement_changes"],
            "unmet_targets": [_unmet(row) for row in review["unmet_constraints"]],
            "candidate_design_changes": candidates,
            "applied_as_revision": candidate_revision,
        },
        "check_delta": {
            "changed_dependencies": delta["changed_dependencies"],
            "stale": [stale_row(row) for row in delta["stale_outputs"]],
            "retained": [stale_row(row) for row in delta["retained_outputs"]],
            "blocked": [stale_row(row) for row in delta["blocked_outputs"]],
            "rerun": delta["rerun_outputs"],
            "stale_counted_as_passing": delta["stale_counted_as_passing"],
        },
        "unresolved": unresolved,
        "not_tested": list(NOT_TESTED) + [
            f"Physical means of reaching {row['input']} = {row['after']}: {PHYSICAL_MEANS}." for row in candidates],
        "not_linked": not_linked,
        "head_at_export": {"revision": latest, "run_id": candidate["run_id"]},
        "files": records,
    }


def write_change_evidence(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    """Write canonical bytes once; an issued packet is never replaced in place."""
    data = canonical_json_bytes(dict(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("xb") as handle:
        handle.write(data)
    return {"path": str(path), "sha256": _sha(data), "bytes": len(data)}
