#!/usr/bin/env python3
"""
Datasheet Scraper and Pin Extractor

Automatically extracts IC pinouts from PDF datasheets.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import re
import json
from typing import List, Dict, Optional
from loguru import logger

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False
    logger.warning("tabula-py not installed. Install with: pip install tabula-py")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 not installed. Install with: pip install PyPDF2")


class DatasheetPinExtractor:
    """Extract pin information from datasheet PDFs."""

    def __init__(self):
        """Initialize extractor."""
        self.output_dir = Path("data/extracted_pinouts")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_from_pdf(self, pdf_path: str, ic_name: str) -> Optional[Dict]:
        """
        Extract pinout from PDF datasheet.

        Args:
            pdf_path: Path to PDF file
            ic_name: IC name (e.g., "ATmega328P")

        Returns:
            Structured pinout data or None
        """
        if not TABULA_AVAILABLE:
            logger.error("tabula-py not available")
            return None

        logger.info(f"Extracting pinout from: {pdf_path}")

        # Try to find pin table in PDF
        try:
            # Read all tables
            tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)

            logger.info(f"Found {len(tables)} tables in PDF")

            # Look for table with pin information
            for i, table in enumerate(tables):
                if self._looks_like_pin_table(table):
                    logger.info(f"Table {i} looks like pin table!")
                    pinout = self._parse_pin_table(table, ic_name)
                    if pinout:
                        return pinout

        except Exception as e:
            logger.error(f"Error reading PDF: {e}")

        return None

    def _looks_like_pin_table(self, table) -> bool:
        """Check if table looks like a pin table."""
        # Check column names
        columns = [str(col).lower() for col in table.columns]

        pin_keywords = ['pin', 'name', 'number', 'type', 'description']

        # If table has columns matching pin keywords
        matching = sum(1 for keyword in pin_keywords if any(keyword in col for col in columns))

        return matching >= 2

    def _parse_pin_table(self, table, ic_name: str) -> Optional[Dict]:
        """Parse pin table into structured format."""
        pins = []

        # Try to identify columns
        columns = {str(col).lower(): col for col in table.columns}

        pin_num_col = None
        pin_name_col = None
        pin_desc_col = None

        for keyword, col_name in columns.items():
            if 'pin' in keyword and ('num' in keyword or '#' in keyword):
                pin_num_col = col_name
            elif 'name' in keyword or 'symbol' in keyword:
                pin_name_col = col_name
            elif 'desc' in keyword or 'function' in keyword:
                pin_desc_col = col_name

        if not pin_num_col or not pin_name_col:
            logger.warning("Couldn't identify pin columns")
            return None

        # Parse rows
        for idx, row in table.iterrows():
            try:
                pin_num = row[pin_num_col]
                pin_name = row[pin_name_col]

                # Skip if not a number
                if not str(pin_num).strip().isdigit():
                    continue

                pin_desc = row[pin_desc_col] if pin_desc_col else ""

                pins.append({
                    "pin_number": int(pin_num),
                    "pin_name": str(pin_name).strip(),
                    "description": str(pin_desc).strip(),
                    "pin_type": self._guess_pin_type(str(pin_name), str(pin_desc))
                })

            except Exception as e:
                continue

        if pins:
            return {
                "part_number": ic_name,
                "pin_count": len(pins),
                "pins": pins,
                "source": "auto-extracted"
            }

        return None

    def _guess_pin_type(self, name: str, desc: str) -> str:
        """Guess pin type from name/description."""
        text = (name + " " + desc).upper()

        if any(keyword in text for keyword in ['VCC', 'VDD', 'POWER', '+V']):
            return "POWER"
        elif any(keyword in text for keyword in ['GND', 'VSS', 'GROUND']):
            return "GROUND"
        elif any(keyword in text for keyword in ['RX', 'TX', 'SDA', 'SCL', 'MOSI', 'MISO']):
            return "IO"
        elif any(keyword in text for keyword in ['RESET', 'RST']):
            return "INPUT"
        else:
            return "IO"

    def save_pinout(self, pinout: Dict):
        """Save extracted pinout to JSON."""
        output_file = self.output_dir / f"{pinout['part_number']}.json"

        with open(output_file, 'w') as f:
            json.dump(pinout, f, indent=2)

        logger.info(f"Saved pinout to: {output_file}")


# List of common ICs to find datasheets for
COMMON_ICS = [
    # Microcontrollers
    ("ATmega328P", "https://ww1.microchip.com/downloads/en/DeviceDoc/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf"),
    ("ATmega2560", "https://ww1.microchip.com/downloads/en/devicedoc/atmel-2549-8-bit-avr-microcontroller-atmega640-1280-1281-2560-2561_datasheet.pdf"),
    ("ESP32", "https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf"),
    ("STM32F103", "https://www.st.com/resource/en/datasheet/stm32f103c8.pdf"),

    # Voltage Regulators
    ("LM7805", "https://www.ti.com/lit/ds/symlink/lm340.pdf"),
    ("AMS1117", "http://www.advanced-monolithic.com/pdf/ds1117.pdf"),
    ("LM317", "https://www.ti.com/lit/ds/symlink/lm317.pdf"),

    # USB-Serial
    ("CH340G", "https://wch.cn/downloads/CH340DS1_PDF.html"),
    ("CP2102", "https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf"),
    ("FT232RL", "https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf"),

    # Memory
    ("W25Q32", "https://www.winbond.com/resource-files/w25q32jv%20revg%2003272018%20plus.pdf"),
    ("AT24C256", "https://ww1.microchip.com/downloads/en/devicedoc/doc0670.pdf"),

    # Logic
    ("74HC595", "https://www.ti.com/lit/ds/symlink/sn74hc595.pdf"),
    ("CD4051", "https://www.ti.com/lit/ds/symlink/cd4051b.pdf"),

    # Motor Drivers
    ("L293D", "https://www.ti.com/lit/ds/symlink/l293.pdf"),
    ("L298N", "https://www.st.com/resource/en/datasheet/l298.pdf"),

    # Sensors
    ("DHT22", "https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf"),
    ("MPU6050", "https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf"),
]


def main():
    """Run datasheet extraction."""
    logger.info("Datasheet Pin Extractor")
    logger.info("="*70)

    if not TABULA_AVAILABLE:
        logger.error("tabula-py not installed!")
        logger.info("Install with:")
        logger.info("  pip install tabula-py")
        logger.info("  # Also requires Java")
        return

    extractor = DatasheetPinExtractor()

    logger.info(f"\nCommon ICs to process: {len(COMMON_ICS)}")
    logger.info("\nTo extract pinouts:")
    logger.info("1. Download datasheets (URLs listed above)")
    logger.info("2. Run: extractor.extract_from_pdf('path/to/datasheet.pdf', 'IC_NAME')")
    logger.info("3. Pinout saved to: data/extracted_pinouts/")

    # Example usage
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE USAGE:")
    logger.info("="*70)

    example = """
from scripts.data_collection.scrape_datasheets import DatasheetPinExtractor

extractor = DatasheetPinExtractor()

# Extract from local PDF
pinout = extractor.extract_from_pdf(
    'datasheets/ATmega328P.pdf',
    'ATmega328P'
)

if pinout:
    extractor.save_pinout(pinout)
    print(f"Extracted {len(pinout['pins'])} pins")
"""

    print(example)

    # List ICs we want
    logger.info("\n" + "="*70)
    logger.info("TARGET ICS (Top Priority):")
    logger.info("="*70)

    for ic_name, url in COMMON_ICS[:10]:
        logger.info(f"\n{ic_name}")
        logger.info(f"  URL: {url}")


if __name__ == "__main__":
    main()
