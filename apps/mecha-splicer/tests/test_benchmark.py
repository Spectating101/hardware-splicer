from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_capability_benchmark_script(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    cmd = [
        "python3",
        "scripts/run_capability_benchmark.py",
        "--out",
        str(tmp_path),
        "--limit",
        "4",
        "--simulation-fidelity",
        "high",
    ]
    subprocess.check_call(cmd, cwd=repo)

    assert (tmp_path / "benchmark_results.json").exists()
    assert (tmp_path / "benchmark_results.csv").exists()
    assert (tmp_path / "BENCHMARK_REPORT.md").exists()

    rows = json.loads((tmp_path / "benchmark_results.json").read_text(encoding="utf-8"))
    assert len(rows) == 4
    assert all("status" in r for r in rows)
