import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
import hashlib
import time

from src.llm.llm_integration import CircuitLLMIntegration
from src.services.cache_service import analysis_cache
from src.vision.enhanced_detector import ComponentDetection

@dataclass
class EducationalContent:
    title: str
    content: str
    difficulty: str  # 'beginner', 'intermediate', 'advanced'
    component_type: str
    video_url: Optional[str] = None
    interactive_demo: Optional[str] = None
    quiz_questions: List[Dict[str, Any]] = None
    learning_objectives: List[str] = None
    prerequisites: List[str] = None
    estimated_time: str = "15 minutes"

@dataclass
class RepairRecommendation:
    component_type: str
    issue: str
    symptoms: List[str]
    solutions: List[str]
    difficulty: str
    tools_needed: List[str]
    safety_notes: List[str]
    estimated_time: str
    success_rate: float

@dataclass
class ProjectRecommendation:
    id: str
    name: str
    description: str
    difficulty: str
    components_needed: List[str]
    estimated_cost: float
    time_required: str
    skills_developed: List[str]
    tutorial_url: Optional[str] = None
    score: float
    category: str
    popularity: int
    rating: float
    tags: List[str] = None

class EnhancedFunctionalMapper:
    """Enhanced LLM-powered mapper with advanced AI features."""
    
    def __init__(self):
        """Initialize the enhanced functional mapper."""
        self.llm_integration = CircuitLLMIntegration()
        self.component_database = self._load_enhanced_component_database()
        self.project_templates = self._load_enhanced_project_templates()
        self.educational_content = self._load_educational_content()
        self.repair_guides = self._load_repair_guides()
        
        # Analysis statistics
        self.analysis_stats = {
            "total_analyses": 0,
            "components_analyzed": 0,
            "projects_generated": 0,
            "educational_content_created": 0
        }
        
        logger.info("Enhanced functional mapper initialized")
    
    def _load_enhanced_component_database(self) -> Dict[str, Any]:
        """Load enhanced component database with detailed metadata."""
        return {
            "ic_chip": {
                "type": "microcontroller",
                "capabilities": [
                    "arduino_projects", "iot_devices", "educational_electronics", 
                    "signal_processing", "data_logging", "sensor_control",
                    "motor_control", "display_control", "communication"
                ],
                "projects": [
                    "weather_station", "led_controller", "motor_control", 
                    "data_logger", "smart_home_controller", "robot_brain"
                ],
                "reuse_value": "high",
                "difficulty": "beginner",
                "market_value": 0.50,
                "educational_value": "high",
                "repair_guide": "Test with multimeter, check for shorts, verify power supply",
                "datasheet_url": "https://example.com/datasheet/ic_chip",
                "manufacturer": "Texas Instruments",
                "part_number": "LM358",
                "description": "Dual operational amplifier",
                "pin_count": 8,
                "package_type": "DIP-8",
                "power_requirements": "3-15V",
                "temperature_range": "-40°C to +85°C",
                "common_applications": ["Audio amplifiers", "Signal conditioning", "Voltage comparators"],
                "learning_topics": ["Operational amplifiers", "Analog circuits", "Signal processing"]
            },
            "capacitor": {
                "type": "passive_component",
                "capabilities": [
                    "power_filtering", "audio_circuits", "voltage_regulation", 
                    "timing_circuits", "signal_coupling", "noise_reduction",
                    "energy_storage", "frequency_filtering"
                ],
                "projects": [
                    "audio_amplifier", "power_supply", "filter_circuit", 
                    "oscillator", "noise_filter", "energy_storage_system"
                ],
                "reuse_value": "medium",
                "difficulty": "beginner",
                "market_value": 0.25,
                "educational_value": "high",
                "repair_guide": "Check capacitance with meter, look for bulging, test ESR",
                "datasheet_url": "https://example.com/datasheet/capacitor",
                "manufacturer": "Murata",
                "part_number": "GRM188R71C104K",
                "description": "100nF ceramic capacitor",
                "package_type": "0603",
                "capacitance": "100nF",
                "voltage_rating": "50V",
                "tolerance": "±10%",
                "temperature_coefficient": "X7R",
                "common_applications": ["Power supply filtering", "Audio coupling", "Timing circuits"],
                "learning_topics": ["Capacitance", "AC circuits", "Filtering"]
            },
            "resistor": {
                "type": "passive_component",
                "capabilities": [
                    "current_limiting", "voltage_division", "biasing", 
                    "load_simulation", "signal_attenuation", "temperature_sensing"
                ],
                "projects": [
                    "led_circuit", "voltage_divider", "sensor_interface", 
                    "current_source", "attenuator", "temperature_sensor"
                ],
                "reuse_value": "low",
                "difficulty": "beginner",
                "market_value": 0.01,
                "educational_value": "high",
                "repair_guide": "Measure resistance, check for burns, verify tolerance",
                "datasheet_url": "https://example.com/datasheet/resistor",
                "manufacturer": "Vishay",
                "part_number": "CRCW0603100RFKEA",
                "description": "100Ω carbon film resistor",
                "package_type": "0603",
                "resistance": "100Ω",
                "power_rating": "0.1W",
                "tolerance": "±1%",
                "temperature_coefficient": "±100ppm/°C",
                "common_applications": ["LED current limiting", "Voltage dividers", "Pull-up resistors"],
                "learning_topics": ["Ohm's Law", "Voltage division", "Power dissipation"]
            },
            "connector": {
                "type": "mechanical_component",
                "capabilities": [
                    "signal_transmission", "data_communication", "modular_design",
                    "power_distribution", "interfacing", "modularity"
                ],
                "projects": [
                    "modular_system", "data_interface", "power_distribution",
                    "sensor_module", "display_interface", "communication_system"
                ],
                "reuse_value": "high",
                "difficulty": "beginner",
                "market_value": 0.10,
                "educational_value": "medium",
                "repair_guide": "Check for bent pins, clean contacts, verify continuity",
                "datasheet_url": "https://example.com/datasheet/connector",
                "manufacturer": "Molex",
                "part_number": "22-01-2027",
                "description": "2-pin header connector",
                "pin_count": 2,
                "package_type": "THT",
                "pitch": "2.54mm",
                "current_rating": "3A",
                "voltage_rating": "250V",
                "contact_material": "Brass",
                "common_applications": ["Sensor connections", "Power distribution", "Data interfaces"],
                "learning_topics": ["Connector types", "Signal integrity", "Modular design"]
            }
        }
    
    def _load_enhanced_project_templates(self) -> List[ProjectRecommendation]:
        """Load enhanced project templates with detailed information."""
        return [
            ProjectRecommendation(
                id="proj_001",
                name="Arduino Audio Amplifier",
                description="Build a simple audio amplifier using operational amplifiers and capacitors for signal processing and filtering.",
                difficulty="beginner",
                components_needed=["ic_chip", "capacitor", "resistor"],
                estimated_cost=5.50,
                time_required="2-3 hours",
                skills_developed=["soldering", "circuit_design", "audio_electronics", "signal_processing"],
                tutorial_url="https://example.com/tutorials/audio-amplifier",
                score=0.85,
                category="audio",
                popularity=95,
                rating=4.8,
                tags=["audio", "amplifier", "beginner", "arduino"]
            ),
            ProjectRecommendation(
                id="proj_002",
                name="IoT Sensor Hub",
                description="Create an IoT sensor hub using microcontrollers and connectors for data collection and transmission.",
                difficulty="intermediate",
                components_needed=["ic_chip", "connector", "capacitor"],
                estimated_cost=12.00,
                time_required="4-6 hours",
                skills_developed=["programming", "iot", "sensor_integration", "data_communication"],
                tutorial_url="https://example.com/tutorials/iot-hub",
                score=0.78,
                category="iot",
                popularity=87,
                rating=4.6,
                tags=["iot", "sensors", "intermediate", "data"]
            ),
            ProjectRecommendation(
                id="proj_003",
                name="Smart LED Controller",
                description="Design a smart LED controller with PWM dimming and color control using microcontrollers and resistors.",
                difficulty="beginner",
                components_needed=["ic_chip", "resistor", "led"],
                estimated_cost=8.00,
                time_required="3-4 hours",
                skills_developed=["pwm_control", "led_driving", "microcontroller_programming"],
                tutorial_url="https://example.com/tutorials/led-controller",
                score=0.82,
                category="lighting",
                popularity=92,
                rating=4.7,
                tags=["led", "lighting", "beginner", "pwm"]
            ),
            ProjectRecommendation(
                id="proj_004",
                name="Power Supply Filter",
                description="Build a power supply filter using capacitors and inductors for noise reduction and voltage regulation.",
                difficulty="intermediate",
                components_needed=["capacitor", "inductor", "resistor"],
                estimated_cost=6.50,
                time_required="2-3 hours",
                skills_developed=["power_electronics", "filtering", "noise_reduction"],
                tutorial_url="https://example.com/tutorials/power-filter",
                score=0.75,
                category="power",
                popularity=78,
                rating=4.5,
                tags=["power", "filtering", "intermediate", "noise"]
            )
        ]
    
    def _load_educational_content(self) -> Dict[str, EducationalContent]:
        """Load educational content for different component types."""
        return {
            "ic_chip": EducationalContent(
                title="Understanding Operational Amplifiers",
                content="Operational amplifiers (op-amps) are fundamental building blocks in analog electronics. They are high-gain voltage amplifiers with differential inputs and single-ended output. Op-amps are used in a wide variety of applications including amplifiers, filters, oscillators, and comparators.",
                difficulty="intermediate",
                component_type="ic_chip",
                video_url="https://example.com/videos/op-amps",
                interactive_demo="https://example.com/demos/op-amp-simulator",
                quiz_questions=[
                    {
                        "question": "What is the primary function of an operational amplifier?",
                        "options": ["Voltage amplification", "Current amplification", "Power amplification", "Frequency amplification"],
                        "correct_answer": 0,
                        "explanation": "Operational amplifiers are primarily used for voltage amplification in electronic circuits."
                    },
                    {
                        "question": "What is the typical open-loop gain of an ideal op-amp?",
                        "options": ["100", "1000", "10000", "Infinite"],
                        "correct_answer": 3,
                        "explanation": "An ideal op-amp has infinite open-loop gain, though practical op-amps have very high but finite gain."
                    }
                ],
                learning_objectives=[
                    "Understand the basic operation of op-amps",
                    "Learn about common op-amp configurations",
                    "Apply op-amps in practical circuits"
                ],
                prerequisites=["Basic electronics", "Voltage and current concepts"],
                estimated_time="20 minutes"
            ),
            "capacitor": EducationalContent(
                title="Capacitors in Electronic Circuits",
                content="Capacitors are passive electronic components that store electrical energy in an electric field. They are essential for filtering, coupling, timing, and energy storage applications. Understanding capacitors is crucial for designing reliable electronic circuits.",
                difficulty="beginner",
                component_type="capacitor",
                video_url="https://example.com/videos/capacitors",
                interactive_demo="https://example.com/demos/capacitor-simulator",
                quiz_questions=[
                    {
                        "question": "What is the unit of capacitance?",
                        "options": ["Ohm", "Farad", "Henry", "Volt"],
                        "correct_answer": 1,
                        "explanation": "Capacitance is measured in Farads (F), named after Michael Faraday."
                    },
                    {
                        "question": "How do capacitors behave in DC circuits?",
                        "options": ["As a short circuit", "As an open circuit", "As a resistor", "As an inductor"],
                        "correct_answer": 1,
                        "explanation": "In DC circuits, capacitors act as open circuits once fully charged."
                    }
                ],
                learning_objectives=[
                    "Understand capacitor operation and characteristics",
                    "Learn about different capacitor types",
                    "Apply capacitors in filtering and timing circuits"
                ],
                prerequisites=["Basic electricity concepts"],
                estimated_time="15 minutes"
            )
        }
    
    def _load_repair_guides(self) -> Dict[str, RepairRecommendation]:
        """Load repair guides for common component issues."""
        return {
            "ic_chip": RepairRecommendation(
                component_type="ic_chip",
                issue="IC Chip Not Functioning",
                symptoms=["No output", "Incorrect output", "Overheating", "Burning smell"],
                solutions=[
                    "Check power supply voltage and current",
                    "Verify all connections and solder joints",
                    "Test with multimeter for shorts",
                    "Replace with known good component"
                ],
                difficulty="intermediate",
                tools_needed=["Multimeter", "Soldering iron", "Desoldering pump", "Oscilloscope"],
                safety_notes=[
                    "Always disconnect power before testing",
                    "Use proper ESD protection",
                    "Check for overheating components"
                ],
                estimated_time="30-60 minutes",
                success_rate=0.75
            ),
            "capacitor": RepairRecommendation(
                component_type="capacitor",
                issue="Capacitor Failure",
                symptoms=["Bulging or leaking", "Reduced capacitance", "High ESR", "Circuit instability"],
                solutions=[
                    "Replace bulging or leaking capacitors",
                    "Measure capacitance with meter",
                    "Check equivalent series resistance (ESR)",
                    "Verify voltage rating"
                ],
                difficulty="beginner",
                tools_needed=["Capacitance meter", "ESR meter", "Soldering iron", "Multimeter"],
                safety_notes=[
                    "Discharge capacitors before testing",
                    "Check polarity for electrolytic capacitors",
                    "Use appropriate voltage ratings"
                ],
                estimated_time="15-30 minutes",
                success_rate=0.90
            )
        }
    
    def map_detections_to_functionality(self, detections: List[ComponentDetection]) -> Dict[str, Any]:
        """Enhanced mapping of component detections to functional metadata."""
        try:
            components = []
            capabilities = set()
            total_market_value = 0.0
            
            for detection in detections:
                component_info = self.component_database.get(detection.class_name, {})
                
                if component_info:
                    component = {
                        "id": f"{detection.class_name}_{len(components)}",
                        "type": detection.class_name,
                        "capabilities": component_info.get("capabilities", []),
                        "reuse_value": component_info.get("reuse_value", "unknown"),
                        "market_value": component_info.get("market_value", 0.0),
                        "educational_value": component_info.get("educational_value", "medium"),
                        "datasheet_url": component_info.get("datasheet_url"),
                        "manufacturer": component_info.get("manufacturer"),
                        "part_number": component_info.get("part_number"),
                        "description": component_info.get("description"),
                        "pin_count": component_info.get("pin_count"),
                        "package_type": component_info.get("package_type"),
                        "detection_confidence": detection.confidence,
                        "detection_method": detection.method.value,
                        "bbox": detection.bbox,
                        "center": detection.center,
                        "area": detection.area,
                        "text_content": detection.text_content
                    }
                    
                    components.append(component)
                    capabilities.update(component_info.get("capabilities", []))
                    total_market_value += component_info.get("market_value", 0.0)
            
            # Calculate scores
            complexity_score = self._calculate_complexity_score(components)
            educational_score = self._calculate_educational_score(components)
            reusability_score = self._calculate_reusability_score(components)
            
            # Determine project potential
            project_potential = self._determine_project_potential(components, capabilities)
            
            functionality_data = {
                "components": components,
                "capabilities": list(capabilities),
                "total_market_value": total_market_value,
                "project_potential": project_potential,
                "complexity_score": complexity_score,
                "educational_score": educational_score,
                "reusability_score": reusability_score,
                "analysis_timestamp": datetime.now().isoformat(),
                "detection_summary": {
                    "total_components": len(components),
                    "high_confidence_detections": len([c for c in components if c["detection_confidence"] > 0.8]),
                    "detection_methods": list(set(c["detection_method"] for c in components))
                }
            }
            
            # Cache the result
            cache_key = self._generate_cache_key(detections)
            analysis_cache.set_analysis_result(cache_key, "enhanced", True, functionality_data)
            
            self.analysis_stats["components_analyzed"] += len(components)
            
            logger.info(f"Mapped {len(components)} components to functionality")
            return functionality_data
            
        except Exception as e:
            logger.error(f"Error in enhanced functionality mapping: {e}")
            return {
                "components": [],
                "capabilities": [],
                "total_market_value": 0.0,
                "project_potential": "poor",
                "complexity_score": 0.0,
                "educational_score": 0.0,
                "reusability_score": 0.0,
                "error": str(e)
            }
    
    def generate_project_recommendations(self, functionality_data: Dict[str, Any]) -> List[ProjectRecommendation]:
        """Generate enhanced project recommendations based on detected components."""
        try:
            components = functionality_data.get("components", [])
            capabilities = set(functionality_data.get("capabilities", []))
            
            # Score all project templates
            scored_projects = []
            for project in self.project_templates:
                score = self._calculate_project_score(project, components, capabilities)
                project.score = score
                scored_projects.append(project)
            
            # Sort by score and filter relevant projects
            relevant_projects = [
                p for p in scored_projects 
                if p.score > 0.3 and self._has_required_components(p, components)
            ]
            
            relevant_projects.sort(key=lambda x: x.score, reverse=True)
            
            # Limit to top recommendations
            recommendations = relevant_projects[:10]
            
            # Cache recommendations
            cache_key = self._generate_capabilities_key(capabilities)
            analysis_cache.set_project_recommendations(list(capabilities), recommendations)
            
            self.analysis_stats["projects_generated"] += len(recommendations)
            
            logger.info(f"Generated {len(recommendations)} project recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating project recommendations: {e}")
            return []
    
    def generate_educational_content(self, components: List[Dict[str, Any]]) -> List[EducationalContent]:
        """Generate educational content for detected components."""
        try:
            educational_content = []
            component_types = set(comp["type"] for comp in components)
            
            for comp_type in component_types:
                if comp_type in self.educational_content:
                    content = self.educational_content[comp_type]
                    educational_content.append(content)
            
            # Generate additional content using LLM if available
            if self.llm_integration and components:
                additional_content = self._generate_llm_educational_content(components)
                educational_content.extend(additional_content)
            
            self.analysis_stats["educational_content_created"] += len(educational_content)
            
            logger.info(f"Generated {len(educational_content)} educational content items")
            return educational_content
            
        except Exception as e:
            logger.error(f"Error generating educational content: {e}")
            return []
    
    def generate_repair_recommendations(self, components: List[Dict[str, Any]]) -> List[RepairRecommendation]:
        """Generate repair recommendations for detected components."""
        try:
            repair_recommendations = []
            component_types = set(comp["type"] for comp in components)
            
            for comp_type in component_types:
                if comp_type in self.repair_guides:
                    repair_guide = self.repair_guides[comp_type]
                    repair_recommendations.append(repair_guide)
            
            logger.info(f"Generated {len(repair_recommendations)} repair recommendations")
            return repair_recommendations
            
        except Exception as e:
            logger.error(f"Error generating repair recommendations: {e}")
            return []
    
    def _calculate_complexity_score(self, components: List[Dict[str, Any]]) -> float:
        """Calculate complexity score based on components."""
        if not components:
            return 0.0
        
        # Factors: number of components, types, pin counts, etc.
        num_components = len(components)
        num_types = len(set(comp["type"] for comp in components))
        total_pins = sum(comp.get("pin_count", 0) for comp in components)
        
        # Normalize scores
        complexity = (num_components * 0.3 + num_types * 0.4 + total_pins * 0.01) / 10
        return min(complexity, 1.0)
    
    def _calculate_educational_score(self, components: List[Dict[str, Any]]) -> float:
        """Calculate educational value score."""
        if not components:
            return 0.0
        
        educational_values = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4
        }
        
        total_score = sum(
            educational_values.get(comp.get("educational_value", "medium"), 0.7)
            for comp in components
        )
        
        return min(total_score / len(components), 1.0)
    
    def _calculate_reusability_score(self, components: List[Dict[str, Any]]) -> float:
        """Calculate reusability score."""
        if not components:
            return 0.0
        
        reuse_values = {
            "high": 1.0,
            "medium": 0.6,
            "low": 0.3
        }
        
        total_score = sum(
            reuse_values.get(comp.get("reuse_value", "medium"), 0.6)
            for comp in components
        )
        
        return min(total_score / len(components), 1.0)
    
    def _determine_project_potential(self, components: List[Dict[str, Any]], capabilities: set) -> str:
        """Determine project potential based on components and capabilities."""
        if not components:
            return "poor"
        
        # Score based on number of components and capabilities
        component_score = min(len(components) / 5.0, 1.0)
        capability_score = min(len(capabilities) / 8.0, 1.0)
        
        total_score = (component_score + capability_score) / 2
        
        if total_score > 0.8:
            return "excellent"
        elif total_score > 0.6:
            return "good"
        elif total_score > 0.4:
            return "fair"
        else:
            return "poor"
    
    def _calculate_project_score(self, project: ProjectRecommendation, 
                               components: List[Dict[str, Any]], 
                               capabilities: set) -> float:
        """Calculate how well a project matches the available components."""
        score = 0.0
        
        # Component availability (40% weight)
        available_components = set(comp["type"] for comp in components)
        required_components = set(project.components_needed)
        
        if required_components.issubset(available_components):
            score += 0.4
        else:
            # Partial match
            overlap = len(required_components.intersection(available_components))
            score += (overlap / len(required_components)) * 0.4
        
        # Capability match (30% weight)
        project_capabilities = set()
        for comp_type in project.components_needed:
            comp_info = self.component_database.get(comp_type, {})
            project_capabilities.update(comp_info.get("capabilities", []))
        
        if project_capabilities.issubset(capabilities):
            score += 0.3
        else:
            overlap = len(project_capabilities.intersection(capabilities))
            score += (overlap / len(project_capabilities)) * 0.3
        
        # Difficulty match (20% weight)
        difficulty_scores = {"beginner": 0.8, "intermediate": 0.6, "advanced": 0.4}
        score += difficulty_scores.get(project.difficulty, 0.6) * 0.2
        
        # Popularity bonus (10% weight)
        score += (project.popularity / 100.0) * 0.1
        
        return min(score, 1.0)
    
    def _has_required_components(self, project: ProjectRecommendation, 
                               components: List[Dict[str, Any]]) -> bool:
        """Check if project has required components."""
        available_components = set(comp["type"] for comp in components)
        required_components = set(project.components_needed)
        
        # Allow partial matches (at least 50% of required components)
        overlap = len(required_components.intersection(available_components))
        return overlap >= len(required_components) * 0.5
    
    def _generate_llm_educational_content(self, components: List[Dict[str, Any]]) -> List[EducationalContent]:
        """Generate educational content using LLM."""
        try:
            # This would integrate with the LLM to generate custom educational content
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error generating LLM educational content: {e}")
            return []
    
    def _generate_cache_key(self, detections: List[ComponentDetection]) -> str:
        """Generate cache key for detections."""
        detection_data = [
            {
                "class_name": d.class_name,
                "bbox": d.bbox,
                "confidence": d.confidence
            }
            for d in detections
        ]
        
        data_str = json.dumps(detection_data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _generate_capabilities_key(self, capabilities: set) -> str:
        """Generate cache key for capabilities."""
        capabilities_str = "|".join(sorted(capabilities))
        return hashlib.md5(capabilities_str.encode()).hexdigest()
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get analysis statistics."""
        return {
            **self.analysis_stats,
            "component_database_size": len(self.component_database),
            "project_templates_count": len(self.project_templates),
            "educational_content_count": len(self.educational_content),
            "repair_guides_count": len(self.repair_guides)
        }

# Global enhanced mapper instance
enhanced_mapper = EnhancedFunctionalMapper()
