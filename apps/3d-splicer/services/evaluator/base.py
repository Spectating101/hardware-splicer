"""
Base evaluator class for functional testing.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
import trimesh
import numpy as np

from src.schemas.functional import FunctionalSpec, EvaluationResult

logger = logging.getLogger(__name__)

class BaseEvaluator(ABC):
    """Base class for all functional evaluators"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        
    @abstractmethod
    def evaluate(self, stl_path: str, spec: FunctionalSpec, params: Dict[str, Any]) -> List[EvaluationResult]:
        """
        Evaluate the STL against functional requirements.
        
        Args:
            stl_path: Path to the STL file
            spec: Functional specification
            params: Design parameters used to generate the STL
            
        Returns:
            List of evaluation results
        """
        pass
    
    def load_mesh(self, stl_path: str) -> trimesh.Trimesh:
        """Load and validate STL mesh"""
        try:
            mesh = trimesh.load_mesh(stl_path, force='mesh')
            
            if not mesh.is_watertight:
                logger.warning(f"Mesh {stl_path} is not watertight")
            
            if not mesh.is_winding_consistent:
                logger.warning(f"Mesh {stl_path} has inconsistent winding")
                
            return mesh
            
        except Exception as e:
            logger.error(f"Failed to load mesh {stl_path}: {e}")
            raise
    
    def calculate_bounds(self, mesh: trimesh.Trimesh) -> Dict[str, float]:
        """Calculate mesh bounding box"""
        bounds = mesh.bounds
        return {
            "x_min": bounds[0, 0],
            "x_max": bounds[1, 0], 
            "y_min": bounds[0, 1],
            "y_max": bounds[1, 1],
            "z_min": bounds[0, 2],
            "z_max": bounds[1, 2],
            "width": bounds[1, 0] - bounds[0, 0],
            "height": bounds[1, 1] - bounds[0, 1],
            "depth": bounds[1, 2] - bounds[0, 2]
        }
    
    def check_overlap(self, 
                     mesh: trimesh.Trimesh, 
                     keepouts: List[Dict[str, Any]]) -> List[EvaluationResult]:
        """
        Check if mesh overlaps with keepout regions.
        
        Args:
            mesh: The mesh to check
            keepouts: List of keepout region definitions
            
        Returns:
            List of evaluation results for keepout violations
        """
        results = []
        
        for i, keepout in enumerate(keepouts):
            # Create keepout bounding box
            if keepout["shape"] == "rect":
                keepout_bounds = np.array([
                    [keepout["at"][0] - keepout["size"][0]/2, 
                     keepout["at"][1] - keepout["size"][1]/2,
                     keepout.get("z", [0, 10])[0]],
                    [keepout["at"][0] + keepout["size"][0]/2,
                     keepout["at"][1] + keepout["size"][1]/2, 
                     keepout.get("z", [0, 10])[1]]
                ])
            else:  # circle
                radius = keepout.get("size", [5.0, 5.0])[0] / 2
                keepout_bounds = np.array([
                    [keepout["at"][0] - radius,
                     keepout["at"][1] - radius,
                     keepout.get("z", [0, 10])[0]],
                    [keepout["at"][0] + radius,
                     keepout["at"][1] + radius,
                     keepout.get("z", [0, 10])[1]]
                ])
            
            # Check for overlap with mesh bounds
            mesh_bounds = mesh.bounds
            overlap = not (mesh_bounds[1, 0] < keepout_bounds[0, 0] or
                          mesh_bounds[0, 0] > keepout_bounds[1, 0] or
                          mesh_bounds[1, 1] < keepout_bounds[0, 1] or
                          mesh_bounds[0, 1] > keepout_bounds[1, 1] or
                          mesh_bounds[1, 2] < keepout_bounds[0, 2] or
                          mesh_bounds[0, 2] > keepout_bounds[1, 2])
            
            results.append(EvaluationResult(
                test_id=f"keepout_{i}",
                passed=not overlap,
                score=0.0 if overlap else 1.0,
                margin=None,
                details=f"Keepout region {i} {'violated' if overlap else 'respected'}"
            ))
            
        return results
