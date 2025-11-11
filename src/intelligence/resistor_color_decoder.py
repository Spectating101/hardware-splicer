"""
Resistor Color Band Decoder

Uses computer vision to read resistor color bands and determine resistance value.
Handles:
- 4-band resistors (most common)
- 5-band resistors (precision)
- 6-band resistors (with temperature coefficient)
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum


class BandColor(Enum):
    """Standard resistor color codes."""
    BLACK = 0
    BROWN = 1
    RED = 2
    ORANGE = 3
    YELLOW = 4
    GREEN = 5
    BLUE = 6
    VIOLET = 7
    GRAY = 8
    WHITE = 9
    GOLD = -1  # ±5% tolerance, 0.1x multiplier
    SILVER = -2  # ±10% tolerance, 0.01x multiplier


# HSV color ranges for each band color
COLOR_RANGES = {
    'BLACK': ([0, 0, 0], [180, 255, 50]),
    'BROWN': ([5, 50, 30], [15, 255, 150]),
    'RED': ([0, 100, 100], [10, 255, 255]),
    'ORANGE': ([10, 100, 100], [20, 255, 255]),
    'YELLOW': ([20, 100, 100], [30, 255, 255]),
    'GREEN': ([35, 50, 50], [85, 255, 255]),
    'BLUE': ([90, 50, 50], [130, 255, 255]),
    'VIOLET': ([130, 50, 50], [160, 255, 255]),
    'GRAY': ([0, 0, 50], [180, 50, 200]),
    'WHITE': ([0, 0, 200], [180, 30, 255]),
    'GOLD': ([15, 100, 100], [30, 255, 255]),  # Metallic gold
    'SILVER': ([0, 0, 150], [180, 30, 220]),  # Metallic silver
}


@dataclass
class ResistorReading:
    """Result of reading a resistor."""
    resistance_ohms: float
    tolerance_percent: float
    temperature_coefficient: Optional[int] = None  # ppm/°C
    band_colors: List[str] = None
    confidence: float = 0.0
    error_message: Optional[str] = None


class ResistorColorDecoder:
    """Decode resistor values from color bands."""

    def __init__(self):
        """Initialize decoder."""
        self.min_band_width = 3  # pixels
        self.max_band_width = 30
        self.min_band_spacing = 5

    def read_resistor(self, image: np.ndarray, resistor_bbox: Tuple[int, int, int, int]) -> ResistorReading:
        """
        Read resistor value from image.

        Args:
            image: Full PCB image
            resistor_bbox: Bounding box (x1, y1, x2, y2) of resistor

        Returns:
            ResistorReading with value and tolerance
        """
        x1, y1, x2, y2 = resistor_bbox

        # Extract resistor region
        resistor_roi = image[y1:y2, x1:x2]

        if resistor_roi.size == 0:
            return ResistorReading(0, 0, error_message="Invalid ROI")

        # Detect bands
        bands = self._detect_bands(resistor_roi)

        if len(bands) < 4:
            return ResistorReading(0, 0, error_message=f"Only detected {len(bands)} bands, need at least 4")

        # Identify colors
        band_colors = self._identify_band_colors(resistor_roi, bands)

        if None in band_colors:
            return ResistorReading(0, 0, error_message="Could not identify all band colors")

        # Decode value
        try:
            resistance, tolerance, temp_coeff = self._decode_bands(band_colors)

            return ResistorReading(
                resistance_ohms=resistance,
                tolerance_percent=tolerance,
                temperature_coefficient=temp_coeff,
                band_colors=band_colors,
                confidence=0.8
            )

        except ValueError as e:
            return ResistorReading(0, 0, error_message=str(e))

    def _detect_bands(self, resistor_roi: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect color band positions.

        Returns:
            List of band bounding boxes (x, y, w, h) in resistor ROI
        """
        # Convert to grayscale
        if len(resistor_roi.shape) == 3:
            gray = cv2.cvtColor(resistor_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = resistor_roi.copy()

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find vertical lines (bands are perpendicular to resistor body)
        # Resistor orientation detection
        height, width = resistor_roi.shape[:2]

        if width > height:
            # Horizontal resistor - bands are vertical
            kernel = np.ones((height // 3, 1), np.uint8)
        else:
            # Vertical resistor - bands are horizontal
            kernel = np.ones((1, width // 3), np.uint8)

        # Dilate to connect band edges
        dilated = cv2.dilate(edges, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter for band-like contours
        bands = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Band should be thin and span most of resistor width/height
            if width > height:
                # Horizontal resistor
                if w >= self.min_band_width and w <= self.max_band_width and h > height * 0.5:
                    bands.append((x, y, w, h))
            else:
                # Vertical resistor
                if h >= self.min_band_width and h <= self.max_band_width and w > width * 0.5:
                    bands.append((x, y, w, h))

        # Sort bands left-to-right (or top-to-bottom)
        if width > height:
            bands.sort(key=lambda b: b[0])  # Sort by x
        else:
            bands.sort(key=lambda b: b[1])  # Sort by y

        return bands

    def _identify_band_colors(self, resistor_roi: np.ndarray, bands: List[Tuple[int, int, int, int]]) -> List[str]:
        """
        Identify color of each band.

        Args:
            resistor_roi: Resistor region image
            bands: List of band bounding boxes

        Returns:
            List of color names
        """
        colors = []

        # Convert to HSV for color detection
        if len(resistor_roi.shape) == 3:
            hsv = cv2.cvtColor(resistor_roi, cv2.COLOR_BGR2HSV)
        else:
            # Grayscale - can only detect black/white/gray
            hsv = None

        for band in bands:
            x, y, w, h = band

            # Sample color from center of band
            center_x = x + w // 2
            center_y = y + h // 2

            if hsv is not None:
                # Extract band region
                band_region = hsv[y:y+h, x:x+w]

                # Get most common color in region
                color = self._identify_color_hsv(band_region)
            else:
                # Grayscale fallback
                brightness = resistor_roi[center_y, center_x]
                if brightness < 50:
                    color = 'BLACK'
                elif brightness > 200:
                    color = 'WHITE'
                else:
                    color = 'GRAY'

            colors.append(color)

        return colors

    def _identify_color_hsv(self, band_region: np.ndarray) -> Optional[str]:
        """
        Identify color from HSV region.

        Args:
            band_region: HSV image of band

        Returns:
            Color name or None
        """
        # Try each color
        best_match = None
        best_score = 0

        for color_name, (lower, upper) in COLOR_RANGES.items():
            # Create mask for this color
            lower = np.array(lower, dtype=np.uint8)
            upper = np.array(upper, dtype=np.uint8)

            mask = cv2.inRange(band_region, lower, upper)

            # Score = percentage of pixels matching
            score = np.count_nonzero(mask) / mask.size

            if score > best_score:
                best_score = score
                best_match = color_name

        # Require at least 20% match
        if best_score < 0.2:
            return None

        return best_match

    def _decode_bands(self, colors: List[str]) -> Tuple[float, float, Optional[int]]:
        """
        Decode resistance value from color bands.

        Args:
            colors: List of band colors (4, 5, or 6 bands)

        Returns:
            (resistance_ohms, tolerance_percent, temp_coefficient_ppm)
        """
        num_bands = len(colors)

        if num_bands == 4:
            # 4-band: digit1, digit2, multiplier, tolerance
            digit1 = BandColor[colors[0]].value
            digit2 = BandColor[colors[1]].value
            multiplier = self._get_multiplier(colors[2])
            tolerance = self._get_tolerance(colors[3])

            resistance = (digit1 * 10 + digit2) * multiplier

            return resistance, tolerance, None

        elif num_bands == 5:
            # 5-band: digit1, digit2, digit3, multiplier, tolerance
            digit1 = BandColor[colors[0]].value
            digit2 = BandColor[colors[1]].value
            digit3 = BandColor[colors[2]].value
            multiplier = self._get_multiplier(colors[3])
            tolerance = self._get_tolerance(colors[4])

            resistance = (digit1 * 100 + digit2 * 10 + digit3) * multiplier

            return resistance, tolerance, None

        elif num_bands == 6:
            # 6-band: digit1, digit2, digit3, multiplier, tolerance, temp_coeff
            digit1 = BandColor[colors[0]].value
            digit2 = BandColor[colors[1]].value
            digit3 = BandColor[colors[2]].value
            multiplier = self._get_multiplier(colors[3])
            tolerance = self._get_tolerance(colors[4])
            temp_coeff = self._get_temp_coefficient(colors[5])

            resistance = (digit1 * 100 + digit2 * 10 + digit3) * multiplier

            return resistance, tolerance, temp_coeff

        else:
            raise ValueError(f"Invalid number of bands: {num_bands}")

    def _get_multiplier(self, color: str) -> float:
        """Get multiplier for color."""
        multipliers = {
            'BLACK': 1,
            'BROWN': 10,
            'RED': 100,
            'ORANGE': 1000,
            'YELLOW': 10000,
            'GREEN': 100000,
            'BLUE': 1000000,
            'VIOLET': 10000000,
            'GRAY': 100000000,
            'WHITE': 1000000000,
            'GOLD': 0.1,
            'SILVER': 0.01
        }
        return multipliers.get(color, 1)

    def _get_tolerance(self, color: str) -> float:
        """Get tolerance percentage for color."""
        tolerances = {
            'BROWN': 1.0,
            'RED': 2.0,
            'GREEN': 0.5,
            'BLUE': 0.25,
            'VIOLET': 0.1,
            'GRAY': 0.05,
            'GOLD': 5.0,
            'SILVER': 10.0,
            'NONE': 20.0  # No band = 20%
        }
        return tolerances.get(color, 20.0)

    def _get_temp_coefficient(self, color: str) -> int:
        """Get temperature coefficient in ppm/°C."""
        temp_coeffs = {
            'BROWN': 100,
            'RED': 50,
            'ORANGE': 15,
            'YELLOW': 25,
            'BLUE': 10,
            'VIOLET': 5
        }
        return temp_coeffs.get(color, 100)

    def format_resistance(self, ohms: float) -> str:
        """
        Format resistance in human-readable form.

        Examples:
            100 -> "100Ω"
            1000 -> "1kΩ"
            1000000 -> "1MΩ"
            4700 -> "4.7kΩ"
        """
        if ohms >= 1e6:
            return f"{ohms / 1e6:.2f}MΩ"
        elif ohms >= 1e3:
            return f"{ohms / 1e3:.2f}kΩ"
        else:
            return f"{ohms:.0f}Ω"


# Global singleton
resistor_color_decoder = ResistorColorDecoder()
