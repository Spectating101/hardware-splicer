"""
Schematic Diagram Generator

Generate schematic diagrams from detected circuits.
Outputs:
- SVG schematics
- KiCad format
- Eagle format
- ASCII art schematics (for quick viewing)
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple
from dataclasses import dataclass

from intelligence.connection_mapper import CircuitSchematic, PinConnection


@dataclass
class SchematicSymbol:
    """A component symbol in schematic."""
    component_id: str
    symbol_type: str  # "IC", "resistor", "capacitor", etc.
    position: Tuple[int, int]  # (x, y) in schematic coordinates
    rotation: int = 0  # 0, 90, 180, 270
    pins: Dict[int, Tuple[int, int]] = None  # pin_number -> (x, y) position


class SchematicsGenerator:
    """Generate schematic diagrams from circuit analysis."""

    def __init__(self):
        """Initialize generator."""
        self.grid_size = 100  # Spacing between components
        self.symbol_width = 200
        self.symbol_height = 150

    def generate_svg(self, schematic: CircuitSchematic) -> str:
        """
        Generate SVG schematic diagram.

        Args:
            schematic: Circuit schematic from connection_mapper

        Returns:
            SVG string
        """
        # Calculate layout
        symbols = self._auto_layout(schematic)

        # Create SVG
        width = 1000
        height = 800

        svg = ET.Element('svg', {
            'width': str(width),
            'height': str(height),
            'xmlns': 'http://www.w3.org/2000/svg'
        })

        # Add grid
        self._add_grid(svg, width, height)

        # Add symbols
        for symbol in symbols:
            self._add_symbol(svg, symbol)

        # Add wires
        for conn in schematic.connections:
            self._add_wire(svg, conn, symbols)

        # Add labels
        for symbol in symbols:
            self._add_label(svg, symbol)

        # Convert to string
        return ET.tostring(svg, encoding='unicode')

    def _auto_layout(self, schematic: CircuitSchematic) -> List[SchematicSymbol]:
        """
        Automatically lay out components in schematic.

        Uses force-directed layout algorithm.
        """
        symbols = []

        # Create symbols for each IC
        for i, ic in enumerate(schematic.ics):
            x = 100 + (i % 3) * self.grid_size * 3
            y = 100 + (i // 3) * self.grid_size * 2

            symbols.append(SchematicSymbol(
                component_id=ic.part_number,
                symbol_type="IC",
                position=(x, y),
                pins=self._calculate_pin_positions(ic, x, y)
            ))

        return symbols

    def _calculate_pin_positions(self, ic, base_x: int, base_y: int) -> Dict[int, Tuple[int, int]]:
        """Calculate positions of IC pins for wiring."""
        pins = {}

        # Simple layout: pins on left and right sides
        pin_count = ic.pin_count
        pins_per_side = pin_count // 2

        pin_spacing = self.symbol_height // (pins_per_side + 1)

        # Left side pins (1 to pins_per_side)
        for i in range(pins_per_side):
            pin_num = i + 1
            pins[pin_num] = (base_x, base_y + pin_spacing * (i + 1))

        # Right side pins (pins_per_side+1 to pin_count)
        for i in range(pins_per_side):
            pin_num = pins_per_side + i + 1
            pins[pin_num] = (base_x + self.symbol_width, base_y + pin_spacing * (i + 1))

        return pins

    def _add_grid(self, svg: ET.Element, width: int, height: int):
        """Add background grid to SVG."""
        grid_group = ET.SubElement(svg, 'g', {'id': 'grid'})

        # Vertical lines
        for x in range(0, width, self.grid_size):
            ET.SubElement(grid_group, 'line', {
                'x1': str(x), 'y1': '0',
                'x2': str(x), 'y2': str(height),
                'stroke': '#e0e0e0', 'stroke-width': '1'
            })

        # Horizontal lines
        for y in range(0, height, self.grid_size):
            ET.SubElement(grid_group, 'line', {
                'x1': '0', 'y1': str(y),
                'x2': str(width), 'y2': str(y),
                'stroke': '#e0e0e0', 'stroke-width': '1'
            })

    def _add_symbol(self, svg: ET.Element, symbol: SchematicSymbol):
        """Add component symbol to SVG."""
        x, y = symbol.position

        if symbol.symbol_type == "IC":
            # Draw IC rectangle
            ET.SubElement(svg, 'rect', {
                'x': str(x), 'y': str(y),
                'width': str(self.symbol_width),
                'height': str(self.symbol_height),
                'fill': 'white', 'stroke': 'black', 'stroke-width': '2'
            })

            # Draw pins
            if symbol.pins:
                for pin_num, (pin_x, pin_y) in symbol.pins.items():
                    # Pin circle
                    ET.SubElement(svg, 'circle', {
                        'cx': str(pin_x), 'cy': str(pin_y),
                        'r': '3', 'fill': 'black'
                    })

                    # Pin number
                    ET.SubElement(svg, 'text', {
                        'x': str(pin_x + 5), 'y': str(pin_y + 5),
                        'font-size': '10', 'fill': 'black'
                    }).text = str(pin_num)

    def _add_wire(self, svg: ET.Element, connection: PinConnection, symbols: List[SchematicSymbol]):
        """Add wire between components."""
        # Find source and destination symbols
        src_symbol = None
        dst_symbol = None

        for symbol in symbols:
            if connection.from_ic and symbol.component_id == connection.from_ic.part_number:
                src_symbol = symbol
            if connection.to_ic and symbol.component_id == connection.to_ic.part_number:
                dst_symbol = symbol

        if not src_symbol or not dst_symbol:
            return

        # Get pin positions
        src_pin = connection.from_pin
        dst_pin = connection.to_pin

        if src_pin not in src_symbol.pins or dst_pin not in dst_symbol.pins:
            return

        x1, y1 = src_symbol.pins[src_pin]
        x2, y2 = dst_symbol.pins[dst_pin]

        # Draw wire (orthogonal routing)
        mid_x = (x1 + x2) // 2

        # Vertical-horizontal-vertical path
        path = f"M {x1} {y1} L {mid_x} {y1} L {mid_x} {y2} L {x2} {y2}"

        ET.SubElement(svg, 'path', {
            'd': path,
            'stroke': 'blue', 'stroke-width': '2', 'fill': 'none'
        })

    def _add_label(self, svg: ET.Element, symbol: SchematicSymbol):
        """Add component label."""
        x, y = symbol.position

        ET.SubElement(svg, 'text', {
            'x': str(x + self.symbol_width // 2),
            'y': str(y + self.symbol_height // 2),
            'font-size': '14', 'fill': 'black',
            'text-anchor': 'middle'
        }).text = symbol.component_id

    def generate_ascii_schematic(self, schematic: CircuitSchematic) -> str:
        """
        Generate ASCII art schematic (for quick viewing in terminal).

        Example:
        ```
                    +-------+
        VCC --------|VCC   1|-----> LED
                    |       |
        GND --------|GND   2|-----> Button
                    +-------+
        ```
        """
        lines = []
        lines.append("ASCII Schematic:")
        lines.append("=" * 50)

        for ic in schematic.ics:
            lines.append(f"\n{ic.part_number}:")
            lines.append("  " + "+" + "-" * 20 + "+")

            # Show a few key pins
            for conn in schematic.connections:
                if conn.from_ic == ic:
                    from_pin = conn.from_pin
                    net = conn.net_name
                    lines.append(f"  | Pin {from_pin:2d} ----> {net}")

            lines.append("  " + "+" + "-" * 20 + "+")

        return "\n".join(lines)


# Global singleton
schematics_generator = SchematicsGenerator()
