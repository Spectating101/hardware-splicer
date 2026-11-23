from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_dry_run(goal: str) -> str:
    completed = subprocess.run(
        ["make", "--dry-run", goal],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout + completed.stderr


def test_standard_ui_serve_target_uses_canonical_product_api() -> None:
    output = make_dry_run("splice-ui-serve")

    assert "main_serve()" in output and "--ui" in output
    assert "hardware_splicer.api:app --host" not in output
    assert "npm test" in output
    assert "npm run build" in output


def test_serve_runs_the_canonical_app_and_ui_package_stages_the_build() -> None:
    from hardware_splicer.cli_entry import CANONICAL_APP

    assert CANONICAL_APP == "hardware_splicer.product_api:app"
    serve = make_dry_run("serve")
    assert "from hardware_splicer.cli_entry import main_serve; main_serve()" in serve
    assert "--ui" in serve
    package = make_dry_run("ui-package")
    assert "npm ci && npm run build" in package
    assert "scripts/package_ui.py" in package


def test_unrelated_make_targets_remain_available() -> None:
    output = make_dry_run("doctor")

    assert "scripts/hardware_splicer.py doctor" in output


def test_headless_backend_checks_use_engine_tests_with_autorouting_disabled() -> None:
    output = make_dry_run("verify-headless-backend")

    assert "HARDWARE_SPLICER_AUTOROUTE=0" in output
    assert "tests/test_digital_engine.py" in output
    assert "tests/test_mcp_backend_gateway.py" in output
    assert "splice-ui" not in output
    assert "npm" not in output
