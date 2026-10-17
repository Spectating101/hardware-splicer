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
from .device_plan import _OVERRIDE_KEYS, DevicePlanError, _module, _validate_spec, build_device_plan
from pydantic import ValidationError

from .physical_evidence_ledger import (PhysicalEvidenceEnvelope, physical_evidence_envelope_hash,
                                       validate_physical_evidence_envelope)
from .mission_donors import (normalize_donors, normalize_used, normalize_finding, read_donors,
                             donor_problem, donor_grounding)
from .donor_device_plan import mission_donor_modules
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
    {"candidate_proposed", "repair_proposed", "evidence_required", "terminal_proposed", "finding_offered"}
)
_EVENT_TYPES = _PROPOSE_TYPES | {"opened", "evaluation_recorded", "accepted", "inventory_read", "donor_read", "design_staged", "evidence_supplied"}
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
_INTAKE_KEYS = frozenset({"goal", "constraints", "inventory", "budgets", "measurements", "requirements", "donors"})
# Spec values a person can require, and where the planner's validated spec holds each one with its default applied.
_REQUIREMENT_PATHS = {
    "case.wall_mm": ("wall", (int, float)),
    "case.clearance_mm": ("clearance", (int, float)),
    "case.antenna_clearance": ("antenna_clearance", bool),
    "case.board_stops": ("board_stops", bool),
    "power.source": ("power.source", str),
}
_MAX_REQUIREMENTS = 10
# What a person can be asked to measure, and the physical-evidence record kind that must carry the answer.
_REQUEST_KINDS = {
    "dimensional": "dimensional_measurement",
    "electrical": "electrical_measurement",
    "continuity": "electrical_measurement",
    "boot_log": "inspection",
}
_REQUEST_KEYS = frozenset({"kind", "target", "quantity", "expected", "instructions", "signal"})
_DIMENSIONAL_QUANTITIES = frozenset({"pcb_mm.x", "pcb_mm.y", "pcb_mm.z", "above_board_mm"})
_MAX_LOG_BYTES = 64 * 1024
_MAX_READINGS = 10
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


def _donor_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (ValueError, TypeError, KeyError) as exc:
        raise MissionValidationError(str(exc)) from exc


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
    normalized = {"goal": goal, "constraints": constraints, "inventory": inventory}
    if raw.get("measurements") is not None:
        normalized["measurements"] = _normalize_measurements(raw["measurements"])
    if raw.get("requirements") is not None:
        normalized["requirements"] = _normalize_requirements(raw["requirements"])
    if "donors" in raw:
        normalized["donors"] = _donor_call(normalize_donors, raw["donors"])
    return normalized, budgets


def _normalize_measurements(value: Any) -> Dict[str, Any]:
    """The person's measured sizes, per library module. Validated as the planner validates spec overrides."""
    raw = _require_mapping(value, label="measurements")
    measured: Dict[str, Any] = {}
    for module_id, sizes in raw.items():
        try:
            _module(str(module_id))
        except DevicePlanError as exc:
            raise MissionValidationError(f"measurements: {exc}") from exc
        sizes = _require_mapping(sizes, label=f"measurements.{module_id}")
        if not sizes or not set(sizes) <= set(_OVERRIDE_KEYS):
            raise MissionValidationError(f"measurements.{module_id} may hold {', '.join(sorted(_OVERRIDE_KEYS))}")
        probe = {"modules": [{"id": "m", "module": module_id, "overrides": dict(sizes)}]}
        try:
            _validate_spec(probe)
        except DevicePlanError as exc:
            raise MissionValidationError(f"measurements.{module_id}: {exc}") from exc
        measured[str(module_id)] = json.loads(json.dumps(sizes))
    return measured


