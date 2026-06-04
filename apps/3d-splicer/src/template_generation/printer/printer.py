# File: src/decomposition/processing/printer.py
# Purpose: Handles print file generation and printer configuration
# Dependencies: Core modules and printer-specific libraries
# Priority: High - Critical for final output generation

import numpy as np
import numpy.typing as npt
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

from ..core.mesh import Mesh
from ..core.component import Component
from ..analysis.structural import StructuralAnalyzer
from .optimization import ComponentOptimizer

class PrinterError(Exception):
   """Custom exception for printer-related errors"""
   pass

@dataclass
class PrinterConfig:
   """Printer configuration parameters"""
   nozzle_size: float = 0.4  # mm
   layer_height: float = 0.2  # mm
   initial_layer_height: float = 0.3  # mm
   line_width: float = 0.45  # mm
   wall_thickness: float = 1.2  # mm
   infill_density: float = 0.2  # percentage
   infill_pattern: str = "gyroid"
   support_density: float = 0.15
   support_pattern: str = "zigzag"
   bed_temperature: int = 60  # Celsius
   nozzle_temperature: int = 200  # Celsius
   print_speed: int = 60  # mm/s
   travel_speed: int = 120  # mm/s
   retraction_distance: float = 6.5  # mm
   retraction_speed: int = 25  # mm/s
   fan_speed: int = 100  # percentage

class PrintQuality(Enum):
   """Print quality presets"""
   DRAFT = "draft"
   NORMAL = "normal"
   HIGH = "high"
   ULTRA = "ultra"

