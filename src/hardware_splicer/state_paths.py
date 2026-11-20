"""Default locations for durable server state (job database, projects, API outputs).

Precedence for every path here:

1. an explicit environment variable (``HARDWARE_SPLICER_STATE_DIR``,
   ``HARDWARE_SPLICER_JOB_DB``, ``HARDWARE_SPLICER_OUTPUT_ROOT``) wins unchanged;
2. in a source checkout, ``<checkout>/.cache/hardware-splicer/state`` (gitignored,
   next to the ``HARDWARE_SPLICER_TMP_ROOT`` scratch default), so two checkouts or
   worktrees never share a job database;
3. for an installed package, ``$XDG_STATE_HOME/hardware-splicer`` or
   ``~/.local/state/hardware-splicer``.

Nothing defaults to ``/tmp``: a shared temp directory let one checkout's server pick
up another checkout's jobs.
"""

from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


def checkout_root(package_dir: Path | None = None) -> Path | None:
    """Return the source checkout containing this package, or None when installed."""

    package = Path(package_dir) if package_dir is not None else _PACKAGE_DIR
    if package.parent.name != "src":
        return None
    root = package.parent.parent
    if (root / "pyproject.toml").is_file():
        return root
    return None


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else None


def user_state_dir() -> Path:
    xdg = _env_path("XDG_STATE_HOME")
    base = xdg if xdg is not None and xdg.is_absolute() else Path.home() / ".local" / "state"
    return base / "hardware-splicer"


def state_dir(package_dir: Path | None = None) -> Path:
    """Root for persistent server state. Not created here."""

    explicit = _env_path("HARDWARE_SPLICER_STATE_DIR")
    if explicit is not None:
        return explicit
    root = checkout_root(package_dir)
    if root is not None:
        return root / ".cache" / "hardware-splicer" / "state"
    return user_state_dir()


def job_db_path(package_dir: Path | None = None) -> Path:
    explicit = _env_path("HARDWARE_SPLICER_JOB_DB")
    if explicit is not None:
        return explicit
    return state_dir(package_dir) / "jobs.sqlite3"


def output_root(package_dir: Path | None = None) -> Path:
    """API-owned build outputs; projects live under ``<output_root>/projects`` by default."""

    explicit = _env_path("HARDWARE_SPLICER_OUTPUT_ROOT")
    if explicit is not None:
        return explicit
    return state_dir(package_dir) / "api"
