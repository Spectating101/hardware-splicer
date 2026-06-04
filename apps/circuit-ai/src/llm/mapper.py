import json
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config import settings
from src.llm.llm_integration import CircuitLLMIntegration

# Import your existing LLM engine components
try:
    from src.services.llm_service.llm_manager import LLMManager
    from src.services.llm_service.model_dispatcher import ModelDispatcher
    LLM_ENGINE_AVAILABLE = True
except ImportError:
    LLM_ENGINE_AVAILABLE = False
    logger.warning("LLM engine not available, using fallback analysis")


class FunctionalMapper:
    """LLM-powered mapper for converting component detections to functional metadata."""
    
    def __init__(self):
        """Initialize the functional mapper."""
        self.component_database = self._load_component_database()
        self.project_templates = self._load_project_templates()
        
        # Initialize LLM engine if available
        if LLM_ENGINE_AVAILABLE:
            try:
                self.llm_manager = LLMManager()
                self.model_dispatcher = ModelDispatcher()
                logger.info("LLM engine initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize LLM engine: {e}")
                self.llm_manager = None
                self.model_dispatcher = None
        else:
            self.llm_manager = None
            self.model_dispatcher = None

        # Provider-agnostic LLM integration (Cohere/Mistral/Cerebras via LiteLLM)
        try:
            self.llm_integration = CircuitLLMIntegration()
        except Exception as e:
            logger.warning(f"LiteLLM integration unavailable: {e}")
            self.llm_integration = None
    
    def _load_component_database(self) -> Dict[str, Any]:
        """Load component database with functional metadata."""
        # Try external YAML content first
        try:
            import yaml
            from pathlib import Path
            path = Path("data/content/components.yaml")
            if path.exists():
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
                # normalize to expected keys
                return {k: {
                    "type": v.get("type"),
                    "capabilities": v.get("capabilities", []),
                    "projects": [],
                    "reuse_value": v.get("reuse_value", "unknown"),
                    "difficulty": v.get("difficulty", "beginner"),
                    "market_value": v.get("market_value", 0.0),
                    "educational_value": v.get("educational_value", "medium"),
                    "repair_guide": v.get("repair_guide", "")
                } for k, v in (data or {}).items()}
        except Exception:
            pass
        # Fallback built-in database
        return {
            "ic_chip": {
                "type": "microcontroller",
                "capabilities": ["arduino_projects", "iot_devices", "educational_electronics", "signal_processing"],
                "projects": ["weather_station", "led_controller", "motor_control", "data_logger"],
                "reuse_value": "high",
                "difficulty": "beginner",
                "market_value": 0.50,
                "educational_value": "high",
                "repair_guide": "Test with multimeter, check for shorts, verify power supply"
            },
            "capacitor": {
                "type": "passive_component",
                "capabilities": ["power_filtering", "audio_circuits", "voltage_regulation", "timing_circuits"],
                "projects": ["audio_amplifier", "power_supply", "filter_circuit", "oscillator"],
                "reuse_value": "medium",
                "difficulty": "beginner",
                "market_value": 0.25,
                "educational_value": "medium",
                "repair_guide": "Check capacitance with meter, look for bulging, test ESR"
            },
            "resistor": {
                "type": "passive_component",
                "capabilities": ["current_limiting", "voltage_division", "biasing", "load_simulation"],
                "projects": ["led_circuit", "voltage_divider", "sensor_interface", "current_source"],
                "reuse_value": "low",
                "difficulty": "beginner",
                "market_value": 0.01,
                "educational_value": "high",
                "repair_guide": "Measure resistance, check for burns, verify tolerance"
            },
            "connector": {
                "type": "interface_component",
                "capabilities": ["signal_transmission", "power_distribution", "modular_design", "data_communication"],
                "projects": ["breadboard_adapter", "cable_assembly", "test_interface", "modular_system"],
                "reuse_value": "high",
                "difficulty": "beginner",
                "market_value": 0.10,
                "educational_value": "medium",
                "repair_guide": "Check for bent pins, test continuity, clean contacts"
            },
            "transformer": {
                "type": "power_component",
                "capabilities": ["voltage_conversion", "isolation", "power_distribution", "signal_coupling"],
                "projects": ["power_supply", "audio_amplifier", "isolation_circuit", "voltage_converter"],
                "reuse_value": "high",
                "difficulty": "intermediate",
                "market_value": 2.00,
                "educational_value": "high",
                "repair_guide": "Check primary/secondary resistance, look for shorts, test insulation"
            },
            "diode": {
                "type": "semiconductor",
                "capabilities": ["rectification", "voltage_regulation", "signal_detection", "protection"],
                "projects": ["power_supply", "detector_circuit", "protection_circuit", "voltage_regulator"],
                "reuse_value": "medium",
                "difficulty": "beginner",
                "market_value": 0.05,
                "educational_value": "medium",
                "repair_guide": "Test forward/reverse bias, check for shorts, verify voltage drop"
            }
        }
    
    def _load_project_templates(self) -> Dict[str, Any]:
        """Load project templates for recommendations."""
        # Try external YAML first
        try:
            import yaml
            from pathlib import Path
            path = Path("data/content/projects.yaml")
            if path.exists():
                with open(path, "r") as f:
                    data = yaml.safe_load(f) or {}
                return data
        except Exception:
            pass
        # Fallback built-in templates
        return {
            "arduino_weather_station": {
                "name": "Arduino Weather Station",
                "description": "Build a weather station using salvaged components for environmental monitoring",
                "difficulty": "beginner",
                "time_estimate": "4-6 hours",
                "components_needed": ["microcontroller", "sensor", "display", "connector"],
                "instructions": "Connect sensors to Arduino, upload code, display readings",
                "educational_value": "high",
                "market_value": 25.00,
                "skills_learned": ["arduino_programming", "sensor_integration", "data_logging", "electronics_basics"],
                "estimated_cost": "$15.00",
                "safety_level": "low",
                "tools_required": ["soldering_iron", "multimeter", "breadboard", "arduino_ide"]
            },
            "audio_amplifier": {
                "name": "Audio Amplifier",
                "description": "Create an audio amplifier from salvaged components for sound projects",
                "difficulty": "intermediate",
                "time_estimate": "6-8 hours",
                "components_needed": ["op_amp", "capacitor", "resistor", "connector"],
                "instructions": "Build amplifier circuit, test with audio source",
                "educational_value": "high",
                "market_value": 45.00,
                "skills_learned": ["analog_circuits", "audio_engineering", "signal_processing", "power_electronics"],
                "estimated_cost": "$8.00",
                "safety_level": "medium",
                "tools_required": ["oscilloscope", "soldering_iron", "multimeter", "breadboard"]
            },
            "led_pattern_controller": {
                "name": "LED Pattern Controller",
                "description": "Design an LED pattern controller for creative lighting projects",
                "difficulty": "beginner",
                "time_estimate": "3-4 hours",
                "components_needed": ["microcontroller", "led", "resistor", "connector"],
                "instructions": "Connect LEDs to microcontroller, program patterns",
                "educational_value": "medium",
                "market_value": 20.00,
                "skills_learned": ["digital_circuits", "programming", "creative_electronics", "basic_electronics"],
                "estimated_cost": "$5.00",
                "safety_level": "low",
                "tools_required": ["breadboard", "arduino_ide", "multimeter", "leds"]
            },
            "power_supply_unit": {
                "name": "Power Supply Unit",
                "description": "Build a regulated power supply from salvaged parts for reliable power",
                "difficulty": "advanced",
                "time_estimate": "8-10 hours",
                "components_needed": ["transformer", "voltage_regulator", "capacitor", "diode"],
                "instructions": "Assemble transformer circuit, add voltage regulation, test output",
                "educational_value": "high",
                "market_value": 60.00,
                "skills_learned": ["power_electronics", "voltage_regulation", "safety_design", "advanced_electronics"],
                "estimated_cost": "$12.00",
                "safety_level": "high",
                "tools_required": ["oscilloscope", "multimeter", "soldering_iron", "safety_equipment"]
            },
            "data_logger": {
                "name": "Data Logger",
                "description": "Create a data logging system for environmental monitoring and research",
                "difficulty": "intermediate",
                "time_estimate": "6-8 hours",
                "components_needed": ["microcontroller", "sensor", "memory", "connector"],
                "instructions": "Connect sensors, implement data storage, create logging interface",
                "educational_value": "high",
                "market_value": 35.00,
                "skills_learned": ["data_acquisition", "sensor_calibration", "embedded_systems", "programming"],
                "estimated_cost": "$18.00",
                "safety_level": "low",
                "tools_required": ["breadboard", "arduino_ide", "multimeter", "sensors"]
            }
        }
    
    def analyze_component_with_llm(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to analyze component functionality and provide insights."""
        if not self.llm_manager:
            return self._fallback_analysis(component_data)
        
        try:
            prompt = f"""
            Analyze this electronic component for educational and reuse potential:
            
            Component Type: {component_data.get('type', 'unknown')}
            Detection Confidence: {component_data.get('detection_confidence', 0):.2f}
            Capabilities: {', '.join(component_data.get('capabilities', []))}
            
            Provide analysis in JSON format with:
            1. Educational value assessment
            2. Reuse potential analysis
            3. Common failure modes
            4. Testing procedures
            5. Safety considerations
            """
            
            response = self.llm_manager.generate_response(prompt)
            
            # Parse LLM response (assuming JSON format)
            try:
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                # Fallback if LLM doesn't return valid JSON
                return self._fallback_analysis(component_data)
                
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_analysis(component_data)
    
    def _fallback_analysis(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis when LLM is unavailable."""
        component_type = component_data.get("class_name", "unknown")
        db_entry = self.component_database.get(component_type, {})
        
        return {
            "type": db_entry.get("type", "unknown"),
            "capabilities": db_entry.get("capabilities", []),
            "reuse_value": db_entry.get("reuse_value", "unknown"),
            "difficulty": db_entry.get("difficulty", "beginner"),
            "market_value": db_entry.get("market_value", 0.0),
            "educational_value": db_entry.get("educational_value", "medium"),
            "repair_guide": db_entry.get("repair_guide", ""),
            "analysis_confidence": 0.6  # Lower confidence for fallback
        }
    
    def generate_repair_guide(self, component_data: Dict[str, Any]) -> str:
        """Generate repair guide for a component."""
        repair_guide = component_data.get("repair_guide", "No repair guide available.")
        
        if self.llm_manager:
            try:
                prompt = f"""
                Generate a detailed repair guide for this electronic component:
                
                Component: {component_data.get('type', 'unknown')}
                Current repair guide: {repair_guide}
                
                Provide a step-by-step repair guide including:
                1. Safety precautions
                2. Required tools
                3. Testing procedures
                4. Common solutions
                5. When to replace vs repair
                """
                
                enhanced_guide = self.llm_manager.generate_response(prompt)
                return enhanced_guide
            except Exception as e:
                logger.error(f"Failed to generate enhanced repair guide: {e}")
                return repair_guide
        
        return repair_guide
    
    def map_detections_to_functionality(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Map component detections to functional metadata with enhanced analysis."""
        if not detections:
            return {"components": [], "capabilities": [], "project_potential": "none"}
        
        mapped_components = []
        all_capabilities = set()
        component_counts = {}
        total_market_value = 0.0
        
        for detection in detections:
            class_name = detection['class_name']
            component_info = self.component_database.get(class_name, {})
            
            # Enhanced component mapping
            mapped_component = {
                "id": f"{class_name}_{len(mapped_components)}",
                "type": class_name,
                "capabilities": component_info.get("capabilities", []),
                "reuse_value": component_info.get("reuse_value", "unknown"),
                "difficulty": component_info.get("difficulty", "unknown"),
                "detection_confidence": detection['confidence'],
                "bbox": detection['bbox'],
                "market_value": component_info.get("market_value", 0.0),
                "educational_value": component_info.get("educational_value", "medium"),
                "repair_guide": component_info.get("repair_guide", "No guide available")
            }

            # Simple pricing heuristic: base market value adjusted by confidence and OCR presence
            try:
                price = float(component_info.get("market_value", 0.0))
                confidence = float(detection.get("confidence", 0.0))
                # Confidence factor: 0.5 to 1.0 multiplier
                price *= (0.5 + 0.5 * max(0.0, min(confidence, 1.0)))
                # OCR part number bonus implies identifiable part → higher resale
                if detection.get("part_number") or detection.get("ocr_text"):
                    # Apply class-dependent multiplier
                    cls_bonus = {
                        "ic_chip": 1.8,
                        "connector": 1.3,
                        "transformer": 1.2,
                        "resistor": 1.05,
                        "capacitor": 1.1,
                        "diode": 1.1,
                    }.get(class_name, 1.1)
                    price *= cls_bonus
                mapped_component["price_estimate"] = round(price, 2)
            except Exception:
                mapped_component["price_estimate"] = component_info.get("market_value", 0.0)
            
            # Add LLM analysis if available (engine or provider-agnostic)
            try:
                if self.llm_manager and settings.llm_enabled:
                    llm_analysis = self.analyze_component_with_llm(mapped_component)
                    mapped_component["llm_analysis"] = llm_analysis
                elif self.llm_integration and settings.llm_enabled:
                    llm_analysis = self.llm_integration.analyze_component_advanced(mapped_component)
                    mapped_component["llm_analysis"] = llm_analysis
            except Exception as e:
                logger.debug(f"LLM analysis skipped: {e}")
            
            mapped_components.append(mapped_component)
            
            # Track capabilities and values
            all_capabilities.update(component_info.get("capabilities", []))
            total_market_value += mapped_component.get("price_estimate", component_info.get("market_value", 0.0))
            
            if class_name not in component_counts:
                component_counts[class_name] = 0
            component_counts[class_name] += 1
        
        return {
            "components": mapped_components,
            "capabilities": list(all_capabilities),
            "component_counts": component_counts,
            "total_components": len(detections),
            "total_market_value": total_market_value,
            "project_potential": self._assess_project_potential(mapped_components),
            "educational_potential": self._assess_educational_potential(mapped_components)
        }
    
    def _assess_educational_potential(self, components: List[Dict]) -> str:
        """Assess educational potential based on components."""
        if not components:
            return "none"
        
        high_edu_count = len([c for c in components if c.get("educational_value") == "high"])
        total_count = len(components)
        
        if high_edu_count / total_count > 0.5:
            return "excellent"
        elif high_edu_count / total_count > 0.3:
            return "good"
        elif high_edu_count / total_count > 0.1:
            return "fair"
        else:
            return "poor"
    
    def generate_project_recommendations(self, functionality_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate project recommendations based on available components."""
        try:
            components = functionality_data.get("components", [])
            capabilities = functionality_data.get("capabilities", [])
            
            if not components:
                return []
            
            # Get project templates
            project_templates = self._load_project_templates()
            
            recommendations = []
            for project_id, template in project_templates.items():
                # Calculate compatibility score
                score = self._calculate_project_score(template, capabilities, components)
                
                if score > 0.3:  # Only recommend if reasonable match
                    recommendation = {
                        "project_id": project_id,
                        "name": template.get("name", project_id),
                        "description": template.get("description", ""),
                        "difficulty": template.get("difficulty", "beginner"),
                        "time_estimate": template.get("time_estimate", "2-4 hours"),
                        "score": score,
                        "components_available": template.get("components_needed", []),
                        "components_needed": template.get("components_needed", []),
                        "instructions": template.get("instructions", "Follow standard electronics assembly procedures")
                    }
                    recommendations.append(recommendation)
            
            # Sort by score and return top 5
            recommendations.sort(key=lambda x: x["score"], reverse=True)
            return recommendations[:5]
            
        except Exception as e:
            logger.error(f"Error generating project recommendations: {e}")
            return []
    
    def _calculate_project_score(self, template: Dict[str, Any], capabilities: List[str], components: List[Dict]) -> float:
        """Calculate compatibility score between project template and available components."""
        try:
            score = 0.0
            
            # Check capability overlap
            template_capabilities = template.get("capabilities", [])
            capability_overlap = len(set(capabilities) & set(template_capabilities))
            if template_capabilities:
                score += (capability_overlap / len(template_capabilities)) * 0.4
            
            # Check component availability
            needed_components = template.get("components_needed", [])
            available_types = [comp.get("class_name", "") for comp in components]
            component_overlap = len(set(needed_components) & set(available_types))
            if needed_components:
                score += (component_overlap / len(needed_components)) * 0.4
            
            # Difficulty bonus (prefer beginner projects)
            difficulty = template.get("difficulty", "beginner")
            if difficulty == "beginner":
                score += 0.2
            elif difficulty == "intermediate":
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating project score: {e}")
            return 0.0
    
    def _get_available_components(self, template: Dict[str, Any], components: List[Dict]) -> List[str]:
        """Get list of available components for a project."""
        required = template.get("components_needed", [])
        available_types = [comp["type"] for comp in components]
        
        return [req for req in required if req in available_types]
    
    def _assess_project_potential(self, components: List[Dict]) -> str:
        """Assess overall project potential based on components."""
        if not components:
            return "none"
        
        high_value_count = len([c for c in components if c.get("reuse_value") == "high"])
        total_count = len(components)
        
        if high_value_count / total_count > 0.5:
            return "excellent"
        elif high_value_count / total_count > 0.3:
            return "good"
        elif high_value_count / total_count > 0.1:
            return "fair"
        else:
            return "poor" 