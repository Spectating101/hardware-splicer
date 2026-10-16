"""OpenPnP job-package inspection for simulation-first PCB assembly.

OpenPnP's simulator is useful before a real pick-and-place machine is connected.
This module does not start OpenPnP or move hardware.  It validates a server-
registered job XML, retains hashes for the job and referenced local XML files,
and emits a simulation package that can be handed to a reviewed simulator or
human operator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .fabrication_operator import FabricationValidationError

_MAX_XML_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class OpenPnpJob:
    job_id: str
    root: Path
    job_file: Path


class OpenPnpJobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, OpenPnpJob] = {}

    def register(self, *, job_id: str, root: str | Path, job_file: str | Path) -> None:
        jid = _id(job_id, "job_id")
        if jid in self._jobs:
            raise FabricationValidationError("OpenPnP job id is already registered")
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise FabricationValidationError("OpenPnP root must be an existing directory")
        raw = Path(job_file)
        path = raw.resolve() if raw.is_absolute() else (root_path / raw).resolve()
        try:
            path.relative_to(root_path)
        except ValueError as exc:
            raise FabricationValidationError("OpenPnP job escapes registered root") from exc
        if not path.is_file() or not path.name.lower().endswith(".job.xml"):
            raise FabricationValidationError("OpenPnP job must be an existing .job.xml file")
        self._jobs[jid] = OpenPnpJob(jid, root_path, path)

    def get(self, job_id: str) -> OpenPnpJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown OpenPnP job id") from exc

    def list_public(self) -> list[dict[str, str]]:
        return [{"job_id": row.job_id} for row in sorted(self._jobs.values(), key=lambda item: item.job_id)]


class OpenPnpSimulationInspector:
    def __init__(self, *, jobs: OpenPnpJobRegistry):
        self.jobs = jobs

    def inspect(self, job_id: str) -> dict[str, Any]:
        job = self.jobs.get(job_id)
        data = job.job_file.read_bytes()
        if not data or len(data) > _MAX_XML_BYTES:
            raise FabricationValidationError("OpenPnP job XML size is invalid")
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise FabricationValidationError("OpenPnP job XML is malformed") from exc

        local_names: dict[str, int] = {}
        referenced_paths: set[Path] = set()
        for element in root.iter():
            name = _local(element.tag)
            local_names[name] = local_names.get(name, 0) + 1
            for value in element.attrib.values():
                if not isinstance(value, str):
                    continue
                lowered = value.lower().strip()
                if not lowered.endswith((".board.xml", ".job.xml", ".xml")):
                    continue
                candidate = (job.job_file.parent / value).resolve()
                try:
                    candidate.relative_to(job.root)
                except ValueError:
                    continue
                if candidate.is_file() and candidate != job.job_file:
                    referenced_paths.add(candidate)

        artifacts = {job.job_file.relative_to(job.root).as_posix(): _sha(job.job_file)}
        for path in sorted(referenced_paths):
            artifacts[path.relative_to(job.root).as_posix()] = _sha(path)

        # OpenPnP XML evolves; use local-name counts as descriptive metadata only,
        # never as an authority claim that a job is manufacturable.
        board_like = sum(count for name, count in local_names.items() if "board" in name.lower())
        placement_like = sum(count for name, count in local_names.items() if "placement" in name.lower())
        return {
            "schema": "hardware_splicer.openpnp_simulation_package.v1",
            "job_id": job.job_id,
            "job_sha256": hashlib.sha256(data).hexdigest(),
            "artifacts": dict(sorted(artifacts.items())),
            "xml_summary": {
                "root_element": _local(root.tag),
                "board_like_elements": board_like,
                "placement_like_elements": placement_like,
                "element_counts": dict(sorted(local_names.items())),
            },
            "simulation_only": True,
            "live_machine_execution": False,
            "simulation_status": "PACKAGE_READY_FOR_OPENPNP_SIMULATOR",
            "physical_correctness": "UNPROVEN",
            "limitations": [
                "XML inspection does not prove feeder setup, fiducials, nozzle compatibility, placement accuracy or solder quality.",
                "Live OpenPnP machine power/play remains outside this adapter.",
            ],
        }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 96 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
