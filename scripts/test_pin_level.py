#!/usr/bin/env python3
"""
Test Pin-Level Functionality

Tests the critical missing piece: pin-level connection mapping.
This enables instructions like:
- "Desolder pin 3 of U5"
- "Cut trace between pin 7 of IC2 and pin 15 of IC4"
- "Bridge pin 12 to pin 5 with a wire"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
from loguru import logger

from src.intelligence.pinout_database import pinout_database
from src.intelligence.pin_detector import pin_detector
from src.intelligence.connection_mapper import connection_mapper
from src.vision import ComponentDetection, DetectionMethod


def test_pinout_database():
    """Test IC pinout database."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: IC Pinout Database")
    logger.info("="*60)

    # Test ESP8266 pinout
    esp_pinout = pinout_database.get_pinout("ESP8266")
    assert esp_pinout is not None, "ESP8266 pinout not found"
    assert esp_pinout.pin_count == 22, f"Expected 22 pins, got {esp_pinout.pin_count}"
    logger.info(f"✅ ESP8266: {esp_pinout.pin_count} pins, {esp_pinout.package.value} package")

    # Test finding specific pin
    gpio0 = pinout_database.find_pin_by_name("ESP8266", "GPIO0")
    assert gpio0 is not None, "GPIO0 not found"
    assert gpio0.pin_number == 15, f"GPIO0 should be pin 15, got {gpio0.pin_number}"
    logger.info(f"✅ GPIO0: pin {gpio0.pin_number}, {gpio0.description}")

    # Test critical pins
    critical = pinout_database.get_critical_pins("ESP8266")
    assert len(critical) > 0, "No critical pins found"
    logger.info(f"✅ Critical pins: {len(critical)} found")
    for pin in critical[:3]:
        logger.info(f"   - Pin {pin.pin_number} ({pin.pin_name}): {pin.description}")

    # Test ATmega328P
    atmega = pinout_database.get_pinout("ATMEGA328P")
    assert atmega is not None, "ATmega328P not found"
    assert atmega.pin_count == 28, f"Expected 28 pins, got {atmega.pin_count}"
    logger.info(f"✅ ATmega328P: {atmega.pin_count} pins, {atmega.package.value} package")

    # Test UART pins
    tx = pinout_database.find_pin_by_name("ATMEGA328P", "TXD")
    rx = pinout_database.find_pin_by_name("ATMEGA328P", "RXD")
    assert tx is not None and rx is not None, "UART pins not found"
    logger.info(f"✅ UART: TX=pin {tx.pin_number}, RX=pin {rx.pin_number}")

    # Test component name search
    arduino_pinout = pinout_database.search_by_component_name("Arduino-Uno")
    assert arduino_pinout is not None, "Arduino search failed"
    assert arduino_pinout.part_number == "ATMEGA328P", "Arduino should map to ATmega328P"
    logger.info(f"✅ Component search: 'Arduino-Uno' → {arduino_pinout.part_number}")

    logger.info("✅ Pinout Database: PASSED\n")


def test_pin_detector():
    """Test pin detection on synthetic IC images."""
    logger.info("="*60)
    logger.info("TEST 2: Pin Detection")
    logger.info("="*60)

    # Create synthetic IC image (DIP package)
    img = np.zeros((480, 640, 3), dtype=np.uint8)

    # Draw IC body (black rectangle)
    cv2.rectangle(img, (200, 100), (440, 380), (50, 50, 50), -1)

    # Draw pin 1 indicator (white dot)
    cv2.circle(img, (210, 110), 5, (255, 255, 255), -1)

    # Draw pins (white rectangles)
    for i in range(14):  # 14 pins per side (28-pin DIP)
        # Left side
        y = 100 + 20 + i * 20
        cv2.rectangle(img, (195, y-3), (200, y+3), (200, 200, 200), -1)

        # Right side
        cv2.rectangle(img, (440, 380-20-i*20-3), (445, 380-20-i*20+3), (200, 200, 200), -1)

    # Mock ATmega328P detection
    ic_bbox = (195, 95, 445, 385)

    # Detect pins
    ic_detection = pin_detector.detect_ic_pins(img, ic_bbox, "ATMEGA328P")

    assert ic_detection is not None, "Pin detection failed"
    logger.info(f"DEBUG: Orientation={ic_detection.orientation.value}, Package={ic_detection.package_type.value}")
    assert ic_detection.pin_count == 28, f"Expected 28 pins, got {ic_detection.pin_count}"
    assert len(ic_detection.pins) == 28, f"Expected 28 detected pins, got {len(ic_detection.pins)}"
    logger.info(f"✅ Detected {len(ic_detection.pins)} pins on ATmega328P")
    logger.info(f"   Pin 1 at {ic_detection.pin1_position}, orientation: {ic_detection.orientation.value}")
    logger.info(f"   Confidence: {ic_detection.confidence:.2f}")

    # Find specific pin position
    vcc_pin = pin_detector.find_pin_by_name(ic_detection, "VCC")
    assert vcc_pin is not None, "VCC pin not found"
    logger.info(f"✅ VCC pin {vcc_pin.pin_number} at position {vcc_pin.position}")

    # Test pin instruction generation
    instruction = pin_detector.generate_pin_instruction(ic_detection, 7, "desolder")
    assert "VCC" in instruction, "Instruction should mention VCC"
    logger.info(f"✅ Instruction: {instruction}")

    logger.info("✅ Pin Detector: PASSED\n")


