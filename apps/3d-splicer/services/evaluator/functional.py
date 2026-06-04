"""
Functional requirement evaluators (drop protection, thermal, accessibility, etc.)
"""

import numpy as np
import trimesh
from typing import List, Dict, Any
from .base import BaseEvaluator
from src.schemas.functional import FunctionalSpec, EvaluationResult

class DropProtectionEvaluator(BaseEvaluator):
    """Evaluates drop protection capabilities"""
    
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate drop protection requirements"""
        results = []
        mesh = self.load_mesh(stl_path)
        
        # Find drop protection requirements
        drop_reqs = [req for req in spec.functional_requirements if req.goal == "drop_protection"]
        
        for req in drop_reqs:
            results.extend(self._evaluate_drop_protection(mesh, req, params))
        
        return results
    
    def _evaluate_drop_protection(self, mesh: trimesh.Trimesh, req: Any, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate specific drop protection requirement"""
        results = []
        
        # Extract shell thickness from parameters
        shell_thickness = params.get("shell", {}).get("thickness_mm", 1.5)
        
        # Simple energy absorption model based on shell thickness
        # More sophisticated models would use FEA or material properties
        energy_absorption = self._estimate_energy_absorption(shell_thickness, mesh)
        
        target_energy = req.absorb_energy_J or 2.0  # Default 2J
        passed = energy_absorption >= target_energy
        margin = (energy_absorption - target_energy) / target_energy if target_energy > 0 else 0
        
        results.append(EvaluationResult(
            test_id="drop_protection_energy",
            passed=passed,
            score=1.0 if passed else max(0.0, energy_absorption / target_energy),
            margin=margin,
            details=f"Energy absorption: {energy_absorption:.2f}J (target: {target_energy:.2f}J)"
        ))
        
        # Check strain limits if specified
        if req.max_strain_pct:
            max_strain = self._estimate_max_strain(shell_thickness)
            strain_passed = max_strain <= req.max_strain_pct
            strain_margin = (req.max_strain_pct - max_strain) / req.max_strain_pct if req.max_strain_pct > 0 else 0
            
            results.append(EvaluationResult(
                test_id="drop_protection_strain",
                passed=strain_passed,
                score=1.0 if strain_passed else max(0.0, 1.0 - max_strain / req.max_strain_pct),
                margin=strain_margin,
                details=f"Max strain: {max_strain:.1f}% (limit: {req.max_strain_pct:.1f}%)"
            ))
        
        return results
    
    def _estimate_energy_absorption(self, thickness: float, mesh: trimesh.Trimesh) -> float:
        """Estimate energy absorption capacity (simplified model)"""
        # Simple model: energy ~ thickness^2 * volume
        volume = mesh.volume
        energy_per_cm3 = 0.1 * (thickness ** 2)  # Heuristic based on thickness
        return volume * energy_per_cm3 / 1000  # Convert to Joules
    
    def _estimate_max_strain(self, thickness: float) -> float:
        """Estimate maximum strain under drop loading (simplified model)"""
        # Simple model: strain ~ 1/thickness for given load
        base_strain = 5.0  # Base strain at 1mm thickness
        return base_strain / thickness

