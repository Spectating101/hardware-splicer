"""Compatibility corrections for manufacturing collection and identity collisions.

Guided planning supplies both the raw intake and its normalized copy, so exact rows
are deduplicated before evaluation. Distinct rows that reuse one canonical connector,
harness, model, artifact, instance, or pin identity remain visible as blockers rather
than being silently resolved by last-write-wins indexing.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Mapping

from . import manufacturing_closure as _target


def _canonical(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "-").replace("_", "-")


def _render(row: Mapping[str, Any]) -> str:
    return json.dumps(dict(row), sort_keys=True, default=str, separators=(",", ":"))


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = _render(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _first(row: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def _simple_collision_checks(
    category: str,
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> list[Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        identity = _canonical(_first(row, *fields))
        if identity:
            grouped[identity].append(row)
    checks: list[Any] = []
    for identity, values in grouped.items():
        variants = {_render(row) for row in values}
        if len(variants) < 2:
            continue
        checks.append(
            _target._check(
                f"identity-collision-{category}-{identity}",
                "identity_collision",
                passed=False,
                message=(
                    f"Canonical {category} identity {identity!r} is reused by "
                    f"{len(variants)} conflicting declarations."
                ),
                source_ids=[identity],
                target_ids=[identity],
                unresolved_fields=["canonical_identity", "selected_declaration"],
                metadata={"category": category, "variants": [dict(row) for row in values]},
            )
        )
    return checks


def _pin_collision_checks(
    rows: list[dict[str, Any]],
    *,
    category: str,
    component_fields: tuple[str, ...],
    pin_fields: tuple[str, ...],
) -> list[Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        component = _canonical(_first(row, *component_fields))
        pin = _canonical(_first(row, *pin_fields))
        if component and pin:
            grouped[(component, pin)].append(row)
    checks: list[Any] = []
    for (component, pin), values in grouped.items():
        nets = {
            _canonical(_first(row, "net", "net_id", "signal", "function"))
            for row in values
        }
        nets.discard("")
        variants = {_render(row) for row in values}
        if len(nets) <= 1 and len(variants) <= 1:
            continue
        if len(nets) <= 1:
            continue
        checks.append(
            _target._check(
                f"identity-collision-{category}-{component}-{pin}",
                "identity_collision",
                passed=False,
                message=(
                    f"{category.replace('_', ' ').title()} identity {component}.{pin} "
                    f"declares conflicting nets {sorted(nets)}."
                ),
                source_ids=[component],
                target_ids=[pin, *sorted(nets)],
                unresolved_fields=["selected_net_identity"],
                metadata={"category": category, "variants": [dict(row) for row in values]},
            )
        )
    return checks


def _identity_collision_checks(data: Mapping[str, list[dict[str, Any]]]) -> list[Any]:
    checks: list[Any] = []
    checks.extend(
        _pin_collision_checks(
            data.get("electrical_pins", []),
            category="electrical_pin",
            component_fields=("component_id", "component", "device_id"),
            pin_fields=("pin", "pin_id", "pad", "port"),
        )
    )
    checks.extend(
        _pin_collision_checks(
            data.get("firmware_pins", []),
            category="firmware_pin",
            component_fields=("component_id", "controller_id", "device_id"),
            pin_fields=("physical_pin", "pin", "pad", "gpio"),
        )
    )
    checks.extend(_simple_collision_checks("connector", data.get("connectors", []), ("connector_id", "instance_id", "id", "name")))
    checks.extend(_simple_collision_checks("harness", data.get("harnesses", []), ("harness_id", "cable_id", "id", "name")))
    checks.extend(_simple_collision_checks("physical_instance", data.get("instances", []), ("instance_id", "serial", "id")))
    checks.extend(_simple_collision_checks("mount", data.get("mounts", []), ("mount_id", "interface_id", "id", "name")))
    checks.extend(_simple_collision_checks("cad_model", data.get("cad", []), ("cad_id", "model_id", "id", "name")))
    checks.extend(_simple_collision_checks("fabrication_artifact", data.get("fabrication", []), ("artifact_id", "id", "name", "path")))
    return checks


def install_manufacturing_collection_compatibility() -> None:
    if getattr(_target, "_deduplicated_collection_installed", False):
        return
    original_collect = _target._collect
    original_build = _target.build_manufacturing_closure

    def _collect(plan: Mapping[str, Any], intake: Mapping[str, Any]):
        collected = original_collect(plan, intake)
        return {key: _deduplicate(list(rows)) for key, rows in collected.items()}

    def build_manufacturing_closure(
        plan: Mapping[str, Any],
        *,
        intake: Mapping[str, Any] | None = None,
        project: Any = None,
    ):
        report = original_build(plan, intake=intake, project=project)
        data = _collect(plan, dict(intake or {}))
        collisions = _identity_collision_checks(data)
        existing_ids = {row.check_id for row in report.checks}
        additions = [row for row in collisions if row.check_id not in existing_ids]
        if not additions:
            return report
        checks = [*report.checks, *additions]
        required_evidence = [
            {
                "check_id": row.check_id,
                "category": row.category,
                "target_ids": row.target_ids,
                "request": f"Capture evidence closing: {row.message}",
                "required_fields": row.unresolved_fields,
            }
            for row in checks
            if row.blocking
        ]
        metadata = dict(report.metadata)
        metadata.update(
            {
                "blocking_check_count": len([row for row in checks if row.blocking]),
                "identity_collision_count": len(additions),
                "manufacturing_authorized": False,
                "fabrication_authorized": False,
                "release_authorized": False,
            }
        )
        return report.model_copy(
            update={
                "checks": checks,
                "required_evidence": required_evidence,
                "metadata": metadata,
            },
            deep=True,
        )

    _target._collect = _collect
    _target.build_manufacturing_closure = build_manufacturing_closure
    _target._deduplicated_collection_installed = True


install_manufacturing_collection_compatibility()
