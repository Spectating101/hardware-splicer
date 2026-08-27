from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping


_DEFAULT_TIMEOUT_S = 60.0
_MAX_DIAGNOSTIC_CHARS = 4000

# Keep only runtime variables needed to start the selected Python/CadQuery
# environment. In particular, do not pass model-provider credentials or other
# application secrets into generated-code workers.
_ALLOWED_ENV_KEYS = {
    "HOME",
    "PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
}

_WORKER_CODE = r"""
import json
import runpy
import sys
from pathlib import Path

script_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
namespace = runpy.run_path(str(script_path))
assembly = namespace.get("result")
if assembly is None:
    raise RuntimeError("CadQuery script did not set `result`")

value = assembly.val() if hasattr(assembly, "val") else assembly
if not hasattr(value, "exportStl"):
    raise RuntimeError("CadQuery `result` does not expose exportStl")
value.exportStl(str(output_path))

if not output_path.is_file() or output_path.stat().st_size <= 0:
    raise RuntimeError("CadQuery worker did not create a non-empty STL")

print(json.dumps({"ok": True, "output": str(output_path), "bytes": output_path.stat().st_size}))
"""


def script_to_stl(py_code: str, out_path: Path, *, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
    """Execute generated CadQuery code outside the API process and export STL.

    This is process isolation, not a complete hostile-code sandbox. The worker
    receives a sanitized environment and is hard-killed on timeout. Higher-risk
    deployments should additionally run the service in a network-disabled,
    filesystem-restricted container.
    """

    if not isinstance(py_code, str) or not py_code.strip():
        raise ValueError("CadQuery code must be a non-empty string")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be greater than zero")

    destination = Path(out_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_path = _write_temp(py_code)
    temp_output = _temporary_output_path(destination)
    try:
        process = _start_worker(source_path, temp_output, env=_sanitized_environment())
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            stdout, stderr = process.communicate()
            raise TimeoutError(
                f"CadQuery worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc

        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )

        try:
            payload = json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery worker returned no valid structured result"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc

        if payload.get("ok") is not True or not temp_output.is_file() or temp_output.stat().st_size <= 0:
            raise RuntimeError(
                "CadQuery worker reported success without a non-empty STL"
                + _diagnostic_suffix(stdout, stderr)
            )

        os.replace(temp_output, destination)
    finally:
        Path(source_path).unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)


def _write_temp(code: str) -> str:
    """Write generated code to a private temporary file and return its path."""

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".py",
        mode="w",
        encoding="utf-8",
    ) as handle:
        handle.write(code)
        handle.flush()
        os.fsync(handle.fileno())
        return handle.name


def _temporary_output_path(destination: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=destination.suffix or ".stl",
        prefix=f".{destination.stem}.",
        dir=destination.parent,
    )
    path = Path(handle.name)
    handle.close()
    path.unlink(missing_ok=True)
    return path


def _sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    current = source or os.environ
    environment = {key: value for key, value in current.items() if key in _ALLOWED_ENV_KEYS}
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["HARDWARE_SPLICER_CAD_WORKER"] = "1"
    return environment


def _start_worker(source_path: str, output_path: Path, *, env: Mapping[str, str]) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {
        "args": [sys.executable, "-I", "-c", _WORKER_CODE, source_path, str(output_path)],
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": dict(env),
        "cwd": str(output_path.parent),
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(**kwargs)  # type: ignore[arg-type]


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            process.kill()
        return

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _diagnostic_suffix(stdout: str | None, stderr: str | None) -> str:
    details = []
    if stderr and stderr.strip():
        details.append(f"stderr={stderr.strip()[-_MAX_DIAGNOSTIC_CHARS:]!r}")
    if stdout and stdout.strip():
        details.append(f"stdout={stdout.strip()[-_MAX_DIAGNOSTIC_CHARS:]!r}")
    return f" ({'; '.join(details)})" if details else ""
