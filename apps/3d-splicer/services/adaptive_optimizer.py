"""
Adaptive Print Parameter Optimizer

Auto-retries failed prints with adjusted parameters based on failure mode.
Learns from history to improve success rate over time.

Author: Dum-E Fabrication System
Version: 1.0.0
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
import time

from .evaluator.fabrication_quality import QualityMetrics, DefectType

logger = logging.getLogger(__name__)


@dataclass
class PrintAttempt:
    """Record of a single print attempt."""
    attempt_number: int
    parameters: Dict
    quality_metrics: Optional[QualityMetrics]
    timestamp: float
    success: bool
    notes: str = ""

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "parameters": self.parameters,
            "quality_metrics": self.quality_metrics.to_dict() if self.quality_metrics else None,
            "timestamp": self.timestamp,
            "success": self.success,
            "notes": self.notes
        }


@dataclass
class OptimizationSession:
    """Complete optimization session with multiple attempts."""
    session_id: str
    initial_parameters: Dict
    attempts: List[PrintAttempt] = field(default_factory=list)
    final_success: bool = False
    iterations_used: int = 0
    total_time_seconds: float = 0.0

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "session_id": self.session_id,
            "initial_parameters": self.initial_parameters,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "final_success": self.final_success,
            "iterations_used": self.iterations_used,
            "total_time_seconds": self.total_time_seconds
        }


class AdaptiveOptimizer:
    """
    Adaptive print parameter optimizer with auto-retry.

    Strategy:
    - Analyze failure mode from quality metrics
    - Adjust parameters based on failure type
    - Retry up to max_iterations times
    - Learn from history (stored in Redis or JSON)
    """

    # Default print parameters (can be overridden)
    DEFAULT_PARAMS = {
        "layer_height_mm": 0.2,
        "wall_thickness_mm": 1.2,
        "infill_percentage": 20,
        "print_speed_mm_s": 50,
        "bed_temperature_c": 60,
        "nozzle_temperature_c": 210,
        "cooling_fan_percentage": 100
    }

    def __init__(
        self,
        max_iterations: int = 3,
        quality_threshold: float = 0.70,
        history_path: Optional[Path] = None
    ):
        """
        Initialize adaptive optimizer.

        Args:
            max_iterations: Maximum retry attempts
            quality_threshold: Minimum quality score to pass
            history_path: Path to save optimization history (JSON)
        """
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.history_path = history_path or Path("optimization_history.json")

        # Load history if available
        self.history: List[Dict] = []
        self._load_history()

        logger.info(f"AdaptiveOptimizer initialized (max_iterations: {max_iterations}, "
                   f"threshold: {quality_threshold})")

    def optimize_print(
        self,
        initial_parameters: Dict,
        print_function: callable,
        evaluate_function: callable
    ) -> OptimizationSession:
        """
        Optimize print parameters through iterative refinement.

        Args:
            initial_parameters: Starting print parameters
            print_function: Function(parameters) -> printed_stl_path
            evaluate_function: Function(design_stl, printed_stl) -> QualityMetrics

        Returns:
            OptimizationSession with all attempts
        """
        session_id = f"opt_{int(time.time())}"
        start_time = time.time()

        session = OptimizationSession(
            session_id=session_id,
            initial_parameters=initial_parameters.copy()
        )

        current_params = initial_parameters.copy()

        logger.info(f"Starting optimization session: {session_id}")

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[Iteration {iteration}/{self.max_iterations}] Attempting print...")

            # Print with current parameters
            try:
                printed_stl_path = print_function(current_params)
            except Exception as e:
                logger.error(f"Print function failed: {e}")
                attempt = PrintAttempt(
                    attempt_number=iteration,
                    parameters=current_params.copy(),
                    quality_metrics=None,
                    timestamp=time.time(),
                    success=False,
                    notes=f"Print failed: {e}"
                )
                session.attempts.append(attempt)
                continue

            # Evaluate quality
            try:
                quality_metrics = evaluate_function(printed_stl_path)
            except Exception as e:
                logger.error(f"Evaluation function failed: {e}")
                attempt = PrintAttempt(
                    attempt_number=iteration,
                    parameters=current_params.copy(),
                    quality_metrics=None,
                    timestamp=time.time(),
                    success=False,
                    notes=f"Evaluation failed: {e}"
                )
                session.attempts.append(attempt)
                continue

            # Record attempt
            success = quality_metrics.pass_fail
            attempt = PrintAttempt(
                attempt_number=iteration,
                parameters=current_params.copy(),
                quality_metrics=quality_metrics,
                timestamp=time.time(),
                success=success,
                notes=quality_metrics.notes
            )
            session.attempts.append(attempt)

            logger.info(f"Quality score: {quality_metrics.overall_score:.2f}, "
                       f"Pass: {success}")

            # Check if successful
            if success:
                session.final_success = True
                session.iterations_used = iteration
                session.total_time_seconds = time.time() - start_time
                logger.info(f"✓ Optimization successful after {iteration} iteration(s)")
                break

            # Adjust parameters for next iteration
            if iteration < self.max_iterations:
                logger.info("Adjusting parameters based on failure mode...")
                current_params = self._adjust_parameters(
                    current_params,
                    quality_metrics,
                    iteration
                )

        # Final result
        if not session.final_success:
            session.iterations_used = self.max_iterations
            session.total_time_seconds = time.time() - start_time
            logger.warning(f"✗ Optimization failed after {self.max_iterations} iterations")

        # Save to history
        self._save_to_history(session)

        return session

    def _adjust_parameters(
        self,
        current_params: Dict,
        quality_metrics: QualityMetrics,
        iteration: int
    ) -> Dict:
        """
        Adjust parameters based on failure mode.

        Args:
            current_params: Current parameters
            quality_metrics: Quality metrics from failed print
            iteration: Current iteration number

        Returns:
            Adjusted parameters
        """
        adjusted_params = current_params.copy()

        # Warping detected → increase bed adhesion
        if quality_metrics.warp_detected:
            logger.info("Addressing warping: increasing bed temp, reducing cooling")
            adjusted_params["bed_temperature_c"] = min(
                adjusted_params.get("bed_temperature_c", 60) + 5,
                80  # Max safe bed temp for PLA
            )
            adjusted_params["cooling_fan_percentage"] = max(
                adjusted_params.get("cooling_fan_percentage", 100) - 20,
                50  # Min cooling
            )

        # Dimensional errors → adjust wall thickness
        if quality_metrics.mean_distance_mm > 0.5:
            logger.info("Addressing dimensional errors: increasing wall thickness")
            adjusted_params["wall_thickness_mm"] = min(
                adjusted_params.get("wall_thickness_mm", 1.2) + 0.4,
                3.0  # Max wall thickness
            )

        # Check for specific defect types
        for defect in quality_metrics.defects:
            defect_type = defect.get("type", "")

            if defect_type == DefectType.UNDER_EXTRUSION.value:
                logger.info("Addressing under-extrusion: increasing nozzle temp, reducing speed")
                adjusted_params["nozzle_temperature_c"] = min(
                    adjusted_params.get("nozzle_temperature_c", 210) + 5,
                    230  # Max safe for PLA
                )
                adjusted_params["print_speed_mm_s"] = max(
                    adjusted_params.get("print_speed_mm_s", 50) - 10,
                    20  # Min reasonable speed
                )

            elif defect_type == DefectType.OVER_EXTRUSION.value:
                logger.info("Addressing over-extrusion: reducing nozzle temp")
                adjusted_params["nozzle_temperature_c"] = max(
                    adjusted_params.get("nozzle_temperature_c", 210) - 5,
                    190  # Min for PLA
                )

            elif defect_type == DefectType.LAYER_ADHESION.value:
                logger.info("Addressing layer adhesion: increasing nozzle temp, reducing speed")
                adjusted_params["nozzle_temperature_c"] = min(
                    adjusted_params.get("nozzle_temperature_c", 210) + 10,
                    230
                )
                adjusted_params["print_speed_mm_s"] = max(
                    adjusted_params.get("print_speed_mm_s", 50) - 15,
                    20
                )

        return adjusted_params

    def _save_to_history(self, session: OptimizationSession):
        """Save session to history."""
        self.history.append(session.to_dict())

        try:
            with open(self.history_path, 'w') as f:
                json.dump(self.history, f, indent=2)
            logger.info(f"Saved session to history: {self.history_path}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def _load_history(self):
        """Load history from file."""
        if self.history_path.exists():
            try:
                with open(self.history_path, 'r') as f:
                    self.history = json.load(f)
                logger.info(f"Loaded {len(self.history)} session(s) from history")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
                self.history = []
        else:
            logger.info("No history file found, starting fresh")

    def get_success_rate(self) -> float:
        """Calculate overall success rate from history."""
        if not self.history:
            return 0.0

        successful = sum(1 for session in self.history if session.get("final_success", False))
        return successful / len(self.history)

    def get_average_iterations(self) -> float:
        """Calculate average iterations needed for success."""
        successful_sessions = [
            session for session in self.history
            if session.get("final_success", False)
        ]

        if not successful_sessions:
            return 0.0

        total_iterations = sum(
            session.get("iterations_used", 0)
            for session in successful_sessions
        )

        return total_iterations / len(successful_sessions)

    def generate_report(self) -> str:
        """Generate optimization history report."""
        lines = []

        lines.append("=" * 70)
        lines.append("ADAPTIVE OPTIMIZATION HISTORY")
        lines.append("=" * 70)
        lines.append("")

        if not self.history:
            lines.append("No optimization sessions recorded yet.")
            lines.append("")
            lines.append("=" * 70)
            return "\n".join(lines)

        lines.append(f"Total Sessions: {len(self.history)}")
        lines.append(f"Success Rate: {self.get_success_rate()*100:.1f}%")
        lines.append(f"Average Iterations (successful): {self.get_average_iterations():.1f}")
        lines.append("")

        # Recent sessions
        lines.append("Recent Sessions:")
        lines.append("")

        for session in self.history[-5:]:  # Last 5 sessions
            lines.append(f"Session: {session['session_id']}")
            lines.append(f"  Result: {'SUCCESS' if session['final_success'] else 'FAILED'}")
            lines.append(f"  Iterations: {session['iterations_used']}")
            lines.append(f"  Time: {session['total_time_seconds']:.1f}s")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    print("Adaptive Print Optimizer")
    print("========================")
    print()
    print("This module automatically retries failed prints with adjusted parameters.")
    print()
    print("Example:")
    print("  optimizer = AdaptiveOptimizer(max_iterations=3)")
    print("  session = optimizer.optimize_print(params, print_func, evaluate_func)")
    print("  print(f'Success: {session.final_success}')")
