from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
E2E_SCRIPT = ROOT / "scripts" / "hardware_splicer_e2e.py"


def test_hardware_splicer_e2e_script_runs_full_chain():
    pytest.importorskip("uvicorn")

    result = subprocess.run(
        [sys.executable, str(E2E_SCRIPT), "--json"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=45,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["splicer3d_ok"] is True
    assert Path(data["bundle_file"]).exists()
    assert Path(data["hardware_bundle_file"]).exists()
    assert Path(data["manifest_file"]).exists()
    assert Path(data["artifacts"]["splicer3d_script"]).exists()
