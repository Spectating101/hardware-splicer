"""
Report generator for clean audit trails and iteration tracking.
"""

import time
from typing import List, Dict, Any
from pathlib import Path
from src.schemas.functional import FunctionalSpec, IterationResult, JobResult

class ReportGenerator:
    """Generate clean markdown reports for audit trails"""
    
    def generate_report(self, job_result: JobResult) -> str:
        """Generate comprehensive markdown report"""
        spec = job_result.spec
        iterations = job_result.iterations
        
        # Header
        report_lines = [
            f"# 3D Splicer Job Report: {job_result.job_id}",
            "",
            f"**Specification**: {spec.id}",
            f"**Status**: {'✅ PASSED' if job_result.success else '❌ FAILED'}",
            f"**Satisfaction**: {job_result.iterations[-1].overall_score:.1%}",
            f"**Iterations**: {len(iterations)}/{spec.iteration_budget.max_iters}",
            f"**Total Time**: {job_result.total_time_s:.1f}s",
            f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # Specification Summary
        report_lines.extend([
            "## Specification Summary",
            "",
            f"- **Board**: {spec.context.board_bbox_mm.x:.1f} × {spec.context.board_bbox_mm.y:.1f} × {spec.context.board_bbox_mm.z:.1f} mm",
            f"- **Mounts**: {len(spec.context.mounts)} standoffs",
            f"- **IO Connectors**: {len(spec.context.io)}",
            f"- **Keepouts**: {len(spec.context.keepouts)}",
            f"- **Material**: {spec.materials.primary} ({spec.materials.infill_pct}% infill)",
            f"- **Layer Height**: {spec.materials.layer_height_mm}mm",
            ""
        ])
        
        # Functional Requirements
        if spec.functional_requirements:
            report_lines.extend([
                "## Functional Requirements",
                ""
            ])
            for req in spec.functional_requirements:
                req_line = f"- **{req.goal}** ({req.id})"
                if req.absorb_energy_J:
                    req_line += f": {req.absorb_energy_J}J energy absorption"
                elif req.min_air_gap_mm:
                    req_line += f": {req.min_air_gap_mm}mm min air gap"
                elif req.max_open_time_s:
                    req_line += f": {req.max_open_time_s}s max open time"
                report_lines.append(req_line)
            report_lines.append("")
        
        # Constraints
        if spec.constraints:
            report_lines.extend([
                "## Constraints",
                ""
            ])
            for constraint in spec.constraints:
                constraint_line = f"- **{constraint.rule}**"
                if constraint.value:
                    constraint_line += f": {constraint.value}"
                report_lines.append(constraint_line)
            report_lines.append("")
        
        # Final Results Summary
        if iterations:
            final_iter = iterations[-1]
            report_lines.extend([
                "## Final Results",
                "",
                f"**Overall Satisfaction**: {final_iter.overall_score:.1%}",
                f"**All Tests Passed**: {'✅ Yes' if final_iter.all_passed else '❌ No'}",
                ""
            ])
            
            # Test results table
            report_lines.extend([
                "### Test Results",
                "",
                "| Test | Status | Score | Margin | Details |",
                "|------|--------|-------|--------|---------|"
            ])
            
            for result in final_iter.evaluation:
                status = "✅ PASS" if result.passed else "❌ FAIL"
                margin_str = f"{result.margin:.1%}" if result.margin is not None else "N/A"
                details = result.details[:50] + "..." if len(result.details) > 50 else result.details
                report_lines.append(
                    f"| {result.test_id} | {status} | {result.score:.2f} | {margin_str} | {details} |"
                )
            report_lines.append("")
        
        # Iteration History
        if iterations:
            report_lines.extend([
                "## Iteration History",
                "",
                "| Iter | Satisfaction | Passed | Time (s) | Key Changes |",
                "|------|-------------|--------|----------|-------------|"
            ])
            
            for i, iter_result in enumerate(iterations):
                passed_str = "✅" if iter_result.all_passed else "❌"
                # Simple change detection (could be enhanced)
                key_changes = "Initial" if i == 0 else "Parameter adjustment"
                report_lines.append(
                    f"| {iter_result.iteration} | {iter_result.overall_score:.1%} | {passed_str} | "
                    f"{iter_result.elapsed_time_s:.1f} | {key_changes} |"
                )
            report_lines.append("")
        
        # Parameter Evolution
        if iterations:
            report_lines.extend([
                "## Parameter Evolution",
                ""
            ])
            
            # Show key parameters across iterations
            key_params = ["shell.thickness_mm", "shell.outer_fillet_mm"]
            
            for param in key_params:
                report_lines.append(f"### {param}")
                values = []
                for iter_result in iterations:
                    param_dict = iter_result.parameters.model_dump()
                    # Navigate nested dict
                    value = param_dict
                    for key in param.split('.'):
                        value = value.get(key, 'N/A')
                    values.append(f"{value:.2f}" if isinstance(value, (int, float)) else str(value))
                
                report_lines.append(f"**Evolution**: {' → '.join(values)}")
                report_lines.append("")
        
        # Artifacts
        if job_result.artifacts:
            report_lines.extend([
                "## Generated Artifacts",
                ""
            ])
            for artifact_type, path in job_result.artifacts.items():
                report_lines.append(f"- **{artifact_type}**: `{path}`")
            report_lines.append("")
        
        # Performance Metrics
        report_lines.extend([
            "## Performance Metrics",
            "",
            f"- **Average Iteration Time**: {sum(i.elapsed_time_s for i in iterations) / len(iterations):.1f}s",
            f"- **Cache Hit Rate**: N/A (not tracked in v0.1)",
            f"- **Parameter Adjustment Count**: {len(iterations) - 1}",
            f"- **Final Satisfaction vs Target**: {final_iter.overall_score:.1%} (target: 80%+)",
            ""
        ])
        
        # Footer
        report_lines.extend([
            "---",
            f"*Generated by 3D Splicer v0.1 on {time.strftime('%Y-%m-%d %H:%M:%S')}*",
            f"*Job ID: {job_result.job_id}*"
        ])
        
        return "\n".join(report_lines)
    
    def save_report(self, job_result: JobResult, output_dir: Path) -> str:
        """Save report to file and return path"""
        report_content = self.generate_report(job_result)
        report_path = output_dir / f"{job_result.job_id}_report.md"
        
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        return str(report_path)
