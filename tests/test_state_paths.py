from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer import state_paths
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.jobs import JobBackend
from hardware_splicer.project_store import default_project_root

ENV = (
    "HARDWARE_SPLICER_STATE_DIR",
    "HARDWARE_SPLICER_JOB_DB",
    "HARDWARE_SPLICER_OUTPUT_ROOT",
    "HARDWARE_SPLICER_PROJECT_ROOT",
    "XDG_STATE_HOME",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def checkout(base: Path) -> Path:
    package = base / "src" / "hardware_splicer"
    package.mkdir(parents=True)
    (base / "pyproject.toml").write_text("[project]\nname='hardware-splicer'\n", encoding="utf-8")
    return package


def test_two_checkouts_get_different_default_databases(tmp_path):
    first = checkout(tmp_path / "main")
    second = checkout(tmp_path / "worktree")
    assert state_paths.job_db_path(first) == tmp_path / "main/.cache/hardware-splicer/state/jobs.sqlite3"
    assert state_paths.job_db_path(second) == tmp_path / "worktree/.cache/hardware-splicer/state/jobs.sqlite3"
    assert state_paths.output_root(first) != state_paths.output_root(second)


def test_this_checkout_defaults_inside_its_gitignored_cache():
    root = Path(state_paths.__file__).resolve().parents[2]
    assert state_paths.checkout_root() == root
    assert state_paths.state_dir() == root / ".cache" / "hardware-splicer" / "state"
    assert JobBackend.from_env().store.db_path == state_paths.job_db_path()
    assert default_project_root() == (state_paths.state_dir() / "api" / "projects").resolve()
    assert not str(state_paths.state_dir()).startswith("/tmp/hardware_splicer")


def test_environment_overrides_win(tmp_path, monkeypatch):
    package = checkout(tmp_path / "repo")
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    assert state_paths.state_dir(package) == tmp_path / "state"
    assert state_paths.job_db_path(package) == tmp_path / "state/jobs.sqlite3"
    assert state_paths.output_root(package) == tmp_path / "state/api"
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_DB", str(tmp_path / "elsewhere/jobs.db"))
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "out"))
    assert state_paths.job_db_path(package) == tmp_path / "elsewhere/jobs.db"
    assert state_paths.output_root(package) == tmp_path / "out"
    assert JobBackend.from_env().store.db_path == tmp_path / "elsewhere/jobs.db"
    engine = DigitalStudyEngine(project_root=tmp_path / "projects")
    try:
        assert engine.backend.store.db_path == tmp_path / "elsewhere/jobs.db"
    finally:
        engine.close()


def test_installed_package_uses_per_user_state(tmp_path, monkeypatch):
    package = tmp_path / "venv/lib/python3.13/site-packages/hardware_splicer"
    package.mkdir(parents=True)
    assert state_paths.checkout_root(package) is None
    assert state_paths.state_dir(package) == tmp_path / "home/.local/state/hardware-splicer"
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert state_paths.job_db_path(package) == tmp_path / "xdg/hardware-splicer/jobs.sqlite3"
    # A relative XDG_STATE_HOME is invalid per the spec and is ignored.
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")
    assert state_paths.state_dir(package) == tmp_path / "home/.local/state/hardware-splicer"


def test_a_src_layout_without_pyproject_is_not_a_checkout(tmp_path):
    package = tmp_path / "unpacked/src/hardware_splicer"
    package.mkdir(parents=True)
    assert state_paths.checkout_root(package) is None
    assert str(state_paths.state_dir(package)).startswith(str(tmp_path / "home"))
