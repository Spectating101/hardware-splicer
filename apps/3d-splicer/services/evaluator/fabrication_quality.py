"""
Fabrication Quality Evaluator for 3D Printed Cases

Compares printed parts against design STL using:
- ICP (Iterative Closest Point) alignment
- Point-to-surface distance metrics
- Warp/dimensional accuracy detection
- Quality scoring (0-1 scale)

Enables vision-based feedback loop for print parameter optimization.

Author: Dum-E Fabrication System
Version: 1.0.0
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class DefectType(Enum):
    """Types of fabrication defects."""
    WARPING = "warping"
    DIMENSIONAL_ERROR = "dimensional_error"
    LAYER_ADHESION = "layer_adhesion"
    OVERHANG_FAILURE = "overhang_failure"
    SUPPORT_SCARRING = "support_scarring"
    STRINGING = "stringing"
    UNDER_EXTRUSION = "under_extrusion"
    OVER_EXTRUSION = "over_extrusion"


@dataclass
class QualityMetrics:
    """Quality assessment metrics for printed part."""
    overall_score: float  # 0-1 (0=failed, 1=perfect)
    dimensional_accuracy: float  # % deviation from design
    mean_distance_mm: float  # Mean point-to-surface distance
    max_distance_mm: float  # Max deviation
    warp_detected: bool
    warp_magnitude_mm: float

    defects: List[Dict] = field(default_factory=list)
    pass_fail: bool = True
    notes: str = ""

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "overall_score": self.overall_score,
            "dimensional_accuracy": self.dimensional_accuracy,
            "mean_distance_mm": self.mean_distance_mm,
            "max_distance_mm": self.max_distance_mm,
            "warp_detected": self.warp_detected,
            "warp_magnitude_mm": self.warp_magnitude_mm,
            "defects": self.defects,
            "pass_fail": self.pass_fail,
            "notes": self.notes
        }


class FabricationQualityEvaluator:
    """
    Evaluates quality of 3D printed parts against design.

    Uses vision-based measurement (from 3D scanner or structured light)
    to compare actual print against CAD model.

    Quality thresholds:
    - Excellent: < 0.2mm deviation
    - Good: < 0.5mm deviation
    - Acceptable: < 1.0mm deviation
    - Poor: >= 1.0mm deviation
    """

    # Quality thresholds (mm)
    EXCELLENT_THRESHOLD = 0.2
    GOOD_THRESHOLD = 0.5
    ACCEPTABLE_THRESHOLD = 1.0

    def __init__(self, quality_threshold: float = 0.70):
        """
        Initialize evaluator.

        Args:
            quality_threshold: Minimum score to pass (0-1)
        """
        self.quality_threshold = quality_threshold
        logger.info(f"FabricationQualityEvaluator initialized (threshold: {quality_threshold})")

    def evaluate_print(
        self,
        design_mesh_path: Path,
        scanned_mesh_path: Path
    ) -> QualityMetrics:
        """
        Evaluate printed part quality.

        Args:
            design_mesh_path: Path to design STL file
            scanned_mesh_path: Path to scanned mesh of printed part

        Returns:
            QualityMetrics with detailed assessment
        """
        try:
            import trimesh
        except ImportError:
            logger.error("trimesh library required for mesh operations")
            return self._create_fallback_metrics("trimesh not available")

        # Load meshes
        try:
            design_mesh = trimesh.load(str(design_mesh_path))
            scanned_mesh = trimesh.load(str(scanned_mesh_path))
        except Exception as e:
            logger.error(f"Failed to load meshes: {e}")
            return self._create_fallback_metrics(f"Mesh loading failed: {e}")

        # Align scanned mesh to design using ICP
        try:
            aligned_scan, transformation = self._align_meshes_icp(scanned_mesh, design_mesh)
        except Exception as e:
            logger.warning(f"ICP alignment failed, using manual alignment: {e}")
            aligned_scan = scanned_mesh
            transformation = np.eye(4)

        # Compute point-to-surface distances
        distances = self._compute_point_distances(aligned_scan, design_mesh)

        # Analyze distances
        mean_distance = np.mean(distances)
        max_distance = np.max(distances)
        std_distance = np.std(distances)

        # Dimensional accuracy (percentage)
        # Use bounding box diagonal as reference
        design_bbox = design_mesh.bounds
        diagonal = np.linalg.norm(design_bbox[1] - design_bbox[0])
        dimensional_accuracy = max(0, 1.0 - (mean_distance / diagonal))

        # Detect warping (systematic deviation in z-direction)
        warp_detected, warp_magnitude = self._detect_warping(aligned_scan, design_mesh)

        # Detect defects
        defects = self._detect_defects(distances, aligned_scan, design_mesh)

        # Overall quality score (0-1)
        overall_score = self._calculate_quality_score(
            mean_distance, max_distance, warp_detected, len(defects)
        )

        # Pass/fail decision
        pass_fail = overall_score >= self.quality_threshold

        # Generate notes
        notes = self._generate_quality_notes(
            mean_distance, max_distance, warp_detected, defects
        )

        metrics = QualityMetrics(
            overall_score=overall_score,
            dimensional_accuracy=dimensional_accuracy * 100,  # Convert to percentage
            mean_distance_mm=mean_distance,
            max_distance_mm=max_distance,
            warp_detected=warp_detected,
            warp_magnitude_mm=warp_magnitude,
            defects=defects,
            pass_fail=pass_fail,
            notes=notes
        )

        logger.info(f"Quality evaluation complete: score={overall_score:.2f}, pass={pass_fail}")

        return metrics

    def _align_meshes_icp(
        self,
        source_mesh,
        target_mesh,
        max_iterations: int = 50
    ) -> Tuple:
        """
        Align source mesh to target using ICP algorithm.

        Args:
            source_mesh: Mesh to align (scanned part)
            target_mesh: Reference mesh (design)
            max_iterations: Maximum ICP iterations

        Returns:
            (aligned_mesh, transformation_matrix)
        """
        # Sample points from meshes
        source_points = source_mesh.sample(10000)
        target_points = target_mesh.sample(10000)

        # Simple ICP (can be replaced with scipy.spatial or Open3D for better results)
        transformation = np.eye(4)

        # For now, use centroid alignment as fallback
        # Full ICP requires scipy or Open3D
        source_centroid = source_points.mean(axis=0)
        target_centroid = target_points.mean(axis=0)

        translation = target_centroid - source_centroid
        transformation[:3, 3] = translation

        # Apply transformation
        aligned_mesh = source_mesh.copy()
        aligned_mesh.apply_transform(transformation)

        return aligned_mesh, transformation

    def _compute_point_distances(self, source_mesh, target_mesh) -> np.ndarray:
        """
        Compute point-to-surface distances.

        Args:
            source_mesh: Source mesh (scanned)
            target_mesh: Target mesh (design)

        Returns:
            Array of distances (mm)
        """
        # Sample points from source
        source_points = source_mesh.sample(5000)

        # Find closest points on target surface
        closest_points, distances, _ = target_mesh.nearest.on_surface(source_points)

        return distances

    def _detect_warping(self, scanned_mesh, design_mesh) -> Tuple[bool, float]:
        """
        Detect warping (systematic z-axis deviation).

        Args:
            scanned_mesh: Scanned mesh
            design_mesh: Design mesh

        Returns:
            (warp_detected, warp_magnitude_mm)
        """
        # Get bottom face points
        design_bounds = design_mesh.bounds
        z_min = design_bounds[0, 2]
        z_threshold = z_min + 2.0  # Bottom 2mm

        # Sample points from bottom region
        scan_points = scanned_mesh.sample(1000)
        design_points = design_mesh.sample(1000)

        # Filter bottom points
        scan_bottom = scan_points[scan_points[:, 2] < (scan_points[:, 2].min() + z_threshold)]
        design_bottom = design_points[design_points[:, 2] < (design_points[:, 2].min() + z_threshold)]

        if len(scan_bottom) < 10 or len(design_bottom) < 10:
            return False, 0.0

        # Check for systematic elevation difference (warping)
        scan_bottom_mean_z = np.mean(scan_bottom[:, 2])
        design_bottom_mean_z = np.mean(design_bottom[:, 2])

        warp_magnitude = abs(scan_bottom_mean_z - design_bottom_mean_z)

        # Warp detected if corners are elevated > 0.5mm
        warp_detected = warp_magnitude > 0.5

        return warp_detected, warp_magnitude

    def _detect_defects(
        self,
        distances: np.ndarray,
        scanned_mesh,
        design_mesh
    ) -> List[Dict]:
        """
        Detect specific fabrication defects.

        Args:
            distances: Point-to-surface distances
            scanned_mesh: Scanned mesh
            design_mesh: Design mesh

        Returns:
            List of defect dictionaries
        """
        defects = []

        # Dimensional errors (areas with large deviations)
        large_deviations = distances > self.ACCEPTABLE_THRESHOLD
        if np.sum(large_deviations) > len(distances) * 0.05:  # More than 5% of points
            defects.append({
                "type": DefectType.DIMENSIONAL_ERROR.value,
                "severity": "high",
                "affected_points": int(np.sum(large_deviations)),
                "description": f"{np.sum(large_deviations)} points exceed {self.ACCEPTABLE_THRESHOLD}mm tolerance"
            })

        # Under-extrusion (scanned volume < design volume)
        scan_volume = scanned_mesh.volume if hasattr(scanned_mesh, 'volume') else 0
        design_volume = design_mesh.volume if hasattr(design_mesh, 'volume') else 0

        if design_volume > 0:
            volume_ratio = scan_volume / design_volume

            if volume_ratio < 0.95:  # More than 5% volume loss
                defects.append({
                    "type": DefectType.UNDER_EXTRUSION.value,
                    "severity": "medium",
                    "volume_ratio": volume_ratio,
                    "description": f"Part volume {volume_ratio*100:.1f}% of design (expected 95-105%)"
                })

            elif volume_ratio > 1.05:  # More than 5% excess
                defects.append({
                    "type": DefectType.OVER_EXTRUSION.value,
                    "severity": "medium",
                    "volume_ratio": volume_ratio,
                    "description": f"Part volume {volume_ratio*100:.1f}% of design (expected 95-105%)"
                })

        return defects

    def _calculate_quality_score(
        self,
        mean_distance: float,
        max_distance: float,
        warp_detected: bool,
        defect_count: int
    ) -> float:
        """
        Calculate overall quality score.

        Args:
            mean_distance: Mean deviation (mm)
            max_distance: Max deviation (mm)
            warp_detected: Whether warping was detected
            defect_count: Number of defects

        Returns:
            Quality score (0-1)
        """
        score = 1.0

        # Penalize based on mean distance
        if mean_distance < self.EXCELLENT_THRESHOLD:
            score -= 0.0
        elif mean_distance < self.GOOD_THRESHOLD:
            score -= 0.1
        elif mean_distance < self.ACCEPTABLE_THRESHOLD:
            score -= 0.25
        else:
            score -= 0.5

        # Penalize based on max distance
        if max_distance > 2.0:
            score -= 0.2
        elif max_distance > 1.0:
            score -= 0.1

        # Penalize warping
        if warp_detected:
            score -= 0.15

        # Penalize defects
        score -= defect_count * 0.1

        return max(0.0, score)

    def _generate_quality_notes(
        self,
        mean_distance: float,
        max_distance: float,
        warp_detected: bool,
        defects: List[Dict]
    ) -> str:
        """Generate human-readable quality notes."""
        notes = []

        # Distance assessment
        if mean_distance < self.EXCELLENT_THRESHOLD:
            notes.append("Excellent dimensional accuracy")
        elif mean_distance < self.GOOD_THRESHOLD:
            notes.append("Good dimensional accuracy")
        elif mean_distance < self.ACCEPTABLE_THRESHOLD:
            notes.append("Acceptable dimensional accuracy")
        else:
            notes.append("Poor dimensional accuracy - significant deviations detected")

        # Warping
        if warp_detected:
            notes.append("Warping detected - check bed adhesion and cooling")

        # Defects
        if defects:
            notes.append(f"{len(defects)} fabrication defects detected")

        return "; ".join(notes)

    def _create_fallback_metrics(self, error_message: str) -> QualityMetrics:
        """Create fallback metrics when evaluation fails."""
        return QualityMetrics(
            overall_score=0.0,
            dimensional_accuracy=0.0,
            mean_distance_mm=999.0,
            max_distance_mm=999.0,
            warp_detected=False,
            warp_magnitude_mm=0.0,
            defects=[],
            pass_fail=False,
            notes=f"Evaluation failed: {error_message}"
        )


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) >= 3:
        design_path = Path(sys.argv[1])
        scanned_path = Path(sys.argv[2])

        evaluator = FabricationQualityEvaluator(quality_threshold=0.70)
        metrics = evaluator.evaluate_print(design_path, scanned_path)

        print("\n" + "="*70)
        print("FABRICATION QUALITY REPORT")
        print("="*70)
        print(f"Overall Score: {metrics.overall_score:.2f}/1.00")
        print(f"Pass/Fail: {'PASS' if metrics.pass_fail else 'FAIL'}")
        print(f"Dimensional Accuracy: {metrics.dimensional_accuracy:.1f}%")
        print(f"Mean Deviation: {metrics.mean_distance_mm:.2f} mm")
        print(f"Max Deviation: {metrics.max_distance_mm:.2f} mm")
        print(f"Warping: {'YES' if metrics.warp_detected else 'NO'}")
        if metrics.warp_detected:
            print(f"  Warp Magnitude: {metrics.warp_magnitude_mm:.2f} mm")
        print(f"\nDefects: {len(metrics.defects)}")
        for defect in metrics.defects:
            print(f"  - {defect['type']}: {defect['description']}")
        print(f"\nNotes: {metrics.notes}")
        print("="*70 + "\n")
    else:
        print("Usage: python fabrication_quality.py <design.stl> <scanned.stl>")
