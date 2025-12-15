"""
Inspection Diff Module (Pocket AOI)

Compares a 'Target' board against a 'Reference' (Golden) board description.
Identifies missing components, extra components, or mismatches.
"""

from typing import List, Dict, Any, Counter
from loguru import logger

class InspectionDiff:
    """Automated Optical Inspection (AOI) logic."""

    def __init__(self):
        logger.info("InspectionDiff (Beta) initialized")

    def compare(self, reference_counts: Dict[str, int], current_detections: List[Any]) -> Dict[str, Any]:
        """
        Compare current detection list against a reference count dictionary.
        
        Args:
            reference_counts: Dict like {"Resistor": 5, "Capacitor": 2}
            current_detections: List of detection objects
        """
        # Count current items
        current_counts = {}
        for det in current_detections:
            current_counts[det.class_name] = current_counts.get(det.class_name, 0) + 1
        
        # Calculate diff
        missing = []
        extra = []
        match = []

        all_keys = set(reference_counts.keys()) | set(current_counts.keys())
        
        for key in all_keys:
            ref = reference_counts.get(key, 0)
            cur = current_counts.get(key, 0)
            
            if cur < ref:
                missing.append(f"{ref - cur}x {key}")
            elif cur > ref:
                extra.append(f"{cur - ref}x {key}")
            else:
                match.append(f"{cur}x {key}")

        status = "PASS" if not missing and not extra else "FAIL"
        
        return {
            "status": status,
            "missing": missing,
            "extra": extra,
            "matched": match,
            "summary": f"Inspection Result: {status}. Missing: {len(missing)}, Extra: {len(extra)}"
        }
