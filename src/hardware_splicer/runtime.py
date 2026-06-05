from __future__ import annotations

import contextlib
import importlib.util
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Iterator, Optional


ROOT = Path(__file__).resolve().parents[2]
CIRCUIT_ROOT = ROOT / "apps" / "circuit-ai"
MECHA_ROOT = ROOT / "apps" / "mecha-splicer"
SPLICER3D_ROOT = ROOT / "apps" / "3d-splicer"
SPLICER3D_VENV_PYTHON = SPLICER3D_ROOT / ".venv" / "bin" / "python"


class ServiceStartError(RuntimeError):
    """Raised when a managed helper service exits before becoming healthy."""


def validate_app_roots() -> None:
    missing = [str(path) for path in (CIRCUIT_ROOT, MECHA_ROOT, SPLICER3D_ROOT) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Hardware-Splicer app roots: {', '.join(missing)}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def health_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False


def _process_output_tail(proc: subprocess.Popen[str], *, terminate: bool = False, limit: int = 4000) -> str:
    if proc.stdout is None:
        return ""
    try:
        if terminate and proc.poll() is None:
            proc.terminate()
        if terminate or proc.poll() is not None:
            stdout, _ = proc.communicate(timeout=3)
            return (stdout or "")[-limit:]
    except Exception as exc:
        return f"<failed to collect service output: {exc}>"
    return ""


def wait_for_health(
    url: str,
    *,
    timeout_s: float = 15.0,
    proc: Optional[subprocess.Popen[str]] = None,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if health_ok(url):
            return
        if proc is not None and proc.poll() is not None:
            tail = _process_output_tail(proc)
            detail = f"\nService output tail:\n{tail}" if tail else ""
            raise ServiceStartError(f"3D-Splicer exited before becoming healthy at {url}.{detail}")
        time.sleep(0.2)
    tail = _process_output_tail(proc, terminate=True) if proc is not None else ""
    detail = f"\nService output tail:\n{tail}" if tail else ""
    raise TimeoutError(f"3D-Splicer did not become healthy at {url}.{detail}")


def start_splicer3d(port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SPLICER3D_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    python_override = os.environ.get("SPLICER3D_PYTHON")
    python = (
        Path(python_override)
        if python_override
        else (SPLICER3D_VENV_PYTHON if SPLICER3D_VENV_PYTHON.exists() else Path(sys.executable))
    )
    return subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=SPLICER3D_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_process(proc: Optional[subprocess.Popen[str]]) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=5)


def ensure_circuit_import_path() -> None:
    path = str(CIRCUIT_ROOT)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    circuit_src = (CIRCUIT_ROOT / "src").resolve()
    existing = sys.modules.get("src")
    existing_paths = [Path(str(item)).resolve() for item in getattr(existing, "__path__", [])] if existing else []
    if existing is not None and circuit_src not in existing_paths:
        for module_name in list(sys.modules):
            if module_name == "src" or module_name.startswith("src."):
                sys.modules.pop(module_name, None)


@contextlib.contextmanager
def patched_env(values: Dict[str, Optional[str]]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _python_import_ok(python: Path, module: str) -> bool:
    if not python.exists():
        return False
    try:
        proc = subprocess.run(
            [str(python), "-c", f"import {module}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        return False


def runtime_status(*, splicer_url: str | None = None) -> Dict[str, object]:
    roots = {
        "root": ROOT,
        "circuit_ai": CIRCUIT_ROOT,
        "mecha_splicer": MECHA_ROOT,
        "splicer3d": SPLICER3D_ROOT,
    }
    app_roots = {
        name: {"path": str(path), "exists": path.exists(), "is_dir": path.is_dir()}
        for name, path in roots.items()
    }
    dependencies = {
        "fastapi": importlib.util.find_spec("fastapi") is not None,
        "uvicorn": importlib.util.find_spec("uvicorn") is not None,
        "cadquery": importlib.util.find_spec("cadquery") is not None,
        "ngspice": shutil.which("ngspice") is not None,
    }
    splicer_python_override = os.environ.get("SPLICER3D_PYTHON")
    splicer_python = (
        Path(splicer_python_override)
        if splicer_python_override
        else (SPLICER3D_VENV_PYTHON if SPLICER3D_VENV_PYTHON.exists() else Path(sys.executable))
    )
    splicer_dependencies = {
        "fastapi": _python_import_ok(splicer_python, "fastapi"),
        "uvicorn": _python_import_ok(splicer_python, "uvicorn"),
        "cadquery": _python_import_ok(splicer_python, "cadquery"),
    }
    status: Dict[str, object] = {
        "ok": all(row["exists"] for row in app_roots.values()),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "splicer3d_python": str(splicer_python),
        "splicer3d_local_venv": SPLICER3D_VENV_PYTHON.exists(),
        "app_roots": app_roots,
        "dependencies": dependencies,
        "splicer3d_dependencies": splicer_dependencies,
    }
    if splicer_url:
        status["splicer3d_health"] = {"url": splicer_url, "ok": health_ok(splicer_url)}
    return status
