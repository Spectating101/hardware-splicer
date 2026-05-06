"""Golden-board visual diff for AOI qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


@dataclass
class GoldenDiff:
    defect_type: str
    bbox: List[int]
    confidence: float
    severity: float
    description: str
    metadata: Dict[str, Any]


class GoldenReferenceInspector:
    """Compare a current PCB photo against a golden/reference image."""

    def __init__(self, min_area_ratio: float = 0.00004, diff_threshold: int = 8) -> None:
        self.min_area_ratio = min_area_ratio
        self.diff_threshold = int(diff_threshold)

    def compare(self, reference_image: np.ndarray, current_image: np.ndarray) -> Dict[str, Any]:
        if cv2 is None:
            return {
                "status": "unavailable",
                "mode": "golden_image_diff",
                "defect_count": 0,
                "defects": [],
                "summary": "OpenCV unavailable for golden image diff.",
            }

        ref = self._to_bgr(reference_image)
        cur = self._to_bgr(current_image)
        if ref.shape[:2] != cur.shape[:2]:
            cur = cv2.resize(cur, (ref.shape[1], ref.shape[0]), interpolation=cv2.INTER_LINEAR)

        diff_mask = self._difference_mask(ref, cur)
        defects = self._extract_defects(ref, cur, diff_mask)
        status = "PASS" if not defects else "FAIL"
        return {
            "status": status,
            "mode": "golden_image_diff",
            "defect_count": len(defects),
            "defects": [self._serialize(defect) for defect in defects],
            "change_area_ratio": round(float(np.count_nonzero(diff_mask) / diff_mask.size), 5),
            "summary": (
                "Golden image comparison passed."
                if status == "PASS"
                else f"Golden image comparison found {len(defects)} changed region(s)."
            ),
            "limitations": [
                "requires consistent camera pose, lighting, board orientation, and scale",
                "flags visual differences; electrical validation still requires tests or reference netlist",
            ],
        }

    def _to_bgr(self, image: np.ndarray) -> np.ndarray:
        img = np.asarray(image)
        if img.ndim == 2:
            img = np.stack([img, img, img], axis=-1)
        if img.ndim == 3 and img.shape[-1] == 4:
            img = img[..., :3]
        if img.dtype != np.uint8:
            img = np.clip(img * 255.0 if img.max(initial=0.0) <= 1.0 else img, 0, 255).astype(np.uint8)
        # Project code usually uses RGB; OpenCV imread callers may pass BGR. The
        # classifier mostly uses relative color/gray signals, so this is enough.
        return img.copy()

    def _difference_mask(self, ref: np.ndarray, cur: np.ndarray) -> np.ndarray:
        ref_blur = cv2.GaussianBlur(ref, (5, 5), 0)
        cur_blur = cv2.GaussianBlur(cur, (5, 5), 0)
        diff = cv2.absdiff(ref_blur, cur_blur)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, self.diff_threshold, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

    def _extract_defects(self, ref: np.ndarray, cur: np.ndarray, mask: np.ndarray) -> List[GoldenDiff]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(20.0, float(mask.shape[0] * mask.shape[1]) * self.min_area_ratio)
        defects: List[GoldenDiff] = []

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            pad = 3
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(mask.shape[1], x + w + pad)
            y2 = min(mask.shape[0], y + h + pad)
            ref_roi = ref[y1:y2, x1:x2]
            cur_roi = cur[y1:y2, x1:x2]
            defect_type, confidence, severity = self._classify_region(ref_roi, cur_roi, area)
            defects.append(
                GoldenDiff(
                    defect_type=defect_type,
                    bbox=[int(x1), int(y1), int(x2), int(y2)],
                    confidence=round(float(confidence), 3),
                    severity=round(float(severity), 3),
                    description=f"Golden-reference visual change: {defect_type}",
                    metadata={"area": round(area, 2), "method": "absdiff_contour"},
                )
            )

        defects.sort(key=lambda item: (item.severity, item.confidence), reverse=True)
        return defects

    def _classify_region(self, ref_roi: np.ndarray, cur_roi: np.ndarray, area: float) -> tuple[str, float, float]:
        ref_gray = cv2.cvtColor(ref_roi, cv2.COLOR_BGR2GRAY)
        cur_gray = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2GRAY)
        ref_mean = float(np.mean(ref_gray)) if ref_gray.size else 0.0
        cur_mean = float(np.mean(cur_gray)) if cur_gray.size else 0.0
        cur_hsv = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2HSV)
        ref_hsv = cv2.cvtColor(ref_roi, cv2.COLOR_BGR2HSV)
        hue = cur_hsv[:, :, 0]
        sat = cur_hsv[:, :, 1]
        val = cur_hsv[:, :, 2]
        ref_greenish = float(np.mean((ref_hsv[:, :, 0] >= 35) & (ref_hsv[:, :, 0] <= 85) & (ref_hsv[:, :, 1] > 60) & (ref_hsv[:, :, 2] > 50)))
        greenish = float(np.mean((hue >= 35) & (hue <= 85) & (sat > 60) & (val > 50)))
        bright_low_sat = float(np.mean((sat < 55) & (val > 145)))
        dark_ratio = float(np.mean(cur_gray < 55))

        confidence = min(0.95, 0.55 + min(area / 900.0, 1.0) * 0.35)
        if greenish > 0.45 and ref_greenish < 0.35 and cur_mean > ref_mean + 8:
            return "missing_component", confidence, 0.9
        if dark_ratio > 0.35 and cur_mean < ref_mean - 18:
            return "burnt_component", confidence, 0.85
        if bright_low_sat > 0.20 and cur_mean > ref_mean + 10:
            return "solder_or_contamination", confidence, 0.65
        if greenish > 0.45 and cur_mean >= ref_mean - 10:
            return "corrosion", confidence, 0.55
        if cur_mean > ref_mean + 18:
            return "missing_component", confidence, 0.9
        if cur_mean < ref_mean - 18:
            return "unexpected_component_or_misalignment", confidence, 0.75
        return "golden_mismatch", confidence, 0.6

    @staticmethod
    def _serialize(defect: GoldenDiff) -> Dict[str, Any]:
        return {
            "defect_type": defect.defect_type,
            "bbox": defect.bbox,
            "confidence": defect.confidence,
            "severity": defect.severity,
            "description": defect.description,
            "metadata": defect.metadata,
        }
