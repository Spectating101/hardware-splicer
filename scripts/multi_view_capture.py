"""
Multi-View PCB Capture Script for Robotic Arm

Orchestrates robot arm movement to capture PCB from multiple angles.

Standard capture sequence:
1. Top view (0°, directly above)
2. North 45° (angled from north side)
3. East 45° (angled from east side)
4. South 45° (angled from south side)
5. West 45° (angled from west side)
6. Bottom view (optional, requires flip mechanism)

Author: Dum-E Vision System
Version: 1.0.0
"""

import cv2
import numpy as np
import logging
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

# Robot interface (abstract - adapt to your specific robot)
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class RobotInterface(ABC):
    """
    Abstract interface for robot arm control.

    Implement this for your specific robot (e.g., ReBeL, UR5, custom).
    """

    @abstractmethod
    def move_to_pose(self, pose: Dict) -> bool:
        """
        Move robot to specified pose.

        Args:
            pose: {
                "position": [x, y, z],  # mm
                "orientation": [roll, pitch, yaw]  # degrees
            }

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def capture_image(self) -> np.ndarray:
        """
        Capture image from mounted camera.

        Returns:
            Image as numpy array (BGR)
        """
        pass

    @abstractmethod
    def get_current_pose(self) -> Dict:
        """
        Get current robot pose.

        Returns:
            {position: [x, y, z], orientation: [roll, pitch, yaw]}
        """
        pass

    @abstractmethod
    def home(self) -> bool:
        """Return robot to home position."""
        pass


class SimulatedRobot(RobotInterface):
    """Simulated robot for testing (uses webcam or test images)."""

    def __init__(self, camera_id: int = 0, use_test_images: bool = False):
        """
        Initialize simulated robot.

        Args:
            camera_id: Webcam ID (if not using test images)
            use_test_images: Use pre-captured test images instead of webcam
        """
        self.camera_id = camera_id
        self.use_test_images = use_test_images
        self.current_pose = {"position": [0, 0, 300], "orientation": [0, 0, 0]}

        if not use_test_images:
            self.camera = cv2.VideoCapture(camera_id)
            if not self.camera.isOpened():
                raise ValueError(f"Could not open camera {camera_id}")

        logger.info("Simulated robot initialized")

    def move_to_pose(self, pose: Dict) -> bool:
        """Simulate movement (just update internal state)."""
        logger.info(f"Moving to pose: {pose}")
        self.current_pose = pose
        time.sleep(0.5)  # Simulate movement time
        return True

    def capture_image(self) -> np.ndarray:
        """Capture from webcam or return test image."""
        if self.use_test_images:
            # Return solid color image as placeholder
            h, w = 600, 800
            image = np.zeros((h, w, 3), dtype=np.uint8)
            image[:, :] = [50, 120, 50]  # Green PCB
            return image
        else:
            ret, frame = self.camera.read()
            if not ret:
                raise RuntimeError("Failed to capture image from camera")
            return frame

    def get_current_pose(self) -> Dict:
        """Return current pose."""
        return self.current_pose

    def home(self) -> bool:
        """Return to home."""
        self.current_pose = {"position": [0, 0, 300], "orientation": [0, 0, 0]}
        return True

    def __del__(self):
        """Cleanup camera."""
        if not self.use_test_images and hasattr(self, 'camera'):
            self.camera.release()


class MultiViewCapture:
    """
    Multi-view capture orchestrator for Dum-E robotic inspection.

    Manages robot movement and image capture across multiple viewpoints.
    """

    # Standard viewpoints for PCB inspection
    VIEWPOINTS = {
        "top": {
            "position": [0, 0, 300],  # Directly above, 300mm height
            "orientation": [0, 0, 0]  # Level
        },
        "north_45": {
            "position": [0, -150, 250],  # North side, angled
            "orientation": [45, 0, 0]  # 45° tilt
        },
        "east_45": {
            "position": [150, 0, 250],  # East side, angled
            "orientation": [45, 0, 90]  # 45° tilt, rotated
        },
        "south_45": {
            "position": [0, 150, 250],  # South side, angled
            "orientation": [45, 0, 180]
        },
        "west_45": {
            "position": [-150, 0, 250],  # West side, angled
            "orientation": [45, 0, 270]
        },
        # Bottom view requires flip mechanism
        # "bottom": {
        #     "position": [0, 0, -300],
        #     "orientation": [180, 0, 0]
        # }
    }

    def __init__(
        self,
        robot: RobotInterface,
        output_dir: Path = None,
        stabilization_delay: float = 1.0
    ):
        """
        Initialize multi-view capture.

        Args:
            robot: Robot interface implementation
            output_dir: Directory to save captured images
            stabilization_delay: Delay after movement (seconds)
        """
        self.robot = robot
        self.output_dir = output_dir or Path("multi_view_captures")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stabilization_delay = stabilization_delay

        logger.info(f"MultiViewCapture initialized (output: {self.output_dir})")

    def capture_sequence(
        self,
        view_ids: List[str] = None,
        save_images: bool = True,
        session_id: str = None
    ) -> Dict[str, np.ndarray]:
        """
        Capture full multi-view sequence.

        Args:
            view_ids: List of view IDs to capture (default: all standard views)
            save_images: Save images to disk
            session_id: Session identifier for saved images

        Returns:
            {view_id: image_array}
        """
        if view_ids is None:
            view_ids = list(self.VIEWPOINTS.keys())

        if session_id is None:
            session_id = time.strftime("%Y%m%d_%H%M%S")

        logger.info(f"Starting multi-view capture sequence (session: {session_id})")
        logger.info(f"Views to capture: {view_ids}")

        images = {}
        metadata = {
            "session_id": session_id,
            "timestamp": time.time(),
            "view_sequence": view_ids,
            "captures": {}
        }

        # Home position first
        logger.info("Moving to home position...")
        self.robot.home()
        time.sleep(self.stabilization_delay)

        # Capture each view
        for i, view_id in enumerate(view_ids, 1):
            logger.info(f"[{i}/{len(view_ids)}] Capturing view: {view_id}")

            try:
                # Move to viewpoint
                pose = self.VIEWPOINTS[view_id]
                success = self.robot.move_to_pose(pose)

                if not success:
                    logger.error(f"Failed to move to viewpoint '{view_id}'")
                    continue

                # Wait for stabilization
                time.sleep(self.stabilization_delay)

                # Capture image
                image = self.robot.capture_image()

                if image is None or image.size == 0:
                    logger.error(f"Failed to capture image for view '{view_id}'")
                    continue

                images[view_id] = image

                # Save image
                if save_images:
                    filename = f"{session_id}_{view_id}.jpg"
                    filepath = self.output_dir / filename
                    cv2.imwrite(str(filepath), image)
                    logger.info(f"Saved image: {filepath}")

                # Save metadata
                metadata["captures"][view_id] = {
                    "pose": pose,
                    "timestamp": time.time(),
                    "image_shape": image.shape,
                    "filename": filename if save_images else None
                }

                logger.info(f"✓ Captured {view_id}: {image.shape}")

            except Exception as e:
                logger.error(f"Error capturing view '{view_id}': {e}")
                continue

        # Return to home
        logger.info("Returning to home position...")
        self.robot.home()

        # Save metadata
        if save_images:
            metadata_path = self.output_dir / f"{session_id}_metadata.json"
            with open(metadata_path, 'w') as f:
                # Convert numpy arrays in metadata to lists
                serializable_metadata = self._make_serializable(metadata)
                json.dump(serializable_metadata, f, indent=2)
            logger.info(f"Saved metadata: {metadata_path}")

        logger.info(f"Multi-view capture complete: {len(images)}/{len(view_ids)} views captured")

        return images

    def capture_single_view(
        self,
        view_id: str,
        save_image: bool = False,
        filename: str = None
    ) -> Optional[np.ndarray]:
        """
        Capture single view.

        Args:
            view_id: View identifier
            save_image: Save image to disk
            filename: Custom filename (optional)

        Returns:
            Captured image or None if failed
        """
        if view_id not in self.VIEWPOINTS:
            logger.error(f"Unknown view ID: {view_id}")
            return None

        logger.info(f"Capturing single view: {view_id}")

        # Move to viewpoint
        pose = self.VIEWPOINTS[view_id]
        self.robot.move_to_pose(pose)
        time.sleep(self.stabilization_delay)

        # Capture
        image = self.robot.capture_image()

        if image is None:
            logger.error(f"Failed to capture view '{view_id}'")
            return None

        # Save if requested
        if save_image:
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{view_id}.jpg"

            filepath = self.output_dir / filename
            cv2.imwrite(str(filepath), image)
            logger.info(f"Saved image: {filepath}")

        return image

    def _make_serializable(self, obj):
        """Convert numpy arrays and other non-serializable types to JSON-compatible format."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._make_serializable(item) for item in obj)
        elif isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        else:
            return obj


