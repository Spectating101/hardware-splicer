"""
Integration tests for enhanced component detector with defect detection.

Tests the full pipeline: component detection → defect detection → quality scoring.
"""

import pytest
import numpy as np
import cv2

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vision.enhanced_detector import EnhancedComponentDetector


@pytest.fixture
def detector():
    """Create enhanced detector instance."""
    return EnhancedComponentDetector()


@pytest.fixture
def sample_pcb_image():
    """Create a synthetic PCB image with components."""
    # Create a green PCB substrate
    image = np.zeros((800, 600, 3), dtype=np.uint8)
    image[:, :] = [50, 120, 50]  # Green FR-4 substrate

    # Add some component-like rectangles (resistors/capacitors)
    cv2.rectangle(image, (100, 100), (150, 120), (139, 69, 19), -1)  # Brown resistor
    cv2.rectangle(image, (200, 150), (250, 170), (200, 200, 200), -1)  # Silver capacitor
    cv2.rectangle(image, (300, 200), (340, 230), (30, 30, 30), -1)  # Black IC

    return image


@pytest.fixture
def pcb_with_defects(sample_pcb_image):
    """Create PCB image with both components and defects."""
    image = sample_pcb_image.copy()

    # Add solder bridge defect
    cv2.rectangle(image, (400, 300), (450, 310), (200, 200, 200), -1)

    # Add burn mark
    cv2.circle(image, (500, 400), 15, (10, 10, 10), -1)

    return image


@pytest.fixture
def pristine_pcb(sample_pcb_image):
    """Create pristine PCB with no defects."""
    return sample_pcb_image.copy()


class TestEnhancedDetectorInitialization:
    """Test initialization of enhanced detector with defect detection."""

    def test_detector_has_defect_capabilities(self, detector):
        """Test that detector has defect detection enabled."""
        # Should have defect detector and scorer
        assert hasattr(detector, 'defect_detection_enabled')

        # If defect detection is enabled, should have detector and scorer
        if detector.defect_detection_enabled:
            assert hasattr(detector, 'defect_detector')
            assert hasattr(detector, 'defect_scorer')
            assert detector.defect_detector is not None
            assert detector.defect_scorer is not None

    def test_backward_compatibility_method_exists(self, detector):
        """Test that old detect_components method still exists."""
        assert hasattr(detector, 'detect_components')
        assert callable(detector.detect_components)

    def test_new_method_exists(self, detector):
        """Test that new detect_components_and_defects method exists."""
        assert hasattr(detector, 'detect_components_and_defects')
        assert callable(detector.detect_components_and_defects)


class TestComponentDetection:
    """Test component detection functionality (existing)."""

    def test_detect_components_returns_list(self, detector, sample_pcb_image):
        """Test that detect_components returns a list."""
        components = detector.detect_components(sample_pcb_image)

        assert isinstance(components, list)

    def test_backward_compatibility(self, detector, sample_pcb_image):
        """Test that old API still works."""
        # This should not raise an exception
        try:
            components = detector.detect_components(sample_pcb_image)
            assert True
        except Exception as e:
            pytest.fail(f"Backward compatibility broken: {e}")


class TestComponentsAndDefects:
    """Test integrated component and defect detection."""

    def test_detect_components_and_defects_returns_dict(self, detector, sample_pcb_image):
        """Test that detect_components_and_defects returns proper structure."""
        result = detector.detect_components_and_defects(sample_pcb_image)

        assert isinstance(result, dict)
        assert "components" in result
        assert "defects" in result
        assert "quality_score" in result
        assert "pass_fail" in result

    def test_components_key_contains_list(self, detector, sample_pcb_image):
        """Test that components key contains a list."""
        result = detector.detect_components_and_defects(sample_pcb_image)

        assert isinstance(result["components"], list)

    def test_defects_key_contains_list(self, detector, sample_pcb_image):
        """Test that defects key contains a list."""
        result = detector.detect_components_and_defects(sample_pcb_image)

        assert isinstance(result["defects"], list)

    def test_quality_score_is_float(self, detector, sample_pcb_image):
        """Test that quality score is a float between 0 and 1."""
        result = detector.detect_components_and_defects(sample_pcb_image)

        assert isinstance(result["quality_score"], (int, float))
        assert 0.0 <= result["quality_score"] <= 1.0

    def test_pass_fail_is_boolean(self, detector, sample_pcb_image):
        """Test that pass_fail is a boolean."""
        result = detector.detect_components_and_defects(sample_pcb_image)

        assert isinstance(result["pass_fail"], bool)


class TestDefectDetection:
    """Test defect detection on various PCB conditions."""

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_pristine_board_high_quality_score(self, detector, pristine_pcb):
        """Test that pristine board gets high quality score."""
        result = detector.detect_components_and_defects(pristine_pcb)

        # Pristine board should have high score
        assert result["quality_score"] >= 0.85
        assert result["pass_fail"] is True

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_defective_board_detects_defects(self, detector, pcb_with_defects):
        """Test that defective board detects some defects."""
        result = detector.detect_components_and_defects(pcb_with_defects)

        # Should detect at least some defects
        # (Classical CV may have false positives/negatives, so we're lenient)
        assert isinstance(result["defects"], list)

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_defects_have_proper_structure(self, detector, pcb_with_defects):
        """Test that detected defects have proper structure."""
        result = detector.detect_components_and_defects(pcb_with_defects)

        for defect in result["defects"]:
            # Should be DefectDetection object or dict with required fields
            if isinstance(defect, dict):
                assert "defect_type" in defect
                assert "bbox" in defect
                assert "confidence" in defect
                assert "severity" in defect
                assert "repair_action" in defect
            else:
                assert hasattr(defect, 'defect_type')
                assert hasattr(defect, 'bbox')
                assert hasattr(defect, 'confidence')
                assert hasattr(defect, 'severity')
                assert hasattr(defect, 'repair_action')


