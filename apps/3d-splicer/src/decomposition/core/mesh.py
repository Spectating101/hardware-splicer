# File: src/decomposition/core/mesh.py
# Purpose: Core mesh representation with comprehensive analysis capabilities
# Dependencies: numpy, scipy, trimesh
# Priority: Critical - Foundation for all mesh operations

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
import numpy as np
import numpy.typing as npt
from scipy.spatial import KDTree, ConvexHull
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh
import trimesh
from pathlib import Path
import logging
from enum import Enum

class FeatureType(Enum):
   SHARP_EDGE = "sharp_edge"
   HIGH_CURVATURE = "high_curvature"
   THIN_REGION = "thin_region"
   SYMMETRY_PLANE = "symmetry_plane"
   SUPPORT_POINT = "support_point"
   CONNECTION_CANDIDATE = "connection_candidate"

@dataclass
class MeshMetadata:
   """Comprehensive mesh analysis data"""
   volume: float
   surface_area: float
   center_of_mass: npt.NDArray[np.float64]
   principal_axes: npt.NDArray[np.float64]
   thickness_stats: Dict[str, float]
   symmetry_planes: List[npt.NDArray[np.float64]]
   bounding_box: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
   convex_hull: ConvexHull
   euler_characteristic: int
   genus: int
   connected_components: int
   is_watertight: bool
   has_self_intersections: bool
   minimum_detail_size: float
   maximum_overhang_angle: float
   estimated_print_time: float
   support_volume_required: float
   printability_score: float

class MeshError(Exception):
   """Custom exception for mesh-related errors"""
   pass

