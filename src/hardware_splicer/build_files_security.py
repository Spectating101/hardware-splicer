"""Path and size guards for /v1/build-files/* (local file viewer boundary)."""

from __future__ import annotations

import os
from pathlib import Path

# KiCad text files can be large; cap served inline content.
DEFAULT_MAX_READ_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_KICAD_CONTENT_BYTES = 16 * 1024 * 1024


def max_read_bytes() -> int:
    raw = os.getenv("HARDWARE_SPLICER_MAX_BUILD_FILE_BYTES", "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return DEFAULT_MAX_READ_BYTES


def max_kicad_content_bytes() -> int:
    raw = os.getenv("HARDWARE_SPLICER_MAX_KICAD_CONTENT_BYTES", "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return DEFAULT_MAX_KICAD_CONTENT_BYTES


def output_roots() -> list[Path]:
    roots: list[Path] = []
    primary = os.getenv("HARDWARE_SPLICER_OUTPUT_ROOT", "/tmp/hardware_splicer_api").strip()
    if primary:
        roots.append(Path(primary).expanduser().resolve())
    extra = os.getenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", "").strip()
    if extra:
        for part in extra.split(os.pathsep):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    # De-dupe while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def allow_arbitrary_build_dir() -> bool:
    return os.getenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", "").lower() in {"1", "true", "yes", "on"}


def assert_build_dir_allowed(root: Path) -> None:
    """Reject build_dir outside trusted output roots unless dev override is set."""
    resolved = root.resolve()
    if allow_arbitrary_build_dir():
        return
    allowed = output_roots()
    for base in allowed:
        if resolved == base or base in resolved.parents:
            return
    primary = allowed[0] if allowed else Path("/tmp/hardware_splicer_api")
    raise ValueError(
        f"build_dir must be under HARDWARE_SPLICER_OUTPUT_ROOT ({primary}); "
        "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
    )


def assert_file_size(path: Path, *, max_bytes: int | None = None) -> None:
    limit = max_bytes if max_bytes is not None else max_read_bytes()
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"cannot stat file: {path.name}") from exc
    if size > limit:
        raise ValueError(f"file too large ({size} bytes; limit {limit})")
