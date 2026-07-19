from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple


SCHEMA_VERSION = "hardware_splicer.module_resolver.v1"

# Fuzzy part-name → module-library id. Order matters (first match wins).
_MODULE_PATTERNS: List[Tuple[re.Pattern[str], str, str, float]] = [
    (re.compile(r"irlz44n|irlz", re.I), "mosfet-irlz44n", "drv", 0.95),
    (re.compile(r"logic.?level.*mosfet|logic.?level.*fet", re.I), "mosfet-irlz44n", "drv", 0.93),
    (re.compile(r"irf520", re.I), "mosfet-irf520", "drv", 0.85),
    (re.compile(r"mosfet", re.I), "mosfet-irlz44n", "drv", 0.8),
    (re.compile(r"ao3400", re.I), "mosfet-irlz44n", "drv", 0.9),
    (re.compile(r"lm2596", re.I), "buck-lm2596", "buck", 0.92),
    (re.compile(r"mp1584|mini buck", re.I), "buck-mp1584", "buck", 0.9),
    (re.compile(r"tp4056|lipo charger", re.I), "tp4056", "usb", 0.9),
    (re.compile(r"esp32[\s\-]?cam|ai[\s\-]?thinker.*cam|ov2640", re.I), "esp32-cam-module", "mcu", 0.96),
    (re.compile(r"esp32", re.I), "esp32-devkit", "mcu", 0.95),
    (re.compile(r"arduino nano|nano", re.I), "arduino-nano", "mcu", 0.9),
    (re.compile(r"pico|raspberry pi pico", re.I), "rpi-pico", "mcu", 0.9),
    (re.compile(r"soil|moisture", re.I), "soil_moisture", "sns", 0.92),
    (re.compile(r"dht22|dht11|temp.*humid", re.I), "dht22", "sns", 0.88),
    (re.compile(r"bme280", re.I), "bme280", "sns", 0.9),
    (re.compile(r"vl53|tof|time.?of.?flight|range sensor|lidar", re.I), "vl53l0x_tof", "sns", 0.88),
    (re.compile(r"vl6180", re.I), "vl6180x-tof", "sns", 0.86),
    (re.compile(r"ultrasonic|hc-?sr04|sonar", re.I), "hc-sr04", "sns", 0.85),
    (re.compile(r"limit.?switch|endstop|end.?stop", re.I), "limit-switch-3pin", "sns", 0.9),
    (re.compile(r"sg90", re.I), "sg90", "act", 0.92),
    (re.compile(r"mg996r", re.I), "mg996r", "act", 0.9),
    # Do NOT match donor board names here — functional_salvage binds inkjet/RC donors.
    (re.compile(r"a4988|stepper.*driver|driver.*stepper|stepper.*section", re.I), "a4988-stepper", "drv", 0.86),
    (re.compile(r"stepper.*motor|28byj|nema", re.I), "28byj48_stepper", "mot", 0.84),
    (re.compile(r"l298n", re.I), "l298n", "drv", 0.9),
    (re.compile(r"dc.*gear.*motor|gear.*motor|brushed.*motor|dc[_ ]motor|6v.*motor", re.I), "dc_motor_3v_6v", "mot", 0.86),
    (re.compile(r"12v.*gear.*motor|geared.*motor.*12", re.I), "dc_geared_motor_12v", "mot", 0.84),
    (re.compile(r"relay", re.I), "relay-1ch-5v", "rly", 0.85),
    (re.compile(r"pump|peristaltic", re.I), "mini-pump-5v", "load", 0.8),
    (re.compile(r"fan|blower", re.I), "fan-5v", "load", 0.8),
    (re.compile(r"usb.*serial|cp210|ch340|ftdi", re.I), "usb-uart", "usb", 0.85),
    (re.compile(r"ssd1306|oled", re.I), "ssd1306", "ui", 0.85),
    (
        re.compile(
            r"power.?bank|usb.*power|5v.*usb|phone charger|(?:usb|5v).*wall wart|wall wart.*(?:usb|5v)",
            re.I,
        ),
        "usb-power-5v",
        "pwr",
        0.92,
    ),
    (
        re.compile(
            r"barrel|(?:12|24)v.*(?:supply|adapter|psu)|(?:wall wart.*(?:12|24)v|(?:12|24)v.*wall wart)",
            re.I,
        ),
        "dc-barrel-12v",
        "pwr",
        0.8,
    ),
]

