"""
Capacitor Value Reader

Uses OCR to read capacitor markings and decode values.
Handles:
- SMD ceramic capacitors (3-digit codes like "104")
- Electrolytic capacitors (printed values like "100uF 25V")
- Tantalum capacitors (letter codes)
"""

import cv2
import numpy as np
import re
from typing import Optional, Tuple
from dataclasses import dataclass
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


@dataclass
class CapacitorReading:
    """Result of reading a capacitor."""
    capacitance_farads: float
    voltage_rating: Optional[float] = None
    marking: Optional[str] = None
    capacitor_type: Optional[str] = None  # "ceramic", "electrolytic", "tantalum"
    confidence: float = 0.0
    error_message: Optional[str] = None


class CapacitorValueReader:
    """Read capacitor values from markings."""

    def __init__(self):
        """Initialize reader."""
        self.use_ocr = TESSERACT_AVAILABLE

    def read_capacitor(self, image: np.ndarray, cap_bbox: Tuple[int, int, int, int],
                      cap_type: str = "ceramic") -> CapacitorReading:
        """
        Read capacitor value from image.

        Args:
            image: Full PCB image
            cap_bbox: Bounding box (x1, y1, x2, y2) of capacitor
            cap_type: "ceramic", "electrolytic", or "tantalum"

        Returns:
            CapacitorReading with value and voltage rating
        """
        x1, y1, x2, y2 = cap_bbox

        # Extract capacitor region
        cap_roi = image[y1:y2, x1:x2]

        if cap_roi.size == 0:
            return CapacitorReading(0, error_message="Invalid ROI")

        # Preprocess for OCR
        preprocessed = self._preprocess_for_ocr(cap_roi)

        # Try OCR if available
        if self.use_ocr:
            text = self._ocr_read(preprocessed)
        else:
            # Fallback: try to detect patterns without OCR
            text = None

        if not text:
            return CapacitorReading(0, error_message="Could not read marking")

        # Decode based on type
        try:
            if cap_type == "ceramic":
                return self._decode_ceramic(text)
            elif cap_type == "electrolytic":
                return self._decode_electrolytic(text)
            elif cap_type == "tantalum":
                return self._decode_tantalum(text)
            else:
                # Try all decoders
                for decoder in [self._decode_ceramic, self._decode_electrolytic, self._decode_tantalum]:
                    result = decoder(text)
                    if result.capacitance_farads > 0:
                        return result

                return CapacitorReading(0, error_message="Could not decode marking")

        except Exception as e:
            return CapacitorReading(0, error_message=str(e))

    def _preprocess_for_ocr(self, cap_roi: np.ndarray) -> np.ndarray:
        """
        Preprocess image for OCR.

        - Convert to grayscale
        - Increase contrast
        - Threshold
        - Denoise
        """
        # Grayscale
        if len(cap_roi.shape) == 3:
            gray = cv2.cvtColor(cap_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = cap_roi.copy()

        # Resize if too small (OCR works better on larger text)
        height, width = gray.shape
        if height < 50 or width < 50:
            scale = max(50 / height, 50 / width)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        gray = clahe.apply(gray)

        # Threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Denoise
        binary = cv2.medianBlur(binary, 3)

        return binary

    def _ocr_read(self, image: np.ndarray) -> Optional[str]:
        """
        Read text from image using OCR.

        Returns:
            Extracted text or None
        """
        if not TESSERACT_AVAILABLE:
            return None

        try:
            # Configure Tesseract for single-line alphanumeric
            config = '--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZuVvFfPpNnMmKk'

            text = pytesseract.image_to_string(image, config=config)

            # Clean up
            text = text.strip().upper()

            return text if text else None

        except Exception:
            return None

    def _decode_ceramic(self, marking: str) -> CapacitorReading:
        """
        Decode ceramic capacitor marking.

        Common formats:
        - 3-digit code: "104" = 10 * 10^4 pF = 100nF
        - 2-digit code: "47" = 47pF
        - Letter code: "10n" = 10nF
        """
        marking = marking.strip().upper()

        # Try direct value (e.g., "10N", "1U", "47P")
        direct_match = re.search(r'(\d+\.?\d*)\s*([PNUMKF])', marking)
        if direct_match:
            value = float(direct_match.group(1))
            unit = direct_match.group(2)

            multipliers = {
                'P': 1e-12,  # pF
                'N': 1e-9,   # nF
                'U': 1e-6,   # µF
                'M': 1e-3,   # mF (rare)
                'F': 1,      # F
                'K': 1e3     # kF (very rare)
            }

            capacitance = value * multipliers.get(unit, 1e-12)

            return CapacitorReading(
                capacitance_farads=capacitance,
                marking=marking,
                capacitor_type="ceramic",
                confidence=0.8
            )

        # Try 3-digit code
        code_match = re.search(r'(\d)(\d)(\d)', marking)
        if code_match:
            digit1 = int(code_match.group(1))
            digit2 = int(code_match.group(2))
            multiplier = int(code_match.group(3))

            # Value in pF
            pf_value = (digit1 * 10 + digit2) * (10 ** multiplier)
            capacitance = pf_value * 1e-12  # Convert to farads

            return CapacitorReading(
                capacitance_farads=capacitance,
                marking=marking,
                capacitor_type="ceramic",
                confidence=0.7
            )

        # Try 2-digit code (direct pF value)
        two_digit_match = re.search(r'^(\d{1,2})$', marking)
        if two_digit_match:
            pf_value = int(two_digit_match.group(1))
            capacitance = pf_value * 1e-12

            return CapacitorReading(
                capacitance_farads=capacitance,
                marking=marking,
                capacitor_type="ceramic",
                confidence=0.6
            )

        return CapacitorReading(0, error_message="Could not decode ceramic marking")

    def _decode_electrolytic(self, marking: str) -> CapacitorReading:
        """
        Decode electrolytic capacitor marking.

        Format: "100uF 25V" or "100µF 25V"
        """
        marking = marking.strip().upper()

        # Extract capacitance
        cap_match = re.search(r'(\d+\.?\d*)\s*[UuµμMm]?F', marking)
        if not cap_match:
            return CapacitorReading(0, error_message="Could not find capacitance value")

        value = float(cap_match.group(1))

        # Assume µF for electrolytic unless otherwise specified
        capacitance = value * 1e-6

        # Extract voltage rating
        voltage_match = re.search(r'(\d+\.?\d*)\s*V', marking)
        voltage = float(voltage_match.group(1)) if voltage_match else None

        return CapacitorReading(
            capacitance_farads=capacitance,
            voltage_rating=voltage,
            marking=marking,
            capacitor_type="electrolytic",
            confidence=0.8
        )

    def _decode_tantalum(self, marking: str) -> CapacitorReading:
        """
        Decode tantalum capacitor marking.

        Letter codes:
        A-Z, a-z map to values
        """
        marking = marking.strip().upper()

        # Try standard electrolytic format first
        result = self._decode_electrolytic(marking)
        if result.capacitance_farads > 0:
            result.capacitor_type = "tantalum"
            return result

        # Try letter code (less common now)
        # Not implementing full letter code here - would need lookup table

        return CapacitorReading(0, error_message="Could not decode tantalum marking")

    def format_capacitance(self, farads: float) -> str:
        """
        Format capacitance in human-readable form.

        Examples:
            1e-12 -> "1pF"
            1e-9 -> "1nF"
            1e-6 -> "1µF"
            100e-6 -> "100µF"
        """
        if farads >= 1e-3:
            return f"{farads * 1e3:.2f}mF"
        elif farads >= 1e-6:
            return f"{farads * 1e6:.2f}µF"
        elif farads >= 1e-9:
            return f"{farads * 1e9:.2f}nF"
        else:
            return f"{farads * 1e12:.2f}pF"


# Global singleton
capacitor_value_reader = CapacitorValueReader()
