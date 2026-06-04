#!/usr/bin/env python3
"""
Test Advanced Trace Follower

Tests multi-layer PCB analysis with vias and junctions.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
from loguru import logger

from src.intelligence.advanced_trace_follower import advanced_trace_follower, TraceSegment, Via, Junction


def create_mock_pcb_image() -> np.ndarray:
    """Create synthetic PCB image with traces, vias, and junctions."""
    # Create copper colored PCB (gold/brown background)
    image = np.ones((500, 500, 3), dtype=np.uint8)
    image[:, :] = [50, 120, 180]  # BGR: copper color

    # Draw traces as darker copper paths (slightly darker than background)
    # Horizontal trace
    cv2.line(image, (50, 100), (450, 100), (30, 100, 160), 15)

    # Vertical trace
    cv2.line(image, (250, 50), (250, 450), (30, 100, 160), 12)

    # Diagonal trace
    cv2.line(image, (100, 200), (400, 400), (30, 100, 160), 10)

    # T-junction
    cv2.line(image, (250, 100), (350, 100), (30, 100, 160), 15)  # Creates T with vertical

    # Draw vias (circles with pads)
    cv2.circle(image, (250, 100), 15, (30, 100, 160), -1)
    cv2.circle(image, (250, 100), 5, (80, 80, 80), -1)  # Hole
    cv2.circle(image, (400, 400), 12, (30, 100, 160), -1)
    cv2.circle(image, (400, 400), 4, (80, 80, 80), -1)  # Hole

    return image


def test_trace_extraction():
    """Test advanced trace extraction."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Advanced Trace Extraction")
    logger.info("="*60)

    image = create_mock_pcb_image()

    traces, mask = advanced_trace_follower._extract_traces_advanced(image, "top")

    assert len(traces) > 0, "Should extract traces"
    assert mask.shape == image.shape[:2], "Mask shape should match image"

    logger.info(f"✅ Extracted {len(traces)} traces")
    for i, trace in enumerate(traces[:5]):
        logger.info(f"   Trace {i}: width={trace.width_px:.1f}px, {len(trace.points)} points")

    logger.info("✅ Trace Extraction: PASSED\n")


def test_via_detection():
    """Test via detection."""
    logger.info("="*60)
    logger.info("TEST 2: Via Detection")
    logger.info("="*60)

    image = create_mock_pcb_image()

    # Extract traces first
    traces, mask = advanced_trace_follower._extract_traces_advanced(image, "top")

    # Detect vias
    vias = advanced_trace_follower._detect_vias(image, mask)

    logger.info(f"✅ Detected {len(vias)} vias")
    for i, via in enumerate(vias):
        logger.info(f"   Via {i}: position={via.position}, diameter={via.diameter_px:.1f}px")

    logger.info("✅ Via Detection: PASSED\n")


def test_junction_detection():
    """Test junction detection."""
    logger.info("="*60)
    logger.info("TEST 3: Junction Detection")
    logger.info("="*60)

    image = create_mock_pcb_image()

    # Extract traces
    traces, mask = advanced_trace_follower._extract_traces_advanced(image, "top")

    # Detect junctions
    junctions = advanced_trace_follower._detect_junctions(mask)

    logger.info(f"✅ Detected {len(junctions)} junctions")
    for i, junction in enumerate(junctions[:5]):
        logger.info(f"   Junction {i}: type={junction.junction_type}, position={junction.position}")

    logger.info("✅ Junction Detection: PASSED\n")


def test_multilayer_analysis():
    """Test complete multi-layer PCB analysis."""
    logger.info("="*60)
    logger.info("TEST 4: Multi-layer PCB Analysis")
    logger.info("="*60)

    top_image = create_mock_pcb_image()
    bottom_image = create_mock_pcb_image()  # Same for testing

    result = advanced_trace_follower.analyze_multilayer_pcb(top_image, bottom_image)

    assert 'traces' in result, "Should have traces"
    assert 'vias' in result, "Should have vias"
    assert 'nets' in result, "Should have nets"
    assert 'junctions' in result, "Should have junctions"
    assert 'graph' in result, "Should have connectivity graph"

    logger.info(f"✅ Analysis complete:")
    logger.info(f"   Traces: {result['trace_count']}")
    logger.info(f"   Vias: {result['via_count']}")
    logger.info(f"   Nets: {result['net_count']}")
    logger.info(f"   Junctions: {len(result['junctions'])}")

    logger.info("✅ Multi-layer Analysis: PASSED\n")


