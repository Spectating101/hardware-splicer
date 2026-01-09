#!/usr/bin/env python3
"""
Expand component database with scraped sensor data from Adafruit
Uses information from WebSearch and WebFetch
"""

import sys
from pathlib import Path

sys.path.insert(0, 'src')

from scrapers.component_database_scraper import ComponentDatabaseScraper, Component


def main():
    print("="*70)
    print("  EXPANDING COMPONENT DATABASE WITH SCRAPED DATA")
    print("="*70)
    print()

    scraper = ComponentDatabaseScraper()

    # Load existing components
    existing = scraper.load_components("component_database.json")
    print(f"Starting with {len(existing)} components")
    print()

    new_components = []

    # Add sensors scraped from Adafruit
    print("Adding sensors from Adafruit (scraped via WebFetch)...")

    # DHT11 (cheaper version of DHT22)
    new_components.append(Component(
        id="dht11",
        name="DHT11 Temperature and Humidity Sensor",
        category="sensor",
        subcategory="temperature_humidity",
        manufacturer="Aosong",
        part_number="DHT11",
        cost_usd=5.00,  # Estimated based on market pricing
        specs={
            "temperature_range": "0 to 50°C",
            "temperature_accuracy": "±2°C",
            "humidity_range": "20-80%",
            "humidity_accuracy": "±5%",
            "sampling_rate": "1 Hz (once per second)",
            "voltage": "3-5V",
            "interface": "Single-wire digital"
        },
        pinout={
            "VCC": "3-5V power",
            "DATA": "Digital data pin (needs 4.7k-10k pullup)",
            "NC": "Not connected",
            "GND": "Ground"
        },
        datasheet_url="https://www.mouser.com/datasheet/2/758/DHT11-Technical-Data-Sheet-Translated-Version-1143054.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/386",
            "amazon": "https://www.amazon.com/s?k=DHT11"
        },
        typical_use_cases=["Basic weather station", "Budget climate monitoring"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Budget-friendly temperature and humidity sensor"
    ))

    # DS18B20
    new_components.append(Component(
        id="ds18b20",
        name="DS18B20 Digital Temperature Sensor",
        category="sensor",
        subcategory="temperature",
        manufacturer="Maxim Integrated",
        part_number="DS18B20",
        cost_usd=3.95,  # From Adafruit
        specs={
            "temperature_range": "-55 to 125°C",
            "accuracy": "±0.5°C (from -10°C to +85°C)",
            "resolution": "9 to 12 bits configurable",
            "voltage": "3.0-5.5V",
            "interface": "1-Wire (OneWire)",
            "unique_id": "64-bit serial code",
            "waterproof_version": "Available"
        },
        pinout={
            "VCC": "3.0-5.5V power",
            "DATA": "1-Wire data (needs 4.7k pullup)",
            "GND": "Ground"
        },
        datasheet_url="https://datasheets.maximintegrated.com/en/ds/DS18B20.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/374",
            "sparkfun": "https://www.sparkfun.com/products/245"
        },
        typical_use_cases=["Water temperature", "Multiple sensor networks", "HVAC monitoring"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Waterproof digital temperature sensor with unique ID"
    ))

    # BME680
    new_components.append(Component(
        id="bme680",
        name="BME680 Environmental Sensor",
        category="sensor",
        subcategory="environmental",
        manufacturer="Bosch",
        part_number="BME680",
        cost_usd=18.95,  # From Adafruit
        specs={
            "temperature_range": "-40 to 85°C",
            "temperature_accuracy": "±1°C",
            "humidity_range": "0-100%",
            "humidity_accuracy": "±3%",
            "pressure_range": "300-1100 hPa",
            "pressure_accuracy": "±1 hPa",
            "gas_sensor": "VOC detection",
            "iaq_index": "Indoor Air Quality index",
            "voltage": "3.3V",
            "interface": "I2C or SPI"
        },
        pinout={
            "VCC": "3.3V power",
            "GND": "Ground",
            "SCL": "I2C clock",
            "SDA": "I2C data"
        },
        datasheet_url="https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme680-ds001.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/3660",
            "amazon": "https://www.amazon.com/s?k=BME680"
        },
        typical_use_cases=["Air quality monitoring", "IAQ index", "Smart home", "Environmental stations"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Premium 4-in-1 environmental sensor with gas/VOC detection"
    ))

    # BMP280
    new_components.append(Component(
        id="bmp280",
        name="BMP280 Barometric Pressure Sensor",
        category="sensor",
        subcategory="pressure",
        manufacturer="Bosch",
        part_number="BMP280",
        cost_usd=9.95,  # From Adafruit
        specs={
            "pressure_range": "300-1100 hPa",
            "pressure_accuracy": "±1 hPa",
            "temperature_range": "-40 to 85°C",
            "temperature_accuracy": "±1°C",
            "altitude_detection": "Yes",
            "voltage": "3.3V",
            "interface": "I2C or SPI"
        },
        pinout={
            "VCC": "3.3V",
            "GND": "Ground",
            "SCL": "I2C clock",
            "SDA": "I2C data"
        },
        datasheet_url="https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp280-ds001.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/2651",
            "sparkfun": "https://www.sparkfun.com/products/15440"
        },
        typical_use_cases=["Weather station", "Altimeter", "Barometric pressure monitoring"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Accurate barometric pressure and temperature sensor"
    ))

    # PIR Motion Sensor
    new_components.append(Component(
        id="pir_motion_sensor",
        name="PIR Motion Sensor",
        category="sensor",
        subcategory="motion",
        manufacturer="Generic",
        part_number="HC-SR501",
        cost_usd=9.95,  # From Adafruit
        specs={
            "detection_range": "Up to 7 meters",
            "detection_angle": "120 degrees",
            "voltage": "5-12V",
            "output": "Digital HIGH when motion detected",
            "delay_time": "Adjustable (0.5 to 200 seconds)",
            "sensitivity": "Adjustable"
        },
        pinout={
            "VCC": "5-12V power",
            "OUT": "Digital output",
            "GND": "Ground"
        },
        datasheet_url="https://www.epitran.it/ebayDrive/datasheet/44.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/189",
            "amazon": "https://www.amazon.com/s?k=PIR+motion+sensor"
        },
        typical_use_cases=["Security systems", "Automatic lighting", "Presence detection"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Passive infrared motion detection sensor"
    ))

    # HC-SR04 Ultrasonic
    new_components.append(Component(
        id="hc_sr04",
        name="HC-SR04 Ultrasonic Distance Sensor",
        category="sensor",
        subcategory="distance",
        manufacturer="Generic",
        part_number="HC-SR04",
        cost_usd=3.95,  # From Adafruit
        specs={
            "range": "2cm to 400cm",
            "accuracy": "±0.3cm",
            "resolution": "0.3cm",
            "voltage": "5V",
            "interface": "Digital trigger/echo",
            "measuring_angle": "15 degrees",
            "frequency": "40 kHz"
        },
        pinout={
            "VCC": "5V power",
            "TRIG": "Trigger input",
            "ECHO": "Echo output",
            "GND": "Ground"
        },
        datasheet_url="https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/3942",
            "sparkfun": "https://www.sparkfun.com/products/15569"
        },
        typical_use_cases=["Robot obstacle detection", "Parking sensors", "Water level monitoring"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Accurate ultrasonic distance measurement sensor"
    ))

    # MPU-6050
    new_components.append(Component(
        id="mpu6050",
        name="MPU-6050 6-DoF Accelerometer/Gyroscope",
        category="sensor",
        subcategory="motion_imu",
        manufacturer="InvenSense",
        part_number="MPU-6050",
        cost_usd=12.95,  # From Adafruit
        specs={
            "accelerometer_range": "±2, ±4, ±8, ±16g",
            "gyroscope_range": "±250, ±500, ±1000, ±2000°/s",
            "dof": "6 (3-axis accel + 3-axis gyro)",
            "voltage": "3.3V",
            "interface": "I2C",
            "dmp": "Digital Motion Processor"
        },
        pinout={
            "VCC": "3.3V",
            "GND": "Ground",
            "SCL": "I2C clock",
            "SDA": "I2C data"
        },
        datasheet_url="https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/3886",
            "amazon": "https://www.amazon.com/s?k=MPU6050"
        },
        typical_use_cases=["Drones", "Self-balancing robots", "Motion tracking", "Gesture recognition"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="6-axis motion tracking sensor with accelerometer and gyroscope"
    ))

    # BH1750 Light Sensor
    new_components.append(Component(
        id="bh1750",
        name="BH1750 Light Sensor",
        category="sensor",
        subcategory="light",
        manufacturer="ROHM",
        part_number="BH1750FVI",
        cost_usd=4.50,  # From Adafruit
        specs={
            "range": "1-65535 lux",
            "resolution": "1 lux",
            "accuracy": "±20%",
            "voltage": "3.3-5V",
            "interface": "I2C",
            "spectral_response": "Approximates human eye"
        },
        pinout={
            "VCC": "3.3-5V",
            "GND": "Ground",
            "SCL": "I2C clock",
            "SDA": "I2C data"
        },
        datasheet_url="https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/4681",
            "amazon": "https://www.amazon.com/s?k=BH1750"
        },
        typical_use_cases=["Automatic brightness control", "Light metering", "Smart lighting"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="adafruit",
        description="Digital ambient light sensor with wide range"
    ))

    print(f"✓ Added {len(new_components)} new components from Adafruit")
    print()

    # Merge with existing
    all_components = scraper.merge_components(new_components, existing)

    print(f"Total components: {len(all_components)}")
    print()

    # Show summary
    categories = {}
    for comp in all_components:
        if comp.category not in categories:
            categories[comp.category] = []
        categories[comp.category].append(comp)

    print("Components by category:")
    for category, comps in sorted(categories.items()):
        print(f"\n  {category.upper()}: {len(comps)} components")
        for comp in sorted(comps, key=lambda x: x.cost_usd):
            print(f"    • {comp.name} - ${comp.cost_usd:.2f} ({comp.source})")

    # Save expanded database
    scraper.save_components(all_components, "component_database.json")

    print()
    print("="*70)
    print(f"✓ Database expanded to {len(all_components)} components!")
    print("="*70)
    print()
    print("Sources:")
    print("  • Random Nerd Tutorials: https://randomnerdtutorials.com/arduino-free-guides-sensors-modules/")
    print("  • Adafruit Sensors: https://www.adafruit.com/category/35")
    print("  • Sensor Comparison: https://www.instructables.com/Sensor-Comparison-DHT11-Vs-DHT22-Vs-BME680-Vs-DS18/")
    print("="*70)


if __name__ == '__main__':
    main()
