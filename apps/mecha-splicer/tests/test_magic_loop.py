from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_magic_loop_script_smoke(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    cmd = [
        "python3",
        "scripts/circuit_mecha_magic_loop.py",
        "--out",
        str(tmp_path),
        "--max-iters",
        "2",
    ]
    subprocess.check_call(cmd, cwd=repo)

    result_path = tmp_path / "MAGIC_LOOP_RESULT.json"
    report_path = tmp_path / "MAGIC_LOOP_REPORT.md"
    assert result_path.exists()
    assert report_path.exists()

    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data.get("final_status") in {"pass", "fail"}
    assert isinstance(data.get("iterations"), list)
    assert len(data.get("iterations") or []) >= 1
