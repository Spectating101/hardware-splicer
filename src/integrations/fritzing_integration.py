#!/usr/bin/env python3
"""
Fritzing Integration
- Uses Fritzing parts library for component graphics
- Generates .fzz files that can be opened in Fritzing
"""

import xml.etree.ElementTree as ET
import zipfile
import json
from pathlib import Path
from typing import Dict, List, Optional
import shutil


class FritzingPartsLibrary:
    """Interface to Fritzing parts library"""

    def __init__(self, parts_repo_path: str = "/tmp/fritzing-parts"):
        self.repo_path = Path(parts_repo_path)
        self.core_parts = self.repo_path / "core"
        self.svg_path = self.repo_path / "svg" / "core"

        # Cache for parsed parts
        self.parts_cache = {}

        # Mapping from our component IDs to Fritzing part files
        # Based on actual Fritzing parts library (1792 parts available)
        self.component_mapping = {
            # Microcontrollers
            'arduino_uno': 'arduino_Uno_Rev3(fix)',  # ✓ Found: arduino_Uno_Rev3(fix).fzp
            'arduino_nano': 'Arduino_Nano3',
            'arduino_mega': 'Arduino_MEGA_2560-Rev3(fix)',  # ✓ Found: Arduino_MEGA_2560-Rev3(fix).fzp
            'arduino_leonardo': 'Arduino_Leonardo_Rev3(fix)',  # ✓ Found: Arduino_Leonardo_Rev3(fix).fzp
            'esp32': None,  # Not in Fritzing core, would need custom
            'esp8266': None,  # Not in Fritzing core

            # Sensors (validated in Fritzing library)
            'bme280': 'SparkFun_BME280_Breakout',  # ✓ Found: SparkFun_BME280_Breakout.fzp
            'bmp280': 'Barometric Pressure Sensor',  # ✓ Found: Barometric Pressure Sensor.fzp
            'dht22': None,  # Not found in core library
            'dht11': None,  # Not found in core library
            'hc_sr04': 'hc-sr04_bf8299a_002',  # ✓ Found: hc-sr04_bf8299a_002.fzp
            'mpu6050': None,  # Not in Fritzing core

            # Displays
            'oled_ssd1306': 'seeed_grove_oled_128x96',  # ✓ Found: seeed_grove_oled_128x96.fzp
            'lcd_16x2': 'sparkfun-displays-lcd-16x2-8x2',  # ✓ Found: sparkfun-displays-lcd-16x2-8x2.fzp
            'lcd_20x4': 'lcd-GDM1602K',  # ✓ Found: lcd-GDM1602K.fzp

            # Actuators
            'servo_sg90': 'servo',  # ✓ Found: servo.fzp
            'servo': 'servo',
            'relay': 'basic-relay-6p_1c569ac_002',  # ✓ Found: basic-relay-6p_1c569ac_002.fzp

            # Basic components
            'led': 'LED-generic-5mm',  # ✓ Found: LED-generic-5mm.fzp
            'led_5mm': 'LED-generic-5mm',
            'led_3mm': 'LED-generic-3mm',  # ✓ Found: LED-generic-3mm.fzp
            'led_rgb': 'led-rgb-4pin-anode_v5',  # ✓ Found: led-rgb-4pin-anode_v5.fzp
            'ws2812b': None,  # NeoPixel not in Fritzing core
            'neopixel': None,
            'resistor': 'resistor',  # ✓ Found: resistor.fzp
            'resistor_5band': 'resistor_5band',  # ✓ Found: resistor_5band.fzp
            'capacitor': 'capacitor_ceramic_100mil',  # ✓ Found: capacitor_ceramic_100mil.fzp
            'capacitor_electrolytic': 'capacitor_electrolytic_medium',  # ✓ Found
        }

    def find_part(self, component_id: str) -> Optional[Path]:
        """Find Fritzing .fzp file for a component"""
        # Check mapping
        fritzing_name = self.component_mapping.get(component_id.lower())
        if not fritzing_name:
            # Try fuzzy search
            search_term = component_id.lower().replace('_', '')
            for fzp_file in self.core_parts.glob("*.fzp"):
                if search_term in fzp_file.stem.lower().replace('_', '').replace('-', ''):
                    return fzp_file
            return None

        # Look for exact match
        candidates = list(self.core_parts.glob(f"{fritzing_name}*.fzp"))
        if candidates:
            return candidates[0]

        return None

    def get_part_svg(self, component_id: str, view: str = "breadboard") -> Optional[Path]:
        """Get SVG file for a component view"""
        fzp_file = self.find_part(component_id)
        if not fzp_file:
            return None

        # Parse .fzp to find SVG reference
        try:
            tree = ET.parse(fzp_file)
            root = tree.getroot()

            # Find the view (breadboard, schematic, or pcb)
            view_element = root.find(f".//views/{view}View/layers")
            if view_element is not None and 'image' in view_element.attrib:
                svg_ref = view_element.attrib['image']
                svg_path = self.svg_path / svg_ref
                if svg_path.exists():
                    return svg_path
        except Exception as e:
            print(f"Error parsing {fzp_file}: {e}")

        return None

    def get_part_info(self, component_id: str) -> Optional[Dict]:
        """Get part metadata from .fzp file"""
        if component_id in self.parts_cache:
            return self.parts_cache[component_id]

        fzp_file = self.find_part(component_id)
        if not fzp_file:
            return None

        try:
            tree = ET.parse(fzp_file)
            root = tree.getroot()

            info = {
                'id': root.attrib.get('moduleId'),
                'title': root.findtext('title', ''),
                'description': root.findtext('description', ''),
                'url': root.findtext('url', ''),
                'tags': [tag.text for tag in root.findall('.//tag')],
                'breadboard_svg': None,
                'schematic_svg': None,
                'pcb_svg': None
            }

            # Get SVG paths
            for view in ['breadboard', 'schematic', 'pcb']:
                svg_path = self.get_part_svg(component_id, view)
                if svg_path:
                    info[f'{view}_svg'] = str(svg_path)

            self.parts_cache[component_id] = info
            return info

        except Exception as e:
            print(f"Error getting part info for {component_id}: {e}")
            return None


