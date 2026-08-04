from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_golden_semiconductor_fixture_e2e.py"


def test_golden_semiconductor_fixture_produces_blocked_verified_package(
    tmp_path: Path,
) -> None:
    out = tmp_path / "golden-semiconductor-fixture"
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
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    )

    report_path = out / "GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.json"
    markdown_path = out / "GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.md"
    package_path = out / "GOLDEN_SEMICONDUCTOR_FIXTURE_PACKAGE.zip"
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert package_path.is_file()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["scenario_id"] == "low_voltage_dut_validation_adapter"
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
    assert report["package"]["source_revision"] == 6
    assert report["package"]["file_count"] == 15
    assert report["package"]["path"] == package_path.name

    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        source_manifest = json.loads(
            archive.read("ENGINEERING_PACKAGE/SOURCE_MANIFEST.json").decode("utf-8")
        )
        blockers = json.loads(
            archive.read("ENGINEERING_PACKAGE/BLOCKERS.json").decode("utf-8")
        )["blockers"]
        authority = json.loads(
            archive.read("ENGINEERING_PACKAGE/AUTHORITY_STATE.json").decode("utf-8")
        )

    assert "ENGINEERING_PACKAGE/MANIFEST.json" in names
    assert "ENGINEERING_PACKAGE/REPAIR_LINEAGE.json" in names
    assert "ENGINEERING_PACKAGE/CONVERSATION_BRIEFINGS.json" in names
    assert source_manifest["raw_source_bytes_included"] is False
    assert len(source_manifest["registered_sources"]) == 6
    assert all("content" not in row for row in source_manifest["registered_sources"])
    assert len(blockers) >= 5
    assert authority["package_authorizes_physical_action"] is False
