"""
Repair Guidance System - Step-by-Step Repair Instructions

Generates detailed repair procedures for electronics:
- Diagnostic procedures
- Component-level troubleshooting
- Step-by-step repair instructions
- Safety warnings
- Tool requirements
- Success verification
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RepairDifficulty(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SafetyLevel(Enum):
    LOW = "low"  # Battery powered, low voltage
    MEDIUM = "medium"  # Line voltage isolated
    HIGH = "high"  # Line voltage present
    CRITICAL = "critical"  # High voltage, RF, or hazardous


@dataclass
class RepairStep:
    """Single step in a repair procedure."""
    step_number: int
    action: str
    details: str
    tools_required: List[str]
    safety_warnings: List[str]
    expected_result: str
    troubleshooting: Dict[str, str]  # problem -> solution
    images_needed: List[str]  # What to photograph
    verification: str  # How to verify success


@dataclass
class RepairProcedure:
    """Complete repair procedure for a specific issue."""
    issue_name: str
    symptoms: List[str]
    root_causes: List[str]
    difficulty: RepairDifficulty
    safety_level: SafetyLevel
    estimated_time_minutes: int
    required_tools: List[str]
    required_parts: List[str]
    steps: List[RepairStep]
    safety_precautions: List[str]
    success_criteria: List[str]
    common_mistakes: List[str]


class RepairGuidanceSystem:
    """Generates repair procedures based on detected components and issues."""

    def __init__(self):
        self.device_procedures = self._load_device_procedures()
        self.component_procedures = self._load_component_procedures()

    def generate_diagnostic_procedure(self, device_type: str,
                                      symptoms: List[str],
                                      components: List[str]) -> Dict[str, Any]:
        """Generate diagnostic flowchart for troubleshooting."""

        diagnostics = {
            "device_type": device_type,
            "reported_symptoms": symptoms,
            "diagnostic_tree": []
        }

        if device_type == "arduino":
            diagnostics["diagnostic_tree"] = [
                {
                    "test": "Does power LED light up?",
                    "tools": ["Visual inspection"],
                    "yes": "Power circuit OK, check USB connection",
                    "no": {
                        "test": "Measure voltage at VCC pin",
                        "tools": ["Multimeter"],
                        "expected": "5V ±0.25V",
                        "yes": "Power OK, LED may be damaged",
                        "no": "Check voltage regulator and input power"
                    }
                },
                {
                    "test": "Does computer recognize USB device?",
                    "tools": ["Computer, USB cable"],
                    "yes": "USB communication OK",
                    "no": {
                        "test": "Check D+ and D- continuity",
                        "tools": ["Multimeter in continuity mode"],
                        "fix": "Repair USB data lines or replace connector"
                    }
                },
                {
                    "test": "Can you upload sketch?",
                    "tools": ["Arduino IDE"],
                    "yes": "Bootloader OK",
                    "no": {
                        "test": "Does crystal oscillate?",
                        "tools": ["Oscilloscope"],
                        "expected": "16MHz square wave",
                        "no": "Replace crystal and load capacitors"
                    }
                }
            ]

        elif device_type == "router":
            diagnostics["diagnostic_tree"] = [
                {
                    "test": "Do any LEDs light up?",
                    "tools": ["Visual inspection"],
                    "no": {
                        "test": "Measure DC input voltage",
                        "tools": ["Multimeter"],
                        "expected": "12V or 5V depending on adapter",
                        "no": "Replace power adapter"
                    }
                },
                {
                    "test": "Can you access web interface?",
                    "tools": ["Computer, ethernet cable"],
                    "no": {
                        "test": "Can you ping 192.168.1.1?",
                        "tools": ["Command prompt"],
                        "no": "Router not booting - check flash memory"
                    }
                },
                {
                    "test": "Is WiFi working?",
                    "no": {
                        "test": "Check antenna connections",
                        "tools": ["Visual inspection"],
                        "fix": "Reconnect antenna or check RF module"
                    }
                }
            ]

        return diagnostics

    def generate_repair_procedure(self, device_type: str,
                                  issue: str,
                                  components_available: List[str]) -> RepairProcedure:
        """Generate step-by-step repair procedure."""

        # Arduino bootloader repair
        if device_type == "arduino" and "bootloader" in issue.lower():
            return RepairProcedure(
                issue_name="Arduino Bootloader Corruption",
                symptoms=[
                    "Cannot upload sketches",
                    "Sketches run but won't accept new uploads",
                    "Computer doesn't recognize device"
                ],
                root_causes=[
                    "Bootloader overwritten by sketch",
                    "Flash memory corruption",
                    "Wrong fuse settings"
                ],
                difficulty=RepairDifficulty.INTERMEDIATE,
                safety_level=SafetyLevel.LOW,
                estimated_time_minutes=20,
                required_tools=[
                    "Second Arduino (as ISP programmer)",
                    "6 jumper wires",
                    "Arduino IDE",
                    "Computer with USB"
                ],
                required_parts=[],
                steps=[
                    RepairStep(
                        step_number=1,
                        action="Setup ISP programmer",
                        details="Upload ArduinoISP sketch to working Arduino",
                        tools_required=["Working Arduino", "Arduino IDE"],
                        safety_warnings=["Disconnect target Arduino before wiring"],
                        expected_result="ISP sketch uploads successfully",
                        troubleshooting={
                            "Upload fails": "Check USB connection and port selection",
                            "Compilation error": "Update Arduino IDE"
                        },
                        images_needed=["IDE with ArduinoISP selected"],
                        verification="Serial monitor shows 'ArduinoISP'"
                    ),
                    RepairStep(
                        step_number=2,
                        action="Wire ISP connections",
                        details="Connect: D13→SCK, D12→MISO, D11→MOSI, D10→RESET, 5V→5V, GND→GND",
                        tools_required=["6 jumper wires"],
                        safety_warnings=["Double-check connections before powering"],
                        expected_result="All 6 wires connected correctly",
                        troubleshooting={
                            "Unsure of pinout": "Refer to Arduino pinout diagram"
                        },
                        images_needed=["Wiring diagram", "Physical connections"],
                        verification="Use multimeter to verify continuity"
                    ),
                    RepairStep(
                        step_number=3,
                        action="Burn bootloader",
                        details="Tools → Burn Bootloader in Arduino IDE",
                        tools_required=["Arduino IDE"],
                        safety_warnings=[],
                        expected_result="'Done burning bootloader' message",
                        troubleshooting={
                            "Verification error": "Check wiring, ensure target has power",
                            "Device signature wrong": "Wrong board selected in IDE",
                            "Can't enter programming mode": "Add 10µF cap between RST and GND on programmer"
                        },
                        images_needed=["IDE bootloader menu"],
                        verification="LEDs on target Arduino should flash during burn"
                    ),
                    RepairStep(
                        step_number=4,
                        action="Test repaired Arduino",
                        details="Disconnect ISP wires, upload Blink sketch via USB",
                        tools_required=["USB cable"],
                        safety_warnings=[],
                        expected_result="Sketch uploads and LED blinks",
                        troubleshooting={
                            "Still won't upload": "May need new ATmega chip",
                            "Upload very slow": "Bootloader burned successfully"
                        },
                        images_needed=["Blinking LED"],
                        verification="LED blinks at 1 second intervals"
                    )
                ],
                safety_precautions=[
                    "Work on non-conductive surface",
                    "Never connect/disconnect while powered",
                    "Verify voltage levels before connecting"
                ],
                success_criteria=[
                    "Sketches upload via USB",
                    "Serial communication works",
                    "No more device not found errors"
                ],
                common_mistakes=[
                    "Swapping MISO and MOSI",
                    "Forgetting to select correct board",
                    "Using damaged USB cable"
                ]
            )

        # ESP8266 re-flashing
        elif "esp" in device_type.lower() or "esp" in issue.lower():
            return RepairProcedure(
                issue_name="ESP8266/ESP32 Firmware Recovery",
                symptoms=[
                    "Won't boot",
                    "Stuck in boot loop",
                    "WiFi not working",
                    "Garbage serial output"
                ],
                root_causes=[
                    "Corrupted firmware",
                    "Bad OTA update",
                    "Flash memory errors"
                ],
                difficulty=RepairDifficulty.ADVANCED,
                safety_level=SafetyLevel.MEDIUM,
                estimated_time_minutes=30,
                required_tools=[
                    "USB-to-UART adapter (3.3V!)",
                    "Jumper wires",
                    "Computer",
                    "esptool.py or flash tool"
                ],
                required_parts=["Firmware binary file"],
                steps=[
                    RepairStep(
                        step_number=1,
                        action="Enter flash mode",
                        details="Connect GPIO0 to GND, power cycle module",
                        tools_required=["Jumper wire"],
                        safety_warnings=["CRITICAL: Must use 3.3V, NOT 5V! Will destroy chip!"],
                        expected_result="Boot mode messages on serial",
                        troubleshooting={
                            "No serial output": "Check TX/RX not swapped",
                            "Gibberish output": "Wrong baud rate, try 115200"
                        },
                        images_needed=["GPIO0 pulled low"],
                        verification="esptool.py can detect chip"
                    ),
                    RepairStep(
                        step_number=2,
                        action="Erase flash",
                        details="Run: esptool.py --port /dev/ttyUSB0 erase_flash",
                        tools_required=["esptool.py"],
                        safety_warnings=[],
                        expected_result="Erasing flash... done",
                        troubleshooting={
                            "Connection failed": "GPIO0 must be grounded",
                            "Timeout": "Check power supply current capacity (need 250mA+)"
                        },
                        images_needed=["Terminal output"],
                        verification="Erase completes without errors"
                    ),
                    RepairStep(
                        step_number=3,
                        action="Flash new firmware",
                        details="Run: esptool.py write_flash 0x00000 firmware.bin",
                        tools_required=["esptool.py", "firmware binary"],
                        safety_warnings=["Don't disconnect during flash"],
                        expected_result="Writing... done",
                        troubleshooting={
                            "Write error": "Bad flash chip, may be hardware failure",
                            "Verify failed": "Download firmware again"
                        },
                        images_needed=["Flash progress"],
                        verification="100% complete, no errors"
                    ),
                    RepairStep(
                        step_number=4,
                        action="Test module",
                        details="Remove GPIO0 ground, reset module, check boot",
                        tools_required=["Serial monitor"],
                        safety_warnings=[],
                        expected_result="Clean boot messages, no errors",
                        troubleshooting={
                            "Still boot loop": "Try different firmware version",
                            "No WiFi": "May need to flash RF calibration data"
                        },
                        images_needed=["Boot messages"],
                        verification="Module boots and runs code"
                    )
                ],
                safety_precautions=[
                    "NEVER use 5V on ESP8266 - permanent damage!",
                    "Ensure adequate current supply (300mA peak)",
                    "Use anti-static precautions",
                    "Disconnect antenna during flash (if external)"
                ],
                success_criteria=[
                    "Module boots without errors",
                    "WiFi can scan networks",
                    "Serial output is clean"
                ],
                common_mistakes=[
                    "Using 5V instead of 3.3V (destroys chip!)",
                    "Insufficient power supply current",
                    "TX/RX not crossed over",
                    "Forgetting to ground GPIO0"
                ]
            )

        # Voltage regulator replacement
        elif "regulator" in issue.lower() or "power" in issue.lower():
            return RepairProcedure(
                issue_name="Voltage Regulator Replacement",
                symptoms=[
                    "No output voltage",
                    "Regulator very hot",
                    "Output voltage incorrect",
                    "Device shuts down under load"
                ],
                root_causes=[
                    "Shorted output",
                    "Excessive current draw",
                    "Regulator failure",
                    "Inadequate cooling"
                ],
                difficulty=RepairDifficulty.INTERMEDIATE,
                safety_level=SafetyLevel.MEDIUM,
                estimated_time_minutes=25,
                required_tools=[
                    "Soldering iron",
                    "Desoldering pump or wick",
                    "Multimeter",
                    "Heat sink (optional)"
                ],
                required_parts=["Replacement regulator (same specs)"],
                steps=[
                    RepairStep(
                        step_number=1,
                        action="Diagnose failure",
                        details="Measure input voltage, output voltage, and continuity",
                        tools_required=["Multimeter"],
                        safety_warnings=["Disconnect power first"],
                        expected_result="Identify which rail is failing",
                        troubleshooting={
                            "Input OK, no output": "Regulator failed",
                            "No input voltage": "Check upstream components",
                            "Output shorted to ground": "Find short before replacing"
                        },
                        images_needed=["Voltage measurements"],
                        verification="Confirmed regulator is the issue"
                    ),
                    RepairStep(
                        step_number=2,
                        action="Remove failed regulator",
                        details="Desolder all 3 pins, remove component",
                        tools_required=["Soldering iron", "Desoldering pump"],
                        safety_warnings=["Hot surface - don't touch PCB immediately"],
                        expected_result="Clean pads, no solder bridges",
                        troubleshooting={
                            "Can't remove": "Add fresh solder first to help flow",
                            "Lifted pad": "Can jumper wire to trace"
                        },
                        images_needed=["Empty footprint"],
                        verification="All holes clear, pads intact"
                    ),
                    RepairStep(
                        step_number=3,
                        action="Install new regulator",
                        details="Insert pins, solder all connections, verify orientation",
                        tools_required=["Soldering iron", "New regulator"],
                        safety_warnings=["Verify pin 1 orientation - backwards will short!"],
                        expected_result="Good solder joints, correct orientation",
                        troubleshooting={
                            "Unsure of orientation": "Check datasheet, match original",
                            "Poor solder joint": "Reheat with fresh solder"
                        },
                        images_needed=["Installed regulator", "Solder joints"],
                        verification="Visual inspection + continuity test"
                    ),
                    RepairStep(
                        step_number=4,
                        action="Test repair",
                        details="Apply input power, measure output voltage",
                        tools_required=["Multimeter", "Power supply"],
                        safety_warnings=["Start with low current limit if possible"],
                        expected_result="Correct output voltage, no heat issues",
                        troubleshooting={
                            "Still no output": "Check surrounding components",
                            "Gets hot quickly": "May have downstream short",
                            "Wrong voltage": "Wrong part installed"
                        },
                        images_needed=["Output voltage reading"],
                        verification="5V ±0.25V (or spec voltage)"
                    )
                ],
                safety_precautions=[
                    "Disconnect all power sources",
                    "Let components cool before touching",
                    "Use ESD protection",
                    "Verify part numbers before installing"
                ],
                success_criteria=[
                    "Output voltage within spec",
                    "Regulator runs cool under load",
                    "Device functions normally"
                ],
                common_mistakes=[
                    "Installing regulator backwards",
                    "Not fixing downstream short first",
                    "Using wrong voltage regulator",
                    "Bridging pins with solder"
                ]
            )

        # Default generic procedure
        return self._generic_repair_procedure(device_type, issue)

    def _generic_repair_procedure(self, device_type: str, issue: str) -> RepairProcedure:
        """Generate generic repair procedure when specific one not available."""
        return RepairProcedure(
            issue_name=f"{device_type} - {issue}",
            symptoms=["Device not functioning"],
            root_causes=["Unknown"],
            difficulty=RepairDifficulty.INTERMEDIATE,
            safety_level=SafetyLevel.MEDIUM,
            estimated_time_minutes=30,
            required_tools=["Multimeter", "Screwdrivers", "Soldering iron"],
            required_parts=[],
            steps=[
                RepairStep(
                    step_number=1,
                    action="Visual inspection",
                    details="Look for damaged components, burn marks, broken traces",
                    tools_required=[],
                    safety_warnings=["Disconnect power"],
                    expected_result="Identify obvious damage",
                    troubleshooting={},
                    images_needed=["Overall board", "Problem areas"],
                    verification="Document all findings"
                ),
                RepairStep(
                    step_number=2,
                    action="Power supply check",
                    details="Verify all voltage rails present and correct",
                    tools_required=["Multimeter"],
                    safety_warnings=["Check for shorts first"],
                    expected_result="All voltages within spec",
                    troubleshooting={
                        "No voltage": "Check regulators and input power",
                        "Wrong voltage": "Measure regulator inputs"
                    },
                    images_needed=["Voltage readings"],
                    verification="Document all rail voltages"
                ),
                RepairStep(
                    step_number=3,
                    action="Component testing",
                    details="Test suspect components individually",
                    tools_required=["Multimeter", "Oscilloscope"],
                    safety_warnings=["Some components hold charge"],
                    expected_result="Identify failed components",
                    troubleshooting={},
                    images_needed=["Test results"],
                    verification="Failed components identified"
                )
            ],
            safety_precautions=[
                "Disconnect all power",
                "Discharge capacitors",
                "Use ESD protection"
            ],
            success_criteria=["Device functions"],
            common_mistakes=["Rushing diagnosis"]
        )

    def _load_device_procedures(self) -> Dict[str, Any]:
        """Load device-specific repair knowledge."""
        return {
            "arduino": {
                "common_issues": [
                    "bootloader_corruption",
                    "usb_not_recognized",
                    "io_pin_damaged",
                    "crystal_failure"
                ],
                "repair_difficulty": "easy_to_moderate"
            },
            "esp8266": {
                "common_issues": [
                    "firmware_corruption",
                    "boot_loop",
                    "wifi_failure",
                    "flash_failure"
                ],
                "repair_difficulty": "moderate_to_advanced"
            },
            "router": {
                "common_issues": [
                    "firmware_brick",
                    "wifi_not_working",
                    "ethernet_failure",
                    "power_supply_failure"
                ],
                "repair_difficulty": "moderate"
            }
        }

    def _load_component_procedures(self) -> Dict[str, Any]:
        """Load component-level repair knowledge."""
        return {
            "capacitor": {
                "testing": "ESR meter or capacitance meter",
                "failure_signs": ["Bulging", "Leaking", "High ESR"],
                "replacement": "Match voltage rating (higher OK) and capacitance"
            },
            "voltage_regulator": {
                "testing": "Measure input and output voltages",
                "failure_signs": ["No output", "Wrong voltage", "Excessive heat"],
                "replacement": "Must match voltage and current specs exactly"
            }
        }


# Global instance
repair_guidance = RepairGuidanceSystem()
