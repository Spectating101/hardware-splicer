"""Bind digital study checks to the revision and sealed run that produced them.

A digital study revision owns one sealed run. Its checks are evidence for that
revision only. When a later revision changes an input a check reads, the earlier
check is stale: it is kept, it names the revision and run it came from, and it is
never counted as passing for the later revision. The rerun result in the later
revision is reported beside it, including a failure.

Nothing here runs an engine, writes project state or grants authority. It reads
sealed runs through ``digital_project.validated_run``, which re-checks every
artifact hash before any claim is used.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from . import digital_cases as cases
from . import digital_project as digital
from .evidence_impact import INVALIDATED, RETAINED, evaluate_evidence_impact

STUDY_CHECK_DELTA_SCHEMA = "hardware_splicer.study_check_delta.v1"
SOURCES_DEPENDENCY = "study-sources"
CASE_DEPENDENCY = "study-case"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    """Hash of a saved revision's canonical snapshot (sorted-key JSON)."""
    return _sha(snapshot)


def load_study_evidence(store, project_id: str, revision: int | None = None) -> dict[str, Any] | None:
    """Return the sealed checks of a digital revision, or None for other projects."""
    envelope = store.load(project_id, revision=revision)
    snapshot = envelope["snapshot"]
    if snapshot.get("mode") != "digital" or not isinstance(snapshot.get("digitalStudy"), dict):
        return None
    envelope, directory, seal = digital.validated_run(store, project_id, envelope["revision"])
    summary = seal["summary"]
    case_id = digital.case_id_for(seal)
    case = digital.case_for_run(seal)
    requirements = dict(summary["requirements"])
    sources = dict(summary.get("source_sha256") or {})
    calculation = case.calculation if case is not None else "SIMULATION.json"
    revision_number = int(envelope["revision"])
    checks = []
    for check in summary["constraints"]:
        names, declaration = cases.check_requirements(case_id, check["id"], requirements, sources)
        checks.append({"check": deepcopy(check), "requirements": list(names), "declaration": declaration})
    return {
        "project_id": project_id,
        "revision": revision_number,
        "snapshot_sha256": snapshot_sha256(snapshot),
        "run_id": seal["run_id"],
        "parent_revision": seal.get("parent_revision"),
        "change_request": seal.get("change_request"),
        "case_id": case_id,
        "requirements": requirements,
        "requirements_met": summary["requirements_met"],
        "source_sha256": _sha(sources),
        "seal_sha256": digital.digest(directory / "sealed-run.json"),
        "calculation": calculation,
        "calculation_sha256": seal["artifact_sha256"].get(calculation),
        "package": {
            "name": "STUDY.zip",
            "sha256": seal["artifact_sha256"].get("STUDY.zip"),
            "path": f"/v1/projects/{project_id}/digital/revisions/{revision_number}/artifacts/STUDY.zip",
        },
        "checks": checks,
    }


def study_dependencies(study: Mapping[str, Any]) -> dict[str, Any]:
    """Every input a registered run reads: its case, hashed sources and requirements."""
    values = {f"requirement:{name}": value for name, value in study["requirements"].items()}
    values[SOURCES_DEPENDENCY] = study["source_sha256"]
    values[CASE_DEPENDENCY] = study["case_id"]
    return values


