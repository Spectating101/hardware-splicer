import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
import cv2
from dataclasses import dataclass
from enum import Enum
import time
from concurrent.futures import ThreadPoolExecutor
import threading

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLO not available")

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR not available")

class DetectionMethod(Enum):
    YOLO = "yolo"
    CLASSICAL = "classical"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"

@dataclass
class ComponentDetection:
    bbox: List[float]  # [x1, y1, x2, y2]
    class_name: str
    confidence: float
    method: DetectionMethod
    metadata: Dict[str, Any]
    center: Optional[Tuple[float, float]] = None
    area: Optional[float] = None
    aspect_ratio: Optional[float] = None
    text_content: Optional[str] = None
    quality_score: Optional[float] = None

class EnhancedComponentDetector:
    """Enhanced component detector with multi-model ensemble and advanced features."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.models = {}
        self.ensemble_weights = {
            'yolo': 0.6,
            'classical': 0.3,
            'custom': 0.1
        }
        
        # Initialize models
        self._initialize_models()
        
        # Component database - Updated for Circuit-AI trained model
        self.component_classes = [
            'Cap1',           # 0 - Capacitor type 1
            'Cap2',           # 1 - Capacitor type 2
            'Cap3',           # 2 - Capacitor type 3
            'Cap4',           # 3 - Capacitor type 4
            'MOSFET',         # 4 - MOSFET transistor
            'Mov',            # 5 - MOV (Metal Oxide Varistor)
            'Resestor',       # 6 - Resistor (note: typo in dataset)
            'Resistor',       # 7 - Resistor
            'Transformer'     # 8 - Transformer
        ]
        
        # Quality assessment parameters
        self.quality_thresholds = {
            'min_confidence': 0.3,
            'min_area': 100,
            'max_aspect_ratio': 10.0,
            'min_text_confidence': 0.5
        }
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"Enhanced detector initialized on {self.device}")
    
    def _initialize_models(self):
        """Initialize detection models."""
        # Try loading trained PCB model first, fall back to pretrained
        if YOLO_AVAILABLE:
            try:
                # Load trained Circuit-AI PCB component detection model
                import os
                trained_model_path = 'pcb_runs/real_pcb_v1/weights/best.pt'
                if os.path.exists(trained_model_path):
                    self.models['yolo'] = YOLO(trained_model_path)
                    logger.info("✅ Loaded trained Circuit-AI PCB model (real_pcb_v1)")
                else:
                    # Fallback to pretrained model
                    self.models['yolo'] = YOLO('yolov8n.pt')
                    logger.info("⚠️  Trained model not found, using pretrained YOLOv8n")
                
                self.models['yolo'].to(self.device)
                logger.info(f"YOLO model loaded on {self.device}")
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}")
        
        # Custom model (placeholder for future implementation)
        self.models['custom'] = None
        
        logger.info(f"Initialized {len(self.models)} detection models")
    
    def detect_components(self, image: np.ndarray, 
                         methods: List[DetectionMethod] = None,
                         enable_ocr: bool = True,
                         enable_quality_assessment: bool = True) -> List[ComponentDetection]:
        """Detect components using multiple methods."""
        if methods is None:
            methods = [DetectionMethod.ENSEMBLE]
        
        all_detections = []
        
        # Run detections in parallel
        futures = []
        for method in methods:
            if method == DetectionMethod.ENSEMBLE:
                futures.append(
                    self.executor.submit(self._detect_ensemble, image, enable_ocr)
                )
            elif method == DetectionMethod.YOLO and 'yolo' in self.models:
                futures.append(
                    self.executor.submit(self._detect_with_yolo, image)
                )
            elif method == DetectionMethod.CLASSICAL:
                futures.append(
                    self.executor.submit(self._detect_with_classical, image)
                )
            elif method == DetectionMethod.CUSTOM and self.models['custom']:
                futures.append(
                    self.executor.submit(self._detect_with_custom, image)
                )
        
        # Collect results
        for future in futures:
            try:
                detections = future.result(timeout=30)
                all_detections.extend(detections)
            except Exception as e:
                logger.error(f"Detection method failed: {e}")
        
        # Post-process detections
        if enable_quality_assessment:
            all_detections = self._assess_quality(all_detections)
        
        # Remove duplicates and merge overlapping detections
        all_detections = self._merge_detections(all_detections)
        
        # Sort by confidence
        all_detections.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"Detected {len(all_detections)} components using {len(methods)} methods")
        return all_detections
    
    def _detect_ensemble(self, image: np.ndarray, enable_ocr: bool) -> List[ComponentDetection]:
        """Ensemble detection using multiple methods."""
        detections = []
        
        # YOLO detection
        if 'yolo' in self.models:
            yolo_detections = self._detect_with_yolo(image)
            detections.extend(yolo_detections)
        
        # Classical detection
        classical_detections = self._detect_with_classical(image)
        detections.extend(classical_detections)
        
        # Custom detection
        if self.models['custom']:
            custom_detections = self._detect_with_custom(image)
            detections.extend(custom_detections)
        
        # OCR enrichment
        if enable_ocr and OCR_AVAILABLE:
            self._enrich_with_ocr(image, detections)
        
        return detections
    
    def _detect_with_yolo(self, image: np.ndarray) -> List[ComponentDetection]:
        """Detect components using YOLO."""
        if 'yolo' not in self.models:
            return []
        
        try:
            results = self.models['yolo'](image)
            detections = []
            
            for r in results:
                if hasattr(r, 'boxes') and r.boxes is not None:
                    boxes = r.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        confidence = box.conf[0].item()
                        class_id = int(box.cls[0].item())
                        
                        # Map class ID to component type
                        class_name = self._map_class_id_to_name(class_id)
                        
                        detection = ComponentDetection(
                            bbox=[x1, y1, x2, y2],
                            class_name=class_name,
                            confidence=confidence,
                            method=DetectionMethod.YOLO,
                            metadata={
                                'class_id': class_id,
                                'model': 'yolov8n'
                            }
                        )
                        
                        # Calculate additional properties
                        self._calculate_detection_properties(detection)
                        detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return []
    
    def _detect_with_classical(self, image: np.ndarray) -> List[ComponentDetection]:
        """Detect components using classical computer vision."""
        detections = []
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                # Filter by area
                area = cv2.contourArea(contour)
                if area < self.quality_thresholds['min_area']:
                    continue
                
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                x1, y1, x2, y2 = x, y, x + w, y + h
                
                # Calculate aspect ratio
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio > self.quality_thresholds['max_aspect_ratio']:
                    continue
                
                # Classify component based on shape and size
                class_name = self._classify_by_shape(contour, area, aspect_ratio)
                
                # Calculate confidence based on contour properties
                confidence = self._calculate_classical_confidence(contour, area, aspect_ratio)
                
                detection = ComponentDetection(
                    bbox=[x1, y1, x2, y2],
                    class_name=class_name,
                    confidence=confidence,
                    method=DetectionMethod.CLASSICAL,
                    metadata={
                        'area': area,
                        'aspect_ratio': aspect_ratio,
                        'contour_points': len(contour)
                    }
                )
                
                # Calculate additional properties
                self._calculate_detection_properties(detection)
                detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Classical detection failed: {e}")
            return []
    
    def _detect_with_custom(self, image: np.ndarray) -> List[ComponentDetection]:
        """Detect components using custom model (placeholder)."""
        # This would implement custom detection logic
        # For now, return empty list
        return []
    
    def _enrich_with_ocr(self, image: np.ndarray, detections: List[ComponentDetection]):
        """Enrich detections with OCR text."""
        if not OCR_AVAILABLE:
            return
        
        try:
            for detection in detections:
                # Extract ROI
                x1, y1, x2, y2 = [int(coord) for coord in detection.bbox]
                roi = image[y1:y2, x1:x2]
                
                if roi.size == 0:
                    continue
                
                # Perform OCR
                try:
                    text = pytesseract.image_to_string(roi, config='--psm 6')
                    text = text.strip()
                    
                    if text:
                        detection.text_content = text
                        detection.metadata['ocr_confidence'] = 0.8  # Placeholder
                except Exception as e:
                    logger.debug(f"OCR failed for detection: {e}")
                    
        except Exception as e:
            logger.error(f"OCR enrichment failed: {e}")
    
    def _assess_quality(self, detections: List[ComponentDetection]) -> List[ComponentDetection]:
        """Assess quality of detections and filter low-quality ones."""
        quality_detections = []
        
        for detection in detections:
            quality_score = self._calculate_quality_score(detection)
            detection.quality_score = quality_score
            
            if quality_score >= self.quality_thresholds['min_confidence']:
                quality_detections.append(detection)
        
        logger.info(f"Quality assessment: {len(detections)} -> {len(quality_detections)} detections")
        return quality_detections
    
    def _calculate_quality_score(self, detection: ComponentDetection) -> float:
        """Calculate quality score for a detection."""
        score = detection.confidence
        
        # Penalize very small detections
        if detection.area and detection.area < 200:
            score *= 0.8
        
        # Penalize extreme aspect ratios
        if detection.aspect_ratio and detection.aspect_ratio > 5.0:
            score *= 0.9
        
        # Bonus for text content
        if detection.text_content:
            score *= 1.1
        
        # Method-specific adjustments
        if detection.method == DetectionMethod.ENSEMBLE:
            score *= 1.05
        
        return min(score, 1.0)
    
    def _merge_detections(self, detections: List[ComponentDetection]) -> List[ComponentDetection]:
        """Merge overlapping detections."""
        if not detections:
            return []
        
        # Sort by confidence
        detections.sort(key=lambda x: x.confidence, reverse=True)
        
        merged = []
        used = set()
        
        for i, detection in enumerate(detections):
            if i in used:
                continue
            
            merged_group = [detection]
            used.add(i)
            
            # Find overlapping detections
            for j, other in enumerate(detections[i+1:], i+1):
                if j in used:
                    continue
                
                if self._detections_overlap(detection, other):
                    merged_group.append(other)
                    used.add(j)
            
            # Merge the group
            if len(merged_group) > 1:
                merged_detection = self._merge_detection_group(merged_group)
                merged.append(merged_detection)
            else:
                merged.append(detection)
        
        return merged
    
    def _detections_overlap(self, det1: ComponentDetection, det2: ComponentDetection, 
                           threshold: float = 0.5) -> bool:
        """Check if two detections overlap significantly."""
        x1_1, y1_1, x2_1, y2_1 = det1.bbox
        x1_2, y1_2, x2_2, y2_2 = det2.bbox
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return False
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        # Calculate IoU
        union = area1 + area2 - intersection
        iou = intersection / union if union > 0 else 0
        
        return iou > threshold
    
    def _merge_detection_group(self, detections: List[ComponentDetection]) -> ComponentDetection:
        """Merge a group of overlapping detections."""
        # Use the highest confidence detection as base
        base = max(detections, key=lambda x: x.confidence)
        
        # Calculate weighted average bbox
        total_weight = sum(d.confidence for d in detections)
        weighted_bbox = [0, 0, 0, 0]
        
        for detection in detections:
            weight = detection.confidence / total_weight
            for i in range(4):
                weighted_bbox[i] += detection.bbox[i] * weight
        
        # Create merged detection
        merged = ComponentDetection(
            bbox=weighted_bbox,
            class_name=base.class_name,
            confidence=sum(d.confidence for d in detections) / len(detections),
            method=DetectionMethod.ENSEMBLE,
            metadata={
                'merged_count': len(detections),
                'methods': [d.method.value for d in detections]
            }
        )
        
        # Calculate additional properties
        self._calculate_detection_properties(merged)
        
        return merged
    
    def _calculate_detection_properties(self, detection: ComponentDetection):
        """Calculate additional properties for a detection."""
        x1, y1, x2, y2 = detection.bbox
        
        # Center point
        detection.center = ((x1 + x2) / 2, (y1 + y2) / 2)
        
        # Area
        detection.area = (x2 - x1) * (y2 - y1)
        
        # Aspect ratio
        width = x2 - x1
        height = y2 - y1
        detection.aspect_ratio = width / height if height > 0 else 0
    
    def _map_class_id_to_name(self, class_id: int) -> str:
        """Map YOLO class ID to component name."""
        if class_id < len(self.component_classes):
            return self.component_classes[class_id]
        return 'unknown'
    
    def _classify_by_shape(self, contour: np.ndarray, area: float, aspect_ratio: float) -> str:
        """Classify component based on shape and size."""
        # Simple classification based on shape properties
        if aspect_ratio > 3.0:
            return 'resistor'
        elif aspect_ratio < 0.5:
            return 'capacitor'
        elif area > 1000:
            return 'ic_chip'
        else:
            return 'connector'
    
    def _calculate_classical_confidence(self, contour: np.ndarray, area: float, aspect_ratio: float) -> float:
        """Calculate confidence for classical detection."""
        # Base confidence on contour properties
        confidence = 0.5
        
        # Adjust based on area
        if 100 <= area <= 5000:
            confidence += 0.2
        
        # Adjust based on aspect ratio
        if 0.2 <= aspect_ratio <= 5.0:
            confidence += 0.2
        
        # Adjust based on contour complexity
        if len(contour) > 10:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def get_detection_summary(self, detections: List[ComponentDetection]) -> Dict[str, Any]:
        """Generate summary of detections."""
        if not detections:
            return {
                'total_components': 0,
                'average_confidence': 0.0,
                'detection_quality': 'low',
                'components_by_type': {},
                'methods_used': []
            }
        
        # Count by type
        components_by_type = {}
        for detection in detections:
            comp_type = detection.class_name
            components_by_type[comp_type] = components_by_type.get(comp_type, 0) + 1
        
        # Calculate statistics
        confidences = [d.confidence for d in detections]
        average_confidence = sum(confidences) / len(confidences)
        
        # Determine quality
        if average_confidence > 0.8:
            quality = 'high'
        elif average_confidence > 0.6:
            quality = 'medium'
        else:
            quality = 'low'
        
        # Methods used
        methods_used = list(set(d.method.value for d in detections))
        
        return {
            'total_components': len(detections),
            'average_confidence': average_confidence,
            'detection_quality': quality,
            'components_by_type': components_by_type,
            'methods_used': methods_used,
            'quality_scores': [d.quality_score for d in detections if d.quality_score]
        }
    
    def draw_detections(self, image: np.ndarray, detections: List[ComponentDetection], 
                       show_labels: bool = True, show_confidence: bool = True) -> np.ndarray:
        """Draw detections on image."""
        img_copy = image.copy()
        
        for detection in detections:
            x1, y1, x2, y2 = [int(coord) for coord in detection.bbox]
            
            # Choose color based on confidence
            if detection.confidence > 0.8:
                color = (0, 255, 0)  # Green
            elif detection.confidence > 0.6:
                color = (255, 255, 0)  # Yellow
            else:
                color = (255, 0, 0)  # Red
            
            # Draw bounding box
            cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            if show_labels:
                label_parts = [detection.class_name]
                if show_confidence:
                    label_parts.append(f"{detection.confidence:.2f}")
                
                label = " ".join(label_parts)
                
                # Calculate text position
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                text_x = x1
                text_y = max(y1 - 10, text_size[1])
                
                # Draw text background
                cv2.rectangle(img_copy, 
                            (text_x, text_y - text_size[1] - 5),
                            (text_x + text_size[0], text_y + 5),
                            color, -1)
                
                # Draw text
                cv2.putText(img_copy, label, (text_x, text_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return img_copy

# Global enhanced detector instance
enhanced_detector = EnhancedComponentDetector()