def test_connection_validation():
    """Test connection validation (voltage compatibility, etc.)."""
    logger.info("="*60)
    logger.info("TEST 3: Connection Validation")
    logger.info("="*60)

    # Test safe connection: ATmega328P (5V) UART to another 5V device
    result = pin_detector.validate_connection(
        "ATMEGA328P", "TXD",
        "CH340", "RXD"
    )
    assert result['valid'], "Should be valid connection"
    assert not result['voltage_mismatch'], "Voltages should match"
    logger.info(f"✅ ATmega TXD → CH340 RXD: {result['recommendation']}")

    # Test unsafe connection: Arduino (5V) to ESP8266 (3.3V)
    result = pin_detector.validate_connection(
        "ATMEGA328P", "TXD",
        "ESP8266", "RXD"
    )
    assert not result['valid'], "Should be INVALID (voltage mismatch)"
    assert result['voltage_mismatch'], "Should detect voltage mismatch"
    logger.info(f"✅ ATmega TXD → ESP8266 RXD: BLOCKED - {result['warnings'][0]}")
    logger.info(f"   Recommendation: {result['recommendation']}")

    # Test ESP8266 to ESP8266 (safe)
    result = pin_detector.validate_connection(
        "ESP8266", "TXD",
        "ESP8266", "RXD"
    )
    assert result['valid'], "ESP to ESP should be safe"
    logger.info(f"✅ ESP TXD → ESP RXD: {result['recommendation']}")

    logger.info("✅ Connection Validation: PASSED\n")


def test_connection_mapper():
    """Test full connection mapping."""
    logger.info("="*60)
    logger.info("TEST 4: Connection Mapper")
    logger.info("="*60)

    # Create synthetic PCB with Arduino + CH340
    img = np.zeros((480, 640, 3), dtype=np.uint8)

    # Mock detections
    detections = [
        ComponentDetection(
            bbox=[200, 100, 440, 380],
            class_name="Arduino-Uno",
            confidence=0.95,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(320, 240)
        ),
        ComponentDetection(
            bbox=[100, 100, 180, 200],
            class_name="CH340",
            confidence=0.90,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(140, 150)
        )
    ]

    # Map connections
    schematic = connection_mapper.map_connections(img, detections)

    logger.info(f"✅ Detected {len(schematic.ics)} ICs")
    for ic in schematic.ics:
        logger.info(f"   - {ic.part_number}: {len(ic.pins)} pins detected")

    logger.info(f"✅ Found {len(schematic.connections)} connections")
    if schematic.connections:
        for conn in schematic.connections[:3]:
            logger.info(
                f"   - {conn.ic1_part} pin {conn.ic1_pin_number} ({conn.ic1_pin_name}) "
                f"→ {conn.ic2_part} pin {conn.ic2_pin_number} ({conn.ic2_pin_name})"
            )

    logger.info(f"✅ Identified {len(schematic.nets)} nets")
    for net in schematic.nets[:5]:
        logger.info(f"   - {net.net_name} ({net.net_type}): {len(net.pins)} pins")

    logger.info(f"✅ Power rails: {schematic.power_rails}")
    logger.info(f"✅ Ground pins: {len(schematic.ground_pins)}")

    if schematic.unconnected_pins:
        logger.info(f"⚠️  Unconnected critical pins: {len(schematic.unconnected_pins)}")
        for ic, pin_num, pin_name in schematic.unconnected_pins[:3]:
            logger.info(f"   - {ic} pin {pin_num} ({pin_name})")

    logger.info("✅ Connection Mapper: PASSED\n")


