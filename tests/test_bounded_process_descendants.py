"""Regressions found by an independent Codex review: a subprocess leader that exits must not leave its group running.

Each runner is exercised with a leader that exits at once while a descendant keeps both output pipes open and sleeps.
The runner must neither wait for the descendant, nor leave it running, nor hang closing the pipes it holds.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from hardware_splicer.bounded_process import run_bounded


def _alive(pid: int) -> bool:
    """A process that is gone or only a zombie awaiting reaping is not alive."""

    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return False
    return state not in {"Z", "X"}


def _wait_dead(pid: int, seconds: float = 3.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


# The leader exits at once while a descendant keeps both pipes open and sleeps. The runner must not wait for the
# descendant, must not leave it running, and must not hang closing the pipes it holds.
def _leader_with_lingering_child(pid_file: Path) -> list[str]:
    code = (
        "import os, sys, time\n"
        "p = os.fork()\n"
        "if p == 0:\n"
        f"    open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "    time.sleep(30)\n"
        "else:\n"
        "    time.sleep(0.3)\n"
    )
    return [sys.executable, "-c", code]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="process-group semantics checked through /proc")
def test_bounded_runner_kills_descendants_left_after_the_leader_exits(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    started = time.monotonic()
    result = run_bounded(_leader_with_lingering_child(pid_file), timeout_s=10)
    elapsed = time.monotonic() - started

    assert result.returncode == 0
    assert elapsed < 4, f"the runner waited {elapsed:.1f}s for a descendant it should have killed"
    child = int(pid_file.read_text())
    assert _wait_dead(child), "a descendant of the exited leader was left running"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="process-group semantics checked through /proc")
def test_routing_runner_kills_descendants_left_after_the_leader_exits(tmp_path: Path) -> None:
    from hardware_splicer import routing_engine

    pid_file = tmp_path / "child.pid"
    started = time.monotonic()
    result = routing_engine._run_process(
        _leader_with_lingering_child(pid_file), cwd=tmp_path, env={"PATH": os.environ.get("PATH", "/usr/bin")}, timeout_s=10
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0
    assert elapsed < 4, f"the runner waited {elapsed:.1f}s for a descendant it should have killed"
    assert _wait_dead(int(pid_file.read_text())), "a descendant of the exited leader was left running"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="process-group semantics checked through /proc")
def test_model3d_runner_kills_descendants_left_after_the_leader_exits(tmp_path: Path) -> None:
    from hardware_splicer.model3d import _run_kicad_cli

    pid_file = tmp_path / "child.pid"
    started = time.monotonic()
    completed = _run_kicad_cli(
        _leader_with_lingering_child(pid_file), timeout_s=10, cwd=tmp_path, env={"PATH": os.environ.get("PATH", "/usr/bin")}
    )
    elapsed = time.monotonic() - started

    assert completed.returncode == 0
    assert elapsed < 4, f"the runner waited {elapsed:.1f}s for a descendant it should have killed"
    assert _wait_dead(int(pid_file.read_text())), "a descendant of the exited leader was left running"
