"""
Component Datasheet Retriever

Retrieves and caches component datasheets for reference during repair.
Provides quick access to:
- Pin diagrams
- Electrical specifications
- Application notes
- Common failure modes
"""

import os
import json
import hashlib
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from pathlib import Path
import requests


@dataclass
class DatasheetInfo:
    """Information about a component datasheet."""
    part_number: str
    manufacturer: Optional[str] = None
    datasheet_url: Optional[str] = None
    local_path: Optional[str] = None
    key_specs: Dict[str, str] = None
    common_issues: List[str] = None
    replacement_parts: List[str] = None


class ComponentDatasheetRetriever:
    """Retrieve and manage component datasheets."""

    def __init__(self, cache_dir: str = "data/datasheets"):
        """Initialize retriever."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Metadata cache
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

        # Known datasheet URLs (for common components)
        self.known_datasheets = self._build_known_datasheets()

    def _load_metadata(self) -> Dict[str, DatasheetInfo]:
        """Load cached metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                return {k: DatasheetInfo(**v) for k, v in data.items()}
        return {}

    def _save_metadata(self):
        """Save metadata to cache."""
        data = {k: asdict(v) for k, v in self.metadata.items()}
        with open(self.metadata_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _build_known_datasheets(self) -> Dict[str, DatasheetInfo]:
        """Build database of known component datasheets."""
        datasheets = {}

        # ATmega328P
        datasheets['ATMEGA328P'] = DatasheetInfo(
            part_number='ATMEGA328P',
            manufacturer='Microchip',
            datasheet_url='https://ww1.microchip.com/downloads/en/DeviceDoc/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf',
            key_specs={
                'Operating Voltage': '1.8V - 5.5V',
                'Flash Memory': '32KB',
                'SRAM': '2KB',
                'EEPROM': '1KB',
                'Max Clock': '20MHz',
                'I/O Pins': '23',
                'ADC Channels': '6 (10-bit)'
            },
            common_issues=[
                'Bootloader corruption',
                'Fuse bits misconfigured',
                'Crystal oscillator not working'
            ],
            replacement_parts=['ATMEGA328P-PU', 'ATMEGA328P-AU']
        )

        # LM7805
        datasheets['LM7805'] = DatasheetInfo(
            part_number='LM7805',
            manufacturer='Texas Instruments',
            datasheet_url='https://www.ti.com/lit/ds/symlink/lm340.pdf',
            key_specs={
                'Output Voltage': '5V',
                'Output Current': '1.5A',
                'Input Voltage': '7V - 35V',
                'Dropout Voltage': '2V',
                'Package': 'TO-220'
            },
            common_issues=[
                'Overheating due to insufficient heatsink',
                'Output short circuit',
                'Input voltage too low'
            ],
            replacement_parts=['L7805CV', 'LM340T-5.0', 'MC7805']
        )

        # ESP8266
        datasheets['ESP8266'] = DatasheetInfo(
            part_number='ESP8266',
            manufacturer='Espressif',
            datasheet_url='https://www.espressif.com/sites/default/files/documentation/0a-esp8266ex_datasheet_en.pdf',
            key_specs={
                'Operating Voltage': '3.3V',
                'Flash': 'External (typically 4MB)',
                'WiFi': '802.11 b/g/n',
                'GPIO': '17 pins',
                'ADC': '1 (10-bit)'
            },
            common_issues=[
                'Brownout during WiFi transmission',
                'GPIO2 must be HIGH at boot',
                'Requires 3.3V logic (not 5V tolerant)'
            ],
            replacement_parts=['ESP-12E', 'ESP-12F', 'NodeMCU']
        )

        # CH340G
        datasheets['CH340G'] = DatasheetInfo(
            part_number='CH340G',
            manufacturer='WCH',
            datasheet_url='https://wch-ic.com/downloads/CH340DS1_PDF.html',
            key_specs={
                'Operating Voltage': '3.3V - 5V',
                'Interface': 'USB to UART',
                'Baud Rate': 'Up to 2Mbps',
                'Package': 'SOP-16'
            },
            common_issues=[
                'Overheating (indicates short circuit)',
                'Driver issues on macOS',
                'ESD damage'
            ],
            replacement_parts=['CH340C', 'CP2102', 'FT232RL']
        )

        # AMS1117
        datasheets['AMS1117'] = DatasheetInfo(
            part_number='AMS1117',
            manufacturer='Advanced Monolithic Systems',
            datasheet_url='http://www.advanced-monolithic.com/pdf/ds1117.pdf',
            key_specs={
                'Output Voltage': '3.3V or 5V',
                'Output Current': '1A',
                'Dropout Voltage': '1.3V',
                'Package': 'SOT-223'
            },
            common_issues=[
                'Insufficient input voltage (needs >4.6V for 3.3V out)',
                'No heat dissipation (gets hot)',
                'Missing decoupling capacitors'
            ],
            replacement_parts=['LD1117', 'LM1117']
        )

        return datasheets

    def get_datasheet_info(self, part_number: str) -> Optional[DatasheetInfo]:
        """
        Get datasheet information for component.

        Args:
            part_number: Component part number

        Returns:
            DatasheetInfo or None
        """
        # Normalize part number
        part_number = part_number.upper().strip()

        # Check cache first
        if part_number in self.metadata:
            return self.metadata[part_number]

        # Check known datasheets
        if part_number in self.known_datasheets:
            info = self.known_datasheets[part_number]
            self.metadata[part_number] = info
            self._save_metadata()
            return info

        # Try fuzzy match
        for known_part in self.known_datasheets.keys():
            if known_part in part_number or part_number in known_part:
                info = self.known_datasheets[known_part]
                # Cache with this part number too
                self.metadata[part_number] = info
                self._save_metadata()
                return info

        return None

    def download_datasheet(self, part_number: str) -> Optional[str]:
        """
        Download datasheet PDF to local cache.

        Args:
            part_number: Component part number

        Returns:
            Local file path or None
        """
        info = self.get_datasheet_info(part_number)
        if not info or not info.datasheet_url:
            return None

        # Generate filename
        filename = f"{part_number}_{hashlib.md5(info.datasheet_url.encode()).hexdigest()[:8]}.pdf"
        local_path = self.cache_dir / filename

        # Check if already downloaded
        if local_path.exists():
            return str(local_path)

        # Download
        try:
            response = requests.get(info.datasheet_url, timeout=30)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                f.write(response.content)

            # Update metadata
            info.local_path = str(local_path)
            self.metadata[part_number] = info
            self._save_metadata()

            return str(local_path)

        except Exception as e:
            print(f"Error downloading datasheet: {e}")
            return None

    def get_key_specs(self, part_number: str) -> Optional[Dict[str, str]]:
        """Get key specifications for component."""
        info = self.get_datasheet_info(part_number)
        return info.key_specs if info else None

    def get_common_issues(self, part_number: str) -> List[str]:
        """Get common issues for component."""
        info = self.get_datasheet_info(part_number)
        return info.common_issues if info and info.common_issues else []

    def get_replacement_parts(self, part_number: str) -> List[str]:
        """Get compatible replacement parts."""
        info = self.get_datasheet_info(part_number)
        return info.replacement_parts if info and info.replacement_parts else []

    def search_datasheets_online(self, part_number: str) -> List[str]:
        """
        Search for datasheets online using common sources.

        Returns:
            List of potential datasheet URLs
        """
        # Search URLs
        search_urls = []

        # Octopart
        search_urls.append(f"https://octopart.com/search?q={part_number}")

        # Datasheet Archive
        search_urls.append(f"https://www.datasheetarchive.com/search/{part_number}")

        # All Datasheet
        search_urls.append(f"https://www.alldatasheet.com/datasheet-pdf/search.jsp?searchWord={part_number}")

        return search_urls


# Global singleton
datasheet_retriever = ComponentDatasheetRetriever()
