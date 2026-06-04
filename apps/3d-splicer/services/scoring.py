"""
Scoring and satisfaction calculation with no-regression guards.
"""

import logging
from typing import Dict, List, Any, Optional
from src.schemas.functional import EvaluationResult

logger = logging.getLogger(__name__)

class SatisfactionScorer:
    """Calculate satisfaction scores and enforce no-regression rules"""
    
    def __init__(self):
        # Default weights for different test domains
        self.default_weights = {
            "fit": 2.0,
            "io": 1.5, 
            "printability": 2.0,
            "drop_proxy": 1.0,
            "thermal": 0.5
        }
        
        # Tests that must pass (hard constraints)
        self.must_pass_tests = {
            "fit", "printability", "envelope_constraint", "board_clearance",
            "mesh_watertight", "mesh_manifold", "wall_thickness"
        }
    
    def calculate_satisfaction(self, 
                             results: List[EvaluationResult], 
                             weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate overall satisfaction score from evaluation results.
        
        Args:
            results: List of evaluation results
            weights: Optional custom weights for test domains
            
        Returns:
            Overall satisfaction score (0-1)
        """
        if not results:
            return 0.0
        
        weights = weights or self.default_weights
        
        # Group results by domain
        domain_scores = {}
        domain_counts = {}
        
        for result in results:
            domain = self._extract_domain(result.test_id)
            weight = weights.get(domain, 1.0)
            
            if domain not in domain_scores:
                domain_scores[domain] = 0.0
                domain_counts[domain] = 0
            
            domain_scores[domain] += result.score * weight
            domain_counts[domain] += weight
        
        # Calculate weighted average
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for domain, weighted_score in domain_scores.items():
            if domain_counts[domain] > 0:
                avg_score = weighted_score / domain_counts[domain]
                weight = weights.get(domain, 1.0)
                total_weighted_score += avg_score * weight
                total_weight += weight
        
        satisfaction = total_weighted_score / total_weight if total_weight > 0 else 0.0
        
        logger.debug(f"Satisfaction calculation: {satisfaction:.3f}")
        
        return satisfaction
    
    def check_no_regression(self, 
                          prev_results: List[EvaluationResult],
                          curr_results: List[EvaluationResult]) -> bool:
        """
        Check if current results show regression from previous results.
        
        Args:
            prev_results: Previous iteration results
            curr_results: Current iteration results
            
        Returns:
            True if no regression detected, False if regression found
        """
        if not prev_results or not curr_results:
            return True
        
        # Create result lookup by test_id
        prev_lookup = {r.test_id: r for r in prev_results}
        curr_lookup = {r.test_id: r for r in curr_results}
        
        # Check for regression in must-pass tests
        for test_id in self.must_pass_tests:
            if test_id in prev_lookup and test_id in curr_lookup:
                prev_result = prev_lookup[test_id]
                curr_result = curr_lookup[test_id]
                
                # If previous test passed, current should not fail
                if prev_result.passed and not curr_result.passed:
                    logger.warning(f"Regression detected: {test_id} passed before, now fails")
                    return False
                
                # If both passed, score should not decrease significantly
                if prev_result.passed and curr_result.passed:
                    score_diff = prev_result.score - curr_result.score
                    if score_diff > 0.1:  # Significant regression threshold
                        logger.warning(f"Regression detected: {test_id} score decreased by {score_diff:.3f}")
                        return False
        
        # Check for overall satisfaction regression
        prev_satisfaction = self.calculate_satisfaction(prev_results)
        curr_satisfaction = self.calculate_satisfaction(curr_results)
        
        satisfaction_diff = prev_satisfaction - curr_satisfaction
        if satisfaction_diff > 0.05:  # 5% regression threshold
            logger.warning(f"Satisfaction regression: {prev_satisfaction:.3f} → {curr_satisfaction:.3f} "
                          f"(Δ{satisfaction_diff:.3f})")
            return False
        
        return True
    
    def get_failed_tests(self, results: List[EvaluationResult]) -> List[str]:
        """Get list of failed test IDs"""
        return [r.test_id for r in results if not r.passed]
    
    def get_must_pass_failures(self, results: List[EvaluationResult]) -> List[str]:
        """Get list of must-pass test failures"""
        failures = []
        for result in results:
            if not result.passed and result.test_id in self.must_pass_tests:
                failures.append(result.test_id)
        return failures
    
    def get_domain_summary(self, results: List[EvaluationResult]) -> Dict[str, Dict[str, Any]]:
        """Get summary statistics by domain"""
        domains = {}
        
        for result in results:
            domain = self._extract_domain(result.test_id)
            
            if domain not in domains:
                domains[domain] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "avg_score": 0.0,
                    "tests": []
                }
            
            domains[domain]["total"] += 1
            if result.passed:
                domains[domain]["passed"] += 1
            else:
                domains[domain]["failed"] += 1
            
            domains[domain]["tests"].append({
                "test_id": result.test_id,
                "passed": result.passed,
                "score": result.score,
                "margin": result.margin,
                "details": result.details
            })
        
        # Calculate average scores
        for domain, stats in domains.items():
            if stats["tests"]:
                avg_score = sum(t["score"] for t in stats["tests"]) / len(stats["tests"])
                stats["avg_score"] = avg_score
        
        return domains
    
    def _extract_domain(self, test_id: str) -> str:
        """Extract domain from test ID"""
        # Map specific test IDs to domains
        domain_mapping = {
            "envelope_constraint": "fit",
            "board_clearance": "fit", 
            "keepout": "fit",
            "mount_accessibility": "fit",
            "io_alignment": "io",
            "io_clearance": "io",
            "mesh_watertight": "printability",
            "mesh_manifold": "printability", 
            "mesh_degenerate": "printability",
            "overhang_angles": "printability",
            "wall_thickness": "printability",
            "minimum_features": "printability",
            "drop_protection_energy": "drop_proxy",
            "drop_protection_strain": "drop_proxy",
            "thermal_air_gap": "thermal",
            "thermal_ventilation": "thermal",
            "toolless_access_time": "accessibility",
            "latch_accessibility": "accessibility"
        }
        
        # Check for exact match first
        if test_id in domain_mapping:
            return domain_mapping[test_id]
        
        # Check for partial matches
        for key, domain in domain_mapping.items():
            if key in test_id:
                return domain
        
        # Default to first part of test_id
        return test_id.split("_")[0]