_POWER_TOPOLOGY_USB = re.compile(
    r"power.?bank|usb.*power|5v.*usb|phone charger|(?:usb|5v).*wall wart|wall wart.*(?:usb|5v)",
    re.I,
)
_POWER_TOPOLOGY_BARREL = re.compile(
    r"barrel|(?:12|24)v.*(?:supply|adapter|psu)|(?:wall wart.*(?:12|24)v|(?:12|24)v.*wall wart)",
    re.I,
)

_USB_WALL_MODULE_IDS = frozenset({"usb-power-5v"})
_BARREL_POWER_MODULE_IDS = frozenset({"dc-barrel-12v"})

# 3.3V MCU + non-logic-level MOSFET → prefer logic-level FET.
_SUBSTITUTIONS: Dict[str, str] = {
    "mosfet-irf520": "mosfet-irlz44n",
}

_ROLE_ALIASES = {
    "controller": "mcu",
    "microcontroller": "mcu",
    "sensor": "sns",
    "actuator": "act",
    "driver": "drv",
    "relay": "rly",
    "servo": "svo",
    "power": "buck",
    "power_source": "pwr",
    "pump": "load",
    "fan": "load",
    "motor": "load",
    "dc_motor": "load",
    "tof_range": "sns",
}


def _part_text(part: Mapping[str, Any]) -> str:
    bits = [
        str(part.get("name") or ""),
        str(part.get("type") or ""),
        str(part.get("kind") or ""),
        str(part.get("part_class") or ""),
    ]
    return " ".join(bits).strip()


def _part_voltage_v(part: Mapping[str, Any]) -> Optional[float]:
    raw = part.get("voltage_v")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _part_implies_usb_5v(part: Mapping[str, Any]) -> bool:
    text = _part_text(part)
    if not text:
        return False
    if str(part.get("module_id") or "").strip() in _USB_WALL_MODULE_IDS | {"tp4056"}:
        return True
    voltage = _part_voltage_v(part)
    if voltage is not None and voltage <= 5.5:
        if _POWER_TOPOLOGY_USB.search(text) or "wall wart" in text.lower():
            return True
    return bool(_POWER_TOPOLOGY_USB.search(text))


def _part_implies_barrel_12v(part: Mapping[str, Any]) -> bool:
    if _part_implies_usb_5v(part):
        return False
    text = _part_text(part)
    return bool(text and _POWER_TOPOLOGY_BARREL.search(text))


def _role_for_module_id(module_id: str, part: Mapping[str, Any]) -> str:
    mid = str(module_id or "").strip()
    if mid in _USB_WALL_MODULE_IDS:
        return "usb"
    if mid.startswith("relay"):
        return "rly"
    if mid in {"sg90", "mg996r"}:
        return "svo"
    for _pattern, pattern_mid, role, _confidence in _MODULE_PATTERNS:
        if pattern_mid == mid:
            return role
    cap = str(part.get("part_class") or part.get("type") or "").lower()
    return _ROLE_ALIASES.get(cap, cap or "misc")


_MULTI_INSTANCE_ROLES = frozenset({"mot", "sns", "load", "act", "svo"})
_DONOR_SOURCES = frozenset({"donor_functional_salvage", "circuit_functional_salvage"})


def _row_coalesce_key(row: Mapping[str, Any]) -> str:
    """Allow multiple motors/sensors with the same catalog module_id."""
    module_id = str(row.get("module_id") or "").strip()
    role = str(row.get("role") or "").strip()
    part_name = str(row.get("part_name") or "").strip().lower()
    instance = str(row.get("instance_id") or "").strip()
    if role in _MULTI_INSTANCE_ROLES and (part_name or instance):
        return f"{module_id}::{instance or part_name}"
    return module_id