def main():
    """Command-line interface for multi-view capture."""
    parser = argparse.ArgumentParser(
        description="Multi-view PCB capture for Dum-E robotic inspection"
    )

    parser.add_argument(
        "--robot-type",
        choices=["simulated", "rebel", "ur5", "custom"],
        default="simulated",
        help="Robot type"
    )

    parser.add_argument(
        "--camera-id",
        type=int,
        default=0,
        help="Camera ID for simulated robot"
    )

    parser.add_argument(
        "--views",
        nargs="+",
        default=None,
        help="Specific views to capture (default: all)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("multi_view_captures"),
        help="Output directory for images"
    )

    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session ID (default: timestamp)"
    )

    parser.add_argument(
        "--stabilization-delay",
        type=float,
        default=1.0,
        help="Stabilization delay after movement (seconds)"
    )

    parser.add_argument(
        "--test-images",
        action="store_true",
        help="Use synthetic test images instead of camera"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize robot
    if args.robot_type == "simulated":
        robot = SimulatedRobot(
            camera_id=args.camera_id,
            use_test_images=args.test_images
        )
    else:
        raise NotImplementedError(f"Robot type '{args.robot_type}' not implemented yet")

    # Initialize capture system
    capture = MultiViewCapture(
        robot=robot,
        output_dir=args.output_dir,
        stabilization_delay=args.stabilization_delay
    )

    # Capture sequence
    images = capture.capture_sequence(
        view_ids=args.views,
        save_images=True,
        session_id=args.session_id
    )

    print(f"\n{'='*70}")
    print(f"Multi-view capture complete!")
    print(f"{'='*70}")
    print(f"Views captured: {len(images)}/{len(args.views or MultiViewCapture.VIEWPOINTS)}")
    print(f"Output directory: {args.output_dir}")
    print(f"{'='*70}\n")

    for view_id in images.keys():
        print(f"  ✓ {view_id}")

    print()


if __name__ == "__main__":
    main()
