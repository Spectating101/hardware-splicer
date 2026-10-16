"""Append-only fabrication missions anchored beside a project.

The agent proposes; Hardware-Splicer decides what is recorded. Evaluations are
written only by HS itself. State is replayed from the event log every time.
Reaching the correct terminal state is success. A mission never changes a
project snapshot or revision and never grants physical authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping

try:
    import fcntl
except ImportError:  # Other API surfaces remain importable on non-POSIX hosts.
    fcntl = None

from .device_draft import draft_from_parts_text, parse_parts_text
from .device_plan import DevicePlanError, build_device_plan
from .project_store import InvalidProjectId, ProjectNotFound, ProjectStore, validate_project_id

MISSION_SCHEMA = "hardware_splicer.fabrication_mission.v1"
PHASES = (
    "INTAKE",
    "ARCHITECTING",
    "EVALUATING",
    "REPAIRING",
    "EVIDENCE_REQUIRED",
    "TERMINAL",
)
TERMINAL_STATES = (
    "READY_FOR_HUMAN_BUILD",
    "BLOCKED_NEEDS_PART_DATA",
    "BLOCKED_NEEDS_REVERSE_ENGINEERING",
    "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
    "BLOCKED_NEEDS_PROCUREMENT_EVIDENCE",
    "BLOCKED_UNSAFE",
    "NO_FEASIBLE_ARCHITECTURE",
    "BUDGET_EXHAUSTED",
)
_BLOCKED_STATES = frozenset(state for state in TERMINAL_STATES if state.startswith("BLOCKED_"))
_CANDIDATE_KINDS = frozenset({"clean_sheet", "reclaim_heavy", "hybrid"})
_PROPOSE_TYPES = frozenset(
    {"candidate_proposed", "repair_proposed", "evidence_required", "terminal_proposed"}
)
_EVENT_TYPES = _PROPOSE_TYPES | {"opened", "evaluation_recorded", "accepted", "inventory_read"}
_EVAL_OPERATIONS = frozenset(
    {
        "device_draft",
        "device_plan",
        "device_engineering",
        "device_case",
        "device_application",
        "device_application_run",
        "device_reclaim_match",
    }
)
_AUTHOR_KEYS = frozenset({"kind", "id"})
_AUTHOR_KINDS = frozenset({"human", "agent", "system"})
_INTAKE_KEYS = frozenset({"goal", "constraints", "inventory", "budgets"})
_BUDGET_KEYS = frozenset({"max_candidates", "max_repairs_per_candidate", "max_operator_jobs"})
_CANDIDATE_KEYS = frozenset({"id", "kind", "label", "spec", "rationale"})
_RESULT_KEYS = frozenset({"errors", "warnings", "result_sha256", "summary"})
_DEFAULT_BUDGETS = {
    "max_candidates": 3,
    "max_repairs_per_candidate": 3,
    "max_operator_jobs": 20,
}
_MAX_CANDIDATES = 3
_MAX_AUTHOR_ID = 120
_MAX_GOAL = 500
_MAX_LIST_ITEM = 300
_MAX_LIST_ITEMS = 40
_MAX_LABEL = 200
_MAX_RATIONALE = 2000
_MAX_NEED = 4000
_MAX_REASON = 2000
_MAX_SUMMARY = 4000
_SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_RUN_ARTIFACT_RE = re.compile(r"^runs/[A-Za-z0-9._-]{1,128}\.json$")
_SYSTEM_AUTHOR = {"kind": "system", "id": "hardware-splicer"}
# The thread store's authority keys plus physical_correctness, checked at every depth, inside lists too.
_MISSION_FORBIDDEN_KEYS = frozenset(
    {"physical_correctness", "authority", "release", "fabrication", "power_on", "status", "revision_override"}
)
_PHYSICAL_EVIDENCE_REQUIRED = [
    "Bench power-on by a person; this terminal state does not authorize energising the board.",
    "Bus scan by a person; recorded evaluations do not establish that the physical buses match the plan.",
    "Measurement by a person; physical correctness remains UNPROVEN and is not granted by this record.",
]


class MissionError(RuntimeError):
    pass


class MissionNotFound(MissionError, FileNotFoundError):
    pass


class MissionConflict(MissionError):
    pass


class MissionStateError(MissionError):
    pass


class MissionValidationError(MissionError, ValueError):
    pass


def _serialized_mutation(method):
    @wraps(method)
    def serialized(self, project_id, mission_id, *args, **kwargs):
        with self.mutation(project_id, mission_id):
            return method(self, project_id, mission_id, *args, **kwargs)

    return serialized


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise MissionError(f"{label} must not be a symlink")


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _read_json(path: Path) -> Dict[str, Any]:
    _reject_symlink(path, label=path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MissionError(f"cannot read mission JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MissionError(f"mission JSON must be an object: {path}")
    return value


def _json_payload(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _reject_symlink(path, label=path.name)
    _reject_symlink(path.parent, label=path.parent.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_payload(value)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _atomic_create_json(path: Path, value: Mapping[str, Any]) -> None:
    """Create an immutable JSON record without replacing a concurrent writer."""

    _reject_symlink(path, label=path.name)
    _reject_symlink(path.parent, label=path.parent.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_payload(value)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError as exc:
            raise MissionConflict(f"immutable mission record already exists: {path.name}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _has_control_chars(value: str) -> bool:
    return any(unicodedata.category(ch).startswith("C") for ch in value)


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MissionValidationError(f"{label} must be an object")
    return value


def _reject_authority(value: Any, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = str(key).lower()
            if "authoriz" in lowered or lowered in _MISSION_FORBIDDEN_KEYS:
                raise MissionValidationError(f"{label} must not contain authority field {key!r}")
            _reject_authority(nested, label=f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_authority(nested, label=f"{label}[{index}]")


def _has_disallowed_controls(value: str) -> bool:
    """Control, format or surrogate characters, except the line breaks and tabs a summary may carry."""
    return any(ch not in "\n\t" and unicodedata.category(ch).startswith("C") for ch in value)


def _require_text(value: Any, *, field: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise MissionValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise MissionValidationError(f"{field} is required")
    if len(cleaned) > max_len:
        raise MissionValidationError(f"{field} must be at most {max_len} characters")
    if _has_control_chars(cleaned):
        raise MissionValidationError(f"{field} must not contain control characters")
    return cleaned


def _require_int(value: Any, *, field: str, min_value: int = 0) -> int:
    if type(value) is not int:
        raise MissionValidationError(f"{field} must be an integer")
    if value < min_value:
        raise MissionValidationError(f"{field} must be at least {min_value}")
    return value


def _normalize_string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MissionValidationError(f"{field} must be a list of strings")
    if len(value) > _MAX_LIST_ITEMS:
        raise MissionValidationError(f"{field} must have at most {_MAX_LIST_ITEMS} items")
    items: list[str] = []
    for index, item in enumerate(value):
        items.append(_require_text(item, field=f"{field}[{index}]", max_len=_MAX_LIST_ITEM))
    return items


def _normalize_author(author: Any, *, allow_system: bool = False) -> Dict[str, str]:
    raw = _require_mapping(author, label="author")
    _reject_authority(raw, label="author")
    extra = set(raw) - _AUTHOR_KEYS
    if extra:
        raise MissionValidationError(f"author contains unknown fields: {sorted(extra)}")
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind.strip() not in _AUTHOR_KINDS:
        raise MissionValidationError("author.kind must be 'human', 'agent', or 'system'")
    kind = kind.strip()
    if kind == "system" and not allow_system:
        raise MissionValidationError("only Hardware Splicer itself writes as a system author")
    author_id = raw.get("id")
    if not isinstance(author_id, str):
        raise MissionValidationError("author.id is required")
    author_id = author_id.strip()
    if not author_id:
        if kind == "agent":
            raise MissionValidationError("agent authors must have a non-empty id naming the agent/model")
        raise MissionValidationError("author.id is required")
    if len(author_id) > _MAX_AUTHOR_ID:
        raise MissionValidationError(f"author.id must be at most {_MAX_AUTHOR_ID} characters")
    if _has_control_chars(author_id):
        raise MissionValidationError("author.id must not contain control or surrogate characters")
    return {"kind": kind, "id": author_id}


def _normalize_budgets(value: Any) -> Dict[str, int]:
    budgets = dict(_DEFAULT_BUDGETS)
    if value is None:
        return budgets
    raw = _require_mapping(value, label="intake.budgets")
    _reject_authority(raw, label="intake.budgets")
    extra = set(raw) - _BUDGET_KEYS
    if extra:
        raise MissionValidationError(f"intake.budgets contains unknown fields: {sorted(extra)}")
    for key in _BUDGET_KEYS:
        if key not in raw:
            continue
        number = _require_int(raw[key], field=f"budgets.{key}", min_value=1)
        if key == "max_candidates" and number > _MAX_CANDIDATES:
            raise MissionValidationError(f"budgets.max_candidates must be at most {_MAX_CANDIDATES}")
        budgets[key] = number
    return budgets


def _normalize_intake(intake: Any) -> tuple[Dict[str, Any], Dict[str, int]]:
    raw = _require_mapping(intake, label="intake")
    _reject_authority(raw, label="intake")
    extra = set(raw) - _INTAKE_KEYS
    if extra:
        raise MissionValidationError(f"intake contains unknown fields: {sorted(extra)}")
    goal = _require_text(raw.get("goal"), field="goal", max_len=_MAX_GOAL)
    constraints = _normalize_string_list(raw.get("constraints"), field="constraints")
    inventory = _normalize_string_list(raw.get("inventory"), field="inventory")
    budgets = _normalize_budgets(raw.get("budgets"))
    return {"goal": goal, "constraints": constraints, "inventory": inventory}, budgets


def _normalize_slug(value: Any, *, field: str) -> str:
    text = _require_text(value, field=field, max_len=32)
    if _SLUG_RE.fullmatch(text) is None:
        raise MissionValidationError(f"{field} must be a short slug")
    return text


def _normalize_spec(value: Any, *, field: str) -> Dict[str, Any]:
    spec = dict(_require_mapping(value, label=field))
    _reject_authority(spec, label=field)
    # The log stores canonical JSON and the view replays it, so a spec must come back exactly as given:
    # string keys only, no NaN or infinity, lists not tuples, text without surrogates.
    try:
        encoded = json.dumps(spec, sort_keys=True, ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionValidationError(f"{field} must be plain JSON with string keys and finite numbers") from exc
    if json.loads(encoded) != spec:
        raise MissionValidationError(f"{field} must be plain JSON with string keys and finite numbers")
    return spec


def _normalize_candidate(value: Any) -> Dict[str, Any]:
    raw = _require_mapping(value, label="candidate")
    _reject_authority(raw, label="candidate")
    extra = set(raw) - _CANDIDATE_KEYS
    if extra:
        raise MissionValidationError(f"candidate contains unknown fields: {sorted(extra)}")
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind.strip() not in _CANDIDATE_KINDS:
        raise MissionValidationError("candidate.kind must be 'clean_sheet', 'reclaim_heavy', or 'hybrid'")
    return {
        "id": _normalize_slug(raw.get("id"), field="candidate.id"),
        "kind": kind.strip(),
        "label": _require_text(raw.get("label"), field="candidate.label", max_len=_MAX_LABEL),
        "spec": _normalize_spec(raw.get("spec"), field="candidate.spec"),
        "rationale": _require_text(raw.get("rationale"), field="candidate.rationale", max_len=_MAX_RATIONALE),
    }


def _normalize_result(value: Any, *, result_sha256: str | None = None) -> Dict[str, Any]:
    raw = dict(_require_mapping(value, label="result"))
    _reject_authority(raw, label="result")
    if result_sha256 is not None:
        raw["result_sha256"] = result_sha256
    extra = set(raw) - _RESULT_KEYS
    if extra:
        raise MissionValidationError(f"result contains unknown fields: {sorted(extra)}")
    sha = raw.get("result_sha256")
    if not isinstance(sha, str) or _SHA256_RE.fullmatch(sha) is None:
        raise MissionValidationError("result.result_sha256 must be 64 hex characters")
    summary = raw.get("summary")
    if not isinstance(summary, str):
        raise MissionValidationError("result.summary must be a string")
    if len(summary) > _MAX_SUMMARY:
        raise MissionValidationError(f"result.summary must be at most {_MAX_SUMMARY} characters")
    if _has_disallowed_controls(summary):
        raise MissionValidationError("result.summary must not contain control or surrogate characters")
    return {
        "errors": _require_int(raw.get("errors"), field="result.errors", min_value=0),
        "warnings": _require_int(raw.get("warnings"), field="result.warnings", min_value=0),
        "result_sha256": sha,
        "summary": summary,
    }


def _plan_is_failing(result: Mapping[str, Any] | None) -> bool:
    if result is None:
        return False
    return int(result.get("errors") or 0) > 0 or int(result.get("warnings") or 0) > 0


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _engineering_content(spec: Mapping[str, Any]) -> Dict[str, Any]:
    """What makes two candidates different designs: not their name, wire colours or the order things are listed in."""
    content = {key: value for key, value in spec.items() if key != "name"}
    if isinstance(content.get("modules"), list):
        content["modules"] = sorted(content["modules"], key=_canonical_json)
    if isinstance(content.get("connections"), list):
        content["connections"] = sorted(
            ({k: v for k, v in row.items() if k != "wire"} if isinstance(row, Mapping) else row
             for row in content["connections"]), key=_canonical_json)
    return content


def _read_inventory(inventory: list[str]) -> Dict[str, Any]:
    text = "\n".join(inventory)
    try:
        reading = parse_parts_text(text)
    except DevicePlanError as exc:
        # Intake permits empty and longer lists than the drafter. Preserve all lines as unknown
        # when parsing refuses, rather than losing the acceptance or treating them as covered.
        reading = {"fragments": [{"text": line, "matches": []} for line in inventory],
                   "controller": None, "parts": [], "left_out": list(inventory)}
        draft = {"ok": False, "error": str(exc), "plan_errors": 0, "plan_warnings": 0}
    else:
        try:
            spec = draft_from_parts_text({"text": text})["spec"]
            findings = build_device_plan(spec).get("findings") or []
            draft = {"ok": True, "error": None,
                     "plan_errors": sum(item.get("severity") == "error" for item in findings),
                     "plan_warnings": sum(item.get("severity") == "warning" for item in findings)}
        except DevicePlanError as exc:
            draft = {"ok": False, "error": str(exc), "plan_errors": 0, "plan_warnings": 0}
    result = {"reading": reading, "draft": draft}
    return {**result, "result_sha256": hashlib.sha256(_canonical_json(result).encode("utf-8")).hexdigest()}


def _inventory_coverage(reading: Mapping[str, Any], spec: Mapping[str, Any]) -> tuple[list[str], Counter]:
    modules = spec.get("modules")
    counts = Counter(item["module"] for item in modules
                     if isinstance(item, Mapping) and isinstance(item.get("module"), str)) if isinstance(modules, list) else Counter()
    uncovered = []
    for fragment in reading["fragments"]:
        matches = fragment["matches"]
        covered = bool(matches)
        for match in matches:
            module = match["module"]
            quantity = int(match.get("quantity", 1))
            available = min(quantity, counts[module])
            counts[module] -= available
            if available < quantity:
                covered = False
        if not covered:
            uncovered.append(fragment["text"])
    # left_out is normally also in fragments; preserve independent entries without doubling them.
    missing_left_out = Counter(reading["left_out"]) - Counter(uncovered)
    uncovered.extend(line for line, count in missing_left_out.items() for _ in range(count))
    return uncovered, counts


def _uncovered_inventory(reading: Mapping[str, Any], spec: Mapping[str, Any]) -> list[str]:
    """Consume module counts in inventory order; an instance cannot cover two fragments."""
    return _inventory_coverage(reading, spec)[0]


def _plan_is_clean(result: Mapping[str, Any] | None) -> bool:
    if result is None:
        return False
    return int(result.get("errors") or 0) == 0 and int(result.get("warnings") or 0) == 0


def _latest_operation(
    evaluations: list[Mapping[str, Any]],
    operation: str,
    *,
    after_seq: int = 0,
) -> Mapping[str, Any] | None:
    latest: Mapping[str, Any] | None = None
    for item in evaluations:
        if item.get("operation") != operation:
            continue
        if int(item.get("seq") or 0) <= after_seq:
            continue
        latest = item
    return latest


def _public_candidate(state: Mapping[str, Any], inventory: Mapping[str, Any] | None) -> Dict[str, Any]:
    uncovered, remaining = _inventory_coverage(inventory["reading"], state["spec"]) if inventory else ([], Counter())
    return {
        "id": state["id"],
        "kind": state["kind"],
        "label": state["label"],
        "rationale": state["rationale"],
        "spec": state["spec"],
        "repairs": state["repairs"],
        "covers_inventory": inventory is not None and not uncovered,
        "uncovered_inventory": uncovered,
        "not_in_inventory": sorted(module for module, count in remaining.items() if count > 0),
        "evaluations": [
            {
                "operation": item["operation"],
                "result": item["result"],
                "artifact": item.get("artifact"),
            }
            for item in state["evaluations"]
        ],
    }


def _replay(events: list[Mapping[str, Any]]) -> Dict[str, Any]:
    phase = "INTAKE"
    candidates: Dict[str, Dict[str, Any]] = {}
    terminal: Dict[str, Any] | None = None
    accepted: Dict[str, Any] | None = None
    inventory: Dict[str, Any] | None = None
    operator_jobs_used = 0
    for event in events:
        event_type = event.get("type")
        seq = int(event.get("seq") or 0)
        if event_type == "opened":
            phase = "INTAKE"
        elif event_type == "accepted":
            accepted = {
                "by": dict(event["author"]),
                "at": event["created_at"],
                "budgets": dict(event["budgets"]),
            }
        elif event_type == "candidate_proposed":
            candidate = dict(event["candidate"])
            candidate_id = candidate["id"]
            candidates[candidate_id] = {
                "id": candidate_id,
                "kind": candidate["kind"],
                "label": candidate["label"],
                "rationale": candidate["rationale"],
                "spec": candidate["spec"],
                "repairs": 0,
                "evaluations": [],
                "proposal_seq": seq,
                "last_repair_seq": None,
            }
            phase = "ARCHITECTING"
        elif event_type == "inventory_read":
            inventory = {key: event[key] for key in ("reading", "draft", "result_sha256")}
        elif event_type == "repair_proposed":
            candidate_id = event["candidate_id"]
            state = candidates[candidate_id]
            state["spec"] = event["spec"]
            state["repairs"] = int(state["repairs"]) + 1
            state["last_repair_seq"] = seq
            phase = "REPAIRING"
        elif event_type == "evaluation_recorded":
            candidate_id = event["candidate_id"]
            candidates[candidate_id]["evaluations"].append(
                {
                    "seq": seq,
                    "operation": event["operation"],
                    "result": event["result"],
                    "artifact": event.get("artifact"),
                    "covers_inventory": inventory is not None and not _uncovered_inventory(
                        inventory["reading"], candidates[candidate_id]["spec"]),
                }
            )
            operator_jobs_used += 1
            phase = "EVALUATING"
        elif event_type == "evidence_required":
            phase = "EVIDENCE_REQUIRED"
        elif event_type == "terminal_proposed":
            phase = "TERMINAL"
            terminal = {
                "state": event["state"],
                "reason": event["reason"],
                "candidate_id": event.get("candidate_id"),
                "cites": list(event.get("cites") or []),
                "grounding": event.get("grounding"),
            }
            if event["state"] == "READY_FOR_HUMAN_BUILD":
                terminal["physical_evidence_required"] = list(_PHYSICAL_EVIDENCE_REQUIRED)
    repairs_used = {cid: state["repairs"] for cid, state in candidates.items() if state["repairs"]}
    last_event_seq = int(events[-1]["seq"]) if events else 0
    return {
        "phase": phase,
        "inventory": inventory,
        "candidates": candidates,
        "repairs_used": repairs_used,
        "operator_jobs_used": operator_jobs_used,
        "terminal": terminal,
        "accepted": accepted,
        "last_event_seq": last_event_seq,
        "last_event_at": events[-1]["created_at"] if events else "",
    }


def _since_seq(candidate: Mapping[str, Any]) -> int:
    last_repair = candidate.get("last_repair_seq")
    if last_repair is not None:
        return int(last_repair)
    return int(candidate.get("proposal_seq") or 0)


def _open_evidence_need_blocks(events: list[Mapping[str, Any]], candidate_id: str) -> bool:
    for item in events:
        if item.get("type") != "evidence_required":
            continue
        named = item.get("candidate_id")
        if named is None or named == candidate_id:
            return True
    return False


def _ready_problem(replayed: Mapping[str, Any], events: list[Mapping[str, Any]], candidate_id: Any) -> str | None:
    """Why this candidate is not ready for a human build, or None when HS's own evaluations support it."""

    candidates = replayed["candidates"]
    if not isinstance(candidate_id, str) or candidate_id not in candidates:
        return "READY_FOR_HUMAN_BUILD requires a candidate with a passing device_plan"
    candidate = candidates[candidate_id]
    inventory = replayed.get("inventory")
    if inventory is None:
        return "READY_FOR_HUMAN_BUILD requires an HS inventory_read event"
    uncovered = _uncovered_inventory(inventory["reading"], candidate["spec"])
    if uncovered:
        return ("READY_FOR_HUMAN_BUILD is refused: the candidate does not contain "
                + ", ".join(uncovered) + " from the person's inventory")
    plan = _latest_operation(candidate["evaluations"], "device_plan", after_seq=_since_seq(candidate))
    if plan is None or not _plan_is_clean(plan.get("result")):
        return "READY_FOR_HUMAN_BUILD requires a passing device_plan after the latest repair"
    engineering = _latest_operation(candidate["evaluations"], "device_engineering", after_seq=int(plan["seq"]))
    if engineering is None:
        return "READY_FOR_HUMAN_BUILD requires a device_engineering evaluation after the passing plan"
    if int(engineering["result"].get("errors") or 0) > 0:
        return "READY_FOR_HUMAN_BUILD requires a device_engineering evaluation with no errors after the passing plan"
    if _open_evidence_need_blocks(events, candidate_id):
        return "READY_FOR_HUMAN_BUILD is refused while an evidence need stands for this candidate or the mission"
    return None


