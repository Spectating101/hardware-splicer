from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from hardware_splicer.integration_stack import IntegrationStack


SCHEMA_VERSION = "hardware_splicer.evidence_salvage_bridge.v1"

_DONOR_EVIDENCE_SOURCES = {
    "board_vision",
    "functional_salvage",
    "donor_functional_salvage",
    "circuit_functional_salvage",
    "donor_interface_contract",
    "manual_donor_interface",
}
_FIRMWARE_INTERFACE_TOKENS = (
    "actuator_driver",
    "motor driver",
    "motor_driver",
    "h-bridge",
    "hbridge",
    "stepper driver",
    "relay driver",
    "load switch",
    "sensor interface",
    "sensor_interface",
    "serial bridge",
    "usb_serial_bridge",
    "uart bridge",
    "control interface",
)


def _block_key(row: Mapping[str, Any]) -> str:
    return str(row.get("block_id") or row.get("name") or json.dumps(dict(row), sort_keys=True, default=str))


def _has_donor_evidence_shape(row: Mapping[str, Any]) -> bool:
    source = str(row.get("source") or "").strip().lower()
    if source in _DONOR_EVIDENCE_SOURCES:
        return True
    return bool(
        row.get("connector_refs")
        or row.get("evidence_gates")
        or row.get("missing_evidence")
        or row.get("required_tests")
        or row.get("source_refs")
    )


def _is_firmware_interface_block(row: Mapping[str, Any]) -> bool:
    """Return true only for opaque donor blocks with firmware-facing controls.

    Inventory primitives such as a bare motor, a known ESP32 board, or a donor-board
    container are not interfaces. Generating signal/polarity/controller-pin gates for
    those rows creates fictitious work and can prevent a valid physical scenario from
    ever closing. This bridge currently owns firmware-facing interface contracts; other
    evidence types should use role-specific contracts/recipes rather than this motor-
    control discovery recipe.
    """
    if not _has_donor_evidence_shape(row):
        return False
    text = " ".join(
        [
            str(row.get("function_type") or ""),
            str(row.get("name") or ""),
            " ".join(str(value) for value in (row.get("capabilities") or [])),
        ]
    ).lower()
    return any(token in text for token in _FIRMWARE_INTERFACE_TOKENS)


