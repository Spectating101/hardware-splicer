"""
Pin Number Detection System

Uses computer vision + OCR to detect IC pin numbers in PCB images.
Critical for generating pin-level repair instructions like:
- "Desolder pin 3 of U5"
- "Measure voltage at pin 7"
- "Bridge pin 12 to pin 15"
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import re

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from intelligence.pinout_database import pinout_database, PinoutDatabase, PackageType


class PinOrientation(Enum):
    """IC orientation on PCB."""
    UP = "up"  # Pin 1 at top
    DOWN = "down"  # Pin 1 at bottom
    LEFT = "left"  # Pin 1 at left
    RIGHT = "right"  # Pin 1 at right


@dataclass
class DetectedPin:
    """A detected IC pin."""
    pin_number: int
    position: Tuple[int, int]  # (x, y) in image
    confidence: float
    detection_method: str  # "ocr", "inference", "counting"
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)


@dataclass
class ICDetectionResult:
    """Complete IC pin detection result."""
    part_number: str
    bbox: Tuple[int, int, int, int]  # IC bounding box
    pin_count: int
    package_type: PackageType
    orientation: PinOrientation
    pins: List[DetectedPin]
    pin1_position: Tuple[int, int]  # Critical: where is pin 1?
    confidence: float


class PinDetector:
    """Detects IC pins and their numbers using computer vision."""

    def __init__(self, pinout_db: Optional[PinoutDatabase] = None):
        self.pinout_db = pinout_db or pinout_database

    def detect_ic_pins(self, image: np.ndarray, ic_bbox: Tuple[int, int, int, int],
                      part_number: str) -> Optional[ICDetectionResult]:
        """
        Detect all pins on an IC.

        Args:
            image: Full PCB image
            ic_bbox: Bounding box of IC (x1, y1, x2, y2)
            part_number: IC part number (to know expected pin count)

        Returns:
            ICDetectionResult with all detected pins
        """
        # Get pinout information
        pinout = self.pinout_db.get_pinout(part_number)
        if not pinout:
            # Try searching by component name
            pinout = self.pinout_db.search_by_component_name(part_number)

        if not pinout:
            return None

        # Extract IC region
        x1, y1, x2, y2 = ic_bbox
        ic_region = image[y1:y2, x1:x2]

        # Detect pin 1 location
        pin1_pos, orientation = self._detect_pin1(ic_region, pinout.package)
        if not pin1_pos:
            return None

        # Convert to absolute coordinates
        pin1_abs = (pin1_pos[0] + x1, pin1_pos[1] + y1)

        # Detect all pins based on package type
        pins = self._detect_all_pins(ic_region, pinout.package, pinout.pin_count,
                                     pin1_pos, orientation)

        # Convert pin positions to absolute coordinates
        for pin in pins:
            pin.position = (pin.position[0] + x1, pin.position[1] + y1)

        return ICDetectionResult(
            part_number=pinout.part_number,
            bbox=ic_bbox,
            pin_count=pinout.pin_count,
            package_type=pinout.package,
            orientation=orientation,
            pins=pins,
            pin1_position=pin1_abs,
            confidence=np.mean([p.confidence for p in pins]) if pins else 0.0
        )

    def _detect_pin1(self, ic_region: np.ndarray, package: PackageType) -> Tuple[Optional[Tuple[int, int]], Optional[PinOrientation]]:
        """
        Detect pin 1 location on IC.

        Pin 1 indicators:
        - DIP: Notch at top or dot near pin 1
        - SOIC/TSSOP: Dot or chamfer
        - QFN/QFP: Dot or chamfer on corner
        - Module (ESP): Antenna side, pin 1 marking
        """
        gray = cv2.cvtColor(ic_region, cv2.COLOR_BGR2GRAY) if len(ic_region.shape) == 3 else ic_region
        h, w = gray.shape

        if package == PackageType.DIP:
            # Look for notch at top (semicircle cutout)
            top_region = gray[0:int(h*0.2), :]
            circles = cv2.HoughCircles(
                top_region, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
                param1=50, param2=30, minRadius=5, maxRadius=int(w*0.2)
            )
            if circles is not None:
                # Notch found at top, pin 1 is top-left
                return ((int(w * 0.1), int(h * 0.1)), PinOrientation.UP)

        # Look for dot/marking (bright spot)
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Threshold for bright dots
        _, bright = cv2.threshold(enhanced, 200, 255, cv2.THRESH_BINARY)

        # Find contours (potential dots)
        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Look for small circular contours in corners
        corners = [
            (int(w * 0.1), int(h * 0.1), PinOrientation.UP),  # Top-left
            (int(w * 0.9), int(h * 0.1), PinOrientation.RIGHT),  # Top-right
            (int(w * 0.9), int(h * 0.9), PinOrientation.DOWN),  # Bottom-right
            (int(w * 0.1), int(h * 0.9), PinOrientation.LEFT),  # Bottom-left
        ]

        for contour in contours:
            area = cv2.contourArea(contour)
            if 10 < area < 500:  # Small dot
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Check if near a corner
                    for corner_x, corner_y, orientation in corners:
                        if abs(cx - corner_x) < w * 0.15 and abs(cy - corner_y) < h * 0.15:
                            return ((cx, cy), orientation)

        # Fallback: assume top-left for DIP/SOIC, bottom-left for QFN/QFP
        if package in [PackageType.DIP, PackageType.SOIC, PackageType.TSSOP]:
            return ((int(w * 0.1), int(h * 0.1)), PinOrientation.UP)
        else:
            return ((int(w * 0.1), int(h * 0.9)), PinOrientation.LEFT)

    def _detect_all_pins(self, ic_region: np.ndarray, package: PackageType,
                        pin_count: int, pin1_pos: Tuple[int, int],
                        orientation: PinOrientation) -> List[DetectedPin]:
        """
        Detect all pins based on package type and pin 1 location.

        For DIP/SOIC: pins along two sides
        For QFN/QFP: pins along four sides
        """
        h, w = ic_region.shape[:2]
        pins = []

        if package in [PackageType.DIP, PackageType.SOIC, PackageType.TSSOP]:
            # Two-sided package
            pins_per_side = pin_count // 2

            # DIP packages always use UP orientation (pin 1 top-left)
            # Left side: pins 1 to pins_per_side (top to bottom)
            for i in range(pins_per_side):
                if pins_per_side > 1:
                    y = int(h * 0.1 + (h * 0.8) * i / (pins_per_side - 1))
                else:
                    y = int(h * 0.5)
                x = int(w * 0.05)
                pins.append(DetectedPin(
                    pin_number=i + 1,
                    position=(x, y),
                    confidence=0.7,
                    detection_method="inference"
                ))

            # Right side: pins_per_side+1 to pin_count (bottom to top)
            for i in range(pins_per_side):
                if pins_per_side > 1:
                    y = int(h * 0.9 - (h * 0.8) * i / (pins_per_side - 1))
                else:
                    y = int(h * 0.5)
                x = int(w * 0.95)
                pins.append(DetectedPin(
                    pin_number=pins_per_side + i + 1,
                    position=(x, y),
                    confidence=0.7,
                    detection_method="inference"
                ))

        elif package in [PackageType.QFN, PackageType.QFP]:
            # Four-sided package
            pins_per_side = pin_count // 4

            if orientation == PinOrientation.LEFT:
                # Bottom side: pins 1 to pins_per_side (left to right)
                for i in range(pins_per_side):
                    x = int(w * 0.1 + (w * 0.8) * i / (pins_per_side - 1))
                    y = int(h * 0.95)
                    pins.append(DetectedPin(
                        pin_number=i + 1,
                        position=(x, y),
                        confidence=0.6,
                        detection_method="inference"
                    ))

                # Left side: pins_per_side+1 to pins_per_side*2 (bottom to top)
                for i in range(pins_per_side):
                    x = int(w * 0.05)
                    y = int(h * 0.9 - (h * 0.8) * i / (pins_per_side - 1))
                    pins.append(DetectedPin(
                        pin_number=pins_per_side + i + 1,
                        position=(x, y),
                        confidence=0.6,
                        detection_method="inference"
                    ))

                # Top side: pins_per_side*2+1 to pins_per_side*3 (right to left)
                for i in range(pins_per_side):
                    x = int(w * 0.9 - (w * 0.8) * i / (pins_per_side - 1))
                    y = int(h * 0.05)
                    pins.append(DetectedPin(
                        pin_number=pins_per_side * 2 + i + 1,
                        position=(x, y),
                        confidence=0.6,
                        detection_method="inference"
                    ))

                # Right side: pins_per_side*3+1 to pin_count (top to bottom)
                for i in range(pins_per_side):
                    x = int(w * 0.95)
                    y = int(h * 0.1 + (h * 0.8) * i / (pins_per_side - 1))
                    pins.append(DetectedPin(
                        pin_number=pins_per_side * 3 + i + 1,
                        position=(x, y),
                        confidence=0.6,
                        detection_method="inference"
                    ))

        elif package == PackageType.MODULE:
            # ESP modules: pins along edges
            # This is complex and varies by module variant
            # Simplified version for ESP-12E/F (22 pins)
            if pin_count == 22:
                # Bottom edge: pins 1-8
                for i in range(8):
                    x = int(w * 0.15 + (w * 0.7) * i / 7)
                    y = int(h * 0.95)
                    pins.append(DetectedPin(
                        pin_number=i + 1,
                        position=(x, y),
                        confidence=0.5,
                        detection_method="inference"
                    ))

                # Left edge: pins 9-11
                for i in range(3):
                    x = int(w * 0.05)
                    y = int(h * 0.8 - (h * 0.4) * i / 2)
                    pins.append(DetectedPin(
                        pin_number=9 + i,
                        position=(x, y),
                        confidence=0.5,
                        detection_method="inference"
                    ))

                # Top edge: pins 12-15
                for i in range(4):
                    x = int(w * 0.2 + (w * 0.6) * i / 3)
                    y = int(h * 0.05)
                    pins.append(DetectedPin(
                        pin_number=12 + i,
                        position=(x, y),
                        confidence=0.5,
                        detection_method="inference"
                    ))

                # Right edge: pins 16-22
                for i in range(7):
                    x = int(w * 0.95)
                    y = int(h * 0.15 + (h * 0.7) * i / 6)
                    pins.append(DetectedPin(
                        pin_number=16 + i,
                        position=(x, y),
                        confidence=0.5,
                        detection_method="inference"
                    ))

        return pins

    def find_pin_position(self, ic_detection: ICDetectionResult,
                         pin_number: int) -> Optional[Tuple[int, int]]:
        """Get position of a specific pin number."""
        for pin in ic_detection.pins:
            if pin.pin_number == pin_number:
                return pin.position
        return None

    def find_pin_by_name(self, ic_detection: ICDetectionResult,
                        pin_name: str) -> Optional[DetectedPin]:
        """
        Find pin by functional name (e.g., 'VCC', 'TXD', 'GPIO0').
        Requires pinout database.
        """
        pinout = self.pinout_db.get_pinout(ic_detection.part_number)
        if not pinout:
            return None

        pin_def = self.pinout_db.find_pin_by_name(ic_detection.part_number, pin_name)
        if not pin_def:
            return None

        # Find detected pin with this number
        for detected_pin in ic_detection.pins:
            if detected_pin.pin_number == pin_def.pin_number:
                return detected_pin

        return None

    def generate_pin_instruction(self, ic_detection: ICDetectionResult,
                                pin_number: int, action: str) -> str:
        """
        Generate human-readable instruction for a specific pin.

        Args:
            ic_detection: IC detection result
            pin_number: Pin number
            action: Action to perform (e.g., "desolder", "measure voltage", "bridge to")

        Returns:
            Instruction string like "Desolder pin 3 (TXD) of U5 (ESP8266)"
        """
        pinout = self.pinout_db.get_pinout(ic_detection.part_number)
        if not pinout:
            return f"{action.capitalize()} pin {pin_number} of {ic_detection.part_number}"

        # Find pin definition
        pin_def = None
        for pd in pinout.pins:
            if pd.pin_number == pin_number:
                pin_def = pd
                break

        if pin_def:
            return (
                f"{action.capitalize()} pin {pin_number} ({pin_def.pin_name}: {pin_def.description}) "
                f"of {ic_detection.part_number}"
            )
        else:
            return f"{action.capitalize()} pin {pin_number} of {ic_detection.part_number}"

    def generate_connection_instruction(self, ic1_detection: ICDetectionResult, pin1_num: int,
                                       ic2_detection: ICDetectionResult, pin2_num: int,
                                       method: str = "wire") -> str:
        """
        Generate instruction to connect two pins.

        Args:
            ic1_detection: First IC detection
            pin1_num: First pin number
            ic2_detection: Second IC detection
            pin2_num: Second pin number
            method: Connection method ("wire", "trace cut + wire", "solder bridge")

        Returns:
            Instruction like "Connect pin 3 (TXD) of ESP8266 to pin 2 (RXD) of ATmega328P with a wire"
        """
        pinout1 = self.pinout_db.get_pinout(ic1_detection.part_number)
        pinout2 = self.pinout_db.get_pinout(ic2_detection.part_number)

        pin1_name = "unknown"
        pin2_name = "unknown"

        if pinout1:
            for pd in pinout1.pins:
                if pd.pin_number == pin1_num:
                    pin1_name = pd.pin_name
                    break

        if pinout2:
            for pd in pinout2.pins:
                if pd.pin_number == pin2_num:
                    pin2_name = pd.pin_name
                    break

        return (
            f"Connect pin {pin1_num} ({pin1_name}) of {ic1_detection.part_number} "
            f"to pin {pin2_num} ({pin2_name}) of {ic2_detection.part_number} "
            f"with {method}"
        )

    def validate_connection(self, ic1_part: str, pin1_name: str,
                           ic2_part: str, pin2_name: str) -> Dict[str, Any]:
        """
        Validate if a proposed connection makes electrical sense.

        Returns:
            {
                'valid': bool,
                'warnings': List[str],
                'voltage_mismatch': bool,
                'recommendation': str
            }
        """
        pin1 = self.pinout_db.find_pin_by_name(ic1_part, pin1_name)
        pin2 = self.pinout_db.find_pin_by_name(ic2_part, pin2_name)

        if not pin1 or not pin2:
            return {
                'valid': False,
                'warnings': ["Unknown pin(s)"],
                'voltage_mismatch': False,
                'recommendation': "Check pin names"
            }

        warnings = []
        voltage_mismatch = False

        # Check voltage compatibility
        if pin1.typical_voltage and pin2.typical_voltage:
            v1 = pin1.typical_voltage
            v2 = pin2.typical_voltage
            if abs(v1 - v2) > 0.5:  # >0.5V difference
                voltage_mismatch = True
                warnings.append(
                    f"VOLTAGE MISMATCH: {ic1_part} pin {pin1_name} is {v1}V, "
                    f"{ic2_part} pin {pin2_name} is {v2}V. "
                    f"Needs level shifter!"
                )

        # Check pin type compatibility
        if pin1.pin_type.value == "output" and pin2.pin_type.value == "output":
            warnings.append("WARNING: Connecting two outputs can cause contention!")

        if pin1.pin_type.value == "power" and pin2.pin_type.value != "power":
            warnings.append("WARNING: Connecting power to non-power pin!")

        # Check current capacity
        if pin1.max_current_ma and pin2.max_current_ma:
            if pin1.pin_type.value == "output" and pin2.pin_type.value == "input":
                if pin2.max_current_ma > pin1.max_current_ma:
                    warnings.append(
                        f"WARNING: Pin {pin2_name} may draw more current ({pin2.max_current_ma}mA) "
                        f"than pin {pin1_name} can source ({pin1.max_current_ma}mA)"
                    )

        valid = len(warnings) == 0 or not voltage_mismatch

        recommendation = ""
        if voltage_mismatch:
            recommendation = f"Use bidirectional level shifter ({min(pin1.typical_voltage, pin2.typical_voltage)}V ↔ {max(pin1.typical_voltage, pin2.typical_voltage)}V)"
        elif warnings:
            recommendation = "Proceed with caution, verify datasheets"
        else:
            recommendation = "Connection appears safe"

        return {
            'valid': valid,
            'warnings': warnings,
            'voltage_mismatch': voltage_mismatch,
            'recommendation': recommendation
        }


# Global singleton
pin_detector = PinDetector()
