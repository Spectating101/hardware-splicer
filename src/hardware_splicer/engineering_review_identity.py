"""Resolve external engineering findings to canonical Hardware Splicer identity.

External analyzers commonly report display references such as ``R12`` or ``VBUS``.
Those strings are useful evidence locations, but they are not themselves canonical
project identity. This module resolves only exact IDs and explicit identity aliases,
records ambiguity, and leaves unmatched findings at project level. Resolution never
raises external authority above ``observed``.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

from .build_files import resolve_build_dir
from .electrical_design import ElectricalDesign
from .machine_project import MachineProject

SCHEMA_VERSION = "hardware_splicer.engineering_review_resolved.v1"
AUTHORITY_CEILING = "observed"

_COMPONENT_IDENTITY_KEYS = (
    "canonical_component_id",
    "electrical_component_id",
    "source_component_id",
    "kicad_reference",
    "reference",
    "ref",
    "module_id",
)
_NET_IDENTITY_KEYS = (
    "canonical_net_id",
    "electrical_net_id",
    "source_net_id",
    "source_net_ids",
    "kicad_net_name",
    "net_name",
    "net",
)
_INTERFACE_IDENTITY_KEYS = (
    "canonical_interface_id",
    "electrical_net_id",
    "canonical_net_id",
    "source_net_id",
    "source_net_ids",
    "kicad_net_name",
    "net_name",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lookup_keys(value: Any) -> tuple[str, ...]:
    text = _text(value)
    if not text:
        return ()
    folded = text.casefold()
    return (f"exact:{text}", f"fold:{folded}")


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _identity_values(metadata: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    values: list[str] = []
    identity = metadata.get("identity")
    sources: list[Mapping[str, Any]] = [metadata]
    if isinstance(identity, Mapping):
        sources.append(identity)
    for source in sources:
        for key in keys:
            values.extend(_values(source.get(key)))
    return values


def _add(index: MutableMapping[str, set[str]], alias: Any, canonical_id: str) -> None:
    for key in _lookup_keys(alias):
        index.setdefault(key, set()).add(canonical_id)


def _add_many(
    index: MutableMapping[str, set[str]],
    aliases: Iterable[Any],
    canonical_id: str,
) -> None:
    for alias in aliases:
        _add(index, alias, canonical_id)


def _resolve(index: Mapping[str, set[str]], value: Any) -> dict[str, Any]:
    text = _text(value)
    matches: set[str] = set()
    for key in _lookup_keys(text):
        matches.update(index.get(key, set()))
    ordered = sorted(matches)
    if len(ordered) == 1:
        return {"input": text, "status": "resolved", "canonical_id": ordered[0]}
    if ordered:
        return {"input": text, "status": "ambiguous", "candidate_ids": ordered}
    return {"input": text, "status": "unresolved"}


def _electrical_indexes(design: ElectricalDesign) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    component_index: dict[str, set[str]] = {}
    net_index: dict[str, set[str]] = {}

    for component in design.components:
        aliases = [component.component_id, component.reference]
        aliases.extend(_identity_values(component.metadata, _COMPONENT_IDENTITY_KEYS))
        _add_many(component_index, aliases, component.component_id)

    for net in design.nets:
        aliases = [net.net_id, net.name]
        aliases.extend(_identity_values(net.metadata, _NET_IDENTITY_KEYS))
        _add_many(net_index, aliases, net.net_id)

    return component_index, net_index


def _machine_indexes(project: MachineProject | None) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    component_index: dict[str, set[str]] = {}
    interface_index: dict[str, set[str]] = {}
    if project is None:
        return component_index, interface_index

    for component in project.components:
        aliases = [component.component_id]
        aliases.extend(_identity_values(component.metadata, _COMPONENT_IDENTITY_KEYS))
        _add_many(component_index, aliases, component.component_id)

    for interface in project.interfaces:
        aliases = [interface.interface_id]
        aliases.extend(_identity_values(interface.metadata, _INTERFACE_IDENTITY_KEYS))
        _add_many(interface_index, aliases, interface.interface_id)

    return component_index, interface_index


def _resolved_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row["canonical_id"])
            for row in rows
            if row.get("status") == "resolved" and row.get("canonical_id")
        }
    )


def _status_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"resolved": 0, "ambiguous": 0, "unresolved": 0}
    for row in rows:
        status = str(row.get("status") or "unresolved")
        counts[status if status in counts else "unresolved"] += 1
    return counts


def resolve_engineering_review(
    review: Mapping[str, Any],
    electrical_design: ElectricalDesign,
    machine_project: MachineProject | None = None,
) -> dict[str, Any]:
    """Attach deterministic canonical resolution to every external finding."""

    electrical_components, electrical_nets = _electrical_indexes(electrical_design)
    machine_components, machine_interfaces = _machine_indexes(machine_project)

    resolved_findings: list[dict[str, Any]] = []
    all_component_rows: list[dict[str, Any]] = []
    all_net_rows: list[dict[str, Any]] = []
    all_machine_component_rows: list[dict[str, Any]] = []
    all_machine_interface_rows: list[dict[str, Any]] = []

    for finding in review.get("findings") or []:
        if not isinstance(finding, Mapping):
            continue
        component_inputs = _values(finding.get("components"))
        net_inputs = _values(finding.get("nets"))

        component_rows = [_resolve(electrical_components, value) for value in component_inputs]
        net_rows = [_resolve(electrical_nets, value) for value in net_inputs]

        machine_component_rows: list[dict[str, Any]] = []
        for value in [*component_inputs, *_resolved_ids(component_rows)]:
            row = _resolve(machine_components, value)
            if row not in machine_component_rows:
                machine_component_rows.append(row)

        machine_interface_rows: list[dict[str, Any]] = []
        for value in [*net_inputs, *_resolved_ids(net_rows)]:
            row = _resolve(machine_interfaces, value)
            if row not in machine_interface_rows:
                machine_interface_rows.append(row)

        all_component_rows.extend(component_rows)
        all_net_rows.extend(net_rows)
        all_machine_component_rows.extend(machine_component_rows)
        all_machine_interface_rows.extend(machine_interface_rows)

        updated = copy.deepcopy(dict(finding))
        updated["authority"] = AUTHORITY_CEILING
        updated["identity_resolution"] = {
            "authority_ceiling": AUTHORITY_CEILING,
            "electrical_components": component_rows,
            "electrical_nets": net_rows,
            "machine_components": machine_component_rows,
            "machine_interfaces": machine_interface_rows,
            "canonical": {
                "electrical_component_ids": _resolved_ids(component_rows),
                "electrical_net_ids": _resolved_ids(net_rows),
                "machine_component_ids": _resolved_ids(machine_component_rows),
                "machine_interface_ids": _resolved_ids(machine_interface_rows),
            },
            "fully_resolved": all(
                row.get("status") == "resolved"
                for row in [*component_rows, *net_rows]
            ),
        }
        resolved_findings.append(updated)

    component_counts = _status_counts(all_component_rows)
    net_counts = _status_counts(all_net_rows)
    machine_component_counts = _status_counts(all_machine_component_rows)
    machine_interface_counts = _status_counts(all_machine_interface_rows)

    output = copy.deepcopy(dict(review))
    output["schema_version"] = SCHEMA_VERSION
    output["source_review"] = {
        "schema_version": review.get("schema_version"),
        "run_id": review.get("run_id"),
        "cache_key": review.get("cache_key"),
    }
    output["authority"] = {
        **dict(review.get("authority") or {}),
        "maximum": AUTHORITY_CEILING,
        "may_authorize_release": False,
    }
    output["findings"] = resolved_findings
    output["identity_resolution"] = {
        "electrical_design_id": electrical_design.design_id,
        "electrical_project_id": electrical_design.project_id,
        "machine_project_id": machine_project.project_id if machine_project else None,
        "finding_count": len(resolved_findings),
        "electrical_component_references": component_counts,
        "electrical_net_references": net_counts,
        "machine_component_references": machine_component_counts,
        "machine_interface_references": machine_interface_counts,
        "unresolved_reference_count": (
            component_counts["unresolved"]
            + component_counts["ambiguous"]
            + net_counts["unresolved"]
            + net_counts["ambiguous"]
        ),
        "statement": (
            "Canonical identity is added without changing analyzer severity or authority. "
            "Unmatched and ambiguous references remain explicit project-level evidence."
        ),
    }
    return output


def write_resolved_engineering_review(
    build_dir: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    """Atomically persist the resolved derivative beside the immutable source review."""

    root = resolve_build_dir(build_dir)
    path = root / "build_compilation" / "ENGINEERING_REVIEW_RESOLVED.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path