def _normalize_requirements(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list) or len(value) > _MAX_REQUIREMENTS:
        raise MissionValidationError(f"requirements must be a list of at most {_MAX_REQUIREMENTS}")
    rows = []
    for index, item in enumerate(value):
        row = _require_mapping(item, label=f"requirements[{index}]")
        if set(row) != {"path", "equals"}:
            raise MissionValidationError(f"requirements[{index}] must hold exactly path and equals")
        path, equals = row["path"], row["equals"]
        if path not in _REQUIREMENT_PATHS:
            raise MissionValidationError(f"requirements[{index}].path must be one of {', '.join(sorted(_REQUIREMENT_PATHS))}")
        kind = _REQUIREMENT_PATHS[path][1]
        if (kind is not bool and isinstance(equals, bool)) or not isinstance(equals, kind):
            raise MissionValidationError(f"requirements[{index}].equals has the wrong type for {path}")
        if isinstance(equals, float) and equals != equals:
            raise MissionValidationError(f"requirements[{index}].equals must be finite")
        rows.append({"path": path, "equals": equals})
    return rows


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or value in (float("inf"), float("-inf")):
        raise MissionValidationError(f"{field} must be a finite number")
    return float(value)


def _normalize_request(value: Any) -> Dict[str, Any]:
    """What the agent asks a person to measure. HS validates the shape; the person decides whether to answer."""
    raw = _require_mapping(value, label="request")
    extra = set(raw) - _REQUEST_KEYS
    if extra:
        raise MissionValidationError(f"request contains unknown fields: {sorted(extra)}")
    kind = raw.get("kind")
    if kind not in _REQUEST_KINDS:
        raise MissionValidationError(f"request.kind must be one of {', '.join(sorted(_REQUEST_KINDS))}")
    request: Dict[str, Any] = {
        "kind": kind,
        "target": _require_text(raw.get("target"), field="request.target", max_len=200),
        "instructions": _require_text(raw.get("instructions"), field="request.instructions", max_len=_MAX_NEED),
    }
    if raw.get("signal") is not None:
        if not request["target"].startswith("donor:") or kind not in {"electrical", "continuity"}:
            raise MissionValidationError("request.signal requires an electrical/continuity donor target")
        request["signal"] = _require_text(raw["signal"], field="request.signal", max_len=120)
    quantity = raw.get("quantity")
    if kind == "dimensional":
        try:
            _module(request["target"])
        except DevicePlanError as exc:
            raise MissionValidationError(f"a dimensional request's target must be a library module id: {exc}") from exc
        if quantity not in _DIMENSIONAL_QUANTITIES:
            raise MissionValidationError(f"a dimensional request's quantity must be one of {', '.join(sorted(_DIMENSIONAL_QUANTITIES))}")
    if kind in {"dimensional", "electrical", "continuity"}:
        request["quantity"] = _normalize_slug(quantity, field="request.quantity") if kind != "dimensional" else quantity
    elif quantity is not None:
        raise MissionValidationError("a boot_log request has no quantity")
    expected = raw.get("expected")
    if expected is not None:
        expected = _require_mapping(expected, label="request.expected")
        if set(expected) != {"min", "max", "unit"}:
            raise MissionValidationError("request.expected must hold exactly min, max and unit")
        low = _finite(expected["min"], field="request.expected.min")
        high = _finite(expected["max"], field="request.expected.max")
        if low > high:
            raise MissionValidationError("request.expected.min must not exceed max")
        request["expected"] = {"min": low, "max": high,
                               "unit": _require_text(expected["unit"], field="request.expected.unit", max_len=10)}
    return request


def _normalize_readings(request: Mapping[str, Any], values: Any) -> Any:
    if request["kind"] == "boot_log":
        raw = _require_mapping(values, label="values")
        if set(raw) != {"log"} or not isinstance(raw["log"], str):
            raise MissionValidationError("a boot log answer is {\"log\": \"<text>\"}")
        if len(raw["log"].encode("utf-8")) > _MAX_LOG_BYTES:
            raise MissionValidationError("a boot log may be at most 64 KB")
        return {"log": raw["log"]}
    if not isinstance(values, list) or not 1 <= len(values) <= _MAX_READINGS:
        raise MissionValidationError(f"values must be a list of 1 to {_MAX_READINGS} readings")
    readings = []
    for index, item in enumerate(values):
        row = _require_mapping(item, label=f"values[{index}]")
        if set(row) != {"quantity", "value", "unit"}:
            raise MissionValidationError(f"values[{index}] must hold exactly quantity, value and unit")
        if row["quantity"] != request.get("quantity"):
            raise MissionValidationError(f"values[{index}].quantity must be {request.get('quantity')!r}, as the need asked")
        readings.append({"quantity": row["quantity"], "value": _finite(row["value"], field=f"values[{index}].value"),
                         "unit": _require_text(row["unit"], field=f"values[{index}].unit", max_len=10)})
    return readings


