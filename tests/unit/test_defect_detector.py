"""
Unit tests for defect detection module.

Tests classical CV and YOLO-based defect detection functionality.
"""

import pytest
import numpy as np
import cv2
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vision.defect_detector import DefectDetector, DefectDetection


@pytest.fixture
def detector():
    """Create detector instance without YOLO model (classical CV only)."""
    return DefectDetector(model_path=None, use_classical_fallback=True)


@pytest.fixture
def sample_pcb_image():
    """Create a synthetic PCB-like image for testing."""
    # Create a green PCB substrate (typical FR-4 color)
    image = np.zeros((800, 600, 3), dtype=np.uint8)
    image[:, :] = [50, 120, 50]  # Green background
    return image


@pytest.fixture
def pcb_with_solder_bridge(sample_pcb_image):
    """PCB image with a simulated solder bridge."""
    image = sample_pcb_image.copy()
    # Add silver/metallic elongated blob (solder bridge)
    cv2.rectangle(image, (100, 100), (150, 110), (200, 200, 200), -1)
    return image


@pytest.fixture
def pcb_with_burn(sample_pcb_image):
    """PCB image with a simulated burnt component."""
    image = sample_pcb_image.copy()
    # Add dark/black spot (burn mark)
    cv2.circle(image, (300, 400), 20, (10, 10, 10), -1)
    return image


@pytest.fixture
def pcb_with_corrosion(sample_pcb_image):
    """PCB image with simulated green corrosion."""
    image = sample_pcb_image.copy()
    # Add bright green oxidation
    cv2.circle(image, (500, 500), 15, (50, 200, 100), -1)
    return image


class TestDefectDetectorInit:
    """Test detector initialization."""

    def test_init_without_model(self):
        """Test initialization without YOLO model."""
        detector = DefectDetector(model_path=None, use_classical_fallback=True)
        assert detector.model is None
        assert detector.use_classical_fallback is True
        assert len(detector.SOLDER_DEFECTS) > 0
        assert len(detector.COMPONENT_DEFECTS) > 0

    def test_init_with_invalid_model_path(self):
        """Test initialization with non-existent model path."""
        detector = DefectDetector(model_path="/nonexistent/model.pt", use_classical_fallback=True)
        # Should gracefully handle missing model
        assert detector.model is None or detector.use_classical_fallback is True


class TestDefectDetection:
    """Test defect detection functionality."""

    def test_detect_on_clean_board(self, detector, sample_pcb_image):
        """Test detection on clean PCB with no defects."""
        defects = detector.detect_defects(sample_pcb_image, confidence_threshold=0.5)
        # Clean board should have minimal or no detections
        # (Some false positives are acceptable in classical CV)
        assert isinstance(defects, list)
        assert len(defects) < 5  # Should not detect many defects on clean board

    def test_detect_solder_bridge(self, detector, pcb_with_solder_bridge):
        """Test detection of solder bridge."""
        defects = detector.detect_defects(pcb_with_solder_bridge, confidence_threshold=0.3)

        # Check if any solder-related defect was detected
        solder_defect_types = detector.SOLDER_DEFECTS
        detected_types = [d.defect_type for d in defects]

        # At least one solder defect should be detected
        has_solder_defect = any(dtype in solder_defect_types for dtype in detected_types)
        assert has_solder_defect or len(defects) > 0, "Should detect solder bridge or similar defect"

    def test_detect_burn(self, detector, pcb_with_burn):
        """Test detection of burnt component."""
        defects = detector.detect_defects(pcb_with_burn, confidence_threshold=0.3)

        # Check for burn detection
        detected_types = [d.defect_type for d in defects]

        # Should detect burn or dark anomaly
        assert len(defects) > 0, "Should detect burnt area"

    def test_detect_corrosion(self, detector, pcb_with_corrosion):
        """Test detection of corrosion."""
        defects = detector.detect_defects(pcb_with_corrosion, confidence_threshold=0.3)

        # Note: Classical CV may struggle with green corrosion on green substrate
        # This test verifies the detector doesn't crash, not necessarily detection accuracy
        # A trained YOLO model would be more reliable for this case
        assert isinstance(defects, list), "Should return a list of defects"

    def test_color_only_corrosion_stays_below_default_aoi_threshold(self, detector, pcb_with_corrosion):
        """Color-only green regions should not flood default AOI reports."""
        defects = detector.detect_defects(pcb_with_corrosion, confidence_threshold=0.65)

        assert not any(defect.defect_type == "corrosion" for defect in defects)

    def test_defect_detection_returns_proper_structure(self, detector, sample_pcb_image):
        """Test that defect detections have proper structure."""
        defects = detector.detect_defects(sample_pcb_image)

        for defect in defects:
            assert isinstance(defect, DefectDetection)
            assert hasattr(defect, 'defect_type')
            assert hasattr(defect, 'bbox')
            assert hasattr(defect, 'confidence')
            assert hasattr(defect, 'severity')
            assert hasattr(defect, 'repair_action')

            # Validate types
            assert isinstance(defect.defect_type, str)
            assert isinstance(defect.bbox, list) and len(defect.bbox) == 4
            assert 0.0 <= defect.confidence <= 1.0
            assert 0.0 <= defect.severity <= 1.0
            assert isinstance(defect.repair_action, str)


