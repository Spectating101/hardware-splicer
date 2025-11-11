"""
Model Loader for Circuit.AI

Lazy loading of YOLO models for production serving.
"""

import os
from typing import Optional, Dict, Any
from loguru import logger
import numpy as np
import cv2
from .confidence_thresholds import get_confidence_threshold, filter_detections_by_confidence

try:
    from ultralytics import YOLO
except ImportError:
    logger.warning("Ultralytics not available - model loading disabled")
    YOLO = None

# Global model cache
_models: Dict[str, Any] = {}

def get_detector(model_name: str = "electrocom61_v1") -> Optional[Any]:
    """
    Get a YOLO detector model with lazy loading.
    
    Args:
        model_name: Name of the model to load
        
    Returns:
        YOLO model instance or None if not available
    """
    if YOLO is None:
        logger.error("Ultralytics not available")
        return None
    
    if model_name not in _models:
        model_path = f"models/pcb/{model_name}.onnx"
        
        if not os.path.exists(model_path):
            logger.error(f"Model not found: {model_path}")
            return None
        
        try:
            logger.info(f"Loading model: {model_path}")
            _models[model_name] = YOLO(model_path)
            logger.info(f"Model {model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return None
    
    return _models[model_name]

def preprocess_image(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Preprocess image bytes for YOLO inference.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        Preprocessed image array or None if failed
    """
    try:
        # Decode image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error("Failed to decode image")
            return None
        
        return img
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        return None

def postprocess_detections(results, confidence_threshold: float = 0.25, use_per_class_thresholds: bool = True) -> list:
    """
    Postprocess YOLO detection results with per-class confidence thresholds.
    
    Args:
        results: YOLO results object
        confidence_threshold: Default minimum confidence for detections
        use_per_class_thresholds: Whether to use per-class confidence thresholds
        
    Returns:
        List of detection dictionaries
    """
    detections = []
    
    if not results or len(results) == 0:
        return detections
    
    result = results[0]
    
    if result.boxes is None or len(result.boxes) == 0:
        return detections
    
    # Extract boxes, classes, and confidences
    boxes = result.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
    classes = result.boxes.cls.cpu().numpy().astype(int)
    confidences = result.boxes.conf.cpu().numpy()
    
    # First pass: filter by default confidence threshold
    valid_indices = confidences >= confidence_threshold
    
    for i, (box, cls, conf) in enumerate(zip(boxes, classes, confidences)):
        if not valid_indices[i]:
            continue
        
        # Get class name
        class_name = result.names[int(cls)]
        
        # Apply per-class threshold if enabled
        if use_per_class_thresholds:
            class_threshold = get_confidence_threshold(class_name)
            if conf < class_threshold:
                continue
        
        # Convert to xywh format (center x, center y, width, height)
        x1, y1, x2, y2 = box
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        width = x2 - x1
        height = y2 - y1
        
        detection = {
            "class_id": int(cls),
            "class_name": class_name,
            "confidence": float(conf),
            "threshold_used": get_confidence_threshold(class_name) if use_per_class_thresholds else confidence_threshold,
            "bbox": {
                "x": float(center_x),
                "y": float(center_y),
                "width": float(width),
                "height": float(height)
            },
            "bbox_xyxy": {
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y2)
            }
        }
        
        detections.append(detection)
    
    return detections

def get_available_models() -> list:
    """
    Get list of available model files.
    
    Returns:
        List of available model names
    """
    models_dir = "models/pcb"
    if not os.path.exists(models_dir):
        return []
    
    models = []
    for file in os.listdir(models_dir):
        if file.endswith(('.onnx', '.pt')):
            model_name = os.path.splitext(file)[0]
            models.append(model_name)
    
    return models

def clear_model_cache():
    """Clear the model cache to free memory."""
    global _models
    _models.clear()
    logger.info("Model cache cleared")
