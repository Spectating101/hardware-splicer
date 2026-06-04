"""
Automatic Hardware Configuration and Optimization

Intelligent auto-config that:
1. Detects available hardware
2. Recommends optimal workflow
3. Tests and optimizes viewpoints
4. Adapts to constraints and failures

Usage:
    python auto_configure.py --test-views
    python auto_configure.py --optimize-for-pcb 100x80
    python auto_configure.py --full-calibration

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import argparse
import logging
import sys
import time
from pathlib import Path
import json
import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.hardware_detector import HardwareDetector, CapabilityLevel
from intelligence.view_optimizer import ViewOptimizer, ViewQuality
from vision.camera_calibration import MultiViewCalibrator


logger = logging.getLogger(__name__)


class AutoConfigurator:
    """
    Intelligent auto-configuration system.

    Automatically configures Dum-E for whatever hardware is available.
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize auto-configurator.

        Args:
            output_dir: Output directory for config files
        """
        self.output_dir = output_dir or Path("auto_config_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.hardware_detector = HardwareDetector()
        self.view_optimizer = ViewOptimizer()
        self.calibrator = MultiViewCalibrator()

        self.config = {}

        logger.info("AutoConfigurator initialized")

    def run_full_auto_config(self) -> Dict:
        """
        Run complete auto-configuration process.

        Returns:
            Configuration dictionary
        """
        print("\n" + "=" * 70)
        print("DUM-E AUTOMATIC CONFIGURATION")
        print("=" * 70)
        print()

        # Step 1: Detect hardware
        print("[Step 1/4] Detecting hardware...")
        hardware = self.hardware_detector.auto_detect()

        if not hardware:
            print("  ⚠ No hardware detected!")
            print("  → Will configure for manual operation")
            self.config["mode"] = "manual"
            return self.config

        print(f"  ✓ Detected {len(hardware)} device(s)")

        # Step 2: Recommend workflow
        print("\n[Step 2/4] Analyzing capabilities...")
        workflow = self.hardware_detector.get_recommended_workflow()

        self.config["workflow"] = workflow
        print(f"  ✓ Recommended mode: {workflow['mode']}")

        # Step 3: Test views (if camera available)
        print("\n[Step 3/4] Testing view quality...")

        primary = self.hardware_detector.primary_hardware
        if primary and hasattr(primary, 'can_rotate'):
            test_results = self._test_view_quality()

            if test_results:
                self.config["view_quality"] = test_results
                print(f"  ✓ Tested {len(test_results)} viewpoints")
            else:
                print("  ⚠ Could not test views (no camera available)")

        # Step 4: Generate final config
        print("\n[Step 4/4] Generating configuration...")

        self.config["hardware"] = [hw.to_dict() for hw in hardware]
        self.config["primary_device"] = primary.to_dict() if primary else None

        # Save config
        config_path = self.output_dir / "dum_e_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        print(f"  ✓ Saved configuration to {config_path}")

        # Print summary
        print("\n" + "=" * 70)
        print("CONFIGURATION COMPLETE")
        print("=" * 70)
        print(f"Hardware: {primary.device_name if primary else 'None'}")
        print(f"Mode: {workflow['mode']}")
        print(f"Multi-view: {'Yes' if workflow.get('enable_fusion') else 'No'}")
        print(f"Config file: {config_path}")
        print("=" * 70 + "\n")

        return self.config

    def _test_view_quality(self) -> List[Dict]:
        """Test quality of different viewpoints."""
        results = []

        # Try to capture test images
        try:
            import cv2

            cap = cv2.VideoCapture(0)

            if not cap.isOpened():
                logger.warning("Could not open camera for view testing")
                return results

            print("  → Capturing test images...")

            # Capture a test frame
            ret, frame = cap.read()

            if not ret:
                logger.warning("Failed to capture test frame")
                cap.release()
                return results

            # Assess quality
            score = self.view_optimizer.assess_view_quality(
                frame,
                view_id="test_view",
                expected_markers=4
            )

            results.append(score.to_dict())

            print(f"  → Test view quality: {score.quality.value} (score: {score.score:.2f})")

            # Show suggestions if quality is poor
            if score.quality in [ViewQuality.POOR, ViewQuality.FAILED]:
                print("  ⚠ View quality issues detected:")
                for issue in score.issues:
                    print(f"      - {issue}")

                print("  → Suggestions:")
                for suggestion in score.suggestions:
                    print(f"      • {suggestion}")

            cap.release()

        except Exception as e:
            logger.error(f"View testing failed: {e}")

        return results

    def optimize_for_pcb(self, width_mm: float, height_mm: float):
        """
        Optimize configuration for specific PCB size.

        Args:
            width_mm: PCB width in mm
            height_mm: PCB height in mm
        """
        print(f"\nOptimizing for PCB: {width_mm}×{height_mm}mm")

        pcb_dimensions = {
            "width_mm": width_mm,
            "height_mm": height_mm,
            "thickness_mm": 1.6  # Standard
        }

        primary = self.hardware_detector.primary_hardware

        if not primary:
            print("  ⚠ No hardware detected - cannot optimize")
            return

        hardware_constraints = {
            "max_reach_mm": primary.max_reach_mm,
            "min_distance_mm": 100.0,  # Typical minimum camera distance
            "precision_mm": primary.position_accuracy_mm
        }

        # Generate optimal viewpoints
        viewpoints = self.view_optimizer.optimize_view_sequence(
            pcb_dimensions,
            hardware_constraints
        )

        print(f"\n  ✓ Generated {len(viewpoints)} optimal viewpoints:")

        for i, vp in enumerate(viewpoints, 1):
            print(f"    {i}. Position: ({vp.position[0]:.1f}, {vp.position[1]:.1f}, {vp.position[2]:.1f})mm")
            print(f"       Orientation: ({vp.orientation[0]:.1f}, {vp.orientation[1]:.1f}, {vp.orientation[2]:.1f})°")
            print(f"       Distance: {vp.camera_distance_mm:.1f}mm")

        # Save to config
        self.config["optimized_viewpoints"] = [
            {
                "position": vp.position,
                "orientation": vp.orientation,
                "distance_mm": vp.camera_distance_mm
            }
            for vp in viewpoints
        ]

        config_path = self.output_dir / f"pcb_{width_mm}x{height_mm}_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        print(f"\n  ✓ Saved optimized config to {config_path}")

    def interactive_calibration(self):
        """Interactive calibration wizard."""
        print("\n" + "=" * 70)
        print("INTERACTIVE CALIBRATION WIZARD")
        print("=" * 70)
        print()

        print("This wizard will help you calibrate Dum-E for your hardware.")
        print()

        # Step 1: Hardware detection
        print("Step 1: Hardware Detection")
        print("-" * 70)

        input("Press Enter to scan for hardware...")

        hardware = self.hardware_detector.auto_detect()
        print()
        print(self.hardware_detector.generate_report())

        if not hardware:
            print("\n⚠ No hardware detected.")
            print("Would you like to:")
            print("  1. Configure for manual operation (phone/webcam)")
            print("  2. Exit and connect hardware")

            choice = input("\nChoice (1/2): ").strip()

            if choice == "1":
                self._configure_manual_mode()
            else:
                print("Exiting. Please connect hardware and try again.")
                return

        else:
            # Step 2: View testing
            print("\nStep 2: View Quality Testing")
            print("-" * 70)
            print("Place a PCB with ArUco markers in view.")
            input("Press Enter when ready...")

            self._test_view_quality()

            # Step 3: Optimization
            print("\nStep 3: Viewpoint Optimization")
            print("-" * 70)

            pcb_size = input("Enter PCB size (width×height in mm, e.g. 100x80): ").strip()

            try:
                width, height = map(float, pcb_size.split('x'))
                self.optimize_for_pcb(width, height)
            except ValueError:
                print("Invalid size format. Using default 100×80mm")
                self.optimize_for_pcb(100, 80)

        # Done
        print("\n" + "=" * 70)
        print("CALIBRATION COMPLETE")
        print("=" * 70)
        print(f"\nConfiguration saved to: {self.output_dir}")
        print("\nYou can now run Dum-E with:")
        print(f"  python scripts/dum_e_workflow.py --config {self.output_dir}/dum_e_config.json")

    def _configure_manual_mode(self):
        """Configure for manual operation."""
        print("\nConfiguring for manual operation...")

        self.config["mode"] = "manual"
        self.config["workflow"] = {
            "mode": "manual_guided",
            "views": ["top", "angle1", "angle2", "angle3"],
            "enable_fusion": True,
            "notes": "Manual positioning with on-screen guidance"
        }

        config_path = self.output_dir / "manual_mode_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        print(f"✓ Manual mode configured: {config_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Automatic Hardware Configuration for Dum-E"
    )

    parser.add_argument(
        "--test-views",
        action="store_true",
        help="Test view quality with current setup"
    )

    parser.add_argument(
        "--optimize-for-pcb",
        type=str,
        help="Optimize for PCB size (e.g., 100x80)"
    )

    parser.add_argument(
        "--full-calibration",
        action="store_true",
        help="Run interactive calibration wizard"
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="Fully automated configuration (no prompts)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("auto_config_output"),
        help="Output directory for config files"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    # Initialize configurator
    configurator = AutoConfigurator(output_dir=args.output_dir)

    # Run requested operation
    if args.full_calibration:
        configurator.interactive_calibration()

    elif args.test_views:
        print("Testing view quality...\n")
        results = configurator._test_view_quality()

        if results:
            print("\n✓ View quality test complete")
        else:
            print("\n⚠ Could not test views")

    elif args.optimize_for_pcb:
        try:
            width, height = map(float, args.optimize_for_pcb.split('x'))
            configurator.optimize_for_pcb(width, height)
        except ValueError:
            print("Error: Invalid PCB size format. Use: 100x80")
            return 1

    elif args.auto:
        configurator.run_full_auto_config()

    else:
        # No arguments - show help and run auto
        print("No arguments provided. Running automatic configuration...\n")
        configurator.run_full_auto_config()

    return 0


if __name__ == "__main__":
    sys.exit(main())
