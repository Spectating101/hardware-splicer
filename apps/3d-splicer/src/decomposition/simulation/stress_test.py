# File: src/decomposition/simulation/stress_test.py
# Purpose: Tests structural integrity under various conditions
# Dependencies: Core modules and structural analyzer
# Priority: High - Critical for validation

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
import logging

from ..core.mesh import Mesh
from ..core.component import Component
from ..analysis.structural import StructuralAnalyzer

class StressTestError(Exception):
    """Custom exception for stress test errors"""
    pass

@dataclass
class LoadCase:
   """Represents a load case for stress testing"""
   forces: List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]  # [(position, force)]
   moments: List[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]  # [(position, moment)]
   constraints: List[Tuple[int, List[bool]]]  # [(vertex_index, [x,y,z fixed])]
   name: str
   description: str

class StressTester:
   """Tests component structural integrity under various conditions"""
   
   def __init__(self):
       self._logger = logging.getLogger(__name__)
       self.structural_analyzer = StructuralAnalyzer(None)
       
       # Test parameters
       self.MAX_STRESS = 50e6  # Pa
       self.MAX_DISPLACEMENT = 1.0  # mm
       self.MIN_SAFETY_FACTOR = 2.0
       
   def run_stress_tests(self,
                       component: Component,
                       load_cases: Optional[List[LoadCase]] = None
                       ) -> Dict[str, Any]:
       """Run comprehensive stress tests"""
       try:
           # Use default load cases if none provided
           if load_cases is None:
               load_cases = self._generate_default_load_cases(component)
               
           results = {
               'passed': True,
               'cases': {},
               'critical_points': set(),
               'safety_factor': float('inf')
           }
           
           # Run each load case
           for case in load_cases:
               case_results = self._run_load_case(component, case)
               results['cases'][case.name] = case_results
               
               # Update overall results
               if not case_results['passed']:
                   results['passed'] = False
               results['critical_points'].update(case_results['critical_points'])
               results['safety_factor'] = min(
                   results['safety_factor'],
                   case_results['safety_factor']
               )
               
           # Add summary metrics
           results['summary'] = self._generate_test_summary(results)
           
           return results
           
       except Exception as e:
           self._logger.error(f"Stress testing failed: {str(e)}")
           raise StressTestError(f"Stress testing failed: {str(e)}")

   def _generate_default_load_cases(self,
                                  component: Component) -> List[LoadCase]:
       """Generate standard load cases for testing"""
       try:
           load_cases = []
           
           # Get component properties
           com = component.mesh.compute_metadata().center_of_mass
           mass = component.mesh.compute_metadata().volume * 1.24  # g/cm³
           weight = mass * 9.81  # N
           
           # Case 1: Gravity load
           load_cases.append(LoadCase(
               forces=[(com, np.array([0, 0, -weight]))],
               moments=[],
               constraints=self._find_base_constraints(component),
               name="gravity_load",
               description="Standard gravity loading"
           ))
           
           # Case 2: Connection loads
           if component.connection_points:
               forces = []
               for conn in component.connection_points:
                   force = weight * 0.5  # Test with 50% of weight
                   forces.append((
                       conn.position,
                       conn.normal * force
                   ))
               load_cases.append(LoadCase(
                   forces=forces,
                   moments=[],
                   constraints=self._find_base_constraints(component),
                   name="connection_loads",
                   description="Forces applied at connection points"
               ))
               
           # Case 3: Torsional load
           load_cases.append(LoadCase(
               forces=[],
               moments=[(
                   com,
                   np.array([0, 0, weight * 0.05])  # 5cm moment arm
               )],
               constraints=self._find_base_constraints(component),
               name="torsion_load",
               description="Torsional loading around vertical axis"
           ))
           
           return load_cases
           
       except Exception as e:
           self._logger.error(f"Load case generation failed: {str(e)}")
           raise StressTestError(f"Load case generation failed: {str(e)}")

   def _run_load_case(self,
                     component: Component,
                     case: LoadCase) -> Dict[str, Any]:
       """Run single load case"""
       try:
           # Update analyzer mesh
           self.structural_analyzer.mesh = component.mesh
           
           # Apply loads and constraints
           analysis = self.structural_analyzer.analyze_structural_integrity(
               loads=case.forces + case.moments,
               constraints=case.constraints
           )
           
           # Check results
           results = {
               'passed': True,
               'critical_points': set(),
               'max_stress': analysis['max_stress'],
               'max_displacement': analysis['max_displacement'],
               'safety_factor': analysis['yield_strength'] / analysis['max_stress']
           }
           
           # Check stress criterion
           if analysis['max_stress'] > self.MAX_STRESS:
               results['passed'] = False
               results['critical_points'].update(
                   self._find_high_stress_points(analysis)
               )
               
           # Check displacement criterion
           if analysis['max_displacement'] > self.MAX_DISPLACEMENT:
               results['passed'] = False
               results['critical_points'].update(
                   self._find_high_displacement_points(analysis)
               )
               
           # Check safety factor
           if results['safety_factor'] < self.MIN_SAFETY_FACTOR:
               results['passed'] = False
               
           return results
           
       except Exception as e:
           self._logger.error(f"Load case execution failed: {str(e)}")
           raise StressTestError(f"Load case execution failed: {str(e)}")

   def _find_base_constraints(self,
                            component: Component
                            ) -> List[Tuple[int, List[bool]]]:
       """Find appropriate base constraints"""
       try:
           constraints = []
           vertices = component.mesh.vertices
           
           # Find lowest vertices
           min_z = np.min(vertices[:, 2])
           base_vertices = np.where(
               vertices[:, 2] < min_z + 0.1
           )[0]
           
           # Add fixed constraints
           for vertex in base_vertices:
               constraints.append((
                   vertex,
                   [True, True, True]  # Fixed in all directions
               ))
               
           return constraints
           
       except Exception as e:
           self._logger.error(f"Constraint finding failed: {str(e)}")
           raise StressTestError(f"Constraint finding failed: {str(e)}")

   def _find_high_stress_points(self,
                              analysis: Dict[str, Any]) -> Set[int]:
       """Find vertices with high stress"""
       try:
           stress_field = analysis['stress_field']
           threshold = self.MAX_STRESS * 0.9  # 90% of max allowed
           
           return set(np.where(stress_field > threshold)[0])
           
       except Exception as e:
           self._logger.error(f"High stress point detection failed: {str(e)}")
           raise StressTestError(
               f"High stress point detection failed: {str(e)}"
           )

   def _find_high_displacement_points(self,
                                   analysis: Dict[str, Any]) -> Set[int]:
       """Find vertices with high displacement"""
       try:
           displacement_field = analysis['displacement_field']
           threshold = self.MAX_DISPLACEMENT * 0.9  # 90% of max allowed
           
           magnitudes = np.linalg.norm(displacement_field, axis=1)
           return set(np.where(magnitudes > threshold)[0])
           
       except Exception as e:
           self._logger.error(
               f"High displacement point detection failed: {str(e)}"
           )
           raise StressTestError(
               f"High displacement point detection failed: {str(e)}"
           )

   def _generate_test_summary(self,
                            results: Dict[str, Any]) -> Dict[str, Any]:
       """Generate summary of test results"""
       try:
           summary = {
               'total_cases': len(results['cases']),
               'passed_cases': sum(
                   1 for case in results['cases'].values()
                   if case['passed']
               ),
               'lowest_safety_factor': results['safety_factor'],
               'critical_regions': len(results['critical_points']),
               'recommendations': []
           }
           
           # Generate recommendations
           if summary['lowest_safety_factor'] < self.MIN_SAFETY_FACTOR:
               summary['recommendations'].append(
                   "Increase material thickness in critical regions"
               )
               
           if summary['critical_regions'] > 0:
               summary['recommendations'].append(
                   "Reinforce areas with high stress concentration"
               )
               
           if summary['passed_cases'] < summary['total_cases']:
               summary['recommendations'].append(
                   "Review failed load cases and adjust design"
               )
               
           return summary
           
       except Exception as e:
           self._logger.error(f"Summary generation failed: {str(e)}")
           raise StressTestError(f"Summary generation failed: {str(e)}")