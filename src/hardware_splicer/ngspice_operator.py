"""Server-owned ngspice batch simulations with immutable-style receipts.

Simulation output is model evidence, never physical evidence.  Agents select a
registered circuit id and a bounded output mode; argv and filesystem paths are
constructed by the server and executed without a shell.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .fabrication_operator import FabricationValidationError


class NgspiceExecutionError(RuntimeError):
    pass


class NgspiceRunner(Protocol):
    def run(self, argv: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]: ...


class SubprocessNgspiceRunner:
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
class NgspiceCircuit:
    circuit_id: str
    path: Path


class NgspiceCircuitRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FabricationValidationError("ngspice circuit root must be an existing directory")
        self._circuits: dict[str, NgspiceCircuit] = {}

    def register(self, *, circuit_id: str, path: str | Path) -> None:
        cid = _id(circuit_id, "circuit_id")
        if cid in self._circuits:
            raise FabricationValidationError("ngspice circuit id is already registered")
        candidate = (self.root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise FabricationValidationError("ngspice circuit escapes registered root") from exc
        if not candidate.is_file() or candidate.suffix.lower() not in {".cir", ".sp", ".spice", ".ckt"}:
            raise FabricationValidationError("ngspice circuit must be an existing SPICE netlist")
        self._circuits[cid] = NgspiceCircuit(cid, candidate)

    def get(self, circuit_id: str) -> NgspiceCircuit:
        try:
            return self._circuits[circuit_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown ngspice circuit id") from exc

    def list_public(self) -> list[dict[str, str]]:
        return [{"circuit_id": item.circuit_id} for item in sorted(self._circuits.values(), key=lambda row: row.circuit_id)]


class NgspiceOperator:
    def __init__(
        self,
        *,
        circuits: NgspiceCircuitRegistry,
        executable: str = "ngspice",
        runner: NgspiceRunner | None = None,
        timeout_seconds: float = 120.0,
    ):
        if not isinstance(executable, str) or not executable.strip() or any(ch in executable for ch in "\r\n\x00"):
            raise FabricationValidationError("ngspice executable must be server-configured text")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= float(timeout_seconds) <= 1800:
            raise FabricationValidationError("ngspice timeout must be between 1 and 1800 seconds")
        self.circuits = circuits
        self.executable = executable.strip()
        self.runner = runner or SubprocessNgspiceRunner()
        self.timeout_seconds = float(timeout_seconds)

    def run(self, circuit_id: str, *, mode: str = "report") -> dict[str, Any]:
        if mode not in {"report", "raw"}:
            raise FabricationValidationError("ngspice mode must be report or raw")
        circuit = self.circuits.get(circuit_id)
        output_dir = circuit.path.parent / ".hs-ngspice" / circuit.circuit_id
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "simulation.log"
        argv = [self.executable, "-b", "-o", str(log_path)]
        raw_path: Path | None = None
        if mode == "raw":
            raw_path = output_dir / "simulation.raw"
            argv.extend(["-r", str(raw_path)])
        argv.append(str(circuit.path))
        try:
            completed = self.runner.run(argv, cwd=circuit.path.parent, timeout_seconds=self.timeout_seconds)
        except (OSError, subprocess.SubprocessError) as exc:
            raise NgspiceExecutionError("ngspice execution failed") from exc
        if completed.returncode != 0:
            raise NgspiceExecutionError(
                f"ngspice failed with exit code {completed.returncode}: {(completed.stderr or '')[:500]}"
            )
        artifacts: dict[str, str] = {}
        for path in [log_path, raw_path]:
            if path is not None and path.is_file() and not path.is_symlink():
                artifacts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = {
            "schema": "hardware_splicer.ngspice_receipt.v1",
            "circuit_id": circuit.circuit_id,
            "mode": mode,
            "argv": argv,
            "exit_code": int(completed.returncode),
            "stdout_sha256": hashlib.sha256((completed.stdout or "").encode("utf-8", errors="replace")).hexdigest(),
            "stderr_sha256": hashlib.sha256((completed.stderr or "").encode("utf-8", errors="replace")).hexdigest(),
            "artifacts": dict(sorted(artifacts.items())),
            "model_correctness": "TOOL_EXECUTED",
            "physical_correctness": "UNPROVEN",
        }
        receipt["receipt_sha256"] = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return receipt


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 96 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