def _assert_ready_for_human_build(
    replayed: Mapping[str, Any],
    event: Mapping[str, Any],
    events: list[Mapping[str, Any]],
) -> None:
    problem = _ready_problem(replayed, events, event.get("candidate_id"))
    if problem:
        raise MissionStateError(problem)


def _assert_no_ready_candidate(replayed: Mapping[str, Any], events: list[Mapping[str, Any]], state: str) -> None:
    # The correct terminal state is the goal: a mission may not stop short of a candidate that is already ready.
    for candidate_id in replayed["candidates"]:
        if _ready_problem(replayed, events, candidate_id) is None:
            raise MissionStateError(f"{state} is refused: candidate {candidate_id} is ready for a human build")


def _assert_blocked_cites(events: list[Mapping[str, Any]], event: Mapping[str, Any]) -> list[int]:
    state = event.get("state")
    cites = event.get("cites")
    if cites is None:
        cites = []
    if not isinstance(cites, list):
        raise MissionValidationError("cites must be a list of event sequence numbers")
    normalized: list[int] = []
    by_seq = {int(item["seq"]): item for item in events}
    target = event.get("candidate_id")
    matched = False
    for item in cites:
        seq = _require_int(item, field="cites item", min_value=1)
        named = by_seq.get(seq)
        if named is None or named.get("type") not in {"evidence_required", "evaluation_recorded"}:
            raise MissionStateError(f"{state} may cite only existing evidence_required or evaluation_recorded events ({seq})")
        if (named.get("type") == "evidence_required" and named.get("blocker") == state
                and (named.get("candidate_id") is None or target is None or named.get("candidate_id") == target)):
            matched = True
        normalized.append(seq)
    if not matched:
        raise MissionStateError(f"{state} must cite an evidence_required event with that blocker for this candidate")
    return normalized


