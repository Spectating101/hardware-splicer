"""
Natural Language Intent Parser

Converts user requests like "build me a temperature sensor" into
structured design specifications.

Examples:
- "build me a WiFi temperature sensor" → {type: "sensor", features: ["wifi", "temperature"]}
- "make an LED blinker" → {type: "actuator", features: ["led", "blink"]}
- "I need a motor controller" → {type: "controller", features: ["motor"]}

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ProjectType(Enum):
    """Types of projects Dum-E can build."""
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    CONTROLLER = "controller"
    DISPLAY = "display"
    COMMUNICATION = "communication"
    POWER_SUPPLY = "power_supply"
    MECHANICAL = "mechanical"  # NEW: Robot arms, mechanisms
    POWER_GENERATION = "power_generation"  # NEW: Hydro, solar, wind
    CUSTOM = "custom"


@dataclass
class DesignIntent:
    """Parsed design intent from user request."""
    project_type: ProjectType
    features: List[str] = field(default_factory=list)
    constraints: Dict[str, any] = field(default_factory=dict)

    # Derived specifications
    required_components: List[str] = field(default_factory=list)
    optional_components: List[str] = field(default_factory=list)

    # Metadata
    raw_request: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "project_type": self.project_type.value,
            "features": self.features,
            "constraints": self.constraints,
            "required_components": self.required_components,
            "optional_components": self.optional_components,
            "raw_request": self.raw_request,
            "confidence": self.confidence
        }


class IntentParser:
    """
    Parse natural language into design specifications.

    Uses pattern matching and keyword extraction.
    Can be upgraded to use LLM for better understanding.
    """

    # Keyword mappings
    PROJECT_KEYWORDS = {
        ProjectType.SENSOR: ["sensor", "measure", "detect", "monitor", "read", "sense"],
        ProjectType.ACTUATOR: ["actuator", "motor", "servo", "led", "relay", "switch", "control"],
        ProjectType.CONTROLLER: ["controller", "control", "manage", "regulate"],
        ProjectType.DISPLAY: ["display", "screen", "show", "oled", "lcd", "monitor"],
        ProjectType.COMMUNICATION: ["wifi", "bluetooth", "radio", "rf", "wireless", "network"],
        ProjectType.POWER_SUPPLY: ["power supply", "battery", "voltage", "regulator", "charger"],
        ProjectType.MECHANICAL: ["robot", "arm", "gripper", "mechanism", "linkage", "actuator", "kinematics"],
        ProjectType.POWER_GENERATION: ["generator", "hydro", "solar", "wind", "turbine", "renewable", "energy harvesting"],
    }

    FEATURE_KEYWORDS = {
        # Sensors
        "temperature": ["temperature", "temp", "thermal", "heat"],
        "humidity": ["humidity", "moisture"],
        "pressure": ["pressure", "barometric"],
        "light": ["light", "brightness", "lux", "ambient"],
        "motion": ["motion", "movement", "pir", "accelerometer"],
        "distance": ["distance", "ultrasonic", "ranging"],
        # Communication
        "wifi": ["wifi", "wireless", "internet"],
        "bluetooth": ["bluetooth", "ble", "bt"],
        # Actuators
        "led": ["led", "light emitting"],
        "motor": ["motor", "stepper", "dc motor"],
        "servo": ["servo"],
        "relay": ["relay"],
        "buzzer": ["buzzer", "beep", "alarm"],
        # Mechanical (NEW)
        "gripper": ["gripper", "claw", "grip", "grasp"],
        "degrees_of_freedom": ["dof", "axis", "axes", "4dof", "6dof"],
        "pick_and_place": ["pick and place", "assembly", "manipulation"],
        # Power Generation (NEW)
        "hydro": ["hydro", "water", "rain", "storm", "flow"],
        "solar": ["solar", "photovoltaic", "pv", "sun"],
        "wind": ["wind", "turbine blade"],
        "rectifier": ["rectifier", "ac to dc", "diode bridge"],
        "voltage_regulation": ["voltage regulation", "buck", "boost", "regulator"],
    }

    # Component templates
    COMPONENT_TEMPLATES = {
        # Electronics
        "temperature_sensor": {
            "options": ["DHT22", "DHT11", "DS18B20", "BME280"],
            "microcontroller_needed": True
        },
        "humidity_sensor": {
            "options": ["DHT22", "DHT11", "BME280"],
            "microcontroller_needed": True
        },
        "wifi_module": {
            "options": ["ESP32", "ESP8266", "Arduino WiFi"],
            "microcontroller_needed": False  # ESP32 has built-in MCU
        },
        "microcontroller": {
            "options": ["ESP32", "Arduino Nano", "Arduino Uno", "ATmega328"],
            "microcontroller_needed": False
        },
        "led": {
            "options": ["LED", "RGB LED", "WS2812"],
            "microcontroller_needed": True
        },
        "motor": {
            "options": ["DC Motor", "Stepper Motor", "Servo Motor"],
            "microcontroller_needed": True,
            "driver_needed": True
        },
        "display": {
            "options": ["OLED 0.96", "LCD 16x2", "LCD 20x4", "TFT"],
            "microcontroller_needed": True
        },
        # Mechanical (NEW)
        "servo": {
            "options": ["MG996R", "MG90S", "SG90", "Servo Motor"],
            "microcontroller_needed": True,
            "driver_needed": True  # PCA9685 servo driver
        },
        "servo_driver": {
            "options": ["PCA9685", "Servo Driver Board"],
            "microcontroller_needed": False
        },
        "3d_printed_parts": {
            "options": ["Custom 3D Print", "Mechanical Linkage", "Bracket"],
            "microcontroller_needed": False
        },
        # Power Generation (NEW)
        "dc_motor_as_generator": {
            "options": ["DC Motor (as generator)", "Toy Motor", "Hobby Motor"],
            "microcontroller_needed": False
        },
        "turbine": {
            "options": ["Water Wheel", "DIY Turbine", "Micro Hydro Turbine"],
            "microcontroller_needed": False
        },
        "rectifier": {
            "options": ["1N4007 Diode Bridge", "Bridge Rectifier Module"],
            "microcontroller_needed": False
        },
        "voltage_regulator": {
            "options": ["7805", "LM317", "Buck Converter", "Boost Converter"],
            "microcontroller_needed": False
        },
    }

    def __init__(self):
        """Initialize intent parser."""
        logger.info("IntentParser initialized")

    def parse(self, user_request: str) -> DesignIntent:
        """
        Parse user request into design intent.

        Args:
            user_request: Natural language request

        Returns:
            DesignIntent with specifications
        """
        request_lower = user_request.lower()

        # 1. Determine project type
        project_type = self._detect_project_type(request_lower)

        # 2. Extract features
        features = self._extract_features(request_lower)

        # 3. Extract constraints
        constraints = self._extract_constraints(request_lower)

        # 4. Determine required components
        required_components = self._determine_components(project_type, features)

        # 5. Calculate confidence
        confidence = self._calculate_confidence(project_type, features)

        intent = DesignIntent(
            project_type=project_type,
            features=features,
            constraints=constraints,
            required_components=required_components,
            raw_request=user_request,
            confidence=confidence
        )

        logger.info(f"Parsed intent: {project_type.value}, features: {features}, confidence: {confidence:.2f}")

        return intent

    def _detect_project_type(self, text: str) -> ProjectType:
        """Detect project type from keywords."""
        scores = {}

        for ptype, keywords in self.PROJECT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[ptype] = score

        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        else:
            return ProjectType.CUSTOM

    def _extract_features(self, text: str) -> List[str]:
        """Extract features from text."""
        features = []

        for feature, keywords in self.FEATURE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                features.append(feature)

        return features

    def _extract_constraints(self, text: str) -> Dict:
        """Extract constraints (budget, size, power, etc.)."""
        constraints = {}

        # Size constraints
        size_match = re.search(r'(\d+)\s*(mm|cm|inch)', text)
        if size_match:
            constraints["max_size_mm"] = float(size_match.group(1))
            if size_match.group(2) == "cm":
                constraints["max_size_mm"] *= 10
            elif size_match.group(2) == "inch":
                constraints["max_size_mm"] *= 25.4

        # Power constraints
        if "battery" in text or "portable" in text:
            constraints["battery_powered"] = True

        if "low power" in text:
            constraints["low_power"] = True

        # Budget
        budget_match = re.search(r'\$(\d+)', text)
        if budget_match:
            constraints["max_budget_usd"] = float(budget_match.group(1))

        return constraints

    def _determine_components(self, project_type: ProjectType, features: List[str]) -> List[str]:
        """Determine required components based on intent."""
        components = []

        # Always need microcontroller for most projects
        needs_mcu = True

        # Feature-specific components
        if "temperature" in features:
            components.append("temperature_sensor")

        if "humidity" in features:
            components.append("humidity_sensor")

        if "wifi" in features or "bluetooth" in features:
            components.append("wifi_module")
            # ESP32 has built-in MCU
            needs_mcu = False

        if "led" in features:
            components.append("led")

        if "motor" in features:
            components.append("motor")
            components.append("motor_driver")

        if project_type == ProjectType.DISPLAY:
            components.append("display")

        # NEW: Mechanical projects
        if project_type == ProjectType.MECHANICAL:
            # Robot arm components
            components.extend(["servo", "servo", "servo", "servo"])  # 4 servos for 4-DOF
            components.append("servo_driver")  # PCA9685
            components.append("3d_printed_parts")  # Mechanical structure
            components.append("microcontroller")  # Arduino for control
            needs_mcu = False  # Already added

        # NEW: Power generation projects
        if project_type == ProjectType.POWER_GENERATION:
            if "hydro" in features:
                components.append("turbine")  # Water wheel
                components.append("dc_motor_as_generator")  # Motor used as generator
                components.append("rectifier")  # Diode bridge
                components.append("voltage_regulator")  # 7805 or buck converter
                components.append("battery")  # Energy storage
                components.append("led")  # Power indicator
                needs_mcu = False  # Simple power circuit, no MCU needed
            elif "solar" in features:
                components.append("solar_panel")
                components.append("charge_controller")
                components.append("battery")
                needs_mcu = False
            elif "wind" in features:
                components.append("wind_turbine")
                components.append("dc_motor_as_generator")
                components.append("rectifier")
                components.append("voltage_regulator")
                components.append("battery")
                needs_mcu = False

        # Add microcontroller if needed
        if needs_mcu and "wifi_module" not in components:
            components.append("microcontroller")

        # Power supply (not needed for power generation projects!)
        if project_type != ProjectType.POWER_GENERATION:
            components.append("power_supply")

        # Add basic components (wires always needed, PCB only for electronics)
        components.append("wires")
        if project_type not in [ProjectType.MECHANICAL, ProjectType.POWER_GENERATION]:
            components.extend(["resistors", "capacitors", "pcb"])
        else:
            # Minimal electronics for mechanical/power projects
            components.append("resistors")

        return components

    def _calculate_confidence(self, project_type: ProjectType, features: List[str]) -> float:
        """Calculate parsing confidence."""
        confidence = 0.5  # Base confidence

        # Higher confidence if we detected a specific type
        if project_type != ProjectType.CUSTOM:
            confidence += 0.3

        # Higher confidence if we found features
        if features:
            confidence += min(len(features) * 0.1, 0.2)

        return min(confidence, 1.0)

    def suggest_alternatives(self, intent: DesignIntent) -> List[str]:
        """Suggest alternative interpretations if confidence is low."""
        if intent.confidence > 0.7:
            return []

        suggestions = []

        suggestions.append("Did you mean:")

        # Suggest similar project types
        if intent.project_type == ProjectType.CUSTOM:
            suggestions.append("  - A sensor project (temperature, humidity, etc.)?")
            suggestions.append("  - An actuator project (LED, motor, relay)?")
            suggestions.append("  - A controller project (automation, regulation)?")

        return suggestions


if __name__ == "__main__":
    # Test intent parser
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = IntentParser()

    test_requests = [
        "build me a WiFi temperature sensor",
        "I need an LED blinker",
        "make a motor controller with WiFi",
        "create a battery-powered humidity monitor",
        "build a smart doorbell with camera"
    ]

    print("=" * 70)
    print("INTENT PARSER TESTS")
    print("=" * 70)
    print()

    for request in test_requests:
        print(f"Request: \"{request}\"")
        intent = parser.parse(request)
        print(f"  Type: {intent.project_type.value}")
        print(f"  Features: {intent.features}")
        print(f"  Components: {intent.required_components}")
        print(f"  Confidence: {intent.confidence:.2f}")
        print()