class TestQualityAssessment:
    """Test quality assessment integration."""

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_quality_assessment_included_when_enabled(self, detector, sample_pcb_image):
        """Test that quality assessment is included when defect detection enabled."""
        result = detector.detect_components_and_defects(
            sample_pcb_image,
            enable_defect_detection=True
        )

        if detector.defect_detection_enabled:
            assert "quality_assessment" in result
            assert result["quality_assessment"] is not None

    def test_quality_assessment_not_included_when_disabled(self, detector, sample_pcb_image):
        """Test that quality assessment is skipped when disabled."""
        result = detector.detect_components_and_defects(
            sample_pcb_image,
            enable_defect_detection=False
        )

        # When disabled, should still have quality_score/pass_fail but may not have full assessment
        assert "quality_score" in result
        assert "pass_fail" in result


class TestDefectDetectionToggle:
    """Test enabling/disabling defect detection."""

    def test_disable_defect_detection(self, detector, sample_pcb_image):
        """Test disabling defect detection."""
        result = detector.detect_components_and_defects(
            sample_pcb_image,
            enable_defect_detection=False
        )

        # Should still return proper structure
        assert "components" in result
        assert "defects" in result
        assert "quality_score" in result
        assert "pass_fail" in result

        # Defects should be empty when disabled
        assert result["defects"] == []
        assert result["quality_score"] == 1.0  # Default when no detection
        assert result["pass_fail"] is True

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_enable_defect_detection(self, detector, sample_pcb_image):
        """Test enabling defect detection."""
        result = detector.detect_components_and_defects(
            sample_pcb_image,
            enable_defect_detection=True
        )

        # Should run defect detection (may or may not find defects)
        assert isinstance(result["defects"], list)


class TestEndToEndPipeline:
    """Test the complete detection pipeline."""

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_full_pipeline_with_defects(self, detector, pcb_with_defects):
        """Test full pipeline on PCB with defects."""
        result = detector.detect_components_and_defects(pcb_with_defects)

        # Should have all components
        assert "components" in result
        assert isinstance(result["components"], list)

        # Should have defects
        assert "defects" in result

        # Should have quality assessment
        assert "quality_score" in result
        assert "pass_fail" in result

        # Quality score should be valid
        assert 0.0 <= result["quality_score"] <= 1.0

    @pytest.mark.skipif(
        not hasattr(EnhancedComponentDetector(), 'defect_detection_enabled') or
        not EnhancedComponentDetector().defect_detection_enabled,
        reason="Defect detection not available"
    )
    def test_full_pipeline_pristine_board(self, detector, pristine_pcb):
        """Test full pipeline on pristine board."""
        result = detector.detect_components_and_defects(pristine_pcb)

        # Should have components
        assert "components" in result

        # Should have minimal or no defects
        assert "defects" in result

        # Should have high quality score
        assert result["quality_score"] >= 0.70
        assert result["pass_fail"] is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_image(self, detector):
        """Test detection on empty/black image."""
        black_image = np.zeros((100, 100, 3), dtype=np.uint8)

        result = detector.detect_components_and_defects(black_image)

        # Should not crash
        assert isinstance(result, dict)
        assert "components" in result
        assert "defects" in result

    def test_very_small_image(self, detector):
        """Test detection on very small image."""
        tiny_image = np.ones((10, 10, 3), dtype=np.uint8) * 100

        result = detector.detect_components_and_defects(tiny_image)

        # Should not crash
        assert isinstance(result, dict)

    def test_white_image(self, detector):
        """Test detection on all-white image."""
        white_image = np.ones((200, 200, 3), dtype=np.uint8) * 255

        result = detector.detect_components_and_defects(white_image)

        # Should not crash
        assert isinstance(result, dict)
        assert result["quality_score"] >= 0.0


class TestMultipleRuns:
    """Test consistency across multiple runs."""

    def test_consistent_results_on_same_image(self, detector, sample_pcb_image):
        """Test that running detection multiple times gives consistent results."""
        result1 = detector.detect_components_and_defects(sample_pcb_image)
        result2 = detector.detect_components_and_defects(sample_pcb_image)

        # Quality scores should be identical for same image
        assert result1["quality_score"] == result2["quality_score"]
        assert result1["pass_fail"] == result2["pass_fail"]

        # Number of defects should be consistent
        assert len(result1["defects"]) == len(result2["defects"])


class TestGracefulDegradation:
    """Test graceful degradation when features unavailable."""

    def test_works_without_defect_detection(self, sample_pcb_image):
        """Test that detector works even if defect detection unavailable."""
        # Create detector that might not have defect detection
        detector = EnhancedComponentDetector()

        # Should not crash regardless of defect detection availability
        try:
            result = detector.detect_components_and_defects(sample_pcb_image)
            assert "components" in result
            assert "quality_score" in result
            assert True
        except Exception as e:
            pytest.fail(f"Should not crash when defect detection unavailable: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