def coalesce_resolved_modules(
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]],
    *,
    power_topology: str | None = None,
) -> List[Dict[str, Any]]:
    """Drop conflicting power modules after fuzzy resolve / goal merge."""
    topology = power_topology or infer_power_topology(parts, resolved_modules)
    rows: List[Dict[str, Any]] = [dict(row) for row in resolved_modules if isinstance(row, Mapping)]
    unresolved = [row for row in rows if not str(row.get("module_id") or "").strip()]
    rows = [row for row in rows if str(row.get("module_id") or "").strip()]
    if topology == "usb_5v":
        rows = [row for row in rows if str(row.get("module_id") or "") not in _BARREL_POWER_MODULE_IDS]
    elif topology == "barrel_12v":
        rows = [row for row in rows if str(row.get("module_id") or "") not in _USB_WALL_MODULE_IDS]

    by_key: Dict[str, Dict[str, Any]] = {}
    source_rank = {
        "donor_functional_salvage": 3,
        "circuit_functional_salvage": 3,
        "user_inventory": 2,
        "gap_fill": 0,
        "unresolved": 0,
    }
    for row in rows:
        module_id = str(row.get("module_id") or "").strip()
        if not module_id:
            continue
        key = _row_coalesce_key(row)
        existing = by_key.get(key)
        if not existing:
            by_key[key] = row
            continue
        # Prefer donor-bound / inventory over gap_fill when the same key collides.
        if source_rank.get(str(row.get("source") or ""), 1) > source_rank.get(str(existing.get("source") or ""), 1):
            by_key[key] = row
    return list(by_key.values()) + unresolved


