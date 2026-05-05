"""
Inspection Diff Module (Pocket AOI)

Compares a 'Target' board against a 'Reference' (Golden) board description.
Identifies missing components, extra components, or mismatches.
"""

from typing import Any, Dict, List

from loguru import logger


class InspectionDiff:
    """Automated Optical Inspection (AOI) logic."""

    def __init__(self) -> None:
        logger.info("InspectionDiff (Beta) initialized")

    @staticmethod
    def _normalize_name(value: Any) -> str:
        if value is None:
            return "unknown"
        return str(value).strip().lower().replace(" ", "_")

    def _as_count(self, value: Any) -> int:
        try:
            as_int = int(value)
        except (TypeError, ValueError):
            return 0
        return max(as_int, 0)

    def _normalize_reference_counts(self, reference_counts: Dict[str, int]) -> Dict[str, int]:
        normalized: Dict[str, int] = {}
        for key, count in reference_counts.items():
            normalized_key = self._normalize_name(key)
            normalized_count = self._as_count(count)
            if not normalized_key or normalized_count <= 0:
                continue
            normalized[normalized_key] = normalized.get(normalized_key, 0) + normalized_count
        return normalized

    def _det_class_name(self, det: Any) -> str:
        if isinstance(det, dict):
            return self._normalize_name(
                det.get("class_name")
                or det.get("class")
                or det.get("label")
            )
        return self._normalize_name(getattr(det, "class_name", None))

    def _count_current(self, current_detections: List[Any]) -> Dict[str, int]:
        current_counts: Dict[str, int] = {}
        for det in current_detections:
            key = self._det_class_name(det)
            current_counts[key] = current_counts.get(key, 0) + 1
        return current_counts

    def compare(self, reference_counts: Dict[str, int], current_detections: List[Any]) -> Dict[str, Any]:
        """
        Compare current detection list against a reference count dictionary.
        
        Args:
            reference_counts: Dict like {"Resistor": 5, "Capacitor": 2}
            current_detections: List of detection objects or dict detections
        """
        if not isinstance(reference_counts, dict):
            raise ValueError("reference_counts must be a dictionary")

        normalized_reference = self._normalize_reference_counts(reference_counts)
        current_counts = self._count_current(current_detections)

        # Calculate diff
        missing = []
        extra = []
        matched = []
        mismatch_count = 0

        all_keys = set(normalized_reference.keys()) | set(current_counts.keys())

        for key in sorted(all_keys):
            ref = normalized_reference.get(key, 0)
            cur = current_counts.get(key, 0)

            if cur < ref:
                delta = ref - cur
                mismatch_count += delta
                missing.append(f"{delta}x {key}")
            elif cur > ref:
                delta = cur - ref
                mismatch_count += delta
                extra.append(f"{delta}x {key}")
            else:
                matched.append(f"{cur}x {key}")

        status = "PASS" if not missing and not extra else "FAIL"
        summary = (
            f"Inspection Result: {status}. "
            f"Missing: {len(missing)}, Extra: {len(extra)}, "
            f"Total mismatched components: {mismatch_count}"
        )

        return {
            "status": status,
            "reference_counts": normalized_reference,
            "current_counts": current_counts,
            "missing": missing,
            "extra": extra,
            "matched": matched,
            "component_delta": mismatch_count,
            "summary": summary,
        }
