"""Canonical physical-identity boundary for salvage/inventory resolution.

Hardware Splicer may know what a donor block *does* without knowing what exact component
it *is*. This module keeps those epistemic states separate.

Model-first rules:
- explicit valid catalog ``module_id`` is a declared identity binding;
- a model may propose an exact/declared-equivalent catalog identity, but deterministic
  validation must find distinctive identity evidence in persisted part fields;
- generic functional similarity never becomes component identity;
- donor functional blocks preserve donor identity/capability and remain external unless
  they explicitly declare a valid catalog module;
- missing driver/power capabilities stay unresolved requirements rather than magic L298N,
  A4988, IRLZ44N, USB, or barrel substitutions;
- model/provider failure keeps identities unresolved.

Explicit offline compatibility may still delegate to the historical resolver/gap-fill
stack for disconnected demos and regression goldens.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, Sequence

from .integrations.catalog_context import build_salvage_catalog_context
from .pcb.module_registry import find_module
from .structured_part_roles import declared_part_role, structured_part_tokens


SCHEMA_VERSION = "hardware_splicer.module_resolution_truth.v1"
_ALLOWED_MATCH_KINDS = {"exact_identity", "declared_equivalent", "no_match"}
_IDENTITY_FIELDS = (
    "name",
    "model",
    "mpn",
    "part_number",
    "manufacturer_part_number",
    "sku",
)
_DECLARED_EQUIVALENT_FIELDS = (
    "catalog_equivalent_id",
    "equivalent_module_id",
    "catalog_module_id",
)
_GENERIC_IDENTITY_TOKENS = {
    "module", "board", "breakout", "sensor", "motor", "driver", "power", "supply",
    "controller", "relay", "mosfet", "transistor", "switch", "display", "camera",
    "servo", "stepper", "pump", "fan", "battery", "buck", "boost", "converter",
    "regulator", "adapter", "connector", "interface", "generic", "unknown", "uart",
    "usb", "i2c", "spi", "adc", "dc", "ac", "5v", "12v", "3v3",
}


def _tokenize(value: Any) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9]+", str(value or "")) if token}


def _identity_tokens_for_part(part: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in _IDENTITY_FIELDS:
        tokens.update(_tokenize(part.get(key)))
    return tokens


def _distinctive_module_tokens(module_id: str) -> set[str]:
    module = find_module(module_id) or {}
    tokens = _tokenize(module_id)
    tokens.update(_tokenize(module.get("label")))
    return {token for token in tokens if len(token) >= 4 and token not in _GENERIC_IDENTITY_TOKENS}


def _declared_equivalent_id(part: Mapping[str, Any]) -> str | None:
    for key in _DECLARED_EQUIVALENT_FIELDS:
        candidate = str(part.get(key) or "").strip()
        if candidate and find_module(candidate) is not None:
            return candidate
    return None


def _identity_binding_allowed(part: Mapping[str, Any], module_id: str, match_kind: str) -> tuple[bool, str]:
    if find_module(module_id) is None:
        return False, "proposed module_id is absent from the live catalog"
    if match_kind == "declared_equivalent":
        declared = _declared_equivalent_id(part)
        if declared == module_id:
            return True, "persisted declared-equivalent catalog identity"
        return False, "declared_equivalent proposal lacks a matching persisted equivalent ID"
    if match_kind != "exact_identity":
        return False, "only exact_identity or declared_equivalent may bind a catalog identity"
    part_tokens = _identity_tokens_for_part(part)
    distinctive = _distinctive_module_tokens(module_id)
    overlap = sorted(part_tokens & distinctive)
    if overlap:
        return True, "distinctive persisted identity token(s): " + ", ".join(overlap)
    return False, "no distinctive catalog identity token is present in persisted part identity fields"


def _catalog_role(module_id: str, part: Mapping[str, Any]) -> str:
    declared_role, _ = declared_part_role(part)
    declared_map = {
        "actuator": "act", "sensor": "sns", "power": "pwr", "controller": "mcu",
        "electrical": "misc", "structure": "misc",
    }
    if declared_role != "unknown":
        return declared_map.get(declared_role, "misc")
    module = find_module(module_id) or {}
    tokens = {
        str(value).strip().lower().replace("-", "_")
        for value in list(module.get("capabilityTags") or [])
        if str(value).strip()
    }
    tokens.add(str(module.get("category") or "").strip().lower().replace("-", "_"))
    if tokens & {"microcontroller", "controller", "compute", "wireless_mcu"}:
        return "mcu"
    if tokens & {"sensor", "sensor_or_adc", "environment_sensor", "distance_sensor", "imu"}:
        return "sns"
    if tokens & {"actuator_driver", "motor_driver", "driver", "h_bridge"}:
        return "drv"
    if tokens & {"motor", "dc_motor", "stepper_motor", "mechanical_motion"}:
        return "mot"
    if tokens & {"power", "power_source", "usb_power", "battery_power"}:
        return "pwr"
    if tokens & {"power_conversion", "buck", "boost", "regulator"}:
        return "buck"
    if tokens & {"relay", "switching"}:
        return "rly"
    if tokens & {"servo", "actuator"}:
        return "act"
    return "misc"


def _role_for_unresolved_part(part: Mapping[str, Any]) -> str:
    role, _ = declared_part_role(part)
    return {
        "actuator": "act", "sensor": "sns", "power": "pwr", "controller": "mcu",
        "electrical": "misc", "structure": "misc",
    }.get(role, "misc")


def _explicit_rows(parts: Sequence[Mapping[str, Any]]) -> tuple[list[Dict[str, Any]], list[int]]:
    rows: list[Dict[str, Any]] = []
    unresolved_indexes: list[int] = []
    for index, part in enumerate(parts):
        explicit = str(part.get("module_id") or "").strip()
        if explicit and find_module(explicit) is not None:
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "part_index": index,
                "instance_id": str(part.get("component_id") or part.get("instance_id") or f"part-{index + 1}"),
                "part_name": str(part.get("name") or explicit),
                "module_id": explicit,
                "role": _catalog_role(explicit, part),
                "source": "declared_catalog_identity",
                "identity_status": "declared",
                "confidence": 1.0,
                "matched_on": "explicit_module_id",
                "authority_effect": "none",
            })
        else:
            unresolved_indexes.append(index)
            if explicit:
                rows.append({
                    "schema_version": SCHEMA_VERSION,
                    "part_index": index,
                    "instance_id": str(part.get("component_id") or part.get("instance_id") or f"part-{index + 1}"),
                    "part_name": str(part.get("name") or explicit),
                    "module_id": None,
                    "role": _role_for_unresolved_part(part),
                    "source": "unresolved_identity",
                    "identity_status": "unresolved",
                    "declared_module_id": explicit,
                    "reason": "declared module_id is absent from the live catalog",
                    "confidence": 0.0,
                    "authority_effect": "none",
                })
    return rows, unresolved_indexes


def _identity_model_enabled() -> bool:
    if os.environ.get("HARDWARE_SPLICER_QWEN_SALVAGE", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    try:
        from .integrations.qwen_text_client import qwen_configured
        return qwen_configured()
    except Exception:
        return False


def _identity_prompt(parts: Sequence[Mapping[str, Any]], indexes: Sequence[int]) -> str:
    projected = []
    for index in indexes:
        part = parts[index]
        projected.append({
            "part_index": index,
            "name": part.get("name"),
            "model": part.get("model"),
            "mpn": part.get("mpn"),
            "part_number": part.get("part_number"),
            "manufacturer_part_number": part.get("manufacturer_part_number"),
            "sku": part.get("sku"),
            "type": part.get("type"),
            "role": part.get("role"),
            "category": part.get("category"),
            "catalog_equivalent_id": part.get("catalog_equivalent_id"),
            "equivalent_module_id": part.get("equivalent_module_id"),
            "voltage_v": part.get("voltage_v"),
            "current_a": part.get("current_a"),
        })
    return f"""Resolve physical inventory identity against Hardware Splicer's catalog.

