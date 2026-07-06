"""Safe read/list of KiCad artifacts under a build directory (for UI preview)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

KICAD_SUFFIXES = (".kicad_pcb", ".kicad_sch", ".kicad_pro")


def resolve_build_dir(build_dir: str | Path) -> Path:
    root = Path(build_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"build_dir not found: {root}")
    return root


def _relative_under_root(root: Path, candidate: Path) -> str:
    resolved = candidate.resolve()
    if resolved == root:
        raise ValueError("relative path must name a file inside build_dir")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes build_dir") from exc
    return str(resolved.relative_to(root))


def list_kicad_files(build_dir: str | Path) -> List[Dict[str, Any]]:
    root = resolve_build_dir(build_dir)
    rows: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in KICAD_SUFFIXES:
            continue
        rel = _relative_under_root(root, path)
        kind = "pcb" if path.suffix.lower() == ".kicad_pcb" else "schematic" if path.suffix.lower() == ".kicad_sch" else "project"
        rows.append(
            {
                "relative": rel,
                "kind": kind,
                "size_bytes": path.stat().st_size,
                "name": path.name,
            }
        )
    rows.sort(key=lambda row: (0 if row["kind"] == "pcb" else 1 if row["kind"] == "schematic" else 2, row["relative"]))
    return rows


def read_build_file(build_dir: str | Path, relative: str) -> Dict[str, Any]:
    root = resolve_build_dir(build_dir)
    rel = relative.strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("invalid relative path")
    target = (root / rel).resolve()
    rel_check = _relative_under_root(root, target)
    if not target.is_file():
        raise ValueError(f"file not found: {rel_check}")
    if target.suffix.lower() not in KICAD_SUFFIXES:
        raise ValueError("only KiCad preview files are served via this endpoint")
    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "relative": rel_check,
        "name": target.name,
        "kind": "pcb" if target.suffix.lower() == ".kicad_pcb" else "schematic",
        "size_bytes": target.stat().st_size,
        "content": text,
    }
