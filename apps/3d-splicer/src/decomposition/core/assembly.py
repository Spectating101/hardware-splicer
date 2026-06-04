# File: src/decomposition/core/assembly.py
# Purpose: Handles component assembly validation and sequencing
# Dependencies: Core modules, numpy, scipy
# Priority: High - Critical for ensuring assemblability

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
import logging
import networkx as nx

from .mesh import Mesh
from .component import Component, ConnectionPoint

class AssemblyError(Exception):
    """Custom exception for assembly-related errors"""
    pass

@dataclass
class AssemblyStep:
    """Represents a single assembly step"""
    component: Component
    connections: List[ConnectionPoint]
    orientation: npt.NDArray[np.float64]
    position: npt.NDArray[np.float64]
    requirements: List[str]

class AssemblyPlanner:
    """Plans and validates component assembly"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
        # Assembly constraints
        self.MIN_CLEARANCE = 2.0  # mm
        self.MAX_INSERTION_ANGLE = 60.0  # degrees
        self.MIN_GRIP_AREA = 100.0  # mm²
        
    def generate_assembly_sequence(self,
                                 components: List[Component]
                                 ) -> List[AssemblyStep]:
        """Generate optimal assembly sequence"""
        try:
            # Build assembly graph
            graph = self._build_assembly_graph(components)
            
            # Find base component
            base = self._identify_base_component(components)
            
            # Generate sequence
            sequence = []
            assembled = {base}
            remaining = set(components) - {base}
            
            # Add base component
            sequence.append(AssemblyStep(
                component=base,
                connections=[],
                orientation=np.array([0, 0, 1]),
                position=np.zeros(3),
                requirements=['place_on_flat_surface']
            ))
            
            while remaining:
                # Find next best component
                next_component = self._find_next_component(
                    assembled,
                    remaining,
                    graph
                )
                
                if not next_component:
                    raise AssemblyError("Unable to complete assembly sequence")
                    
                # Generate assembly step
                step = self._generate_assembly_step(
                    next_component,
                    assembled,
                    graph
                )
                
                sequence.append(step)
                assembled.add(next_component)
                remaining.remove(next_component)
                
            return sequence
            
        except Exception as e:
            self._logger.error(f"Assembly sequence generation failed: {str(e)}")
            raise AssemblyError(f"Assembly sequence generation failed: {str(e)}")

    def validate_assembly(self,
                         components: List[Component],
                         sequence: Optional[List[AssemblyStep]] = None
                         ) -> Dict[str, Any]:
        """Validate assembly sequence and connections"""
        try:
            # Generate sequence if not provided
            if sequence is None:
                sequence = self.generate_assembly_sequence(components)
                
            validation = {
                'valid': True,
                'issues': [],
                'metrics': {}
            }
            
            # Validate sequence
            sequence_validation = self._validate_sequence(sequence)
            if not sequence_validation['valid']:
                validation['valid'] = False
                validation['issues'].extend(sequence_validation['issues'])
                
            # Validate connections
            connection_validation = self._validate_connections(
                components,
                sequence
            )
            if not connection_validation['valid']:
                validation['valid'] = False
                validation['issues'].extend(connection_validation['issues'])
                
            # Validate clearances
            clearance_validation = self._validate_clearances(sequence)
            if not clearance_validation['valid']:
                validation['valid'] = False
                validation['issues'].extend(clearance_validation['issues'])
                
            # Compute metrics
            validation['metrics'] = {
                'step_count': len(sequence),
                'max_connection_count': max(
                    len(step.connections) for step in sequence
                ),
                'complexity_score': self._compute_complexity_score(sequence)
            }
            
            return validation
            
        except Exception as e:
            self._logger.error(f"Assembly validation failed: {str(e)}")
            raise AssemblyError(f"Assembly validation failed: {str(e)}")

    def _build_assembly_graph(self,
                            components: List[Component]) -> nx.Graph:
        """Build graph representing assembly relationships"""
        try:
            graph = nx.Graph()
            
            # Add components as nodes
            for component in components:
                graph.add_node(component, connections=[])
                
            # Add edges based on connections
            for comp1 in components:
                for connection in comp1.connection_points:
                    if connection.mating_component:
                        comp2 = next(
                            c for c in components
                            if c.id == connection.mating_component
                        )
                        
                        # Add edge with connection data
                        # Add edge with connection data
                        graph.add_edge(
                            comp1,
                            comp2,
                            connection=connection,
                            strength=connection.strength_factor,
                            type=connection.connection_type
                        )
                        
            return graph
            
        except Exception as e:
            self._logger.error(f"Assembly graph building failed: {str(e)}")
            raise AssemblyError(f"Assembly graph building failed: {str(e)}")

    def _identify_base_component(self,
                              components: List[Component]) -> Component:
       """Identify best base component for assembly"""
       try:
           scores = []
           
           for component in components:
               score = 0.0
               
               # Consider size
               volume = component.mesh.compute_metadata().volume
               score += volume * 0.3
               
               # Consider stability
               com = component.mesh.compute_metadata().center_of_mass
               stability = -com[2]  # Lower center of mass is more stable
               score += stability * 0.3
               
               # Consider connections
               connection_count = len(component.connection_points)
               score += connection_count * 0.4
               
               scores.append((component, score))
               
           return max(scores, key=lambda x: x[1])[0]
           
       except Exception as e:
           self._logger.error(f"Base component identification failed: {str(e)}")
           raise AssemblyError(
               f"Base component identification failed: {str(e)}"
           )

    def _find_next_component(self,
                            assembled: Set[Component],
                            remaining: Set[Component],
                            graph: nx.Graph) -> Optional[Component]:
        """Find next best component to assemble"""
        try:
            candidates = []
            
            for component in remaining:
                # Check if component has connections to assembled parts
                connections = [
                    edge for edge in graph.edges(component)
                    if any(node in assembled for node in edge)
                ]
                
                if not connections:
                    continue
                    
                # Score candidate
                score = self._score_assembly_candidate(
                    component,
                    connections,
                    assembled,
                    graph
                )
                
                candidates.append((component, score))
                
            return max(candidates, key=lambda x: x[1])[0] if candidates else None
            
        except Exception as e:
            self._logger.error(f"Next component selection failed: {str(e)}")
            raise AssemblyError(f"Next component selection failed: {str(e)}")

    def _generate_assembly_step(self,
                                component: Component,
                                assembled: Set[Component],
                                graph: nx.Graph) -> AssemblyStep:
        """Generate assembly step for component"""
        try:
            # Get relevant connections
            connections = [
                edge[2]['connection'] for edge in graph.edges(component, data=True)
                if any(node in assembled for node in edge[:2])
            ]
            
            # Compute optimal orientation
            orientation = self._compute_assembly_orientation(
                component,
                connections,
                assembled
            )
            
            # Compute position
            position = self._compute_assembly_position(
                component,
                connections,
                assembled
            )
            
            # Generate requirements
            requirements = self._generate_step_requirements(
                component,
                connections,
                assembled
            )
            
            return AssemblyStep(
                component=component,
                connections=connections,
                orientation=orientation,
                position=position,
                requirements=requirements
            )
            
        except Exception as e:
            self._logger.error(f"Assembly step generation failed: {str(e)}")
            raise AssemblyError(f"Assembly step generation failed: {str(e)}")

    def _validate_sequence(self,
                            sequence: List[AssemblyStep]) -> Dict[str, Any]:
        """Validate assembly sequence"""
        try:
            validation = {
                'valid': True,
                'issues': []
            }
            
            assembled = set()
            
            for step in sequence:
                # Validate step
                step_validation = self._validate_assembly_step(
                    step,
                    assembled
                )
                
                if not step_validation['valid']:
                    validation['valid'] = False
                    validation['issues'].extend(step_validation['issues'])
                    
                assembled.add(step.component)
                
            return validation
            
        except Exception as e:
            self._logger.error(f"Sequence validation failed: {str(e)}")
            raise AssemblyError(f"Sequence validation failed: {str(e)}")

    def _validate_clearances(self,
                            sequence: List[AssemblyStep]) -> Dict[str, Any]:
        """Validate assembly clearances"""
        try:
            validation = {
                'valid': True,
                'issues': []
            }
            
            assembled_meshes = []
            
            for step in sequence:
                # Check clearance with assembled components
                for mesh in assembled_meshes:
                    clearance = self._compute_clearance(
                        step.component.mesh,
                        mesh,
                        step.position,
                        step.orientation
                    )
                    
                    if clearance < self.MIN_CLEARANCE:
                        validation['valid'] = False
                        validation['issues'].append({
                            'type': 'insufficient_clearance',
                            'component': step.component.id,
                            'clearance': clearance
                        })
                        
                # Add to assembled meshes
                assembled_meshes.append(
                    self._transform_mesh(
                        step.component.mesh,
                        step.position,
                        step.orientation
                    )
                )
                
            return validation
            
        except Exception as e:
            self._logger.error(f"Clearance validation failed: {str(e)}")
            raise AssemblyError(f"Clearance validation failed: {str(e)}")