"""
Intelligent Hardware Auto-Detection System

Automatically detects and configures available hardware:
- Phone sensors (gyroscope, accelerometer, camera)
- Robot arm capabilities (DOF, reach, precision)
- Turntables, linear stages
- Camera specifications

Adapts workflow to whatever hardware is available.

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import logging
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class HardwareType(Enum):
    """Types of hardware interfaces."""
    PHONE = "phone"
    WEBCAM = "webcam"
    ROBOT_ARM = "robot_arm"
    TURNTABLE = "turntable"
    LINEAR_STAGE = "linear_stage"
    DSLR_CAMERA = "dslr_camera"
    UNKNOWN = "unknown"


class CapabilityLevel(Enum):
    """Hardware capability levels."""
    BASIC = "basic"  # Manual positioning, limited automation
    INTERMEDIATE = "intermediate"  # Semi-automated, some feedback
    ADVANCED = "advanced"  # Fully automated, precise control


@dataclass
class HardwareCapabilities:
    """Detected hardware capabilities."""
    hardware_type: HardwareType
    capability_level: CapabilityLevel

    # Movement capabilities
    can_rotate: bool = False
    can_translate: bool = False
    can_tilt: bool = False
    degrees_of_freedom: int = 0

    # Sensing capabilities
    has_position_feedback: bool = False
    has_orientation_sensor: bool = False
    has_auto_focus: bool = False

    # Precision
    position_accuracy_mm: float = 10.0  # Estimated accuracy
    orientation_accuracy_deg: float = 5.0

    # Workspace
    max_reach_mm: float = 500.0
    workspace_volume_cm3: float = 0.0

    # Metadata
    device_name: str = "Unknown"
    connection_type: str = "unknown"
    notes: str = ""

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "hardware_type": self.hardware_type.value,
            "capability_level": self.capability_level.value,
            "can_rotate": self.can_rotate,
            "can_translate": self.can_translate,
            "can_tilt": self.can_tilt,
            "degrees_of_freedom": self.degrees_of_freedom,
            "has_position_feedback": self.has_position_feedback,
            "has_orientation_sensor": self.has_orientation_sensor,
            "has_auto_focus": self.has_auto_focus,
            "position_accuracy_mm": self.position_accuracy_mm,
            "orientation_accuracy_deg": self.orientation_accuracy_deg,
            "max_reach_mm": self.max_reach_mm,
            "workspace_volume_cm3": self.workspace_volume_cm3,
            "device_name": self.device_name,
            "connection_type": self.connection_type,
            "notes": self.notes
        }


class HardwareDetector:
    """
    Intelligent hardware detection and auto-configuration.

    Detects:
    - What hardware is available
    - What it can do
    - How to control it
    - Optimal workflow for that hardware
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize hardware detector.

        Args:
            config_path: Optional path to hardware config file
        """
        self.config_path = config_path or Path("hardware_config.json")
        self.detected_hardware: List[HardwareCapabilities] = []
        self.primary_hardware: Optional[HardwareCapabilities] = None

        logger.info("HardwareDetector initialized")

    def auto_detect(self) -> List[HardwareCapabilities]:
        """
        Auto-detect all available hardware.

        Returns:
            List of detected hardware with capabilities
        """
        logger.info("Starting hardware auto-detection...")

        self.detected_hardware = []

        # Check for cameras
        cameras = self._detect_cameras()
        self.detected_hardware.extend(cameras)

        # Check for robot arms (via common protocols)
        robots = self._detect_robot_arms()
        self.detected_hardware.extend(robots)

        # Check for turntables/stages
        motion_devices = self._detect_motion_devices()
        self.detected_hardware.extend(motion_devices)

        # Check for phone sensors (if running on Android/iOS)
        phone = self._detect_phone_sensors()
        if phone:
            self.detected_hardware.append(phone)

        # Select primary hardware (most capable)
        if self.detected_hardware:
            self.primary_hardware = self._select_primary_hardware()
            logger.info(f"Primary hardware: {self.primary_hardware.device_name} "
                       f"({self.primary_hardware.hardware_type.value})")
        else:
            logger.warning("No hardware detected! Will use manual mode.")

        # Save configuration
        self._save_config()

        logger.info(f"Detection complete: {len(self.detected_hardware)} device(s) found")
        return self.detected_hardware

    def _detect_cameras(self) -> List[HardwareCapabilities]:
        """Detect available cameras."""
        cameras = []

        import cv2

        # Try to open cameras 0-3
        for camera_id in range(4):
            try:
                cap = cv2.VideoCapture(camera_id)
                if cap.isOpened():
                    # Get camera properties
                    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    fps = cap.get(cv2.CAP_PROP_FPS)

                    # Check if it has auto-focus
                    has_autofocus = cap.get(cv2.CAP_PROP_AUTOFOCUS) > 0

                    cap.release()

                    camera = HardwareCapabilities(
                        hardware_type=HardwareType.WEBCAM,
                        capability_level=CapabilityLevel.BASIC,
                        can_rotate=False,
                        can_translate=False,
                        degrees_of_freedom=0,
                        has_auto_focus=has_autofocus,
                        position_accuracy_mm=50.0,  # Manual positioning
                        device_name=f"Camera {camera_id}",
                        connection_type="USB/Built-in",
                        notes=f"Resolution: {int(width)}×{int(height)}, {int(fps)} FPS"
                    )

                    cameras.append(camera)
                    logger.info(f"✓ Detected camera {camera_id}: {int(width)}×{int(height)}")

            except Exception as e:
                logger.debug(f"No camera at index {camera_id}: {e}")
                continue

        return cameras

    def _detect_robot_arms(self) -> List[HardwareCapabilities]:
        """Detect robot arms via common protocols."""
        robots = []

        # Check for common robot arm interfaces

        # 1. Check for UR robots (Universal Robots)
        if self._check_ur_robot():
            robot = HardwareCapabilities(
                hardware_type=HardwareType.ROBOT_ARM,
                capability_level=CapabilityLevel.ADVANCED,
                can_rotate=True,
                can_translate=True,
                can_tilt=True,
                degrees_of_freedom=6,
                has_position_feedback=True,
                has_orientation_sensor=True,
                position_accuracy_mm=0.1,
                orientation_accuracy_deg=0.5,
                max_reach_mm=850.0,
                workspace_volume_cm3=125000.0,
                device_name="UR5/UR10 Robot Arm",
                connection_type="Ethernet",
                notes="6-DOF industrial robot with ±0.1mm repeatability"
            )
            robots.append(robot)
            logger.info("✓ Detected UR robot arm")

        # 2. Check for ReBeL robot
        if self._check_rebel_robot():
            robot = HardwareCapabilities(
                hardware_type=HardwareType.ROBOT_ARM,
                capability_level=CapabilityLevel.ADVANCED,
                can_rotate=True,
                can_translate=True,
                can_tilt=True,
                degrees_of_freedom=6,
                has_position_feedback=True,
                has_orientation_sensor=True,
                position_accuracy_mm=0.02,
                orientation_accuracy_deg=0.1,
                max_reach_mm=500.0,
                workspace_volume_cm3=50000.0,
                device_name="ReBeL 6-DOF Arm",
                connection_type="USB/Serial",
                notes="Research robot, ±0.02mm precision, $4500"
            )
            robots.append(robot)
            logger.info("✓ Detected ReBeL robot arm")

        # 3. Check for Arduino-based DIY robots
        if self._check_arduino_robot():
            robot = HardwareCapabilities(
                hardware_type=HardwareType.ROBOT_ARM,
                capability_level=CapabilityLevel.INTERMEDIATE,
                can_rotate=True,
                can_translate=True,
                can_tilt=True,
                degrees_of_freedom=4,  # Typical DIY arm
                has_position_feedback=False,  # Often open-loop
                position_accuracy_mm=5.0,
                orientation_accuracy_deg=2.0,
                max_reach_mm=400.0,
                device_name="Arduino Robot Arm",
                connection_type="Serial",
                notes="DIY/hobby robot arm"
            )
            robots.append(robot)
            logger.info("✓ Detected Arduino-based robot")

        return robots

    def _detect_motion_devices(self) -> List[HardwareCapabilities]:
        """Detect turntables, linear stages, etc."""
        devices = []

        # Check for motorized turntable
        if self._check_turntable():
            turntable = HardwareCapabilities(
                hardware_type=HardwareType.TURNTABLE,
                capability_level=CapabilityLevel.INTERMEDIATE,
                can_rotate=True,
                can_translate=False,
                degrees_of_freedom=1,
                has_position_feedback=True,
                position_accuracy_mm=100.0,  # Rotational accuracy
                orientation_accuracy_deg=1.0,
                device_name="Motorized Turntable",
                connection_type="USB/Serial",
                notes="360° rotation for multi-view capture"
            )
            devices.append(turntable)
            logger.info("✓ Detected motorized turntable")

        return devices

    def _detect_phone_sensors(self) -> Optional[HardwareCapabilities]:
        """Detect phone sensors (if running on mobile)."""
        # Check if we're running on Android/iOS
        system = platform.system()

        # This would need platform-specific APIs in production
        # For now, just detect if we're on mobile platform

        if system == "Android" or system == "iOS":
            phone = HardwareCapabilities(
                hardware_type=HardwareType.PHONE,
                capability_level=CapabilityLevel.INTERMEDIATE,
                can_rotate=False,  # Manual rotation
                has_orientation_sensor=True,  # Gyroscope
                has_auto_focus=True,
                position_accuracy_mm=20.0,  # Manual positioning
                orientation_accuracy_deg=1.0,  # Good gyro
                device_name=f"{system} Phone",
                connection_type="Native",
                notes="Phone camera with orientation sensors"
            )
            logger.info(f"✓ Detected {system} phone sensors")
            return phone

        return None

    def _check_ur_robot(self) -> bool:
        """Check for UR robot on network."""
        # Try to connect to default UR robot IP
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            # UR robots typically on port 30002
            result = sock.connect_ex(('192.168.1.100', 30002))
            sock.close()
            return result == 0
        except:
            return False

    def _check_rebel_robot(self) -> bool:
        """Check for ReBeL robot."""
        # Check for ReBeL SDK or serial connection
        # This would need actual SDK integration
        return False  # Placeholder

    def _check_arduino_robot(self) -> bool:
        """Check for Arduino-based robot."""
        # Look for Arduino serial ports
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if 'Arduino' in port.description or 'CH340' in port.description:
                    return True
        except ImportError:
            pass
        return False

    def _check_turntable(self) -> bool:
        """Check for motorized turntable."""
        # Similar to Arduino check
        return False  # Placeholder

    def _select_primary_hardware(self) -> HardwareCapabilities:
        """Select primary hardware (most capable)."""
        # Score each hardware
        def score(hw: HardwareCapabilities) -> int:
            score = 0

            # Capability level
            if hw.capability_level == CapabilityLevel.ADVANCED:
                score += 100
            elif hw.capability_level == CapabilityLevel.INTERMEDIATE:
                score += 50

            # DOF
            score += hw.degrees_of_freedom * 10

            # Capabilities
            if hw.can_rotate: score += 20
            if hw.can_translate: score += 20
            if hw.can_tilt: score += 15
            if hw.has_position_feedback: score += 30
            if hw.has_orientation_sensor: score += 10

            # Precision
            score += int(10 / (hw.position_accuracy_mm + 0.1))

            return score

        scored = [(score(hw), hw) for hw in self.detected_hardware]
        scored.sort(key=lambda x: x[0], reverse=True)

        return scored[0][1] if scored else None

    def get_recommended_workflow(self) -> Dict:
        """
        Get recommended workflow based on detected hardware.

        Returns:
            Workflow configuration
        """
        if not self.primary_hardware:
            return {
                "mode": "manual",
                "views": ["single"],
                "notes": "No hardware detected. Use manual capture."
            }

        hw = self.primary_hardware

        if hw.hardware_type == HardwareType.ROBOT_ARM:
            return {
                "mode": "automated_multi_view",
                "views": ["top", "north_45", "east_45", "south_45", "west_45"],
                "enable_fusion": True,
                "enable_auto_calibration": True,
                "notes": "Full automated multi-view with robot arm"
            }

        elif hw.hardware_type == HardwareType.TURNTABLE:
            return {
                "mode": "semi_automated_rotation",
                "views": ["0", "45", "90", "135", "180", "225", "270", "315"],
                "enable_fusion": True,
                "enable_auto_calibration": False,
                "notes": "Rotate PCB on turntable, fixed camera"
            }

        elif hw.hardware_type == HardwareType.PHONE:
            return {
                "mode": "manual_guided",
                "views": ["top", "angle1", "angle2", "angle3"],
                "enable_fusion": True,
                "enable_auto_calibration": False,
                "notes": "Manual positioning with orientation guidance"
            }

        else:  # Webcam or unknown
            return {
                "mode": "manual",
                "views": ["top", "angle1", "angle2"],
                "enable_fusion": False,
                "enable_auto_calibration": False,
                "notes": "Manual camera positioning, basic inspection"
            }

    def _save_config(self):
        """Save detected hardware configuration."""
        config = {
            "detected_at": __import__('time').time(),
            "hardware": [hw.to_dict() for hw in self.detected_hardware],
            "primary": self.primary_hardware.to_dict() if self.primary_hardware else None,
            "recommended_workflow": self.get_recommended_workflow()
        }

        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved hardware config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def generate_report(self) -> str:
        """Generate human-readable hardware report."""
        lines = []

        lines.append("=" * 70)
        lines.append("HARDWARE AUTO-DETECTION REPORT")
        lines.append("=" * 70)
        lines.append("")

        if not self.detected_hardware:
            lines.append("No hardware detected.")
            lines.append("")
            lines.append("Recommendations:")
            lines.append("  - Use phone on tripod for manual multi-view capture")
            lines.append("  - Or use webcam for single-view inspection")
            lines.append("")
        else:
            lines.append(f"Detected Devices: {len(self.detected_hardware)}")
            lines.append("")

            for i, hw in enumerate(self.detected_hardware, 1):
                lines.append(f"{i}. {hw.device_name}")
                lines.append(f"   Type: {hw.hardware_type.value}")
                lines.append(f"   Capability: {hw.capability_level.value}")
                lines.append(f"   DOF: {hw.degrees_of_freedom}")
                lines.append(f"   Accuracy: {hw.position_accuracy_mm:.2f}mm")
                lines.append(f"   {hw.notes}")
                lines.append("")

            lines.append("Primary Hardware:")
            if self.primary_hardware:
                lines.append(f"  {self.primary_hardware.device_name}")
                lines.append("")

            workflow = self.get_recommended_workflow()
            lines.append("Recommended Workflow:")
            lines.append(f"  Mode: {workflow['mode']}")
            lines.append(f"  Views: {', '.join(workflow['views'])}")
            lines.append(f"  Multi-view fusion: {'Enabled' if workflow.get('enable_fusion') else 'Disabled'}")
            lines.append(f"  Notes: {workflow['notes']}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Test hardware detection
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    detector = HardwareDetector()
    hardware = detector.auto_detect()

    print()
    print(detector.generate_report())
