from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .base import BackendResult, BackendStatus


PROJECTION_SCHEMA = "hardware_splicer.tscircuit_projection.v1"


def _safe_id(prefix: str, value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value).strip("_")
    return f"{prefix}_{cleaned or 'unknown'}"


def build_circuit_json_projection(
    *,
    modules: Iterable[Mapping[str, Any]],
    wires: Iterable[Mapping[str, Any]],
    project_name: str,
) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = [
        {
            "type": "source_project_metadata",
            "name": project_name,
            "software_used_string": "hardware-splicer",
        }
    ]
    for index, module in enumerate(modules):
        module_id = str(module.get("module_id") or module.get("moduleId") or f"module-{index}")
        instance_id = str(module.get("instance_id") or module.get("id") or f"m{index}")
        source_group_id = _safe_id("source_group", instance_id)
        elements.append(
            {
                "type": "source_group",
                "source_group_id": source_group_id,
                "name": instance_id,
                "is_subcircuit": True,
                "subcircuit_id": module_id,
                "hardware_splicer": {
                    "module_id": module_id,
                    "source": module.get("source"),
                    "interface_status": module.get("interface_status"),
                    "firmware_authorized": module.get("firmware_authorized"),
                    "reference_equivalents": module.get("reference_equivalents") or [],
                },
            }
        )
    for index, wire in enumerate(wires):
        start = wire.get("from") or {}
        end = wire.get("to") or {}
        elements.append(
            {
                "type": "source_trace",
                "source_trace_id": _safe_id("source_trace", str(wire.get("id") or index)),
                "connected_source_port_ids": [
                    _safe_id("source_port", f"{start.get('nodeId') or start.get('role')}_{start.get('pinId') or start.get('pin')}"),
                    _safe_id("source_port", f"{end.get('nodeId') or end.get('role')}_{end.get('pinId') or end.get('pin')}"),
                ],
                "hardware_splicer": {
                    "from": dict(start),
                    "to": dict(end),
                },
            }
        )
    return elements


def write_tscircuit_projection(
    *,
    modules: Iterable[Mapping[str, Any]],
    wires: Iterable[Mapping[str, Any]],
    project_name: str,
    out_path: str | Path,
) -> BackendResult:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = build_circuit_json_projection(
        modules=modules,
        wires=wires,
        project_name=project_name,
    )
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return BackendResult(
        backend="tscircuit",
        status=BackendStatus.SUCCESS,
        outputs=[str(path)],
        diagnostics=[
            "Projection preserves Hardware Splicer evidence metadata; external Circuit JSON validation remains a downstream gate."
        ],
    )