def _assert_no_feasible_architecture(replayed: Mapping[str, Any], budgets: Mapping[str, int]) -> None:
    candidates = replayed["candidates"]
    if not candidates:
        raise MissionStateError("NO_FEASIBLE_ARCHITECTURE requires at least one candidate")
    max_repairs = int(budgets["max_repairs_per_candidate"])
    for candidate_id, candidate in candidates.items():
        after_seq = _since_seq(candidate)
        plan = _latest_operation(candidate["evaluations"], "device_plan", after_seq=after_seq)
        if plan is None:
            raise MissionStateError(
                f"candidate {candidate_id} has no device_plan evaluation since its latest repair"
            )
        failing = _plan_is_failing(plan.get("result"))
        spent = int(candidate["repairs"]) >= max_repairs
        if not failing or not spent:
            raise MissionStateError(
                "NO_FEASIBLE_ARCHITECTURE requires every candidate's latest device_plan to be failing "
                f"with repairs spent ({candidate_id})"
            )
    if len(candidates) != int(budgets["max_candidates"]):
        raise MissionStateError("NO_FEASIBLE_ARCHITECTURE requires all budgeted candidate slots to be used")
    specs = [_canonical_json(_engineering_content(candidate["spec"])) for candidate in candidates.values()]
    if len(set(specs)) != len(specs):
        raise MissionStateError("NO_FEASIBLE_ARCHITECTURE requires pairwise distinct current candidate specs")
    inventory = replayed.get("inventory")
    if inventory is None:
        raise MissionStateError("NO_FEASIBLE_ARCHITECTURE requires an HS inventory_read event to check coverage")
    for candidate_id, candidate in candidates.items():
        uncovered = _uncovered_inventory(inventory["reading"], candidate["spec"])
        if uncovered:
            raise MissionStateError(f"NO_FEASIBLE_ARCHITECTURE is refused: candidate {candidate_id} does not contain "
                                    + ", ".join(uncovered) + " from the person's inventory")
    draft = inventory["draft"]
    if draft["ok"] and draft["plan_errors"] == 0 and draft["plan_warnings"] == 0:
        raise MissionStateError("NO_FEASIBLE_ARCHITECTURE is refused: HS's own draft of the inventory plans clean; "
                                "the agent should propose it")


