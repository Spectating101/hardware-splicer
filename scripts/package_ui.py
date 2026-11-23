"""Stage the built UI for inclusion in Python wheels (run via make ui-package)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


def package_ui(source: Path, destination: Path) -> None:
    if not (source / "index.html").is_file():
        raise SystemExit(f"UI build missing: {source / 'index.html'}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    hashes = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.is_file() and path != destination / "manifest.json"
    }
    (destination / "manifest.json").write_text(
        json.dumps({"sha256": hashes}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    package_ui(root / "apps/splice-ui/dist", root / "src/hardware_splicer/ui_dist")
