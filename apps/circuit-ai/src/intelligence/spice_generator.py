"""
SPICE Circuit Simulator Generator

Generates SPICE netlists from detected circuits for simulation.
Enables "what-if" analysis before making modifications.

Example use case:
- User wants to change power supply from 5V to 3.3V
- Generate SPICE netlist from detected circuit
- Simulate with 3.3V
- Warn if any components will be damaged or circuit won't work
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from intelligence.connection_mapper import CircuitSchematic, PinConnection
from intelligence.pinout_database import pinout_database, PinType


@dataclass
class SpiceComponent:
    """A component in SPICE format."""
    name: str  # R1, C2, IC3, etc.
    type: str  # "resistor", "capacitor", "ic", "voltage_source", etc.
    nodes: List[str]  # Connected net names
    value: Optional[str] = None  # "10k", "100nF", etc.
    model: Optional[str] = None  # For ICs, transistors


@dataclass
class SpiceNetlist:
    """Complete SPICE netlist."""
    title: str
    components: List[SpiceComponent]
    models: Dict[str, str] = field(default_factory=dict)  # Model definitions
    analysis: List[str] = field(default_factory=list)  # .DC, .AC, .TRAN commands
    error_message: Optional[str] = None


class SpiceGenerator:
    """Generate SPICE netlists from detected circuits."""

    def __init__(self):
        """Initialize generator."""
        self.component_counter = {}  # Track component IDs

    def generate_netlist(self, schematic: CircuitSchematic,
                        component_values: Optional[Dict[str, float]] = None) -> SpiceNetlist:
        """
        Generate SPICE netlist from circuit schematic.

        Args:
            schematic: Circuit schematic from connection_mapper
            component_values: Optional dict mapping component names to values
                             e.g., {"R1": 10000, "C1": 100e-9}

        Returns:
            SpiceNetlist ready for simulation
        """
        netlist = SpiceNetlist(
            title="Circuit-AI Generated Netlist",
            components=[]
        )

        # Add power supplies
        for rail_name, voltage in schematic.power_rails.items():
            # Create voltage source
            netlist.components.append(SpiceComponent(
                name=f"V{len(netlist.components) + 1}",
                type="voltage_source",
                nodes=[rail_name, "0"],  # Connect to ground
                value=f"{voltage}V"
            ))

        # Add ICs
        for ic in schematic.ics:
            part_number = ic.part_number

            # Get pinout
            pinout = pinout_database.get_pinout(part_number)
            if not pinout:
                continue

            # Find connections for each pin
            pin_connections = {}
            for conn in schematic.connections:
                if conn.from_ic == ic:
                    pin_connections[conn.from_pin] = conn.net_name
                if conn.to_ic == ic:
                    pin_connections[conn.to_pin] = conn.net_name

            # Generate component based on IC type
            if "LM78" in part_number or "AMS1117" in part_number:
                # Voltage regulator - can model as subcircuit
                netlist.components.append(self._generate_voltage_regulator(
                    ic, pin_connections, pinout
                ))

            elif "ATMEGA" in part_number or "ESP" in part_number:
                # Microcontroller - model as load + pullups
                netlist.components.append(self._generate_mcu_model(
                    ic, pin_connections, pinout
                ))

            else:
                # Generic IC - just note it in comments
                pass

        # Add passive components from connections
        # Look for resistors and capacitors in trace analysis
        for i, conn in enumerate(schematic.connections):
            # If connection has a component in between, add it
            # This would need component detection data
            pass

        # Add analysis commands
        netlist.analysis.append(".op")  # Operating point analysis
        netlist.analysis.append(".dc V1 0 5 0.1")  # DC sweep
        netlist.analysis.append(".print dc v(VCC) i(V1)")

        return netlist

    def _generate_voltage_regulator(self, ic, pin_connections: Dict[int, str],
                                   pinout) -> SpiceComponent:
        """
        Generate SPICE model for voltage regulator.

        LM7805: 3 pins - IN, GND, OUT
        AMS1117: 3 pins - GND, OUT, IN
        """
        part = ic.part_number

        if "LM78" in part:
            # LM78xx series
            # Pin 1: IN, Pin 2: GND, Pin 3: OUT
            vin_net = pin_connections.get(1, "VIN")
            gnd_net = pin_connections.get(2, "0")
            vout_net = pin_connections.get(3, "VOUT")

            # Extract voltage from part number (e.g., LM7805 -> 5V)
            voltage_match = re.search(r'78(\d{2})', part)
            if voltage_match:
                output_voltage = int(voltage_match.group(1))
            else:
                output_voltage = 5  # Default

            return SpiceComponent(
                name=f"X{self._get_component_id('X')}",
                type="voltage_regulator",
                nodes=[vin_net, gnd_net, vout_net],
                value=f"{output_voltage}V",
                model=f"LM78{output_voltage:02d}"
            )

        elif "AMS1117" in part:
            # AMS1117: Pin 1: GND, Pin 2: VOUT, Pin 3: VIN
            gnd_net = pin_connections.get(1, "0")
            vout_net = pin_connections.get(2, "VOUT")
            vin_net = pin_connections.get(3, "VIN")

            return SpiceComponent(
                name=f"X{self._get_component_id('X')}",
                type="voltage_regulator",
                nodes=[vin_net, gnd_net, vout_net],
                value="3.3V",  # AMS1117 usually 3.3V
                model="AMS1117"
            )

        return None

    def _generate_mcu_model(self, ic, pin_connections: Dict[int, str],
                          pinout) -> SpiceComponent:
        """
        Generate SPICE model for microcontroller.

        Model as:
        - Power pins with decoupling caps
        - I/O pins as loads
        """
        # Find VCC and GND pins
        vcc_nets = []
        gnd_nets = []

        for pin_def in pinout.pins:
            if pin_def.pin_type == PinType.POWER:
                net = pin_connections.get(pin_def.pin_number)
                if net:
                    vcc_nets.append(net)
            elif pin_def.pin_type == PinType.GROUND:
                net = pin_connections.get(pin_def.pin_number)
                if net:
                    gnd_nets.append(net)

        vcc_net = vcc_nets[0] if vcc_nets else "VCC"
        gnd_net = gnd_nets[0] if gnd_nets else "0"

        # Model MCU as current sink
        return SpiceComponent(
            name=f"I{self._get_component_id('I')}",
            type="current_source",
            nodes=[vcc_net, gnd_net],
            value="50mA"  # Typical MCU current
        )

    def _get_component_id(self, prefix: str) -> int:
        """Get next component ID for prefix."""
        if prefix not in self.component_counter:
            self.component_counter[prefix] = 1
        else:
            self.component_counter[prefix] += 1
        return self.component_counter[prefix]

    def to_spice_text(self, netlist: SpiceNetlist) -> str:
        """
        Convert netlist to SPICE text format.

        Returns:
            SPICE netlist as string
        """
        lines = []

        # Title
        lines.append(netlist.title)
        lines.append("")

        # Components
        for comp in netlist.components:
            if comp.type == "voltage_source":
                # Vname node+ node- DC value
                lines.append(f"{comp.name} {comp.nodes[0]} {comp.nodes[1]} DC {comp.value}")

            elif comp.type == "resistor":
                # Rname node1 node2 value
                lines.append(f"{comp.name} {comp.nodes[0]} {comp.nodes[1]} {comp.value}")

            elif comp.type == "capacitor":
                # Cname node1 node2 value
                lines.append(f"{comp.name} {comp.nodes[0]} {comp.nodes[1]} {comp.value}")

            elif comp.type == "voltage_regulator":
                # Subcircuit call
                lines.append(f"{comp.name} {' '.join(comp.nodes)} {comp.model}")

            elif comp.type == "current_source":
                # Iname node+ node- DC value
                lines.append(f"{comp.name} {comp.nodes[0]} {comp.nodes[1]} DC {comp.value}")

        lines.append("")

        # Models
        for model_name, model_def in netlist.models.items():
            lines.append(model_def)

        lines.append("")

        # Analysis
        for analysis in netlist.analysis:
            lines.append(analysis)

        lines.append("")
        lines.append(".end")

        return "\n".join(lines)

    def simulate_modification(self, netlist: SpiceNetlist,
                            modification: Dict[str, any]) -> Dict[str, any]:
        """
        Simulate a proposed modification.

        Args:
            netlist: Original netlist
            modification: Dict describing modification
                         e.g., {"change_voltage": {"from": "5V", "to": "3.3V"}}

        Returns:
            Simulation results with warnings
        """
        # This would interface with ngspice or similar
        # For now, return mock results

        results = {
            'success': True,
            'warnings': [],
            'voltages': {},
            'currents': {}
        }

        # Example: detect if voltage change would damage components
        if 'change_voltage' in modification:
            old_v = float(modification['change_voltage']['from'].replace('V', ''))
            new_v = float(modification['change_voltage']['to'].replace('V', ''))

            if new_v < old_v:
                results['warnings'].append(
                    f"Reducing voltage from {old_v}V to {new_v}V may cause circuit to malfunction"
                )
            elif new_v > old_v:
                results['warnings'].append(
                    f"Increasing voltage from {old_v}V to {new_v}V may damage components"
                )

        return results


# Global singleton
spice_generator = SpiceGenerator()