def _part_data_grounding(replayed: Mapping[str, Any]) -> str:
    # Only HS's own reading of the person's list can show that part data is missing. A failing plan the agent cites
    # proves nothing: an agent can break its own wiring to get one.
    inventory = replayed.get("inventory")
    if inventory is not None:
        draft = inventory["draft"]
        if (inventory["reading"]["left_out"] or not draft["ok"]
                or draft["plan_errors"] + draft["plan_warnings"] > 0):
            return "hs_inventory_reading"
    raise MissionStateError("BLOCKED_NEEDS_PART_DATA is refused: HS has data for every part listed "
                            "and its own draft of them plans clean")


def _assert_budget_exhausted(replayed: Mapping[str, Any], budgets: Mapping[str, int]) -> None:
    used = int(replayed["operator_jobs_used"])
    maximum = int(budgets["max_operator_jobs"])
    if used < maximum:
        raise MissionStateError("BUDGET_EXHAUSTED requires the operator job budget to be spent")


def _validate_mission_record(
    value: Mapping[str, Any],
    *,
    project_id: str,
    mission_id: str,
) -> Dict[str, Any]:
    try:
        if value.get("schema_version") != MISSION_SCHEMA:
            raise MissionError("mission schema_version is missing or unsupported")
        stored_mission = value.get("mission_id")
        if not isinstance(stored_mission, str) or stored_mission != mission_id:
            raise MissionError("mission_id does not match the mission directory")
        stored_project = value.get("project_id")
        if not isinstance(stored_project, str) or stored_project != project_id:
            raise MissionError("project_id does not match the project directory")
        if type(value.get("revision")) is not int:
            raise MissionError("mission revision must be an integer")
        if not isinstance(value.get("intake"), Mapping):
            raise MissionError("mission intake must be an object")
        if not isinstance(value.get("budgets"), Mapping):
            raise MissionError("mission budgets must be an object")
        if not isinstance(value.get("created_at"), str):
            raise MissionError("mission created_at must be a string")
    except MissionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise MissionError("mission record is structurally corrupt") from exc
    return dict(value)