def _compare(request: Mapping[str, Any], readings: Any) -> str:
    expected = request.get("expected")
    if not expected or not isinstance(readings, list):
        return "not_comparable"
    if any(row["unit"] != expected["unit"] for row in readings):
        return "not_comparable"
    inside = all(expected["min"] <= row["value"] <= expected["max"] for row in readings)
    return "within" if inside else "outside"


def _dimensional_override(request: Mapping[str, Any], readings: list[Mapping[str, Any]]) -> Dict[str, Any]:
    value = readings[-1]["value"]
    quantity = request["quantity"]
    if quantity.startswith("pcb_mm."):
        return {"pcb_mm": {quantity.split(".", 1)[1]: value}}
    return {quantity: value}


def _merge_measurements(base: Mapping[str, Any], extra: Mapping[str, Any]) -> Dict[str, Any]:
    merged = json.loads(json.dumps(dict(base)))
    for module_id, sizes in extra.items():
        entry = merged.setdefault(module_id, {})
        for key, value in sizes.items():
            if isinstance(value, Mapping):
                entry.setdefault(key, {}).update(value)
            else:
                entry[key] = value
    return merged


def _person_measurements(intake: Mapping[str, Any], replayed: Mapping[str, Any]) -> Dict[str, Any]:
    return _merge_measurements(intake.get("measurements") or {}, replayed.get("supplied_measurements") or {})


def _violated_requirements(requirements: list[Mapping[str, Any]], spec: Mapping[str, Any], donors=None) -> list[str]:
    """Requirements the spec breaks, read from the planner's own validated spec so absent keys take its defaults."""
    if not requirements:
        return []
    try:
        context = mission_donor_modules({"donors": donors or []}, spec)
        clean = _validate_spec(json.loads(json.dumps(spec)), donor_modules=context)
    except DevicePlanError:
        return [f"{row['path']} (the spec does not validate)" for row in requirements]
    broken = []
    for row in requirements:
        value: Any = clean
        for key in _REQUIREMENT_PATHS[row["path"]][0].split("."):
            value = value.get(key) if isinstance(value, Mapping) else None
        if value != row["equals"] or isinstance(value, bool) != isinstance(row["equals"], bool):
            broken.append(f"{row['path']} must be {json.dumps(row['equals'])}")
    return broken


def _assert_measurements_are_the_persons(measured: Mapping[str, Any], spec: Mapping[str, Any], *, field: str) -> None:
    """Measured sizes are physical evidence. An agent cannot have measured anything; only the person can say, in the
    intake or by answering a measurement need."""
    modules = spec.get("modules")
    for index, row in enumerate(modules if isinstance(modules, list) else []):
        if not isinstance(row, Mapping) or not row.get("overrides"):
            continue
        if row["overrides"] != measured.get(row.get("module")):
            raise MissionValidationError(
                f"{field}.modules[{index}].overrides are refused: measured sizes are physical evidence that only the "
                "person supplies, in the mission intake's measurements or by answering a measurement need")


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


def _native_donors(spec: Mapping[str, Any]) -> list[str]:
    modules = spec.get("modules")
    return [m["module"] for m in (modules if isinstance(modules, list) else []) if isinstance(m, Mapping)
            and isinstance(m.get("module"), str) and m["module"].startswith("donor:")]


def _assert_native_references(spec, references):
    native = _native_donors(spec)
    normalized = _donor_call(normalize_used, native, references)
    if len(native) != len(normalized):
        raise MissionValidationError("a physical donor block may not be placed more than once")
    if native and set(normalized) != set(spec.get("donors_used") or []):
        raise MissionValidationError("wired donor modules must cover exactly donors_used")


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
    if "donors_used" in content:
        content["donors_used"] = _donor_call(normalize_used, content["donors_used"])
        if not content["donors_used"]:
            content.pop("donors_used")
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
                     "plan_warnings": sum(item.get("severity") == "warning" for item in findings),
                     "plan_unrepairable": sum(item.get("severity") in {"error", "warning"} and not item.get("suggestions")
                                              for item in findings)}
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


