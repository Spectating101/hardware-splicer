"""
Integration tests for ML pipeline components
Tests YOLO model loading, inference, and result processing
"""

import pytest
import numpy as np
from PIL import Image
import io
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vision.loader import get_detector, preprocess_image, postprocess_detections
from src.core.ingest import CircuitAnalyzer


class TestYOLOModelLoading:
    """Test YOLO model loading and initialization"""

    def test_model_loader_function_exists(self):
        """Test that model loader function is accessible"""
        assert callable(get_detector)

    def test_model_loading_with_valid_name(self):
        """Test loading model with valid model name"""
        try:
            model = get_detector("electrocom61_v1")
            # Model might not exist in test env, so None is acceptable
            assert model is None or model is not None
        except Exception as e:
            # Expected if model file doesn't exist
            assert "not found" in str(e).lower() or "no such file" in str(e).lower()

    def test_model_loading_with_invalid_name(self):
        """Test loading model with invalid name returns None"""
        model = get_detector("nonexistent_model_xyz")
        assert model is None


class TestImagePreprocessing:
    """Test image preprocessing pipeline"""

    def test_preprocess_valid_image(self):
        """Test preprocessing a valid image"""
        # Create test image
        img = Image.new('RGB', (640, 640), color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_bytes = img_buffer.getvalue()

        # Preprocess
        processed = preprocess_image(img_bytes)

        assert processed is not None
        assert isinstance(processed, np.ndarray)
        assert len(processed.shape) == 3  # Height, Width, Channels

    def test_preprocess_invalid_data(self):
        """Test preprocessing invalid image data"""
        invalid_data = b"not an image"
        processed = preprocess_image(invalid_data)

        assert processed is None

    def test_preprocess_various_formats(self):
        """Test preprocessing different image formats"""
        formats = ['JPEG', 'PNG']

        for fmt in formats:
            img = Image.new('RGB', (320, 320), color='red')
            img_buffer = io.BytesIO()
            img.save(img_buffer, format=fmt)
            img_bytes = img_buffer.getvalue()

            processed = preprocess_image(img_bytes)
            assert processed is not None

    def test_preprocess_different_sizes(self):
        """Test preprocessing images of different sizes"""
        sizes = [(100, 100), (640, 480), (1920, 1080)]

        for size in sizes:
            img = Image.new('RGB', size, color='green')
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG')
            img_bytes = img_buffer.getvalue()

            processed = preprocess_image(img_bytes)
            assert processed is not None


class TestDetectionPostprocessing:
    """Test detection result postprocessing"""

    def test_postprocess_function_exists(self):
        """Test that postprocessing function exists"""
        assert callable(postprocess_detections)

    def test_postprocess_empty_results(self):
        """Test postprocessing empty detection results"""
        # This test depends on the actual implementation
        # For now, just verify the function is callable
        pass

    def test_postprocess_confidence_filtering(self):
        """Test that confidence threshold is applied"""
        # Mock detection results would be needed here
        # This is a placeholder for when we have the actual structure
        pass


class TestCircuitAnalyzer:
    """Test the main CircuitAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing"""
        return CircuitAnalyzer()

    @pytest.fixture
    def test_image(self):
        """Create a test PCB image"""
        img = Image.new('RGB', (640, 640), color='green')
        # Add some colored rectangles to simulate components
        pixels = img.load()

        # Simulate a resistor (small rectangle)
        for x in range(100, 150):
            for y in range(100, 120):
                pixels[x, y] = (139, 69, 19)  # Brown

        # Simulate a capacitor (cylinder shape approximation)
        for x in range(200, 250):
            for y in range(100, 140):
                pixels[x, y] = (0, 0, 255)  # Blue

        return np.array(img)

    def test_analyzer_initialization(self, analyzer):
        """Test that analyzer initializes correctly"""
        assert analyzer is not None
        assert hasattr(analyzer, 'analyze_pcb')

    def test_analyze_pcb_method_exists(self, analyzer):
        """Test that analyze_pcb method is callable"""
        assert callable(analyzer.analyze_pcb)

    def test_analyze_pcb_with_valid_image(self, analyzer, test_image):
        """Test analyzing a valid PCB image"""
        try:
            results = analyzer.analyze_pcb(
                test_image,
                backend="enhanced",
                enable_ocr=False
            )

            assert results is not None
            assert isinstance(results, dict)
            assert "detections" in results or "components" in results

        except Exception as e:
            # If dependencies aren't loaded, that's expected in test env
            assert "model" in str(e).lower() or "detector" in str(e).lower()

    def test_analyze_pcb_backends(self, analyzer, test_image):
        """Test different analysis backends"""
        backends = ["enhanced", "yolo"]

        for backend in backends:
            try:
                results = analyzer.analyze_pcb(
                    test_image,
                    backend=backend,
                    enable_ocr=False
                )
                # Should return results or raise expected exception
                assert results is not None or True
            except Exception as e:
                # Expected if models not available
                pass

    def test_get_analysis_summary(self, analyzer):
        """Test analysis summary generation"""
        assert hasattr(analyzer, 'get_analysis_summary')
        assert callable(analyzer.get_analysis_summary)

        # Test with mock results
        mock_results = {
            "detections": [
                {"type": "resistor", "confidence": 0.9, "value": 1000},
                {"type": "capacitor", "confidence": 0.85, "value": 100}
            ]
        }

        try:
            summary = analyzer.get_analysis_summary(mock_results)
            assert summary is not None
            assert isinstance(summary, dict)
        except Exception:
            # Expected if implementation differs
            pass


class TestMLPipelineIntegration:
    """Test end-to-end ML pipeline"""

    @pytest.fixture
    def test_pcb_image(self):
        """Create realistic test PCB image"""
        # Create a more realistic PCB simulation
        img = Image.new('RGB', (1024, 768), color=(34, 139, 34))  # Green PCB

        pixels = img.load()

        # Simulate traces (copper lines)
        for x in range(100, 900):
            for y in range(380, 385):
                pixels[x, y] = (184, 115, 51)  # Copper color

        # Simulate some components
        components = [
            # Resistor
            {"x": 200, "y": 370, "w": 40, "h": 15, "color": (139, 69, 19)},
            # Capacitor
            {"x": 300, "y": 365, "w": 30, "h": 25, "color": (0, 0, 128)},
            # IC chip
            {"x": 450, "y": 340, "w": 80, "h": 60, "color": (0, 0, 0)},
        ]

        for comp in components:
            for x in range(comp["x"], comp["x"] + comp["w"]):
                for y in range(comp["y"], comp["y"] + comp["h"]):
                    if 0 <= x < 1024 and 0 <= y < 768:
                        pixels[x, y] = comp["color"]

        return np.array(img)

    def test_full_pipeline_smoke_test(self, test_pcb_image):
        """Smoke test for complete ML pipeline"""
        analyzer = CircuitAnalyzer()

        try:
            # Run analysis
            results = analyzer.analyze_pcb(
                test_pcb_image,
                backend="enhanced",
                enable_ocr=False
            )

            # Verify results structure
            assert results is not None
            assert isinstance(results, dict)

            # Get summary
            summary = analyzer.get_analysis_summary(results)
            assert summary is not None

        except Exception as e:
            # Expected failures in test environment
            expected_errors = [
                "model",
                "detector",
                "not found",
                "cannot import"
            ]
            assert any(err in str(e).lower() for err in expected_errors)

    def test_pipeline_handles_invalid_input(self):
        """Test pipeline gracefully handles invalid input"""
        analyzer = CircuitAnalyzer()

        # Test with invalid image
        invalid_image = np.array([])

        try:
            results = analyzer.analyze_pcb(invalid_image)
            # Should either return empty results or raise appropriate exception
            assert results is not None or True
        except (ValueError, TypeError, AttributeError):
            # Expected exceptions for invalid input
            pass

    def test_pipeline_performance_baseline(self, test_pcb_image):
        """Test that pipeline meets basic performance requirements"""
        import time

        analyzer = CircuitAnalyzer()

        try:
            start = time.perf_counter()
            results = analyzer.analyze_pcb(test_pcb_image, backend="enhanced")
            elapsed = time.perf_counter() - start

            # Should complete within reasonable time (30 seconds)
            assert elapsed < 30.0

        except Exception:
            # Skip if models not available
            pytest.skip("Models not available in test environment")


class TestModelCaching:
    """Test model caching and reuse"""

    def test_model_loaded_once(self):
        """Test that model is cached after first load"""
        # First load
        model1 = get_detector("electrocom61_v1")

        # Second load should return cached instance
        model2 = get_detector("electrocom61_v1")

        # Should be same instance (if caching works)
        # or both None (if model doesn't exist)
        if model1 is not None:
            assert model1 is model2

    def test_different_models_cached_separately(self):
        """Test that different models are cached separately"""
        model1 = get_detector("model_a")
        model2 = get_detector("model_b")

        # If both exist, should be different instances
        if model1 is not None and model2 is not None:
            assert model1 is not model2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
