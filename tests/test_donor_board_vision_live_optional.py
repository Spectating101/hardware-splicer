"""Optional live donor-board Qwen vision — requires API key."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.getenv("HARDWARE_SPLICER_RUN_VISION_LIVE", "").strip().lower() not in {"1", "true", "yes", "on"},
    reason="set HARDWARE_SPLICER_RUN_VISION_LIVE=1 to run live donor vision",
)
@pytest.mark.skipif(
    not (os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")),
    reason="QWEN_API_KEY or DASHSCOPE_API_KEY required for live donor vision",
)
def test_live_donor_board_vision_smoke() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vision_donor_live_smoke.py"), "--live", "--json"],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "HARDWARE_SPLICER_RUN_VISION_LIVE": "1",
        },
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "board_evidence" in proc.stdout or "component_count" in proc.stdout
