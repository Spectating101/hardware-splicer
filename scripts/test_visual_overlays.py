#!/usr/bin/env python3
"""
Test Visual Overlay System

Tests the visual guidance overlays that make repair instructions visual.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
from loguru import logger

from src.intelligence.visual_overlay import visual_overlay_renderer, VisualOverlay, OverlayType
from src.intelligence.pin_detector import pin_detector, PinOrientation, ICDetectionResult, DetectedPin
from src.intelligence.connection_mapper import connection_mapper, PinConnection, CircuitSchematic
from src.intelligence.pinout_database import PackageType
from src.vision import ComponentDetection, DetectionMethod


def create_test_pcb_image() -> np.ndarray:
    """Create a synthetic PCB image for testing."""
    # Create green PCB background
    img = np.ones((600, 800, 3), dtype=np.uint8) * np.array([0, 100, 0], dtype=np.uint8)

    # Draw some components (black rectangles)
    # IC1 (Arduino/ATmega)
    cv2.rectangle(img, (300, 200), (500, 400), (50, 50, 50), -1)
    cv2.putText(img, "U1", (380, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # IC2 (USB chip)
    cv2.rectangle(img, (100, 200), (250, 280), (50, 50, 50), -1)
    cv2.putText(img, "U2", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Draw some traces (copper color)
    cv2.line(img, (250, 240), (300, 300), (100, 180, 200), 3)  # Trace 1
    cv2.line(img, (250, 260), (300, 320), (100, 180, 200), 3)  # Trace 2

    # Draw some pads/pins (circles)
    for i in range(0, 10):
        y = 210 + i * 20
        cv2.circle(img, (295, y), 4, (200, 200, 100), -1)  # Left side of IC1
        cv2.circle(img, (505, y), 4, (200, 200, 100), -1)  # Right side of IC1

    return img


def test_basic_overlays():
    """Test basic overlay rendering."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Basic Overlay Rendering")
    logger.info("="*60)

    img = create_test_pcb_image()

    # Test cut trace overlay
    cut_overlay = VisualOverlay(
        overlay_type=OverlayType.CUT_TRACE,
        position=(275, 300),
        label="TX-RX connection",
        color=visual_overlay_renderer.colors['cut']
    )

    result = visual_overlay_renderer.render_all_overlays(img, [cut_overlay])
    assert result.shape == img.shape, "Output shape mismatch"
    assert not np.array_equal(result, img), "Image should be modified"
    logger.info("✅ Cut trace overlay rendered")

    # Test desolder overlay
    desolder_overlay = VisualOverlay(
        overlay_type=OverlayType.DESOLDER_PIN,
        position=(295, 230),
        label="Pin 3 of U1",
        color=visual_overlay_renderer.colors['desolder']
    )

    result = visual_overlay_renderer.render_all_overlays(img, [desolder_overlay])
    assert not np.array_equal(result, img), "Image should be modified"
    logger.info("✅ Desolder overlay rendered")

    # Test measure point overlay
    measure_overlay = VisualOverlay(
        overlay_type=OverlayType.MEASURE_POINT,
        position=(295, 210),
        label="VCC (expect 5V)",
        color=visual_overlay_renderer.colors['measure']
    )

    result = visual_overlay_renderer.render_all_overlays(img, [measure_overlay])
    logger.info("✅ Measure point overlay rendered")

    # Test solder bridge overlay
    bridge_overlay = VisualOverlay(
        overlay_type=OverlayType.SOLDER_BRIDGE,
        position=(295, 250),
        secondary_position=(295, 270),
        label="GPIO0 to GND",
        color=visual_overlay_renderer.colors['bridge']
    )

    result = visual_overlay_renderer.render_all_overlays(img, [bridge_overlay])
    logger.info("✅ Solder bridge overlay rendered")

    # Test component highlight
    highlight_overlay = VisualOverlay(
        overlay_type=OverlayType.HIGHLIGHT_COMPONENT,
        position=(300, 200),
        bbox=(300, 200, 500, 400),
        label="ATmega328P",
        color=visual_overlay_renderer.colors['highlight']
    )

    result = visual_overlay_renderer.render_all_overlays(img, [highlight_overlay])
    logger.info("✅ Component highlight overlay rendered")

    # Test all overlays together
    all_overlays = [cut_overlay, desolder_overlay, measure_overlay, bridge_overlay, highlight_overlay]
    result = visual_overlay_renderer.render_all_overlays(img, all_overlays)
    assert not np.array_equal(result, img), "Image should be modified"
    logger.info(f"✅ All {len(all_overlays)} overlays rendered together")

    # Save test image
    output_path = Path(__file__).parent.parent / "test_output_overlays.jpg"
    cv2.imwrite(str(output_path), result)
    logger.info(f"✅ Test image saved to {output_path}")

    logger.info("✅ Basic Overlays: PASSED\n")


