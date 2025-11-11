#!/usr/bin/env python3
"""
IC Datasheet Downloader

Downloads datasheets for top 50 most common ICs.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from loguru import logger
from typing import List, Dict
import time


class DatasheetDownloader:
    """Download IC datasheets."""

    def __init__(self, output_dir: str = "data/datasheets"):
        """Initialize downloader."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Top 50 most common ICs in electronics
        self.top_ics = [
            # Microcontrollers
            {"name": "ATmega328P", "manufacturer": "Microchip", "url": "https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf"},
            {"name": "ATmega2560", "manufacturer": "Microchip", "url": "https://ww1.microchip.com/downloads/en/devicedoc/atmel-2549-8-bit-avr-microcontroller-atmega640-1280-1281-2560-2561_datasheet.pdf"},
            {"name": "ESP8266", "manufacturer": "Espressif", "url": "https://www.espressif.com/sites/default/files/documentation/0a-esp8266ex_datasheet_en.pdf"},
            {"name": "ESP32", "manufacturer": "Espressif", "url": "https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf"},
            {"name": "STM32F103", "manufacturer": "ST", "url": "https://www.st.com/resource/en/datasheet/stm32f103c8.pdf"},
            {"name": "PIC16F877A", "manufacturer": "Microchip", "url": "https://ww1.microchip.com/downloads/en/DeviceDoc/39582b.pdf"},

            # Voltage Regulators
            {"name": "LM7805", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/lm7805.pdf"},
            {"name": "LM7812", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/lm78.pdf"},
            {"name": "AMS1117", "manufacturer": "AMS", "url": "http://www.advanced-monolithic.com/pdf/ds1117.pdf"},
            {"name": "LM317", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/lm317.pdf"},
            {"name": "LM2596", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/lm2596.pdf"},

            # USB/Serial
            {"name": "CH340G", "manufacturer": "WCH", "url": "https://www.wch-ic.com/downloads/CH340DS1_PDF.html"},
            {"name": "FT232RL", "manufacturer": "FTDI", "url": "https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf"},
            {"name": "CP2102", "manufacturer": "Silicon Labs", "url": "https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf"},

            # Op-Amps
            {"name": "LM358", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/lm358.pdf"},
            {"name": "TL072", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/tl072.pdf"},
            {"name": "NE5532", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/ne5532.pdf"},

            # Logic ICs
            {"name": "74HC595", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/sn74hc595.pdf"},
            {"name": "74HC04", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/sn74hc04.pdf"},
            {"name": "CD4017", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/cd4017b.pdf"},

            # Sensors
            {"name": "DHT11", "manufacturer": "Aosong", "url": "https://www.mouser.com/datasheet/2/758/DHT11-Technical-Data-Sheet-Translated-Version-1143054.pdf"},
            {"name": "DS18B20", "manufacturer": "Maxim", "url": "https://datasheets.maximintegrated.com/en/ds/DS18B20.pdf"},
            {"name": "BMP280", "manufacturer": "Bosch", "url": "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp280-ds001.pdf"},

            # Motor Drivers
            {"name": "L298N", "manufacturer": "ST", "url": "https://www.st.com/resource/en/datasheet/l298.pdf"},
            {"name": "ULN2003", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/uln2003a.pdf"},

            # Power Management
            {"name": "TP4056", "manufacturer": "TP", "url": "https://dlnmh9ip6v2uc.cloudfront.net/datasheets/Prototyping/TP4056.pdf"},
            {"name": "TPS54340", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/tps54340.pdf"},

            # Memory
            {"name": "AT24C32", "manufacturer": "Microchip", "url": "https://ww1.microchip.com/downloads/en/devicedoc/doc0336.pdf"},
            {"name": "W25Q128", "manufacturer": "Winbond", "url": "https://www.winbond.com/resource-files/w25q128jv%20revf%2003272018%20plus.pdf"},

            # Display Drivers
            {"name": "MAX7219", "manufacturer": "Maxim", "url": "https://datasheets.maximintegrated.com/en/ds/MAX7219-MAX7221.pdf"},
            {"name": "TM1637", "manufacturer": "Titan Micro", "url": "https://www.mcielectronics.cl/website_MCI/static/documents/Datasheet_TM1637.pdf"},

            # Additional Common ICs
            {"name": "NE555", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/ne555.pdf"},
            {"name": "LM393", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/lm393.pdf"},
            {"name": "4N35", "manufacturer": "Vishay", "url": "https://www.vishay.com/docs/81181/4n35.pdf"},
            {"name": "PC817", "manufacturer": "Sharp", "url": "https://www.sharpsde.com/fileadmin/products/Optoelectronics/Datasheets/PC817.pdf"},
            {"name": "IRF540", "manufacturer": "Infineon", "url": "https://www.infineon.com/dgdl/irf540n.pdf"},
            {"name": "2N2222", "manufacturer": "ON Semi", "url": "https://www.onsemi.com/pdf/datasheet/p2n2222a-d.pdf"},
            {"name": "BC547", "manufacturer": "ON Semi", "url": "https://www.onsemi.com/pdf/datasheet/bc546-d.pdf"},

            # Wi-Fi/Bluetooth
            {"name": "HC-05", "manufacturer": "HC", "url": "https://components101.com/sites/default/files/component_datasheet/HC-05%20Datasheet.pdf"},
            {"name": "NRF24L01", "manufacturer": "Nordic", "url": "https://www.nordicsemi.com/products/nrf24l01"},

            # Real-Time Clocks
            {"name": "DS1307", "manufacturer": "Maxim", "url": "https://datasheets.maximintegrated.com/en/ds/DS1307.pdf"},
            {"name": "DS3231", "manufacturer": "Maxim", "url": "https://datasheets.maximintegrated.com/en/ds/DS3231.pdf"},

            # ADC/DAC
            {"name": "MCP3008", "manufacturer": "Microchip", "url": "https://ww1.microchip.com/downloads/en/DeviceDoc/21295d.pdf"},
            {"name": "ADS1115", "manufacturer": "TI", "url": "https://www.ti.com/lit/ds/symlink/ads1115.pdf"},

            # LED Drivers
            {"name": "WS2812B", "manufacturer": "Worldsemi", "url": "https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf"},

            # Misc
            {"name": "MPU6050", "manufacturer": "TDK", "url": "https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf"},
            {"name": "HC-SR04", "manufacturer": "ETC", "url": "https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf"},
            {"name": "SG90", "manufacturer": "TowerPro", "url": "http://www.ee.ic.ac.uk/pcheung/teaching/DE1_EE/stores/sg90_datasheet.pdf"},
            {"name": "LCD1602", "manufacturer": "Generic", "url": "https://www.sparkfun.com/datasheets/LCD/ADM1602K-NSW-FBS-3.3v.pdf"},
            {"name": "MCP23017", "manufacturer": "Microchip", "url": "https://ww1.microchip.com/downloads/en/devicedoc/20001952c.pdf"},
        ]

    def download_datasheet(self, ic: Dict) -> bool:
        """
        Download a single datasheet.

        Args:
            ic: Dictionary with name, manufacturer, url

        Returns:
            True if successful
        """
        name = ic['name']
        url = ic['url']
        manufacturer = ic['manufacturer']

        output_file = self.output_dir / f"{name}_{manufacturer}.pdf"

        if output_file.exists():
            logger.info(f"✅ Already have: {name}")
            return True

        logger.info(f"⬇️  Downloading: {name} ({manufacturer})")
        logger.info(f"   URL: {url}")

        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()

            # Some URLs might be HTML pages, not direct PDFs
            content_type = response.headers.get('content-type', '')

            if 'pdf' not in content_type.lower() and not url.endswith('.pdf'):
                logger.warning(f"   ⚠️  Not a direct PDF link, skipping: {name}")
                return False

            with open(output_file, 'wb') as f:
                f.write(response.content)

            file_size = output_file.stat().st_size / 1024 / 1024  # MB
            logger.info(f"   ✅ Downloaded: {name} ({file_size:.1f} MB)")

            return True

        except Exception as e:
            logger.error(f"   ❌ Failed: {e}")
            if output_file.exists():
                output_file.unlink()
            return False

    def download_all(self):
        """Download all datasheets."""
        logger.info("="*70)
        logger.info("IC DATASHEET DOWNLOADER")
        logger.info("="*70)
        logger.info(f"\nDownloading {len(self.top_ics)} datasheets...")

        successful = 0
        failed = []

        for i, ic in enumerate(self.top_ics, 1):
            logger.info(f"\n[{i}/{len(self.top_ics)}] {ic['name']}")

            if self.download_datasheet(ic):
                successful += 1
            else:
                failed.append(ic['name'])

            # Rate limit - be nice to servers
            time.sleep(1)

        logger.info(f"\n{'='*70}")
        logger.info("DOWNLOAD COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"\n✅ Successfully downloaded: {successful}/{len(self.top_ics)}")
        logger.info(f"📁 Saved to: {self.output_dir}")

        if failed:
            logger.info(f"\n❌ Failed downloads ({len(failed)}):")
            for name in failed:
                logger.info(f"   - {name}")

        logger.info(f"\n💡 Next Steps:")
        logger.info(f"   1. Extract pinout tables from PDFs")
        logger.info(f"   2. Parse into structured format")
        logger.info(f"   3. Add to pinout database")
        logger.info(f"   Run: python scripts/data_collection/scrape_datasheets.py")

        return successful


def main():
    """Download all IC datasheets."""
    downloader = DatasheetDownloader()
    downloader.download_all()


if __name__ == "__main__":
    main()
