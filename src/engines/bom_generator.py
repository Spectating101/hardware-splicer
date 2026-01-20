#!/usr/bin/env python3
"""
BOM (Bill of Materials) Generator

Extracts components from KiCAD netlist and generates BOM with:
- Component references
- Values
- Footprints
- Quantities
- DigiKey part numbers (when available)
- Pricing information
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from src.engines.kicad_sexp import parse_sexp_file, sexp_find_all


@dataclass
class BOMItem:
    """Single item in bill of materials"""
    references: List[str]  # e.g., ["R1", "R2", "R3"]
    value: str  # e.g., "10K", "100nF"
    footprint: str  # e.g., "Resistor_SMD:R_0805"
    quantity: int
    part_number: Optional[str] = None  # DigiKey/JLCPCB part number
    description: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    supplier: Optional[str] = None
    supplier_link: Optional[str] = None


class BOMGenerator:
    """Generate BOM from KiCAD netlist"""

    # Common component mappings to DigiKey
    DIGIKEY_MAPPINGS = {
        # Resistors (0805)
        "10K": "RMCF0805FT10K0CT-ND",
        "4.7K": "RMCF0805FT4K70CT-ND",
        "1K": "RMCF0805FT1K00CT-ND",

        # Capacitors (0805)
        "100nF": "1276-1003-1-ND",  # Ceramic 100nF 0805
        "10uF": "1276-1096-1-ND",  # Ceramic 10uF 0805
        "1uF": "1276-1066-1-ND",  # Ceramic 1uF 0805

        # Common ICs
        "ESP32": "1965-ESP32-WROOM-32ECT-ND",
        "AMS1117-3.3": "1470-3603-1-ND",
        "BME280": "828-1063-1-ND",
    }

    # Estimated pricing (fallback if DigiKey API not available)
    PRICE_ESTIMATES = {
        "resistor": 0.10,
        "capacitor": 0.15,
        "led": 0.20,
        "ic": 5.00,
        "connector": 0.50,
    }

    def __init__(self):
        pass

    def parse_kicad_netlist(self, netlist_path: str) -> List[Dict]:
        """
        Parse a KiCad netlist and extract components.

        Supports:
        - KiCad CLI netlist export: `--format kicadsexpr` (preferred)
        - Best-effort regex fallback for older/partial netlists
        """
        p = Path(netlist_path)
        if not p.exists():
            return []

        # Peek a small prefix to decide parser strategy.
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:4096]
        except Exception:
            head = ""

        # 0) KiCad XML netlist (kicadxml) - common on older flows.
        if "<export" in head and "<components" in head and "<comp" in head:
            try:
                root = ET.parse(str(p)).getroot()
                comps: List[Dict[str, str]] = []
                for comp in root.findall(".//components/comp"):
                    ref = (comp.get("ref") or "").strip()
                    value = (comp.findtext("value") or "").strip()
                    footprint = (comp.findtext("footprint") or "").strip()
                    if ref:
                        comps.append({"reference": ref, "value": value, "footprint": footprint})
                if comps:
                    return comps
            except Exception:
                # Fall back to other methods.
                pass

        # 1) Robust parse via S-expression (KiCad 6+ style kicadsexpr netlist)
        try:
            ast = parse_sexp_file(str(p))
            comps = []
            for comp in sexp_find_all(ast, "comp"):
                ref = ""
                value = ""
                footprint = ""

                for child in comp:
                    if not isinstance(child, list) or len(child) < 2:
                        continue
                    head = child[0]
                    if head == "ref" and isinstance(child[1], str):
                        ref = child[1]
                    elif head == "value" and isinstance(child[1], str):
                        value = child[1]
                    elif head == "footprint" and isinstance(child[1], str):
                        footprint = child[1]

                if ref:
                    comps.append({"reference": ref, "value": value, "footprint": footprint})

            if comps:
                return comps
        except Exception:
            # fall back to regex parsing
            pass

        # 2) Regex fallback (older exports)
        components: List[Dict] = []
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            # Example: (comp (ref R1) (value 10K) (footprint Resistor_SMD:R_0805))
            comp_pattern = r"\(comp\s+\(ref\s+([^)\\s]+)\)\s+\(value\s+([^)]+)\)(?:\s+\(footprint\s+([^)]+)\))?"
            for match in re.finditer(comp_pattern, content):
                ref = match.group(1).strip().strip('"')
                value = match.group(2).strip().strip('"')
                footprint = match.group(3).strip().strip('"') if match.group(3) else ""
                components.append({"reference": ref, "value": value, "footprint": footprint})
        except Exception:
            return []

        return components

    def group_components(self, components: List[Dict]) -> List[BOMItem]:
        """Group components by value and footprint"""
        grouped = {}

        for comp in components:
            value = comp['value']
            footprint = comp['footprint']
            key = (value, footprint)

            if key not in grouped:
                grouped[key] = {
                    'references': [],
                    'value': value,
                    'footprint': footprint,
                }

            grouped[key]['references'].append(comp['reference'])

        # Convert to BOMItem list
        bom_items = []
        for (value, footprint), data in grouped.items():
            item = BOMItem(
                references=sorted(data['references']),
                value=value,
                footprint=footprint,
                quantity=len(data['references'])
            )
            bom_items.append(item)

        return sorted(bom_items, key=lambda x: x.references[0])

    def add_part_numbers(self, bom_items: List[BOMItem]) -> List[BOMItem]:
        """Add DigiKey part numbers to BOM items"""
        for item in bom_items:
            # Try to find DigiKey part number
            if item.value in self.DIGIKEY_MAPPINGS:
                item.part_number = self.DIGIKEY_MAPPINGS[item.value]
                item.supplier = "DigiKey"
                item.supplier_link = f"https://www.digikey.com/en/products/detail/{item.part_number}"

        return bom_items

    def add_pricing(self, bom_items: List[BOMItem], include_pricing: bool = False) -> List[BOMItem]:
        """Add pricing information (estimated or from API)"""
        if not include_pricing:
            return bom_items

        for item in bom_items:
            # Determine component type from reference
            ref = item.references[0]
            comp_type = None

            if ref.startswith('R'):
                comp_type = 'resistor'
            elif ref.startswith('C'):
                comp_type = 'capacitor'
            elif ref.startswith('D') or ref.startswith('LED'):
                comp_type = 'led'
            elif ref.startswith('U'):
                comp_type = 'ic'
            elif ref.startswith('J') or ref.startswith('P'):
                comp_type = 'connector'

            if comp_type:
                item.unit_price = self.PRICE_ESTIMATES.get(comp_type, 1.00)
                item.total_price = item.unit_price * item.quantity

        return bom_items

    def generate_bom(self, netlist_path: str, include_pricing: bool = False) -> Dict:
        """Generate complete BOM from KiCAD netlist"""
        # Parse netlist
        components = self.parse_kicad_netlist(netlist_path)

        if not components:
            return {
                'status': 'error',
                'message': 'No components found in netlist',
                'items': []
            }

        # Group components
        bom_items = self.group_components(components)

        # Add part numbers
        bom_items = self.add_part_numbers(bom_items)

        # Add pricing
        bom_items = self.add_pricing(bom_items, include_pricing)

        # Calculate totals
        total_components = len(components)
        unique_parts = len(bom_items)
        total_cost = sum(item.total_price or 0 for item in bom_items)
        parts_with_numbers = sum(1 for item in bom_items if item.part_number)

        return {
            'status': 'success',
            'summary': {
                'total_components': total_components,
                'unique_parts': unique_parts,
                'parts_with_digikey_numbers': parts_with_numbers,
                'estimated_total_cost': total_cost if include_pricing else None
            },
            'items': [
                {
                    'references': item.references,
                    'value': item.value,
                    'footprint': item.footprint,
                    'quantity': item.quantity,
                    'part_number': item.part_number,
                    'supplier': item.supplier,
                    'supplier_link': item.supplier_link,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                }
                for item in bom_items
            ]
        }

    def export_csv(self, bom: Dict) -> str:
        """Export BOM to CSV format"""
        lines = []

        # Header
        lines.append("Reference,Value,Footprint,Quantity,Part Number,Supplier,Unit Price,Total Price")

        # Items
        for item in bom['items']:
            refs = '+'.join(item['references'])
            line = f"{refs},{item['value']},{item['footprint']},{item['quantity']}," \
                   f"{item['part_number'] or ''},{item['supplier'] or ''}," \
                   f"{item['unit_price'] or ''},{item['total_price'] or ''}"
            lines.append(line)

        # Summary
        lines.append("")
        lines.append(f"Total Components,{bom['summary']['total_components']}")
        lines.append(f"Unique Parts,{bom['summary']['unique_parts']}")
        if bom['summary']['estimated_total_cost']:
            lines.append(f"Estimated Total Cost,${bom['summary']['estimated_total_cost']:.2f}")

        return '\n'.join(lines)


def demo():
    """Demo BOM generation"""
    print("="*70)
    print("  BOM GENERATOR DEMO")
    print("="*70)
    print()

    generator = BOMGenerator()

    # Create sample netlist for demo
    sample_netlist = """
    (export (version D)
      (components
        (comp (ref R1) (value 10K) (footprint Resistor_SMD:R_0805))
        (comp (ref R2) (value 10K) (footprint Resistor_SMD:R_0805))
        (comp (ref R3) (value 4.7K) (footprint Resistor_SMD:R_0805))
        (comp (ref C1) (value 100nF) (footprint Capacitor_SMD:C_0805))
        (comp (ref C2) (value 10uF) (footprint Capacitor_SMD:C_0805))
        (comp (ref U1) (value ESP32) (footprint RF_Module:ESP32-WROOM-32))
        (comp (ref U2) (value AMS1117-3.3) (footprint Package_TO_SOT_SMD:SOT-223-3))
      )
    )
    """

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.net', delete=False) as f:
        f.write(sample_netlist)
        netlist_path = f.name

    # Generate BOM
    bom = generator.generate_bom(netlist_path, include_pricing=True)

    print(f"Status: {bom['status']}")
    print()
    print("Summary:")
    print(f"  Total Components: {bom['summary']['total_components']}")
    print(f"  Unique Parts: {bom['summary']['unique_parts']}")
    print(f"  Parts with DigiKey #: {bom['summary']['parts_with_digikey_numbers']}")
    if bom['summary']['estimated_total_cost']:
        print(f"  Estimated Cost: ${bom['summary']['estimated_total_cost']:.2f}")
    print()

    print("BOM Items:")
    print("-" * 70)
    for item in bom['items']:
        refs = ', '.join(item['references'])
        print(f"{refs:20} {item['value']:15} x{item['quantity']}")
        if item['part_number']:
            print(f"{'':20} DigiKey: {item['part_number']}")
        if item['total_price']:
            print(f"{'':20} Cost: ${item['total_price']:.2f}")
        print()

    # CSV export
    print("CSV Export:")
    print("-" * 70)
    csv = generator.export_csv(bom)
    print(csv)

    # Cleanup
    import os
    os.unlink(netlist_path)


if __name__ == '__main__':
    demo()
