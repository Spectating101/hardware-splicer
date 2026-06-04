"""
IO accessibility evaluator.
"""

import numpy as np
from typing import List, Dict, Any
from .base import BaseEvaluator
from src.schemas.functional import FunctionalSpec, EvaluationResult

class IOAccessibilityEvaluator(BaseEvaluator):
    """Evaluates IO connector accessibility and alignment"""
    
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate IO accessibility"""
        results = []
        
        # Check IO slot alignment
        results.extend(self._check_io_alignment(spec, params))
        
        # Check IO clearances
        results.extend(self._check_io_clearances(spec, params))
        
        return results
    
    def _check_io_alignment(self, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Check IO slot alignment with board connectors"""
        results = []
        
        io_slots = params.get("io_slots", [])
        
        for i, (board_io, slot) in enumerate(zip(spec.context.io, io_slots)):
            # Extract board IO position
            board_x, board_y = 0, 0  # Board center is origin
            if board_io.edge == "south":
                board_x = board_io.offset_mm - spec.context.board_bbox_mm.x / 2
                board_y = -spec.context.board_bbox_mm.y / 2
            elif board_io.edge == "north":
                board_x = board_io.offset_mm - spec.context.board_bbox_mm.x / 2
                board_y = spec.context.board_bbox_mm.y / 2
            elif board_io.edge == "east":
                board_x = spec.context.board_bbox_mm.x / 2
                board_y = board_io.offset_mm - spec.context.board_bbox_mm.y / 2
            elif board_io.edge == "west":
                board_x = -spec.context.board_bbox_mm.x / 2
                board_y = board_io.offset_mm - spec.context.board_bbox_mm.y / 2
            
            # Extract slot position (from template context)
            slot_x = slot.get("offset_mm", 0) - spec.context.board_bbox_mm.x / 2
            slot_y = 0  # Will be calculated based on edge
            
            # Calculate slot position based on edge
            shell_clearance = 1.0
            outer_x = spec.context.board_bbox_mm.x + 2 * (params.get("shell", {}).get("thickness_mm", 1.5) + shell_clearance)
            outer_y = spec.context.board_bbox_mm.y + 2 * (params.get("shell", {}).get("thickness_mm", 1.5) + shell_clearance)
            
            if board_io.edge == "south":
                slot_y = -outer_y / 2
            elif board_io.edge == "north":
                slot_y = outer_y / 2
            elif board_io.edge == "east":
                slot_x = outer_x / 2
                slot_y = slot.get("offset_mm", 0) - spec.context.board_bbox_mm.y / 2
            elif board_io.edge == "west":
                slot_x = -outer_x / 2
                slot_y = slot.get("offset_mm", 0) - spec.context.board_bbox_mm.y / 2
            
            # Check alignment tolerance
            alignment_tolerance = 1.0  # mm
            x_error = abs(slot_x - board_x)
            y_error = abs(slot_y - board_y)
            
            alignment_ok = x_error <= alignment_tolerance and y_error <= alignment_tolerance
            alignment_score = max(0.0, 1.0 - (x_error + y_error) / (2 * alignment_tolerance))
            
            results.append(EvaluationResult(
                test_id=f"io_alignment_{i}",
                passed=alignment_ok,
                score=alignment_score,
                margin=alignment_tolerance - (x_error + y_error) / 2,
                details=f"IO {i} alignment: x_error={x_error:.2f}mm, y_error={y_error:.2f}mm "
                       f"(tolerance: {alignment_tolerance}mm)"
            ))
        
        return results
    
    def _check_io_clearances(self, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Check IO slot clearances and dimensions"""
        results = []
        
        io_slots = params.get("io_slots", [])
        
        for i, (board_io, slot) in enumerate(zip(spec.context.io, io_slots)):
            # Get slot dimensions
            slot_size = slot.get("size", [12.0, 5.0])
            slot_w, slot_h = slot_size[0], slot_size[1]
            
            # Get required connector dimensions
            if board_io.slot:
                required_w, required_h = board_io.slot[0], board_io.slot[1]
            else:
                # Default connector sizes
                connector_defaults = {
                    "usb": [12.0, 5.0],
                    "hdmi": [14.0, 5.5],
                    "ethernet": [16.0, 13.5],
                    "power": [5.5, 2.1],
                    "audio": [3.5, 3.5],
                    "custom": [12.0, 5.0]
                }
                required_w, required_h = connector_defaults.get(board_io.type, [12.0, 5.0])
            
            # Add clearance tolerance
            clearance = 0.5  # mm
            required_w += clearance
            required_h += clearance
            
            # Check if slot is large enough
            width_ok = slot_w >= required_w
            height_ok = slot_h >= required_h
            
            width_margin = (slot_w - required_w) / required_w if required_w > 0 else 0
            height_margin = (slot_h - required_h) / required_h if required_h > 0 else 0
            overall_margin = min(width_margin, height_margin)
            
            passed = width_ok and height_ok
            score = 1.0 if passed else max(0.0, (slot_w * slot_h) / (required_w * required_h))
            
            results.append(EvaluationResult(
                test_id=f"io_clearance_{i}",
                passed=passed,
                score=score,
                margin=overall_margin,
                details=f"IO {i} clearance: slot={slot_w:.1f}x{slot_h:.1f}mm, "
                       f"required={required_w:.1f}x{required_h:.1f}mm, "
                       f"margin={overall_margin:.1%}"
            ))
        
        return results
