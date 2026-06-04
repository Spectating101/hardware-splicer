# File: src/decomposition/processing/optimization.py
# Purpose: Optimizes component orientations, layouts, and connections
# Dependencies: Core modules, numpy, scipy
# Priority: High - Critical for print quality and efficiency

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from scipy.optimize import minimize
from scipy.spatial import ConvexHull
import networkx as nx

from ..core.mesh import Mesh
from ..core.component import Component, ConnectionPoint
from ..analysis.geometric import GeometricAnalyzer
from ..analysis.structural import StructuralAnalyzer

class OptimizationError(Exception):
   """Custom exception for optimization-related errors"""
   pass

@dataclass
class OptimizationParams:
   """Parameters controlling optimization behavior"""
   support_weight: float = 1.0
   strength_weight: float = 1.0
   material_weight: float = 0.5
   time_weight: float = 0.5
   quality_weight: float = 0.8
   max_iterations: int = 1000
   convergence_threshold: float = 0.001
   allow_anisotropic: bool = True
   min_connection_strength: float = 0.7
   max_overhang_angle: float = 45.0  # degrees

class OptimizationGoal(Enum):
   """Different optimization objectives"""
   MINIMUM_SUPPORT = "min_support"
   MAXIMUM_STRENGTH = "max_strength"
   MINIMUM_MATERIAL = "min_material"
   MINIMUM_TIME = "min_time"
   MAXIMUM_QUALITY = "max_quality"
   BALANCED = "balanced"

