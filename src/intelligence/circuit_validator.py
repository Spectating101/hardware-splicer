#!/usr/bin/env python3
"""
Circuit Validation Engine
Prevents expensive mistakes by validating component compatibility
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    CRITICAL = "critical"  # Will damage components
    ERROR = "error"        # Won't work
    WARNING = "warning"    # Might work but not recommended
    INFO = "info"          # Optimization suggestion


@dataclass
class ValidationIssue:
    """A validation issue found in the circuit"""
    severity: ValidationSeverity
    component: str
    issue: str
    explanation: str
    solution: str
    source: str  # Where this rule came from


class CircuitValidator:
    """Validates circuits for common mistakes and incompatibilities"""

    def __init__(self):
        # Voltage compatibility rules (from Arduino forums/datasheets)
        self.voltage_rules = {
            '3.3V_components': [
                'esp8266', 'esp32', 'esp32_c6',
                'bme280', 'bmp280', 'bmp180',
                'mpu6050', 'hmc5883l', 'vl53l0x',
                'tcs34725', 'ccs811', 'max30102'
            ],
            '5V_tolerant': [
                'dht11', 'dht22', 'ds18b20',
                'hc_sr04', 'pir', 'relay'
            ],
            '5V_only': [
                'arduino_uno', 'arduino_nano', 'arduino_mega'
            ]
        }

        # I2C address conflicts (scraped from datasheets)
        self.i2c_addresses = {
            'bme280': ['0x76', '0x77'],
            'bmp280': ['0x76', '0x77'],
            'bmp180': ['0x77'],
            'mpu6050': ['0x68', '0x69'],
            'bh1750': ['0x23', '0x5C'],
            'tcs34725': ['0x29'],
            'ccs811': ['0x5A', '0x5B'],
            'hmc5883l': ['0x1E'],
            'vl53l0x': ['0x29'],
            'max30102': ['0x57'],
            'at24c256': ['0x50', '0x51', '0x52', '0x53', '0x54', '0x55', '0x56', '0x57']
        }

        # Power consumption (from datasheets)
        self.power_consumption = {
            'esp32': {'voltage': 3.3, 'current_typical': 160, 'current_peak': 240},
            'esp8266': {'voltage': 3.3, 'current_typical': 80, 'current_peak': 170},
            'arduino_uno': {'voltage': 5, 'current_typical': 50, 'current_peak': 50},
            'arduino_nano': {'voltage': 5, 'current_typical': 19, 'current_peak': 19},
            'arduino_mega': {'voltage': 5, 'current_typical': 50, 'current_peak': 50},
            'servo_sg90': {'voltage': 5, 'current_typical': 100, 'current_peak': 650},
            'relay_1ch': {'voltage': 5, 'current_typical': 70, 'current_peak': 70},
            'relay_4ch': {'voltage': 5, 'current_typical': 280, 'current_peak': 280},
            'ws2812b': {'voltage': 5, 'current_per_led': 60, 'current_peak': 60},
            'oled_ssd1306': {'voltage': 3.3, 'current_typical': 20, 'current_peak': 20}
        }

        # Common mistakes from Arduino forums/Stack Exchange
        self.common_mistakes = [
            {
                'pattern': lambda d: 'bme280' in d['components'] and d['mcu_voltage'] == 5,
                'severity': ValidationSeverity.CRITICAL,
                'issue': 'BME280 on 5V microcontroller without level shifter',
                'explanation': 'BME280 is a 3.3V device. Connecting directly to 5V Arduino will damage it.',
                'solution': 'Use a logic level converter (bi-directional) between Arduino and BME280, or use a 3.3V Arduino/ESP32.',
                'source': 'Adafruit BME280 Guide, Arduino Forum'
            },
            {
                'pattern': lambda d: 'mpu6050' in d['components'] and d['mcu_voltage'] == 5,
                'severity': ValidationSeverity.CRITICAL,
                'issue': 'MPU6050 on 5V microcontroller without level shifter',
                'explanation': 'MPU6050 operates at 3.3V. 5V logic levels will damage the I2C pins.',
                'solution': 'Use a logic level converter or switch to 3.3V microcontroller (ESP32).',
                'source': 'SparkFun MPU6050 Hookup Guide'
            },
            {
                'pattern': lambda d: len([c for c in d['components'] if 'servo' in c]) > 0 and d.get('external_power') == False,
                'severity': ValidationSeverity.ERROR,
                'issue': 'Servos powered from Arduino 5V pin',
                'explanation': 'Servos draw 500-650mA peak current. Arduino 5V pin can only provide 500mA total. This will brown-out the Arduino.',
                'solution': 'Use external 5V power supply for servos. Connect grounds together but power servos separately.',
                'source': 'Arduino Forum - Servo Power Issues'
            },
            {
                'pattern': lambda d: 'ws2812b' in d['components'] and d.get('led_count', 0) > 10 and d.get('external_power') == False,
                'severity': ValidationSeverity.ERROR,
                'issue': 'WS2812B LED strip powered from Arduino',
                'explanation': "Each LED draws 60mA. With many LEDs, total current exceeds Arduino's capability.",
                'solution': 'Use external 5V power supply rated for LED count × 60mA. Connect grounds together.',
                'source': 'Adafruit NeoPixel Guide'
            }
        ]

    def validate_circuit(self, design: Dict) -> List[ValidationIssue]:
        """
        Validate a circuit design for common issues

        Args:
            design: Circuit design dict with:
                - microcontroller: str
                - components: List[str] (component IDs)
                - connections: Dict (optional)
                - features: List[str] (optional)

        Returns:
            List of ValidationIssue objects
        """
        issues = []

        # Prepare design data
        design_data = self._prepare_design_data(design)

        # Run all validation checks
        issues.extend(self._check_voltage_compatibility(design_data))
        issues.extend(self._check_i2c_conflicts(design_data))
        issues.extend(self._check_power_budget(design_data))
        issues.extend(self._check_common_mistakes(design_data))
        issues.extend(self._check_pin_availability(design_data))

        return sorted(issues, key=lambda x: ['critical', 'error', 'warning', 'info'].index(x.severity.value))

    def _prepare_design_data(self, design: Dict) -> Dict:
        """Prepare and enrich design data for validation"""
        mcu = design.get('microcontroller', '').lower()
        components = [c.lower() if isinstance(c, str) else c.get('id', '').lower()
                     for c in design.get('components', [])]

        # Determine MCU voltage
        mcu_voltage = 3.3 if any(v in mcu for v in ['esp32', 'esp8266']) else 5.0

        return {
            'microcontroller': mcu,
            'mcu_voltage': mcu_voltage,
            'components': components,
            'features': design.get('features', []),
            'external_power': design.get('external_power', False),
            'led_count': design.get('led_count', 30)  # Default for WS2812B
        }

    def _check_voltage_compatibility(self, design: Dict) -> List[ValidationIssue]:
        """Check for voltage level mismatches"""
        issues = []
        mcu_voltage = design['mcu_voltage']
        components = design['components']

        for comp in components:
            # Check if 3.3V component on 5V system
            if mcu_voltage == 5.0:
                for comp_3v in self.voltage_rules['3.3V_components']:
                    if comp_3v in comp:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.CRITICAL,
                            component=comp,
                            issue=f'{comp.upper()} requires 3.3V but connected to 5V microcontroller',
                            explanation=f'{comp.upper()} operates at 3.3V. Direct connection to 5V logic will damage the component permanently.',
                            solution='Use a bi-directional logic level converter (e.g., TXS0108E) or switch to 3.3V microcontroller (ESP32/ESP8266).',
                            source='Component datasheet, verified by Arduino community'
                        ))

        return issues

    def _check_i2c_conflicts(self, design: Dict) -> List[ValidationIssue]:
        """Check for I2C address conflicts"""
        issues = []
        components = design['components']

        # Find I2C components
        i2c_components = [c for c in components if any(i2c_comp in c for i2c_comp in self.i2c_addresses.keys())]

        if len(i2c_components) > 1:
            # Check for address conflicts
            address_usage = {}
            for comp in i2c_components:
                for known_comp, addresses in self.i2c_addresses.items():
                    if known_comp in comp:
                        default_addr = addresses[0]  # First address is usually default
                        if default_addr not in address_usage:
                            address_usage[default_addr] = []
                        address_usage[default_addr].append((comp, known_comp, addresses))

            # Find conflicts
            for addr, comps in address_usage.items():
                if len(comps) > 1:
                    comp_names = ', '.join([c[0].upper() for c in comps])
                    alt_addresses = []
                    for c in comps:
                        if len(c[2]) > 1:
                            alt_addresses.append(f"{c[0].upper()} can use {', '.join(c[2][1:])}")

                    solution = "Change I2C address on one component. "
                    if alt_addresses:
                        solution += "Alternative addresses: " + "; ".join(alt_addresses)
                    else:
                        solution += "One component may need to be removed or use a I2C multiplexer (TCA9548A)."

                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        component=comp_names,
                        issue=f'I2C address conflict at {addr}',
                        explanation=f'Multiple components ({comp_names}) are using the same I2C address {addr}. Only one will work.',
                        solution=solution,
                        source='Component datasheets, I2C specification'
                    ))

        return issues

    def _check_power_budget(self, design: Dict) -> List[ValidationIssue]:
        """Check if power consumption exceeds available power"""
        issues = []
        mcu = design['microcontroller']
        components = design['components']

        # Calculate total current draw
        total_current = 0
        component_currents = []

        # MCU current
        if mcu in self.power_consumption:
            mcu_current = self.power_consumption[mcu]['current_typical']
            total_current += mcu_current
            component_currents.append((mcu.upper(), mcu_current))

        # Component currents
        for comp in components:
            for known_comp, specs in self.power_consumption.items():
                if known_comp in comp:
                    current = specs['current_typical']
                    if known_comp == 'ws2812b':
                        led_count = design.get('led_count', 30)
                        current = specs['current_per_led'] * led_count
                        component_currents.append((f"{comp.upper()} ({led_count} LEDs)", current))
                    else:
                        component_currents.append((comp.upper(), current))
                    total_current += current
                    break

        # Check against power budget
        # USB power limit: 500mA (USB 2.0), 900mA (USB 3.0)
        # Arduino Uno 5V pin: 500mA when powered via USB
        if total_current > 400:  # Conservative limit
            current_breakdown = "\n".join([f"  • {name}: {curr}mA" for name, curr in component_currents])

            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                component="Power Supply",
                issue=f'Total current draw ({total_current}mA) exceeds safe USB power limit (400mA)',
                explanation=f'Circuit draws too much current:\n{current_breakdown}\nTotal: {total_current}mA',
                solution='Use external power supply (wall adapter or battery) rated for at least {:.1f}A at {}V. Connect grounds together.'.format(
                    total_current / 1000 * 1.3,  # 30% safety margin
                    design['mcu_voltage']
                ),
                source='USB specification, Arduino power guidelines'
            ))

        return issues

    def _check_common_mistakes(self, design: Dict) -> List[ValidationIssue]:
        """Check against database of common mistakes"""
        issues = []

        for mistake in self.common_mistakes:
            if mistake['pattern'](design):
                issues.append(ValidationIssue(
                    severity=mistake['severity'],
                    component='Circuit Design',
                    issue=mistake['issue'],
                    explanation=mistake['explanation'],
                    solution=mistake['solution'],
                    source=mistake['source']
                ))

        return issues

    def _check_pin_availability(self, design: Dict) -> List[ValidationIssue]:
        """Check if microcontroller has enough pins"""
        issues = []
        mcu = design['microcontroller']
        components = design['components']

        # Pin counts for common MCUs
        pin_counts = {
            'arduino_uno': {'digital': 14, 'analog': 6, 'pwm': 6, 'i2c': 1},
            'arduino_nano': {'digital': 14, 'analog': 8, 'pwm': 6, 'i2c': 1},
            'arduino_mega': {'digital': 54, 'analog': 16, 'pwm': 15, 'i2c': 1},
            'esp32': {'digital': 34, 'analog': 18, 'pwm': 16, 'i2c': 2},
            'esp8266': {'digital': 11, 'analog': 1, 'pwm': 4, 'i2c': 1}
        }

        if mcu in pin_counts:
            # Estimate pins needed (rough calculation)
            pins_needed = len(components) * 2  # Rough estimate
            available_pins = pin_counts[mcu]['digital']

            if pins_needed > available_pins * 0.8:  # 80% threshold
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    component=mcu.upper(),
                    issue='Possible insufficient pins',
                    explanation=f'Estimated {pins_needed} pins needed, {available_pins} available. This is tight.',
                    solution='Consider using I2C/SPI devices to share pins, or upgrade to Arduino Mega (54 pins).',
                    source='Pin count estimation'
                ))

        return issues

    def format_report(self, issues: List[ValidationIssue]) -> str:
        """Format validation issues as readable report"""
        if not issues:
            return "✅ No validation issues found! Circuit looks good."

        report = []
        report.append("="*70)
        report.append("  CIRCUIT VALIDATION REPORT")
        report.append("="*70)
        report.append("")

        # Count by severity
        critical = sum(1 for i in issues if i.severity == ValidationSeverity.CRITICAL)
        errors = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)

        report.append(f"Found {len(issues)} issue(s):")
        if critical:
            report.append(f"  🔴 {critical} CRITICAL (will damage components)")
        if errors:
            report.append(f"  🟠 {errors} ERROR (won't work)")
        if warnings:
            report.append(f"  🟡 {warnings} WARNING (not recommended)")
        report.append("")

        # List issues
        for i, issue in enumerate(issues, 1):
            severity_icon = {
                ValidationSeverity.CRITICAL: "🔴 CRITICAL",
                ValidationSeverity.ERROR: "🟠 ERROR",
                ValidationSeverity.WARNING: "🟡 WARNING",
                ValidationSeverity.INFO: "ℹ️ INFO"
            }

            report.append(f"{i}. {severity_icon[issue.severity]}: {issue.issue}")
            report.append(f"   Component: {issue.component}")
            report.append(f"   Problem: {issue.explanation}")
            report.append(f"   Solution: {issue.solution}")
            report.append(f"   Source: {issue.source}")
            report.append("")

        report.append("="*70)

        return "\n".join(report)


def main():
    """Demo validation engine"""
    validator = CircuitValidator()

    # Test case 1: BME280 on Arduino (voltage mismatch)
    print("TEST 1: BME280 on Arduino Uno (should catch voltage issue)")
    print("-"*70)
    design1 = {
        'microcontroller': 'arduino_uno',
        'components': ['bme280', 'dht22']
    }
    issues1 = validator.validate_circuit(design1)
    print(validator.format_report(issues1))
    print()

    # Test case 2: Multiple BME280s (I2C conflict)
    print("TEST 2: Two BME280 sensors (should catch I2C conflict)")
    print("-"*70)
    design2 = {
        'microcontroller': 'esp32',
        'components': ['bme280', 'bmp280']  # Both default to 0x76
    }
    issues2 = validator.validate_circuit(design2)
    print(validator.format_report(issues2))
    print()

    # Test case 3: Too many servos
    print("TEST 3: Multiple servos without external power")
    print("-"*70)
    design3 = {
        'microcontroller': 'arduino_uno',
        'components': ['servo_sg90', 'servo_sg90', 'servo_sg90'],
        'external_power': False
    }
    issues3 = validator.validate_circuit(design3)
    print(validator.format_report(issues3))
    print()

    # Test case 4: Good circuit
    print("TEST 4: Well-designed ESP32 circuit (should pass)")
    print("-"*70)
    design4 = {
        'microcontroller': 'esp32',
        'components': ['bme280', 'oled_ssd1306'],
        'features': ['wifi']
    }
    issues4 = validator.validate_circuit(design4)
    print(validator.format_report(issues4))


if __name__ == '__main__':
    main()
