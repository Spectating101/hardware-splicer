# File: src/decomposition/analysis/aesthetic.py
# Purpose: Handles aesthetic feature analysis and preservation
# Dependencies: Core modules, numpy, scipy
# Priority: High - Critical for preserving design intent

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from sklearn.cluster import DBSCAN
from scipy.spatial import cKDTree
import logging
from dataclasses import dataclass
from enum import Enum

from ..core.mesh import Mesh, FeatureType
from ..core.component import Component

class AestheticError(Exception):
   """Custom exception for aesthetic analysis errors"""
   pass

@dataclass
class SurfaceQualityMetrics:
   """Surface quality analysis metrics"""
   flatness: float
   roughness: float 
   feature_size: float
   printability: float
   detail_preservation: float

class PatternType(Enum):
   """Types of detected patterns"""
   REGULAR = "regular"       # Evenly spaced repeating elements
   SYMMETRIC = "symmetric"   # Mirror symmetry patterns  
   RADIAL = "radial"        # Circular/radial patterns
   LINEAR = "linear"        # Linear arrangements
   GRID = "grid"           # Grid-like patterns

class AestheticAnalyzer:
   """Advanced aesthetic feature analysis and preservation"""
   
   def __init__(self, mesh: Mesh):
       self.mesh = mesh
       self._logger = logging.getLogger(__name__)
       
       # Analysis parameters
       self.FEATURE_SENSITIVITY = 0.7
       self.PATTERN_THRESHOLD = 0.85  
       self.SYMMETRY_TOLERANCE = 0.01
       self.DETAIL_SCALE = 0.5  # mm
       self.MIN_PATTERN_SIZE = 3  # Minimum vertices for pattern
       self.SURFACE_CONTINUITY_THRESHOLD = 0.7
       self.MIN_SURFACE_REGION = 100  # Minimum vertices for continuous surface
       
       # Initialize caches
       self._cache = {
           'feature_map': None,
           'pattern_data': None, 
           'symmetry_data': None,
           'detail_regions': None,
           'surface_quality': None,
           'structural_importance': None,
           'curvature': None
       }

   def identify_features(self) -> Dict[str, Set[int]]:
       """Identify aesthetic features"""
       if self._cache['feature_map'] is not None:
           return self._cache['feature_map']
           
       try:
           features = {
               'surface_details': self._detect_surface_details(),
               'patterns': self._detect_patterns(),
               'symmetrical': self._identify_symmetrical_features(),
               'decorative': self._detect_decorative_elements(),
               'continuous_surfaces': self._find_continuous_surfaces()
           }
           
           # Add analysis metadata
           for feature_type, feature_set in features.items():
               if feature_set:
                   self._logger.info(
                       f"Detected {len(feature_set)} {feature_type}"
                   )
                   
           self._cache['feature_map'] = features
           return features
           
       except Exception as e:
           self._logger.error(f"Feature identification failed: {str(e)}")
           raise AestheticError(f"Feature identification failed: {str(e)}")

   def analyze_surface_quality(self) -> Dict[str, npt.NDArray[np.float64]]:
       """Analyze surface quality for printing considerations"""
       if self._cache['surface_quality'] is not None:
           return self._cache['surface_quality']

       try:
           vertices = self.mesh.vertices
           normals = self.mesh.get_vertex_normals()
           
           quality_metrics = np.zeros(len(vertices), dtype=[
               ('surface_quality', float),
               ('printability', float),
               ('detail_preservation', float)
           ])
           
           # Analyze each vertex
           for i in range(len(vertices)):
               neighbors = self._get_vertex_neighbors(i)
               local_vertices = vertices[neighbors]
               
               metrics = self._analyze_local_surface_quality(
                   i, local_vertices, normals[neighbors]
               )
               
               quality_metrics[i] = (
                   metrics.flatness * metrics.roughness,
                   metrics.printability,
                   metrics.detail_preservation
               )
               
           critical_regions = self._identify_critical_quality_regions(
               quality_metrics['surface_quality'],
               quality_metrics['printability'],
               quality_metrics['detail_preservation']
           )
           
           quality_data = {
               'metrics': quality_metrics,
               'critical_regions': critical_regions,
               'average_quality': np.mean(quality_metrics['surface_quality']),
               'min_quality': np.min(quality_metrics['surface_quality'])
           }
           
           self._cache['surface_quality'] = quality_data
           return quality_data
           
       except Exception as e:
           self._logger.error(f"Surface quality analysis failed: {str(e)}")
           raise AestheticError(f"Surface quality analysis failed: {str(e)}")

   def recommend_split_regions(self) -> List[Dict[str, Any]]:
       """Recommend regions for splitting based on aesthetic considerations"""
       try:
           features = self.identify_features()
           quality_data = self.analyze_surface_quality()
           
           recommendations = []
           
           # Consider different types of splits
           pattern_splits = self._find_pattern_boundaries(features['patterns'])
           symmetry_splits = self._find_symmetry_splits(features['symmetrical'])
           detail_splits = self._find_detail_preservation_splits(
               features['surface_details'],
               quality_data
           )
           
           # Combine and score all splits
           for split_type, splits in [
               ('pattern', pattern_splits),
               ('symmetry', symmetry_splits),
               ('detail', detail_splits)
           ]:
               for split in splits:
                   recommendation = {
                       'type': split_type,
                       'region': split,
                       'importance': self._compute_split_importance(
                           split, quality_data
                       ),
                       'constraints': self._compute_split_constraints(split)
                   }
                   recommendations.append(recommendation)
                   
           # Sort by importance
           return sorted(
               recommendations,
               key=lambda x: x['importance'],
               reverse=True
           )
           
       except Exception as e:
           self._logger.error(f"Split recommendation failed: {str(e)}")
           raise AestheticError(f"Split recommendation failed: {str(e)}")

   def validate_decomposition(self,
                            components: List[Component]) -> Dict[str, Any]:
       """Validate decomposition from aesthetic perspective"""
       try:
           # Compute validation metrics
           validation = {
               'pattern_preservation': self._validate_pattern_preservation(
                   components
               ),
               'symmetry_preservation': self._validate_symmetry_preservation(
                   components
               ),
               'detail_preservation': self._validate_detail_preservation(
                   components
               ),
               'surface_quality': self._validate_surface_quality(
                   components
               )
           }
           
           # Compute overall score
           validation['aesthetic_score'] = self._compute_aesthetic_score(
               validation
           )
           
           # Find problematic regions
           validation['critical_regions'] = self._identify_critical_regions(
               validation
           )
           
           # Add validation summary
           validation['summary'] = self._generate_validation_summary(
               validation
           )
           
           return validation
           
       except Exception as e:
           self._logger.error(f"Decomposition validation failed: {str(e)}")
           raise AestheticError(f"Decomposition validation failed: {str(e)}")

   def _detect_surface_details(self) -> Set[int]:
       """Detect detailed surface features"""
       try:
           # Get required data
           normals = self.mesh.get_vertex_normals()
           curvature = self._get_curvature()
           
           # Initialize detail metric
           n_vertices = len(self.mesh.vertices)
           detail_metric = np.zeros(n_vertices)
           
           # Compute metrics for each vertex
           for i in range(n_vertices):
               neighbors = self._get_vertex_neighbors(i)
               if not neighbors:
                   continue
                   
               # Normal variation
               normal_variation = self._compute_normal_variation(
                   i, neighbors, normals
               )
               
               # Curvature contribution
               curvature_score = self._compute_curvature_score(
                   i, neighbors, curvature
               )
               
               # Feature size contribution
               size_score = self._compute_feature_size_score(
                   i, neighbors
               )
               
               # Combine metrics
               detail_metric[i] = (
                   0.4 * normal_variation +
                   0.4 * curvature_score +
                   0.2 * size_score
               )
               
           # Threshold to find detailed regions
           threshold = np.percentile(detail_metric, 90)
           detailed_vertices = set(np.where(detail_metric > threshold)[0])
           
           # Clean up isolated vertices
           return self._remove_isolated_vertices(detailed_vertices)
           
       except Exception as e:
           self._logger.error(f"Surface detail detection failed: {str(e)}")
           raise AestheticError(f"Surface detail detection failed: {str(e)}")

   def _detect_patterns(self) -> Set[int]:
       """Detect repeating geometric patterns"""
       if self._cache['pattern_data'] is not None:
           return self._cache['pattern_data']['vertices']
           
       try:
           vertices = self.mesh.vertices
           pattern_features = set()
           
           # Compute local features
           local_features = self._compute_local_features()
           
           # Cluster similar features
           clustering = DBSCAN(
               eps=self.PATTERN_THRESHOLD,
               min_samples=self.MIN_PATTERN_SIZE
           ).fit(local_features)
           
           # Process clusters
           labels = clustering.labels_
           unique_labels = set(labels) - {-1}  # Exclude noise
           
           for label in unique_labels:
               cluster_vertices = np.where(labels == label)[0]
               
               # Validate pattern
               if self._validate_pattern_cluster(cluster_vertices):
                   pattern_features.update(cluster_vertices)
                   
           # Store pattern data
           self._cache['pattern_data'] = {
               'vertices': pattern_features,
               'types': self._classify_patterns(pattern_features),
               'relationships': self._analyze_pattern_relationships(
                   pattern_features
               )
           }
           
           return pattern_features
           
       except Exception as e:
           self._logger.error(f"Pattern detection failed: {str(e)}")
           raise AestheticError(f"Pattern detection failed: {str(e)}")

   def _compute_local_features(self) -> npt.NDArray[np.float64]:
       """Compute local geometric features for pattern detection"""
       try:
           vertices = self.mesh.vertices
           normals = self.mesh.get_vertex_normals()
           features = []
           
           for i in range(len(vertices)):
               neighbors = self._get_vertex_neighbors(i)
               if not neighbors:
                   continue
                   
               # Compute feature vector components
               shape_features = self._compute_shape_distribution(
                   vertices[neighbors]
               )
               normal_features = self._compute_normal_distribution(
                   normals[neighbors]
               )
               curvature_features = self._compute_curvature_features(
                   i, vertices[neighbors]
               )
               
               # Combine features
               feature_vector = np.concatenate([
                   shape_features,
                   normal_features,
                   curvature_features
               ])
               
               features.append(feature_vector)
               
           return np.array(features)
           
       except Exception as e:
           self._logger.error(f"Local feature computation failed: {str(e)}")
           raise AestheticError(f"Local feature computation failed: {str(e)}")

   def _compute_shape_distribution(self,
                                 vertices: npt.NDArray[np.float64]
                                 ) -> npt.NDArray[np.float64]:
       """Compute shape distribution features for local region"""
       try:
           # Compute pairwise distances
           n_points = len(vertices)
           distances = []
           
           for i in range(n_points):
               for j in range(i + 1, n_points):
                   distances.append(
                       np.linalg.norm(vertices[i] - vertices[j])
                   )
                   
           distances = np.array(distances)
           
           # Compute distribution features
           if len(distances) > 0:
               hist, _ = np.histogram(
                   distances,
                   bins='auto',
                   density=True
               )
               return hist
           else:
               return np.zeros(10)  # Default histogram size
               
       except Exception as e:
           self._logger.error(
               f"Shape distribution computation failed: {str(e)}"
           )
           raise AestheticError(
               f"Shape distribution computation failed: {str(e)}"
           )

   def _compute_normal_distribution(self,
                                  normals: npt.NDArray[np.float64]
                                  ) -> npt.NDArray[np.float64]:
       """Compute normal distribution features"""
       try:
           # Compute pairwise normal similarities
           n_normals = len(normals)
           similarities = []
           
           for i in range(n_normals):
               for j in range(i + 1, n_normals):
                   similarities.append(
                       abs(np.dot(normals[i], normals[j]))
                   )
                   
           similarities = np.array(similarities)
           
           if len(similarities) > 0:
               return np.array([
                   np.mean(similarities),
                   np.std(similarities),
                   np.min(similarities),
                   np.max(similarities),
                   np.median(similarities)
               ])
           else:
               return np.zeros(5)
               
       except Exception as e:
           self._logger.error(
               f"Normal distribution computation failed: {str(e)}"
           )
           raise AestheticError(
               f"Normal distribution computation failed: {str(e)}"
           )

   def _compute_curvature_features(self,
                                 vertex_idx: int,
                                 local_vertices: npt.NDArray[np.float64]
                                 ) -> npt.NDArray[np.float64]:
       """Compute curvature-based features"""
       try:
           curvature = self._get_curvature()
           local_curvature = curvature[vertex_idx]
           
           # Get vertex and its normal
           vertex = self.mesh.vertices[vertex_idx]
           normal = self.mesh.get_vertex_normals()[vertex_idx]
           
           # Project vertices to tangent plane
           local_centered = local_vertices - vertex
           projected = local_centered - np.outer(
               np.dot(local_centered, normal),
               normal
           )
           
           # Compute features
           gaussian_curvature = self._compute_gaussian_curvature(
               vertex_idx,
               projected
           )
           
           mean_curvature = self._compute_mean_curvature(
               vertex_idx,
               projected
           )
           
           return np.array([
               gaussian_curvature,
               mean_curvature,
               np.mean(local_curvature),
               np.std(local_curvature),
               np.max(abs(local_curvature))
           ])
           
       except Exception as e:
           self._logger.error(
               f"Curvature feature computation failed: {str(e)}"
           )
           raise AestheticError(
               f"Curvature feature computation failed: {str(e)}"
            )

   def _get_curvature(self) -> npt.NDArray[np.float64]:
       """Get or compute mesh curvature"""
       if self._cache['curvature'] is None:
           try:
               self._cache['curvature'] = self.mesh.analyze_curvature()
           except Exception as e:
               self._logger.error(f"Curvature computation failed: {str(e)}")
               raise AestheticError(f"Curvature computation failed: {str(e)}")
               
       return self._cache['curvature']

   def _compute_gaussian_curvature(self,
                                 vertex_idx: int,
                                 projected_vertices: npt.NDArray[np.float64]
                                 ) -> float:
       """Compute Gaussian curvature at vertex"""
       try:
           # Compute angles
           angles = self._compute_corner_angles(projected_vertices)
           angle_sum = np.sum(angles)
           
           # Compute local area
           area = self._compute_local_area(projected_vertices)
           
           if area > 0:
               return (2 * np.pi - angle_sum) / area
           else:
               return 0.0
               
       except Exception as e:
           self._logger.error(
               f"Gaussian curvature computation failed: {str(e)}"
           )
           raise AestheticError(
               f"Gaussian curvature computation failed: {str(e)}"
           )

   def _compute_corner_angles(self,
                            vertices: npt.NDArray[np.float64]
                            ) -> npt.NDArray[np.float64]:
       """Compute corner angles for vertex ring"""
       try:
           n_vertices = len(vertices)
           angles = np.zeros(n_vertices)
           
           for i in range(n_vertices):
               prev = vertices[i-1]
               curr = vertices[i]
               next_v = vertices[(i+1) % n_vertices]
               
               v1 = prev - curr
               v2 = next_v - curr
               
               # Normalize vectors
               v1 = v1 / np.linalg.norm(v1)
               v2 = v2 / np.linalg.norm(v2)
               
               # Compute angle
               angle = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
               angles[i] = angle
               
           return angles
           
       except Exception as e:
           self._logger.error(f"Corner angle computation failed: {str(e)}")
           raise AestheticError(f"Corner angle computation failed: {str(e)}")

   def _compute_local_area(self,
                         vertices: npt.NDArray[np.float64]) -> float:
       """Compute area of local vertex region"""
       try:
           # Compute area using triangulation
           n_vertices = len(vertices)
           area = 0.0
           
           for i in range(1, n_vertices - 1):
               v1 = vertices[i] - vertices[0]
               v2 = vertices[i+1] - vertices[0]
               area += 0.5 * np.linalg.norm(np.cross(v1, v2))
               
           return area
           
       except Exception as e:
           self._logger.error(f"Local area computation failed: {str(e)}")
           raise AestheticError(f"Local area computation failed: {str(e)}")

   def _compute_mean_curvature(self,
                             vertex_idx: int,
                             projected_vertices: npt.NDArray[np.float64]
                             ) -> float:
       """Compute mean curvature at vertex"""
       try:
           # Get vertex normal
           normal = self.mesh.get_vertex_normals()[vertex_idx]
           
           # Compute Laplacian
           n_neighbors = len(projected_vertices)
           if n_neighbors < 3:
               return 0.0
               
           laplacian = np.zeros(3)
           weights = self._compute_vertex_weights(projected_vertices)
           
           for i, neighbor in enumerate(projected_vertices):
               laplacian += weights[i] * (neighbor - self.mesh.vertices[vertex_idx])
               
           # Project onto normal
           mean_curvature = 0.5 * np.dot(laplacian, normal)
           
           return mean_curvature
           
       except Exception as e:
           self._logger.error(f"Mean curvature computation failed: {str(e)}")
           raise AestheticError(f"Mean curvature computation failed: {str(e)}")

   def _compute_vertex_weights(self,
                             vertices: npt.NDArray[np.float64]
                             ) -> npt.NDArray[np.float64]:
       """Compute vertex weights for mean curvature computation"""
       try:
           n_vertices = len(vertices)
           weights = np.zeros(n_vertices)
           
           # Compute cotangent weights
           for i in range(n_vertices):
               prev = vertices[i-1]
               curr = vertices[i]
               next_v = vertices[(i+1) % n_vertices]
               
               # Compute cotangents
               cot_alpha = self._compute_cotangent(prev, curr, next_v)
               cot_beta = self._compute_cotangent(next_v, curr, prev)
               
               weights[i] = 0.5 * (cot_alpha + cot_beta)
               
           return weights
           
       except Exception as e:
           self._logger.error(f"Vertex weight computation failed: {str(e)}")
           raise AestheticError(f"Vertex weight computation failed: {str(e)}")

   def _compute_cotangent(self,
                         p1: npt.NDArray[np.float64],
                         p2: npt.NDArray[np.float64],
                         p3: npt.NDArray[np.float64]) -> float:
       """Compute cotangent of angle at p2"""
       try:
           v1 = p1 - p2
           v2 = p3 - p2
           
           # Normalize vectors
           v1 = v1 / np.linalg.norm(v1)
           v2 = v2 / np.linalg.norm(v2)
           
           sin_theta = np.linalg.norm(np.cross(v1, v2))
           cos_theta = np.dot(v1, v2)
           
           if sin_theta != 0:
               return cos_theta / sin_theta
           else:
               return 0.0
               
       except Exception as e:
           self._logger.error(f"Cotangent computation failed: {str(e)}")
           raise AestheticError(f"Cotangent computation failed: {str(e)}")

   def _analyze_local_surface_quality(self,
                                    vertex_idx: int,
                                    local_vertices: npt.NDArray[np.float64],
                                    local_normals: npt.NDArray[np.float64]
                                    ) -> SurfaceQualityMetrics:
       """Analyze surface quality metrics for local region"""
       try:
           # Compute flatness
           flatness = self._compute_flatness(local_vertices, local_normals)
           
           # Compute roughness
           roughness = self._compute_roughness(local_vertices)
           
           # Compute feature size
           feature_size = self._compute_feature_size(
               vertex_idx,
               local_vertices
           )
           
           # Compute printability
           printability = self._compute_printability_metric(
               flatness,
               feature_size
           )
           
           # Compute detail preservation
           detail_preservation = self._compute_detail_preservation_metric(
               roughness,
               feature_size
           )
           
           return SurfaceQualityMetrics(
               flatness=flatness,
               roughness=roughness,
               feature_size=feature_size,
               printability=printability,
               detail_preservation=detail_preservation
           )
           
       except Exception as e:
           self._logger.error(
               f"Local surface quality analysis failed: {str(e)}"
           )
           raise AestheticError(
               f"Local surface quality analysis failed: {str(e)}"
           )

   def _identify_critical_quality_regions(self,
                                        surface_quality: npt.NDArray[np.float64],
                                        printability: npt.NDArray[np.float64],
                                        detail_preservation: npt.NDArray[np.float64]
                                        ) -> List[Dict[str, Any]]:
       """Identify regions with critical quality issues"""
       try:
           critical_regions = []
           
           # Check surface quality
           low_quality = np.where(surface_quality < 0.5)[0]
           if len(low_quality) > 0:
               critical_regions.append({
                   'type': 'low_surface_quality',
                   'vertices': set(low_quality),
                   'severity': 1 - np.mean(surface_quality[low_quality])
               })
               
           # Check printability
           low_printability = np.where(printability < 0.6)[0]
           if len(low_printability) > 0:
               critical_regions.append({
                   'type': 'low_printability',
                   'vertices': set(low_printability),
                   'severity': 1 - np.mean(printability[low_printability])
               })
               
           # Check detail preservation
           poor_detail = np.where(detail_preservation < 0.7)[0]
           if len(poor_detail) > 0:
               critical_regions.append({
                   'type': 'poor_detail_preservation',
                   'vertices': set(poor_detail),
                   'severity': 1 - np.mean(detail_preservation[poor_detail])
               })
               
           return critical_regions
           
       except Exception as e:
           self._logger.error(
               f"Critical region identification failed: {str(e)}"
           )
           raise AestheticError(
               f"Critical region identification failed: {str(e)}"
           )

   def _generate_validation_summary(self,
                                 validation_data: Dict[str, Any]
                                 ) -> Dict[str, Any]:
       """Generate summary of validation results"""
       try:
           summary = {
               'overall_score': validation_data['aesthetic_score'],
               'major_issues': [],
               'minor_issues': [],
               'recommendations': []
           }
           
           # Check individual metrics
           for metric, data in validation_data.items():
               if isinstance(data, dict) and 'score' in data:
                   if data['score'] < 0.6:
                       summary['major_issues'].append({
                           'type': metric,
                           'score': data['score'],
                           'details': data.get('details', '')
                       })
                   elif data['score'] < 0.8:
                       summary['minor_issues'].append({
                           'type': metric,
                           'score': data['score'],
                           'details': data.get('details', '')
                       })
                       
           # Generate recommendations
           summary['recommendations'] = self._generate_improvement_recommendations(
               validation_data
           )
           
           return summary
           
       except Exception as e:
           self._logger.error(
               f"Validation summary generation failed: {str(e)}"
           )
           raise AestheticError(
               f"Validation summary generation failed: {str(e)}"
           )

   def _generate_improvement_recommendations(self,
                                          validation_data: Dict[str, Any]
                                          ) -> List[Dict[str, Any]]:
       """Generate recommendations for improving decomposition"""
       try:
           recommendations = []
           
           # Check pattern preservation
           if validation_data['pattern_preservation']['score'] < 0.8:
               recommendations.append({
                   'type': 'pattern_preservation',
                   'priority': 'high' if validation_data['pattern_preservation']['score'] < 0.6 else 'medium',
                   'suggestion': 'Adjust decomposition to better preserve repeating patterns',
                   'affected_regions': validation_data['pattern_preservation'].get('affected_regions', [])
               })
               
           # Check symmetry preservation
           if validation_data['symmetry_preservation']['score'] < 0.8:
               recommendations.append({
                   'type': 'symmetry_preservation',
                   'priority': 'high' if validation_data['symmetry_preservation']['score'] < 0.6 else 'medium',
                   'suggestion': 'Maintain symmetry in decomposition',
                   'affected_regions': validation_data['symmetry_preservation'].get('affected_regions', [])
               })
               
           # Check surface quality
           if validation_data['surface_quality']['score'] < 0.8:
               recommendations.append({
                   'type': 'surface_quality',
                   'priority': 'medium',
                   'suggestion': 'Improve surface quality in critical regions',
                   'affected_regions': validation_data['surface_quality'].get('critical_regions', [])
               })
               
           return sorted(
               recommendations,
               key=lambda x: 0 if x['priority'] == 'high' else 1
           )
           
       except Exception as e:
           self._logger.error(
               f"Recommendation generation failed: {str(e)}"
           )
           raise AestheticError(
               f"Recommendation generation failed: {str(e)}"
           )