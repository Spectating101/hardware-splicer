"""Closure wrapper around the mature project-package generator.

The underlying package generation logic remains byte-for-byte preserved in
:mod:`hardware_splicer.project_package_core`. This compatibility surface adds a
post-generation manufacturing reconciliation gate without forcing every existing
caller to change imports.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping

from . import project_package_core as _core
from .manufacturing_reconciliation import apply_manufacturing_reconciliation
from .rover_power_evidence import apply_rover_power_evidence_gate

SCHEMA_VERSION = _core.SCHEMA_VERSION
def render_project_page_md(package: Mapping[str, Any]) -> str:
    """Append auditable physical-power tasks to the existing project page."""
    base = _core.render_project_page_md(package)
    report = package.get("rover_power_evidence") or {}
    if not isinstance(report, Mapping) or report.get("status") != "blocked":
        return base
    declared = dict(report.get("declared") or {})
    lines = [
        "",
        "## MOTOR POWER EVIDENCE — NOT AUTHORIZED TO ENERGIZE",
        "",
        "The following are **user-declared specifications, not physical measurements**.",
        "",
        f"- Battery nominal (declared): `{declared.get('battery_nominal_v')}` V",
        f"- Battery capacity (declared): `{declared.get('battery_capacity_mah')}` mAh",
        f"- Motor count (declared): `{declared.get('motor_count')}`",
        f"- Simultaneous stated motor stall-current sum: `{declared.get('simultaneous_stall_current_a')}` A (not a measured pack or driver capability)",
        "",
        "**Measurements authenticated in this report:** none. "
        "Bench-session records require separate instrumentation and review.",
        "",
        "### Unresolved power and thermal requirements",
    ]
    for issue in report.get("blockers") or []:
        if not isinstance(issue, Mapping):
            continue
        lines.append(f"- **{issue.get('code')}**: {issue.get('message')}")
    lines.extend([
        "",
        "### Required evidence before considering any power-on",
    ])
    for action in report.get("next_actions") or []:
        lines.append(f"- {action}")
    lines.extend([
        "",
        "L298 manufacturer reference: https://www.st.com/resource/en/datasheet/l298.pdf "
        "(table 4 is conditional test data, not this rover's measured voltage drop).",
        "",
    ])
    return base.rstrip() + "\n" + "\n".join(lines)



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


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_project_package(
    build_dir: str | Path,
    *,
    result: Mapping[str, Any] | None = None,
    source: str = "auto",
) -> Dict[str, Any]:
    """Build a project package and attach manufacturing reconciliation."""

    root = Path(build_dir).resolve()
    package = _core.build_project_package(root, result=result, source=source)
    intake = _core._read_json(root / "PROJECT_INTAKE.json")
    graph = _build_graph(root, result)
    checked = apply_manufacturing_reconciliation(package, build_graph=graph, intake=intake)
    return apply_rover_power_evidence_gate(checked, intake=intake, graph=graph)


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
    intake = _core._read_json(root / "PROJECT_INTAKE.json")
    graph = _build_graph(root, result)
    checked = apply_manufacturing_reconciliation(
        dict(output.get("package") or {}), build_graph=graph, intake=intake
    )
    package = apply_rover_power_evidence_gate(checked, intake=intake, graph=graph)

    package_path = root / "PROJECT_PACKAGE.json"
    page_path = root / "PROJECT_PAGE.md"
    _atomic_write_text(
        package_path,
        json.dumps(package, indent=2) + "\n",
    )
    _atomic_write_text(
        page_path,
        render_project_page_md(package),
    )

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
