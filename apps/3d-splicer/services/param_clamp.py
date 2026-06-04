"""
Parameter clamping layer for deterministic, bounded adjustments.
"""

import logging
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParamRange:
    """Parameter range with step size and monotonic adjustment rules"""
    min_val: float
    max_val: float
    step_size: float = 0.1
    monotonic_inc: bool = True  # True for increase, False for decrease
    
class ParamClampLayer:
    """Deterministic parameter adjustment with bounds and monotonic rules"""
    
    def __init__(self):
        # Define parameter ranges and adjustment rules
        self.ranges = {
            "shell.thickness_mm": ParamRange(1.0, 4.0, 0.2, True),
            "shell.inner_fillet_mm": ParamRange(0.5, 3.0, 0.1, True),
            "shell.outer_fillet_mm": ParamRange(0.5, 3.0, 0.1, True),
            "vents.cell_mm": ParamRange(2.0, 6.0, 0.5, False),  # Smaller = more vents
            "vents.margin_mm": ParamRange(1.0, 4.0, 0.2, True),
            "latches.count": ParamRange(2, 8, 1, True),
            "latches.tab_mm.0": ParamRange(4.0, 10.0, 0.5, True),  # Width
            "latches.tab_mm.1": ParamRange(1.0, 3.0, 0.1, True),  # Height
            "latches.lip_mm": ParamRange(0.3, 1.5, 0.1, True),
        }
        
        # Test-specific adjustment rules (v0.1 guardrail table)
        self.adjustment_rules = {
            # Drop protection failures
            "drop_protection_energy": {
                "shell.thickness_mm": +0.2,  # Increase thickness
            },
            "drop_protection_strain": {
                "shell.thickness_mm": +0.2,
            },
            
            # Printability failures  
            "overhang_angles": {
                "shell.outer_fillet_mm": +0.3,  # Larger fillets reduce overhangs
            },
            "wall_thickness": {
                "shell.thickness_mm": +0.2,  # Ensure minimum wall thickness
            },
            
            # Thermal failures
            "thermal_air_gap": {
                "vents.cell_mm": -0.5,  # Smaller cells = more ventilation
                "vents.margin_mm": +0.2,
            },
            "thermal_ventilation": {
                "vents.cell_mm": -0.3,
                "vents.margin_mm": -0.1,
            },
            
            # IO accessibility failures
            "io_alignment": {
                "io_slots.offset_adjust": +0.2,  # Adjust slot position
            },
            "io_clearance": {
                "io_slots.size_adjust": +0.5,  # Increase slot size
            },
            
            # Accessibility failures
            "toolless_access_time": {
                "latches.count": +1,
                "latches.tab_mm.0": +0.5,  # Larger tabs easier to grip
            },
            "latch_accessibility": {
                "latches.tab_mm.0": +0.3,
                "latches.tab_mm.1": +0.1,
            },
            
            # Geometric failures
            "envelope_constraint": {
                "shell.thickness_mm": -0.2,
                "shell.outer_fillet_mm": -0.1,
            },
            "board_clearance": {
                "shell.thickness_mm": +0.2,
            },
            "keepout": {
                "shell.thickness_mm": -0.1,  # Reduce interference
            }
        }
    
    def adjust_params(self, 
                     current_params: Dict[str, Any], 
                     failed_tests: List[str]) -> Dict[str, Any]:
        """
        Adjust parameters based on failed tests using deterministic rules.
        
        Args:
            current_params: Current parameter set
            failed_tests: List of failed test IDs
            
        Returns:
            Adjusted parameter set
        """
        logger.info(f"Adjusting parameters for failed tests: {failed_tests}")
        
        # Deep copy current parameters
        new_params = self._deep_copy_params(current_params)
        
        # Apply adjustments for each failed test
        for test_id in failed_tests:
            if test_id in self.adjustment_rules:
                adjustments = self.adjustment_rules[test_id]
                for param_path, adjustment in adjustments.items():
                    new_params = self._apply_adjustment(new_params, param_path, adjustment)
        
        # Ensure all parameters are within bounds
        new_params = self._clamp_all_params(new_params)
        
        logger.info(f"Parameter adjustment complete")
        return new_params
    
    def _deep_copy_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy parameter dictionary"""
        import copy
        return copy.deepcopy(params)
    
    def _apply_adjustment(self, params: Dict[str, Any], param_path: str, adjustment: float) -> Dict[str, Any]:
        """Apply a single parameter adjustment"""
        try:
            # Navigate to the parameter using dot notation
            parts = param_path.split('.')
            current = params
            
            # Navigate to parent of target parameter
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Apply adjustment to target parameter
            target_param = parts[-1]
            if target_param not in current:
                # Initialize with default value
                current[target_param] = 1.5 if "thickness" in param_path else 1.0
            
            old_value = current[target_param]
            new_value = old_value + adjustment
            
            logger.debug(f"Adjusting {param_path}: {old_value} → {new_value} (Δ{adjustment})")
            current[target_param] = new_value
            
        except Exception as e:
            logger.warning(f"Failed to adjust parameter {param_path}: {e}")
        
        return params
    
    def _clamp_all_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clamp all parameters to valid ranges"""
        return self._clamp_params_recursive(params, "")
    
    def _clamp_params_recursive(self, params: Dict[str, Any], prefix: str) -> Dict[str, Any]:
        """Recursively clamp parameters"""
        for key, value in params.items():
            param_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recurse into nested dictionaries
                params[key] = self._clamp_params_recursive(value, param_path)
            elif isinstance(value, (int, float)):
                # Clamp numeric values
                if param_path in self.ranges:
                    range_def = self.ranges[param_path]
                    clamped_value = max(range_def.min_val, 
                                      min(range_def.max_val, value))
                    if clamped_value != value:
                        logger.debug(f"Clamped {param_path}: {value} → {clamped_value}")
                    params[key] = clamped_value
        
        return params
    
    def get_param_bounds(self, param_path: str) -> tuple:
        """Get min/max bounds for a parameter"""
        if param_path in self.ranges:
            range_def = self.ranges[param_path]
            return range_def.min_val, range_def.max_val
        return None, None
    
    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Validate parameters against bounds and return violations"""
        violations = []
        
        def check_recursive(data, prefix=""):
            for key, value in data.items():
                param_path = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    check_recursive(value, param_path)
                elif isinstance(value, (int, float)):
                    if param_path in self.ranges:
                        range_def = self.ranges[param_path]
                        if value < range_def.min_val or value > range_def.max_val:
                            violations.append(f"{param_path}: {value} not in [{range_def.min_val}, {range_def.max_val}]")
        
        check_recursive(params)
        return violations