class Mesh:
   """Advanced mesh representation with comprehensive analysis capabilities"""
   
   # Class-level constants for analysis parameters
   SHARP_EDGE_THRESHOLD = 60  # degrees
   HIGH_CURVATURE_THRESHOLD = 0.7
   THIN_REGION_THRESHOLD = 1.5  # mm
   SYMMETRY_TOLERANCE = 0.01
   MIN_FEATURE_SIZE = 0.1  # mm
   MAX_OVERHANG_ANGLE = 45  # degrees

    def __init__(self, 
                    vertices: npt.NDArray[np.float64],
                    faces: npt.NDArray[np.int64],
                    name: str = "unnamed_mesh",
                    validate: bool = True):
        """Initialize mesh with optional validation"""
        if validate:
            self._validate_input(vertices, faces)
            
        self.vertices = vertices
        self.faces = faces
        self.name = name
        
        # Initialize caches
        self._cache = {
            'trimesh': None,
            'kdtree': None,
            'metadata': None,
            'normal_cache': None,
            'feature_points': {},
            'curvature': None,
            'thickness': None,
            'adjacency': None,
            'laplacian': None,
            'feature_size': None,
            'symmetry': None,
            'support_analysis': None
        }
        
        # Initialize loggers
        self._logger = logging.getLogger(f"Mesh_{name}")
        
        # Compute basic properties
        self._initialize_basic_properties()

    def _validate_input(self, vertices: npt.NDArray[np.float64], faces: npt.NDArray[np.int64]):
        """Validate input data"""
        if not isinstance(vertices, np.ndarray) or vertices.dtype != np.float64:
            raise MeshError("Vertices must be a float64 numpy array")
        if not isinstance(faces, np.ndarray) or faces.dtype != np.int64:
            raise MeshError("Faces must be an int64 numpy array")
        if vertices.shape[1] != 3:
            raise MeshError("Vertices must be 3-dimensional")
        if faces.shape[1] != 3:
            raise MeshError("Faces must be triangular")
        if np.any(faces >= len(vertices)):
            raise MeshError("Face indices out of bounds")

    def _initialize_basic_properties(self):
        """Initialize basic mesh properties"""
        try:
            # Compute vertex valence
            self._vertex_valence = self._compute_vertex_valence()
            
            # Check mesh topology
            self._check_topology()
            
            # Initialize bounding box
            self.bbox_min = np.min(self.vertices, axis=0)
            self.bbox_max = np.max(self.vertices, axis=0)
            
            # Compute basic metrics
            self.n_vertices = len(self.vertices)
            self.n_faces = len(self.faces)
            self.mesh_area = self._compute_surface_area()
            
        except Exception as e:
            self._logger.error(f"Error initializing mesh properties: {str(e)}")
            raise MeshError(f"Initialization failed: {str(e)}")

    @property
    def trimesh(self) -> trimesh.Trimesh:
        """Lazy loading of trimesh object with caching"""
        if self._cache['trimesh'] is None:
            try:
                self._cache['trimesh'] = trimesh.Trimesh(
                    vertices=self.vertices.copy(),
                    faces=self.faces.copy(),
                    process=False
                )
            except Exception as e:
                raise MeshError(f"Failed to create trimesh object: {str(e)}")
        return self._cache['trimesh']

    def _compute_vertex_valence(self) -> npt.NDArray[np.int64]:
        """Compute vertex valence (number of connected edges)"""
        valence = np.zeros(len(self.vertices), dtype=np.int64)
        for face in self.faces:
            valence[face] += 1
        return valence

    def _check_topology(self):
        """Verify mesh topology"""
        # Create edge list
        edges = set()
        boundary_edges = set()
        
        for face in self.faces:
            for i in range(3):
                edge = tuple(sorted([face[i], face[(i+1)%3]]))
                if edge in edges:
                    boundary_edges.add(edge)
                edges.add(edge)
                
        self.has_boundaries = len(boundary_edges) > 0
        self.is_manifold = all(len([e for e in edges if e[0] == v or e[1] == v]) >= 2 
                                for v in range(len(self.vertices)))

    def compute_metadata(self, force_recompute: bool = False) -> MeshMetadata:
        """Compute comprehensive mesh analysis"""
        if self._cache['metadata'] is not None and not force_recompute:
            return self._cache['metadata']

        try:
            # Basic properties
            volume = self.trimesh.volume
            surface_area = self.mesh_area
            com = self.trimesh.center_mass
            
            # Principal axes using PCA
            vertices_centered = self.vertices - com
            _, principal_axes = np.linalg.eigh(vertices_centered.T @ vertices_centered)
            
            # Thickness analysis
            thickness_map = self._compute_thickness_distribution()
            thickness_stats = {
                'min': np.min(thickness_map),
                'max': np.max(thickness_map),
                'mean': np.mean(thickness_map),
                'median': np.median(thickness_map),
                'std': np.std(thickness_map)
            }
            
            # Advanced analysis
            symmetry_planes = self._detect_symmetry_planes()
            convex_hull = ConvexHull(self.vertices)
            euler_char = self._compute_euler_characteristic()
            genus = self._compute_genus()
            
            # Printability analysis
            printability = self._analyze_printability()
            
            metadata = MeshMetadata(
                volume=volume,
                surface_area=surface_area,
                center_of_mass=com,
                principal_axes=principal_axes,
                thickness_stats=thickness_stats,
                symmetry_planes=symmetry_planes,
                bounding_box=(self.bbox_min, self.bbox_max),
                convex_hull=convex_hull,
                euler_characteristic=euler_char,
                genus=genus,
                connected_components=self._count_connected_components(),
                is_watertight=self.trimesh.is_watertight,
                has_self_intersections=self.trimesh.is_self_intersecting,
                minimum_detail_size=self._compute_minimum_detail_size(),
                maximum_overhang_angle=printability['max_overhang'],
                estimated_print_time=printability['estimated_time'],
                support_volume_required=printability['support_volume'],
                printability_score=printability['score']
            )
            
            self._cache['metadata'] = metadata
            return metadata
            
        except Exception as e:
            self._logger.error(f"Error computing metadata: {str(e)}")
            raise MeshError(f"Metadata computation failed: {str(e)}")

    def _compute_thickness_distribution(self) -> npt.NDArray[np.float64]:
        """Compute local thickness across the mesh using ray casting"""
        if self._cache['thickness'] is not None:
            return self._cache['thickness']
            
        # Initialize KD-tree for efficient nearest neighbor search
        if self._cache['kdtree'] is None:
            self._cache['kdtree'] = KDTree(self.vertices)
            
        # Get vertex normals
        normals = self.get_vertex_normals()
        thickness_map = np.zeros(len(self.vertices))
        
        # Ray casting parameters
        RAY_LENGTH = 100.0  # mm
        N_RAYS = 8  # rays per vertex
        
        for i, (vertex, normal) in enumerate(zip(self.vertices, normals)):
            hits = []
            
            # Cast multiple rays in different directions
            for theta in np.linspace(0, 2*np.pi, N_RAYS):
                # Create rotation matrix around normal
                rotation = self._rotation_matrix_from_axis_angle(normal, theta)
                
                # Cast ray in both directions
                ray_dir = rotation @ normal
                ray_origins = [vertex + 0.001 * ray_dir, vertex - 0.001 * ray_dir]
                ray_directions = [ray_dir, -ray_dir]
                
                for origin, direction in zip(ray_origins, ray_directions):
                    locations, _, _ = self.trimesh.ray.intersects_location(
                        ray_origins=[origin],
                        ray_directions=[direction]
                    )
                    if len(locations) > 0:
                        # Find closest hit point
                        distances = np.linalg.norm(locations - vertex, axis=1)
                        hits.append(np.min(distances))
            
            if hits:
                thickness_map[i] = np.median(hits)
            else:
                # If no hits, estimate based on nearest neighbors
                _, indices = self._cache['kdtree'].query(vertex, k=5)
                thickness_map[i] = np.mean(thickness_map[indices[thickness_map[indices] > 0]])
                
        self._cache['thickness'] = thickness_map
        return thickness_map

    def _compute_euler_characteristic(self) -> int:
        """Compute Euler characteristic (V - E + F)"""
        V = len(self.vertices)
        F = len(self.faces)
        E = len(set(tuple(sorted([self.faces[i][j], self.faces[i][(j+1)%3]]))
                    for i in range(len(self.faces))
                    for j in range(3)))
        return V - E + F

    def _compute_genus(self) -> int:
        """Compute mesh genus"""
        euler_char = self._compute_euler_characteristic()
        return int((2 - euler_char) / 2)

    def _count_connected_components(self) -> int:
        """Count number of connected components using graph traversal"""
        # Build adjacency list
        adj_list = [[] for _ in range(len(self.vertices))]
        for face in self.faces:
            for i in range(3):
                adj_list[face[i]].append(face[(i+1)%3])
                adj_list[face[(i+1)%3]].append(face[i])
                
        # BFS to count components
        visited = set()
        components = 0
        
        for v in range(len(self.vertices)):
            if v not in visited:
                components += 1
                queue = [v]
                visited.add(v)
                
                while queue:
                    current = queue.pop(0)
                    for neighbor in adj_list[current]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            
        return components

    def _analyze_printability(self) -> Dict[str, float]:
        """Analyze mesh for 3D printing considerations"""
        if self._cache['support_analysis'] is not None:
            return self._cache['support_analysis']
            
        try:
            # Get face normals and areas
            face_normals = self.trimesh.face_normals
            face_areas = self.trimesh.area_faces
            
            # Analyze overhangs
            up_vector = np.array([0, 0, 1])
            angles = np.arccos(np.clip(np.dot(face_normals, up_vector), -1.0, 1.0))
            overhang_mask = angles > np.radians(45)
            
            # Calculate support volume
            support_volume = np.sum(face_areas[overhang_mask] * 
                                    np.sin(angles[overhang_mask]))
            
            # Estimate print time based on volume and complexity
            volume = self.trimesh.volume
            complexity_factor = len(self.faces) / volume
            estimated_time = volume * 0.1 * (1 + complexity_factor * 0.2)
            
            # Calculate printability score
            max_overhang = np.max(np.degrees(angles))
            support_ratio = support_volume / volume
            detail_score = self._compute_minimum_detail_size() / self.MIN_FEATURE_SIZE
            
            printability_score = 1.0
            printability_score -= 0.3 * (support_ratio)
            printability_score -= 0.2 * (max_overhang / 90)
            printability_score -= 0.1 * (1 - detail_score if detail_score < 1 else 0)
            printability_score = max(0.0, min(1.0, printability_score))
            
            analysis = {
                'max_overhang': max_overhang,
                'support_volume': support_volume,
                'estimated_time': estimated_time,
                'score': printability_score
            }
            
            self._cache['support_analysis'] = analysis
            return analysis
            
        except Exception as e:
            self._logger.error(f"Error in printability analysis: {str(e)}")
            raise MeshError(f"Printability analysis failed: {str(e)}")

    def _compute_minimum_detail_size(self) -> float:
        """Compute minimum feature size"""
        if self._cache['feature_size'] is not None:
            return self._cache['feature_size']
            
        # Compute edge lengths
        edges = set()
        for face in self.faces:
            for i in range(3):
                edges.add(tuple(sorted([face[i], face[(i+1)%3]])))
                
        edge_lengths = [np.linalg.norm(self.vertices[e[0]] - self.vertices[e[1]])
                        for e in edges]
                        
        min_length = np.min(edge_lengths)
        
        # Compute face areas
        face_areas = np.zeros(len(self.faces))
        for i, face in enumerate(self.faces):
            v1, v2, v3 = self.vertices[face]
            face_areas[i] = np.linalg.norm(np.cross(v2-v1, v3-v1)) / 2
            
        min_area = np.min(face_areas)
        
        # Feature size is minimum of edge lengths and sqrt of minimum face area
        feature_size = min(min_length, np.sqrt(min_area))
        self._cache['feature_size'] = feature_size
        
        return feature_size

    def _rotation_matrix_from_axis_angle(self, 
                                        axis: npt.NDArray[np.float64], 
                                        theta: float) -> npt.NDArray[np.float64]:
        """Compute rotation matrix from axis and angle"""
        axis = axis / np.linalg.norm(axis)
        a = np.cos(theta/2)
        b, c, d = -axis * np.sin(theta/2)
        
        return np.array([
            [a*a+b*b-c*c-d*d, 2*(b*c-a*d), 2*(b*d+a*c)],
            [2*(b*c+a*d), a*a+c*c-b*b-d*d, 2*(c*d-a*b)],
            [2*(b*d-a*c), 2*(c*d+a*b), a*a+d*d-b*b-c*c]
        ])

    def analyze_curvature(self) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Compute principal curvatures for each vertex"""
        if self._cache['curvature'] is not None:
            return self._cache['curvature']
            
        # Compute Laplacian matrix
        if self._cache['laplacian'] is None:
            self._cache['laplacian'] = self._compute_laplacian()
            
        L = self._cache['laplacian']
        positions = self.vertices
        
        # Solve eigenvalue problem
        try:
            eigenvalues, eigenvectors = eigsh(L, k=2, which='SM')
            principal_curvatures = np.column_stack([
                eigenvectors[:, 0] * np.sqrt(np.abs(eigenvalues[0])),
                eigenvectors[:, 1] * np.sqrt(np.abs(eigenvalues[1]))
            ])
            
            self._cache['curvature'] = principal_curvatures
            return principal_curvatures
            
        except Exception as e:
            self._logger.error(f"Error computing curvature: {str(e)}")
            raise MeshError(f"Curvature computation failed: {str(e)}")

    def _compute_laplacian(self) -> csr_matrix:
        """Compute Laplacian matrix using cotangent weights"""
        n_vertices = len(self.vertices)
        rows, cols, data = [], [], []
        
        for face in self.faces:
            # Compute cotangent weights for each edge
            for i in range(3):
                j = (i + 1) % 3
                k = (i + 2) % 3
                
                vi = self.vertices[face[i]]
                vj = self.vertices[face[j]]
                vk = self.vertices[face[k]]
                
                # Compute cotangent of angle at vk
                ej = vj - vk
                ei = vi - vk
                cotangent = (np.dot(ej, ei) / 
                            np.linalg.norm(np.cross(ej, ei)))
                
                weight = cotangent / 2
                
                # Add to matrix entries
                rows.extend([face[i], face[j], face[i], face[j]])
                cols.extend([face[j], face[i], face[i], face[j]])
                data.extend([weight, weight, -weight, -weight])
                
        return csr_matrix((data, (rows, cols)), shape=(n_vertices, n_vertices))

    def get_vertex_normals(self) -> npt.NDArray[np.float64]:
        """Compute or return cached vertex normals"""
        if self._cache['normal_cache'] is None:
            self._cache['normal_cache'] = self.trimesh.vertex_normals
        return self._cache['normal_cache']

    def identify_features(self, feature_type: FeatureType) -> Set[int]:
        """Identify mesh features of specified type"""
        if feature_type.value in self._cache['feature_points']:
            return self._cache['feature_points'][feature_type.value]
            
        features = set()
        
        if feature_type == FeatureType.SHARP_EDGE:
            # Identify sharp edges using dihedral angles
            edge_vertices = set()
            for face1_idx, face1 in enumerate(self.faces):
                for face2_idx, face2 in enumerate(self.faces[face1_idx+1:], face1_idx+1):
                    shared_vertices = set(face1) & set(face2)
                    if len(shared_vertices) == 2:
                        angle = self._compute_dihedral_angle(face1_idx, face2_idx)
                        if abs(angle) > np.radians(self.SHARP_EDGE_THRESHOLD):
                            edge_vertices.update(shared_vertices)
            features.update(edge_vertices)
            
        elif feature_type == FeatureType.HIGH_CURVATURE:
            curvature = self.analyze_curvature()
            max_curvature = np.max(np.abs(curvature), axis=1)
            features.update(np.where(max_curvature > self.HIGH_CURVATURE_THRESHOLD)[0])
            
        elif feature_type == FeatureType.THIN_REGION:
            thickness = self._compute_thickness_distribution()
            features.update(np.where(thickness < self.THIN_REGION_THRESHOLD)[0])
            
        elif feature_type == FeatureType.SYMMETRY_PLANE:
            symmetry_planes = self._detect_symmetry_planes()
            for plane in symmetry_planes:
                features.update(self._get_vertices_near_plane(plane))
            
        self._cache['feature_points'][feature_type.value] = features
        return features

    def _compute_dihedral_angle(self, face1_idx: int, face2_idx: int) -> float:
        """Compute dihedral angle between two faces"""
        normal1 = self.trimesh.face_normals[face1_idx]
        normal2 = self.trimesh.face_normals[face2_idx]
        return np.arccos(np.clip(np.dot(normal1, normal2), -1.0, 1.0))

    def _get_vertices_near_plane(self, 
                                plane_normal: npt.NDArray[np.float64],
                                tolerance: float = 0.01) -> Set[int]:
        """Get vertices that lie near a plane"""
        # Normalize plane normal
        plane_normal = plane_normal / np.linalg.norm(plane_normal)
        
        # Project vertices onto plane normal
        com = self.compute_metadata().center_of_mass
        distances = np.abs(np.dot(self.vertices - com, plane_normal))
        
        return set(np.where(distances < tolerance)[0])

    @classmethod
    def from_file(cls, file_path: Path) -> 'Mesh':
        """Load mesh from file with error handling"""
        try:
            mesh = trimesh.load(str(file_path))
            return cls(vertices=mesh.vertices, faces=mesh.faces,
                        name=file_path.stem)
        except Exception as e:
            raise MeshError(f"Failed to load mesh from {file_path}: {str(e)}")

    def clear_cache(self):
        """Clear all cached computations"""
        self._cache = {key: None for key in self._cache}