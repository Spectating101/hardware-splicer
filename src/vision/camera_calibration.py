"""
Camera Calibration and Pose Estimation for Multi-View PCB Inspection

Extends ArUco marker detection to compute camera poses and transformation matrices
for multi-view fusion in Dum-E robotic vision system.

Based on:
- Existing aruco_locator.py
- OpenCV camera calibration framework
- Multi-view geometry principles

Author: Dum-E Vision System
Version: 1.0.0
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class CameraPose:
    """
    Camera pose in 3D space relative to reference frame.

    The reference frame is defined by ArUco markers on the PCB.
    """
    rotation_matrix: np.ndarray  # 3x3 rotation matrix
    translation_vector: np.ndarray  # 3x1 translation vector (in mm or meters)
    view_id: str  # Identifier (e.g., "top", "angle_45_north", "bottom")
    timestamp: Optional[float] = None
    confidence: float = 1.0  # 0-1, based on marker detection quality

    # Metadata
    markers_detected: int = 0
    markers_expected: int = 4
    reprojection_error: float = 0.0

    def to_dict(self) -> Dict:
        """Export to dictionary for serialization."""
        return {
            "view_id": self.view_id,
            "rotation_matrix": self.rotation_matrix.tolist(),
            "translation_vector": self.translation_vector.tolist(),
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "markers_detected": self.markers_detected,
            "markers_expected": self.markers_expected,
            "reprojection_error": self.reprojection_error
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CameraPose':
        """Load from dictionary."""
        return cls(
            rotation_matrix=np.array(data["rotation_matrix"]),
            translation_vector=np.array(data["translation_vector"]),
            view_id=data["view_id"],
            timestamp=data.get("timestamp"),
            confidence=data.get("confidence", 1.0),
            markers_detected=data.get("markers_detected", 0),
            markers_expected=data.get("markers_expected", 4),
            reprojection_error=data.get("reprojection_error", 0.0)
        )


@dataclass
class CalibrationResult:
    """Complete calibration result for multi-view system."""
    camera_matrix: np.ndarray  # 3x3 intrinsic matrix
    dist_coeffs: np.ndarray  # Distortion coefficients
    poses: List[CameraPose] = field(default_factory=list)
    marker_size_mm: float = 30.0  # ArUco marker size in mm
    marker_ids: List[int] = field(default_factory=lambda: [0, 1, 2, 3])

    def to_file(self, filepath: Path):
        """Save calibration to JSON file."""
        data = {
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.tolist(),
            "marker_size_mm": self.marker_size_mm,
            "marker_ids": self.marker_ids,
            "poses": [pose.to_dict() for pose in self.poses]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved calibration to {filepath}")

    @classmethod
    def from_file(cls, filepath: Path) -> 'CalibrationResult':
        """Load calibration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        result = cls(
            camera_matrix=np.array(data["camera_matrix"]),
            dist_coeffs=np.array(data["dist_coeffs"]),
            marker_size_mm=data.get("marker_size_mm", 30.0),
            marker_ids=data.get("marker_ids", [0, 1, 2, 3]),
            poses=[CameraPose.from_dict(p) for p in data.get("poses", [])]
        )

        logger.info(f"Loaded calibration from {filepath}")
        return result


