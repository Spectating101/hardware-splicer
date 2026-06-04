"""
Dum-E End-to-End Robotic Workflow Orchestrator

Complete autonomous workflow:
1. Multi-view PCB capture
2. Component and defect detection
3. Multi-view fusion
4. Case design generation
5. Fabrication with quality feedback
6. Verification and retry if needed

Author: Dum-E Robotic Assistant
Version: 1.0.0
"""

import argparse
import logging
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vision.enhanced_detector import EnhancedComponentDetector
from vision.camera_calibration import MultiViewCalibrator, CalibrationResult
from vision.multi_view_fusion import MultiViewFusion
from multi_view_capture import MultiViewCapture, SimulatedRobot

# Optional: 3d-splicer integration (if available)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "3d-splicer"))
    from circuit_ai_client import CircuitAIClient
    from services.adaptive_optimizer import AdaptiveOptimizer
    from services.evaluator.fabrication_quality import FabricationQualityEvaluator
    SPLICER_AVAILABLE = True
except ImportError:
    SPLICER_AVAILABLE = False
    logging.warning("3d-splicer not available - fabrication features disabled")


logger = logging.getLogger(__name__)


class DumEWorkflow:
    """
    Complete Dum-E robotic workflow orchestrator.

    Integrates:
    - Circuit-AI (vision)
    - 3d-splicer (fabrication)
    - Multi-view capture
    - Quality feedback
    """

    def __init__(
        self,
        robot_interface=None,
        output_dir: Path = None,
        enable_fabrication: bool = False,
        enable_multi_view: bool = True
    ):
        """
        Initialize Dum-E workflow.

        Args:
            robot_interface: Robot control interface
            output_dir: Output directory for results
            enable_fabrication: Enable 3D printing features
            enable_multi_view: Use multi-view capture
        """
        self.robot = robot_interface
        self.output_dir = output_dir or Path("dum_e_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_fabrication = enable_fabrication and SPLICER_AVAILABLE
        self.enable_multi_view = enable_multi_view

        # Initialize components
        self.detector = EnhancedComponentDetector()

        if self.enable_multi_view:
            self.calibrator = MultiViewCalibrator(marker_size_mm=30.0)
            self.fusion = MultiViewFusion(min_views_for_consensus=2)

            if self.robot:
                self.capture = MultiViewCapture(robot=self.robot, output_dir=self.output_dir)

        if self.enable_fabrication:
            self.splicer_client = CircuitAIClient()
            self.optimizer = AdaptiveOptimizer(max_iterations=3)
            self.quality_evaluator = FabricationQualityEvaluator()

        logger.info(f"DumEWorkflow initialized")
        logger.info(f"  Multi-view: {self.enable_multi_view}")
        logger.info(f"  Fabrication: {self.enable_fabrication}")

    def run_complete_workflow(
        self,
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Run complete Dum-E workflow.

        Returns:
            Results dictionary with all outputs
        """
        if session_id is None:
            session_id = f"dum_e_{int(time.time())}"

        logger.info(f"=" * 70)
        logger.info(f"Starting Dum-E workflow: {session_id}")
        logger.info(f"=" * 70)

        start_time = time.time()
        results = {
            "session_id": session_id,
            "timestamp": start_time,
            "steps_completed": [],
            "status": "in_progress"
        }

        # Step 1: Multi-view capture
        logger.info("\n[Step 1/5] Multi-view PCB capture...")

        if self.enable_multi_view and self.robot:
            images = self.capture.capture_sequence(session_id=session_id)
            results["images_captured"] = len(images)
            results["steps_completed"].append("capture")
            logger.info(f"✓ Captured {len(images)} views")
        else:
            logger.warning("Skipping multi-view capture (no robot available)")
            images = {}

        # Step 2: Component and defect detection
        logger.info("\n[Step 2/5] Component and defect detection...")

        detections_per_view = {}
        for view_id, image in images.items():
            detection_result = self.detector.detect_components_and_defects(image)
            detections_per_view[view_id] = detection_result

        results["detections_per_view"] = {
            view_id: {
                "component_count": len(det["components"]),
                "defect_count": len(det["defects"]),
                "quality_score": det["quality_score"]
            }
            for view_id, det in detections_per_view.items()
        }
        results["steps_completed"].append("detection")
        logger.info(f"✓ Detected components and defects in {len(detections_per_view)} views")

        # Step 3: Multi-view fusion (if enabled)
        if self.enable_multi_view and len(images) > 1:
            logger.info("\n[Step 3/5] Multi-view fusion...")

            # TODO: Need camera poses for proper fusion
            # For now, skip fusion if poses not available
            logger.warning("Multi-view fusion requires camera calibration - skipping for now")
            results["steps_completed"].append("fusion_skipped")
        else:
            logger.info("\n[Step 3/5] Skipping multi-view fusion (single view)")
            results["steps_completed"].append("fusion_skipped")

        # Step 4: Case design generation (if fabrication enabled)
        if self.enable_fabrication:
            logger.info("\n[Step 4/5] Case design generation...")

            # Use first view's detections
            first_view = list(detections_per_view.values())[0] if detections_per_view else None

            if first_view and first_view["components"]:
                # Convert to board spec format
                board_spec = self._convert_to_board_spec(first_view)

                # Submit to 3d-splicer
                try:
                    job = self.splicer_client.submit_board_spec(
                        board_spec,
                        output_dir=str(self.output_dir / session_id)
                    )

                    results["case_generation_job_id"] = job.get("job_id")
                    results["steps_completed"].append("case_design")
                    logger.info(f"✓ Case design submitted (job: {job.get('job_id')})")

                except Exception as e:
                    logger.error(f"Case generation failed: {e}")
                    results["case_generation_error"] = str(e)
            else:
                logger.warning("No components detected - skipping case generation")
                results["steps_completed"].append("case_design_skipped")
        else:
            logger.info("\n[Step 4/5] Fabrication disabled - skipping case generation")
            results["steps_completed"].append("case_design_disabled")

        # Step 5: Quality verification (if fabrication enabled)
        if self.enable_fabrication and "case_generation_job_id" in results:
            logger.info("\n[Step 5/5] Quality verification...")

            # TODO: Actual print + scan + evaluate
            # For now, just log that it would happen
            logger.info("Quality verification would happen here:")
            logger.info("  1. Wait for print completion")
            logger.info("  2. Scan printed part")
            logger.info("  3. Evaluate quality vs design")
            logger.info("  4. Retry with adjusted parameters if needed")

            results["steps_completed"].append("verification_pending")
        else:
            logger.info("\n[Step 5/5] Skipping quality verification")
            results["steps_completed"].append("verification_disabled")

        # Complete
        end_time = time.time()
        results["status"] = "completed"
        results["total_time_seconds"] = end_time - start_time

        logger.info(f"\n" + "=" * 70)
        logger.info(f"Dum-E workflow completed in {results['total_time_seconds']:.1f}s")
        logger.info(f"Steps: {' → '.join(results['steps_completed'])}")
        logger.info(f"=" * 70 + "\n")

        # Save results
        results_path = self.output_dir / f"{session_id}_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to: {results_path}")

        return results

    def run_inspection_only(
        self,
        image_paths: List[Path]
    ) -> Dict:
        """
        Run inspection-only workflow (no fabrication).

        Args:
            image_paths: Paths to PCB images

        Returns:
            Inspection results
        """
        logger.info("Running inspection-only workflow...")

        results = {
            "mode": "inspection_only",
            "images": [],
            "overall_quality": 0.0,
            "total_defects": 0
        }

        for i, image_path in enumerate(image_paths, 1):
            logger.info(f"[{i}/{len(image_paths)}] Inspecting: {image_path.name}")

            import cv2
            image = cv2.imread(str(image_path))

            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                continue

            # Detect components and defects
            detection = self.detector.detect_components_and_defects(image)

            results["images"].append({
                "path": str(image_path),
                "components": len(detection["components"]),
                "defects": len(detection["defects"]),
                "quality_score": detection["quality_score"],
                "pass_fail": detection["pass_fail"]
            })

            results["total_defects"] += len(detection["defects"])

        # Calculate overall quality
        if results["images"]:
            results["overall_quality"] = sum(
                img["quality_score"] for img in results["images"]
            ) / len(results["images"])

        return results

    def _convert_to_board_spec(self, detection_result: Dict) -> Dict:
        """Convert detection result to board specification for 3d-splicer."""
        # Simplified conversion - adjust based on actual API
        return {
            "components": detection_result["components"],
            "board_dimensions": {
                "width": 100,  # Placeholder - should compute from detections
                "height": 100,
                "thickness": 1.6  # Standard PCB thickness
            }
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Dum-E End-to-End Robotic Workflow"
    )

    parser.add_argument(
        "--mode",
        choices=["full", "inspection", "capture", "fabrication"],
        default="full",
        help="Workflow mode"
    )

    parser.add_argument(
        "--robot-type",
        choices=["simulated", "rebel", "ur5"],
        default="simulated",
        help="Robot type"
    )

    parser.add_argument(
        "--images",
        nargs="+",
        type=Path,
        help="Image paths (for inspection mode)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dum_e_output"),
        help="Output directory"
    )

    parser.add_argument(
        "--session-id",
        type=str,
        help="Session ID (default: auto-generated)"
    )

    parser.add_argument(
        "--enable-fabrication",
        action="store_true",
        help="Enable 3D printing features"
    )

    parser.add_argument(
        "--disable-multi-view",
        action="store_true",
        help="Disable multi-view capture"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize robot (if needed)
    robot = None
    if args.mode in ["full", "capture"]:
        if args.robot_type == "simulated":
            robot = SimulatedRobot(use_test_images=True)
        else:
            logger.error(f"Robot type '{args.robot_type}' not implemented yet")
            return 1

    # Initialize workflow
    workflow = DumEWorkflow(
        robot_interface=robot,
        output_dir=args.output_dir,
        enable_fabrication=args.enable_fabrication,
        enable_multi_view=not args.disable_multi_view
    )

    # Run workflow
    if args.mode == "inspection" and args.images:
        results = workflow.run_inspection_only(args.images)
        print("\n" + "=" * 70)
        print("INSPECTION RESULTS")
        print("=" * 70)
        print(f"Images inspected: {len(results['images'])}")
        print(f"Overall quality: {results['overall_quality']:.2f}")
        print(f"Total defects: {results['total_defects']}")
        print("=" * 70 + "\n")

    elif args.mode == "full":
        results = workflow.run_complete_workflow(session_id=args.session_id)

    else:
        logger.error(f"Mode '{args.mode}' not fully implemented yet")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
