from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Sequence


SCHEMA_VERSION = "hardware_splicer.backend_result.v1"


class BackendStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class BackendResult:
    backend: str
    status: BackendStatus
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    version: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    @property
    def ok(self) -> bool:
        return self.status == BackendStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        body = asdict(self)
        body["status"] = self.status.value
        body["ok"] = self.ok
        return body


def executable_version(executable: str, args: Sequence[str] = ("--version",)) -> Optional[str]:
    path = shutil.which(executable)
    if not path:
        return None
    try:
        proc = subprocess.run(
            [path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr or "").strip().splitlines()
    return text[0] if text else path


def run_command_backend(
    *,
    backend: str,
    command: Sequence[str],
    cwd: str | Path,
    inputs: Iterable[str] = (),
    expected_outputs: Iterable[str] = (),
    version: Optional[str] = None,
    timeout_s: int = 300,
) -> BackendResult:
    if not command or not shutil.which(command[0]):
        return BackendResult(
            backend=backend,
            status=BackendStatus.SKIPPED,
            inputs=list(inputs),
            diagnostics=[f"executable not found: {command[0] if command else '<empty>'}"],
            version=version,
        )
    try:
        proc = subprocess.run(
            list(command),
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return BackendResult(
            backend=backend,
            status=BackendStatus.FAILED,
            inputs=list(inputs),
            diagnostics=[f"command timed out after {timeout_s}s"],
            version=version,
        )
    except OSError as exc:
        return BackendResult(
            backend=backend,
            status=BackendStatus.FAILED,
            inputs=list(inputs),
            diagnostics=[str(exc)],
            version=version,
        )

    root = Path(cwd)
    outputs = [str(root / rel) for rel in expected_outputs if (root / rel).exists()]
    diagnostics = []
    if proc.stdout.strip():
        diagnostics.append(proc.stdout.strip()[-4000:])
    if proc.stderr.strip():
        diagnostics.append(proc.stderr.strip()[-4000:])
    status = BackendStatus.SUCCESS if proc.returncode == 0 else BackendStatus.FAILED
    return BackendResult(
        backend=backend,
        status=status,
        inputs=list(inputs),
        outputs=outputs,
        diagnostics=diagnostics,
        version=version,
    )
