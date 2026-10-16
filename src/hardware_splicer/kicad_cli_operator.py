"""Bounded KiCad CLI integration for deterministic EDA verification and export.

Agents select a server-registered KiCad project id and one of a small fixed set
of operations. They never provide argv, executable paths, arbitrary filesystem
paths, or shell text. KiCad remains authoritative for ERC/DRC results.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .fabrication_operator import FabricationValidationError


class KicadExecutionError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]: ...


class SubprocessCommandRunner:
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
        )


@dataclass(frozen=True)
class KicadProjectDescriptor:
    project_id: str
    root: Path
    schematic: Path | None
    board: Path | None


class KicadProjectRegistry:
    def __init__(self) -> None:
        self._projects: dict[str, KicadProjectDescriptor] = {}

    def register(
        self,
        *,
        project_id: str,
        root: str | Path,
        schematic: str | Path | None = None,
        board: str | Path | None = None,
    ) -> None:
        pid = _id(project_id, "project_id")
        if pid in self._projects:
            raise FabricationValidationError("KiCad project id is already registered")
        root_literal = Path(root)
        if root_literal.is_symlink():
            raise FabricationValidationError("KiCad project root must not be a symlink")
        root_path = root_literal.resolve()
        if not root_path.is_dir():
            raise FabricationValidationError("KiCad project root must be an existing directory")
        sch = self._file(root_path, schematic, ".kicad_sch", "schematic") if schematic is not None else None
        pcb = self._file(root_path, board, ".kicad_pcb", "board") if board is not None else None
        if sch is None and pcb is None:
            raise FabricationValidationError("KiCad project needs a schematic or board")
        self._projects[pid] = KicadProjectDescriptor(pid, root_path, sch, pcb)

    def get(self, project_id: str) -> KicadProjectDescriptor:
        try:
            return self._projects[project_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown KiCad project id") from exc

    def list_public(self) -> list[dict[str, Any]]:
        values = []
        for project in sorted(self._projects.values(), key=lambda row: row.project_id):
            values.append({
                "project_id": project.project_id,
                "has_schematic": project.schematic is not None,
                "has_board": project.board is not None,
                "capabilities": [
                    *(["erc"] if project.schematic is not None else []),
                    *(["drc", "gerbers", "drill", "positions", "step"] if project.board is not None else []),
                ],
            })
        return values

    @staticmethod
    def _file(root: Path, value: str | Path, suffix: str, field: str) -> Path:
        raw = Path(value)
        candidate = raw if raw.is_absolute() else root / raw
        if candidate.is_symlink():
            raise FabricationValidationError(f"KiCad {field} must not be a symlink")
        path = candidate.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise FabricationValidationError(f"KiCad {field} escapes registered root") from exc
        if not path.is_file() or path.suffix.lower() != suffix:
            raise FabricationValidationError(f"KiCad {field} must be an existing {suffix} file")
        return path


class KicadCliOperator:
    """Run a fixed KiCad verification/export surface and return evidence receipts."""

    def __init__(
        self,
        *,
        projects: KicadProjectRegistry,
        executable: str = "kicad-cli",
        runner: CommandRunner | None = None,
        timeout_seconds: float = 120.0,
    ):
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("KiCad executable must be server-configured text")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= float(timeout_seconds) <= 1800:
            raise FabricationValidationError("KiCad timeout must be between 1 and 1800 seconds")
        self.projects = projects
        self.executable = executable.strip()
        self.runner = runner or SubprocessCommandRunner()
        self.timeout_seconds = float(timeout_seconds)

    def version(self) -> dict[str, Any]:
        completed = self._run([self.executable, "version"], cwd=Path.cwd())
        return self._receipt("version", completed, artifacts={})

    def verify(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        reports = _safe_run_dir(project.root, "verify")
        receipts: list[dict[str, Any]] = []
        if project.schematic is not None:
            output = reports / "erc.json"
            completed = self._run([
                self.executable, "sch", "erc", "--format", "json", "--exit-code-violations",
                "--output", str(output), str(project.schematic),
            ], cwd=project.root, allow_violation_exit=True)
            receipts.append(self._receipt("erc", completed, artifacts=self._hash_files([output])))
        if project.board is not None:
            output = reports / "drc.json"
            completed = self._run([
                self.executable, "pcb", "drc", "--format", "json", "--exit-code-violations",
                "--output", str(output), str(project.board),
            ], cwd=project.root, allow_violation_exit=True)
            receipts.append(self._receipt("drc", completed, artifacts=self._hash_files([output])))
        return {
            "schema": "hardware_splicer.kicad_verification.v1",
            "project_id": project.project_id,
            "checks": receipts,
            "passed": all(item["exit_code"] == 0 for item in receipts),
            "authoritative_tool": "kicad-cli",
            "physical_correctness": "UNPROVEN",
        }

    def export_manufacturing(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        if project.board is None:
            raise FabricationValidationError("KiCad manufacturing export requires a board")
        output = _safe_run_dir(project.root, "manufacturing")
        commands = [
            [self.executable, "pcb", "export", "gerbers", "--output", str(output), str(project.board)],
            [self.executable, "pcb", "export", "drill", "--output", str(output), str(project.board)],
            [self.executable, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--output", str(output / "positions.csv"), str(project.board)],
            [self.executable, "pcb", "export", "step", "--output", str(output / "board.step"), str(project.board)],
        ]
        command_receipts = []
        for argv in commands:
            completed = self._run(argv, cwd=project.root)
            command_receipts.append(self._receipt("export", completed, artifacts={}))
        artifacts = self._hash_files(sorted(path for path in output.rglob("*") if path.is_file()))
        return {
            "schema": "hardware_splicer.kicad_manufacturing_bundle.v1",
            "project_id": project.project_id,
            "commands": command_receipts,
            "artifacts": artifacts,
            "bundle_sha256": _json_sha(artifacts),
            "physical_correctness": "UNPROVEN",
        }

    def _run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        allow_violation_exit: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = self.runner.run(argv, cwd=cwd, timeout_seconds=self.timeout_seconds)
        except (OSError, subprocess.SubprocessError) as exc:
            raise KicadExecutionError("KiCad CLI execution failed") from exc
        accepted = {0, 5} if allow_violation_exit else {0}
        if completed.returncode not in accepted:
            raise KicadExecutionError(
                f"KiCad CLI failed with exit code {completed.returncode}: {(completed.stderr or '')[:500]}"
            )
        return completed

    @staticmethod
    def _receipt(operation: str, completed: subprocess.CompletedProcess[str], *, artifacts: Mapping[str, str]) -> dict[str, Any]:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return {
            "schema": "hardware_splicer.tool_receipt.v1",
            "tool": "kicad-cli",
            "operation": operation,
            "argv": [str(item) for item in completed.args] if isinstance(completed.args, (list, tuple)) else [str(completed.args)],
            "exit_code": int(completed.returncode),
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8", errors="replace")).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode("utf-8", errors="replace")).hexdigest(),
            "artifacts": dict(artifacts),
        }

    @staticmethod
    def _hash_files(paths: list[Path] | tuple[Path, ...]) -> dict[str, str]:
        result: dict[str, str] = {}
        for path in paths:
            if not path.is_file() or path.is_symlink():
                continue
            result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return dict(sorted(result.items()))


def _safe_run_dir(root: Path, label: str) -> Path:
    base_literal = root / ".hs-kicad"
    if base_literal.exists() and base_literal.is_symlink():
        raise FabricationValidationError("KiCad output root must not be a symlink")
    base = base_literal.resolve()
    try:
        base.relative_to(root)
    except ValueError as exc:
        raise FabricationValidationError("KiCad output root escapes registered project") from exc
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=f"{label}-", dir=base))
    if path.is_symlink() or path.resolve().parent != base.resolve():
        raise FabricationValidationError("KiCad output directory is invalid")
    return path


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 96 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _json_sha(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
