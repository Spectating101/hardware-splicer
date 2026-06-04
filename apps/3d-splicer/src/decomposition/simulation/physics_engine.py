# File: src/decomposition/simulation/physics_engine.py
# Purpose: Physics simulation for structural analysis and assembly validation
# Dependencies: numpy, scipy, Component class
# Priority: High - Critical for validation

import numpy as np
import numpy.typing as npt
from typing import Dict, List, Tuple, Optional
from scipy.sparse import csc_matrix, linalg as spla
from scipy.spatial.transform import Rotation
from ..core.component import Component, ConnectionPoint
from ..core.mesh import Mesh

class PhysicsEngine:
    """Advanced physics simulation for component analysis and assembly"""
    
    def __init__(self):
        self.gravity = np.array([0, 0, -9.81])
        self.material_properties = {
            'density': 1.24,  # g/cm³ for PLA
            'youngs_modulus': 3.5e9,  # Pa
            'poissons_ratio': 0.36,
            'yield_strength': 50e6,  # Pa
            'friction_coefficient': 0.3
        }
        
        self._cache = {
            'fem_models': {},
            'contact_maps': {},
            'stress_history': {},
            'assembly_sequence': None
        }
        
        # Simulation parameters
        self.TIME_STEP = 0.001  # seconds
        self.MAX_ITERATIONS = 1000
        self.CONVERGENCE_TOL = 1e-6
        self.CONTACT_STIFFNESS = 1e5
        
    def analyze_assembly_physics(self,
                               components: List[Component],
                               connections: List[ConnectionPoint],
                               sequence: Optional[List[int]] = None) -> Dict:
        """Comprehensive physics analysis of assembly"""
        
        # Initialize assembly state
        state = self._initialize_assembly_state(components, connections)
        
        # If no sequence provided, compute optimal sequence
        if sequence is None:
            sequence = self._compute_optimal_sequence(components, connections)
            
        # Simulate assembly process
        assembly_results = []
        for step in sequence:
            # Update state for this step
            state = self._simulate_assembly_step(state, step)
            
            # Check for collisions
            collisions = self._detect_collisions(state)
            if collisions:
                return {
                    'success': False,
                    'failed_step': step,
                    'reason': 'collision',
                    'details': collisions
                }
                
            # Validate connections
            connection_status = self._validate_connections(state, step)
            if not connection_status['valid']:
                return {
                    'success': False,
                    'failed_step': step,
                    'reason': 'connection_failure',
                    'details': connection_status
                }
                
            # Update forces and torques
            state = self._update_dynamics(state)
            
            # Check stability
            stability = self._check_stability(state)
            if not stability['stable']:
                return {
                    'success': False,
                    'failed_step': step,
                    'reason': 'instability',
                    'details': stability
                }
                
            assembly_results.append({
                'step': step,
                'state': state,
                'stability': stability,
                'forces': self._compute_internal_forces(state)
            })
            
        # Validate final assembly
        final_validation = self._validate_final_assembly(state)
        
        return {
            'success': True,
            'assembly_sequence': sequence,
            'step_results': assembly_results,
            'final_state': state,
            'validation': final_validation,
            'stress_analysis': self._analyze_final_stress_state(state)
        }

    def _initialize_assembly_state(self,
                                    components: List[Component],
                                    connections: List[ConnectionPoint]) -> Dict:
        """Initialize physics state for assembly simulation"""
        return {
            'positions': [c.mesh.compute_metadata().center_of_mass 
                            for c in components],
            'orientations': [self._compute_initial_orientation(c) 
                            for c in components],
            'velocities': [np.zeros(3) for _ in components],
            'angular_velocities': [np.zeros(3) for _ in components],
            'forces': [np.zeros(3) for _ in components],
            'torques': [np.zeros(3) for _ in components],
            'components': components,
            'connections': connections,
            'assembled_components': set(),
            'active_connections': set(),
            'contact_points': [],
            'time': 0.0
        }

    def _compute_optimal_sequence(self,
                                components: List[Component],
                                connections: List[ConnectionPoint]) -> List[int]:
        """Compute optimal assembly sequence"""
        
        # Build dependency graph
        G = self._build_dependency_graph(components, connections)
        
        # Find base component (most connections/largest volume)
        base_scores = []
        for i, comp in enumerate(components):
            score = (len(comp.connection_points) * 
                    comp.mesh.compute_metadata().volume)
            base_scores.append((i, score))
            
        base_component = max(base_scores, key=lambda x: x[1])[0]
        
        # Build sequence using modified topological sort
        sequence = [base_component]
        remaining = set(range(len(components))) - {base_component}
        
        while remaining:
            # Score remaining components
            scores = []
            for i in remaining:
                score = self._compute_assembly_score(i, sequence, G)
                scores.append((i, score))
                
            # Add highest scoring component
            next_component = max(scores, key=lambda x: x[1])[0]
            sequence.append(next_component)
            remaining.remove(next_component)
            
        return sequence

    def _simulate_assembly_step(self,
                                state: Dict,
                                step: int) -> Dict:
        """Simulate physics for single assembly step"""
        
        dt = self.TIME_STEP
        
        # Get component being assembled
        component = state['components'][step]
        
        # Find target position and orientation
        target_pose = self._compute_target_pose(state, step)
        
        # Simulate movement to target
        for _ in range(self.MAX_ITERATIONS):
            # Update position and orientation
            state['positions'][step] += state['velocities'][step] * dt
            
            # Update orientation using quaternion integration
            angular_vel = state['angular_velocities'][step]
            if np.any(angular_vel):
                delta_rot = Rotation.from_rotvec(angular_vel * dt)
                current_rot = Rotation.from_matrix(state['orientations'][step])
                new_rot = delta_rot * current_rot
                state['orientations'][step] = new_rot.as_matrix()
                
            # Check for collisions
            collisions = self._detect_collisions(state)
            if collisions:
                # Handle collision response
                state = self._resolve_collisions(state, collisions)
                
            # Update forces and torques
            state = self._update_forces(state, target_pose, step)
            
            # Check convergence
            if self._check_convergence(state, target_pose, step):
                break
                
        return state

    def _detect_collisions(self, state: Dict) -> List[Dict]:
        """Detect collisions between components"""
        collisions = []
        
        # For each pair of components
        n_components = len(state['components'])
        for i in range(n_components):
            for j in range(i + 1, n_components):
                # Skip if both components are already assembled
                if (i in state['assembled_components'] and 
                    j in state['assembled_components']):
                    continue
                    
                # Transform meshes to current positions
                mesh_i = self._transform_mesh(
                    state['components'][i].mesh,
                    state['positions'][i],
                    state['orientations'][i]
                )
                mesh_j = self._transform_mesh(
                    state['components'][j].mesh,
                    state['positions'][j],
                    state['orientations'][j]
                )
                
                # Check for intersection
                collision = self._check_mesh_intersection(mesh_i, mesh_j)
                if collision:
                    collisions.append({
                        'components': (i, j),
                        'point': collision['point'],
                        'normal': collision['normal'],
                        'depth': collision['depth']
                    })
                    
        return collisions

    def _update_forces(self,
                        state: Dict,
                        target_pose: Dict,
                        step: int) -> Dict:
        """Update forces and torques for assembly step"""
        
        # Clear previous forces and torques
        state['forces'] = [np.zeros(3) for _ in state['components']]
        state['torques'] = [np.zeros(3) for _ in state['components']]
        
        # Apply gravity to unassembled components
        for i, component in enumerate(state['components']):
            if i not in state['assembled_components']:
                mass = (component.mesh.compute_metadata().volume * 
                        self.material_properties['density'])
                state['forces'][i] += mass * self.gravity
                
        # Add connection forces
        connection_forces = self._compute_connection_forces(state)
        for i, force in enumerate(connection_forces):
            state['forces'][i] += force
            
        # Add target pose attraction forces for current step
        if not self._check_convergence(state, target_pose, step):
            attraction_force, attraction_torque = self._compute_attraction_forces(
                state, target_pose, step
            )
            state['forces'][step] += attraction_force
            state['torques'][step] += attraction_torque
            
        return state

    def _check_stability(self, state: Dict) -> Dict:
        """Check stability of current assembly state"""
        
        # Compute total center of mass
        total_mass = 0
        com = np.zeros(3)
        
        for i, component in enumerate(state['components']):
            if i in state['assembled_components']:
                mass = (component.mesh.compute_metadata().volume * 
                        self.material_properties['density'])
                total_mass += mass
                com += mass * state['positions'][i]
                
        if total_mass > 0:
            com /= total_mass
            
        # Check if COM projects within support polygon
        support_polygon = self._compute_support_polygon(state)
        stability_margin = self._check_com_stability(com, support_polygon)
        
        # Analyze joint stability
        joint_stability = self._analyze_joint_stability(state)
        
        return {
            'stable': (stability_margin > 0 and 
                        all(js['stable'] for js in joint_stability)),
            'com_margin': stability_margin,
            'joint_stability': joint_stability,
            'critical_joints': [
                i for i, js in enumerate(joint_stability) 
                if not js['stable']
            ]
        }

    def _validate_final_assembly(self, state: Dict) -> Dict:
        """Validate complete assembly"""
        
        # Check all connections are properly mated
        connection_status = self._validate_all_connections(state)
        
        # Check stress state
        stress_state = self._analyze_final_stress_state(state)
        
        # Check overall stability
        stability = self._check_stability(state)
        
        # Verify no intersections
        intersections = self._detect_collisions(state)
        
        return {
            'valid': (connection_status['valid'] and
                        stress_state['valid'] and
                        stability['stable'] and
                        not intersections),
            'connection_status': connection_status,
            'stress_state': stress_state,
            'stability': stability,
            'intersections': intersections
        }

    def _analyze_final_stress_state(self, state: Dict) -> Dict:
        """Analyze stress state of final assembly"""
        
        try:
            # Build global FEM model
            fem_model = self._build_global_fem_model(state)
            
            # Apply gravity and connection forces
            forces = self._compute_global_forces(state)
            
            # Solve FEM system
            displacements = self._solve_global_fem(fem_model, forces)
            
            # Compute stresses
            stresses = self._compute_global_stress_field(
                fem_model, displacements
            )
            
            # Analyze results
            max_stress = np.max(np.abs(stresses))
            max_displacement = np.max(np.abs(displacements))
            
            return {
                'valid': max_stress < self.material_properties['yield_strength'],
                'max_stress': max_stress,
                'max_displacement': max_displacement,
                'stress_field': stresses,
                'displacement_field': displacements,
                'critical_regions': self._identify_critical_regions(stresses)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }