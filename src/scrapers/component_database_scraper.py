#!/usr/bin/env python3
"""
Component Database Scraper for Circuit-AI
Scrapes component specs and pricing from DigiKey, Mouser, Adafruit, SparkFun
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class Component:
    """Represents a scraped component"""
    id: str
    name: str
    category: str  # "microcontroller", "sensor", "display", etc.
    subcategory: str  # "wifi", "temperature", "oled", etc.
    manufacturer: str
    part_number: str
    cost_usd: float
    specs: Dict  # Technical specifications
    pinout: Dict  # Pin configuration
    datasheet_url: Optional[str]
    buy_links: Dict  # {source: url}
    typical_use_cases: List[str]
    compatible_with: List[str]
    source: str  # Where it was scraped from
    description: str


class ComponentDatabaseScraper:
    """Scrapes components from online sources"""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "data" / "component_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Known component sources
        self.sources = {
            'adafruit': {
                'base_url': 'https://www.adafruit.com',
                'categories': {
                    'esp32': 'https://www.adafruit.com/category/945',
                    'sensors': 'https://www.adafruit.com/category/35',
                    'displays': 'https://www.adafruit.com/category/63'
                }
            },
            'sparkfun': {
                'base_url': 'https://www.sparkfun.com',
                'categories': {
                    'microcontrollers': 'https://www.sparkfun.com/categories/300',
                    'sensors': 'https://www.sparkfun.com/categories/23'
                }
            },
            'digikey': {
                'base_url': 'https://www.digikey.com',
                'search_url': 'https://www.digikey.com/en/products/filter/'
            },
            'mouser': {
                'base_url': 'https://www.mouser.com',
                'search_url': 'https://www.mouser.com/c/'
            }
        }

    def build_component_from_data(
        self,
        name: str,
        category: str,
        subcategory: str,
        specs: Dict,
        cost: float,
        source: str,
        **kwargs
    ) -> Component:
        """Build a component from scraped data"""

        # Generate ID from name
        comp_id = name.lower().replace(' ', '_').replace('-', '_')

        # Extract manufacturer and part number if available
        manufacturer = kwargs.get('manufacturer', 'Unknown')
        part_number = kwargs.get('part_number', comp_id)

        return Component(
            id=comp_id,
            name=name,
            category=category,
            subcategory=subcategory,
            manufacturer=manufacturer,
            part_number=part_number,
            cost_usd=cost,
            specs=specs,
            pinout=kwargs.get('pinout', {}),
            datasheet_url=kwargs.get('datasheet_url'),
            buy_links=kwargs.get('buy_links', {source: kwargs.get('url', '')}),
            typical_use_cases=kwargs.get('use_cases', []),
            compatible_with=kwargs.get('compatible_with', []),
            source=source,
            description=kwargs.get('description', f"{name} from {source}")
        )

    def save_components(self, components: List[Component], filename: str = "scraped_components.json"):
        """Save components to cache"""
        cache_file = self.cache_dir / filename

        data = [asdict(comp) for comp in components]

        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Saved {len(components)} components to {cache_file}")

    def load_components(self, filename: str = "scraped_components.json") -> List[Component]:
        """Load components from cache"""
        cache_file = self.cache_dir / filename

        if not cache_file.exists():
            return []

        with open(cache_file, 'r') as f:
            data = json.load(f)

        components = [Component(**comp) for comp in data]
        print(f"✓ Loaded {len(components)} components from cache")

        return components

    def merge_components(self, new_components: List[Component], existing: List[Component]) -> List[Component]:
        """Merge new components with existing, avoiding duplicates"""
        existing_ids = {comp.id for comp in existing}

        merged = existing.copy()

        for comp in new_components:
            if comp.id not in existing_ids:
                merged.append(comp)
            else:
                # Update pricing if different source has better price
                existing_comp = next(c for c in merged if c.id == comp.id)
                if comp.cost_usd < existing_comp.cost_usd:
                    existing_comp.cost_usd = comp.cost_usd
                    existing_comp.buy_links[comp.source] = comp.buy_links.get(comp.source, '')

        return merged

    def search_components(self, query: str, category: Optional[str] = None) -> List[Component]:
        """Search for components (placeholder - would use WebSearch in practice)"""
        print(f"\nWould search for: '{query}' in category: {category or 'all'}")
        print("Use WebSearch tool in Claude Code to actually scrape")
        return []


def build_manual_database():
    """
    Build initial component database manually from known components
    This simulates what would be scraped from DigiKey/Mouser/Adafruit
    """
    print("="*70)
    print("  BUILDING COMPONENT DATABASE")
    print("="*70)
    print()

    scraper = ComponentDatabaseScraper()

    components = []

    # WiFi Microcontrollers
    print("Adding WiFi Microcontrollers...")

    components.append(Component(
        id="esp32_devkit_v1",
        name="ESP32 DevKit V1",
        category="microcontroller",
        subcategory="wifi_bluetooth",
        manufacturer="Espressif",
        part_number="ESP32-DEVKITV1",
        cost_usd=8.00,
        specs={
            "cores": 2,
            "cpu_mhz": 240,
            "ram_kb": 520,
            "flash_mb": 4,
            "wifi": "802.11 b/g/n (2.4GHz)",
            "bluetooth": "BLE 4.2",
            "gpio_pins": 30,
            "adc_channels": 18,
            "dac_channels": 2,
            "i2c": 2,
            "spi": 4,
            "uart": 3,
            "voltage": "3.3V",
            "input_voltage": "5V via USB or 7-12V via Vin"
        },
        pinout={
            "3V3": "3.3V power output",
            "GND": "Ground",
            "D1": "GPIO1 (TX)",
            "D2": "GPIO2",
            "D3": "GPIO3 (RX)",
            "D4": "GPIO4",
            "D5": "GPIO5"
        },
        datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf",
        buy_links={
            "amazon": "https://www.amazon.com/s?k=ESP32+DevKit",
            "adafruit": "https://www.adafruit.com/product/3405",
            "aliexpress": "https://www.aliexpress.com/wholesale?SearchText=esp32+devkit"
        },
        typical_use_cases=["IoT", "WiFi sensor", "Bluetooth devices", "Web server", "Smart home"],
        compatible_with=["DHT22", "OLED SSD1306", "BME280", "relays", "servos"],
        source="manual",
        description="Popular ESP32 development board with WiFi and Bluetooth"
    ))

    components.append(Component(
        id="esp8266_nodemcu",
        name="ESP8266 NodeMCU",
        category="microcontroller",
        subcategory="wifi",
        manufacturer="Espressif",
        part_number="ESP8266-12E",
        cost_usd=4.00,
        specs={
            "cores": 1,
            "cpu_mhz": 80,
            "ram_kb": 80,
            "flash_mb": 4,
            "wifi": "802.11 b/g/n (2.4GHz)",
            "bluetooth": None,
            "gpio_pins": 17,
            "adc_channels": 1,
            "i2c": 1,
            "spi": 1,
            "uart": 2,
            "voltage": "3.3V",
            "input_voltage": "5V via USB"
        },
        pinout={
            "3V3": "3.3V power output",
            "GND": "Ground",
            "D1": "GPIO5",
            "D2": "GPIO4",
            "D3": "GPIO0",
            "D4": "GPIO2",
            "D5": "GPIO14",
            "D6": "GPIO12",
            "D7": "GPIO13"
        },
        datasheet_url="https://www.espressif.com/sites/default/files/documentation/0a-esp8266ex_datasheet_en.pdf",
        buy_links={
            "amazon": "https://www.amazon.com/s?k=ESP8266+NodeMCU",
            "adafruit": "https://www.adafruit.com/product/2471",
            "aliexpress": "https://www.aliexpress.com/wholesale?SearchText=nodemcu"
        },
        typical_use_cases=["Simple IoT", "WiFi sensor", "Home automation", "Learning"],
        compatible_with=["DHT22", "DHT11", "OLED SSD1306", "relays"],
        source="manual",
        description="Budget-friendly WiFi microcontroller, perfect for simple IoT projects"
    ))

    components.append(Component(
        id="esp32_c6_devkit",
        name="ESP32-C6 DevKit",
        category="microcontroller",
        subcategory="wifi_bluetooth_zigbee",
        manufacturer="Espressif",
        part_number="ESP32-C6-DEVKIT-C1",
        cost_usd=12.00,
        specs={
            "cores": 1,
            "cpu_mhz": 160,
            "ram_kb": 512,
            "flash_mb": 4,
            "wifi": "802.11 b/g/n/ax (WiFi 6, 2.4GHz)",
            "bluetooth": "BLE 5.0",
            "zigbee": "IEEE 802.15.4",
            "thread": "Yes",
            "matter": "Yes",
            "gpio_pins": 22,
            "voltage": "3.3V"
        },
        pinout={
            "3V3": "3.3V power output",
            "GND": "Ground",
            "GPIO0-GPIO21": "General purpose I/O"
        },
        datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32-c6_datasheet_en.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/5933",
            "digikey": "https://www.digikey.com/en/products/detail/espressif-systems/ESP32-C6-DEVKITC-1/17860621"
        },
        typical_use_cases=["Matter devices", "WiFi 6 IoT", "Zigbee/Thread networks", "Smart home"],
        compatible_with=["All ESP32 peripherals"],
        source="manual",
        description="Latest ESP32 with WiFi 6, Matter, Zigbee support"
    ))

    # Sensors
    print("Adding Sensors...")

    components.append(Component(
        id="dht22",
        name="DHT22 Temperature and Humidity Sensor",
        category="sensor",
        subcategory="temperature_humidity",
        manufacturer="Aosong",
        part_number="AM2302",
        cost_usd=3.50,
        specs={
            "temperature_range": "-40 to 80°C",
            "temperature_accuracy": "±0.5°C",
            "humidity_range": "0-100%",
            "humidity_accuracy": "±2-5%",
            "sampling_rate": "0.5 Hz (once every 2 seconds)",
            "voltage": "3.3-5V",
            "interface": "Single-wire digital"
        },
        pinout={
            "VCC": "3.3-5V power",
            "DATA": "Digital data pin (needs 4.7k-10k pullup to VCC)",
            "NC": "Not connected",
            "GND": "Ground"
        },
        datasheet_url="https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf",
        buy_links={
            "amazon": "https://www.amazon.com/s?k=DHT22",
            "adafruit": "https://www.adafruit.com/product/385",
            "sparkfun": "https://www.sparkfun.com/products/10167"
        },
        typical_use_cases=["Weather station", "Indoor climate monitoring", "Greenhouse automation"],
        compatible_with=["ESP32", "ESP8266", "Arduino", "Raspberry Pi"],
        source="manual",
        description="Accurate digital temperature and humidity sensor"
    ))

    components.append(Component(
        id="bme280",
        name="BME280 Temperature, Humidity, Pressure Sensor",
        category="sensor",
        subcategory="environmental",
        manufacturer="Bosch",
        part_number="BME280",
        cost_usd=8.00,
        specs={
            "temperature_range": "-40 to 85°C",
            "temperature_accuracy": "±1°C",
            "humidity_range": "0-100%",
            "humidity_accuracy": "±3%",
            "pressure_range": "300-1100 hPa",
            "pressure_accuracy": "±1 hPa",
            "voltage": "3.3V",
            "interface": "I2C or SPI"
        },
        pinout={
            "VCC": "3.3V power",
            "GND": "Ground",
            "SCL": "I2C clock",
            "SDA": "I2C data",
            "CSB": "Chip select (for SPI)",
            "SDO": "SPI data out"
        },
        datasheet_url="https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf",
        buy_links={
            "adafruit": "https://www.adafruit.com/product/2652",
            "sparkfun": "https://www.sparkfun.com/products/13676",
            "amazon": "https://www.amazon.com/s?k=BME280"
        },
        typical_use_cases=["Weather station", "Altitude measurement", "Indoor air quality"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="manual",
        description="All-in-one environmental sensor with temperature, humidity, and barometric pressure"
    ))

    # Displays
    print("Adding Displays...")

    components.append(Component(
        id="oled_ssd1306_128x64",
        name="OLED Display 0.96\" 128x64 SSD1306",
        category="display",
        subcategory="oled",
        manufacturer="Solomon Systech",
        part_number="SSD1306",
        cost_usd=5.00,
        specs={
            "resolution": "128x64 pixels",
            "size": "0.96 inch diagonal",
            "interface": "I2C",
            "voltage": "3.3-5V",
            "colors": "Monochrome (white or blue)",
            "viewing_angle": "160°"
        },
        pinout={
            "VCC": "3.3-5V power",
            "GND": "Ground",
            "SCL": "I2C clock",
            "SDA": "I2C data"
        },
        datasheet_url="https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf",
        buy_links={
            "amazon": "https://www.amazon.com/s?k=SSD1306+OLED",
            "adafruit": "https://www.adafruit.com/product/326",
            "aliexpress": "https://www.aliexpress.com/wholesale?SearchText=ssd1306"
        },
        typical_use_cases=["Status display", "Sensor readouts", "Menu interface"],
        compatible_with=["ESP32", "ESP8266", "Arduino"],
        source="manual",
        description="Small, crisp OLED display perfect for projects"
    ))

    print(f"\n✓ Built database with {len(components)} components")
    print()

    # Show summary
    categories = {}
    for comp in components:
        if comp.category not in categories:
            categories[comp.category] = []
        categories[comp.category].append(comp)

    print("Components by category:")
    for category, comps in categories.items():
        print(f"  {category}: {len(comps)} components")
        for comp in comps:
            print(f"    • {comp.name} - ${comp.cost_usd:.2f}")

    # Save to file
    scraper.save_components(components, "component_database.json")

    print()
    print("="*70)
    print("✓ Component database built successfully!")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. Use WebSearch to find more components")
    print("  2. Use WebFetch to scrape DigiKey/Mouser product pages")
    print("  3. Expand to 100+ components")
    print("="*70)

    return components


if __name__ == '__main__':
    build_manual_database()
