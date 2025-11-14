"""
Fault Detector

Analyzes images for visual signs of failure: burned components, corrosion, broken traces.
"""

import numpy as np
from typing import List, Dict
from loguru import logger


class FaultDetector:
    """Detect visual faults in PCB images."""
    
    def __init__(self):
        """Initialize fault detector."""
        logger.info("FaultDetector initialized")
    
    def detect_faults(self, image: np.ndarray) -> Dict:
        """
        Analyze image for visual faults.
        
        Args:
            image: PCB image as numpy array (RGB or BGR)
            
        Returns:
            Dict with detected faults and severity
        """
        faults = {
            "burned_components": self._detect_burned(image),
            "corrosion": self._detect_corrosion(image),
            "broken_traces": self._detect_broken_traces(image),
            "overall_condition": "Unknown"
        }
        
        # Assess overall condition
        severity_scores = []
        if faults["burned_components"]["detected"]:
            severity_scores.append(faults["burned_components"]["severity"])
        if faults["corrosion"]["detected"]:
            severity_scores.append(faults["corrosion"]["severity"])
        if faults["broken_traces"]["detected"]:
            severity_scores.append(faults["broken_traces"]["severity"])
        
        if severity_scores:
            avg_severity = np.mean(severity_scores)
            if avg_severity > 0.7:
                faults["overall_condition"] = "Poor - Multiple serious faults"
            elif avg_severity > 0.5:
                faults["overall_condition"] = "Fair - Some damage detected"
            elif avg_severity > 0.3:
                faults["overall_condition"] = "Good - Minor issues"
            else:
                faults["overall_condition"] = "Excellent - No significant issues"
        else:
            faults["overall_condition"] = "Excellent - No faults detected"
        
        return faults
    
    def _detect_burned(self, image: np.ndarray) -> Dict:
        """Detect burned or overheated components (black/charred areas)."""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image
        
        # Look for very dark pixels (burned areas)
        dark_threshold = 50
        dark_pixels = gray < dark_threshold
        dark_ratio = np.sum(dark_pixels) / dark_pixels.size
        
        detected = dark_ratio > 0.02  # More than 2% dark pixels
        
        return {
            "detected": detected,
            "severity": min(dark_ratio * 10, 1.0),  # Scale to 0-1
            "dark_pixel_ratio": dark_ratio,
            "description": f"Potential burned/charred components ({dark_ratio*100:.1f}% dark pixels)"
        }
    
    def _detect_corrosion(self, image: np.ndarray) -> Dict:
        """Detect corrosion (greenish/whitish discoloration)."""
        if len(image.shape) != 3:
            return {
                "detected": False,
                "severity": 0.0,
                "ratio": 0.0,
                "description": "Cannot analyze grayscale image for corrosion"
            }
        
        r, g, b = image[:,:,0], image[:,:,1], image[:,:,2]
        
        # Green corrosion (copper oxidation): high green relative to red/blue
        green_corrosion = (g > r + 20) & (g > b + 20)
        green_ratio = np.sum(green_corrosion) / (image.shape[0] * image.shape[1])
        
        # White corrosion: high values in all channels (copper sulfide)
        white_corrosion = (r > 150) & (g > 150) & (b > 150)
        white_ratio = np.sum(white_corrosion) / (image.shape[0] * image.shape[1])
        
        total_corrosion_ratio = (green_ratio + white_ratio) / 2
        detected = total_corrosion_ratio > 0.05  # More than 5% corrosion indicators
        
        return {
            "detected": detected,
            "severity": min(total_corrosion_ratio * 5, 1.0),
            "green_corrosion_ratio": green_ratio,
            "white_corrosion_ratio": white_ratio,
            "description": f"Potential corrosion detected (green: {green_ratio*100:.1f}%, white: {white_ratio*100:.1f}%)"
        }
    
    def _detect_broken_traces(self, image: np.ndarray) -> Dict:
        """Detect broken traces (discontinuous lines, cracks in copper)."""
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image
        
        # Look for high-contrast edges (broken traces have sharp transitions)
        # Simple edge detection: look for pixels that differ significantly from neighbors
        h, w = gray.shape
        edge_pixels = 0
        
        # Sample edges (faster than full convolution)
        for i in range(1, h-1, 5):  # Sample every 5 pixels for speed
            for j in range(1, w-1, 5):
                neighbors = [
                    gray[i-1, j], gray[i+1, j],
                    gray[i, j-1], gray[i, j+1]
                ]
                center = gray[i, j]
                avg_neighbor = np.mean(neighbors)
                if abs(center - avg_neighbor) > 30:
                    edge_pixels += 1
        
        # Normalize
        total_sampled = (h // 5) * (w // 5)
        edge_ratio = edge_pixels / total_sampled if total_sampled > 0 else 0
        
        detected = edge_ratio > 0.15  # More than 15% edge pixels suggest damage
        
        return {
            "detected": detected,
            "severity": min(edge_ratio * 2, 1.0),
            "edge_ratio": edge_ratio,
            "description": f"Potential broken traces or cracks (edge ratio: {edge_ratio:.2f})"
        }


# Test it
if __name__ == "__main__":
    from pathlib import Path
    from PIL import Image
    
    test_images = list(Path('datasets/real_pcb_archive/test/images').glob('*.jpg'))
    if test_images:
        img = Image.open(test_images[0])
        img_array = np.array(img)
        
        detector = FaultDetector()
        faults = detector.detect_faults(img_array)
        
        print("FAULT DETECTION RESULT:")
        print(f"  Overall Condition: {faults['overall_condition']}")
        print(f"  Burned Components: {faults['burned_components']['detected']}")
        print(f"    Severity: {faults['burned_components']['severity']:.0%}")
        print(f"  Corrosion: {faults['corrosion']['detected']}")
        print(f"    Severity: {faults['corrosion']['severity']:.0%}")
        print(f"  Broken Traces: {faults['broken_traces']['detected']}")
        print(f"    Severity: {faults['broken_traces']['severity']:.0%}")
