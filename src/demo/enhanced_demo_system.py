#!/usr/bin/env python3
"""
Enhanced Demo System for Circuit.AI
==================================

Provides realistic PCB analysis demo without heavy ML compute.
Focuses on platform development and user experience.
"""

import json
import random
from typing import Dict, Any, List, Optional
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from loguru import logger


class EnhancedDemoSystem:
    """Enhanced demo system for realistic PCB analysis."""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize enhanced demo system.
        If a seed is provided, randomness becomes reproducible.
        """
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.component_templates = self._load_component_templates()
        self.project_templates = self._load_project_templates()
        self.analysis_scenarios = self._load_analysis_scenarios()
        
        logger.info("Enhanced demo system initialized")
    
    def _load_component_templates(self) -> Dict[str, Any]:
        """Load realistic component templates."""
        return {
            "ic_chip": {
                "variants": ["microcontroller", "op_amp", "voltage_regulator", "logic_gate"],
                "confidence_range": (0.85, 0.98),
                "market_value_range": (0.25, 2.50),
                "educational_value": "high",
                "reuse_value": "high",
                "capabilities": ["arduino_projects", "iot_devices", "signal_processing", "control_systems"]
            },
            "capacitor": {
                "variants": ["electrolytic", "ceramic", "tantalum", "film"],
                "confidence_range": (0.80, 0.95),
                "market_value_range": (0.05, 0.75),
                "educational_value": "medium",
                "reuse_value": "medium",
                "capabilities": ["power_filtering", "audio_circuits", "timing_circuits", "voltage_regulation"]
            },
            "resistor": {
                "variants": ["carbon_film", "metal_film", "wire_wound", "surface_mount"],
                "confidence_range": (0.90, 0.99),
                "market_value_range": (0.01, 0.10),
                "educational_value": "high",
                "reuse_value": "low",
                "capabilities": ["current_limiting", "voltage_division", "biasing", "load_simulation"]
            },
            "connector": {
                "variants": ["header", "usb", "audio", "power"],
                "confidence_range": (0.75, 0.90),
                "market_value_range": (0.10, 1.50),
                "educational_value": "medium",
                "reuse_value": "high",
                "capabilities": ["signal_transmission", "power_distribution", "modular_design", "data_communication"]
            },
            "transformer": {
                "variants": ["power", "audio", "isolation", "step_down"],
                "confidence_range": (0.70, 0.85),
                "market_value_range": (1.00, 15.00),
                "educational_value": "high",
                "reuse_value": "high",
                "capabilities": ["voltage_conversion", "isolation", "power_distribution", "signal_coupling"]
            },
            "diode": {
                "variants": ["rectifier", "zener", "schottky", "led"],
                "confidence_range": (0.80, 0.95),
                "market_value_range": (0.05, 0.50),
                "educational_value": "medium",
                "reuse_value": "medium",
                "capabilities": ["rectification", "voltage_regulation", "signal_detection", "protection"]
            }
        }
    
    def _load_project_templates(self) -> List[Dict[str, Any]]:
        """Load realistic project templates."""
        return [
            {
                "name": "Arduino Weather Station",
                "description": "Build a weather station using salvaged components",
                "difficulty": "beginner",
                "time_estimate": "4-6 hours",
                "components_required": ["microcontroller", "sensor", "display", "connector"],
                "skills_learned": ["arduino_programming", "sensor_integration", "data_logging"],
                "educational_value": "high",
                "estimated_cost": "$15.00",
                "safety_level": "low",
                "market_value": 25.00
            },
            {
                "name": "Audio Amplifier",
                "description": "Create an audio amplifier from salvaged components",
                "difficulty": "intermediate",
                "time_estimate": "6-8 hours",
                "components_required": ["op_amp", "capacitor", "resistor", "connector"],
                "skills_learned": ["analog_circuits", "audio_engineering", "signal_processing"],
                "educational_value": "high",
                "estimated_cost": "$8.00",
                "safety_level": "medium",
                "market_value": 45.00
            },
            {
                "name": "LED Pattern Controller",
                "description": "Design an LED pattern controller for creative projects",
                "difficulty": "beginner",
                "time_estimate": "3-4 hours",
                "components_required": ["microcontroller", "led", "resistor", "connector"],
                "skills_learned": ["digital_circuits", "programming", "creative_electronics"],
                "educational_value": "medium",
                "estimated_cost": "$5.00",
                "safety_level": "low",
                "market_value": 20.00
            },
            {
                "name": "Power Supply Unit",
                "description": "Build a regulated power supply from salvaged parts",
                "difficulty": "advanced",
                "time_estimate": "8-10 hours",
                "components_required": ["transformer", "voltage_regulator", "capacitor", "diode"],
                "skills_learned": ["power_electronics", "voltage_regulation", "safety_design"],
                "educational_value": "high",
                "estimated_cost": "$12.00",
                "safety_level": "high",
                "market_value": 60.00
            },
            {
                "name": "Data Logger",
                "description": "Create a data logging system for environmental monitoring",
                "difficulty": "intermediate",
                "time_estimate": "6-8 hours",
                "components_required": ["microcontroller", "sensor", "memory", "connector"],
                "skills_learned": ["data_acquisition", "sensor_calibration", "embedded_systems"],
                "educational_value": "high",
                "estimated_cost": "$18.00",
                "safety_level": "low",
                "market_value": 35.00
            }
        ]
    
    def _load_analysis_scenarios(self) -> List[Dict[str, Any]]:
        """Load realistic analysis scenarios."""
        return [
            {
                "name": "Educational PCB",
                "description": "PCB from educational electronics kit",
                "components": ["ic_chip", "resistor", "capacitor", "connector"],
                "total_value": 8.50,
                "educational_potential": "excellent",
                "reuse_potential": "high"
            },
            {
                "name": "Consumer Electronics",
                "description": "PCB from discarded consumer device",
                "components": ["ic_chip", "capacitor", "resistor", "diode", "connector"],
                "total_value": 12.75,
                "educational_potential": "good",
                "reuse_potential": "medium"
            },
            {
                "name": "Industrial Control",
                "description": "PCB from industrial control system",
                "components": ["ic_chip", "transformer", "capacitor", "resistor", "connector"],
                "total_value": 25.00,
                "educational_potential": "excellent",
                "reuse_potential": "high"
            },
            {
                "name": "Audio Equipment",
                "description": "PCB from audio amplifier or mixer",
                "components": ["op_amp", "capacitor", "resistor", "connector", "transformer"],
                "total_value": 18.50,
                "educational_potential": "good",
                "reuse_potential": "medium"
            },
            {
                "name": "Dense Analog Board",
                "description": "High component density analog circuit board",
                "components": ["resistor", "resistor", "resistor", "capacitor", "capacitor", "diode", "ic_chip"],
                "total_value": 14.20,
                "educational_potential": "high",
                "reuse_potential": "medium"
            },
            {
                "name": "Power Board",
                "description": "Power supply board with high-current components",
                "components": ["transformer", "capacitor", "diode", "connector", "capacitor"],
                "total_value": 32.10,
                "educational_potential": "high",
                "reuse_potential": "high"
            }
        ]
    
    def generate_realistic_detections(self, image: np.ndarray, scenario: str = None) -> List[Dict[str, Any]]:
        """Generate realistic component detections for demo."""
        if scenario is None:
            scenario = self.rng.choice(self.analysis_scenarios)
        
        detections = []
        components = scenario["components"]
        
        # Generate realistic bounding boxes
        img_height, img_width = image.shape[:2]
        
        for i, component_type in enumerate(components):
            # Get component template
            template = self.component_templates[component_type]
            
            # Generate realistic bounding box
            bbox = self._generate_realistic_bbox(img_width, img_height, i)
            
            # Generate realistic confidence
            confidence = self.rng.uniform(*template["confidence_range"])
            
            # Generate market value
            market_value = self.rng.uniform(*template["market_value_range"])
            
            # Create detection
            detection = {
                "class_name": component_type,
                "confidence": confidence,
                "bbox": bbox,
                "capabilities": template["capabilities"],
                "market_value": market_value,
                "educational_value": template["educational_value"],
                "reuse_value": template["reuse_value"],
                "variant": self.rng.choice(template["variants"])
            }
            
            detections.append(detection)
        
        return detections
    
    def _generate_realistic_bbox(self, img_width: int, img_height: int, index: int) -> List[int]:
        """Generate realistic bounding box coordinates."""
        # Create grid-based positioning for realistic layout
        grid_size = 4
        cell_width = img_width // grid_size
        cell_height = img_height // grid_size
        
        # Position components in different grid cells
        row = (index * 2) % grid_size
        col = (index * 3) % grid_size
        
        x1 = col * cell_width + self.rng.randint(10, cell_width // 3)
        y1 = row * cell_height + self.rng.randint(10, cell_height // 3)
        x2 = x1 + self.rng.randint(cell_width // 4, cell_width // 2)
        y2 = y1 + self.rng.randint(cell_height // 4, cell_height // 2)
        
        return [x1, y1, x2, y2]
    
    def generate_analysis_summary(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate realistic analysis summary."""
        total_components = len(detections)
        total_market_value = sum(d.get("market_value", 0) for d in detections)
        
        # Calculate educational potential
        educational_values = [d.get("educational_value", "medium") for d in detections]
        high_edu_count = educational_values.count("high")
        educational_potential = "excellent" if high_edu_count >= 2 else "good" if high_edu_count >= 1 else "medium"
        
        # Calculate reuse potential
        reuse_values = [d.get("reuse_value", "medium") for d in detections]
        high_reuse_count = reuse_values.count("high")
        reuse_potential = "excellent" if high_reuse_count >= 2 else "good" if high_reuse_count >= 1 else "medium"
        
        # Component breakdown
        component_types = {}
        for detection in detections:
            comp_type = detection["class_name"]
            component_types[comp_type] = component_types.get(comp_type, 0) + 1
        
        return {
            "total_components": total_components,
            "total_market_value": total_market_value,
            "educational_potential": educational_potential,
            "reuse_potential": reuse_potential,
            "component_types": component_types,
            "analysis_quality": "high",
            "processing_time": self.rng.uniform(1.5, 3.0)
        }
    
    def generate_project_recommendations(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate realistic project recommendations."""
        available_components = [d["class_name"] for d in detections]
        available_capabilities = []
        
        for detection in detections:
            available_capabilities.extend(detection.get("capabilities", []))
        
        recommendations = []
        
        for project in self.project_templates:
            # Calculate match score
            required_components = project["components_required"]
            matches = sum(1 for comp in required_components if comp in available_components)
            score = matches / len(required_components) if required_components else 0
            
            # Only recommend if score is reasonable
            if score >= 0.3:
                recommendation = project.copy()
                recommendation["score"] = score
                recommendation["components_available"] = [comp for comp in required_components if comp in available_components]
                recommendation["components_needed"] = [comp for comp in required_components if comp not in available_components]
                recommendations.append(recommendation)
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:3]
    
    def create_enhanced_demo_image(self, detections: List[Dict[str, Any]], image: np.ndarray) -> np.ndarray:
        """Create enhanced demo image with realistic annotations."""
        # Convert to PIL Image
        if isinstance(image, np.ndarray):
            pil_image = Image.fromarray(image)
        else:
            pil_image = image
        
        draw = ImageDraw.Draw(pil_image)
        
        # Color scheme for different component types
        colors = {
            'ic_chip': (255, 0, 0),      # Red
            'capacitor': (0, 255, 0),     # Green
            'resistor': (0, 0, 255),      # Blue
            'connector': (255, 255, 0),   # Yellow
            'transformer': (255, 0, 255), # Magenta
            'diode': (0, 255, 255)        # Cyan
        }
        
        for detection in detections:
            bbox = detection.get('bbox', [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                component_type = detection.get('class_name', 'unknown')
                confidence = detection.get('confidence', 0)
                variant = detection.get('variant', '')
                
                # Get color for component type
                color = colors.get(component_type, (128, 128, 128))
                
                # Draw bounding box
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                
                # Draw label with variant
                label = f"{component_type} ({variant}) - {confidence:.2f}"
                draw.text((x1, y1-25), label, fill=color)
                
                # Draw confidence bar
                bar_width = int((x2 - x1) * confidence)
                draw.rectangle([x1, y2+2, x1+bar_width, y2+6], fill=color)
        
        return np.array(pil_image)
    
    def generate_component_details(self, component_type: str) -> Dict[str, Any]:
        """Generate detailed component information."""
        template = self.component_templates.get(component_type, {})
        
        return {
            "type": component_type,
            "variants": template.get("variants", []),
            "capabilities": template.get("capabilities", []),
            "educational_value": template.get("educational_value", "medium"),
            "reuse_value": template.get("reuse_value", "medium"),
            "market_value_range": template.get("market_value_range", (0.01, 1.00)),
            "common_applications": self._get_common_applications(component_type),
            "testing_procedures": self._get_testing_procedures(component_type),
            "safety_notes": self._get_safety_notes(component_type)
        }
    
    def _get_common_applications(self, component_type: str) -> List[str]:
        """Get common applications for component type."""
        applications = {
            "ic_chip": ["Microcontrollers", "Signal processing", "Control systems", "IoT devices"],
            "capacitor": ["Power filtering", "Audio circuits", "Timing circuits", "Voltage regulation"],
            "resistor": ["Current limiting", "Voltage division", "Biasing circuits", "Load simulation"],
            "connector": ["Signal transmission", "Power distribution", "Modular design", "Data communication"],
            "transformer": ["Voltage conversion", "Isolation", "Power distribution", "Signal coupling"],
            "diode": ["Rectification", "Voltage regulation", "Signal detection", "Protection circuits"]
        }
        return applications.get(component_type, ["General electronics"])
    
    def _get_testing_procedures(self, component_type: str) -> List[str]:
        """Get testing procedures for component type."""
        procedures = {
            "ic_chip": ["Visual inspection", "Power supply test", "Functional test", "Pin continuity"],
            "capacitor": ["Capacitance measurement", "ESR test", "Leakage test", "Visual inspection"],
            "resistor": ["Resistance measurement", "Power rating check", "Visual inspection", "Tolerance verification"],
            "connector": ["Continuity test", "Pin inspection", "Mating test", "Visual inspection"],
            "transformer": ["Primary/secondary resistance", "Insulation test", "Voltage ratio test", "Visual inspection"],
            "diode": ["Forward bias test", "Reverse bias test", "Voltage drop test", "Visual inspection"]
        }
        return procedures.get(component_type, ["Basic functional test"])
    
    def _get_safety_notes(self, component_type: str) -> List[str]:
        """Get safety notes for component type."""
        safety_notes = {
            "ic_chip": ["Discharge capacitors before handling", "Use ESD protection", "Check power supply polarity"],
            "capacitor": ["Discharge before handling", "Check voltage ratings", "Avoid reverse polarity"],
            "resistor": ["Check power ratings", "Avoid overheating", "Use appropriate wattage"],
            "connector": ["Check pin alignment", "Avoid forced insertion", "Inspect for damage"],
            "transformer": ["High voltage hazard", "Check insulation", "Use proper grounding"],
            "diode": ["Check polarity", "Avoid reverse voltage", "Check current ratings"]
        }
        return safety_notes.get(component_type, ["Handle with care", "Check specifications"])


def main():
    """Test enhanced demo system."""
    print("🎯 Enhanced Demo System Test")
    print("=" * 40)
    
    demo_system = EnhancedDemoSystem()
    
    # Create test image
    test_image = np.ones((400, 600, 3), dtype=np.uint8) * 255
    
    # Generate realistic detections
    detections = demo_system.generate_realistic_detections(test_image)
    
    print(f"✅ Generated {len(detections)} realistic detections")
    
    # Generate analysis summary
    summary = demo_system.generate_analysis_summary(detections)
    print(f"✅ Analysis summary: {summary['total_components']} components, ${summary['total_market_value']:.2f} value")
    
    # Generate project recommendations
    recommendations = demo_system.generate_project_recommendations(detections)
    print(f"✅ Generated {len(recommendations)} project recommendations")
    
    # Test component details
    component_details = demo_system.generate_component_details("ic_chip")
    print(f"✅ Component details: {len(component_details['capabilities'])} capabilities")
    
    print("\n📋 Demo System Ready for Platform Development!")


if __name__ == "__main__":
    main() 