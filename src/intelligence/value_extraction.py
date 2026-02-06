"""
Component Value Extraction - OCR & Pattern Recognition

Extracts component values from PCB images:
- Resistor color codes
- Capacitor markings
- IC part numbers
- Text OCR for labels
- SMD codes
"""

import re
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComponentValue:
    """Extracted component value."""
    component_id: str
    component_type: str
    value: Optional[str] = None
    unit: Optional[str] = None
    tolerance: Optional[str] = None
    part_number: Optional[str] = None
    confidence: float = 0.0
    extraction_method: str = ""


class ValueExtractor:
    """Extracts component values using OCR and pattern recognition."""

    def __init__(self):
        self.resistor_color_codes = self._load_resistor_codes()
        self.smd_codes = self._load_smd_codes()
        self.capacitor_codes = self._load_capacitor_codes()

        # Try to import pytesseract for OCR
        try:
            import pytesseract
            self.ocr_available = True
        except ImportError:
            self.ocr_available = False

    def extract_values(self, image: np.ndarray,
                      component_detections: List[Any]) -> List[ComponentValue]:
        """Extract values for all detected components."""
        extracted_values = []

        for comp in component_detections:
            value = self._extract_component_value(image, comp)
            if value:
                extracted_values.append(value)

        return extracted_values

    def _extract_component_value(self, image: np.ndarray,
                                 component: Any) -> Optional[ComponentValue]:
        """Extract value for single component."""

        comp_type = component.class_name if hasattr(component, 'class_name') else str(component)
        comp_id = getattr(component, 'id', f"comp_{id(component)}")

        # Get component ROI
        if hasattr(component, 'bbox'):
            x1, y1, x2, y2 = map(int, component.bbox)
            roi = image[y1:y2, x1:x2]
        else:
            return None

        # Try different extraction methods based on component type
        if "Resistor" in comp_type:
            return self._extract_resistor_value(roi, comp_id, comp_type)
        elif "Capacitor" in comp_type:
            return self._extract_capacitor_value(roi, comp_id, comp_type)
        elif any(ic in comp_type for ic in ["IC", "Chip", "ATmega", "ESP", "Arduino"]):
            return self._extract_ic_marking(roi, comp_id, comp_type)
        else:
            # Try generic OCR
            return self._extract_generic_text(roi, comp_id, comp_type)

    def _extract_resistor_value(self, roi: np.ndarray,
                               comp_id: str,
                               comp_type: str) -> Optional[ComponentValue]:
        """
        Extract resistor value from color bands or SMD codes.

        Uses ResistorColorDecoder for through-hole resistors with color bands,
        and OCR for SMD resistors with numerical codes.
        """
        # Check if SMD (smaller, has text) or through-hole (larger, color bands)
        height, width = roi.shape[:2]

        if width < 50:  # Likely SMD
            # Try to read SMD code (3-4 digit number)
            if self.ocr_available:
                text = self._ocr_text(roi)
                smd_value = self._decode_smd_resistor(text)
                if smd_value:
                    return ComponentValue(
                        component_id=comp_id,
                        component_type=comp_type,
                        value=smd_value['value'],
                        unit='Ω',
                        tolerance=smd_value.get('tolerance'),
                        confidence=0.7,
                        extraction_method="SMD code"
                    )

        else:  # Likely through-hole with color bands
            # Try to use the resistor color decoder
            try:
                from src.intelligence.resistor_color_decoder import resistor_color_decoder

                # Create a pseudo bounding box for the full ROI
                bbox = (0, 0, width, height)
                reading = resistor_color_decoder.read_resistor(roi, bbox)

                if reading.resistance_ohms > 0 and reading.error_message is None:
                    # Successfully decoded color bands
                    formatted_value = resistor_color_decoder.format_resistance(reading.resistance_ohms)
                    return ComponentValue(
                        component_id=comp_id,
                        component_type=comp_type,
                        value=formatted_value.replace('Ω', ''),
                        unit='Ω',
                        tolerance=f"±{reading.tolerance_percent}%",
                        confidence=reading.confidence,
                        extraction_method="color_band_decode"
                    )
                else:
                    # Color decoder failed, log the reason
                    logger.debug(f"Color band decode failed: {reading.error_message}")

            except ImportError:
                logger.debug("ResistorColorDecoder not available")
            except Exception as e:
                logger.debug(f"Color band decode error: {e}")

            # Fallback: return common values based on size with low confidence
            common_values = ["10k", "1k", "100", "4.7k", "220"]
            return ComponentValue(
                component_id=comp_id,
                component_type=comp_type,
                value=common_values[0],  # Default guess
                unit='Ω',
                confidence=0.3,
                extraction_method="estimated_from_size"
            )

        return None

    def _extract_capacitor_value(self, roi: np.ndarray,
                                comp_id: str,
                                comp_type: str) -> Optional[ComponentValue]:
        """Extract capacitor value from markings."""

        if self.ocr_available:
            text = self._ocr_text(roi)

            # Try to parse capacitor codes
            # Format 1: "104" = 10 * 10^4 pF = 100nF
            # Format 2: "10u" = 10µF
            # Format 3: "100n" = 100nF

            # Check for direct notation (10u, 100n, etc.)
            match = re.search(r'(\d+\.?\d*)\s*([upnm])', text, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit_code = match.group(2).lower()

                unit_map = {
                    'u': 'µF',
                    'p': 'pF',
                    'n': 'nF',
                    'm': 'mF'
                }

                return ComponentValue(
                    component_id=comp_id,
                    component_type=comp_type,
                    value=value,
                    unit=unit_map.get(unit_code, 'F'),
                    confidence=0.8,
                    extraction_method="OCR_direct"
                )

            # Check for 3-digit code (e.g., 104)
            match = re.search(r'(\d{3})', text)
            if match:
                code = match.group(1)
                decoded = self._decode_capacitor_code(code)
                if decoded:
                    return ComponentValue(
                        component_id=comp_id,
                        component_type=comp_type,
                        value=decoded['value'],
                        unit=decoded['unit'],
                        confidence=0.7,
                        extraction_method="3_digit_code"
                    )

        # Default common values
        common_cap_values = ["100nF", "10µF", "22pF", "1µF"]
        return ComponentValue(
            component_id=comp_id,
            component_type=comp_type,
            value=common_cap_values[0],
            unit='F',
            confidence=0.2,
            extraction_method="estimated"
        )

    def _extract_ic_marking(self, roi: np.ndarray,
                           comp_id: str,
                           comp_type: str) -> Optional[ComponentValue]:
        """Extract IC part number from top marking."""

        if not self.ocr_available:
            return None

        # Preprocess for better OCR
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # OCR
        text = self._ocr_text(enhanced)

        if text and len(text) > 2:
            # Clean up text
            cleaned = text.strip()

            return ComponentValue(
                component_id=comp_id,
                component_type=comp_type,
                part_number=cleaned,
                confidence=0.6,
                extraction_method="OCR"
            )

        return None

    def _extract_generic_text(self, roi: np.ndarray,
                             comp_id: str,
                             comp_type: str) -> Optional[ComponentValue]:
        """Extract any text from component."""

        if not self.ocr_available:
            return None

        text = self._ocr_text(roi)

        if text and len(text) > 1:
            return ComponentValue(
                component_id=comp_id,
                component_type=comp_type,
                part_number=text.strip(),
                confidence=0.5,
                extraction_method="OCR_generic"
            )

        return None

    def _ocr_text(self, image: np.ndarray) -> str:
        """Perform OCR on image region."""
        if not self.ocr_available:
            return ""

        try:
            import pytesseract

            # Configure tesseract for better results
            config = '--psm 7 --oem 3'  # Single line, LSTM OCR

            text = pytesseract.image_to_string(image, config=config)
            return text.strip()
        except:
            return ""

    def _decode_smd_resistor(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Decode SMD resistor code.

        Common formats:
        - 3 digit: 103 = 10 * 10^3 = 10kΩ
        - 4 digit: 1002 = 100 * 10^2 = 10kΩ
        - R notation: 4R7 = 4.7Ω, R47 = 0.47Ω
        """

        # R notation
        if 'R' in text or 'r' in text:
            # 4R7 = 4.7Ω
            match = re.search(r'(\d*)R(\d*)', text, re.IGNORECASE)
            if match:
                before = match.group(1) or '0'
                after = match.group(2) or '0'
                value = f"{before}.{after}" if after != '0' else before
                return {'value': value, 'unit': 'Ω', 'tolerance': None}

        # 3 digit code
        match = re.search(r'(\d{3})', text)
        if match:
            code = match.group(1)
            first = int(code[0])
            second = int(code[1])
            multiplier = int(code[2])

            base = first * 10 + second
            value = base * (10 ** multiplier)

            # Convert to k or M if large
            if value >= 1_000_000:
                return {'value': f"{value/1_000_000:.1f}M", 'unit': 'Ω'}
            elif value >= 1_000:
                return {'value': f"{value/1_000:.1f}k", 'unit': 'Ω'}
            else:
                return {'value': str(value), 'unit': 'Ω'}

        return None

    def _decode_capacitor_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Decode 3-digit capacitor code.

        Format: XYZ = XY * 10^Z pF

        Examples:
        - 104 = 10 * 10^4 pF = 100,000pF = 100nF
        - 223 = 22 * 10^3 pF = 22,000pF = 22nF
        """

        if len(code) != 3:
            return None

        try:
            first = int(code[0])
            second = int(code[1])
            multiplier = int(code[2])

            base = first * 10 + second
            value_pf = base * (10 ** multiplier)

            # Convert to appropriate unit
            if value_pf >= 1_000_000:
                return {'value': f"{value_pf/1_000_000:.2f}", 'unit': 'µF'}
            elif value_pf >= 1_000:
                return {'value': f"{value_pf/1_000:.1f}", 'unit': 'nF'}
            else:
                return {'value': str(value_pf), 'unit': 'pF'}

        except:
            return None

    def _load_resistor_codes(self) -> Dict[str, Any]:
        """Load resistor color code table."""
        return {
            'black': 0,
            'brown': 1,
            'red': 2,
            'orange': 3,
            'yellow': 4,
            'green': 5,
            'blue': 6,
            'violet': 7,
            'grey': 8,
            'white': 9,
            'gold': -1,  # 0.1 multiplier
            'silver': -2  # 0.01 multiplier
        }

    def _load_smd_codes(self) -> Dict[str, str]:
        """Load common SMD component codes."""
        return {
            # Common voltage regulators
            '117': 'LM1117',
            '1117': 'AMS1117',
            '662K': 'LM2662',

            # Common op-amps
            '358': 'LM358',
            '324': 'LM324',

            # Common transistors
            'A7': '2N7002',
            'J3': 'MMBT3904',
        }

    def _load_capacitor_codes(self) -> Dict[str, str]:
        """Load capacitor voltage rating codes."""
        return {
            '0J': '6.3V',
            '1A': '10V',
            '1C': '16V',
            '1E': '25V',
            '1V': '35V',
            '1H': '50V',
            '2A': '100V',
            '2C': '160V',
            '2E': '250V',
        }

    def infer_value_from_context(self, component_type: str,
                                 nearby_components: List[str],
                                 circuit_type: str) -> Optional[ComponentValue]:
        """
        Infer component value from circuit context.

        Uses electrical engineering knowledge.
        """

        # MCU decoupling capacitors
        if "Capacitor" in component_type and any("ATmega" in c or "Arduino" in c for c in nearby_components):
            return ComponentValue(
                component_id="inferred",
                component_type=component_type,
                value="100",
                unit="nF",
                confidence=0.6,
                extraction_method="context_inference",
                part_number="Likely 100nF decoupling cap"
            )

        # Crystal load capacitors
        if "Capacitor" in component_type and any("Crystal" in c for c in nearby_components):
            return ComponentValue(
                component_id="inferred",
                component_type=component_type,
                value="22",
                unit="pF",
                confidence=0.7,
                extraction_method="context_inference",
                part_number="Likely crystal load cap (18-22pF typical)"
            )

        # LED current limiting resistor
        if "Resistor" in component_type and any("LED" in c for c in nearby_components):
            return ComponentValue(
                component_id="inferred",
                component_type=component_type,
                value="220-1k",
                unit="Ω",
                confidence=0.5,
                extraction_method="context_inference",
                part_number="LED current limiting (typically 220-1k)"
            )

        # Pull-up resistors near MCU
        if "Resistor" in component_type and circuit_type == "arduino":
            return ComponentValue(
                component_id="inferred",
                component_type=component_type,
                value="10k",
                unit="Ω",
                confidence=0.5,
                extraction_method="context_inference",
                part_number="Likely pull-up (10k typical for Arduino)"
            )

        return None


# Global instance
value_extractor = ValueExtractor()
