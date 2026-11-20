"""Checkout paths come from state_paths.repo_root(), never from a module's own location.

An installed wheel lives in site-packages, so walking up from ``__file__`` lands in
the virtualenv instead of the checkout given by ``--repo-root`` /
``HARDWARE_SPLICER_REPO_ROOT``. Reaching package-internal files (``data/``,
``ui_dist``, ``tool_workers``) from ``__file__`` is fine.
"""

from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "hardware_splicer"
ALLOWED = {"state_paths.py"}  # owns the one checkout lookup
UP = re.compile(r"\.parents\[(\d+)\]|\.parent\b|os\.path\.dirname\(")


def _levels_up(line: str) -> int:
    tail = line[line.index("__file__"):]
    levels = 0
    for match in UP.finditer(tail):
        levels += int(match.group(1)) + 1 if match.group(1) is not None else 1
    if "os.path.dirname(" in line[: line.index("__file__")]:
        levels += line[: line.index("__file__")].count("os.path.dirname(")
    return levels


def test_no_module_walks_out_of_the_package_from_its_own_file():
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE)
        if relative.as_posix() in ALLOWED:
            continue
        # A top-level module may go up one level (to hardware_splicer/); a module in
        # a subpackage one more per level of nesting.
        allowed_up = len(relative.parts)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "__file__" in line and _levels_up(line) > allowed_up:
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert offenders == [], "use state_paths.repo_root() for checkout paths:\n" + "\n".join(offenders)


def test_the_guard_recognises_checkout_walks():
    assert _levels_up("ROOT = Path(__file__).resolve().parents[2]") == 3
    assert _levels_up("DATA = Path(__file__).resolve().parent / 'data'") == 1
    assert _levels_up("X = Path(__file__).parent.parent / 'data'") == 2
    assert _levels_up("X = os.path.dirname(os.path.dirname(__file__))") == 2


def test_repo_root_redirects_checkout_lookups(tmp_path, monkeypatch):
    from hardware_splicer import project_scene_api
    from hardware_splicer.state_paths import repo_root

    monkeypatch.setenv("HARDWARE_SPLICER_REPO_ROOT", str(tmp_path))
    assert repo_root() == tmp_path.resolve()
    assert project_scene_api._repo_root() == tmp_path.resolve()