class MultiViewCalibrator:
    """
    Multi-view camera calibrator for robotic PCB inspection.

    Uses ArUco markers placed on PCB to compute camera poses
    for each viewpoint in the multi-view capture sequence.

    Standard configuration:
    - 4 ArUco markers at PCB corners
    - 6 views: top + 4×45° angles + bottom (optional)
    - Marker size: 30mm (default)
    """

    def __init__(
        self,
        marker_size_mm: float = 30.0,
        marker_ids: List[int] = None,
        aruco_dict_type: int = cv2.aruco.DICT_4X4_50
    ):
        """
        Initialize multi-view calibrator.

        Args:
            marker_size_mm: Physical size of ArUco markers in mm
            marker_ids: List of marker IDs to detect (default: [0, 1, 2, 3])
            aruco_dict_type: ArUco dictionary type
        """
        self.marker_size_mm = marker_size_mm
        self.marker_ids = marker_ids or [0, 1, 2, 3]

        # ArUco detector
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(aruco_dict_type)
        self.aruco_params = cv2.aruco.DetectorParameters()

        # Camera intrinsics (to be calibrated or loaded)
        self.camera_matrix = None
        self.dist_coeffs = None

        # Collected poses
        self.poses: List[CameraPose] = []

        logger.info(f"MultiViewCalibrator initialized (marker size: {marker_size_mm}mm)")

    def calibrate_camera_intrinsics(
        self,
        calibration_images: List[np.ndarray],
        checkerboard_size: Tuple[int, int] = (9, 6),
        square_size_mm: float = 25.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calibrate camera intrinsics using checkerboard pattern.

        Args:
            calibration_images: List of checkerboard images
            checkerboard_size: Inner corners (width, height)
            square_size_mm: Checkerboard square size in mm

        Returns:
            camera_matrix: 3x3 intrinsic matrix
            dist_coeffs: Distortion coefficients
        """
        # Object points in 3D space
        objp = np.zeros((checkerboard_size[0] * checkerboard_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:checkerboard_size[0], 0:checkerboard_size[1]].T.reshape(-1, 2)
        objp *= square_size_mm

        obj_points = []  # 3D points in real world
        img_points = []  # 2D points in image

        for image in calibration_images:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(gray, checkerboard_size, None)

            if ret:
                obj_points.append(objp)

                # Refine corner locations
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                img_points.append(corners_refined)

        if len(obj_points) < 3:
            raise ValueError(f"Need at least 3 good checkerboard images, got {len(obj_points)}")

        # Calibrate
        ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            obj_points, img_points, calibration_images[0].shape[:2][::-1], None, None
        )

        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs

        logger.info(f"Camera calibrated with {len(obj_points)} images")
        logger.info(f"RMS reprojection error: {ret:.3f}")

        return camera_matrix, dist_coeffs

    def load_camera_intrinsics(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray):
        """Load pre-calibrated camera intrinsics."""
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        logger.info("Loaded camera intrinsics")

    def estimate_pose_from_markers(
        self,
        image: np.ndarray,
        view_id: str
    ) -> Optional[CameraPose]:
        """
        Estimate camera pose from ArUco markers in image.

        Args:
            image: Input image with ArUco markers
            view_id: View identifier (e.g., "top", "angle_45_north")

        Returns:
            CameraPose if successful, None otherwise
        """
        if self.camera_matrix is None:
            raise ValueError("Camera intrinsics not set. Call calibrate_camera_intrinsics() or load_camera_intrinsics() first.")

        # Detect markers
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=self.aruco_params)

        if ids is None or len(ids) == 0:
            logger.warning(f"No ArUco markers detected in view '{view_id}'")
            return None

        detected_ids = ids.flatten().tolist()
        expected_ids = self.marker_ids

        # Need at least 3 markers for pose estimation
        common_ids = [i for i in detected_ids if i in expected_ids]
        if len(common_ids) < 3:
            logger.warning(f"Only {len(common_ids)} expected markers found in view '{view_id}' (need >= 3)")
            return None

        # Define 3D positions of markers in world frame (PCB frame)
        # Assume markers are at PCB corners in a square configuration
        marker_3d_positions = self._get_marker_3d_positions()

        # Collect corresponding 2D-3D points
        object_points = []
        image_points = []

        for i, marker_id in enumerate(detected_ids):
            if marker_id in expected_ids:
                # Get 2D corner positions
                corner = corners[i][0]

                # Use center of marker for simplicity
                center_2d = corner.mean(axis=0)
                image_points.append(center_2d)

                # Get 3D position
                marker_idx = expected_ids.index(marker_id)
                object_points.append(marker_3d_positions[marker_idx])

        object_points = np.array(object_points, dtype=np.float32)
        image_points = np.array(image_points, dtype=np.float32)

        # Solve PnP (Perspective-n-Point)
        success, rvec, tvec = cv2.solvePnP(
            object_points,
            image_points,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            logger.warning(f"PnP failed for view '{view_id}'")
            return None

        # Convert rotation vector to matrix
        rotation_matrix, _ = cv2.Rodrigues(rvec)

        # Calculate confidence based on number of markers detected
        confidence = len(common_ids) / len(expected_ids)

        # Calculate reprojection error
        projected_points, _ = cv2.projectPoints(
            object_points, rvec, tvec, self.camera_matrix, self.dist_coeffs
        )
        reprojection_error = np.sqrt(np.mean((image_points - projected_points.squeeze()) ** 2))

        pose = CameraPose(
            rotation_matrix=rotation_matrix,
            translation_vector=tvec.flatten(),
            view_id=view_id,
            confidence=confidence,
            markers_detected=len(common_ids),
            markers_expected=len(expected_ids),
            reprojection_error=reprojection_error
        )

        logger.info(f"Estimated pose for '{view_id}': {len(common_ids)}/{len(expected_ids)} markers, error: {reprojection_error:.2f}px")

        return pose

    def calibrate_multi_view_sequence(
        self,
        images: List[np.ndarray],
        view_ids: List[str]
    ) -> CalibrationResult:
        """
        Calibrate all views in multi-view sequence.

        Args:
            images: List of images from different viewpoints
            view_ids: List of view identifiers

        Returns:
            CalibrationResult with all poses
        """
        if len(images) != len(view_ids):
            raise ValueError("Number of images must match number of view IDs")

        self.poses = []

        for image, view_id in zip(images, view_ids):
            pose = self.estimate_pose_from_markers(image, view_id)
            if pose is not None:
                self.poses.append(pose)

        result = CalibrationResult(
            camera_matrix=self.camera_matrix,
            dist_coeffs=self.dist_coeffs,
            poses=self.poses,
            marker_size_mm=self.marker_size_mm,
            marker_ids=self.marker_ids
        )

        logger.info(f"Multi-view calibration complete: {len(self.poses)}/{len(view_ids)} poses estimated")

        return result

    def _get_marker_3d_positions(self) -> np.ndarray:
        """
        Get 3D positions of ArUco markers in world frame (PCB frame).

        Assumes markers are at corners of a rectangular PCB.
        Origin at center of PCB, Z-up.

        Returns:
            Array of 3D positions [N, 3] in mm
        """
        # Example: 100mm × 100mm PCB with markers at corners
        # Adjust based on actual PCB size
        pcb_width = 100.0  # mm
        pcb_height = 100.0  # mm

        half_w = pcb_width / 2
        half_h = pcb_height / 2

        positions = np.array([
            [-half_w, -half_h, 0],  # Marker 0: bottom-left
            [half_w, -half_h, 0],   # Marker 1: bottom-right
            [half_w, half_h, 0],    # Marker 2: top-right
            [-half_w, half_h, 0]    # Marker 3: top-left
        ], dtype=np.float32)

        return positions

    def transform_point_to_world(
        self,
        point_2d: np.ndarray,
        pose: CameraPose,
        z_world: float = 0.0
    ) -> np.ndarray:
        """
        Transform 2D image point to 3D world coordinates.

        Args:
            point_2d: 2D point in image [x, y]
            pose: Camera pose
            z_world: Assumed Z coordinate in world frame (mm)

        Returns:
            3D point in world frame [x, y, z]
        """
        # This is a simplified version assuming planar world (PCB surface)
        # For full 3D, need depth information

        # Undistort point
        point_2d_undistorted = cv2.undistortPoints(
            np.array([[point_2d]], dtype=np.float32),
            self.camera_matrix,
            self.dist_coeffs,
            P=self.camera_matrix
        )[0][0]

        # Convert to normalized camera coordinates
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        cx = self.camera_matrix[0, 2]
        cy = self.camera_matrix[1, 2]

        x_norm = (point_2d_undistorted[0] - cx) / fx
        y_norm = (point_2d_undistorted[1] - cy) / fy

        # Ray in camera frame
        ray_camera = np.array([x_norm, y_norm, 1.0])

        # Transform to world frame
        R = pose.rotation_matrix
        t = pose.translation_vector

        # Solve for intersection with plane z = z_world
        # This is simplified - for proper multi-view, use triangulation

        # World point (simplified)
        world_point = R.T @ (ray_camera - t)
        scale = z_world / world_point[2] if world_point[2] != 0 else 1.0
        world_point *= scale

        return world_point


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        # Test with real images
        image_path = sys.argv[1]
        image = cv2.imread(image_path)

        if image is None:
            print(f"Error: Could not load image {image_path}")
            sys.exit(1)

        # Initialize calibrator
        calibrator = MultiViewCalibrator(marker_size_mm=30.0)

        # For demo, use simple camera matrix (should be calibrated properly)
        h, w = image.shape[:2]
        focal_length = max(h, w) * 1.2
        camera_matrix = np.array([
            [focal_length, 0, w / 2],
            [0, focal_length, h / 2],
            [0, 0, 1]
        ], dtype=np.float32)
        dist_coeffs = np.zeros(5, dtype=np.float32)

        calibrator.load_camera_intrinsics(camera_matrix, dist_coeffs)

        # Estimate pose
        pose = calibrator.estimate_pose_from_markers(image, "test_view")

        if pose:
            print(f"\nPose estimation successful!")
            print(f"View ID: {pose.view_id}")
            print(f"Markers detected: {pose.markers_detected}/{pose.markers_expected}")
            print(f"Confidence: {pose.confidence:.2f}")
            print(f"Reprojection error: {pose.reprojection_error:.2f} pixels")
            print(f"\nRotation matrix:\n{pose.rotation_matrix}")
            print(f"\nTranslation vector: {pose.translation_vector}")
        else:
            print("Failed to estimate pose (no markers detected)")
    else:
        print("Usage: python camera_calibration.py <image_path>")
        print("Image should contain ArUco markers (IDs: 0, 1, 2, 3)")
