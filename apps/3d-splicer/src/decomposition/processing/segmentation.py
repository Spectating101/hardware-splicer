# File: src/decomposition/processing/segmentation.py
# Purpose: Core decomposition logic implementing segmentation strategies
# Dependencies: All core and analysis modules
# Priority: Critical - Main decomposition engine

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from scipy.cluster import hierarchy
from scipy.spatial import Delaunay, KDTree
from sklearn.cluster import SpectralClustering
import networkx as nx
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..core.mesh import Mesh
from ..core.component import Component, ConnectionPoint, ConnectionType
from ..analysis.geometric import GeometricAnalyzer 
from ..analysis.structural import StructuralAnalyzer
from ..analysis.aesthetic import AestheticAnalyzer

class SegmentationError(Exception):
   """Custom exception for segmentation-related errors"""
   pass

@dataclass
class SegmentationParams:
   """Parameters for controlling segmentation behavior"""
   target_count: Optional[int] = None
   min_component_volume: float = 0.01
   preserve_symmetry: bool = True
   structural_priority: float = 1.0
   aesthetic_priority: float = 1.0
   convergence_threshold: float = 0.001
   max_iterations: int = 100
   feature_sensitivity: float = 0.7
   connection_spacing: float = 0.1
   min_connection_strength: float = 0.5
   boundary_smoothness: float = 0.8
   min_feature_size: float = 0.5
   support_angle_threshold: float = 45.0  # degrees
   max_overhang: float = 60.0  # degrees