def _public_candidate(state: Mapping[str, Any], inventory: Mapping[str, Any] | None,
                      requirements: list[Mapping[str, Any]], donors=None) -> Dict[str, Any]:
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
        "violated_requirements": _violated_requirements(requirements, state["spec"], donors),
        "evaluations": [
            {
                "seq": item["seq"],
                "operation": item["operation"],
                "result": item["result"],
                "artifact": item.get("artifact"),
            }
            for item in state["evaluations"]
        ],
    }


def _replay(events: list[Mapping[str, Any]], intake: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    phase = "INTAKE"
    candidates: Dict[str, Dict[str, Any]] = {}
    terminal: Dict[str, Any] | None = None
    accepted: Dict[str, Any] | None = None
    inventory: Dict[str, Any] | None = None
    donors: list[Dict[str, Any]] = []
    donor_read = False
    staged: Dict[str, Any] | None = None
    needs: Dict[int, Dict[str, Any]] = {}
    supplied_measurements: Dict[str, Any] = {}
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
                "last_evidence_seq": None,
            }
            phase = "ARCHITECTING"
        elif event_type == "inventory_read":
            inventory = {key: event[key] for key in ("reading", "draft", "result_sha256")}
        elif event_type == "donor_read":
            donor_read = True
            donors = [{**d, "findings": [], "person_measurements": []} for d in event["donors"]]
        elif event_type == "finding_offered":
            for donor in donors:
                if donor["donor_id"] == event["finding"]["donor_id"]:
                    donor["findings"].append({**event["finding"], "seq": seq, "author": event["author"]})
        elif event_type == "design_staged":
            # Delivery after READY: it opens a review and changes neither the phase nor the verdict.
            staged = {"review_id": event["review_id"], "package_sha256": event["package_sha256"], "seq": seq}
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
            needs[seq] = {"seq": seq, "blocker": event["blocker"], "need": event["need"],
                          "candidate_id": event.get("candidate_id"), "request": event.get("request"),
                          "need_state": "open", "answered_by": None}
            needs[seq]["cites"] = list(event.get("cites") or [])
            phase = "EVIDENCE_REQUIRED"
        elif event_type == "evidence_supplied":
            need = needs[int(event["need_seq"])]
            need["need_state"] = "contradicted" if event["comparison"] == "outside" else "resolved"
            need["answered_by"] = seq
            # A new physical fact invalidates checks that came before it, as a repair does.
            for candidate_id, state in candidates.items():
                if need["candidate_id"] in (None, candidate_id):
                    state["last_evidence_seq"] = seq
            override = event.get("override")
            if override:
                supplied_measurements = _merge_measurements(supplied_measurements, override)
            request = need.get("request") or {}
            if request.get("kind") == "electrical" and request.get("signal"):
                for donor in donors:
                    if donor["donor_id"] == request.get("target"):
                        donor["person_measurements"].append({"signal": request["signal"], "values": event["values"],
                            "evidence_id": event["evidence_id"], "envelope_hash": event["envelope_hash"],
                            "seq": seq, "grade": "person_measurement", "comparison": event["comparison"]})
            standing = any(item["need_state"] != "resolved" for item in needs.values())
            phase = "EVIDENCE_REQUIRED" if standing else "EVALUATING"
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
        "donors": donors,
        "donor_read": donor_read,
        "donor_references": list((intake or {}).get("donors") or []),
        "candidates": candidates,
        "repairs_used": repairs_used,
        "operator_jobs_used": operator_jobs_used,
        "terminal": terminal,
        "accepted": accepted,
        "staged": staged,
        "needs": list(needs.values()),
        "supplied_measurements": supplied_measurements,
        "requirements": list((intake or {}).get("requirements") or []),
        "last_event_seq": last_event_seq,
        "last_event_at": events[-1]["created_at"] if events else "",
    }


def _since_seq(candidate: Mapping[str, Any]) -> int:
    """Checks count only after the candidate's latest repair and the latest physical fact that concerns it."""
    last_repair = candidate.get("last_repair_seq")
    base = int(last_repair) if last_repair is not None else int(candidate.get("proposal_seq") or 0)
    return max(base, int(candidate.get("last_evidence_seq") or 0))