def resolve_parts_to_modules(parts: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Map intake-normalized parts to module-library IDs with role hints."""
    resolved: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for part in parts:
        text = _part_text(part)
        explicit_id = str(part.get("module_id") or "").strip()
        if explicit_id:
            row = {
                "schema_version": SCHEMA_VERSION,
                "part_name": str(part.get("name") or text or explicit_id),
                "module_id": explicit_id,
                "role": _role_for_module_id(explicit_id, part),
                "source": "user_inventory",
                "confidence": 1.0,
                "matched_on": "explicit_module_id",
            }
            key = _row_coalesce_key(row)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(row)
            continue
        if not text:
            continue
        match: Optional[Dict[str, Any]] = None
        for pattern, module_id, role, confidence in _MODULE_PATTERNS:
            if pattern.search(text):
                match = {
                    "schema_version": SCHEMA_VERSION,
                    "part_name": str(part.get("name") or text),
                    "module_id": module_id,
                    "role": role,
                    "source": "user_inventory",
                    "confidence": confidence,
                    "matched_on": pattern.pattern,
                }
                break
        if match and match.get("module_id") in _SUBSTITUTIONS:
            match = dict(match)
            match["module_id"] = _SUBSTITUTIONS[str(match["module_id"])]

        if not match:
            cap = str(part.get("part_class") or part.get("type") or "").lower()
            role = _ROLE_ALIASES.get(cap, cap or "misc")
            match = {
                "schema_version": SCHEMA_VERSION,
                "part_name": str(part.get("name") or text),
                "module_id": None,
                "role": role,
                "source": "unresolved",
                "confidence": 0.2,
                "matched_on": cap,
            }
        if match.get("module_id"):
            key = _row_coalesce_key(match)
            if key in seen_keys:
                continue
            seen_keys.add(key)
        resolved.append(match)
    return coalesce_resolved_modules(parts, resolved)


def _iter_functional_salvage_blocks(donor_context: Mapping[str, Any] | None) -> List[Dict[str, Any]]:
    """Collect reusable_blocks from circuit boards / top-level functional_salvage."""
    if not donor_context:
        return []
    blocks: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _take(report: Mapping[str, Any] | None) -> None:
        if not isinstance(report, Mapping):
            return
        for block in report.get("reusable_blocks") or []:
            if not isinstance(block, Mapping):
                continue
            block_id = str(block.get("block_id") or block.get("name") or "")
            key = block_id or json_dumps_safe(block)
            if key in seen:
                continue
            seen.add(key)
            blocks.append(dict(block))

    if isinstance(donor_context.get("reusable_blocks"), list):
        _take({"reusable_blocks": donor_context.get("reusable_blocks")})
    circuit = donor_context.get("circuit")
    if isinstance(circuit, Mapping):
        for board in circuit.get("boards") or []:
            if isinstance(board, Mapping):
                fs = board.get("functional_salvage")
                if isinstance(fs, Mapping):
                    _take(fs)
                if isinstance(board.get("reusable_blocks"), list):
                    _take({"reusable_blocks": board.get("reusable_blocks")})
    fs_top = donor_context.get("functional_salvage")
    if isinstance(fs_top, Mapping):
        _take(fs_top)
    # Planner output carries expanded FS blocks on reusable_blocks.
    splice = donor_context.get("splice_plan")
    if isinstance(splice, Mapping):
        nested = splice.get("reusable_blocks")
        if isinstance(nested, list):
            _take({"reusable_blocks": nested})
    return blocks


def json_dumps_safe(value: Any) -> str:
    try:
        import json

        return json.dumps(value, sort_keys=True, default=str)[:240]
    except Exception:
        return str(value)[:240]


def _module_id_for_donor_block(block: Mapping[str, Any]) -> Tuple[str, str] | None:
    """Map a functional_salvage block to a catalog stand-in + role (carrier interface)."""
    ftype = str(block.get("function_type") or "").lower()
    caps = " ".join(str(c).lower() for c in (block.get("capabilities") or []))
    name = str(block.get("name") or "").lower()
    text = f"{ftype} {caps} {name}"
    status = str(block.get("status") or "").lower()
    if status and status not in {"reuse_ready", "ready_after_measurements", "layout_review_required", ""}:
        # Still bind layout_review / reuse_ready; skip only hard rejects.
        if status in {"do_not_reuse", "blocked", "unsafe"}:
            return None
    if "stepper" in text or ftype in {"stepper_driver", "motion_driver"}:
        return "a4988-stepper", "drv"
    if ftype == "actuator_driver" or "h-bridge" in text or "hbridge" in text or "motor driver" in text:
        return "l298n", "drv"
    if ftype == "power_regulation" or "battery" in text or "power" in caps:
        # Battery input sections are reuse notes — do not invent a USB wall-wart stand-in.
        if "battery" in text or "j_batt" in text or "batt" in name:
            return None
        if "24" in text or "12" in text:
            return "dc-barrel-12v", "pwr"
        if "usb" in text or "5v" in text:
            return "usb-power-5v", "pwr"
        return None
    if ftype in {"sensor_io", "sensor"} or "limit" in text or "switch" in text:
        return "limit-switch-3pin", "sns"
    return None


def merge_functional_salvage_modules(
    donor_context: Mapping[str, Any] | None,
    parts: List[Mapping[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Bind donor reusable_blocks into resolved_modules so gap_fill cannot substitute them away."""
    parts = parts or []
    donor_part_names = [
        str(p.get("name") or "")
        for p in parts
        if "donor" in str(p.get("type") or "").lower() or "donor" in str(p.get("name") or "").lower()
    ]
    default_donor_name = donor_part_names[0] if donor_part_names else "donor board"
    rows: List[Dict[str, Any]] = []
    bound_donor_names: set[str] = set()

    for block in _iter_functional_salvage_blocks(donor_context):
        mapped = _module_id_for_donor_block(block)
        if not mapped:
            continue
        module_id, role = mapped
        board_id = str(block.get("board_id") or "")
        part_name = default_donor_name
        for name in donor_part_names:
            if board_id and board_id.replace("_", " ") in name.lower().replace("-", " "):
                part_name = name
                break
            if "inkjet" in name.lower() and "stepper" in str(block.get("name") or "").lower():
                part_name = name
                break
            if "rc" in name.lower() and ("h-bridge" in str(block.get("name") or "").lower() or "motor driver" in str(block.get("name") or "").lower()):
                part_name = name
                break
        connector_refs = [str(c) for c in (block.get("connector_refs") or []) if str(c).strip()]
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "part_name": part_name,
                "module_id": module_id,
                "role": role,
                "source": "donor_functional_salvage",
                "confidence": float(block.get("confidence") or block.get("reuse_value_score") or 0.8),
                "matched_on": "functional_salvage.reusable_blocks",
                "donor_block_id": str(block.get("block_id") or ""),
                "donor_block_name": str(block.get("name") or ""),
                "board_id": board_id,
                "connector_refs": connector_refs,
                "extractability": dict(block.get("extractability") or {}) if isinstance(block.get("extractability"), Mapping) else {},
                "instance_id": str(block.get("block_id") or module_id),
            }
        )
        bound_donor_names.add(part_name)

    # Drop unresolved placeholder rows for donor boards we just bound.
    # (Caller coalesces FS rows + heuristic rows together.)
    _ = bound_donor_names
    return rows


