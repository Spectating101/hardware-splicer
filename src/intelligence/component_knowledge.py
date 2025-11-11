"""
Component Knowledge Base - Deep Electronics Domain Knowledge

This module contains extensive knowledge about electronic components:
- Physical properties (pinouts, packages)
- Electrical characteristics (voltage ranges, current limits)
- Typical use cases and circuit patterns
- Common values and their applications
- Failure modes and troubleshooting
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ComponentCategory(Enum):
    MICROCONTROLLER = "microcontroller"
    POWER = "power"
    PASSIVE = "passive"
    SENSOR = "sensor"
    CONNECTOR = "connector"
    DISPLAY = "display"
    WIRELESS = "wireless"
    STORAGE = "storage"
    TIMING = "timing"
    PROTECTION = "protection"
    LOGIC = "logic"
    ANALOG = "analog"


@dataclass
class ComponentSpec:
    """Detailed component specifications."""
    name: str
    category: ComponentCategory
    typical_voltages: List[float]  # Volts
    typical_currents: List[float]  # Amps
    power_dissipation: Optional[float]  # Watts
    pin_count: Optional[int]
    common_packages: List[str]
    typical_values: List[str]  # For passives
    common_companions: List[str]  # Components often found nearby
    typical_functions: List[str]
    modification_potential: List[str]
    failure_modes: List[str]
    test_points: List[str]  # Where to probe for testing


# Comprehensive component knowledge database
COMPONENT_DATABASE = {
    # Microcontrollers
    "Arduino-Uno": ComponentSpec(
        name="Arduino Uno (ATmega328P)",
        category=ComponentCategory.MICROCONTROLLER,
        typical_voltages=[5.0, 3.3],
        typical_currents=[0.02, 0.05],  # 20-50mA active
        power_dissipation=0.25,
        pin_count=28,
        common_packages=["DIP-28", "TQFP-32"],
        typical_values=[],
        common_companions=["Capacitor", "Crystal", "Resistor", "USB-Connector"],
        typical_functions=["programmable_io", "pwm", "adc", "uart", "spi", "i2c"],
        modification_potential=[
            "Reprogram for different functionality",
            "Add external sensors via I2C/SPI",
            "Use as standalone MCU after extracting",
            "Connect WiFi module for IoT",
            "Add SD card for data logging"
        ],
        failure_modes=["corrupted_bootloader", "blown_io_pin", "crystal_failure"],
        test_points=["VCC", "GND", "RESET", "XTAL1", "XTAL2"]
    ),

    "ATmega328P": ComponentSpec(
        name="ATmega328P Microcontroller",
        category=ComponentCategory.MICROCONTROLLER,
        typical_voltages=[5.0, 3.3],
        typical_currents=[0.015, 0.04],
        power_dissipation=0.2,
        pin_count=28,
        common_packages=["DIP-28", "TQFP-32", "QFN-32"],
        typical_values=[],
        common_companions=["Capacitor", "Crystal", "Resistor"],
        typical_functions=["programmable_io", "pwm", "adc", "uart", "spi", "i2c"],
        modification_potential=["Same as Arduino-Uno"],
        failure_modes=["corrupted_flash", "blown_io", "power_issue"],
        test_points=["VCC", "GND", "RESET"]
    ),

    "ESP8266": ComponentSpec(
        name="ESP8266 WiFi Module",
        category=ComponentCategory.WIRELESS,
        typical_voltages=[3.3],
        typical_currents=[0.07, 0.17],  # 70-170mA active, up to 300mA peak
        power_dissipation=0.6,
        pin_count=32,
        common_packages=["QFN-32"],
        typical_values=[],
        common_companions=["Flash-Memory", "Voltage-Regulator", "Capacitor", "Antenna"],
        typical_functions=["wifi", "tcp_ip", "mqtt", "http", "programmable_gpio"],
        modification_potential=[
            "Extract and use standalone for IoT projects",
            "Flash custom firmware (NodeMCU, Tasmota)",
            "Use as WiFi-to-serial bridge",
            "Add external antenna for better range",
            "Connect sensors for wireless data collection"
        ],
        failure_modes=["wifi_calibration_lost", "flash_corruption", "power_instability"],
        test_points=["VCC", "GND", "EN", "RST", "TX", "RX"]
    ),

    "ESP32": ComponentSpec(
        name="ESP32 Dual-Core WiFi+BT Module",
        category=ComponentCategory.WIRELESS,
        typical_voltages=[3.3],
        typical_currents=[0.08, 0.24],  # 80-240mA active
        power_dissipation=0.8,
        pin_count=48,
        common_packages=["QFN-48", "QFN-56"],
        typical_values=[],
        common_companions=["Flash-Memory", "PSRAM", "Voltage-Regulator", "Capacitor"],
        typical_functions=["wifi", "bluetooth", "dual_core", "adc", "dac", "touch_sensor"],
        modification_potential=[
            "More powerful than ESP8266 for complex projects",
            "Use Bluetooth for BLE sensor networks",
            "Run FreeRTOS for multitasking",
            "Add camera for vision projects"
        ],
        failure_modes=["bootloader_issue", "wifi_cal_lost", "brown_out"],
        test_points=["VCC", "GND", "EN", "IO0", "TX", "RX"]
    ),

    # Voltage Regulators
    "Voltage-Regulator": ComponentSpec(
        name="Voltage Regulator (Generic)",
        category=ComponentCategory.POWER,
        typical_voltages=[5.0, 3.3, 12.0],
        typical_currents=[0.1, 1.0, 1.5],  # 100mA to 1.5A typical
        power_dissipation=2.0,
        pin_count=3,
        common_packages=["TO-220", "SOT-23", "TO-252"],
        typical_values=["5V", "3.3V", "12V", "adjustable"],
        common_companions=["Capacitor", "Diode", "Resistor"],
        typical_functions=["voltage_conversion", "power_regulation", "current_limiting"],
        modification_potential=[
            "Tap regulated voltage for additional circuits",
            "Replace with higher current regulator",
            "Add heatsink for more power",
            "Use as portable power supply"
        ],
        failure_modes=["thermal_shutdown", "output_short", "overvoltage_damage"],
        test_points=["VIN", "VOUT", "GND"]
    ),

    "LM7805": ComponentSpec(
        name="LM7805 5V Linear Regulator",
        category=ComponentCategory.POWER,
        typical_voltages=[5.0],
        typical_currents=[1.0, 1.5],
        power_dissipation=15.0,  # With heatsink
        pin_count=3,
        common_packages=["TO-220"],
        typical_values=["5V"],
        common_companions=["Capacitor"],
        typical_functions=["5v_regulation"],
        modification_potential=["Tap 5V for USB devices", "Add heatsink for 1A+"],
        failure_modes=["thermal_shutdown", "short_circuit"],
        test_points=["VIN", "VOUT", "GND"]
    ),

    "AMS1117": ComponentSpec(
        name="AMS1117 Low Dropout Regulator",
        category=ComponentCategory.POWER,
        typical_voltages=[3.3, 5.0],
        typical_currents=[1.0],
        power_dissipation=1.0,
        pin_count=4,
        common_packages=["SOT-223", "TO-252"],
        typical_values=["3.3V", "5V"],
        common_companions=["Capacitor"],
        typical_functions=["low_dropout_regulation"],
        modification_potential=["Good for 3.3V projects", "Low heat dissipation"],
        failure_modes=["thermal_shutdown", "dropout_voltage_too_low"],
        test_points=["VIN", "VOUT", "GND"]
    ),

    # Capacitors
    "Capacitor": ComponentSpec(
        name="Capacitor (Generic)",
        category=ComponentCategory.PASSIVE,
        typical_voltages=[6.3, 16, 25, 50],
        typical_currents=[0.0],  # Passive
        power_dissipation=0.0,
        pin_count=2,
        common_packages=["0805", "1206", "radial", "SMD"],
        typical_values=["100nF", "10uF", "100uF", "1uF", "22pF", "0.1uF"],
        common_companions=["Voltage-Regulator", "Microcontroller", "Crystal"],
        typical_functions=["decoupling", "filtering", "energy_storage", "timing"],
        modification_potential=[
            "Replace for different filtering characteristics",
            "Add bulk capacitance for stability",
            "Use for power smoothing"
        ],
        failure_modes=["dried_out", "short_circuit", "open_circuit", "ESR_high"],
        test_points=["positive", "negative"]
    ),

    # Resistors
    "Resistor": ComponentSpec(
        name="Resistor (Generic)",
        category=ComponentCategory.PASSIVE,
        typical_voltages=[],  # Determined by circuit
        typical_currents=[0.001, 0.1],
        power_dissipation=0.25,  # 1/4 watt typical
        pin_count=2,
        common_packages=["0805", "1206", "through-hole"],
        typical_values=["10k", "1k", "100", "4.7k", "10", "100k"],
        common_companions=["LED", "Transistor", "IC"],
        typical_functions=["current_limiting", "pull_up", "pull_down", "voltage_divider"],
        modification_potential=[
            "Change value for different current",
            "Add for pull-up/pull-down",
            "Replace for LED brightness"
        ],
        failure_modes=["burnt_out", "cracked", "value_drift"],
        test_points=["terminal1", "terminal2"]
    ),

    # Connectors
    "USB-Connector": ComponentSpec(
        name="USB Connector",
        category=ComponentCategory.CONNECTOR,
        typical_voltages=[5.0],
        typical_currents=[0.5, 2.0],  # USB 2.0: 500mA, USB 3.0: 900mA, USB-C: up to 3A
        power_dissipation=0.0,
        pin_count=4,
        common_packages=["USB-A", "USB-B", "Micro-USB", "USB-C"],
        typical_values=[],
        common_companions=["Voltage-Regulator", "Fuse", "Diode"],
        typical_functions=["power_input", "data_transfer", "programming"],
        modification_potential=[
            "Use as 5V power source",
            "Add for device programming",
            "Charge batteries via USB"
        ],
        failure_modes=["broken_pins", "worn_connector", "short_circuit"],
        test_points=["VBUS", "D+", "D-", "GND"]
    ),

    "Ethernet-Connector": ComponentSpec(
        name="Ethernet RJ45 Connector",
        category=ComponentCategory.CONNECTOR,
        typical_voltages=[48.0],  # PoE
        typical_currents=[0.35],  # PoE
        power_dissipation=0.0,
        pin_count=8,
        common_packages=["RJ45"],
        typical_values=[],
        common_companions=["Transformer", "LED"],
        typical_functions=["network_data", "poe_power"],
        modification_potential=[
            "Extract PoE for power",
            "Use for wired networking projects",
            "Add to Raspberry Pi"
        ],
        failure_modes=["broken_tab", "damaged_pins"],
        test_points=["TX+", "TX-", "RX+", "RX-"]
    ),

    # Timing
    "Crystal": ComponentSpec(
        name="Crystal Oscillator",
        category=ComponentCategory.TIMING,
        typical_voltages=[3.3, 5.0],
        typical_currents=[0.001],
        power_dissipation=0.01,
        pin_count=2,
        common_packages=["HC-49", "SMD"],
        typical_values=["16MHz", "8MHz", "32.768kHz", "20MHz"],
        common_companions=["Capacitor", "Microcontroller"],
        typical_functions=["clock_generation", "timing_reference"],
        modification_potential=[
            "Replace for overclock/underclock",
            "Use for RTC circuits"
        ],
        failure_modes=["stopped_oscillation", "cracked_crystal"],
        test_points=["XTAL1", "XTAL2"]
    ),

    # Storage
    "Flash-Memory": ComponentSpec(
        name="Flash Memory Chip",
        category=ComponentCategory.STORAGE,
        typical_voltages=[3.3, 1.8],
        typical_currents=[0.01, 0.03],
        power_dissipation=0.1,
        pin_count=8,
        common_packages=["SOIC-8", "WSON-8"],
        typical_values=["1MB", "4MB", "8MB", "16MB"],
        common_companions=["ESP8266", "ESP32", "Microcontroller"],
        typical_functions=["firmware_storage", "data_storage"],
        modification_potential=[
            "Dump firmware for analysis",
            "Replace with larger capacity",
            "Use for data logging"
        ],
        failure_modes=["corruption", "write_failure", "wear_out"],
        test_points=["CS", "CLK", "MISO", "MOSI"]
    ),

    # Indicators
    "LED": ComponentSpec(
        name="LED (Light Emitting Diode)",
        category=ComponentCategory.PASSIVE,
        typical_voltages=[1.8, 2.0, 3.0],  # Forward voltage
        typical_currents=[0.02],  # 20mA typical
        power_dissipation=0.06,
        pin_count=2,
        common_packages=["0805", "1206", "5mm", "3mm"],
        typical_values=["red", "green", "blue", "white"],
        common_companions=["Resistor"],
        typical_functions=["status_indicator", "power_indicator"],
        modification_potential=[
            "Add for debugging",
            "Change color",
            "Use for visual feedback"
        ],
        failure_modes=["burnt_out", "reverse_voltage_damage"],
        test_points=["anode", "cathode"]
    ),
}


def get_component_spec(component_name: str) -> Optional[ComponentSpec]:
    """Get detailed specs for a component."""
    # Try exact match first
    if component_name in COMPONENT_DATABASE:
        return COMPONENT_DATABASE[component_name]

    # Try partial match
    for key, spec in COMPONENT_DATABASE.items():
        if key.lower() in component_name.lower() or component_name.lower() in key.lower():
            return spec

    return None


def infer_component_relationships(comp1_name: str, comp2_name: str) -> Tuple[str, float, str]:
    """
    Infer the relationship between two components based on domain knowledge.

    Returns:
        (relationship_type, confidence, functional_role)
    """
    spec1 = get_component_spec(comp1_name)
    spec2 = get_component_spec(comp2_name)

    if not spec1 or not spec2:
        return ("unknown", 0.3, "Unknown connection")

    # Power relationships
    if spec1.category == ComponentCategory.POWER:
        if spec2.category == ComponentCategory.PASSIVE and "Capacitor" in comp2_name:
            return ("power", 0.9, "Power filtering/smoothing")
        if spec2.category == ComponentCategory.MICROCONTROLLER:
            return ("power", 0.95, "MCU power supply")

    # Decoupling capacitors near MCU (check both directions)
    if spec1.category == ComponentCategory.MICROCONTROLLER or spec2.category == ComponentCategory.MICROCONTROLLER:
        if "Capacitor" in comp1_name or "Capacitor" in comp2_name:
            return ("power", 0.85, "Power decoupling")
        if "Crystal" in comp1_name or "Crystal" in comp2_name:
            return ("signal", 0.9, "Clock generation")
        if "Resistor" in comp1_name or "Resistor" in comp2_name:
            return ("signal", 0.6, "Pull-up/pull-down or current limiting")

    # Crystal load capacitors
    if spec1.category == ComponentCategory.TIMING:
        if "Capacitor" in comp2_name:
            return ("signal", 0.85, "Crystal load capacitance")

    # USB connections
    if "USB" in comp1_name:
        if spec2.category == ComponentCategory.POWER:
            return ("power", 0.9, "USB power regulation")
        if spec2.category == ComponentCategory.MICROCONTROLLER:
            return ("data", 0.85, "USB data interface")

    # Wireless module connections
    if spec1.category == ComponentCategory.WIRELESS:
        if "Flash" in comp2_name or "Memory" in comp2_name:
            return ("data", 0.95, "Firmware storage")
        if spec2.category == ComponentCategory.POWER:
            return ("power", 0.9, "WiFi module power")

    # LED and resistor
    if "LED" in comp1_name and "Resistor" in comp2_name:
        return ("signal", 0.95, "LED current limiting")

    return ("unknown", 0.4, "Unidentified connection")


def estimate_power_consumption(component_name: str) -> Dict[str, float]:
    """Estimate power consumption for a component."""
    spec = get_component_spec(component_name)

    if not spec:
        return {"voltage_v": 0, "current_a": 0, "power_w": 0}

    # Use typical values
    voltage = spec.typical_voltages[0] if spec.typical_voltages else 0
    current = spec.typical_currents[0] if spec.typical_currents else 0
    power = voltage * current

    return {
        "voltage_v": voltage,
        "current_a": current,
        "power_w": power,
        "peak_current_a": spec.typical_currents[-1] if spec.typical_currents else current
    }


def get_modification_ideas(component_name: str) -> List[str]:
    """Get specific modification ideas for a component."""
    spec = get_component_spec(component_name)
    return spec.modification_potential if spec else []


def get_test_points(component_name: str) -> List[str]:
    """Get recommended test points for debugging."""
    spec = get_component_spec(component_name)
    return spec.test_points if spec else []


def get_failure_modes(component_name: str) -> List[str]:
    """Get common failure modes for troubleshooting."""
    spec = get_component_spec(component_name)
    return spec.failure_modes if spec else []
