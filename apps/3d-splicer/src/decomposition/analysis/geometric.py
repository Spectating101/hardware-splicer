# File: src/decomposition/analysis/geometric.py
# Purpose: Advanced geometric analysis for mesh decomposition
# Dependencies: Mesh and Component classes, numpy, scipy
# Priority: High - Core analysis engine

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from scipy.spatial import ConvexHull, Delaunay
from scipy.cluster import hierarchy
from sklearn.decomposition import PCA
from sklearn.cluster import SpectralClustering
import networkx as nx
from ..core.mesh import Mesh, FeatureType
from ..core.component import Component

class GeometricAnalyzer:
   """Advanced geometric analysis for mesh decomposition"""
   
   def __init__(self, mesh: Mesh):
       self.mesh = mesh
       self._cache = {
           'convex_hull': None,
           'feature_edges': None,
           'curvature_map': None,
           'symmetry_data': None,
           'segmentation_graph': None,
           'feature_clusters': None
       }
       
       # Analysis parameters
       self.FEATURE_THRESHOLD = 0.7
       self.CURVATURE_THRESHOLD = 0.8
       self.SYMMETRY_TOLERANCE = 0.01
       self.MIN_SEGMENT_SIZE = 100  # vertices
       
   def find_natural_splits(self, 
                         feature_weight: float = 1.0,
                         curvature_weight: float = 1.0,
                         symmetry_weight: float = 1.0) -> List[Dict[str, Any]]:
       """Identify optimal splitting planes using multiple criteria"""
       
       # Get geometric features
       feature_edges = self._compute_feature_edges()
       curvature = self._compute_curvature_map()
       symmetry = self._detect_symmetry_planes()
       thickness = self.mesh._compute_thickness_distribution()
       
       # Build weighted feature graph
       graph = self._build_feature_graph(
           feature_edges,
           curvature,
           symmetry,
           thickness,
           feature_weight,
           curvature_weight,
           symmetry_weight
       )
       
       # Find optimal cuts
       cuts = self._find_optimal_cuts(graph)
       
       # Validate and refine cuts
       refined_cuts = []
       for cut in cuts:
           if self._validate_split_plane(cut['plane']):
               refined = self._refine_split_plane(
                   cut['plane'],
                   cut['features'],
                   cut['score']
               )
               refined_cuts.append(refined)
               
       return refined_cuts

   def _build_feature_graph(self,
                          feature_edges: Set[Tuple[int, int]],
                          curvature: npt.NDArray[np.float64],
                          symmetry: List[Dict],
                          thickness: npt.NDArray[np.float64],
                          w_feature: float,
                          w_curve: float,
                          w_sym: float) -> nx.Graph:
       """Build weighted graph representing mesh features"""
       
       graph = nx.Graph()
       vertices = self.mesh.vertices
       
       # Add nodes
       for i in range(len(vertices)):
           graph.add_node(i, position=vertices[i],
                         curvature=curvature[i],
                         thickness=thickness[i])
                         
       # Add feature edges
       for v1, v2 in feature_edges:
           weight = w_feature
           # Modify weight based on curvature
           weight *= (1 + abs(curvature[v1] - curvature[v2]))
           # Modify weight based on thickness
           weight *= (1 + abs(thickness[v1] - thickness[v2]))
           graph.add_edge(v1, v2, weight=weight)
           
       # Add symmetry planes influence
       for sym in symmetry:
           plane = sym['plane']
           score = sym['score']
           self._add_symmetry_edges(graph, plane, score * w_sym)
           
       return graph

   def _find_optimal_cuts(self, graph: nx.Graph) -> List[Dict]:
       """Find optimal cutting planes using graph analysis"""
       cuts = []
       
       # Convert to numpy arrays for efficient computation
       positions = np.array([graph.nodes[n]['position'] for n in graph.nodes])
       weights = np.array([graph.edges[e]['weight'] for e in graph.edges])
       
       # Use spectral clustering to find initial segments
       n_cuts = self._estimate_optimal_cuts()
       clustering = SpectralClustering(
           n_clusters=n_cuts,
           affinity='precomputed',
           random_state=42
       )
       
       # Build affinity matrix
       n_vertices = len(positions)
       affinity = np.zeros((n_vertices, n_vertices))
       for (u, v, d) in graph.edges(data=True):
           affinity[u, v] = d['weight']
           affinity[v, u] = d['weight']
           
       labels = clustering.fit_predict(affinity)
       
       # Find cutting planes between clusters
       for i in range(n_cuts):
           for j in range(i + 1, n_cuts):
               cluster1 = positions[labels == i]
               cluster2 = positions[labels == j]
               
               if len(cluster1) > 0 and len(cluster2) > 0:
                   # Find optimal separating plane
                   plane = self._compute_separating_plane(cluster1, cluster2)
                   
                   # Compute cut score
                   score = self._evaluate_cut_quality(
                       plane, cluster1, cluster2, graph
                   )
                   
                   cuts.append({
                       'plane': plane,
                       'features': {
                           'cluster1': cluster1,
                           'cluster2': cluster2
                       },
                       'score': score
                   })
                   
       return sorted(cuts, key=lambda x: x['score'], reverse=True)