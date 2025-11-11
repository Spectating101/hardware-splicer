"""
Modification Planner - Circuit Repurposing & Enhancement

Plans safe modifications for repurposing electronics:
- Component extraction strategies
- Circuit modification procedures
- Firmware reprogramming steps
- Safety validation
- Compatibility checking
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ModificationType(Enum):
    EXTRACTION = "extraction"  # Remove component for reuse
    REPROGRAMMING = "reprogramming"  # Change firmware
    CIRCUIT_MOD = "circuit_modification"  # Physical circuit changes
    ENHANCEMENT = "enhancement"  # Add new capabilities
    REPURPOSE = "repurpose"  # Complete function change


@dataclass
class ModificationStep:
    """Single step in modification process."""
    step_number: int
    action: str
    rationale: str
    tools_required: List[str]
    components_affected: List[str]
    reversible: bool
    safety_warnings: List[str]
    expected_outcome: str
    validation_test: str


@dataclass
class ModificationPlan:
    """Complete modification plan."""
    modification_name: str
    modification_type: ModificationType
    goal: str
    difficulty: str
    estimated_time_minutes: int
    cost_estimate_usd: float
    required_skills: List[str]
    tools_needed: List[str]
    parts_needed: List[str]
    steps: List[ModificationStep]
    safety_checks: List[str]
    reversibility: str  # "fully", "partially", "irreversible"
    success_criteria: List[str]
    alternative_approaches: List[str]


class ModificationPlanner:
    """Plans circuit modifications and repurposing."""

    def __init__(self):
        self.modification_library = self._load_modification_library()

    def plan_component_extraction(self, component_name: str,
                                  device_type: str,
                                  intended_use: str) -> ModificationPlan:
        """Plan safe extraction of component for reuse."""

        if "ESP8266" in component_name or "ESP32" in component_name:
            return ModificationPlan(
                modification_name=f"Extract {component_name} Module",
                modification_type=ModificationType.EXTRACTION,
                goal=f"Remove {component_name} for use in {intended_use}",
                difficulty="intermediate",
                estimated_time_minutes=45,
                cost_estimate_usd=0,
                required_skills=["Desoldering", "Component identification"],
                tools_needed=[
                    "Hot air station or heat gun",
                    "Flux",
                    "Tweezers",
                    "Multimeter",
                    "Magnifying glass"
                ],
                parts_needed=[
                    "Breakout board (optional)",
                    "Pin headers (optional)"
                ],
                steps=[
                    ModificationStep(
                        step_number=1,
                        action="Document original connections",
                        rationale="Need pinout reference for reuse",
                        tools_required=["Camera", "Multimeter"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=["Disconnect power completely"],
                        expected_outcome="Photo and notes of all connections",
                        validation_test="Cross-reference with datasheet"
                    ),
                    ModificationStep(
                        step_number=2,
                        action="Identify all solder joints",
                        rationale="Must desolder all pads to remove module",
                        tools_required=["Magnifying glass"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="All pads marked and counted",
                        validation_test="Compare pad count with datasheet"
                    ),
                    ModificationStep(
                        step_number=3,
                        action="Apply flux to all pads",
                        rationale="Flux helps heat transfer and solder flow",
                        tools_required=["Flux pen or liquid flux"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=["Work in ventilated area"],
                        expected_outcome="Flux visible on all pads",
                        validation_test="Visual inspection"
                    ),
                    ModificationStep(
                        step_number=4,
                        action="Heat module evenly with hot air",
                        rationale="Reflow all solder simultaneously to prevent damage",
                        tools_required=["Hot air station at 350°C"],
                        components_affected=[component_name],
                        reversible=False,
                        safety_warnings=[
                            "Don't overheat - can damage chip",
                            "Keep hot air moving",
                            "Watch for other components shifting"
                        ],
                        expected_outcome="Module releases from board",
                        validation_test="Gentle pressure with tweezers - should lift freely"
                    ),
                    ModificationStep(
                        step_number=5,
                        action="Clean pads on module",
                        rationale="Remove excess solder for clean installation later",
                        tools_required=["Solder wick", "Isopropyl alcohol"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=["Let module cool first"],
                        expected_outcome="Clean, flat pads on module",
                        validation_test="Visual inspection under magnification"
                    ),
                    ModificationStep(
                        step_number=6,
                        action="Test extracted module",
                        rationale="Verify not damaged during extraction",
                        tools_required=["Multimeter", "Power supply", "USB-UART adapter"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=["Use 3.3V only"],
                        expected_outcome="Module powers up and responds",
                        validation_test="Connect serial adapter, see boot messages"
                    )
                ],
                safety_checks=[
                    "Power completely disconnected",
                    "Work area is non-conductive",
                    "Hot air temperature not excessive",
                    "Other components secured or protected"
                ],
                reversibility="irreversible_for_original_device",
                success_criteria=[
                    "Module removed without damage",
                    "Module powers up correctly",
                    "All functions test OK",
                    "Ready for new project"
                ],
                alternative_approaches=[
                    "Use desoldering gun if available",
                    "Solder individual pads with iron (slow but safe)",
                    "Cut traces and desolder pads individually (destructive)"
                ]
            )

        elif "Arduino" in component_name or "ATmega" in component_name:
            return ModificationPlan(
                modification_name=f"Extract {component_name} MCU",
                modification_type=ModificationType.EXTRACTION,
                goal=f"Remove MCU chip for standalone use",
                difficulty="beginner_to_intermediate",
                estimated_time_minutes=20,
                cost_estimate_usd=0,
                required_skills=["Basic soldering/desoldering"],
                tools_needed=[
                    "Desoldering pump OR desoldering wick",
                    "Soldering iron",
                    "IC extractor tool (for DIP) OR tweezers (for SMD)"
                ],
                parts_needed=["Breadboard or dev board for testing"],
                steps=[
                    ModificationStep(
                        step_number=1,
                        action="Identify chip package type",
                        rationale="DIP packages much easier to remove than SMD",
                        tools_required=[],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Know if DIP or SMD package",
                        validation_test="DIP has through-hole pins, SMD is surface mount"
                    ),
                    ModificationStep(
                        step_number=2,
                        action="Desolder all pins",
                        rationale="All pins must be free to remove chip",
                        tools_required=["Soldering iron", "Desoldering pump or wick"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=["Don't overheat chip - work quickly on each pin"],
                        expected_outcome="All solder removed from pins",
                        validation_test="Gently wiggle chip - should move freely"
                    ),
                    ModificationStep(
                        step_number=3,
                        action="Extract chip carefully",
                        rationale="Bent pins or ESD damage can destroy chip",
                        tools_required=["IC extractor or tweezers"],
                        components_affected=[component_name],
                        reversible=False,
                        safety_warnings=["Use ESD protection", "Don't bend pins"],
                        expected_outcome="Chip removed with straight pins",
                        validation_test="Visual inspection of all pins"
                    ),
                    ModificationStep(
                        step_number=4,
                        action="Test extracted chip",
                        rationale="Verify chip still functional",
                        tools_required=["Breadboard", "Arduino as ISP"],
                        components_affected=[component_name],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Chip can be programmed and runs code",
                        validation_test="Upload blink sketch via ISP"
                    )
                ],
                safety_checks=[
                    "Power disconnected",
                    "ESD protection used",
                    "Pins not bent"
                ],
                reversibility="partially_reversible",
                success_criteria=[
                    "Chip extracted without damage",
                    "All pins straight",
                    "Chip programmable and functional"
                ],
                alternative_approaches=[
                    "Leave chip in place, use entire board",
                    "Cut chip out with cutters (destructive)"
                ]
            )

        else:
            return self._generic_extraction_plan(component_name, device_type)

    def plan_firmware_modification(self, device_type: str,
                                   current_firmware: str,
                                   desired_functionality: str) -> ModificationPlan:
        """Plan firmware replacement or modification."""

        if device_type == "arduino":
            return ModificationPlan(
                modification_name="Arduino Firmware Reprogramming",
                modification_type=ModificationType.REPROGRAMMING,
                goal=f"Change functionality to: {desired_functionality}",
                difficulty="beginner",
                estimated_time_minutes=30,
                cost_estimate_usd=0,
                required_skills=["Basic Arduino programming", "USB connection"],
                tools_needed=["Computer", "Arduino IDE", "USB cable"],
                parts_needed=[],
                steps=[
                    ModificationStep(
                        step_number=1,
                        action="Backup current firmware (if possible)",
                        rationale="May want to restore original function later",
                        tools_required=["avrdude"],
                        components_affected=["Arduino"],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Firmware dumped to .hex file",
                        validation_test="Check file size > 0"
                    ),
                    ModificationStep(
                        step_number=2,
                        action="Write or obtain new sketch",
                        rationale="Need code for desired functionality",
                        tools_required=["Arduino IDE", "Libraries"],
                        components_affected=["Arduino"],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Sketch compiles without errors",
                        validation_test="Verify > Compilation successful"
                    ),
                    ModificationStep(
                        step_number=3,
                        action="Upload new firmware",
                        rationale="Replace old functionality with new",
                        tools_required=["Arduino IDE", "USB cable"],
                        components_affected=["Arduino"],
                        reversible=True,
                        safety_warnings=["Don't disconnect during upload"],
                        expected_outcome="Upload successful",
                        validation_test="See 'Done uploading' message"
                    ),
                    ModificationStep(
                        step_number=4,
                        action="Test new functionality",
                        rationale="Verify reprogramming worked",
                        tools_required=["Serial monitor", "Test equipment"],
                        components_affected=["Arduino"],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="New code runs as expected",
                        validation_test="Observe desired behavior"
                    )
                ],
                safety_checks=[
                    "Don't upload code that could damage hardware",
                    "Verify pin assignments correct",
                    "Test with limited power first"
                ],
                reversibility="fully_reversible",
                success_criteria=[
                    "New code uploads successfully",
                    "Desired functionality works",
                    "No hardware damage"
                ],
                alternative_approaches=[
                    "Use bootloader for easy updates",
                    "Use ISP programmer for direct flash access"
                ]
            )

        elif "router" in device_type.lower():
            return ModificationPlan(
                modification_name="Router Firmware Upgrade (OpenWRT)",
                modification_type=ModificationType.REPROGRAMMING,
                goal="Install OpenWRT for advanced features",
                difficulty="advanced",
                estimated_time_minutes=60,
                cost_estimate_usd=0,
                required_skills=["Networking", "Linux command line", "Risk tolerance"],
                tools_needed=[
                    "Computer",
                    "Ethernet cable",
                    "TFTP server software",
                    "Serial adapter (for recovery)"
                ],
                parts_needed=[],
                steps=[
                    ModificationStep(
                        step_number=1,
                        action="Research router compatibility",
                        rationale="Not all routers support OpenWRT",
                        tools_required=["Web browser"],
                        components_affected=["Router"],
                        reversible=True,
                        safety_warnings=["Wrong firmware can brick router!"],
                        expected_outcome="Confirmed compatible, found firmware",
                        validation_test="OpenWRT wiki lists your model"
                    ),
                    ModificationStep(
                        step_number=2,
                        action="Backup original firmware",
                        rationale="May need to restore if things go wrong",
                        tools_required=["Router admin interface"],
                        components_affected=["Router"],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Firmware backup file saved",
                        validation_test="File size reasonable for flash size"
                    ),
                    ModificationStep(
                        step_number=3,
                        action="Flash OpenWRT firmware",
                        rationale="Replace stock firmware with OpenWRT",
                        tools_required=["TFTP or web interface"],
                        components_affected=["Router"],
                        reversible=True,
                        safety_warnings=[
                            "CRITICAL: Don't power off during flash!",
                            "Use wired connection, not WiFi",
                            "Verify firmware checksum first"
                        ],
                        expected_outcome="Flash completes, router reboots",
                        validation_test="Wait 5 minutes, try to ping 192.168.1.1"
                    ),
                    ModificationStep(
                        step_number=4,
                        action="Configure OpenWRT",
                        rationale="Set up for desired use case",
                        tools_required=["Web browser", "SSH client"],
                        components_affected=["Router"],
                        reversible=True,
                        safety_warnings=["Change default password immediately!"],
                        expected_outcome="Router configured and working",
                        validation_test="Can access internet through router"
                    )
                ],
                safety_checks=[
                    "Downloaded firmware matches router model exactly",
                    "Firmware checksum verified",
                    "Power supply stable (UPS recommended)",
                    "Have recovery plan (serial access)"
                ],
                reversibility="partially_reversible",
                success_criteria=[
                    "OpenWRT boots successfully",
                    "Network connectivity works",
                    "WiFi functional",
                    "Web interface accessible"
                ],
                alternative_approaches=[
                    "Use DD-WRT instead",
                    "Keep stock firmware, use only features available",
                    "Extract WiFi module for standalone use"
                ]
            )

        return self._generic_firmware_plan(device_type, desired_functionality)

    def plan_circuit_enhancement(self, device_type: str,
                                 enhancement: str,
                                 available_space: bool = True) -> ModificationPlan:
        """Plan adding new capabilities to existing circuit."""

        if "wifi" in enhancement.lower() and device_type == "arduino":
            return ModificationPlan(
                modification_name="Add WiFi to Arduino",
                modification_type=ModificationType.ENHANCEMENT,
                goal="Add WiFi connectivity using ESP8266",
                difficulty="intermediate",
                estimated_time_minutes=90,
                cost_estimate_usd=5,
                required_skills=["Arduino programming", "Serial communication", "Breadboard wiring"],
                tools_needed=["Soldering iron", "Breadboard", "Jumper wires"],
                parts_needed=[
                    "ESP8266 module (ESP-01 or NodeMCU)",
                    "3.3V voltage regulator",
                    "Logic level shifter (if using 5V Arduino)",
                    "Resistors (10kΩ for pullups)"
                ],
                steps=[
                    ModificationStep(
                        step_number=1,
                        action="Select ESP8266 module variant",
                        rationale="Different modules have different pinouts and power requirements",
                        tools_required=[],
                        components_affected=[],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Chosen ESP-01, ESP-12, or NodeMCU",
                        validation_test="Have correct module and breakout board"
                    ),
                    ModificationStep(
                        step_number=2,
                        action="Wire power supply (3.3V)",
                        rationale="ESP8266 requires 3.3V at up to 250mA",
                        tools_required=["Wire cutters", "Soldering iron"],
                        components_affected=["Arduino", "ESP8266"],
                        reversible=True,
                        safety_warnings=[
                            "NEVER connect ESP8266 to 5V!",
                            "Arduino 3.3V pin cannot supply enough current",
                            "Use separate regulator or module"
                        ],
                        expected_outcome="3.3V supply connected to ESP",
                        validation_test="Measure voltage at ESP VCC pin = 3.3V"
                    ),
                    ModificationStep(
                        step_number=3,
                        action="Wire serial communication",
                        rationale="Arduino talks to ESP via serial (TX/RX)",
                        tools_required=["Jumper wires", "Logic level shifter"],
                        components_affected=["Arduino", "ESP8266"],
                        reversible=True,
                        safety_warnings=["Must use level shifter - Arduino TX is 5V!"],
                        expected_outcome="Arduino TX → Level Shift → ESP RX, ESP TX → Arduino RX",
                        validation_test="Check continuity, verify levels with multimeter"
                    ),
                    ModificationStep(
                        step_number=4,
                        action="Add pullup resistors",
                        rationale="ESP8266 needs GPIO0 and GPIO2 pulled high to boot normally",
                        tools_required=["10kΩ resistors", "Soldering iron"],
                        components_affected=["ESP8266"],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="10kΩ from GPIO0 to 3.3V, 10kΩ from GPIO2 to 3.3V",
                        validation_test="Measure ~3.3V on GPIO pins"
                    ),
                    ModificationStep(
                        step_number=5,
                        action="Flash AT firmware to ESP",
                        rationale="Use AT commands for easy Arduino control",
                        tools_required=["USB-serial adapter", "esptool"],
                        components_affected=["ESP8266"],
                        reversible=True,
                        safety_warnings=["Don't use Arduino TX during flash - conflicts"],
                        expected_outcome="ESP responds to AT commands",
                        validation_test="Send 'AT' via serial, receive 'OK'"
                    ),
                    ModificationStep(
                        step_number=6,
                        action="Upload WiFi sketch to Arduino",
                        rationale="Arduino code to communicate with ESP",
                        tools_required=["Arduino IDE"],
                        components_affected=["Arduino"],
                        reversible=True,
                        safety_warnings=[],
                        expected_outcome="Arduino can send AT commands to ESP",
                        validation_test="Serial monitor shows WiFi connection successful"
                    )
                ],
                safety_checks=[
                    "ESP8266 voltage is 3.3V, not 5V",
                    "Current supply adequate (250mA+)",
                    "Logic levels shifted correctly",
                    "No short circuits"
                ],
                reversibility="fully_reversible",
                success_criteria=[
                    "ESP8266 boots and responds to AT commands",
                    "Arduino can connect to WiFi network",
                    "Can send/receive data over WiFi"
                ],
                alternative_approaches=[
                    "Use Arduino WiFi shield (expensive but easier)",
                    "Use ESP8266 as standalone MCU instead of Arduino",
                    "Use ESP32 for integrated solution"
                ]
            )

        return self._generic_enhancement_plan(device_type, enhancement)

    def validate_modification_safety(self, plan: ModificationPlan,
                                    components: List[str]) -> Dict[str, Any]:
        """Validate if modification is safe given available components."""

        validation = {
            "safe": True,
            "warnings": [],
            "blockers": [],
            "recommendations": []
        }

        # Check for destructive steps
        irreversible_steps = [s for s in plan.steps if not s.reversible]
        if irreversible_steps:
            validation["warnings"].append(
                f"{len(irreversible_steps)} irreversible steps - proceed with caution"
            )

        # Check voltage compatibility
        if "ESP8266" in str(plan.parts_needed) or "ESP32" in str(plan.parts_needed):
            if "5V" in str(components):
                validation["warnings"].append(
                    "CRITICAL: ESP modules require 3.3V! Level shifting required!"
                )

        # Check skill level
        if plan.difficulty == "expert":
            validation["warnings"].append(
                "Expert difficulty - consider seeking help if inexperienced"
            )

        # Check required tools
        specialized_tools = ["hot air station", "oscilloscope", "logic analyzer"]
        for tool in specialized_tools:
            if tool in str(plan.tools_needed).lower():
                validation["recommendations"].append(
                    f"Requires specialized tool: {tool}"
                )

        return validation

    def _generic_extraction_plan(self, component: str, device: str) -> ModificationPlan:
        """Generic component extraction procedure."""
        return ModificationPlan(
            modification_name=f"Extract {component}",
            modification_type=ModificationType.EXTRACTION,
            goal=f"Remove {component} for reuse",
            difficulty="intermediate",
            estimated_time_minutes=30,
            cost_estimate_usd=0,
            required_skills=["Soldering", "Desoldering"],
            tools_needed=["Soldering iron", "Desoldering tool", "Flux"],
            parts_needed=[],
            steps=[],
            safety_checks=["Power disconnected", "ESD protection"],
            reversibility="irreversible",
            success_criteria=["Component removed undamaged"],
            alternative_approaches=["Purchase new component instead"]
        )

    def _generic_firmware_plan(self, device: str, functionality: str) -> ModificationPlan:
        """Generic firmware modification procedure."""
        return ModificationPlan(
            modification_name=f"Reprogram {device}",
            modification_type=ModificationType.REPROGRAMMING,
            goal=functionality,
            difficulty="intermediate",
            estimated_time_minutes=45,
            cost_estimate_usd=0,
            required_skills=["Programming", "Flashing firmware"],
            tools_needed=["Programmer", "Computer"],
            parts_needed=[],
            steps=[],
            safety_checks=["Backup original firmware", "Verify firmware compatibility"],
            reversibility="partially_reversible",
            success_criteria=["New firmware runs successfully"],
            alternative_approaches=[]
        )

    def _generic_enhancement_plan(self, device: str, enhancement: str) -> ModificationPlan:
        """Generic circuit enhancement procedure."""
        return ModificationPlan(
            modification_name=f"Add {enhancement} to {device}",
            modification_type=ModificationType.ENHANCEMENT,
            goal=f"Enhance with {enhancement}",
            difficulty="intermediate",
            estimated_time_minutes=60,
            cost_estimate_usd=10,
            required_skills=["Circuit modification", "Testing"],
            tools_needed=["Soldering iron", "Multimeter"],
            parts_needed=["Additional components"],
            steps=[],
            safety_checks=["Voltage compatibility", "Current capacity"],
            reversibility="partially_reversible",
            success_criteria=["Enhancement functional"],
            alternative_approaches=[]
        )

    def _load_modification_library(self) -> Dict[str, Any]:
        """Load library of known modifications."""
        return {
            "arduino_wifi": "Add WiFi using ESP8266",
            "router_openwrt": "Flash OpenWRT firmware",
            "extract_esp": "Extract ESP module for standalone use"
        }


# Global instance
modification_planner = ModificationPlanner()
