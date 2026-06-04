"""
Master evaluator that coordinates all evaluation domains.
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

from .base import BaseEvaluator
from .geometric import GeometricEvaluator
from .printability import PrintabilityEvaluator
from .functional import DropProtectionEvaluator, ThermalEvaluator, AccessibilityEvaluator
from .io_accessibility import IOAccessibilityEvaluator
from src.schemas.functional import FunctionalSpec, EvaluationResult

logger = logging.getLogger(__name__)

class MasterEvaluator:
    """Coordinates all evaluation domains"""
    
    def __init__(self):
        self.evaluators = {
            "geometric": GeometricEvaluator(),
            "printability": PrintabilityEvaluator(),
            "drop_protection": DropProtectionEvaluator(),
            "thermal": ThermalEvaluator(),
            "accessibility": AccessibilityEvaluator(),
            "io_accessibility": IOAccessibilityEvaluator()
        }
        
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """
        Run all evaluations on the STL file.
        
        Args:
            stl_path: Path to the STL file
            spec: Functional specification
            params: Design parameters used to generate the STL
            
        Returns:
            Combined list of all evaluation results
        """
        logger.info(f"Evaluating STL: {stl_path}")
        
        all_results = []
        
        # Always run geometric and printability evaluations
        all_results.extend(self.evaluators["geometric"].evaluate(stl_path, spec, params))
        all_results.extend(self.evaluators["printability"].evaluate(stl_path, spec, params))
        
        # Run functional evaluations based on requirements
        for req in spec.functional_requirements:
            if req.goal == "drop_protection":
                all_results.extend(self.evaluators["drop_protection"].evaluate(stl_path, spec, params))
            elif req.goal == "thermal_clearance":
                all_results.extend(self.evaluators["thermal"].evaluate(stl_path, spec, params))
            elif req.goal == "toolless_access":
                all_results.extend(self.evaluators["accessibility"].evaluate(stl_path, spec, params))
        
        # Always check IO accessibility if there are IO connectors
        if spec.context.io:
            all_results.extend(self.evaluators["io_accessibility"].evaluate(stl_path, spec, params))
        
        # Calculate overall score
        if all_results:
            overall_score = sum(result.score for result in all_results) / len(all_results)
            all_passed = all(result.passed for result in all_results)
            
            logger.info(f"Evaluation complete: {len(all_results)} tests, "
                       f"overall score: {overall_score:.3f}, all passed: {all_passed}")
        else:
            overall_score = 0.0
            all_passed = False
            logger.warning("No evaluation results generated")
        
        return all_results
    
    def get_summary(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Get evaluation summary statistics"""
        if not results:
            return {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "overall_score": 0.0,
                "all_passed": False,
                "by_domain": {}
            }
        
        total_tests = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total_tests - passed
        overall_score = sum(r.score for r in results) / total_tests
        all_passed = all(r.passed for r in results)
        
        # Group by domain
        by_domain = {}
        for result in results:
            domain = result.test_id.split("_")[0]
            if domain not in by_domain:
                by_domain[domain] = {"total": 0, "passed": 0, "failed": 0, "avg_score": 0.0}
            
            by_domain[domain]["total"] += 1
            if result.passed:
                by_domain[domain]["passed"] += 1
            else:
                by_domain[domain]["failed"] += 1
        
        # Calculate domain averages
        for domain in by_domain:
            domain_results = [r for r in results if r.test_id.startswith(domain)]
            if domain_results:
                by_domain[domain]["avg_score"] = sum(r.score for r in domain_results) / len(domain_results)
        
        return {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "overall_score": overall_score,
            "all_passed": all_passed,
            "by_domain": by_domain
        }
