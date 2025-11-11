#!/usr/bin/env python3
"""
Test Circuit Intelligence Layer (Standalone - No YOLO imports)

Tests the new circuit intelligence functionality with mock detections.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from loguru import logger
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from enum import Enum


# Define minimal classes to avoid YOLO imports
class DetectionMethod(Enum):
    YOLO = "yolo"
    CLASSICAL = "classical"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


@dataclass
class ComponentDetection:
    bbox: List[float]
    class_name: str
    confidence: float
    method: DetectionMethod
    metadata: Dict[str, Any]
    center: Optional[Tuple[float, float]] = None
    area: Optional[float] = None


# Now import the intelligence layer
from src.intelligence.circuit_analyzer import circuit_intelligence


def create_mock_arduino_detections():
    """Create mock detections for an Arduino board."""
    detections = [
        # ATmega328P MCU (center of board)
        ComponentDetection(
            bbox=[300, 200, 380, 280],
            class_name="Arduino-Uno",
            confidence=0.95,
            method=DetectionMethod.YOLO,
            metadata={"type": "microcontroller"}
        ),
        # USB connector
        ComponentDetection(
            bbox=[50, 100, 100, 150],
            class_name="USB-Connector",
            confidence=0.90,
            method=DetectionMethod.YOLO,
            metadata={"type": "connector"}
        ),
        # Voltage regulator near power
        ComponentDetection(
            bbox=[150, 80, 180, 110],
            class_name="Voltage-Regulator",
            confidence=0.88,
            method=DetectionMethod.YOLO,
            metadata={"type": "power"}
        ),
        # Capacitors near MCU (decoupling)
        ComponentDetection(
            bbox=[290, 190, 300, 200],
            class_name="Capacitor",
            confidence=0.85,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        ComponentDetection(
            bbox=[385, 195, 395, 205],
            class_name="Capacitor",
            confidence=0.87,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        # Capacitors near voltage regulator
        ComponentDetection(
            bbox=[140, 85, 148, 93],
            class_name="Capacitor",
            confidence=0.84,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        ComponentDetection(
            bbox=[185, 85, 193, 93],
            class_name="Capacitor",
            confidence=0.86,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        # Crystal oscillator near MCU
        ComponentDetection(
            bbox=[390, 240, 410, 250],
            class_name="Crystal",
            confidence=0.82,
            method=DetectionMethod.YOLO,
            metadata={"type": "timing"}
        ),
        # Resistors (pull-ups, LED current limiting)
        ComponentDetection(
            bbox=[100, 300, 105, 310],
            class_name="Resistor",
            confidence=0.80,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        ComponentDetection(
            bbox=[110, 300, 115, 310],
            class_name="Resistor",
            confidence=0.81,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        # LEDs
        ComponentDetection(
            bbox=[100, 320, 110, 330],
            class_name="LED",
            confidence=0.88,
            method=DetectionMethod.YOLO,
            metadata={"type": "indicator"}
        )
    ]
    return detections


def create_mock_router_detections():
    """Create mock detections for a WiFi router."""
    detections = [
        # ESP8266 WiFi module
        ComponentDetection(
            bbox=[250, 150, 350, 200],
            class_name="ESP8266",
            confidence=0.92,
            method=DetectionMethod.YOLO,
            metadata={"type": "wireless"}
        ),
        # Flash memory
        ComponentDetection(
            bbox=[380, 160, 420, 190],
            class_name="Flash-Memory",
            confidence=0.89,
            method=DetectionMethod.YOLO,
            metadata={"type": "storage"}
        ),
        # Ethernet connectors
        ComponentDetection(
            bbox=[50, 200, 100, 250],
            class_name="Ethernet-Connector",
            confidence=0.93,
            method=DetectionMethod.YOLO,
            metadata={"type": "connector"}
        ),
        ComponentDetection(
            bbox=[50, 260, 100, 310],
            class_name="Ethernet-Connector",
            confidence=0.91,
            method=DetectionMethod.YOLO,
            metadata={"type": "connector"}
        ),
        ComponentDetection(
            bbox=[50, 320, 100, 370],
            class_name="Ethernet-Connector",
            confidence=0.90,
            method=DetectionMethod.YOLO,
            metadata={"type": "connector"}
        ),
        # Power regulator
        ComponentDetection(
            bbox=[150, 100, 180, 120],
            class_name="Voltage-Regulator",
            confidence=0.87,
            method=DetectionMethod.YOLO,
            metadata={"type": "power"}
        ),
        # Capacitors for power filtering
        ComponentDetection(
            bbox=[140, 105, 148, 113],
            class_name="Capacitor",
            confidence=0.83,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        ),
        ComponentDetection(
            bbox=[185, 105, 193, 113],
            class_name="Capacitor",
            confidence=0.84,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"}
        )
    ]
    return detections


def test_intelligence_layer():
    """Test the circuit intelligence layer."""
    logger.info("=" * 60)
    logger.info("Testing Circuit Intelligence Layer")
    logger.info("=" * 60)

    # Test 1: Arduino board analysis
    logger.info("\n📟 Test 1: Arduino Board Analysis")
    logger.info("-" * 60)

    arduino_detections = create_mock_arduino_detections()
    image_dims = (640, 480)  # Standard image dimensions

    topology = circuit_intelligence.analyze_circuit(arduino_detections, image_dims)

    logger.info(f"✅ Device Type: {topology.device_type}")
    logger.info(f"   Confidence: {topology.device_confidence:.2f}")
    logger.info(f"   Repair Complexity: {topology.repair_complexity}")
    logger.info(f"   Repurpose Potential: {topology.repurpose_potential:.2f}")
    logger.info(f"\n📦 Functional Blocks: {len(topology.functional_blocks)}")
    for block in topology.functional_blocks:
        logger.info(f"   - {block.block_type}: {block.function}")
        logger.info(f"     Components: {len(block.components)}, Critical: {block.critical_level}")
        logger.info(f"     Capabilities: {', '.join(block.capabilities[:3])}")

    logger.info(f"\n⚡ Power Analysis:")
    logger.info(f"   Voltage Levels: {', '.join(topology.power_tree.get('voltage_levels', []))}")
    logger.info(f"   Can Tap Power: {topology.power_tree.get('can_tap_power', False)}")

    logger.info(f"\n🔧 Modification Suggestions:")
    for i, suggestion in enumerate(topology.modification_suggestions[:5], 1):
        logger.info(f"   {i}. {suggestion}")

    # Test 2: WiFi Router analysis
    logger.info("\n\n📡 Test 2: WiFi Router Analysis")
    logger.info("-" * 60)

    router_detections = create_mock_router_detections()

    topology = circuit_intelligence.analyze_circuit(router_detections, image_dims)

    logger.info(f"✅ Device Type: {topology.device_type}")
    logger.info(f"   Confidence: {topology.device_confidence:.2f}")
    logger.info(f"   Repair Complexity: {topology.repair_complexity}")
    logger.info(f"   Repurpose Potential: {topology.repurpose_potential:.2f}")
    logger.info(f"\n📦 Functional Blocks: {len(topology.functional_blocks)}")
    for block in topology.functional_blocks:
        logger.info(f"   - {block.block_type}: {block.function}")
        logger.info(f"     Components: {len(block.components)}, Critical: {block.critical_level}")

    logger.info(f"\n🔧 Modification Suggestions:")
    for i, suggestion in enumerate(topology.modification_suggestions[:5], 1):
        logger.info(f"   {i}. {suggestion}")

    # NEW: Show deep analysis
    logger.info(f"\n⚡ Power Budget Analysis:")
    if topology.power_budget:
        logger.info(f"   Total Power: {topology.power_budget['total_power_w']:.2f}W")
        logger.info(f"   Thermal Estimate: {topology.power_budget['thermal_estimate_c']:.1f}°C")
        if topology.power_budget['recommendations']:
            logger.info(f"   Recommendations:")
            for rec in topology.power_budget['recommendations'][:3]:
                logger.info(f"      - {rec}")

    logger.info(f"\n🔬 Voltage Rails:")
    for rail in topology.voltage_rails[:3]:
        logger.info(f"   {rail['voltage']}V rail: {rail['current_draw_a']:.3f}A / {rail['current_capacity_a']:.1f}A")
        logger.info(f"      Margin: {rail['margin_percent']:.0f}%, Safe to tap: {rail['safe_to_tap']}")

    logger.info(f"\n🧪 Test Points Available:")
    for comp, points in list(topology.test_points.items())[:3]:
        logger.info(f"   {comp}: {', '.join(points)}")

    logger.info(f"\n⚠️  Known Failure Modes:")
    for comp, modes in list(topology.failure_modes.items())[:3]:
        logger.info(f"   {comp}: {modes[0]}")

    logger.info(f"\n🔢 Electrical Calculations:")
    if topology.electrical_calculations:
        for calc_type, calc_data in list(topology.electrical_calculations.items())[:2]:
            logger.info(f"   {calc_type}: {calc_data}")

    logger.info(f"\n📋 Circuit Behavior Predictions:")
    if topology.circuit_behavior:
        for behavior_type in list(topology.circuit_behavior.keys())[:2]:
            behavior = topology.circuit_behavior[behavior_type]
            if 'function' in behavior:
                logger.info(f"   {behavior_type}: {behavior['function']}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Circuit Intelligence Layer Tests Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_intelligence_layer()
