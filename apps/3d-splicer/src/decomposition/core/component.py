# File: src/decomposition/core/component.py
# Purpose: Defines component data structures and manipulation methods
# Dependencies: Mesh class, numpy, scipy
# Priority: Critical - Core data structure for decomposed parts

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any
import numpy as np
import numpy.typing as npt
from enum import Enum
from scipy.spatial import KDTree
from scipy.spatial.transform import Rotation
from .mesh import Mesh, MeshError

class ConnectionType(Enum):
   SNAP_FIT = "snap_fit"
   PEG_HOLE = "peg_hole"
   DOVETAIL = "dovetail"
   SLIDING = "sliding"
   THREADED = "threaded"
   PRESSURE_FIT = "pressure_fit"
   CLIP = "clip"

@dataclass
class ConnectionGeometry:
   """Detailed geometry for connection points"""
   main_geometry: Dict[str, float]  # Primary dimensions
   clearance: float  # Tolerance for fitting
   reinforcement: Optional[Dict[str, float]]  # Additional support structures
   stress_distribution: npt.NDArray[np.float64]  # Stress analysis results
   print_orientation: npt.NDArray[np.float64]  # Optimal print direction
   support_requirements: Dict[str, Any]  # Support structure needs
   layer_orientation: npt.NDArray[np.float64]  # Layer direction for strength

@dataclass
class ConnectionPoint:
   """Comprehensive connection point definition"""
   position: npt.NDArray[np.float64]
   normal: npt.NDArray[np.float64]
   connection_type: ConnectionType
   geometry: ConnectionGeometry
   mating_component: Optional[str] = None
   strength_factor: float = 1.0
   stress_concentration: float = 0.0
   max_load: float = 0.0
   safety_factor: float = 2.0
   assembly_order: int = 0
   is_critical: bool = False
   validation_status: Dict[str, bool] = field(default_factory=dict)

@dataclass
class ComponentMetadata:
   """Extended component metadata"""
   volume: float
   surface_area: float
   center_of_mass: npt.NDArray[np.float64]
   principal_axes: npt.NDArray[np.float64]
   mass: float
   moment_of_inertia: npt.NDArray[np.float64]
   bounding_box: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
   print_orientation: Optional[npt.NDArray[np.float64]] = None
   support_requirements: Dict[str, float] = field(default_factory=dict)
   structural_score: float = 0.0
   aesthetic_score: float = 0.0
   printability_score: float = 0.0
   assembly_complexity: float = 0.0
   estimated_print_time: float = 0.0
   material_volume: float = 0.0
   support_volume: float = 0.0

class ComponentError(Exception):
   """Custom exception for component-related errors"""
   pass

