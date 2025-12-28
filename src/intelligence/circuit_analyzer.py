"""
Circuit Intelligence Layer - Spatial Relationship & Functional Analysis

This module provides deep circuit understanding beyond component detection:
- Spatial relationship analysis (which components work together)
- Functional block detection (power, control, I/O, communication)
- Circuit topology understanding (signal flow, power distribution)
- Device-specific intelligence (Arduino, phone, computer, router patterns)

Focus: High-value repair/repurpose electronics (Arduino, phones, computers, routers)
Not: Low-value appliances (hairdryers, fridges, etc.)
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Set, Optional
from dataclasses import dataclass, field
from scipy.spatial import distance_matrix
from sklearn.cluster import DBSCAN
from collections import defaultdict
from loguru import logger

from vision.enhanced_detector import ComponentDetection
from intelligence.component_knowledge import (
    get_component_spec, infer_component_relationships,
    estimate_power_consumption, get_modification_ideas,
    get_test_points, get_failure_modes
)
from intelligence.electrical_analysis import electrical_analyzer


@dataclass
class ComponentRelationship:
    """Represents a relationship between two components."""
    component1: ComponentDetection
    component2: ComponentDetection
    distance: float  # Physical distance on PCB
    relationship_type: str  # 'power', 'signal', 'control', 'data', 'unknown'
    confidence: float  # How confident we are about this relationship
    functional_role: str  # What this connection does


@dataclass
class FunctionalBlock:
    """Represents a functional section of the circuit."""
    block_id: str
    block_type: str  # 'power', 'mcu_core', 'rf', 'usb', 'display', 'storage', etc.
    components: List[ComponentDetection]
    center: Tuple[float, float]
    function: str  # Human-readable description
    capabilities: List[str]  # What this block can do
    modification_potential: List[str]  # How this can be repurposed
    critical_level: str  # 'essential', 'important', 'optional'
    power_requirements: Optional[Dict[str, Any]] = None
    signal_interfaces: List[str] = field(default_factory=list)


@dataclass
class CircuitTopology:
    """High-level understanding of circuit structure."""
    device_type: str  # 'arduino', 'phone', 'router', 'computer', 'unknown'
    device_confidence: float
    functional_blocks: List[FunctionalBlock]
    power_tree: Dict[str, Any]  # Power distribution hierarchy
    signal_paths: List[Dict[str, Any]]  # Key signal routes
    repair_complexity: str  # 'easy', 'moderate', 'hard', 'expert'
    repurpose_potential: float  # 0-1 score
    modification_suggestions: List[str]

    # NEW: Deep electrical analysis
    power_budget: Optional[Dict[str, Any]] = None  # Total power consumption
    voltage_rails: List[Dict[str, Any]] = field(default_factory=list)  # Available voltages
    test_points: Dict[str, List[str]] = field(default_factory=dict)  # Component test points
    failure_modes: Dict[str, List[str]] = field(default_factory=dict)  # Known failure modes
    electrical_calculations: Dict[str, Any] = field(default_factory=dict)  # Specific calculations
    circuit_behavior: Dict[str, Any] = field(default_factory=dict)  # Expected behavior


class CircuitIntelligenceAnalyzer:
    """
    Analyzes PCB components to understand circuit function and topology.

    Goes beyond detection to answer:
    - What does this circuit DO?
    - How do components work together?
    - What can I repurpose/repair?
    - Which modifications are safe?
    """

    def __init__(self):
        """Initialize circuit intelligence analyzer."""
        # Device-specific pattern libraries (limited scope: high-value devices)
        self.device_patterns = self._load_device_patterns()
        self.functional_patterns = self._load_functional_patterns()

        # Spatial analysis parameters
        self.clustering_eps = 0.15  # 15% of image for DBSCAN
        self.min_cluster_size = 2

        logger.info("Circuit Intelligence Analyzer initialized")

    def analyze_circuit(self, detections: List[ComponentDetection],
                       image_dimensions: Tuple[int, int]) -> CircuitTopology:
        """
        Perform complete circuit intelligence analysis.

        Args:
            detections: List of detected components
            image_dimensions: (width, height) of PCB image

        Returns:
            CircuitTopology with complete understanding
        """
        if not detections:
            return self._empty_topology()

        logger.info(f"Analyzing circuit with {len(detections)} components")

        # Populate centers if missing
        for detection in detections:
            if detection.center is None:
                x1, y1, x2, y2 = detection.bbox
                detection.center = ((x1 + x2) / 2, (y1 + y2) / 2)

        # Step 1: Spatial relationship analysis
        relationships = self._analyze_spatial_relationships(detections, image_dimensions)

        # Step 2: Functional block detection
        functional_blocks = self._detect_functional_blocks(
            detections, relationships, image_dimensions
        )

        # Step 3: Device type identification
        device_type, device_confidence = self._identify_device_type(
            detections, functional_blocks
        )

        # Step 4: Power tree analysis
        power_tree = self._analyze_power_distribution(
            detections, functional_blocks
        )

        # Step 5: Signal path analysis
        signal_paths = self._analyze_signal_paths(
            detections, functional_blocks, device_type
        )

        # Step 6: Repair/repurpose analysis
        repair_complexity = self._assess_repair_complexity(
            device_type, functional_blocks
        )

        repurpose_potential = self._assess_repurpose_potential(
            device_type, functional_blocks
        )

        modification_suggestions = self._generate_modification_suggestions(
            device_type, functional_blocks, signal_paths
        )

        # NEW STEPS: Deep electrical analysis
        # Step 7: Power budget calculation
        component_names = [d.class_name for d in detections]
        power_budget = electrical_analyzer.analyze_power_budget(component_names)

        # Step 8: Voltage rail analysis
        voltage_rails = electrical_analyzer.analyze_voltage_rails(
            component_names, {}  # TODO: pass regulator info
        )

        # Step 9: Test points for each component
        test_points = {}
        for detection in detections:
            points = get_test_points(detection.class_name)
            if points:
                test_points[detection.class_name] = points

        # Step 10: Failure modes for troubleshooting
        failure_modes = {}
        for detection in detections:
            modes = get_failure_modes(detection.class_name)
            if modes:
                failure_modes[detection.class_name] = modes

        # Step 11: Circuit-specific electrical calculations
        electrical_calculations = self._perform_electrical_calculations(
            detections, functional_blocks, device_type
        )

        # Step 12: Circuit behavior prediction
        circuit_behavior = self._predict_circuit_behavior(
            device_type, functional_blocks, detections
        )

        topology = CircuitTopology(
            device_type=device_type,
            device_confidence=device_confidence,
            functional_blocks=functional_blocks,
            power_tree=power_tree,
            signal_paths=signal_paths,
            repair_complexity=repair_complexity,
            repurpose_potential=repurpose_potential,
            modification_suggestions=modification_suggestions,
            power_budget=power_budget.__dict__ if power_budget else None,
            voltage_rails=[rail.__dict__ for rail in voltage_rails],
            test_points=test_points,
            failure_modes=failure_modes,
            electrical_calculations=electrical_calculations,
            circuit_behavior=circuit_behavior
        )

        logger.info(f"Circuit analysis complete: {device_type} with {len(functional_blocks)} blocks, "
                   f"{power_budget.total_power_w:.2f}W total power")
        return topology

    def _analyze_spatial_relationships(self,
                                      detections: List[ComponentDetection],
                                      image_dims: Tuple[int, int]) -> List[ComponentRelationship]:
        """
        Analyze which components are physically close (likely connected).

        Uses spatial clustering and distance analysis to infer connections
        even without trace detection.
        """
        relationships = []

        # Extract component centers (normalized to 0-1)
        centers = np.array([[d.center[0] / image_dims[0],
                            d.center[1] / image_dims[1]] for d in detections])

        # Calculate pairwise distances
        distances = distance_matrix(centers, centers)

        # Find nearby component pairs (within clustering distance)
        for i in range(len(detections)):
            for j in range(i + 1, len(detections)):
                dist = distances[i, j]

                if dist < self.clustering_eps:  # Components are close
                    # Infer relationship type based on component types
                    rel_type, confidence = self._infer_relationship_type(
                        detections[i], detections[j], dist
                    )

                    functional_role = self._infer_functional_role(
                        detections[i], detections[j], rel_type
                    )

                    relationship = ComponentRelationship(
                        component1=detections[i],
                        component2=detections[j],
                        distance=dist,
                        relationship_type=rel_type,
                        confidence=confidence,
                        functional_role=functional_role
                    )

                    relationships.append(relationship)

        logger.info(f"Identified {len(relationships)} component relationships")
        return relationships

    def _detect_functional_blocks(self,
                                  detections: List[ComponentDetection],
                                  relationships: List[ComponentRelationship],
                                  image_dims: Tuple[int, int]) -> List[FunctionalBlock]:
        """
        Detect functional blocks using spatial clustering and pattern matching.

        Examples:
        - MCU + capacitors + crystal = Microcontroller core
        - Voltage regulator + capacitors = Power supply section
        - RF chip + antenna connector = Wireless module
        """
        # Spatial clustering to group nearby components
        centers = np.array([[d.center[0] / image_dims[0],
                            d.center[1] / image_dims[1]] for d in detections])

        clustering = DBSCAN(eps=self.clustering_eps, min_samples=self.min_cluster_size)
        cluster_labels = clustering.fit_predict(centers)

        # Group components by cluster
        clusters = defaultdict(list)
        for idx, label in enumerate(cluster_labels):
            if label != -1:  # -1 means noise (unclustered)
                clusters[label].append(detections[idx])

        # Analyze each cluster to determine function
        functional_blocks = []

        for cluster_id, components in clusters.items():
            block = self._analyze_cluster_function(
                cluster_id, components, image_dims
            )
            if block:
                functional_blocks.append(block)

        logger.info(f"Detected {len(functional_blocks)} functional blocks")
        return functional_blocks

    def _analyze_cluster_function(self,
                                 cluster_id: int,
                                 components: List[ComponentDetection],
                                 image_dims: Tuple[int, int]) -> Optional[FunctionalBlock]:
        """
        Determine what a cluster of components does.

        Pattern matching against known circuit blocks.
        """
        # Extract component types
        component_types = [c.class_name.lower() for c in components]
        component_type_counts = {t: component_types.count(t) for t in set(component_types)}

        # Calculate cluster center
        centers = [c.center for c in components]
        cluster_center = (
            sum(c[0] for c in centers) / len(centers),
            sum(c[1] for c in centers)  / len(centers)
        )

        # Pattern matching to identify block type
        block_type, function, capabilities = self._match_functional_pattern(
            component_type_counts, component_types
        )

        # Assess modification potential
        modification_potential = self._assess_block_modification_potential(
            block_type, component_type_counts
        )

        # Determine criticality
        critical_level = self._assess_criticality(block_type)

        block = FunctionalBlock(
            block_id=f"block_{cluster_id}",
            block_type=block_type,
            components=components,
            center=cluster_center,
            function=function,
            capabilities=capabilities,
            modification_potential=modification_potential,
            critical_level=critical_level
        )

        return block

    def _match_functional_pattern(self,
                                  component_counts: Dict[str, int],
                                  component_list: List[str]) -> Tuple[str, str, List[str]]:
        """
        Match component combinations to known functional blocks.

        Returns: (block_type, function_description, capabilities)
        """
        # Microcontroller core pattern
        if any('mcu' in c or 'microcontroller' in c or 'arduino' in c for c in component_list):
            if component_counts.get('capacitor', 0) >= 2:
                return (
                    'mcu_core',
                    'Microcontroller with power decoupling and support circuitry',
                    ['programmable', 'gpio', 'reprogrammable', 'control_logic']
                )

        # Power supply pattern
        if any('regulator' in c or 'ldo' in c or 'buck' in c or 'boost' in c for c in component_list):
            return (
                'power_supply',
                'Voltage regulation and power distribution',
                ['voltage_conversion', 'power_distribution', 'can_tap_power']
            )

        # USB/Communication pattern
        if any('usb' in c or 'uart' in c or 'ftdi' in c for c in component_list):
            return (
                'usb_interface',
                'USB communication and data transfer',
                ['serial_communication', 'programming', 'data_transfer', 'can_reprogram']
            )

        # RF/Wireless pattern
        if any('esp' in c or 'wifi' in c or 'bluetooth' in c or 'rf' in c for c in component_list):
            return (
                'wireless_module',
                'Wireless communication (WiFi/Bluetooth)',
                ['wireless', 'internet', 'remote_control', 'iot_capable']
            )

        # Display interface
        if any('lcd' in c or 'oled' in c or 'display' in c for c in component_list):
            return (
                'display_interface',
                'Display driver and control circuitry',
                ['visual_output', 'user_interface', 'can_reuse_display']
            )

        # Sensor cluster
        if any('sensor' in c or 'temp' in c or 'accel' in c or 'gyro' in c for c in component_list):
            return (
                'sensor_module',
                'Environmental or motion sensing',
                ['data_acquisition', 'monitoring', 'reusable_sensors']
            )

        # Memory/Storage
        if any('flash' in c or 'eeprom' in c or 'memory' in c or 'sd' in c for c in component_list):
            return (
                'storage',
                'Data storage and memory',
                ['data_persistence', 'firmware_storage', 'expandable']
            )

        # Motor/Actuator control
        if any('motor' in c or 'driver' in c or 'servo' in c or 'relay' in c for c in component_list):
            return (
                'actuator_control',
                'Motor or actuator driver circuit',
                ['movement', 'physical_control', 'automation']
            )

        # Default: passive support circuitry
        if component_counts.get('resistor', 0) + component_counts.get('capacitor', 0) > len(component_list) * 0.7:
            return (
                'passive_network',
                'Filtering, decoupling, or signal conditioning',
                ['signal_conditioning', 'noise_filtering', 'basic_support']
            )

        # Unknown
        return (
            'unknown',
            'Unidentified circuit block',
            ['unknown_function']
        )

    def _identify_device_type(self,
                             detections: List[ComponentDetection],
                             blocks: List[FunctionalBlock]) -> Tuple[str, float]:
        """
        Identify what type of device this is.

        Focus on high-value repair/repurpose targets:
        - Arduino/development boards
        - Phones
        - Computers/laptops
        - Routers/networking
        """
        component_names = [d.class_name.lower() for d in detections]
        block_types = [b.block_type for b in blocks]

        # Arduino detection
        if any('arduino' in name for name in component_names):
            return ('arduino', 0.95)

        if 'mcu_core' in block_types and 'usb_interface' in block_types:
            if any('atmega' in name or 'avr' in name for name in component_names):
                return ('arduino', 0.85)

        # Phone detection
        if any('phone' in name or 'mobile' in name for name in component_names):
            return ('phone', 0.90)

        if 'display_interface' in block_types and 'wireless_module' in block_types:
            if any('battery' in name or 'charger' in name for name in component_names):
                return ('phone', 0.75)

        # Router detection
        if any('router' in name or 'ethernet' in name for name in component_names):
            return ('router', 0.90)

        if 'wireless_module' in block_types and component_names.count('connector') >= 3:
            return ('router', 0.70)

        # Computer/laptop detection
        if any('cpu' in name or 'processor' in name or 'ram' in name for name in component_names):
            return ('computer', 0.85)

        if 'storage' in block_types and len(blocks) >= 5:
            return ('computer', 0.60)

        # Development board (generic)
        if 'mcu_core' in block_types:
            return ('development_board', 0.65)

        return ('unknown', 0.0)

    def _analyze_power_distribution(self,
                                   detections: List[ComponentDetection],
                                   blocks: List[FunctionalBlock]) -> Dict[str, Any]:
        """
        Analyze power distribution tree.

        Important for:
        - Safe modifications (don't cut power!)
        - Power tapping for new features
        - Understanding voltage levels
        """
        power_blocks = [b for b in blocks if b.block_type == 'power_supply']

        # Build power tree (simplified without trace detection)
        power_tree = {
            'primary_source': 'unknown',
            'voltage_levels': [],
            'regulation_stages': len(power_blocks),
            'power_pins': [],
            'can_tap_power': len(power_blocks) > 0,
            'safe_voltage_points': []
        }

        # Infer voltage levels from power block components
        for block in power_blocks:
            # Look for voltage regulators
            for comp in block.components:
                if any(term in comp.class_name.lower() for term in ['regulator', '3.3v', '5v', '1.8v']):
                    if '3.3' in comp.class_name.lower() or '3v3' in comp.class_name.lower():
                        power_tree['voltage_levels'].append('3.3V')
                        power_tree['safe_voltage_points'].append(comp.center)
                    elif '5v' in comp.class_name.lower():
                        power_tree['voltage_levels'].append('5V')
                        power_tree['safe_voltage_points'].append(comp.center)

        if not power_tree['voltage_levels']:
            power_tree['voltage_levels'] = ['unknown']

        return power_tree

    def _analyze_signal_paths(self,
                             detections: List[ComponentDetection],
                             blocks: List[FunctionalBlock],
                             device_type: str) -> List[Dict[str, Any]]:
        """
        Identify key signal paths (without trace detection).

        Important for understanding:
        - Data flow
        - Control signals
        - What can be tapped/modified
        """
        signal_paths = []

        # Look for communication blocks
        usb_blocks = [b for b in blocks if b.block_type == 'usb_interface']
        wireless_blocks = [b for b in blocks if b.block_type == 'wireless_module']
        mcu_blocks = [b for b in blocks if b.block_type == 'mcu_core']

        # USB paths (reprogramming, data)
        for usb_block in usb_blocks:
            for mcu_block in mcu_blocks:
                signal_paths.append({
                    'name': 'USB Programming',
                    'from_block': usb_block.block_id,
                    'to_block': mcu_block.block_id,
                    'signal_type': 'data',
                    'purpose': 'Programming and serial communication',
                    'can_tap': True,
                    'modification_potential': 'Can reprogram MCU, add serial debugging'
                })

        # Wireless paths
        for wireless_block in wireless_blocks:
            signal_paths.append({
                'name': 'Wireless Communication',
                'from_block': wireless_block.block_id,
                'to_block': 'external',
                'signal_type': 'rf',
                'purpose': 'WiFi/Bluetooth communication',
                'can_tap': False,
                'modification_potential': 'Can repurpose for IoT projects'
            })

        return signal_paths

    def _assess_repair_complexity(self,
                                 device_type: str,
                                 blocks: List[FunctionalBlock]) -> str:
        """Assess how difficult repairs would be."""
        # Device-specific complexity
        if device_type in ['arduino', 'development_board']:
            return 'easy'
        elif device_type in ['router']:
            return 'moderate'
        elif device_type in ['phone', 'computer']:
            return 'hard'
        else:
            # Base on component count and complexity
            total_components = sum(len(b.components) for b in blocks)
            if total_components < 20:
                return 'easy'
            elif total_components < 50:
                return 'moderate'
            else:
                return 'hard'

    def _assess_repurpose_potential(self,
                                   device_type: str,
                                   blocks: List[FunctionalBlock]) -> float:
        """Score repurposing potential (0-1)."""
        score = 0.0

        # Device type bonuses
        device_scores = {
            'arduino': 0.9,
            'development_board': 0.85,
            'router': 0.7,
            'phone': 0.5,
            'computer': 0.4
        }
        score += device_scores.get(device_type, 0.3)

        # Functional block bonuses
        block_bonuses = {
            'mcu_core': 0.15,
            'wireless_module': 0.10,
            'usb_interface': 0.08,
            'sensor_module': 0.07,
            'display_interface': 0.06
        }

        for block in blocks:
            score += block_bonuses.get(block.block_type, 0.0)

        return min(score, 1.0)

    def _assess_block_modification_potential(self,
                                            block_type: str,
                                            component_counts: Dict[str, int]) -> List[str]:
        """What modifications are possible with this block."""
        modifications = []

        if block_type == 'mcu_core':
            modifications.extend([
                'Reprogram for new functionality',
                'Add custom firmware',
                'Use GPIO pins for sensors/actuators',
                'Create standalone controller'
            ])

        elif block_type == 'wireless_module':
            modifications.extend([
                'Repurpose for IoT project',
                'Create WiFi-enabled device',
                'Remote control application',
                'Network sensor node'
            ])

        elif block_type == 'power_supply':
            modifications.extend([
                'Tap power for additional circuits',
                'Power external sensors',
                'Create portable power supply'
            ])

        elif block_type == 'usb_interface':
            modifications.extend([
                'Serial communication interface',
                'Programming port for MCU',
                'Debug interface',
                'USB device emulation'
            ])

        elif block_type == 'display_interface':
            modifications.extend([
                'Reuse display for projects',
                'Create standalone display module',
                'Add to embedded systems'
            ])

        return modifications

    def _generate_modification_suggestions(self,
                                          device_type: str,
                                          blocks: List[FunctionalBlock],
                                          signal_paths: List[Dict[str, Any]]) -> List[str]:
        """Generate practical modification suggestions."""
        suggestions = []

        # Device-specific suggestions
        if device_type == 'arduino':
            suggestions.append("Upload custom Arduino sketch for new functionality")
            suggestions.append("Connect additional sensors via available GPIO pins")
            suggestions.append("Use as IoT controller by adding WiFi module")

        elif device_type == 'router':
            suggestions.append("Install OpenWRT for advanced features")
            suggestions.append("Repurpose as network monitoring device")
            suggestions.append("Use as WiFi repeater or access point")
            suggestions.append("Extract ESP module for standalone IoT projects")

        elif device_type == 'phone':
            suggestions.append("Reuse display for Raspberry Pi projects")
            suggestions.append("Extract camera module for computer vision")
            suggestions.append("Salvage battery for portable projects")
            suggestions.append("Use as dedicated music player or e-reader")

        elif device_type == 'development_board':
            suggestions.append("Reprogram MCU for custom applications")
            suggestions.append("Use as prototyping platform")
            suggestions.append("Create educational electronics projects")

        # Block-specific suggestions
        for block in blocks:
            if block.block_type == 'wireless_module' and device_type != 'phone':
                suggestions.append(f"Repurpose {block.block_type} for WiFi/BT connectivity")

        return list(set(suggestions))  # Remove duplicates

    def _assess_criticality(self, block_type: str) -> str:
        """How critical is this block to device operation."""
        critical_blocks = {'power_supply', 'mcu_core'}
        important_blocks = {'usb_interface', 'wireless_module', 'storage'}

        if block_type in critical_blocks:
            return 'essential'
        elif block_type in important_blocks:
            return 'important'
        else:
            return 'optional'

    def _infer_relationship_type(self,
                                comp1: ComponentDetection,
                                comp2: ComponentDetection,
                                distance: float) -> Tuple[str, float]:
        """
        Infer what type of connection exists between components.

        NOW USES DEEP COMPONENT KNOWLEDGE!
        """
        # Use domain knowledge from component database
        rel_type, confidence, _ = infer_component_relationships(
            comp1.class_name, comp2.class_name
        )

        # Adjust confidence based on distance (closer = more likely connected)
        if distance < 0.05:  # Very close
            confidence *= 1.2
        elif distance > 0.2:  # Far apart
            confidence *= 0.7

        confidence = min(confidence, 1.0)  # Cap at 1.0

        return (rel_type, confidence)

    def _infer_functional_role(self,
                              comp1: ComponentDetection,
                              comp2: ComponentDetection,
                              rel_type: str) -> str:
        """
        What does this connection do?

        NOW USES DEEP COMPONENT KNOWLEDGE!
        """
        # Use domain knowledge from component database
        _, _, functional_role = infer_component_relationships(
            comp1.class_name, comp2.class_name
        )

        return functional_role

    def _load_device_patterns(self) -> Dict[str, Any]:
        """
        Load device-specific circuit patterns.

        Currently limited to high-value repair/repurpose targets:
        - Arduino/development boards
        - Phones
        - Computers/laptops
        - Routers/networking equipment
        """
        return {
            'arduino': {
                'required_blocks': ['mcu_core', 'power_supply'],
                'optional_blocks': ['usb_interface', 'wireless_module'],
                'typical_components': ['atmega', 'avr', 'usb', 'regulator', 'crystal'],
                'repair_difficulty': 'easy',
                'repurpose_potential': 'high'
            },
            'phone': {
                'required_blocks': ['mcu_core', 'display_interface', 'wireless_module', 'power_supply'],
                'optional_blocks': ['storage', 'sensor_module', 'camera'],
                'typical_components': ['soc', 'display', 'battery', 'charging', 'wifi', 'bluetooth'],
                'repair_difficulty': 'hard',
                'repurpose_potential': 'medium'
            },
            'router': {
                'required_blocks': ['mcu_core', 'wireless_module', 'power_supply'],
                'optional_blocks': ['storage', 'usb_interface'],
                'typical_components': ['esp', 'wifi', 'ethernet', 'flash', 'regulator'],
                'repair_difficulty': 'moderate',
                'repurpose_potential': 'high'
            },
            'computer': {
                'required_blocks': ['mcu_core', 'power_supply', 'storage'],
                'optional_blocks': ['display_interface', 'usb_interface', 'wireless_module'],
                'typical_components': ['cpu', 'ram', 'storage', 'gpu', 'ports'],
                'repair_difficulty': 'hard',
                'repurpose_potential': 'medium'
            }
        }

    def _load_functional_patterns(self) -> Dict[str, Any]:
        """Load common functional circuit patterns."""
        return {
            'voltage_regulator': {
                'components': ['regulator', 'capacitor', 'capacitor'],
                'function': 'Voltage regulation',
                'modifiable': True
            },
            'usb_to_serial': {
                'components': ['usb', 'ftdi', 'uart'],
                'function': 'USB to serial conversion',
                'modifiable': True
            },
            'crystal_oscillator': {
                'components': ['crystal', 'capacitor', 'capacitor'],
                'function': 'Clock generation',
                'modifiable': False  # Critical for MCU operation
            }
        }

    def _perform_electrical_calculations(self,
                                         detections: List[ComponentDetection],
                                         functional_blocks: List[FunctionalBlock],
                                         device_type: str) -> Dict[str, Any]:
        """
        Perform circuit-specific electrical calculations.

        Pure electrical engineering - no ML needed!
        """
        calculations = {}

        # Find LEDs and calculate current limiting resistors
        leds = [d for d in detections if 'LED' in d.class_name]
        if leds:
            # Assume 5V supply for Arduino-type boards, 3.3V for others
            supply_v = 5.0 if device_type == 'arduino' else 3.3
            led_calc = electrical_analyzer.calculate_led_current_limiting_resistor(supply_v)
            calculations['led_resistor'] = led_calc

        # Find voltage regulators and estimate efficiency
        regulators = [d for d in detections if 'Regulator' in d.class_name or 'LM' in d.class_name]
        if regulators:
            # Typical scenario: 12V -> 5V @ 500mA
            reg_calc = electrical_analyzer.estimate_regulator_efficiency(
                vin=12.0, vout=5.0, iout=0.5, regulator_type="linear"
            )
            calculations['regulator_efficiency'] = reg_calc

        # Find crystals and calculate load capacitance
        crystals = [d for d in detections if 'Crystal' in d.class_name]
        if crystals:
            # Common frequencies for MCUs
            crystal_calc = electrical_analyzer.estimate_crystal_load_capacitance(16e6)  # 16MHz
            calculations['crystal_load_caps'] = crystal_calc

        # Microcontroller decoupling calculations
        mcus = [d for d in detections if any(x in d.class_name for x in ['Arduino', 'ATmega', 'ESP'])]
        if mcus:
            # Typical MCU: 50mA @ 5V, 1MHz switching
            decoupling_calc = electrical_analyzer.calculate_capacitor_decoupling(
                ic_current_a=0.05, voltage_v=5.0, switching_freq_hz=1e6
            )
            calculations['mcu_decoupling'] = decoupling_calc

        return calculations

    def _predict_circuit_behavior(self,
                                  device_type: str,
                                  functional_blocks: List[FunctionalBlock],
                                  detections: List[ComponentDetection]) -> Dict[str, Any]:
        """
        Predict circuit behavior and provide troubleshooting guidance.

        Domain knowledge from electrical engineering.
        """
        behavior = {}

        # Identify circuit types from functional blocks
        circuit_types = []
        for block in functional_blocks:
            if block.block_type == 'power_supply':
                circuit_types.append('power_supply')
            elif block.block_type == 'mcu_core':
                circuit_types.append('microcontroller')
            elif block.block_type == 'rf' or block.block_type == 'wireless':
                circuit_types.append('wireless')
            elif block.block_type == 'usb':
                circuit_types.append('usb_interface')

        # Get behavior predictions for each circuit type
        for ctype in set(circuit_types):
            behavior[ctype] = electrical_analyzer.predict_circuit_behavior(
                ctype, [d.class_name for d in detections]
            )

        # Add device-specific guidance
        if device_type == 'arduino':
            behavior['arduino_specific'] = {
                'programming': "Use USB or ICSP header for programming",
                'bootloader': "Press RESET before upload if auto-reset fails",
                'power_options': "Can power via USB (5V) or DC jack (7-12V)",
                'common_issues': [
                    "Sketch upload fails: Check drivers, try different USB cable",
                    "Not responding: Check bootloader, may need re-flashing",
                    "GPIO not working: Check if pin used by special function"
                ]
            }
        elif device_type == 'router':
            behavior['router_specific'] = {
                'firmware_access': "Check for UART/JTAG headers for console access",
                'reset_procedure': "Hold reset button 10+ seconds for factory reset",
                'common_issues': [
                    "No WiFi: Check antenna connections, flash memory corruption",
                    "Won't boot: Check power supply voltage/current",
                    "Ethernet not working: Check PHY chip and transformers"
                ]
            }

        return behavior

    def _empty_topology(self) -> CircuitTopology:
        """Return empty topology for error cases."""
        return CircuitTopology(
            device_type='unknown',
            device_confidence=0.0,
            functional_blocks=[],
            power_tree={},
            signal_paths=[],
            repair_complexity='unknown',
            repurpose_potential=0.0,
            modification_suggestions=[]
        )


# Singleton instance
circuit_intelligence = CircuitIntelligenceAnalyzer()