class ThermalEvaluator(BaseEvaluator):
    """Evaluates thermal management capabilities"""
    
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate thermal requirements"""
        results = []
        mesh = self.load_mesh(stl_path)
        
        # Find thermal requirements
        thermal_reqs = [req for req in spec.functional_requirements if req.goal == "thermal_clearance"]
        
        for req in thermal_reqs:
            results.extend(self._evaluate_thermal_clearance(mesh, req, params))
        
        return results
    
    def _evaluate_thermal_clearance(self, mesh: trimesh.Trimesh, req: Any, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate thermal clearance requirements"""
        results = []
        
        # Extract ventilation parameters
        vents = params.get("vents", {})
        vent_cell_size = vents.get("cell_mm", 4.0)
        
        # Estimate ventilation area (simplified)
        mesh_area = mesh.area
        vent_density = 1.0 / (vent_cell_size ** 2) if vent_cell_size > 0 else 0
        vent_area = mesh_area * vent_density * 0.1  # Assume 10% of vent area is open
        
        # Estimate air gap
        shell_thickness = params.get("shell", {}).get("thickness_mm", 1.5)
        air_gap = min(shell_thickness * 0.5, vent_cell_size * 0.25)  # Simplified model
        
        target_air_gap = req.min_air_gap_mm or 1.0
        passed = air_gap >= target_air_gap
        margin = (air_gap - target_air_gap) / target_air_gap if target_air_gap > 0 else 0
        
        results.append(EvaluationResult(
            test_id="thermal_air_gap",
            passed=passed,
            score=1.0 if passed else max(0.0, air_gap / target_air_gap),
            margin=margin,
            details=f"Air gap: {air_gap:.2f}mm (target: {target_air_gap:.2f}mm)"
        ))
        
        # Check ventilation area
        min_vent_area = mesh_area * 0.05  # Minimum 5% of surface area
        vent_passed = vent_area >= min_vent_area
        vent_margin = (vent_area - min_vent_area) / min_vent_area if min_vent_area > 0 else 0
        
        results.append(EvaluationResult(
            test_id="thermal_ventilation",
            passed=vent_passed,
            score=1.0 if vent_passed else max(0.0, vent_area / min_vent_area),
            margin=vent_margin,
            details=f"Ventilation area: {vent_area:.1f}mm² (minimum: {min_vent_area:.1f}mm²)"
        ))
        
        return results

class AccessibilityEvaluator(BaseEvaluator):
    """Evaluates accessibility and usability requirements"""
    
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate accessibility requirements"""
        results = []
        
        # Find accessibility requirements
        access_reqs = [req for req in spec.functional_requirements if req.goal == "toolless_access"]
        
        for req in access_reqs:
            results.extend(self._evaluate_toolless_access(req, params))
        
        return results
    
    def _evaluate_toolless_access(self, req: Any, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate toolless access requirements"""
        results = []
        
        # Extract latch parameters
        latches = params.get("latches", {})
        latch_type = latches.get("type", "snap")
        latch_count = latches.get("count", 4)
        tab_size = latches.get("tab_mm", [6.0, 1.4])
        lip_size = latches.get("lip_mm", 0.6)
        
        # Estimate opening time based on latch design
        if latch_type == "snap":
            # Snap latches: quick release
            opening_time = 2.0 + (latch_count - 4) * 0.5  # Base 2s + 0.5s per extra latch
        elif latch_type == "sliding":
            # Sliding latches: moderate time
            opening_time = 5.0 + latch_count * 1.0
        else:
            # Default: assume screw-based
            opening_time = 30.0 + latch_count * 10.0
        
        target_time = req.max_open_time_s or 5.0
        passed = opening_time <= target_time
        margin = (target_time - opening_time) / target_time if target_time > 0 else 0
        
        results.append(EvaluationResult(
            test_id="toolless_access_time",
            passed=passed,
            score=1.0 if passed else max(0.0, 1.0 - opening_time / target_time),
            margin=margin,
            details=f"Opening time: {opening_time:.1f}s (target: {target_time:.1f}s)"
        ))
        
        # Check latch accessibility
        tab_area = tab_size[0] * tab_size[1] if len(tab_size) >= 2 else 6.0 * 1.4
        min_tab_area = 5.0  # Minimum tab area for accessibility
        
        tab_passed = tab_area >= min_tab_area
        tab_margin = (tab_area - min_tab_area) / min_tab_area if min_tab_area > 0 else 0
        
        results.append(EvaluationResult(
            test_id="latch_accessibility",
            passed=tab_passed,
            score=1.0 if tab_passed else max(0.0, tab_area / min_tab_area),
            margin=tab_margin,
            details=f"Latch tab area: {tab_area:.1f}mm² (minimum: {min_tab_area:.1f}mm²)"
        ))
        
        return results
