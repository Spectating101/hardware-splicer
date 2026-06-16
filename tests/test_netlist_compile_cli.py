"""CLI netlist-compile and compose --netlist-json (general engine)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "netlist_fixtures" / "json" / "usb_esp_pir.json"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    return env


def test_netlist_compile_cli(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hardware_splicer.py"),
            "netlist-compile",
            "--netlist",
            str(FIXTURE),
            "--out",
            str(tmp_path),
            "--json",
        ],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert int((payload.get("design_quality") or {}).get("kicad_drc_errors") or 0) == 0
    assert (tmp_path / "build_compilation" / "circuit_netlist.json").is_file()


def test_compose_netlist_json_alias(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hardware_splicer.py"),
            "compose",
            "--netlist-json",
            str(FIXTURE),
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "drc_pass=True" in proc.stdout
