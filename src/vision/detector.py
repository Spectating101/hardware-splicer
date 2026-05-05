import torch
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config import settings
from src.vision.component_taxonomy import model_class_name
from src.vision.model_resolver import is_generic_yolo_path, resolve_pcb_model_path, resolve_pcb_model_paths
from src.vision.image_polisher import polish_for_inference
from src.vision.confidence_thresholds import DEFAULT_CONFIDENCE, get_confidence_threshold

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
        self.loaded_model_path = None
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.default_backend = getattr(settings, 'detection_backend', 'classical')
        self.ocr_enabled_default = getattr(settings, 'enable_ocr', True)
        self.ocr_lang = getattr(settings, 'ocr_lang', 'eng')
        self.yolo_min_confidence = float(getattr(settings, "yolo_min_confidence", 0.2))
        self.yolo_nms_iou = float(getattr(settings, "yolo_nms_iou", 0.45))

        # Lazy-load the heavy model to keep imports fast and make unit tests easy to patch.
        self.model = None
        self.supplemental_models: Dict[str, Any] = {}
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
        resolved_path = resolve_pcb_model_path(self.model_path)
        if not resolved_path:
            if is_generic_yolo_path(self.model_path):
                logger.warning(
                    f"Configured YOLO model {self.model_path} is generic COCO, not a PCB detector; "
                    "using classical CV fallback"
                )
            else:
                logger.warning(f"PCB YOLO model not found at {self.model_path}; using classical CV fallback")
            return False
        try:
            self.model = YOLO(resolved_path)
            self.model.to(self.device)
            self.loaded_model_path = resolved_path
            logger.info(f"Loaded PCB YOLO model from {resolved_path}")
            return True
        except Exception as e:
            self.model = None
            self.loaded_model_path = None
            logger.warning(f"PCB YOLO unavailable ({resolved_path}): {e}; using classical CV fallback")
            return False
    
    def detect_components(self, image: np.ndarray, backend: Optional[str] = None, enable_ocr: Optional[bool] = None) -> List[Dict[str, Any]]:
        selected_backend = (backend or self.default_backend).lower()
        use_ocr = self.ocr_enabled_default if enable_ocr is None else enable_ocr

        detections: List[Dict[str, Any]] = []
        try:
            if selected_backend == 'yolo':
                detections = self._detect_with_yolo(image)
            elif selected_backend in ('hybrid', 'ensemble'):
                detections = self._detect_with_yolo(image)
                if not detections:
                    detections = self._detect_with_supplemental_yolo(image)
                if not detections:
                    detections = self._detect_with_classical_cv(image)
                    for det in detections:
                        det.setdefault("provenance", {})["backend"] = "classical-fallback"
                elif self._should_supplement_yolo(detections):
                    learned_supplemental = self._detect_with_supplemental_yolo(image)
                    detections = self._merge_detections(detections, learned_supplemental)
                    if self._should_supplement_yolo(detections):
                        supplemental = self._detect_with_classical_cv(image)
                        for det in supplemental:
                            det.setdefault("provenance", {})["backend"] = "classical-supplement"
                        detections = self._merge_detections(detections, supplemental)
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

    def _should_supplement_yolo(self, detections: List[Dict[str, Any]]) -> bool:
        if len(detections) < 3:
            return True
        semantic_confidences = [
            float(det.get("semantic_confidence", det.get("confidence", 0.0)))
            for det in detections
            if isinstance(det.get("semantic_confidence", det.get("confidence")), (int, float))
        ]
        if not semantic_confidences:
            return True
        return (sum(semantic_confidences) / len(semantic_confidences)) < 0.35

    def _merge_detections(
        self,
        base_detections: List[Dict[str, Any]],
        supplemental_detections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged = list(base_detections)
        for candidate in supplemental_detections:
            if all(self._bbox_iou(candidate.get("bbox"), existing.get("bbox")) < 0.2 for existing in merged):
                merged.append(candidate)
        return merged

    @staticmethod
    def _bbox_iou(box_a: Any, box_b: Any) -> float:
        if not isinstance(box_a, (list, tuple)) or not isinstance(box_b, (list, tuple)):
            return 0.0
        if len(box_a) != 4 or len(box_b) != 4:
            return 0.0
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]
        inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
        inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter_area
        return inter_area / union if union > 0 else 0.0

    def _detect_with_yolo(self, image: np.ndarray) -> List[Dict[str, Any]]:
        if not self._ensure_yolo_model():
            return []
        return self._detect_with_model(image, self.model, self.loaded_model_path, "yolo")

    def _detect_with_supplemental_yolo(self, image: np.ndarray) -> List[Dict[str, Any]]:
        if YOLO is None:
            return []
        primary = self.loaded_model_path or resolve_pcb_model_path(self.model_path)
        supplemental_paths = [
            path for path in resolve_pcb_model_paths(self.model_path)
            if path != primary
        ]
        if not supplemental_paths:
            return []

        detections: List[Dict[str, Any]] = []
        for model_path in supplemental_paths[:1]:
            model = self.supplemental_models.get(model_path)
            if model is None:
                try:
                    model = YOLO(model_path)
                    model.to(self.device)
                    self.supplemental_models[model_path] = model
                    logger.info(f"Loaded supplemental PCB YOLO model from {model_path}")
                except Exception as e:
                    logger.warning(f"Supplemental PCB YOLO unavailable ({model_path}): {e}")
                    continue
            detections.extend(self._detect_with_model(image, model, model_path, "yolo-supplement"))
        return detections

    def _detect_with_model(self, image: np.ndarray, model: Any, model_path: Optional[str], backend: str) -> List[Dict[str, Any]]:
        model_image = image
        if model_image.dtype != np.uint8:
            if model_image.max(initial=0.0) <= 1.0:
                model_image = (np.clip(model_image, 0.0, 1.0) * 255).astype(np.uint8)
            else:
                model_image = np.clip(model_image, 0, 255).astype(np.uint8)
        results = model(model_image, verbose=False)
        detections = []
        for r in results:
            if getattr(r, 'boxes', None) is not None:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cls_raw = box.cls[0] if hasattr(box.cls, "__len__") else box.cls
                    cls_id = int(cls_raw)
                    class_name, raw_class_name = model_class_name(model, cls_id, self.component_classes)
                    conf_raw = box.conf[0] if hasattr(box.conf, "__len__") else box.conf
                    conf = float(conf_raw)
                    threshold = get_confidence_threshold(class_name) if class_name else DEFAULT_CONFIDENCE
                    if conf < max(threshold, self.yolo_min_confidence):
                        continue
                    detections.append(
                        {
                            "bbox": [float(x1), float(y1), float(x2), float(y2)],
                            "confidence": conf,
                            "class_id": cls_id,
                            "class_name": class_name,
                            "center": [float((x1 + x2) / 2.0), float((y1 + y2) / 2.0)],
                            "semantic_confidence": conf,
                            "provenance": {
                                "backend": backend,
                                "model_path": model_path,
                                "raw_class_name": raw_class_name,
                                "threshold": threshold,
                            },
                        }
                    )
        return self._suppress_overlapping_detections(detections)

    def _suppress_overlapping_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if cv2 is None:
            return sorted(detections, key=lambda det: float(det.get("confidence", 0.0)), reverse=True)
        if len(detections) <= 1:
            return detections

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for det in detections:
            grouped.setdefault(str(det.get("class_name") or "unknown"), []).append(det)

        suppressed: List[Dict[str, Any]] = []
        for dets in grouped.values():
            if len(dets) == 1:
                suppressed.extend(dets)
                continue

            boxes_xyxy = np.asarray([det.get("bbox", []) for det in dets], dtype=float)
            scores = np.asarray([float(det.get("confidence", 0.0)) for det in dets], dtype=float)
            if boxes_xyxy.ndim != 2 or boxes_xyxy.shape[1] != 4:
                suppressed.extend(dets)
                continue

            widths = np.clip(boxes_xyxy[:, 2] - boxes_xyxy[:, 0], 0.0, None)
            heights = np.clip(boxes_xyxy[:, 3] - boxes_xyxy[:, 1], 0.0, None)
            boxes_xywh = np.column_stack([boxes_xyxy[:, 0], boxes_xyxy[:, 1], widths, heights])

            keep = cv2.dnn.NMSBoxes(
                boxes_xywh.astype(int).tolist(),
                scores.tolist(),
                0.0,
                self.yolo_nms_iou,
            )
            if len(keep) == 0:
                continue

            for raw in keep:
                idx = int(raw[0]) if isinstance(raw, (list, tuple, np.ndarray)) else int(raw)
                if 0 <= idx < len(dets):
                    suppressed.append(dets[idx])

        return sorted(suppressed, key=lambda det: float(det.get("confidence", 0.0)), reverse=True)

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
                    "semantic_confidence": min(conf, 0.65),
                    "class_id": self.component_classes.index(cls) if cls in self.component_classes else -1,
                    "class_name": cls,
                    "center": [float(x + bw / 2.0), float(y + bh / 2.0)],
                    "provenance": {
                        "backend": "classical",
                        "method": "contour_shape_heuristic",
                        "limitations": [
                            "candidate localization only",
                            "semantic class is shape-based and needs review",
                        ],
                    },
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

    def preprocess_image(self, image: np.ndarray, *, include_metadata: bool = False) -> np.ndarray:
        """
        Normalize and optionally polish input image for model inference.

        include_metadata=True returns ``(image, metadata)`` for debugging and audit.
        """
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

        processed, metadata = polish_for_inference(img)
        if include_metadata:
            return processed, metadata
        return processed

    def get_detection_summary(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        by_backend: Dict[str, int] = {}
        confidences: list[float] = []
        semantic_confidences: list[float] = []
        for det in detections or []:
            name = det.get("class_name") or "unknown"
            by_type[name] = by_type.get(name, 0) + 1
            provenance = det.get("provenance") if isinstance(det.get("provenance"), dict) else {}
            backend = provenance.get("backend") or "unknown"
            by_backend[backend] = by_backend.get(backend, 0) + 1
            conf = det.get("confidence")
            if isinstance(conf, (int, float)):
                confidences.append(float(conf))
            semantic_conf = det.get("semantic_confidence")
            if isinstance(semantic_conf, (int, float)):
                semantic_confidences.append(float(semantic_conf))

        avg_conf = (sum(confidences) / len(confidences)) if confidences else 0.0
        avg_semantic_conf = (sum(semantic_confidences) / len(semantic_confidences)) if semantic_confidences else avg_conf
        heuristic_count = sum(
            count
            for backend, count in by_backend.items()
            if backend in {"classical", "classical-fallback", "classical-supplement"}
        )
        review_required = heuristic_count > 0

        if avg_conf >= 0.75 and not review_required:
            quality = "high"
        elif avg_conf >= 0.5:
            quality = "medium"
        else:
            quality = "low"
        if avg_semantic_conf >= 0.75 and not review_required:
            semantic_quality = "high"
        elif avg_semantic_conf >= 0.45:
            semantic_quality = "candidate"
        else:
            semantic_quality = "low"

        return {
            "total_components": sum(by_type.values()),
            "components_by_type": by_type,
            "backend_breakdown": by_backend,
            "average_confidence": avg_conf,
            "average_semantic_confidence": avg_semantic_conf,
            "detection_quality": quality,
            "semantic_quality": semantic_quality,
            "review_required": review_required,
            "limitations": (
                ["Some detections are heuristic candidates; verify class labels against the image."]
                if review_required else []
            ),
        }