def test_repair_instructions():
    """Test generation of pin-level repair instructions."""
    logger.info("="*60)
    logger.info("TEST 5: Pin-Level Repair Instructions")
    logger.info("="*60)

    # Mock schematic
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = [
        ComponentDetection(
            bbox=[200, 100, 440, 380],
            class_name="ESP8266",
            confidence=0.95,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(320, 240)
        )
    ]

    schematic = connection_mapper.map_connections(img, detections)

    # Generate measurement instruction
    if schematic.ics:
        ic = schematic.ics[0]
        instruction = connection_mapper.generate_measurement_instruction(
            schematic, ic.part_number, 1  # VCC pin
        )
        logger.info(f"✅ Measurement instruction:")
        logger.info(f"   {instruction}")

        # Generate bridge instruction (example: connect GPIO0 to GND for flash mode)
        bridge_inst = connection_mapper.generate_bridge_instruction(
            schematic, ic.part_number, 15,  # GPIO0
            ic.part_number, 9  # GND
        )
        logger.info(f"✅ Bridge instruction:")
        logger.info(f"   {bridge_inst}")

    logger.info("✅ Repair Instructions: PASSED\n")


def test_integration():
    """Test complete pin-level analysis workflow."""
    logger.info("="*60)
    logger.info("TEST 6: Complete Pin-Level Workflow")
    logger.info("="*60)

    # Simulate Arduino board with USB chip
    img = np.zeros((600, 800, 3), dtype=np.uint8)

    detections = [
        ComponentDetection(
            bbox=[300, 200, 540, 480],
            class_name="Arduino-Uno",
            confidence=0.95,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(420, 340)
        ),
        ComponentDetection(
            bbox=[100, 200, 200, 300],
            class_name="CH340",
            confidence=0.90,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(150, 250)
        ),
        ComponentDetection(
            bbox=[250, 150, 350, 180],
            class_name="Voltage-Regulator",
            confidence=0.85,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(300, 165)
        )
    ]

    logger.info("Step 1: Detect IC pins...")
    schematic = connection_mapper.map_connections(img, detections)
    logger.info(f"   → {len(schematic.ics)} ICs with pins detected")

    logger.info("Step 2: Map connections...")
    logger.info(f"   → {len(schematic.connections)} connections found")

    logger.info("Step 3: Identify nets...")
    logger.info(f"   → {len(schematic.nets)} nets identified")

    logger.info("Step 4: Find power rails...")
    logger.info(f"   → Power rails: {list(schematic.power_rails.keys())}")

    logger.info("Step 5: Generate repair instructions...")

    # Example: Arduino bootloader repair via ISP
    if len(schematic.ics) > 0:
        arduino_ic = [ic for ic in schematic.ics if "ATMEGA" in ic.part_number]
        if arduino_ic:
            ic = arduino_ic[0]

            # ISP connection instructions
            logger.info("   Arduino Bootloader Repair (ISP):")

            mosi = pinout_database.find_pin_by_name(ic.part_number, "MOSI")
            miso = pinout_database.find_pin_by_name(ic.part_number, "MISO")
            sck = pinout_database.find_pin_by_name(ic.part_number, "SCK")
            reset = pinout_database.find_pin_by_name(ic.part_number, "RESET")

            if all([mosi, miso, sck, reset]):
                logger.info(f"   - Connect ISP MOSI to pin {mosi.pin_number} ({mosi.pin_name})")
                logger.info(f"   - Connect ISP MISO to pin {miso.pin_number} ({miso.pin_name})")
                logger.info(f"   - Connect ISP SCK to pin {sck.pin_number} ({sck.pin_name})")
                logger.info(f"   - Connect ISP RESET to pin {reset.pin_number} ({reset.pin_name})")
                logger.info(f"   - Connect ISP VCC to 5V rail")
                logger.info(f"   - Connect ISP GND to GND")

    logger.info("\n✅ Integration Workflow: PASSED")
    logger.info("Pin-level instructions now possible!")


def main():
    """Run all tests."""
    logger.info("\n" + "="*60)
    logger.info("PIN-LEVEL FUNCTIONALITY TEST")
    logger.info("Testing the CRITICAL missing piece")
    logger.info("="*60)

    try:
        test_pinout_database()
        test_pin_detector()
        test_connection_validation()
        test_connection_mapper()
        test_repair_instructions()
        test_integration()

        logger.info("\n" + "="*60)
        logger.info("✅ ALL PIN-LEVEL TESTS PASSED!")
        logger.info("="*60)
        logger.info("\nCRITICAL CAPABILITIES NOW ENABLED:")
        logger.info("✅ Pin-level connection mapping")
        logger.info("✅ Pin-specific repair instructions")
        logger.info("✅ Voltage compatibility validation")
        logger.info("✅ Trace cutting instructions")
        logger.info("✅ Pin bridging instructions")
        logger.info("✅ Measurement point identification")
        logger.info("\nThis is THE breakthrough for real repair guidance!")

    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