def _validate_event_record(value: Mapping[str, Any], *, sequence: int) -> Dict[str, Any]:
    try:
        seq = value.get("seq")
        if seq.__class__ is not int or seq != sequence:
            raise MissionError(f"event seq must equal file number {sequence}")
        if value.get("type") not in _EVENT_TYPES:
            raise MissionError("event type is missing or unsupported")
        author = value.get("author")
        if not isinstance(author, Mapping):
            raise MissionError("event author must be an object")
        if author.get("kind") not in _AUTHOR_KINDS:
            raise MissionError("event author.kind is missing or unsupported")
        author_id = author.get("id")
        if not isinstance(author_id, str) or not author_id:
            raise MissionError("event author.id must be a non-empty string")
        if not isinstance(value.get("created_at"), str):
            raise MissionError("event created_at must be a string")
    except MissionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise MissionError("event record is structurally corrupt") from exc
    return dict(value)


class MissionStore:
    """Store fabrication missions beside a project tree without touching authority."""

    def __init__(self, root: str | Path | ProjectStore | None = None) -> None:
        if isinstance(root, ProjectStore):
            self.project_store = root
        else:
            self.project_store = ProjectStore(root)
        self._mutation_local = threading.local()

    @contextmanager
    def mutation(self, project_id: str, mission_id: str) -> Iterator[None]:
        """Exclude competing writers/runs, including other processes, without blocking readers.

        The immutable mission marker supplies a stable lock inode. Conflicts are
        immediate (HTTP 409), rather than queuing another expensive operation.
        Re-entry on this store/thread lets an executor commit under its run lock.
        The OS releases the lock if a worker exits; this is not a durable run queue.
        """
        if fcntl is None:
            raise MissionError("mission mutations require POSIX advisory locking")
        marker = self._mission_dir(project_id, mission_id) / "mission.json"
        _reject_symlink(marker, label="mission.json")
        held = getattr(self._mutation_local, "held", set())
        if marker in held:
            yield
            return
        try:
            fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError as exc:
            raise MissionNotFound(mission_id) from exc
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MissionConflict("mission is busy; retry after the current operation finishes") from exc
            self._mutation_local.held = held
            held.add(marker)
            try:
                yield
            finally:
                held.remove(marker)
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _project_dir(self, project_id: str) -> Path:
        safe_id = validate_project_id(project_id)
        path = (self.project_store.root / safe_id).resolve()
        if path.parent != self.project_store.root:
            raise InvalidProjectId("project_id resolves outside project root")
        if not path.is_dir():
            raise ProjectNotFound(safe_id)
        return path

    def _assert_inside_project(self, path: Path, project_dir: Path, *, label: str) -> None:
        _reject_symlink(path, label=label)
        if path.exists() and not _path_inside(path, project_dir):
            raise MissionError(f"{label} resolves outside the project directory")

    def _assert_missions_tree_has_no_symlinks(self, missions_root: Path) -> None:
        _reject_symlink(missions_root, label="missions directory")
        if not missions_root.exists():
            return
        if not missions_root.is_dir():
            raise MissionError("missions path is not a directory")
        for mission_dir in missions_root.iterdir():
            _reject_symlink(mission_dir, label="mission directory")
            if not mission_dir.is_dir():
                continue
            _reject_symlink(mission_dir / "mission.json", label="mission.json")
            events_dir = mission_dir / "events"
            _reject_symlink(events_dir, label="events directory")
            if events_dir.is_dir():
                for event_path in events_dir.iterdir():
                    _reject_symlink(event_path, label="event file")
            runs_dir = mission_dir / "runs"
            _reject_symlink(runs_dir, label="runs directory")
            if runs_dir.is_dir():
                for run_path in runs_dir.iterdir():
                    _reject_symlink(run_path, label="run file")

    def _missions_root(self, project_id: str) -> Path:
        project_dir = self._project_dir(project_id)
        missions = project_dir / "missions"
        self._assert_inside_project(missions, project_dir, label="missions directory")
        if missions.exists():
            self._assert_missions_tree_has_no_symlinks(missions)
        return missions

    def _mission_dir(self, project_id: str, mission_id: str) -> Path:
        safe_mission = validate_project_id(mission_id)
        project_dir = self._project_dir(project_id)
        path = self._missions_root(project_id) / safe_mission
        self._assert_inside_project(path, project_dir, label="mission directory")
        return path

    def _events_dir(self, project_id: str, mission_id: str) -> Path:
        project_dir = self._project_dir(project_id)
        events_dir = self._mission_dir(project_id, mission_id) / "events"
        self._assert_inside_project(events_dir, project_dir, label="events directory")
        return events_dir

    def _event_path(self, project_id: str, mission_id: str, sequence: int) -> Path:
        path = self._events_dir(project_id, mission_id) / f"{int(sequence):08d}.json"
        _reject_symlink(path, label="event file")
        return path

    def _events(self, project_id: str, mission_id: str) -> list[Dict[str, Any]]:
        events_dir = self._events_dir(project_id, mission_id)
        if not events_dir.is_dir():
            return []
        events: list[Dict[str, Any]] = []
        file_seqs: list[int] = []
        for path in sorted(events_dir.glob("*.json")):
            _reject_symlink(path, label="event file")
            if not path.stem.isdigit():
                raise MissionError(f"event file name is not a sequence: {path.name}")
            sequence = int(path.stem)
            events.append(_validate_event_record(_read_json(path), sequence=sequence))
            file_seqs.append(sequence)
        if file_seqs != list(range(1, len(file_seqs) + 1)):
            raise MissionError("event sequence must be contiguous from 1")
        return events

    def _latest_revision(self, project_id: str) -> int:
        return int(self.project_store.load(project_id)["revision"])

    def _write_event(
        self,
        project_id: str,
        mission_id: str,
        sequence: int,
        record: Mapping[str, Any],
    ) -> Dict[str, Any]:
        payload = dict(record)
        payload["seq"] = int(sequence)
        payload["created_at"] = _utc_now()
        _atomic_create_json(self._event_path(project_id, mission_id, sequence), payload)
        return payload

    def _mission_view(
        self,
        project_id: str,
        mission_id: str,
        *,
        include_events: bool,
    ) -> Dict[str, Any]:
        mission_path = self._mission_dir(project_id, mission_id) / "mission.json"
        _reject_symlink(mission_path, label="mission.json")
        if not mission_path.is_file():
            raise MissionNotFound(mission_id)
        try:
            meta = _validate_mission_record(
                _read_json(mission_path),
                project_id=project_id,
                mission_id=mission_id,
            )
            events = self._events(project_id, mission_id)
            if not events or events[0].get("seq") != 1:
                raise MissionError("committed mission is missing event 1")
            replayed = _replay(events)
        except MissionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise MissionError(f"mission {mission_id!r} is structurally corrupt") from exc
        budgets = dict(meta["budgets"])
        budgets["repairs_used"] = dict(replayed["repairs_used"])
        budgets["operator_jobs_used"] = replayed["operator_jobs_used"]
        view = {
            "schema_version": meta["schema_version"],
            "mission_id": meta["mission_id"],
            "project_id": meta["project_id"],
            "revision": meta["revision"],
            "intake": dict(meta["intake"]),
            "budgets": budgets,
            "created_at": meta["created_at"],
            "phase": replayed["phase"],
            "accepted": replayed["accepted"],
            "inventory": replayed["inventory"],
            "candidates": [_public_candidate(item, replayed["inventory"]) for item in replayed["candidates"].values()],
            "terminal": replayed["terminal"],
            "last_event_seq": replayed["last_event_seq"],
            "physical_correctness": "UNPROVEN",
            "firmware_authorized": False,
            "power_on_authorized": False,
        }
        if include_events:
            view["events"] = events
        return view

    def open_mission(
        self,
        project_id: str,
        *,
        intake: Mapping[str, Any],
        author: Mapping[str, Any],
    ) -> Dict[str, Any]:
        normalized_intake, budgets = _normalize_intake(intake)
        normalized_author = _normalize_author(author)
        safe_id = validate_project_id(project_id)
        revision = self._latest_revision(safe_id)
        mission_id = f"mission-{uuid.uuid4().hex[:16]}"
        mission_dir = self._mission_dir(safe_id, mission_id)
        if mission_dir.exists():
            raise MissionConflict(f"mission already exists: {mission_id}")
        record = {
            "schema_version": MISSION_SCHEMA,
            "mission_id": mission_id,
            "project_id": safe_id,
            "revision": revision,
            "intake": normalized_intake,
            "budgets": budgets,
            "created_at": _utc_now(),
        }
        self._write_event(
            safe_id,
            mission_id,
            1,
            {"type": "opened", "author": normalized_author},
        )
        _atomic_write_json(mission_dir / "mission.json", record)
        return self.get_mission(safe_id, mission_id)

    def list_missions(self, project_id: str) -> list[Dict[str, Any]]:
        missions_root = self._missions_root(project_id)
        if not missions_root.is_dir():
            return []
        rows: list[Dict[str, Any]] = []
        for directory in missions_root.iterdir():
            _reject_symlink(directory, label="mission directory")
            if not directory.is_dir():
                continue
            mission_path = directory / "mission.json"
            _reject_symlink(mission_path, label="mission.json")
            if not mission_path.is_file():
                continue
            rows.append(self._mission_view(project_id, directory.name, include_events=False))
        rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return rows

    def get_mission(self, project_id: str, mission_id: str) -> Dict[str, Any]:
        return self._mission_view(project_id, mission_id, include_events=True)

    def _current(self, project_id: str, mission_id: str) -> tuple[Dict[str, Any], list[Dict[str, Any]], Dict[str, Any]]:
        view = self.get_mission(project_id, mission_id)
        events = list(view["events"])
        replayed = _replay(events)
        return view, events, replayed

    def _assert_not_terminal(self, replayed: Mapping[str, Any], mission_id: str) -> None:
        if replayed.get("phase") == "TERMINAL" or replayed.get("terminal") is not None:
            raise MissionStateError(f"mission {mission_id!r} is terminal and cannot accept new events")

    def _run_file_path(self, project_id: str, mission_id: str, filename: str) -> Path:
        project_dir = self._project_dir(project_id)
        mission_dir = self._mission_dir(project_id, mission_id)
        runs_dir = mission_dir / "runs"
        self._assert_inside_project(runs_dir, project_dir, label="runs directory")
        path = runs_dir / filename
        self._assert_inside_project(path, project_dir, label="run file")
        if path.exists() and not _path_inside(path, mission_dir):
            raise MissionError("run file resolves outside the mission directory")
        return path

    def _write_run_artifact(
        self,
        project_id: str,
        mission_id: str,
        sequence: int,
        operation: str,
        artifact: Mapping[str, Any],
    ) -> tuple[str, str]:
        payload = artifact if isinstance(artifact, dict) else dict(artifact)
        try:
            encoded = _json_payload(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise MissionValidationError("artifact must be JSON-serializable") from exc
        digest = hashlib.sha256(encoded).hexdigest()
        # Named by content, not by event number: a file left by an interrupted write is never in the way of the
        # next evaluation, and identical output is stored once.
        filename = f"{operation}-{digest[:16]}.json"
        path = self._run_file_path(project_id, mission_id, filename)
        if path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise MissionError(f"run file {filename} does not match its content hash")
        else:
            try:
                _atomic_create_json(path, payload)
            except MissionConflict:
                pass  # a concurrent writer stored the same bytes under the same content name
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise MissionError(f"run file {filename} does not match its content hash")
        return f"runs/{filename}", digest

    def read_run(self, project_id: str, mission_id: str, artifact: str) -> Dict[str, Any]:
        """Return a hashed run file this mission's own evaluations reference. Read-only."""

        if not isinstance(artifact, str) or _RUN_ARTIFACT_RE.fullmatch(artifact) is None:
            raise MissionValidationError("artifact must be a runs/<name>.json path")
        view = self.get_mission(project_id, mission_id)
        recorded = None
        for candidate in view.get("candidates") or []:
            for evaluation in candidate.get("evaluations") or []:
                if evaluation.get("artifact") == artifact:
                    recorded = evaluation
                    break
            if recorded is not None:
                break
        if recorded is None:
            raise MissionError(f"run artifact {artifact!r} is not referenced by this mission's evaluations")
        filename = artifact.split("/", 1)[1]
        path = self._run_file_path(project_id, mission_id, filename)
        if not path.is_file():
            raise MissionError(f"run file {artifact} is missing")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = (recorded.get("result") or {}).get("result_sha256")
        if not isinstance(expected, str) or digest.lower() != expected.lower():
            raise MissionError(f"run file {artifact} does not match its recorded result_sha256")
        return _read_json(path)

    @_serialized_mutation
    def accept_mission(
        self,
        project_id: str,
        mission_id: str,
        *,
        author: Mapping[str, Any],
    ) -> Dict[str, Any]:
        normalized_author = _normalize_author(author, allow_system=True)
        if normalized_author["kind"] != "human":
            raise MissionValidationError("only a person can accept a mission and its budgets")
        view, _events, replayed = self._current(project_id, mission_id)
        self._assert_not_terminal(replayed, mission_id)
        if replayed.get("accepted") is not None:
            raise MissionStateError("mission is already accepted")
        budgets = dict(view["budgets"])
        budgets["repairs_used"] = dict(budgets.get("repairs_used") or {})
        last_seq = int(replayed["last_event_seq"])
        # Inventory has no authority effect. Persist it BEFORE acceptance so an
        # interrupted write cannot enable runs without their frozen grounding.
        # A retry after that first write reuses the reading, not a newer parser.
        if replayed.get("inventory") is None:
            inventory = _read_inventory(view["intake"]["inventory"])
            self._write_event(
                project_id, mission_id, last_seq + 1,
                {"type": "inventory_read", "author": dict(_SYSTEM_AUTHOR), **inventory},
            )
            last_seq += 1
        self._write_event(
            project_id, mission_id, last_seq + 1,
            {"type": "accepted", "author": normalized_author, "budgets": budgets},
        )
        return self.get_mission(project_id, mission_id)

    @_serialized_mutation
    def propose(
        self,
        project_id: str,
        mission_id: str,
        event: Mapping[str, Any],
        *,
        author: Mapping[str, Any],
        expected_event_seq: int | None = None,
    ) -> Dict[str, Any]:
        raw_event = _require_mapping(event, label="event")
        _reject_authority(raw_event, label="event")
        normalized_author = _normalize_author(author)
        view, events, replayed = self._current(project_id, mission_id)
        last_seq = int(replayed["last_event_seq"])
        if expected_event_seq is not None:
            if expected_event_seq.__class__ is not int:
                raise MissionValidationError("expected_event_seq must be an integer")
            if expected_event_seq != last_seq:
                raise MissionConflict(
                    f"mission {mission_id!r} is at event {last_seq}, expected {expected_event_seq}"
                )
        self._assert_not_terminal(replayed, mission_id)
        event_type = raw_event.get("type")
        if not isinstance(event_type, str) or event_type not in _PROPOSE_TYPES:
            raise MissionValidationError(
                "event type must be 'candidate_proposed', 'repair_proposed', "
                "'evidence_required', or 'terminal_proposed'"
            )
        budgets = view["budgets"]
        record: Dict[str, Any] = {"type": event_type, "author": normalized_author}
        if event_type == "candidate_proposed":
            candidate = _normalize_candidate(raw_event.get("candidate"))
            if candidate["id"] in replayed["candidates"]:
                raise MissionValidationError(f"candidate {candidate['id']!r} already exists")
            if len(replayed["candidates"]) >= int(budgets["max_candidates"]):
                raise MissionStateError("candidate budget is exhausted; no more candidates may be proposed")
            record["candidate"] = candidate
        elif event_type == "repair_proposed":
            candidate_id = _normalize_slug(raw_event.get("candidate_id"), field="candidate_id")
            candidate = replayed["candidates"].get(candidate_id)
            if candidate is None:
                raise MissionValidationError(f"candidate {candidate_id!r} does not exist")
            # Only a verdict on the current spec counts: a repair is not stacked on a failure of the spec it replaced.
            plan = _latest_operation(candidate["evaluations"], "device_plan", after_seq=_since_seq(candidate))
            if plan is None or not _plan_is_failing(plan.get("result")):
                raise MissionStateError("repair_proposed requires a failing device_plan evaluation of the current spec")
            if int(candidate["repairs"]) >= int(budgets["max_repairs_per_candidate"]):
                raise MissionStateError("repair budget for this candidate is spent")
            record["candidate_id"] = candidate_id
            record["spec"] = _normalize_spec(raw_event.get("spec"), field="spec")
            inventory = replayed.get("inventory")
            if inventory is not None:
                # Compare lines, not counts: a repair may not cover one listed part by dropping another.
                dropped = (Counter(_uncovered_inventory(inventory["reading"], record["spec"]))
                           - Counter(_uncovered_inventory(inventory["reading"], candidate["spec"])))
                if dropped:
                    raise MissionStateError("repair_proposed is refused: the repair drops inventory: "
                                            + ", ".join(dropped.elements()))
            record["rationale"] = _require_text(
                raw_event.get("rationale"), field="rationale", max_len=_MAX_RATIONALE
            )
        elif event_type == "evidence_required":
            blocker = raw_event.get("blocker")
            if blocker not in _BLOCKED_STATES:
                raise MissionValidationError("blocker must be a BLOCKED_* terminal state")
            if "candidate_id" in raw_event and raw_event.get("candidate_id") is not None:
                candidate_id = _normalize_slug(raw_event.get("candidate_id"), field="candidate_id")
                if candidate_id not in replayed["candidates"]:
                    raise MissionValidationError(f"candidate {candidate_id!r} does not exist")
                record["candidate_id"] = candidate_id
            record["blocker"] = blocker
            record["need"] = _require_text(raw_event.get("need"), field="need", max_len=_MAX_NEED)
        else:
            state = raw_event.get("state")
            if state not in TERMINAL_STATES:
                raise MissionValidationError("terminal state is not in the documented set")
            record["state"] = state
            record["reason"] = _require_text(raw_event.get("reason"), field="reason", max_len=_MAX_REASON)
            if "candidate_id" in raw_event and raw_event.get("candidate_id") is not None:
                candidate_id = _normalize_slug(raw_event.get("candidate_id"), field="candidate_id")
                if candidate_id not in replayed["candidates"]:
                    raise MissionValidationError(f"candidate {candidate_id!r} does not exist")
                record["candidate_id"] = candidate_id
            if state == "READY_FOR_HUMAN_BUILD":
                _assert_ready_for_human_build(replayed, raw_event, events)
                record["grounding"] = "hs_evaluation"
            elif state in _BLOCKED_STATES:
                _assert_no_ready_candidate(replayed, events, state)
                record["cites"] = _assert_blocked_cites(events, raw_event)
                record["grounding"] = (_part_data_grounding(replayed)
                                       if state == "BLOCKED_NEEDS_PART_DATA" else "agent_assertion")
            elif state == "NO_FEASIBLE_ARCHITECTURE":
                _assert_no_feasible_architecture(replayed, budgets)
                _assert_no_ready_candidate(replayed, events, state)
                record["grounding"] = "hs_evaluation"
            elif state == "BUDGET_EXHAUSTED":
                _assert_budget_exhausted(replayed, budgets)
                _assert_no_ready_candidate(replayed, events, state)
                record["grounding"] = "hs_budget"
            if "cites" in raw_event and "cites" not in record:
                cites = raw_event.get("cites")
                if cites is None:
                    record["cites"] = []
                elif isinstance(cites, list):
                    record["cites"] = [_require_int(item, field="cites item", min_value=1) for item in cites]
                else:
                    raise MissionValidationError("cites must be a list of event sequence numbers")
        self._write_event(project_id, mission_id, last_seq + 1, record)
        return self.get_mission(project_id, mission_id)

    @_serialized_mutation
    def record_evaluation(
        self,
        project_id: str,
        mission_id: str,
        *,
        candidate_id: str,
        operation: str,
        result: Mapping[str, Any],
        artifact: Mapping | None = None,
    ) -> Dict[str, Any]:
        _view, _events, replayed = self._current(project_id, mission_id)
        if replayed.get("accepted") is None:
            raise MissionStateError("mission has not been accepted")
        self._assert_not_terminal(replayed, mission_id)
        budgets = _view["budgets"]
        if int(replayed["operator_jobs_used"]) >= int(budgets["max_operator_jobs"]):
            raise MissionStateError("operator job budget is exhausted")
        safe_candidate = _normalize_slug(candidate_id, field="candidate_id")
        if safe_candidate not in replayed["candidates"]:
            raise MissionValidationError(f"candidate {safe_candidate!r} does not exist")
        if not isinstance(operation, str) or operation not in _EVAL_OPERATIONS:
            raise MissionValidationError(
                "operation must be one of device_draft, device_plan, device_engineering, "
                "device_case, device_application, device_application_run, device_reclaim_match"
            )
        last_seq = int(replayed["last_event_seq"])
        next_seq = last_seq + 1
        sha_override = None
        artifact_path = None
        if artifact is not None:
            # Validate everything before anything is written, so a refused result leaves no file behind.
            raw_artifact = _require_mapping(artifact, label="artifact")
            _normalize_result(result, result_sha256="0" * 64)
            artifact_path, sha_override = self._write_run_artifact(
                project_id, mission_id, next_seq, operation, raw_artifact
            )
        normalized_result = _normalize_result(result, result_sha256=sha_override)
        record: Dict[str, Any] = {
            "type": "evaluation_recorded",
            "author": dict(_SYSTEM_AUTHOR),
            "candidate_id": safe_candidate,
            "operation": operation,
            "result": normalized_result,
        }
        if artifact_path is not None:
            record["artifact"] = artifact_path
        self._write_event(project_id, mission_id, next_seq, record)
        return self.get_mission(project_id, mission_id)
