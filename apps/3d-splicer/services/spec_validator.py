"""
Spec preflight validator - catch contradictions and issues early.
"""

import logging
from typing import List, Dict, Any, Tuple
from src.schemas.functional import FunctionalSpec

logger = logging.getLogger(__name__)

class SpecValidator:
    """Validates functional specifications before processing"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate(self, spec: FunctionalSpec) -> Tuple[bool, List[str], List[str]]:
        """
        Validate specification for contradictions and issues.
        
        Args:
            spec: Functional specification to validate
            
        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        logger.info(f"Validating spec: {spec.id}")
        
        # Core validation checks
        self._validate_board_dimensions(spec)
        self._validate_envelope_constraints(spec)
        self._validate_keepout_overlaps(spec)
        self._validate_mount_accessibility(spec)
        self._validate_io_clearances(spec)
        self._validate_goal_compatibility(spec)
        self._validate_numeric_ranges(spec)
        self._validate_iteration_budget(spec)
        
        # Enhanced contradiction checks
        self._validate_contradiction_matrix(spec)
        
        is_valid = len(self.errors) == 0
        
        logger.info(f"Validation complete: {len(self.errors)} errors, {len(self.warnings)} warnings")
        
        return is_valid, self.errors, self.warnings
    
    def _validate_board_dimensions(self, spec: FunctionalSpec):
        """Validate board dimensions are reasonable"""
        board = spec.context.board_bbox_mm
        
        # Check minimum dimensions
        if board.x < 10 or board.y < 10:
            self.errors.append(f"Board too small: {board.x}x{board.y}mm (minimum 10x10mm)")
        
        # Check maximum dimensions
        if board.x > 200 or board.y > 200:
            self.errors.append(f"Board too large: {board.x}x{board.y}mm (maximum 200x200mm)")
        
        # Check thickness
        if board.z < 0.5 or board.z > 10:
            self.errors.append(f"Board thickness unreasonable: {board.z}mm (range: 0.5-10mm)")
    
    def _validate_envelope_constraints(self, spec: FunctionalSpec):
        """Validate envelope constraints are achievable"""
        board = spec.context.board_bbox_mm
        
        # Find envelope constraint
        envelope_constraint = None
        for constraint in spec.constraints:
            if constraint.rule == "overall_envelope_mm" and constraint.value:
                try:
                    if isinstance(constraint.value, str):
                        # Parse "[150,75,12]" format
                        envelope_str = constraint.value.strip("[]")
                        envelope_dims = [float(x.strip()) for x in envelope_str.split(",")]
                    else:
                        envelope_dims = constraint.value
                    
                    envelope_constraint = envelope_dims
                    break
                except (ValueError, IndexError):
                    self.errors.append(f"Invalid envelope constraint format: {constraint.value}")
                    return
        
        if envelope_constraint:
            # Check if envelope can accommodate board + minimum shell
            min_shell = 1.0  # Minimum shell thickness
            min_clearance = 1.0  # Minimum clearance
            required_x = board.x + 2 * (min_shell + min_clearance)
            required_y = board.y + 2 * (min_shell + min_clearance)
            required_z = board.z + min_shell + 2.0  # Board + shell + clearance
            
            if (required_x > envelope_constraint[0] or 
                required_y > envelope_constraint[1] or 
                required_z > envelope_constraint[2]):
                self.errors.append(
                    f"Envelope too small: board needs {required_x}x{required_y}x{required_z}mm, "
                    f"envelope allows {envelope_constraint[0]}x{envelope_constraint[1]}x{envelope_constraint[2]}mm"
                )
    
    def _validate_keepout_overlaps(self, spec: FunctionalSpec):
        """Check for keepout overlaps with mounts and IO"""
        board = spec.context.board_bbox_mm
        
        # Check keepout vs mount overlaps
        for i, keepout in enumerate(spec.context.keepouts):
            keepout_x, keepout_y = keepout.at
            
            # Check against mounts
            for j, mount in enumerate(spec.context.mounts):
                mount_x, mount_y = mount.pos
                distance = ((keepout_x - mount_x)**2 + (keepout_y - mount_y)**2)**0.5
                
                # Minimum clearance between keepout and mount
                min_clearance = 2.0  # mm
                if distance < min_clearance:
                    self.errors.append(
                        f"Keepout {i} too close to mount {j}: {distance:.1f}mm "
                        f"(minimum {min_clearance}mm clearance)"
                    )
            
            # Check against IO connectors
            for k, io in enumerate(spec.context.io):
                # Estimate IO position based on edge and offset
                io_x, io_y = self._estimate_io_position(io, board)
                distance = ((keepout_x - io_x)**2 + (keepout_y - io_y)**2)**0.5
                
                if distance < 2.0:  # Minimum clearance
                    self.warnings.append(
                        f"Keepout {i} close to IO {k}: {distance:.1f}mm "
                        f"(may affect connector accessibility)"
                    )
    
    def _validate_mount_accessibility(self, spec: FunctionalSpec):
        """Validate mount points are accessible"""
        board = spec.context.board_bbox_mm
        
        for i, mount in enumerate(spec.context.mounts):
            mount_x, mount_y = mount.pos
            
            # Check if mount is within board bounds
            margin = 2.0  # Minimum margin from board edge
            if (mount_x < margin or mount_x > board.x - margin or
                mount_y < margin or mount_y > board.y - margin):
                self.errors.append(
                    f"Mount {i} too close to board edge: ({mount_x}, {mount_y}) "
                    f"(minimum {margin}mm margin from edge)"
                )
            
            # Check mount hole diameter is reasonable
            if mount.dia < 1.0 or mount.dia > 6.0:
                self.warnings.append(
                    f"Mount {i} hole diameter unusual: {mount.dia}mm "
                    f"(typical range: 1.0-6.0mm)"
                )
    
    def _validate_io_clearances(self, spec: FunctionalSpec):
        """Validate IO connector clearances"""
        board = spec.context.board_bbox_mm
        
        for i, io in enumerate(spec.context.io):
            # Check offset is within board bounds
            if io.edge in ["north", "south"]:
                if io.offset_mm < 0 or io.offset_mm > board.x:
                    self.errors.append(
                        f"IO {i} offset out of bounds: {io.offset_mm}mm "
                        f"(board width: {board.x}mm)"
                    )
            else:  # east, west
                if io.offset_mm < 0 or io.offset_mm > board.y:
                    self.errors.append(
                        f"IO {i} offset out of bounds: {io.offset_mm}mm "
                        f"(board height: {board.y}mm)"
                    )
            
            # Check slot dimensions are reasonable
            if io.slot:
                slot_w, slot_h = io.slot
                if slot_w < 2.0 or slot_w > 20.0 or slot_h < 1.0 or slot_h > 15.0:
                    self.warnings.append(
                        f"IO {i} slot dimensions unusual: {slot_w}x{slot_h}mm "
                        f"(typical: 2-20mm x 1-15mm)"
                    )
    
    def _validate_goal_compatibility(self, spec: FunctionalSpec):
        """Check for mutually exclusive goals"""
        goals = [req.goal for req in spec.functional_requirements]
        
        # Check for conflicting goals
        conflicting_pairs = [
            ("drop_protection", "thermal_clearance"),  # Thick walls vs ventilation
        ]
        
        for goal1, goal2 in conflicting_pairs:
            if goal1 in goals and goal2 in goals:
                self.warnings.append(
                    f"Potentially conflicting goals: {goal1} and {goal2} "
                    f"(may require careful parameter tuning)"
                )
        
        # Check for unrealistic combinations
        if len(goals) > 4:
            self.warnings.append(
                f"Many functional goals ({len(goals)}): may be difficult to satisfy all "
                f"simultaneously"
            )
    
    def _validate_numeric_ranges(self, spec: FunctionalSpec):
        """Validate numeric parameters are in reasonable ranges"""
        # Check materials parameters
        materials = spec.materials
        if materials.infill_pct < 0 or materials.infill_pct > 100:
            self.errors.append(f"Invalid infill percentage: {materials.infill_pct}%")
        
        if materials.layer_height_mm < 0.1 or materials.layer_height_mm > 0.5:
            self.errors.append(f"Invalid layer height: {materials.layer_height_mm}mm")
        
        # Check tolerances
        tolerances = spec.tolerances
        if tolerances.fit_mm < 0 or tolerances.fit_mm > 2.0:
            self.errors.append(f"Invalid fit tolerance: {tolerances.fit_mm}mm")
        
        if tolerances.hole_dia_mm < 0 or tolerances.hole_dia_mm > 1.0:
            self.errors.append(f"Invalid hole diameter tolerance: {tolerances.hole_dia_mm}mm")
        
        # Check functional requirements
        for req in spec.functional_requirements:
            if req.goal == "drop_protection":
                if req.absorb_energy_J and (req.absorb_energy_J < 0 or req.absorb_energy_J > 50):
                    self.errors.append(f"Invalid energy absorption: {req.absorb_energy_J}J")
                
                if req.max_strain_pct and (req.max_strain_pct < 0 or req.max_strain_pct > 100):
                    self.errors.append(f"Invalid max strain: {req.max_strain_pct}%")
            
            elif req.goal == "thermal_clearance":
                if req.min_air_gap_mm and (req.min_air_gap_mm < 0 or req.min_air_gap_mm > 10):
                    self.errors.append(f"Invalid air gap: {req.min_air_gap_mm}mm")
            
            elif req.goal == "toolless_access":
                if req.max_open_time_s and (req.max_open_time_s < 0 or req.max_open_time_s > 60):
                    self.errors.append(f"Invalid opening time: {req.max_open_time_s}s")
    
    def _validate_iteration_budget(self, spec: FunctionalSpec):
        """Validate iteration budget is reasonable"""
        budget = spec.iteration_budget
        
        if budget.max_iters < 1 or budget.max_iters > 10:
            self.errors.append(f"Invalid max iterations: {budget.max_iters} (range: 1-10)")
        
        if budget.max_seconds < 30 or budget.max_seconds > 600:
            self.errors.append(f"Invalid max time: {budget.max_seconds}s (range: 30-600s)")
    
    def _validate_contradiction_matrix(self, spec: FunctionalSpec):
        """Enhanced contradiction matrix validation"""
        board = spec.context.board_bbox_mm
        
        # Find envelope constraint
        envelope_constraint = None
        for constraint in spec.constraints:
            if constraint.rule == "overall_envelope_mm" and constraint.value:
                try:
                    if isinstance(constraint.value, str):
                        envelope_str = constraint.value.strip("[]")
                        envelope_dims = [float(x.strip()) for x in envelope_str.split(",")]
                    else:
                        envelope_dims = constraint.value
                    envelope_constraint = envelope_dims
                    break
                except (ValueError, IndexError):
                    self.errors.append(f"Invalid envelope constraint format: {constraint.value}")
                    return
        
        # Check tight envelope scenarios
        if envelope_constraint:
            min_shell = 1.5  # Minimum practical shell thickness
            min_clearance = 1.0  # Minimum clearance
            required_x = board.x + 2 * (min_shell + min_clearance)
            required_y = board.y + 2 * (min_shell + min_clearance)
            required_z = board.z + min_shell + 2.0
            
            # Check if envelope is barely sufficient (warning threshold)
            margin_x = envelope_constraint[0] - required_x
            margin_y = envelope_constraint[1] - required_y
            margin_z = envelope_constraint[2] - required_z
            
            if margin_x < 2.0 or margin_y < 2.0 or margin_z < 2.0:
                self.warnings.append(
                    f"Tight envelope margins: X={margin_x:.1f}mm, Y={margin_y:.1f}mm, Z={margin_z:.1f}mm. "
                    f"Consider larger envelope or smaller board."
                )
        
        # Check for negative air gaps
        for req in spec.functional_requirements:
            if req.goal == "thermal_clearance" and req.min_air_gap_mm is not None:
                if req.min_air_gap_mm <= 0:
                    self.errors.append(f"Negative air gap specified: {req.min_air_gap_mm}mm")
                elif req.min_air_gap_mm > 5.0:
                    self.warnings.append(f"Large air gap may be difficult to achieve: {req.min_air_gap_mm}mm")
        
        # Check for overlapping keepouts and IO
        for i, keepout in enumerate(spec.context.keepouts):
            keepout_x, keepout_y = keepout.at
            
            for j, io in enumerate(spec.context.io):
                io_x, io_y = self._estimate_io_position(io, board)
                distance = ((keepout_x - io_x)**2 + (keepout_y - io_y)**2)**0.5
                
                if distance < 3.0:  # Minimum clearance for IO access
                    self.errors.append(
                        f"Keepout {i} too close to IO {j}: {distance:.1f}mm "
                        f"(minimum 3.0mm for connector access)"
                    )
        
        # Check for conflicting functional requirements
        goals = [req.goal for req in spec.functional_requirements]
        
        # Drop protection vs thermal (thick walls vs ventilation)
        if "drop_protection" in goals and "thermal_clearance" in goals:
            self.warnings.append(
                "Conflicting goals: drop protection (thick walls) vs thermal clearance (ventilation). "
                "May require careful parameter tuning."
            )
        
        # Check for unrealistic combinations
        if len(goals) > 4:
            self.warnings.append(
                f"Many functional goals ({len(goals)}): may be difficult to satisfy all simultaneously. "
                "Consider prioritizing key requirements."
            )
        
        # Check material compatibility with requirements
        materials = spec.materials
        if materials.primary in ["PLA", "PETG"] and "drop_protection" in goals:
            # PLA/PETG may not be ideal for high-impact applications
            self.warnings.append(
                f"Material {materials.primary} may not be optimal for drop protection. "
                "Consider ABS or reinforced materials for high-impact applications."
            )
    
    def _estimate_io_position(self, io, board) -> Tuple[float, float]:
        """Estimate IO connector position on board"""
        if io.edge == "north":
            return io.offset_mm, board.y
        elif io.edge == "south":
            return io.offset_mm, 0
        elif io.edge == "east":
            return board.x, io.offset_mm
        else:  # west
            return 0, io.offset_mm
