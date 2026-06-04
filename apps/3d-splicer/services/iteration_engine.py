"""
Iterative optimization engine for functional 3D case generation.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from services.planner import LLMPlanner
from services.evaluator.master import MasterEvaluator
from src.core.cadquery_generator import script_to_stl
from src.core.template_loader import render_template
from src.schemas.functional import (
    FunctionalSpec, DesignParameters, IterationResult, 
    EvaluationResult, JobResult
)

logger = logging.getLogger(__name__)

class IterationEngine:
    """Main engine for iterative optimization"""
    
    def __init__(self, planner: Optional[LLMPlanner] = None, evaluator: Optional[MasterEvaluator] = None):
        self.planner = planner or LLMPlanner()
        self.evaluator = evaluator or MasterEvaluator()
        
    def optimize(self, spec: FunctionalSpec, output_dir: str = "jobs") -> JobResult:
        """
        Run iterative optimization to find optimal design parameters.
        
        Args:
            spec: Functional specification
            output_dir: Directory to store artifacts
            
        Returns:
            Job result with final design and evaluation
        """
        logger.info(f"Starting optimization for spec: {spec.id}")
        
        start_time = time.time()
        iterations = []
        
        # Create output directory
        job_dir = Path(output_dir) / spec.id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize parameters
        current_params = self.planner.propose_initial_parameters(spec)
        logger.info(f"Initial parameters: {current_params.model_dump()}")
        
        best_score = 0.0
        best_params = current_params
        best_iteration = None
        
        try:
            for iteration_num in range(spec.iteration_budget.max_iters):
                logger.info(f"Starting iteration {iteration_num + 1}/{spec.iteration_budget.max_iters}")
                
                iteration_start = time.time()
                
                # Generate STL from current parameters
                stl_path = self._generate_stl(spec, current_params, job_dir, iteration_num)
                
                # Evaluate the generated STL
                evaluation_results = self.evaluator.evaluate(stl_path, spec, current_params.model_dump())
                
                # Calculate overall score
                overall_score = sum(result.score for result in evaluation_results) / len(evaluation_results) if evaluation_results else 0.0
                all_passed = all(result.passed for result in evaluation_results)
                
                iteration_time = time.time() - iteration_start
                
                # Create iteration result
                iteration = IterationResult(
                    iteration=iteration_num + 1,
                    parameters=current_params,
                    evaluation=evaluation_results,
                    overall_score=overall_score,
                    all_passed=all_passed,
                    elapsed_time_s=iteration_time
                )
                
                iterations.append(iteration)
                
                logger.info(f"Iteration {iteration_num + 1} complete: "
                           f"score={overall_score:.3f}, passed={all_passed}, time={iteration_time:.1f}s")
                
                # Update best result
                if overall_score > best_score:
                    best_score = overall_score
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
                    current_params = self.planner.revise_parameters(spec, iterations, current_params)
                    logger.info(f"Revised parameters for next iteration: {current_params.model_dump()}")
                
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
        
        success = best_iteration is not None and best_iteration.all_passed
        
        return JobResult(
            job_id=spec.id,
            spec=spec,
            iterations=iterations,
            final_parameters=best_params if best_iteration else None,
            artifacts=artifacts,
            report=report,
            success=success,
            total_time_s=total_time
        )
    
    def _generate_stl(self, spec: FunctionalSpec, params: DesignParameters, job_dir: Path, iteration: int) -> str:
        """Generate STL from parameters using template system"""
        stl_filename = f"{spec.id}_iter_{iteration + 1}.stl"
        stl_path = job_dir / stl_filename
        
        # Convert parameters to template context
        context = self._params_to_template_context(spec, params)
        
        # Render template
        template_code = render_template("functional_case.cq.j2", context)
        
        # Generate STL
        script_to_stl(template_code, stl_path)
        
        logger.info(f"Generated STL: {stl_path}")
        return str(stl_path)
    
    def _params_to_template_context(self, spec: FunctionalSpec, params: DesignParameters) -> Dict[str, Any]:
        """Convert design parameters to template context"""
        context = {
            "spec": spec.model_dump(),
            "params": params.model_dump(),
            "board": spec.context.board_bbox_mm.model_dump(),
            "mounts": [mount.model_dump() for mount in spec.context.mounts],
            "io": [conn.model_dump() for conn in spec.context.io],
            "keepouts": [keepout.model_dump() for keepout in spec.context.keepouts]
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
        
        # Generate GLB preview (placeholder - would need GLB export)
        if spec.outputs.glb_preview:
            glb_path = job_dir / f"{spec.id}_preview.glb"
            # TODO: Implement GLB export
            artifacts["glb"] = str(glb_path)
        
        # Save parameters
        params_path = job_dir / f"{spec.id}_params.json"
        with open(params_path, 'w') as f:
            f.write(params.model_dump_json(indent=2))
        artifacts["parameters"] = str(params_path)
        
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
