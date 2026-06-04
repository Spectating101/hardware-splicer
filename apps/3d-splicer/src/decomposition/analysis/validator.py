# File: src/decomposition/analysis/validator.py
# Purpose: Validates components and decomposition results
# Dependencies: Core modules, numpy, scipy
# Priority: High - Critical for ensuring quality output

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
import logging

from ..core.mesh import Mesh
from ..core.component import Component
from .geometric import GeometricAnalyzer
from .structural import StructuralAnalyzer
from .aesthetic import AestheticAnalyzer

class ValidationError(Exception):
   """Custom exception for validation errors"""
   pass

@dataclass 
class ValidationMetrics:
   """Metrics for component validation"""
   structural_score: float
   printability_score: float
   aesthetic_score: float
   connection_score: float
   overall_score: float
   issues: List[str]

class DecompositionValidator:
   """Validates decomposition results across multiple criteria"""

   def __init__(self):
       self._logger = logging.getLogger(__name__)
       
       # Initialize analyzers
       self.geometric_analyzer = GeometricAnalyzer(None)
       self.structural_analyzer = StructuralAnalyzer(None)
       self.aesthetic_analyzer = AestheticAnalyzer(None)
       
       # Validation thresholds
       self.MIN_STRUCTURAL_SCORE = 0.7
       self.MIN_PRINTABILITY_SCORE = 0.6
       self.MIN_AESTHETIC_SCORE = 0.7
       self.MIN_CONNECTION_SCORE = 0.8
       
   def validate_decomposition(self,
                            original_mesh: Mesh,
                            components: List[Component]) -> Dict[str, Any]:
       """Validate complete decomposition result"""
       try:
           validation = {
               'valid': True,
               'components': {},
               'global': {},
               'issues': []
           }
           
           # Validate individual components
           for component in components:
               component_validation = self.validate_component(component)
               validation['components'][component.id] = component_validation
               
               if not component_validation.overall_score > 0.7:
                   validation['valid'] = False
                   validation['issues'].extend(component_validation.issues)
                   
           # Validate global properties
           global_validation = self._validate_global_properties(
               original_mesh,
               components
           )
           validation['global'] = global_validation
           
           if not global_validation['valid']:
               validation['valid'] = False
               validation['issues'].extend(global_validation['issues'])
               
           # Add validation summary
           validation['summary'] = self._generate_validation_summary(validation)
           
           return validation
           
       except Exception as e:
           self._logger.error(f"Decomposition validation failed: {str(e)}")
           raise ValidationError(f"Decomposition validation failed: {str(e)}")

   def validate_component(self, component: Component) -> ValidationMetrics:
       """Validate individual component"""
       try:
           # Structural validation
           structural_score = self._validate_structural_integrity(component)
           
           # Printability validation
           printability_score = self._validate_printability(component)
           
           # Aesthetic validation
           aesthetic_score = self._validate_aesthetics(component)
           
           # Connection validation
           connection_score = self._validate_connections(component)
           
           # Collect issues
           issues = []
           if structural_score < self.MIN_STRUCTURAL_SCORE:
               issues.append("insufficient_structural_integrity")
           if printability_score < self.MIN_PRINTABILITY_SCORE:
               issues.append("poor_printability")
           if aesthetic_score < self.MIN_AESTHETIC_SCORE:
               issues.append("aesthetic_features_compromised")
           if connection_score < self.MIN_CONNECTION_SCORE:
               issues.append("weak_connections")
               
           # Compute overall score
           overall_score = np.mean([
               structural_score,
               printability_score,
               aesthetic_score,
               connection_score
           ])
           
           return ValidationMetrics(
               structural_score=structural_score,
               printability_score=printability_score,
               aesthetic_score=aesthetic_score,
               connection_score=connection_score,
               overall_score=overall_score,
               issues=issues
           )
           
       except Exception as e:
           self._logger.error(f"Component validation failed: {str(e)}")
           raise ValidationError(f"Component validation failed: {str(e)}")

   def _validate_structural_integrity(self, component: Component) -> float:
       """Validate structural integrity of component"""
       try:
           # Update analyzer mesh
           self.structural_analyzer.mesh = component.mesh
           
           # Analyze structural properties
           analysis = self.structural_analyzer.analyze_structural_integrity()
           
           # Compute normalized score
           score = 0.0
           
           # Check stress distribution
           max_stress = analysis['max_stress']
           if max_stress > 0:
               stress_score = 1.0 - (max_stress / analysis['yield_strength'])
               score += stress_score * 0.4
               
           # Check stability
           score += analysis['stability_score'] * 0.3
           
           # Check support requirements
           support_score = 1.0 - (
               analysis['support_requirements']['support_volume'] /
               component.mesh.compute_metadata().volume
           )
           score += support_score * 0.3
           
           return np.clip(score, 0.0, 1.0)
           
       except Exception as e:
           self._logger.error(f"Structural validation failed: {str(e)}")
           raise ValidationError(f"Structural validation failed: {str(e)}")

   def _validate_printability(self, component: Component) -> float:
       """Validate component printability"""
       try:
           # Get component metadata
           metadata = component.mesh.compute_metadata()
           
           score = 0.0
           
           # Check overhangs
           max_overhang = metadata.maximum_overhang_angle
           overhang_score = 1.0 - (max_overhang / 90.0)
           score += overhang_score * 0.3
           
           # Check feature sizes
           min_feature = metadata.minimum_detail_size
           if min_feature > 0.4:  # mm
               feature_score = 1.0
           else:
               feature_score = min_feature / 0.4
           score += feature_score * 0.3
           
           # Check support requirements
           support_score = 1.0 - metadata.support_volume_required
           score += support_score * 0.4
           
           return np.clip(score, 0.0, 1.0)
           
       except Exception as e:
           self._logger.error(f"Printability validation failed: {str(e)}")
           raise ValidationError(f"Printability validation failed: {str(e)}")

   def _validate_aesthetics(self, component: Component) -> float:
       """Validate aesthetic preservation"""
       try:
           # Update analyzer mesh
           self.aesthetic_analyzer.mesh = component.mesh
           
           # Analyze aesthetic features
           features = self.aesthetic_analyzer.identify_features()
           quality = self.aesthetic_analyzer.analyze_surface_quality()
           
           score = 0.0
           
           # Check feature preservation
           if features['surface_details']:
               detail_score = len(features['surface_details']) / (
                   len(component.mesh.vertices) * 0.1
               )
               score += np.clip(detail_score, 0.0, 1.0) * 0.3
               
           # Check surface quality
           quality_score = np.mean(quality['metrics']['surface_quality'])
           score += quality_score * 0.4
           
           # Check pattern preservation
           if features['patterns']:
               pattern_score = len(features['patterns']) / (
                   len(component.mesh.vertices) * 0.05
               )
               score += np.clip(pattern_score, 0.0, 1.0) * 0.3
               
           return np.clip(score, 0.0, 1.0)
           
       except Exception as e:
           self._logger.error(f"Aesthetic validation failed: {str(e)}")
           raise ValidationError(f"Aesthetic validation failed: {str(e)}")

   def _validate_connections(self, component: Component) -> float:
       """Validate component connections"""
       try:
           if not component.connection_points:
               return 1.0  # No connections needed
               
           scores = []
           
           for connection in component.connection_points:
               # Check connection strength
               strength_score = connection.strength_factor
               scores.append(strength_score * 0.4)
               
               # Check connection placement
               placement_score = self._validate_connection_placement(
                   component,
                   connection
               )
               scores.append(placement_score * 0.3)
               
               # Check connection printability
               print_score = self._validate_connection_printability(connection)
               scores.append(print_score * 0.3)
               
           return np.mean(scores)
           
       except Exception as e:
           self._logger.error(f"Connection validation failed: {str(e)}")
           raise ValidationError(f"Connection validation failed: {str(e)}")

   def _validate_global_properties(self,
                                original_mesh: Mesh,
                                components: List[Component]) -> Dict[str, Any]:
       """Validate global properties of decomposition"""
       try:
           validation = {
               'valid': True,
               'issues': []
           }
           
           # Check volume preservation
           original_volume = original_mesh.compute_metadata().volume
           component_volume = sum(
               c.mesh.compute_metadata().volume for c in components
           )
           
           volume_ratio = component_volume / original_volume
           if not 0.95 <= volume_ratio <= 1.05:
               validation['valid'] = False
               validation['issues'].append('volume_mismatch')
               
           # Check feature preservation
           if not self._validate_global_features(
               original_mesh,
               components
           ):
               validation['valid'] = False
               validation['issues'].append('feature_loss')
               
           # Check assembly feasibility
           if not self._validate_assembly_feasibility(components):
               validation['valid'] = False
               validation['issues'].append('assembly_issues')
               
           # Add metrics
           validation['metrics'] = {
               'volume_ratio': volume_ratio,
               'component_count': len(components),
               'max_size_ratio': self._compute_size_ratio(components),
               'connection_density': self._compute_connection_density(components)
           }
           
           return validation
           
       except Exception as e:
           self._logger.error(f"Global validation failed: {str(e)}")
           raise ValidationError(f"Global validation failed: {str(e)}")