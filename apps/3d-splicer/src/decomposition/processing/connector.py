# File: src/decomposition/processing/connector.py
# Purpose: Handles component connection generation and optimization
# Dependencies: Core modules and Component class
# Priority: High - Critical for assembly

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.mesh import Mesh
from ..core.component import Component, ConnectionPoint, ConnectionType

class ConnectorError(Exception):
    """Custom exception for connector-related errors"""
    pass

class ConnectionStrategy(Enum):
    """Different strategies for connection placement"""
    UNIFORM = "uniform"
    STRESS_BASED = "stress_based"
    GEOMETRY_BASED = "geometry_based"
    HYBRID = "hybrid"

@dataclass
class ConnectionSpec:
    """Connection specification parameters"""
    min_strength: float = 0.7
    min_spacing: float = 5.0  # mm
    max_angle: float = 45.0   # degrees
    clearance: float = 0.2    # mm
    safety_factor: float = 2.0

class ConnectionGenerator:
    """Generates and optimizes component connections"""
    
    def __init__(self, spec: Optional[ConnectionSpec] = None):
        self.spec = spec or ConnectionSpec()
        self._logger = logging.getLogger(__name__)
        
    def generate_connections(self,
                           components: List[Component],
                           strategy: ConnectionStrategy = ConnectionStrategy.HYBRID
                           ) -> Dict[str, Any]:
        """Generate connections between components"""
        try:
            # Initialize connection plan
            plan = {
                'connections': {},
                'metrics': {},
                'validation': {}
            }
            
            # Find adjacent component pairs
            adjacencies = self._find_adjacent_components(components)
            
            # Generate connections for each pair
            for comp1, comp2 in adjacencies:
                # Analyze interface
                interface = self._analyze_interface(comp1, comp2)
                
                # Generate connection points
                connections = self._generate_connection_points(
                    comp1,
                    comp2,
                    interface,
                    strategy
                )
                
                # Validate connections
                validation = self._validate_connections(
                    connections,
                    interface
                )
                
                if not validation['valid']:
                    raise ConnectorError(
                        f"Invalid connections between {comp1.id} and {comp2.id}: "
                        f"{validation['issues']}"
                    )
                    
                # Store results
                pair_id = (comp1.id, comp2.id)
                plan['connections'][pair_id] = connections
                plan['validation'][pair_id] = validation
                plan['metrics'][pair_id] = self._compute_connection_metrics(
                    connections,
                    interface
                )
                
            return plan
            
        except Exception as e:
            self._logger.error(f"Connection generation failed: {str(e)}")
            raise ConnectorError(f"Connection generation failed: {str(e)}")

    def _find_adjacent_components(self,
                                components: List[Component]
                                ) -> List[Tuple[Component, Component]]:
        """Find pairs of adjacent components"""
        try:
            adjacencies = []
            
            for i, comp1 in enumerate(components):
                for comp2 in components[i+1:]:
                    if self._check_adjacency(comp1, comp2):
                        adjacencies.append((comp1, comp2))
                        
            return adjacencies
            
        except Exception as e:
            self._logger.error(f"Adjacency detection failed: {str(e)}")
            raise ConnectorError(f"Adjacency detection failed: {str(e)}")

    def _analyze_interface(self,
                         comp1: Component,
                         comp2: Component) -> Dict[str, Any]:
        """Analyze interface between components"""
        try:
            # Find interface region
            vertices1, vertices2 = self._find_interface_vertices(comp1, comp2)
            
            # Compute interface properties
            center = np.mean(comp1.mesh.vertices[list(vertices1)], axis=0)
            normal = self._compute_interface_normal(
                vertices1,
                vertices2,
                comp1,
                comp2
            )
            
            # Analyze interface characteristics
            characteristics = {
                'area': self._compute_interface_area(vertices1, comp1),
                'perimeter': self._compute_interface_perimeter(vertices1, comp1),
                'curvature': self._compute_interface_curvature(vertices1, comp1),
                'thickness': self._compute_interface_thickness(vertices1, comp1)
            }
            
            return {
                'vertices1': vertices1,
                'vertices2': vertices2,
                'center': center,
                'normal': normal,
                'characteristics': characteristics
            }
            
        except Exception as e:
            self._logger.error(f"Interface analysis failed: {str(e)}")
            raise ConnectorError(f"Interface analysis failed: {str(e)}")

    def _generate_connection_points(self,
                                 comp1: Component,
                                 comp2: Component,
                                 interface: Dict[str, Any],
                                 strategy: ConnectionStrategy
                                 ) -> List[ConnectionPoint]:
        """Generate optimal connection points"""
        try:
            if strategy == ConnectionStrategy.UNIFORM:
                return self._generate_uniform_connections(
                    comp1,
                    comp2,
                    interface
                )
            elif strategy == ConnectionStrategy.STRESS_BASED:
                return self._generate_stress_based_connections(
                    comp1,
                    comp2,
                    interface
                )
            elif strategy == ConnectionStrategy.GEOMETRY_BASED:
                return self._generate_geometry_based_connections(
                    comp1,
                    comp2,
                    interface
                )
            else:  # HYBRID
                return self._generate_hybrid_connections(
                    comp1,
                    comp2,
                    interface
                )
                
        except Exception as e:
            self._logger.error(f"Connection point generation failed: {str(e)}")
            raise ConnectorError(f"Connection point generation failed: {str(e)}")

    def _validate_connections(self,
                            connections: List[ConnectionPoint],
                            interface: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated connections"""
        try:
            validation = {
                'valid': True,
                'issues': []
            }
            
            # Check minimum strength
            for connection in connections:
                if connection.strength_factor < self.spec.min_strength:
                    validation['valid'] = False
                    validation['issues'].append({
                        'type': 'insufficient_strength',
                        'connection': connection,
                        'strength': connection.strength_factor
                    })
                    
            # Check spacing
            for i, conn1 in enumerate(connections):
                for conn2 in connections[i+1:]:
                    spacing = np.linalg.norm(conn1.position - conn2.position)
                    if spacing < self.spec.min_spacing:
                        validation['valid'] = False
                        validation['issues'].append({
                            'type': 'insufficient_spacing',
                            'connections': (conn1, conn2),
                            'spacing': spacing
                        })
                        
            # Check angles
            interface_normal = interface['normal']
            for connection in connections:
                angle = np.arccos(np.dot(connection.normal, interface_normal))
                if angle > np.radians(self.spec.max_angle):
                    validation['valid'] = False
                    validation['issues'].append({
                        'type': 'excessive_angle',
                        'connection': connection,
                        'angle': np.degrees(angle)
                    })
                    
            return validation
            
        except Exception as e:
            self._logger.error(f"Connection validation failed: {str(e)}")
            raise ConnectorError(f"Connection validation failed: {str(e)}")

    def _compute_connection_metrics(self,
                                 connections: List[ConnectionPoint],
                                 interface: Dict[str, Any]) -> Dict[str, float]:
        """Compute metrics for connection configuration"""
        try:
            # Initialize metrics
            metrics = {
                'total_strength': 0.0,
                'average_spacing': 0.0,
                'coverage_ratio': 0.0,
                'uniformity_score': 0.0
            }
            
            # Compute total strength
            metrics['total_strength'] = sum(
                conn.strength_factor for conn in connections
            )
            
            # Compute average spacing
            spacings = []
            for i, conn1 in enumerate(connections):
                for conn2 in connections[i+1:]:
                    spacings.append(
                        np.linalg.norm(conn1.position - conn2.position)
                    )
            metrics['average_spacing'] = np.mean(spacings) if spacings else 0.0
            
            # Compute coverage ratio
            interface_area = interface['characteristics']['area']
            connection_area = sum(
                np.pi * (conn.geometry.main_geometry['diameter']/2)**2
                for conn in connections
            )
            metrics['coverage_ratio'] = connection_area / interface_area
            
            # Compute uniformity score
            metrics['uniformity_score'] = self._compute_uniformity_score(
                connections,
                interface
            )
            
            return metrics
            
        except Exception as e:
            self._logger.error(f"Metric computation failed: {str(e)}")
            raise ConnectorError(f"Metric computation failed: {str(e)}")