"""
LLM-based parameter planner for functional 3D case generation.

The planner takes functional requirements and proposes design parameters
that the CAD builder can use to generate geometry.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from src.schemas.functional import FunctionalSpec, DesignParameters, IterationResult

logger = logging.getLogger(__name__)

class LLMPlanner:
    """LLM-based parameter planner"""
    
    def __init__(self, model_name: str = "gpt-4", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or "mock-key"  # For MVP, use mock responses
        
    def propose_initial_parameters(self, spec: FunctionalSpec) -> DesignParameters:
        """
        Propose initial design parameters based on functional specification.
        
        Args:
            spec: Functional specification with requirements and constraints
            
        Returns:
            Initial design parameters
        """
        logger.info(f"Proposing initial parameters for spec: {spec.id}")
        
        # Extract board dimensions
        board = spec.context.board_bbox_mm
        board_area = board.x * board.y
        
        # Initial parameter estimation based on heuristics
        initial_params = {
            "shell": {
                "thickness_mm": max(1.5, board_area / 1000),  # Heuristic based on board size
                "inner_fillet_mm": 1.0,
                "outer_fillet_mm": 1.5
            },
            "bosses": [],
            "vents": {
                "pattern": "grid",
                "cell_mm": 4.0,
                "margin_mm": 2.0,
                "region": "top"
            },
            "io_slots": [],
            "latches": {
                "type": "snap",
                "count": 4,
                "tab_mm": [6.0, 1.4],
                "lip_mm": 0.6
            }
        }
        
        # Add mount points
        for mount in spec.context.mounts:
            boss = {
                "at": mount.pos,
                "dia_mm": mount.dia + 2.0,  # Add clearance
                "hole_mm": mount.dia,
                "height_mm": mount.height or 3.0
            }
            initial_params["bosses"].append(boss)
        
        # Add IO slots
        for io in spec.context.io:
            slot = {
                "edge": io.edge,
                "offset_mm": io.offset_mm,
                "size": io.slot or [12.0, 5.0]  # Default USB-C size
            }
            initial_params["io_slots"].append(slot)
        
        # Adjust parameters based on functional requirements
        for req in spec.functional_requirements:
            if req.goal == "drop_protection" and req.absorb_energy_J:
                # Increase shell thickness for drop protection
                energy_factor = min(req.absorb_energy_J / 2.0, 3.0)
                initial_params["shell"]["thickness_mm"] *= (1 + energy_factor * 0.3)
                
            elif req.goal == "thermal_clearance" and req.min_air_gap_mm:
                # Increase ventilation for thermal management
                initial_params["vents"]["cell_mm"] = min(initial_params["vents"]["cell_mm"], 
                                                       max(2.0, req.min_air_gap_mm))
                
            elif req.goal == "toolless_access":
                # Ensure latches are accessible
                initial_params["latches"]["count"] = max(4, int(board_area / 1000))
        
        return DesignParameters(**initial_params)
    
    def revise_parameters(self, 
                         spec: FunctionalSpec,
                         history: List[IterationResult],
                         current_params: DesignParameters) -> DesignParameters:
        """
        Revise parameters based on evaluation results and failure patterns.
        
        Args:
            spec: Original functional specification
            history: Previous iteration results
            current_params: Current parameter set
            
        Returns:
            Revised parameters
        """
        if not history:
            return current_params
            
        logger.info(f"Revising parameters based on {len(history)} previous iterations")
        
        # Analyze failure patterns from history
        failed_tests = {}
        for iteration in history[-3:]:  # Look at last 3 iterations
            for result in iteration.evaluation:
                if not result.passed:
                    if result.test_id not in failed_tests:
                        failed_tests[result.test_id] = []
                    failed_tests[result.test_id].append(result)
        
        # Create revised parameters (deep copy current)
        revised = current_params.model_dump()
        
        # Apply revisions based on failure patterns
        for test_id, failures in failed_tests.items():
            avg_margin = sum(f.margin or 0 for f in failures) / len(failures)
            
            if test_id == "geometric_fit":
                # Increase clearances
                revised["shell"]["thickness_mm"] += 0.2
                
            elif test_id == "printability_overhang":
                # Reduce overhangs by adjusting geometry
                revised["shell"]["outer_fillet_mm"] = max(1.0, 
                    revised["shell"]["outer_fillet_mm"] - 0.3)
                
            elif test_id == "drop_protection":
                # Increase shell thickness and add reinforcements
                revised["shell"]["thickness_mm"] += 0.5
                if "reinforcements" not in revised["shell"]:
                    revised["shell"]["reinforcements"] = True
                    
            elif test_id == "thermal_clearance":
                # Increase ventilation
                revised["vents"]["cell_mm"] = max(2.0, 
                    revised["vents"]["cell_mm"] - 0.5)
                revised["vents"]["margin_mm"] = max(1.0,
                    revised["vents"]["margin_mm"] - 0.2)
                    
            elif test_id == "io_accessibility":
                # Increase IO slot clearances
                for slot in revised["io_slots"]:
                    slot["size"][0] += 0.5
                    slot["size"][1] += 0.3
        
        # Apply constraint-based adjustments
        for constraint in spec.constraints:
            if constraint.rule == "printability:overhang_angle_deg":
                if constraint.value and constraint.value < 55:
                    # Aggressive anti-overhang measures
                    revised["shell"]["outer_fillet_mm"] = max(2.0, 
                        revised["shell"]["outer_fillet_mm"])
                        
            elif constraint.rule == "printability:min_wall_thickness_mm":
                if constraint.value:
                    revised["shell"]["thickness_mm"] = max(
                        revised["shell"]["thickness_mm"], 
                        constraint.value
                    )
        
        # Apply monotonic improvements for repeated failures
        if len(history) > 2:
            recent_scores = [iter.overall_score for iter in history[-3:]]
            if all(recent_scores[i] >= recent_scores[i-1] for i in range(1, len(recent_scores))):
                # Scores are not improving, try more aggressive changes
                logger.warning("Scores not improving, applying aggressive parameter changes")
                revised["shell"]["thickness_mm"] *= 1.2
                revised["vents"]["cell_mm"] = max(1.5, revised["vents"]["cell_mm"] * 0.8)
        
        return DesignParameters(**revised)
    
    def should_stop(self, 
                   spec: FunctionalSpec,
                   history: List[IterationResult]) -> bool:
        """
        Determine if the optimization should stop.
        
        Args:
            spec: Functional specification
            history: Iteration history
            
        Returns:
            True if should stop, False otherwise
        """
        if not history:
            return False
            
        current = history[-1]
        
        # Stop if all tests pass
        if current.all_passed:
            logger.info("All tests passed, stopping optimization")
            return True
            
        # Stop if budget exceeded
        if len(history) >= spec.iteration_budget.max_iters:
            logger.warning("Maximum iterations reached")
            return True
            
        # Stop if timeout exceeded (would be checked by caller)
        
        # Stop if no improvement in last N iterations
        if len(history) >= 5:
            recent_scores = [iter.overall_score for iter in history[-5:]]
            if max(recent_scores) - min(recent_scores) < 0.05:
                logger.warning("No significant improvement in recent iterations")
                return True
                
        return False

# Mock LLM implementation for MVP
class MockLLMPlanner(LLMPlanner):
    """Mock LLM planner for MVP testing"""
    
    def __init__(self):
        super().__init__(model_name="mock", api_key="mock")
        
    def propose_initial_parameters(self, spec: FunctionalSpec) -> DesignParameters:
        """Mock initial parameter proposal"""
        return super().propose_initial_parameters(spec)
        
    def revise_parameters(self, 
                         spec: FunctionalSpec,
                         history: List[IterationResult],
                         current_params: DesignParameters) -> DesignParameters:
        """Mock parameter revision"""
        return super().revise_parameters(spec, history, current_params)