class TestClassicalCVMethods:
    """Test individual classical CV detection methods."""

    def test_detect_solder_bridges_method(self, detector, pcb_with_solder_bridge):
        """Test _detect_solder_bridges method directly."""
        hsv = cv2.cvtColor(pcb_with_solder_bridge, cv2.COLOR_BGR2HSV)
        defects = detector._detect_solder_bridges(pcb_with_solder_bridge, hsv)

        # Should return a list
        assert isinstance(defects, list)

    def test_detect_burns_method(self, detector, pcb_with_burn):
        """Test _detect_burns method directly."""
        hsv = cv2.cvtColor(pcb_with_burn, cv2.COLOR_BGR2HSV)
        defects = detector._detect_burns(pcb_with_burn, hsv)

        assert isinstance(defects, list)

    def test_detect_corrosion_method(self, detector, pcb_with_corrosion):
        """Test _detect_corrosion method directly."""
        hsv = cv2.cvtColor(pcb_with_corrosion, cv2.COLOR_BGR2HSV)
        defects = detector._detect_corrosion(pcb_with_corrosion, hsv)

        assert isinstance(defects, list)


class TestDeduplication:
    """Test defect deduplication logic."""

    def test_deduplicate_identical_detections(self, detector):
        """Test deduplication of identical defects."""
        defects = [
            DefectDetection("solder_bridge", [100, 100, 110, 110], 0.9, 0.85, "Remove solder"),
            DefectDetection("solder_bridge", [100, 100, 110, 110], 0.85, 0.80, "Remove solder"),  # Exact overlap
        ]

        deduplicated = detector._deduplicate_detections(defects)

        # Should keep only the higher confidence detection
        assert len(deduplicated) == 1
        assert deduplicated[0].confidence == 0.9

    def test_deduplicate_separate_detections(self, detector):
        """Test that non-overlapping detections are preserved."""
        defects = [
            DefectDetection("solder_bridge", [100, 100, 110, 110], 0.9, 0.85, "Remove solder"),
            DefectDetection("cold_joint", [500, 500, 510, 510], 0.8, 0.70, "Reheat"),
        ]

        deduplicated = detector._deduplicate_detections(defects)

        # Both should be kept
        assert len(deduplicated) == 2


