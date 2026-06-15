"""Load repo .env.local into os.environ (never log values)."""

from __future__ import annotations

import os
from pathlib import Path

from .runtime import ROOT


def load_env_local() -> bool:
    """Merge repo-root .env.local; existing process env wins."""
    path = ROOT / ".env.local"
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ and value:
                os.environ[key] = value
    except OSError:
        return False
    return True
