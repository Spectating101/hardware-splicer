from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_golden_rover_jarvis_e2e.py"


def test_golden_rover_jarvis_e2e_produces_verified_package(tmp_path: Path) -> None:
    out = tmp_path / "golden-rover"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "HARDWARE_SPLICER_SKIP_VISION_LIVE": "1",
        "HARDWARE_SPLICER_OFFLINE_LLM": "1",
        "HARDWARE_SPLICER_OFFLINE_VISION": "1",
        "HARDWARE_SPLICER_OFFLINE_SALVAGE": "1",
        "QWEN_DISABLED": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"

    report_path = out / "GOLDEN_ROVER_JARVIS_E2E.json"
    markdown_path = out / "GOLDEN_ROVER_JARVIS_E2E.md"
    package_path = out / "GOLDEN_ROVER_ENGINEERING_PACKAGE.zip"
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert package_path.is_file()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["revision_chain"] == {
        "initial": 1,
        "proposal": 2,
        "decision": 3,
        "preview_failure": 4,
        "repair": 5,
        "conversation": 6,
        "package_record": 7,
    }
    assert all(row["passed"] for row in report["checks"])
    assert all(value is False for value in report["physical_authority"].values())
    assert report["package"]["path"] == package_path.name
    assert report["package"]["source_revision"] == 6
    assert report["package"]["file_count"] == 15

    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
    assert "ENGINEERING_PACKAGE/MANIFEST.json" in names
    assert "ENGINEERING_PACKAGE/ACTION_TRACE.json" in names
    assert "ENGINEERING_PACKAGE/REPAIR_LINEAGE.json" in names
    assert "ENGINEERING_PACKAGE/CONVERSATION_BRIEFINGS.json" in names
    assert "ENGINEERING_PACKAGE/AUTHORITY_STATE.json" in names