class ComponentOptimizer:
   """Optimizes components for 3D printing"""
   
   def __init__(self):
       self._logger = logging.getLogger(__name__)
       
       # Initialize caches
       self._cache = {
           'orientation_scores': {},
           'layout_scores': {},
           'connection_scores': {},
           'support_volumes': {},
           'strength_analysis': {}
       }
       
       # Optimization constants
       self.BED_SIZE = (250, 210)  # mm
       self.MIN_SPACING = 5.0  # mm
       self.MAX_OVERHANG_ANGLE = 45.0  # degrees
       self.MIN_WALL_THICKNESS = 0.8  # mm
       
   def optimize_components(self,
                         components: List[Component],
                         params: OptimizationParams,
                         goal: OptimizationGoal = OptimizationGoal.BALANCED
                         ) -> Dict[str, Any]:
       """Execute complete optimization pipeline"""
       try:
           # Optimize individual components
           self._logger.info("Optimizing component orientations...")
           oriented_components = self._optimize_orientations(
               components, params, goal
           )
           
           # Optimize print layout
           self._logger.info("Optimizing print layout...")
           layout_plan = self._optimize_layout(
               oriented_components, params
           )
           
           # Optimize connections
           self._logger.info("Optimizing connections...")
           connection_plan = self._optimize_connections(
               oriented_components, params
           )
           
           # Generate support structures
           self._logger.info("Generating support structures...")
           support_plan = self._generate_support_structures(
               oriented_components,
               layout_plan,
               params
           )
           
           # Validate results
           self._logger.info("Validating optimization results...")
           validation = self._validate_optimization(
               oriented_components,
               layout_plan,
               connection_plan,
               support_plan,
               params
           )
           
           if not validation['valid']:
               raise OptimizationError(
                   f"Optimization validation failed: {validation['reason']}"
               )
               
           return {
               'components': oriented_components,
               'layout': layout_plan,
               'connections': connection_plan,
               'supports': support_plan,
               'metrics': self._compute_optimization_metrics(
                   oriented_components,
                   layout_plan,
                   connection_plan,
                   support_plan
               )
           }
           
       except Exception as e:
           self._logger.error(f"Component optimization failed: {str(e)}")
           raise OptimizationError(f"Component optimization failed: {str(e)}")

   def _optimize_orientations(self,
                            components: List[Component],
                            params: OptimizationParams,
                            goal: OptimizationGoal) -> List[Component]:
       """Optimize print orientation for each component"""
       try:
           optimized = []
           
           for component in components:
               # Generate candidate orientations
               candidates = self._generate_orientation_candidates(component)
               
               # Score candidates
               scores = self._score_orientations(
                   component,
                   candidates,
                   params,
                   goal
               )
               
               # Select best orientation
               best_orientation = max(
                   scores.items(),
                   key=lambda x: x[1]['total_score']
               )[0]
               
               # Apply orientation
               oriented_component = self._apply_orientation(
                   component,
                   best_orientation
               )
               
               optimized.append(oriented_component)
               
           return optimized
           
       except Exception as e:
           self._logger.error(f"Orientation optimization failed: {str(e)}")
           raise OptimizationError(
               f"Orientation optimization failed: {str(e)}"
           )

   def _optimize_layout(self,
                       components: List[Component],
                       params: OptimizationParams) -> Dict[str, Any]:
       """Optimize print bed layout"""
       try:
           # Initialize layout grid
           grid = self._initialize_print_bed()
           
           # Sort components by size
           sorted_components = sorted(
               components,
               key=lambda c: c.mesh.compute_metadata().volume,
               reverse=True
           )
           
           layout_plan = {
               'positions': {},
               'rotations': {},
               'layer_assignments': {}
           }
           
           # Place components
           current_layer = 0
           remaining = list(sorted_components)
           
           while remaining:
               # Try to place components in current layer
               layer_assignment = self._optimize_layer_layout(
                   remaining,
                   grid,
                   current_layer,
                   params
               )
               
               # Update layout plan
               layout_plan['positions'].update(layer_assignment['positions'])
               layout_plan['rotations'].update(layer_assignment['rotations'])
               
               # Assign layer
               for comp in layer_assignment['components']:
                   layout_plan['layer_assignments'][comp.id] = current_layer
                   remaining.remove(comp)
                   
               current_layer += 1
               
           return layout_plan
           
       except Exception as e:
           self._logger.error(f"Layout optimization failed: {str(e)}")
           raise OptimizationError(f"Layout optimization failed: {str(e)}")

   def _optimize_connections(self,
                           components: List[Component],
                           params: OptimizationParams) -> Dict[str, Any]:
       """Optimize component connections"""
       try:
           connection_plan = {
               'points': {},
               'types': {},
               'orientations': {}
           }
           
           # Build component adjacency graph
           graph = self._build_connection_graph(components)
           
           # Optimize each connection
           for comp1, comp2 in graph.edges():
               # Find interface region
               interface = self._compute_interface_region(comp1, comp2)
               
               # Generate connection candidates
               candidates = self._generate_connection_candidates(
                   comp1,
                   comp2,
                   interface
               )
               
               # Score candidates
               scores = self._score_connections(
                   candidates,
                   comp1,
                   comp2,
                   params
               )
               
               # Select optimal connections
               optimal = self._select_optimal_connections(
                   scores,
                   comp1,
                   comp2,
                   params
               )
               
               # Update plan
               connection_plan['points'][(comp1.id, comp2.id)] = optimal['points']
               connection_plan['types'][(comp1.id, comp2.id)] = optimal['types']
               connection_plan['orientations'][(comp1.id, comp2.id)] = optimal['orientations']
               
           return connection_plan
           
       except Exception as e:
           self._logger.error(f"Connection optimization failed: {str(e)}")
           raise OptimizationError(f"Connection optimization failed: {str(e)}")

   def _generate_support_structures(self,
                                 components: List[Component],
                                 layout: Dict[str, Any],
                                 params: OptimizationParams) -> Dict[str, Any]:
       """Generate optimized support structures"""
       try:
           support_plan = {
               'structures': {},
               'volumes': {},
               'contact_points': {}
           }
           
           for component in components:
               # Analyze overhangs
               overhangs = self._analyze_overhangs(
                   component,
                   layout['rotations'][component.id]
               )
               
               if not overhangs:
                   continue
                   
               # Generate support candidates
               candidates = self._generate_support_candidates(
                   component,
                   overhangs,
                   params
               )
               
               # Optimize supports
               optimal_supports = self._optimize_support_layout(
                   candidates,
                   component,
                   params
               )
               
               # Update plan
               support_plan['structures'][component.id] = optimal_supports['geometry']
               support_plan['volumes'][component.id] = optimal_supports['volume']
               support_plan['contact_points'][component.id] = optimal_supports['contacts']
               
           return support_plan
           
       except Exception as e:
           self._logger.error(f"Support structure generation failed: {str(e)}")
           raise OptimizationError(
               f"Support structure generation failed: {str(e)}"
           )

   def _generate_orientation_candidates(self,
                                     component: Component
                                     ) -> List[npt.NDArray[np.float64]]:
       """Generate candidate orientations for component"""
       try:
           candidates = []
           
           # Get component principal axes
           axes = component.mesh.compute_metadata().principal_axes
           
           # Generate orientations aligned with principal axes
           for axis in axes:
               for angle in np.linspace(0, 2*np.pi, 8):
                   rotation = self._compute_rotation_matrix(axis, angle)
                   candidates.append(rotation)
                   
           # Add orientations based on flat surfaces
           flat_surfaces = self._find_flat_surfaces(component)
           for surface in flat_surfaces:
               normal = surface['normal']
               rotation = self._align_with_normal(normal)
               candidates.append(rotation)
               
           return candidates
           
       except Exception as e:
           self._logger.error(
               f"Orientation candidate generation failed: {str(e)}"
           )
           raise OptimizationError(
               f"Orientation candidate generation failed: {str(e)}"
           )

   def _score_orientations(self,
                         component: Component,
                         orientations: List[npt.NDArray[np.float64]],
                         params: OptimizationParams,
                         goal: OptimizationGoal) -> Dict[int, Dict[str, float]]:
       """Score candidate orientations"""
       try:
           scores = {}
           
           for i, orientation in enumerate(orientations):
               # Apply orientation temporarily
               temp_comp = self._apply_orientation(component, orientation)
               
               # Compute metrics
               support_volume = self._compute_support_volume(temp_comp)
               strength_score = self._compute_strength_score(temp_comp)
               quality_score = self._compute_quality_score(temp_comp)
               
               # Compute weighted score based on goal
               if goal == OptimizationGoal.MINIMUM_SUPPORT:
                   total_score = -support_volume
               elif goal == OptimizationGoal.MAXIMUM_STRENGTH:
                   total_score = strength_score
               elif goal == OptimizationGoal.MAXIMUM_QUALITY:
                   total_score = quality_score
               else:  # Balanced
                   total_score = (
                       -params.support_weight * support_volume +
                       params.strength_weight * strength_score +
                       params.quality_weight * quality_score
                   )
                   
               scores[i] = {
                   'support_volume': support_volume,
                   'strength_score': strength_score,
                   'quality_score': quality_score,
                   'total_score': total_score
               }
               
           return scores
           
       except Exception as e:
           self._logger.error(f"Orientation scoring failed: {str(e)}")
           raise OptimizationError(f"Orientation scoring failed: {str(e)}")

   def _optimize_layer_layout(self,
                            components: List[Component],
                            grid: npt.NDArray[np.bool_],
                            layer: int,
                            params: OptimizationParams) -> Dict[str, Any]:
       """Optimize component layout for print layer"""
       try:
           layout = {
               'positions': {},
               'rotations': {},
               'components': []
           }
           
           # Initialize packing algorithm
           packer = self._initialize_packer(self.BED_SIZE)
           
           # Try to pack components
           for component in components:
               # Get component bounds
               bounds = component.mesh.compute_metadata().bounding_box
               
               # Try different rotations
               best_position = None
               best_rotation = None
               min_waste = float('inf')
               
               for angle in [0, 90, 180, 270]:
                   rotated_bounds = self._rotate_bounds(bounds, angle)
                   
                   # Try to find position
                   position = packer.find_position(rotated_bounds)
                   
                   if position is not None:
                       # Compute packing efficiency
                       waste = self._compute_packing_waste(
                           position,
                           rotated_bounds,
                           grid
                       )
                       
                       if waste < min_waste:
                           min_waste = waste
                           best_position = position
                           best_rotation = angle
                           
               if best_position is not None:
                   # Update layout
                   layout['positions'][component.id] = best_position
                   layout['rotations'][component.id] = best_rotation
                   layout['components'].append(component)
                   
                   # Update packing state
                   packer.add_component(
                       best_position,
                       self._rotate_bounds(bounds, best_rotation)
                   )
                   
           return layout
           
       except Exception as e:
           self._logger.error(f"Layer layout optimization failed: {str(e)}")
           raise OptimizationError(f"Layer layout optimization failed: {str(e)}")

   def _compute_interface_region(self,
                               comp1: Component,
                               comp2: Component) -> Dict[str, Any]:
       """Compute interface region between components"""
       try:
           # Find close vertices
           tree = cKDTree(comp1.mesh.vertices)
           distances, indices = tree.query(comp2.mesh.vertices)
           
           # Get interface vertices
           interface_vertices1 = set()
           interface_vertices2 = set()
           
           for v2, (v1, dist) in enumerate(zip(indices, distances)):
               if dist < self.MIN_SPACING:
                   interface_vertices1.add(v1)
                   interface_vertices2.add(v2)
                   
           # Compute interface properties
           center = np.mean(comp1.mesh.vertices[list(interface_vertices1)], axis=0)
           
           normal = self._compute_interface_normal(
               interface_vertices1,
               interface_vertices2,
               comp1,
               comp2
           )
           
           return {
               'vertices1': interface_vertices1,
               'vertices2': interface_vertices2,
               'center': center,
               'normal': normal,
               'area': self._compute_interface_area(interface_vertices1, comp1)
           }
           
       except Exception as e:
           self._logger.error(f"Interface computation failed: {str(e)}")
           raise OptimizationError(f"Interface computation failed: {str(e)}")

   def _validate_optimization(self,
                            components: List[Component],
                            layout: Dict[str, Any],
                            connections: Dict[str, Any],
                            supports: Dict[str, Any],
                            params: OptimizationParams) -> Dict[str, Any]:
       """Validate optimization results"""
       try:
           validation = {
               'valid': True,
               'issues': []
           }
           
           # Validate orientations
           for component in components:
               if not self._validate_component_orientation(component, params):
                   validation['valid'] = False
                   validation['issues'].append({
                       'type': 'invalid_orientation',
                       'component': component.id
                   })
                   
           # Validate layout
           if not self._validate_layout(layout, components):
               validation['valid'] = False
               validation['issues'].append({
                   'type': 'invalid_layout',
                   'details': 'Component collision or out of bounds'
               })
               
           # Validate connections
           if not self._validate_connections(connections, components, params):
               validation['valid'] = False
               validation['issues'].append({
                   'type': 'invalid_connections',
                   'details': 'Connection strength or interference issues'
               })
               
           # Validate supports
           if not self._validate_supports(supports, components, params):
               validation['valid'] = False
               validation['issues'].append({
                   'type': 'invalid_supports',
                   'details': 'Insufficient support or stability issues'
               })
               
           return validation
           
       except Exception as e:
           self._logger.error(f"Optimization validation failed: {str(e)}")
           raise OptimizationError(f"Optimization validation failed: {str(e)}")

   def _compute_optimization_metrics(self,
                                  components: List[Component],
                                  layout: Dict[str, Any],
                                  connections: Dict[str, Any],
                                  supports: Dict[str, Any]) -> Dict[str, float]:
       """Compute final optimization metrics"""
       try:
           # Initialize metrics
           metrics = {
               'total_volume': 0.0,
               'support_volume': 0.0,
               'print_time': 0.0,
               'bed_utilization': 0.0,
               'max_layer_height': 0.0,
               'connection_strength': 0.0
           }
           
           # Compute component metrics
           for component in components:
               metrics['total_volume'] += component.mesh.compute_metadata().volume
               metrics['print_time'] += self._estimate_print_time(component)
               
           # Add support metrics
           for support_data in supports['volumes'].values():
               metrics['support_volume'] += support_data
               
           # Compute bed utilization
           metrics['bed_utilization'] = self._compute_bed_utilization(layout)
           
           # Compute maximum layer height
           metrics['max_layer_height'] = max(
               layout['layer_assignments'].values()
           )
           
           # Compute average connection strength
           metrics['connection_strength'] = np.mean([
               self._compute_connection_strength(conn)
               for conn in connections['points'].values()
           ])
           
           return metrics
           
       except Exception as e:
           self._logger.error(f"Metric computation failed: {str(e)}")
           raise OptimizationError(f"Metric computation failed: {str(e)}")