import pytest
import numpy as np
from unittest.mock import Mock, patch
from src.vision.detector import ComponentDetector


class TestComponentDetector:
    """Test cases for ComponentDetector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ComponentDetector()
    
    def test_initialization(self):
        """Test detector initialization."""
        assert self.detector is not None
        assert hasattr(self.detector, 'model')
        assert hasattr(self.detector, 'component_classes')

    @patch('src.vision.detector.resolve_pcb_model_path', return_value=None)
    @patch('src.vision.detector.YOLO')
    def test_yolo_does_not_load_generic_coco_fallback(self, mock_yolo, _mock_resolver):
        """YOLO mode should not silently become a generic COCO detector."""
        image = np.random.randint(0, 255, (120, 120, 3), dtype=np.uint8)

        self.detector.detect_components(image, backend="yolo", enable_ocr=False)

        mock_yolo.assert_not_called()
    
    def test_preprocess_image_rgb(self):
        """Test RGB image preprocessing."""
        # Create a sample RGB image
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        processed = self.detector.preprocess_image(image)
        
        assert processed.shape == (100, 100, 3)
        assert processed.dtype == np.float32
        assert processed.max() <= 1.0
        assert processed.min() >= 0.0
    
    def test_preprocess_image_rgba(self):
        """Test RGBA image preprocessing."""
        # Create a sample RGBA image
        image = np.random.randint(0, 255, (100, 100, 4), dtype=np.uint8)
        
        processed = self.detector.preprocess_image(image)
        
        assert processed.shape == (100, 100, 3)  # Should convert to RGB
        assert processed.dtype == np.float32
    
    def test_preprocess_image_grayscale(self):
        """Test grayscale image preprocessing."""
        # Create a sample grayscale image
        image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        
        processed = self.detector.preprocess_image(image)
        
        assert processed.shape == (100, 100, 3)  # Should convert to RGB
        assert processed.dtype == np.float32
    
    @patch('src.vision.detector.YOLO')
    def test_detect_components_success(self, mock_yolo):
        """Test successful component detection."""
        # Mock YOLO results
        mock_result = Mock()
        mock_box = Mock()
        mock_box.xyxy = [np.array([100, 150, 200, 250])]
        mock_box.conf = np.array([0.85])
        mock_box.cls = np.array([0])  # ic_chip class
        
        mock_result.boxes = [mock_box]
        mock_yolo.return_value.return_value = [mock_result]
        
        # Create test image
        image = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        
        detections = self.detector.detect_components(image)
        
        assert len(detections) == 1
        assert detections[0]['class_name'] == 'ic_chip'
        assert detections[0]['confidence'] == 0.85
        assert detections[0]['bbox'] == [100, 150, 200, 250]
    
    @patch('src.vision.detector.YOLO')
    def test_detect_components_no_detections(self, mock_yolo):
        """Test component detection with no detections."""
        # Mock YOLO results with no detections
        mock_result = Mock()
        mock_result.boxes = None
        mock_yolo.return_value.return_value = [mock_result]
        
        image = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        
        detections = self.detector.detect_components(image)
        
        assert len(detections) == 0

    @patch('src.vision.detector.YOLO')
    def test_yolo_filters_below_class_threshold(self, mock_yolo):
        mock_model = mock_yolo.return_value
        mock_model.names = {0: "resistor"}
        low = Mock()
        low.xyxy = [np.array([10, 10, 60, 40])]
        low.conf = np.array([0.3])
        low.cls = np.array([0])
        high = Mock()
        high.xyxy = [np.array([80, 10, 130, 40])]
        high.conf = np.array([0.7])
        high.cls = np.array([0])
        mock_result = Mock()
        mock_result.boxes = [low, high]
        mock_model.return_value = [mock_result]

        image = np.random.randint(0, 255, (120, 200, 3), dtype=np.uint8)
        detections = self.detector.detect_components(image, backend="yolo", enable_ocr=False)

        assert len(detections) == 1
        assert detections[0]["confidence"] >= 0.7

    @patch('src.vision.detector.YOLO')
    def test_yolo_nms_suppresses_overlapping_class_duplicates(self, mock_yolo):
        mock_model = mock_yolo.return_value
        mock_model.names = {0: "resistor"}
        first = Mock()
        first.xyxy = [np.array([10, 10, 110, 60])]
        first.conf = np.array([0.95])
        first.cls = np.array([0])
        second = Mock()
        second.xyxy = [np.array([12, 12, 108, 58])]
        second.conf = np.array([0.80])
        second.cls = np.array([0])
        mock_result = Mock()
        mock_result.boxes = [first, second]
        mock_model.return_value = [mock_result]

        image = np.random.randint(0, 255, (160, 240, 3), dtype=np.uint8)
        detections = self.detector.detect_components(image, backend="yolo", enable_ocr=False)

        assert len(detections) == 1
        assert detections[0]["confidence"] >= 0.9

    @patch('src.vision.detector.resolve_pcb_model_path', return_value='models/pcb/pcb_components_yolo11n_thawed.pt')
    @patch('src.vision.detector.YOLO')
    def test_yolo_receives_uint8_image_after_preprocessing(self, mock_yolo, _mock_resolver):
        mock_model = mock_yolo.return_value
        mock_result = Mock()
        mock_result.boxes = None
        mock_model.return_value = [mock_result]

        image = np.random.random((120, 120, 3)).astype(np.float32)
        detections = self.detector.detect_components(image, backend="yolo", enable_ocr=False)

        assert detections == []
        model_image = mock_model.call_args.args[0]
        assert model_image.dtype == np.uint8
        assert model_image.max() <= 255
    
    def test_get_detection_summary_empty(self):
        """Test detection summary with empty detections."""
        summary = self.detector.get_detection_summary([])
        
        assert summary['total_components'] == 0
        assert summary['components_by_type'] == {}
        assert summary['review_required'] is False
    
    def test_get_detection_summary_with_detections(self):
        """Test detection summary with detections."""
        detections = [
            {
                'class_name': 'ic_chip',
                'confidence': 0.9,
                'bbox': [100, 150, 200, 250]
            },
            {
                'class_name': 'capacitor',
                'confidence': 0.8,
                'bbox': [300, 200, 350, 250]
            },
            {
                'class_name': 'ic_chip',
                'confidence': 0.85,
                'bbox': [400, 300, 450, 350]
            }
        ]
        
        summary = self.detector.get_detection_summary(detections)
        
        assert summary['total_components'] == 3
        assert summary['components_by_type']['ic_chip'] == 2
        assert summary['components_by_type']['capacitor'] == 1
        assert summary['average_confidence'] == pytest.approx(0.85, abs=0.01)
        assert summary['detection_quality'] == 'high'
        assert summary['semantic_quality'] == 'high'
    
    def test_get_detection_summary_low_confidence(self):
        """Test detection summary with low confidence."""
        detections = [
            {
                'class_name': 'ic_chip',
                'confidence': 0.3,
                'bbox': [100, 150, 200, 250]
            }
        ]
        
        summary = self.detector.get_detection_summary(detections)
        
        assert summary['detection_quality'] == 'low'
    
    def test_get_detection_summary_medium_confidence(self):
        """Test detection summary with medium confidence."""
        detections = [
            {
                'class_name': 'ic_chip',
                'confidence': 0.6,
                'bbox': [100, 150, 200, 250]
            }
        ]
        
        summary = self.detector.get_detection_summary(detections)
        
        assert summary['detection_quality'] == 'medium'

    def test_hybrid_backend_falls_back_to_classical_when_yolo_empty(self):
        """Hybrid backend should stay useful when the PCB model has no confident boxes."""
        image = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        fallback_detection = {
            "bbox": [10.0, 10.0, 40.0, 40.0],
            "confidence": 0.7,
            "class_id": 1,
            "class_name": "capacitor",
            "center": [25.0, 25.0],
        }

        with patch.object(self.detector, "_detect_with_yolo", return_value=[]), \
             patch.object(self.detector, "_detect_with_classical_cv", return_value=[fallback_detection]):
            detections = self.detector.detect_components(image, backend="hybrid", enable_ocr=False)

        assert len(detections) == 1
        assert detections[0]["class_name"] == "capacitor"
        assert detections[0]["provenance"]["backend"] == "classical-fallback"

    def test_hybrid_backend_supplements_sparse_yolo_candidates(self):
        image = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        yolo_detection = {
            "bbox": [10.0, 10.0, 40.0, 40.0],
            "confidence": 0.7,
            "semantic_confidence": 0.7,
            "class_id": 12,
            "class_name": "led",
            "center": [25.0, 25.0],
            "provenance": {"backend": "yolo"},
        }
        supplemental_detection = {
            "bbox": [100.0, 100.0, 160.0, 150.0],
            "confidence": 0.62,
            "semantic_confidence": 0.5,
            "class_id": 1,
            "class_name": "capacitor",
            "center": [130.0, 125.0],
        }

        with patch.object(self.detector, "_detect_with_yolo", return_value=[yolo_detection]), \
             patch.object(self.detector, "_detect_with_supplemental_yolo", return_value=[]), \
             patch.object(self.detector, "_detect_with_classical_cv", return_value=[supplemental_detection]):
            detections = self.detector.detect_components(image, backend="hybrid", enable_ocr=False)

        assert len(detections) == 2
        assert detections[1]["provenance"]["backend"] == "classical-supplement"

    def test_hybrid_backend_prefers_supplemental_yolo_before_classical(self):
        image = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        yolo_detection = {
            "bbox": [10.0, 10.0, 40.0, 40.0],
            "confidence": 0.7,
            "semantic_confidence": 0.7,
            "class_id": 12,
            "class_name": "led",
            "center": [25.0, 25.0],
            "provenance": {"backend": "yolo"},
        }
        learned_detection = {
            "bbox": [100.0, 100.0, 160.0, 150.0],
            "confidence": 0.62,
            "semantic_confidence": 0.62,
            "class_id": 6,
            "class_name": "connector",
            "center": [130.0, 125.0],
            "provenance": {"backend": "yolo-supplement"},
        }
        second_learned_detection = {
            "bbox": [180.0, 100.0, 230.0, 150.0],
            "confidence": 0.58,
            "semantic_confidence": 0.58,
            "class_id": 7,
            "class_name": "resistor",
            "center": [205.0, 125.0],
            "provenance": {"backend": "yolo-supplement"},
        }

        with patch.object(self.detector, "_detect_with_yolo", return_value=[yolo_detection]), \
             patch.object(self.detector, "_detect_with_supplemental_yolo", return_value=[learned_detection, second_learned_detection]), \
             patch.object(self.detector, "_detect_with_classical_cv") as mock_classical:
            detections = self.detector.detect_components(image, backend="hybrid", enable_ocr=False)

        assert len(detections) == 3
        assert detections[1]["provenance"]["backend"] == "yolo-supplement"
        mock_classical.assert_not_called()

    def test_hybrid_backend_does_not_classical_flood_two_confident_yolo_detections(self):
        image = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        yolo_detections = [
            {
                "bbox": [10.0, 10.0, 40.0, 40.0],
                "confidence": 0.74,
                "semantic_confidence": 0.74,
                "class_id": 6,
                "class_name": "connector",
                "center": [25.0, 25.0],
                "provenance": {"backend": "yolo"},
            },
            {
                "bbox": [100.0, 100.0, 140.0, 140.0],
                "confidence": 0.72,
                "semantic_confidence": 0.72,
                "class_id": 6,
                "class_name": "connector",
                "center": [120.0, 120.0],
                "provenance": {"backend": "yolo"},
            },
        ]

        with patch.object(self.detector, "_detect_with_yolo", return_value=yolo_detections), \
             patch.object(self.detector, "_detect_with_supplemental_yolo", return_value=[]), \
             patch.object(self.detector, "_detect_with_classical_cv") as mock_classical:
            detections = self.detector.detect_components(image, backend="hybrid", enable_ocr=False)

        assert len(detections) == 2
        mock_classical.assert_not_called()

    def test_classical_detections_are_marked_for_review(self):
        image = np.zeros((300, 300, 3), dtype=np.uint8)
        cv = pytest.importorskip("cv2")
        cv.rectangle(image, (40, 40), (120, 100), (255, 255, 255), -1)

        detections = self.detector.detect_components(image, backend="classical", enable_ocr=False)
        summary = self.detector.get_detection_summary(detections)

        assert detections
        assert summary["review_required"] is True
        assert summary["semantic_quality"] in {"candidate", "low"}
        assert summary["limitations"]

    @patch('src.vision.detector.resolve_pcb_model_path', return_value=None)
    @patch('src.vision.detector.YOLO')
    def test_explicit_yolo_backend_returns_empty_when_pcb_model_missing(self, mock_yolo, _mock_resolver):
        image = np.random.randint(0, 255, (120, 120, 3), dtype=np.uint8)

        detections = self.detector.detect_components(image, backend="yolo", enable_ocr=False)

        assert detections == []
        mock_yolo.assert_not_called()
