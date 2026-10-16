"""Drive one accepted fabrication mission to a terminal state.

This is an agent with no privileged path; it may only read the mission
(get_mission, read_run), propose events (propose with the given agent author and
the current expected_event_seq), and ask the executor for checks
(run_mission_operation). It must not call record_evaluation or accept_mission or
write files.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .device_draft import draft_from_parts_text
from .device_plan import DevicePlanError
from .device_suggestions import apply_first_suggestions
from .mission_executor import run_mission_operation
from .mission_store import MissionStateError, MissionStore

_CANDIDATE_ID = "A"
_EXCEEDS = "exceeds_limit"


def _propose(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    author: Mapping[str, Any],
    event: Mapping[str, Any],
) -> dict[str, Any]:
    view = missions.get_mission(project_id, mission_id)
    return missions.propose(
        project_id,
        mission_id,
        event,
        author=author,
        expected_event_seq=view["last_event_seq"],
    )


def _candidate(view: Mapping[str, Any], candidate_id: str = _CANDIDATE_ID) -> dict[str, Any]:
    return next(item for item in view["candidates"] if item.get("id") == candidate_id)


def _latest_eval(candidate: Mapping[str, Any], operation: str) -> dict[str, Any]:
    latest = None
    for item in candidate.get("evaluations") or []:
        if item.get("operation") == operation:
            latest = item
    if latest is None:
        raise MissionStateError(f"no {operation} evaluation is recorded for this candidate")
    return latest


def _finding_rules(plan: Mapping[str, Any]) -> list[str]:
    rules: list[str] = []
    seen: set[str] = set()
    for finding in plan.get("findings") or []:
        if not isinstance(finding, Mapping):
            continue
        if finding.get("severity") not in {"error", "warning"}:
            continue
        rule = finding.get("rule")
        if not isinstance(rule, str) or not rule or rule in seen:
            continue
        seen.add(rule)
        rules.append(rule)
    return rules


def _exceeded_limits(review: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for domain in review.get("domains") or []:
        if not isinstance(domain, Mapping):
            continue
        for check in domain.get("checks") or []:
            if not isinstance(check, Mapping) or check.get("status") != _EXCEEDS:
                continue
            names.append(str(check.get("id") or check.get("title") or check.get("summary") or "limit"))
    return names


def _block(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    author: Mapping[str, Any],
    *,
    blocker: str,
    need: str,
    reason: str,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {"type": "evidence_required", "blocker": blocker, "need": need}
    if candidate_id is not None:
        event["candidate_id"] = candidate_id
    view = _propose(missions, project_id, mission_id, author, event)
    terminal: dict[str, Any] = {
        "type": "terminal_proposed",
        "state": blocker,
        "reason": reason,
        "cites": [view["last_event_seq"]],
    }
    if candidate_id is not None:
        terminal["candidate_id"] = candidate_id
    return _propose(missions, project_id, mission_id, author, terminal)


def _budget_exhausted(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    author: Mapping[str, Any],
) -> dict[str, Any]:
    return _propose(
        missions,
        project_id,
        mission_id,
        author,
        {
            "type": "terminal_proposed",
            "state": "BUDGET_EXHAUSTED",
            "reason": "the operator job budget cannot pay for the review",
        },
    )


def _run_check(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    *,
    operation: str,
) -> dict[str, Any] | None:
    try:
        return run_mission_operation(
            missions, project_id, mission_id, candidate_id=_CANDIDATE_ID, operation=operation
        )
    except MissionStateError as exc:
        if "budget" in str(exc).lower():
            return None
        raise


def _inventory_grounds_part_data(view: Mapping[str, Any]) -> bool:
    """Whether HS's reading of the person's list shows missing part data, the only grounding the store accepts."""
    inventory = view.get("inventory") or {}
    reading, draft = inventory.get("reading") or {}, inventory.get("draft") or {}
    return bool(reading.get("left_out") or not draft.get("ok")
                or int(draft.get("plan_errors") or 0) + int(draft.get("plan_warnings") or 0))


def _candidate_spec(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    author: Mapping[str, Any],
    view: Mapping[str, Any],
    starting_spec: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if starting_spec is not None:
        return copy.deepcopy(dict(starting_spec)), None
    inventory = list(view["intake"]["inventory"])
    try:
        draft = draft_from_parts_text({"text": "\n".join(inventory)})
    except DevicePlanError as exc:
        need = f"No library draft for the listed parts: {exc}"
        return None, _block(
            missions,
            project_id,
            mission_id,
            author,
            blocker="BLOCKED_NEEDS_PART_DATA",
            need=need,
            reason=need,
        )
    left_out = list((draft.get("parsed") or {}).get("left_out") or [])
    if left_out:
        need = "Not in the device library, so HS has no data to plan them: " + ", ".join(left_out)
        return None, _block(
            missions,
            project_id,
            mission_id,
            author,
            blocker="BLOCKED_NEEDS_PART_DATA",
            need=need,
            reason=need,
        )
    return dict(draft["spec"]), None


def run_mission(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    *,
    author: Mapping[str, Any],
    starting_spec: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    view = missions.get_mission(project_id, mission_id)
    if view.get("terminal") is not None:
        return view
    if view.get("accepted") is None:
        raise MissionStateError("mission has not been accepted")

    spec, blocked = _candidate_spec(missions, project_id, mission_id, author, view, starting_spec)
    if blocked is not None:
        return blocked
    inventory = list(view["intake"]["inventory"])
    label = ", ".join(inventory) or "candidate A"
    if len(label) > 200:
        label = label[:200]
    rationale = (
        "the person's own wiring of the listed inventory"
        if starting_spec is not None
        else "drafted from the listed inventory"
    )
    view = _propose(
        missions,
        project_id,
        mission_id,
        author,
        {
            "type": "candidate_proposed",
            "candidate": {
                "id": _CANDIDATE_ID,
                "kind": "clean_sheet",
                "label": label,
                "spec": spec,
                "rationale": rationale,
            },
        },
    )

    max_repairs = int(view["budgets"]["max_repairs_per_candidate"])
    bound = max_repairs + 2
    for _ in range(bound):
        ran = _run_check(missions, project_id, mission_id, operation="device_plan")
        if ran is None:
            return _budget_exhausted(missions, project_id, mission_id, author)
        view = ran
        candidate = _candidate(view)
        evaluation = _latest_eval(candidate, "device_plan")
        plan = missions.read_run(project_id, mission_id, evaluation["artifact"])
        errors = int(evaluation["result"].get("errors") or 0)
        warnings = int(evaluation["result"].get("warnings") or 0)
        if errors == 0 and warnings == 0:
            break
        if int(candidate["repairs"]) >= max_repairs:
            # The runner has no second architecture to propose, so it never claims the search is exhausted. Without
            # HS grounding for a part-data blocker it leaves the mission open: honest, unlike an invented blocker.
            if not _inventory_grounds_part_data(view):
                return view
            need = "The latest plan still has findings after this candidate's repairs are spent"
            return _block(
                missions,
                project_id,
                mission_id,
                author,
                blocker="BLOCKED_NEEDS_PART_DATA",
                need=need,
                reason=need,
                candidate_id=_CANDIDATE_ID,
            )
        rules = _finding_rules(plan)
        named = ", ".join(rules) if rules else "findings"
        if isinstance(plan, dict) and "wires" in plan and "findings" in plan:
            new_spec, changed = apply_first_suggestions(candidate["spec"], plan)
        else:
            new_spec, changed = candidate["spec"], False
        if changed:
            view = _propose(
                missions,
                project_id,
                mission_id,
                author,
                {
                    "type": "repair_proposed",
                    "candidate_id": _CANDIDATE_ID,
                    "spec": new_spec,
                    "rationale": f"apply planner suggestions for {named}",
                },
            )
            continue
        if not _inventory_grounds_part_data(view):
            # HS's own draft of the listed parts plans clean, so part data is not what is missing. Leave it open.
            return view
        need = f"The planner reports {named} and offers no repair HS can express"
        return _block(
            missions,
            project_id,
            mission_id,
            author,
            blocker="BLOCKED_NEEDS_PART_DATA",
            need=need,
            reason=need,
            candidate_id=_CANDIDATE_ID,
        )
    else:
        if not _inventory_grounds_part_data(view):
            # HS's own draft of the listed parts plans clean, so part data is not what is missing. Leave it open.
            return view
        need = "The planner did not reach a clean plan within the repair bound"
        return _block(
            missions,
            project_id,
            mission_id,
            author,
            blocker="BLOCKED_NEEDS_PART_DATA",
            need=need,
            reason=need,
            candidate_id=_CANDIDATE_ID,
        )

    ran = _run_check(missions, project_id, mission_id, operation="device_engineering")
    if ran is None:
        return _budget_exhausted(missions, project_id, mission_id, author)
    view = ran
    candidate = _candidate(view)
    review_eval = _latest_eval(candidate, "device_engineering")
    review = missions.read_run(project_id, mission_id, review_eval["artifact"])
    if int(review_eval["result"].get("errors") or 0) > 0:
        exceeded = _exceeded_limits(review)
        if exceeded:
            need = f"Engineering review exceeds limits: {', '.join(exceeded)}"
        elif isinstance(review, dict) and review.get("refused"):
            need = f"Engineering review exceeds limits: {review['refused']}"
        else:
            need = "Engineering review exceeds limits"
        return _block(
            missions,
            project_id,
            mission_id,
            author,
            blocker="BLOCKED_UNSAFE",
            need=need,
            reason=need,
            candidate_id=_CANDIDATE_ID,
        )
    plan_eval = _latest_eval(candidate, "device_plan")
    counts = review.get("counts") if isinstance(review, dict) else {}
    counts = counts if isinstance(counts, Mapping) else {}
    reason = (
        f"{plan_eval['result']['summary']}; engineering review "
        f"{int(counts.get('exceeds_limit') or 0)} exceeds_limit, "
        f"{int(counts.get('advisory') or 0)} advisory"
    )
    return _propose(
        missions,
        project_id,
        mission_id,
        author,
        {
            "type": "terminal_proposed",
            "state": "READY_FOR_HUMAN_BUILD",
            "candidate_id": _CANDIDATE_ID,
            "reason": reason,
        },
    )
