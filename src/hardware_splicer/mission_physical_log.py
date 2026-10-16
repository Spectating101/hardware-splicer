"""Append-only physical receipt log anchored to a Fabrication Mission.

FabricationMission's primary event log represents software reasoning and terminal
truth.  A real build may begin only after a mission reaches READY_FOR_HUMAN_BUILD,
so physical execution/observation receipts need a separate append-only history that
can continue after the mission itself is terminal.

This log does not reopen a terminal mission, change its terminal verdict, grant
physical authority, or declare physical correctness.  It is a provenance sidecar
for later project revisions and evidence assessment.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .mission_store import MissionError, MissionStateError, MissionStore, MissionValidationError

_SCHEMA = "hardware_splicer.mission_physical_receipt.v1"
_RECEIPT_TYPES = frozenset({"dispatch", "observation", "evidence"})
_SOURCE_SCHEMAS = {
    "dispatch": frozenset({"hardware_splicer.physical_dispatch_receipt.v1"}),
    "observation": frozenset(
        {
            "hardware_splicer.physical_observation_artifact.v1",
            "hardware_splicer.camera_observation.v1",
            "hardware_splicer.instrument_observation.v1",
            "hardware_splicer.camera_status.v1",
        }
    ),
    "evidence": frozenset({"hardware_splicer.physical_evidence.v1"}),
}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FILE_RE = re.compile(r"^[0-9]{8}\.json$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Mapping[str, Any]) -> tuple[dict[str, Any], bytes]:
    if not isinstance(value, Mapping):
        raise MissionValidationError("physical receipt source must be an object")
    try:
        text = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        normalized = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise MissionValidationError("physical receipt source must be canonical JSON") from exc
    return normalized, text.encode("utf-8")


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value.strip()) is None:
        raise MissionValidationError(f"{field} must be a bounded identifier")
    return value.strip()


def _atomic_create(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise MissionError("physical receipt path must not be a symlink")
    payload = json.dumps(dict(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise MissionError("physical receipt sequence already exists") from exc
    finally:
        temp.unlink(missing_ok=True)


class MissionPhysicalLog:
    """Retain canonical physical receipts without modifying mission replay state."""

    def __init__(self, missions: MissionStore):
        if not isinstance(missions, MissionStore):
            raise MissionValidationError("MissionPhysicalLog requires a MissionStore")
        self.missions = missions

    def record(
        self,
        project_id: str,
        mission_id: str,
        *,
        receipt_type: str,
        source: Mapping[str, Any],
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        if receipt_type not in _RECEIPT_TYPES:
            raise MissionValidationError("receipt_type must be dispatch, observation, or evidence")
        normalized, encoded = _canonical(source)
        source_schema = normalized.get("schema") or normalized.get("schema_version")
        if source_schema not in _SOURCE_SCHEMAS[receipt_type]:
            raise MissionValidationError(
                f"{receipt_type} receipt schema is not supported: {source_schema!r}"
            )
        self._validate_truth_boundary(receipt_type, normalized)
        safe_candidate = _identifier(candidate_id, field="candidate_id") if candidate_id is not None else None

        # Share the mission's mutation lock so physical sidecar sequence assignment
        # cannot race with another process writing this mission's physical history.
        with self.missions.mutation(project_id, mission_id):
            mission = self.missions.get_mission(project_id, mission_id)
            if mission.get("accepted") is None:
                raise MissionStateError("physical receipts require a human-accepted mission")
            if safe_candidate is not None:
                candidates = {str(row.get("id")) for row in mission.get("candidates") or []}
                if safe_candidate not in candidates:
                    raise MissionValidationError(
                        f"candidate {safe_candidate!r} does not exist in this mission"
                    )
            directory = self._receipts_dir(project_id, mission_id)
            sequence = self._next_sequence(directory)
            record = {
                "schema": _SCHEMA,
                "seq": sequence,
                "recorded_at": _now(),
                "recorded_by": {"kind": "system", "id": "hardware-splicer"},
                "receipt_type": receipt_type,
                "candidate_id": safe_candidate,
                "source_schema": source_schema,
                "source_sha256": hashlib.sha256(encoded).hexdigest(),
                "source": normalized,
                "mission_terminal_state_unchanged": True,
                "physical_correctness": "UNPROVEN",
                "grants_physical_authority": False,
            }
            _atomic_create(directory / f"{sequence:08d}.json", record)
            return json.loads(json.dumps(record))

    def list(self, project_id: str, mission_id: str) -> list[dict[str, Any]]:
        # Establish mission existence even when it has no physical receipts yet.
        self.missions.get_mission(project_id, mission_id)
        directory = self._receipts_dir(project_id, mission_id)
        if not directory.exists():
            return []
        if directory.is_symlink() or not directory.is_dir():
            raise MissionError("physical receipts directory is invalid")
        rows: list[dict[str, Any]] = []
        expected = 1
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.is_symlink() or _FILE_RE.fullmatch(path.name) is None:
                continue
            seq = int(path.stem)
            if seq != expected:
                raise MissionError("physical receipt sequence must be contiguous from 1")
            rows.append(self._read(path, expected_seq=seq))
            expected += 1
        return rows

    def read(self, project_id: str, mission_id: str, sequence: int) -> dict[str, Any]:
        if type(sequence) is not int or sequence < 1:
            raise MissionValidationError("physical receipt sequence must be a positive integer")
        self.missions.get_mission(project_id, mission_id)
        path = self._receipts_dir(project_id, mission_id) / f"{sequence:08d}.json"
        if not path.is_file() or path.is_symlink():
            raise MissionError("physical receipt does not exist")
        return self._read(path, expected_seq=sequence)

    def _receipts_dir(self, project_id: str, mission_id: str) -> Path:
        # MissionStore already performs project/mission id and path-containment checks.
        mission_dir = self.missions._mission_dir(project_id, mission_id)
        directory = mission_dir / "physical" / "receipts"
        resolved_parent = mission_dir.resolve()
        if directory.exists() and directory.is_symlink():
            raise MissionError("physical receipts directory must not be a symlink")
        try:
            directory.resolve().relative_to(resolved_parent)
        except ValueError as exc:
            raise MissionError("physical receipts directory escapes mission root") from exc
        return directory

    def _next_sequence(self, directory: Path) -> int:
        if not directory.exists():
            return 1
        if directory.is_symlink() or not directory.is_dir():
            raise MissionError("physical receipts directory is invalid")
        sequences = sorted(
            int(path.stem)
            for path in directory.iterdir()
            if path.is_file() and not path.is_symlink() and _FILE_RE.fullmatch(path.name)
        )
        if sequences != list(range(1, len(sequences) + 1)):
            raise MissionError("physical receipt sequence must be contiguous from 1")
        return len(sequences) + 1

    def _read(self, path: Path, *, expected_seq: int) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MissionError("physical receipt cannot be read") from exc
        if not isinstance(value, dict) or value.get("schema") != _SCHEMA:
            raise MissionError("physical receipt record is invalid")
        if value.get("seq") != expected_seq:
            raise MissionError("physical receipt sequence does not match its file")
        if value.get("physical_correctness") != "UNPROVEN":
            raise MissionError("mission physical log must not claim physical correctness")
        if value.get("grants_physical_authority") is not False:
            raise MissionError("mission physical log must not grant physical authority")
        source = value.get("source")
        normalized, encoded = _canonical(source)
        if normalized != source or hashlib.sha256(encoded).hexdigest() != value.get("source_sha256"):
            raise MissionError("physical receipt source hash does not match retained source")
        return value

    @staticmethod
    def _validate_truth_boundary(receipt_type: str, source: Mapping[str, Any]) -> None:
        if receipt_type in {"dispatch", "observation"}:
            if source.get("physical_correctness") != "UNPROVEN":
                raise MissionValidationError(
                    f"{receipt_type} receipt must keep physical_correctness UNPROVEN"
                )
        if receipt_type == "dispatch" and source.get("schema") == "hardware_splicer.physical_dispatch_receipt.v1":
            if source.get("authority") not in {"not_required", "human_grant_consumed"}:
                raise MissionValidationError("dispatch receipt has unsupported authority provenance")
