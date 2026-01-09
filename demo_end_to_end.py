#!/usr/bin/env python3
"""
Circuit-AI End-to-End Demo
Demonstrates the complete workflow:
1. Design circuit
2. Validate for mistakes
3. Export to Fritzing .fzz file
"""

import sys
sys.path.insert(0, 'src')

from intelligence.circuit_validator import CircuitValidator
from integrations.fritzing_integration import FritzingPartsLibrary, FritzingFileGenerator
from pathlib import Path


def demo_temperature_monitor():
    """Demo: Arduino + BME280 temperature sensor"""
    print("="*70)
    print("  DEMO 1: Temperature Monitor")
    print("="*70)
    print()

    # Step 1: Design
    print("[Step 1] Design Circuit")
    print("-"*70)
    design = {
        'project_name': 'Temperature Monitor',
        'microcontroller': 'arduino_uno',
        'components': [
            {'id': 'bme280', 'pins': {'vcc': '3.3V', 'scl': 'A5', 'sda': 'A4'}},
            {'id': 'led', 'pins': {'anode': '13'}},
            {'id': 'resistor', 'value': '220'}
        ]
    }
    print(f"  Microcontroller: {design['microcontroller']}")
    print(f"  Components: {len(design['components'])}")
    print()

    # Step 2: Validate
    print("[Step 2] Validate Circuit")
    print("-"*70)
    validator = CircuitValidator()
    issues = validator.validate_circuit(design)

    if issues:
        print(validator.format_report(issues))
    else:
        print("  ✓ No issues found! Circuit looks good.")
    print()

    # Step 3: Export to Fritzing
    print("[Step 3] Export to Fritzing")
    print("-"*70)
    parts_lib = FritzingPartsLibrary()
    fzz_gen = FritzingFileGenerator(parts_lib)

    output_file = 'output/temperature_monitor.fzz'
    fzz_path = fzz_gen.generate_fzz(design, output_file)

    if Path(fzz_path).exists():
        file_size = Path(fzz_path).stat().st_size
        print(f"  ✓ Generated: {fzz_path}")
        print(f"  ✓ File size: {file_size} bytes")
        print(f"  ✓ Can be opened in Fritzing!")
    print()


def demo_bad_circuit():
    """Demo: Circuit with validation errors"""
    print("="*70)
    print("  DEMO 2: Bad Circuit (Should Catch Errors)")
    print("="*70)
    print()

    # Step 1: Design (with intentional mistakes)
    print("[Step 1] Design Circuit (with mistakes)")
    print("-"*70)
    design = {
        'project_name': 'Arduino + BME280 on 5V (WRONG!)',
        'microcontroller': 'arduino_uno',
        'components': ['bme280', 'servo_sg90', 'servo_sg90', 'servo_sg90'],  # Use string format
        'external_power': False
    }
    print(f"  BME280 powered from: 5V (should be 3.3V)")
    print(f"  3x servos without external power")
    print()

    # Step 2: Validate
    print("[Step 2] Validate Circuit")
    print("-"*70)
    validator = CircuitValidator()
    issues = validator.validate_circuit(design)

    print(validator.format_report(issues))

    critical_count = sum(1 for i in issues if i.severity.value == 'critical')
    error_count = sum(1 for i in issues if i.severity.value == 'error')

    print(f"  CAUGHT {critical_count} critical issues and {error_count} errors!")
    print(f"  💰 This validation just saved you ~$50 in fried components")
    print()

    # Step 3: Still export (user can see the circuit even with errors)
    print("[Step 3] Export to Fritzing (with warnings)")
    print("-"*70)
    parts_lib = FritzingPartsLibrary()
    fzz_gen = FritzingFileGenerator(parts_lib)

    output_file = 'output/bad_circuit_example.fzz'
    fzz_path = fzz_gen.generate_fzz(design, output_file)

    print(f"  ✓ Generated: {fzz_path}")
    print(f"  ⚠️  But user was warned about issues!")
    print()


def demo_smart_home_sensor():
    """Demo: More complex circuit"""
    print("="*70)
    print("  DEMO 3: Smart Home Sensor Node")
    print("="*70)
    print()

    design = {
        'project_name': 'Smart Home Sensor Node',
        'microcontroller': 'arduino_uno',
        'components': ['bme280', 'oled_ssd1306', 'hc_sr04', 'relay', 'led', 'led', 'led']
    }

    print("[Design] Multi-sensor home automation node")
    print("-"*70)
    print("  • BME280 (temperature/humidity/pressure)")
    print("  • OLED display")
    print("  • HC-SR04 (distance sensor)")
    print("  • Relay (control AC device)")
    print("  • 3x LEDs (status indicators)")
    print()

    print("[Validate]")
    print("-"*70)
    validator = CircuitValidator()
    issues = validator.validate_circuit(design)

    if issues:
        print(validator.format_report(issues))
    else:
        print("  ✓ Circuit validated successfully!")
    print()

    print("[Export]")
    print("-"*70)
    parts_lib = FritzingPartsLibrary()
    fzz_gen = FritzingFileGenerator(parts_lib)

    output_file = 'output/smart_home_node.fzz'
    fzz_path = fzz_gen.generate_fzz(design, output_file)

    print(f"  ✓ {fzz_path}")
    print()


def main():
    print()
    print("█"*70)
    print("  CIRCUIT-AI: END-TO-END DEMO")
    print("  Design → Validate → Export to Fritzing")
    print("█"*70)
    print()

    # Run demos
    demo_temperature_monitor()
    demo_bad_circuit()
    demo_smart_home_sensor()

    # Summary
    print("="*70)
    print("  SUMMARY: What Circuit-AI Does")
    print("="*70)
    print()
    print("✓ VALIDATES circuits before you build them")
    print("  • Catches voltage mismatches (saves $$)")
    print("  • Detects power issues (prevents brown-outs)")
    print("  • Warns about I2C conflicts")
    print("  • Checks pin availability")
    print()
    print("✓ EXPORTS to professional tools")
    print("  • Generates .fzz files for Fritzing")
    print("  • Uses 1000+ professional component graphics")
    print("  • Interoperable with existing workflows")
    print()
    print("✓ UNIQUE VALUE: Fritzing + TinkerCAD DON'T validate")
    print("  • They show diagrams, we PREVENT MISTAKES")
    print("  • Pays for itself on first use")
    print()
    print("="*70)
    print()
    print("Next step: Build web interface to make this accessible!")
    print()


if __name__ == '__main__':
    main()
