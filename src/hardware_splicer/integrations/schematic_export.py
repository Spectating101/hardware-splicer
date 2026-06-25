"""Export CircuitNetlist → KiCad 9 `.kicad_sch` (minimal valid sheet)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..netlist.ir import CircuitNetlist
from .schematic_symbols import EMBEDDED_LIB_IDS, embedded_schematic_lib_symbols, schematic_symbol_for_module


def _uid() -> str:
    return str(uuid.uuid4())


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def netlist_to_kicad_schematic(
    netlist: CircuitNetlist,
    *,
    title: str = "Hardware-Splicer compile",
) -> str:
    """Generate a KiCad 9 schematic with connector symbols and net wires."""
    lines: List[str] = [
        '(kicad_sch (version 20250114) (generator "hardware-splicer")',
        f'  (uuid "{_uid()}")',
        '  (paper "A4")',
        "  (lib_symbols",
        *embedded_schematic_lib_symbols(),
        "  )",
    ]

    ref_positions: Dict[str, tuple[float, float]] = {}
    pin_positions: Dict[str, Dict[str, tuple[float, float]]] = {}
    for index, comp in enumerate(netlist.components):
        x = 25.4 + (index % 4) * 50.8
        y = 25.4 + (index // 4) * 38.1
        lib_id, _prefix, footprint = schematic_symbol_for_module(
            comp.module_id, ref=comp.ref, value=str(comp.value or "")
        )
        footprint = str(comp.footprint or footprint)
        sheet_lib = lib_id if lib_id in EMBEDDED_LIB_IDS else "HS:ModuleBlock"
        ref_positions[comp.ref] = (x, y)
        pin_positions[comp.ref] = {"1": (x, y)}
        lines.extend(
            [
                "  (symbol",
                f'    (lib_id "{_esc(sheet_lib)}")',
                f"    (at {x:.4f} {y:.4f} 0)",
                f'    (uuid "{_uid()}")',
                f'    (property "Reference" "{_esc(comp.ref)}" (at {x:.4f} {y - 6.35:.4f} 0)',
                '      (effects (font (size 1.27 1.27))))',
                f'    (property "Value" "{_esc(comp.value or comp.module_id or comp.ref)}" (at {x:.4f} {y + 6.35:.4f} 0)',
                '      (effects (font (size 1.27 1.27))))',
                f'    (property "Footprint" "{_esc(footprint)}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
                f'    (property "HS_ModuleId" "{_esc(str(comp.module_id or ""))}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
                '    (instances',
                "      (project hardware-splicer",
                "        (path / (reference " + f'"{_esc(comp.ref)}")' + " (unit 1))",
                "      )",
                "    )",
                "  )",
            ]
        )

    for net in netlist.nets:
        if len(net.pins) < 2:
            continue
        anchor = net.pins[0]
        ax, ay = pin_positions.get(anchor.component_ref, {}).get("1", (0.0, 0.0))
        for pin_ref in net.pins[1:]:
            bx, by = pin_positions.get(pin_ref.component_ref, {}).get("1", (0.0, 0.0))
            mid_x = (ax + bx) / 2
            lines.extend(
                [
                    "  (wire",
                    f'    (pts (xy {ax:.4f} {ay:.4f}) (xy {mid_x:.4f} {ay:.4f}))',
                    '    (stroke (width 0) (type default))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                    "  (wire",
                    f'    (pts (xy {mid_x:.4f} {ay:.4f}) (xy {mid_x:.4f} {by:.4f}))',
                    '    (stroke (width 0) (type default))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                    "  (wire",
                    f'    (pts (xy {mid_x:.4f} {by:.4f}) (xy {bx:.4f} {by:.4f}))',
                    '    (stroke (width 0) (type default))',
                    f'    (uuid "{_uid()}")',
                    "  )",
                    f'  (label "{_esc(net.name)}" (at {mid_x:.4f} {(ay + by) / 2:.4f} 0)',
                    '    (effects (font (size 1.27 1.27)) (justify left bottom))',
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
) -> str:
    path = Path(out_path)
    text = netlist_to_kicad_schematic(netlist, title=title or "Hardware-Splicer compile")
    path.write_text(text, encoding="utf-8")
    return str(path)