def test_helper_functions():
    """Test overlay creation helper functions."""
    logger.info("="*60)
    logger.info("TEST 2: Overlay Creation Helpers")
    logger.info("="*60)

    # Create mock IC detection
    pins = [
        DetectedPin(pin_number=1, position=(295, 210), confidence=0.7, detection_method="inference"),
        DetectedPin(pin_number=3, position=(295, 230), confidence=0.7, detection_method="inference"),
        DetectedPin(pin_number=7, position=(295, 270), confidence=0.7, detection_method="inference"),
    ]

    ic_detection = ICDetectionResult(
        part_number="ATMEGA328P",
        bbox=(300, 200, 500, 400),
        pin_count=28,
        package_type=PackageType.DIP,
        orientation=PinOrientation.UP,
        pins=pins,
        pin1_position=(295, 210),
        confidence=0.7
    )

    # Test desolder helper
    desolder_overlay = visual_overlay_renderer.create_desolder_pin_overlay(ic_detection, 3, "TXD pin")
    assert desolder_overlay is not None, "Desolder overlay creation failed"
    assert desolder_overlay.overlay_type == OverlayType.DESOLDER_PIN
    logger.info("✅ Desolder overlay helper works")

    # Test measure helper
    measure_overlay = visual_overlay_renderer.create_measure_point_overlay(ic_detection, 7, 5.0)
    assert measure_overlay is not None, "Measure overlay creation failed"
    assert "5.0V" in measure_overlay.label
    logger.info("✅ Measure overlay helper works")

    # Test bridge helper
    bridge_overlay = visual_overlay_renderer.create_solder_bridge_overlay(ic_detection, 1, 3)
    assert bridge_overlay is not None, "Bridge overlay creation failed"
    assert bridge_overlay.secondary_position is not None
    logger.info("✅ Bridge overlay helper works")

    # Test component highlight helper
    highlight_overlay = visual_overlay_renderer.create_component_highlight_overlay(ic_detection)
    assert highlight_overlay is not None, "Highlight overlay creation failed"
    assert highlight_overlay.bbox is not None
    logger.info("✅ Component highlight helper works")

    logger.info("✅ Helper Functions: PASSED\n")


def test_repair_sequence():
    """Test repair sequence generation."""
    logger.info("="*60)
    logger.info("TEST 3: Repair Sequence Generation")
    logger.info("="*60)

    img = create_test_pcb_image()

    # Create mock schematic
    pins = [
        DetectedPin(pin_number=1, position=(295, 210), confidence=0.7, detection_method="inference"),
        DetectedPin(pin_number=2, position=(295, 230), confidence=0.7, detection_method="inference"),
        DetectedPin(pin_number=3, position=(295, 250), confidence=0.7, detection_method="inference"),
    ]

    ic_detection = ICDetectionResult(
        part_number="ATMEGA328P",
        bbox=(300, 200, 500, 400),
        pin_count=28,
        package_type=PackageType.DIP,
        orientation=PinOrientation.UP,
        pins=pins,
        pin1_position=(295, 210),
        confidence=0.7
    )

    schematic = CircuitSchematic(
        ics=[ic_detection],
        connections=[],
        nets=[],
        power_rails={},
        ground_pins=[],
        unconnected_pins=[],
        confidence=0.7
    )

    # Define repair steps
    repair_steps = [
        {
            'type': 'measure',
            'ic_name': 'ATMEGA328P',
            'pin1': 1,
            'label': 'Check VCC voltage',
            'expected_voltage': 5.0
        },
        {
            'type': 'desolder',
            'ic_name': 'ATMEGA328P',
            'pin1': 2,
            'label': 'Remove pin 2'
        },
        {
            'type': 'bridge',
            'ic_name': 'ATMEGA328P',
            'pin1': 1,
            'pin2': 3,
            'label': 'Bridge power to pin 3'
        }
    ]

    # Generate sequence
    sequence = visual_overlay_renderer.create_repair_sequence_overlays(img, schematic, repair_steps)

    assert len(sequence) == 3, f"Expected 3 steps, got {len(sequence)}"
    logger.info(f"✅ Generated {len(sequence)} step images")

    # Save sequence
    output_dir = Path(__file__).parent.parent / "test_output"
    output_dir.mkdir(exist_ok=True)

    for i, step_img in enumerate(sequence):
        output_path = output_dir / f"repair_step_{i+1}.jpg"
        cv2.imwrite(str(output_path), step_img)
        logger.info(f"   Step {i+1} saved to {output_path}")

    logger.info("✅ Repair Sequence: PASSED\n")


def test_integration():
    """Test integration with connection mapper."""
    logger.info("="*60)
    logger.info("TEST 4: Integration with Connection Mapper")
    logger.info("="*60)

    img = create_test_pcb_image()

    # Create mock detections
    detections = [
        ComponentDetection(
            bbox=[300, 200, 500, 400],
            class_name="Arduino-Uno",
            confidence=0.95,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(400, 300)
        )
    ]

    # Map connections
    schematic = connection_mapper.map_connections(img, detections)

    logger.info(f"✅ Detected {len(schematic.ics)} ICs")

    if schematic.ics:
        # Create highlight for first IC
        ic = schematic.ics[0]
        highlight = visual_overlay_renderer.create_component_highlight_overlay(ic, "Target IC")

        # Add measure points for critical pins
        overlays = [highlight]
        critical_pins = [1, 7, 20]  # VCC, GND, AVCC
        for pin_num in critical_pins:
            measure = visual_overlay_renderer.create_measure_point_overlay(ic, pin_num)
            if measure:
                overlays.append(measure)

        # Render
        result = visual_overlay_renderer.render_all_overlays(img, overlays)

        # Save
        output_path = Path(__file__).parent.parent / "test_output_integrated.jpg"
        cv2.imwrite(str(output_path), result)
        logger.info(f"✅ Integrated overlay saved to {output_path}")

    logger.info("✅ Integration: PASSED\n")


def main():
    """Run all tests."""
    logger.info("\n" + "="*60)
    logger.info("VISUAL OVERLAY SYSTEM TEST")
    logger.info("Testing visual repair guidance")
    logger.info("="*60)

    try:
        test_basic_overlays()
        test_helper_functions()
        test_repair_sequence()
        test_integration()

        logger.info("\n" + "="*60)
        logger.info("✅ ALL VISUAL OVERLAY TESTS PASSED!")
        logger.info("="*60)
        logger.info("\nVisual guidance system ready!")
        logger.info("Repair instructions are now visual and easy to follow.")

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
