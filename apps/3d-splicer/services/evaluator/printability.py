"""
3D printability evaluator.
"""

import numpy as np
import trimesh
from typing import List, Dict, Any
from .base import BaseEvaluator
from src.schemas.functional import FunctionalSpec, EvaluationResult

class PrintabilityEvaluator(BaseEvaluator):
    """Evaluates 3D printing feasibility and constraints"""
    
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Evaluate printability constraints"""
        results = []
        mesh = self.load_mesh(stl_path)
        
        # Check mesh validity
        results.extend(self._check_mesh_validity(mesh))
        
        # Check overhang angles
        results.extend(self._check_overhang_angles(mesh, spec))
        
        # Check wall thickness
        results.extend(self._check_wall_thickness(mesh, spec, params))
        
        # Check minimum feature size
        results.extend(self._check_minimum_features(mesh, spec))
        
        return results
    
    def _check_mesh_validity(self, mesh: trimesh.Trimesh) -> List[EvaluationResult]:
        """Check basic mesh validity for 3D printing"""
        results = []
        
        # Check watertight
        watertight = mesh.is_watertight
        results.append(EvaluationResult(
            test_id="mesh_watertight",
            passed=watertight,
            score=1.0 if watertight else 0.0,
            margin=None,
            details=f"Mesh is {'watertight' if watertight else 'not watertight'}"
        ))
        
        # Check manifold
        manifold = mesh.is_winding_consistent
        results.append(EvaluationResult(
            test_id="mesh_manifold",
            passed=manifold,
            score=1.0 if manifold else 0.0,
            margin=None,
            details=f"Mesh is {'manifold' if manifold else 'not manifold'}"
        ))
        
        # Check for degenerate faces
        degenerate_faces = np.sum(mesh.area_faces < 1e-10)
        passed = degenerate_faces == 0
        results.append(EvaluationResult(
            test_id="mesh_degenerate",
            passed=passed,
            score=1.0 if passed else max(0.0, 1.0 - degenerate_faces / len(mesh.faces)),
            margin=None,
            details=f"Degenerate faces: {degenerate_faces}"
        ))
        
        return results
    
    def _check_overhang_angles(self, mesh: trimesh.Trimesh, spec: FunctionalSpec) -> List[EvaluationResult]:
        """Check for overhang angles that exceed printing limits"""
        results = []
        
        # Find overhang angle constraint
        max_overhang_angle = 55.0  # Default (more generous)
        for constraint in spec.constraints:
            if constraint.rule == "printability:overhang_angle_deg":
                if constraint.value:
                    if isinstance(constraint.value, (int, float)):
                        max_overhang_angle = float(constraint.value)
                    else:
                        try:
                            max_overhang_angle = float(constraint.value)
                        except (ValueError, TypeError):
                            max_overhang_angle = 55.0
                break
        
        # Calculate face normals
        face_normals = mesh.face_normals
        
        # Check angles relative to build plate (Z-up)
        build_plate_normal = np.array([0, 0, -1])
        
        # Calculate angles between face normals and build plate normal
        dot_products = np.dot(face_normals, build_plate_normal)
        angles = np.arccos(np.clip(np.abs(dot_products), 0, 1)) * 180 / np.pi
        
        # Find faces that exceed overhang limit
        overhang_faces = angles > (90 - max_overhang_angle)
        overhang_ratio = np.sum(overhang_faces) / len(angles)
        
        # Calculate worst overhang angle
        worst_angle = np.max(angles[overhang_faces]) if np.any(overhang_faces) else 0
        
        passed = overhang_ratio < 0.1  # Allow up to 10% of faces to be overhangs
        margin = (0.1 - overhang_ratio) / 0.1 if overhang_ratio < 0.1 else 0
        
        results.append(EvaluationResult(
            test_id="overhang_angles",
            passed=passed,
            score=1.0 if passed else max(0.0, 1.0 - overhang_ratio),
            margin=margin,
            details=f"Overhang ratio: {overhang_ratio:.2%}, worst angle: {worst_angle:.1f}° "
                   f"(limit: {max_overhang_angle}°)"
        ))
        
        return results
    
    def _check_wall_thickness(self, mesh: trimesh.Trimesh, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """Check minimum wall thickness constraints"""
        results = []
        
        # Calculate minimum wall thickness from nozzle size
        layer_height = spec.materials.layer_height_mm
        wall_count = spec.materials.wall_count
        nozzle_diameter = layer_height * 4  # Heuristic: nozzle ≈ 4x layer height
        
        # Minimum wall thickness = nozzle diameter × wall count
        min_wall_thickness = nozzle_diameter * wall_count
        
        # Override with constraint if specified
        for constraint in spec.constraints:
            if constraint.rule == "printability:min_wall_thickness_mm":
                if constraint.value:
                    if isinstance(constraint.value, (int, float)):
                        min_wall_thickness = float(constraint.value)
                    else:
                        try:
                            min_wall_thickness = float(constraint.value)
                        except (ValueError, TypeError):
                            pass  # Keep calculated value
                break
        
        # Get shell thickness from parameters
        shell_thickness = params.get("shell", {}).get("thickness_mm", 1.5)
        
        # Check if shell thickness meets minimum
        passed = shell_thickness >= min_wall_thickness
        margin = (shell_thickness - min_wall_thickness) / min_wall_thickness if min_wall_thickness > 0 else 0
        
        results.append(EvaluationResult(
            test_id="wall_thickness",
            passed=passed,
            score=1.0 if passed else max(0.0, shell_thickness / min_wall_thickness),
            margin=margin,
            details=f"Shell thickness: {shell_thickness:.2f}mm (minimum: {min_wall_thickness:.2f}mm, "
                   f"nozzle: {nozzle_diameter:.2f}mm, walls: {wall_count})"
        ))
        
        return results
    
    def _check_minimum_features(self, mesh: trimesh.Trimesh, spec: FunctionalSpec) -> List[EvaluationResult]:
        """Check minimum feature size for printing"""
        results = []
        
        # Estimate minimum printable feature size based on layer height
        layer_height = spec.materials.layer_height_mm
        min_feature_size = layer_height * 2  # Conservative estimate
        
        # Calculate mesh bounding box
        bounds = mesh.bounds
        mesh_size = np.max(bounds[1] - bounds[0])
        
        # Check if smallest dimension is printable
        smallest_dim = np.min([bounds[1, 0] - bounds[0, 0], 
                              bounds[1, 1] - bounds[0, 1], 
                              bounds[1, 2] - bounds[0, 2]])
        
        passed = smallest_dim >= min_feature_size
        margin = (smallest_dim - min_feature_size) / min_feature_size if min_feature_size > 0 else 0
        
        results.append(EvaluationResult(
            test_id="minimum_features",
            passed=passed,
            score=1.0 if passed else max(0.0, smallest_dim / min_feature_size),
            margin=margin,
            details=f"Smallest dimension: {smallest_dim:.2f}mm (minimum: {min_feature_size:.2f}mm)"
        ))
        
        return results
