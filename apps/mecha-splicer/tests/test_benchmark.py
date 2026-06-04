from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_capability_benchmark_script(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    out_rel = "dist_ready_for_sale/benchmark_test"
    cmd = [
        "python3",
        "scripts/run_capability_benchmark.py",
        "--out",
        out_rel,
        "--limit",
        "4",
        "--simulation-fidelity",
        "high",
    ]
    subprocess.check_call(cmd, cwd=repo)

    out_dir = repo / out_rel
    assert (out_dir / "benchmark_results.json").exists()
    assert (out_dir / "benchmark_results.csv").exists()
    assert (out_dir / "BENCHMARK_REPORT.md").exists()

    rows = json.loads((out_dir / "benchmark_results.json").read_text(encoding="utf-8"))
    assert len(rows) == 4
    assert all("status" in r for r in rows)
