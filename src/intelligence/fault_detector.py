"""
Fault Detector

Analyzes images for visual signs of failure: burned components, corrosion, broken traces.
Uses adaptive thresholding and HSV color space for more robust detection.
"""

import numpy as np
import cv2
from typing import List, Dict
from loguru import logger


class FaultDetector:
    """Detect visual faults in PCB images."""
    
    def __init__(self):
        """Initialize fault detector."""
        logger.info("FaultDetector initialized (Adaptive Mode)")
    
    def detect_faults(self, image: np.ndarray) -> Dict:
        """
        Analyze image for visual faults.
        
        Args:
            image: PCB image as numpy array (RGB or BGR)
            
        Returns:
            Dict with detected faults and severity
        """
        # Ensure image is RGB for consistency in internal methods
        if image.ndim == 3 and image.shape[2] == 3:
             # OpenCV loads as BGR usually, but we assume the input pipeline provides RGB
             # If input is BGR, some color checks might be swapped, but let's stick to standard handling
             pass

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
            elif avg_severity > 0.4:
                faults["overall_condition"] = "Fair - Some damage detected"
            elif avg_severity > 0.2:
                faults["overall_condition"] = "Good - Minor issues"
            else:
                faults["overall_condition"] = "Excellent - No significant issues"
        else:
            faults["overall_condition"] = "Excellent - No faults detected"
        
        return faults
    
    def _detect_burned(self, image: np.ndarray) -> Dict:
        """
        Detect burned/charred components using adaptive dark pixel analysis.
        Relative to average board brightness to avoid false positives in low light.
        """
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
            
        avg_brightness = np.mean(gray)
        
        # Adaptive threshold: Burned areas are significantly darker than the mean
        # If board is bright (150), threshold is ~50. If board is dark (60), threshold is ~20.
        dark_threshold = max(20, int(avg_brightness * 0.35))
        
        dark_pixels = gray < dark_threshold
        dark_ratio = np.sum(dark_pixels) / dark_pixels.size
        
        # Heuristic: >3% very dark pixels might be burns, but ignore if whole image is too dark
        detected = (dark_ratio > 0.03) and (avg_brightness > 40)
        
        # Calculate severity
        severity = min(dark_ratio * 15, 1.0) if detected else 0.0
        
        return {
            "detected": detected,
            "severity": severity,
            "dark_pixel_ratio": dark_ratio,
            "description": f"Potential charring/burns (adaptive thresh: {dark_threshold})"
        }
    
    def _detect_corrosion(self, image: np.ndarray) -> Dict:
        """
        Detect corrosion using HSV color space for better isolation of 
        green/teal (copper oxidation) and white/crusty (battery leak/salt).
        """
        if image.ndim != 3:
            return {"detected": False, "severity": 0.0, "description": "Grayscale input"}
            
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # 1. Copper Oxidation (Green/Teal)
        # Hue: 35-85 (Greenish range), Saturation: > 40, Value: 40-200
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([90, 255, 220])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        green_ratio = np.sum(mask_green > 0) / mask_green.size
        
        # 2. White Corrosion (Battery acid salts)
        # Low Saturation, High Value (White/Light Grey)
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 30, 255])
        mask_white = cv2.inRange(hsv, lower_white, upper_white)
        white_ratio = np.sum(mask_white > 0) / mask_white.size
        
        # Thresholds
        green_detected = green_ratio > 0.02  # 2% is a safer floor for real corrosion
        white_detected = white_ratio > 0.05  # White is common (silkscreen), so need higher thresh or smarter ROI
        
        # Refine White: Subtract silkscreen (usually very organized lines)
        # For now, we trust green more.
        
        detected = green_detected # White is too noisy without shape analysis
        severity = min(green_ratio * 20, 1.0)
        
        desc = []
        if green_detected: desc.append(f"Green oxidation ({green_ratio:.1%})")
        if white_detected and green_detected: desc.append(f"possible salt build-up")
        
        return {
            "detected": detected,
            "severity": severity,
            "green_ratio": green_ratio,
            "white_ratio": white_ratio,
            "description": ", ".join(desc) if desc else "No corrosion detected"
        }
    
    def _detect_broken_traces(self, image: np.ndarray) -> Dict:
        """
        Detect broken traces. 
        Note: This is very hard with simple CV. We use a high-pass filter approach
        to find discontinuities in high-contrast lines.
        """
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
            
        # Canny edge detection
        edges = cv2.Canny(gray, 100, 200)
        
        # Find contours of edges
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze contours: extremely short open contours might be breaks
        # Valid traces are usually long continuous lines.
        short_open_contours = 0
        total_trace_length = 0
        
        for cnt in contours:
            perimeter = cv2.arcLength(cnt, False) # False = open
            total_trace_length += perimeter
            if 5 < perimeter < 20: # Short segments
                short_open_contours += 1
                
        # Metric: Density of short segments per unit of trace length
        # Noisy images have high density of short segments
        if total_trace_length > 0:
            break_density = short_open_contours / total_trace_length
        else:
            break_density = 0
            
        detected = break_density > 0.15
        severity = min(break_density * 5, 1.0)
        
        return {
            "detected": detected,
            "severity": severity,
            "break_density": break_density,
            "description": f"Potential trace discontinuities (density: {break_density:.2f})"
        }

if __name__ == "__main__":
    pass