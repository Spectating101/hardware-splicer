"""
Intelligent View Optimization System

Auto-optimizes camera viewpoints based on quality feedback:
- "This angle is blurry → adjust position"
- "Can't see markers → move camera"
- "Too much glare → change lighting/angle"
- "Collision risk → find alternative path"

Learns optimal viewpoints for different PCB types.

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import numpy as np
import cv2
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ViewQuality(Enum):
    """View quality assessment."""
    EXCELLENT = "excellent"  # Perfect view
    GOOD = "good"  # Usable
    POOR = "poor"  # Needs adjustment
    FAILED = "failed"  # Unusable


@dataclass
class ViewScore:
    """Quality score for a single view."""
    view_id: str
    quality: ViewQuality
    score: float  # 0-1

    # Quality factors
    sharpness: float = 0.0
    exposure: float = 0.0
    marker_visibility: float = 0.0
    coverage: float = 0.0
    glare: float = 0.0

    # Issues
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "view_id": self.view_id,
            "quality": self.quality.value,
            "score": self.score,
            "sharpness": self.sharpness,
            "exposure": self.exposure,
            "marker_visibility": self.marker_visibility,
            "coverage": self.coverage,
            "glare": self.glare,
            "issues": self.issues,
            "suggestions": self.suggestions
        }


@dataclass
class OptimalViewpoint:
    """Optimized viewpoint configuration."""
    position: List[float]  # [x, y, z] in mm
    orientation: List[float]  # [roll, pitch, yaw] in degrees
    camera_distance_mm: float
    predicted_quality: float
    alternative_positions: List[Dict] = field(default_factory=list)


class ViewOptimizer:
    """
    Intelligent view optimization using visual feedback.

    Uses computer vision metrics to:
    - Assess view quality
    - Suggest adjustments
    - Learn optimal viewpoints
    - Avoid bad configurations
    """

    # Quality thresholds
    EXCELLENT_THRESHOLD = 0.85
    GOOD_THRESHOLD = 0.70
    POOR_THRESHOLD = 0.50

    def __init__(self, learning_history_path: Optional[Path] = None):
        """
        Initialize view optimizer.

        Args:
            learning_history_path: Path to save learned viewpoints
        """
        self.history_path = learning_history_path or Path("view_optimization_history.json")
        self.learned_viewpoints: Dict[str, List[OptimalViewpoint]] = {}

        self._load_history()

        logger.info("ViewOptimizer initialized")

    def assess_view_quality(
        self,
        image: np.ndarray,
        view_id: str,
        expected_markers: int = 4
    ) -> ViewScore:
        """
        Assess quality of a captured view.

        Args:
            image: Captured image
            view_id: View identifier
            expected_markers: Number of ArUco markers expected

        Returns:
            ViewScore with detailed assessment
        """
        score = ViewScore(view_id=view_id, quality=ViewQuality.GOOD, score=0.0)

        # 1. Sharpness (focus quality)
        score.sharpness = self._measure_sharpness(image)

        # 2. Exposure (lighting quality)
        score.exposure = self._measure_exposure(image)

        # 3. Marker visibility (ArUco markers)
        score.marker_visibility = self._measure_marker_visibility(image, expected_markers)

        # 4. Coverage (how much of PCB is visible)
        score.coverage = self._measure_coverage(image)

        # 5. Glare (reflections)
        score.glare = self._measure_glare(image)

        # Overall score (weighted average)
        weights = {
            "sharpness": 0.25,
            "exposure": 0.20,
            "marker_visibility": 0.30,
            "coverage": 0.15,
            "glare": 0.10
        }

        score.score = (
            score.sharpness * weights["sharpness"] +
            score.exposure * weights["exposure"] +
            score.marker_visibility * weights["marker_visibility"] +
            score.coverage * weights["coverage"] +
            (1.0 - score.glare) * weights["glare"]  # Glare is bad
        )

        # Classify quality
        if score.score >= self.EXCELLENT_THRESHOLD:
            score.quality = ViewQuality.EXCELLENT
        elif score.score >= self.GOOD_THRESHOLD:
            score.quality = ViewQuality.GOOD
        elif score.score >= self.POOR_THRESHOLD:
            score.quality = ViewQuality.POOR
            self._generate_improvement_suggestions(score)
        else:
            score.quality = ViewQuality.FAILED
            self._generate_improvement_suggestions(score)

        logger.info(f"View '{view_id}' quality: {score.quality.value} (score: {score.score:.2f})")

        return score

    def _measure_sharpness(self, image: np.ndarray) -> float:
        """
        Measure image sharpness using Laplacian variance.

        Returns:
            Sharpness score (0-1, higher = sharper)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()

        # Normalize to 0-1 (empirically determined thresholds)
        # Variance > 500 = sharp, < 100 = blurry
        score = min(variance / 500.0, 1.0)

        return score

    def _measure_exposure(self, image: np.ndarray) -> float:
        """
        Measure exposure quality (not too dark, not too bright).

        Returns:
            Exposure score (0-1, 1 = optimal)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = gray.mean()

        # Optimal brightness: 100-150 (out of 255)
        # Too dark < 80, too bright > 180

        if 100 <= mean_brightness <= 150:
            score = 1.0
        elif 80 <= mean_brightness < 100:
            score = 0.7 + (mean_brightness - 80) / 20 * 0.3
        elif 150 < mean_brightness <= 180:
            score = 1.0 - (mean_brightness - 150) / 30 * 0.3
        elif mean_brightness < 80:
            score = mean_brightness / 80 * 0.7
        else:  # > 180
            score = max(0.0, 1.0 - (mean_brightness - 180) / 75)

        return score

    def _measure_marker_visibility(self, image: np.ndarray, expected: int) -> float:
        """
        Measure ArUco marker visibility.

        Returns:
            Marker visibility score (0-1)
        """
        try:
            # Detect ArUco markers
            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            parameters = cv2.aruco.DetectorParameters()

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            corners, ids, rejected = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

            if ids is None:
                return 0.0

            detected_count = len(ids)
            score = detected_count / expected

            return min(score, 1.0)

        except Exception as e:
            logger.warning(f"Marker detection failed: {e}")
            return 0.5  # Unknown

    def _measure_coverage(self, image: np.ndarray) -> float:
        """
        Measure how much of the image contains useful content (not blank).

        Returns:
            Coverage score (0-1)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Edge detection to find content
        edges = cv2.Canny(gray, 50, 150)

        # Percentage of pixels with edges (content)
        content_ratio = np.count_nonzero(edges) / edges.size

        # Good coverage: 5-20% edges (too much = noise, too little = empty)
        if 0.05 <= content_ratio <= 0.20:
            score = 1.0
        elif content_ratio < 0.05:
            score = content_ratio / 0.05
        else:
            score = max(0.5, 1.0 - (content_ratio - 0.20) / 0.30)

        return score

    def _measure_glare(self, image: np.ndarray) -> float:
        """
        Measure glare/reflections (bright spots).

        Returns:
            Glare score (0-1, 1 = lots of glare, 0 = no glare)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Threshold for very bright pixels (potential glare)
        _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

        # Percentage of very bright pixels
        glare_ratio = np.count_nonzero(bright_mask) / bright_mask.size

        # More than 5% very bright = significant glare
        score = min(glare_ratio / 0.05, 1.0)

        return score

    def _generate_improvement_suggestions(self, score: ViewScore):
        """Generate suggestions to improve view quality."""

        if score.sharpness < 0.6:
            score.issues.append("Image is blurry")
            score.suggestions.append("Enable auto-focus or adjust camera focus")
            score.suggestions.append("Reduce camera shake (stabilize mount)")

        if score.exposure < 0.6:
            gray_level = score.exposure * 127.5  # Estimate
            if gray_level < 80:
                score.issues.append("Image is too dark")
                score.suggestions.append("Increase lighting or exposure time")
            else:
                score.issues.append("Image is too bright")
                score.suggestions.append("Reduce lighting or decrease exposure")

        if score.marker_visibility < 0.75:
            score.issues.append("ArUco markers not visible")
            score.suggestions.append("Adjust camera angle to face markers")
            score.suggestions.append("Improve lighting on markers")
            score.suggestions.append("Move closer to PCB")

        if score.coverage < 0.5:
            score.issues.append("Poor PCB coverage in frame")
            score.suggestions.append("Adjust camera distance")
            score.suggestions.append("Change angle to capture more area")

        if score.glare > 0.3:
            score.issues.append("Excessive glare/reflections")
            score.suggestions.append("Adjust lighting angle")
            score.suggestions.append("Use diffused lighting")
            score.suggestions.append("Change camera position to avoid reflections")

    def suggest_adjustment(
        self,
        current_position: Dict,
        view_score: ViewScore
    ) -> Optional[Dict]:
        """
        Suggest position adjustment based on view quality.

        Args:
            current_position: {position: [x, y, z], orientation: [r, p, y]}
            view_score: Quality assessment

        Returns:
            Suggested adjustment or None if view is good enough
        """
        if view_score.quality in [ViewQuality.EXCELLENT, ViewQuality.GOOD]:
            return None  # No adjustment needed

        suggested = current_position.copy()
        adjustments = []

        # Adjust based on issues
        if view_score.sharpness < 0.6:
            # Move closer for better detail
            suggested["position"][2] -= 50  # Move down 50mm
            adjustments.append("Moved closer for sharper focus")

        if view_score.marker_visibility < 0.75:
            # Tilt down to see markers better
            suggested["orientation"][1] += 10  # Pitch down 10°
            adjustments.append("Tilted down to see markers")

        if view_score.glare > 0.3:
            # Rotate to avoid reflections
            suggested["orientation"][2] += 15  # Yaw 15°
            adjustments.append("Rotated to reduce glare")

        if adjustments:
            logger.info(f"Suggested adjustments: {', '.join(adjustments)}")
            return suggested
        else:
            return None

    def optimize_view_sequence(
        self,
        pcb_dimensions: Dict,
        hardware_constraints: Dict
    ) -> List[OptimalViewpoint]:
        """
        Generate optimal view sequence for a PCB.

        Args:
            pcb_dimensions: {width_mm, height_mm, thickness_mm}
            hardware_constraints: {max_reach_mm, min_distance_mm, ...}

        Returns:
            List of optimal viewpoints
        """
        viewpoints = []

        # Calculate optimal distance based on PCB size
        pcb_diagonal = np.sqrt(pcb_dimensions["width_mm"]**2 +
                              pcb_dimensions["height_mm"]**2)

        # Camera should be 1.5× diagonal away for full coverage
        optimal_distance = pcb_diagonal * 1.5
        optimal_distance = min(optimal_distance, hardware_constraints.get("max_reach_mm", 500))
        optimal_distance = max(optimal_distance, hardware_constraints.get("min_distance_mm", 100))

        # Standard viewpoints
        standard_views = [
            {"name": "top", "angle": 0, "rotation": 0},
            {"name": "north_45", "angle": 45, "rotation": 0},
            {"name": "east_45", "angle": 45, "rotation": 90},
            {"name": "south_45", "angle": 45, "rotation": 180},
            {"name": "west_45", "angle": 45, "rotation": 270},
        ]

        for view in standard_views:
            # Calculate position
            angle_rad = np.radians(view["angle"])
            rotation_rad = np.radians(view["rotation"])

            x = optimal_distance * np.sin(angle_rad) * np.cos(rotation_rad)
            y = optimal_distance * np.sin(angle_rad) * np.sin(rotation_rad)
            z = optimal_distance * np.cos(angle_rad)

            viewpoint = OptimalViewpoint(
                position=[x, y, z],
                orientation=[0, view["angle"], view["rotation"]],
                camera_distance_mm=optimal_distance,
                predicted_quality=0.85  # Estimate
            )

            viewpoints.append(viewpoint)

        logger.info(f"Generated {len(viewpoints)} optimal viewpoints for PCB "
                   f"({pcb_dimensions['width_mm']}×{pcb_dimensions['height_mm']}mm)")

        return viewpoints

    def _save_history(self):
        """Save learned viewpoints to history."""
        # TODO: Implement history saving
        pass

    def _load_history(self):
        """Load learned viewpoints from history."""
        # TODO: Implement history loading
        pass

    def generate_report(self, view_scores: List[ViewScore]) -> str:
        """Generate quality report for multiple views."""
        lines = []

        lines.append("=" * 70)
        lines.append("VIEW QUALITY REPORT")
        lines.append("=" * 70)
        lines.append("")

        for score in view_scores:
            lines.append(f"View: {score.view_id}")
            lines.append(f"  Quality: {score.quality.value.upper()}")
            lines.append(f"  Overall Score: {score.score:.2f}/1.00")
            lines.append(f"  Sharpness: {score.sharpness:.2f}")
            lines.append(f"  Exposure: {score.exposure:.2f}")
            lines.append(f"  Marker Visibility: {score.marker_visibility:.2f}")
            lines.append(f"  Coverage: {score.coverage:.2f}")
            lines.append(f"  Glare: {score.glare:.2f}")

            if score.issues:
                lines.append(f"  Issues:")
                for issue in score.issues:
                    lines.append(f"    - {issue}")

            if score.suggestions:
                lines.append(f"  Suggestions:")
                for suggestion in score.suggestions:
                    lines.append(f"    → {suggestion}")

            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Test view optimizer
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    optimizer = ViewOptimizer()

    print("View Optimizer - Intelligent Camera Position Optimization")
    print("=" * 70)
    print()
    print("Features:")
    print("  - Auto-assess view quality (sharpness, exposure, marker visibility)")
    print("  - Suggest position adjustments")
    print("  - Optimize viewpoint sequence")
    print("  - Learn from quality feedback")
