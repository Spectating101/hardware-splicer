"""
Deterministic heuristic planner for v0.1 - no LLM, just smart defaults and bounded adjustments.
"""

import logging
from typing import Dict, List, Any, Optional
from src.schemas.functional import FunctionalSpec, DesignParameters, IterationResult
from .param_clamp import ParamClampLayer

logger = logging.getLogger(__name__)

class HeuristicPlanner:
    """Deterministic parameter planner using heuristics and bounded adjustments"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.clamp_layer = ParamClampLayer()
        
    def propose_initial_parameters(self, spec: FunctionalSpec) -> DesignParameters:
        """
        Propose initial design parameters using deterministic heuristics.
        
        Args:
            spec: Functional specification
            
        Returns:
            Initial design parameters
        """
        logger.info(f"Proposing initial parameters for spec: {spec.id}")
        
        # Extract board dimensions
        board = spec.context.board_bbox_mm
        board_area = board.x * board.y
        board_perimeter = 2 * (board.x + board.y)
        
        # Initialize with conservative defaults
        initial_params = {
            "shell": {
                "thickness_mm": max(1.5, board_area / 800),  # Conservative thickness
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
                "count": max(4, int(board_perimeter / 40)),  # Scale with board size
                "tab_mm": [6.0, 1.4],
                "lip_mm": 0.6
            }
        }
        
        # Add mount points
        for mount in spec.context.mounts:
            boss = {
                "at": mount.pos,
                "dia_mm": mount.dia + 1.5,  # Conservative clearance
                "hole_mm": mount.dia,
                "height_mm": mount.height or 3.0
            }
            initial_params["bosses"].append(boss)
        
        # Add IO slots
        for io in spec.context.io:
            slot = {
                "edge": io.edge,
                "offset_mm": io.offset_mm,
                "size": io.slot or self._get_default_connector_size(io.type)
            }
            initial_params["io_slots"].append(slot)
        
        # Adjust parameters based on functional requirements
        for req in spec.functional_requirements:
            if req.goal == "drop_protection":
                # Increase shell thickness for drop protection
                energy_factor = min((req.absorb_energy_J or 2.0) / 2.0, 2.0)
                initial_params["shell"]["thickness_mm"] *= (1 + energy_factor * 0.2)
                
                # Add reinforcements for high energy requirements
                if req.absorb_energy_J and req.absorb_energy_J > 3.0:
                    initial_params["shell"]["outer_fillet_mm"] *= 1.2
                    
            elif req.goal == "thermal_clearance":
                # Increase ventilation for thermal management
                target_gap = req.min_air_gap_mm or 1.0
                initial_params["vents"]["cell_mm"] = min(initial_params["vents"]["cell_mm"], 
                                                       max(2.0, target_gap * 2))
                initial_params["vents"]["margin_mm"] = max(1.0, target_gap)
                
            elif req.goal == "toolless_access":
                # Ensure latches are accessible
                target_time = req.max_open_time_s or 5.0
                if target_time < 3.0:
                    # Quick access - more latches, larger tabs
                    initial_params["latches"]["count"] = max(6, initial_params["latches"]["count"])
                    initial_params["latches"]["tab_mm"][0] = max(7.0, initial_params["latches"]["tab_mm"][0])
        
        # Apply constraint-based adjustments
        for constraint in spec.constraints:
            if constraint.rule == "printability:overhang_angle_deg":
                if constraint.value and constraint.value < 50:
                    # Aggressive anti-overhang measures
                    initial_params["shell"]["outer_fillet_mm"] = max(2.0, 
                        initial_params["shell"]["outer_fillet_mm"])
                    
            elif constraint.rule == "printability:min_wall_thickness_mm":
                if constraint.value:
                    initial_params["shell"]["thickness_mm"] = max(
                        initial_params["shell"]["thickness_mm"], 
                        constraint.value
                    )
        
        # Clamp all parameters to valid ranges
        initial_params = self.clamp_layer._clamp_all_params(initial_params)
        
        logger.info(f"Initial parameters generated: shell_thickness={initial_params['shell']['thickness_mm']:.2f}mm")
        
        return DesignParameters(**initial_params)
    
    def revise_parameters(self, 
                         spec: FunctionalSpec,
                         history: List[IterationResult],
                         current_params: DesignParameters) -> DesignParameters:
        """
        Revise parameters based on evaluation results using deterministic rules.
        
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
        
        # Get failed tests from last iteration
        last_iteration = history[-1]
        failed_tests = [result.test_id for result in last_iteration.evaluation if not result.passed]
        
        logger.info(f"Failed tests: {failed_tests}")
        
        # Convert to dict for processing
        params_dict = current_params.model_dump()
        
        # Apply deterministic adjustments
        params_dict = self.clamp_layer.adjust_params(params_dict, failed_tests)
        
        # Additional heuristic adjustments based on failure patterns
        params_dict = self._apply_heuristic_adjustments(params_dict, failed_tests, history)
        
        # Ensure no regression in previously passed tests
        params_dict = self._ensure_no_regression(params_dict, history, spec)
        
        logger.info(f"Parameter revision complete")
        
        return DesignParameters(**params_dict)
    
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
            
        # Stop if no improvement in recent iterations
        if len(history) >= 3:
            recent_scores = [iter.overall_score for iter in history[-3:]]
            if max(recent_scores) - min(recent_scores) < 0.05:
                logger.warning("No significant improvement in recent iterations")
                return True
        
        # Stop if we're making things worse
        if len(history) >= 2:
            if current.overall_score < history[-2].overall_score:
                logger.warning("Score degrading, stopping optimization")
                return True
                
        return False
    
    def _get_default_connector_size(self, connector_type: str) -> List[float]:
        """Get default connector dimensions"""
        defaults = {
            "usb": [12.0, 5.0],
            "hdmi": [14.0, 5.5],
            "ethernet": [16.0, 13.5],
            "power": [5.5, 2.1],
            "audio": [3.5, 3.5],
            "custom": [12.0, 5.0]
        }
        return defaults.get(connector_type, [12.0, 5.0])
    
    def _apply_heuristic_adjustments(self, 
                                   params: Dict[str, Any], 
                                   failed_tests: List[str], 
                                   history: List[IterationResult]) -> Dict[str, Any]:
        """Apply additional heuristic adjustments based on failure patterns"""
        
        # Count consecutive failures for the same test
        failure_counts = {}
        for iter_result in history[-3:]:  # Look at last 3 iterations
            for result in iter_result.evaluation:
                if not result.passed:
                    failure_counts[result.test_id] = failure_counts.get(result.test_id, 0) + 1
        
        # Apply more aggressive adjustments for repeatedly failed tests
        for test_id, count in failure_counts.items():
            if count >= 2:  # Failed in multiple recent iterations
                if "drop_protection" in test_id:
                    params["shell"]["thickness_mm"] *= 1.1  # 10% increase
                elif "thermal" in test_id:
                    params["vents"]["cell_mm"] *= 0.9  # 10% decrease (more vents)
                elif "overhang" in test_id:
                    params["shell"]["outer_fillet_mm"] *= 1.15  # 15% increase
                elif "accessibility" in test_id:
                    params["latches"]["tab_mm"][0] *= 1.1  # 10% larger tabs
        
        return params
    
    def _ensure_no_regression(self, 
                            params: Dict[str, Any], 
                            history: List[IterationResult],
                            spec: FunctionalSpec) -> Dict[str, Any]:
        """Ensure we don't regress on previously passed tests"""
        
        if len(history) < 2:
            return params
        
        # Find tests that passed in previous iteration
        prev_iteration = history[-2]
        passed_tests = [result.test_id for result in prev_iteration.evaluation if result.passed]
        
        # For each passed test, ensure we don't make changes that would break it
        for test_id in passed_tests:
            if "drop_protection" in test_id and "shell" in params:
                # Don't reduce shell thickness below previous level
                prev_thickness = prev_iteration.parameters.shell.get("thickness_mm", 1.5)
                if params["shell"]["thickness_mm"] < prev_thickness * 0.95:
                    params["shell"]["thickness_mm"] = prev_thickness * 0.95
                    
            elif "thermal" in test_id and "vents" in params:
                # Don't reduce ventilation below previous level
                prev_cell_size = prev_iteration.parameters.vents.get("cell_mm", 4.0)
                if params["vents"]["cell_mm"] > prev_cell_size * 1.05:
                    params["vents"]["cell_mm"] = prev_cell_size * 1.05
        
        return params
