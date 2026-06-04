"""
Multi-View Detection Fusion for Robotic PCB Inspection

Fuses component and defect detections from multiple camera viewpoints
using consensus voting and geometric constraints.

Approach:
- Feature-level fusion (not full 3D reconstruction)
- Consensus voting: defect must appear in 2+ views
- Project detections to common reference frame (top-down view)
- Deduplicate based on 3D proximity

Author: Dum-E Vision System
Version: 1.0.0
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .camera_calibration import CameraPose
from .defect_detector import DefectDetection

logger = logging.getLogger(__name__)


@dataclass
class FusedDetection:
    """
    Detection fused from multiple viewpoints.

    Combines evidence from multiple cameras to increase confidence
    and reduce false positives.
    """
    defect_type: str
    position_3d: np.ndarray  # [x, y, z] in world frame (mm)
    bbox_2d_top: List[int]  # [x1, y1, x2, y2] projected to top view
    confidence: float  # Combined confidence from all views
    severity: float
    repair_action: str

    # Multi-view metadata
    supporting_views: List[str] = field(default_factory=list)  # View IDs
    view_count: int = 0  # Number of views that detected this
    position_uncertainty: float = 0.0  # Std dev of position estimates (mm)

    # Original detections from each view
    source_detections: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "defect_type": self.defect_type,
            "position_3d": self.position_3d.tolist(),
            "bbox_2d_top": self.bbox_2d_top,
            "confidence": self.confidence,
            "severity": self.severity,
            "repair_action": self.repair_action,
            "supporting_views": self.supporting_views,
            "view_count": self.view_count,
            "position_uncertainty": self.position_uncertainty
        }


class MultiViewFusion:
    """
    Fuses detections from multiple viewpoints for robust PCB inspection.

    Key features:
    - Consensus voting (reduces false positives)
    - 3D position estimation from multiple views
    - Handles partial occlusions (different views see different defects)
    - Uncertainty quantification
    """

    def __init__(
        self,
        min_views_for_consensus: int = 2,
        max_position_distance_mm: float = 5.0,
        confidence_fusion_method: str = "max"
    ):
        """
        Initialize multi-view fusion.

        Args:
            min_views_for_consensus: Minimum views to confirm a detection
            max_position_distance_mm: Max distance to consider detections as same defect
            confidence_fusion_method: How to combine confidences ("max", "mean", "vote")
        """
        self.min_views_for_consensus = min_views_for_consensus
        self.max_position_distance_mm = max_position_distance_mm
        self.confidence_fusion_method = confidence_fusion_method

        logger.info(f"MultiViewFusion initialized (min_views: {min_views_for_consensus}, "
                   f"max_distance: {max_position_distance_mm}mm)")

    def fuse_detections(
        self,
        detections_per_view: Dict[str, List[DefectDetection]],
        poses_per_view: Dict[str, CameraPose],
        camera_matrix: np.ndarray
    ) -> List[FusedDetection]:
        """
        Fuse detections from multiple views.

        Args:
            detections_per_view: {view_id: [DefectDetection, ...]}
            poses_per_view: {view_id: CameraPose}
            camera_matrix: 3x3 camera intrinsic matrix

        Returns:
            List of fused detections with multi-view consensus
        """
        if len(detections_per_view) == 0:
            return []

        # Step 1: Project all detections to 3D world coordinates
        detections_3d = self._project_detections_to_3d(
            detections_per_view, poses_per_view, camera_matrix
        )

        # Step 2: Cluster detections across views (find correspondences)
        clusters = self._cluster_detections_3d(detections_3d)

        # Step 3: Apply consensus voting and fuse
        fused_detections = []

        for cluster_id, cluster_detections in clusters.items():
            # Only keep detections that appear in minimum number of views
            if len(cluster_detections) >= self.min_views_for_consensus:
                fused = self._fuse_cluster(cluster_detections, cluster_id)
                fused_detections.append(fused)
            else:
                logger.debug(f"Cluster {cluster_id} rejected: only {len(cluster_detections)} views "
                           f"(need >= {self.min_views_for_consensus})")

        logger.info(f"Fused {len(fused_detections)} detections from {len(detections_per_view)} views "
                   f"(consensus threshold: {self.min_views_for_consensus} views)")

        return fused_detections

    def _project_detections_to_3d(
        self,
        detections_per_view: Dict[str, List[DefectDetection]],
        poses_per_view: Dict[str, CameraPose],
        camera_matrix: np.ndarray
    ) -> List[Dict]:
        """
        Project 2D detections to 3D world coordinates.

        Returns:
            List of dicts with {detection, view_id, position_3d}
        """
        detections_3d = []

        for view_id, detections in detections_per_view.items():
            if view_id not in poses_per_view:
                logger.warning(f"No pose available for view '{view_id}', skipping")
                continue

            pose = poses_per_view[view_id]

            for detection in detections:
                # Use center of bounding box as representative point
                bbox = detection.bbox
                center_2d = np.array([
                    (bbox[0] + bbox[2]) / 2,
                    (bbox[1] + bbox[3]) / 2
                ])

                # Project to 3D (assume on PCB surface z=0)
                position_3d = self._project_2d_to_3d(
                    center_2d, pose, camera_matrix, z_world=0.0
                )

                detections_3d.append({
                    "detection": detection,
                    "view_id": view_id,
                    "position_3d": position_3d,
                    "pose": pose
                })

        return detections_3d

    def _project_2d_to_3d(
        self,
        point_2d: np.ndarray,
        pose: CameraPose,
        camera_matrix: np.ndarray,
        z_world: float = 0.0
    ) -> np.ndarray:
        """
        Project 2D image point to 3D world coordinates.

        Simplified version assuming planar surface (PCB at z=z_world).

        Args:
            point_2d: [x, y] in image
            pose: Camera pose
            camera_matrix: 3x3 intrinsic matrix
            z_world: Z coordinate in world frame (mm)

        Returns:
            [x, y, z] in world frame
        """
        # Convert to normalized camera coordinates
        fx = camera_matrix[0, 0]
        fy = camera_matrix[1, 1]
        cx = camera_matrix[0, 2]
        cy = camera_matrix[1, 2]

        x_norm = (point_2d[0] - cx) / fx
        y_norm = (point_2d[1] - cy) / fy

        # Ray in camera frame (direction vector)
        ray_camera = np.array([x_norm, y_norm, 1.0])
        ray_camera = ray_camera / np.linalg.norm(ray_camera)

        # Camera position in world frame
        R = pose.rotation_matrix
        t = pose.translation_vector

        # Ray direction in world frame
        ray_world = R.T @ ray_camera

        # Camera origin in world frame
        camera_origin = -R.T @ t

        # Intersect ray with plane z = z_world
        # P = O + λ * d, where P_z = z_world
        # z_world = O_z + λ * d_z
        # λ = (z_world - O_z) / d_z

        if abs(ray_world[2]) < 1e-6:
            # Ray parallel to plane, use approximate depth
            lambda_param = 300.0  # Assume 300mm depth
        else:
            lambda_param = (z_world - camera_origin[2]) / ray_world[2]

        # 3D point
        point_3d = camera_origin + lambda_param * ray_world

        return point_3d

    def _cluster_detections_3d(
        self,
        detections_3d: List[Dict]
    ) -> Dict[int, List[Dict]]:
        """
        Cluster detections based on 3D proximity and defect type.

        Detections from different views that are close in 3D space
        and have the same defect type are clustered together.

        Args:
            detections_3d: List of {detection, view_id, position_3d}

        Returns:
            {cluster_id: [detection_dict, ...]}
        """
        clusters = defaultdict(list)
        cluster_id = 0

        used = [False] * len(detections_3d)

        for i, det1 in enumerate(detections_3d):
            if used[i]:
                continue

            # Start new cluster
            current_cluster = [det1]
            used[i] = True

            # Find all detections that belong to this cluster
            for j, det2 in enumerate(detections_3d):
                if used[j]:
                    continue

                # Same defect type?
                if det1["detection"].defect_type != det2["detection"].defect_type:
                    continue

                # Close in 3D space?
                distance = np.linalg.norm(det1["position_3d"] - det2["position_3d"])

                if distance <= self.max_position_distance_mm:
                    current_cluster.append(det2)
                    used[j] = True

            clusters[cluster_id] = current_cluster
            cluster_id += 1

        return clusters

    def _fuse_cluster(
        self,
        cluster_detections: List[Dict],
        cluster_id: int
    ) -> FusedDetection:
        """
        Fuse a cluster of detections into single detection.

        Args:
            cluster_detections: List of detection dicts from same cluster
            cluster_id: Cluster identifier

        Returns:
            FusedDetection with combined information
        """
        # Defect type (should be same for all in cluster)
        defect_type = cluster_detections[0]["detection"].defect_type

        # 3D position: mean of all detections
        positions = np.array([d["position_3d"] for d in cluster_detections])
        position_3d = positions.mean(axis=0)
        position_uncertainty = positions.std() if len(positions) > 1 else 0.0

        # Confidence: combine based on method
        confidences = [d["detection"].confidence for d in cluster_detections]

        if self.confidence_fusion_method == "max":
            combined_confidence = max(confidences)
        elif self.confidence_fusion_method == "mean":
            combined_confidence = np.mean(confidences)
        elif self.confidence_fusion_method == "vote":
            # Voting-based: confidence proportional to number of views
            combined_confidence = len(cluster_detections) / 6.0  # Assume max 6 views
        else:
            combined_confidence = np.mean(confidences)

        # Severity: take maximum (most conservative)
        severity = max(d["detection"].severity for d in cluster_detections)

        # Repair action: from first detection (should be same for same defect type)
        repair_action = cluster_detections[0]["detection"].repair_action

        # Supporting views
        supporting_views = [d["view_id"] for d in cluster_detections]
        view_count = len(set(supporting_views))  # Unique views

        # Project to top-down 2D bbox (for visualization)
        # Use mean position and approximate size
        bbox_size = 10  # mm
        bbox_2d_top = [
            int(position_3d[0] - bbox_size / 2),
            int(position_3d[1] - bbox_size / 2),
            int(position_3d[0] + bbox_size / 2),
            int(position_3d[1] + bbox_size / 2)
        ]

        # Source detections (for debugging)
        source_detections = [
            {
                "view_id": d["view_id"],
                "confidence": d["detection"].confidence,
                "bbox_2d": d["detection"].bbox
            }
            for d in cluster_detections
        ]

        fused = FusedDetection(
            defect_type=defect_type,
            position_3d=position_3d,
            bbox_2d_top=bbox_2d_top,
            confidence=combined_confidence,
            severity=severity,
            repair_action=repair_action,
            supporting_views=supporting_views,
            view_count=view_count,
            position_uncertainty=position_uncertainty,
            source_detections=source_detections
        )

        return fused

    def filter_false_positives(
        self,
        fused_detections: List[FusedDetection],
        min_confidence: float = 0.5,
        max_uncertainty_mm: float = 10.0
    ) -> List[FusedDetection]:
        """
        Filter out likely false positives based on fusion metadata.

        Args:
            fused_detections: List of fused detections
            min_confidence: Minimum confidence threshold
            max_uncertainty_mm: Maximum position uncertainty (mm)

        Returns:
            Filtered list of detections
        """
        filtered = []

        for detection in fused_detections:
            # Filter by confidence
            if detection.confidence < min_confidence:
                continue

            # Filter by uncertainty
            if detection.position_uncertainty > max_uncertainty_mm:
                continue

            filtered.append(detection)

        logger.info(f"Filtered {len(fused_detections)} → {len(filtered)} detections "
                   f"(conf >= {min_confidence}, uncertainty <= {max_uncertainty_mm}mm)")

        return filtered

    def generate_consensus_report(
        self,
        fused_detections: List[FusedDetection]
    ) -> str:
        """Generate human-readable consensus report."""
        lines = []

        lines.append("=" * 70)
        lines.append("MULTI-VIEW CONSENSUS DEFECT REPORT")
        lines.append("=" * 70)
        lines.append("")

        if not fused_detections:
            lines.append("No defects confirmed by multi-view consensus.")
            lines.append("")
            lines.append("=" * 70)
            return "\n".join(lines)

        lines.append(f"Total Confirmed Defects: {len(fused_detections)}")
        lines.append("")

        # Sort by severity
        sorted_detections = sorted(fused_detections, key=lambda d: d.severity, reverse=True)

        for i, defect in enumerate(sorted_detections, 1):
            lines.append(f"{i}. {defect.defect_type.upper()}")
            lines.append(f"   Position (3D): ({defect.position_3d[0]:.1f}, "
                        f"{defect.position_3d[1]:.1f}, {defect.position_3d[2]:.1f}) mm")
            lines.append(f"   Severity: {defect.severity:.2f}")
            lines.append(f"   Confidence: {defect.confidence:.2f}")
            lines.append(f"   Confirmed by: {defect.view_count} views {defect.supporting_views}")
            lines.append(f"   Position uncertainty: {defect.position_uncertainty:.2f} mm")
            lines.append(f"   Repair action: {defect.repair_action}")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    print("Multi-View Fusion Module")
    print("========================")
    print()
    print("This module fuses detections from multiple camera viewpoints.")
    print()
    print("Key features:")
    print("- Consensus voting (defect must appear in 2+ views)")
    print("- 3D position estimation")
    print("- False positive reduction")
    print()
    print("Example:")
    print("  fusion = MultiViewFusion(min_views_for_consensus=2)")
    print("  fused = fusion.fuse_detections(detections_per_view, poses, camera_matrix)")
    print("  report = fusion.generate_consensus_report(fused)")