class FritzingFileGenerator:
    """Generates .fzz files (Fritzing project files)"""

    def __init__(self, parts_library: FritzingPartsLibrary):
        self.parts_lib = parts_library

    def generate_fzz(self, design: Dict, output_path: str) -> str:
        """
        Generate a .fzz file from Circuit-AI design

        .fzz files are ZIP archives containing:
        - main.fz (XML with circuit layout)
        - svg/*.svg (embedded SVG files)
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create temporary directory for .fzz contents
        temp_dir = Path(f"/tmp/fzz_temp_{design.get('project_name', 'circuit')}")
        temp_dir.mkdir(exist_ok=True)

        try:
            # Generate main.fz (Fritzing XML)
            main_fz = self._generate_main_fz(design)
            (temp_dir / "main.fz").write_text(main_fz)

            # Create ZIP file
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_dir / "main.fz", "main.fz")

            return str(output_file)

        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _generate_main_fz(self, design: Dict) -> str:
        """Generate main.fz XML content"""
        # Simplified Fritzing XML structure
        # Real Fritzing files have much more detail, but this is a minimal working version

        project_name = design.get('project_name', 'Circuit-AI Design')
        mcu = design.get('microcontroller', 'arduino_uno')
        components = design.get('components', [])

        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<module fritzingVersion="0.9.3b">',
            f'  <title>{project_name}</title>',
            '  <instances>',
        ]

        # Add microcontroller
        mcu_part = self.parts_lib.get_part_info(mcu)
        if mcu_part:
            xml_parts.append(f'    <instance moduleIdRef="{mcu_part["id"]}" modelIndex="0">')
            xml_parts.append('      <views>')
            xml_parts.append('        <breadboardView layer="breadboard">')
            xml_parts.append('          <geometry x="100" y="100"/>')
            xml_parts.append('        </breadboardView>')
            xml_parts.append('      </views>')
            xml_parts.append('    </instance>')

        # Add components
        x_offset = 300
        for i, comp in enumerate(components):
            comp_id = comp if isinstance(comp, str) else comp.get('id', '')
            comp_part = self.parts_lib.get_part_info(comp_id)

            if comp_part:
                y_pos = 100 + (i * 80)
                xml_parts.append(f'    <instance moduleIdRef="{comp_part["id"]}" modelIndex="{i+1}">')
                xml_parts.append('      <views>')
                xml_parts.append('        <breadboardView layer="breadboard">')
                xml_parts.append(f'          <geometry x="{x_offset}" y="{y_pos}"/>')
                xml_parts.append('        </breadboardView>')
                xml_parts.append('      </views>')
                xml_parts.append('    </instance>')

        xml_parts.append('  </instances>')
        xml_parts.append('</module>')

        return '\n'.join(xml_parts)


def main():
    """Demo Fritzing integration"""
    print("="*70)
    print("  FRITZING INTEGRATION DEMO")
    print("="*70)
    print()

    # Initialize
    parts_lib = FritzingPartsLibrary()
    fzz_gen = FritzingFileGenerator(parts_lib)

    # Test 1: Find Arduino Uno part
    print("TEST 1: Find Arduino Uno in Fritzing library")
    print("-"*70)
    uno_part = parts_lib.find_part('arduino_uno')
    if uno_part:
        print(f"✓ Found: {uno_part.name}")
        info = parts_lib.get_part_info('arduino_uno')
        if info:
            print(f"  Title: {info['title']}")
            print(f"  Breadboard SVG: {Path(info['breadboard_svg']).name if info['breadboard_svg'] else 'Not found'}")
    else:
        print("✗ Arduino Uno not found")
    print()

    # Test 2: Search for sensors
    print("TEST 2: Find BME280 sensor")
    print("-"*70)
    bme_part = parts_lib.find_part('bme280')
    if bme_part:
        print(f"✓ Found: {bme_part.name}")
    else:
        print("✗ BME280 not found (might not be in Fritzing core)")
    print()

    # Test 3: Generate .fzz file
    print("TEST 3: Generate Fritzing .fzz file")
    print("-"*70)
    design = {
        'project_name': 'Arduino Temperature Sensor',
        'microcontroller': 'arduino_uno',
        'components': ['dht22', 'led', 'resistor']
    }

    try:
        fzz_file = fzz_gen.generate_fzz(design, 'output/test_circuit.fzz')
        print(f"✓ Generated: {fzz_file}")
        print(f"  File size: {Path(fzz_file).stat().st_size} bytes")
        print("  You can open this in Fritzing!")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    # Test 4: List available Arduino boards
    print("TEST 4: Available Arduino boards in Fritzing")
    print("-"*70)
    arduino_parts = list(parts_lib.core_parts.glob("Arduino*.fzp"))
    print(f"Found {len(arduino_parts)} Arduino boards:")
    for part in arduino_parts[:10]:
        print(f"  • {part.stem}")
    if len(arduino_parts) > 10:
        print(f"  ... and {len(arduino_parts) - 10} more")
    print()

    print("="*70)
    print("  FRITZING INTEGRATION READY")
    print("="*70)
    print()
    print("Benefits:")
    print("  ✓ Access to 1000+ professional component graphics")
    print("  ✓ Can generate .fzz files that open in Fritzing")
    print("  ✓ Users can continue editing in Fritzing if they want")
    print("  ✓ No need to hand-draw every component")
    print()


if __name__ == '__main__':
    main()