Parts:
{json.dumps(projected, ensure_ascii=False, sort_keys=True, indent=2)}

Catalog (stable full view; this is not a goal-ranked shortlist):
{build_salvage_catalog_context(max_entries=240)}

Return JSON only:
{{
  "bindings": [
    {{"part_index": 0, "match_kind": "exact_identity | declared_equivalent | no_match", "module_id": "catalog id or null", "reasoning": "identity evidence only"}}
  ],
  "unresolved_questions": []
}}

Rules:
- This is PHYSICAL IDENTITY resolution, not functional substitution or architecture selection.
- Bind a catalog module only when the persisted name/model/MPN/part-number/SKU identifies that exact catalog item, or a persisted declared-equivalent ID explicitly names it.
- Generic category similarity is NOT identity. A generic DC motor is not automatically dc_motor_3v_6v; a generic MOSFET or AO3400 is not IRLZ44N; an unknown H-bridge is not L298N.
- Do not map a donor capability to a familiar representative module.
- If exact identity is not defensible, return no_match and leave the part external/unresolved.
- Never invent voltage/current/rating facts or module IDs.
- This step has no fabrication, flashing, power, motion, or release authority.
"""


def _unresolved_part_row(part: Mapping[str, Any], index: int, *, reason: str, rejected_module_id: str | None = None) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "part_index": index,
        "instance_id": str(part.get("component_id") or part.get("instance_id") or f"part-{index + 1}"),
        "part_name": str(part.get("name") or part.get("model") or f"part-{index + 1}"),
        "module_id": None,
        "role": _role_for_unresolved_part(part),
        "source": "unresolved_identity",
        "identity_status": "unresolved",
        "reason": reason,
        "confidence": 0.0,
        "authority_effect": "none",
    }
    if rejected_module_id:
        row["rejected_module_id"] = rejected_module_id
    return row


def resolve_inventory_identity(
    parts: Sequence[Mapping[str, Any]],
    *,
    goal: str = "",
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    """Resolve exact physical identity without functional catalog substitution."""
    from .integrations.llm_policy import offline_salvage_enabled

    part_rows = [deepcopy(dict(row)) for row in parts if isinstance(row, Mapping)]
    if offline_salvage_enabled():
        from .module_resolver import resolve_parts_to_modules_with_llm
        return resolve_parts_to_modules_with_llm(part_rows, goal=goal)

    rows, unresolved_indexes = _explicit_rows(part_rows)
    explicit_unresolved = {int(row["part_index"]) for row in rows if row.get("identity_status") == "unresolved"}
    model_indexes = [index for index in unresolved_indexes if index not in explicit_unresolved]
    meta: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": "model_first_identity",
        "legacy_heuristic_used": False,
        "explicit_binding_count": sum(row.get("identity_status") == "declared" for row in rows),
        "model": {"used": False},
    }

    if model_indexes and (llm_callable is not None or _identity_model_enabled()):
        prompt = _identity_prompt(part_rows, model_indexes)
        if llm_callable is None:
            from .integrations.qwen_text_client import call_qwen_chat
            response = call_qwen_chat(
                prompt,
                json_mode=True,
                stage="salvage_identity",
                system="Resolve exact persisted physical identity only; never perform functional substitution.",
                timeout_s=75,
            )
        else:
            response = llm_callable(
                prompt,
                json_mode=True,
                stage="salvage_identity",
                system="Resolve exact persisted physical identity only; never perform functional substitution.",
                timeout_s=75,
            )
        meta["model"] = {
            "used": bool(response.get("ok")),
            "provider": response.get("provider"),
            "model": response.get("model"),
            "reason": response.get("error") or response.get("reason"),
        }
        if response.get("ok"):
            try:
                parsed = json.loads(str(response.get("content") or "{}"))
            except json.JSONDecodeError:
                parsed = {}
            bindings = parsed.get("bindings") if isinstance(parsed, Mapping) else []
            by_index: Dict[int, Mapping[str, Any]] = {}
            for binding in list(bindings or []):
                if not isinstance(binding, Mapping):
                    continue
                try:
                    index = int(binding.get("part_index"))
                except (TypeError, ValueError):
                    continue
                by_index[index] = binding
            for index in model_indexes:
                part = part_rows[index]
                binding = by_index.get(index) or {}
                match_kind = str(binding.get("match_kind") or "no_match").strip()
                module_id = str(binding.get("module_id") or "").strip()
                if match_kind not in _ALLOWED_MATCH_KINDS:
                    match_kind = "no_match"
                allowed, basis = _identity_binding_allowed(part, module_id, match_kind) if module_id else (False, "model returned no exact catalog identity")
                if allowed:
                    rows.append({
                        "schema_version": SCHEMA_VERSION,
                        "part_index": index,
                        "instance_id": str(part.get("component_id") or part.get("instance_id") or f"part-{index + 1}"),
                        "part_name": str(part.get("name") or module_id),
                        "module_id": module_id,
                        "role": _catalog_role(module_id, part),
                        "source": "model_identity_proposed",
                        "identity_status": "model_proposed",
                        "identity_match_kind": match_kind,
                        "identity_basis": basis,
                        "confidence": 0.0,
                        "matched_on": "validated_physical_identity",
                        "authority_effect": "none",
                    })
                else:
                    rows.append(_unresolved_part_row(part, index, reason=basis, rejected_module_id=module_id or None))
        else:
            for index in model_indexes:
                rows.append(_unresolved_part_row(part_rows[index], index, reason="identity model/provider unavailable"))
    else:
        for index in model_indexes:
            rows.append(_unresolved_part_row(part_rows[index], index, reason="no identity model/provider available"))

    rows.sort(key=lambda row: int(row.get("part_index") or 0))
    meta["resolved_count"] = sum(bool(row.get("module_id")) for row in rows)
    meta["unresolved_count"] = sum(not bool(row.get("module_id")) for row in rows)
    meta["unresolved_part_indexes"] = [int(row["part_index"]) for row in rows if not row.get("module_id")]
    return rows, meta


def _iter_functional_blocks(donor_context: Mapping[str, Any] | None) -> list[Dict[str, Any]]:
    """Traverse persisted donor wrappers without interpreting human-facing labels."""
    if not isinstance(donor_context, Mapping):
        return []
    blocks: list[Dict[str, Any]] = []
    seen: set[str] = set()

    def take(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("block_id") and (value.get("function_type") or value.get("capabilities")):
                key = str(value.get("block_id"))
                if key not in seen:
                    seen.add(key)
                    blocks.append(deepcopy(dict(value)))
            # These are structural schema wrappers only.  In particular, circuit/boards
            # are needed for persisted donor captures where functional_salvage belongs to
            # a particular board.  No arbitrary mapping recursion or name-based inference.
            for key in (
                "circuit",
                "boards",
                "functional_salvage",
                "reusable_blocks",
                "blocks",
            ):
                child = value.get(key)
                if isinstance(child, (list, tuple, Mapping)):
                    take(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                take(child)

    take(donor_context)
    return blocks


def _donor_role(block: Mapping[str, Any]) -> str:
    return {
        "actuator_driver": "drv", "stepper_driver": "drv", "motion_driver": "drv",
        "power_regulation": "pwr", "sensor_io": "sns", "sensor": "sns",
        "controller": "mcu", "actuator": "act",
    }.get(str(block.get("function_type") or "").strip().lower(), "misc")


def functional_salvage_identity_rows(
    donor_context: Mapping[str, Any] | None,
    *,
    parts: Sequence[Mapping[str, Any]] | None = None,
) -> list[Dict[str, Any]]:
    """Preserve donor block identity/capability without catalog stand-in substitution."""
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        from .module_resolver import merge_functional_salvage_modules
        return merge_functional_salvage_modules(donor_context, list(parts or []))

    rows: list[Dict[str, Any]] = []
    for block in _iter_functional_blocks(donor_context):
        status = str(block.get("status") or "").strip().lower()
        if status in {"do_not_reuse", "blocked", "unsafe"}:
            continue
        explicit = str(block.get("module_id") or block.get("catalog_module_id") or "").strip()
        valid_explicit = explicit if explicit and find_module(explicit) is not None else None
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "part_name": str(block.get("name") or block.get("block_id") or "donor functional block"),
            "instance_id": str(block.get("block_id") or "donor-block"),
            "module_id": valid_explicit,
            "role": _donor_role(block),
            "source": "donor_functional_salvage_declared" if valid_explicit else "donor_functional_salvage_external",
            "identity_status": "declared" if valid_explicit else "external_unresolved",
            "external_capability_only": valid_explicit is None,
            "donor_block_id": str(block.get("block_id") or ""),
            "donor_block_name": str(block.get("name") or ""),
            "board_id": str(block.get("board_id") or ""),
            "function_type": str(block.get("function_type") or ""),
            "capabilities": [str(value) for value in list(block.get("capabilities") or [])],
            "connector_refs": [str(value) for value in list(block.get("connector_refs") or []) if str(value).strip()],
            "extractability": deepcopy(dict(block.get("extractability") or {})) if isinstance(block.get("extractability"), Mapping) else {},
            "confidence": float(block.get("confidence") or block.get("reuse_value_score") or 0.0),
            "authority_effect": "none",
        })
    return rows


def _has_driver_capability(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(str(row.get("role") or "") == "drv" for row in rows)


def fill_capability_gaps(rows: Sequence[Mapping[str, Any]], *, parts: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    """Add unresolved capability requirements, never concrete substitute identities."""
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        from .module_resolver import fill_salvage_gaps
        return fill_salvage_gaps([dict(row) for row in rows], parts=[dict(row) for row in parts])

    result = [deepcopy(dict(row)) for row in rows]
    if _has_driver_capability(result):
        return result
    has_stepper = any(bool(structured_part_tokens(part) & {"stepper_motor", "stepper"}) for part in parts)
    has_driven_actuator = any(
        bool(structured_part_tokens(part) & {"dc_motor", "motor", "stepper_motor", "stepper", "pump", "fan"})
        for part in parts
    )
    if has_stepper:
        result.append({
            "schema_version": SCHEMA_VERSION,
            "part_name": "required stepper driver capability",
            "instance_id": "gap-stepper-driver",
            "module_id": None,
            "role": "drv",
            "source": "unresolved_capability_gap",
            "identity_status": "unresolved",
            "required_capability": "stepper_driver",
            "reason": "A declared stepper actuator exists without an identified driver capability.",
            "confidence": 0.0,
            "authority_effect": "none",
        })
    elif has_driven_actuator:
        result.append({
            "schema_version": SCHEMA_VERSION,
            "part_name": "required actuator driver/switch capability",
            "instance_id": "gap-actuator-driver",
            "module_id": None,
            "role": "drv",
            "source": "unresolved_capability_gap",
            "identity_status": "unresolved",
            "required_capability": "actuator_driver_or_switch",
            "reason": "A declared driven actuator exists without an identified driver/switch capability.",
            "confidence": 0.0,
            "authority_effect": "none",
        })
    return result


def infer_power_topology_truth(
    parts: Sequence[Mapping[str, Any]],
    resolved_modules: Sequence[Mapping[str, Any]],
    *,
    constraints: Mapping[str, Any] | None = None,
) -> str:
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        from .module_resolver import infer_power_topology
        return infer_power_topology([dict(row) for row in parts], list(resolved_modules), constraints=constraints)
    constraints_map = dict(constraints or {})
    explicit = str(constraints_map.get("power_topology") or "").strip().lower()
    if explicit in {"usb_5v", "barrel_12v", "hybrid"}:
        return explicit
    module_ids = {str(row.get("module_id") or "").strip() for row in resolved_modules if str(row.get("module_id") or "").strip()}
    has_usb = "usb-power-5v" in module_ids
    has_barrel = "dc-barrel-12v" in module_ids
    if has_usb and has_barrel:
        return "hybrid"
    if has_usb:
        return "usb_5v"
    if has_barrel:
        return "barrel_12v"
    return "unresolved"


def module_overrides_truth(
    resolved_modules: Sequence[Mapping[str, Any]],
    *,
    build_id: str | None = None,
) -> Dict[str, str]:
    """Direct bound role→module projection with no substitution or magic preferred IDs."""
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        from .module_resolver import module_overrides_for_build
        return module_overrides_for_build(build_id=build_id, resolved_modules=list(resolved_modules))
    overrides: Dict[str, str] = {}
    donor_rows: list[Mapping[str, Any]] = []
    ordinary_rows: list[Mapping[str, Any]] = []
    for row in resolved_modules:
        module_id = str(row.get("module_id") or "").strip()
        role = str(row.get("role") or "").strip()
        if not module_id or not role or find_module(module_id) is None:
            continue
        if str(row.get("source") or "").startswith("donor_functional_salvage"):
            donor_rows.append(row)
        else:
            ordinary_rows.append(row)
    for row in ordinary_rows + donor_rows:
        overrides[str(row.get("role"))] = str(row.get("module_id"))
    return overrides


def merge_truth_rows(*collections: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    """Merge identity/capability rows without name-based substitution or power inference."""
    rows: list[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for collection in collections:
        for raw in collection:
            row = deepcopy(dict(raw))
            key = (str(row.get("instance_id") or ""), str(row.get("module_id") or ""), str(row.get("source") or ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows
