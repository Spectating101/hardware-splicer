"""Export CircuitNetlist → KiCad `.kicad_sch` with catalog-pin fidelity.

Known module identities are emitted as embedded per-component symbols whose pin numbers,
pin names, and electrical types come directly from the Hardware Splicer module registry.
Each connected pin receives a short wire stub and a same-sheet local net label. This keeps
large generated schematics readable while preserving the actual endpoint graph for KiCad ERC.

Unknown/non-catalog components retain the historical generic-symbol fallback. The exporter is
still not an electrical authority: numeric voltage compatibility remains an HS evidence/contract
check, while KiCad ERC independently checks the electrical pin types that survive this lowering.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from ..netlist.ir import CircuitNetlist
from .schematic_pin_policy import (
    PowerFlagPlan,
    catalog_pins,
    pin_electrical_type,
    plan_no_connects,
    plan_power_flags,
)
from .schematic_symbols import EMBEDDED_LIB_IDS, embedded_schematic_lib_symbols, schematic_symbol_for_module


_PIN_SPACING_MM = 2.54
_PIN_X_MM = -7.62
_STUB_LENGTH_MM = 5.08


def _uid() -> str:
    return str(uuid.uuid4())


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _safe_token(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(text))
    return cleaned or "component"


def _pin_layout(pins: Sequence[Mapping[str, object]]) -> Dict[str, float]:
    count = len(pins)
    if not count:
        return {}
    start = -((count - 1) * _PIN_SPACING_MM) / 2.0
    return {
        str(pin.get("id")): start + index * _PIN_SPACING_MM
        for index, pin in enumerate(pins)
    }


def _dynamic_lib_id(ref: str, module_id: str) -> str:
    return f"HSNET:{_safe_token(ref)}_{_safe_token(module_id)}"


def _dynamic_symbol_definition(
    *,
    lib_id: str,
    ref: str,
    value: str,
    module_id: Optional[str],
    pins: Sequence[Mapping[str, object]],
) -> List[str]:
    layout = _pin_layout(pins)
    half_height = max(3.81, (max((abs(row) for row in layout.values()), default=0.0) + 2.54))
    name = lib_id.split(":", 1)[1]
    result = [
        f'    (symbol "{_esc(lib_id)}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
        f'      (property "Reference" "{_esc(ref[:1] or "U")}" (at 0 {half_height + 2.54:.4f} 0) (effects (font (size 1.27 1.27))))',
        f'      (property "Value" "{_esc(value)}" (at 0 {-half_height - 2.54:.4f} 0) (effects (font (size 1.27 1.27))))',
        f'      (symbol "{_esc(name)}_0_1"',
        f'        (rectangle (start -5.08 {half_height:.4f}) (end 5.08 {-half_height:.4f}) (stroke (width 0.254) (type default)) (fill (type background)))',
    ]
    for pin in pins:
        pin_id = str(pin.get("id"))
        pin_name = str(pin.get("label") or pin_id)
        y = layout[pin_id]
        result.append(
            f'        (pin {pin_electrical_type(module_id, pin)} line (at {_PIN_X_MM:.4f} {y:.4f} 0) (length 2.54) '
            f'(name "{_esc(pin_name)}" (effects (font (size 1.27 1.27)))) (number "{_esc(pin_id)}"))'
        )
    result.extend(["      )", "    )"])
    return result


_PWR_FLAG_LIB_ID = "power:PWR_FLAG"


def _pwr_flag_lib_symbol() -> List[str]:
    return [
        f'    (symbol "{_PWR_FLAG_LIB_ID}" (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom no) (on_board no)',
        '      (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) hide))',
        '      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))',
        '      (symbol "PWR_FLAG_0_0"',
        '        (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1"))',
        "      )",
        '      (symbol "PWR_FLAG_0_1"',
        '        (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))',
        "      )",
        "    )",
    ]


def _pwr_flag_instance(number: int, x: float, y: float, plan: PowerFlagPlan) -> List[str]:
    return [
        "  (symbol",
        f'    (lib_id "{_PWR_FLAG_LIB_ID}")',
        f"    (at {x:.4f} {y:.4f} 0)",
        "    (unit 1)",
        "    (in_bom no)",
        "    (on_board no)",
        f'    (uuid "{_uid()}")',
        f'    (property "Reference" "#FLG{number:02d}" (at {x:.4f} {y - 2.54:.4f} 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (property "Value" "PWR_FLAG" (at {x:.4f} {y - 5.08:.4f} 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (property "HS_FedBy" "{_esc(plan.source)}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (pin "1" (uuid "{_uid()}"))',
        "    (instances",
        '      (project "hardware-splicer"',
        f'        (path "/" (reference "#FLG{number:02d}") (unit 1))',
        "      )",
        "    )",
        "  )",
    ]


def netlist_to_kicad_schematic(
    netlist: CircuitNetlist,
    *,
    title: str = "Hardware-Splicer compile",
    build_id: Optional[str] = None,
) -> str:
    """Generate a KiCad schematic preserving every known catalog endpoint pin.

    ``build_id`` selects per-build pin policy (recipe-note terminals); without it only the
    module-level and microcontroller rules apply. No-connect flags and PWR_FLAGs come from
    :mod:`schematic_pin_policy`, never from ERC output.
    """

    dynamic_defs: List[str] = []
    component_pins: Dict[str, list[Dict[str, object]]] = {}
    component_lib_ids: Dict[str, str] = {}
    seen_lib_ids: set[str] = set()
    for comp in netlist.components:
        pins = catalog_pins(comp.module_id)
        component_pins[comp.ref] = pins
        if not pins:
            continue
        lib_id = _dynamic_lib_id(comp.ref, str(comp.module_id or comp.ref))
        component_lib_ids[comp.ref] = lib_id
        if lib_id in seen_lib_ids:
            continue
        seen_lib_ids.add(lib_id)
        dynamic_defs.extend(
            _dynamic_symbol_definition(
                lib_id=lib_id,
                ref=comp.ref,
                value=str(comp.value or comp.module_id or comp.ref),
                module_id=comp.module_id,
                pins=pins,
            )
        )

    flag_plans = plan_power_flags(netlist)
    no_connect_plans = plan_no_connects(netlist, build_id=build_id)

    lines: List[str] = [
        '(kicad_sch (version 20250114) (generator "hardware-splicer")',
        f'  (uuid "{_uid()}")',
        '  (paper "A4")',
        "  (lib_symbols",
        *embedded_schematic_lib_symbols(),
        *dynamic_defs,
        *(_pwr_flag_lib_symbol() if flag_plans else []),
        "  )",
    ]

    pin_positions: Dict[str, Dict[str, tuple[float, float]]] = {}

    for index, comp in enumerate(netlist.components):
        x = 33.02 + (index % 3) * 66.04
        y = 33.02 + (index // 3) * 55.88
        pins = component_pins.get(comp.ref) or []
        layout = _pin_layout(pins)
        _fallback_lib, _prefix, footprint = schematic_symbol_for_module(
            comp.module_id,
            ref=comp.ref,
            value=str(comp.value or ""),
        )
        footprint = str(comp.footprint or footprint)

        if pins:
            sheet_lib = component_lib_ids[comp.ref]
            # KiCad library-symbol Y coordinates are Cartesian (positive up), while
            # schematic sheet coordinates increase downward. Project local pin Y with
            # the opposite sign so wire stubs/no-connect markers land on the real pins.
            pin_positions[comp.ref] = {
                str(pin.get("id")): (x + _PIN_X_MM, y - layout[str(pin.get("id"))])
                for pin in pins
            }
        else:
            sheet_lib = _fallback_lib if _fallback_lib in EMBEDDED_LIB_IDS else "HS:ModuleBlock"
            pin_positions[comp.ref] = {"1": (x + _PIN_X_MM, y + 2.54), "2": (x + _PIN_X_MM, y - 2.54)}

        lines.extend(
            [
                "  (symbol",
                f'    (lib_id "{_esc(sheet_lib)}")',
                f"    (at {x:.4f} {y:.4f} 0)",
                "    (unit 1)",
                "    (in_bom yes)",
                "    (on_board yes)",
                f'    (uuid "{_uid()}")',
                f'    (property "Reference" "{_esc(comp.ref)}" (at {x:.4f} {y - 10.16:.4f} 0)',
                '      (effects (font (size 1.27 1.27))))',
                f'    (property "Value" "{_esc(comp.value or comp.module_id or comp.ref)}" (at {x:.4f} {y + 10.16:.4f} 0)',
                '      (effects (font (size 1.27 1.27))))',
                f'    (property "Footprint" "{_esc(footprint)}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
                f'    (property "HS_ModuleId" "{_esc(str(comp.module_id or ""))}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
            ]
        )

        if pins:
            for pin in pins:
                pin_id = str(pin.get("id"))
                lines.append(f'    (pin "{_esc(pin_id)}" (uuid "{_uid()}"))')
        else:
            lines.extend(
                [
                    f'    (pin "1" (uuid "{_uid()}"))',
                    f'    (pin "2" (uuid "{_uid()}"))',
                ]
            )

        lines.extend(
            [
                "    (instances",
                '      (project "hardware-splicer"',
                f'        (path "/" (reference "{_esc(comp.ref)}") (unit 1))',
                "      )",
                "    )",
                "  )",
            ]
        )

    # Connect the exact endpoint pin to a short stub carrying a local same-sheet net label.
    for net in netlist.nets:
        for pin_ref in net.pins:
            position = pin_positions.get(pin_ref.component_ref, {}).get(pin_ref.pin)
            if position is None:
                # Preserve historical fallback compatibility for opaque components while
                # leaving catalog endpoint validation to the electrical truth layer.
                position = pin_positions.get(pin_ref.component_ref, {}).get("1")
            if position is None:
                continue
            px, py = position
            stub_x = px - _STUB_LENGTH_MM
            lines.extend(
                [
                    "  (wire",
                    f'    (pts (xy {px:.4f} {py:.4f}) (xy {stub_x:.4f} {py:.4f}))',
                    '    (stroke (width 0) (type default))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                    f'  (label "{_esc(net.name)}" (at {stub_x:.4f} {py:.4f} 180)',
                    '    (effects (font (size 1.27 1.27)) (justify right bottom))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                ]
            )

    # Off-board feeds: one PWR_FLAG per net that needs it, planned from connector/module data.
    for number, plan in enumerate(flag_plans, start=1):
        position = pin_positions.get(plan.ref, {}).get(plan.pin)
        if position is None:
            continue
        px, py = position
        stub_x = px - _STUB_LENGTH_MM
        if plan.stub:
            lines.extend(
                [
                    "  (wire",
                    f'    (pts (xy {px:.4f} {py:.4f}) (xy {stub_x:.4f} {py:.4f}))',
                    '    (stroke (width 0) (type default))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                    f'  (label "{_esc(plan.net)}" (at {stub_x:.4f} {py:.4f} 180)',
                    '    (effects (font (size 1.27 1.27)) (justify right bottom))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                ]
            )
        lines.extend(_pwr_flag_instance(number, stub_x, py, plan))

    for plan in no_connect_plans:
        position = pin_positions.get(plan.ref, {}).get(plan.pin)
        if position is None:
            continue
        x, y = position
        lines.extend(
            [
                "  (no_connect",
                f"    (at {x:.4f} {y:.4f})",
                f'    (uuid "{_uid()}")',
                "  )",
            ]
        )

    lines.append(f'  (title_block (title "{_esc(title)}") (date "") (rev "1") (company "Hardware-Splicer"))')
    lines.append(")")
    return "\n".join(lines) + "\n"


def write_schematic_for_netlist(
    netlist: CircuitNetlist,
    out_path: str | Path,
    *,
    title: Optional[str] = None,
    build_id: Optional[str] = None,
) -> str:
    path = Path(out_path)
    text = netlist_to_kicad_schematic(
        netlist, title=title or "Hardware-Splicer compile", build_id=build_id
    )
    path.write_text(text, encoding="utf-8")
    return str(path)