def donor_has_bound_driver(
    resolved_modules: List[Mapping[str, Any]] | None = None,
    donor_context: Mapping[str, Any] | None = None,
) -> bool:
    for row in resolved_modules or []:
        if str(row.get("source") or "") in _DONOR_SOURCES and str(row.get("role") or "") == "drv" and row.get("module_id"):
            return True
    for block in _iter_functional_salvage_blocks(donor_context):
        mapped = _module_id_for_donor_block(block)
        if mapped and mapped[1] == "drv":
            return True
    return False


def resolve_parts_to_modules_with_llm(
    parts: List[Mapping[str, Any]],
    *,
    goal: str = "",
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Map intake parts → module_id. LLM-first when keyed; regex is offline fallback only."""
    from .integrations.qwen_salvage_resolver import (
        call_qwen_salvage_map_intake,
        merge_qwen_intake_map,
        merge_qwen_salvage_into_resolved,
        qwen_salvage_enabled,
        salvage_resolve_mode,
    )

    mode = salvage_resolve_mode()
    heuristic = resolve_parts_to_modules(parts) if mode != "llm_only" else []
    meta: Dict[str, Any] = {
        "resolve_mode": mode,
        "heuristic": mode in {"heuristic", "llm_first"},
        "qwen": {"used": False},
    }

    explicit_rows: List[Dict[str, Any]] = [
        dict(row)
        for row in heuristic
        if str(row.get("matched_on") or "") == "explicit_module_id" and row.get("module_id")
    ]
    if not explicit_rows:
        for part in parts:
            explicit_id = str(part.get("module_id") or "").strip()
            if explicit_id:
                explicit_rows.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "part_name": str(part.get("name") or explicit_id),
                        "module_id": explicit_id,
                        "role": _role_for_module_id(explicit_id, part),
                        "source": "user_inventory",
                        "confidence": 1.0,
                        "matched_on": "explicit_module_id",
                    }
                )

    if mode in {"llm_first", "llm_only"} and qwen_salvage_enabled():
        qwen = call_qwen_salvage_map_intake(
            goal=goal,
            parts=parts,
            heuristic_hints=heuristic if mode == "llm_first" else None,
        )
        if qwen.get("ok"):
            if mode == "llm_only":
                merged = merge_qwen_intake_map(parts, qwen, explicit_rows=explicit_rows)
            else:
                merged = merge_qwen_salvage_into_resolved(heuristic, qwen)
            merged = coalesce_resolved_modules(parts, merged)
            meta["qwen"] = {
                "used": True,
                "model": qwen.get("model"),
                "reasoning": qwen.get("reasoning"),
                "power_notes": qwen.get("power_notes"),
                "rejected": qwen.get("rejected") or [],
                "suggested_purchases": qwen.get("suggested_purchases") or [],
                "unresolved_after": [r.get("part_name") for r in merged if not r.get("module_id")],
            }
            return merged, meta
        meta["qwen"] = {
            "used": False,
            "reason": qwen.get("error") or qwen.get("reason") or "qwen_map_failed",
            "fallback": "heuristic",
        }
        if mode == "llm_only":
            merged = coalesce_resolved_modules(parts, explicit_rows + [r for r in heuristic if not r.get("module_id")])
            return merged, meta

    unresolved = [row for row in heuristic if not row.get("module_id")]
    if unresolved and qwen_salvage_enabled() and mode == "heuristic":
        qwen = call_qwen_salvage_map_intake(
            goal=goal,
            parts=parts,
            heuristic_hints=unresolved,
        )
        merged = coalesce_resolved_modules(parts, merge_qwen_salvage_into_resolved(heuristic, qwen))
        meta["qwen"] = {
            "used": bool(qwen.get("ok")),
            "model": qwen.get("model"),
            "reasoning": qwen.get("reasoning"),
            "rejected": qwen.get("rejected") or [],
            "suggested_purchases": qwen.get("suggested_purchases") or [],
            "unresolved_after": [r.get("part_name") for r in merged if not r.get("module_id")],
        }
        return merged, meta

    meta["qwen"] = {
        "used": False,
        "reason": "heuristic_only" if mode == "heuristic" else "qwen_unavailable",
    }
    return heuristic, meta


_MOTOR_PART_TYPES = frozenset({"dc_motor", "motor", "gear_motor", "brushed_motor"})
_STEPPER_PART_TYPES = frozenset({"stepper_motor", "stepper"})
_MOTOR_MODULE_PREFIXES = ("dc_motor", "dc_geared_motor", "vibration_motor")
_DRIVER_MODULE_IDS = frozenset(
    {
        "l298n",
        "drv8833-motor",
        "l9110-motor",
        "tb6612fng-motor",
        "bts7960-motor",
        "mosfet-irlz44n",
        "a4988-stepper",
        "tmc2209-stepper",
        "drv8825_stepper",
    }
)
_STEPPER_DRIVER_MODULE_IDS = frozenset({"a4988-stepper", "tmc2209-stepper", "drv8825_stepper"})


def _inventory_has_stepper_motors(
    parts: List[Mapping[str, Any]] | None,
    resolved_modules: List[Mapping[str, Any]],
) -> bool:
    for part in parts or []:
        ptype = str(part.get("type") or "").lower()
        text = _part_text(part).lower()
        if ptype in _STEPPER_PART_TYPES or "stepper" in text:
            return True
    for row in resolved_modules:
        module_id = str(row.get("module_id") or "")
        if module_id in {"28byj48_stepper"}:
            return True
    return False


def _inventory_has_dc_motors(
    parts: List[Mapping[str, Any]] | None,
    resolved_modules: List[Mapping[str, Any]],
) -> bool:
    for part in parts or []:
        ptype = str(part.get("type") or "").lower()
        text = _part_text(part).lower()
        if ptype in _STEPPER_PART_TYPES or "stepper" in text:
            continue
        if ptype in _MOTOR_PART_TYPES:
            return True
        if "motor" in text and "driver" not in text:
            return True
    for row in resolved_modules:
        role = str(row.get("role") or "")
        module_id = str(row.get("module_id") or "")
        if role in {"mot", "load"} and module_id.startswith(_MOTOR_MODULE_PREFIXES):
            return True
    return False


def fill_salvage_gaps(
    resolved_modules: List[Dict[str, Any]],
    *,
    parts: List[Mapping[str, Any]] | None = None,
    donor_context: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Deterministic gap-fill for salvage (driver for motors, etc.) — no LLM.

    When functional_salvage already binds a donor actuator_driver, do not catalog-substitute
    L298N/A4988 — that was the junk→intent failure mode.
    """
    rows = [dict(row) for row in resolved_modules]
    # Drop unresolved donor_board placeholders once FS bound the same part.
    bound_names = {
        str(row.get("part_name") or "").strip().lower()
        for row in rows
        if str(row.get("source") or "") in _DONOR_SOURCES and row.get("module_id")
    }
    if bound_names:
        rows = [
            row
            for row in rows
            if not (
                str(row.get("source") or "") == "unresolved"
                and str(row.get("part_name") or "").strip().lower() in bound_names
            )
        ]

    donor_drv = donor_has_bound_driver(rows, donor_context)
    if donor_drv:
        # Strip dishonest catalog substitutes that slipped in before FS bind / workshop.
        rows = [
            row
            for row in rows
            if not (
                str(row.get("source") or "") in {"gap_fill", "goal_picker", "qwen_workshop"}
                and str(row.get("module_id") or "").strip() in _DRIVER_MODULE_IDS
            )
        ]

    module_ids = {str(row.get("module_id") or "").strip() for row in rows if row.get("module_id")}
    has_driver = bool(module_ids & _DRIVER_MODULE_IDS) or any(
        str(row.get("role") or "") == "drv" and row.get("module_id") for row in rows
    )
    if donor_drv:
        has_driver = True
    if (
        _inventory_has_stepper_motors(parts, rows)
        and not (module_ids & _STEPPER_DRIVER_MODULE_IDS)
        and not donor_drv
    ):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "part_name": "stepper driver (gap fill)",
                "module_id": "a4988-stepper",
                "role": "drv",
                "source": "gap_fill",
                "confidence": 0.72,
                "matched_on": "stepper_motor_without_driver",
            }
        )
        module_ids.add("a4988-stepper")
        has_driver = True
    if _inventory_has_dc_motors(parts, rows) and not has_driver:
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "part_name": "motor driver (gap fill)",
                "module_id": "l298n",
                "role": "drv",
                "source": "gap_fill",
                "confidence": 0.7,
                "matched_on": "dc_motor_without_driver",
            }
        )
    return coalesce_resolved_modules(parts or [], rows)


