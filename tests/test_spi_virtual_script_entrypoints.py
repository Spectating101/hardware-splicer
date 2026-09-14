import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


@pytest.mark.parametrize(
    "script_name",
    [
        "capture_vendor_model.py",
        "import_vendor_model.py",
        "run_spi_virtual_model_campaign.py",
        "run_spi_virtual_repair_control.py",
        "run_spi_virtual_verification.py",
        "validate_captured_vendor_model.py",
    ],
)
def test_spi_operator_script_help_resolves_real_package(script_name: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / script_name), "--help"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()


def _run_json_script(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    return payload


def test_documented_virtual_verification_cli_executes() -> None:
    result = _run_json_script(str(SCRIPTS / "run_spi_virtual_verification.py"), "--case", "corpus")
    assert result["all_expectations_pass"] is True
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_documented_repair_control_cli_executes() -> None:
    result = _run_json_script(str(SCRIPTS / "run_spi_virtual_repair_control.py"), "--fault", "all")
    assert result["all_controls_pass"] is True
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_documented_model_campaign_cli_executes_without_captures() -> None:
    result = _run_json_script(str(SCRIPTS / "run_spi_virtual_model_campaign.py"))
    assert result["status"] == "model_capture_required"
    assert result["ready_execution_ids"] == []
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False