class PrinterManager:
   """Manages print file generation and printer settings"""
   
   def __init__(self, config: Optional[PrinterConfig] = None):
       self.config = config or PrinterConfig()
       self._logger = logging.getLogger(__name__)
       
       # Initialize optimizer
       self.optimizer = ComponentOptimizer()
       
       # Cache for computed values
       self._cache = {
           'slice_params': {},
           'support_data': {},
           'gcode_segments': {},
           'material_estimates': {}
       }
       
       # Printer constraints
       self.BUILD_VOLUME = (250, 210, 200)  # mm
       self.MIN_FEATURE_SIZE = self.config.nozzle_size * 2
       self.MAX_OVERHANG = 45  # degrees
       
   def generate_print_files(self,
                          components: List[Component],
                          output_dir: Path,
                          quality: PrintQuality = PrintQuality.NORMAL
                          ) -> Dict[str, Any]:
       """Generate complete print files for components"""
       try:
           self._logger.info(f"Generating print files with {quality.value} quality")
           
           # Adjust settings for quality level
           print_config = self._adjust_config_for_quality(quality)
           
           # Prepare output directory
           output_dir.mkdir(parents=True, exist_ok=True)
           
           results = {
               'files': {},
               'estimates': {},
               'validations': {}
           }
           
           # Process each component
           for component in components:
               # Generate slice configuration
               slice_config = self._generate_slice_config(
                   component,
                   print_config
               )
               
               # Generate supports
               support_data = self._generate_supports(
                   component,
                   slice_config
               )
               
               # Generate G-code
               gcode_file = self._generate_gcode(
                   component,
                   slice_config,
                   support_data,
                   output_dir
               )
               
               # Validate output
               validation = self._validate_print_file(
                   gcode_file,
                   component,
                   slice_config
               )
               
               # Store results
               results['files'][component.id] = gcode_file
               results['estimates'][component.id] = self._compute_print_estimates(
                   component,
                   slice_config,
                   support_data
               )
               results['validations'][component.id] = validation
               
           return results
           
       except Exception as e:
           self._logger.error(f"Print file generation failed: {str(e)}")
           raise PrinterError(f"Print file generation failed: {str(e)}")

   def _generate_slice_config(self,
                            component: Component,
                            print_config: PrinterConfig) -> Dict[str, Any]:
       """Generate optimized slicing configuration for component"""
       try:
           if component.id in self._cache['slice_params']:
               return self._cache['slice_params'][component.id]
               
           # Analyze component geometry
           geometry = self._analyze_component_geometry(component)
           
           # Adjust parameters based on geometry
           config = {
               'layer_height': self._optimize_layer_height(
                   geometry,
                   print_config
               ),
               'infill': self._optimize_infill(
                   geometry,
                   print_config
               ),
               'support': self._optimize_support_params(
                   geometry,
                   print_config
               ),
               'speeds': self._optimize_print_speeds(
                   geometry,
                   print_config
               ),
               'cooling': self._optimize_cooling(
                   geometry,
                   print_config
               )
           }
           
           # Validate configuration
           if not self._validate_slice_config(config, component):
               raise PrinterError(
                   f"Invalid slice configuration for component {component.id}"
               )
               
           self._cache['slice_params'][component.id] = config
           return config
           
       except Exception as e:
           self._logger.error(f"Slice configuration generation failed: {str(e)}")
           raise PrinterError(
               f"Slice configuration generation failed: {str(e)}"
           )

   def _generate_supports(self,
                        component: Component,
                        slice_config: Dict[str, Any]) -> Dict[str, Any]:
       """Generate support structures for component"""
       try:
           if component.id in self._cache['support_data']:
               return self._cache['support_data'][component.id]
               
           # Analyze overhangs
           overhangs = self._analyze_overhangs(component)
           
           # Generate support points
           support_points = self._generate_support_points(
               component,
               overhangs,
               slice_config
           )
           
           # Generate support structures
           supports = self._generate_support_structures(
               support_points,
               component,
               slice_config
           )
           
           # Optimize support parameters
           support_data = self._optimize_supports(
               supports,
               component,
               slice_config
           )
           
           self._cache['support_data'][component.id] = support_data
           return support_data
           
       except Exception as e:
           self._logger.error(f"Support generation failed: {str(e)}")
           raise PrinterError(f"Support generation failed: {str(e)}")

   def _generate_gcode(self,
                      component: Component,
                      slice_config: Dict[str, Any],
                      support_data: Dict[str, Any],
                      output_dir: Path) -> Path:
       """Generate G-code file for component"""
       try:
           # Initialize G-code generator
           gcode = self._initialize_gcode()
           
           # Add printer configuration
           gcode.extend(self._generate_printer_config(slice_config))
           
           # Generate layers
           layers = self._generate_layers(
               component,
               slice_config,
               support_data
           )
           
           # Add layer G-code
           for layer in layers:
               gcode.extend(self._generate_layer_gcode(layer))
               
           # Add finalization commands
           gcode.extend(self._generate_end_gcode())
           
           # Write to file
           output_file = output_dir / f"{component.id}.gcode"
           self._write_gcode(gcode, output_file)
           
           return output_file
           
       except Exception as e:
           self._logger.error(f"G-code generation failed: {str(e)}")
           raise PrinterError(f"G-code generation failed: {str(e)}")

   def _analyze_component_geometry(self,
                                component: Component) -> Dict[str, Any]:
       """Analyze component geometry for print optimization"""
       try:
           geometry = {
               'volume': component.mesh.compute_metadata().volume,
               'surface_area': component.mesh.compute_metadata().surface_area,
               'bounding_box': component.mesh.compute_metadata().bounding_box,
               'min_feature_size': self._compute_min_feature_size(component),
               'max_overhang_angle': self._compute_max_overhang(component),
               'layer_complexity': self._analyze_layer_complexity(component),
               'critical_features': self._identify_critical_features(component)
           }
           
           # Add derived metrics
           geometry.update(self._compute_derived_metrics(geometry))
           
           return geometry
           
       except Exception as e:
           self._logger.error(f"Geometry analysis failed: {str(e)}")
           raise PrinterError(f"Geometry analysis failed: {str(e)}")

   def _optimize_layer_height(self,
                            geometry: Dict[str, Any],
                            config: PrinterConfig) -> float:
       """Optimize layer height based on geometry"""
       try:
           min_height = max(
               0.1,  # Absolute minimum
               geometry['min_feature_size'] * 0.1,
               config.nozzle_size * 0.25
           )
           
           max_height = min(
               0.75 * config.nozzle_size,
               geometry['min_feature_size'] * 0.5
           )
           
           # Consider geometry complexity
           if geometry['layer_complexity'] > 0.7:
               # More complex geometry needs finer layers
               target_height = min_height + (max_height - min_height) * 0.3
           else:
               # Simpler geometry can use larger layers
               target_height = min_height + (max_height - min_height) * 0.7
               
           # Round to nearest multiple of minimum step
           step = 0.04  # mm
           return round(target_height / step) * step
           
       except Exception as e:
           self._logger.error(f"Layer height optimization failed: {str(e)}")
           raise PrinterError(f"Layer height optimization failed: {str(e)}")

   def _optimize_infill(self,
                       geometry: Dict[str, Any],
                       config: PrinterConfig) -> Dict[str, Any]:
       """Optimize infill parameters"""
       try:
           # Base density on structural requirements
           base_density = self._compute_required_density(geometry)
           
           # Adjust for different regions
           density_map = self._generate_density_map(geometry)
           
           # Select pattern based on geometry
           pattern = self._select_infill_pattern(geometry)
           
           return {
               'density': base_density,
               'density_map': density_map,
               'pattern': pattern,
               'overlap': self._compute_infill_overlap(geometry),
               'direction': self._optimize_infill_direction(geometry)
           }
           
       except Exception as e:
           self._logger.error(f"Infill optimization failed: {str(e)}")
           raise PrinterError(f"Infill optimization failed: {str(e)}")

   def _optimize_supports(self,
                        supports: Dict[str, Any],
                        component: Component,
                        slice_config: Dict[str, Any]) -> Dict[str, Any]:
       """Optimize support structures"""
       try:
           # Analyze support requirements
           requirements = self._analyze_support_requirements(
               component,
               supports
           )
           
           # Optimize density distribution
           density_map = self._optimize_support_density(
               requirements,
               slice_config
           )
           
           # Optimize interface layers
           interface = self._optimize_support_interface(
               requirements,
               slice_config
           )
           
           # Generate optimized support geometry
           geometry = self._generate_support_geometry(
               density_map,
               interface,
               requirements
           )
           
           return {
               'geometry': geometry,
               'density_map': density_map,
               'interface': interface,
               'connection_points': self._compute_support_connections(
                   geometry,
                   component
               )
           }
           
       except Exception as e:
           self._logger.error(f"Support optimization failed: {str(e)}")
           raise PrinterError(f"Support optimization failed: {str(e)}")

   def _validate_print_file(self,
                          gcode_file: Path,
                          component: Component,
                          slice_config: Dict[str, Any]) -> Dict[str, Any]:
       """Validate generated print file"""
       try:
           validation = {
               'valid': True,
               'issues': []
           }
           
           # Validate G-code syntax
           if not self._validate_gcode_syntax(gcode_file):
               validation['valid'] = False
               validation['issues'].append('invalid_gcode_syntax')
               
           # Validate print parameters
           if not self._validate_print_parameters(slice_config):
               validation['valid'] = False
               validation['issues'].append('invalid_print_parameters')
               
           # Check feature preservation
           if not self._validate_feature_preservation(
               component,
               slice_config
           ):
               validation['valid'] = False
               validation['issues'].append('feature_preservation_failed')
               
           # Validate supports
           if not self._validate_support_structures(
               component,
               slice_config
           ):
               validation['valid'] = False
               validation['issues'].append('inadequate_supports')
               
           return validation
           
       except Exception as e:
           self._logger.error(f"Print file validation failed: {str(e)}")
           raise PrinterError(f"Print file validation failed: {str(e)}")

   def _compute_print_estimates(self,
                              component: Component,
                              slice_config: Dict[str, Any],
                              support_data: Dict[str, Any]) -> Dict[str, float]:
       """Compute print time and material estimates"""
       try:
           # Initialize estimates
           estimates = {
               'print_time': 0.0,  # seconds
               'material_length': 0.0,  # mm
               'material_volume': 0.0,  # mm³
               'support_volume': 0.0,  # mm³
               'layer_count': 0
           }
           
           # Compute basic metrics
           estimates['layer_count'] = int(
               component.mesh.compute_metadata().bounding_box[1][2] /
               slice_config['layer_height']
           )
           
           # Compute material volume
           estimates['material_volume'] = (
               component.mesh.compute_metadata().volume *
               (1 + slice_config['infill']['density'])
           )
           
           # Add support volume
           estimates['support_volume'] = sum(
               support['volume']
               for support in support_data['geometry'].values()
           )
           
           # Compute material length
           estimates['material_length'] = self._compute_filament_length(
               estimates['material_volume'] + estimates['support_volume'],
               self.config.nozzle_size
           )
           
           # Compute print time
           estimates['print_time'] = self._estimate_print_time(
               estimates,
               slice_config
           )
           
           return estimates
           
       except Exception as e:
           self._logger.error(f"Print estimation failed: {str(e)}")
           raise PrinterError(f"Print estimation failed: {str(e)}")