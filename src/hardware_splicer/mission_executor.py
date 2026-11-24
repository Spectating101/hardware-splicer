"""Software-only device checks for an accepted fabrication mission.

The executor runs Hardware Splicer's own canonical device functions against a
candidate's current spec and records what they returned. It never flashes,
never powers a board, never writes a project snapshot, and never grants
physical or release authority. Only an accepted mission may run, and only
within the mission's operator-job budget. A check that refuses or cannot run
is recorded as a failure, never as a pass.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .device_application import build_device_application
from .device_application_runtime import DeviceRuntimeError, run_device_application
from .device_case import build_device_case
from .device_engineering import build_engineering_review
from .device_plan import DevicePlanError, build_device_plan
from .mission_store import MissionStateError, MissionStore, MissionValidationError

MISSION_OPERATIONS = (
    "device_plan",
    "device_engineering",
    "device_case",
    "device_application",
    "device_application_run",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))


def _count_severity(findings: Any, severity: str) -> int:
    if not isinstance(findings, list):
        return 0
    return sum(1 for item in findings if isinstance(item, Mapping) and item.get("severity") == severity)


def _plan_summary(findings: Any, errors: int, warnings: int) -> str:
    error_word = "error" if errors == 1 else "errors"
    warning_word = "warning" if warnings == 1 else "warnings"
    rules = [
        str(item.get("rule"))
        for item in findings
        if isinstance(item, Mapping) and item.get("severity") == "error" and item.get("rule")
    ]
    if rules:
        return f"device_plan: {errors} {error_word} ({', '.join(rules)}), {warnings} {warning_word}"
    return f"device_plan: {errors} {error_word}, {warnings} {warning_word}"


def _failing_scenarios(phase: Any) -> int:
    if not isinstance(phase, Mapping):
        return 0
    rows = phase.get("scenarios")
    if not isinstance(rows, list):
        return 0
    failed = 0
    for row in rows:
        if not isinstance(row, Mapping):
            failed += 1
            continue
        if row.get("pass") is not True or row.get("finding", False) is not False:
            failed += 1
    return failed


def _refused(message: str) -> tuple[int, int, str, dict[str, Any]]:
    return 1, 0, f"refused: {message}", {"refused": message}


def _not_run(reason: str) -> tuple[int, int, str, dict[str, Any]]:
    return 1, 0, f"not run: {reason}", {"not_run": reason}


def _run_operation(operation: str, spec: Mapping[str, Any]) -> tuple[int, int, str, Any]:
    if operation == "device_plan":
        plan = build_device_plan(spec)
        findings = plan.get("findings") or []
        errors = _count_severity(findings, "error")
        warnings = _count_severity(findings, "warning")
        return errors, warnings, _plan_summary(findings, errors, warnings), plan
    if operation == "device_engineering":
        review = build_engineering_review(spec)
        counts = review.get("counts") or {}
        errors = int(counts.get("exceeds_limit") or 0)
        warnings = int(counts.get("advisory") or 0)
        summary = (
            f"device_engineering: {errors} exceeds_limit, {warnings} advisory; "
            "the review never passes anything"
        )
        return errors, warnings, summary, review
    if operation == "device_case":
        metadata, _package = build_device_case(spec)
        return 0, 0, "device_case: 0 errors, 0 warnings", metadata
    if operation == "device_application":
        metadata, _package = build_device_application(spec)
        return 0, 0, "device_application: 0 errors, 0 warnings", metadata
    result = run_device_application(spec)
    errors = _failing_scenarios(result.get("host")) + _failing_scenarios(result.get("vendor_host"))
    status = result.get("status")
    warnings = 0
    notes = []
    if status == "FAILED" and errors == 0:
        errors = 1  # the runtime's own verdict outranks a scenario count that happens to be empty
        notes.append("the runtime reported FAILED")
    if status != "PASSED":
        # PARTIAL: the host tests ran but the vendor-host lane did not, so it is not a clean result.
        warnings = 1
        vendor = result.get("vendor_host") if isinstance(result.get("vendor_host"), Mapping) else {}
        notes.append(f"status {status}; vendor-host lane: {vendor.get('status', 'unknown')}")
    summary = f"device_application_run: {errors} failing scenarios" + (f" ({'; '.join(notes)})" if notes else "")
    return errors, warnings, summary, result


def run_mission_operation(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    *,
    candidate_id: str,
    operation: str,
) -> dict[str, Any]:
    # Lock BEFORE reading the spec and checking the budget, through recording
    # the result. No repair/terminal/second run can interleave and cause old
    # work to be credited to a new spec, or spend the same remaining job twice.
    with missions.mutation(project_id, mission_id):
        return _run_locked_mission_operation(
            missions, project_id, mission_id, candidate_id=candidate_id, operation=operation
        )


def _run_locked_mission_operation(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    *,
    candidate_id: str,
    operation: str,
) -> dict[str, Any]:
    if operation not in MISSION_OPERATIONS:
        raise MissionValidationError(
            "operation must be one of device_plan, device_engineering, device_case, "
            "device_application, device_application_run"
        )
    view = missions.get_mission(project_id, mission_id)
    if view.get("accepted") is None:
        raise MissionStateError("mission has not been accepted")
    # Refuse before running: a finished or over-budget mission must not spend a compile or a test run.
    if view.get("terminal") is not None:
        raise MissionStateError("mission is terminal and runs no more checks")
    budgets = view["budgets"]
    if int(budgets["operator_jobs_used"]) >= int(budgets["max_operator_jobs"]):
        raise MissionStateError("operator job budget is exhausted")
    candidate = next((item for item in view["candidates"] if item.get("id") == candidate_id), None)
    if candidate is None:
        raise MissionValidationError(f"candidate {candidate_id!r} does not exist")
    spec = candidate["spec"]
    try:
        errors, warnings, summary, artifact = _run_operation(operation, spec)
    except DevicePlanError as exc:
        errors, warnings, summary, artifact = _refused(str(exc))
    except DeviceRuntimeError as exc:
        errors, warnings, summary, artifact = _not_run(str(exc))
    return missions.record_evaluation(
        project_id,
        mission_id,
        candidate_id=candidate_id,
        operation=operation,
        result={"errors": errors, "warnings": warnings, "summary": summary},
        artifact=_json_safe(artifact),
    )
