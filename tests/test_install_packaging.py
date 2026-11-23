"""Installed-package contract: package data, entry points and the doctor's install report."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "hardware_splicer"


def _package_data_patterns() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return config["tool"]["setuptools"]["package-data"]["hardware_splicer"]


def test_every_tracked_package_resource_is_declared_package_data():
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "src/hardware_splicer"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    patterns = _package_data_patterns()
    resources = [
        Path(name).relative_to("src/hardware_splicer").as_posix()
        for name in tracked
        if not name.endswith(".py")
    ]
    assert resources, "expected tracked package resources"
    missing = [name for name in resources if not any(fnmatch(name, pattern) for pattern in patterns)]
    assert missing == [], f"not shipped in the wheel: {missing}"


def test_firmware_templates_resolve_from_the_package():
    from hardware_splicer.device_application import TEMPLATE_DIR

    assert TEMPLATE_DIR.is_relative_to(PACKAGE)
    assert (TEMPLATE_DIR / "app_core.h").is_file()


def test_doctor_reports_install_mode_and_configured_checkout(tmp_path):
    repo = tmp_path / "checkout"
    (repo / "projects").mkdir(parents=True)
    env = {"PYTHONPATH": str(ROOT / "src"), "HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin",
           "HARDWARE_SPLICER_STATE_DIR": str(tmp_path / "state"),
           "HARDWARE_SPLICER_TMP_ROOT": str(tmp_path / "builds")}
    result = subprocess.run(
        [sys.executable, "-c", "from hardware_splicer.cli_entry import main_doctor; main_doctor()",
         "--repo-root", str(repo)],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    install = report["install"]
    assert install["mode"] == "checkout"
    assert install["repo_root"] == str(repo.resolve())
    assert install["repo_root_configured"] is True
    assert install["projects_available"] is True
    assert install["state_dir"] == str(tmp_path / "state")
    assert install["scratch_dir"] == str(tmp_path / "builds")
    assert report["app_roots"]["root"]["path"] == str(repo.resolve())


def test_missing_case_inputs_point_the_operator_at_a_checkout(tmp_path, monkeypatch):
    from dataclasses import replace

    import pytest

    from hardware_splicer import digital_cases as cases
    from hardware_splicer.digital_engine import DigitalRuntimeUnavailable, DigitalStudyEngine

    detached = replace(cases.CASES["fielddeck-5"], root=tmp_path / "no-checkout")
    monkeypatch.setitem(cases.CASES, "fielddeck-5", detached)
    engine = DigitalStudyEngine(project_root=tmp_path / "projects", job_db=tmp_path / "jobs.sqlite3")
    try:
        with pytest.raises(DigitalRuntimeUnavailable) as raised:
            engine.create(case_id="fielddeck-5")
    finally:
        engine.close()
    message = str(raised.value)
    assert "--repo-root" in message and "HARDWARE_SPLICER_REPO_ROOT" in message
    assert f"and {len(detached.inputs) - 3} more" in message
    assert len(message) < 400
