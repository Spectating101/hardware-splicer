import numpy as np
from PIL import Image
from typing import Dict, Any, List
from loguru import logger
from src.vision.detector import ComponentDetector
from src.llm.mapper import FunctionalMapper


class CircuitAnalyzer:
    """Main orchestrator for PCB analysis pipeline."""
    
    def __init__(self):
        """Initialize the circuit analyzer."""
        self.detector = ComponentDetector()
        self.mapper = FunctionalMapper()
        logger.info("CircuitAnalyzer initialized")
    
    def analyze_pcb(self, image: np.ndarray, backend: str | None = None, enable_ocr: bool | None = None) -> Dict[str, Any]:
        """Complete PCB analysis pipeline."""
        try:
            logger.info("Starting PCB analysis")
            
            # Step 1: Preprocess image
            processed_image = self.detector.preprocess_image(image)
            
            # Step 2: Detect components
            detections = self.detector.detect_components(processed_image, backend=backend, enable_ocr=enable_ocr)
            
            # Step 3: Generate detection summary
            detection_summary = self.detector.get_detection_summary(detections)
            
            # Step 4: Map to functional metadata
            functionality_data = self.mapper.map_detections_to_functionality(detections)
            
            # Step 5: Generate project recommendations
            recommendations = self.mapper.generate_project_recommendations(functionality_data)
            
            # Step 6: Compile results
            results = {
                "detections": detections,
                "detection_summary": detection_summary,
                "functionality_analysis": functionality_data,
                "project_recommendations": recommendations,
                "analysis_metadata": {
                    "total_processing_time": "~2 seconds",
                    "detection_quality": detection_summary.get("detection_quality", "unknown"),
                    "project_potential": functionality_data.get("project_potential", "none"),
                    "backend": backend or self.detector.default_backend,
                    "ocr": bool(enable_ocr) if enable_ocr is not None else self.detector.ocr_enabled_default
                }
            }
            
            logger.info(f"Analysis complete: {detection_summary.get('total_components', 0)} components detected")
            return results
            
        except Exception as e:
            logger.error(f"Error in PCB analysis: {e}")
            return {
                "error": str(e),
                "detection_summary": {"total_components": 0},
                "functionality_analysis": {"components": [], "capabilities": []},
                "project_recommendations": []
            }
    
    def analyze_from_file(self, image_path: str) -> Dict[str, Any]:
        """Analyze PCB from image file."""
        try:
            # Load image
            image = Image.open(image_path)
            image_np = np.array(image)
            
            return self.analyze_pcb(image_np)
            
        except Exception as e:
            logger.error(f"Error loading image from {image_path}: {e}")
            return {
                "error": f"Could not load image: {str(e)}",
                "detection_summary": {"total_components": 0},
                "functionality_analysis": {"components": [], "capabilities": []},
                "project_recommendations": []
            }
    
    def get_analysis_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable summary of analysis results."""
        detection_summary = results.get("detection_summary", {})
        functionality_data = results.get("functionality_analysis", {})
        recommendations = results.get("project_recommendations", [])
        
        total_components = detection_summary.get("total_components", 0)
        components_by_type = detection_summary.get("components_by_type", {})
        project_potential = functionality_data.get("project_potential", "none")
        
        # Generate summary text
        summary_text = f"Found {total_components} components on this PCB. "
        
        if components_by_type:
            component_list = [f"{count} {comp_type}" for comp_type, count in components_by_type.items()]
            summary_text += f"Components include: {', '.join(component_list)}. "
        
        if project_potential != "none":
            summary_text += f"Project potential: {project_potential}. "
        
        if recommendations:
            top_recommendation = recommendations[0]
            summary_text += f"Top recommendation: {top_recommendation['name']} ({top_recommendation['difficulty']} level)."
        else:
            summary_text += "No specific project recommendations available."
        
        return {
            "summary_text": summary_text,
            "total_components": total_components,
            "project_potential": project_potential,
            "top_recommendation": recommendations[0] if recommendations else None,
            "component_breakdown": components_by_type
        }
    
    def generate_demo_data(self) -> Dict[str, Any]:
        """Generate demo data for testing and presentation."""
        return {
            "detection_summary": {
                "total_components": 47,
                "components_by_type": {
                    "ic_chip": 8,
                    "capacitor": 12,
                    "resistor": 27
                },
                "average_confidence": 0.85,
                "detection_quality": "high"
            },
            "functionality_analysis": {
                "components": [
                    {
                        "id": "ic_chip_1",
                        "type": "ic_chip",
                        "capabilities": ["arduino_projects", "iot_devices"],
                        "reuse_value": "high",
                        "difficulty": "beginner"
                    }
                ],
                "capabilities": ["arduino_projects", "iot_devices", "power_filtering"],
                "component_counts": {"ic_chip": 8, "capacitor": 12, "resistor": 27},
                "total_components": 47,
                "project_potential": "excellent"
            },
            "project_recommendations": [
                {
                    "project_id": "weather_station",
                    "name": "Arduino Weather Station",
                    "description": "Monitor temperature, humidity, and pressure",
                    "difficulty": "beginner",
                    "time_estimate": "2-4 hours",
                    "score": 0.8,
                    "components_available": ["microcontroller"],
                    "components_needed": ["microcontroller", "sensor", "display"],
                    "instructions": "Connect sensors to Arduino, upload code, display readings"
                }
            ],
            "analysis_metadata": {
                "total_processing_time": "1.8 seconds",
                "detection_quality": "high",
                "project_potential": "excellent"
            }
        } 