"""Material budget modes — same engine, different parts constraints.

Scratch (open): pick/buy anything the design needs (editor, NL compose, greenfield).
Salvage (constrained): start from inventory; small allowed_purchases for gaps (level shifter, LDO, …).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Mapping, Sequence

MaterialMode = Literal["scratch", "salvage"]
StrategyMode = Literal["open", "constrained"]

# Small parts commonly bought to close salvage gaps (not full catalog freedom).
DEFAULT_ALLOWED_PURCHASES: tuple[str, ...] = (
    "level-shifter-4ch",
    "ldo-ams1117-3v3",
    "buck-mp1584",
    "resistor-10k",
    "mosfet-irlz44n",
    "relay-1ch-5v",
)

OPEN_MODE_AUTO_ADDITIONS: tuple[str, ...] = (
    "level-shifter-4ch",
    "ldo-ams1117-3v3",
    "mosfet-irlz44n",
)


def resolve_strategy_mode(constraints: Mapping[str, Any] | None) -> StrategyMode:
    raw = str((constraints or {}).get("strategy_mode") or "constrained").strip().lower()
    return "open" if raw == "open" else "constrained"


def resolve_material_mode(
    *,
    constraints: Mapping[str, Any] | None = None,
    salvage_mode: bool = False,
) -> MaterialMode:
    """Classify intake/compose path by material budget (not by UI surface)."""
    constraints_map = dict(constraints or {})
    graph_mode = str(constraints_map.get("graph_mode") or "").strip().lower()
    if salvage_mode or constraints_map.get("compose_from_inventory") is True:
        return "salvage"
    if graph_mode in {"scratch", "compose", "canvas"}:
        return "scratch"
    if resolve_strategy_mode(constraints_map) == "open":
        return "scratch"
    return "salvage" if constraints_map.get("inventory_only") is True else "scratch"


def allowed_purchases(constraints: Mapping[str, Any] | None) -> List[str]:
    extra = list((constraints or {}).get("allowed_purchases") or [])
    if extra:
        return list(dict.fromkeys(str(x) for x in extra if str(x).strip()))
    return list(DEFAULT_ALLOWED_PURCHASES)


def can_add_module(
    module_id: str,
    *,
    material_mode: MaterialMode,
    inventory_ids: Sequence[str],
    constraints: Mapping[str, Any] | None = None,
) -> bool:
    mid = str(module_id).strip()
    if not mid:
        return False
    if material_mode == "scratch":
        return True
    if mid in inventory_ids:
        return True
    return mid in allowed_purchases(constraints)


def expand_module_ids_for_safety(
    module_ids: Sequence[str],
    *,
    safety_messages: Sequence[str],
    material_mode: MaterialMode,
    inventory_ids: Sequence[str] | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> List[str]:
    """Add support modules when material budget allows (open scratch or salvage purchases)."""
    ids = list(dict.fromkeys(str(m) for m in module_ids if str(m).strip()))
    inventory = list(inventory_ids or ids)
    text = " ".join(str(m) for m in safety_messages).lower()

    candidates: List[str] = []
    if "level shifter" in text or "logic" in text and "5v" in text:
        candidates.append("level-shifter-4ch")
    if "regulator" in text or "outputs 5v" in text and "expects 3" in text:
        candidates.append("ldo-ams1117-3v3")
    if "irf520" in text or "does not switch fully" in text:
        candidates.append("mosfet-irlz44n")

    if material_mode == "scratch":
        pool = list(dict.fromkeys([*candidates, *OPEN_MODE_AUTO_ADDITIONS]))
    else:
        pool = [c for c in candidates if c in allowed_purchases(constraints)]

    for mid in pool:
        if mid not in ids and can_add_module(mid, material_mode=material_mode, inventory_ids=inventory, constraints=constraints):
            ids.append(mid)
    return ids


def material_mode_summary(
    *,
    material_mode: MaterialMode | str,
    constraints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    mode = str(material_mode)
    return {
        "material_mode": mode,
        "strategy_mode": resolve_strategy_mode(constraints),
        "inventory_only": mode == "salvage",
        "allowed_purchases": allowed_purchases(constraints) if mode == "salvage" else ["*catalog*"],
        "editor_scratch_unified": True,
        "description": (
            "Open catalog — add any module the design needs"
            if mode == "scratch"
            else "Inventory-first — only salvaged parts plus allowed_purchases"
        ),
    }
