#!/usr/bin/env python3
"""
MASSIVE Database Expansion - Get to 80-100 components
Using aggressive web scraping data
Goal: 100% monetization readiness
"""

import sys
from pathlib import Path

sys.path.insert(0, 'src')

from scrapers.component_database_scraper import ComponentDatabaseScraper, Component


def main():
    print("="*70)
    print("  MASSIVE DATABASE EXPANSION")
    print("  Target: 80-100 components for 100% monetization readiness")
    print("="*70)
    print()

    scraper = ComponentDatabaseScraper()
    existing = scraper.load_components("component_database.json")
    print(f"Starting: {len(existing)} components\n")

    new_components = []

    # =================================================================
    # GAS & AIR QUALITY SENSORS (8 components)
    # =================================================================
    print("Adding Gas & Air Quality Sensors...")

    for sensor_type, part, price, gas in [
        ("MQ-2", "MQ-2", 3.00, "Smoke, LPG, Propane"),
        ("MQ-3", "MQ-3", 3.00, "Alcohol, Ethanol"),
        ("MQ-4", "MQ-4", 3.00, "Methane, CNG"),
        ("MQ-5", "MQ-5", 3.00, "LPG, Natural Gas"),
        ("MQ-7", "MQ-7", 3.50, "Carbon Monoxide"),
        ("MQ-8", "MQ-8", 3.50, "Hydrogen"),
        ("MQ-9", "MQ-9", 3.50, "CO, Flammable Gases"),
        ("MQ-135", "MQ-135", 4.00, "Air Quality, NH3, NOx, Benzene"),
    ]:
        new_components.append(Component(
            id=f"{sensor_type.lower()}_gas_sensor",
            name=f"{sensor_type} Gas Sensor",
            category="sensor",
            subcategory="gas",
            manufacturer="Generic",
            part_number=part,
            cost_usd=price,
            specs={
                "operating_voltage": "5V",
                "preheat_time": "24-48 hours",
                "detects": gas,
                "output": "Analog and Digital",
                "interface": "Analog voltage output"
            },
            pinout={
                "VCC": "5V",
                "GND": "Ground",
                "A0": "Analog output",
                "D0": "Digital output (with comparator)"
            },
            datasheet_url=f"https://www.sparkfun.com/datasheets/Sensors/MQ-{sensor_type[3:]}.pdf",
            buy_links={"amazon": f"https://www.amazon.com/s?k={sensor_type}+sensor"},
            typical_use_cases=["Gas leak detection", "Air quality monitoring", "Safety systems"],
            compatible_with=["Arduino", "ESP32", "ESP8266"],
            source="web_search",
            description=f"Gas sensor for detecting {gas}"
        ))

    # =================================================================
    # CURRENT & VOLTAGE SENSORS (4 components)
    # =================================================================
    print("Adding Current & Voltage Sensors...")

    new_components.extend([
        Component(
            id="acs712_5a",
            name="ACS712 Current Sensor 5A",
            category="sensor",
            subcategory="current",
            manufacturer="Allegro",
            part_number="ACS712-05B",
            cost_usd=2.50,
            specs={
                "max_current": "±5A",
                "sensitivity": "185mV/A",
                "operating_voltage": "5V",
                "output": "Analog voltage (2.5V at 0A)",
                "bandwidth": "80kHz"
            },
            pinout={"VCC": "5V", "GND": "Ground", "OUT": "Analog output"},
            datasheet_url="https://www.allegromicro.com/en/products/sense/current-sensor-ics/zero-to-fifty-amp-integrated-conductor-sensor-ics/acs712",
            buy_links={"amazon": "https://www.amazon.com/s?k=ACS712"},
            typical_use_cases=["Current monitoring", "Power measurement", "Overcurrent protection"],
            compatible_with=["Arduino analog pins"],
            source="web_search",
            description="Hall-effect current sensor for AC/DC measurement"
        ),
        Component(
            id="acs712_20a",
            name="ACS712 Current Sensor 20A",
            category="sensor",
            subcategory="current",
            manufacturer="Allegro",
            part_number="ACS712-20B",
            cost_usd=3.00,
            specs={"max_current": "±20A", "sensitivity": "100mV/A", "operating_voltage": "5V"},
            pinout={"VCC": "5V", "GND": "Ground", "OUT": "Analog output"},
            datasheet_url="https://www.allegromicro.com/en/products/sense/current-sensor-ics/zero-to-fifty-amp-integrated-conductor-sensor-ics/acs712",
            buy_links={"amazon": "https://www.amazon.com/s?k=ACS712+20A"},
            typical_use_cases=["High current monitoring", "Motor control", "Battery management"],
            compatible_with=["Arduino"],
            source="web_search",
            description="20A Hall-effect current sensor"
        ),
        Component(
            id="acs712_30a",
            name="ACS712 Current Sensor 30A",
            category="sensor",
            subcategory="current",
            manufacturer="Allegro",
            part_number="ACS712-30B",
            cost_usd=3.50,
            specs={"max_current": "±30A", "sensitivity": "66mV/A", "operating_voltage": "5V"},
            pinout={"VCC": "5V", "GND": "Ground", "OUT": "Analog output"},
            datasheet_url="https://www.allegromicro.com/en/products/sense/current-sensor-ics/zero-to-fifty-amp-integrated-conductor-sensor-ics/acs712",
            buy_links={"keyestudio": "https://www.keyestudio.com/products/keyestudio-acs712-30a-current-sensor-for-arduino"},
            typical_use_cases=["High power monitoring", "Industrial automation"],
            compatible_with=["Arduino"],
            source="web_search",
            description="30A Hall-effect current sensor for high-power applications"
        ),
        Component(
            id="voltage_sensor_25v",
            name="Voltage Sensor Module 0-25V",
            category="sensor",
            subcategory="voltage",
            manufacturer="Generic",
            part_number="VOLTAGE-SENSOR",
            cost_usd=1.50,
            specs={"input_range": "0-25V DC", "output_voltage": "0-5V", "voltage_divider_ratio": "5:1"},
            pinout={"VCC": "5V", "GND": "Ground", "S": "Signal output"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=voltage+sensor+module"},
            typical_use_cases=["Battery monitoring", "Power supply measurement"],
            compatible_with=["Arduino analog pins"],
            source="manual",
            description="Simple voltage divider for measuring 0-25V"
        )
    ])

    # =================================================================
    # SOUND & MICROPHONE SENSORS (2 components)
    # =================================================================
    print("Adding Sound Sensors...")

    new_components.extend([
        Component(
            id="ky037_microphone",
            name="KY-037 High Sensitivity Microphone",
            category="sensor",
            subcategory="sound",
            manufacturer="Generic",
            part_number="KY-037",
            cost_usd=2.00,
            specs={
                "operating_voltage": "3.3-5V",
                "chip": "LM393 comparator + Electret microphone",
                "sensitivity": "Adjustable via potentiometer",
                "output": "Analog and Digital"
            },
            pinout={"VCC": "3.3-5V", "GND": "Ground", "A0": "Analog output", "D0": "Digital output"},
            datasheet_url="https://kunkune.co.uk/shop/arduino-sensors/ky-037-high-sensitive-sound-microphone-sensor/",
            buy_links={"kunkune": "https://kunkune.co.uk/shop/arduino-sensors/ky-037-high-sensitive-sound-microphone-sensor/"},
            typical_use_cases=["Sound detection", "Voice activated devices", "Clap switch"],
            compatible_with=["Arduino", "ESP32"],
            source="web_search",
            description="Sound sensor with adjustable sensitivity"
        ),
        Component(
            id="sound_sensor_module",
            name="Sound Sensor Module",
            category="sensor",
            subcategory="sound",
            manufacturer="Generic",
            part_number="SOUND-001",
            cost_usd=1.50,
            specs={"operating_voltage": "3.3-5V", "sensitivity": "Fixed", "output": "Digital"},
            pinout={"VCC": "3.3-5V", "GND": "Ground", "OUT": "Digital output"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=sound+sensor+module+arduino"},
            typical_use_cases=["Sound activated switch", "Noise level detection"],
            compatible_with=["Arduino"],
            source="manual",
            description="Simple sound detection module"
        )
    ])

    # =================================================================
    # COMMUNICATION MODULES (7 components)
    # =================================================================
    print("Adding Communication Modules...")

    new_components.extend([
        Component(
            id="hc05_bluetooth",
            name="HC-05 Bluetooth Module",
            category="communication",
            subcategory="bluetooth",
            manufacturer="Generic",
            part_number="HC-05",
            cost_usd=6.00,
            specs={
                "bluetooth_version": "2.0 + EDR",
                "operating_voltage": "3.3V (5V tolerant)",
                "range": "10 meters",
                "baud_rate": "9600 (default, configurable)",
                "modes": "Master and Slave"
            },
            pinout={"VCC": "3.6-6V", "GND": "Ground", "TXD": "UART TX", "RXD": "UART RX (3.3V!)", "STATE": "Connection status"},
            datasheet_url="https://components101.com/wireless/hc-05-bluetooth-module",
            buy_links={"amazon": "https://www.amazon.com/s?k=HC-05+bluetooth"},
            typical_use_cases=["Wireless serial communication", "Robot control", "IoT projects"],
            compatible_with=["Arduino (with level shifter for RX)", "ESP32"],
            source="manual",
            description="Classic Bluetooth 2.0 serial module"
        ),
        Component(
            id="hc06_bluetooth",
            name="HC-06 Bluetooth Module",
            category="communication",
            subcategory="bluetooth",
            manufacturer="Generic",
            part_number="HC-06",
            cost_usd=5.00,
            specs={"bluetooth_version": "2.0", "mode": "Slave only", "operating_voltage": "3.3V", "range": "10 meters"},
            pinout={"VCC": "3.6-6V", "GND": "Ground", "TXD": "UART TX", "RXD": "UART RX (3.3V!)"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=HC-06+bluetooth"},
            typical_use_cases=["Bluetooth serial (slave mode only)"],
            compatible_with=["Arduino with level shifter"],
            source="manual",
            description="Bluetooth module (slave mode only)"
        ),
        Component(
            id="nrf24l01",
            name="NRF24L01 2.4GHz Wireless Module",
            category="communication",
            subcategory="rf",
            manufacturer="Nordic",
            part_number="NRF24L01",
            cost_usd=3.00,
            specs={
                "frequency": "2.4GHz ISM band",
                "operating_voltage": "1.9-3.6V (use 3.3V)",
                "data_rate": "250kbps to 2Mbps",
                "range": "100m (line of sight with PA+LNA)",
                "interface": "SPI"
            },
            pinout={"VCC": "3.3V", "GND": "Ground", "CE": "Chip Enable", "CSN": "SPI Chip Select", "SCK": "SPI Clock", "MOSI": "SPI MOSI", "MISO": "SPI MISO", "IRQ": "Interrupt"},
            datasheet_url="https://www.nordicsemi.com/products/nrf24l01",
            buy_links={"amazon": "https://www.amazon.com/s?k=NRF24L01"},
            typical_use_cases=["Wireless sensor networks", "RC control", "Data transmission"],
            compatible_with=["Arduino", "ESP32"],
            source="manual",
            description="Low-cost 2.4GHz wireless transceiver"
        ),
        Component(
            id="lora_sx1278",
            name="LoRa SX1278 433MHz Module",
            category="communication",
            subcategory="lora",
            manufacturer="Semtech",
            part_number="SX1278",
            cost_usd=8.00,
            specs={
                "frequency": "410-525MHz (433MHz typical)",
                "operating_voltage": "1.8-3.7V (3.3V typical)",
                "range": "Up to 10km (line of sight)",
                "sensitivity": "-148dBm",
                "interface": "SPI"
            },
            pinout={"VCC": "3.3V", "GND": "Ground", "MISO": "SPI MISO", "MOSI": "SPI MOSI", "SCK": "SPI Clock", "NSS": "SPI CS", "RST": "Reset", "DIO0-DIO5": "Digital I/O"},
            datasheet_url="https://www.semtech.com/products/wireless-rf/lora-core/sx1278",
            buy_links={"amazon": "https://www.amazon.com/s?k=SX1278+LoRa"},
            typical_use_cases=["Long-range IoT", "Remote monitoring", "LoRaWAN gateways"],
            compatible_with=["Arduino", "ESP32"],
            source="web_search",
            description="Long-range low-power wireless module"
        ),
        Component(
            id="neo6m_gps",
            name="NEO-6M GPS Module",
            category="communication",
            subcategory="gps",
            manufacturer="u-blox",
            part_number="NEO-6M",
            cost_usd=12.00,
            specs={
                "channels": "50",
                "update_rate": "5Hz (default 1Hz)",
                "accuracy": "2.5m",
                "operating_voltage": "3-5V",
                "interface": "UART (9600 baud)",
                "output": "NMEA sentences"
            },
            pinout={"VCC": "3-5V", "GND": "Ground", "TX": "UART TX", "RX": "UART RX"},
            datasheet_url="https://www.u-blox.com/en/product/neo-6-series",
            buy_links={"amazon": "https://www.amazon.com/s?k=NEO-6M+GPS"},
            typical_use_cases=["GPS tracking", "Location-based projects", "Navigation"],
            compatible_with=["Arduino", "ESP32", "ESP8266"],
            source="web_search",
            description="GPS module with antenna for location tracking"
        ),
        Component(
            id="sim800l_gsm",
            name="SIM800L GSM/GPRS Module",
            category="communication",
            subcategory="cellular",
            manufacturer="SIMCom",
            part_number="SIM800L",
            cost_usd=10.00,
            specs={
                "bands": "850/900/1800/1900MHz",
                "gprs": "Class 10",
                "operating_voltage": "3.4-4.4V",
                "peak_current": "2A",
                "interface": "UART"
            },
            pinout={"VCC": "3.7-4.2V", "GND": "Ground", "TXD": "UART TX", "RXD": "UART RX", "RST": "Reset"},
            datasheet_url="https://www.simcom.com/product/SIM800L.html",
            buy_links={"amazon": "https://www.amazon.com/s?k=SIM800L"},
            typical_use_cases=["SMS/Call projects", "GPRS data", "Remote monitoring"],
            compatible_with=["Arduino with proper power supply"],
            source="manual",
            description="GSM module for SMS, calls, and mobile data"
        ),
        Component(
            id="esp32_cam",
            name="ESP32-CAM Camera Module",
            category="communication",
            subcategory="camera_wifi",
            manufacturer="Espressif",
            part_number="ESP32-CAM",
            cost_usd=10.00,
            specs={
                "camera": "OV2640 2MP",
                "wifi": "802.11 b/g/n",
                "bluetooth": "BLE 4.2",
                "ram": "520KB SRAM",
                "flash": "4MB",
                "sd_card": "MicroSD slot"
            },
            pinout={"5V": "5V input", "GND": "Ground", "U0R": "UART RX (programming)", "U0T": "UART TX", "GPIO0-GPIO16": "GPIO pins"},
            datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=ESP32-CAM"},
            typical_use_cases=["IP camera", "Face recognition", "Photo upload"],
            compatible_with=["Standalone or Arduino IDE"],
            source="manual",
            description="ESP32 with built-in camera for vision projects"
        )
    ])

    # =================================================================
    # DISPLAYS - TFT & LED (6 components)
    # =================================================================
    print("Adding Advanced Displays...")

    new_components.extend([
        Component(
            id="st7735_tft",
            name="1.8\" TFT Display ST7735",
            category="display",
            subcategory="tft",
            manufacturer="Sitronix",
            part_number="ST7735",
            cost_usd=8.00,
            specs={
                "size": "1.8 inch",
                "resolution": "128x160 pixels",
                "colors": "262K (18-bit)",
                "interface": "SPI",
                "operating_voltage": "3.3-5V"
            },
            pinout={"VCC": "3.3-5V", "GND": "Ground", "SCL": "SPI Clock", "SDA": "SPI MOSI", "RES": "Reset", "DC": "Data/Command", "CS": "Chip Select", "BL": "Backlight"},
            datasheet_url="https://www.displayfuture.com/Display/datasheet/controller/ST7735.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=ST7735"},
            typical_use_cases=["Color graphics", "Games", "Data visualization"],
            compatible_with=["Arduino", "ESP32"],
            source="web_search",
            description="Small color TFT display with SPI interface"
        ),
        Component(
            id="ili9341_tft",
            name="2.4\" TFT Display ILI9341",
            category="display",
            subcategory="tft",
            manufacturer="ILI Technology",
            part_number="ILI9341",
            cost_usd=12.00,
            specs={
                "size": "2.4 inch",
                "resolution": "240x320 pixels",
                "colors": "262K (18-bit)",
                "interface": "SPI",
                "touch": "Optional touchscreen"
            },
            pinout={"VCC": "5V", "GND": "Ground", "CS": "Chip Select", "RST": "Reset", "DC": "Data/Command", "SDI": "SPI MOSI", "SCK": "SPI Clock", "LED": "Backlight", "SDO": "SPI MISO"},
            datasheet_url="https://www.displayfuture.com/Display/datasheet/controller/ILI9341.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=ILI9341"},
            typical_use_cases=["Larger color displays", "Touch interfaces", "IoT dashboards"],
            compatible_with=["Arduino Mega", "ESP32"],
            source="manual",
            description="Popular 2.4\" color TFT with touchscreen option"
        ),
        Component(
            id="max7219_7seg",
            name="MAX7219 8-Digit 7-Segment Display",
            category="display",
            subcategory="7segment",
            manufacturer="Maxim",
            part_number="MAX7219",
            cost_usd=5.00,
            specs={
                "digits": "8 digits",
                "operating_voltage": "5V",
                "interface": "SPI",
                "brightness_control": "16 levels",
                "current_limit": "40mA per segment"
            },
            pinout={"VCC": "5V", "GND": "Ground", "DIN": "Data In (SPI MOSI)", "CS": "Chip Select", "CLK": "Clock (SPI SCK)"},
            datasheet_url="https://datasheets.maximintegrated.com/en/ds/MAX7219-MAX7221.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=MAX7219"},
            typical_use_cases=["Digital clocks", "Counters", "Scoreboards"],
            compatible_with=["Arduino"],
            source="manual",
            description="8-digit 7-segment display driver via SPI"
        ),
        Component(
            id="ws2812b_strip",
            name="WS2812B Addressable RGB LED Strip",
            category="display",
            subcategory="led_strip",
            manufacturer="WorldSemi",
            part_number="WS2812B",
            cost_usd=15.00,
            specs={
                "type": "Addressable RGB LED",
                "leds_per_meter": "30, 60, or 144",
                "operating_voltage": "5V",
                "current_per_led": "60mA max (white at full brightness)",
                "colors": "16.7 million (24-bit)",
                "protocol": "One-wire serial"
            },
            pinout={"5V": "5V power", "GND": "Ground", "DIN": "Data input"},
            datasheet_url="https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=WS2812B", "adafruit": "https://www.adafruit.com/product/1138"},
            typical_use_cases=["Decorative lighting", "Ambient displays", "LED art"],
            compatible_with=["Arduino", "ESP32"],
            source="web_search",
            description="Individually addressable RGB LED strip"
        ),
        Component(
            id="neopixel_ring",
            name="NeoPixel Ring 12 LED",
            category="display",
            subcategory="led_ring",
            manufacturer="Adafruit",
            part_number="NeoPixel-Ring-12",
            cost_usd=7.50,
            specs={"leds": "12", "type": "WS2812B", "diameter": "44.5mm", "operating_voltage": "5V"},
            pinout={"5V": "Power", "GND": "Ground", "IN": "Data input", "OUT": "Data output (chainable)"},
            datasheet_url="",
            buy_links={"adafruit": "https://www.adafruit.com/product/1643"},
            typical_use_cases=["Circular displays", "Status indicators", "Wearables"],
            compatible_with=["Arduino"],
            source="manual",
            description="12 WS2812B LEDs in circular arrangement"
        ),
        Component(
            id="tm1637_4digit",
            name="TM1637 4-Digit 7-Segment Display",
            category="display",
            subcategory="7segment",
            manufacturer="Titan Micro",
            part_number="TM1637",
            cost_usd=2.00,
            specs={"digits": "4", "operating_voltage": "3.3-5V", "interface": "2-wire (CLK, DIO)", "brightness": "8 levels"},
            pinout={"VCC": "3.3-5V", "GND": "Ground", "CLK": "Clock", "DIO": "Data I/O"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=TM1637"},
            typical_use_cases=["Simple clocks", "Timers", "Temperature displays"],
            compatible_with=["Arduino"],
            source="manual",
            description="Cheap 4-digit display with clock module"
        )
    ])

    # =================================================================
    # INPUT DEVICES (4 components)
    # =================================================================
    print("Adding Input Devices...")

    new_components.extend([
        Component(
            id="ky040_encoder",
            name="KY-040 Rotary Encoder",
            category="input",
            subcategory="encoder",
            manufacturer="Generic",
            part_number="KY-040",
            cost_usd=2.50,
            specs={
                "operating_voltage": "5V",
                "pulses_per_revolution": "20",
                "detents": "20",
                "switch": "Push button integrated"
            },
            pinout={"VCC": "5V", "GND": "Ground", "CLK": "Clock output A", "DT": "Data output B", "SW": "Switch (push button)"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=KY-040"},
            typical_use_cases=["Volume control", "Menu navigation", "Value adjustment"],
            compatible_with=["Arduino"],
            source="manual",
            description="Rotary encoder with push button"
        ),
        Component(
            id="joystick_module",
            name="Analog Joystick Module",
            category="input",
            subcategory="joystick",
            manufacturer="Generic",
            part_number="JOYSTICK-XY",
            cost_usd=3.00,
            specs={
                "axes": "2 (X and Y)",
                "operating_voltage": "5V",
                "output": "Analog (0-5V on each axis)",
                "button": "Push button (Z axis)"
            },
            pinout={"VCC": "5V", "GND": "Ground", "VRx": "X-axis analog", "VRy": "Y-axis analog", "SW": "Button"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=arduino+joystick+module"},
            typical_use_cases=["Game controllers", "Robot control", "Camera pan/tilt"],
            compatible_with=["Arduino analog pins"],
            source="manual",
            description="2-axis analog joystick with button"
        ),
        Component(
            id="keypad_4x4",
            name="4x4 Matrix Keypad",
            category="input",
            subcategory="keypad",
            manufacturer="Generic",
            part_number="KEYPAD-4X4",
            cost_usd=3.50,
            specs={"keys": "16 keys (4x4 matrix)", "operating_voltage": "5V", "interface": "8 digital pins (4 rows + 4 cols)"},
            pinout={"ROW1-ROW4": "Row pins", "COL1-COL4": "Column pins"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=4x4+keypad"},
            typical_use_cases=["Password entry", "Calculators", "Phone interfaces"],
            compatible_with=["Arduino"],
            source="manual",
            description="16-key membrane keypad"
        ),
        Component(
            id="capacitive_touch",
            name="TTP223 Capacitive Touch Sensor",
            category="input",
            subcategory="touch",
            manufacturer="Generic",
            part_number="TTP223",
            cost_usd=1.50,
            specs={"operating_voltage": "2-5.5V", "output": "Digital (HIGH when touched)", "mode": "Toggle or momentary"},
            pinout={"VCC": "2-5.5V", "GND": "Ground", "SIG": "Signal output"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=TTP223"},
            typical_use_cases=["Touch buttons", "Capacitive switches", "Interactive projects"],
            compatible_with=["Arduino"],
            source="manual",
            description="Single-key capacitive touch sensor"
        )
    ])

    # =================================================================
    # POWER MODULES (3 components)
    # =================================================================
    print("Adding Power Modules...")

    new_components.extend([
        Component(
            id="lm2596_buck",
            name="LM2596 DC-DC Buck Converter",
            category="power",
            subcategory="buck_converter",
            manufacturer="Texas Instruments",
            part_number="LM2596",
            cost_usd=2.00,
            specs={
                "input_voltage": "4-40V",
                "output_voltage": "1.25-37V (adjustable)",
                "max_current": "3A",
                "efficiency": "Up to 92%",
                "switching_frequency": "150kHz"
            },
            pinout={"IN+": "Input positive", "IN-": "Input negative/Ground", "OUT+": "Output positive", "OUT-": "Output negative/Ground"},
            datasheet_url="https://www.ti.com/lit/ds/symlink/lm2596.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=LM2596"},
            typical_use_cases=["Voltage reduction", "Battery regulation", "Power supplies"],
            compatible_with=["Any project needing voltage step-down"],
            source="manual",
            description="Adjustable step-down switching regulator"
        ),
        Component(
            id="mt3608_boost",
            name="MT3608 DC-DC Boost Converter",
            category="power",
            subcategory="boost_converter",
            manufacturer="Generic",
            part_number="MT3608",
            cost_usd=1.50,
            specs={
                "input_voltage": "2-24V",
                "output_voltage": "5-28V (adjustable)",
                "max_current": "2A",
                "efficiency": "Up to 93%"
            },
            pinout={"IN+": "Input positive", "IN-": "Input negative", "OUT+": "Output positive", "OUT-": "Output negative"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=MT3608"},
            typical_use_cases=["Voltage boost", "Battery projects", "LED drivers"],
            compatible_with=["Any project needing voltage step-up"],
            source="manual",
            description="Step-up voltage booster"
        ),
        Component(
            id="tp4056_charger",
            name="TP4056 Lithium Battery Charger",
            category="power",
            subcategory="battery_charger",
            manufacturer="Generic",
            part_number="TP4056",
            cost_usd=1.00,
            specs={
                "input": "5V (Micro USB)",
                "charge_current": "1A (default)",
                "battery_type": "Single cell Li-Ion/LiPo (3.7V)",
                "protection": "Overcharge, overdischarge, overcurrent"
            },
            pinout={"IN+": "5V input", "IN-": "Ground", "B+": "Battery positive", "B-": "Battery negative", "OUT+": "Output positive", "OUT-": "Output negative"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=TP4056"},
            typical_use_cases=["Battery charging", "Portable projects", "Power banks"],
            compatible_with=["3.7V Li-Ion/LiPo batteries"],
            source="manual",
            description="Li-Ion battery charger with protection"
        )
    ])

    # =================================================================
    # ADDITIONAL SENSORS (5 components)
    # =================================================================
    print("Adding More Sensors...")

    new_components.extend([
        Component(
            id="tsl2561_light",
            name="TSL2561 Luminosity Sensor",
            category="sensor",
            subcategory="light_lux",
            manufacturer="AMS",
            part_number="TSL2561",
            cost_usd=6.00,
            specs={"range": "0.1 - 40,000 lux", "interface": "I2C", "operating_voltage": "2.7-3.6V (3.3V typical)", "i2c_address": "0x29, 0x39, or 0x49"},
            pinout={"VCC": "2.7-3.6V", "GND": "Ground", "SDA": "I2C Data", "SCL": "I2C Clock"},
            datasheet_url="https://ams.com/tsl2561",
            buy_links={"adafruit": "https://www.adafruit.com/product/439"},
            typical_use_cases=["Accurate lux measurement", "Auto-brightness", "Light meters"],
            compatible_with=["Arduino", "ESP32"],
            source="manual",
            description="Precision light-to-digital converter"
        ),
        Component(
            id="soil_moisture",
            name="Soil Moisture Sensor",
            category="sensor",
            subcategory="moisture",
            manufacturer="Generic",
            part_number="SOIL-001",
            cost_usd=2.00,
            specs={"operating_voltage": "3.3-5V", "output": "Analog (capacitive) or Digital", "measurement": "Soil moisture/humidity"},
            pinout={"VCC": "3.3-5V", "GND": "Ground", "A0": "Analog output", "D0": "Digital output (optional)"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=soil+moisture+sensor"},
            typical_use_cases=["Plant watering", "Garden automation", "Agriculture"],
            compatible_with=["Arduino"],
            source="manual",
            description="Capacitive soil moisture sensor"
        ),
        Component(
            id="water_level",
            name="Water Level Sensor",
            category="sensor",
            subcategory="water",
            manufacturer="Generic",
            part_number="WATER-001",
            cost_usd=1.50,
            specs={"operating_voltage": "3-5V", "output": "Analog", "detection": "Water presence and level"},
            pinout={"VCC": "3-5V", "GND": "Ground", "S": "Analog signal"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=water+level+sensor"},
            typical_use_cases=["Water tank monitoring", "Flood detection", "Aquarium automation"],
            compatible_with=["Arduino"],
            source="manual",
            description="Water level and rain detection sensor"
        ),
        Component(
            id="flame_sensor",
            name="Flame Sensor Module",
            category="sensor",
            subcategory="flame",
            manufacturer="Generic",
            part_number="FLAME-001",
            cost_usd=2.00,
            specs={"detection_range": "60 degrees", "detection_distance": "80cm", "wavelength": "760-1100nm (IR)", "output": "Digital and Analog"},
            pinout={"VCC": "3.3-5V", "GND": "Ground", "D0": "Digital output", "A0": "Analog output"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=flame+sensor"},
            typical_use_cases=["Fire detection", "Safety systems", "Robot firefighter"],
            compatible_with=["Arduino"],
            source="manual",
            description="IR flame detection sensor"
        ),
        Component(
            id="rain_sensor",
            name="Rain Drop Sensor",
            category="sensor",
            subcategory="rain",
            manufacturer="Generic",
            part_number="RAIN-001",
            cost_usd=1.50,
            specs={"operating_voltage": "3.3-5V", "output": "Analog and Digital", "sensitivity": "Adjustable"},
            pinout={"VCC": "3.3-5V", "GND": "Ground", "A0": "Analog output", "D0": "Digital output"},
            datasheet_url="",
            buy_links={"amazon": "https://www.amazon.com/s?k=rain+sensor"},
            typical_use_cases=["Weather stations", "Auto window closers", "Irrigation control"],
            compatible_with=["Arduino"],
            source="manual",
            description="Raindrop detection sensor"
        )
    ])

    # =================================================================
    # MOTOR DRIVERS (3 components)
    # =================================================================
    print("Adding Motor Drivers...")

    new_components.extend([
        Component(
            id="l298n_driver",
            name="L298N Motor Driver",
            category="actuator",
            subcategory="motor_driver",
            manufacturer="STMicroelectronics",
            part_number="L298N",
            cost_usd=4.00,
            specs={
                "channels": "2 (dual H-bridge)",
                "max_voltage": "46V",
                "max_current": "2A per channel (4A peak)",
                "logic_voltage": "5V",
                "motor_voltage": "5-35V"
            },
            pinout={"IN1-IN4": "Motor control inputs", "ENA, ENB": "Enable pins (PWM for speed)", "OUT1-OUT4": "Motor outputs", "12V": "Motor power input", "5V": "Logic power (or output from onboard regulator)", "GND": "Ground"},
            datasheet_url="https://www.st.com/resource/en/datasheet/l298.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=L298N"},
            typical_use_cases=["DC motor control", "Robot drive", "2-wheel robots"],
            compatible_with=["Arduino"],
            source="manual",
            description="Dual H-bridge motor driver for 2 DC motors"
        ),
        Component(
            id="tb6612_driver",
            name="TB6612FNG Motor Driver",
            category="actuator",
            subcategory="motor_driver",
            manufacturer="Toshiba",
            part_number="TB6612FNG",
            cost_usd=5.00,
            specs={
                "channels": "2",
                "max_voltage": "15V",
                "continuous_current": "1.2A per channel",
                "peak_current": "3.2A",
                "efficiency": "Higher than L298N"
            },
            pinout={"PWMA, PWMB": "PWM speed control", "AIN1, AIN2, BIN1, BIN2": "Direction control", "A01, A02, B01, B02": "Motor outputs", "VM": "Motor power (2.5-13.5V)", "VCC": "Logic power (2.7-5.5V)", "GND": "Ground", "STBY": "Standby"},
            datasheet_url="",
            buy_links={"adafruit": "https://www.adafruit.com/product/2448"},
            typical_use_cases=["Small DC motors", "Efficient motor control", "Battery-powered robots"],
            compatible_with=["Arduino"],
            source="manual",
            description="Efficient dual motor driver (better than L298N)"
        ),
        Component(
            id="drv8825_stepper",
            name="DRV8825 Stepper Driver",
            category="actuator",
            subcategory="stepper_driver",
            manufacturer="Texas Instruments",
            part_number="DRV8825",
            cost_usd=6.00,
            specs={
                "max_voltage": "45V",
                "max_current": "2.2A per coil",
                "microstepping": "1, 1/2, 1/4, 1/8, 1/16, 1/32",
                "interface": "STEP/DIR"
            },
            pinout={"VMOT": "Motor power (8.2-45V)", "GND": "Ground", "STEP": "Step input", "DIR": "Direction", "EN": "Enable", "MS1, MS2, MS3": "Microstepping", "RST": "Reset", "SLP": "Sleep", "A1, A2, B1, B2": "Motor coils"},
            datasheet_url="https://www.ti.com/lit/ds/symlink/drv8825.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=DRV8825"},
            typical_use_cases=["3D printers", "CNC machines", "Precise stepper control"],
            compatible_with=["Arduino"],
            source="manual",
            description="Advanced stepper motor driver with microstepping"
        )
    ])

    # =================================================================
    # REAL-TIME CLOCKS (2 components)
    # =================================================================
    print("Adding Real-Time Clocks...")

    new_components.extend([
        Component(
            id="ds1307_rtc",
            name="DS1307 RTC Module",
            category="timekeeping",
            subcategory="rtc",
            manufacturer="Maxim",
            part_number="DS1307",
            cost_usd=3.00,
            specs={
                "interface": "I2C",
                "operating_voltage": "5V",
                "battery_backup": "CR2032 coin cell",
                "accuracy": "±2 minutes/month",
                "features": "56 bytes RAM"
            },
            pinout={"VCC": "5V", "GND": "Ground", "SDA": "I2C Data", "SCL": "I2C Clock", "SQW": "Square wave output"},
            datasheet_url="https://datasheets.maximintegrated.com/en/ds/DS1307.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=DS1307"},
            typical_use_cases=["Digital clocks", "Data loggers", "Timers"],
            compatible_with=["Arduino"],
            source="manual",
            description="I2C real-time clock with battery backup"
        ),
        Component(
            id="ds3231_rtc",
            name="DS3231 Precision RTC",
            category="timekeeping",
            subcategory="rtc_precision",
            manufacturer="Maxim",
            part_number="DS3231",
            cost_usd=5.00,
            specs={
                "interface": "I2C",
                "operating_voltage": "2.3-5.5V",
                "battery_backup": "CR2032",
                "accuracy": "±2 ppm (±1 minute/year)",
                "temperature_compensated": "Yes (TCXO)"
            },
            pinout={"VCC": "2.3-5.5V", "GND": "Ground", "SDA": "I2C Data", "SCL": "I2C Clock", "SQW": "Square wave/interrupt", "32K": "32.768kHz output"},
            datasheet_url="https://datasheets.maximintegrated.com/en/ds/DS3231.pdf",
            buy_links={"amazon": "https://www.amazon.com/s?k=DS3231"},
            typical_use_cases=["Precision clocks", "Long-term data logging", "Alarms"],
            compatible_with=["Arduino", "ESP32"],
            source="manual",
            description="High-precision temperature-compensated RTC"
        )
    ])

    print(f"\n✓ Added {len(new_components)} new components!")

    # Merge and save
    all_components = scraper.merge_components(new_components, existing)

    print(f"\nTotal components: {len(all_components)}")

    # Summary
    categories = {}
    for comp in all_components:
        if comp.category not in categories:
            categories[comp.category] = []
        categories[comp.category].append(comp)

    print("\n" + "="*70)
    print("  FINAL DATABASE SUMMARY")
    print("="*70)

    for category, comps in sorted(categories.items()):
        print(f"\n{category.upper()}: {len(comps)} components")
        print("-"*70)
        for comp in sorted(comps, key=lambda x: x.cost_usd)[:10]:  # Show first 10
            print(f"  ${comp.cost_usd:6.2f}  {comp.name}")
        if len(comps) > 10:
            print(f"  ... and {len(comps)-10} more")

    scraper.save_components(all_components, "component_database.json")

    print("\n" + "="*70)
    print(f"✓ DATABASE EXPANDED TO {len(all_components)} COMPONENTS!")
    print("="*70)
    print(f"\nProgress: {len(all_components)}/100 components ({len(all_components)}%)")
    print("\nMonetization readiness: SIGNIFICANTLY IMPROVED")
    print("="*70)


if __name__ == '__main__':
    main()
