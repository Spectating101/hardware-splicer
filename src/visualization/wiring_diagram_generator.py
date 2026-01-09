#!/usr/bin/env python3
"""
Visual Wiring Diagram Generator for Circuit-AI
Generates breadboard-style SVG diagrams showing component placement and wiring
"""

from pathlib import Path
from typing import List, Dict, Tuple
import json


class WiringDiagramGenerator:
    """Generates SVG breadboard diagrams for Arduino projects"""

    def __init__(self):
        # Breadboard dimensions (standard half-size breadboard)
        self.breadboard_width = 800
        self.breadboard_height = 500
        self.hole_spacing = 10
        self.rows = 30
        self.cols = 63

        # Colors
        self.colors = {
            'breadboard': '#FFFACD',
            'power_rail_pos': '#FF0000',
            'power_rail_neg': '#0000FF',
            'wire_5v': '#FF0000',
            'wire_gnd': '#000000',
            'wire_signal': '#00FF00',
            'wire_i2c_sda': '#FFFF00',
            'wire_i2c_scl': '#FFA500',
            'component': '#4169E1',
            'arduino': '#00979D'
        }

        # Standard component sizes
        self.component_sizes = {
            'arduino_uno': (55, 70),
            'esp32': (50, 30),
            'esp8266': (25, 35),
            'sensor_small': (15, 15),  # DHT, PIR, etc.
            'sensor_large': (20, 20),  # BME280, etc.
            'display_oled': (30, 30),
            'lcd_16x2': (80, 36),
            'led': (5, 5),
            'resistor': (2, 10),
            'relay': (20, 20),
            'servo': (23, 12)
        }

    def generate_diagram(self, design: Dict, output_path: str) -> str:
        """
        Generate complete wiring diagram SVG

        Args:
            design: Circuit design dict with microcontroller, components, connections
            output_path: Path to save SVG file

        Returns:
            Path to generated SVG file
        """
        svg_content = []

        # SVG header
        svg_content.append(f'''<svg width="{self.breadboard_width + 400}" height="{self.breadboard_height + 200}"
            xmlns="http://www.w3.org/2000/svg">''')

        # Title
        svg_content.append(f'''<text x="20" y="30" font-size="24" font-weight="bold">
            {design.get('project_name', 'Circuit Diagram')}</text>''')

        # Draw breadboard
        svg_content.append(self._draw_breadboard(50, 70))

        # Draw microcontroller
        mcu_type = design.get('microcontroller', 'arduino_uno')
        mcu_pos = (900, 150)
        svg_content.append(self._draw_microcontroller(mcu_type, mcu_pos))

        # Draw components on breadboard
        component_positions = {}
        y_offset = 150
        for i, component in enumerate(design.get('components', [])):
            pos = (150 + (i * 100), y_offset)
            component_positions[component['id']] = pos
            svg_content.append(self._draw_component(component, pos))

        # Draw wiring connections
        connections = self._generate_connections(design, mcu_pos, component_positions)
        for connection in connections:
            svg_content.append(connection)

        # Legend
        svg_content.append(self._draw_legend(50, self.breadboard_height + 120))

        # SVG footer
        svg_content.append('</svg>')

        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text('\n'.join(svg_content))

        return str(output_file)

    def _draw_breadboard(self, x: int, y: int) -> str:
        """Draw breadboard base with holes and power rails"""
        svg = []

        # Breadboard background
        svg.append(f'''<rect x="{x}" y="{y}" width="{self.breadboard_width}"
            height="{self.breadboard_height}" fill="{self.colors['breadboard']}"
            stroke="#999" stroke-width="2" rx="10"/>''')

        # Power rails (top)
        rail_y = y + 20
        svg.append(f'''<line x1="{x+20}" y1="{rail_y}" x2="{x+self.breadboard_width-20}"
            y2="{rail_y}" stroke="{self.colors['power_rail_pos']}" stroke-width="8"/>''')
        svg.append(f'''<line x1="{x+20}" y1="{rail_y+15}" x2="{x+self.breadboard_width-20}"
            y2="{rail_y+15}" stroke="{self.colors['power_rail_neg']}" stroke-width="8"/>''')

        # Power rails (bottom)
        rail_y = y + self.breadboard_height - 35
        svg.append(f'''<line x1="{x+20}" y1="{rail_y}" x2="{x+self.breadboard_width-20}"
            y2="{rail_y}" stroke="{self.colors['power_rail_pos']}" stroke-width="8"/>''')
        svg.append(f'''<line x1="{x+20}" y1="{rail_y+15}" x2="{x+self.breadboard_width-20}"
            y2="{rail_y+15}" stroke="{self.colors['power_rail_neg']}" stroke-width="8"/>''')

        # Labels
        svg.append(f'''<text x="{x+self.breadboard_width-15}" y="{y+25}" font-size="10" fill="red">+</text>''')
        svg.append(f'''<text x="{x+self.breadboard_width-15}" y="{y+40}" font-size="10" fill="blue">-</text>''')

        return '\n'.join(svg)

    def _draw_microcontroller(self, mcu_type: str, pos: Tuple[int, int]) -> str:
        """Draw microcontroller board"""
        x, y = pos
        svg = []

        if 'arduino' in mcu_type.lower():
            # Arduino board
            width, height = 55, 70
            svg.append(f'''<rect x="{x}" y="{y}" width="{width}" height="{height}"
                fill="{self.colors['arduino']}" stroke="#000" stroke-width="2" rx="3"/>''')
            svg.append(f'''<text x="{x+width//2}" y="{y+height//2}" text-anchor="middle"
                font-size="10" fill="white" font-weight="bold">ARDUINO</text>''')

            # USB connector
            svg.append(f'''<rect x="{x+width-10}" y="{y+height//3}" width="10" height="15"
                fill="#C0C0C0" stroke="#000"/>''')

            # Power jack
            svg.append(f'''<circle cx="{x+10}" cy="{y+10}" r="5" fill="#000"/>''')

        elif 'esp32' in mcu_type.lower():
            # ESP32 board
            width, height = 50, 30
            svg.append(f'''<rect x="{x}" y="{y}" width="{width}" height="{height}"
                fill="#000080" stroke="#000" stroke-width="2" rx="3"/>''')
            svg.append(f'''<text x="{x+width//2}" y="{y+height//2}" text-anchor="middle"
                font-size="10" fill="white" font-weight="bold">ESP32</text>''')

            # Antenna
            svg.append(f'''<rect x="{x}" y="{y+height-8}" width="15" height="8"
                fill="#FFD700" stroke="#000"/>''')

        # Pin headers (simplified)
        pin_spacing = 5
        for i in range(10):
            svg.append(f'''<circle cx="{x+10+i*5}" cy="{y}" r="1" fill="#FFD700"/>''')
            svg.append(f'''<circle cx="{x+10+i*5}" cy="{y+70}" r="1" fill="#FFD700"/>''')

        # Label
        svg.append(f'''<text x="{x}" y="{y-5}" font-size="12" font-weight="bold">
            {mcu_type.upper().replace('_', ' ')}</text>''')

        return '\n'.join(svg)

    def _draw_component(self, component: Dict, pos: Tuple[int, int]) -> str:
        """Draw a component on the breadboard"""
        x, y = pos
        svg = []

        comp_type = component.get('type', 'sensor_small')
        comp_name = component.get('name', 'Component')

        # Get component size
        if 'dht' in comp_name.lower():
            width, height = 15, 20
            color = '#4169E1'
        elif 'bme' in comp_name.lower() or 'bmp' in comp_name.lower():
            width, height = 20, 20
            color = '#8B4513'
        elif 'oled' in comp_name.lower():
            width, height = 30, 30
            color = '#000'
        elif 'lcd' in comp_name.lower():
            width, height = 80, 36
            color = '#90EE90'
        elif 'led' in comp_name.lower():
            width, height = 5, 10
            color = '#FF0000'
        elif 'relay' in comp_name.lower():
            width, height = 20, 20
            color = '#4682B4'
        elif 'servo' in comp_name.lower():
            width, height = 23, 12
            color = '#FFA500'
        else:
            width, height = 15, 15
            color = self.colors['component']

        # Draw component body
        svg.append(f'''<rect x="{x}" y="{y}" width="{width}" height="{height}"
            fill="{color}" stroke="#000" stroke-width="1.5" rx="2"/>''')

        # Component pins
        num_pins = component.get('pins', 4)
        for i in range(min(num_pins, 8)):
            pin_x = x + (width / (num_pins + 1)) * (i + 1)
            svg.append(f'''<line x1="{pin_x}" y1="{y+height}" x2="{pin_x}" y2="{y+height+8}"
                stroke="#FFD700" stroke-width="2"/>''')
            svg.append(f'''<circle cx="{pin_x}" cy="{y+height+10}" r="2" fill="#FFD700"/>''')

        # Label
        svg.append(f'''<text x="{x+width//2}" y="{y-5}" text-anchor="middle"
            font-size="10" font-weight="bold">{comp_name[:15]}</text>''')

        return '\n'.join(svg)

    def _generate_connections(self, design: Dict, mcu_pos: Tuple[int, int],
                             component_positions: Dict) -> List[str]:
        """Generate wiring connections between components and microcontroller"""
        connections = []
        mcu_x, mcu_y = mcu_pos

        # Standard connections for common sensors
        for comp_id, (comp_x, comp_y) in component_positions.items():
            # Power connections (red wire to VCC, black to GND)
            connections.append(self._draw_wire(
                (comp_x + 10, comp_y + 25),
                (mcu_x + 40, mcu_y),
                self.colors['wire_5v'],
                "5V"
            ))
            connections.append(self._draw_wire(
                (comp_x + 20, comp_y + 25),
                (mcu_x + 50, mcu_y),
                self.colors['wire_gnd'],
                "GND"
            ))

            # Signal wire (green)
            connections.append(self._draw_wire(
                (comp_x + 30, comp_y + 25),
                (mcu_x + 20, mcu_y + 20),
                self.colors['wire_signal'],
                "DATA"
            ))

        return connections

    def _draw_wire(self, start: Tuple[int, int], end: Tuple[int, int],
                   color: str, label: str = "") -> str:
        """Draw a wire connection with optional label"""
        x1, y1 = start
        x2, y2 = end

        # Calculate control points for curved wire
        mid_x = (x1 + x2) / 2
        mid_y = min(y1, y2) - 30

        svg = []

        # Curved wire path
        svg.append(f'''<path d="M {x1},{y1} Q {mid_x},{mid_y} {x2},{y2}"
            stroke="{color}" stroke-width="2" fill="none"/>''')

        # Wire label (optional)
        if label:
            svg.append(f'''<text x="{mid_x}" y="{mid_y-5}" font-size="8"
                text-anchor="middle" fill="{color}">{label}</text>''')

        return '\n'.join(svg)

    def _draw_legend(self, x: int, y: int) -> str:
        """Draw wire color legend"""
        svg = []

        svg.append(f'''<text x="{x}" y="{y}" font-size="14" font-weight="bold">
            Wire Color Code:</text>''')

        legends = [
            (self.colors['wire_5v'], "Red: Power (5V/3.3V)"),
            (self.colors['wire_gnd'], "Black: Ground (GND)"),
            (self.colors['wire_signal'], "Green: Signal/Data"),
            (self.colors['wire_i2c_sda'], "Yellow: I2C SDA"),
            (self.colors['wire_i2c_scl'], "Orange: I2C SCL")
        ]

        for i, (color, text) in enumerate(legends):
            legend_y = y + 20 + (i * 20)
            svg.append(f'''<line x1="{x}" y1="{legend_y}" x2="{x+30}" y2="{legend_y}"
                stroke="{color}" stroke-width="4"/>''')
            svg.append(f'''<text x="{x+40}" y="{legend_y+5}" font-size="12">{text}</text>''')

        return '\n'.join(svg)


def main():
    """Demo of wiring diagram generator"""
    generator = WiringDiagramGenerator()

    # Example design
    design = {
        'project_name': 'DHT22 Temperature Sensor',
        'microcontroller': 'arduino_uno',
        'components': [
            {'id': 'dht22_1', 'name': 'DHT22', 'type': 'sensor', 'pins': 3},
            {'id': 'led_1', 'name': 'LED', 'type': 'led', 'pins': 2}
        ]
    }

    output = generator.generate_diagram(design, 'output/test_diagram.svg')
    print(f"✓ Generated diagram: {output}")


if __name__ == '__main__':
    main()
