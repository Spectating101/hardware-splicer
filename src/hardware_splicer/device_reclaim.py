"""Advisory name matches from a reclaim list to the device planner's existing library.

No chip identification, compatibility assessment, plan changes or evidence promotion takes place here.
"""

from __future__ import annotations

from typing import Any

from .device_plan import module_library
from .part_lookup import MAX_QUERY, name_match_tier
from .text_safety import has_hidden_characters

MAX_PARTS = 300
ADVISORY_NOTE = (
    "You may already have this part on the board you took apart; its marking is what you read, not proof, "
    "and the device planner's data for it is the library's, not your chip's. These are name matches only, "
    "not a compatibility assessment. A recorded reading is not a pass. Nothing here approves building, powering or release."
)


class DeviceReclaimError(ValueError):
    """The reclaim list cannot be read safely."""


def _text(value: Any, label: str, limit: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise DeviceReclaimError(f"{label} must be text")
    if has_hidden_characters(value):
        raise DeviceReclaimError(f"{label} may not contain control or invisible characters")
    text = value.strip()
    if len(text) > limit or (required and not text):
        raise DeviceReclaimError(f"{label} must be {'1' if required else '0'} to {limit} characters")
    return text


def _chip_tier(marking: str, listed: str) -> str | None:
    """The library lists one part; a marking is that part (exact) or that part plus a package or grade code (variant).

    Never the other way round: ESP32-WROOM-32 is a different module from the listed ESP32-WROOM-32E, not a variant of it.
    """

    q, n = marking.strip().lower(), listed.strip().lower()
    if q == n:
        return "exact"
    if len(q) > len(n) and q.startswith(n) and name_match_tier(q, n) == "variant":
        return "variant"
    return None


def match_reclaimed_parts(body: Any) -> dict[str, Any]:
    """Compare reported markings with whole library names, explicit MPNs and sourced chip markings.

    Kinds are preserved as reported, not inferred from a name or used as a compatibility claim.
    The request contains text only: dimensions, readings and numeric values are not consumed.
    """

    if not isinstance(body, dict) or not isinstance(body.get("parts"), list) or len(body["parts"]) > MAX_PARTS:
        raise DeviceReclaimError(f"parts must be a list of at most {MAX_PARTS}")
    rows = []
    seen = set()
    for i, part in enumerate(body["parts"]):
        if not isinstance(part, dict):
            raise DeviceReclaimError(f"parts[{i}] must be an object")
        ref = _text(part.get("ref"), f"parts[{i}].ref", 40, required=True)
        kind = _text(part.get("kind"), f"parts[{i}].kind", 40, required=True)
        marking = _text(part.get("marking"), f"parts[{i}].marking", MAX_QUERY)
        if ref.lower() in seen:
            raise DeviceReclaimError(f"reference {ref!r} is used twice")
        seen.add(ref.lower())
        rows.append({"ref": ref, "kind": kind, "marking": marking})

    library = module_library()
    for row in rows:
        matches = []
        for entry in library["modules"]:
            candidates = []
            for field in ("name", "mpn"):
                name = entry.get(field)
                tier = name_match_tier(row["marking"], name) if isinstance(name, str) else None
                if tier in ("exact", "variant"):
                    candidates.append((tier, field, name))
            if candidates:
                tier, field, name = min(candidates, key=lambda c: c[0] != "exact")
                matches.append({"module": entry["id"], "name": entry["name"], "tier": tier,
                                "relation": "module", "matched_field": field, "matched_name": name})
            for chip in entry.get("chips", []):
                tier = _chip_tier(row["marking"], chip["marking"])
                if tier:
                    note = (
                        f"The library lists {chip['marking']} as the {chip['role']} ({entry['name']}). "
                        "The chip or radio module alone is not that module and does not come with its board, pins, "
                        "regulator or wiring rules. The marking is what you read, not proof."
                    )
                    matches.append({"module": entry["id"], "name": entry["name"], "tier": tier,
                                    "relation": "chip_on_module", "matched_field": "chips.marking",
                                    "matched_name": chip["marking"], "role": chip["role"],
                                    "source": chip["source"], "note": note})
        matches.sort(key=lambda m: m["tier"] != "exact")
        row.update(matched=bool(matches), matches=matches)
    return {"parts": rows, "source": "device planner module library", "note": ADVISORY_NOTE}