def infer_power_topology(
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]] | None = None,
    *,
    constraints: Mapping[str, Any] | None = None,
) -> str:
    """Return usb_5v | barrel_12v | hybrid from inventory."""
    resolved_modules = resolved_modules or []
    constraints_map = dict(constraints or {})
    battery_v = constraints_map.get("battery_voltage_v")
    has_barrel = any(_part_implies_barrel_12v(part) for part in parts)
    has_barrel_module = any(str(row.get("module_id") or "") == "dc-barrel-12v" for row in resolved_modules)
    if battery_v is not None:
        try:
            bv = float(battery_v)
            if bv >= 6.0:
                has_usb = any(_part_implies_usb_5v(part) for part in parts)
                has_usb_module = any(
                    str(row.get("module_id") or "") == "usb-power-5v" for row in resolved_modules
                )
                # Declared pack (e.g. 7.4V) without a barrel PSU → hybrid battery path, not 12V brick.
                if has_barrel or has_barrel_module:
                    return "barrel_12v" if not (has_usb or has_usb_module) else "hybrid"
                if has_usb or has_usb_module:
                    return "hybrid"
                return "hybrid"
        except (TypeError, ValueError):
            pass

    has_usb = any(_part_implies_usb_5v(part) for part in parts)
    has_usb_module = any(str(row.get("module_id") or "") == "usb-power-5v" for row in resolved_modules)
    usb_only = (has_usb or has_usb_module) and not (has_barrel or has_barrel_module)
    if usb_only:
        return "usb_5v"
    if has_barrel or has_barrel_module:
        return "barrel_12v"
    if has_usb or has_usb_module:
        return "hybrid"
    return "barrel_12v"


