#!/usr/bin/env python3
"""
Automatic Datasheet Processor

Processes all downloaded datasheets to extract pinout information.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber
from loguru import logger
from typing import List, Dict, Optional
import json
import re


class AutoDatasheetProcessor:
    """Process datasheets automatically."""

    def __init__(self, datasheet_dir: str = "data/datasheets",
                 output_dir: str = "data/extracted_pinouts"):
        """Initialize processor."""
        self.datasheet_dir = Path(datasheet_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_ic_name_from_filename(self, filename: str) -> str:
        """
        Extract IC name from filename.

        Args:
            filename: PDF filename

        Returns:
            IC name
        """
        # Remove extension and manufacturer
        name = filename.replace('.pdf', '')

        # Split by underscore
        parts = name.split('_')

        # Usually IC name is first part
        ic_name = parts[0]

        return ic_name

    def find_pinout_tables(self, pdf_path: Path) -> List[Dict]:
        """
        Find pinout tables in PDF.

        Args:
            pdf_path: Path to PDF

        Returns:
            List of potential pinout data
        """
        logger.info(f"  Analyzing {pdf_path.name}...")

        pinouts = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Scan first 50 pages (pinouts usually early in datasheet)
                max_pages = min(50, len(pdf.pages))

                for page_num in range(max_pages):
                    page = pdf.pages[page_num]
                    text = page.extract_text()

                    if not text:
                        continue

                    # Look for pinout keywords
                    if any(keyword in text.lower() for keyword in
                           ['pin description', 'pin configuration', 'pin assignment',
                            'pinout', 'pin functions', 'terminal functions']):

                        # Try to extract tables
                        tables = page.extract_tables()

                        for table in tables:
                            if not table or len(table) < 2:
                                continue

                            # Check if table looks like a pinout
                            header = [str(cell).lower() if cell else '' for cell in table[0]]

                            if any(keyword in ' '.join(header) for keyword in
                                   ['pin', 'name', 'function', 'description', 'number']):

                                # Found a pinout table
                                pinouts.append({
                                    'page': page_num + 1,
                                    'table': table,
                                    'text_context': text[:500]  # First 500 chars for context
                                })

        except Exception as e:
            logger.warning(f"  Failed to process PDF: {e}")

        return pinouts

    def parse_pinout_table(self, table: List[List], ic_name: str) -> Optional[Dict]:
        """
        Parse pinout table into structured format.

        Args:
            table: Table data
            ic_name: IC name

        Returns:
            Pinout dict or None
        """
        if not table or len(table) < 2:
            return None

        # Get header
        header = [str(cell).lower() if cell else '' for cell in table[0]]

        # Find column indices
        pin_col = -1
        name_col = -1
        function_col = -1

        for i, h in enumerate(header):
            if 'pin' in h or 'number' in h or 'no' in h:
                pin_col = i
            elif 'name' in h or 'signal' in h:
                name_col = i
            elif 'function' in h or 'description' in h or 'type' in h:
                function_col = i

        if pin_col == -1:
            return None

        # Parse rows
        pins = []

        for row in table[1:]:
            if len(row) <= max(pin_col, name_col, function_col):
                continue

            pin_num = str(row[pin_col]).strip() if row[pin_col] else ''
            pin_name = str(row[name_col]).strip() if name_col >= 0 and row[name_col] else ''
            pin_function = str(row[function_col]).strip() if function_col >= 0 and row[function_col] else ''

            # Filter out header rows and invalid pins
            if not pin_num or pin_num.lower() in ['pin', 'no', 'number', '']:
                continue

            # Try to extract numeric pin number
            pin_match = re.search(r'(\d+)', pin_num)
            if pin_match:
                pin_number = int(pin_match.group(1))

                pins.append({
                    'pin': pin_number,
                    'name': pin_name if pin_name else f'PIN{pin_number}',
                    'function': pin_function if pin_function else 'Unknown'
                })

        if len(pins) < 3:  # Too few pins, probably not a real pinout
            return None

        return {
            'ic_name': ic_name,
            'pins': pins,
            'total_pins': len(pins)
        }

    def process_datasheet(self, pdf_path: Path) -> Optional[Dict]:
        """
        Process a single datasheet.

        Args:
            pdf_path: Path to PDF

        Returns:
            Pinout dict or None
        """
        ic_name = self.extract_ic_name_from_filename(pdf_path.name)

        logger.info(f"\nProcessing: {ic_name}")
        logger.info(f"  File: {pdf_path.name}")

        # Check if already processed
        output_file = self.output_dir / f"{ic_name}_pinout.json"

        if output_file.exists():
            logger.info(f"  ✅ Already processed")
            with open(output_file, 'r') as f:
                return json.load(f)

        # Find pinout tables
        pinout_tables = self.find_pinout_tables(pdf_path)

        if not pinout_tables:
            logger.warning(f"  ⚠️  No pinout tables found")
            return None

        logger.info(f"  Found {len(pinout_tables)} potential pinout tables")

        # Try to parse each table
        best_pinout = None
        max_pins = 0

        for i, pt in enumerate(pinout_tables):
            parsed = self.parse_pinout_table(pt['table'], ic_name)

            if parsed and parsed['total_pins'] > max_pins:
                best_pinout = parsed
                max_pins = parsed['total_pins']
                logger.info(f"    Table {i+1} (page {pt['page']}): {max_pins} pins")

        if best_pinout:
            # Save pinout
            with open(output_file, 'w') as f:
                json.dump(best_pinout, f, indent=2)

            logger.info(f"  ✅ Extracted {best_pinout['total_pins']} pins")
            logger.info(f"  💾 Saved to: {output_file}")

            return best_pinout
        else:
            logger.warning(f"  ⚠️  Could not parse pinout tables")
            return None

    def process_all_datasheets(self):
        """Process all downloaded datasheets."""
        logger.info("="*70)
        logger.info("AUTOMATIC DATASHEET PROCESSOR")
        logger.info("="*70)

        if not self.datasheet_dir.exists():
            logger.error(f"Datasheet directory not found: {self.datasheet_dir}")
            return

        pdf_files = list(self.datasheet_dir.glob("*.pdf"))

        if not pdf_files:
            logger.error("No PDF files found!")
            return

        logger.info(f"\nFound {len(pdf_files)} datasheets to process")

        successful = 0
        failed = []
        total_pins = 0

        for pdf_path in pdf_files:
            pinout = self.process_datasheet(pdf_path)

            if pinout:
                successful += 1
                total_pins += pinout['total_pins']
            else:
                failed.append(pdf_path.stem)

        logger.info(f"\n{'='*70}")
        logger.info("PROCESSING COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"\n✅ Successfully processed: {successful}/{len(pdf_files)}")
        logger.info(f"📍 Total pins extracted: {total_pins}")
        logger.info(f"📁 Saved to: {self.output_dir}")

        if failed:
            logger.info(f"\n⚠️  Failed to extract ({len(failed)}):")
            for name in failed[:10]:  # Show first 10
                logger.info(f"   - {name}")

        return successful


def main():
    """Process all datasheets."""
    processor = AutoDatasheetProcessor()
    processor.process_all_datasheets()


if __name__ == "__main__":
    main()
