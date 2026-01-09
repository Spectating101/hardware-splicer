import torch
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config import settings

# Optional dependencies
try:
    import cv2  # type: ignore
except Exception:
    cv2 = None

try:
    from ultralytics import YOLO  # type: ignore
except Exception:
    YOLO = None

# Import robust OCR Engine
from src.vision.ocr_engine import OCREngine

class ComponentDetector:
    """YOLO-based component detector for PCB analysis."""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize the component detector with configurable backend."""
        self.model_path = model_path or settings.yolo_model_path
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.default_backend = getattr(settings, 'detection_backend', 'classical')
        self.ocr_enabled_default = getattr(settings, 'enable_ocr', True)
        self.ocr_lang = getattr(settings, 'ocr_lang', 'eng')

        # Lazy-load the heavy model to keep imports fast and make unit tests easy to patch.
        self.model = None
        if YOLO is None:
            logger.warning("ultralytics not installed; YOLO backend disabled")

        self.component_classes = [
            'ic_chip', 'capacitor', 'resistor', 'connector',
            'transformer', 'diode', 'led', 'transistor'
        ]
        
        # Initialize OCR
        self.ocr_engine = OCREngine()

    def _ensure_yolo_model(self) -> bool:
        if self.model is not None:
            return True
        if YOLO is None:
            return False
        try:
            self.model = YOLO(self.model_path)
            self.model.to(self.device)
            logger.info(f"Loaded YOLO model from {self.model_path}")
            return True
        except Exception as e:
            try:
                self.model = YOLO("yolov8n.pt")
                self.model.to(self.device)
                logger.warning(f"Using default YOLO model due to: {e}")
                return True
            except Exception as e2:
                self.model = None
                logger.warning(f"YOLO unavailable: {e2}")
                return False
    
    def detect_components(self, image: np.ndarray, backend: Optional[str] = None, enable_ocr: Optional[bool] = None) -> List[Dict[str, Any]]:
        selected_backend = (backend or self.default_backend).lower()
        use_ocr = self.ocr_enabled_default if enable_ocr is None else enable_ocr

        detections: List[Dict[str, Any]] = []
        try:
            if selected_backend == 'yolo':
                detections = self._detect_with_yolo(image)
            elif selected_backend == 'classical':
                detections = self._detect_with_classical_cv(image)
            elif selected_backend == 'remote' and settings.remote_detect_url:
                detections = self._detect_remote(image)
            else:
                detections = self._detect_with_classical_cv(image)

            if use_ocr and len(detections) > 0:
                self._enrich_with_ocr(image, detections)

            logger.info(f"Detected {len(detections)} components (backend={selected_backend}, ocr={use_ocr})")
            return detections
        except Exception as e:
            logger.error(f"Error in component detection: {e}")
            return []

    def _detect_with_yolo(self, image: np.ndarray) -> List[Dict[str, Any]]:
        if not self._ensure_yolo_model():
            return self._detect_with_classical_cv(image)
        results = self.model(image)
        detections = []
        for r in results:
            if getattr(r, 'boxes', None) is not None:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cls_raw = box.cls[0] if hasattr(box.cls, "__len__") else box.cls
                    cls_id = int(cls_raw)
                    class_name = self.component_classes[cls_id] if cls_id < len(self.component_classes) else 'unknown'
                    conf_raw = box.conf[0] if hasattr(box.conf, "__len__") else box.conf
                    detections.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'confidence': float(conf_raw),
                        'class_id': cls_id,
                        'class_name': class_name,
                        'center': [float((x1 + x2) / 2.0), float((y1 + y2) / 2.0)]
                    })
        return detections

    def _detect_with_classical_cv(self, image: np.ndarray) -> List[Dict[str, Any]]:
        if cv2 is None:
            logger.warning("OpenCV not installed; classical backend cannot run. Returning empty detections.")
            return []

        # Ensure uint8 RGB
        img = image.copy()
        if img.dtype != np.uint8:
            img = (np.clip(img, 0, 1) * 255).astype(np.uint8) if img.max() <= 1.0 else img.astype(np.uint8)

        if img.ndim == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray_blur, 60, 160)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _hierarchy = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: List[Dict[str, Any]] = []
        h, w = gray.shape[:2]
        area_img = float(h * w)
        if area_img <= 0:
            return []

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            if area < 0.0003 * area_img or area > 0.25 * area_img:
                continue

            aspect = (bw / float(bh)) if bh > 0 else 0.0
            rect_area = float(bw * bh)
            contour_area = float(cv2.contourArea(cnt))
            rectangularity = (contour_area / rect_area) if rect_area > 0 else 0.0

            roi = dilated[y : y + bh, x : x + bw]
            edge_density = float(np.count_nonzero(roi)) / float(roi.size) if roi.size else 0.0
            area_norm = area / area_img

            if area > 0.01 * area_img and 0.6 <= aspect <= 2.0:
                cls = "ic_chip"
                base = 0.7
            elif 2.5 <= aspect <= 12.0 and area > 0.002 * area_img:
                cls = "connector"
                base = 0.6
            else:
                cls = "resistor" if aspect >= 1.2 else "capacitor"
                base = 0.5

            w1 = float(getattr(settings, "cv_aspect_weight", 0.35))
            w2 = float(getattr(settings, "cv_edge_density_weight", 0.35))
            w3 = float(getattr(settings, "cv_rectangularity_weight", 0.2))
            w4 = float(getattr(settings, "cv_area_norm_weight", 0.1))

            aspect_score = 1.0 - min(abs(aspect - 1.0) / 5.0, 1.0)
            conf = base + (w1 * aspect_score + w2 * edge_density + w3 * rectangularity + w4 * min(area_norm / 0.02, 1.0)) * 0.3
            conf = float(max(0.0, min(conf, 0.99)))

            x1, y1, x2, y2 = float(x), float(y), float(x + bw), float(y + bh)
            detections.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": self.component_classes.index(cls) if cls in self.component_classes else -1,
                    "class_name": cls,
                    "center": [float(x + bw / 2.0), float(y + bh / 2.0)],
                }
            )

        return detections

    def _detect_remote(self, image: np.ndarray) -> List[Dict[str, Any]]:
        url = getattr(settings, "remote_detect_url", None)
        if not url:
            return []
        try:
            import base64
            from io import BytesIO

            import requests  # type: ignore

            pil = Image.fromarray(image)
            buf = BytesIO()
            pil.save(buf, format="PNG")
            payload = {"image_base64": base64.b64encode(buf.getvalue()).decode("utf-8")}
            r = requests.post(url, json=payload, timeout=20)
            r.raise_for_status()
            data = r.json()

            dets: List[Dict[str, Any]] = []
            for d in data.get("detections", []) or []:
                dets.append(
                    {
                        "bbox": [float(x) for x in d.get("bbox", [0, 0, 0, 0])],
                        "confidence": float(d.get("confidence", 0.0)),
                        "class_id": int(d.get("class_id", -1)),
                        "class_name": str(d.get("class_name", "unknown")),
                        "center": [float(c) for c in d.get("center", [0, 0])],
                        "provenance": {"backend": "remote"},
                    }
                )
            return dets
        except Exception as e:
            logger.warning(f"Remote detection failed: {e}")
            return []

    def _enrich_with_ocr(self, image: np.ndarray, detections: List[Dict[str, Any]]) -> None:
        if cv2 is None:
            return
        img = image.copy()
        if img.dtype != np.uint8:
            img = (np.clip(img, 0, 1) * 255).astype(np.uint8) if img.max() <= 1.0 else img.astype(np.uint8)
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        for det in detections:
            if det.get('class_name') not in ('ic_chip', 'connector'):
                continue
            x1, y1, x2, y2 = [int(v) for v in det['bbox']]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(gray.shape[1]-1, x2), min(gray.shape[0]-1, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            
            # Use EasyOCR engine
            text = self.ocr_engine.read_text(roi)
            
            cleaned = (text or "").strip().replace("\n", " ").replace("\r", " ")
            cleaned = ' '.join(cleaned.split())
            det['ocr_text'] = cleaned
            part_number = None
            if cleaned:
                tokens = [t for t in cleaned.split(' ') if len(t) >= 3]
                if tokens:
                    part_number = max(tokens, key=len)
            det['part_number'] = part_number

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        img = np.asarray(image)
        if img.ndim == 2:
            img = np.stack([img, img, img], axis=-1)
        elif img.ndim == 3:
            if img.shape[-1] == 4:
                img = img[..., :3]
            elif img.shape[-1] != 3:
                raise ValueError(f"Unsupported image shape: {img.shape}")
        else:
            raise ValueError(f"Unsupported image shape: {img.shape}")

        img = img.astype(np.float32, copy=False)
        if img.max(initial=0.0) > 1.0:
            img = img / 255.0
        img = np.clip(img, 0.0, 1.0)
        return img

    def get_detection_summary(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        confidences: list[float] = []
        for det in detections or []:
            name = det.get("class_name") or "unknown"
            by_type[name] = by_type.get(name, 0) + 1
            conf = det.get("confidence")
            if isinstance(conf, (int, float)):
                confidences.append(float(conf))

        avg_conf = (sum(confidences) / len(confidences)) if confidences else 0.0
        if avg_conf >= 0.75:
            quality = "high"
        elif avg_conf >= 0.5:
            quality = "medium"
        else:
            quality = "low"
        return {
            "total_components": sum(by_type.values()),
            "components_by_type": by_type,
            "average_confidence": avg_conf,
            "detection_quality": quality,
        }
