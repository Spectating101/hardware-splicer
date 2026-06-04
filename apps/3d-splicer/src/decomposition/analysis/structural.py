# File: src/decomposition/analysis/structural.py
# Purpose: Structural analysis for component stability and printing
# Dependencies: Mesh, Component, numpy, scipy
# Priority: High - Critical for ensuring printable components

import numpy as np
import numpy.typing as npt
from typing import Dict, List, Tuple, Set, Optional, Any
from scipy.sparse import csr_matrix, linalg as spla
import tetgen
from ..core.mesh import Mesh
from ..core.component import Component, ConnectionPoint

class StructuralAnalyzer:
    """Advanced structural analysis for 3D printing"""

    def __init__(self, mesh: Mesh):
        self.mesh = mesh
        self._cache = {
            'fem_mesh': None,
            'stiffness_matrix': None,
            'stress_field': None,
            'deformation': None,
            'stability_analysis': None
        }
        
        # Material properties (default to PLA)
        self.material = {
            'youngs_modulus': 3.5e9,  # Pa
            'poissons_ratio': 0.36,
            'yield_strength': 50e6,  # Pa
            'density': 1240,  # kg/m³
            'layer_bond_strength': 0.8  # Relative to bulk strength
        }
        
    def analyze_structural_integrity(self, 
                                   loads: Optional[List[Dict]] = None,
                                   constraints: Optional[List[Dict]] = None
                                   ) -> Dict[str, float]:
        """Comprehensive structural analysis"""
        
        # Generate tetrahedral mesh if not cached
        if self._cache['fem_mesh'] is None:
            self._cache['fem_mesh'] = self._generate_tetrahedral_mesh()
            
        # Apply loads and constraints
        if loads is None:
            loads = self._generate_default_loads()
        if constraints is None:
            constraints = self._generate_default_constraints()
            
        # Perform FEM analysis
        displacement = self._solve_fem(loads, constraints)
        stress = self._compute_stress_field(displacement)
        
        # Analyze results
        max_stress = np.max(np.abs(stress))
        max_displacement = np.max(np.abs(displacement))
        safety_factor = self.material['yield_strength'] / max_stress
        
        # Check layer adhesion
        layer_analysis = self._analyze_layer_strength(stress)
        
        # Analyze support requirements
        support_analysis = self._analyze_support_needs(stress)
        
        return {
            'max_stress': max_stress,
            'max_displacement': max_displacement,
            'safety_factor': safety_factor,
            'critical_regions': self._identify_critical_regions(stress),
            'layer_strength_ratio': layer_analysis['strength_ratio'],
            'support_requirements': support_analysis,
            'stability_score': self._compute_stability_score(stress, displacement)
        }

    def _generate_tetrahedral_mesh(self) -> Dict:
        """Generate tetrahedral mesh for FEM analysis"""
        
        # Initialize tetgen
        vertices = self.mesh.vertices
        faces = self.mesh.faces
        
        # Create tetgen instance
        tet = tetgen.TetGen(vertices, faces)
        
        # Generate high-quality mesh
        node, elem = tet.tetrahedralize(
            order=2,  # Quadratic elements
            mindihedral=10,  # Minimum dihedral angle
            minratio=1.5,  # Maximum radius-edge ratio
            quality=True
        )
        
        return {
            'nodes': node,
            'elements': elem,
            'node_maps': self._generate_node_maps(node)
        }

    def _solve_fem(self,
                  loads: List[Dict],
                  constraints: List[Dict]) -> npt.NDArray[np.float64]:
        """Solve FEM system with given loads and constraints"""
        
        # Get or compute stiffness matrix
        if self._cache['stiffness_matrix'] is None:
            self._cache['stiffness_matrix'] = self._compute_stiffness_matrix()
            
        K = self._cache['stiffness_matrix']
        
        # Apply constraints
        K_constrained, f = self._apply_constraints(K, loads, constraints)
        
        # Solve system
        try:
            # Try direct solver first
            u = spla.spsolve(K_constrained, f)
        except Exception:
            # Fall back to iterative solver
            u, info = spla.bicgstab(K_constrained, f, tol=1e-10)
            if info != 0:
                raise ValueError("FEM solution failed to converge")
                
        return u

    def _compute_stress_field(self, 
                            displacement: npt.NDArray[np.float64]
                            ) -> npt.NDArray[np.float64]:
        """Compute stress field from displacements"""
        
        fem_mesh = self._cache['fem_mesh']
        elements = fem_mesh['elements']
        nodes = fem_mesh['nodes']
        
        # Initialize stress array (6 components per element)
        n_elements = len(elements)
        stress = np.zeros((n_elements, 6))
        
        # Compute constitutive matrix
        D = self._get_constitutive_matrix()
        
        # Compute stress for each element
        for i, element in enumerate(elements):
            # Get element displacements
            elem_disp = displacement[np.array([3*n + j for n in element 
                                             for j in range(3)])]
            
            # Compute B matrix
            B = self._compute_B_matrix(nodes[element])
            
            # Compute stress
            stress[i] = D @ B @ elem_disp
            
        return stress

    def _analyze_layer_strength(self, 
                              stress: npt.NDArray[np.float64]
                              ) -> Dict[str, float]:
        """Analyze strength relative to layer orientation"""
        
        # Get print orientation
        orientation = self._determine_print_orientation()
        
        # Transform stress to layer coordinates
        layer_stress = self._transform_stress_to_layers(stress, orientation)
        
        # Analyze interlayer stresses
        normal_stress = layer_stress[:, 2]  # Z-direction normal stress
        shear_stress = np.sqrt(layer_stress[:, 3]**2 + layer_stress[:, 4]**2)
        
        # Compare to material limits
        normal_ratio = np.max(np.abs(normal_stress)) / (
            self.material['yield_strength'] * self.material['layer_bond_strength']
        )
        shear_ratio = np.max(shear_stress) / (
            self.material['yield_strength'] * self.material['layer_bond_strength'] * 0.5
        )
        
        return {
            'strength_ratio': max(normal_ratio, shear_ratio),
            'critical_normal_stress': np.max(np.abs(normal_stress)),
            'critical_shear_stress': np.max(shear_stress),
            'weak_layers': self._identify_weak_layers(layer_stress)
        }

    def _analyze_support_needs(self,
                             stress: npt.NDArray[np.float64]
                             ) -> Dict[str, Any]:
        """Analyze support structure requirements"""
        
        # Find regions needing support
        fem_mesh = self._cache['fem_mesh']
        elements = fem_mesh['elements']
        nodes = fem_mesh['nodes']
        
        # Compute element centroids and volumes
        centroids = np.mean(nodes[elements], axis=1)
        volumes = self._compute_element_volumes(nodes, elements)
        
        # Identify overhang regions
        up_vector = np.array([0, 0, 1])
        overhangs = self._identify_overhangs(centroids, volumes)
        
        # Analyze stress in overhang regions
        overhang_stress = stress[overhangs]
        
        return {
            'support_regions': overhangs,
            'total_support_volume': np.sum(volumes[overhangs]),
            'max_overhang_stress': np.max(np.abs(overhang_stress)),
            'support_points': self._compute_support_points(
                centroids[overhangs], overhang_stress
            )
        }