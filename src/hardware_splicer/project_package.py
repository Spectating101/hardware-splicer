"""Closure wrapper around the mature project-package generator.

The underlying package generation logic remains byte-for-byte preserved in
:mod:`hardware_splicer.project_package_core`. This compatibility surface adds a
post-generation manufacturing reconciliation gate without forcing every existing
caller to change imports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from . import project_package_core as _core
from .manufacturing_reconciliation import apply_manufacturing_reconciliation

SCHEMA_VERSION = _core.SCHEMA_VERSION
render_project_page_md = _core.render_project_page_md


def _build_graph(
    root: Path,
    result: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    graph = _core._read_json(root / "build_compilation" / "build_graph.json")
    if graph:
        return graph
    payload = dict(result or {})
    compose_result = payload.get("compose_result")
    if isinstance(compose_result, Mapping):
        candidate = compose_result.get("graph")
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return {}


def build_project_package(
    build_dir: str | Path,
    *,
    result: Mapping[str, Any] | None = None,
    source: str = "auto",
) -> Dict[str, Any]:
    """Build a project package and attach manufacturing reconciliation."""

    root = Path(build_dir).resolve()
    package = _core.build_project_package(root, result=result, source=source)
    return apply_manufacturing_reconciliation(
        package,
        build_graph=_build_graph(root, result),
    )


def write_project_package_artifacts(
    build_dir: str | Path,
    *,
    result: Mapping[str, Any] | None = None,
    source: str = "auto",
    candidate: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Write package artifacts, then atomically enforce reconciliation gates."""

    root = Path(build_dir).resolve()
    output = _core.write_project_package_artifacts(
        root,
        result=result,
        source=source,
        candidate=candidate,
    )
    package = apply_manufacturing_reconciliation(
        dict(output.get("package") or {}),
        build_graph=_build_graph(root, result),
    )

    package_path = root / "PROJECT_PACKAGE.json"
    page_path = root / "PROJECT_PAGE.md"
    package_path.write_text(json.dumps(package, indent=2), encoding="utf-8")
    page_path.write_text(_core.render_project_page_md(package), encoding="utf-8")

    output["package"] = package
    output["gates"] = package.get("gates")
    artifacts = dict(output.get("artifacts") or {})
    artifacts["project_package"] = str(package_path)
    artifacts["project_page"] = str(page_path)
    output["artifacts"] = artifacts
    return output


def __getattr__(name: str) -> Any:
    """Preserve access to non-overridden helpers during the compatibility period."""

    return getattr(_core, name)
