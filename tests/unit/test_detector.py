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
    
    def test_get_detection_summary_empty(self):
        """Test detection summary with empty detections."""
        summary = self.detector.get_detection_summary([])
        
        assert summary['total_components'] == 0
        assert summary['components_by_type'] == {}
    
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