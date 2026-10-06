"""Filesystem-derived live change summaries for a machine project.

A state is a cheap directory listing. It never reads snapshot bytes, never
follows symlinks, and never upgrades authority. The stream that consumes these
summaries is information only.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

_NUMBERED_JSON = re.compile(r"^[0-9]+\.json$")
_CHANGE_TYPES = (
    "revision.saved",
    "thread.created",
    "thread.event",
    "review.opened",
    "review.event",
    "artifact.pinned",
)


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _iter_entries(path: Path) -> Iterable[os.DirEntry[str]]:
    if _is_symlink(path):
        return
    try:
        if not path.is_dir():
            return
    except OSError:
        return
    try:
        with os.scandir(path) as iterator:
            yield from iterator
    except OSError:
        return


def _numbered_seq(entry: os.DirEntry[str]) -> int | None:
    if not _NUMBERED_JSON.fullmatch(entry.name):
        return None
    try:
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            return None
    except OSError:
        return None
    return int(entry.name.split(".", 1)[0])


def _max_numbered(directory: Path) -> int:
    highest = 0
    for entry in _iter_entries(directory):
        seq = _numbered_seq(entry)
        if seq is not None and seq > highest:
            highest = seq
    return highest


def _numbered_list(directory: Path) -> list[int]:
    values: list[int] = []
    for entry in _iter_entries(directory):
        seq = _numbered_seq(entry)
        if seq is not None:
            values.append(seq)
    return sorted(set(values))


def _child_dirs(directory: Path) -> list[str]:
    names: list[str] = []
    for entry in _iter_entries(directory):
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        names.append(entry.name)
    return names


def _seq_map(root: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for name in _child_dirs(root):
        mapping[name] = _max_numbered(root / name / "events")
    return mapping


def project_state(project_dir: str | Path) -> dict[str, Any]:
    """Return counters derived only from directory and file names."""

    root = Path(project_dir)
    return {
        "revision": _max_numbered(root / "revisions"),
        "threads": _seq_map(root / "threads"),
        "reviews": _seq_map(root / "reviews"),
        "pins": _numbered_list(root / "artifact_pins"),
    }


def _as_state(value: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = value or {}
    threads = raw.get("threads") if isinstance(raw.get("threads"), Mapping) else {}
    reviews = raw.get("reviews") if isinstance(raw.get("reviews"), Mapping) else {}
    pins = raw.get("pins") if isinstance(raw.get("pins"), list) else []
    return {
        "revision": int(raw.get("revision") or 0),
        "threads": {str(key): int(seq) for key, seq in threads.items()},
        "reviews": {str(key): int(seq) for key, seq in reviews.items()},
        "pins": sorted({int(item) for item in pins}),
    }


def _change(change_type: str, entity_id: str, seq: int | None) -> dict[str, Any]:
    return {"type": change_type, "id": entity_id, "seq": seq}


def _seq_changes(
    change_type: str,
    entity_id: str,
    old_seq: int,
    new_seq: int,
) -> list[dict[str, Any]]:
    return [_change(change_type, entity_id, seq) for seq in range(old_seq + 1, new_seq + 1)]


def diff_states(old: Mapping[str, Any] | None, new: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return deterministic change rows describing how ``new`` differs from ``old``."""

    before = _as_state(old)
    after = _as_state(new)
    changes: list[dict[str, Any]] = []

    for revision in range(before["revision"] + 1, after["revision"] + 1):
        changes.append(_change("revision.saved", str(revision), revision))

    old_threads = before["threads"]
    new_threads = after["threads"]
    created_threads = sorted(set(new_threads) - set(old_threads))
    for thread_id in created_threads:
        changes.append(_change("thread.created", thread_id, None))
    for thread_id in created_threads:
        # Seq 1 is the creation comment; only later events are thread.event.
        changes.extend(_seq_changes("thread.event", thread_id, 1, new_threads[thread_id]))
    for thread_id in sorted(set(new_threads) & set(old_threads)):
        changes.extend(
            _seq_changes("thread.event", thread_id, old_threads[thread_id], new_threads[thread_id])
        )

    old_reviews = before["reviews"]
    new_reviews = after["reviews"]
    for review_id in sorted(set(new_reviews) - set(old_reviews)):
        changes.append(_change("review.opened", review_id, None))
        changes.extend(_seq_changes("review.event", review_id, 0, new_reviews[review_id]))
    for review_id in sorted(set(new_reviews) & set(old_reviews)):
        changes.extend(
            _seq_changes("review.event", review_id, old_reviews[review_id], new_reviews[review_id])
        )

    old_pins = set(before["pins"])
    for revision in after["pins"]:
        if revision not in old_pins:
            changes.append(_change("artifact.pinned", str(revision), revision))

    return changes


__all__ = ["diff_states", "project_state", "_CHANGE_TYPES"]
