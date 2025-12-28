"""
Intelligent Design Generator

Converts design intent + available resources into buildable schematics.

Flow:
1. Take parsed intent (from intent_parser)
2. Check available resources (from resource_manager)
3. Generate optimized design (schematic + wiring + BOM)
4. Output virtual design for preview
5. Prepare fabrication instructions for robot

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import logging
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class DesignStatus(Enum):
    """Design generation status."""
    FEASIBLE = "feasible"
    REQUIRES_SUBSTITUTION = "requires_substitution"
    MISSING_COMPONENTS = "missing_components"
    INFEASIBLE = "infeasible"


@dataclass
class Connection:
    """Wiring connection between components."""
    from_component: str
    from_pin: str
    to_component: str
    to_pin: str
    wire_type: str = "jumper"  # jumper, trace, solderable
    notes: str = ""


@dataclass
class ComponentPlacement:
    """Physical placement specification."""
    component: str
    position: Tuple[float, float]  # (x, y) in mm
    rotation: float = 0.0  # degrees
    layer: str = "top"  # top, bottom


@dataclass
class Design:
    """Complete design specification."""
    project_name: str
    project_type: str

    # Components
    bill_of_materials: List[Dict] = field(default_factory=list)

    # Connections
    wiring: List[Connection] = field(default_factory=list)

    # Layout
    placements: List[ComponentPlacement] = field(default_factory=list)

    # Fabrication
    pcb_size_mm: Tuple[float, float] = (100, 80)
    estimated_build_time_min: float = 0.0

    # Metadata
    status: DesignStatus = DesignStatus.FEASIBLE
    substitutions_made: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Instructions
    assembly_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "project_name": self.project_name,
            "project_type": self.project_type,
            "bill_of_materials": self.bill_of_materials,
            "wiring": [
                {
                    "from": f"{c.from_component}.{c.from_pin}",
                    "to": f"{c.to_component}.{c.to_pin}",
                    "type": c.wire_type,
                    "notes": c.notes
                }
                for c in self.wiring
            ],
            "placements": [
                {
                    "component": p.component,
                    "position": p.position,
                    "rotation": p.rotation,
                    "layer": p.layer
                }
                for p in self.placements
            ],
            "pcb_size_mm": self.pcb_size_mm,
            "estimated_build_time_min": self.estimated_build_time_min,
            "status": self.status.value,
            "substitutions_made": self.substitutions_made,
            "warnings": self.warnings,
            "assembly_steps": self.assembly_steps
        }


class DesignGenerator:
    """
    Generates buildable designs from intent and resources.

    Features:
    - Component selection and optimization
    - Wiring generation (schematic)
    - Layout optimization
    - Substitution handling
    - Fabrication instruction generation
    """

    # Standard pinouts for common components
    PINOUTS = {
        "ESP32": {
            "power": ["3V3", "GND"],
            "gpio": [f"GPIO{i}" for i in range(40)],
            "i2c": ["SDA", "SCL"],
            "special": ["EN", "BOOT"]
        },
        "Arduino Nano": {
            "power": ["5V", "3V3", "GND"],
            "gpio": [f"D{i}" for i in range(14)] + [f"A{i}" for i in range(8)],
            "i2c": ["A4", "A5"],
            "spi": ["D11", "D12", "D13"]
        },
        "DHT22": {
            "pins": ["VCC", "DATA", "NC", "GND"]
        },
        "DHT11": {
            "pins": ["VCC", "DATA", "NC", "GND"]
        },
        "LED": {
            "pins": ["ANODE", "CATHODE"]
        },
        "BME280": {
            "power": ["VCC", "GND"],
            "i2c": ["SDA", "SCL"]
        }
    }

    # Design templates for common projects
    DESIGN_TEMPLATES = {
        "wifi_temperature_sensor": {
            "required": ["microcontroller_wifi", "temperature_sensor"],
            "connections": [
                ("microcontroller_wifi", "3V3", "temperature_sensor", "VCC"),
                ("microcontroller_wifi", "GND", "temperature_sensor", "GND"),
                ("microcontroller_wifi", "GPIO4", "temperature_sensor", "DATA"),
            ],
            "code_template": "wifi_sensor.ino"
        },
        "led_blinker": {
            "required": ["microcontroller", "led", "resistor_330"],
            "connections": [
                ("microcontroller", "GPIO2", "resistor_330", "IN"),
                ("resistor_330", "OUT", "led", "ANODE"),
                ("led", "CATHODE", "microcontroller", "GND"),
            ],
            "code_template": "blink.ino"
        },
        "motor_controller": {
            "required": ["microcontroller", "motor_driver", "motor"],
            "connections": [
                ("microcontroller", "5V", "motor_driver", "VCC"),
                ("microcontroller", "GND", "motor_driver", "GND"),
                ("microcontroller", "GPIO5", "motor_driver", "IN1"),
                ("microcontroller", "GPIO6", "motor_driver", "IN2"),
                ("motor_driver", "OUT1", "motor", "TERMINAL1"),
                ("motor_driver", "OUT2", "motor", "TERMINAL2"),
            ],
            "code_template": "motor_control.ino"
        },
        # NEW: Robot Arm (4-DOF)
        "robot_arm_4dof": {
            "required": ["microcontroller", "servo_driver", "servo", "servo", "servo", "servo", "3d_printed_parts"],
            "connections": [
                # Power connections
                ("power_supply", "5V", "servo_driver", "VCC"),
                ("power_supply", "GND", "servo_driver", "GND"),
                ("microcontroller", "5V", "servo_driver", "VDD"),  # Logic power
                # I2C connection (Arduino to PCA9685)
                ("microcontroller", "SDA", "servo_driver", "SDA"),
                ("microcontroller", "SCL", "servo_driver", "SCL"),
                # Servo connections (servo driver channels 0-3)
                ("servo_driver", "CH0", "servo", "PWM"),  # Base rotation
                ("servo_driver", "CH1", "servo", "PWM"),  # Shoulder
                ("servo_driver", "CH2", "servo", "PWM"),  # Elbow
                ("servo_driver", "CH3", "servo", "PWM"),  # Gripper
                # Mechanical linkages (represented as connections)
                ("3d_printed_parts", "BASE", "servo", "SHAFT"),  # Base servo
                ("3d_printed_parts", "SHOULDER", "servo", "SHAFT"),  # Shoulder servo
                ("3d_printed_parts", "ELBOW", "servo", "SHAFT"),  # Elbow servo
                ("3d_printed_parts", "GRIPPER", "servo", "SHAFT"),  # Gripper servo
            ],
            "code_template": "robot_arm.ino"
        },
        # NEW: Hydro Generator (Rain/Storm)
        "hydro_generator": {
            "required": ["turbine", "dc_motor_as_generator", "rectifier", "voltage_regulator", "battery", "led", "resistors"],
            "connections": [
                # Mechanical: water flow → turbine → motor shaft
                ("turbine", "SHAFT", "dc_motor_as_generator", "SHAFT"),
                # Electrical: motor generates AC, rectify to DC
                ("dc_motor_as_generator", "OUT+", "rectifier", "AC1"),
                ("dc_motor_as_generator", "OUT-", "rectifier", "AC2"),
                # Rectified DC → voltage regulator
                ("rectifier", "DC+", "voltage_regulator", "VIN"),
                ("rectifier", "DC-", "voltage_regulator", "GND"),
                # Regulated output → battery + LED indicator
                ("voltage_regulator", "VOUT", "battery", "+"),
                ("voltage_regulator", "GND", "battery", "-"),
                ("voltage_regulator", "VOUT", "resistors", "IN"),
                ("resistors", "OUT", "led", "ANODE"),
                ("led", "CATHODE", "voltage_regulator", "GND"),
            ],
            "code_template": None  # No code needed, pure hardware
        }
    }

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize design generator.

        Args:
            output_dir: Output directory for generated designs
        """
        self.output_dir = output_dir or Path("generated_designs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("DesignGenerator initialized")

    def generate_design(
        self,
        intent: 'DesignIntent',
        resource_manager: 'ResourceManager'
    ) -> Design:
        """
        Generate complete design from intent and available resources.

        Args:
            intent: Parsed design intent
            resource_manager: Resource manager with inventory

        Returns:
            Complete design specification
        """
        logger.info(f"Generating design for: {intent.raw_request}")

        # Create design object
        design = Design(
            project_name=intent.raw_request[:50],  # Truncate
            project_type=intent.project_type.value
        )

        # Step 1: Check resource availability
        availability = resource_manager.check_availability(intent.required_components)

        if not availability["feasible"]:
            design.status = DesignStatus.MISSING_COMPONENTS
            design.warnings.append(f"Missing components: {availability['missing']}")
            logger.warning(f"Design not feasible - missing: {availability['missing']}")
            # Continue generating design to show what WOULD be built
            # This gives users a complete BOM/wiring diagram even without components

        # Step 2: Build BOM (generate theoretical design if components missing)
        self._build_bom(design, intent, resource_manager, availability)

        # Step 3: Generate wiring connections
        self._generate_wiring(design, intent)

        # Step 4: Optimize component placement
        self._optimize_placement(design)

        # Step 5: Generate assembly instructions
        self._generate_assembly_steps(design)

        # Step 6: Estimate build time
        design.estimated_build_time_min = self._estimate_build_time(design)

        # Save design
        design_path = self.output_dir / f"{design.project_name.replace(' ', '_')}.json"
        with open(design_path, 'w') as f:
            json.dump(design.to_dict(), f, indent=2)

        logger.info(f"Design generated: {design_path}")
        logger.info(f"  Status: {design.status.value}")
        logger.info(f"  Components: {len(design.bill_of_materials)}")
        logger.info(f"  Connections: {len(design.wiring)}")
        logger.info(f"  Build time: {design.estimated_build_time_min:.1f} min")

        return design

    def _build_bom(
        self,
        design: Design,
        intent: 'DesignIntent',
        resource_manager: 'ResourceManager',
        availability: Dict
    ):
        """Build bill of materials with substitutions."""

        # Optimize for available resources
        optimized = resource_manager.optimize_for_available_resources(
            {"required_components": intent.required_components},
            prefer_scraps=True
        )

        # Track which components were allocated
        allocated_components = set()

        # Add allocated components to BOM
        for comp_alloc in optimized["components"]:
            design.bill_of_materials.append({
                "component": comp_alloc["component"],
                "quantity": 1,
                "condition": comp_alloc["condition"],
                "cost_usd": comp_alloc["cost"],
                "is_substitute": comp_alloc.get("is_substitute", False)
            })
            allocated_components.add(comp_alloc["component"])

        # Add missing components as "required purchase" with estimated prices
        for comp_name in intent.required_components:
            if comp_name not in allocated_components:
                # Estimate price for missing component
                estimated_price = self._estimate_component_price(comp_name)
                design.bill_of_materials.append({
                    "component": comp_name,
                    "quantity": 1,
                    "condition": "required_purchase",
                    "cost_usd": estimated_price,
                    "is_substitute": False
                })

        # Record substitutions
        design.substitutions_made = optimized.get("substitutions", [])

        if design.substitutions_made:
            design.status = DesignStatus.REQUIRES_SUBSTITUTION
            logger.info(f"Made {len(design.substitutions_made)} substitutions")

    def _generate_wiring(self, design: Design, intent: 'DesignIntent'):
        """Generate wiring connections based on project type."""

        # Determine template based on features
        template_name = self._select_template(intent)

        if template_name and template_name in self.DESIGN_TEMPLATES:
            template = self.DESIGN_TEMPLATES[template_name]

            # Map template components to actual BOM components
            component_map = self._map_components_to_bom(template["required"], design.bill_of_materials)

            # Generate connections from template
            for conn_spec in template["connections"]:
                from_comp_type, from_pin, to_comp_type, to_pin = conn_spec

                from_comp = component_map.get(from_comp_type)
                to_comp = component_map.get(to_comp_type)

                if from_comp and to_comp:
                    connection = Connection(
                        from_component=from_comp,
                        from_pin=from_pin,
                        to_component=to_comp,
                        to_pin=to_pin,
                        wire_type="jumper"
                    )
                    design.wiring.append(connection)

        else:
            # Generic wiring for unknown project types
            logger.warning(f"No template for {intent.project_type.value}, using generic wiring")
            self._generate_generic_wiring(design)

    def _select_template(self, intent: 'DesignIntent') -> Optional[str]:
        """Select appropriate design template."""

        # NEW: Robot Arm
        if intent.project_type.value == "mechanical":
            return "robot_arm_4dof"

        # NEW: Hydro Generator
        if intent.project_type.value == "power_generation":
            if "hydro" in intent.features:
                return "hydro_generator"
            # TODO: Add solar_panel, wind_turbine templates later
            return "hydro_generator"  # Default to hydro for now

        # WiFi + Temperature = wifi_temperature_sensor
        if "wifi" in intent.features and "temperature" in intent.features:
            return "wifi_temperature_sensor"

        # LED = led_blinker
        if "led" in intent.features and "motor" not in intent.features:
            return "led_blinker"

        # Motor = motor_controller
        if "motor" in intent.features:
            return "motor_controller"

        return None

    def _map_components_to_bom(self, required: List[str], bom: List[Dict]) -> Dict[str, str]:
        """Map template component types to actual BOM component names."""
        mapping = {}

        for req in required:
            for bom_item in bom:
                comp_name = bom_item["component"]

                # Fuzzy matching with expanded patterns
                if req == "microcontroller_wifi":
                    if any(x in comp_name for x in ["ESP32", "ESP8266", "wifi_module", "ESP"]):
                        mapping[req] = comp_name
                        break

                elif req == "microcontroller":
                    if any(x in comp_name for x in ["Arduino", "ATmega", "microcontroller"]):
                        mapping[req] = comp_name
                        break

                elif req == "temperature_sensor":
                    if any(x in comp_name for x in ["DHT", "BME280", "DS18B20", "temperature_sensor", "temp"]):
                        mapping[req] = comp_name
                        break

                elif req.lower() in comp_name.lower() or comp_name.lower() in req.lower():
                    mapping[req] = comp_name
                    break

        return mapping

    def _estimate_component_price(self, component_name: str) -> float:
        """Estimate price for a component (fallback pricing)."""
        # Market average estimates (USD)
        price_estimates = {
            # Electronics
            "esp32": 8.00,
            "esp8266": 4.00,
            "arduino": 5.00,
            "arduino nano": 3.50,
            "microcontroller": 5.00,
            "dht22": 3.50,
            "dht11": 1.50,
            "temperature_sensor": 3.00,
            "wifi_module": 6.00,
            "motor_driver": 4.00,
            "motor": 8.00,
            "led": 0.10,
            "resistor": 0.05,
            "resistors": 0.20,
            "capacitor": 0.10,
            "capacitors": 0.30,
            "wire": 0.10,
            "wires": 0.50,
            "pcb": 2.00,
            "power_supply": 5.00,
            "battery": 3.00,
            "sensor": 5.00,
            "display": 8.00,
            "lcd": 10.00,
            "oled": 12.00,
            # Mechanical (NEW)
            "servo": 6.00,
            "mg996r": 8.00,
            "mg90s": 4.00,
            "sg90": 2.50,
            "servo_driver": 4.00,
            "pca9685": 4.00,
            "3d_printed_parts": 5.00,
            "3d print": 5.00,
            # Power Generation (NEW)
            "turbine": 0.00,  # DIY from bottles
            "water wheel": 0.00,
            "dc_motor_as_generator": 0.00,  # Scrap motor
            "rectifier": 0.20,  # 4× diodes
            "1n4007": 0.05,
            "voltage_regulator": 0.30,
            "7805": 0.30,
            "lm317": 0.40,
            "buck converter": 1.50,
            "solar_panel": 15.00,
            "wind_turbine": 20.00,
        }

        # Try exact match first
        comp_lower = component_name.lower()
        if comp_lower in price_estimates:
            return price_estimates[comp_lower]

        # Try partial match
        for key, price in price_estimates.items():
            if key in comp_lower or comp_lower in key:
                return price

        # Default estimate for unknown components
        return 5.00

    def _generate_generic_wiring(self, design: Design):
        """Generate generic wiring for unknown project types."""

        # Find microcontroller
        mcu = None
        for item in design.bill_of_materials:
            if any(mc in item["component"] for mc in ["ESP32", "Arduino", "ATmega"]):
                mcu = item["component"]
                break

        if not mcu:
            design.warnings.append("No microcontroller found - cannot generate wiring")
            return

        # Connect all sensors/actuators to MCU
        gpio_pin = 2

        for item in design.bill_of_materials:
            comp = item["component"]

            if comp == mcu:
                continue

            # Power connections
            design.wiring.append(Connection(
                from_component=mcu,
                from_pin="3V3",
                to_component=comp,
                to_pin="VCC",
                notes="Power supply"
            ))

            design.wiring.append(Connection(
                from_component=mcu,
                from_pin="GND",
                to_component=comp,
                to_pin="GND",
                notes="Ground"
            ))

            # Data connection
            design.wiring.append(Connection(
                from_component=mcu,
                from_pin=f"GPIO{gpio_pin}",
                to_component=comp,
                to_pin="DATA",
                notes="Signal/data line"
            ))

            gpio_pin += 1

    def _optimize_placement(self, design: Design):
        """Optimize component placement on PCB."""

        # Simple grid placement
        x_offset = 10  # mm from edge
        y_offset = 10
        spacing = 20  # mm between components

        x, y = x_offset, y_offset
        max_width = design.pcb_size_mm[0] - 20

        for item in design.bill_of_materials:
            placement = ComponentPlacement(
                component=item["component"],
                position=(x, y),
                rotation=0.0,
                layer="top"
            )
            design.placements.append(placement)

            # Move to next position
            x += spacing
            if x > max_width:
                x = x_offset
                y += spacing

    def _generate_assembly_steps(self, design: Design):
        """Generate step-by-step assembly instructions."""

        design.assembly_steps = [
            "1. Prepare PCB and components",
            "2. Place components according to layout"
        ]

        # Add placement steps
        for i, placement in enumerate(design.placements, 3):
            design.assembly_steps.append(
                f"{i}. Place {placement.component} at ({placement.position[0]:.1f}, {placement.position[1]:.1f})mm"
            )

        # Add wiring steps
        step_num = len(design.assembly_steps) + 1
        for conn in design.wiring:
            design.assembly_steps.append(
                f"{step_num}. Connect {conn.from_component}.{conn.from_pin} → "
                f"{conn.to_component}.{conn.to_pin} ({conn.notes})"
            )
            step_num += 1

        design.assembly_steps.append(f"{step_num}. Test circuit before powering on")
        design.assembly_steps.append(f"{step_num + 1}. Upload firmware and test")

    def _estimate_build_time(self, design: Design) -> float:
        """Estimate build time in minutes."""

        # Base time
        time_min = 10.0

        # Component placement: 2 min per component
        time_min += len(design.bill_of_materials) * 2.0

        # Wiring: 1.5 min per connection
        time_min += len(design.wiring) * 1.5

        # Testing and programming: 10 min
        time_min += 10.0

        return time_min

    def generate_schematic_ascii(self, design: Design) -> str:
        """Generate ASCII art schematic for preview."""

        lines = []

        lines.append("=" * 70)
        lines.append(f"SCHEMATIC: {design.project_name}")
        lines.append("=" * 70)
        lines.append("")

        # Components
        lines.append("COMPONENTS:")
        for item in design.bill_of_materials:
            condition_marker = "♻" if item["condition"] == "scrap" else "●"
            lines.append(f"  {condition_marker} {item['component']}")
        lines.append("")

        # Connections
        lines.append("WIRING:")
        for conn in design.wiring:
            lines.append(f"  {conn.from_component}.{conn.from_pin} ──> {conn.to_component}.{conn.to_pin}")
            if conn.notes:
                lines.append(f"      ({conn.notes})")
        lines.append("")

        # Substitutions
        if design.substitutions_made:
            lines.append("SUBSTITUTIONS:")
            for sub in design.substitutions_made:
                lines.append(f"  {sub['original']} → {sub['substitute']}")
            lines.append("")

        # Warnings
        if design.warnings:
            lines.append("⚠ WARNINGS:")
            for warning in design.warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Test design generator
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    from intent_parser import IntentParser, DesignIntent
    from resource_manager import ResourceManager, Component, ComponentCondition

    # Setup
    generator = DesignGenerator()
    parser = IntentParser()
    resource_mgr = ResourceManager()

    # Add some components to inventory
    resource_mgr.add_component(Component(
        name="ESP32",
        component_type="microcontroller",
        quantity=1,
        condition=ComponentCondition.NEW,
        cost_usd=8.00
    ))

    resource_mgr.add_component(Component(
        name="DHT22",
        component_type="sensor",
        quantity=1,
        condition=ComponentCondition.SCRAP,
        source="scavenged"
    ))

    # Test design generation
    request = "build me a WiFi temperature sensor"
    intent = parser.parse(request)

    print(f"\nRequest: \"{request}\"")
    print(f"Intent: {intent.project_type.value}, features: {intent.features}\n")

    design = generator.generate_design(intent, resource_mgr)

    print(generator.generate_schematic_ascii(design))
    print(f"\nEstimated build time: {design.estimated_build_time_min:.1f} minutes")
