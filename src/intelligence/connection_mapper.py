"""
Pin-to-Pin Connection Mapper

THE CRITICAL MISSING PIECE for real repair guidance.

Combines:
- Component detection (YOLO)
- Pin detection (computer vision)
- Trace analysis (follows copper)
- Pinout database (knows pin functions)

To generate instructions like:
- "Cut trace between pin 7 of U3 and pin 15 of U5"
- "Desolder pin 3 of IC2"
- "Bridge pin 12 of ESP8266 to pin 5 of voltage regulator"
- "Measure voltage at pin 8 of ATmega328P (should be 16MHz)"
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
import networkx as nx

from intelligence.pinout_database import pinout_database, PinDefinition
from intelligence.pin_detector import pin_detector, ICDetectionResult, DetectedPin
from intelligence.trace_analyzer import trace_analyzer


@dataclass
class PinConnection:
    """A connection between two IC pins."""
    ic1_part: str
    ic1_pin_number: int
    ic1_pin_name: str
    ic1_position: Tuple[int, int]

    ic2_part: str
    ic2_pin_number: int
    ic2_pin_name: str
    ic2_position: Tuple[int, int]

    connection_type: str  # "direct_trace", "via", "power_plane", "ground_plane", "inferred"
    trace_length_mm: Optional[float] = None
    trace_resistance_ohm: Optional[float] = None
    confidence: float = 0.0


@dataclass
class NetConnection:
    """A named net (like 5V, GND, SDA, etc.) with all connected pins."""
    net_name: str  # "5V", "GND", "I2C_SDA", "UART_TX", etc.
    net_type: str  # "power", "ground", "signal", "analog"
    pins: List[Tuple[str, int, str]]  # [(ic_part, pin_number, pin_name), ...]
    voltage: Optional[float] = None
    max_current_a: Optional[float] = None


@dataclass
class CircuitSchematic:
    """Complete circuit connectivity map (like a schematic, but extracted from PCB photo)."""
    ics: List[ICDetectionResult]  # All detected ICs
    connections: List[PinConnection]  # Pin-to-pin connections
    nets: List[NetConnection]  # Named nets
    power_rails: Dict[str, float]  # {"5V": 5.0, "3V3": 3.3}
    ground_pins: List[Tuple[str, int]]  # All GND pins: [(ic_part, pin_num), ...]
    unconnected_pins: List[Tuple[str, int, str]]  # Pins not connected: [(ic, pin_num, pin_name), ...]
    confidence: float = 0.0


class ConnectionMapper:
    """Maps pin-to-pin connections in a PCB."""

    def __init__(self):
        self.pinout_db = pinout_database
        self.pin_det = pin_detector
        self.trace_ana = trace_analyzer

    def map_connections(self, image: np.ndarray, component_detections: List[Any],
                       calibration_mm: Optional[float] = None) -> CircuitSchematic:
        """
        Create complete circuit connectivity map from PCB image.

        This is THE function that enables pin-level repair instructions.

        Args:
            image: PCB photo
            component_detections: Component detections from YOLO
            calibration_mm: Known dimension for scale (optional)

        Returns:
            Complete circuit schematic with all connections
        """
        # Step 1: Detect IC pins
        ic_detections = self._detect_all_ic_pins(image, component_detections)

        # Step 2: Analyze traces
        trace_analysis = self.trace_ana.analyze_traces(image, component_detections, calibration_mm)

        # Step 3: Map traces to pins
        pin_connections = self._map_traces_to_pins(ic_detections, trace_analysis)

        # Step 4: Identify nets (power rails, common signals)
        nets = self._identify_nets(ic_detections, pin_connections)

        # Step 5: Find power rails
        power_rails = self._identify_power_rails(nets)

        # Step 6: Find ground connections
        ground_pins = self._identify_ground_pins(ic_detections)

        # Step 7: Find unconnected pins
        unconnected = self._find_unconnected_pins(ic_detections, pin_connections)

        # Calculate overall confidence
        if ic_detections:
            avg_confidence = np.mean([ic.confidence for ic in ic_detections])
        else:
            avg_confidence = 0.0

        return CircuitSchematic(
            ics=ic_detections,
            connections=pin_connections,
            nets=nets,
            power_rails=power_rails,
            ground_pins=ground_pins,
            unconnected_pins=unconnected,
            confidence=avg_confidence
        )

    def _detect_all_ic_pins(self, image: np.ndarray,
                           component_detections: List[Any]) -> List[ICDetectionResult]:
        """Detect pins on all ICs in the image."""
        ic_detections = []

        # Filter for ICs only (not passives)
        ic_types = ["ATMEGA328P", "ATmega328", "Arduino-Uno", "Arduino",
                   "ESP8266", "ESP32", "ESP-12", "NodeMCU",
                   "LM7805", "AMS1117", "Voltage-Regulator",
                   "CH340", "CP2102", "FT232",
                   "Flash-Memory", "W25Q", "MX25L"]

        for detection in component_detections:
            # Check if this is an IC
            is_ic = any(ic_type.lower() in detection.class_name.lower() for ic_type in ic_types)

            if is_ic:
                # Convert bbox to tuple
                bbox = tuple(map(int, detection.bbox))

                # Detect pins
                ic_detection = self.pin_det.detect_ic_pins(image, bbox, detection.class_name)

                if ic_detection:
                    ic_detections.append(ic_detection)

        return ic_detections

    def _map_traces_to_pins(self, ic_detections: List[ICDetectionResult],
                           trace_analysis: Dict[str, Any]) -> List[PinConnection]:
        """
        Map detected traces to specific IC pins.

        This is the hardest part: figuring out which trace connects which pins.
        """
        connections = []

        if not trace_analysis.get('traces'):
            return connections

        # Build spatial index of all pins
        pin_index = []  # [(x, y, ic_part, pin_number, pin_name), ...]
        for ic in ic_detections:
            pinout = self.pinout_db.get_pinout(ic.part_number)
            for detected_pin in ic.pins:
                pin_name = "unknown"
                if pinout:
                    for pin_def in pinout.pins:
                        if pin_def.pin_number == detected_pin.pin_number:
                            pin_name = pin_def.pin_name
                            break

                pin_index.append((
                    detected_pin.position[0],
                    detected_pin.position[1],
                    ic.part_number,
                    detected_pin.pin_number,
                    pin_name
                ))

        # For each trace, find pins at endpoints
        traces = trace_analysis.get('traces', [])
        for trace in traces:
            # Handle both dict and Trace object
            if hasattr(trace, 'start_point'):
                # It's a Trace object
                start_point = trace.start_point
                end_point = trace.end_point
                trace_length = trace.length_mm
                trace_resistance = None  # Calculate if needed
            else:
                # It's a dict
                endpoints = trace.get('endpoints', [])
                if len(endpoints) < 2:
                    continue
                start_point = endpoints[0]
                end_point = endpoints[-1]
                trace_length = trace.get('length_mm')
                trace_resistance = trace.get('resistance_ohm')

            # Find pins near start and end
            start_pin = self._find_nearest_pin(start_point, pin_index, max_distance=50)
            end_pin = self._find_nearest_pin(end_point, pin_index, max_distance=50)

            if start_pin and end_pin and start_pin != end_pin:
                connections.append(PinConnection(
                    ic1_part=start_pin[2],
                    ic1_pin_number=start_pin[3],
                    ic1_pin_name=start_pin[4],
                    ic1_position=(start_pin[0], start_pin[1]),
                    ic2_part=end_pin[2],
                    ic2_pin_number=end_pin[3],
                    ic2_pin_name=end_pin[4],
                    ic2_position=(end_pin[0], end_pin[1]),
                    connection_type="direct_trace",
                    trace_length_mm=trace_length,
                    trace_resistance_ohm=trace_resistance,
                    confidence=0.7
                ))

        # Infer common connections (VCC-VCC, GND-GND, TX-RX)
        inferred = self._infer_common_connections(ic_detections)
        connections.extend(inferred)

        return connections

    def _find_nearest_pin(self, point: Tuple[int, int], pin_index: List[Tuple],
                         max_distance: float = 50) -> Optional[Tuple]:
        """Find pin nearest to a point."""
        px, py = point
        nearest = None
        min_dist = max_distance

        for pin in pin_index:
            pin_x, pin_y = pin[0], pin[1]
            dist = np.sqrt((px - pin_x)**2 + (py - pin_y)**2)

            if dist < min_dist:
                min_dist = dist
                nearest = pin

        return nearest

    def _infer_common_connections(self, ic_detections: List[ICDetectionResult]) -> List[PinConnection]:
        """
        Infer connections based on common patterns:
        - All VCC pins likely connected
        - All GND pins likely connected
        - MCU TX → USB chip RX
        - MCU RX → USB chip TX
        - ESP GPIO0 → Button → GND
        - etc.
        """
        connections = []

        # Group pins by function
        vcc_pins = []
        gnd_pins = []
        tx_pins = []
        rx_pins = []

        for ic in ic_detections:
            pinout = self.pinout_db.get_pinout(ic.part_number)
            if not pinout:
                continue

            for detected_pin in ic.pins:
                pin_def = None
                for pd in pinout.pins:
                    if pd.pin_number == detected_pin.pin_number:
                        pin_def = pd
                        break

                if not pin_def:
                    continue

                pin_name_upper = pin_def.pin_name.upper()

                # Categorize
                if "VCC" in pin_name_upper or "VDD" in pin_name_upper or pin_name_upper == "3V3":
                    vcc_pins.append((ic.part_number, detected_pin.pin_number, pin_def.pin_name, detected_pin.position))
                elif "GND" in pin_name_upper or pin_name_upper == "GROUND":
                    gnd_pins.append((ic.part_number, detected_pin.pin_number, pin_def.pin_name, detected_pin.position))
                elif "TXD" in pin_name_upper or "TX" == pin_name_upper:
                    tx_pins.append((ic.part_number, detected_pin.pin_number, pin_def.pin_name, detected_pin.position))
                elif "RXD" in pin_name_upper or "RX" == pin_name_upper:
                    rx_pins.append((ic.part_number, detected_pin.pin_number, pin_def.pin_name, detected_pin.position))

        # Connect TX to RX (cross-connect)
        for tx_pin in tx_pins:
            for rx_pin in rx_pins:
                # Don't connect IC to itself
                if tx_pin[0] == rx_pin[0]:
                    continue

                connections.append(PinConnection(
                    ic1_part=tx_pin[0],
                    ic1_pin_number=tx_pin[1],
                    ic1_pin_name=tx_pin[2],
                    ic1_position=tx_pin[3],
                    ic2_part=rx_pin[0],
                    ic2_pin_number=rx_pin[1],
                    ic2_pin_name=rx_pin[2],
                    ic2_position=rx_pin[3],
                    connection_type="inferred",
                    confidence=0.8
                ))

        return connections

    def _identify_nets(self, ic_detections: List[ICDetectionResult],
                      connections: List[PinConnection]) -> List[NetConnection]:
        """
        Identify named nets (like power rails, I2C bus, etc.).

        Uses graph connectivity: if pins are connected, they're on same net.
        """
        # Build connectivity graph
        G = nx.Graph()

        # Add all pins as nodes
        for ic in ic_detections:
            pinout = self.pinout_db.get_pinout(ic.part_number)
            for detected_pin in ic.pins:
                pin_name = "unknown"
                if pinout:
                    for pd in pinout.pins:
                        if pd.pin_number == detected_pin.pin_number:
                            pin_name = pd.pin_name
                            break

                node_id = f"{ic.part_number}_pin{detected_pin.pin_number}"
                G.add_node(node_id, ic=ic.part_number, pin_num=detected_pin.pin_number, pin_name=pin_name)

        # Add connections as edges
        for conn in connections:
            node1 = f"{conn.ic1_part}_pin{conn.ic1_pin_number}"
            node2 = f"{conn.ic2_part}_pin{conn.ic2_pin_number}"
            G.add_edge(node1, node2)

        # Find connected components (each is a net)
        nets = []
        for component in nx.connected_components(G):
            nodes = list(component)

            # Determine net name and type from pin names
            pin_names = [G.nodes[n]['pin_name'] for n in nodes]
            net_name, net_type = self._infer_net_name(pin_names)

            pins = [(G.nodes[n]['ic'], G.nodes[n]['pin_num'], G.nodes[n]['pin_name']) for n in nodes]

            # Determine voltage if power net
            voltage = None
            if net_type == "power":
                if "5V" in net_name or "VCC" in net_name:
                    voltage = 5.0
                elif "3V3" in net_name or "3.3V" in net_name:
                    voltage = 3.3
                elif "12V" in net_name:
                    voltage = 12.0

            nets.append(NetConnection(
                net_name=net_name,
                net_type=net_type,
                pins=pins,
                voltage=voltage
            ))

        return nets

    def _infer_net_name(self, pin_names: List[str]) -> Tuple[str, str]:
        """Infer net name from connected pin names."""
        pin_names_upper = [p.upper() for p in pin_names]

        # Power
        if any("VCC" in p or "VDD" in p for p in pin_names_upper):
            return ("VCC_5V", "power")
        if any("3V3" in p or "3.3V" in p for p in pin_names_upper):
            return ("VCC_3V3", "power")

        # Ground
        if any("GND" in p or "GROUND" in p for p in pin_names_upper):
            return ("GND", "ground")

        # I2C
        if any("SDA" in p for p in pin_names_upper):
            return ("I2C_SDA", "signal")
        if any("SCL" in p for p in pin_names_upper):
            return ("I2C_SCL", "signal")

        # SPI
        if any("MOSI" in p for p in pin_names_upper):
            return ("SPI_MOSI", "signal")
        if any("MISO" in p for p in pin_names_upper):
            return ("SPI_MISO", "signal")
        if any("SCK" in p for p in pin_names_upper):
            return ("SPI_SCK", "signal")

        # UART
        if any("TXD" in p or p == "TX" for p in pin_names_upper):
            return ("UART_TX", "signal")
        if any("RXD" in p or p == "RX" for p in pin_names_upper):
            return ("UART_RX", "signal")

        # Default
        return (f"NET_{pin_names[0]}", "signal")

    def _identify_power_rails(self, nets: List[NetConnection]) -> Dict[str, float]:
        """Extract power rails from nets."""
        rails = {}
        for net in nets:
            if net.net_type == "power" and net.voltage:
                rails[net.net_name] = net.voltage
        return rails

    def _identify_ground_pins(self, ic_detections: List[ICDetectionResult]) -> List[Tuple[str, int]]:
        """Find all ground pins."""
        ground_pins = []

        for ic in ic_detections:
            pinout = self.pinout_db.get_pinout(ic.part_number)
            if not pinout:
                continue

            for detected_pin in ic.pins:
                pin_def = None
                for pd in pinout.pins:
                    if pd.pin_number == detected_pin.pin_number:
                        pin_def = pd
                        break

                if pin_def and "GND" in pin_def.pin_name.upper():
                    ground_pins.append((ic.part_number, detected_pin.pin_number))

        return ground_pins

    def _find_unconnected_pins(self, ic_detections: List[ICDetectionResult],
                               connections: List[PinConnection]) -> List[Tuple[str, int, str]]:
        """Find pins that aren't connected to anything (potential issues)."""
        # Build set of connected pins
        connected = set()
        for conn in connections:
            connected.add((conn.ic1_part, conn.ic1_pin_number))
            connected.add((conn.ic2_part, conn.ic2_pin_number))

        # Find unconnected
        unconnected = []
        for ic in ic_detections:
            pinout = self.pinout_db.get_pinout(ic.part_number)
            if not pinout:
                continue

            for detected_pin in ic.pins:
                pin_key = (ic.part_number, detected_pin.pin_number)

                if pin_key not in connected:
                    pin_name = "unknown"
                    for pd in pinout.pins:
                        if pd.pin_number == detected_pin.pin_number:
                            pin_name = pd.pin_name
                            break

                    # Only report if it's critical or should be connected
                    pin_def = None
                    for pd in pinout.pins:
                        if pd.pin_number == detected_pin.pin_number:
                            pin_def = pd
                            break

                    if pin_def and pin_def.critical:
                        unconnected.append((ic.part_number, detected_pin.pin_number, pin_name))

        return unconnected

    def generate_cut_trace_instruction(self, schematic: CircuitSchematic,
                                      ic1_name: str, pin1: int,
                                      ic2_name: str, pin2: int) -> str:
        """Generate instruction to cut trace between two pins."""
        # Find connection
        connection = None
        for conn in schematic.connections:
            if ((conn.ic1_part == ic1_name and conn.ic1_pin_number == pin1 and
                 conn.ic2_part == ic2_name and conn.ic2_pin_number == pin2) or
                (conn.ic2_part == ic1_name and conn.ic2_pin_number == pin1 and
                 conn.ic1_part == ic2_name and conn.ic1_pin_number == pin2)):
                connection = conn
                break

        if not connection:
            return f"ERROR: No connection found between {ic1_name} pin {pin1} and {ic2_name} pin {pin2}"

        return (
            f"Cut trace between pin {connection.ic1_pin_number} ({connection.ic1_pin_name}) of {connection.ic1_part} "
            f"and pin {connection.ic2_pin_number} ({connection.ic2_pin_name}) of {connection.ic2_part}. "
            f"Trace is approximately {connection.trace_length_mm:.1f}mm long. "
            f"Use sharp hobby knife, cut at midpoint to allow reconnection if needed."
        )

    def generate_bridge_instruction(self, schematic: CircuitSchematic,
                                   ic1_name: str, pin1: int,
                                   ic2_name: str, pin2: int) -> str:
        """Generate instruction to bridge (connect) two pins."""
        # Validate connection
        pin1_def = None
        pin2_def = None

        for ic in schematic.ics:
            if ic.part_number == ic1_name:
                pinout = self.pinout_db.get_pinout(ic1_name)
                if pinout:
                    for pd in pinout.pins:
                        if pd.pin_number == pin1:
                            pin1_def = pd
                            break

            if ic.part_number == ic2_name:
                pinout = self.pinout_db.get_pinout(ic2_name)
                if pinout:
                    for pd in pinout.pins:
                        if pd.pin_number == pin2:
                            pin2_def = pd
                            break

        if not pin1_def or not pin2_def:
            return f"ERROR: Unknown pins"

        # Check voltage compatibility
        warning = ""
        if pin1_def.typical_voltage and pin2_def.typical_voltage:
            if abs(pin1_def.typical_voltage - pin2_def.typical_voltage) > 0.5:
                warning = f" WARNING: Voltage mismatch ({pin1_def.typical_voltage}V vs {pin2_def.typical_voltage}V)! Use level shifter!"

        return (
            f"Bridge pin {pin1} ({pin1_def.pin_name}) of {ic1_name} "
            f"to pin {pin2} ({pin2_def.pin_name}) of {ic2_name} "
            f"with 30AWG wire or solder blob.{warning}"
        )

    def generate_measurement_instruction(self, schematic: CircuitSchematic,
                                        ic_name: str, pin_num: int) -> str:
        """Generate instruction to measure voltage/signal at a pin."""
        # Find pin
        pin_def = None
        pinout = self.pinout_db.get_pinout(ic_name)
        if pinout:
            for pd in pinout.pins:
                if pd.pin_number == pin_num:
                    pin_def = pd
                    break

        if not pin_def:
            return f"Measure voltage at pin {pin_num} of {ic_name}"

        expected = ""
        if pin_def.typical_voltage is not None:
            expected = f" (should be {pin_def.typical_voltage}V in normal operation)"

        return (
            f"Measure voltage at pin {pin_num} ({pin_def.pin_name}: {pin_def.description}) "
            f"of {ic_name} with multimeter{expected}. "
            f"Black probe to GND, red probe to pin."
        )


# Global singleton
connection_mapper = ConnectionMapper()
