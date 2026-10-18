"""A person answers a mission's measurement request by typing the reading.

HS builds the physical-evidence envelope itself, so no browser ever has to reproduce its hash, then hands it to the
same `MissionStore.supply_evidence` that checks every envelope: its hash, that it is bound to this project, mission,
need and these values, that it was not used before, and the requested range. Nothing here widens what an answer
can do. A typed reading is the person's own report: no instrument or calibration is recorded, and the mission stays
UNPROVEN.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from .mission_store import (
    MissionStateError,
    MissionStore,
    MissionValidationError,
    _REQUEST_KINDS,
    _compare,
    _normalize_author,
    _normalize_readings,
)
from .physical_evidence_ledger import build_physical_evidence_envelope


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def answer_need(
    missions: MissionStore,
    project_id: str,
    mission_id: str,
    need_seq: int,
    *,
    values: Any,
    author: Mapping[str, Any],
    expected_event_seq: int | None = None,
) -> dict[str, Any]:
    person = _normalize_author(author)
    if person["kind"] != "human":
        raise MissionValidationError("only a person can answer a measurement request")
    view = missions.get_mission(project_id, mission_id)
    need = next((item for item in view["needs"] if item["seq"] == need_seq), None)
    if need is None:
        raise MissionValidationError(f"event {need_seq} is not an evidence need of this mission")
    request = need.get("request")
    if not request:
        raise MissionStateError(f"need {need_seq} has no structured request a person can answer")
    readings = _normalize_readings(request, values)

    now = datetime.now(timezone.utc).isoformat()
    token = uuid.uuid4().hex[:16]
    raw = _canonical(readings)
    record: dict[str, Any] = {
        "evidence_id": f"ev-{token}",
        "project_id": project_id,
        "candidate_revision": "mission",
        "kind": _REQUEST_KINDS[request["kind"]],
        "target_ids": [request["target"]],
        "procedure_id": "mission-need",
        # A reading is "passed" when it met the range that was asked for; a log or a size has no range to miss.
        "passed": _compare(request, readings) != "outside",
        "captured_at": now,
        "operator": person["id"],
        "measured_values": ({"log_sha256": hashlib.sha256(raw).hexdigest(), "log_bytes": len(readings["log"].encode("utf-8"))}
                            if request["kind"] == "boot_log" else {"readings": readings}),
        "acceptance_criteria": dict(request.get("expected") or {}),
        "raw_refs": ["mission-answer"],
        "metadata": {"entry": "typed by the person in the mission page; no instrument or calibration is recorded"},
    }
    envelope = build_physical_evidence_envelope(
        envelope_id=f"env-{token}",
        record=record,
        raw_files=[{"ref": "mission-answer.json", "content_hash": f"sha256:{hashlib.sha256(raw).hexdigest()}",
                    "media_type": "application/json", "size_bytes": len(raw), "captured_at": now}],
        created_at=now,
        created_by=person["id"],
        metadata={"mission": {"project_id": project_id, "mission_id": mission_id, "need_seq": need_seq, "values": readings}},
    )
    return missions.supply_evidence(
        project_id, mission_id, need_seq,
        envelope=envelope.model_dump(mode="json"), values=values, author=person, expected_event_seq=expected_event_seq,
    )