def _collect_reusable_blocks(package: Mapping[str, Any]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def take(values: Iterable[Any]) -> None:
        for raw in values:
            if not isinstance(raw, Mapping):
                continue
            row = dict(raw)
            key = _block_key(row)
            if key in seen:
                continue
            seen.add(key)
            blocks.append(row)

    splice_plan = package.get("splice_plan")
    if isinstance(splice_plan, Mapping):
        take(splice_plan.get("reusable_blocks") or [])
    take(package.get("reusable_blocks") or [])
    donor_context = package.get("donor_context")
    if isinstance(donor_context, Mapping):
        take(donor_context.get("reusable_blocks") or [])
        fs = donor_context.get("functional_salvage")
        if isinstance(fs, Mapping):
            take(fs.get("reusable_blocks") or [])
    return blocks


def _partition_interface_blocks(package: Mapping[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    selected: List[Dict[str, Any]] = []
    ignored: List[Dict[str, Any]] = []
    for row in _collect_reusable_blocks(package):
        if _is_firmware_interface_block(row):
            selected.append(row)
        else:
            ignored.append(
                {
                    "block_id": row.get("block_id"),
                    "board_id": row.get("board_id"),
                    "name": row.get("name"),
                    "function_type": row.get("function_type"),
                    "source": row.get("source"),
                    "reason": "not_an_opaque_firmware_control_interface",
                }
            )
    return selected, ignored


def _iter_reusable_blocks(package: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Compatibility helper returning only firmware-interface donor blocks."""
    selected, _ = _partition_interface_blocks(package)
    return selected


def attach_evidence_first_integrations(
    salvage_package: Mapping[str, Any],
    *,
    out_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Attach evidence contracts and authority decisions to an existing package.

    This is a compatibility seam: existing graph generation remains untouched, while
    downstream firmware and partner-facing claims can read the stricter authority
    result and block on unresolved donor interfaces.
    """

    package = dict(salvage_package)
    build_id = str(package.get("recommended_build_id") or "salvage-build")
    stack = IntegrationStack(graph_id=f"salvage:{build_id}")
    interface_blocks, ignored_blocks = _partition_interface_blocks(package)
    contracts = stack.ingest_functional_salvage(interface_blocks)
    interface_packages = [stack.build_interface_package(c.interface_id) for c in contracts]

    driver_contracts = [
        c
        for c in contracts
        if "driver" in c.functional_role.lower()
        or any(
            str(ref.get("module_id") or "") in {"l298n", "a4988-stepper"}
            for ref in c.reference_equivalents
        )
    ]
    unresolved_drivers = [c for c in driver_contracts if not c.can_generate_firmware()]
    firmware_authorized = not unresolved_drivers

    firmware = dict(package.get("firmware_scaffold") or {})
    firmware["evidence_authorized"] = firmware_authorized
    if unresolved_drivers:
        firmware["status"] = "blocked_needs_donor_control_interface"
        firmware["authority_blockers"] = [
            {
                "interface_id": c.interface_id,
                "virtual_module_id": c.virtual_module_id,
                "unresolved_fields": c.unresolved_fields(),
            }
            for c in unresolved_drivers
        ]
    package["firmware_scaffold"] = firmware

    authority = {
        "schema_version": SCHEMA_VERSION,
        "firmware_authorized": firmware_authorized,
        "power_authorized": False,
        "interface_contract_count": len(contracts),
        "ignored_reusable_block_count": len(ignored_blocks),
        "unresolved_driver_interfaces": [c.interface_id for c in unresolved_drivers],
        "claim_boundary": (
            "Generated design artifacts are candidates only. Power and function claims remain "
            "blocked until required donor interface measurements pass."
        ),
    }
    legacy_modules = [
        dict(row)
        for row in (package.get("resolved_modules") or [])
        if isinstance(row, Mapping)
    ]
    donor_sources = {
        "donor_functional_salvage",
        "circuit_functional_salvage",
        "donor_interface_contract",
    }
    non_donor_modules = [
        row for row in legacy_modules if str(row.get("source") or "") not in donor_sources
    ]
    canonical_donor_modules = [c.to_resolved_module() for c in contracts]
    authority_modules = non_donor_modules + canonical_donor_modules

    package["authority_resolved_modules"] = authority_modules
    package["evidence_integrations"] = {
        "schema_version": SCHEMA_VERSION,
        "authority": authority,
        "evidence_graph": stack.evidence_graph.to_dict(),
        "interfaces": interface_packages,
        "ignored_reusable_blocks": ignored_blocks,
        "authority_resolved_modules": authority_modules,
        "compatibility": {
            "mode": "legacy_graph_projection" if canonical_donor_modules else "native",
            "legacy_catalog_projection": [
                row
                for row in legacy_modules
                if str(row.get("source") or "") in donor_sources
            ],
            "claim_boundary": (
                "Legacy catalog rows may support existing graph rendering only; "
                "their pin semantics are not authority-bearing."
            ),
        },
    }

    if out_dir is not None:
        root = Path(out_dir)
        root.mkdir(parents=True, exist_ok=True)
        evidence_dir = root / "evidence_integrations"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "AUTHORITY.json").write_text(
            json.dumps(authority, indent=2), encoding="utf-8"
        )
        (evidence_dir / "EVIDENCE_GRAPH.json").write_text(
            json.dumps(stack.evidence_graph.to_dict(), indent=2), encoding="utf-8"
        )
        for index, contract in enumerate(contracts, start=1):
            stack.write_package(contract.interface_id, evidence_dir / f"interface-{index:02d}")
        package["evidence_integrations"]["artifact_dir"] = str(evidence_dir)

    return package


def build_intake_salvage_package_evidence_first(**kwargs: Any) -> Dict[str, Any]:
    """Run the current salvage planner, then attach the stricter integration layer."""

    from hardware_splicer.salvage_bridge import build_intake_salvage_package

    out_dir = kwargs.pop("evidence_out_dir", None)
    package = build_intake_salvage_package(**kwargs)
    return attach_evidence_first_integrations(package, out_dir=out_dir)
