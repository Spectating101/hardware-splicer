"""Donor board vision dry-run on synthetic test image."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "tests" / "data" / "donor_rc_board_sample.png"


@pytest.fixture(scope="module", autouse=True)
def ensure_donor_sample_image() -> None:
    if IMAGE.is_file():
        return
    script = ROOT / "scripts" / "generate_donor_test_image.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=ROOT)


def test_donor_image_exists():
    assert IMAGE.is_file()
    assert IMAGE.stat().st_size > 100


def test_donor_vision_dry_run_smoke():
    from hardware_splicer.board_vision_salvage import _analyze_board_image_path

    result = _analyze_board_image_path(
        IMAGE,
        goal="salvage RC motor driver",
        live=False,
        device_hint="RC toy motor board",
        symptoms=["motors do not spin"],
    )
    assert result.get("mode") == "dry_run"
    assert (result.get("preflight") or {}).get("image_sha256")


def test_vision_donor_smoke_script():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vision_donor_live_smoke.py")],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