def study_check_nodes(study: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project sealed checks as assurance outputs bound to their revision and run."""
    evidence = {
        "revision": study["revision"],
        "run_id": study["run_id"],
        "case_id": study["case_id"],
        "snapshot_sha256": study["snapshot_sha256"],
        "seal_sha256": study["seal_sha256"],
        "calculation": study["calculation"],
        "calculation_sha256": study["calculation_sha256"],
        "package_sha256": study["package"]["sha256"],
    }
    nodes = []
    for row in study["checks"]:
        check = row["check"]
        nodes.append({
            "node_id": f"check:{check['id']}",
            "kind": "check",
            "surface": "digitalStudy.constraints",
            "local_id": check["id"],
            "summary": str(check.get("label") or check["id"]),
            "status": "passed" if check["passed"] is True else "failed",
            "source_ids": [],
            "claim_ids": [],
            "source_refs": [],
            "raw": deepcopy(check),
            "dependency_ids": sorted({*(f"requirement:{name}" for name in row["requirements"]),
                                      SOURCES_DEPENDENCY, CASE_DEPENDENCY}),
            "dependency_coverage_complete": True,
            "dependency_declaration": row["declaration"],
            "evidence": dict(evidence),
        })
    return nodes


def _result(check: Mapping[str, Any]) -> dict[str, Any]:
    return {key: check.get(key) for key in ("passed", "actual", "limit", "unit")}


def _check_view(node: Mapping[str, Any]) -> dict[str, Any]:
    return {**_result(node["raw"]), "revision": node["evidence"]["revision"], "run_id": node["evidence"]["run_id"]}


def evaluate_study_check_delta(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    """Mark base-revision checks stale or retained against a candidate revision.

    ``base`` and ``candidate`` are assurance projections carrying ``study``. A
    retained check must also reproduce exactly in the candidate's rerun; if the
    rerun differs, or the check is gone, the earlier result is stale regardless
    of its declaration.
    """
    base_study, candidate_study = base.get("study"), candidate.get("study")
    if not base_study or not candidate_study:
        return None
    before = base_study["dependencies"]
    after = candidate_study["dependencies"]
    changed = sorted(key for key in set(before) | set(after) if _canonical(before.get(key)) != _canonical(after.get(key)))
    base_checks = [row for row in base.get("outputs") or [] if row.get("kind") == "check"]
    reruns = {row["local_id"]: row for row in candidate.get("outputs") or [] if row.get("kind") == "check"}
    impact = evaluate_evidence_impact({
        "evidence_items": [{"evidence_id": f"output:{row['node_id']}", "depends_on": row["dependency_ids"],
                            "dependencies_complete": row["dependency_coverage_complete"] is True}
                           for row in base_checks],
        "changed_dependency_ids": changed,
    })
    if impact["status"] != "evaluated":
        raise ValueError("study check dependencies are invalid: " + ", ".join(impact["validation_errors"]))
    by_id = {f"output:{row['node_id']}": row for row in base_checks}
    rows = []
    for result in impact["results"]:
        node = by_id[result["evidence_id"]]
        rerun = reruns.get(node["local_id"])
        status, reasons = result["status"], list(result["reasons"])
        if rerun is None:
            status = INVALIDATED
            reasons.append({"kind": "check_absent_in_candidate", "ids": [node["node_id"]]})
        elif status == RETAINED and _result(rerun["raw"]) != _result(node["raw"]):
            status = INVALIDATED
            reasons.append({"kind": "rerun_result_differs", "ids": [node["node_id"]]})
        rows.append({
            "evidence_id": result["evidence_id"],
            "status": status,
            "depends_on": result["depends_on"],
            "dependencies_complete": result["dependencies_complete"],
            "reasons": reasons,
            "metadata": {
                "kind": "check",
                "node_id": node["node_id"],
                "summary": node["summary"],
                "dependency_declaration": node["dependency_declaration"],
                **_check_view(node),
                "package_sha256": node["evidence"]["package_sha256"],
                "rerun": _check_view(rerun) if rerun is not None else None,
                # A stale result describes its own revision only.
                "counts_for_candidate": status == RETAINED,
            },
        })
    base_ids = {row["local_id"]: row for row in base_checks}
    rerun_rows = []
    for node in reruns.values():
        old = base_ids.get(node["local_id"])
        passed = node["raw"]["passed"] is True
        transition = ("new" if old is None
                      else "unchanged" if (old["raw"]["passed"] is True) == passed
                      else "resolved" if passed else "regressed")
        rerun_rows.append({"node_id": node["node_id"], "summary": node["summary"], "transition": transition,
                           **_check_view(node)})
    return {
        "schema_version": STUDY_CHECK_DELTA_SCHEMA,
        "base_revision": base_study["revision"],
        "candidate_revision": candidate_study["revision"],
        "changed_dependencies": [{"dependency_id": key, "before": before.get(key), "after": after.get(key)}
                                 for key in changed],
        "stale_outputs": [row for row in rows if row["status"] == INVALIDATED],
        "blocked_outputs": [row for row in rows if row["status"] not in {INVALIDATED, RETAINED}],
        "retained_outputs": [row for row in rows if row["status"] == RETAINED],
        "rerun_outputs": rerun_rows,
        "failing_outputs": [row for row in rerun_rows if row["passed"] is not True],
        "packages": {"before": {"revision": base_study["revision"], "run_id": base_study["run_id"], **base_study["package"]},
                     "after": {"revision": candidate_study["revision"], "run_id": candidate_study["run_id"],
                               **candidate_study["package"]}},
        "stale_counted_as_passing": False,
        "authority_effect": "none",
        "physical_authority_granted": False,
    }