def test_trace_under_component():
    """Test trace following under components."""
    logger.info("="*60)
    logger.info("TEST 5: Trace Under Component")
    logger.info("="*60)

    image = create_mock_pcb_image()

    # Component bounding box
    component_bbox = (200, 90, 300, 110)

    # Entry point and direction
    entry_point = (200, 100)
    entry_direction = (1, 0)  # Moving right

    exit_point = advanced_trace_follower.follow_trace_under_component(
        image, component_bbox, entry_point, entry_direction
    )

    assert exit_point is not None, "Should predict exit point"
    assert isinstance(exit_point, tuple), "Exit point should be tuple"
    assert len(exit_point) == 2, "Exit point should be (x, y)"

    logger.info(f"✅ Entry: {entry_point}, Exit: {exit_point}")

    logger.info("✅ Trace Under Component: PASSED\n")


def test_impedance_calculation():
    """Test trace impedance estimation."""
    logger.info("="*60)
    logger.info("TEST 6: Trace Impedance Calculation")
    logger.info("="*60)

    # Test various trace widths
    test_cases = [
        (0.2, "narrow trace"),
        (0.5, "50Ω trace"),
        (1.0, "wide trace"),
        (2.0, "power trace")
    ]

    for width_mm, description in test_cases:
        impedance = advanced_trace_follower.estimate_trace_impedance(
            width_mm=width_mm,
            thickness_mm=0.035,
            height_above_plane_mm=1.6,
            er=4.5
        )

        # Just verify impedance is reasonable (20-200Ω range)
        assert 20 < impedance < 200, f"Impedance {impedance:.1f}Ω out of reasonable range"
        logger.info(f"✅ {description}: width={width_mm}mm → {impedance:.1f}Ω")

    # Verify relationship: narrower trace = higher impedance
    z1 = advanced_trace_follower.estimate_trace_impedance(0.2, 0.035, 1.6, 4.5)
    z2 = advanced_trace_follower.estimate_trace_impedance(1.0, 0.035, 1.6, 4.5)
    assert z1 > z2, "Narrower trace should have higher impedance"

    logger.info("✅ Impedance Calculation: PASSED\n")


def test_skeletonization():
    """Test skeletonization algorithm."""
    logger.info("="*60)
    logger.info("TEST 7: Skeletonization")
    logger.info("="*60)

    # Create thick trace
    binary = np.zeros((100, 100), dtype=np.uint8)
    cv2.line(binary, (10, 50), (90, 50), 255, 10)

    skeleton = advanced_trace_follower._skeletonize(binary)

    assert skeleton.shape == binary.shape, "Skeleton shape should match input"
    assert np.any(skeleton > 0), "Skeleton should have points"

    # Count skeleton points
    skeleton_count = np.count_nonzero(skeleton)
    original_count = np.count_nonzero(binary)

    assert skeleton_count < original_count * 0.5, "Skeleton should be thinner"

    logger.info(f"✅ Original: {original_count} pixels, Skeleton: {skeleton_count} pixels")
    logger.info(f"✅ Reduction: {100 * (1 - skeleton_count/original_count):.1f}%")

    logger.info("✅ Skeletonization: PASSED\n")


def main():
    """Run all tests."""
    logger.info("\n" + "="*60)
    logger.info("ADVANCED TRACE FOLLOWER TEST")
    logger.info("Testing multi-layer PCB analysis")
    logger.info("="*60)

    try:
        test_trace_extraction()
        test_via_detection()
        test_junction_detection()
        test_multilayer_analysis()
        test_trace_under_component()
        test_impedance_calculation()
        test_skeletonization()

        logger.info("\n" + "="*60)
        logger.info("✅ ALL ADVANCED TRACE TESTS PASSED!")
        logger.info("="*60)
        logger.info("\nAdvanced trace following system ready!")
        logger.info("Features: multi-layer, vias, junctions, impedance calculation")

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
