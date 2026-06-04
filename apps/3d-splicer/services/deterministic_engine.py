"""
Deterministic iteration engine for v0.1 - bounded retries with caching and idempotency.
"""

import time
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from .heuristic_planner import HeuristicPlanner
from .evaluator.master import MasterEvaluator
from .scoring import SatisfactionScorer
from .spec_validator import SpecValidator
from src.core.cadquery_generator import script_to_stl
from src.core.template_loader import render_template
from src.schemas.functional import (
    FunctionalSpec, DesignParameters, IterationResult, 
    EvaluationResult, JobResult
)

logger = logging.getLogger(__name__)

class DeterministicEngine:
    """Deterministic iteration engine with caching and idempotency"""
    
    def __init__(self, planner: Optional[HeuristicPlanner] = None, evaluator: Optional[MasterEvaluator] = None):
        self.planner = planner or HeuristicPlanner(seed=42)
        self.evaluator = evaluator or MasterEvaluator()
        self.scorer = SatisfactionScorer()
        self.validator = SpecValidator()
        self.evaluation_cache = {}  # Cache for evaluation results
        
    def optimize(self, spec: FunctionalSpec, output_dir: str = "jobs") -> JobResult:
        """
        Run deterministic optimization with bounded retries.
        
        Args:
            spec: Functional specification
            output_dir: Directory to store artifacts
            
        Returns:
            Job result with final design and evaluation
        """
        logger.info(f"Starting deterministic optimization for spec: {spec.id}")
        
        # Validate specification first
        is_valid, errors, warnings = self.validator.validate(spec)
        if not is_valid:
            logger.error(f"Spec validation failed: {errors}")
            raise ValueError(f"Spec validation failed: {errors}")
        
        if warnings:
            logger.warning(f"Spec validation warnings: {warnings}")
        
        # Generate deterministic job ID from spec hash
        job_id = self._generate_job_id(spec)
        logger.info(f"Job ID: {job_id}")
        
        # Check for existing results (idempotency)
        existing_result = self._check_existing_result(job_id, output_dir)
        if existing_result:
            logger.info(f"Found existing result for job {job_id}")
            return existing_result
        
        start_time = time.time()
        iterations = []
        
        # Create output directory
        job_dir = Path(output_dir) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize parameters
        current_params = self.planner.propose_initial_parameters(spec)
        logger.info(f"Initial parameters: shell_thickness={current_params.shell.get('thickness_mm', 0):.2f}mm")
        
        best_score = 0.0
        best_params = current_params
        best_iteration = None
        
        try:
            for iteration_num in range(spec.iteration_budget.max_iters):
                logger.info(f"Starting iteration {iteration_num + 1}/{spec.iteration_budget.max_iters}")
                
                iteration_start = time.time()
                
                # Generate STL from current parameters
                stl_path = self._generate_stl(spec, current_params, job_dir, iteration_num)
                
                # Evaluate the generated STL (with caching)
                evaluation_results = self._evaluate_with_cache(stl_path, spec, current_params.model_dump())
                
                # Calculate satisfaction score and check for must-pass failures
                satisfaction_score = self.scorer.calculate_satisfaction(evaluation_results)
                all_passed = all(result.passed for result in evaluation_results)
                must_pass_failures = self.scorer.get_must_pass_failures(evaluation_results)
                
                iteration_time = time.time() - iteration_start
                
                # Create iteration result
                iteration = IterationResult(
                    iteration=iteration_num + 1,
                    parameters=current_params,
                    evaluation=evaluation_results,
                    overall_score=satisfaction_score,
                    all_passed=all_passed,
                    elapsed_time_s=iteration_time
                )
                
                iterations.append(iteration)
                
                logger.info(f"Iteration {iteration_num + 1} complete: "
                           f"satisfaction={satisfaction_score:.3f}, passed={all_passed}, "
                           f"must_pass_failures={len(must_pass_failures)}, time={iteration_time:.1f}s")
                
                # Update best result
                if satisfaction_score > best_score:
                    best_score = satisfaction_score
                    best_params = current_params
                    best_iteration = iteration
                
                # Check stopping conditions
                if self.planner.should_stop(spec, iterations):
                    logger.info("Stopping optimization - conditions met")
                    break
                
                # Check timeout
                elapsed_total = time.time() - start_time
                if elapsed_total >= spec.iteration_budget.max_seconds:
                    logger.warning("Stopping optimization - timeout reached")
                    break
                
                # Prepare for next iteration (if not stopping)
                if not all_passed and iteration_num < spec.iteration_budget.max_iters - 1:
                    # Check for regression before revising parameters
                    if len(iterations) > 1:
                        prev_results = iterations[-2].evaluation
                        no_regression = self.scorer.check_no_regression(prev_results, evaluation_results)
                        
                        if not no_regression:
                            logger.warning("Regression detected, applying conservative parameter revision")
                            # Apply more conservative adjustments for regression
                            current_params = self._apply_conservative_revision(spec, iterations, current_params)
                        else:
                            current_params = self.planner.revise_parameters(spec, iterations, current_params)
                    else:
                        current_params = self.planner.revise_parameters(spec, iterations, current_params)
                    
                    logger.info(f"Revised parameters for next iteration")
                
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            raise
        
        total_time = time.time() - start_time
        
        # Generate final artifacts if we have a best result
        artifacts = {}
        if best_iteration:
            artifacts = self._generate_final_artifacts(spec, best_params, job_dir, best_iteration)
        
        # Generate report
        report = self._generate_report(spec, iterations, best_iteration)
        
        # Save report to file
        if spec.outputs.report != "none":
            report_path = job_dir / f"report.{spec.outputs.report}"
            with open(report_path, 'w') as f:
                f.write(report)
            artifacts["report"] = str(report_path)
        
        # Save complete result for idempotency
        result = JobResult(
            job_id=job_id,
            spec=spec,
            iterations=iterations,
            final_parameters=best_params if best_iteration else None,
            artifacts=artifacts,
            report=report,
            success=best_iteration is not None and best_iteration.all_passed,
            total_time_s=total_time
        )
        
        self._save_result(result, job_dir)
        
        return result
    
    def _apply_conservative_revision(self, spec: FunctionalSpec, iterations: List[IterationResult], current_params: DesignParameters) -> DesignParameters:
        """Apply conservative parameter revision when regression is detected"""
        # Get failed tests from last iteration
        last_iteration = iterations[-1]
        failed_tests = self.scorer.get_failed_tests(last_iteration.evaluation)
        
        # Apply smaller, more conservative adjustments
        params_dict = current_params.model_dump()
        
        # Conservative adjustments (half the normal step size)
        conservative_adjustments = {
            "drop_protection_energy": {"shell.thickness_mm": +0.1},
            "drop_protection_strain": {"shell.thickness_mm": +0.1},
            "overhang_angles": {"shell.outer_fillet_mm": +0.1},
            "wall_thickness": {"shell.thickness_mm": +0.1},
            "thermal_air_gap": {"vents.cell_mm": -0.2},
            "thermal_ventilation": {"vents.cell_mm": -0.1},
        }
        
        for test_id in failed_tests:
            if test_id in conservative_adjustments:
                adjustments = conservative_adjustments[test_id]
                for param_path, adjustment in adjustments.items():
                    params_dict = self.planner.clamp_layer._apply_adjustment(params_dict, param_path, adjustment)
        
        # Clamp all parameters
        params_dict = self.planner.clamp_layer._clamp_all_params(params_dict)
        
        return DesignParameters(**params_dict)
    
    def _generate_job_id(self, spec: FunctionalSpec) -> str:
        """Generate deterministic job ID from spec hash"""
        spec_dict = spec.model_dump()
        spec_str = json.dumps(spec_dict, sort_keys=True)
        spec_hash = hashlib.sha256(spec_str.encode()).hexdigest()[:16]
        return f"{spec.id}_{spec_hash}"
    
    def _check_existing_result(self, job_id: str, output_dir: str) -> Optional[JobResult]:
        """Check for existing result to enable idempotency"""
        job_dir = Path(output_dir) / job_id
        result_file = job_dir / "result.json"
        
        if result_file.exists():
            try:
                with open(result_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loading existing result from {result_file}")
                return JobResult(**data)
            except Exception as e:
                logger.warning(f"Failed to load existing result: {e}")
        
        return None
    
    def _save_result(self, result: JobResult, job_dir: Path):
        """Save result for idempotency"""
        result_file = job_dir / "result.json"
        try:
            with open(result_file, 'w') as f:
                json.dump(result.model_dump(), f, indent=2, default=str)
            logger.info(f"Saved result to {result_file}")
        except Exception as e:
            logger.warning(f"Failed to save result: {e}")
    
    def _evaluate_with_cache(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate with caching for performance"""
        # Generate cache key
        params_str = json.dumps(params, sort_keys=True)
        spec_dict = spec.model_dump()
        spec_str = json.dumps(spec_dict, sort_keys=True)
        cache_key = hashlib.md5((params_str + spec_str).encode()).hexdigest()
        
        # Check cache
        if cache_key in self.evaluation_cache:
            logger.debug(f"Using cached evaluation for {cache_key}")
            return self.evaluation_cache[cache_key]
        
        # Run evaluation
        results = self.evaluator.evaluate(stl_path, spec, params)
        
        # Cache results
        self.evaluation_cache[cache_key] = results
        
        return results
    
    def _generate_stl(self, spec: FunctionalSpec, params: DesignParameters, job_dir: Path, iteration: int) -> str:
        """Generate STL from parameters using template system"""
        stl_filename = f"{spec.id}_iter_{iteration + 1}.stl"
        stl_path = job_dir / stl_filename
        
        # Convert parameters to template context
        context = self._params_to_template_context(spec, params)
        
        # Render template
        template_code = render_template("functional_case_simple.cq.j2", context)
        
        # Generate STL
        script_to_stl(template_code, stl_path)
        
        logger.info(f"Generated STL: {stl_path}")
        return str(stl_path)
    
    def _params_to_template_context(self, spec: FunctionalSpec, params: DesignParameters) -> Dict[str, Any]:
        """Convert design parameters to template context"""
        params_dict = params.model_dump()
        context = {
            "spec": spec.model_dump(),
            "params": params_dict,
            "board": spec.context.board_bbox_mm.model_dump(),
            "mounts": [mount.model_dump() for mount in spec.context.mounts],
            "io": [conn.model_dump() for conn in spec.context.io],
            "keepouts": [keepout.model_dump() for keepout in spec.context.keepouts],
            # Add individual parameter sections for template access
            "shell": params_dict.get("shell", {}),
            "bosses": params_dict.get("bosses", []),
            "vents": params_dict.get("vents", {}),
            "io_slots": params_dict.get("io_slots", []),
            "latches": params_dict.get("latches", {})
        }
        return context
    
    def _generate_final_artifacts(self, spec: FunctionalSpec, params: DesignParameters, job_dir: Path, best_iteration: IterationResult) -> Dict[str, str]:
        """Generate final artifacts for the best design"""
        artifacts = {}
        
        # Generate final STL
        if spec.outputs.stl:
            final_stl = job_dir / f"{spec.id}_final.stl"
            stl_path = self._generate_stl(spec, params, job_dir, -1)  # Use -1 to indicate final
            Path(stl_path).rename(final_stl)
            artifacts["stl"] = str(final_stl)
        
        # Save parameters
        params_path = job_dir / f"{spec.id}_params.json"
        with open(params_path, 'w') as f:
            json.dump(params.model_dump(), f, indent=2, default=str)
        artifacts["parameters"] = str(params_path)
        
        # Save iteration history
        iterations_path = job_dir / f"{spec.id}_iterations.json"
        with open(iterations_path, 'w') as f:
            json.dump([iter.model_dump() for iter in best_iteration.evaluation], f, indent=2, default=str)
        artifacts["iterations"] = str(iterations_path)
        
        return artifacts
    
    def _generate_report(self, spec: FunctionalSpec, iterations: List[IterationResult], best_iteration: Optional[IterationResult]) -> str:
        """Generate markdown report of optimization results"""
        report_lines = [
            f"# Optimization Report: {spec.id}",
            "",
            f"**Specification ID**: {spec.id}",
            f"**Total Iterations**: {len(iterations)}",
            f"**Total Time**: {sum(iter.elapsed_time_s for iter in iterations):.1f}s",
            f"**Success**: {'Yes' if best_iteration and best_iteration.all_passed else 'No'}",
            "",
            "## Functional Requirements",
            ""
        ]
        
        for req in spec.functional_requirements:
            report_lines.append(f"- **{req.goal}**: {req.id}")
        
        if best_iteration:
            report_lines.extend([
                "",
                "## Final Results",
                "",
                f"**Overall Score**: {best_iteration.overall_score:.3f}",
                f"**All Tests Passed**: {best_iteration.all_passed}",
                "",
                "### Test Results",
                ""
            ])
            
            for result in best_iteration.evaluation:
                status = "✅ PASS" if result.passed else "❌ FAIL"
                report_lines.append(f"- **{result.test_id}**: {status} (score: {result.score:.3f})")
                if result.details:
                    report_lines.append(f"  - {result.details}")
        
        report_lines.extend([
            "",
            "## Iteration History",
            "",
            "| Iteration | Score | Passed | Time (s) | Key Changes |",
            "|-----------|-------|--------|----------|-------------|"
        ])
        
        for iter_result in iterations:
            passed_str = "✅" if iter_result.all_passed else "❌"
            report_lines.append(
                f"| {iter_result.iteration} | {iter_result.overall_score:.3f} | {passed_str} | "
                f"{iter_result.elapsed_time_s:.1f} | - |"
            )
        
        return "\n".join(report_lines)