def overrides_from_resource_plan(diy_plan: Mapping[str, Any]) -> Dict[str, str]:
    """Map DIY resource_strategy selected_resources → role overrides."""
    resource_plan = dict(diy_plan.get("resource_plan") or {})
    selected = list(resource_plan.get("selected_resources") or [])
    if not selected:
        return {}
    pseudo_parts: List[Dict[str, Any]] = []
    for row in selected:
        if not isinstance(row, dict):
            continue
        caps = [str(c).lower() for c in (row.get("capabilities") or [])]
        pseudo_parts.append(
            {
                "name": str(row.get("name") or row.get("resource_id") or ""),
                "type": caps[0] if caps else str(row.get("resource_kind") or ""),
            }
        )
    if not pseudo_parts:
        return {}
    resolved = resolve_parts_to_modules(pseudo_parts)
    return module_overrides_for_build(build_id=None, resolved_modules=resolved)


def module_overrides_for_build(
    *,
    build_id: str | None,
    resolved_modules: List[Mapping[str, Any]],
    mcu_logic_voltage: float = 3.3,
) -> Dict[str, str]:
    """Role → module_id overrides from user inventory and substitution rules."""
    overrides: Dict[str, str] = {}
    # Pass 1: inventory / heuristic. Pass 2: donor FS wins for same role.
    for row in resolved_modules:
        module_id = row.get("module_id")
        role = row.get("role")
        if module_id and role and str(row.get("source") or "") not in _DONOR_SOURCES:
            overrides[str(role)] = str(module_id)
    for row in resolved_modules:
        module_id = row.get("module_id")
        role = row.get("role")
        if module_id and role and str(row.get("source") or "") in _DONOR_SOURCES:
            overrides[str(role)] = str(module_id)

    mcu_ids = {str(row.get("module_id") or "") for row in resolved_modules}
    has_esp32 = bool(mcu_ids & {"esp32-devkit", "esp32-cam-module"})
    # Camera brain wins over bare DevKit when inventory/goal already resolved a CAM module.
    if "esp32-cam-module" in mcu_ids:
        overrides["mcu"] = "esp32-cam-module"
    if (mcu_logic_voltage <= 3.4 or has_esp32) and overrides.get("drv") == "mosfet-irf520":
        overrides["drv"] = _SUBSTITUTIONS["mosfet-irf520"]
    if has_esp32 and overrides.get("drv") in {None, "mosfet-irf520"} and build_id == "automatic_plant_watering":
        overrides["drv"] = "mosfet-irlz44n"

    # LM2596 needs ≥7V in; prefer MP1584 when user only has 5V USB path.
    if build_id == "automatic_plant_watering" and overrides.get("buck") == "buck-lm2596":
        overrides["buck"] = "buck-mp1584"

    # Recipe role aliases — catalog recipes use usb/rly/svo, inventory may say pwr/relay/act.
    if overrides.get("pwr") in _USB_WALL_MODULE_IDS and "usb" not in overrides:
        overrides["usb"] = overrides["pwr"]
    if overrides.get("usb") == "usb-uart" and any(
        str(row.get("module_id") or "") in _USB_WALL_MODULE_IDS for row in resolved_modules
    ):
        overrides["usb"] = "usb-power-5v"
    if overrides.get("rly") is None:
        for key in ("relay", "drv"):
            mid = overrides.get(key)
            if mid and str(mid).startswith("relay"):
                overrides["rly"] = str(mid)
                break
    if overrides.get("svo") is None and overrides.get("act") in {"sg90", "mg996r"}:
        overrides["svo"] = overrides["act"]

    return overrides


