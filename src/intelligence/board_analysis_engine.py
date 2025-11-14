"""
Board Analysis Engine

Unified analysis: board type + faults + repair recommendations
Answers: "What is this board?" and "What's wrong with it?"
"""

from typing import List, Dict
from loguru import logger
from src.intelligence.board_classifier import BoardClassifier
from src.intelligence.fault_detector import FaultDetector
import numpy as np


class BoardAnalysisEngine:
    """Complete board analysis: identification + fault detection + recommendations."""
    
    def __init__(self):
        """Initialize the analysis engine."""
        self.classifier = BoardClassifier()
        self.detector = FaultDetector()
        logger.info("BoardAnalysisEngine initialized")
    
    def analyze(self, image: np.ndarray, detected_components: List) -> Dict:
        """
        Complete board analysis.
        
        Args:
            image: PCB image as numpy array
            detected_components: List of detected component objects
            
        Returns:
            Dict with board type, faults, and recommendations
        """
        # Step 1: Identify board type
        board_info = self.classifier.classify(detected_components)
        
        # Step 2: Detect faults
        faults = self.detector.detect_faults(image)
        
        # Step 3: Generate recommendations
        recommendations = self._generate_recommendations(board_info, faults)
        
        return {
            "board_identification": board_info,
            "fault_analysis": faults,
            "recommendations": recommendations,
            "summary": self._generate_summary(board_info, faults, recommendations)
        }
    
    def _generate_recommendations(self, board_info: Dict, faults: Dict) -> Dict:
        """Generate repair/salvage recommendations based on board type and faults."""
        
        board_type = board_info.get("board_type", "Unknown")
        overall_condition = faults.get("overall_condition", "Unknown")
        
        recommendations = {
            "repairability": "Unknown",
            "salvage_value": "Unknown",
            "actions": [],
            "cautions": []
        }
        
        # Assess repairability
        if "Multiple serious faults" in overall_condition:
            recommendations["repairability"] = "Low - Multiple faults detected"
            recommendations["salvage_value"] = "High - Component salvage only"
        elif "Some damage" in overall_condition:
            recommendations["repairability"] = "Medium - Some repair possible"
            recommendations["salvage_value"] = "Medium - Partial recovery possible"
        elif "Minor issues" in overall_condition:
            recommendations["repairability"] = "High - Likely repairable"
            recommendations["salvage_value"] = "Low - Repair recommended"
        else:
            recommendations["repairability"] = "Excellent - Board appears functional"
            recommendations["salvage_value"] = "Very Low - Use as-is if applicable"
        
        # Board-specific recommendations
        if "Power Supply" in board_type:
            recommendations["actions"].append("✓ Check all electrolytic capacitors for bulging/leakage")
            recommendations["actions"].append("✓ Test transformer with continuity checker")
            recommendations["actions"].append("✓ Inspect MOSFET/rectifier diodes for damage")
            recommendations["cautions"].append("⚠ Power supplies may store charge - discharge before work")
            recommendations["cautions"].append("⚠ Transformer primary may be high voltage")
        
        elif "Audio Amplifier" in board_type:
            recommendations["actions"].append("✓ Check filter capacitors for leakage")
            recommendations["actions"].append("✓ Test power transistors")
            recommendations["actions"].append("✓ Verify transformer impedance")
            recommendations["cautions"].append("⚠ High voltage on output transformer")
        
        elif "Motherboard" in board_type or "Control" in board_type:
            recommendations["actions"].append("✓ Check all electrolytic capacitors")
            recommendations["actions"].append("✓ Look for burned-out MOSFETs or ICs")
            recommendations["actions"].append("✓ Verify power distribution traces")
            recommendations["cautions"].append("⚠ Complex circuits - full schematic needed for repair")
        
        elif "Power Distribution" in board_type:
            recommendations["actions"].append("✓ Check varistor for damage")
            recommendations["actions"].append("✓ Test voltage regulation circuits")
            recommendations["actions"].append("✓ Verify bulk capacitors")
            recommendations["cautions"].append("⚠ May handle high currents - check ratings")
        
        # Fault-specific actions
        if faults["burned_components"]["detected"]:
            recommendations["actions"].append("✓ Identify and replace burned components")
            recommendations["cautions"].append("⚠ Burned components indicate overcurrent or overvoltage event")
        
        if faults["corrosion"]["detected"]:
            recommendations["actions"].append("✓ Clean corrosion with isopropyl alcohol and soft brush")
            recommendations["actions"].append("✓ Reflow solder joints after cleaning")
            recommendations["cautions"].append("⚠ Corrosion may have damaged copper traces")
        
        if faults["broken_traces"]["detected"]:
            recommendations["actions"].append("✓ Inspect all traces carefully under magnification")
            recommendations["actions"].append("✓ Consider jumper wire repairs if traces broken")
            recommendations["cautions"].append("⚠ Broken traces significantly reduce repairability")
        
        return recommendations
    
    def _generate_summary(self, board_info: Dict, faults: Dict, recommendations: Dict) -> str:
        """Generate human-readable summary."""
        
        board_type = board_info.get("board_type", "Unknown")
        confidence = board_info.get("confidence", 0)
        condition = faults.get("overall_condition", "Unknown")
        repairability = recommendations.get("repairability", "Unknown")
        
        summary = f"""
BOARD ANALYSIS SUMMARY:
{'='*60}

This board is identified as:
  → {board_type} (confidence: {confidence:.0%})

Current condition: {condition}

Repairability assessment: {repairability}

Salvage value: {recommendations.get('salvage_value', 'Unknown')}

Next steps:
  1. {recommendations['actions'][0] if recommendations['actions'] else 'Inspect board carefully'}
  2. {recommendations['actions'][1] if len(recommendations['actions']) > 1 else 'Check all major components'}
  3. {recommendations['actions'][2] if len(recommendations['actions']) > 2 else 'Test with appropriate equipment'}

WARNINGS:
{chr(10).join('  • ' + c for c in recommendations['cautions'][:3]) if recommendations['cautions'] else '  • None'}
{'='*60}
"""
        return summary.strip()


# Test it
if __name__ == "__main__":
    from pathlib import Path
    from PIL import Image
    from src.vision.enhanced_detector import EnhancedComponentDetector, DetectionMethod
    
    # Load test image
    test_images = list(Path('datasets/real_pcb_archive/test/images').glob('*.jpg'))
    if test_images:
        img = Image.open(test_images[0])
        img_array = np.array(img)
        
        # Detect components
        detector = EnhancedComponentDetector()
        detections = detector.detect_components(
            img_array,
            methods=[DetectionMethod.YOLO],
            enable_ocr=False
        )
        
        # Analyze
        engine = BoardAnalysisEngine()
        result = engine.analyze(img_array, detections)
        
        print(result["summary"])
