"""Execute explicitly accepted, software-side AI project previews.

This module is deliberately narrower than the AI proposal vocabulary. It runs
deterministic previews, imports registered sources and stages native edits. It never
runs arbitrary commands, enables LLM-first compose, touches devices, or elevates
fabrication, flashing, power, motion, operational, or release authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence

from .ai_project_action_inputs import validate_action_inputs
from .ai_project_execution_receipts import (
    candidate_execution_lock,
    load_candidate_execution_receipt,
    store_candidate_execution_receipt,
    unchanged_execution_base,
)
from .compose_dispatch import compose_dispatch
from .engineering_project_source_bundle import analyze_registered_project_bundle
from .engineering_cad_carrier import generate_registered_pcb_carrier
from .guided_engineering_planner import plan_guided_engineering_project
from .project_store import ProjectStore, validate_project_id

AI_TOOL_EXECUTOR_SCHEMA = "hardware_splicer.ai_project_tool_executor.v1"
AI_TOOL_RESULT_SCHEMA = "hardware_splicer.ai_project_tool_result.v1"
AI_TOOL_EXECUTOR_IDENTITY = "hardware_splicer.ai_project_tool_executor.python.v1"

EXECUTABLE_AI_PREVIEW_ACTIONS = (
    "run_guided_plan",
    "run_compose",
    "run_erc",
    "run_drc",
    "inspect_registered_sources",
    "generate_board_carrier_candidate",
    "promote_registered_sources",
    "propose_kicad_edit",
)

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_MAX_RESULT_JSON_BYTES = 16 * 1024 * 1024
_MAX_SUMMARY_ROWS = 64


class AIProjectToolExecutorError(RuntimeError):
    """Base error for accepted AI preview execution."""


class AIActionNotExecutable(AIProjectToolExecutorError, ValueError):
    pass


class AIActionNotAccepted(AIProjectToolExecutorError, ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: Any, label: str) -> str:
    token = str(value or "").strip()
    if not _ID_RE.fullmatch(token):
        raise ValueError(f"{label} has an invalid identifier")
    return token


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> Dict[str, Any]:
    payload = _canonical_json(value)
    if len(payload) > _MAX_RESULT_JSON_BYTES:
        raise ValueError("AI preview result exceeds the bounded JSON artifact ceiling")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _run_root(
    store: ProjectStore,
    project_id: str,
    session_id: str,
    action_id: str,
) -> tuple[Path, str]:
    safe_project = validate_project_id(project_id)
    safe_session = _safe_id(session_id, "session_id")
    safe_action = _safe_id(action_id, "action_id")
    project_dir = (store.root / safe_project).resolve()
    if project_dir.parent != store.root:
        raise ValueError("project tool directory resolves outside project root")
    run_dir = (
        project_dir / "ai_tool_runs" / safe_session / safe_action
    ).resolve()
    expected_parent = (project_dir / "ai_tool_runs" / safe_session).resolve()
    if run_dir.parent != expected_parent:
        raise ValueError("AI tool run directory resolves outside the session boundary")
    relative = run_dir.relative_to(project_dir).as_posix()
    return run_dir, relative


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        dict(row)
        for row in list(value)[:_MAX_SUMMARY_ROWS]
        if isinstance(row, Mapping)
    ]


def _combined_sources(snapshot: Mapping[str, Any]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for collection in (
        snapshot.get("engineeringSources"),
        snapshot.get("engineeringParsedSources"),
    ):
        for source in _rows(collection):
            key = (
                str(source.get("source_id") or ""),
                str(source.get("content_hash") or source.get("revision") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(source)
    return result


def _planner_intake(
    project_id: str,
    snapshot: Mapping[str, Any],
    session: Mapping[str, Any],
    action: Mapping[str, Any],
) -> Dict[str, Any]:
    inputs = _mapping(action.get("inputs"))
    explicit = inputs.get("intake")
    if isinstance(explicit, Mapping):
        intake = dict(explicit)
    else:
        constraints = _mapping(session.get("constraints"))
        intake = {
            "project_id": project_id,
            "name": str(snapshot.get("name") or project_id),
            "goal": str(session.get("mission") or ""),
            "intent": str(session.get("mission") or ""),
            "mode": str(snapshot.get("mode") or constraints.get("mode") or "greenfield"),
            "constraints": constraints,
            "parts": list(
                snapshot.get("parts")
                or snapshot.get("availableParts")
                or constraints.get("parts")
                or []
            ),
            "available_parts": list(
                snapshot.get("available_parts")
                or snapshot.get("availableParts")
                or constraints.get("available_parts")
                or []
            ),
        }
    intake["project_id"] = project_id
    intake.setdefault("goal", str(session.get("mission") or ""))
    intake.setdefault("intent", str(session.get("mission") or ""))
    intake.setdefault("constraints", _mapping(session.get("constraints")))
    return intake


def _plan_summary(plan: Mapping[str, Any]) -> Dict[str, Any]:
    readiness = _mapping(plan.get("engineering_readiness"))
    status = _mapping(plan.get("engineering_status"))
    closure = _mapping(plan.get("manufacturing_closure"))
    execution = _mapping(plan.get("engineering_execution_plan"))
    return {
        "schema_version": str(plan.get("schema_version") or ""),
        "engineering_readiness": readiness,
        "engineering_status": status,
        "manufacturing_closure": {
            "status": closure.get("status"),
            "blocking_check_count": len(_rows(closure.get("blocking_checks"))),
            "warning_check_count": len(_rows(closure.get("warning_checks"))),
        },
        "execution_preview": {
            "check_count": len(_rows(execution.get("checks"))),
            "unresolved_count": len(_rows(execution.get("unresolved"))),
            "automatic_execution": False,
        },
        "missing_info": [str(row) for row in list(plan.get("missing_info") or [])[:64]],
        "ordered_step_count": len(list(plan.get("ordered_steps") or [])),
    }


def _compose_summary(result: Mapping[str, Any]) -> Dict[str, Any]:
    quality_gate = _mapping(result.get("design_quality_gate"))
    failure = _mapping(result.get("failure"))
    return {
        "ok": bool(result.get("ok")),
        "mode": str(result.get("mode") or ""),
        "build_id": result.get("build_id"),
        "module_ids": [str(row) for row in list(result.get("module_ids") or [])[:64]],
        "design_quality_gate": quality_gate,
        "failure": failure,
        "warnings": [str(row) for row in list(result.get("warnings") or [])[:64]],
        "error": result.get("error"),
        "automatic_execution": False,
        "allow_llm_first": False,
        "export_gerber": False,
    }


def load_ai_project_action_execution(
    store: ProjectStore, project_id: str, session: Mapping[str, Any], action: Mapping[str, Any]
) -> Dict[str, Any] | None:
    """Read persisted execution, including detached native candidate receipts."""
    if isinstance(action.get("tool_result"), Mapping):
        return dict(action["tool_result"])
    if action.get("action_type") != "propose_kicad_edit":
        return None
    run_dir, _ = _run_root(store, project_id, str(session.get("session_id") or ""), str(action.get("action_id") or ""))
    receipt = load_candidate_execution_receipt(run_dir, project_id, session, action)
    return dict(receipt["tool_result"]) if receipt is not None else None


def execute_ai_project_action_preview(
    store: ProjectStore,
    project_id: str,
    session: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    guided_planner: Callable[..., Dict[str, Any]] | None = None,
    compose_callable: Callable[..., Dict[str, Any]] | None = None,
    execution_revision: int | None = None,
    prepared_snapshot_sink: Callable[[Mapping[str, Any]], None] | None = None,
) -> Dict[str, Any]:
    """Execute one accepted allowlisted action against its pinned project revision."""

    kwargs = {
        "guided_planner": guided_planner,
        "compose_callable": compose_callable,
        "execution_revision": execution_revision,
        "prepared_snapshot_sink": prepared_snapshot_sink,
    }
    if action.get("action_type") == "propose_kicad_edit":
        run_dir, _ = _run_root(store, project_id, str(session.get("session_id") or ""), str(action.get("action_id") or ""))
        with candidate_execution_lock(run_dir):
            return _execute_action(store, project_id, session, action, **kwargs)
    return _execute_action(store, project_id, session, action, **kwargs)


def _execute_action(
    store: ProjectStore,
    project_id: str,
    session: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    guided_planner: Callable[..., Dict[str, Any]] | None,
    compose_callable: Callable[..., Dict[str, Any]] | None,
    execution_revision: int | None,
    prepared_snapshot_sink: Callable[[Mapping[str, Any]], None] | None,
) -> Dict[str, Any]:

    action_type = str(action.get("action_type") or "")
    if action_type not in EXECUTABLE_AI_PREVIEW_ACTIONS:
        raise AIActionNotExecutable(
            f"AI action type {action_type!r} is not executable in the preview boundary"
        )
    decision = _mapping(action.get("decision"))
    accepted = (
        str(action.get("status") or "") == "accepted"
        and str(decision.get("decision") or "") == "accepted"
        and bool(str(decision.get("reviewer") or "").strip())
        and bool(str(decision.get("decided_at") or "").strip())
        and decision.get("executed") is False
    )
    if not accepted:
        raise AIActionNotAccepted(
            "AI action requires a persisted, unexecuted human acceptance decision"
        )
    if action.get("tool_result"):
        return dict(action.get("tool_result") or {})
    if action.get("unrecognized_source_ids"):
        raise AIActionNotExecutable("model action has unrecognized source citations")

    session_id = _safe_id(session.get("session_id"), "session_id")
    action_id = _safe_id(action.get("action_id"), "action_id")
    pinned_revision = int(
        action.get("project_revision") or session.get("project_revision") or 0
    )
    if pinned_revision < 1:
        raise ValueError("AI action has no valid pinned project revision")
    pinned = store.load(project_id, revision=pinned_revision)
    snapshot = dict(pinned["snapshot"])
    run_dir, relative_run_dir = _run_root(store, project_id, session_id, action_id)
    execution_identity: dict[str, Any] = {}
    if action_type == "propose_kicad_edit":
        receipt = load_candidate_execution_receipt(run_dir, project_id, session, action)
        if receipt is not None:
            return dict(receipt["tool_result"])
    if action_type in {"promote_registered_sources", "propose_kicad_edit"}:
        current, execution_identity = unchanged_execution_base(
            store, project_id, pinned_revision=pinned_revision,
            expected_revision=execution_revision,
            require_native_pin=action_type == "propose_kicad_edit",
        )
    started_at = _utc_now()
    prepared_bundle: dict[str, Any] | None = None

    try:
        if action_type == "promote_registered_sources":
            from .source_project_editing import prepare_kicad_source_bundle

            inputs = validate_action_inputs(action_type, _mapping(action.get("inputs")))
            prepared = prepare_kicad_source_bundle(
                store, project_id, expected_revision=int(current["revision"]),
                source_ids=inputs.get("source_ids"),
                primary_source_id=inputs.get("primary_source_id"),
            )
            prepared_bundle = prepared
            artifact_name = "source_promotion.json"
            artifact = _atomic_write_json(run_dir / artifact_name, prepared["promotion"])
            summary = {
                "ok": True, "promotion": prepared["promotion"],
                "prepared_build_dir": prepared["build_dir"],
                "source_identity": execution_identity,
                "source_revision_impact": prepared["snapshot"].get("sourceRevisionImpact"),
                "automatic_execution": False,
            }
            if prepared_snapshot_sink is not None:
                prepared_snapshot_sink(prepared["snapshot"])
        elif action_type == "propose_kicad_edit":
            from .project_candidates import propose_candidate
            from .project_review_store import ProjectReviewStore

            inputs = validate_action_inputs(action_type, _mapping(action.get("inputs")))
            proposed = propose_candidate(
                store, project_id, kind=inputs["kind"], ops=inputs["ops"],
                author=AI_TOOL_EXECUTOR_IDENTITY,
                note=inputs.get("note") or str(action.get("title") or "AI proposed native edit"),
                base_revision=int(current["revision"]),
                verified=False,
            )
            candidate = proposed["candidate"]
            review = ProjectReviewStore(store).get(project_id, candidate["review_id"])
            artifact_name = "kicad_candidate.json"
            artifact = _atomic_write_json(run_dir / artifact_name, proposed)
            summary = {
                "ok": True,
                "candidate_id": candidate["candidate_id"],
                "review_id": candidate["review_id"],
                "base_revision": candidate["base_revision"],
                "kind": candidate["kind"],
                "base_sha256": candidate["base_sha256"],
                "edited_sha256": candidate["edited_sha256"],
                "source_identity": execution_identity,
                "checks": candidate["checks"],
                "source_revision_impact": _mapping(review.get("candidate_snapshot")).get("sourceRevisionImpact"),
                "review_status": "pending",
                "candidate_accepted": False,
                "automatic_execution": False,
            }
        elif action_type == "run_guided_plan":
            planner = guided_planner or plan_guided_engineering_project
            intake = _planner_intake(project_id, snapshot, session, action)
            plan = planner(
                intake,
                engineering_sources=_combined_sources(snapshot),
                declared_conflicts=[],
                baseline_project=None,
                skip_vision=True,
            )
            artifact_path = run_dir / "guided_plan.json"
            artifact = _atomic_write_json(artifact_path, plan)
            summary = _plan_summary(plan)
            artifact_name = "guided_plan.json"
        elif action_type == "generate_board_carrier_candidate":
            design_dir = run_dir / 'parametric_board_carrier'
            generated = generate_registered_pcb_carrier(
                project_id, _rows(snapshot.get("engineeringSources")),
                design_dir, project_root=store.root,
            )
            artifact_path = run_dir / 'carrier_design_manifest.json'
            artifact = _atomic_write_json(artifact_path, generated)
            summary = {
                "ok": True, "status": generated.get("status"),
                "source_board_sha256": generated.get("registered_board_sha256"),
                "board_bbox_mm": generated.get("board_bbox_mm"),
                "carrier_outer_mm": generated.get("carrier_outer_mm"),
                "valid_solid": generated.get("validated_single_solid"),
                "artifact_dir_relative": f"{relative_run_dir}/parametric_board_carrier",
                "generated_artifacts": generated.get("generated_artifacts"),
                "geometric_envelope_only": True,
                "device_fit_verified": False,
                "fabrication_authorized": False,
                "manufacturing_approved": False,
                "automatic_execution": False,
            }
            artifact_name = artifact_path.name
        elif action_type == "inspect_registered_sources":
            # Multi-domain software action; source types, rather than the device
            # name, dispatch to KiCad, CAD, repair guide and/or reference BOM.
            # Model inputs never supply paths, commands, source claims or ratings.
            inspected = analyze_registered_project_bundle(
                project_id, _rows(snapshot.get("engineeringSources")),
                project_root=store.root,
                budget_cap_usd=_mapping(snapshot.get('constraints')).get('max_cost_usd'),
            )
            artifact_path = run_dir / "registered_engineering_sources.json"
            artifact = _atomic_write_json(artifact_path, inspected)
            summary = {
                "ok": True,
                "result_status": inspected.get("status"),
                "source_set_sha256": inspected.get("source_set_sha256"),
                "source_types": sorted(set(
                    row.get("kind", "unsupported")
                    for row in _mapping(inspected.get("input_sources")).values()
                    if isinstance(row, Mapping))),
                "project_context": inspected.get("project_context"),
                "rule_check_count": len(_mapping(inspected.get("software_checks"))),
                "geometry_items": len(_mapping(inspected.get("geometry"))),
                "repair_guides": len(_mapping(inspected.get("repair_evidence"))),
                "reference_bom_audit": bool(inspected.get("alternative_reference_bom_audit")),
                "source_inspection_only": True,
                "source_analysis_complete": inspected.get("status") in {"analyzed_with_findings", "analyzed_non_electrical_sources"},
                "source_analysis_failures": inspected.get("source_analysis_failures") or [],
                "engineering_objective_completed": False,
                "physical_fit_verified": False,
                "repair_diagnosis_verified": False,
                "manufacturing_approved": False,
                "automatic_execution": False,
            }
            artifact_name = artifact_path.name
        elif action_type in {"run_erc", "run_drc"}:
            from .artifact_retention import load_artifact_pin

            gate = "erc" if action_type == "run_erc" else "drc"
            kind = "schematic" if gate == "erc" else "pcb"
            pin = load_artifact_pin(store, project_id, pinned_revision)
            if pin is not None and _mapping(pin.get("artifacts")).get(kind) is not None:
                from .source_project_editing import check_retained_native_design

                # Check this action's design revision, including accepted native
                # edits. Later bookkeeping or design revisions never rebase it.
                checked = check_retained_native_design(
                    store, project_id, expected_revision=pinned_revision, kind=kind,
                )
                checks = _mapping(checked.get("checks"))
                if checks.get("ran") is not True:
                    raise ValueError(f"retained native {gate} check did not run: {checks.get('reason') or 'unavailable'}")
                actual = _mapping(checks.get("after"))
                artifact_path = run_dir / f"{gate}_retained_project.json"
                summary = {
                    "ok": True, "source_revision": pinned_revision,
                    "source_sha256": checked.get("source_sha256"),
                    "source_context": checked.get("source_context"),
                    "project_context": "retained_native_revision",
                    "check": gate, "check_executed": True,
                    "check_status": "executed",
                    "rule_finding_count": actual.get("total"),
                    "rule_findings_by_type": actual.get("by_type"),
                    "checks": checks,
                }
            else:
                # Legacy projects without a native pin retain the original
                # uploaded-source behavior, still bound to the pinned snapshot.
                checked = analyze_registered_project_bundle(
                    project_id, _rows(snapshot.get("engineeringSources")), project_root=store.root,
                )
                actual = _mapping(_mapping(checked.get("software_checks")).get(gate))
                if checked.get("project_context") != "source_bundle_sibling_files_present" or not actual.get("check_executed"):
                    raise ValueError(f"complete registered KiCad project required for {gate} preview")
                artifact_path = run_dir / f"{gate}_registered_project.json"
                summary = {
                    "ok": True, "source_set_sha256": checked.get("source_set_sha256"),
                    "project_context": checked.get("project_context"),
                    "project_stem": checked.get("project_stem"),
                    "check": gate, "check_executed": True,
                    "check_status": actual.get("status"),
                    "rule_finding_count": actual.get("rule_finding_count"),
                    "rule_findings_by_type": actual.get("rule_findings_by_type"),
                    "report_sha256": actual.get("report_sha256"),
                }
            artifact = _atomic_write_json(artifact_path, checked)
            summary.update({
                "source_design_is_not_validated": True,
                "manufacturing_approved": False,
                "automatic_execution": False,
            })
            artifact_name = artifact_path.name
        elif action_type == "run_compose":
            compose = compose_callable or compose_dispatch
            inputs = validate_action_inputs(action_type, _mapping(action.get("inputs")))
            phrase = str(
                inputs.get("phrase")
                or inputs.get("goal")
                or session.get("mission")
                or ""
            ).strip()
            if not phrase and not any(
                inputs.get(key) for key in ("module_ids", "resolved_modules", "canvas_nodes", "netlist")
            ):
                raise ValueError("run_compose requires a goal or structured circuit inputs")
            constraints = {
                **_mapping(session.get("constraints")),
                **_mapping(inputs.get("constraints")),
            }
            compose_dir = run_dir / "compose"
            result = compose(
                out_dir=compose_dir,
                phrase=phrase or None,
                module_ids=inputs.get("module_ids"),
                resolved_modules=inputs.get("resolved_modules"),
                canvas_nodes=inputs.get("canvas_nodes"),
                canvas_wires=inputs.get("canvas_wires"),
                netlist=inputs.get("netlist"),
                splice_plan=inputs.get("splice_plan"),
                build_id=inputs.get("build_id"),
                drc_fixup=inputs.get("drc_fixup"),
                constraints=constraints,
                material_mode=(
                    str(inputs.get("material_mode"))
                    if inputs.get("material_mode")
                    else None
                ),
                salvage_mode=bool(inputs.get("salvage_mode", False)),
                export_gerber=False,
                wire_only=bool(inputs.get("wire_only", False)),
                allow_llm_first=False,
                request_id=action_id,
            )
            artifact_path = run_dir / "compose_result.json"
            artifact = _atomic_write_json(artifact_path, result)
            summary = _compose_summary(result)
            artifact_name = "compose_result.json"
        else:
            raise AIActionNotExecutable(action_type)
        status_value = "succeeded"
        error = None
    except Exception as exc:
        if prepared_bundle is not None:
            from .source_project_editing import discard_prepared_kicad_source_bundle
            discard_prepared_kicad_source_bundle(prepared_bundle, store=store)
        status_value = "failed"
        summary = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "automatic_execution": False,
        }
        artifact_path = run_dir / "failure.json"
        artifact = _atomic_write_json(artifact_path, summary)
        artifact_name = "failure.json"
        error = {"type": type(exc).__name__, "message": str(exc)}

    completed_at = _utc_now()
    result = {
        "schema_version": AI_TOOL_RESULT_SCHEMA,
        "executor_identity": AI_TOOL_EXECUTOR_IDENTITY,
        "project_id": project_id,
        "project_revision": pinned_revision,
        "session_id": session_id,
        "action_id": action_id,
        "action_type": action_type,
        "status": status_value,
        "started_at": started_at,
        "completed_at": completed_at,
        "summary": summary,
        "error": error,
        "artifact": {
            "project_relative_path": f"{relative_run_dir}/{artifact_name}",
            **artifact,
        },
        "automatic_execution": False,
        "physical_authority_unchanged": True,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }
    if action_type == "propose_kicad_edit":
        result["execution_receipt_relative_path"] = f"{relative_run_dir}/execution_receipt.json"
        result["project_revision_advanced"] = False
        store_candidate_execution_receipt(
            run_dir, project_id, session, action, identity=execution_identity, result=result,
        )
    return result
