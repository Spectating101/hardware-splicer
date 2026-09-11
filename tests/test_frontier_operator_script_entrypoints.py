from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = (
    "plan_frontier_operator_experiment.py",
    "preflight_codex_astra.py",
    "audit_codex_astra_trace.py",
    "prepare_codex_astra_case.py",
    "run_codex_astra_case.py",
)


@pytest.mark.parametrize("script_name", SCRIPTS)
def test_frontier_script_help_uses_installed_hardware_splicer_package(
    script_name: str,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / script_name
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    combined = completed.stdout + completed.stderr
    assert completed.returncode == 0, combined
    assert "usage:" in completed.stdout.lower()
    assert "scripts/hardware_splicer.py" not in combined
    assert "partially initialized module 'hardware_splicer'" not in combined
