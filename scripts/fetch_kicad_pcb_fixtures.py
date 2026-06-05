#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "examples" / "kicad_pcb_fixtures"
BOARD_DIR = DEST / "kicad_demos_9_0_2"
REF = "9.0.2"
API_ROOT = "https://gitlab.com/api/v4/projects/kicad%2Fcode%2Fkicad/repository/files"
RAW_ROOT = "https://gitlab.com/kicad/code/kicad/-/raw"

FIXTURES = [
    {
        "id": "custom_pads_test",
        "source_path": "demos/custom_pads_test/custom_pads_test.kicad_pcb",
        "why": "Small custom-pad stress board for footprint/pad and STEP export edge cases.",
    },
    {
        "id": "microwave",
        "source_path": "demos/microwave/microwave.kicad_pcb",
        "why": "RF-style board with unusual scale and geometry, useful for outline/placement extraction.",
    },
    {
        "id": "pic_programmer",
        "source_path": "demos/pic_programmer/pic_programmer.kicad_pcb",
        "why": "Medium through-hole board with many components and holes.",
    },
    {
        "id": "stickhub",
        "source_path": "demos/stickhub/StickHub.kicad_pcb",
        "why": "Compact modern embedded board with dense footprints and routing.",
    },
]


def main() -> int:
    BOARD_DIR.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for fixture in FIXTURES:
        source_path = fixture["source_path"]
        target = BOARD_DIR / Path(source_path).name
        data = _fetch(source_path)
        target.write_bytes(data)
        metrics = _kicad_metrics(target)
        rows.append(
            {
                **fixture,
                "file": str(target.relative_to(DEST)),
                "source_url": f"{RAW_ROOT}/{REF}/{source_path}",
                "license": "GPL-3.0-or-later",
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
                "kicad_cli_step_export": metrics,
            }
        )

    license_text = _fetch("LICENSE.GPLv3")
    license_path = DEST / "LICENSE.GPLv3.txt"
    license_path.write_bytes(license_text)

    manifest = {
        "schema_version": "hardware_splicer.kicad_pcb_fixtures.v1",
        "source": {
            "name": "KiCad official demo projects",
            "repository": "https://gitlab.com/kicad/code/kicad",
            "ref": REF,
            "license": "GPL-3.0-or-later",
            "license_file": str(license_path.relative_to(DEST)),
        },
        "fixtures": rows,
    }
    manifest_path = DEST / "SOURCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(DEST), "fixture_count": len(rows)}, indent=2))
    return 0


def _fetch(path: str) -> bytes:
    encoded = urllib.parse.quote(path, safe="")
    url = f"{API_ROOT}/{encoded}/raw?ref={urllib.parse.quote(REF, safe='')}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _kicad_metrics(path: Path) -> Dict[str, Any]:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return {"attempted": False, "ready": False, "reason": "kicad-cli not found"}
    version_proc = subprocess.run(
        [kicad_cli, "version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    version = (version_proc.stdout or version_proc.stderr or "").strip()
    with tempfile.TemporaryDirectory(prefix="hardware_splicer_kicad_fixture_") as tmp:
        step_path = Path(tmp) / f"{path.stem}.step"
        proc = subprocess.run(
            [kicad_cli, "pcb", "export", "step", "--force", "--output", str(step_path), str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return {
            "attempted": True,
            "ready": proc.returncode == 0 and step_path.exists() and step_path.stat().st_size > 0,
            "kicad_cli_version": version,
            "returncode": proc.returncode,
            "step_bytes": step_path.stat().st_size if step_path.exists() else 0,
        }


if __name__ == "__main__":
    raise SystemExit(main())
