from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

PROJECT_STORE_SCHEMA = "hardware_splicer.project_snapshot.v1"
_PROJECT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


class ProjectStoreError(RuntimeError):
    """Base error for persistent project state."""


class InvalidProjectId(ProjectStoreError, ValueError):
    pass


class ProjectNotFound(ProjectStoreError, FileNotFoundError):
    pass


class RevisionConflict(ProjectStoreError):
    pass


class CorruptProject(ProjectStoreError):
    pass


@dataclass(frozen=True)
class ProjectSummary:
    project_id: str
    name: str
    mode: str
    current_stage: str
    latest_revision: int
    saved_at: str
    archived: bool
    recovered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "mode": self.mode,
            "current_stage": self.current_stage,
            "latest_revision": self.latest_revision,
            "saved_at": self.saved_at,
            "archived": self.archived,
            "recovered": self.recovered,
        }


def default_project_root() -> Path:
    configured = os.getenv("HARDWARE_SPLICER_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    output_root = Path(os.getenv("HARDWARE_SPLICER_OUTPUT_ROOT", "/tmp/hardware_splicer_api"))
    return (output_root / "projects").expanduser().resolve()


def validate_project_id(project_id: str) -> str:
    raw = str(project_id or "")
    value = raw.strip()
    if raw != value or not _PROJECT_ID_RE.fullmatch(value) or value in {".", ".."}:
        raise InvalidProjectId(
            "project_id must start with an alphanumeric character and contain only "
            "letters, numbers, dot, underscore, or dash (maximum 96 characters)"
        )
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorruptProject(f"cannot read valid project JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CorruptProject(f"project JSON must be an object: {path}")
    return value


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
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


class ProjectStore:
    """Revisioned filesystem store for editable project snapshots.

    Build directories remain references inside the snapshot. The store writes only JSON
    envelopes and never follows or copies paths found in project state.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).expanduser().resolve() if root is not None else default_project_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        safe_id = validate_project_id(project_id)
        path = (self.root / safe_id).resolve()
        if path.parent != self.root:
            raise InvalidProjectId("project_id resolves outside project root")
        return path

    @staticmethod
    def _revision_name(revision: int) -> str:
        if revision < 1:
            raise ValueError("revision must be at least 1")
        return f"{revision:08d}.json"

    def _revision_path(self, project_id: str, revision: int) -> Path:
        return self._project_dir(project_id) / "revisions" / self._revision_name(revision)

    def _manifest_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _manifest_or_default(self, project_id: str) -> Dict[str, Any]:
        path = self._manifest_path(project_id)
        if not path.exists():
            return {
                "schema_version": PROJECT_STORE_SCHEMA,
                "project_id": validate_project_id(project_id),
                "latest_revision": 0,
                "archived": False,
                "created_at": _utc_now(),
                "saved_at": "",
            }
        return _read_json(path)

    def save(
        self,
        project_id: str,
        snapshot: Mapping[str, Any],
        *,
        expected_revision: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        safe_id = validate_project_id(project_id)
        if not isinstance(snapshot, Mapping):
            raise TypeError("snapshot must be a mapping")
        json.dumps(snapshot, ensure_ascii=False)
        json.dumps(metadata or {}, ensure_ascii=False)

        manifest = self._manifest_or_default(safe_id)
        current = int(manifest.get("latest_revision") or 0)
        if expected_revision is not None and int(expected_revision) != current:
            raise RevisionConflict(
                f"project {safe_id!r} is at revision {current}, expected {expected_revision}"
            )

        revision = current + 1
        saved_at = _utc_now()
        envelope: Dict[str, Any] = {
            "schema_version": PROJECT_STORE_SCHEMA,
            "project_id": safe_id,
            "revision": revision,
            "saved_at": saved_at,
            "snapshot": dict(snapshot),
            "metadata": dict(metadata or {}),
        }
        revision_path = self._revision_path(safe_id, revision)
        if revision_path.exists():
            raise RevisionConflict(f"revision already exists: {safe_id}@{revision}")
        _atomic_write_json(revision_path, envelope)

        next_manifest = {
            "schema_version": PROJECT_STORE_SCHEMA,
            "project_id": safe_id,
            "latest_revision": revision,
            "archived": bool(manifest.get("archived", False)),
            "created_at": manifest.get("created_at") or saved_at,
            "saved_at": saved_at,
        }
        _atomic_write_json(self._manifest_path(safe_id), next_manifest)
        return envelope

    def _validate_envelope(self, project_id: str, revision: int, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if envelope.get("schema_version") != PROJECT_STORE_SCHEMA:
            raise CorruptProject(f"unsupported project snapshot schema at {project_id}@{revision}")
        if envelope.get("project_id") != project_id:
            raise CorruptProject(f"project id mismatch at {project_id}@{revision}")
        if int(envelope.get("revision") or 0) != revision:
            raise CorruptProject(f"revision mismatch at {project_id}@{revision}")
        if not isinstance(envelope.get("snapshot"), dict):
            raise CorruptProject(f"snapshot must be an object at {project_id}@{revision}")
        return envelope

    def _revision_numbers(self, project_id: str) -> Iterable[int]:
        revisions = self._project_dir(project_id) / "revisions"
        if not revisions.is_dir():
            return []
        values = []
        for path in revisions.glob("*.json"):
            if path.stem.isdigit():
                values.append(int(path.stem))
        return sorted(values, reverse=True)

    def load(self, project_id: str, revision: int | None = None) -> Dict[str, Any]:
        safe_id = validate_project_id(project_id)
        project_dir = self._project_dir(safe_id)
        if not project_dir.is_dir():
            raise ProjectNotFound(safe_id)

        if revision is not None:
            path = self._revision_path(safe_id, int(revision))
            if not path.is_file():
                raise ProjectNotFound(f"{safe_id}@{revision}")
            return self._validate_envelope(safe_id, int(revision), _read_json(path))

        candidates: list[int] = []
        try:
            manifest = _read_json(self._manifest_path(safe_id))
            latest = int(manifest.get("latest_revision") or 0)
            if latest:
                candidates.append(latest)
        except CorruptProject:
            pass
        candidates.extend(number for number in self._revision_numbers(safe_id) if number not in candidates)

        errors: list[str] = []
        for candidate in candidates:
            try:
                envelope = _read_json(self._revision_path(safe_id, candidate))
                return self._validate_envelope(safe_id, candidate, envelope)
            except CorruptProject as exc:
                errors.append(str(exc))
        if errors:
            raise CorruptProject("; ".join(errors))
        raise ProjectNotFound(safe_id)

    def load_latest_with_recovery(self, project_id: str) -> Dict[str, Any]:
        """Load latest valid state and repair corrupt manifest/revision pointers.

        Corrupt revisions newer than the recovered truth are quarantined with a
        ``.corrupt`` suffix. The manifest is atomically repointed so the next
        optimistic save can continue from the recovered revision immediately.
        Recovery remains visible until a successful new save replaces the manifest.
        """

        safe_id = validate_project_id(project_id)
        project_dir = self._project_dir(safe_id)
        if not project_dir.is_dir():
            raise ProjectNotFound(safe_id)

        manifest_path = self._manifest_path(safe_id)
        requested_revision: int | None = None
        manifest_problem = False
        manifest: Dict[str, Any] = {}
        prior_recovery: Dict[str, Any] = {}
        try:
            manifest = _read_json(manifest_path)
            requested_revision = int(manifest.get("latest_revision") or 0) or None
            if isinstance(manifest.get("recovery"), dict):
                prior_recovery = dict(manifest["recovery"])
        except CorruptProject:
            manifest_problem = manifest_path.exists()

        if requested_revision is not None:
            try:
                envelope = self.load(safe_id, revision=requested_revision)
                recovered_now = False
            except CorruptProject:
                envelope = self.load(safe_id)
                recovered_now = True
        else:
            envelope = self.load(safe_id)
            recovered_now = manifest_problem

        loaded_revision = int(envelope.get("revision") or 0)
        recovered_now = recovered_now or (
            requested_revision is not None and loaded_revision != requested_revision
        )
        quarantined: list[int] = []

        if recovered_now:
            for candidate in self._revision_numbers(safe_id):
                if candidate <= loaded_revision:
                    continue
                try:
                    self.load(safe_id, revision=candidate)
                except CorruptProject:
                    source = self._revision_path(safe_id, candidate)
                    quarantine = source.with_name(f"{source.name}.corrupt")
                    if quarantine.exists():
                        quarantine.unlink()
                    source.replace(quarantine)
                    quarantined.append(candidate)

            saved_at = str(envelope.get("saved_at") or "")
            prior_recovery = {
                "requested_revision": requested_revision,
                "loaded_revision": loaded_revision,
                "quarantined_revisions": quarantined,
            }
            repaired_manifest = {
                "schema_version": PROJECT_STORE_SCHEMA,
                "project_id": safe_id,
                "latest_revision": loaded_revision,
                "archived": bool(manifest.get("archived", False)),
                "created_at": manifest.get("created_at") or saved_at,
                "saved_at": saved_at,
                "recovery": prior_recovery,
            }
            _atomic_write_json(manifest_path, repaired_manifest)

        recovery_used = recovered_now or bool(prior_recovery)
        recovery = {
            "used": recovery_used,
            "requested_revision": prior_recovery.get("requested_revision", requested_revision),
            "loaded_revision": int(prior_recovery.get("loaded_revision") or loaded_revision),
            "quarantined_revisions": list(prior_recovery.get("quarantined_revisions") or quarantined),
        }
        body = dict(envelope)
        body["recovery"] = recovery
        return body

    def list_projects(self, *, include_archived: bool = False) -> list[Dict[str, Any]]:
        projects: list[ProjectSummary] = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir():
                continue
            try:
                project_id = validate_project_id(directory.name)
                manifest = _read_json(directory / "project.json")
                archived = bool(manifest.get("archived", False))
                if archived and not include_archived:
                    continue
                latest = self.load_latest_with_recovery(project_id)
                snapshot = latest["snapshot"]
                projects.append(
                    ProjectSummary(
                        project_id=project_id,
                        name=str(snapshot.get("projectName") or snapshot.get("project_name") or "Untitled project"),
                        mode=str(snapshot.get("mode") or "greenfield"),
                        current_stage=str(snapshot.get("currentStage") or snapshot.get("current_stage") or "intake"),
                        latest_revision=int(latest["revision"]),
                        saved_at=str(latest.get("saved_at") or manifest.get("saved_at") or ""),
                        archived=archived,
                        recovered=bool(latest.get("recovery", {}).get("used")),
                    )
                )
            except (ProjectStoreError, ValueError, OSError):
                continue
        projects.sort(key=lambda row: row.saved_at, reverse=True)
        return [row.to_dict() for row in projects]

    def set_archived(self, project_id: str, archived: bool = True) -> Dict[str, Any]:
        safe_id = validate_project_id(project_id)
        manifest = self._manifest_or_default(safe_id)
        if int(manifest.get("latest_revision") or 0) < 1:
            raise ProjectNotFound(safe_id)
        manifest["archived"] = bool(archived)
        manifest["saved_at"] = _utc_now()
        _atomic_write_json(self._manifest_path(safe_id), manifest)
        return manifest

    def duplicate(self, source_project_id: str, target_project_id: str) -> Dict[str, Any]:
        source = self.load(source_project_id)
        target = validate_project_id(target_project_id)
        if self._project_dir(target).exists():
            raise RevisionConflict(f"target project already exists: {target}")
        snapshot = dict(source["snapshot"])
        snapshot["projectId"] = target
        return self.save(
            target,
            snapshot,
            metadata={
                "duplicated_from": source["project_id"],
                "source_revision": source["revision"],
            },
        )

    def delete(self, project_id: str) -> None:
        safe_id = validate_project_id(project_id)
        path = self._project_dir(safe_id)
        if not path.is_dir():
            raise ProjectNotFound(safe_id)
        shutil.rmtree(path)
