"""Nested authority-regression scan for engineering revision comparison."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_revision_diff as _target


_FLAGS = {
    "fabrication_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "release_authorized",
}


def _scan(value: Any, *, path: str, rows: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            if key in _FLAGS and item is True:
                rows.append(f"Candidate sets {child}=true outside a scoped human authorization record.")
            _scan(item, path=child, rows=rows)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan(item, path=f"{path}[{index}]", rows=rows)


def install_nested_authority_scan() -> None:
    if getattr(_target, "_nested_authority_scan_installed", False):
        return
    original = _target._authority_regressions

    def _authority_regressions(plan: Mapping[str, Any]) -> list[str]:
        rows = list(original(plan))
        machine = plan.get("machine_project")
        if isinstance(machine, Mapping):
            _scan(machine.get("metadata") or {}, path="machine_project.metadata", rows=rows)
            _scan(
                machine.get("discipline_payloads") or {},
                path="machine_project.discipline_payloads",
                rows=rows,
            )
        _scan(plan.get("manufacturing_closure") or {}, path="manufacturing_closure", rows=rows)
        _scan(plan.get("engineering_execution_plan") or {}, path="engineering_execution_plan", rows=rows)
        return list(dict.fromkeys(rows))

    _target._authority_regressions = _authority_regressions
    _target._nested_authority_scan_installed = True


install_nested_authority_scan()
