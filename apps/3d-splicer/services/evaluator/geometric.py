"""
Geometric fit and clearance evaluator.
"""

import numpy as np
from typing import List, Dict, Any
from .base import BaseEvaluator
from src.schemas.functional import FunctionalSpec, EvaluationResult

class GeometricEvaluator(BaseEvaluator):
    """Evaluates geometric fit, clearances, and envelope constraints"""
    
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate geometric constraints"""
        results = []
        mesh = self.load_mesh(stl_path)
        bounds = self.calculate_bounds(mesh)
        
        # Check overall envelope constraints
        results.extend(self._check_envelope_constraints(bounds, spec))
        
        # Check keepout violations
        if spec.context.keepouts:
            results.extend(self.check_overlap(mesh, spec.context.keepouts))
        
        # Check board clearance
        results.extend(self._check_board_clearance(bounds, spec))
        
        # Check mount point accessibility
        results.extend(self._check_mount_accessibility(bounds, spec))
        
        return results
    
    def _check_envelope_constraints(self, bounds: Dict[str, float], spec: FunctionalSpec) -> List[EvaluationResult]:
        """Check if mesh fits within envelope constraints"""
        results = []
        
        for constraint in spec.constraints:
            if constraint.rule == "overall_envelope_mm":
                if constraint.value:
                    # Parse envelope constraint (assume format like "[150,75,12]")
                    try:
                        envelope_str = constraint.value.strip("[]")
                        envelope_dims = [float(x.strip()) for x in envelope_str.split(",")]
                        
                        width_ok = bounds["width"] <= envelope_dims[0]
                        height_ok = bounds["height"] <= envelope_dims[1] 
                        depth_ok = bounds["depth"] <= envelope_dims[2]
                        
                        all_ok = width_ok and height_ok and depth_ok
                        
                        # Calculate margin
                        width_margin = (envelope_dims[0] - bounds["width"]) / envelope_dims[0]
                        height_margin = (envelope_dims[1] - bounds["height"]) / envelope_dims[1]
                        depth_margin = (envelope_dims[2] - bounds["depth"]) / envelope_dims[2]
                        overall_margin = min(width_margin, height_margin, depth_margin)
                        
                        results.append(EvaluationResult(
                            test_id="envelope_constraint",
                            passed=all_ok,
                            score=1.0 if all_ok else max(0.0, overall_margin),
                            margin=overall_margin,
                            details=f"Envelope: {bounds['width']:.1f}x{bounds['height']:.1f}x{bounds['depth']:.1f}mm "
                                   f"(limit: {envelope_dims[0]}x{envelope_dims[1]}x{envelope_dims[2]}mm)"
                        ))
                    except (ValueError, IndexError) as e:
                        results.append(EvaluationResult(
                            test_id="envelope_constraint",
                            passed=False,
                            score=0.0,
                            margin=None,
                            details=f"Invalid envelope constraint format: {e}"
                        ))
        
        return results
    
    def _check_board_clearance(self, bounds: Dict[str, float], spec: FunctionalSpec) -> List[EvaluationResult]:
        """Check clearance around board"""
        results = []
        
        board = spec.context.board_bbox_mm
        
        # Check if case provides adequate clearance around board
        clearance_x = (bounds["width"] - board.x) / 2
        clearance_y = (bounds["height"] - board.y) / 2
        
        min_clearance = min(clearance_x, clearance_y)
        target_clearance = 1.0  # Minimum 1mm clearance
        
        passed = min_clearance >= target_clearance
        margin = (min_clearance - target_clearance) / target_clearance if target_clearance > 0 else 0
        
        results.append(EvaluationResult(
            test_id="board_clearance",
            passed=passed,
            score=1.0 if passed else max(0.0, min_clearance / target_clearance),
            margin=margin,
            details=f"Board clearance: {min_clearance:.2f}mm (target: {target_clearance}mm)"
        ))
        
        return results
    
    def _check_mount_accessibility(self, bounds: Dict[str, float], spec: FunctionalSpec) -> List[EvaluationResult]:
        """Check if mount points are accessible"""
        results = []
        
        for i, mount in enumerate(spec.context.mounts):
            # Check if mount point is within case bounds
            mount_x, mount_y = mount.pos
            
            within_bounds = (bounds["x_min"] <= mount_x <= bounds["x_max"] and
                           bounds["y_min"] <= mount_y <= bounds["y_max"])
            
            # Check clearance around mount point
            clearance_radius = mount.dia / 2 + 1.0  # Mount radius + 1mm clearance
            
            # Simple check - ensure mount area is not at case edge
            edge_margin_x = min(mount_x - bounds["x_min"], bounds["x_max"] - mount_x)
            edge_margin_y = min(mount_y - bounds["y_min"], bounds["y_max"] - mount_y)
            min_edge_margin = min(edge_margin_x, edge_margin_y)
            
            accessible = within_bounds and min_edge_margin >= clearance_radius
            margin = (min_edge_margin - clearance_radius) / clearance_radius if clearance_radius > 0 else 0
            
            results.append(EvaluationResult(
                test_id=f"mount_accessibility_{i}",
                passed=accessible,
                score=1.0 if accessible else max(0.0, min_edge_margin / clearance_radius),
                margin=margin,
                details=f"Mount {i} accessibility: {min_edge_margin:.2f}mm clearance "
                       f"(required: {clearance_radius:.2f}mm)"
            ))
        
        return results
