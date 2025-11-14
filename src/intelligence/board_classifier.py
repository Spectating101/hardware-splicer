"""
Board Type Classifier

Takes detected components and identifies what type of PCB board it is.
"""

from typing import List, Dict, Tuple
from loguru import logger


class BoardClassifier:
    """Classify PCB board types based on detected components."""
    
    # Component signatures for different board types
    BOARD_SIGNATURES = {
        "Power Supply Unit": {
            "required": ["Transformer"],
            "expected": ["Cap1", "Cap2", "Cap3", "Cap4", "MOSFET", "Mov"],
            "confidence_boost": 0.3,
            "description": "AC/DC power conversion board"
        },
        "Audio Amplifier": {
            "required": ["Transformer"],
            "expected": ["Cap1", "Cap2", "Cap3", "Cap4"],
            "confidence_boost": 0.2,
            "description": "Audio signal amplification board"
        },
        "Motherboard/Control": {
            "required": ["MOSFET"],
            "expected": ["Cap1", "Cap2", "Cap3", "Cap4", "Resistor"],
            "confidence_boost": 0.15,
            "description": "System control or motherboard"
        },
        "Power Distribution": {
            "required": ["Mov"],
            "expected": ["MOSFET", "Cap1", "Cap2"],
            "confidence_boost": 0.2,
            "description": "Voltage regulation and protection board"
        },
    }
    
    def __init__(self):
        """Initialize board classifier."""
        logger.info("BoardClassifier initialized")
    
    def classify(self, detected_components: List) -> Dict:
        """
        Classify board type from detected components.
        
        Args:
            detected_components: List of detection objects with class_name attribute
            
        Returns:
            Dict with board_type, confidence, and description
        """
        if not detected_components:
            return {
                "board_type": "Unknown",
                "confidence": 0.0,
                "description": "No components detected",
                "components_found": []
            }
        
        # Extract component names
        component_names = [d.class_name for d in detected_components]
        unique_components = set(component_names)
        
        logger.debug(f"Classifying board with components: {unique_components}")
        
        # Score each board type
        scores = {}
        for board_type, signature in self.BOARD_SIGNATURES.items():
            score = self._score_board_type(unique_components, signature)
            scores[board_type] = score
        
        # Find best match
        if not scores or max(scores.values()) < 0.3:
            return {
                "board_type": "Generic PCB Board",
                "confidence": 0.5,
                "description": "Could not match to known board type",
                "components_found": list(unique_components)
            }
        
        best_board = max(scores, key=scores.get)
        best_score = scores[best_board]
        
        signature = self.BOARD_SIGNATURES[best_board]
        
        return {
            "board_type": best_board,
            "confidence": min(best_score, 0.95),  # Cap at 95%
            "description": signature["description"],
            "components_found": list(unique_components),
            "matching_components": self._get_matched_components(unique_components, signature),
            "score_breakdown": scores
        }
    
    def _score_board_type(self, components: set, signature: Dict) -> float:
        """Score how well components match a board type signature."""
        score = 0.0
        
        # Check required components
        required = set(signature.get("required", []))
        if required.issubset(components):
            score += 0.5
        elif required and components & required:
            score += 0.25
        
        # Check expected components
        expected = set(signature.get("expected", []))
        if expected:
            matches = len(components & expected)
            expected_count = len(expected)
            match_ratio = matches / expected_count
            score += match_ratio * 0.5
        
        # Add confidence boost if matched
        if required and required.issubset(components):
            score += signature.get("confidence_boost", 0.1)
        
        return min(score, 1.0)
    
    def _get_matched_components(self, components: set, signature: Dict) -> List[str]:
        """Get list of components that matched the signature."""
        required = set(signature.get("required", []))
        expected = set(signature.get("expected", []))
        matched = (required & components) | (expected & components)
        return sorted(list(matched))


# Test it
if __name__ == "__main__":
    from pathlib import Path
    import numpy as np
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
        
        # Classify board
        classifier = BoardClassifier()
        result = classifier.classify(detections)
        
        print("BOARD CLASSIFICATION RESULT:")
        print(f"  Board Type: {result['board_type']}")
        print(f"  Confidence: {result['confidence']:.1%}")
        print(f"  Description: {result['description']}")
        print(f"  Components Found: {result['components_found']}")