def merge_module_overrides(*maps: Mapping[str, str] | None) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for mapping in maps:
        if not mapping:
            continue
        for key, value in mapping.items():
            if value:
                merged[str(key)] = str(value)
    return merged


def salvage_plan_input_from_intake(
    splice_plan: Mapping[str, Any],
    *,
    resolved_modules: List[Mapping[str, Any]] | None = None,
    module_overrides: Mapping[str, str] | None = None,
    power_topology: str | None = None,
    strategy_mode: str | None = None,
    compose_from_inventory: bool | None = None,
) -> Dict[str, Any]:
    """Shape consumed by plan-to-graph / compile_build_graph.cjs."""
    target = dict(splice_plan.get("target") or {})
    body: Dict[str, Any] = {
        "target": target,
        "reusable_blocks": list(splice_plan.get("reusable_blocks") or []),
        "build_candidates": list(splice_plan.get("build_candidates") or []),
    }
    if resolved_modules:
        body["resolved_modules"] = [dict(row) for row in resolved_modules]
    if module_overrides:
        body["module_overrides"] = dict(module_overrides)
    if power_topology:
        body["power_topology"] = power_topology
    if strategy_mode:
        body["strategy_mode"] = strategy_mode
    resolved_ids = [
        str(row.get("module_id") or "").strip()
        for row in (resolved_modules or [])
        if isinstance(row, dict) and str(row.get("module_id") or "").strip()
    ]
    build_id = str((target.get("recommended_build_id") or "")).strip()
    if compose_from_inventory is True:
        body["compose_from_inventory"] = True
    elif (
        strategy_mode == "constrained"
        and len(set(resolved_ids)) >= 2
        and build_id == "generic_low_voltage_build"
    ):
        body["compose_from_inventory"] = True
    return body
