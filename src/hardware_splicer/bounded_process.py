"""Bounded subprocess runner: cap captured output and always reap the group.

A flooding child must not fill RAM. stdout/stderr are drained on background
threads that keep only a small tail. Timeouts and unexpected errors kill the
process group (``killpg``) and the child is always reaped.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TAIL_BYTES = 8192
DEFAULT_READ_CHUNK = 65536


class BoundedProcessError(RuntimeError):
    """The child timed out or could not be started."""

    def __init__(self, message: str, *, timed_out: bool = False, returncode: int | None = None) -> None:
        super().__init__(message)
        self.timed_out = timed_out
        self.returncode = returncode


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    returncode: int
    stdout_tail: bytes
    stderr_tail: bytes
    timed_out: bool


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def wait_leader_and_kill_group(proc: subprocess.Popen[bytes], timeout_s: float) -> bool:
    """Wait for the group leader, then kill whatever is left in its process group. Returns True on timeout.

    The leader is observed with ``WNOWAIT`` so it stays an unreaped zombie while the group is killed. That keeps its pid,
    which is the group id, reserved: a descendant that outlived the leader (and still holds the output pipes) is killed,
    and the id cannot have been handed to an unrelated process in between. Only then is the leader reaped.
    """

    deadline = time.monotonic() + max(0.0, float(timeout_s))
    timed_out = False
    while True:
        try:
            state = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            break
        if state is not None:
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
        time.sleep(0.005)
    _kill_process_group(proc.pid)
    _reap(proc)
    return timed_out


def _tail_reader(stream: Any, limit: int, sink: list[bytes], done: threading.Event) -> None:
    buf = bytearray()
    try:
        while True:
            chunk = stream.read(DEFAULT_READ_CHUNK)
            if not chunk:
                break
            buf.extend(chunk)
            overflow = len(buf) - limit
            if overflow > 0:
                del buf[:overflow]
    except Exception:
        pass
    finally:
        sink.append(bytes(buf))
        done.set()


def _reap(proc: subprocess.Popen[bytes]) -> int:
    try:
        proc.wait()
    except Exception:
        return int(proc.returncode) if proc.returncode is not None else -1
    return int(proc.returncode) if proc.returncode is not None else -1


def run_bounded(
    cmd: Sequence[str],
    *,
    timeout_s: float,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    tail_bytes: int = DEFAULT_TAIL_BYTES,
) -> BoundedProcessResult:
    """Run ``cmd`` in a new session. Captured output is capped at ``tail_bytes``."""

    try:
        proc = subprocess.Popen(
            list(cmd),
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            # Unbuffered, so closing a pipe never waits on a lock held by a reader thread that is blocked in read().
            bufsize=0,
        )
    except FileNotFoundError as exc:
        raise BoundedProcessError("executable not found", returncode=None) from exc

    stdout_sink: list[bytes] = []
    stderr_sink: list[bytes] = []
    stdout_done = threading.Event()
    stderr_done = threading.Event()
    stdout_thread = threading.Thread(
        target=_tail_reader,
        args=(proc.stdout, tail_bytes, stdout_sink, stdout_done),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tail_reader,
        args=(proc.stderr, tail_bytes, stderr_sink, stderr_done),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        try:
            # Always kills the group afterwards, not only on timeout: a leader that exits while a descendant keeps the
            # pipes open must not leave that descendant running or make the readers wait for it.
            timed_out = wait_leader_and_kill_group(proc, timeout_s)
        except BaseException:
            _kill_process_group(proc.pid)
            _reap(proc)
            raise
    finally:
        stdout_done.wait(timeout=2.0)
        stderr_done.wait(timeout=2.0)
        stdout_thread.join(timeout=2.0)
        stderr_thread.join(timeout=2.0)
        if proc.stdout is not None:
            try:
                proc.stdout.close()
            except Exception:
                pass
        if proc.stderr is not None:
            try:
                proc.stderr.close()
            except Exception:
                pass
        if proc.returncode is None:
            _kill_process_group(proc.pid)
            _reap(proc)

    if timed_out:
        raise BoundedProcessError(
            f"timed out after {timeout_s}s",
            timed_out=True,
            returncode=proc.returncode,
        )
    return BoundedProcessResult(
        returncode=int(proc.returncode) if proc.returncode is not None else -1,
        stdout_tail=stdout_sink[0] if stdout_sink else b"",
        stderr_tail=stderr_sink[0] if stderr_sink else b"",
        timed_out=False,
    )