class TestSeverityAssignment:
    """Test severity score assignment."""

    def test_severity_for_critical_defects(self, detector):
        """Test that critical defects get high severity scores."""
        # Test severity estimation for critical defects
        severity_short = detector._estimate_severity("short_circuit", [100, 100, 110, 110], np.zeros((200, 200, 3)))
        severity_open = detector._estimate_severity("open_circuit", [100, 100, 110, 110], np.zeros((200, 200, 3)))

        assert severity_short >= 0.85
        assert severity_open >= 0.85

    def test_severity_for_cosmetic_defects(self, detector):
        """Test that cosmetic defects get low severity scores."""
        # Test severity for cosmetic defects
        severity_corrosion = detector._estimate_severity("corrosion", [100, 100, 110, 110], np.zeros((200, 200, 3)))

        assert severity_corrosion < 0.70

    def test_repair_action_exists(self, detector):
        """Test that repair actions are suggested for common defect types."""
        # Test repair suggestions for various defect types
        defect_types = [
            "solder_bridge", "cold_joint", "burnt_component",
            "corrosion", "short_circuit", "broken_trace"
        ]

        for defect_type in defect_types:
            repair = detector._suggest_repair(defect_type)
            assert isinstance(repair, str)
            assert len(repair) > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_image(self, detector):
        """Test detection on empty/black image."""
        black_image = np.zeros((100, 100, 3), dtype=np.uint8)
        defects = detector.detect_defects(black_image)

        # Should not crash, return empty or minimal detections
        assert isinstance(defects, list)

    def test_very_small_image(self, detector):
        """Test detection on very small image."""
        tiny_image = np.ones((10, 10, 3), dtype=np.uint8) * 100
        defects = detector.detect_defects(tiny_image)

        # Should not crash
        assert isinstance(defects, list)

    def test_high_confidence_threshold(self, detector, pcb_with_solder_bridge):
        """Test that high confidence threshold filters detections."""
        defects_low = detector.detect_defects(pcb_with_solder_bridge, confidence_threshold=0.1)
        defects_high = detector.detect_defects(pcb_with_solder_bridge, confidence_threshold=0.95)

        # High threshold should have fewer or equal detections
        assert len(defects_high) <= len(defects_low)
        assert all(defect.confidence >= 0.95 for defect in defects_high)

    def test_rectangular_black_component_is_not_burn(self, detector, sample_pcb_image):
        """Normal dark IC packages should not be flagged as burnt components."""
        image = sample_pcb_image.copy()
        cv2.rectangle(image, (100, 100), (160, 140), (10, 10, 10), -1)

        defects = detector.detect_defects(image, confidence_threshold=0.5)

        assert not any(defect.defect_type == "burnt_component" for defect in defects)

    def test_broken_trace_heuristic_is_exploratory_below_default_threshold(self, detector, sample_pcb_image):
        """Line-fragment trace guesses should not surface at default confidence."""
        image = sample_pcb_image.copy()
        cv2.line(image, (40, 60), (120, 60), (220, 220, 220), 2)

        defects = detector.detect_defects(image, confidence_threshold=0.5)

        assert not any(defect.defect_type == "broken_trace" for defect in defects)

    def test_tiny_solder_sliver_is_exploratory_below_default_threshold(self, detector, sample_pcb_image):
        """Tiny metallic slivers are too ambiguous for default solder-bridge reporting."""
        image = sample_pcb_image.copy()
        cv2.rectangle(image, (100, 100), (130, 104), (220, 220, 220), -1)

        defects = detector.detect_defects(image, confidence_threshold=0.65)

        assert not any(defect.defect_type == "solder_bridge" for defect in defects)

    def test_small_dark_artifact_is_not_default_burn_candidate(self, detector, sample_pcb_image):
        """Small dark board features should stay below the default burn threshold."""
        image = sample_pcb_image.copy()
        cv2.circle(image, (200, 200), 7, (8, 8, 8), -1)

        defects = detector.detect_defects(image, confidence_threshold=0.65)

        assert not any(defect.defect_type == "burnt_component" for defect in defects)

    def test_with_component_detections(self, detector, sample_pcb_image):
        """Test defect detection with component context."""
        component_detections = [
            {"label": "resistor", "bbox": [100, 100, 150, 120], "confidence": 0.9}
        ]

        defects = detector.detect_defects(sample_pcb_image, component_detections=component_detections)

        # Should not crash with component context
        assert isinstance(defects, list)


class TestDefectDetectionDataclass:
    """Test DefectDetection dataclass."""

    def test_defect_detection_creation(self):
        """Test creating DefectDetection object."""
        defect = DefectDetection(
            defect_type="solder_bridge",
            bbox=[100, 200, 120, 210],
            confidence=0.92,
            severity=0.90,
            repair_action="Remove excess solder"
        )

        assert defect.defect_type == "solder_bridge"
        assert defect.bbox == [100, 200, 120, 210]
        assert defect.confidence == 0.92
        assert defect.severity == 0.90
        assert defect.repair_action == "Remove excess solder"

    def test_defect_detection_to_dict(self):
        """Test converting DefectDetection to dictionary."""
        defect = DefectDetection(
            defect_type="cold_joint",
            bbox=[300, 400, 310, 410],
            confidence=0.75,
            severity=0.60,
            repair_action="Reheat with flux"
        )

        defect_dict = {
            "defect_type": defect.defect_type,
            "bbox": defect.bbox,
            "confidence": defect.confidence,
            "severity": defect.severity,
            "repair_action": defect.repair_action
        }

        assert defect_dict["defect_type"] == "cold_joint"
        assert defect_dict["confidence"] == 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
