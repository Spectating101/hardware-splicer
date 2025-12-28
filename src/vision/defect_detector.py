"""
Defect Detection Module for PCB Inspection

Detects solder defects, component damage, substrate issues, and electrical hazards.
Supports YOLOv8 model + classical CV fallback for robustness.

Author: Dum-E Vision System
Version: 1.0.0
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DefectDetection:
    """Single defect detection result"""
    defect_type: str
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float
    severity: float  # 0.0-1.0 (0=minor, 1=critical)
    component_id: Optional[str] = None
    description: str = ""
    repair_action: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DefectDetector:
    """
    Multi-modal PCB defect detector.

    Detects:
    - Solder defects (cold joints, bridges, insufficient, excess, tombstoning)
    - Component damage (cracks, burns, misalignment)
    - PCB substrate issues (broken traces, delamination, corrosion)
    - Electrical hazards (shorts, opens, ESD damage)
    """

    # Defect type definitions
    SOLDER_DEFECTS = [
        "cold_joint", "solder_bridge", "insufficient_solder",
        "excess_solder", "tombstoning"
    ]

    COMPONENT_DEFECTS = [
        "cracked_component", "burnt_component", "missing_component",
        "misaligned_component"
    ]

    SUBSTRATE_DEFECTS = [
        "broken_trace", "delamination", "corrosion", "contamination"
    ]

    ELECTRICAL_DEFECTS = [
        "short_circuit", "open_circuit", "esd_damage"
    ]

    def __init__(self, model_path: Optional[str] = None, use_classical_fallback: bool = True):
        """
        Initialize defect detector.

        Args:
            model_path: Path to trained YOLOv8 defect detection model (optional)
            use_classical_fallback: Enable classical CV methods if model fails
        """
        self.model = None
        self.use_classical_fallback = use_classical_fallback

        if model_path and Path(model_path).exists():
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                logger.info(f"Loaded YOLO defect model: {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}. Using classical CV only.")
        else:
            logger.info("No YOLO model provided. Using classical CV detection.")

    def detect_defects(
        self,
        image: np.ndarray,
        component_detections: Optional[List[Dict]] = None,
        confidence_threshold: float = 0.5
    ) -> List[DefectDetection]:
        """
        Detect all defects in PCB image.

        Args:
            image: Input PCB image (BGR format)
            component_detections: Optional list of detected components for context
            confidence_threshold: Minimum confidence for YOLO detections

        Returns:
            List of DefectDetection objects
        """
        defects = []

        # Try YOLO model first
        if self.model is not None:
            try:
                yolo_defects = self._detect_with_yolo(image, confidence_threshold)
                defects.extend(yolo_defects)
                logger.debug(f"YOLO detected {len(yolo_defects)} defects")
            except Exception as e:
                logger.error(f"YOLO detection failed: {e}")

        # Classical CV detection (always run as supplement or fallback)
        if self.use_classical_fallback or self.model is None:
            classical_defects = self._detect_with_classical_cv(image, component_detections)
            defects.extend(classical_defects)
            logger.debug(f"Classical CV detected {len(classical_defects)} defects")

        # Remove duplicates (same defect detected by multiple methods)
        defects = self._deduplicate_detections(defects)

        logger.info(f"Total defects detected: {len(defects)}")
        return defects

    def _detect_with_yolo(self, image: np.ndarray, threshold: float) -> List[DefectDetection]:
        """Run YOLOv8 defect detection"""
        results = self.model(image, conf=threshold, verbose=False)
        defects = []

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                bbox = box.xyxy[0].cpu().numpy().astype(int).tolist()

                defect_type = self.model.names[cls_id]
                severity = self._estimate_severity(defect_type, bbox, image)

                defects.append(DefectDetection(
                    defect_type=defect_type,
                    bbox=bbox,
                    confidence=conf,
                    severity=severity,
                    description=f"YOLO detected {defect_type}",
                    repair_action=self._suggest_repair(defect_type),
                    metadata={"detector": "yolo"}
                ))

        return defects

    def _detect_with_classical_cv(
        self,
        image: np.ndarray,
        component_detections: Optional[List[Dict]] = None
    ) -> List[DefectDetection]:
        """Classical computer vision defect detection"""
        defects = []

        # Convert to different color spaces for analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Detect solder bridges (metallic bridges between pads)
        bridges = self._detect_solder_bridges(image, hsv)
        defects.extend(bridges)

        # Detect burns (dark charred areas)
        burns = self._detect_burns(image, hsv)
        defects.extend(burns)

        # Detect corrosion (green oxidation)
        corrosion = self._detect_corrosion(image, hsv)
        defects.extend(corrosion)

        # Detect broken traces (discontinuities in copper paths)
        broken_traces = self._detect_broken_traces(gray)
        defects.extend(broken_traces)

        # Detect missing components (if we have expected locations)
        if component_detections:
            missing = self._detect_missing_components(image, component_detections)
            defects.extend(missing)

        return defects

    def _detect_solder_bridges(self, image: np.ndarray, hsv: np.ndarray) -> List[DefectDetection]:
        """Detect solder bridges (shorts) between pads"""
        defects = []

        # Silver/metallic color range for solder
        lower_silver = np.array([0, 0, 150])
        upper_silver = np.array([180, 50, 255])

        mask = cv2.inRange(hsv, lower_silver, upper_silver)

        # Morphological operations to find bridges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
        bridges = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Find connected components
        contours, _ = cv2.findContours(bridges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)

            # Filter by size (bridges are thin and elongated)
            if area < 10 or area > 500:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = max(w, h) / (min(w, h) + 1e-6)

            # Bridges are elongated (high aspect ratio)
            if aspect_ratio > 3.0:
                defects.append(DefectDetection(
                    defect_type="solder_bridge",
                    bbox=[x, y, x + w, y + h],
                    confidence=0.7,
                    severity=0.9,  # Critical - causes shorts
                    description=f"Solder bridge detected (aspect ratio: {aspect_ratio:.1f})",
                    repair_action="Remove excess solder with desoldering wick",
                    metadata={"detector": "classical_cv", "area": area, "aspect_ratio": aspect_ratio}
                ))

        return defects

    def _detect_burns(self, image: np.ndarray, hsv: np.ndarray) -> List[DefectDetection]:
        """Detect burnt/charred components"""
        defects = []

        # Dark brown/black color range for burns
        lower_burn = np.array([0, 0, 0])
        upper_burn = np.array([180, 255, 80])

        mask = cv2.inRange(hsv, lower_burn, upper_burn)

        # Remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)

            if area < 50 or area > 5000:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Check if area is actually dark (not just shadow)
            roi = image[y:y+h, x:x+w]
            mean_intensity = cv2.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))[0]

            if mean_intensity < 60:  # Very dark
                defects.append(DefectDetection(
                    defect_type="burnt_component",
                    bbox=[x, y, x + w, y + h],
                    confidence=0.65,
                    severity=0.85,  # High severity - component likely damaged
                    description=f"Burnt area detected (mean intensity: {mean_intensity:.1f})",
                    repair_action="Replace damaged component",
                    metadata={"detector": "classical_cv", "area": area, "intensity": mean_intensity}
                ))

        return defects

    def _detect_corrosion(self, image: np.ndarray, hsv: np.ndarray) -> List[DefectDetection]:
        """Detect green oxidation/corrosion"""
        defects = []

        # Green color range for copper oxidation
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])

        mask = cv2.inRange(hsv, lower_green, upper_green)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)

            if area < 20 or area > 2000:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            defects.append(DefectDetection(
                defect_type="corrosion",
                bbox=[x, y, x + w, y + h],
                confidence=0.6,
                severity=0.5,  # Medium - degrades over time
                description=f"Corrosion detected (area: {area} px)",
                repair_action="Clean with isopropyl alcohol, consider conformal coating",
                metadata={"detector": "classical_cv", "area": area}
            ))

        return defects

    def _detect_broken_traces(self, gray: np.ndarray) -> List[DefectDetection]:
        """Detect broken copper traces"""
        defects = []

        # Edge detection to find discontinuities
        edges = cv2.Canny(gray, 50, 150)

        # Dilate to connect nearby edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        # Find lines (traces)
        lines = cv2.HoughLinesP(dilated, 1, np.pi/180, 50, minLineLength=30, maxLineGap=20)

        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]

                # Check for abrupt endings (potential breaks)
                # This is a simplified heuristic - real breaks need more sophisticated analysis
                length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

                # Look for short isolated segments (potential break indicators)
                if 30 < length < 100:
                    defects.append(DefectDetection(
                        defect_type="broken_trace",
                        bbox=[min(x1, x2)-5, min(y1, y2)-5, max(x1, x2)+5, max(y1, y2)+5],
                        confidence=0.4,  # Low confidence - needs verification
                        severity=0.95,  # Critical if real
                        description=f"Potential trace break (length: {length:.1f} px)",
                        repair_action="Verify with multimeter, repair with solder jumper wire",
                        metadata={"detector": "classical_cv", "length": length}
                    ))

        return defects

    def _detect_missing_components(
        self,
        image: np.ndarray,
        component_detections: List[Dict]
    ) -> List[DefectDetection]:
        """Detect missing components by comparing against expected positions"""
        defects = []

        # This requires a reference board or BOM
        # For now, we'll detect empty pads (solder pads without components)

        # TODO: Implement pad detection + occupancy check
        # This would involve:
        # 1. Detect all solder pads (circular metallic regions)
        # 2. Check if any component detection overlaps with pad
        # 3. Flag empty pads as potential missing components

        return defects

    def _deduplicate_detections(self, defects: List[DefectDetection]) -> List[DefectDetection]:
        """Remove duplicate detections from multiple detectors"""
        if len(defects) <= 1:
            return defects

        unique_defects = []

        for defect in defects:
            # Check if this defect overlaps significantly with existing ones
            is_duplicate = False

            for existing in unique_defects:
                iou = self._calculate_iou(defect.bbox, existing.bbox)

                # If high overlap and same type, it's a duplicate
                if iou > 0.5 and defect.defect_type == existing.defect_type:
                    # Keep the one with higher confidence
                    if defect.confidence > existing.confidence:
                        unique_defects.remove(existing)
                        unique_defects.append(defect)
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_defects.append(defect)

        return unique_defects

    def _calculate_iou(self, bbox1: List[int], bbox2: List[int]) -> float:
        """Calculate Intersection over Union between two bounding boxes"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        # Intersection
        x_inter_min = max(x1_min, x2_min)
        y_inter_min = max(y1_min, y2_min)
        x_inter_max = min(x1_max, x2_max)
        y_inter_max = min(y1_max, y2_max)

        if x_inter_max < x_inter_min or y_inter_max < y_inter_min:
            return 0.0

        inter_area = (x_inter_max - x_inter_min) * (y_inter_max - y_inter_min)

        # Union
        bbox1_area = (x1_max - x1_min) * (y1_max - y1_min)
        bbox2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = bbox1_area + bbox2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def _estimate_severity(self, defect_type: str, bbox: List[int], image: np.ndarray) -> float:
        """Estimate defect severity based on type and visual features"""
        # Base severity by type
        severity_map = {
            # Critical defects (shorts/opens)
            "solder_bridge": 0.9,
            "short_circuit": 1.0,
            "open_circuit": 1.0,
            "broken_trace": 0.95,

            # High severity (component damage)
            "burnt_component": 0.85,
            "cracked_component": 0.8,
            "missing_component": 0.9,

            # Medium severity (solder quality)
            "cold_joint": 0.6,
            "insufficient_solder": 0.65,
            "tombstoning": 0.7,

            # Lower severity (cosmetic/gradual degradation)
            "excess_solder": 0.4,
            "corrosion": 0.5,
            "contamination": 0.3,
            "delamination": 0.7,
        }

        base_severity = severity_map.get(defect_type, 0.5)

        # Adjust based on size (larger defects often more severe)
        x1, y1, x2, y2 = bbox
        area = (x2 - x1) * (y2 - y1)

        if area > 5000:  # Large defect
            base_severity = min(1.0, base_severity + 0.1)

        return base_severity

    def _suggest_repair(self, defect_type: str) -> str:
        """Suggest repair action for defect type"""
        repair_map = {
            "solder_bridge": "Remove excess solder with desoldering wick",
            "cold_joint": "Reheat joint with fresh flux and solder",
            "insufficient_solder": "Add more solder to joint",
            "excess_solder": "Remove excess with desoldering wick",
            "burnt_component": "Replace component, check for shorts",
            "cracked_component": "Replace component",
            "missing_component": "Install missing component per BOM",
            "misaligned_component": "Reflow solder and realign component",
            "broken_trace": "Repair with solder jumper wire or conductive epoxy",
            "corrosion": "Clean with IPA, apply conformal coating",
            "short_circuit": "Identify and remove short, check for damage",
            "open_circuit": "Check for broken traces, repair connections",
            "contamination": "Clean with IPA and lint-free wipes",
            "delamination": "Board may need replacement if severe",
        }

        return repair_map.get(defect_type, "Visual inspection and testing required")


if __name__ == "__main__":
    # Quick test
    import sys

    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        image = cv2.imread(image_path)

        if image is None:
            print(f"Error: Could not load image {image_path}")
            sys.exit(1)

        detector = DefectDetector()
        defects = detector.detect_defects(image)

        print(f"\nDetected {len(defects)} defects:")
        for i, defect in enumerate(defects, 1):
            print(f"\n{i}. {defect.defect_type}")
            print(f"   Severity: {defect.severity:.2f}")
            print(f"   Confidence: {defect.confidence:.2f}")
            print(f"   Repair: {defect.repair_action}")
    else:
        print("Usage: python defect_detector.py <image_path>")