def _resolved_needs(events: list[Mapping[str, Any]]) -> set[int]:
    return {int(item["need_seq"]) for item in events
            if item.get("type") == "evidence_supplied" and item.get("comparison") != "outside"}


def _open_evidence_need_blocks(events: list[Mapping[str, Any]], candidate_id: str) -> bool:
    resolved = _resolved_needs(events)
    for item in events:
        if item.get("type") != "evidence_required" or int(item["seq"]) in resolved:
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
    problem = donor_problem(replayed, candidate["spec"], ready=True)
    if problem:
        return "READY_FOR_HUMAN_BUILD is refused: " + problem
    try:
        mission_donor_modules(replayed, candidate["spec"])
    except DevicePlanError as exc:
        return "READY_FOR_HUMAN_BUILD is refused: " + str(exc)
    inventory = replayed.get("inventory")
    if inventory is None:
        return "READY_FOR_HUMAN_BUILD requires an HS inventory_read event"
    uncovered = _uncovered_inventory(inventory["reading"], candidate["spec"])
    if uncovered:
        return ("READY_FOR_HUMAN_BUILD is refused: the candidate does not contain "
                + ", ".join(uncovered) + " from the person's inventory")
    broken = _violated_requirements(replayed.get("requirements") or [], candidate["spec"], replayed.get("donors"))
    if broken:
        return "READY_FOR_HUMAN_BUILD is refused: the candidate breaks the person's requirements: " + "; ".join(broken)
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
    resolved = _resolved_needs(events)
    target = event.get("candidate_id")
    matched = False
    for item in cites:
        seq = _require_int(item, field="cites item", min_value=1)
        named = by_seq.get(seq)
        if named is None or named.get("type") not in {"evidence_required", "evaluation_recorded"}:
            raise MissionStateError(f"{state} may cite only existing evidence_required or evaluation_recorded events ({seq})")
        if seq in resolved:
            raise MissionStateError(f"{state} may not cite need {seq}: a person's evidence resolved it")
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
        donor_error = donor_problem(replayed, candidate["spec"], ready=False)
        if donor_error:
            raise MissionStateError(f"NO_FEASIBLE_ARCHITECTURE is refused: candidate {candidate_id}: {donor_error}")
        broken = _violated_requirements(replayed.get("requirements") or [], candidate["spec"], replayed.get("donors"))
        if broken:
            # A design that ignores what the person required says nothing about whether their device is feasible.
            raise MissionStateError(f"NO_FEASIBLE_ARCHITECTURE is refused: candidate {candidate_id} breaks the "
                                    "person's requirements: " + "; ".join(broken))
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
                or draft.get("plan_unrepairable", draft["plan_errors"] + draft["plan_warnings"]) > 0):
            return "hs_inventory_reading"
    raise MissionStateError("BLOCKED_NEEDS_PART_DATA is refused: HS has data for every part listed "
                            "and its own draft of them plans clean or has only repairable findings")


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
            replayed = _replay(events, meta["intake"])
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
            "donors": replayed["donors"],
            "candidates": [_public_candidate(item, replayed["inventory"], replayed["requirements"], replayed["donors"])
                           for item in replayed["candidates"].values()],
            "terminal": replayed["terminal"],
            "staged": replayed["staged"],
            "needs": replayed["needs"],
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
        replayed = _replay(events, view["intake"])
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

        return json.loads(self.read_run_bytes(project_id, mission_id, artifact).decode("utf-8"))

    def read_run_bytes(self, project_id: str, mission_id: str, artifact: str) -> bytes:
        """The exact stored bytes of a run file, whose sha256 is the evaluation's recorded result_sha256."""

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
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        expected = (recorded.get("result") or {}).get("result_sha256")
        if not isinstance(expected, str) or digest.lower() != expected.lower():
            raise MissionError(f"run file {artifact} does not match its recorded result_sha256")
        return data

    def _package_path(self, project_id: str, mission_id: str, package_sha256: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", package_sha256 or ""):
            raise MissionValidationError("package_sha256 must be 64 lowercase hex characters")
        project_dir = self._project_dir(project_id)
        mission_dir = self._mission_dir(project_id, mission_id)
        path = mission_dir / "packages" / f"{package_sha256[:16]}.zip"
        self._assert_inside_project(path, project_dir, label="package file")
        _reject_symlink(path, label="package file")
        return path

    def store_package(self, project_id: str, mission_id: str, data: bytes) -> str:
        """Keep a delivery package by its content hash. Writing the same bytes again is a no-op."""

        digest = hashlib.sha256(data).hexdigest()
        path = self._package_path(project_id, mission_id, digest)
        if path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise MissionError(f"package {path.name} does not match its content hash")
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
        return digest

    def read_package(self, project_id: str, mission_id: str, package_sha256: str) -> bytes | None:
        path = self._package_path(project_id, mission_id, package_sha256)
        if not path.is_file():
            return None
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != package_sha256:
            raise MissionError(f"package {path.name} does not match its content hash")
        return data

    def _envelope_used(self, project_id: str, envelope_hash: str) -> bool:
        root = self._missions_root(project_id)
        if not root.is_dir():
            return False
        for mission_dir in sorted(root.iterdir()):
            if not (mission_dir / "mission.json").is_file():
                continue
            for event in self._events(project_id, mission_dir.name):
                if event.get("type") == "evidence_supplied" and event.get("envelope_hash") == envelope_hash:
                    return True
        return False

    @_serialized_mutation
    def supply_evidence(
        self,
        project_id: str,
        mission_id: str,
        need_seq: int,
        *,
        envelope: Mapping[str, Any],
        values: Any,
        author: Mapping[str, Any],
        expected_event_seq: int | None = None,
    ) -> Dict[str, Any]:
        """A person answers an evidence need with a physical-evidence envelope bound to this mission and need.

        HS checks the envelope's hash and binding and compares numbers with the requested range. It grants nothing:
        the mission stays UNPROVEN and no flashing or power-on is authorized by an answer.
        """

        person = _normalize_author(author)
        if person["kind"] != "human":
            raise MissionValidationError("only a person can supply physical evidence")
        view, events, replayed = self._current(project_id, mission_id)
        last_seq = int(replayed["last_event_seq"])
        if expected_event_seq is not None and (expected_event_seq.__class__ is not int or expected_event_seq != last_seq):
            raise MissionConflict(f"mission {mission_id!r} is at event {last_seq}, expected {expected_event_seq}")
        self._assert_not_terminal(replayed, mission_id)
        need = next((item for item in replayed["needs"] if item["seq"] == need_seq), None)
        if need is None:
            raise MissionValidationError(f"event {need_seq} is not an evidence need of this mission")
        request = need.get("request")
        if not request:
            raise MissionStateError(f"need {need_seq} has no structured request a person can answer")
        if need["need_state"] == "resolved":
            raise MissionStateError(f"need {need_seq} is already resolved")
        readings = _normalize_readings(request, values)
        try:
            parsed = PhysicalEvidenceEnvelope.model_validate(dict(_require_mapping(envelope, label="envelope")))
        except ValidationError as exc:
            raise MissionValidationError(f"envelope is not a valid physical-evidence envelope: {exc.errors()[0]['msg']}") from exc
        recomputed = physical_evidence_envelope_hash(
            envelope_id=parsed.envelope_id, record=parsed.record, raw_files=parsed.raw_files,
            created_at=parsed.created_at, created_by=parsed.created_by, metadata=parsed.metadata,
        )
        if recomputed != parsed.envelope_hash:
            raise MissionValidationError("envelope_hash does not match the envelope's contents")
        if self._envelope_used(project_id, parsed.envelope_hash):
            raise MissionValidationError("this envelope was already used in this project")
        binding = parsed.metadata.get("mission")
        expected_binding = {"project_id": project_id, "mission_id": mission_id, "need_seq": need_seq, "values": readings}
        if not isinstance(binding, Mapping) or json.loads(json.dumps(dict(binding))) != json.loads(json.dumps(expected_binding)):
            raise MissionValidationError(
                "the envelope must be bound to this project, mission and need, and carry the same values, in metadata.mission")
        if parsed.record.project_id != project_id:
            raise MissionValidationError("the envelope's record belongs to another project")
        if parsed.record.kind.value != _REQUEST_KINDS[request["kind"]]:
            raise MissionValidationError(f"a {request['kind']} need is answered by a {_REQUEST_KINDS[request['kind']]} record")
        if request["target"].startswith("donor:"):
            if (request["target"] not in parsed.record.target_ids or parsed.record.metadata.get("simulated")
                    or validate_physical_evidence_envelope(parsed)):
                raise MissionValidationError("donor evidence requires a matching target and a valid nonsimulated envelope")
        record: Dict[str, Any] = {
            "type": "evidence_supplied",
            "author": person,
            "need_seq": need_seq,
            "envelope_id": parsed.envelope_id,
            "envelope_hash": parsed.envelope_hash,
            "evidence_id": parsed.record.evidence_id,
            "values": readings,
            "comparison": _compare(request, readings),
        }
        if request["kind"] == "dimensional":
            override = {request["target"]: _dimensional_override(request, readings)}
            intake_sizes = (view["intake"].get("measurements") or {}).get(request["target"]) or {}
            for key, value in override[request["target"]].items():
                known = intake_sizes.get(key)
                clash = (isinstance(value, Mapping) and isinstance(known, Mapping)
                         and any(k in known and known[k] != v for k, v in value.items())) or (
                    not isinstance(value, Mapping) and known is not None and known != value)
                if clash:
                    raise MissionValidationError(f"this measurement contradicts the intake measurement of {request['target']} {key}")
            record["override"] = override
        self._write_event(project_id, mission_id, last_seq + 1, record)
        return self.get_mission(project_id, mission_id)

    @_serialized_mutation
    def record_design_staged(
        self, project_id: str, mission_id: str, *, review_id: str, package_sha256: str
    ) -> Dict[str, Any]:
        """HS records, once, that a READY mission's design was staged for a person's review."""

        view, events, replayed = self._current(project_id, mission_id)
        terminal = replayed.get("terminal") or {}
        if terminal.get("state") != "READY_FOR_HUMAN_BUILD":
            raise MissionStateError("only a READY_FOR_HUMAN_BUILD mission can stage its design")
        if replayed.get("staged") is not None:
            return self.get_mission(project_id, mission_id)
        self._write_event(project_id, mission_id, int(replayed["last_event_seq"]) + 1, {
            "type": "design_staged", "author": dict(_SYSTEM_AUTHOR),
            "review_id": _require_text(review_id, field="review_id", max_len=64),
            "package_sha256": package_sha256,
        })
        return self.get_mission(project_id, mission_id)

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
        if view["intake"].get("donors") and not replayed.get("donor_read"):
            donors = _donor_call(read_donors, self.project_store, project_id, view["intake"]["donors"])
            _reject_authority(donors, label="donor_read")
            digest = hashlib.sha256(_canonical_json(donors).encode("utf-8")).hexdigest()
            self._write_event(project_id, mission_id, last_seq + 1,
                             {"type": "donor_read", "author": dict(_SYSTEM_AUTHOR),
                              "donors": donors, "result_sha256": digest})
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
                "'evidence_required', 'finding_offered', or 'terminal_proposed'"
            )
        budgets = view["budgets"]
        record: Dict[str, Any] = {"type": event_type, "author": normalized_author}
        references = list(view["intake"].get("donors") or [])
        if event_type == "candidate_proposed":
            candidate = _normalize_candidate(raw_event.get("candidate"))
            if "donors_used" in candidate["spec"]:
                candidate["spec"]["donors_used"] = _donor_call(normalize_used, candidate["spec"]["donors_used"], references)
            _assert_native_references(candidate["spec"], references)
            if candidate["id"] in replayed["candidates"]:
                raise MissionValidationError(f"candidate {candidate['id']!r} already exists")
            if len(replayed["candidates"]) >= int(budgets["max_candidates"]):
                raise MissionStateError("candidate budget is exhausted; no more candidates may be proposed")
            _assert_measurements_are_the_persons(_person_measurements(view["intake"], replayed), candidate["spec"],
                                                field="candidate.spec")
            record["candidate"] = candidate
        elif event_type == "repair_proposed":
            candidate_id = _normalize_slug(raw_event.get("candidate_id"), field="candidate_id")
            candidate = replayed["candidates"].get(candidate_id)
            if candidate is None:
                raise MissionValidationError(f"candidate {candidate_id!r} does not exist")
            # Only a verdict on the current spec counts: a repair is not stacked on a failure of the spec it replaced.
            plan = _latest_operation(candidate["evaluations"], "device_plan", after_seq=_since_seq(candidate))
            review = (_latest_operation(candidate["evaluations"], "device_engineering", after_seq=int(plan["seq"]))
                      if plan is not None else None)
            base = (int(candidate["last_repair_seq"]) if candidate.get("last_repair_seq") is not None
                    else int(candidate.get("proposal_seq") or 0))
            new_fact = int(candidate.get("last_evidence_seq") or 0) > base
            failing = plan is not None and _plan_is_failing(plan.get("result"))
            review_failed = review is not None and int(review["result"].get("errors") or 0) > 0
            if not (failing or review_failed or new_fact):
                raise MissionStateError("repair_proposed requires a failing device_plan or device_engineering evaluation "
                                        "of the current spec, or a person's evidence since the latest repair")
            if int(candidate["repairs"]) >= int(budgets["max_repairs_per_candidate"]):
                raise MissionStateError("repair budget for this candidate is spent")
            record["candidate_id"] = candidate_id
            record["spec"] = _normalize_spec(raw_event.get("spec"), field="spec")
            if "donors_used" in record["spec"]:
                record["spec"]["donors_used"] = _donor_call(normalize_used, record["spec"]["donors_used"], references)
            _assert_native_references(record["spec"], references)
            dropped_donors = set(candidate["spec"].get("donors_used") or []) - set(record["spec"].get("donors_used") or [])
            if dropped_donors:
                raise MissionStateError("repair_proposed drops used donors: " + ", ".join(sorted(dropped_donors)))
            removed = set(_native_donors(candidate["spec"])) - set(_native_donors(record["spec"]))
            if removed:
                raise MissionStateError("repair_proposed drops wired donor modules: " + ", ".join(sorted(removed)))
            _assert_measurements_are_the_persons(_person_measurements(view["intake"], replayed), record["spec"], field="spec")
            newly_broken = (set(_violated_requirements(replayed["requirements"], record["spec"], replayed["donors"]))
                            - set(_violated_requirements(replayed["requirements"], candidate["spec"], replayed["donors"])))
            if newly_broken:
                raise MissionStateError("repair_proposed is refused: the repair breaks the person's requirements: "
                                        + "; ".join(sorted(newly_broken)))
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
            if raw_event.get("request") is not None:
                record["request"] = _normalize_request(raw_event["request"])
                target = record["request"]["target"]
                if target.startswith("donor:") and target not in {r["donor_id"] for r in references}:
                    raise MissionValidationError("request donor target must be in intake")
            if "cites" in raw_event:
                cites = raw_event["cites"]
                if not isinstance(cites, list) or len(cites) > 40:
                    raise MissionValidationError("need.cites must be a list of at most 40 finding sequences")
                by_seq = {e["seq"]: e for e in events}
                record["cites"] = []
                for cite in cites:
                    cite = _require_int(cite, field="need.cites item", min_value=1)
                    if by_seq.get(cite, {}).get("type") != "finding_offered":
                        raise MissionValidationError("need.cites may reference only existing findings")
                    target = (record.get("request") or {}).get("target")
                    if target and target.startswith("donor:") and by_seq[cite]["finding"]["donor_id"] != target:
                        raise MissionValidationError("cited finding belongs to another donor")
                    record["cites"].append(cite)
        elif event_type == "finding_offered":
            if normalized_author["kind"] != "agent":
                raise MissionValidationError("only agents may offer findings")
            if set(raw_event) != {"type", "finding"}:
                raise MissionValidationError("finding_offered accepts only type and finding; no author or grade override")
            if replayed.get("accepted") is None:
                raise MissionStateError("findings require an accepted mission with a frozen donor_read")
            record["finding"] = _donor_call(normalize_finding, raw_event.get("finding"), references)
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
                                       if state == "BLOCKED_NEEDS_PART_DATA" else
                                       donor_grounding(replayed, events, raw_event, record["cites"]))
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