class Component:
   """Advanced component representation with comprehensive analysis and validation"""

   # Class constants for analysis and validation
   MIN_WALL_THICKNESS = 1.0  # mm
   MAX_OVERHANG_ANGLE = 45.0  # degrees
   MIN_SAFETY_FACTOR = 2.0
   CRITICAL_STRESS_THRESHOLD = 0.8
   
    def __init__(self,
                    mesh: Mesh,
                    component_id: str,
                    parent_id: Optional[str] = None,
                    material_properties: Optional[Dict] = None):
        """Initialize component with optional material properties"""
        self.mesh = mesh
        self.id = component_id
        self.parent_id = parent_id
        self.connection_points: List[ConnectionPoint] = []
        self.adjacent_components: Set[str] = set()
        self.metadata: Optional[ComponentMetadata] = None
        self.assembly_priority: int = 0
        
        # Initialize material properties with defaults if not provided
        self.material_properties = material_properties or {
            'density': 1.24,  # g/cm³ (PLA)
            'youngs_modulus': 3.5e9,  # Pa
            'yield_strength': 50e6,  # Pa
            'poissons_ratio': 0.36,
            'thermal_expansion': 68e-6,  # m/m-K
            'glass_transition': 60  # °C
        }
        
        # Initialize caches
        self._cache = {
            'stress_analysis': None,
            'support_analysis': None,
            'connection_validation': None,
            'printability_analysis': None,
            'assembly_analysis': None,
            'thermal_analysis': None
        }
        
        # Compute initial metadata
        self._compute_metadata()
        
        # Validate initial state
        self._validate_component()

    def _compute_metadata(self) -> ComponentMetadata:
        """Compute comprehensive component metadata"""
        try:
            # Get basic mesh metadata
            mesh_metadata = self.mesh.compute_metadata()
            
            # Compute mass properties
            volume = mesh_metadata.volume
            mass = volume * self.material_properties['density']
            
            # Compute moment of inertia
            moi = self._compute_moment_of_inertia(mass)
            
            # Analyze printability
            printability = self._analyze_printability()
            
            # Create metadata object
            self.metadata = ComponentMetadata(
                volume=volume,
                surface_area=mesh_metadata.surface_area,
                center_of_mass=mesh_metadata.center_of_mass,
                principal_axes=mesh_metadata.principal_axes,
                mass=mass,
                moment_of_inertia=moi,
                bounding_box=mesh_metadata.bounding_box,
                print_orientation=printability['optimal_orientation'],
                support_requirements=printability['support_requirements'],
                structural_score=self._compute_structural_score(),
                aesthetic_score=self._compute_aesthetic_score(),
                printability_score=printability['score'],
                assembly_complexity=self._compute_assembly_complexity(),
                estimated_print_time=printability['estimated_time'],
                material_volume=volume,
                support_volume=printability['support_volume']
            )
            
            return self.metadata
            
        except Exception as e:
            raise ComponentError(f"Failed to compute metadata: {str(e)}")

    def _compute_moment_of_inertia(self, mass: float) -> npt.NDArray[np.float64]:
        """Compute moment of inertia tensor"""
        vertices = self.mesh.vertices
        faces = self.mesh.faces
        
        # Center vertices
        centroid = self.mesh.compute_metadata().center_of_mass
        vertices_centered = vertices - centroid
        
        # Initialize inertia tensor
        inertia = np.zeros((3, 3))
        
        # Compute contribution from each tetrahedral element
        for face in faces:
            v1, v2, v3 = vertices_centered[face]
            # Form tetrahedron with origin
            tet_volume = abs(np.dot(v1, np.cross(v2, v3))) / 6
            
            # Contribute to inertia tensor
            for i in range(3):
                for j in range(3):
                    if i == j:
                        term = (v1[i]**2 + v2[i]**2 + v3[i]**2) / 10
                    else:
                        term = (v1[i]*v1[j] + v2[i]*v2[j] + v3[i]*v3[j]) / 10
                    inertia[i,j] += tet_volume * term
                    
        return inertia * (mass / self.metadata.volume)

    def add_connection_point(self,
                            position: npt.NDArray[np.float64],
                            normal: npt.NDArray[np.float64],
                            connection_type: ConnectionType,
                            geometry_params: Dict[str, float]) -> ConnectionPoint:
        """Add a new connection point with comprehensive validation"""
        try:
            # Validate position
            if not self._is_position_valid(position):
                raise ComponentError("Connection position is outside component bounds")
                
            # Validate normal
            normal = normal / np.linalg.norm(normal)
            
            # Generate connection geometry
            geometry = self._generate_connection_geometry(
                position, normal, connection_type, geometry_params
            )
            
            # Create connection point
            connection = ConnectionPoint(
                position=position,
                normal=normal,
                connection_type=connection_type,
                geometry=geometry,
                strength_factor=self._compute_connection_strength(position, normal),
                stress_concentration=self._compute_stress_concentration(position),
                max_load=self._compute_max_load(position, normal),
                assembly_order=len(self.connection_points)
            )
            
            # Validate connection
            if not self._validate_connection(connection):
                raise ComponentError("Connection validation failed")
                
            self.connection_points.append(connection)
            return connection
            
        except Exception as e:
            raise ComponentError(f"Failed to add connection point: {str(e)}")

    def _generate_connection_geometry(self,
                                    position: npt.NDArray[np.float64],
                                    normal: npt.NDArray[np.float64],
                                    connection_type: ConnectionType,
                                    params: Dict[str, float]) -> ConnectionGeometry:
        """Generate detailed connection geometry based on type and parameters"""
        try:
            # Initialize basic geometry
            main_geometry = {}
            clearance = 0.2  # Default clearance in mm
            
            if connection_type == ConnectionType.SNAP_FIT:
                main_geometry = self._generate_snap_fit_geometry(params)
                clearance = 0.15  # Tighter clearance for snap fits
                
            elif connection_type == ConnectionType.PEG_HOLE:
                main_geometry = self._generate_peg_hole_geometry(params)
                
            elif connection_type == ConnectionType.DOVETAIL:
                main_geometry = self._generate_dovetail_geometry(params)
                clearance = 0.1  # Very tight clearance for dovetails
                
            # Compute stress distribution
            stress_dist = self._compute_connection_stress_distribution(
                position, normal, main_geometry
            )
            
            # Determine optimal print orientation
            print_orient = self._compute_optimal_print_orientation(
                position, normal, main_geometry
            )
            
            # Analyze support requirements
            support_reqs = self._analyze_connection_support_requirements(
                position, normal, main_geometry, print_orient
            )
            
            # Determine layer orientation for maximum strength
            layer_orient = self._compute_optimal_layer_orientation(
                position, normal, stress_dist
            )
            
            return ConnectionGeometry(
                main_geometry=main_geometry,
                clearance=clearance,
                reinforcement=self._generate_reinforcement(main_geometry, stress_dist),
                stress_distribution=stress_dist,
                print_orientation=print_orient,
                support_requirements=support_reqs,
                layer_orientation=layer_orient
            )
            
        except Exception as e:
            raise ComponentError(f"Failed to generate connection geometry: {str(e)}")

    def _generate_snap_fit_geometry(self, params: Dict[str, float]) -> Dict[str, float]:
        """Generate specific geometry for snap-fit connections"""
        # Calculate beam dimensions based on material properties
        E = self.material_properties['youngs_modulus']
        yield_strength = self.material_properties['yield_strength']
        
        # Default parameters if not provided
        thickness = params.get('thickness', 2.0)
        width = params.get('width', 5.0)
        height = params.get('height', 10.0)
        
        # Calculate maximum deflection
        max_deflection = height * 0.1  # 10% of height
        
        # Calculate required beam length
        required_length = np.sqrt((3 * E * thickness * max_deflection) / 
                                (2 * yield_strength))
        
        return {
            'beam_length': required_length,
            'beam_thickness': thickness,
            'beam_width': width,
            'hook_height': height * 0.15,
            'hook_angle': 45.0,
            'entry_angle': 30.0,
            'base_thickness': thickness * 1.5
        }

    def _generate_peg_hole_geometry(self, params: Dict[str, float]) -> Dict[str, float]:
        """Generate specific geometry for peg-hole connections"""
        # Default parameters if not provided
        diameter = params.get('diameter', 5.0)
        length = params.get('length', diameter * 2)
        
        # Calculate optimal dimensions based on material properties
        min_wall_thickness = self.MIN_WALL_THICKNESS
        
        return {
            'peg_diameter': diameter,
            'hole_diameter': diameter + 0.2,  # Add clearance
            'length': length,
            'fillet_radius': diameter * 0.1,
            'wall_thickness': max(min_wall_thickness, diameter * 0.3),
            'taper_angle': 2.0,  # Degrees
            'support_rib_thickness': diameter * 0.2
        }

    def _generate_dovetail_geometry(self, params: Dict[str, float]) -> Dict[str, float]:
        """Generate specific geometry for dovetail connections"""
        # Default parameters if not provided
        width = params.get('width', 10.0)
        height = params.get('height', width * 0.5)
        
        # Calculate optimal angles based on material properties
        friction_coef = 0.3  # Typical for PLA
        optimal_angle = np.degrees(np.arctan(1 / (2 * friction_coef)))
        
        return {
            'width': width,
            'height': height,
            'angle': optimal_angle,
            'length': width * 2,
            'neck_width': width * 0.6,
            'groove_depth': height * 0.1,
            'end_clearance': 0.2
        }

    def _validate_component(self) -> bool:
        """Comprehensive component validation"""
        try:
            validations = {
                'wall_thickness': self._validate_wall_thickness(),
                'printability': self._validate_printability(),
                'structural': self._validate_structural_integrity(),
                'connections': self._validate_all_connections(),
                'assembly': self._validate_assembly_feasibility()
            }
            
            return all(validations.values())
            
        except Exception as e:
            raise ComponentError(f"Component validation failed: {str(e)}")

    def _validate_wall_thickness(self) -> bool:
        """Validate minimum wall thickness throughout component"""
        thickness = self.mesh._compute_thickness_distribution()
        return np.min(thickness) >= self.MIN_WALL_THICKNESS

    def _validate_printability(self) -> bool:
        """Validate component printability"""
        printability = self._analyze_printability()
        return (printability['score'] > 0.5 and
                printability['max_overhang'] <= self.MAX_OVERHANG_ANGLE)

    def _validate_structural_integrity(self) -> bool:
        """Validate structural integrity under expected loads"""
        if self._cache['stress_analysis'] is None:
            self._cache['stress_analysis'] = self._perform_stress_analysis()
            
        analysis = self._cache['stress_analysis']
        return (analysis['max_stress'] * self.MIN_SAFETY_FACTOR 
                self.material_properties['yield_strength'])

    def _validate_all_connections(self) -> bool:
       """Validate all connection points"""
       return all(self._validate_connection(conn) for conn in self.connection_points)

    def _validate_connection(self, connection: ConnectionPoint) -> bool:
       """Validate individual connection point"""
       try:
           # Structural validation
           stress_valid = connection.stress_concentration < self.CRITICAL_STRESS_THRESHOLD
           strength_valid = connection.strength_factor >= self.MIN_SAFETY_FACTOR
           
           # Geometric validation
           geometry = connection.geometry
           geo_valid = self._validate_connection_geometry(connection)
           
           # Print orientation validation
           orientation_valid = self._validate_print_orientation(
               connection.position,
               connection.geometry.print_orientation
           )
           
           # Layer alignment validation for strength
           layer_valid = self._validate_layer_alignment(
               connection.geometry.layer_orientation
           )
           
           # Support structure validation
           support_valid = self._validate_support_requirements(
               connection.geometry.support_requirements
           )
           
           # Update validation status
           connection.validation_status.update({
               'stress': stress_valid,
               'strength': strength_valid,
               'geometry': geo_valid,
               'orientation': orientation_valid,
               'layer_alignment': layer_valid,
               'support': support_valid
           })
           
           return all(connection.validation_status.values())
           
       except Exception as e:
           raise ComponentError(f"Connection validation failed: {str(e)}")

    def _validate_connection_geometry(self, connection: ConnectionPoint) -> bool:
       """Validate connection geometry constraints"""
       geometry = connection.geometry.main_geometry
       
       if connection.connection_type == ConnectionType.SNAP_FIT:
           min_thickness = max(self.MIN_WALL_THICKNESS, 
                             geometry['beam_thickness'] * 0.5)
           return (geometry['beam_thickness'] >= min_thickness and
                  geometry['beam_length'] >= geometry['beam_thickness'] * 3 and
                  geometry['hook_height'] <= geometry['beam_thickness'] * 2)
                  
       elif connection.connection_type == ConnectionType.PEG_HOLE:
           return (geometry['wall_thickness'] >= self.MIN_WALL_THICKNESS and
                  geometry['length'] >= geometry['peg_diameter'] and
                  geometry['fillet_radius'] >= geometry['peg_diameter'] * 0.05)
                  
       elif connection.connection_type == ConnectionType.DOVETAIL:
           return (geometry['neck_width'] >= self.MIN_WALL_THICKNESS and
                  geometry['angle'] >= 30 and geometry['angle'] <= 60 and
                  geometry['length'] >= geometry['width'])
                  
       return True

    def _validate_support_requirements(self, requirements: Dict[str, Any]) -> bool:
       """Validate that required supports are feasible"""
       # Check support volume ratio
       if requirements.get('volume_ratio', 0) > 2.0:  # More than 2x support volume
           return False
           
       # Check support accessibility
       if not requirements.get('accessible', True):
           return False
           
       # Check support removal feasibility
       if not requirements.get('removable', True):
           return False
           
       return True

    def _validate_layer_alignment(self, layer_orientation: npt.NDArray[np.float64]) -> bool:
       """Validate layer orientation for strength"""
       # Compute angle between layer orientation and principal stress direction
       stress_analysis = self._cache.get('stress_analysis')
       if stress_analysis is None:
           return True  # Skip validation if stress analysis not available
           
       principal_stress = stress_analysis.get('principal_direction')
       if principal_stress is not None:
           angle = np.arccos(np.abs(np.dot(layer_orientation, principal_stress)))
           return np.degrees(angle) <= 45  # Layers should be within 45° of principal stress
           
       return True

    def _analyze_printability(self) -> Dict[str, Any]:
       """Analyze component printability in detail"""
       if self._cache['printability_analysis'] is not None:
           return self._cache['printability_analysis']

       try:
           # Get face normals and areas
           face_normals = self.mesh.trimesh.face_normals
           face_areas = self.mesh.trimesh.area_faces
           
           # Analyze overhangs for different orientations
           orientations = self._generate_test_orientations()
           orientation_scores = {}
           
           for orientation in orientations:
               # Transform normals to test orientation
               R = Rotation.from_rotvec(orientation).as_matrix()
               transformed_normals = (R @ face_normals.T).T
               
               # Compute overhang angles
               up_vector = np.array([0, 0, 1])
               angles = np.arccos(np.clip(np.dot(transformed_normals, up_vector), -1.0, 1.0))
               
               # Calculate scores for this orientation
               overhang_area = np.sum(face_areas[angles > np.radians(45)])
               support_volume = self._estimate_support_volume(transformed_normals, face_areas)
               layer_alignment = self._compute_layer_alignment_score(transformed_normals)
               
               orientation_scores[tuple(orientation)] = {
                   'overhang_area': overhang_area,
                   'support_volume': support_volume,
                   'layer_alignment': layer_alignment
               }
           
           # Find optimal orientation
           optimal_orientation = min(orientation_scores.keys(),
                                  key=lambda k: orientation_scores[k]['support_volume'])
           
           # Compute final scores
           best_scores = orientation_scores[optimal_orientation]
           total_area = np.sum(face_areas)
           
           analysis = {
               'score': 1.0 - (best_scores['overhang_area'] / total_area),
               'optimal_orientation': np.array(optimal_orientation),
               'support_volume': best_scores['support_volume'],
               'support_requirements': self._compute_support_requirements(optimal_orientation),
               'max_overhang': np.max(np.degrees(angles)),
               'estimated_time': self._estimate_print_time(best_scores)
           }
           
           self._cache['printability_analysis'] = analysis
           return analysis
           
       except Exception as e:
           raise ComponentError(f"Printability analysis failed: {str(e)}")

    def _generate_test_orientations(self) -> List[npt.NDArray[np.float64]]:
       """Generate test orientations for printability analysis"""
       # Generate uniformly distributed orientations using spherical coordinates
       n_tests = 100
       orientations = []
       
       phi = np.arccos(1 - 2 * np.linspace(0, 1, int(np.sqrt(n_tests))))
       theta = np.linspace(0, 2*np.pi, int(np.sqrt(n_tests)))
       
       for p in phi:
           for t in theta:
               orientation = np.array([
                   np.sin(p) * np.cos(t),
                   np.sin(p) * np.sin(t),
                   np.cos(p)
               ])
               orientations.append(orientation)
               
       return orientations