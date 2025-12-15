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
import sys
import os

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLO not available - Install ultralytics")

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.info("OCR not available - Install pytesseract for text reading")

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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, knowledge_base_path: str = None):
        self.config = config or {}
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.models = {}
        self.model_source = "uninitialized"
        self.custom_model_found = False
        self.fallback_used = False
        self.ensemble_weights = {
            'yolo': 0.6,
            'classical': 0.3,
            'custom': 0.1
        }
        
        self.knowledge_base_path = knowledge_base_path
        self.knowledge = None
        
        # Try to load Knowledge Base if path provided
        if self.knowledge_base_path:
            try:
                # Add src root to path if needed to find circuit_agent
                src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
                if src_root not in sys.path:
                    sys.path.insert(0, src_root)
                
                # Import here to avoid circular dependencies if this file is imported by circuit_agent
                from circuit_agent import CircuitKnowledgeBase
                self.knowledge = CircuitKnowledgeBase(knowledge_path=self.knowledge_base_path)
            except ImportError as e:
                logger.warning(f"Could not load CircuitKnowledgeBase: {e}. Pinout overlays will be disabled.")
            except Exception as e:
                logger.error(f"Error initializing KnowledgeBase: {e}")

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
            'Transformer',    # 8 - Transformer
            'Arduino Uno'     # 9 - Arduino Uno Board (added for detection)
        ]
        
        # Quality assessment parameters
        self.quality_thresholds = {
            'min_confidence': 0.3,
            'min_area': 100,
            'max_aspect_ratio': 10.0,
            'min_text_confidence': 0.5
        }

        # Per-class minimum confidence (tuned for PCB parts; extend as new labels are added)
        self.class_conf_thresholds = {
            'Cap1': 0.25,
            'Cap2': 0.25,
            'Cap3': 0.25,
            'Cap4': 0.25,
            'MOSFET': 0.3,
            'Mov': 0.3,
            'Resistor': 0.25,
            'Resestor': 0.25,
            'Transformer': 0.35,
            'Arduino Uno': 0.6 # High confidence for board detection
        }
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"Enhanced detector initialized on {self.device}")
    
    def _initialize_models(self):
        """Initialize detection models."""
        if YOLO_AVAILABLE:
            try:
                # Load trained Circuit-AI PCB component detection model
                # Path relative to this file: ../../pcb_runs/real_pcb_v1/weights/best.pt
                trained_model_path = os.path.join(os.path.dirname(__file__), '../../pcb_runs/real_pcb_v1/weights/best.pt')
                trained_model_path = os.path.abspath(trained_model_path)
                
                if os.path.exists(trained_model_path):
                    self.models['yolo'] = YOLO(trained_model_path)
                    logger.info(f"✅ Loaded trained Circuit-AI PCB model from {trained_model_path}")
                    self.model_source = f"trained:{os.path.basename(trained_model_path)}"
                    self.custom_model_found = True
                else:
                    self.models['yolo'] = YOLO('yolov8n.pt')
                    logger.warning(f"⚠️  Trained model not found at {trained_model_path}, using pretrained YOLOv8n")
                    self.model_source = "yolov8n-fallback"
                    self.fallback_used = True
                
                self.models['yolo'].to(self.device)
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}")
                self.model_source = "yolo-load-failed"
        else:
            self.model_source = "yolo-unavailable"
            self.fallback_used = True
        
        self.models['custom'] = None
    
    def detect_components(self, image: np.ndarray, 
                         methods: List[DetectionMethod] = None,
                         enable_ocr: bool = True,
                         enable_quality_assessment: bool = True,
                         mobile_optimized: bool = False) -> List[ComponentDetection]:
        """Detect components using multiple methods."""
        if methods is None:
            methods = [DetectionMethod.ENSEMBLE]

        image = self._normalize_image(image, mobile_optimized)
        all_detections = []
        
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
        
        for future in futures:
            try:
                detections = future.result(timeout=30)
                all_detections.extend(detections)
            except Exception as e:
                logger.error(f"Detection method failed: {e}")
        
        all_detections = self._apply_class_thresholds(all_detections)
        if enable_quality_assessment:
            all_detections = self._assess_quality(all_detections)
        
        all_detections = self._merge_detections(all_detections)
        all_detections.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_detections
    
    def _detect_ensemble(self, image: np.ndarray, enable_ocr: bool) -> List[ComponentDetection]:
        """Ensemble detection using multiple methods."""
        detections = []
        
        if 'yolo' in self.models:
            yolo_detections = self._detect_with_yolo(image)
            detections.extend(yolo_detections)
        
        classical_detections = self._detect_with_classical(image)
        detections.extend(classical_detections)
        
        if enable_ocr and OCR_AVAILABLE:
            self._enrich_with_ocr(image, detections)
        
        return detections
    
    def _detect_with_yolo(self, image: np.ndarray) -> List[ComponentDetection]:
        """Detect components using YOLO."""
        if 'yolo' not in self.models:
            return []
        
        try:
            results = self.models['yolo'](image, verbose=False)
            detections = []
            
            for r in results:
                if hasattr(r, 'boxes') and r.boxes is not None:
                    boxes = r.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        confidence = box.conf[0].item()
                        class_id = int(box.cls[0].item())
                        
                        class_name = self._map_class_id_to_name(class_id)
                        
                        detection = ComponentDetection(
                            bbox=[x1, y1, x2, y2],
                            class_name=class_name,
                            confidence=confidence,
                            method=DetectionMethod.YOLO,
                            metadata={
                                'class_id': class_id,
                                'model': 'yolo'
                            }
                        )
                        
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
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.quality_thresholds['min_area']:
                    continue
                
                x, y, w, h = cv2.boundingRect(contour)
                x1, y1, x2, y2 = x, y, x + w, y + h
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio > self.quality_thresholds['max_aspect_ratio']:
                    continue
                
                class_name = self._classify_by_shape(contour, area, aspect_ratio)
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
                
                self._calculate_detection_properties(detection)
                detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Classical detection failed: {e}")
            return []
    
    def _enrich_with_ocr(self, image: np.ndarray, detections: List[ComponentDetection]):
        """Enrich detections with OCR text."""
        if not OCR_AVAILABLE:
            return
        
        try:
            for detection in detections:
                x1, y1, x2, y2 = [int(coord) for coord in detection.bbox]
                # Clamp coordinates
                h, w = image.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                roi = image[y1:y2, x1:x2]
                
                if roi.size == 0 or roi.shape[0] < 5 or roi.shape[1] < 5:
                    continue
                
                try:
                    text = pytesseract.image_to_string(roi, config='--psm 6')
                    text = text.strip()
                    
                    if text and len(text) > 1:
                        detection.text_content = text
                        detection.metadata['ocr_confidence'] = 0.8
                except Exception as e:
                    # OCR errors are common on small noisy patches, just ignore
                    pass
                    
        except Exception as e:
            logger.error(f"OCR enrichment loop failed: {e}")
    
    def _assess_quality(self, detections: List[ComponentDetection]) -> List[ComponentDetection]:
        """Assess quality of detections and filter low-quality ones."""
        quality_detections = []
        for detection in detections:
            quality_score = self._calculate_quality_score(detection)
            detection.quality_score = quality_score
            if quality_score >= self.quality_thresholds['min_confidence']:
                quality_detections.append(detection)
        return quality_detections
    
    def _calculate_quality_score(self, detection: ComponentDetection) -> float:
        """Calculate quality score for a detection."""
        score = detection.confidence
        if detection.area and detection.area < 200: score *= 0.8
        if detection.aspect_ratio and detection.aspect_ratio > 5.0: score *= 0.9
        if detection.text_content: score *= 1.1
        if detection.method == DetectionMethod.ENSEMBLE: score *= 1.05
        return min(score, 1.0)
    
    def _merge_detections(self, detections: List[ComponentDetection]) -> List[ComponentDetection]:
        """Merge overlapping detections."""
        if not detections: return []
        detections.sort(key=lambda x: x.confidence, reverse=True)
        merged = []
        used = set()
        
        for i, detection in enumerate(detections):
            if i in used: continue
            merged_group = [detection]
            used.add(i)
            for j, other in enumerate(detections[i+1:], i+1):
                if j in used: continue
                if self._detections_overlap(detection, other):
                    merged_group.append(other)
                    used.add(j)
            
            if len(merged_group) > 1:
                merged.append(self._merge_detection_group(merged_group))
            else:
                merged.append(detection)
        return merged
    
    def _detections_overlap(self, det1: ComponentDetection, det2: ComponentDetection, threshold: float = 0.5) -> bool:
        """Check if two detections overlap significantly."""
        x1_1, y1_1, x2_1, y2_1 = det1.bbox
        x1_2, y1_2, x2_2, y2_2 = det2.bbox
        x1_i = max(x1_1, x1_2); y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2); y2_i = min(y2_1, y2_2)
        if x2_i <= x1_i or y2_i <= y1_i: return False
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2) 
        union = area1 + area2 - intersection
        iou = intersection / union if union > 0 else 0
        return iou > threshold
    
    def _merge_detection_group(self, detections: List[ComponentDetection]) -> ComponentDetection:
        """Merge a group of overlapping detections."""
        base = max(detections, key=lambda x: x.confidence)
        total_weight = sum(d.confidence for d in detections)
        weighted_bbox = [0.0]*4
        for detection in detections:
            weight = detection.confidence / total_weight
            for i in range(4): weighted_bbox[i] += detection.bbox[i] * weight
        
        merged = ComponentDetection(
            bbox=weighted_bbox,
            class_name=base.class_name,
            confidence=sum(d.confidence for d in detections) / len(detections),
            method=DetectionMethod.ENSEMBLE,
            metadata={'merged_count': len(detections)}
        )
        self._calculate_detection_properties(merged)
        return merged
    
    def _calculate_detection_properties(self, detection: ComponentDetection):
        """Calculate additional properties for a detection."""
        x1, y1, x2, y2 = detection.bbox
        detection.center = ((x1 + x2) / 2, (y1 + y2) / 2)
        detection.area = (x2 - x1) * (y2 - y1)
        width = x2 - x1
        height = y2 - y1
        detection.aspect_ratio = width / height if height > 0 else 0

    def _normalize_image(self, image: np.ndarray, mobile_optimized: bool) -> np.ndarray:
        """Ensure image is RGB uint8 and optionally downscale."""
        img = image
        if img.dtype != np.uint8: img = np.clip(img, 0, 255).astype(np.uint8)
        if img.ndim == 2: img = np.stack([img] * 3, axis=-1)
        elif img.ndim == 3 and img.shape[2] == 4: img = img[:, :, :3]
        if mobile_optimized:
            max_dim = max(img.shape[0], img.shape[1])
            if max_dim > 4096:
                scale = 4096 / float(max_dim)
                img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)), interpolation=cv2.INTER_AREA)
        return img

    def _apply_class_thresholds(self, detections: List[ComponentDetection]) -> List[ComponentDetection]:
        """Filter detections using per-class confidence thresholds."""
        filtered = []
        for det in detections:
            threshold = self.class_conf_thresholds.get(det.class_name, self.quality_thresholds['min_confidence'])
            if det.confidence >= threshold: filtered.append(det)
        return filtered

    def _map_class_id_to_name(self, class_id: int) -> str:
        """Map YOLO class ID to component name."""
        if class_id < len(self.component_classes): return self.component_classes[class_id]
        return 'unknown'
    
    def _classify_by_shape(self, contour: np.ndarray, area: float, aspect_ratio: float) -> str:
        """Classify component based on shape and size."""
        if aspect_ratio > 3.0: return 'resistor'
        elif aspect_ratio < 0.5: return 'capacitor'
        elif area > 1000: return 'ic_chip'
        else: return 'connector'
    
    def _calculate_classical_confidence(self, contour: np.ndarray, area: float, aspect_ratio: float) -> float:
        """Calculate confidence for classical detection."""
        confidence = 0.5
        if 100 <= area <= 5000: confidence += 0.2
        if 0.2 <= aspect_ratio <= 5.0: confidence += 0.2
        if len(contour) > 10: confidence += 0.1
        return min(confidence, 1.0)
    
    def draw_detections(self, image: np.ndarray, detections: List[ComponentDetection], show_labels: bool = True, show_confidence: bool = True) -> np.ndarray:
        """Draw detections on image."""
        img_copy = image.copy()
        for detection in detections:
            x1, y1, x2, y2 = [int(coord) for coord in detection.bbox]
            color = (0, 255, 0) if detection.confidence > 0.8 else ((255, 255, 0) if detection.confidence > 0.6 else (255, 0, 0))
            cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, 2)
            if show_labels:
                label = f"{detection.class_name}" + (f" {detection.confidence:.2f}" if show_confidence else "")
                t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                cv2.rectangle(img_copy, (x1, y1 - t_size[1] - 5), (x1 + t_size[0], y1), color, -1)
                cv2.putText(img_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return img_copy

    def draw_pinout_overlay(self, image: np.ndarray, board_detection: ComponentDetection, board_info: Dict[str, Any]) -> np.ndarray:
        """Draws pinout labels and locations on an image for a detected board."""
        img_copy = image.copy()
        x1_img, y1_img, x2_img, y2_img = [int(coord) for coord in board_detection.bbox]
        board_width_px = x2_img - x1_img
        board_height_px = y2_img - y1_img

        board_width_mm = board_info.get('bbox_mm', {}).get('x')
        board_height_mm = board_info.get('bbox_mm', {}).get('y')

        if not board_width_mm or not board_height_mm: return img_copy

        px_per_mm_x = board_width_px / board_width_mm
        px_per_mm_y = board_height_px / board_height_mm
        
        headers = board_info.get('headers', [])
        for header in headers:
            for pin in header.get('pins', []):
                pin_name = pin.get('name')
                pin_x_mm = pin.get('x_mm')
                pin_y_mm = pin.get('y_mm')
                if pin_name and pin_x_mm is not None and pin_y_mm is not None:
                    # Assuming pin coords are from bottom-left or top-left standard
                    # Here we assume board definition is top-left origin (standard) but image Y is down
                    pin_x_px = int(x1_img + pin_x_mm * px_per_mm_x)
                    pin_y_px = int(y2_img - pin_y_mm * px_per_mm_y) # Flip Y logic: y2 is bottom of board
                    
                    cv2.circle(img_copy, (pin_x_px, pin_y_px), radius=4, color=(0, 255, 255), thickness=-1)
                    cv2.putText(img_copy, pin_name, (pin_x_px + 7, pin_y_px + 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return img_copy