class DecompositionEngine:
   """Core engine for mesh decomposition with comprehensive analysis"""

   def __init__(self, mesh: Mesh):
       self.mesh = mesh
       self.geometric_analyzer = GeometricAnalyzer(mesh)
       self.structural_analyzer = StructuralAnalyzer(mesh)
       self.aesthetic_analyzer = AestheticAnalyzer(mesh)
       
       # Initialize components list and graphs
       self.components: List[Component] = []
       self._adjacency_graph = None
       
       # Setup caching
       self._cache = {
           'segmentation_graph': None,
           'feature_analysis': None,
           'boundary_analysis': None,
           'connection_analysis': None,
           'stress_analysis': None,
           'printability': None
       }
       
       # Constants
       self.ADJACENCY_THRESHOLD = 0.01  # For component adjacency checks
       self.MIN_COMPONENT_SIZE = 100  # Minimum vertices per component
       self.MAX_CONNECTION_STRESS = 0.8  # Relative to material yield strength
       
       # Initialize logger
       self._logger = logging.getLogger(__name__)
       
   def decompose(self, params: SegmentationParams) -> List[Component]:
       """Execute full decomposition pipeline"""
       try:
           # Initial analysis
           self._logger.info("Starting initial analysis...")
           analysis_data = self._perform_initial_analysis(params)
           
           # Generate initial segmentation
           self._logger.info("Generating initial segmentation...")
           initial_segments = self._generate_initial_segmentation(
               analysis_data,
               params
           )
           
           # Refine segmentation
           self._logger.info("Refining segmentation...")
           refined_segments = self._refine_segmentation(
               initial_segments,
               analysis_data,
               params
           )
           
           # Create components
           self._logger.info("Generating components...")
           self.components = self._create_components(refined_segments)
           
           # Generate connections
           self._logger.info("Generating connection points...")
           self._generate_connection_points(params)
           
           # Validate final result
           self._logger.info("Validating decomposition...")
           if not self._validate_decomposition():
               raise SegmentationError("Failed to validate final decomposition")
           
           return self.components
           
       except Exception as e:
           self._logger.error(f"Decomposition failed: {str(e)}")
           raise SegmentationError(f"Decomposition failed: {str(e)}")

   def _perform_initial_analysis(self, params: SegmentationParams) -> Dict:
       """Perform comprehensive initial analysis"""
       analysis_data = {
           'symmetry': self.geometric_analyzer.analyze_symmetry(),
           'structural': self.structural_analyzer.analyze_structural_integrity(),
           'aesthetic': self.aesthetic_analyzer.identify_features(),
           'curvature': self.mesh.analyze_curvature(),
           'thickness': self.mesh._compute_thickness_distribution(),
           'stress': self._analyze_stress_distribution(),
           'feature_size': self._analyze_feature_sizes(),
           'printability': self._analyze_printability_constraints()
       }
       
       # Add derived metrics
       analysis_data.update(self._compute_derived_metrics(analysis_data))
       
       return analysis_data

   def _compute_derived_metrics(self, base_analysis: Dict) -> Dict:
       """Compute additional metrics from base analysis"""
       derived = {}
       
       # Compute feature importance
       derived['feature_importance'] = self._compute_feature_importance(
           base_analysis['aesthetic'],
           base_analysis['structural']
       )
       
       # Analyze potential split regions
       derived['split_candidates'] = self._find_split_candidates(
           base_analysis['thickness'],
           base_analysis['curvature']
       )
       
       # Compute connection suitability map
       derived['connection_suitability'] = self._compute_connection_suitability(
           base_analysis['stress'],
           base_analysis['thickness']
       )
       
       return derived

   def _analyze_stress_distribution(self) -> Dict[str, Any]:
       """Analyze stress distribution in mesh"""
       if self._cache['stress_analysis'] is not None:
           return self._cache['stress_analysis']

       # Compute base stress distribution
       stress_tensor = self.structural_analyzer._compute_stress_tensor()
       
       # Compute von Mises stress
       von_mises = np.sqrt(0.5 * (
           (stress_tensor[..., 0, 0] - stress_tensor[..., 1, 1])**2 +
           (stress_tensor[..., 1, 1] - stress_tensor[..., 2, 2])**2 +
           (stress_tensor[..., 2, 2] - stress_tensor[..., 0, 0])**2 +
           6 * (stress_tensor[..., 0, 1]**2 + 
                stress_tensor[..., 1, 2]**2 + 
                stress_tensor[..., 2, 0]**2)
       ))
       
       # Find stress concentrations
       stress_concentrations = self._find_stress_concentrations(von_mises)
       
       # Analyze principal stresses
       principal_stresses = np.linalg.eigvalsh(stress_tensor)
       
       analysis = {
           'von_mises': von_mises,
           'principal_stresses': principal_stresses,
           'concentrations': stress_concentrations,
           'max_stress': np.max(von_mises),
           'mean_stress': np.mean(von_mises)
       }
       
       self._cache['stress_analysis'] = analysis
       return analysis

   def _find_stress_concentrations(self, 
                                 stress_field: npt.NDArray[np.float64]
                                 ) -> List[Dict[str, Any]]:
       """Identify regions of stress concentration"""
       concentrations = []
       
       # Find local maxima in stress field
       maxima_indices = self._find_local_maxima(stress_field)
       
       for idx in maxima_indices:
           # Analyze concentration region
           region = self._analyze_concentration_region(idx, stress_field)
           
           if region['significance'] > 0.7:  # Threshold for significance
               concentrations.append(region)
               
       return concentrations

   def _analyze_feature_sizes(self) -> Dict[str, npt.NDArray[np.float64]]:
       """Analyze feature sizes across mesh"""
       # Compute local feature sizes
       vertices = self.mesh.vertices
       feature_sizes = np.zeros(len(vertices))
       
       # Use KD-tree for efficient neighbor search
       tree = KDTree(vertices)
       
       for i, vertex in enumerate(vertices):
           # Find nearest neighbors
           distances, _ = tree.query(vertex, k=10)
           
           # Compute local feature size metrics
           feature_sizes[i] = self._compute_local_feature_size(distances)
           
       return {
           'sizes': feature_sizes,
           'min_size': np.min(feature_sizes),
           'max_size': np.max(feature_sizes),
           'critical_regions': self._identify_critical_feature_regions(feature_sizes)
       }

   def _analyze_printability_constraints(self) -> Dict[str, Any]:
       """Analyze printability constraints"""
       if self._cache['printability'] is not None:
           return self._cache['printability']

       # Get face normals and areas
       face_normals = self.mesh.trimesh.face_normals
       face_areas = self.mesh.trimesh.area_faces
       
       # Analyze overhangs
       up_vector = np.array([0, 0, 1])
       angles = np.arccos(np.clip(np.dot(face_normals, up_vector), -1.0, 1.0))
       overhang_mask = angles > np.radians(45)
       
       # Compute support requirements
       support_volume = np.sum(face_areas[overhang_mask] * 
                             np.sin(angles[overhang_mask]))
       
       analysis = {
           'overhang_angles': angles,
           'support_required': overhang_mask,
           'support_volume': support_volume,
           'problematic_regions': self._identify_problematic_regions(angles, face_areas)
       }
       
       self._cache['printability'] = analysis
       return analysis

   def _identify_problematic_regions(self,
                                   angles: npt.NDArray[np.float64],
                                   areas: npt.NDArray[np.float64]
                                   ) -> List[Dict[str, Any]]:
       """Identify regions that might be problematic for printing"""
       problems = []
       
       # Check for severe overhangs
       severe_overhangs = angles > np.radians(60)
       if np.any(severe_overhangs):
           problems.append({
               'type': 'severe_overhang',
               'locations': np.where(severe_overhangs)[0],
               'severity': np.max(angles[severe_overhangs])
           })
           
       # Check for large unsupported areas
       large_areas = areas > np.mean(areas) * 3
       if np.any(large_areas & (angles > np.radians(30))):
           problems.append({
               'type': 'large_unsupported_area',
               'locations': np.where(large_areas & (angles > np.radians(30)))[0],
               'severity': np.max(areas[large_areas & (angles > np.radians(30))])
           })
           
       return problems

   def _build_segmentation_graph(self,
                               analysis_data: Dict,
                               params: SegmentationParams) -> nx.Graph:
       """Build weighted graph for segmentation"""
       graph = nx.Graph()
       vertices = self.mesh.vertices
       faces = self.mesh.faces
       
       # Add nodes with features
       for i, vertex in enumerate(vertices):
           graph.add_node(i, position=vertex)
           
       # Add edges with weights
       edges = set()
       for face in faces:
           for i in range(3):
               v1, v2 = face[i], face[(i+1)%3]
               edge = tuple(sorted([v1, v2]))
               if edge not in edges:
                   edges.add(edge)
                   
                   # Compute edge weight using multiple criteria
                   weight = self._compute_edge_weight(
                       edge,
                       analysis_data,
                       params
                   )
                   
                   graph.add_edge(v1, v2, weight=weight)
                   
       return graph

   def _compute_edge_weight(self,
                          edge: Tuple[int, int],
                          analysis_data: Dict,
                          params: SegmentationParams) -> float:
       """Compute weighted edge cost"""
       v1, v2 = edge
       
       # Get vertex positions
       p1 = self.mesh.vertices[v1]
       p2 = self.mesh.vertices[v2]
       
       # Compute distance weight
       distance = np.linalg.norm(p2 - p1)
       distance_weight = np.exp(-distance / self.mesh.compute_metadata().bounding_box[1].max())
       
       # Compute normal similarity
       n1 = self.mesh.get_vertex_normals()[v1]
       n2 = self.mesh.get_vertex_normals()[v2]
       normal_weight = 1 - abs(np.dot(n1, n2))
       
       # Compute curvature weight
       curvature_diff = abs(analysis_data['curvature'][v1] - 
                          analysis_data['curvature'][v2])
       curvature_weight = np.exp(-curvature_diff)
       
       # Compute feature weight
       feature_weight = self._compute_feature_weight(
           v1, v2, analysis_data['aesthetic']
       )
       
       # Compute structural weight
       structural_weight = self._compute_structural_weight(
           v1, v2, analysis_data['structural']
       )
       
       # Combine weights
       total_weight = (
           distance_weight * 0.2 +
           normal_weight * 0.2 +
           curvature_weight * 0.2 +
           feature_weight * params.aesthetic_priority +
           structural_weight * params.structural_priority
       )
       
       return total_weight

   def _compute_feature_weight(self,
                             v1: int,
                             v2: int,
                             aesthetic_data: Dict) -> float:
       """Compute weight based on aesthetic features"""
       feature_weight = 0.0
       
       # Check if vertices are part of important features
       for feature_type, vertices in aesthetic_data.items():
           if v1 in vertices or v2 in vertices:
               if feature_type == 'sharp_edges':
                   feature_weight += 0.8
               elif feature_type == 'symmetry_points':
                   feature_weight += 0.6
               elif feature_type == 'pattern_points':
                   feature_weight += 0.4
                   
       return min(feature_weight, 1.0)

   def _compute_structural_weight(self,
                                v1: int,
                                v2: int,
                                structural_data: Dict) -> float:
       """Compute weight based on structural importance"""
       # Get stress values
       stress1 = structural_data['von_mises'][v1]
       stress2 = structural_data['von_mises'][v2]
       
       # Higher weight for high stress gradient
       stress_gradient = abs(stress1 - stress2)
       stress_weight = np.exp(-stress_gradient / structural_data['max_stress'])
       
       return stress_weight

   def _spectral_segmentation(self,
                            graph: nx.Graph,
                            target_count: int) -> Dict[int, Set[int]]:
       """Perform spectral clustering on mesh"""
       # Convert graph to adjacency matrix
       adjacency = nx.adjacency_matrix(graph).toarray()
       
       # Compute Laplacian
       degree = np.diag(np.sum(adjacency, axis=1))
       # Compute Laplacian
       degree = np.diag(np.sum(adjacency, axis=1))
       laplacian = degree - adjacency
       
       # Perform spectral clustering
       clustering = SpectralClustering(
           n_clusters=target_count,
           affinity='precomputed',
           random_state=42
       ).fit(adjacency)
       
       # Convert to segment format
       segments = {}
       for i in range(target_count):
           segments[i] = set(np.where(clustering.labels_ == i)[0])
           
       return segments

   def _feature_based_segmentation(self, analysis_data: Dict) -> Dict[int, Set[int]]:
       """Segment mesh based on geometric features"""
       features = analysis_data['aesthetic']
       
       # Combine different feature types
       feature_points = set()
       for feature_type, points in features.items():
           if isinstance(points, set):
               feature_points.update(points)
               
       # Build feature graph
       feature_graph = nx.Graph()
       
       # Add nodes and edges based on feature proximity
       points = list(feature_points)
       tree = KDTree(self.mesh.vertices[points])
       
       for i, point_idx in enumerate(points):
           # Find nearby feature points
           neighbors = tree.query_ball_point(
               self.mesh.vertices[point_idx],
               r=self.mesh.compute_metadata().bounding_box[1].max() * 0.1
           )
           
           for neighbor in neighbors:
               if neighbor != i:
                   feature_graph.add_edge(
                       point_idx,
                       points[neighbor],
                       weight=np.linalg.norm(
                           self.mesh.vertices[point_idx] -
                           self.mesh.vertices[points[neighbor]]
                       )
                   )
                   
       # Perform community detection
       communities = nx.community.greedy_modularity_communities(feature_graph)
       
       # Convert to segments
       segments = {}
       for i, community in enumerate(communities):
           segments[i] = set(community)
           
       return segments

   def _optimize_segmentation_combination(self,
                                        segmentations: List[Tuple[str, Dict[int, Set[int]]]],
                                        analysis_data: Dict,
                                        params: SegmentationParams) -> Dict[int, Set[int]]:
       """Combine and optimize multiple segmentation approaches"""
       # Initialize consensus matrix
       n_vertices = len(self.mesh.vertices)
       consensus = np.zeros((n_vertices, n_vertices))
       
       # Build consensus matrix
       for seg_type, segmentation in segmentations:
           # Convert segmentation to matrix form
           seg_matrix = np.zeros((n_vertices, n_vertices))
           for segment in segmentation.values():
               for v1 in segment:
                   for v2 in segment:
                       seg_matrix[v1, v2] = 1
                       
           # Add to consensus with weighting
           if seg_type == 'spectral':
               consensus += seg_matrix * 0.4
           elif seg_type == 'feature':
               consensus += seg_matrix * 0.3
           elif seg_type == 'symmetry':
               consensus += seg_matrix * 0.3
               
       # Normalize consensus
       consensus /= len(segmentations)
       
       # Perform final clustering on consensus matrix
       final_clustering = SpectralClustering(
           n_clusters=len(segmentations[0][1]),
           affinity='precomputed',
           random_state=42
       ).fit(consensus)
       
       # Convert to segments
       final_segments = {}
       for i in range(len(segmentations[0][1])):
           final_segments[i] = set(np.where(final_clustering.labels_ == i)[0])
           
       return final_segments

   def _refine_segmentation(self,
                          segments: Dict[int, Set[int]],
                          analysis_data: Dict,
                          params: SegmentationParams) -> Dict[int, Set[int]]:
       """Refine segmentation through iterative optimization"""
       current_segments = segments.copy()
       
       for iteration in range(params.max_iterations):
           changes = 0
           
           # Find boundary vertices
           boundaries = self._find_boundary_vertices(current_segments)
           
           # Optimize each boundary vertex
           for vertex in boundaries:
               # Get current and neighboring segments
               current_seg = self._find_vertex_segment(vertex, current_segments)
               neighbor_segs = self._get_adjacent_segments(vertex, current_segments)
               
               # Find optimal segment assignment
               best_seg = self._evaluate_vertex_assignment(
                   vertex,
                   current_seg,
                   neighbor_segs,
                   analysis_data,
                   params
               )
               
               # Update if better assignment found
               if best_seg != current_seg:
                   current_segments[current_seg].remove(vertex)
                   current_segments[best_seg].add(vertex)
                   changes += 1
                   
           # Check convergence
           if changes / len(boundaries) < params.convergence_threshold:
               break
               
       return current_segments

   def _find_boundary_vertices(self, segments: Dict[int, Set[int]]) -> Set[int]:
       """Find vertices at segment boundaries"""
       boundaries = set()
       
       # Build vertex-to-segment mapping
       vertex_segments = {}
       for seg_id, vertices in segments.items():
           for vertex in vertices:
               vertex_segments[vertex] = seg_id
               
       # Check each vertex's neighbors
       for vertex in vertex_segments:
           neighbors = self._get_vertex_neighbors(vertex)
           
           # If any neighbor is in different segment, this is a boundary
           for neighbor in neighbors:
               if (neighbor in vertex_segments and 
                   vertex_segments[neighbor] != vertex_segments[vertex]):
                   boundaries.add(vertex)
                   break
                   
       return boundaries

   def _get_vertex_neighbors(self, vertex: int) -> Set[int]:
       """Get neighboring vertices"""
       neighbors = set()
       
       # Search faces for vertex
       for face in self.mesh.faces:
           if vertex in face:
               # Add other vertices in face
               neighbors.update(v for v in face if v != vertex)
               
       return neighbors

   def _evaluate_vertex_assignment(self,
                                 vertex: int,
                                 current_segment: int,
                                 neighbor_segments: Set[int],
                                 analysis_data: Dict,
                                 params: SegmentationParams) -> int:
       """Evaluate best segment assignment for vertex"""
       best_segment = current_segment
       best_score = self._compute_assignment_score(
           vertex,
           current_segment,
           analysis_data,
           params
       )
       
       # Evaluate each neighboring segment
       for segment in neighbor_segments:
           score = self._compute_assignment_score(
               vertex,
               segment,
               analysis_data,
               params
           )
           
           if score > best_score:
               best_score = score
               best_segment = segment
               
       return best_segment

   def _compute_assignment_score(self,
                               vertex: int,
                               segment: int,
                               analysis_data: Dict,
                               params: SegmentationParams) -> float:
       """Compute score for assigning vertex to segment"""
       # Initialize score components
       geometric_score = self._compute_geometric_score(vertex, segment)
       structural_score = self._compute_structural_score(vertex, segment, analysis_data)
       aesthetic_score = self._compute_aesthetic_score(vertex, segment, analysis_data)
       
       # Combine scores with weights
       total_score = (
           geometric_score +
           params.structural_priority * structural_score +
           params.aesthetic_priority * aesthetic_score
       )
       
       return total_score

   def _create_components(self, segments: Dict[int, Set[int]]) -> List[Component]:
       """Create component objects from segmentation"""
       components = []
       
       for segment_id, vertices in segments.items():
           # Extract submesh
           submesh = self._extract_submesh(vertices)
           
           # Create component
           component = Component(
               mesh=submesh,
               component_id=f"component_{segment_id}"
           )
           
           # Compute component metadata
           component._compute_metadata()
           
           components.append(component)
           
       return components

   def _extract_submesh(self, vertices: Set[int]) -> Mesh:
       """Extract submesh for given vertices"""
       # Create vertex mapping
       old_to_new = {old: new for new, old in enumerate(sorted(vertices))}
       
       # Get new vertices
       new_vertices = self.mesh.vertices[list(vertices)]
       
       # Get faces that use these vertices
       new_faces = []
       for face in self.mesh.faces:
           if all(v in vertices for v in face):
               new_face = [old_to_new[v] for v in face]
               new_faces.append(new_face)
               
       new_faces = np.array(new_faces)
       
       # Create new mesh
       return Mesh(new_vertices, new_faces)

   def _generate_connection_points(self, params: SegmentationParams):
       """Generate connection points between components"""
       # Build adjacency graph
       self._build_adjacency_graph()
       
       # For each adjacent pair
       for i, comp1 in enumerate(self.components):
           for j, comp2 in enumerate(self.components[i+1:], i+1):
               if not self._check_adjacency(comp1, comp2):
                   continue
                   
               # Analyze interface
               interface = self._compute_interface_region(comp1, comp2)
               interface_data = self._analyze_interface(interface, comp1, comp2)
               
               # Generate connection points
               connections = self._generate_optimal_connections(
                   interface_data,
                   comp1,
                   comp2,
                   params
               )
               
               # Assign connections
               self._assign_connections(connections, comp1, comp2)

   def _compute_interface_region(self,
                               comp1: Component,
                               comp2: Component) -> Dict[str, Any]:
       """Compute interface region between components"""
       # Find close vertices
       tree = KDTree(comp1.mesh.vertices)
       distances, indices = tree.query(comp2.mesh.vertices)
       
       # Get interface vertices
       interface_vertices1 = set()
       interface_vertices2 = set()
       
       for v2, (v1, dist) in enumerate(zip(indices, distances)):
           if dist < self.ADJACENCY_THRESHOLD:
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

   def _generate_optimal_connections(self,
                                  interface: Dict[str, Any],
                                  comp1: Component,
                                  comp2: Component,
                                  params: SegmentationParams) -> List[ConnectionPoint]:
       """Generate optimal connection points for interface"""
       connections = []
       
       # Determine number of connections needed
       n_connections = self._determine_connection_count(interface)
       
       # Generate connection points
       for i in range(n_connections):
           # Find optimal position
           position = self._find_optimal_connection_position(
               interface,
               connections,
               params
           )
           
           # Determine connection type
           conn_type = self._determine_connection_type(
               position,
               interface,
               comp1,
               comp2
           )
           
           # Create connection
           connection = ConnectionPoint(
               position=position,
               normal=interface['normal'],
               connection_type=conn_type,
               geometry=self._generate_connection_geometry(
                   position,
                   interface,
                   conn_type
               )
           )
           
           connections.append(connection)
           
       return connections

   def _validate_decomposition(self) -> bool:
       """Validate complete decomposition"""
       try:
           validations = {
               'structural': self._validate_structural_integrity(),
               'printability': self._validate_printability(),
               'connections': self._validate_connections(),
               'aesthetics': self._validate_aesthetics()
           }
           
           if not all(validations.values()):
               self._logger.warning("Validation failed: " + 
                                  str({k: v for k, v in validations.items() 
                                      if not v}))
               
           return all(validations.values())
           
       except Exception as e:
           self._logger.error(f"Validation error: {str(e)}")
           return False

   def _validate_structural_integrity(self) -> bool:
       """Validate structural integrity of decomposition"""
       try:
           # Check each component
           for component in self.components:
               # Analyze stress distribution
               stress_analysis = self.structural_analyzer.analyze_structural_integrity(
                   component.mesh
               )
               
               # Check maximum stress
               if stress_analysis['max_stress'] > self.MAX_CONNECTION_STRESS:
                   return False
                   
               # Check stability
               if not stress_analysis['stability_score'] > 0.5:
                   return False
                   
           # Check connections
           for comp in self.components:
               for conn in comp.connection_points:
                   if not self._validate_connection_strength(conn):
                       return False
                       
           return True
           
       except Exception as e:
           self._logger.error(f"Structural validation error: {str(e)}")
           return False

   def _validate_printability(self) -> bool:
       """Validate printability of decomposition"""
       try:
           for component in self.components:
               # Check overhangs
               printability = component.analyze_printability()
               if printability['max_overhang'] > self.params.max_overhang:
                   return False
                   
               # Check support requirements
               if printability['support_volume'] > 0.3 * component.metadata.volume:
                   return False
                   
               # Check feature sizes
               if not self._validate_component_features(component):
                   return False
                   
           return True
           
       except Exception as e:
           self._logger.error(f"Printability validation error: {str(e)}")
           return False

   def _validate_connections(self) -> bool:
       """Validate connection points"""
       try:
           # Check each connection
           for comp in self.components:
               for conn in comp.connection_points:
                   # Validate geometry
                   if not self._validate_connection_geometry(conn):
                       return False
                       
                   # Validate strength
                   if not self._validate_connection_strength(conn):
                       return False
                       
                   # Validate printability
                   if not self._validate_connection_printability(conn):
                       return False
                       
           # Validate global connection layout
           return self._validate_global_connections()
           
       except Exception as e:
           self._logger.error(f"Connection validation error: {str(e)}")
           return False

   def _validate_aesthetics(self) -> bool:
       """Validate aesthetic preservation"""
       try:
           # Get original aesthetic features
           original_features = self.aesthetic_analyzer.identify_features()
           
            # Check feature preservation
           for feature_type, features in original_features.items():
               if not self._validate_feature_preservation(
                   feature_type, features
               ):
                   return False
                   
           # Validate symmetry preservation
           if not self._validate_symmetry_preservation():
               return False
               
           # Validate pattern preservation
           if not self._validate_pattern_preservation():
               return False
               
           return True
           
       except Exception as e:
           self._logger.error(f"Aesthetic validation error: {str(e)}")
           return False

   def _validate_feature_preservation(self,
                                   feature_type: str,
                                   features: Set[int]) -> bool:
       """Validate preservation of specific feature type"""
       # Map original features to components
       feature_mapping = self._map_features_to_components(features)
       
       # Check each feature is preserved within a single component
       for feature_vertices in feature_mapping.values():
           if not self._check_feature_integrity(feature_vertices):
               return False
               
       return True

   def _map_features_to_components(self, features: Set[int]) -> Dict[int, Set[int]]:
       """Map original features to new components"""
       feature_mapping = {}
       
       for vertex in features:
           # Find component containing this vertex
           component_id = self._find_component_for_vertex(vertex)
           
           if component_id not in feature_mapping:
               feature_mapping[component_id] = set()
               
           feature_mapping[component_id].add(vertex)
           
       return feature_mapping

   def save_decomposition(self, output_dir: Path):
       """Save decomposition results"""
       try:
           output_dir.mkdir(parents=True, exist_ok=True)
           
           # Save each component
           for i, component in enumerate(self.components):
               component_dir = output_dir / f"component_{i}"
               component_dir.mkdir(exist_ok=True)
               
               # Save mesh
               component.mesh.trimesh.export(
                   str(component_dir / "mesh.stl")
               )
               
               # Save metadata
               self._save_component_metadata(
                   component,
                   component_dir / "metadata.json"
               )
               
               # Save connection information
               self._save_connection_data(
                   component,
                   component_dir / "connections.json"
               )
               
           # Save global decomposition data
           self._save_decomposition_data(output_dir / "decomposition.json")
           
       except Exception as e:
           self._logger.error(f"Failed to save decomposition: {str(e)}")
           raise SegmentationError(f"Failed to save decomposition: {str(e)}")