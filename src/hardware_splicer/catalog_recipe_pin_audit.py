"""Deterministic catalog-recipe pin integrity audit.

A catalog recipe is not electrically meaningful if a declared wire endpoint exists only in
recipe prose/JSON but is absent from the module contract or from the engine footprint pad
model. Such endpoints can otherwise disappear before ERC/DRC and produce a false green.

This audit judges representation integrity only. It does not choose architectures, repair
recipes, or infer replacement pins/components.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from .pcb.module_registry import find_module, find_pin, resolve_module_pads


SCHEMA_VERSION = "hardware_splicer.catalog_recipe_pin_audit.v1"
_RECIPES_PATH = Path(__file__).resolve().parent / "data" / "catalog_recipes.json"


def _finding(
    code: str,
    build_id: str,
    path: str,
    message: str,
    *,
    observed: Any = None,
) -> Dict[str, Any]:
    return {
        "code": code,
        "build_id": build_id,
        "path": path,
        "message": message,
        "observed": observed,
        "severity": "blocking",
    }


def load_catalog_recipes(path: str | Path | None = None) -> Dict[str, Dict[str, Any]]:
    """Load the canonical recipe map while tolerating the historical flat fixture shape."""

    source = Path(path).resolve() if path is not None else _RECIPES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"catalog recipes must be a JSON object: {source}")

    # Current generated data is an envelope:
    # {schema_version, build_catalog_capability_groups, recipes}.  The original audit
    # accidentally iterated that envelope, so it inspected zero modules/endpoints while
    # reporting success.  Explicit caller-supplied flat recipe maps remain supported for
    # focused fixtures, but production data must descend through `recipes`.
    if "recipes" in payload:
        raw_recipes = payload.get("recipes")
        if not isinstance(raw_recipes, Mapping):
            raise ValueError(f"catalog recipes envelope has non-object recipes field: {source}")
    else:
        raw_recipes = payload

    return {
        str(build_id): dict(recipe)
        for build_id, recipe in raw_recipes.items()
        if isinstance(recipe, Mapping)
    }


def audit_catalog_recipe_pins(
    recipes: Mapping[str, Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Verify every recipe endpoint survives module contract → engine pad representation."""

    source = recipes if recipes is not None else load_catalog_recipes()
    findings: list[Dict[str, Any]] = []
    checked_endpoints = 0
    checked_modules = 0

    for build_id, raw_recipe in sorted(source.items()):
        recipe = dict(raw_recipe or {})
        role_modules: Dict[str, str] = {}
        for index, raw_module in enumerate(recipe.get("modules") or []):
            if not isinstance(raw_module, Mapping):
                findings.append(
                    _finding(
                        "RECIPE_MODULE_ROW_INVALID",
                        build_id,
                        f"recipes.{build_id}.modules[{index}]",
                        "Catalog module row is not an object.",
                        observed=raw_module,
                    )
                )
                continue
            role = str(raw_module.get("role") or "").strip()
            module_id = str(raw_module.get("moduleId") or raw_module.get("module_id") or "").strip()
            if not role or not module_id:
                findings.append(
                    _finding(
                        "RECIPE_MODULE_BINDING_INCOMPLETE",
                        build_id,
                        f"recipes.{build_id}.modules[{index}]",
                        "Catalog module row requires non-empty role and module identity.",
                        observed={"role": role, "module_id": module_id},
                    )
                )
                continue
            checked_modules += 1
            if role in role_modules:
                findings.append(
                    _finding(
                        "RECIPE_ROLE_DUPLICATE",
                        build_id,
                        f"recipes.{build_id}.modules[{index}].role",
                        "Catalog recipe binds the same role more than once.",
                        observed=role,
                    )
                )
            role_modules[role] = module_id
            if find_module(module_id) is None:
                findings.append(
                    _finding(
                        "RECIPE_MODULE_UNKNOWN",
                        build_id,
                        f"recipes.{build_id}.modules[{index}].moduleId",
                        "Catalog recipe references a module absent from structured engine data.",
                        observed=module_id,
                    )
                )

        for wire_index, raw_wire in enumerate(recipe.get("wires") or []):
            if not isinstance(raw_wire, Mapping):
                findings.append(
                    _finding(
                        "RECIPE_WIRE_ROW_INVALID",
                        build_id,
                        f"recipes.{build_id}.wires[{wire_index}]",
                        "Catalog wire row is not an object.",
                        observed=raw_wire,
                    )
                )
                continue
            for side in ("from", "to"):
                endpoint = raw_wire.get(side)
                path = f"recipes.{build_id}.wires[{wire_index}].{side}"
                if not isinstance(endpoint, Mapping):
                    findings.append(
                        _finding(
                            "RECIPE_ENDPOINT_INVALID",
                            build_id,
                            path,
                            "Catalog wire endpoint is not an object.",
                            observed=endpoint,
                        )
                    )
                    continue
                role = str(endpoint.get("role") or "").strip()
                pin_id = str(endpoint.get("pin") or "").strip()
                module_id = role_modules.get(role, "")
                checked_endpoints += 1
                if not module_id:
                    findings.append(
                        _finding(
                            "RECIPE_ENDPOINT_ROLE_UNBOUND",
                            build_id,
                            f"{path}.role",
                            "Wire endpoint role is not bound to a declared recipe module.",
                            observed=role,
                        )
                    )
                    continue
                module = find_module(module_id)
                if module is None:
                    continue
                if not pin_id or find_pin(module, pin_id) is None:
                    findings.append(
                        _finding(
                            "RECIPE_PIN_NOT_IN_MODULE_CONTRACT",
                            build_id,
                            f"{path}.pin",
                            "Wire endpoint pin is absent from the module's structured pin contract.",
                            observed={"role": role, "module_id": module_id, "pin": pin_id},
                        )
                    )
                    continue
                pads = resolve_module_pads(module_id, module) or []
                pad_ids = {str(row.get("pinId") or "") for row in pads if isinstance(row, Mapping)}
                if pin_id not in pad_ids:
                    findings.append(
                        _finding(
                            "RECIPE_PIN_NOT_IN_ENGINE_PADS",
                            build_id,
                            f"{path}.pin",
                            "Wire endpoint is valid catalog truth but is absent from the engine pad model and may disappear before physical verification.",
                            observed={
                                "role": role,
                                "module_id": module_id,
                                "pin": pin_id,
                                "engine_pad_ids": sorted(pad_ids),
                            },
                        )
                    )

    blocking = [row for row in findings if row.get("severity") == "blocking"]
    by_build: Dict[str, list[Dict[str, Any]]] = {}
    for row in findings:
        by_build.setdefault(str(row.get("build_id") or ""), []).append(row)

    codes = {str(row.get("code") or "") for row in blocking}
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if blocking else "pass",
        "recipe_count": len(source),
        "checked_module_count": checked_modules,
        "checked_endpoint_count": checked_endpoints,
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking),
        "findings": findings,
        "findings_by_build": by_build,
        "checks": {
            "module_identity_exists": "RECIPE_MODULE_UNKNOWN" not in codes,
            "wire_endpoint_role_bound": "RECIPE_ENDPOINT_ROLE_UNBOUND" not in codes,
            "wire_pin_in_module_contract": "RECIPE_PIN_NOT_IN_MODULE_CONTRACT" not in codes,
            "wire_pin_in_engine_pad_model": "RECIPE_PIN_NOT_IN_ENGINE_PADS" not in codes,
            "architecture_repair_attempted": False,
        },
        "authority_effect": "none",
    }
