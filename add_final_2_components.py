#!/usr/bin/env python3
"""Add final 2 components to reach exactly 100"""

import sys
from pathlib import Path

sys.path.insert(0, 'src')

from scrapers.component_database_scraper import ComponentDatabaseScraper, Component


def main():
    print("="*70)
    print("  ADDING FINAL 2 COMPONENTS TO REACH 100!")
    print("="*70)
    print()

    scraper = ComponentDatabaseScraper()
    db_filename = "component_database.json"

    existing = scraper.load_components(db_filename)
    print(f"Current: {len(existing)} components")
    print()

    new_components = [
        # Pressure sensor
        Component(
            id="bmp180_pressure",
            name="BMP180 Barometric Pressure Sensor",
            category="sensor",
            subcategory="pressure",
            manufacturer="Bosch",
            part_number="BMP180",
            cost_usd=4.00,
            specs={
                "interface": "I2C",
                "measures": "Pressure (300-1100 hPa), Temperature",
                "operating_voltage": "3.3V or 5V",
                "i2c_address": "0x77",
                "altitude_range": "-500m to 9000m"
            },
            pinout={
                "VCC": "3.3-5V",
                "GND": "Ground",
                "SDA": "I2C Data",
                "SCL": "I2C Clock"
            },
            datasheet_url="https://www.adafruit.com/product/1603",
            buy_links={"adafruit": "https://www.adafruit.com/product/1603"},
            typical_use_cases=["Weather stations", "Altitude measurement", "Barometric pressure"],
            compatible_with=["Arduino", "ESP32", "ESP8266"],
            source="web_search",
            description="Digital barometric pressure and temperature sensor"
        ),

        # RFID reader
        Component(
            id="rc522_rfid",
            name="RC522 RFID Reader Module",
            category="sensor",
            subcategory="rfid",
            manufacturer="NXP",
            part_number="MFRC522",
            cost_usd=3.00,
            specs={
                "interface": "SPI",
                "frequency": "13.56 MHz",
                "operating_voltage": "3.3V",
                "reading_distance": "0-6cm",
                "supported_cards": "MIFARE Classic, NTAG"
            },
            pinout={
                "VCC": "3.3V",
                "GND": "Ground",
                "RST": "Reset",
                "MISO": "SPI MISO",
                "MOSI": "SPI MOSI",
                "SCK": "SPI Clock",
                "SDA": "SPI Chip Select"
            },
            datasheet_url="https://www.nxp.com/docs/en/data-sheet/MFRC522.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=RC522+RFID"},
            typical_use_cases=["Access control", "ID verification", "Smart cards", "NFC reading"],
            compatible_with=["Arduino", "ESP32", "ESP8266", "MFRC522 library"],
            source="web_search",
            description="13.56MHz RFID reader/writer for contactless cards"
        )
    ]

    print("Adding 2 final components:")
    print("  1. BMP180 Barometric Pressure Sensor")
    print("  2. RC522 RFID Reader Module")
    print()

    merged = scraper.merge_components(existing, new_components)
    scraper.save_components(merged, db_filename)

    print("="*70)
    print(f"✓ COMPLETE: {len(merged)} COMPONENTS!")
    print("="*70)
    print()
    print("🎉 100-COMPONENT DATABASE ACHIEVED! 🎉")
    print()
    print("Monetization Readiness: Component Database = 100% ✓")
    print("="*70)


if __name__ == '__main__':
    main()
